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
    """The manual capture's 26 steps, shot at the facing the guide asks for, name exactly the
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
    assert len(names) == 26 and sorted(names) == sorted(pack.ALL_POSES)
    # one turn right is view 7 (counter-clockwise index), as the viewer counts
    assert C.YawIndex(facing0, C.Target(facing0, 1)) == 7
    assert C.PoseName(3, 90) == pack.pose_name(3, 90) == "y000_p+90"


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
