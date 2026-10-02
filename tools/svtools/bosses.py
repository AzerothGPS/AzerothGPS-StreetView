"""The dungeons' bosses, from AzerothGPS's Data/Instances.lua (generated numbers and names): a boss spot's
title in the street view is "Dungeon Name, Boss Name" (the user, 2026-10-02): the boss the harvester framed
(meta "boss"), else the one nearest the spot (the camera stands a few yards to about 70 yd in front of him;
AzerothGPS's spawn positions can differ from the harvester's, so the meta's name comes first)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTANCES = ROOT.parent / "azerothgps" / "addon" / "AzerothGPS" / "Data" / "Instances.lua"
NEAR_YD = 90  # (Onyxia's spot is about 70 yd off her)

_LEVEL = re.compile(r'^ns\.Instances\[(\d+)\] = \{ name = "((?:[^"\\]|\\.)*)"')
_BOSS = re.compile(r'^\s*\{ "((?:[^"\\]|\\.)*)", \d+, (-?[\d.]+), (-?[\d.]+)')


def load(path: Path | None = None) -> dict[int, tuple[str, list[tuple[str, float, float]]]]:
    """{ level: (dungeon name, [(boss name, x, y), ...]) }; empty without the AzerothGPS checkout."""
    path = path or INSTANCES
    if not path.exists():
        return {}
    out: dict[int, tuple[str, list]] = {}
    level, in_bosses = None, False
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _LEVEL.match(line)
        if m:
            level = int(m.group(1))
            out[level] = (m.group(2).replace('\\"', '"'), [])
            in_bosses = False
            continue
        if level is None:
            continue
        if line.strip().startswith("bosses = {"):
            in_bosses = True
            continue
        if in_bosses:
            b = _BOSS.match(line)
            if b:
                out[level][1].append((b.group(1).replace('\\"', '"'), float(b.group(2)), float(b.group(3))))
            elif line.strip().startswith("}"):
                in_bosses = False
    return out


def title(data: dict, p: dict) -> str | None:
    """ "Dungeon Name, Boss Name" for an instance spot near a boss, else None."""
    if p.get("kind") != "instance":
        return None
    entry = data.get(int(p["cont"]))
    if p.get("boss"):  # (the harvester's own: the boss it framed)
        return f"{p.get('zone') or (entry[0] if entry else '')}, {p['boss']}".strip(", ")
    if not entry:
        return None
    name, bosses = entry
    best, best_d = None, NEAR_YD ** 2
    for boss, x, y in bosses:
        d = (x - p["x"]) ** 2 + (y - p["y"]) ** 2
        if d <= best_d:
            best, best_d = boss, d
    if not best:
        return None
    return f"{p.get('zone') or name}, {best}"
