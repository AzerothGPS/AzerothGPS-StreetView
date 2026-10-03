-- AzerothGPS StreetView: saved settings, start-up and slash commands. Display only.
local addonName, ns = ...

local D = ns.Data

ns.DEFAULTS = {
  viewer = { width = 640 }, -- point = { anchor, x, y } once moved
  yawSign = 1,
}

function ns.Print(...)
  print("|cff4da6ffStreetView:|r", ...)
end
local Print = ns.Print

local function InitDB()
  AzerothGPSStreetViewDB = type(AzerothGPSStreetViewDB) == "table" and AzerothGPSStreetViewDB or {}
  local db = AzerothGPSStreetViewDB
  for k, v in pairs(ns.DEFAULTS) do
    if db[k] == nil then
      if type(v) == "table" then
        local copy = {}
        for k2, v2 in pairs(v) do copy[k2] = v2 end
        db[k] = copy
      else
        db[k] = v
      end
    end
  end
  ns.db = db
  D.yawSign = db.yawSign == -1 and -1 or 1
end

-- No pictures found (the user, 2026-10-03): they ship inside this addon, but a copy without them (GitHub's source
-- code, an install cut short) has only the empty Index.lua. Then the figure, a boss's Shift-click, /sv here|open and
-- Where in the Azeroth? (its button, a game's link, an invitation) show this notice and stop.
ns.PAGE_URL = "https://www.curseforge.com/wow/addons/azerothgps-streetview"

function ns.HasData() return D.count > 0 end

function ns.DataNoticeText()
  return "No street view pictures were found. They come with AzerothGPS StreetView from CurseForge (a copy of "
    .. "the source code from GitHub has none): reinstall it from the page below, then restart the game completely."
end

local notice
function ns.ShowDataNotice()
  local text = ns.DataNoticeText()
  local API = _G.AzerothGPS
  if not (API and API.Window) then
    Print(text .. " " .. ns.PAGE_URL)
    return
  end
  if not notice then
    notice = API.Window("AzerothGPSStreetViewDataNotice", 380, 200, "Street View Pictures Missing")
    notice.text = notice:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    notice.text:SetPoint("TOPLEFT", 18, notice.top - 10)
    notice.text:SetPoint("TOPRIGHT", -18, notice.top - 10)
    notice.text:SetJustifyH("LEFT")
    notice.text:SetSpacing(2)
    -- the page's address, to copy (the game can't open links): selected on a click, never changed
    local box = CreateFrame("EditBox", nil, notice, "InputBoxTemplate")
    box:SetSize(320, 22)
    box:SetPoint("BOTTOM", 0, 50)
    box:SetAutoFocus(false)
    box:SetScript("OnTextChanged", function(self, user) if user then self:SetText(ns.PAGE_URL) self:HighlightText() end end)
    box:SetScript("OnEditFocusGained", function(self) self:HighlightText() end)
    box:SetScript("OnEscapePressed", function(self) self:ClearFocus() notice:Hide() end)
    box:SetText(ns.PAGE_URL)
    box:SetCursorPosition(0)
    notice.box = box
    local hint = notice:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    hint:SetPoint("BOTTOM", box, "TOP", 0, 4)
    hint:SetText("Click, then Ctrl+C to copy")
    local ok = CreateFrame("Button", nil, notice, "UIPanelButtonTemplate")
    ok:SetSize(90, 24)
    ok:SetPoint("BOTTOM", 0, 16)
    ok:SetText("OK")
    ok:SetScript("OnClick", function() notice:Hide() end)
  end
  notice.text:SetText(text)
  notice:Show()
end

-- true with pictures installed; else the notice, false
function ns.NeedData()
  if ns.HasData() then return true end
  ns.ShowDataNotice()
  return false
end

-- The view nearest the player, looking the way they face.
function ns.Here()
  if not ns.NeedData() then return end
  local API = _G.AzerothGPS
  local x, y, cont
  if API then x, y, cont = API.PlayerWorld() end -- (not `API and ...`: that keeps one value)
  if not x then
    Print("Your position isn't available here.")
    return
  end
  local p, d = D.Nearest(API.BaseContinent(cont), x, y)
  if not p then
    Print("No street views on this continent yet.")
    return
  end
  ns.Viewer.Open(p, API.Facing())
  if d > 60 then Print(string.format("The nearest street view is %d yards away.", d)) end
end

local HELP = {
  "/sv - drag the figure from the AzerothGPS map onto a road to look around.",
  "/sv here - the street view nearest you.",
  "/sv open <id> - a street view by its id.",
  "/sv list - the installed street views.",
  "/sv hide - close the viewer.",
  "/sv flipyaw - turn the views the other way (if left and right are swapped).",
  "/sv probe - check that this game client shows JPEG images.",
}

-- The private developer addon (AzerothGPS_StreetView_Dev, never shipped) adds its /sv commands
-- and tools through this: fn(ns), called once.
ns.commands, ns.commandHelp = {}, {}
function AzerothGPS_StreetView_Extend(fn) fn(ns) end

SLASH_AZEROTHGPSSTREETVIEW1 = "/sv"
SLASH_AZEROTHGPSSTREETVIEW2 = "/streetview"
SlashCmdList.AZEROTHGPSSTREETVIEW = function(msg)
  local cmd, rest = strtrim(msg or ""):match("^(%S*)%s*(.-)$")
  cmd = (cmd or ""):lower()
  if cmd == "here" then
    ns.Here()
  elseif cmd == "open" then
    if not ns.NeedData() then return end
    local p = D.byId[rest]
    if p then ns.Viewer.Open(p) else Print("No street view with id " .. tostring(rest)) end
  elseif cmd == "list" then
    Print(string.format("%d street views installed.", D.count))
    for cont, list in pairs(D.byCont) do
      for _, p in ipairs(list) do
        Print(string.format("  %s  %s", p.id, p.zone or ("continent " .. cont)))
      end
    end
  elseif cmd == "hide" then
    ns.Viewer.Hide()
  elseif cmd == "flipyaw" then
    ns.db.yawSign = -(ns.db.yawSign or 1)
    D.yawSign = ns.db.yawSign
    Print(D.yawSign == 1 and "Views turn counter-clockwise (default)." or "Views turn clockwise.")
    ns.Viewer.Refresh()
  elseif cmd == "probe" then
    ns.Viewer.Probe()
  elseif ns.commands[cmd] then -- (the dev addon's)
    ns.commands[cmd](rest)
  else
    for _, line in ipairs(HELP) do Print(line) end
    for _, line in ipairs(ns.commandHelp) do Print(line) end
  end
end

local ev = CreateFrame("Frame")
ev:RegisterEvent("ADDON_LOADED")
ev:RegisterEvent("PLAYER_LOGIN")
ev:RegisterEvent("PLAYER_ENTERING_WORLD")
ev:SetScript("OnEvent", function(_, event, arg1, arg2)
  if event == "PLAYER_ENTERING_WORLD" then
    -- The game sees only the files that were there when it started: pictures installed later show
    -- as plain green until a restart. On a fresh start every installed view can be shown; after a
    -- /reload only those (D.loadable, kept in the saved settings).
    if arg1 then -- (isInitialLogin: the game just started)
      ns.db.loadable = {}
      for id in pairs(D.byId) do ns.db.loadable[id] = true end
    end
    if arg1 or arg2 then D.loadable = ns.db.loadable end
    -- (the first time after loading: a /reload or not; a game going on takes up again after a /reload)
    if ns.reloadedUI == nil then
      ns.reloadedUI = arg2 and true or false
      if ns.Game and ns.Game.TryResume then ns.Game.TryResume() end
    end
    return
  end
  if event == "ADDON_LOADED" and arg1 == addonName then
    InitDB()
  elseif event == "PLAYER_LOGIN" then
    D.Load()
    if not ns.HasData() then -- (once a login, in chat; the notice itself only when a street view is asked for)
      Print(ns.DataNoticeText() .. " " .. ns.PAGE_URL)
    end
    -- after AzerothGPS has built its map (its PLAYER_LOGIN runs first; one frame later to be sure)
    C_Timer.After(0, function()
      local ok, err = pcall(ns.Figure.Init)
      if not ok then Print("|cffff6060the map figure failed to start:|r " .. tostring(err)) end
    end)
  end
end)
