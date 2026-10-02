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

local frame, chrome, view, img, missing, title, info, preload, ahead, hud, gameLogo, badge
local HUD_PAD, HUD_LINES, HUD_MIN_W = 8, 4, 110 -- the game's corner box: its inset, lines under the time, least width
local HUD_FOLD, HUD_ROW = 16, 14 -- ... its fold button's size; the player list's rows
local HUD_WAVE = 4 -- ... a winner's name rolling: a letter at the wave's crest this much bigger (font pixels)
-- Where in the Azeroth?'s logo over the title bar while a game shows (Media/GameLogo.tga, square:
-- the logo fills its width, about 3/4 of its height): this wide, in the top-left corner
local GAME_LOGO = 141 -- (176 less 20%: the user, 2026-09-30)
local SV_LOGO = 94 -- StreetView's own logo there outside a game, the same way (Media/SvLogo<px>.tga; 104 less 10%: the user, 2026-09-30)
-- ... drawn from Media/GameLogo<px>.tga, the logo pre-scaled to px pixels (svtools/media.py
-- GAME_LOGO_PX): the size nearest its real pixels on this screen is shown 1:1, not a big picture
-- shrunk by the graphics card
local GAME_LOGO_PX = { 72, 80, 88, 96, 104, 112, 120, 128, 144, 160, 176, 192, 208, 224, 256, 288 }
local tiles = {} -- panorama tile textures by col * 100 + row
local cells = {} -- cube view cell textures
local ghosts = {} -- ... a second copy, zoomed a little further, faint: the blur of a move up the road
local move -- the move to the next spot being animated (V.GoToward)
-- The map following the arrows (the user, 2026-10-02): from the first arrow clicked in a viewing, the AzerothGPS
-- map centers on each spot walked to; closing the street view puts the map back as it was before that first
-- click, unless the player moved the map meanwhile: then it's left alone for the rest of the viewing.
-- { saved = AzerothGPS.SaveView(), x, y, cont, zoom (where the map was put last), off = true (moved by the player) }
local follow
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
  title:SetPoint("LEFT", 100, 0) -- (clear of the corner logo)
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
  -- Where in the Azeroth?'s box in the picture's top-right corner (the user, 2026-10-01; V.SetHud): the
  -- level and the round, the time left large, and a few lines under it
  hud = CreateFrame("Frame", nil, view)
  hud:SetPoint("TOPRIGHT", -8, -8)
  hud:SetFrameLevel(view:GetFrameLevel() + 8)
  local hbg = hud:CreateTexture(nil, "BACKGROUND")
  hbg:SetAllPoints()
  hbg:SetColorTexture(0, 0, 0, 0.6)
  hud.head = hud:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  hud.head:SetPoint("TOPRIGHT", -HUD_PAD, -HUD_PAD)
  hud.big = hud:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  if _G.GameFontNormalHuge then hud.big:SetFontObject(_G.GameFontNormalHuge) end
  hud.head:SetJustifyH("RIGHT")
  hud.big:SetJustifyH("RIGHT")
  hud.lines = {}
  for i = 1, HUD_LINES do
    hud.lines[i] = hud:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    hud.lines[i]:SetJustifyH("RIGHT")
  end
  hud.rows = {} -- (the player list's rows: made as they're needed)
  -- the list's mouse wheel (more players than it shows: it scrolls them) and its bar at the right
  local list = CreateFrame("Frame", nil, hud)
  list:SetScript("OnMouseWheel", function(_, delta) if V.OnHudWheel then V.OnHudWheel(delta) end end)
  list:Hide()
  local track = list:CreateTexture(nil, "ARTWORK")
  track:SetColorTexture(1, 1, 1, 0.1)
  track:SetWidth(3)
  track:SetPoint("TOPRIGHT")
  track:SetPoint("BOTTOMRIGHT")
  list.thumb = list:CreateTexture(nil, "OVERLAY")
  list.thumb:SetColorTexture(1, 0.82, 0, 0.7)
  list.thumb:SetWidth(3)
  hud.list = list
  -- "-" folds the box to the time left (or the round's points), "+" opens it (the user, 2026-10-01: for a
  -- better view); kept between games
  local fold = CreateFrame("Button", nil, hud)
  fold:SetSize(HUD_FOLD, HUD_FOLD)
  fold:SetPoint("TOPLEFT", 4, -4)
  local edge = fold:CreateTexture(nil, "BACKGROUND")
  edge:SetAllPoints()
  edge:SetColorTexture(1, 0.82, 0, 0.55)
  local fill = fold:CreateTexture(nil, "BORDER")
  fill:SetPoint("TOPLEFT", 1, -1)
  fill:SetPoint("BOTTOMRIGHT", -1, 1)
  fill:SetColorTexture(0.1, 0.08, 0.03, 0.95)
  local lit = fold:CreateTexture(nil, "HIGHLIGHT")
  lit:SetAllPoints()
  lit:SetColorTexture(1, 1, 1, 0.15)
  fold.label = fold:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  fold.label:SetPoint("CENTER", 0, 1)
  fold:SetScript("OnClick", function()
    ns.db.viewer.hudFolded = not ns.db.viewer.hudFolded or nil
    V.SetHud(hud.last, true)
  end)
  fold:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:SetText(ns.db.viewer.hudFolded and "Show the details" or "Hide the details", 1, 1, 1)
    GameTooltip:AddLine(ns.db.viewer.hudFolded and "The round, what it's worth and the players."
      or "Only the time left stays, for a better view.", nil, nil, nil, true)
    GameTooltip:Show()
  end)
  fold:SetScript("OnLeave", GameTooltip_Hide)
  hud.fold = fold
  -- the celebration (as the map's panel): a soft glow around the box, its colors drifting (V.AnimateHud)
  local glow = CreateFrame("Frame", nil, hud, "BackdropTemplate")
  glow:SetPoint("TOPLEFT", -3, 3)
  glow:SetPoint("BOTTOMRIGHT", 3, -3)
  glow:SetFrameLevel(math.max(0, hud:GetFrameLevel() - 1))
  if glow.SetBackdrop then glow:SetBackdrop({ edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 3 }) end
  glow:Hide()
  hud.glow = glow
  hud.wash = hud:CreateTexture(nil, "BORDER")
  hud.wash:SetAllPoints()
  hud.wash:SetColorTexture(1, 1, 1, 0)
  hud.wash:Hide()
  hud.waves = {} -- (the winners' names, a letter each: made as they're needed)
  hud:Hide()
  -- the corner logo on its brown plate, half above the title bar, in place of the round portrait:
  -- the game's during a game, StreetView's otherwise (the user, 2026-09-30; V.GameLook)
  gameLogo = CreateFrame("Frame", nil, frame)
  gameLogo:SetSize(GAME_LOGO, GAME_LOGO)
  -- (the top-left corner, where the portrait is otherwise: the user, 2026-09-30; sticking out a
  -- little past the left edge, as the portrait does)
  -- (its size, picture and place: FitLogo)
  gameLogo:SetFrameLevel(frame:GetFrameLevel() + 30)
  local logoTex = gameLogo:CreateTexture(nil, "ARTWORK")
  logoTex:SetAllPoints()
  gameLogo.tex = logoTex
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
    V.MapFollowEnd()
    if ns.Figure then ns.Figure.Redraw() end
  end)
end

-- The title: the spot's zone and map coordinates (a game's street view: neither; a spot with a `title` of
-- its own, the dev addon's comparisons: that).
local function Title(p)
  if cur and cur.game then return SetTitle("") end -- (the game's logo sits on the title bar)
  if type(p.title) == "string" then return SetTitle(p.title) end
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

-- The logo's picture for this screen: the pre-scaled size nearest the pixels GAME_LOGO UI units
-- cover, shown at exactly that many pixels.
local function FitLogo(game)
  local ppu = 1 -- screen pixels per UI unit of the viewer
  if GetPhysicalScreenSize then
    local _, h = GetPhysicalScreenSize()
    if h and h > 0 then ppu = h / 768 * frame:GetEffectiveScale() end
  end
  local units = game and GAME_LOGO or SV_LOGO
  local want, px = units * ppu, GAME_LOGO_PX[1]
  for _, s in ipairs(GAME_LOGO_PX) do
    if math.abs(s - want) < math.abs(px - want) then px = s end
  end
  local pot = 1
  while pot < px do pot = pot * 2 end
  gameLogo.tex:SetTexture(MEDIA .. (game and "GameLogo" or "SvLogo") .. px)
  gameLogo.tex:SetTexCoord(0, px / pot, 0, px / pot)
  if gameLogo.tex.SetSnapToPixelGrid then gameLogo.tex:SetSnapToPixelGrid(true) end
  local size = px / ppu
  gameLogo:SetSize(size, size)
  gameLogo:ClearAllPoints()
  gameLogo:SetPoint("CENTER", frame, "TOPLEFT", size * 0.42, chrome and CHROME_TITLE / 2 or -(PAD + TITLE_H / 2))
end

-- The corner logo: the game's in a game (on), else StreetView's; both on their brown plates in
-- place of the round portrait (the user, 2026-09-30).
function V.GameLook(on)
  if not frame then return end
  FitLogo(on)
  gameLogo:SetFrameStrata(frame:GetFrameStrata()) -- (over the title bar: above every part of the frame)
  gameLogo:SetFrameLevel(math.min(9000, TopLevel(chrome or frame) + 5))
  gameLogo:Show()
  if chrome then
    if chrome.SetBorder then pcall(chrome.SetBorder, chrome, "ButtonFrameTemplateNoPortrait") end
    local portrait = chrome.GetPortrait and chrome:GetPortrait() or (chrome.PortraitContainer and chrome.PortraitContainer.portrait)
    if portrait then portrait:Hide() end
  elseif badge then
    badge:Hide()
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
  if not game then V.SetHud(nil) end
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

-- A row of the corner box's player list: the name at the left, the round's points and the total at the right.
local function HudRow(k)
  local row = hud.rows[k]
  if row then return row end
  row = {}
  for _, part in ipairs({ "name", "last", "total" }) do
    row[part] = hud:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    row[part]:SetJustifyH(part == "name" and "LEFT" or "RIGHT")
  end
  hud.rows[k] = row
  return row
end

-- A winner's name in the corner box's list, a font string per letter (UTF-8 characters), rolling: a wave runs
-- through it, each letter growing and taking the celebration's colors in turn (V.AnimateHud). After the
-- row's rank ("1."), then "(you)" after it when it's this player.
local function HudWave(k)
  local w = hud.waves[k]
  if not w then
    w = { letters = {} }
    w.you = hud:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    hud.waves[k] = w
  end
  return w
end

local function SetWave(w, row, r)
  local font, size, flags = row.name:GetFont()
  w.font, w.size, w.flags, w.anchor = font, math.floor((size or 10) + 0.5), flags, row.name
  local n = 0
  for ch in tostring(r.who):gmatch("[\1-\127\194-\244][\128-\191]*") do
    n = n + 1
    local l = w.letters[n]
    if not l then
      l = hud:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
      w.letters[n] = l
    end
    l:SetText(ch)
    l.px = nil
    l:Show()
  end
  for i = n + 1, #w.letters do w.letters[i]:Hide() end
  w.n = n
  w.you:SetText(r.you and "|cff9d9d9d(you)|r" or "")
  w.you:Show()
  w.on = true
end

local function HideWave(w)
  w.on = false
  for _, l in ipairs(w.letters) do l:Hide() end
  w.you:Hide()
end

-- The corner box's motion (its OnUpdate while it has any): the glow's colors, the winners' names rolling.
function V.AnimateHud(t)
  local h = hud and hud.last
  if not h then return end
  local colors = h.colors
  if hud.glow:IsShown() and colors then
    local r, g, b, pulse = colors(t)
    if hud.glow.SetBackdropBorderColor then hud.glow:SetBackdropBorderColor(r, g, b, pulse) end
    hud.wash:SetColorTexture(r, g, b, 0.08 + 0.05 * math.sin(t * 2.4))
  end
  for _, w in ipairs(hud.waves) do
    if w.on then
      local x = 4
      for i = 1, w.n do
        local l = w.letters[i]
        local bump = math.max(0, math.sin(t * 5 - i * 0.55)) ^ 2 -- (the wave: one crest rolling along)
        local px = w.size + math.floor(HUD_WAVE * bump + 0.5)
        if l.px ~= px and w.font then
          l:SetFont(w.font, px, w.flags)
          l.px = px
        end
        if colors then
          local r, g, b = colors(t * 2 - i * 0.6)
          l:SetTextColor(r, g, b)
        end
        l:ClearAllPoints()
        l:SetPoint("BOTTOMLEFT", w.anchor, "BOTTOMRIGHT", x, 0) -- (on the row's baseline: letters grow upward)
        x = x + l:GetStringWidth()
      end
      w.you:ClearAllPoints()
      w.you:SetPoint("BOTTOMLEFT", w.anchor, "BOTTOMRIGHT", x + 4, 0)
    end
  end
end

-- Where in the Azeroth?'s corner box (h: Gm.Hud's { head, big, lines, board, celebrate, colors }; nil: none). Called ten times a
-- second: laid out again only when what it shows changes (`force`: anyway). Folded ("-"): only the time
-- left, or the round's points, beside "+".
function V.SetHud(h, force)
  if not hud then return end
  if not (h and cur and cur.game) then
    hud.key, hud.last = nil, nil
    return hud:Hide()
  end
  hud.last = h
  local folded = ns.db.viewer.hudFolded and true or false
  local lines, board = h.lines or {}, h.board or { rows = {}, n = 0, offset = 0, window = 0 }
  local parts = { h.head or "", h.big or "", tostring(folded), board.n, board.offset, tostring(h.celebrate) }
  for _, s in ipairs(lines) do parts[#parts + 1] = s end
  for _, r in ipairs(board.rows) do
    parts[#parts + 1] = r.name .. "\2" .. r.last .. "\2" .. r.total .. "\2" .. tostring(r.winner)
  end
  local key = table.concat(parts, "\1")
  if key == hud.key and hud:IsShown() and not force then return end
  hud.key = key
  hud.fold.label:SetText(folded and "+" or "-")
  -- (the first line leaves room for the fold button at its left)
  local above, height, width = nil, HUD_PAD, 0
  local showHead = not folded or not h.big
  hud.head:SetShown(showHead)
  if showHead then
    hud.head:SetText(h.head or "")
    above, height, width = hud.head, HUD_PAD + hud.head:GetStringHeight(), hud.head:GetStringWidth() + HUD_FOLD + 6
  end
  hud.big:SetShown(h.big ~= nil)
  if h.big then
    hud.big:SetText(h.big)
    hud.big:ClearAllPoints()
    if above then
      hud.big:SetPoint("TOPRIGHT", above, "BOTTOMRIGHT", 0, -2)
      height = height + 2
    else
      hud.big:SetPoint("TOPRIGHT", -HUD_PAD, -HUD_PAD)
    end
    width = math.max(width, hud.big:GetStringWidth() + (above and 0 or HUD_FOLD + 6))
    above, height = hud.big, height + hud.big:GetStringHeight()
  end
  for i, s in ipairs(hud.lines) do
    local text = not folded and lines[i] or nil
    s:SetShown(text ~= nil)
    if text then
      s:SetText(text)
      s:ClearAllPoints()
      s:SetPoint("TOPRIGHT", above, "BOTTOMRIGHT", 0, -3)
      above, height, width = s, height + 3 + s:GetStringHeight(), math.max(width, s:GetStringWidth())
    end
  end
  -- the player list: the names at the left, the round's points and the totals in columns at the right
  local rows = folded and {} or board.rows
  local scrolls = #rows > 0 and board.n > board.window
  local bar = scrolls and 6 or 0
  local nameW, lastW, totalW = 0, 0, 0
  local rolling = false
  for k, r in ipairs(rows) do
    local row = HudRow(k)
    row.name:SetText(r.name)
    row.last:SetText(r.last)
    row.total:SetText(r.total)
    -- (a winner's name rolls: measured whole, with room for the wave's crest, then drawn a letter each)
    nameW = math.max(nameW, row.name:GetStringWidth() + (r.winner and HUD_WAVE * 3 or 0))
    lastW = math.max(lastW, row.last:GetStringWidth())
    totalW = math.max(totalW, row.total:GetStringWidth())
    if r.winner then
      row.name:SetText(r.rank)
      SetWave(HudWave(k), row, r)
      rolling = true
    elseif hud.waves[k] then
      HideWave(hud.waves[k])
    end
  end
  for k = #rows + 1, #hud.waves do HideWave(hud.waves[k]) end
  local top = height + 6
  for k, row in ipairs(hud.rows) do
    local r = rows[k]
    local on = r ~= nil
    row.name:SetShown(on)
    row.last:SetShown(on)
    row.total:SetShown(on)
    if on then
      local y = -(top + (k - 1) * HUD_ROW + (r.pinned and 3 or 0)) -- (this player's own, pinned: a little apart)
      row.name:ClearAllPoints()
      row.name:SetPoint("TOPLEFT", hud, "TOPLEFT", HUD_PAD, y)
      row.total:ClearAllPoints()
      row.total:SetPoint("TOPRIGHT", hud, "TOPRIGHT", -HUD_PAD - bar, y)
      row.last:ClearAllPoints()
      row.last:SetPoint("TOPRIGHT", hud, "TOPRIGHT", -HUD_PAD - bar - totalW - 10, y)
      height = top + k * HUD_ROW + (r.pinned and 3 or 0)
    end
  end
  if #rows > 0 then width = math.max(width, nameW + 12 + lastW + 10 + totalW + bar) end
  -- (more players than it shows: the mouse wheel over it scrolls, the bar shows where)
  local list = hud.list
  list:SetShown(scrolls)
  list:EnableMouseWheel(scrolls)
  if scrolls then
    local rowsH = board.window * HUD_ROW
    list:ClearAllPoints()
    list:SetPoint("TOPLEFT", hud, "TOPLEFT", 2, -top + 1)
    list:SetPoint("TOPRIGHT", hud, "TOPRIGHT", -HUD_PAD + 2, -top + 1)
    list:SetHeight(rowsH)
    local th = math.max(8, rowsH * board.window / board.n)
    list.thumb:ClearAllPoints()
    list.thumb:SetPoint("TOPRIGHT", list, "TOPRIGHT", 0, -(rowsH - th) * board.offset / math.max(1, board.n - board.window))
    list.thumb:SetHeight(th)
  end
  hud:SetSize(math.max(folded and 0 or HUD_MIN_W, width + 2 * HUD_PAD), height + HUD_PAD + 1)
  -- the celebration's glow, as on the map's panel; the motion only while there's some
  hud.glow:SetShown(h.celebrate == true)
  hud.wash:SetShown(h.celebrate == true)
  if h.celebrate or rolling then
    hud:SetScript("OnUpdate", function() V.AnimateHud(GetTime()) end)
    V.AnimateHud(GetTime and GetTime() or 0) -- (the letters placed now, not a frame later)
  else
    hud:SetScript("OnUpdate", nil)
  end
  hud:Show()
end

-- Close the viewer if it shows Street Guess's view.
function V.CloseGame()
  V.SetHud(nil)
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

-- For the dev addon's media shots (the pictures for the CurseForge page and the wiki): look a given way
-- (heading: radians counter-clockwise from north, as the map's; pitch up and the field of view across, in
-- degrees), turn by degrees (right and up: positive), and set the window's width and place (from the
-- screen's middle). A panorama or cube spot only (else false).
function V.LookAt(heading, pitch, fov)
  if not (cur and cur.pano) then return false end
  if heading then cur.lon = D.PanoLon(cur.p, heading) end
  if pitch then cur.lat = math.max(-MAX_LAT, math.min(MAX_LAT, pitch)) end
  if fov then cur.fov = math.max(FOV_MIN, math.min(FOV_MAX, fov)) end
  V.Refresh()
  return true
end

function V.Pan(dLon, dLat)
  if not (cur and cur.pano) then return false end
  cur.lon = cur.lon + (dLon or 0)
  cur.lat = math.max(-MAX_LAT, math.min(MAX_LAT, cur.lat + (dLat or 0)))
  V.Refresh()
  return true
end

function V.Place(width, x, y)
  if not frame then V.Build() end
  if width then SetWidth(width) end
  if x and y then
    frame:ClearAllPoints()
    frame:SetPoint("CENTER", UIParent, "CENTER", x, y)
  end
end

-- The game's corner box folded (on) or open, as its -/+ button does.
function V.SetHudFolded(on)
  ns.db.viewer.hudFolded = on and true or nil
  if hud and hud.last then V.SetHud(hud.last, true) end
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
  V.MapFollowStart()
  if not (cur.cube and D.HasCube(q) and GetTime) then
    V.Open(q, heading)
    return V.MapFollow(q)
  end
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

-- Where the map is now: x, y, its base continent, zoom (yards from the middle to the edge); nil without one.
local function MapAt()
  local API = _G.AzerothGPS
  if not (API and API.View) then return nil end
  local x, y, c, _, scale, half = API.View()
  if not (x and y and c) then return nil end
  local zoom = scale and half and scale > 0 and half / scale or nil
  return x, y, API.BaseContinent and API.BaseContinent(c) or c, zoom
end

-- Whether the player moved the map since it was last put on a spot (dragged, zoomed, back to their position).
local function MapMoved()
  if not (follow and follow.x) then return false end
  local x, y, c, zoom = MapAt()
  if not x then return false end
  if c ~= follow.cont or (x - follow.x) ^ 2 + (y - follow.y) ^ 2 > 4 then return true end
  return zoom ~= nil and follow.zoom ~= nil and math.abs(zoom - follow.zoom) > follow.zoom * 0.02
end

-- The first arrow clicked in a viewing: the map's view kept to come back to.
function V.MapFollowStart()
  local API = _G.AzerothGPS
  if follow or (cur and cur.game) or not (API and API.SaveView and API.LookAt) then return end
  follow = { saved = API.SaveView() }
end

-- Arrived at spot `p` by an arrow: the map on it, at the zoom it has (not once the player moved it).
function V.MapFollow(p)
  local API = _G.AzerothGPS
  if not follow or follow.off or (cur and cur.game) or not (API and API.LookAt) then return end
  if MapMoved() then
    follow.off = true
    return
  end
  local _, _, _, zoom = MapAt()
  zoom = zoom or follow.zoom
  API.LookAt(p.cont, p.x, p.y, zoom)
  follow.x, follow.y, follow.zoom = p.x, p.y, zoom
  follow.cont = API.BaseContinent and API.BaseContinent(p.cont) or p.cont
end

-- The street view closed: the map back where it was before the first arrow (unless the player moved it).
function V.MapFollowEnd()
  local f = follow
  if not f then return end
  local moved = f.off or MapMoved()
  follow = nil
  local API = _G.AzerothGPS
  if not moved and API and API.RestoreView then API.RestoreView(f.saved) end
end

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
      V.MapFollow(q)
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
