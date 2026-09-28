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
    n, size = pack.build_pack(build, "2026.09.28")
    assert n == 1 and size > 0
    img = build / pack.PACK / "Images" / "1-1629--4373" / "y000_p+00.jpg"
    assert Image.open(img).size == (1024, 512)
    # the generated Index.lua loads and the addon's Data.lua reads it
    lua = lupa.LuaRuntime()
    lua.execute((build / pack.PACK / "Index.lua").read_text(encoding="utf-8"))
    ns = lua.table()
    lua.eval("function(src) return assert(load(src)) end")(
        (ROOT / "addon" / "AzerothGPS_StreetView" / "Data.lua").read_text(encoding="utf-8"))("x", ns)
    assert ns.Data.Load() == 1
    p = ns.Data.byId["1-1629--4373"]
    assert p.zone == "Razor Hill" and p.facing == pytest.approx(1.5)
    assert ns.Data.ImagePath(p, 0, 0) == "Interface\\AddOns\\AzerothGPS_StreetView_Data\\Images\\1-1629--4373\\y000_p+00.jpg"
    assert ns.Data.HasPose(p, 1, 0) and not ns.Data.HasPose(p, 3, 0)


def test_import_harvest(tmp_path):
    exp = tmp_path / "export" / "1-100--200"
    (exp / "views").mkdir(parents=True)
    for name in pack.ALL_POSES[:2]:
        Image.new("RGB", (1024, 512), (10, 20, 30)).save(exp / "views" / f"{name}.jpg")
    (exp / "meta.json").write_text(
        '{"id": "1-100--200", "cont": 1, "x": 100.2, "y": -199.8, "facing": 2.5, "zone": "Durotar",'
        ' "captured": "2026-10-01T00:00:00+00:00"}', encoding="utf-8")
    bad = tmp_path / "export" / "junk"
    bad.mkdir()
    (bad / "meta.json").write_text('{"id": "1-0-0", "cont": 1, "x": 50, "y": 50}', encoding="utf-8")
    build = tmp_path / "build"
    stats = pack.import_harvest(tmp_path / "export", build, log=lambda *_: None)
    assert stats == {"points": 1, "images": 2, "skipped": 1}
    n, _ = pack.build_pack(build, "2026.10.01")
    assert n == 1
    assert (build / pack.PACK / "Images" / "1-100--200" / "y000_p+00.jpg").exists()
    index = (build / pack.PACK / "Index.lua").read_text(encoding="utf-8")
    assert 'id = "1-100--200"' in index and "facing = 2.5000" in index


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


def test_index_lists_panoramas():
    pts = [{"id": "0-1-1", "cont": 0, "x": 1, "y": 1, "facing": 0.5, "zone": "Z", "poses": ["y000_p+00"],
            "pano": {"cols": 8, "rows": 4}}]
    assert "pano = { cols = 8, rows = 4 }" in pack.index_lua(pts, "v")
