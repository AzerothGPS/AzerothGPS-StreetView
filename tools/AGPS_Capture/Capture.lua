-- AzerothGPS StreetView capture (developer tool, never shipped or published). Fully manual:
-- this addon never moves the character or the camera. You turn yourself (right mouse button)
-- and set the camera angle with the game's own "Set View" keys; the addon shows a guide with
-- which shot is next and how far to turn, hides names and the interface for the shots, and
-- takes one screenshot each time you press its key. tools/sv.py import turns the screenshots
-- into the StreetView data pack. (The automated capture lives in the separate harvester repo,
-- for a private server only.)
--
-- One-time setup, in first person (mouse wheel all the way in), turning with the RIGHT mouse
-- button so the camera stays straight ahead of your character:
--   look level at the horizon      /svcap save level     (saves the game's camera view 2)
--   look up about 50 degrees       /svcap save up        (view 3)
--   look down about 50 degrees     /svcap save down      (view 4)
--   look straight up               /svcap save zenith    (view 5)
-- Bind the game's own "Set View 2" to "Set View 5" keys (Key Bindings > Camera) and this
-- addon's "Capture a street view shot" key (Key Bindings > AddOns).

local addonName = ...
local C = AGPSCapture -- Poses.lua

BINDING_HEADER_AGPSC = "AzerothGPS StreetView capture"
BINDING_NAME_AGPSC_CAPTURE = "Capture a street view shot"

local TOLERANCE = math.rad(4) -- how close to the asked direction a shot must be
local HIDE_DELAY = 0.15 -- seconds between hiding the guide and the screenshot
local SHOT_GAP = 1.1 -- screenshot files are named to the second: at most one a second
local SHOT_TIMEOUT = 4 -- seconds to wait for the game to say the screenshot was saved
local MOVE_LIMIT = 1 -- yards: walking away cancels the spot

-- The clean look: no names, nameplates, bubbles or target icons. Only the ones this client
-- has are touched, and all are put back afterwards.
local CLEAN = {
  nameplateShowAll = "0", nameplateShowEnemies = "0", nameplateShowFriends = "0",
  nameplateShowFriendlyNPCs = "0", nameplateShowSelf = "0",
  UnitNameNPC = "0", UnitNameHostleNPC = "0", UnitNameInteractiveNPC = "0",
  UnitNameFriendlySpecialNPCName = "0", UnitNameNonCombatCreatureName = "0",
  UnitNameEnemyPlayerName = "0", UnitNameFriendlyPlayerName = "0", UnitNameOwn = "0",
  UnitNameEnemyPetName = "0", UnitNameFriendlyPetName = "0",
  UnitNameEnemyGuardianName = "0", UnitNameFriendlyGuardianName = "0",
  UnitNameEnemyTotemName = "0", UnitNameFriendlyTotemName = "0",
  UnitNamePlayerGuild = "0", UnitNamePlayerPVPTitle = "0",
  chatBubbles = "0", chatBubblesParty = "0",
  SoftTargetIconGameObject = "0", SoftTargetIconInteract = "0", SoftTargetIconEnemy = "0",
  SoftTargetIconFriend = "0", SoftTargetNameplateEnemy = "0", SoftTargetNameplateFriend = "0",
  SoftTargetNameplateInteract = "0",
  ShowQuestUnitCircles = "0", occludedSilhouettePlayer = "0",
  screenshotFormat = "jpeg", screenshotQuality = "10",
}

local run -- the spot being captured
local saved -- cvars to put back
local guide, lines

local function Say(msg) print("|cff4da6ffStreetView capture:|r " .. msg) end

local function GetCVarSafe(name)
  if C_CVar and C_CVar.GetCVar then return C_CVar.GetCVar(name) end
  return GetCVar(name)
end
local function SetCVarSafe(name, value)
  if C_CVar and C_CVar.SetCVar then return pcall(C_CVar.SetCVar, name, value) end
  return pcall(SetCVar, name, value)
end

-- Hide or show the interface (what Alt+Z does), falling back to UIParent.
local function UIVisible(on)
  if not (SetUIVisibility and pcall(SetUIVisibility, on)) then
    if on then UIParent:Show() else UIParent:Hide() end
  end
end

local function Clean()
  saved = {}
  for name, value in pairs(CLEAN) do
    local old = GetCVarSafe(name)
    if old ~= nil then
      saved[name] = old
      SetCVarSafe(name, value)
    end
  end
  UIVisible(false)
end

local function Restore()
  for name, value in pairs(saved or {}) do SetCVarSafe(name, value) end
  saved = nil
  UIVisible(true)
end

local function KeyName()
  local key = GetBindingKey("AGPSC_CAPTURE")
  return key and GetBindingText(key) or "your capture key (Key Bindings > AddOns)"
end

-- Watch the game's own "Set View" key presses when they go through Lua, so the guide can
-- tell whether the right view was set after the last turn. (Only watching: never called.)
hooksecurefunc("SetView", function(n)
  if run then
    run.viewSeen, run.lastView, run.viewFacing = true, n, GetPlayerFacing()
  end
end)

-- What still has to happen before this step's shot: nil when ready, else a line to show.
local function Pending(step)
  local facing = GetPlayerFacing()
  local off = C.AngleDiff(C.Target(run.facing0, step.turns), facing)
  if math.abs(off) > TOLERANCE then
    return string.format("Turn %s %d degrees (right mouse button)", off < 0 and "right" or "left",
      math.floor(math.abs(math.deg(off)) + 0.5))
  end
  local want = C.VIEWS[step.view]
  if want and run.viewSeen and (run.lastView ~= want or math.abs(C.AngleDiff(facing, run.viewFacing)) > math.rad(1)) then
    return "Press your Set View " .. want .. " key (" .. C.LABEL[step.view] .. ")"
  end
end

local function Refresh()
  if not run then return end
  local step = C.SEQUENCE[run.i]
  lines[1]:SetText(string.format("Street view capture  -  shot %d of %d", run.i, #C.SEQUENCE))
  if step.view == "nadir" then
    lines[2]:SetText("Camera: hold the right mouse button and look all the way down")
  else
    lines[2]:SetText("Camera: Set View " .. C.VIEWS[step.view] .. " (" .. C.LABEL[step.view] .. ")")
  end
  local todo = Pending(step)
  if todo then
    lines[3]:SetText("|cffffd100" .. todo .. "|r")
  else
    lines[3]:SetText("|cff40ff40Ready: press " .. KeyName() .. "|r")
  end
  lines[4]:SetText("|cff999999Take a step to cancel this spot.|r")
end

local function BuildGuide()
  -- on WorldFrame, so it stays visible while the interface is hidden
  guide = CreateFrame("Frame", nil, WorldFrame, "BackdropTemplate")
  guide:SetFrameStrata("TOOLTIP")
  guide:SetScale(UIParent:GetEffectiveScale() / WorldFrame:GetEffectiveScale())
  guide:SetSize(480, 92)
  guide:SetPoint("TOP", WorldFrame, "TOP", 0, -40)
  if guide.SetBackdrop then
    guide:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
    guide:SetBackdropColor(0, 0, 0, 0.75)
    guide:SetBackdropBorderColor(0.3, 0.55, 0.9, 1)
  end
  lines = {}
  local fonts = { "GameFontNormalLarge", "GameFontHighlight", "GameFontHighlight", "GameFontHighlightSmall" }
  for i = 1, 4 do
    local fs = guide:CreateFontString(nil, "OVERLAY", fonts[i])
    fs:SetPoint("TOP", 0, -8 - (i - 1) * 20)
    lines[i] = fs
  end
  local wait = 0
  guide:SetScript("OnUpdate", function(_, dt)
    wait = wait - dt
    if wait > 0 or not run then return end
    wait = 0.05
    local x, y = UnitPosition("player")
    if not x or (x - run.x) ^ 2 + (y - run.y) ^ 2 > MOVE_LIMIT ^ 2 then
      AGPSCapture_Stop("you moved.")
      return
    end
    if not run.waiting then Refresh() end
  end)
  guide:Hide()
end

local function Finish(done, why)
  if not run then return end
  local r = run
  run = nil
  guide:Hide()
  Restore()
  r.done, r.why = done, why
  r.i, r.waiting, r.lastShot, r.viewSeen, r.lastView, r.viewFacing = nil, nil, nil, nil, nil, nil
  if done then
    Say(string.format("spot #%d done (%d shots). Go to the next spot, or /reload and run the import.", r.n, #r.shots))
  else
    Say("|cffff6060spot cancelled:|r " .. tostring(why) .. " The import skips it.")
  end
end

function AGPSCapture_Stop(why)
  Finish(false, why or "stopped by you.")
end

local function Start()
  local db = AGPSCaptureDB
  for key in pairs(C.VIEWS) do
    if not db.views[key] then
      Say("|cffff6060set up the camera views first|r (/svcap help): '" .. key .. "' is missing.")
      return
    end
  end
  if InCombatLockdown() then return Say("not in combat.") end
  if IsMounted() then return Say("get off your mount first (the camera would be too high).") end
  if UnitExists("target") then return Say("clear your target first (Escape).") end
  local x, y, z, cont = UnitPosition("player")
  if not x then return Say("your position isn't available here.") end
  run = {
    n = #db.captures + 1, i = 1, lastShot = 0, shots = {},
    x = x, y = y, z = z, cont = cont, facing = GetPlayerFacing(),
    mapID = C_Map.GetBestMapForUnit("player"), zone = GetZoneText(), subzone = GetSubZoneText(),
    time = time(), date = date("%Y-%m-%d %H:%M:%S"), build = select(2, GetBuildInfo()),
  }
  run.facing0 = run.facing
  db.captures[#db.captures + 1] = run
  if not guide then BuildGuide() end
  Clean()
  guide:Show()
  Refresh()
end

local function Shoot()
  local step = C.SEQUENCE[run.i]
  local todo = Pending(step)
  if todo then
    lines[3]:SetText("|cffff6060Not yet:|r " .. todo)
    return
  end
  run.waiting = run.i
  guide:Hide()
  local delay = math.max(HIDE_DELAY, run.lastShot + SHOT_GAP - GetTime())
  C_Timer.After(delay, function()
    if not run then return end
    local facing = GetPlayerFacing()
    run.lastShot = GetTime()
    -- the file name the game gives it (to the second; sv.py also looks a second or two later)
    run.shots[#run.shots + 1] = { pose = C.ShotName(step, run.facing0, facing), facing = facing,
      file = date("WoWScrnShot_%m%d%y_%H%M%S") }
    Screenshot()
    local i = run.i
    C_Timer.After(SHOT_TIMEOUT, function()
      if run and run.waiting == i then
        run.shots[#run.shots].timeout = true
        AGPSCapture_Saved()
      end
    end)
  end)
end

-- The screenshot is on disk (or timed out): next shot, or the spot is done.
function AGPSCapture_Saved()
  if not run or not run.waiting then return end
  run.waiting = nil
  run.i = run.i + 1
  if run.i > #C.SEQUENCE then
    Finish(true)
  else
    guide:Show()
    Refresh()
  end
end

-- The key: starts a spot where you stand, then takes each shot.
function AGPSCapture_Key()
  if not run then
    Start()
  elseif not run.waiting then
    Shoot()
  end
end

local ev = CreateFrame("Frame")
ev:RegisterEvent("ADDON_LOADED")
ev:RegisterEvent("SCREENSHOT_SUCCEEDED")
ev:RegisterEvent("SCREENSHOT_FAILED")
ev:RegisterEvent("PLAYER_REGEN_DISABLED")
ev:SetScript("OnEvent", function(_, event, arg1)
  if event == "ADDON_LOADED" and arg1 == addonName then
    AGPSCaptureDB = type(AGPSCaptureDB) == "table" and AGPSCaptureDB or {}
    AGPSCaptureDB.views = AGPSCaptureDB.views or {}
    AGPSCaptureDB.captures = AGPSCaptureDB.captures or {}
  elseif event == "SCREENSHOT_SUCCEEDED" or event == "SCREENSHOT_FAILED" then
    if run and run.waiting then
      if event == "SCREENSHOT_FAILED" then run.shots[#run.shots].failed = true end
      AGPSCapture_Saved()
    end
  elseif event == "PLAYER_REGEN_DISABLED" then
    AGPSCapture_Stop("combat started.")
  end
end)

SLASH_AGPSCAPTURE1 = "/svcap"
SlashCmdList.AGPSCAPTURE = function(msg)
  local cmd, arg = strtrim(msg or ""):lower():match("^(%S*)%s*(.-)$")
  local db = AGPSCaptureDB
  if cmd == "save" and C.VIEWS[arg] then
    SaveView(C.VIEWS[arg]) -- (stores the camera angle you set by hand; doesn't move anything)
    db.views[arg] = true
    Say("saved the '" .. arg .. "' camera angle as the game's view " .. C.VIEWS[arg] .. ".")
  elseif cmd == "go" then
    AGPSCapture_Key()
  elseif cmd == "stop" then
    AGPSCapture_Stop()
  elseif cmd == "status" then
    local have = {}
    for key in pairs(C.VIEWS) do have[#have + 1] = key .. (db.views[key] and " ok" or " MISSING") end
    Say("views: " .. table.concat(have, ", ") .. string.format(". %d spots captured.", #db.captures))
  elseif cmd == "clear" then
    db.captures = {}
    Say("forgot all captured spots (the screenshots stay in the Screenshots folder).")
  else
    Say("one-time setup in first person, turning with the RIGHT mouse button:")
    Say("  look level: /svcap save level    up ~50: /svcap save up")
    Say("  down ~50: /svcap save down    straight up: /svcap save zenith")
    Say("  (steeper up and down views leave no gaps above and below in the panorama)")
    Say("bind the game's Set View 2-5 keys (Key Bindings > Camera) and the capture key (> AddOns).")
    Say("then stand on a road, not mounted, no target, and press the capture key: a guide")
    Say("shows which way to turn and which view key to press for each of the 28 shots.")
    Say("/svcap status, /svcap stop, /svcap clear")
  end
end
