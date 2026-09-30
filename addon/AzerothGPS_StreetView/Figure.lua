-- The figure on the AzerothGPS map: drag it out and the road network lights up (the road under
-- the pointer brightest) with the street views as dots; drop it and the nearest view opens in
-- the viewer, looking the way the map's top points. A plain click opens the view nearest you.
-- Uses only AzerothGPS's public API (the AzerothGPS global, docs/api.md there).
local _, ns = ...

local F = {}
ns.Figure = F
local D = ns.Data

local ICON = "Interface\\AddOns\\AzerothGPS_StreetView\\Media\\Figure"
local ROADS = { 0.25, 0.6, 1 } -- the road network while carrying
local ROAD_HOT = { 0.55, 0.85, 1 } -- the road under the pointer
local VIEWS = { 0.05, 0.3, 0.95 } -- street views
local PICK = { 1, 0.82, 0.1 } -- the view a drop would open / the view open now
local SNAP_UI = 40 -- a view within this many UI units of the pointer is picked on drop
local ROAD_UI = 20 -- ... a road within this is highlighted
local HOVER_EVERY = 0.05 -- seconds between pointer checks while carrying

local API, button, carry
local carrying, hover, lastDrop = false, nil, 0

function F.Redraw()
  if API then API.Redraw() end
end

-- What's under the pointer: { cont, x, y, point, edge } or nil off the map.
local function Probe()
  local x, y, cont = API.CursorWorld()
  if not x then return nil end
  local _, _, _, _, scale = API.View()
  scale = scale or 1
  local h = { cont = cont, x = x, y = y }
  h.point = D.Nearest(API.BaseContinent(cont), x, y, SNAP_UI / scale)
  local ok, _, _, dist, edge = pcall(API.NearestRoad, cont, x, y)
  if ok and dist and dist * scale <= ROAD_UI then h.edge = edge end
  return h
end

local function UpdateHover()
  local h = Probe()
  local changed = (h and h.point) ~= (hover and hover.point) or (h and h.edge) ~= (hover and hover.edge)
    or (h == nil) ~= (hover == nil)
  hover = h
  if changed then F.Redraw() end
end

-- Drawn on the map on every redraw (AzerothGPS.SetOverlay).
function F.Draw(ctx)
  local base = API.BaseContinent(ctx.cont)
  if carrying then
    if hover and hover.edge and hover.cont == ctx.cont then
      local e = API.RoadEdge(hover.cont, hover.edge)
      if e then
        for i = 5, #e - 3, 2 do ctx.Line(e[i], e[i + 1], e[i + 2], e[i + 3], ROAD_HOT, 6, 1) end
      end
    end
    for _, p in ipairs(D.PointsOn(base)) do ctx.Dot(p.x, p.y, VIEWS, 3, 1) end -- (small: inside the road's line)
    if hover and hover.point then ctx.Dot(hover.point.x, hover.point.y, PICK, 13, 1) end
  end
  -- the view open in the viewer: its spot and the way it looks
  local cur = ns.Viewer.Current()
  if cur and cur.p.cont == base and not cur.game then -- (not Street Guess's: that would give it away)
    local p, h = cur.p, ns.Viewer.Heading()
    local len = 36 / ctx.scale -- (36 UI units whatever the zoom)
    for _, a in ipairs({ h - 0.45, h + 0.45 }) do
      ctx.Line(p.x, p.y, p.x + math.cos(a) * len, p.y + math.sin(a) * len, PICK, 2, 0.9)
    end
    ctx.Dot(p.x, p.y, PICK, 10, 1)
  end
end

local function Playing() return ns.Game and ns.Game.Playing() end

function F.Pick()
  if Playing() then
    UIErrorsFrame:AddMessage("Not during a game of Where in the Azeroth?", 1, 0.82, 0)
    return
  end
  carrying = true
  hover = nil
  button.icon:SetAlpha(0.25)
  carry:Show()
  API.ShowRoads("StreetView", true, ROADS)
  if D.count == 0 then
    UIErrorsFrame:AddMessage("No street views installed yet", 1, 0.82, 0)
  end
end

function F.Drop()
  if not carrying then return end
  UpdateHover()
  carrying = false
  lastDrop = GetTime()
  carry:Hide()
  button.icon:SetAlpha(1)
  API.ShowRoads("StreetView", false)
  local h = hover
  hover = nil
  if h and h.point then
    local _, _, _, rot = API.View()
    ns.Viewer.Open(h.point, -(rot or 0)) -- (the map's top: north, or the player's facing when heading-up)
  elseif h then
    UIErrorsFrame:AddMessage("No street view here yet", 1, 0.82, 0)
  end
  F.Redraw()
end

function F.Init()
  if button then return end
  API = _G.AzerothGPS
  if type(API) ~= "table" or not API.SetOverlay then
    ns.Print("|cffff6060needs AzerothGPS with its public API (the version after 1.0.6).|r")
    return
  end
  local parent = API.MapButtonParent()
  if not parent then
    F.tries = (F.tries or 0) + 1
    if F.tries < 10 then C_Timer.After(1, F.Init) end -- (the map not built yet)
    return
  end

  button = CreateFrame("Button", nil, parent)
  button:SetSize(28, 28)
  -- In AzerothGPS's bottom-right column: right above its import button, or above its "Back to
  -- your position" button while that one shows (only when the map is panned away from you).
  local recenter, import = API.MapButton and API.MapButton("recenter"), API.MapButton and API.MapButton("import")
  -- (the lowest of our buttons: Street Guess's, when it's there, with the figure above it)
  local lowest = button
  local function Place()
    lowest:ClearAllPoints()
    local below = (recenter and recenter:IsShown() and recenter) or import
    if below then
      lowest:SetPoint("BOTTOM", below, "TOP", 0, 4)
    else
      lowest:SetPoint("BOTTOMRIGHT", -6, 70) -- (an AzerothGPS without MapButton)
    end
  end
  Place()
  if recenter then
    recenter:HookScript("OnShow", Place)
    recenter:HookScript("OnHide", Place)
  end
  local bg = button:CreateTexture(nil, "BACKGROUND")
  bg:SetAllPoints()
  bg:SetTexture("Interface\\Minimap\\UI-Minimap-Background")
  button.icon = button:CreateTexture(nil, "ARTWORK")
  button.icon:SetTexture(ICON)
  button.icon:SetSize(24, 24)
  button.icon:SetPoint("CENTER")
  button:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
  button:RegisterForClicks("LeftButtonUp")
  button:RegisterForDrag("LeftButton")
  button:SetScript("OnDragStart", F.Pick)
  button:SetScript("OnDragStop", F.Drop)
  button:SetScript("OnClick", function()
    if Playing() then return UIErrorsFrame:AddMessage("Not during a game of Where in the Azeroth?", 1, 0.82, 0) end
    if GetTime() - lastDrop > 0.3 then ns.Here() end
  end)
  button:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:AddLine("Street View")
    GameTooltip:AddLine("Drag onto a road to look around there.", 1, 1, 1, true)
    GameTooltip:AddLine("Click: the street view nearest you.", 0.8, 0.8, 0.8, true)
    GameTooltip:AddLine(string.format("%d views installed.", D.count), 0.6, 0.6, 0.6)
    GameTooltip:Show()
  end)
  button:SetScript("OnLeave", GameTooltip_Hide)

  -- the figure in hand, following the pointer
  carry = CreateFrame("Frame", nil, UIParent)
  carry:SetFrameStrata("TOOLTIP")
  carry:SetSize(36, 36)
  carry:Hide()
  local ct = carry:CreateTexture(nil, "OVERLAY")
  ct:SetAllPoints()
  ct:SetTexture(ICON)
  local wait = 0
  carry:SetScript("OnUpdate", function(self, dt)
    local x, y = GetCursorPosition()
    local s = UIParent:GetEffectiveScale()
    self:ClearAllPoints()
    self:SetPoint("BOTTOM", UIParent, "BOTTOMLEFT", x / s, y / s - 4) -- (feet on the pointer)
    wait = wait - dt
    if wait <= 0 then
      wait = HOVER_EVERY
      UpdateHover()
    end
  end)

  API.SetOverlay("StreetView", F.Draw)

  -- Street Guess's button: in this one's place, with this one above it
  local ok, game = pcall(ns.Game.Init, button)
  if not ok then
    ns.Print("|cffff6060Where in the Azeroth? failed to start:|r " .. tostring(game))
  elseif game then
    lowest = game
    button:ClearAllPoints()
    Place()
    button:SetPoint("BOTTOM", game, "TOP", 0, 4)
  end
end

-- The figure is dimmed while a Street Guess game is on (it can't be used then).
function F.Refresh()
  if button then button:SetAlpha(Playing() and 0.35 or 1) end
end
