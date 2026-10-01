-- The street view window. A spot with a panorama pans smoothly: drag the picture (the scenery
-- follows the pointer), the mouse wheel zooms, the arrows turn 45 degrees and Up/Down tilt.
-- A spot without one shows its separate views, one at a time. Its spot and direction show on
-- the AzerothGPS map.
-- Framed like the AzerothGPS map: the game's own window frame (metal border, title bar, round
-- portrait with the logo, close button), or a plain dark border if this client lacks it.
local _, ns = ...

local V = {}
ns.Viewer = V
local D = ns.Data

local MEDIA = "Interface\\AddOns\\AzerothGPS_StreetView\\Media\\"
local PAD = 4 -- picture inset from the frame's edge
local BORDER = 3 -- the dark border (as the AzerothGPS map's)
local CHROME_TITLE = 22 -- the game frame's title bar, above the frame (as the map's)
local TITLE_H = 22 -- our own title bar, inside the frame, when the game frame isn't there
local BAR_H = 0 -- the controls strip along the top: none (the user, 2026-09-30: the picture is
-- dragged, zoomed with the wheel and walked with its arrows; the buttons and heading text only took room)
local CONTROLS_X = 60 -- controls start right of the portrait (or badge)
local MIN_W, MAX_W = 360, 1400
local DRAG_STEP = 60 -- UI units of dragging across the picture per view turned
local FOV, FOV_MIN, FOV_MAX = 90, 40, 110 -- panorama: degrees across the window (the wheel zooms)
local TURN_DEG, TILT_DEG = 45, 20 -- panorama: the arrow and Up/Down buttons
local ARROW_SIZE, ARROW_LAT = 56, -15 -- way-to-go arrows: size, and degrees below the horizon
local STEP_HFOV = 85 -- single views: their field of view across (the capture's, measured)
local CUBE_FOV = FOV_MAX -- cube views open fully zoomed out (standing still and turning); the wheel zooms in
local GRID_COLS, GRID_ROWS = 24, 12 -- cube views: the window is drawn as this many cells
local MAX_LAT = 85 -- cube views: how far up or down you can look
local PITCH_NAMES = { [-90] = "straight down", [-45] = "looking down", [0] = "level", [45] = "looking up", [90] = "straight up" }

local frame, chrome, view, img, missing, title, info, preload, ahead, timerBox, gameLogo, badge
-- Where in the Azeroth?'s logo over the title bar while a game shows (Media/GameLogo.tga, square:
-- the logo fills its width, about 3/4 of its height): this wide, in the top-left corner
local GAME_LOGO = 141 -- (176 less 20%: the user, 2026-09-30)
local tiles = {} -- panorama tile textures by col * 100 + row
local cells = {} -- cube view cell textures
local ghosts = {} -- ... a second copy, zoomed a little further, faint: the blur of a move up the road
local move -- the move to the next spot being animated (V.GoToward)
local MOVE_OUT, MOVE_IN = 0.3, 0.3 -- seconds: zooming toward the next spot, then fading into it
local MOVE_ZOOM = 0.45 -- the view narrows this much on the way (a fraction of its field of view)
local GHOST_ZOOM, GHOST_ALPHA = 0.16, 0.45 -- the blur copy: that much further in, this faint at full blur
local lastMarkHeading -- heading last drawn on the map
local arrows = {} -- way-to-go arrow buttons
local dragging = false -- the picture is being dragged (arrows hidden)
local HideArrows -- (defined further down; the drag handler in V.Build uses it)
local topH = TITLE_H -- our own title bar's height (0 with the game frame)
local cur -- { p, yaw, pitch (index into D.PITCHES) }, or { p, pano = true, lon, lat, fov }

local function Button(parent, text, width, onClick)
  local ok, b = pcall(CreateFrame, "Button", nil, parent, "UIPanelButtonTemplate")
  if not ok or not b then
    b = CreateFrame("Button", nil, parent, "BackdropTemplate")
    if b.SetBackdrop then
      b:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
      b:SetBackdropColor(0.15, 0.15, 0.2, 1)
      b:SetBackdropBorderColor(0.4, 0.4, 0.5, 1)
    end
    b:SetNormalFontObject("GameFontHighlightSmall")
  end
  b:SetSize(width, 22)
  b:SetText(text)
  b:SetScript("OnClick", onClick)
  return b
end

local function SavePosition()
  local point, _, rel, x, y = frame:GetPoint(1)
  ns.db.viewer.point = { point, rel, x, y }
  ns.db.viewer.width = math.floor(frame:GetWidth() + 0.5)
end

local function SetWidth(w)
  w = math.max(MIN_W, math.min(MAX_W, w))
  local imgW = w - 2 * PAD
  frame:SetSize(w, imgW / 2 + topH + BAR_H + 2 * PAD)
end

local function SetTitle(text)
  if chrome then
    if chrome.SetTitle then
      chrome:SetTitle(text)
    elseif chrome.TitleContainer and chrome.TitleContainer.TitleText then
      chrome.TitleContainer.TitleText:SetText(text)
    end
  elseif title then
    title:SetText(text)
  end
end

-- Dragging `f` moves the window.
local function MoveHandle(f)
  f:EnableMouse(true)
  f:SetScript("OnMouseDown", function() frame:StartMoving() end)
  f:SetScript("OnMouseUp", function()
    frame:StopMovingOrSizing()
    SavePosition()
  end)
end

-- The game's own window frame around the viewer, set up as AzerothGPS's map does it
-- (GPSFrame.lua there): only its border, title bar, portrait and close button draw; the
-- picture stays clickable. nil if this client has no PortraitFrameTemplate.
local function WindowFrame()
  local ok, c = pcall(CreateFrame, "Frame", nil, frame, "PortraitFrameTemplate")
  if not ok or not c or not c.NineSlice then return nil end
  c:SetPoint("TOPLEFT", frame, "TOPLEFT", -2, CHROME_TITLE)
  c:SetPoint("BOTTOMRIGHT", frame, "BOTTOMRIGHT", 2, -2)
  c:SetFrameLevel(frame:GetFrameLevel() + 12)
  c:EnableMouse(false)
  if c.Bg then c.Bg:Hide() end -- (the picture is the window's content)
  if c.TopTileStreaks then c.TopTileStreaks:Hide() end
  local strip = c:CreateTexture(nil, "BACKGROUND") -- behind the title only
  strip:SetPoint("TOPLEFT", 2, -2)
  strip:SetPoint("BOTTOMRIGHT", c, "TOPRIGHT", -2, -CHROME_TITLE)
  strip:SetColorTexture(0.06, 0.06, 0.07, 1)
  local portrait = c.GetPortrait and c:GetPortrait() or (c.PortraitContainer and c.PortraitContainer.portrait)
  if portrait then portrait:SetTexture(MEDIA .. "Portrait") end -- (the logo with a margin)
  if c.CloseButton then c.CloseButton:SetScript("OnClick", function() V.Hide() end) end
  local grab = CreateFrame("Frame", nil, c) -- the title bar moves the window
  grab:SetPoint("TOPLEFT", 56, 0)
  grab:SetPoint("TOPRIGHT", -26, 0)
  grab:SetHeight(CHROME_TITLE)
  MoveHandle(grab)
  return c
end

-- Without the game frame: our own title bar, the logo as a badge over the corner, a close button.
local function PlainTitle()
  local bar = CreateFrame("Frame", nil, frame)
  bar:SetPoint("TOPLEFT", PAD, -PAD)
  bar:SetPoint("TOPRIGHT", -PAD - 22, -PAD)
  bar:SetHeight(TITLE_H - 2)
  MoveHandle(bar)
  badge = CreateFrame("Frame", nil, frame)
  badge:SetSize(56, 56)
  badge:SetPoint("CENTER", frame, "TOPLEFT", 12, -10)
  badge:SetFrameLevel(frame:GetFrameLevel() + 10)
  MoveHandle(badge)
  local logo = badge:CreateTexture(nil, "ARTWORK")
  logo:SetAllPoints()
  logo:SetTexture(MEDIA .. "Portrait")
  title = bar:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  title:SetPoint("LEFT", 40, 0) -- (clear of the badge)
  title:SetPoint("RIGHT", -4, 0)
  title:SetJustifyH("LEFT")
  local ok, close = pcall(CreateFrame, "Button", nil, frame, "UIPanelCloseButton")
  if not ok or not close then close = Button(frame, "X", 20, nil) end
  close:SetPoint("TOPRIGHT", 0, 0)
  close:SetScript("OnClick", function() V.Hide() end)
end

function V.Build()
  frame = CreateFrame("Frame", "AzerothGPSStreetViewFrame", UIParent, "BackdropTemplate")
  frame:SetFrameStrata("HIGH")
  frame:SetClampedToScreen(true)
  frame:SetMovable(true)
  frame:EnableMouse(true)
  frame:Hide()
  if frame.SetBackdrop then -- (the AzerothGPS map's border)
    frame:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = BORDER })
    frame:SetBackdropColor(0.05, 0.05, 0.05, 1)
    frame:SetBackdropBorderColor(0.15, 0.15, 0.15, 1)
  end
  table.insert(UISpecialFrames, "AzerothGPSStreetViewFrame") -- Escape closes it

  chrome = WindowFrame()
  if chrome then
    topH = 0
    frame:SetClampRectInsets(-8, 2, CHROME_TITLE + 8, -2) -- (the frame's title bar and portrait stick out)
  else
    topH = TITLE_H
    PlainTitle()
    frame:SetClampRectInsets(-18, 0, 20, 0) -- (the badge sticks out over the corner)
  end
  local pos = ns.db.viewer.point
  if pos then
    frame:SetPoint(pos[1], UIParent, pos[2], pos[3], pos[4])
  else
    frame:SetPoint("CENTER", 0, 120)
  end
  SetWidth(ns.db.viewer.width or 640)

  -- controls along the top, right of the portrait
  local top = -(PAD + topH + (BAR_H - 22) / 2)
  local left = Button(frame, "<", 28, function() V.TurnBy(-1) end)
  left:SetPoint("TOPLEFT", CONTROLS_X, top)
  local right = Button(frame, ">", 28, function() V.TurnBy(1) end)
  right:SetPoint("LEFT", left, "RIGHT", 2, 0)
  local up = Button(frame, "Up", 40, function() V.Tilt(1) end)
  up:SetPoint("LEFT", right, "RIGHT", 8, 0)
  local down = Button(frame, "Down", 48, function() V.Tilt(-1) end)
  down:SetPoint("LEFT", up, "RIGHT", 2, 0)
  ahead = Button(frame, "Go ahead", 72, function() V.GoAhead() end)
  ahead:SetPoint("LEFT", down, "RIGHT", 8, 0)
  info = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  info:SetPoint("LEFT", ahead, "RIGHT", 8, 0)
  info:SetPoint("RIGHT", -10, 0)
  info:SetJustifyH("RIGHT")
  for _, b in ipairs({ left, right, up, down, ahead }) do b:Hide() end
  info:Hide()

  -- the picture
  view = CreateFrame("Frame", nil, frame)
  view:SetClipsChildren(true) -- (panorama tiles slide past the edges)
  view:SetPoint("TOPLEFT", PAD, -(PAD + topH + BAR_H))
  view:SetPoint("BOTTOMRIGHT", -PAD, PAD)
  view:EnableMouse(true)
  view:EnableMouseWheel(true)
  img = view:CreateTexture(nil, "ARTWORK")
  img:SetAllPoints()
  missing = view:CreateFontString(nil, "OVERLAY", "GameFontHighlight")
  missing:SetPoint("CENTER")
  missing:SetWidth(400)
  missing:Hide()
  view:SetScript("OnMouseWheel", function(_, delta)
    if cur and cur.pano then V.Zoom(delta) else V.TurnBy(delta > 0 and -1 or 1) end
  end)
  -- drag across the picture to look around (like pulling the scenery)
  local dragX, dragY
  view:SetScript("OnMouseDown", function(_, button)
    if button == "LeftButton" then
      dragX, dragY = GetCursorPosition()
      dragging = true
      HideArrows()
    end
  end)
  view:SetScript("OnMouseUp", function()
    dragX = nil
    if dragging then
      dragging = false
      V.Refresh() -- (the arrows come back)
    end
  end)
  view:SetScript("OnUpdate", function()
    if not dragX then return end
    local x, y = GetCursorPosition()
    local s = frame:GetEffectiveScale()
    local dx, dy = (x - dragX) / s, (y - dragY) / s
    if cur and cur.pano then
      -- smooth: the scenery follows the pointer (pull right: look left; pull up: look down)
      if dx ~= 0 or dy ~= 0 then
        local dpu = cur.fov / view:GetWidth() -- degrees per UI unit (flat panorama)
        if cur.cube then -- (in perspective: the angle a UI unit spans at the window's middle)
          dpu = math.deg(math.tan(math.rad(cur.fov) / 2) / (view:GetWidth() / 2))
        end
        cur.lon = cur.lon - dx * dpu
        cur.lat = cur.lat - dy * dpu
        dragX, dragY = x, y
        V.Refresh()
      end
    elseif math.abs(dx) >= DRAG_STEP then
      V.TurnBy(dx > 0 and -1 or 1) -- pulling the picture right turns to the left
      dragX = x
    elseif math.abs(dy) >= DRAG_STEP then
      V.Tilt(dy > 0 and -1 or 1) -- pulling it up looks down
      dragY = y
    end
  end)
  -- Street Guess's countdown, over the top of the picture
  timerBox = CreateFrame("Frame", nil, view)
  timerBox:SetSize(84, 30)
  timerBox:SetPoint("TOP", 0, -6)
  timerBox:SetFrameLevel(view:GetFrameLevel() + 8)
  local tbg = timerBox:CreateTexture(nil, "BACKGROUND")
  tbg:SetAllPoints()
  tbg:SetColorTexture(0, 0, 0, 0.6)
  timerBox.text = timerBox:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  timerBox.text:SetPoint("CENTER")
  timerBox:Hide()
  -- the game's logo on its brown plate, half above the title bar (the user, 2026-09-30); the
  -- corner portrait goes while it shows (V.GameLook)
  gameLogo = CreateFrame("Frame", nil, frame)
  gameLogo:SetSize(GAME_LOGO, GAME_LOGO)
  -- (the top-left corner, where the portrait is otherwise: the user, 2026-09-30; sticking out a
  -- little past the left edge, as the portrait does)
  gameLogo:SetPoint("CENTER", frame, "TOPLEFT", GAME_LOGO * 0.42, chrome and CHROME_TITLE / 2 or -(PAD + TITLE_H / 2))
  gameLogo:SetFrameLevel(frame:GetFrameLevel() + 30)
  local logoTex = gameLogo:CreateTexture(nil, "ARTWORK")
  logoTex:SetAllPoints()
  logoTex:SetTexture(MEDIA .. "GameLogo")
  MoveHandle(gameLogo)
  gameLogo:Hide()
  -- hidden, tiny textures: the views next to this one load ahead of time
  preload = {}
  for i = 1, 4 do
    local t = view:CreateTexture(nil, "BACKGROUND")
    t:SetSize(1, 1)
    t:SetPoint("TOPLEFT")
    t:SetAlpha(0)
    preload[i] = t
  end

  view:SetScript("OnSizeChanged", function()
    if cur and cur.pano then V.Refresh() end
  end)

  -- resize from the corner (the picture keeps its 2:1 shape); above the game frame's border
  local grip = CreateFrame("Button", nil, frame)
  grip:SetSize(16, 16)
  grip:SetPoint("BOTTOMRIGHT", -4, 4)
  grip:SetFrameLevel(frame:GetFrameLevel() + 14)
  local gbg = grip:CreateTexture(nil, "BACKGROUND") -- (visible even if the old art is missing here)
  gbg:SetPoint("BOTTOMRIGHT")
  gbg:SetSize(8, 8)
  gbg:SetColorTexture(0.6, 0.5, 0.25, 0.6)
  grip:SetNormalTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Up")
  grip:SetHighlightTexture("Interface\\ChatFrame\\UI-ChatIM-SizeGrabber-Highlight")
  grip:SetScript("OnMouseDown", function(self)
    self.sizing = true
  end)
  grip:SetScript("OnMouseUp", function(self)
    self.sizing = false
    SavePosition()
  end)
  grip:SetScript("OnUpdate", function(self)
    if not self.sizing then return end
    local x = GetCursorPosition() / frame:GetEffectiveScale()
    local l, t = frame:GetLeft(), frame:GetTop()
    frame:ClearAllPoints()
    frame:SetPoint("TOPLEFT", UIParent, "BOTTOMLEFT", l, t)
    SetWidth(x - l)
  end)

  frame:SetScript("OnUpdate", V.MoveStep) -- (idle unless a move is being animated)
  frame:SetScript("OnHide", function()
    if ns.Figure then ns.Figure.Redraw() end
  end)
end

-- The title: the spot's zone and map coordinates (a game's street view: neither).
local function Title(p)
  if cur and cur.game then return SetTitle("") end -- (the game's logo sits on the title bar)
  local API = _G.AzerothGPS
  local where = p.zone or "?"
  local mapID, zone, u, v
  if API then mapID, zone, u, v = API.LocateWorld(p.cont, p.x, p.y) end -- (not `API and ...`: one value only)
  if mapID then where = string.format("%s  %.1f, %.1f", zone, u * 100, v * 100) end
  SetTitle(where)
end

local function HideTiles()
  for _, tex in pairs(tiles) do tex:Hide() end
end

-- The way-to-go arrows (white chevrons, like Google's): one per road leaving the spot and per
-- nearby street view, standing on the ground in their direction. Hidden while the view is
-- being dragged. Clicking one goes to the next street view that way.
local function NewArrow(i)
  local b = CreateFrame("Button", nil, view)
  b:SetSize(ARROW_SIZE, ARROW_SIZE)
  b:SetFrameLevel(view:GetFrameLevel() + 5)
  b.tex = b:CreateTexture(nil, "OVERLAY")
  b.tex:SetAllPoints()
  b.tex:SetTexture(MEDIA .. "Arrow")
  b:RegisterForClicks("LeftButtonUp")
  b:SetScript("OnClick", function(self) V.GoToward(self.heading) end)
  b:SetScript("OnEnter", function(self)
    self.tex:SetVertexColor(1, 0.85, 0.35)
    GameTooltip:SetOwner(self, "ANCHOR_TOP")
    GameTooltip:SetText("Go " .. D.Compass(self.heading), 1, 1, 1)
    GameTooltip:Show()
  end)
  b:SetScript("OnLeave", function(self)
    self.tex:SetVertexColor(1, 1, 1)
    GameTooltip_Hide()
  end)
  b:Hide()
  arrows[i] = b
  return b
end

HideArrows = function()
  for _, b in ipairs(arrows) do b:Hide() end
end

-- Place the arrows for a view looking along centerHeading (radians); project(dir) gives
-- where the ground that way appears (x, y from the window's top-left), nil when behind. An
-- arrow whose spot on the ground is below the view stays at its bottom edge, so the ways on
-- are always in sight.
local function PlaceArrowsAt(centerHeading, project)
  local dirs = cur and cur.dirs
  if dragging or move or not dirs or not centerHeading then return HideArrows() end
  local w, h = view:GetWidth(), view:GetHeight()
  for i, dir in ipairs(dirs) do
    local b = arrows[i] or NewArrow(i)
    local rel = math.deg(D.AngleDiff(centerHeading, dir)) -- degrees to the right
    local x, y = project(dir)
    if y then y = math.min(y, h - ARROW_SIZE * 0.75) end
    if x and y and y > ARROW_SIZE / 2 and x > ARROW_SIZE / 2 and x < w - ARROW_SIZE / 2 then
      b.heading = dir
      b:ClearAllPoints()
      b:SetPoint("CENTER", view, "TOPLEFT", x, -y)
      b.tex:SetRotation(-math.rad(rel) * 0.6) -- (leaning the way it points, as on the ground)
      b:Show()
    else
      b:Hide()
    end
  end
  for i = #dirs + 1, #arrows do arrows[i]:Hide() end
end

-- ... for a flat view: looking along centerHeading, tilted centerLat degrees, ppd UI units a degree.
local function PlaceArrows(centerHeading, centerLat, ppd)
  local w, h = view:GetWidth(), view:GetHeight()
  local top = centerLat + h / ppd / 2
  PlaceArrowsAt(centerHeading, function(dir)
    return w / 2 + math.deg(D.AngleDiff(centerHeading, dir)) * ppd, (top - ARROW_LAT) * ppd
  end)
end

local function HideCells(from, pool)
  pool = pool or cells
  for i = from or 1, #pool do pool[i]:Hide() end
end

-- Lay a list of cube cells (D.CubeCells) out as the textures in `pool`.
local function DrawCells(p, list, pool, layer, alpha)
  for i, c in ipairs(list) do
    local tex = pool[i]
    if not tex then
      tex = view:CreateTexture(nil, layer)
      if tex.SetSnapToPixelGrid then tex:SetSnapToPixelGrid(false) end
      if tex.SetTexelSnappingBias then tex:SetTexelSnappingBias(0) end
      pool[i] = tex
    end
    local path = D.CubePath(p, c.face, c.col, c.row)
    if tex.path ~= path then
      if tex:SetTexture(path, "CLAMP", "CLAMP") == false then tex:SetColorTexture(0.06, 0.06, 0.08, 1) end
      tex.path = path
    end
    tex:ClearAllPoints()
    tex:SetPoint("TOPLEFT", view, "TOPLEFT", c.x, -c.y)
    tex:SetSize(c.cw + 0.5, c.ch + 0.5) -- (a hair of overlap: no seams between cells)
    local uv = c.uv
    tex:SetTexCoord(uv[1], uv[2], uv[3], uv[4], uv[5], uv[6], uv[7], uv[8])
    tex:SetAlpha(alpha)
    tex:Show()
  end
  HideCells(#list + 1, pool)
end

-- The cube view: the window as a grid of small cells, each cut from the cube in perspective.
local function CubeRefresh()
  local p = cur.p
  img:Hide()
  missing:Hide()
  HideTiles()
  local w, h = view:GetWidth(), view:GetHeight()
  if not w or w <= 0 or not h or h <= 0 then return end
  cur.lon = (cur.lon + 180) % 360 - 180
  cur.lat = math.max(-MAX_LAT, math.min(MAX_LAT, cur.lat))
  local blur = cur.blur or 0
  DrawCells(p, D.CubeCells(p, cur.lon, cur.lat, cur.fov, w, h, GRID_COLS, GRID_ROWS), cells, "ARTWORK", 1)
  -- moving up the road: a faint copy zoomed a little further in over it reads as motion blur
  -- (there's no real blur for addons; only for the half second of the move)
  local g = cur.ghost -- (arriving: the last spot's view, zoomed in toward here, fading into this one)
  if g then
    DrawCells(g.p, D.CubeCells(g.p, g.lon, g.lat, g.fov, w, h, GRID_COLS, GRID_ROWS), ghosts, "OVERLAY", g.alpha)
  elseif blur > 0 then
    DrawCells(p, D.CubeCells(p, cur.lon, cur.lat, cur.fov * (1 - GHOST_ZOOM * blur), w, h, GRID_COLS, GRID_ROWS),
      ghosts, "OVERLAY", GHOST_ALPHA * blur)
  else
    HideCells(1, ghosts)
  end
  Title(p)
  local heading = D.PanoHeading(p, cur.lon)
  local tilt = math.floor(cur.lat + 0.5)
  local looking = tilt == 0 and "level" or (tilt > 0 and ("looking up " .. tilt) or ("looking down " .. -tilt))
  info:SetText(D.Compass(heading) .. "  " .. looking)
  PlaceArrowsAt(heading, function(dir)
    return D.CubeProject(p, cur.lon, cur.lat, cur.fov, w, h, dir, -ARROW_LAT)
  end)
  if ns.Figure and (not lastMarkHeading or math.abs(D.AngleDiff(heading, lastMarkHeading)) > 0.03) then
    lastMarkHeading = heading
    ns.Figure.Redraw()
  end
end

-- The panorama: the tiles in view, laid flat and slid into place.
local function PanoRefresh()
  local p = cur.p
  img:Hide()
  missing:Hide()
  local w, h = view:GetWidth(), view:GetHeight()
  if not w or w <= 0 or not h or h <= 0 then return end
  cur.lon = (cur.lon + 180) % 360 - 180
  local list, lat = D.PanoTiles(p, cur.lon, cur.lat, cur.fov, w, h)
  cur.lat = lat
  local used = {}
  for _, t in ipairs(list) do
    local key = t.col * 100 + t.row
    local tex = tiles[key]
    if not tex then
      tex = view:CreateTexture(nil, "ARTWORK")
      if tex.SetSnapToPixelGrid then tex:SetSnapToPixelGrid(false) end
      if tex.SetTexelSnappingBias then tex:SetTexelSnappingBias(0) end
      tiles[key] = tex
    end
    local path = D.PanoPath(p, t.col, t.row)
    if tex.path ~= path then
      if tex:SetTexture(path) == false then tex:SetColorTexture(0.06, 0.06, 0.08, 1) end
      tex.path = path
    end
    tex:ClearAllPoints()
    tex:SetPoint("TOPLEFT", view, "TOPLEFT", t.x, -t.y)
    tex:SetSize(t.size, t.size)
    tex:Show()
    used[key] = true
  end
  for key, tex in pairs(tiles) do
    if not used[key] then tex:Hide() end
  end
  Title(p)
  local heading = D.PanoHeading(p, cur.lon)
  local tilt = math.floor(cur.lat + 0.5)
  local looking = tilt == 0 and "level" or (tilt > 0 and ("looking up " .. tilt) or ("looking down " .. -tilt))
  info:SetText(D.Compass(heading) .. "  " .. looking)
  PlaceArrows(heading, cur.lat, w / cur.fov)
  -- the map's marker: only when the heading moved noticeably (map redraws aren't free)
  if ns.Figure and (not lastMarkHeading or math.abs(D.AngleDiff(heading, lastMarkHeading)) > 0.03) then
    lastMarkHeading = heading
    ns.Figure.Redraw()
  end
end

-- Draw the current view.
function V.Refresh()
  if not frame or not cur then return end
  if cur.cube then return CubeRefresh() end
  HideCells()
  HideCells(1, ghosts)
  if cur.pano then return PanoRefresh() end
  HideTiles()
  img:Show()
  local p, pitch = cur.p, D.PITCHES[cur.pitch]
  local path = D.ImagePath(p, cur.yaw, pitch)
  local loaded = D.HasPose(p, cur.yaw, pitch) and img:SetTexture(path)
  if loaded == false or not D.HasPose(p, cur.yaw, pitch) then
    img:SetColorTexture(0.06, 0.06, 0.08, 1)
    missing:SetText("No picture for this view yet\n|cff999999" .. D.PoseName(cur.yaw, pitch) .. "|r")
    missing:Show()
  else
    missing:Hide()
  end
  local heading = D.Heading(p, cur.yaw)
  Title(p)
  if pitch == 90 or pitch == -90 then
    HideArrows()
  else
    PlaceArrows(heading, pitch, view:GetWidth() / STEP_HFOV)
  end
  local facing = (pitch == 90 or pitch == -90) and "" or (D.Compass(heading) .. "  ")
  info:SetText(facing .. PITCH_NAMES[pitch])
  -- load the neighbors ahead of time
  if pitch ~= 90 and pitch ~= -90 then
    preload[1]:SetTexture(D.ImagePath(p, D.Turn(p, cur.yaw, 1), pitch))
    preload[2]:SetTexture(D.ImagePath(p, D.Turn(p, cur.yaw, -1), pitch))
  end
  if cur.pitch > 1 then preload[3]:SetTexture(D.ImagePath(p, cur.yaw, D.PITCHES[cur.pitch - 1])) end
  if cur.pitch < #D.PITCHES then preload[4]:SetTexture(D.ImagePath(p, cur.yaw, D.PITCHES[cur.pitch + 1])) end
  if ns.Figure then ns.Figure.Redraw() end
end

-- Open point p looking toward `heading` (radians, counter-clockwise from north; default its
-- first view), level. game: Street Guess's view (no place name, no walking on, not on the map).
-- A game's look (on) or the viewer's own: the game's logo in the top-left corner instead of the
-- portrait.
-- The highest frame level among `f` and everything under it (the game frame's border, title bar
-- and close button sit in child frames of their own).
local function TopLevel(f, best)
  best = math.max(best or 0, f:GetFrameLevel())
  for _, c in ipairs({ f:GetChildren() }) do
    if c ~= gameLogo then best = TopLevel(c, best) end
  end
  return best
end

function V.GameLook(on)
  if not frame then return end
  if on then -- (over the title bar: above every part of the game frame)
    gameLogo:SetFrameStrata(frame:GetFrameStrata())
    gameLogo:SetFrameLevel(math.min(9000, TopLevel(chrome or frame) + 5))
  end
  gameLogo:SetShown(on)
  if chrome then
    if chrome.SetBorder then
      pcall(chrome.SetBorder, chrome, on and "ButtonFrameTemplateNoPortrait" or "PortraitFrameTemplate")
    end
    local portrait = chrome.GetPortrait and chrome:GetPortrait() or (chrome.PortraitContainer and chrome.PortraitContainer.portrait)
    if portrait then portrait:SetShown(not on) end
  elseif badge then
    badge:SetShown(not on)
  end
end

function V.Open(p, heading, game)
  if not frame then V.Build() end
  if D.HasCube(p) then
    cur = { p = p, pano = true, cube = true, lon = heading and D.PanoLon(p, heading) or 0, lat = 0,
      fov = CUBE_FOV } -- (every spot opens fully zoomed out, Go ahead too)
  elseif D.HasPano(p) then
    cur = { p = p, pano = true, lon = heading and D.PanoLon(p, heading) or 0, lat = 0, fov = (cur and cur.fov) or FOV }
  else
    cur = { p = p, yaw = heading and D.YawFor(p, heading) or 0, pitch = D.LEVEL }
  end
  local API = _G.AzerothGPS
  cur.game = game or nil
  if not game then timerBox:Hide() end
  cur.dirs = not game and D.Directions(p, API and API.Roads and API.Roads(p.cont)) or nil
  if ahead.SetEnabled then ahead:SetEnabled(not game) end -- (hidden: V.GoAhead stays for the arrows)
  lastMarkHeading = nil
  V.GameLook(game and true or false)
  frame:Show()
  V.Refresh()
end

function V.Hide()
  if frame then frame:Hide() end
end

-- Street Guess's countdown on the picture (text, nil: none).
function V.SetTimer(text)
  if not timerBox then return end
  if text and cur and cur.game then
    timerBox.text:SetText(text)
    timerBox:Show()
  else
    timerBox:Hide()
  end
end

-- Close the viewer if it shows Street Guess's view.
function V.CloseGame()
  V.SetTimer(nil)
  if cur and cur.game then
    cur = nil
    if frame then frame:Hide() end
  end
end

function V.TurnBy(dir)
  if not cur then return end
  if cur.pano then
    cur.lon = cur.lon + dir * TURN_DEG -- (right: clockwise)
    return V.Refresh()
  end
  local pitch = D.PITCHES[cur.pitch]
  if pitch == 90 or pitch == -90 then cur.pitch = D.LEVEL end -- (straight up/down: back to level first)
  cur.yaw = D.Turn(cur.p, cur.yaw, dir)
  V.Refresh()
end

function V.Tilt(dir)
  if not cur then return end
  if cur.pano then
    cur.lat = cur.lat + dir * TILT_DEG
    return V.Refresh()
  end
  cur.pitch = math.max(1, math.min(#D.PITCHES, cur.pitch + dir))
  V.Refresh()
end

-- Panorama zoom: the mouse wheel narrows or widens the view.
function V.Zoom(delta)
  if not (cur and cur.pano) then return end
  cur.fov = math.max(FOV_MIN, math.min(FOV_MAX, cur.fov * (delta > 0 and 0.85 or 1 / 0.85)))
  V.Refresh()
end

-- The next street view toward `heading` (the nearest within 50 degrees of it and
-- D.NEXT_RANGE yards), looking that way.
function V.GoToward(heading)
  if not cur or not heading or cur.game or move then return end
  local q = D.Ahead(cur.p, heading)
  if not q then
    UIErrorsFrame:AddMessage("No street view that way yet", 1, 0.82, 0)
    return
  end
  if not (cur.cube and D.HasCube(q) and GetTime) then return V.Open(q, heading) end
  -- like Google's: turn to face the way, zoom in toward it with a blur, then settle at the next
  -- spot (its pictures start loading now, hidden)
  local i = 0
  for _, face in ipairs(D.FACE_NAMES) do
    for col = 0, 1 do
      for row = 0, 1 do
        i = i + 1
        local t = preload[i]
        if not t then
          t = view:CreateTexture(nil, "BACKGROUND")
          t:SetSize(1, 1)
          t:SetPoint("TOPLEFT")
          t:SetAlpha(0)
          preload[i] = t
        end
        t:SetTexture(D.CubePath(q, face, col, row))
      end
    end
  end
  local lon1 = D.PanoLon(cur.p, heading)
  move = { stage = 1, t0 = GetTime(), q = q, heading = heading, lon0 = cur.lon,
    dlon = (lon1 - cur.lon + 180) % 360 - 180, lat0 = cur.lat, fov0 = cur.fov }
  HideArrows()
end

local function Ease(t) return t < 0.5 and 2 * t * t or 1 - (-2 * t + 2) ^ 2 / 2 end

-- The move's frames (V.Build's driver).
function V.MoveStep()
  if not move then return end
  if not cur or not frame:IsShown() then move = nil return end
  local t = (GetTime() - move.t0) / (move.stage == 1 and MOVE_OUT or MOVE_IN)
  local k = Ease(math.min(1, t))
  if move.stage == 1 then
    cur.lon = move.lon0 + move.dlon * k
    cur.lat = move.lat0 * (1 - k)
    cur.fov = move.fov0 * (1 - MOVE_ZOOM * k)
    cur.blur = k
    V.Refresh()
    if t >= 1 then
      -- arrive: the next spot at its normal zoom, under the last view still zooming in and fading
      -- out (one continuous move forward, never back out)
      local q, heading = move.q, move.heading
      local ghost = { p = cur.p, lon = cur.lon, lat = cur.lat, fov0 = cur.fov, fov = cur.fov, alpha = 1 }
      move = { stage = 2, t0 = GetTime(), ghost = ghost } -- (set first: the arrows stay hidden while it arrives)
      V.Open(q, heading)
      cur.ghost = ghost
      V.Refresh()
    end
  else
    local g = move.ghost
    g.fov = g.fov0 * (1 - MOVE_ZOOM * 0.5 * k) -- (still moving forward as it fades)
    g.alpha = 1 - k
    if t >= 1 then
      cur.ghost = nil
      move = nil
    end
    V.Refresh()
  end
end

function V.GoAhead()
  if cur then V.GoToward(V.Heading()) end
end

-- The view shown (nil when the window is closed): { p, yaw, pitch }, and its heading.
function V.Current()
  if frame and frame:IsShown() and cur then return cur end
end
function V.Heading()
  if not cur then return 0 end
  if cur.pano then return D.PanoHeading(cur.p, cur.lon) end
  return D.Heading(cur.p, cur.yaw)
end

-- Show a JPEG shipped with the addon, to check this client draws JPEG files at all.
function V.Probe()
  if not frame then V.Build() end
  cur = nil
  HideTiles()
  HideCells()
  HideArrows()
  img:Show()
  frame:Show()
  local ok = img:SetTexture(MEDIA .. "Probe.jpg")
  SetTitle("JPEG check")
  info:SetText("")
  if ok == false then
    img:SetColorTexture(0.2, 0.02, 0.02, 1)
    missing:SetText("This client did not load the JPEG test image.\n(New files need a full game restart, not /reload.)")
    missing:Show()
    ns.Print("JPEG check: |cffff6060failed|r. Tell Claude: the viewer needs BLP images instead.")
  else
    missing:Hide()
    ns.Print("JPEG check: the game accepted the file. You should see a blue and orange test card saying JPEG OK.")
  end
end
