"""tools/svtools: pose names match the addon, screenshots are found and cropped, and the
generated pack loads in the addon's Lua."""

import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from svtools import pack  # noqa: E402

lupa = pytest.importorskip("lupa")

KAL = "AzerothGPS_StreetView"  # (the pictures ship inside the viewer)


def test_capture_sequence_covers_every_view_once():
    """The manual capture's 28 steps, shot at the facing the guide asks for, name exactly the
    views the viewer and the pack use (turning right = the viewer's counter-clockwise order)."""
    lua = lupa.LuaRuntime()
    poses = ROOT.parent / "AzerothGPS-StreetView-Dev" / "addon" / "AzerothGPS_StreetView_Dev" / "Poses.lua"
    if not poses.exists():
        pytest.skip("needs the AzerothGPS-StreetView-Dev checkout next to this one")
    lua.execute(poses.read_text(encoding="utf-8"))
    C = lua.globals().AGPSCapture
    facing0 = 1.0
    names = []
    for i in range(1, len(C.SEQUENCE) + 1):
        step = C.SEQUENCE[i]
        facing = C.Target(facing0, step.turns) + 0.03  # a little off, within the tolerance
        names.append(C.ShotName(step, facing0, facing))
    assert len(names) == 28 and sorted(names) == sorted(pack.ALL_POSES + pack.EXTRA_POSES)
    # one turn right is view 7 (counter-clockwise index), as the viewer counts
    assert C.YawIndex(facing0, C.Target(facing0, 1)) == 7
    assert C.PoseName(0, 90) == pack.pose_name(3, 90) == "y000_p+90"  # (the viewer's one straight-up view)
    assert C.PoseName(6, -90) == "y270_p-90"  # (the turned one keeps its direction)


def test_match_shot_tolerates_a_second_or_two():
    shots = {"WoWScrnShot_092826_201504": Path("a.jpg"), "WoWScrnShot_092826_201506": Path("b.jpg")}
    used = set()
    assert pack.match_shot("WoWScrnShot_092826_201503", shots, used) == Path("a.jpg")
    used.add("WoWScrnShot_092826_201504")
    assert pack.match_shot("WoWScrnShot_092826_201504", shots, used) == Path("b.jpg")  # +2 s
    assert pack.match_shot("WoWScrnShot_092826_201510", shots, used) is None
    assert pack.match_shot("garbage", shots, used) is None


def test_crop_is_centered_2to1():
    im = Image.new("RGB", (1920, 1080), (255, 0, 0))
    out = pack.crop_2to1(im)
    assert out.size == (1024, 512)
    tall = pack.crop_2to1(Image.new("RGB", (800, 600)))
    assert tall.size == (1024, 512)


def test_import_and_build_pack(tmp_path):
    wow = tmp_path / "wow"
    shots_dir = wow / "Screenshots"
    shots_dir.mkdir(parents=True)
    sv = wow / "WTF" / "Account" / "X" / "SavedVariables"
    sv.mkdir(parents=True)
    shots = []
    for i, name in enumerate(pack.ALL_POSES[:3]):
        stem = f"WoWScrnShot_092826_2015{10 + i * 2:02d}"
        Image.new("RGB", (1920, 1080), (i * 80, 100, 50)).save(shots_dir / f"{stem}.jpg")
        shots.append(f'{{ ["pose"] = "{name}", ["file"] = "{stem}" }}')
    sv.joinpath("AGPS_Capture.lua").write_text(
        'AGPSCaptureDB = { ["captures"] = { { ["done"] = true, ["cont"] = 1, ["x"] = 1629.4, ["y"] = -4373.1,'
        ' ["z"] = 31.2, ["facing"] = 1.5, ["zone"] = "Durotar", ["subzone"] = "Razor Hill",'
        ' ["date"] = "2026-09-28 20:15:10", ["shots"] = { ' + ", ".join(shots) + " } },"
        ' { ["done"] = false, ["cont"] = 1, ["x"] = 1, ["y"] = 1, ["shots"] = {} } } }',
        encoding="utf-8")
    build = tmp_path / "build"
    stats = pack.import_captures(wow, build, log=lambda *_: None)
    assert stats == {"captures": 1, "skipped": 1, "images": 3, "missing": 0}
    # the user's own screenshots never go into a pack
    n, _ = pack.build_pack(build, "2026.09.28")
    assert n == 0 and not (build / "packs" / KAL / "Images" / "1-1629--4373").exists()
    assert "1-1629--4373" not in (build / "packs" / KAL / "Index.lua").read_text(encoding="utf-8")
    # (with manual=True, for checking the viewer reads single views)
    n, size = pack.build_pack(build, "2026.09.28", manual=True)
    assert n == 1 and size > 0
    assert (build / "master" / "1-1629--4373" / "views" / "y000_p+00.jpg").exists()
    img = build / "packs" / KAL / "Images" / "1-1629--4373" / "y000_p+00.jpg"
    assert Image.open(img).size == (1024, 512)
    # the generated Index.lua loads and the addon's Data.lua reads it
    lua = lupa.LuaRuntime()
    lua.execute((build / "packs" / KAL / "Index.lua").read_text(encoding="utf-8"))
    ns = lua.table()
    lua.eval("function(src) return assert(load(src)) end")(
        (ROOT / "addon" / "AzerothGPS_StreetView" / "Data.lua").read_text(encoding="utf-8"))("x", ns)
    assert ns.Data.Load() == 1
    p = ns.Data.byId["1-1629--4373"]
    assert p.zone == "Razor Hill" and p.facing == pytest.approx(1.5)
    assert ns.Data.ImagePath(p, 0, 0) == "Interface\\AddOns\\AzerothGPS_StreetView\\Images\\1-1629--4373\\y000_p+00.jpg"
    assert ns.Data.HasPose(p, 1, 0) and not ns.Data.HasPose(p, 3, 0)


def test_import_harvest(tmp_path):
    exp = tmp_path / "export" / "1-100--200"
    (exp / "cube").mkdir(parents=True)
    for f in "FRBLUD":
        for i in (0, 1):
            for j in (0, 1):
                Image.effect_noise((64, 64), 60).convert("RGB").save(exp / "cube" / f"{f}{i}{j}.jpg")  # (textured: not a broken render)
    (exp / "meta.json").write_text(
        '{"id": "1-100--200", "cont": 1, "x": 100.2, "y": -199.8, "facing": 2.5, "zone": "Durotar",'
        ' "captured": "2026-10-01T00:00:00+00:00", "cube": {"size": 64, "pad": 0.08, "mismatch": 9.5}}',
        encoding="utf-8")
    bad = tmp_path / "export" / "junk"
    bad.mkdir()
    (bad / "meta.json").write_text('{"id": "1-0-0", "cont": 1, "x": 50, "y": 50}', encoding="utf-8")
    build = tmp_path / "build"
    stats = pack.import_harvest(tmp_path / "export", build, log=lambda *_: None)
    assert stats == {"points": 1, "images": 24, "skipped": 1}
    n, _ = pack.build_pack(build, "2026.10.01")
    assert n == 1
    assert (build / "packs" / KAL / "Images" / "1-100--200" / "cube" / "F00.jpg").exists()
    index = (build / "packs" / KAL / "Index.lua").read_text(encoding="utf-8")
    assert 'id = "1-100--200"' in index and "facing = 2.5000" in index and "cube = { pad = 0.08 }" in index


def test_pull_copies_only_new_or_changed_spots(tmp_path):
    from svtools import pull
    share = tmp_path / "share"
    spot = share / "out" / "1-100--200"
    (spot / "cube").mkdir(parents=True)
    for f in "FRBLUD":
        for i in (0, 1):
            for j in (0, 1):
                Image.new("RGB", (16, 16)).save(spot / "cube" / f"{f}{i}{j}.jpg")
    meta = '{"id": "1-100--200", "cont": 1, "x": 100, "y": -200, "cube": {"size": 16, "pad": 0.08}}'
    (spot / "meta.json").write_text(meta, encoding="utf-8")
    half = share / "out" / "1-300-300"  # still being stitched: no meta.json yet
    (half / "cube").mkdir(parents=True)
    (share / "review").mkdir()
    Image.new("RGB", (8, 4)).save(share / "review" / "1-100--200.jpg")
    build = tmp_path / "build"
    quiet = lambda *_: None  # noqa: E731

    first = pull.pull(share, build, log=quiet)
    assert (first["points"], first["reviews"], first["on_share"]) == (1, 1, 1)
    assert (build / "master" / "1-100--200" / "cube" / "U11.jpg").exists()
    assert (build / "harvest-review" / "1-100--200.jpg").exists()
    assert not (build / "harvest-staging").exists()

    again = pull.pull(share, build, log=quiet)
    assert (again["points"], again["reviews"]) == (0, 0)

    (spot / "meta.json").write_text(meta.replace('"x": 100', '"x": 100.1'), encoding="utf-8")
    assert pull.pull(share, build, log=quiet)["points"] == 1

    assert pull.resolve_source("//PC/agps-work", build) == Path("//PC/agps-work")
    assert pull.resolve_source(None, build) == Path("//PC/agps-work")  # remembered


def test_stitch_measures_the_camera_and_rebuilds_the_panorama():
    """Pictures rendered from a known panorama with a known field of view, shallow up/down
    views, small yaw offsets and aiming errors: calibrate recovers them and the panorama
    matches."""
    import math
    import numpy as np
    from svtools import stitch as st

    rng = np.random.default_rng(7)
    base = Image.fromarray(rng.integers(0, 255, (16, 32, 3)).astype(np.uint8)).resize((512, 256), Image.BICUBIC)
    noise = Image.fromarray(rng.integers(0, 255, (64, 128, 3)).astype(np.uint8)).resize((512, 256), Image.BICUBIC)
    pano = (np.asarray(base) * 0.6 + np.asarray(noise) * 0.4).astype(np.uint8)
    true = st.Rig(hfov=84.0, pitch={"level": 3.0, "up": 32.0, "down": -30.0, "zenith": 86.0, "nadir": -85.0},
                  yaw_off={"level": 0, "up": 1.5, "down": -2.0, "zenith": 0, "nadir": 0})
    shots = []
    for k in range(8):
        for ring in ("level", "up", "down"):
            yaw = math.radians(-45 * k + rng.uniform(-4, 4))
            img = st.render(pano, yaw + math.radians(true.yaw_off[ring]), math.radians(true.pitch[ring]), 320, 180, 84)
            shots.append(st.Shot(img, yaw, ring))
    for ring in ("zenith", "nadir"):
        for turn in (0, -90):  # (two each, 90 degrees apart, as the manual capture takes them)
            yaw = math.radians(turn + rng.uniform(-3, 3))
            shots.append(st.Shot(st.render(pano, yaw, math.radians(true.pitch[ring]), 320, 180, 84), yaw, ring))
    rig = st.calibrate(shots, width=160)
    assert rig.hfov == pytest.approx(84, abs=1)
    assert rig.pitch["up"] == pytest.approx(32, abs=1.5) and rig.pitch["down"] == pytest.approx(-30, abs=1.5)
    back = st.panorama(shots, rig, 512)
    assert np.abs(back.astype(float) - pano.astype(float)).mean() < 8


def test_index_lists_cubes():
    pts = [{"id": "0-1-1", "cont": 0, "x": 1, "y": 1, "facing": 0.5, "zone": "Z", "poses": ["y000_p+00"],
            "cube": {"pad": 0.08}}]
    text = pack.index_lua(pts, "v", "AzerothGPS_StreetView_EasternKingdoms")
    assert "cube = { pad = 0.08 }" in text and "AzerothGPS_StreetView_EasternKingdoms" in text


def test_viewer_cells_sample_the_cube_where_they_look():
    """The viewer's Lua (Data.lua D.CubeCells) and the stitcher's Python (stitch.FACES,
    tile_bounds) agree: every cell corner's texture coordinate in its tile is the direction
    that screen point looks along, for views all around, straight up and straight down."""
    import math
    import numpy as np
    from svtools import stitch as st

    lua = lupa.LuaRuntime()
    ns = lua.table()
    lua.eval("function(src) return assert(load(src)) end")(
        (ROOT / "addon" / "AzerothGPS_StreetView" / "Data.lua").read_text(encoding="utf-8"))("x", ns)
    D = ns.Data
    p = lua.eval("{ id = 'q', cube = { pad = 0.08 } }")
    w, h, cols, rows = 640.0, 320.0, 16, 8
    for lon, lat, fov in ((0, 0, 75), (37, 12, 90), (-150, -30, 60), (95, 84, 75), (200, -85, 100)):
        cells = D.CubeCells(p, lon, lat, fov, w, h, cols, rows)
        assert len(cells) >= cols * rows
        area = sum(cells[i].cw * cells[i].ch for i in range(1, len(cells) + 1))
        assert area == pytest.approx(w * h)  # (the whole window, no holes)
        r, u, fw = st.axes(-math.radians(lon), math.radians(lat))
        f = (w / 2) / math.tan(math.radians(fov) / 2)
        for c in (cells[i] for i in range(1, len(cells) + 1)):
            nrm, fr, fu = (np.array(v, dtype=float) for v in st.FACES[c.face])
            a_lo, a_hi, b_lo, b_hi = st.tile_bounds(c.col, c.row)
            corners = [(c.x, c.y), (c.x, c.y + c.ch), (c.x + c.cw, c.y), (c.x + c.cw, c.y + c.ch)]
            for k, (sx, sy) in enumerate(corners):
                uu, vv = c.uv[2 * k + 1], c.uv[2 * k + 2]
                assert -0.001 <= uu <= 1.001 and -0.001 <= vv <= 1.001  # (inside the tile's image)
                a = a_lo + uu * (a_hi - a_lo)
                b = b_hi - vv * (b_hi - b_lo)
                got = a * fr + b * fu + nrm
                want = (sx - w / 2) * r + (h / 2 - sy) * u + f * fw
                cos = got @ want / np.linalg.norm(got) / np.linalg.norm(want)
                assert cos > 1 - 1e-9, (lon, lat, c.face, k)


def test_cube_tiles_render_the_panorama():
    """Cube tiles rendered from pictures of a known panorama show that panorama."""
    import math
    import numpy as np
    from svtools import stitch as st

    rng = np.random.default_rng(3)
    pano = np.asarray(Image.fromarray(rng.integers(0, 255, (8, 16, 3)).astype(np.uint8)).resize((512, 256), Image.BICUBIC))
    rig = st.Rig(hfov=90.0, pitch={"level": 0.0, "up": 45.0, "down": -45.0, "zenith": 90.0, "nadir": -90.0})
    shots = [st.Shot(st.render(pano, math.radians(-45 * k), math.radians(rig.pitch[ring]), 320, 180, 90), math.radians(-45 * k), ring)
             for k in range(8) for ring in ("level", "up", "down")]
    shots += [st.Shot(st.render(pano, math.radians(t), math.radians(rig.pitch[ring]), 320, 180, 90), math.radians(t), ring)
              for ring in ("zenith", "nadir") for t in (0, -90)]
    tiles = st.cube_tiles(shots, rig, 64)
    assert sorted(tiles) == sorted(f"{f}{i}{j}" for f in "FRBLUD" for i in (0, 1) for j in (0, 1))
    for name, img in tiles.items():
        d = st.tile_dirs(name[0], int(name[1]), int(name[2]), 64)
        lon = np.arctan2(d[:, 0], d[:, 2])
        lat = np.arcsin(np.clip(d[:, 1], -1, 1))
        px = np.clip((lon / math.pi + 1) / 2 * 512 - 0.5, 0, 510.999)
        py = np.clip((0.5 - lat / math.pi) * 256 - 0.5, 0, 254.999)
        want = st.sample(pano.astype(np.float32), px, py)
        assert np.abs(img.reshape(-1, 3).astype(float) - want).mean() < 10, name


def test_compare_data_for_the_dev_addon():
    # the user, 2026-10-01: a spot as rendered and as captured in the game, for the dev addon's Compare
    import lupa
    from svtools import compare
    sets = [{"name": 'Thunder "Bluff"', "cont": 1, "x": -1248.3, "y": 68.1, "z": 127.57, "versions": [
        {"key": "game", "label": "In Game", "id": "thunder-bluff-game", "facing": 1.23456, "pad": 0.08},
        {"key": "render", "label": "Render", "id": "thunder-bluff-render", "facing": -2.8469, "pad": 0.08}]}]
    lua = lupa.LuaRuntime()
    lua.execute(compare.compare_lua(sets))
    s = lua.globals().AzerothGPSStreetViewDevCompare[1]
    assert s.name == 'Thunder "Bluff"' and s.cont == 1 and s.versions[2].id == "thunder-bluff-render"
    assert abs(s.versions[1].facing - 1.2346) < 1e-9
    assert compare.slug("Thunder Bluff, central rise") == "thunder-bluff-central-rise"
    spot = {"cont": 1, "x": -1248.3, "y": 68.1}
    pts = {"a": {"id": "a", "cont": 1, "x": -1248.0, "y": 68.0, "date": "2026-10-01 17:00"},
           "b": {"id": "b", "cont": 1, "x": -1249.0, "y": 69.0, "date": "2026-10-01 18:00"},
           "c": {"id": "c", "cont": 1, "x": -1300.0, "y": 68.0, "date": "2026-10-01 19:00"},
           "d": {"id": "d", "cont": 0, "x": -1248.3, "y": 68.1, "date": "2026-10-01 20:00"}}
    assert compare.nearest_capture(pts, spot)["id"] == "b"  # (the latest within 10 yd, on its continent)


def test_compare_stitches_window_grabs_by_their_names(tmp_path, monkeypatch):
    # (the private client saves no screenshots of its own: harvester.gm's window grabs, named by direction
    # and saved view, k<k>_v<n>.png and k<k>_nadir.png)
    import math

    import numpy as np
    from PIL import Image
    from svtools import compare, pack as pk
    folder = tmp_path / "grabs"
    folder.mkdir()
    names = [f"k{k}_v{n}" for k in range(8) for n in (2, 3, 4)] + ["k0_v5", "k2_v5", "k0_nadir", "k2_nadir", "notes"]
    for n in names:
        Image.new("RGB", (32, 18), (40, 80, 120)).save(folder / f"{n}.png")
    seen = []

    def fake_cube(shots, out_dir, *a, **kw):
        seen.extend(shots)
        return {"pad": 0.08, "hfov": 90.0, "preview": np.zeros((4, 8, 3), np.uint8)}
    monkeypatch.setattr(pk, "write_cube", fake_cube)
    spot = {"id": "1--1248-68", "cont": 1, "x": -1248.3, "y": 68.1}
    p = compare.stitch_grabs(folder, spot, 3.4363, tmp_path / "work", log=lambda *a: None)
    assert p["id"] == "1--1248-68-grabs" and p["facing"] == 3.4363 and len(seen) == 28
    by = {(round(s.yaw, 4), s.ring) for s in seen}
    assert (0.0, "level") in by and (round(-3 * math.pi / 4, 4), "down") in by and (round(-math.pi / 2, 4), "nadir") in by
    assert sum(1 for s in seen if s.ring == "zenith") == 2
    # (the camera's look steps from its bottom limit, mapped to the rings; the rest left out)
    steps = tmp_path / "steps"
    steps.mkdir()
    for k in range(8):
        for s in ("p0", "p1", "p2", "p3", "p4", "p5", "p6", "v5"):
            Image.new("RGB", (32, 18)).save(steps / f"k{k}_{s}.png")
    rings = compare.parse_rings("p0=nadir, p2=down,p4=level,p6=up,v5=zenith,p9=sideways")
    assert rings == {"p0": "nadir", "p2": "down", "p4": "level", "p6": "up", "v5": "zenith"}
    assert compare.parse_ring_pitches("p0=nadir@-88,p4=level@8,p5=up,p6=zenith@x") == {
        "p0": ("nadir", -88.0), "p4": ("level", 8.0), "p5": ("up", None), "p6": ("zenith", None)}
    seen.clear()
    compare.stitch_grabs(steps, spot, 3.4363, tmp_path / "work2", rings=rings, log=lambda *a: None)
    assert len(seen) == 40 and {s.ring for s in seen} == {"nadir", "down", "level", "up", "zenith"}


def test_every_point_has_one_pack_inside_the_viewer():
    cfg = pack.CONFIG
    for cont in (0, 1, 2991, 10001):  # (and Undercity's level)
        assert pack.pack_for(cfg, {"cont": cont}) is not None
    assert len({c for p in cfg["sd"]["packs"] for c in p["continents"]}) == sum(len(p["continents"]) for p in cfg["sd"]["packs"])
    # one addon (the user, 2026-09-29): the pictures and their Index.lua ship inside the viewer,
    # whose toc loads Index.lua last (after Data.lua defines the reader)
    assert [(p["name"], p.get("in_viewer")) for p in cfg["sd"]["packs"]] == [("AzerothGPS_StreetView", True)]
    viewer = (ROOT / "addon" / "AzerothGPS_StreetView" / "AzerothGPS_StreetView.toc").read_text(encoding="utf-8")
    files = [l.strip() for l in viewer.splitlines() if l.strip() and not l.startswith("#")]
    assert files[-1] == "Index.lua" and files.index("Data.lua") < files.index("Index.lua")
    assert "AzerothGPS_StreetView_Kalimdor" in pack.LEGACY_PACKS and "AzerothGPS_StreetView_EasternKingdoms" in pack.LEGACY_PACKS
    # the developer addon (private repo) depends on the viewer, listed under it with its own icon
    # (the figure with a gear, 2026-10-01: also its minimap button's)
    dev = ROOT.parent / "AzerothGPS-StreetView-Dev" / "addon" / "AzerothGPS_StreetView_Dev" / "AzerothGPS_StreetView_Dev.toc"
    if dev.exists():
        text = dev.read_text(encoding="utf-8")
        assert "## Dependencies: AzerothGPS_StreetView" in text
        assert "## IconTexture: Interface\\AddOns\\AzerothGPS_StreetView_Dev\\Media\\Icon" in text
        assert (dev.parent / "Media" / "Icon.tga").exists()
    for pk in cfg["sd"]["packs"]:  # (planned sizes stay under the limit at the measured SD size)
        assert pk["planned"] * 700_000 < cfg["budget_bytes"], pk["name"]


def fake_spot(build, pid, cont, x, y, px=128):
    import json as js
    d = build / "master" / pid / "cube"
    d.mkdir(parents=True)
    rng = __import__("numpy").random.default_rng(1)
    for f in "FRBLUD":
        for i in (0, 1):
            for j in (0, 1):
                n = px // 2 if f in "UD" else px
                Image.fromarray(rng.integers(0, 255, (n, n, 3)).astype("uint8")).save(d / f"{f}{i}{j}.jpg")
    pts = js.loads((build / "points.json").read_text()) if (build / "points.json").exists() else {}
    pts[pid] = {"id": pid, "cont": cont, "x": x, "y": y, "facing": 0.0, "zone": "Z", "poses": [], "cube": {"pad": 0.08}}
    (build / "points.json").write_text(js.dumps(pts))


def test_pack_scales_down_and_respects_the_budget(tmp_path):
    import copy
    cfg = copy.deepcopy(pack.CONFIG)
    cfg["sd"]["tile"], cfg["sd"]["pole"] = 64, 32
    build = tmp_path / "build"
    fake_spot(build, "1-5-5", 1, 5, 5)
    fake_spot(build, "0-7-7", 0, 7, 7)
    fake_spot(build, "2991-1-1", 2991, 1, 1)
    reports = {r["name"]: r for r in pack.build_packs(build, "2026.10.01", cfg)}
    assert reports[KAL]["points"] == 3  # (every continent in the one pack)
    tile = build / "packs" / KAL / "Images" / "0-7-7" / "cube"
    assert Image.open(tile / "F00.jpg").size == (64, 64) and Image.open(tile / "U00.jpg").size == (32, 32)
    assert not (build / "packs" / KAL / f"{KAL}.toc").exists()  # (the viewer's own toc loads it)
    assert "packs (limit" in pack.budget(list(reports.values()), cfg)
    cfg["budget_bytes"] = 1000
    with pytest.raises(SystemExit):
        pack.build_packs(build, "2026.10.01", cfg)


def test_old_single_pack_moves_into_the_master(tmp_path):
    build = tmp_path / "build"
    old = build / "AzerothGPS_StreetView_Data" / "Images" / "1-5-5" / "cube"
    old.mkdir(parents=True)
    Image.new("RGB", (8, 8)).save(old / "F00.jpg")
    pack.migrate(build)
    assert (build / "master" / "1-5-5" / "cube" / "F00.jpg").exists()
    assert not (build / "AzerothGPS_StreetView_Data").exists()


def test_release_zips_are_checked(tmp_path):
    import copy
    import zipfile
    from svtools import release
    cfg = copy.deepcopy(pack.CONFIG)
    cfg["sd"]["tile"], cfg["sd"]["pole"] = 64, 32
    build = tmp_path / "build"
    fake_spot(build, "1-5-5", 1, 5, 5)
    ready = release.release_data(build, tmp_path / "dist", "2026.10.01", upload=False, cfg=cfg, log=lambda *_: None)
    assert len(ready) == 1 and ready[0]["spots"] == 1
    z = ready[0]["zip"]
    assert z.name == f"{KAL}-2026.10.01.zip"
    with zipfile.ZipFile(z) as f:
        names = f.namelist()
        index = f.read(f"{KAL}/Index.lua").decode("utf-8")
    # one addon: the viewer's code with the built pictures and Index.lua laid over its stub
    for n in (f"{KAL}/{KAL}.toc", f"{KAL}/Viewer.lua", f"{KAL}/Game.lua", f"{KAL}/Images/1-5-5/cube/F00.jpg"):
        assert n in names, n
    assert "1-5-5" in index and names.count(f"{KAL}/Index.lua") == 1
    assert release.check_zip(z, KAL, cfg["budget_bytes"]) == []
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as f:
        f.writestr("P/Index.lua", 'x = "C:\\Users\\someone\\WoW"')
        f.writestr("P/notes.txt", "hi")
        f.writestr("Other/a.jpg", "x")
    problems = release.check_zip(bad, "P", cfg["budget_bytes"])
    assert any("personal" in p for p in problems) and any("notes.txt" in p for p in problems)
    assert any("outside" in p for p in problems)
    with pytest.raises(SystemExit):  # (no project ids or token: refuses to upload)
        release.release_data(build, tmp_path / "dist", "2026.10.01", upload=True, cfg=cfg, log=lambda *_: None)


def test_stitch_repairs_a_picture_taken_at_the_wrong_angle():
    """One 'up' picture really looking down, and a 'straight up' one really level (both seen in
    a manual capture): repair moves them to where they fit and the panorama comes out right."""
    import math
    import numpy as np
    from svtools import stitch as st

    rng = np.random.default_rng(7)
    base = Image.fromarray(rng.integers(0, 255, (16, 32, 3)).astype(np.uint8)).resize((512, 256), Image.BICUBIC)
    noise = Image.fromarray(rng.integers(0, 255, (64, 128, 3)).astype(np.uint8)).resize((512, 256), Image.BICUBIC)
    pano = (np.asarray(base) * 0.6 + np.asarray(noise) * 0.4).astype(np.uint8)
    true = {"level": 2.0, "up": 45.0, "down": -40.0, "zenith": 88.0, "nadir": -88.0}
    shots = []
    for k in range(8):
        for ring in ("level", "up", "down"):
            yaw = math.radians(-45 * k)
            really = "down" if (k == 1 and ring == "up") else ring
            shots.append(st.Shot(st.render(pano, yaw, math.radians(true[really]), 240, 135, 84), yaw, ring))
    for ring, turn in (("zenith", 0), ("zenith", -90), ("nadir", -90), ("nadir", 0)):
        really = "level" if (ring == "zenith" and turn == 0) else ring
        shots.append(st.Shot(st.render(pano, math.radians(turn), math.radians(true[really]), 240, 135, 84),
                             math.radians(turn), ring))
    rig = st.calibrate(shots, width=160)
    fixed, done = st.repair(shots, rig, width=160)
    assert len(done) >= 2 and all("moved" in d or "left out" in d for d in done)
    assert shots[4].ring == "down"  # (k = 1, taken as 'up')
    rig = st.calibrate(fixed, rig, width=160)
    back = st.panorama(fixed, rig, 512)
    assert np.abs(back.astype(float) - pano.astype(float)).mean() < 8


def test_spot_id_tolerates_rounded_meta():
    # the id comes from the exact spot (-2576.52 -> -2577); meta.json keeps -2576.5 (-> -2576 by round())
    assert pack.id_matches("1-561--2577", 1, 560.9, -2576.5)
    assert pack.id_matches("1-561--2576", 1, 560.9, -2576.5)
    assert not pack.id_matches("1-561--2579", 1, 560.9, -2576.5)
    assert not pack.id_matches("0-561--2577", 1, 560.9, -2576.5)
    assert not pack.id_matches("junk", 1, 560.9, -2576.5)


def test_ship_points_thins_to_the_shipping_spacing():
    from svtools.pack import ship_points
    # a straight road with a spot every 100 yd, and a parallel road 60 yd away
    road = [{"id": f"1-{x}-0", "cont": 1, "x": x, "y": 0} for x in range(0, 2001, 100)]
    side = [{"id": f"1-{x}-60", "cont": 1, "x": x, "y": 60} for x in range(0, 2001, 100)]
    kept = ship_points(road + side, 200)
    xs = sorted(p["x"] for p in kept if p["y"] == 0)
    assert xs == list(range(0, 2001, 200))  # every other spot along the road
    assert not [p for p in kept if p["y"] == 60]  # (the parallel road's are too close to them)
    assert ship_points(road, None) == road and len(ship_points(road, 0)) == len(road)
    # the same input, the same pick (a later build ships what an earlier one did)
    assert [p["id"] for p in ship_points(list(reversed(road)), 200)] == [p["id"] for p in ship_points(road, 200)]


def test_broken_and_reported_spots_are_held_back_for_a_retake(tmp_path):
    import json
    from PIL import Image
    from svtools import pack
    build = tmp_path / "build"
    points = {}
    for pid, flat in (("1-100-100", False), ("1-500-500", True), ("1-900-900", False)):
        cube = build / "master" / pid / "cube"
        cube.mkdir(parents=True)
        for f in "FRBLUD":
            for i in (0, 1):
                for j in (0, 1):
                    im = Image.new("RGB", (64, 64), (0, 90, 0)) if flat else Image.effect_noise((64, 64), 60).convert("RGB")
                    im.save(cube / f"{f}{i}{j}.jpg")
        x = int(pid.split("-")[1])
        points[pid] = {"id": pid, "cont": 1, "x": x, "y": x, "z": 0, "facing": 0, "zone": "Z", "poses": [],
                       "cube": {"pad": 0.08}, "source": "harvester", "imported_at": 1000}
    (build / "points.json").write_text(json.dumps(points), encoding="utf-8")
    held = pack.retake(build, points, {"1-900-900": 2000, "1-100-100": 500})  # (the second reported before its import)
    assert set(held) == {"1-500-500", "1-900-900"}
    assert "broken render" in held["1-500-500"]["reason"] and held["1-900-900"]["reason"] == "reported in game"
    assert json.loads((build / "retake.json").read_text(encoding="utf-8")).keys() == held.keys()


def test_reported_in_game_reads_the_saved_settings(tmp_path):
    from svtools import pack
    sv = tmp_path / "WTF" / "Account" / "ACC" / "SavedVariables"
    sv.mkdir(parents=True)
    (sv / "AzerothGPS_StreetView.lua").write_text(
        """AzerothGPSStreetViewDB = {
["reported"] = {
["1--1019-383"] = 1790700000,
["0-5-5"] = 1790700100,
},
["yawSign"] = 1,
}
""",
        encoding="utf-8")
    assert pack.reported_in_game(tmp_path) == {"1--1019-383": 1790700000, "0-5-5": 1790700100}


def test_road_sync_retires_spots_off_the_roads_and_lists_new_roads():
    from svtools import roads
    # an old road north-south (x 0..1000 at y 0) and a new road east-west (y 0..1000 at x 2000)
    current = {1: {"e": [[1, 2, 1000, 0, 0, 0, 1000, 0], [3, 4, 1000, 0, 2000, 0, 2000, 1000]]}}
    rendered = [{"id": f"1-{x}-0", "cont": 1, "x": x, "y": 0, "zone": "Z"} for x in range(0, 1001, 100)]
    rendered.append({"id": "1-500-800", "cont": 1, "x": 500, "y": 800, "zone": "Z"})  # its road was removed
    planned = [{"id": f"1-{x}-0", "cont": 1, "x": x, "y": 0, "zone": "Z"} for x in range(0, 1001, 100)]
    planned += [{"id": f"1-2000-{y}", "cont": 1, "x": 2000, "y": y, "zone": "Z"} for y in range(0, 1001, 100)]
    planned.append({"id": "1-2000-5000", "cont": 1, "x": 2000, "y": 5000, "zone": ""})  # no zone: never
    r = roads.diff(rendered, planned, current, 100, None)
    assert [p["id"] for p in r["retired"]] == ["1-500-800"]
    assert sorted(q["id"] for q in r["add"]) == sorted(f"1-2000-{y}" for y in range(0, 1001, 100))
    # shipping every ~200 yd: only every other new spot needs rendering
    r = roads.diff(rendered, planned, current, 100, 200)
    assert len(r["add"]) == 6


def test_cave_and_instance_spots_are_tagged_in_the_index():
    pts = [{"id": "1-5-5", "cont": 1, "x": 5, "y": 5, "facing": 0, "zone": "Z", "poses": [], "cube": {"pad": 0.08}},
           {"id": "1-9-9", "cont": 1, "x": 9, "y": 9, "facing": 0, "zone": "Z", "poses": [], "cube": {"pad": 0.08},
            "kind": "cave"}]
    lua = lupa.LuaRuntime()
    lua.execute(pack.index_lua(pts, "v", KAL))
    got = lua.eval("AzerothGPS_StreetViewPacks[1].points")
    assert got[1].kind is None and got[2].kind == "cave"


def test_spots_held_by_eye_stay_out_until_rendered_again(tmp_path):
    build = tmp_path / "build"
    fake_spot(build, "0-5-5", 0, 5, 5)
    fake_spot(build, "0-9-9", 0, 9, 9)
    import json as js
    pts = js.loads((build / "points.json").read_text())
    pts["0-5-5"]["imported_at"] = 100
    held = pack.retake(build, pts, {}, {"0-5-5": {"reason": "under the city", "at": 200}})
    assert list(held) == ["0-5-5"] and held["0-5-5"]["reason"] == "under the city"
    pts["0-5-5"]["imported_at"] = 300  # (rendered again after it was held)
    assert pack.retake(build, pts, {}, {"0-5-5": {"reason": "under the city", "at": 200}}) == {}


def test_landmarks_always_ship_on_top_of_the_thinned_pick():
    from svtools.pack import ship_points
    road = [{"id": f"1-{x}-0", "cont": 1, "x": x, "y": 0} for x in range(0, 2001, 100)]
    plain = {p["id"] for p in ship_points(road, 200)}
    kept = {p["id"] for p in ship_points(road, 200, {"1-300-0"})}  # (300 would be thinned out)
    assert kept == plain | {"1-300-0"}  # (nothing else changes: no rework for a landmark)
    # a landmark the pick has anyway changes nothing either (it still counts in the chain)
    assert {p["id"] for p in ship_points(road, 200, {"1-400-0", "1-300-0"})} == plain | {"1-300-0"}
    assert {p["id"] for p in ship_points(road, 200, set())} == plain


def test_a_spots_worth_grows_with_its_distance_from_points_of_interest(tmp_path):
    import json
    from svtools import worth
    pois_lua = tmp_path / "Pois.lua"
    pois_lua.write_text('local _, ns = ...\nns.Pois = {\n  [0] = {\n'
                        '    {1,0.0,0.0,"Flight, Zone",2,"A"}, {2,5000.0,0.0,"A Mine",0}, {3,-3000.0,0.0,"A Lake",12},\n'
                        '  },\n  [2991] = {\n    {3,100.0,100.0,"Only Labels Here",9},\n  },\n}\n', encoding="utf-8")
    lm = tmp_path / "landmarks.json"
    lm.write_text(json.dumps({"landmarks": [
        {"name": "Somewhere", "status": "spot", "id": "1-0-0", "cont": 1, "x": 0, "y": 0},
        {"name": "Under", "status": "mark", "near": {"cont": 10001, "x": 1600, "y": 240}}]}), encoding="utf-8")
    pois = worth.load_pois(pois_lua, lm)
    assert sorted(pois[0]) == [(0.0, 0.0), (1600.0, 240.0), (5000.0, 0.0)]  # (labels left out; Undercity on 0)
    assert pois[2991] == [(100.0, 100.0)]  # (a map with labels only: they count)
    W = lambda c, x, y, **kw: worth.worth(pois, {"cont": c, "x": x, "y": y, **kw})
    assert W(0, 50, 0) == 100 and W(0, 100, 0) == 100  # (by a point of interest)
    assert W(0, 550, 0) == 150 and W(0, 3300, 0) == 200  # (halfway: 150; far from all: 200)
    assert W(0, -3000, 0) == 200  # (the lake's label doesn't count)
    assert W(1, 1000, 0) == 200 and W(1, 400, 0) == 135  # (round to 5s)
    assert W(10001, 1650, 240) == 100  # (Undercity's level by its base continent)
    assert W(0, 3300, 0, kind="cave") == 100 and W(20036, 1, 1) == 100  # (never in the game anyway)
    assert worth.worth({}, {"cont": 0, "x": 1, "y": 1}) == 100  # (no AzerothGPS checkout: 100)
    line = pack.index_lua([{"id": "0-1-1", "cont": 0, "x": 1, "y": 1, "facing": 0, "poses": [], "worth": 165}], "v")
    assert "worth = 165," in line
    assert pack.id_matches("0--8606-846-f2", 0, -8606.0, 845.7) and pack.id_matches("10001-1599-217", 10001, 1598.9, 217.3)
    assert not pack.id_matches("0--8606-846-x2", 0, -8606.0, 845.7)


def test_city_spots_ship_denser_after_the_roads():
    from svtools.pack import ship_points
    road = [{"id": f"1-{x}-0", "cont": 1, "x": x, "y": 0} for x in range(0, 2001, 100)]
    city = [{"id": f"1-{x}-300", "cont": 1, "x": x, "y": 300, "city": "Orgrimmar"} for x in range(0, 601, 25)]
    city.append({"id": "1-200-20", "cont": 1, "x": 200, "y": 20, "city": "Orgrimmar"})  # (next to a road spot)
    plain = {p["id"] for p in ship_points(road, 200)}
    got = {p["id"] for p in ship_points(road + city, 200, None, 75)}
    assert plain <= got  # (no road spot gives way)
    kept_city = sorted((p for p in road + city if p["id"] in got and p.get("city")), key=lambda p: p["x"])
    assert "1-200-20" not in got  # (a shipped road spot is right there)
    assert [p["x"] for p in kept_city] == [0, 75, 150, 225, 300, 375, 450, 525, 600]  # (~75 yd apart)
    # without a city spacing (or without city spots) nothing changes
    assert {p["id"] for p in ship_points(road, 200, None, 75)} == plain
    assert ([p["id"] for p in ship_points(road + city, 200)]
            == [p["id"] for p in ship_points([dict(p, city=None) for p in road + city], 200)])


def test_picked_landmarks_stay_out_of_the_thinning():
    # 2026-10-01: 12 picked landmarks (off the roads, with a z) went into the greedy as ordinary
    # spots and 15 shipped road spots gave way, 9 in a chain across Tanaris
    from svtools import roads
    from svtools.pack import ship_points, shipped
    road = [{"id": f"1-{x}-0", "cont": 1, "x": x, "y": 0} for x in range(0, 2001, 100)]
    picked = [{"id": "1-151-20", "cont": 1, "x": 151, "y": 20}, {"id": "1-1049-5", "cont": 1, "x": 1049, "y": 5}]
    plain = {p["id"] for p in ship_points(road, 200)}
    assert {p["id"] for p in ship_points(road + picked, 200)} != plain | {"1-151-20", "1-1049-5"}  # (the old way)
    marked = {"1-151-20", "1-1049-5"}
    got = {p["id"] for p in shipped(road + picked, 200, marked | {"1-300-0"}, marked)}
    assert got == plain | marked | {"1-300-0"}  # (no road spot gives way, the pinned road spot joins)
    # the road sync never retires a landmark, and a picked one covers no planned road spot
    import svtools.landmarks as lm
    real = lm.pinned_ids, lm.marked_ids
    far_landmark = {"id": "1-1049-500", "cont": 1, "x": 1049, "y": 500}  # (500 yd off the road)
    far_spot = {"id": "1-500-400", "cont": 1, "x": 500, "y": 400}
    lm.pinned_ids = lambda doc=None: marked | {"1-1049-500"}
    lm.marked_ids = lambda doc=None: marked | {"1-1049-500"}
    try:
        net = {1: {"e": [[0, 0, 0, 0, 0, 0, 2000, 0]]}}
        d = roads.diff(road + picked + [far_landmark, far_spot], [], net, 100, None)
        assert [p["id"] for p in d["retired"]] == ["1-500-400"]
        lm.marked_ids = lambda doc=None: {"1-151-20", "1-1049-500"}
        d = roads.diff([picked[0]], [{"id": "1-150-0", "cont": 1, "x": 150, "y": 0, "zone": "Z"}], net, 100, None)
        assert [q["id"] for q in d["add"]] == ["1-150-0"]
    finally:
        lm.pinned_ids, lm.marked_ids = real


def test_marks_from_the_game_become_landmark_spots(tmp_path):
    from svtools import landmarks
    doc = {"landmarks": [{"name": "Booty Bay", "status": "mark", "near": {"cont": 0, "x": -14383.3, "y": 487.1}},
                         {"name": "Crossroads, center", "status": "spot", "id": "1--454--2651", "cont": 1,
                          "x": -453.6, "y": -2651.2}]}
    marks = [{"name": "booty bay", "cont": 0, "x": -14400.04, "y": 470.2, "z": 9.5, "facing": 1.2, "mapID": 1434, "at": 5},
             {"name": "Booty Bay", "cont": 0, "x": -14390.0, "y": 480.0, "z": 9.0, "facing": 1.0, "mapID": 1434, "at": 9},
             {"name": "Undercity, Trade Quarter", "cont": 0, "x": 1630.3, "y": 240.6, "z": -43.0, "facing": 3.1,
              "mapID": 1458, "at": 9}]
    assert landmarks.merge_marks(doc, marks, log=lambda *a: None) == 2
    bb = doc["landmarks"][0]
    assert bb["status"] == "spot" and bb["id"] == "0--14390-480" and bb["facing"] == 1.0 and "near" not in bb
    uc = doc["landmarks"][-1]
    assert uc["cont"] == 10001 and uc["id"] == "10001-1630-241" and uc["z"] == -43.0  # (the Undercity's level)
    assert landmarks.pinned_ids(doc) == {"0--14390-480", "1--454--2651", "10001-1630-241"}
    assert landmarks.merge_marks(doc, marks, log=lambda *a: None) == 0  # (nothing new the second time)
    sv = tmp_path / "WTF" / "Account" / "X" / "SavedVariables"
    sv.mkdir(parents=True)
    (sv / "AzerothGPS_StreetView_Dev.lua").write_text(
        'AzerothGPSStreetViewDevDB = {\n["marks"] = {\n{\n["name"] = "Gadgetzan",\n["x"] = -7120.5,\n["y"] = -3780.25,\n'
        '["z"] = 9,\n["cont"] = 1,\n["facing"] = 0.5,\n["mapID"] = 1446,\n["at"] = 100,\n},\n},\n}\n', encoding="utf-8")
    assert [m["name"] for m in landmarks.read_marks(tmp_path)] == ["Gadgetzan"]


def test_the_landmarks_file_is_consistent():
    from svtools import landmarks
    doc = landmarks.load()
    names = [e["name"] for e in doc["landmarks"]]
    assert len(names) == len(set(names)) and len(names) >= 30
    for e in doc["landmarks"]:
        if e["status"] == "spot":
            assert pack.id_matches(e["id"], e["cont"], e["x"], e["y"]), e["name"]
        else:
            assert e["status"] == "mark" and {"cont", "x", "y"} <= set(e["near"]), e["name"]


def test_pull_media_copies_new_and_changed_files_but_not_frames(tmp_path):
    # (the CurseForge and wiki media the capture PC took, from its share's media folder)
    from svtools import pull
    share, dst = tmp_path / "share", tmp_path / "StreetView-media"
    for name in ("hero-viewer.png", "candidates/h1-a.png", "sv-look-around.gif", "sv-look-around.frames/0000.png",
                 "notes.bin"):
        f = share / "media" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x" * 10)
    stats = pull.pull_media(share, dst)
    assert stats == {"copied": 3, "on_share": 3}
    assert sorted(p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file()) == [
        "candidates/h1-a.png", "hero-viewer.png", "sv-look-around.gif"]
    assert pull.pull_media(share, dst)["copied"] == 0  # (nothing new)
    (share / "media" / "hero-viewer.png").write_bytes(b"y" * 12)
    assert pull.pull_media(share, dst)["copied"] == 1
    assert pull.pull_media(share, dst, frames=True)["copied"] == 1  # (the frames, asked for)


def test_install_private_skips_the_real_game(tmp_path, monkeypatch):
    # the user, 2026-10-01: the latest street views into the private server's addon folder only
    import sv
    private, missing = tmp_path / "private" / "AddOns", tmp_path / "gone" / "AddOns"
    private.mkdir(parents=True)
    lst = tmp_path / ".agps-installs"
    lst.write_text(f"# the private client\n{private}\n{missing}\n", encoding="utf-8")
    monkeypatch.setattr(sv, "EXTRA_INSTALLS", lst)
    into = []
    monkeypatch.setattr(sv, "install_into", lambda addons, dev: into.append((addons, dev)))
    monkeypatch.setattr(sv, "install", lambda *a: into.append("the real game"))
    assert sv.install_private(True) == 1 and into == [(private, True)]
