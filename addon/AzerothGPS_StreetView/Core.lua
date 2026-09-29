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

-- The view nearest the player, looking the way they face.
function ns.Here()
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
  "/sv dev - the Report picture button in Where in the Azeroth? on or off (for taking broken pictures again).",
  "/sv reports - the street views reported as broken; /sv unreport <id> or /sv unreport all.",
}

SLASH_AZEROTHGPSSTREETVIEW1 = "/sv"
SLASH_AZEROTHGPSSTREETVIEW2 = "/streetview"
SlashCmdList.AZEROTHGPSSTREETVIEW = function(msg)
  local cmd, rest = strtrim(msg or ""):match("^(%S*)%s*(.-)$")
  cmd = (cmd or ""):lower()
  if cmd == "here" then
    ns.Here()
  elseif cmd == "open" then
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
  elseif cmd == "dev" then
    ns.db.dev = not ns.db.dev or nil
    Print(ns.db.dev and "Report picture is on (Where in the Azeroth?)." or "Report picture is off.")
  elseif cmd == "reports" then
    local n = 0
    for id in pairs(ns.db.reported or {}) do
      n = n + 1
      Print("  reported: " .. id)
    end
    Print(n == 0 and "No street views reported." or (n .. " reported. /sv unreport <id> or /sv unreport all"))
  elseif cmd == "unreport" then
    if rest == "all" then
      ns.db.reported = nil
      Print("No street views reported now.")
    elseif ns.db.reported and ns.db.reported[rest] then
      ns.db.reported[rest] = nil
      Print("Street view " .. rest .. " is no longer reported.")
    else
      Print("Not reported: " .. tostring(rest) .. " (/sv reports lists them)")
    end
  else
    for _, line in ipairs(HELP) do Print(line) end
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
    return
  end
  if event == "ADDON_LOADED" and arg1 == addonName then
    InitDB()
  elseif event == "PLAYER_LOGIN" then
    D.Load()
    -- after AzerothGPS has built its map (its PLAYER_LOGIN runs first; one frame later to be sure)
    C_Timer.After(0, function()
      local ok, err = pcall(ns.Figure.Init)
      if not ok then Print("|cffff6060the map figure failed to start:|r " .. tostring(err)) end
    end)
  end
end)
