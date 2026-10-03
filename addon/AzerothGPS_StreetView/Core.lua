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

-- Pages to copy (the game can't open links): CurseForge's by project id, which takes you to the project
-- whatever its address.
ns.PAGE_URL = "https://www.curseforge.com/projects/1721639" -- (this addon)
ns.AZEROTHGPS_URL = "https://www.curseforge.com/projects/1712208" -- (AzerothGPS)
ns.MIN_API = 12 -- AzerothGPS's API version this addon needs (AzerothGPS 1.1.0: a boss's Shift-click)

-- A popup window: AzerothGPS's own (every popup looks like its map window without the logo, AzerothGPS.Window),
-- else the same look made here (AzerothGPS missing or too old to have it).
function ns.Window(name, w, h, title)
  local API = _G.AzerothGPS
  if type(API) == "table" and API.Window then return API.Window(name, w, h, title) end
  local f = CreateFrame("Frame", name, UIParent, BackdropTemplateMixin and "BackdropTemplate" or nil)
  f:SetSize(w, h)
  f:SetPoint("CENTER")
  f:SetFrameStrata("DIALOG")
  f:SetToplevel(true)
  f:SetClampedToScreen(true)
  f:EnableMouse(true)
  f:SetMovable(true)
  f:RegisterForDrag("LeftButton")
  f:SetScript("OnDragStart", function(self) self:StartMoving() end)
  f:SetScript("OnDragStop", function(self) self:StopMovingOrSizing() end)
  if name and UISpecialFrames then table.insert(UISpecialFrames, name) end -- (Escape closes it)
  local bg = f:CreateTexture(nil, "BACKGROUND")
  bg:SetPoint("TOPLEFT", 3, -3)
  bg:SetPoint("BOTTOMRIGHT", -3, 3)
  bg:SetColorTexture(0.05, 0.05, 0.06, 0.95)
  local ok, chrome = pcall(CreateFrame, "Frame", nil, f, "PortraitFrameTemplate")
  if ok and chrome and chrome.NineSlice then
    chrome:SetAllPoints()
    chrome:SetFrameLevel(f:GetFrameLevel())
    chrome:EnableMouse(false)
    if chrome.Bg then chrome.Bg:Hide() end
    if chrome.TopTileStreaks then chrome.TopTileStreaks:Hide() end
    if chrome.SetBorder then pcall(chrome.SetBorder, chrome, "ButtonFrameTemplateNoPortrait") end
    if chrome.PortraitContainer then chrome.PortraitContainer:Hide() end
    if chrome.portrait then chrome.portrait:Hide() end
    if chrome.CloseButton then chrome.CloseButton:SetScript("OnClick", function() f:Hide() end) end
    if chrome.SetTitle then
      chrome:SetTitle(title or "")
    elseif chrome.TitleContainer and chrome.TitleContainer.TitleText then
      chrome.TitleContainer.TitleText:SetText(title or "")
    end
    f.top = -30
  else
    if f.SetBackdrop then
      f:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
      f:SetBackdropColor(0.05, 0.05, 0.06, 0.95)
      f:SetBackdropBorderColor(0.3, 0.3, 0.3, 1)
    end
    local t = f:CreateFontString(nil, "ARTWORK", "GameFontNormal")
    t:SetPoint("TOP", 0, -8)
    t:SetText(title or "")
    local close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
    close:SetPoint("TOPRIGHT", 2, 2)
    close:SetScript("OnClick", function() f:Hide() end)
    f.top = -28
  end
  f:Hide()
  return f
end

-- A notice: the text, a page's address to copy, and OK. One window per name, made the first time.
local notices = {}
function ns.Notice(name, title, text, url)
  local f = notices[name]
  if not f then
    f = ns.Window(name, 380, 200, title)
    f.text = f:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
    f.text:SetPoint("TOPLEFT", 18, f.top - 10)
    f.text:SetPoint("TOPRIGHT", -18, f.top - 10)
    f.text:SetJustifyH("LEFT")
    f.text:SetSpacing(2)
    -- the page's address, to copy: selected on a click, never changed
    local box = CreateFrame("EditBox", nil, f, "InputBoxTemplate")
    box:SetSize(320, 22)
    box:SetPoint("BOTTOM", 0, 50)
    box:SetAutoFocus(false)
    box:SetScript("OnTextChanged", function(self, user) if user then self:SetText(f.url) self:HighlightText() end end)
    box:SetScript("OnEditFocusGained", function(self) self:HighlightText() end)
    box:SetScript("OnEscapePressed", function(self) self:ClearFocus() f:Hide() end)
    f.box = box
    local hint = f:CreateFontString(nil, "OVERLAY", "GameFontDisableSmall")
    hint:SetPoint("BOTTOM", box, "TOP", 0, 4)
    hint:SetText("Click, then Ctrl+C to copy")
    local ok = CreateFrame("Button", nil, f, "UIPanelButtonTemplate")
    ok:SetSize(90, 24)
    ok:SetPoint("BOTTOM", 0, 16)
    ok:SetText("OK")
    ok:SetScript("OnClick", function() f:Hide() end)
    notices[name] = f
  end
  f.url = url
  f.text:SetText(text)
  f.box:SetText(url)
  f.box:SetCursorPosition(0)
  f:Show()
  return f
end

-- No pictures found (the user, 2026-10-03): they ship inside this addon, but a copy without them (GitHub's source
-- code, an install cut short) has only the empty Index.lua. Then the figure, a boss's Shift-click, /sv here|open and
-- Where in the Azeroth? (its button, a game's link, an invitation) show this notice and stop.
function ns.HasData() return D.count > 0 end

function ns.DataNoticeText()
  return "No street view pictures were found. They come with AzerothGPS StreetView from CurseForge (a copy of "
    .. "the source code from GitHub has none): reinstall it from the page below, then restart the game completely."
end

function ns.ShowDataNotice()
  return ns.Notice("AzerothGPSStreetViewDataNotice", "Street View Pictures Missing", ns.DataNoticeText(), ns.PAGE_URL)
end

-- AzerothGPS missing, turned off or too old (the user, 2026-10-03): the toc lists it as an optional dependency, so
-- this addon still loads without it and says so (a required one would leave it unloaded, nothing said). nil when
-- it's there and new enough; else "missing", "disabled" or "old".
function ns.AzerothGPSState()
  local API = _G.AzerothGPS
  if type(API) == "table" then
    return (tonumber(API.version) or 0) < ns.MIN_API and "old" or nil
  end
  local info = (C_AddOns and C_AddOns.GetAddOnInfo) or _G.GetAddOnInfo
  local ok, name, _, loadable, reason
  if info then ok, name, _, _, loadable, reason = pcall(info, "AzerothGPS") end
  if ok and name and reason ~= "MISSING" and (reason == "DISABLED" or loadable == false) then return "disabled" end
  return "missing"
end

function ns.AzerothGPSNoticeText(state)
  if state == "old" then
    return "AzerothGPS StreetView needs a newer AzerothGPS (1.1.0 or later). Update AzerothGPS from the page below, "
      .. "then restart the game. Until then some of StreetView may not work."
  elseif state == "disabled" then
    return "AzerothGPS StreetView needs AzerothGPS, which is installed but turned off. Turn it on in the AddOns list "
      .. "(the AddOns button at the character select screen), then log in again."
  end
  return "AzerothGPS StreetView needs AzerothGPS: the street views open from its map. Install AzerothGPS from the "
    .. "page below (the CurseForge app installs it with StreetView), then restart the game."
end

-- At login: the notice when AzerothGPS isn't there or is too old. The state, or nil when all is well.
function ns.CheckAzerothGPS()
  local state = ns.AzerothGPSState()
  if state then
    ns.Notice("AzerothGPSStreetViewNeedsAzerothGPS", state == "old" and "AzerothGPS Too Old" or "AzerothGPS Needed",
      ns.AzerothGPSNoticeText(state), ns.AZEROTHGPS_URL)
    Print(ns.AzerothGPSNoticeText(state))
  end
  return state
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
    local agps = ns.CheckAzerothGPS()
    if agps == "missing" or agps == "disabled" then return end -- (no map to show anything on)
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
