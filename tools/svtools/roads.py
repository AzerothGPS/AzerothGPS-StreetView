"""Road sync (PLAN.md part 11.1): the rendered street views against AzerothGPS's current roads.

Every data update starts here. A rendered spot farther than RETIRE_YD from every current road
(its road was removed or moved) is retired: left out of the packs, kept in the master. A spot the
current roads plan (the harvester's planner, the same spacing and zone rules as the render run)
with no rendered spot within half the spacing is to render. Only the ones the packs would ship
(pack.shipped over what's rendered plus them) go on the list, the harvester's spot-list
format. Written to build/road-diff.json; `build_packs` leaves the retired ones out. Landmarks are
never retired, and the picked ones (with a z, off the roads) neither cover nor displace road spots.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

RETIRE_YD = 60  # a rendered spot this far from every road: its road is gone
SAMPLE_YD = 15  # roads sampled this finely for the distance (the error stays under half of it)


def road_samples(roads: dict, step: float = SAMPLE_YD) -> dict[int, dict]:
    """Points along every road edge, bucketed per continent by cell: {cont: {(i, j): [(x, y), ...]}}."""
    grid: dict[int, dict] = {}
    for cont, r in roads.items():
        g = grid.setdefault(int(cont), {})
        for e in r.get("e", []):
            pts = e[4:]
            for i in range(0, len(pts) - 3, 2):
                x1, y1, x2, y2 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
                n = max(1, int(math.hypot(x2 - x1, y2 - y1) / step))
                for k in range(n + 1):
                    x, y = x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n
                    g.setdefault((int(x // RETIRE_YD), int(y // RETIRE_YD)), []).append((x, y))
    return grid


def road_distance(grid: dict, cont: int, x: float, y: float) -> float:
    """The distance to the nearest road sample, capped at 2 * RETIRE_YD (farther: that)."""
    g = grid.get(int(cont), {})
    ci, cj = int(x // RETIRE_YD), int(y // RETIRE_YD)
    best = 2 * RETIRE_YD
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for qx, qy in g.get((ci + di, cj + dj), ()):
                d = math.hypot(qx - x, qy - y)
                if d < best:
                    best = d
    return best


def diff(rendered: list[dict], planned: list[dict], roads: dict, spacing: float, ship_spacing: float | None,
         city_ship_spacing: float | None = None) -> dict:
    """{retired: [spot...], add: [planned spot...]} (see the module's notes)."""
    from . import landmarks
    from .pack import shipped
    pinned, marked = landmarks.pinned_ids(), landmarks.marked_ids()
    grid = road_samples(roads)
    # (a landmark is never retired: the picked ones stand off the roads on purpose; nor a city spot:
    # it follows the capital's own streets, ns.RoadOverlays, not these roads)
    retired = [p for p in rendered if p["id"] not in pinned and not p.get("city")
               and road_distance(grid, p["cont"], p["x"], p["y"]) > RETIRE_YD]
    retired_ids = {p["id"] for p in retired}
    kept = [p for p in rendered if p["id"] not in retired_ids]
    half = spacing / 2
    buckets: dict = {}
    for p in kept:
        if p["id"] in marked:  # (not road spots: they cover no planned road spot)
            continue
        buckets.setdefault((int(p["cont"]), int(p["x"] // half), int(p["y"] // half)), []).append(p)

    def covered(q) -> bool:
        c, i, j = int(q["cont"]), int(q["x"] // half), int(q["y"] // half)
        return any(math.hypot(p["x"] - q["x"], p["y"] - q["y"]) < half
                   for di in (-1, 0, 1) for dj in (-1, 0, 1) for p in buckets.get((c, i + di, j + dj), ()))

    new = [q for q in planned if q.get("zone") and not covered(q)]
    if ship_spacing:  # only what the packs would ship, with what's rendered already
        ship = {p["id"] for p in shipped(kept + new, ship_spacing, pinned, marked, city_ship_spacing)}
        new = [q for q in new if q["id"] in ship]
    return {"retired": retired, "add": new}


def plan(agps: Path, harvester: Path, spacing: float) -> tuple[dict, list[dict]]:
    """(roads, planned spots) from an AzerothGPS checkout, with the harvester's planner."""
    sys.path.insert(0, str(harvester))
    from harvester import points as hp
    roads, maps = hp.load_azerothgps(agps)
    return roads, hp.generate(roads, maps, spacing=spacing)


def report(result: dict) -> str:
    by: dict = {}
    for kind in ("retired", "add"):
        for p in result[kind]:
            key = (p.get("zone") or "?", kind)
            by[key] = by.get(key, 0) + 1
    lines = [f"road sync: {len(result['retired'])} rendered spots retired (their road is gone), "
             f"{len(result['add'])} spots to render (new roads)"]
    zones = sorted({z for z, _ in by})
    for z in zones:
        lines.append(f"  {z}: {by.get((z, 'retired'), 0)} retired, {by.get((z, 'add'), 0)} to render")
    return "\n".join(lines)


def run(build: Path, agps: Path, harvester: Path, cfg: dict) -> dict:
    points = json.loads((build / "points.json").read_text(encoding="utf-8"))
    rendered = [p for p in points.values() if p.get("source") == "harvester"]
    roads, planned = plan(agps, harvester, cfg["spacing_yd"])
    result = diff(rendered, planned, roads, cfg["spacing_yd"], cfg.get("ship_spacing_yd"),
                  cfg.get("city_ship_spacing_yd"))
    out = {"retired": {p["id"]: {"cont": p["cont"], "x": p["x"], "y": p["y"], "zone": p.get("zone", "")}
                       for p in result["retired"]},
           "add": [{"id": q["id"], "cont": q["cont"], "x": q["x"], "y": q["y"], "zone": q.get("zone", ""),
                    "heading": q.get("heading")} for q in result["add"]]}
    (build / "road-diff.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return result
