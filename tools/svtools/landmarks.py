"""Landmarks: street views that always ship (the user, 2026-09-30), `landmarks.json` in the repo.

Famous stops (the Crossroads, Cathedral Square, the Valley of Strength...) that the 200 yd thinning
could drop or that no road spot reaches. An entry is either
- `spot`: a spot by `id` with its `cont`, `x`, `y` (a planned spot, or one marked in game); kept by
  `pack.ship_points` (and the harvester's `ship.py`) whatever the thinning says;
- `mark`: still needs its exact standing point, from the dev addon's `/sv mark <name>` in game
  (`sv.cmd landmarks` merges the marks from the game's SavedVariables) or a hand estimate checked on
  a test render; `near` is where the place is, from map data.
The harvester reads this file (the repos sit side by side) to render the spots that aren't in its
plan, standing on the floor nearest a marked `z` and looking along `facing`.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

from .pack import ROOT, point_id
from .savedvars import load_savedvariables

FILE = ROOT / "landmarks.json"
# city maps whose street views live on a level continent of their own (AzerothGPS ns.CityLevels)
LEVEL_OF_MAP = {1458: 10001}  # Undercity
DEV_SAVES = "AzerothGPS_StreetView_Dev.lua"


def load(path: Path | None = None) -> dict:
    path = path or FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"landmarks": []}


def save(doc: dict, path: Path | None = None) -> None:
    (path or FILE).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def pinned_ids(doc: dict | None = None) -> set[str]:
    """The ids of the landmark spots (status 'spot'): they always ship."""
    doc = doc if doc is not None else load()
    return {e["id"] for e in doc.get("landmarks", []) if e.get("status") == "spot" and e.get("id")}


def spots(doc: dict | None = None) -> list[dict]:
    """The landmark spots as spot dicts (id, cont, x, y and whatever else they carry)."""
    doc = doc if doc is not None else load()
    keys = ("id", "cont", "x", "y", "z", "facing", "zone", "mapID", "name")
    return [{k: e[k] for k in keys if k in e} for e in doc.get("landmarks", [])
            if e.get("status") == "spot" and e.get("id")]


def read_marks(wow: Path) -> list[dict]:
    """The spots marked with the dev addon's /sv mark, over every account in the game folder."""
    out = []
    for sv in sorted((wow / "WTF" / "Account").glob(f"*/SavedVariables/{DEV_SAVES}")):
        db = load_savedvariables(sv).get("AzerothGPSStreetViewDevDB") or {}
        marks = db.get("marks") or []
        if isinstance(marks, dict):
            marks = [marks[k] for k in sorted(marks)]
        out.extend(m for m in marks if isinstance(m, dict) and m.get("name") and m.get("x") is not None)
    return out


def _key(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def merge_marks(doc: dict, marks: list[dict], log=print) -> int:
    """Each mark onto the landmark of the same name (letters and digits, any case; else the one whose
    name starts with it), or a new landmark. The latest mark of a name wins. Returns how many changed."""
    by_key = {_key(e["name"]): e for e in doc.setdefault("landmarks", [])}
    latest: dict[str, dict] = {}
    for m in marks:
        k = _key(m["name"])
        if k not in latest or (m.get("at") or 0) >= (latest[k].get("at") or 0):
            latest[k] = m
    changed = 0
    for k, m in latest.items():
        e = by_key.get(k) or next((v for kk, v in by_key.items() if kk.startswith(k)), None)
        if e is None:
            e = {"name": m["name"]}
            doc["landmarks"].append(e)
            by_key[k] = e
        cont = LEVEL_OF_MAP.get(int(m.get("mapID") or 0), int(m.get("cont") or 0))
        x, y = round(float(m["x"]), 1), round(float(m["y"]), 1)
        new = {"status": "spot", "id": point_id(cont, x, y), "cont": cont, "x": x, "y": y,
               "z": round(float(m.get("z") or 0), 2), "facing": round(float(m.get("facing") or 0), 4),
               "zone": m.get("zone") or None, "mapID": m.get("mapID"), "marked": m.get("at") or int(time.time())}
        if any(e.get(k2) != v for k2, v in new.items() if k2 != "marked"):
            near = e.get("near")
            e.update(new)
            e.pop("near", None)
            if near and int(near["cont"]) == cont:
                d = math.hypot(near["x"] - x, near["y"] - y)
                e["note"] = (e.get("note", "") + f"; marked in game {d:.0f} yd from the map estimate").lstrip("; ")
            changed += 1
            log(f"  {e['name']}: {e['id']} (facing {e['facing']})")
    return changed


def report(doc: dict | None = None) -> list[str]:
    doc = doc if doc is not None else load()
    lines = []
    for e in doc.get("landmarks", []):
        where = e.get("id") or "to mark (near {cont} {x:.0f} {y:.0f})".format(**e["near"]) if e.get("near") else e.get("id")
        lines.append(f"{e.get('status', '?'):5s} {e['name'][:48]:48s} {where}")
    return lines
