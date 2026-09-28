-- The 26 shots of a spot in the order the guide asks for them, and their image names (the
-- same names as the viewer's Data.lua D.PoseName and tools/svtools/pack.py pose_name).
-- Pure Lua: tested under lupa (tests/test_tools.py).
--
-- For each of 8 directions, 45 degrees apart turning right: level, up 45, down 45 (the game's
-- own saved camera views 2, 3 and 4, pressed by the player). Then straight up (view 5) and
-- straight down (the player looks all the way down with the mouse).
AGPSCapture = AGPSCapture or {}
local C = AGPSCapture

C.STEP = math.pi / 4
C.VIEWS = { level = 2, up = 3, down = 4, zenith = 5 } -- the game's camera view numbers
C.PITCH = { level = 0, up = 45, down = -45, zenith = 90, nadir = -90 }
C.LABEL = { level = "level", up = "up 45 degrees", down = "down 45 degrees", zenith = "straight up",
  nadir = "straight down" }

-- { turns = 45-degree steps to the right of the spot's first facing, view }
C.SEQUENCE = {}
for k = 0, 7 do
  for _, v in ipairs({ "level", "up", "down" }) do C.SEQUENCE[#C.SEQUENCE + 1] = { turns = k, view = v } end
end
C.SEQUENCE[#C.SEQUENCE + 1] = { turns = 8, view = "zenith" } -- (8 turns: back to the first facing)
C.SEQUENCE[#C.SEQUENCE + 1] = { turns = 8, view = "nadir" }

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

function C.PoseName(yaw, pitch)
  if pitch == 90 or pitch == -90 then yaw = 0 end
  return string.format("y%03d_p%s%02d", yaw * 45, pitch < 0 and "-" or "+", math.abs(pitch))
end

-- Name of the image for sequence step `step` shot facing `facing`.
function C.ShotName(step, facing0, facing)
  return C.PoseName(C.YawIndex(facing0, facing), C.PITCH[step.view])
end
