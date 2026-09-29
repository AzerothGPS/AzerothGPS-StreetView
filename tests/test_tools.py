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

KAL = "AzerothGPS_StreetView_Kalimdor"


def test_capture_sequence_covers_every_view_once():
    """The manual capture's 28 steps, shot at the facing the guide asks for, name exactly the
    views the viewer and the pack use (turning right = the viewer's counter-clockwise order)."""
    lua = lupa.LuaRuntime()
    lua.execute((ROOT / "tools" / "AGPS_Capture" / "Poses.lua").read_text(encoding="utf-8"))
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
    assert ns.Data.ImagePath(p, 0, 0) == "Interface\\AddOns\\AzerothGPS_StreetView_Kalimdor\\Images\\1-1629--4373\\y000_p+00.jpg"
    assert ns.Data.HasPose(p, 1, 0) and not ns.Data.HasPose(p, 3, 0)


def test_import_harvest(tmp_path):
    exp = tmp_path / "export" / "1-100--200"
    (exp / "cube").mkdir(parents=True)
    for f in "FRBLUD":
        for i in (0, 1):
            for j in (0, 1):
                Image.new("RGB", (64, 64), (10, 20, 30)).save(exp / "cube" / f"{f}{i}{j}.jpg")
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


def test_every_point_has_one_pack_and_packs_sit_under_the_viewer():
    cfg = pack.CONFIG
    names = [p["name"] for p in cfg["sd"]["packs"]]
    for cont in (0, 1, 2991):
        assert pack.pack_for(cfg, {"cont": cont}) is not None
    assert len({c for p in cfg["sd"]["packs"] for c in p["continents"]}) == sum(len(p["continents"]) for p in cfg["sd"]["packs"])
    # the packs (and the capture tool) depend on the viewer, so the game lists them under it, with
    # its figure as their icon; the viewer names none of them (that would be a loop)
    viewer = (ROOT / "addon" / "AzerothGPS_StreetView" / "AzerothGPS_StreetView.toc").read_text(encoding="utf-8")
    assert not any(n in viewer for n in names)
    figure = "## IconTexture: Interface\\AddOns\\AzerothGPS_StreetView\\Media\\Figure"
    for text in (pack.toc("v", "t"), (ROOT / "tools" / "AGPS_Capture" / "AGPS_Capture.toc").read_text(encoding="utf-8")):
        assert "## Dependencies: AzerothGPS_StreetView" in text and figure in text
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


def test_packs_split_by_continent_scale_down_and_respect_the_budget(tmp_path):
    import copy
    cfg = copy.deepcopy(pack.CONFIG)
    cfg["sd"]["tile"], cfg["sd"]["pole"] = 64, 32
    build = tmp_path / "build"
    fake_spot(build, "1-5-5", 1, 5, 5)
    fake_spot(build, "0-7-7", 0, 7, 7)
    fake_spot(build, "2991-1-1", 2991, 1, 1)
    reports = {r["name"]: r for r in pack.build_packs(build, "2026.10.01", cfg)}
    assert reports["AzerothGPS_StreetView_Kalimdor"]["points"] == 2  # (Kalimdor and Zephras Isle)
    assert reports["AzerothGPS_StreetView_EasternKingdoms"]["points"] == 1
    tile = build / "packs" / "AzerothGPS_StreetView_EasternKingdoms" / "Images" / "0-7-7" / "cube"
    assert Image.open(tile / "F00.jpg").size == (64, 64) and Image.open(tile / "U00.jpg").size == (32, 32)
    assert not (build / "packs" / "AzerothGPS_StreetView_Kalimdor" / "Images" / "0-7-7").exists()
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
    assert [x["pack"]["name"] for x in ready] == ["AzerothGPS_StreetView_Kalimdor"]  # (no empty packs)
    z = ready[0]["zip"]
    with zipfile.ZipFile(z) as f:
        names = f.namelist()
    assert "AzerothGPS_StreetView_Kalimdor/AzerothGPS_StreetView_Kalimdor.toc" in names
    assert release.check_zip(z, "AzerothGPS_StreetView_Kalimdor", cfg["budget_bytes"]) == []
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
