-- The street view window: one view at a time (2:1 images), turned with the arrows, the mouse
-- wheel or by dragging across the picture. Its spot and direction show on the AzerothGPS map.
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
local BAR_H = 30 -- the controls strip along the top
local CONTROLS_X = 60 -- controls start right of the portrait (or badge)
local MIN_W, MAX_W = 360, 1400
local DRAG_STEP = 60 -- UI units of dragging across the picture per view turned
local PITCH_NAMES = { [-90] = "straight down", [-45] = "looking down", [0] = "level", [45] = "looking up", [90] = "straight up" }

local frame, chrome, img, missing, title, info, preload
local topH = TITLE_H -- our own title bar's height (0 with the game frame)
local cur -- { p, yaw, pitch (index into D.PITCHES) }

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
  if portrait then portrait:SetTexture(MEDIA .. "Logo") end
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
  local badge = CreateFrame("Frame", nil, frame)
  badge:SetSize(56, 56)
  badge:SetPoint("CENTER", frame, "TOPLEFT", 12, -10)
  badge:SetFrameLevel(frame:GetFrameLevel() + 10)
  MoveHandle(badge)
  local logo = badge:CreateTexture(nil, "ARTWORK")
  logo:SetAllPoints()
  logo:SetTexture(MEDIA .. "Logo")
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
  local ahead = Button(frame, "Go ahead", 72, function() V.GoAhead() end)
  ahead:SetPoint("LEFT", down, "RIGHT", 8, 0)
  info = frame:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  info:SetPoint("LEFT", ahead, "RIGHT", 8, 0)
  info:SetPoint("RIGHT", -10, 0)
  info:SetJustifyH("RIGHT")

  -- the picture
  local view = CreateFrame("Frame", nil, frame)
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
  view:SetScript("OnMouseWheel", function(_, delta) V.TurnBy(delta > 0 and -1 or 1) end)
  -- drag across the picture to look around (like pulling the scenery)
  local dragX, dragY
  view:SetScript("OnMouseDown", function(_, button)
    if button == "LeftButton" then dragX, dragY = GetCursorPosition() end
  end)
  view:SetScript("OnMouseUp", function() dragX = nil end)
  view:SetScript("OnUpdate", function()
    if not dragX then return end
    local x, y = GetCursorPosition()
    local s = frame:GetEffectiveScale()
    local dx, dy = (x - dragX) / s, (y - dragY) / s
    if math.abs(dx) >= DRAG_STEP then
      V.TurnBy(dx > 0 and -1 or 1) -- pulling the picture right turns to the left
      dragX = x
    elseif math.abs(dy) >= DRAG_STEP then
      V.Tilt(dy > 0 and -1 or 1) -- pulling it up looks down
      dragY = y
    end
  end)
  -- hidden, tiny textures: the views next to this one load ahead of time
  preload = {}
  for i = 1, 4 do
    local t = view:CreateTexture(nil, "BACKGROUND")
    t:SetSize(1, 1)
    t:SetPoint("TOPLEFT")
    t:SetAlpha(0)
    preload[i] = t
  end

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

  frame:SetScript("OnHide", function()
    if ns.Figure then ns.Figure.Redraw() end
  end)
end

-- Draw the current view.
function V.Refresh()
  if not frame or not cur then return end
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
  local API = _G.AzerothGPS
  local where = p.zone or "?"
  local mapID, zone, u, v
  if API then mapID, zone, u, v = API.LocateWorld(p.cont, p.x, p.y) end -- (not `API and ...`: one value only)
  if mapID then where = string.format("%s  %.1f, %.1f", zone, u * 100, v * 100) end
  SetTitle(where)
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
-- first view), level.
function V.Open(p, heading)
  if not frame then V.Build() end
  cur = { p = p, yaw = heading and D.YawFor(p, heading) or 0, pitch = D.LEVEL }
  frame:Show()
  V.Refresh()
end

function V.Hide()
  if frame then frame:Hide() end
end

function V.TurnBy(dir)
  if not cur then return end
  local pitch = D.PITCHES[cur.pitch]
  if pitch == 90 or pitch == -90 then cur.pitch = D.LEVEL end -- (straight up/down: back to level first)
  cur.yaw = D.Turn(cur.p, cur.yaw, dir)
  V.Refresh()
end

function V.Tilt(dir)
  if not cur then return end
  cur.pitch = math.max(1, math.min(#D.PITCHES, cur.pitch + dir))
  V.Refresh()
end

function V.GoAhead()
  if not cur then return end
  local q = D.Ahead(cur.p, D.Heading(cur.p, cur.yaw))
  if not q then
    UIErrorsFrame:AddMessage("No street view ahead", 1, 0.82, 0)
    return
  end
  V.Open(q, D.Heading(cur.p, cur.yaw))
end

-- The view shown (nil when the window is closed): { p, yaw, pitch }, and its heading.
function V.Current()
  if frame and frame:IsShown() and cur then return cur end
end
function V.Heading()
  return cur and D.Heading(cur.p, cur.yaw) or 0
end

-- Show a JPEG shipped with the addon, to check this client draws JPEG files at all.
function V.Probe()
  if not frame then V.Build() end
  cur = nil
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
