"""The addon's pure Lua (Data.lua) under lupa, and every Lua file compiling."""

import math
from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa")

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addon" / "AzerothGPS_StreetView"
LUA_FILES = sorted(ROOT.glob("addon/**/*.lua")) + sorted(ROOT.glob("tools/AGPS_Capture/*.lua"))


def load(lua, ns, path: Path):
    f = lua.eval("function(src, name) return assert(load(src, '@' .. name)) end")(path.read_text(encoding="utf-8"), path.name)
    f("AzerothGPS_StreetView", ns)


def multi(lua, f, *args):
    t = lua.eval("function(f, ...) return { f(...) } end")(f, *args)
    return tuple(t[i] for i in range(1, len(t) + 1))


@pytest.fixture
def env():
    lua = lupa.LuaRuntime()
    ns = lua.table()
    load(lua, ns, ADDON / "Data.lua")
    D = ns.Data
    packs = lua.eval("""{ { name = "t", root = "Interface\\\\AddOns\\\\P\\\\Images\\\\", ext = "jpg", points = {
        { id = "1-0-0", cont = 1, x = 0, y = 0, facing = 0 },
        { id = "1-100-0", cont = 1, x = 100, y = 0, facing = 0 },
        { id = "1-0-100", cont = 1, x = 0, y = 100, facing = 0, poses = { ["y000_p+00"] = true } },
        { id = "0-5-5", cont = 0, x = 5, y = 5, facing = 1 },
    } } }""")
    assert D.Load(packs) == 4
    return lua, D


@pytest.mark.parametrize("path", LUA_FILES, ids=lambda p: p.name)
def test_every_lua_file_compiles(path):
    lua = lupa.LuaRuntime()
    ok, err = lua.eval("function(src, n) local f, e = load(src, '@' .. n); return f ~= nil, e end")(
        path.read_text(encoding="utf-8"), path.name)
    assert ok, err


def test_toc_lists_every_file():
    toc = (ADDON / "AzerothGPS_StreetView.toc").read_text(encoding="utf-8").splitlines()
    listed = {l.strip() for l in toc if l.strip() and not l.startswith("#")}
    assert listed == {p.name for p in ADDON.glob("*.lua")}


def test_nearest_within_range(env):
    lua, D = env
    p, d = multi(lua, D.Nearest, 1, 90.0, 10.0)
    assert p.id == "1-100-0" and d == pytest.approx(math.hypot(10, 10))
    assert D.Nearest(1, 90.0, 10.0, 5.0) is None
    assert D.Nearest(2, 0.0, 0.0) is None
    assert multi(lua, D.Nearest, 0, 0.0, 0.0)[0].id == "0-5-5"


def test_bearing_and_compass(env):
    lua, D = env
    assert D.Bearing(0, 0, 10, 0) == pytest.approx(0)  # due north
    assert D.Bearing(0, 0, 0, 10) == pytest.approx(math.pi / 2)  # due west (counter-clockwise)
    assert D.Compass(0.0) == "N" and D.Compass(math.pi / 2) == "W" and D.Compass(-math.pi / 2) == "E"
    assert D.Compass(math.pi / 4) == "NW" and D.Compass(math.pi) == "S"


def test_yaw_index_and_turning(env):
    lua, D = env
    p = D.byId["1-0-0"]
    assert D.YawFor(p, 0.0) == 0
    assert D.YawFor(p, math.pi / 2) == 2  # west: two steps counter-clockwise
    assert D.YawFor(p, -math.pi / 4) == 7  # north-east
    # Turning right (clockwise) from north faces north-east.
    y = D.Turn(p, 0, 1)
    assert D.Compass(D.Heading(p, y)) == "NE"
    assert D.Compass(D.Heading(p, D.Turn(p, 0, -1))) == "NW"
    # With the other yaw sign the same headings map to mirrored views.
    D.yawSign = -1
    assert D.YawFor(p, math.pi / 2) == 6
    assert D.Compass(D.Heading(p, D.Turn(p, 0, 1))) == "NE"


def test_ahead_picks_the_view_in_front(env):
    lua, D = env
    p = D.byId["1-0-0"]
    assert D.Ahead(p, 0.0).id == "1-100-0"  # north
    assert D.Ahead(p, math.pi / 2).id == "1-0-100"  # west
    assert D.Ahead(p, math.pi) is None  # nothing south


def test_pose_names_and_paths(env):
    lua, D = env
    assert D.PoseName(0, 0) == "y000_p+00"
    assert D.PoseName(7, -45) == "y315_p-45"
    assert D.PoseName(3, 90) == "y000_p+90"
    p = D.byId["1-0-100"]
    assert D.ImagePath(p, 0, 0) == "Interface\\AddOns\\P\\Images\\1-0-100\\y000_p+00.jpg"
    assert D.HasPose(p, 0, 0) and not D.HasPose(p, 1, 0)
    assert D.HasPose(D.byId["1-0-0"], 5, 45)  # no pose list: all assumed


@pytest.fixture
def pano(env):
    lua, D = env
    p = lua.eval("{ id = '0-1-1', cont = 0, x = 1, y = 1, facing = 1.0, pano = { cols = 8, rows = 4 },"
                 " pack = { root = 'R/', ext = 'jpg' } }")
    return lua, D, p


def tiles(lua, D, p, lon, lat, fov, w, h):
    out, lat2 = multi(lua, D.PanoTiles, p, lon, lat, fov, w, h)
    got = {(t.col, t.row): (round(t.x, 3), round(t.y, 3), round(t.size, 3)) for t in (out[i] for i in range(1, len(out) + 1))}
    return got, lat2


def test_pano_tiles_straight_ahead(pano):
    lua, D, p = pano
    got, lat = tiles(lua, D, p, 0.0, 0.0, 90.0, 640.0, 320.0)
    ppd = 640 / 90
    assert set(got) == {(3, 1), (4, 1), (3, 2), (4, 2)}
    assert got[(3, 1)][0] == pytest.approx(0) and got[(4, 1)][0] == pytest.approx(45 * ppd, abs=1e-3)
    assert got[(3, 1)][1] == pytest.approx(-22.5 * ppd, abs=1e-3) and got[(3, 2)][1] == pytest.approx(22.5 * ppd, abs=1e-3)
    assert lat == 0


def test_pano_tiles_wrap_around_the_back(pano):
    lua, D, p = pano
    got, _ = tiles(lua, D, p, 170.0, 0.0, 90.0, 640.0, 320.0)  # looking back: 125..215 degrees
    cols = {c for c, _ in got}
    assert cols == {6, 7, 0}  # 90..135 (part), 135..180, then -180..-135 past the seam
    ppd = 640 / 90
    assert got[(0, 1)][0] == pytest.approx(55 * ppd, abs=1e-3)


def test_pano_lat_stays_inside_the_picture(pano):
    lua, D, p = pano
    _, lat = tiles(lua, D, p, 0.0, 80.0, 90.0, 640.0, 320.0)
    assert lat == pytest.approx(90 - 22.5)


def test_pano_heading_and_path(pano):
    lua, D, p = pano
    assert D.HasPano(p)
    assert D.PanoHeading(p, 0.0) == pytest.approx(1.0)
    assert D.PanoHeading(p, 90.0) == pytest.approx(1.0 - math.pi / 2)  # right of view 0: clockwise
    assert D.PanoLon(p, D.PanoHeading(p, 37.0)) == pytest.approx(37.0)
    assert D.PanoPath(p, 3, 1) == r"R/0-1-1\pano\t31.jpg"
