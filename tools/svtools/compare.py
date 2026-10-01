"""Comparisons for the dev addon (the user, 2026-10-01): a spot as the harvester rendered it next to the
same spot captured in the game (the dev addon's capture tool on the private test server), both in the
street view window (the dev addon's Compare.lua).

The capture is imported and stitched in its own folder (build/compare-work), never in the master: its
spot id is the render's, and the master's must stay the render. Both cubes and CompareData.lua go to
build/compare, which `sv.cmd install --dev` lays over the dev addon (Compare\\<id>\\cube\\, CompareData.lua).
Screenshots of the game: never in git (build/ is ignored).
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import pack


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def lua_str(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def compare_lua(sets: list[dict]) -> str:
    """CompareData.lua for the sets ({ name, cont, x, y, z, versions: [{ key, label, id, facing, pad }] })."""
    out = ["-- Written by StreetView's `sv.cmd compare` (tools/svtools/compare.py): don't edit.",
           "-- Pictures of World of Warcraft (c) Blizzard Entertainment: never in git.",
           "AzerothGPSStreetViewDevCompare = {"]
    for s in sets:
        out.append(f"  {{ name = {lua_str(s['name'])}, cont = {int(s['cont'])}, x = {s['x']}, y = {s['y']}, "
                   f"z = {s.get('z') or 0}, versions = {{")
        for v in s["versions"]:
            out.append(f"    {{ key = {lua_str(v['key'])}, label = {lua_str(v['label'])}, id = {lua_str(v['id'])}, "
                       f"facing = {round(v['facing'], 4)}, pad = {v['pad']} }},")
        out.append("  } },")
    out.append("}")
    return "\n".join(out) + "\n"


def nearest_capture(points: dict, spot: dict, within: float = 10.0) -> dict | None:
    """The latest capture within `within` yards of the spot, on its continent."""
    near = [p for p in points.values() if p.get("cont") == spot["cont"]
            and (p["x"] - spot["x"]) ** 2 + (p["y"] - spot["y"]) ** 2 <= within ** 2]
    return max(near, key=lambda p: p.get("date", "")) if near else None


def build_set(name: str, render_id: str, capture_wow: Path, build: Path, log=print) -> dict:
    """The set `name`: the render `render_id` (build/master) and the latest capture near it in
    `capture_wow` (its Screenshots and SavedVariables), stitched. Adds it to build/compare (replacing a set
    of the same name) and returns it."""
    out, work = build / "compare", build / "compare-work"
    render = json.loads((build / "points.json").read_text(encoding="utf-8")).get(render_id)
    if not render or not render.get("cube"):
        raise SystemExit(f"{render_id}: no rendered cube in build/master")
    pack.import_captures(capture_wow, work, log=log)
    points = json.loads((work / "points.json").read_text(encoding="utf-8"))
    cap = nearest_capture(points, render)
    if not cap:
        raise SystemExit(f"No finished capture within 10 yd of {render_id} in {capture_wow}")
    pack.stitch_points(capture_wow, work, only={cap["id"]}, force=True, log=log)
    cap = json.loads((work / "points.json").read_text(encoding="utf-8"))[cap["id"]]
    if not cap.get("cube"):
        raise SystemExit(f"{cap['id']}: the capture couldn't be stitched (too few shots?)")
    s = slug(name)
    versions = []
    for key, label, p, src in (("game", "In Game", cap, work / "master" / cap["id"] / "cube"),
                               ("render", "Render", render, build / "master" / render_id / "cube")):
        vid = f"{s}-{key}"
        dst = out / "Compare" / vid / "cube"
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        for f in sorted(src.glob("*.jpg")):
            shutil.copy2(f, dst / f.name)
        versions.append({"key": key, "label": label, "id": vid, "facing": p.get("facing") or 0,
                         "pad": (p.get("cube") or {}).get("pad", 0.08)})
    entry = {"name": name, "cont": render["cont"], "x": render["x"], "y": render["y"], "z": render.get("z") or 0,
             "render": render_id, "capture": {"id": cap["id"], "date": cap.get("date"), "build": cap.get("build")},
             "versions": versions}
    sets_file = build / "compare-sets.json"  # (beside build/compare: everything in it goes into the addon)
    sets = [x for x in (json.loads(sets_file.read_text(encoding="utf-8")) if sets_file.exists() else [])
            if x["name"] != name]
    sets.append(entry)
    sets_file.write_text(json.dumps(sets, indent=1), encoding="utf-8")
    (out / "CompareData.lua").write_text(compare_lua(sets), encoding="utf-8")
    log(f"compare {name}: {render_id} (render) and the capture {cap['id']} of {cap.get('date')} in build/compare")
    return entry
