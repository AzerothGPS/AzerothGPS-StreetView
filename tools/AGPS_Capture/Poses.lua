-- The 28 shots of a spot in the order the guide asks for them, and their image names (the
-- same names as the viewer's Data.lua D.PoseName and tools/svtools/pack.py pose_name).
-- Pure Lua: tested under lupa (tests/test_tools.py).
--
-- For each of 8 directions, 45 degrees apart turning right: level, up about 50, down about 50
-- (the game's own saved camera views 2, 3 and 4, pressed by the player). Then straight up
-- (view 5) and straight down (the player looks all the way down with the mouse), each twice,
-- 90 degrees apart: one straight-up picture is too narrow one way to meet the up ring, and
-- the second, turned, covers that side (no gaps in the panorama even if the up and down views
-- were saved a little shallow).
AGPSCapture = AGPSCapture or {}
local C = AGPSCapture

C.STEP = math.pi / 4
C.VIEWS = { level = 2, up = 3, down = 4, zenith = 5 } -- the game's camera view numbers
C.PITCH = { level = 0, up = 45, down = -45, zenith = 90, nadir = -90 }
C.LABEL = { level = "level", up = "up about 50 degrees", down = "down about 50 degrees", zenith = "straight up",
  nadir = "straight down" }

-- { turns = 45-degree steps to the right of the spot's first facing, view }
C.SEQUENCE = {}
for k = 0, 7 do
  for _, v in ipairs({ "level", "up", "down" }) do C.SEQUENCE[#C.SEQUENCE + 1] = { turns = k, view = v } end
end
C.SEQUENCE[#C.SEQUENCE + 1] = { turns = 8, view = "zenith" } -- (8 turns: back to the first facing)
C.SEQUENCE[#C.SEQUENCE + 1] = { turns = 10, view = "zenith" } -- (90 degrees further right)
C.SEQUENCE[#C.SEQUENCE + 1] = { turns = 10, view = "nadir" }
C.SEQUENCE[#C.SEQUENCE + 1] = { turns = 8, view = "nadir" } -- (back left to the first facing)

-- Angle a - b wrapped to [-pi, pi).
function C.AngleDiff(a, b)
  return (a - b + math.pi) % (2 * math.pi) - math.pi
end

-- The facing a step asks for (facing is counter-clockwise from north, so right is minus).
function C.Target(facing0, turns)
  return facing0 - turns * C.STEP
end

-- The view index (0..7, counter-clockwise from the first facing, like the viewer) a shot
-- taken facing `facing` belongs to.
function C.YawIndex(facing0, facing)
  return math.floor(C.AngleDiff(facing, facing0) / C.STEP + 0.5) % 8
end

-- (straight up and down keep their direction here: y000 is the one the viewer shows, y270 the
-- turned one, used by the panorama)
function C.PoseName(yaw, pitch)
  return string.format("y%03d_p%s%02d", yaw * 45, pitch < 0 and "-" or "+", math.abs(pitch))
end

-- Name of the image for sequence step `step` shot facing `facing`.
function C.ShotName(step, facing0, facing)
  return C.PoseName(C.YawIndex(facing0, facing), C.PITCH[step.view])
end
