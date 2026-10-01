"""A spot's worth in Where in the Azeroth? (the user, 2026-10-01): the most a round there can score.
100 by a point of interest, up to 200 far from any: a random road spot in the wilds is harder to place
than one in a town. Written into the Index (`worth`), and the game scales its points with it (Game.lua
Gm.Score). Kept off cave and instance spots (they never come up in the game).

Points of interest: AzerothGPS's flight masters and the map's points of interest (towns, mines, towers,
farms: Data/Pois.lua kinds 1 and 2) and every landmark (landmarks.json). The place labels (kind 3)
name lakes, seas and hills too and lie everywhere, so they count only on a map with nothing else
(Zephras Isle).
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .pack import ROOT

NEAR_YD = 100  # this close to a point of interest (or closer): worth WORTH_MIN
FAR_YD = 1000  # this far from every one (or farther): worth WORTH_MAX; in between, in a straight line
WORTH_MIN, WORTH_MAX = 100, 200
STEP = 5  # worths are rounded to this
POIS = ROOT.parent / "azerothgps" / "addon" / "AzerothGPS" / "Data" / "Pois.lua"
LEVEL_BASE = {10001: 0}  # a city level's points are in its base continent's coordinates (Undercity)

_ROW = re.compile(r'\{(\d+),(-?[\d.]+),(-?[\d.]+),"')


def load_pois(path: Path | None = None, landmarks_file: Path | None = None) -> dict[int, list[tuple[float, float]]]:
    """{continent: [(x, y), ...]} of the points of interest (see the module's notes). Empty when the
    AzerothGPS checkout isn't there (then every spot is worth WORTH_MIN)."""
    path = path or POIS
    by_kind: dict[int, dict[int, list]] = {}
    if path.exists():
        cont = None
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*\[(\d+)\] = \{", line)
            if m:
                cont = int(m.group(1))
                continue
            if cont is None:
                continue
            for k, x, y in _ROW.findall(line):
                by_kind.setdefault(cont, {}).setdefault(int(k), []).append((float(x), float(y)))
    out: dict[int, list] = {}
    for cont, kinds in by_kind.items():
        main = kinds.get(1, []) + kinds.get(2, [])
        out[cont] = main or kinds.get(3, [])
    lf = landmarks_file or (ROOT / "landmarks.json")
    if lf.exists():
        for e in json.loads(lf.read_text(encoding="utf-8")).get("landmarks", []):
            src = e if e.get("status") == "spot" else e.get("near")
            if src:
                c = int(src["cont"])
                out.setdefault(LEVEL_BASE.get(c, c), []).append((float(src["x"]), float(src["y"])))
    return out


def nearest(pois: dict, cont: int, x: float, y: float) -> float | None:
    pts = pois.get(LEVEL_BASE.get(int(cont), int(cont)))
    if not pts:
        return None
    return min(math.hypot(px - x, py - y) for px, py in pts)


def worth(pois: dict, p: dict) -> int:
    """The spot's worth: WORTH_MIN within NEAR_YD of a point of interest, WORTH_MAX from FAR_YD out."""
    if p.get("kind") or int(p["cont"]) >= 20000:
        return WORTH_MIN
    d = nearest(pois, p["cont"], float(p["x"]), float(p["y"]))
    if d is None:
        return WORTH_MIN
    t = min(1.0, max(0.0, (d - NEAR_YD) / (FAR_YD - NEAR_YD)))
    return int(STEP * round((WORTH_MIN + (WORTH_MAX - WORTH_MIN) * t) / STEP))
