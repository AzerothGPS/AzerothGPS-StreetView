-- AzerothGPS StreetView capture (developer tool, never shipped or published).
-- Where you stand, one key press takes the 26 views of a street view: rings of 8 (45 degrees
-- apart) looking down, level and up, plus straight up and straight down. It only turns the
-- camera (saved camera views + FlipCameraYaw), hides the interface and names for the shots,
-- and calls Screenshot(); you do all the moving. tools/sv.py import turns the screenshots
-- into the StreetView data pack.
--
-- One-time setup, in first person (mouse wheel all the way in), turning with the RIGHT mouse
-- button so the camera stays straight behind your eyes:
--   look level at the horizon      /svcap save level
--   look up about 45 degrees       /svcap save up
--   look down about 45 degrees     /svcap save down
--   look straight up               /svcap save zenith
-- These overwrite the game's camera views 2 to 5. Then bind a key (Key Bindings > AddOns >
-- "Capture a street view here") or type /svcap go.

local addonName = ...

BINDING_HEADER_AGPSC = "AzerothGPS StreetView capture"
BINDING_NAME_AGPSC_CAPTURE = "Capture a street view here"

local VIEW = { level = 2, up = 3, down = 4, zenith = 5 }
local SETTLE = 0.5 -- seconds after turning the camera before the shot
local SHOT_GAP = 1.1 -- screenshot files are named to the second: at most one a second
local SHOT_TIMEOUT = 4 -- seconds to wait for the game to say the screenshot was saved
local NADIR_PITCH = 1.5 -- seconds of pitching down from the down view (hits the limit)

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

-- The 26 shots in order: { name, view, yaw steps of 45 degrees, nadir }. Names match the
-- viewer's (Data.lua D.PoseName).
local POSES = {}
local function Pose(name, view, yaw, nadir) POSES[#POSES + 1] = { name = name, view = view, yaw = yaw, nadir = nadir } end
for i = 0, 7 do Pose(string.format("y%03d_p+00", i * 45), "level", i) end
for i = 0, 7 do Pose(string.format("y%03d_p+45", i * 45), "up", i) end
for i = 0, 7 do Pose(string.format("y%03d_p-45", i * 45), "down", i) end
Pose("y000_p+90", "zenith", 0)
Pose("y000_p-90", "down", 0, true)

local run -- the capture in progress
local saved -- cvars to put back
local Finish

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
  if MoveViewDownStop then MoveViewDownStop() end
  for name, value in pairs(saved or {}) do SetCVarSafe(name, value) end
  saved = nil
  UIVisible(true)
  SetView(VIEW.level)
end

local function Ready()
  local db = AGPSCaptureDB
  for key in pairs(VIEW) do
    if not db.views[key] then
      return false, "set up the camera views first (/svcap help): '" .. key .. "' is missing."
    end
  end
  if InCombatLockdown() then return false, "not in combat." end
  if GetUnitSpeed("player") > 0 then return false, "stand still." end
  if IsMounted() then return false, "get off your mount (the camera would be too high)." end
  if UnitExists("target") then return false, "clear your target first (Escape)." end
  if not UnitPosition("player") then return false, "your position isn't available here." end
  return true
end

local Step

local function Shoot()
  if not run then return end
  local wait = run.lastShot + SHOT_GAP - GetTime()
  if wait > 0 then
    C_Timer.After(wait, Shoot)
    return
  end
  local pose = POSES[run.i]
  run.lastShot = GetTime()
  run.waiting = run.i
  -- the file name the game gives it (to the second; sv.py also looks a second either side)
  run.shots[#run.shots + 1] = { pose = pose.name, file = date("WoWScrnShot_%m%d%y_%H%M%S") }
  Screenshot()
  local i = run.i
  C_Timer.After(SHOT_TIMEOUT, function()
    if run and run.waiting == i then
      run.shots[#run.shots].timeout = true
      run.waiting = nil
      run.i = run.i + 1
      Step()
    end
  end)
end

function Step()
  if not run then return end
  local pose = POSES[run.i]
  if not pose then
    Finish(true)
    return
  end
  SetView(VIEW[pose.view])
  if pose.yaw > 0 then FlipCameraYaw(pose.yaw * 45) end
  if pose.nadir then
    MoveViewDownStart()
    C_Timer.After(NADIR_PITCH, function()
      MoveViewDownStop()
      C_Timer.After(SETTLE, Shoot)
    end)
  else
    C_Timer.After(SETTLE, Shoot)
  end
end

function Finish(done, why)
  if not run then return end
  local r = run
  run = nil
  Restore()
  r.done = done
  r.why = why
  r.i, r.waiting, r.lastShot = nil, nil, nil -- (working state, not worth saving)
  if done then
    local timeouts = 0
    for _, s in ipairs(r.shots) do if s.timeout then timeouts = timeouts + 1 end end
    Say(string.format("captured %d views here (#%d)%s. Next spot, or /reload and run the import.",
      #r.shots, r.n, timeouts > 0 and (" |cffff6060- " .. timeouts .. " not confirmed saved|r") or ""))
  else
    Say("|cffff6060stopped:|r " .. tostring(why) .. " This spot will be skipped by the import.")
  end
end

function AGPSCapture_Go()
  if run then
    Say("already capturing.")
    return
  end
  local ok, why = Ready()
  if not ok then
    Say("|cffff6060can't capture:|r " .. why)
    return
  end
  local x, y, z, cont = UnitPosition("player")
  local db = AGPSCaptureDB
  run = {
    n = #db.captures + 1, i = 1, lastShot = 0, shots = {}, -- (not -math.huge: SavedVariables can't hold infinity)
    x = x, y = y, z = z, cont = cont, facing = GetPlayerFacing(),
    mapID = C_Map.GetBestMapForUnit("player"), zone = GetZoneText(), subzone = GetSubZoneText(),
    time = time(), date = date("%Y-%m-%d %H:%M:%S"), build = select(2, GetBuildInfo()),
  }
  db.captures[#db.captures + 1] = run
  Say(string.format("capturing #%d: about 35 seconds. Don't touch the mouse or keys.", run.n))
  Clean()
  Step()
end

local ev = CreateFrame("Frame")
ev:RegisterEvent("ADDON_LOADED")
ev:RegisterEvent("SCREENSHOT_SUCCEEDED")
ev:RegisterEvent("SCREENSHOT_FAILED")
ev:RegisterEvent("PLAYER_REGEN_DISABLED")
ev:RegisterEvent("PLAYER_STARTED_MOVING")
ev:SetScript("OnEvent", function(_, event, arg1)
  if event == "ADDON_LOADED" and arg1 == addonName then
    AGPSCaptureDB = type(AGPSCaptureDB) == "table" and AGPSCaptureDB or {}
    AGPSCaptureDB.views = AGPSCaptureDB.views or {}
    AGPSCaptureDB.captures = AGPSCaptureDB.captures or {}
  elseif event == "SCREENSHOT_SUCCEEDED" or event == "SCREENSHOT_FAILED" then
    if run and run.waiting == run.i then
      if event == "SCREENSHOT_FAILED" then run.shots[#run.shots].failed = true end
      run.waiting = nil
      run.i = run.i + 1
      Step()
    end
  elseif event == "PLAYER_REGEN_DISABLED" then
    Finish(false, "combat started.")
  elseif event == "PLAYER_STARTED_MOVING" then
    Finish(false, "you moved.")
  end
end)

SLASH_AGPSCAPTURE1 = "/svcap"
SlashCmdList.AGPSCAPTURE = function(msg)
  local cmd, arg = strtrim(msg or ""):lower():match("^(%S*)%s*(.-)$")
  local db = AGPSCaptureDB
  if cmd == "save" and VIEW[arg] then
    SaveView(VIEW[arg])
    db.views[arg] = true
    Say("saved the '" .. arg .. "' view (camera view " .. VIEW[arg] .. ").")
  elseif cmd == "go" then
    AGPSCapture_Go()
  elseif cmd == "test" and VIEW[arg] then
    SetView(VIEW[arg])
  elseif cmd == "stop" then
    Finish(false, "stopped by you.")
  elseif cmd == "status" then
    local have = {}
    for key in pairs(VIEW) do have[#have + 1] = key .. (db.views[key] and " ok" or " MISSING") end
    Say("views: " .. table.concat(have, ", ") .. string.format(". %d spots captured.", #db.captures))
  elseif cmd == "clear" then
    db.captures = {}
    Say("forgot all captured spots (the screenshots stay in the Screenshots folder).")
  else
    Say("one-time setup in first person, turning with the RIGHT mouse button:")
    Say("  look level: /svcap save level   up ~45: /svcap save up")
    Say("  down ~45: /svcap save down   straight up: /svcap save zenith")
    Say("  (/svcap test <name> shows a saved view)")
    Say("then stand on a road, no target, not mounted: /svcap go (or bind a key).")
    Say("/svcap status, /svcap stop, /svcap clear")
  end
end
