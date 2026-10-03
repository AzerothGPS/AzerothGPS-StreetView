"""Checks every street view the game can put up (Where in the Azeroth? or the viewer) for picture
problems: missing tiles, flat (broken) tiles, black patches, too dark or too bright, no sky, a blue-green
underwater floor. `python tests/image_check.py [out.json]`; prints the flagged spots, worst first.
Reads the installed build (build/packs/AzerothGPS_StreetView), the pictures players get.
"""

import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "build" / "packs" / "AzerothGPS_StreetView"
FACES = "FRBLUD"
FLAT_STD = 6.0

LIMITS = {  # (a spot is flagged past any of these)
    "missing": 0,       # tiles missing
    "flat": 3,          # side tiles nearly one flat color (8+ are held back from the packs)
    "black": 0.05,      # share of near-black pixels (max channel < 12) in the side and floor tiles
    "dark": 38,         # mean brightness of the side tiles below this
    "bright": 125,      # ... above this indoors: washed out (2026-10-01: Stormwind Keep's halls came out at
                        # 130-157). Outdoors the sky is in the side tiles, so bright plains and snow pass 125
                        # with nothing wrong: only spots the harvester marks "interior" are checked.
    "nosky": 30,        # mean brightness of the up tiles below this (canopy can do it too: a warning)
    "underwater": 35,   # the floor's blue minus red above this, with green above red: under water?
}


def spots():
    points_file = ROOT / "build" / "points.json"
    points = json.loads(points_file.read_text(encoding="utf-8")) if points_file.exists() else {}
    text = (PACK / "Index.lua").read_text(encoding="utf-8")
    for m in re.finditer(r'\{ id = "([^"]+)", cont = (-?\d+),.*?zone = "([^"]*)"(.*?)\},\n', text):
        pid, cont, zone, rest = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        kind = re.search(r'kind = "([^"]+)"', rest)
        yield {"id": pid, "cont": cont, "zone": zone, "kind": kind.group(1) if kind else None,
               "in_game": cont < 20000 and not kind, "interior": bool(points.get(pid, {}).get("interior"))}


def check(pid, interior=False):
    cube = PACK / "Images" / pid / "cube"
    m = {"missing": 0, "flat": 0}
    side_l, black_n, px_n = [], 0, 0
    up_l, floor = [], []
    for f in FACES:
        for i in (0, 1):
            for j in (0, 1):
                t = cube / f"{f}{i}{j}.jpg"
                if not t.exists():
                    m["missing"] += 1
                    continue
                with Image.open(t) as im:
                    small = im.convert("RGB").resize((48, 48))
                st = ImageStat.Stat(small)
                lum = 0.299 * st.mean[0] + 0.587 * st.mean[1] + 0.114 * st.mean[2]
                if f in "FRBL":
                    side_l.append(lum)
                    if ImageStat.Stat(small.convert("L")).stddev[0] < FLAT_STD:
                        m["flat"] += 1
                if f in "FRBLD":
                    px = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
                    black_n += sum(1 for p in px if max(p) < 12)
                    px_n += len(px)
                if f == "U":
                    up_l.append(lum)
                if f == "D":
                    floor.append(st.mean)
    m["black"] = round(black_n / px_n, 3) if px_n else 1
    m["dark"] = round(sum(side_l) / len(side_l), 1) if side_l else 0
    m["nosky"] = round(sum(up_l) / len(up_l), 1) if up_l else 0
    if floor:
        r, g, b = (sum(c[k] for c in floor) / len(floor) for k in range(3))
        m["underwater"] = round(b - r, 1) if g > r else -99
    else:
        m["underwater"] = -99
    flags = []
    if m["missing"] > LIMITS["missing"]:
        flags.append(f"{m['missing']} tiles missing")
    if m["flat"] >= LIMITS["flat"]:
        flags.append(f"{m['flat']} flat tiles")
    if m["black"] > LIMITS["black"]:
        flags.append(f"{m['black'] * 100:.0f}% black")
    if m["dark"] < LIMITS["dark"]:
        flags.append(f"dark (brightness {m['dark']})")
    if interior and m["dark"] > LIMITS["bright"]:
        flags.append(f"too bright (brightness {m['dark']})")
    if m["nosky"] < LIMITS["nosky"]:
        flags.append(f"no sky (up {m['nosky']})")
    if m["underwater"] > LIMITS["underwater"]:
        flags.append(f"underwater? (floor blue {m['underwater']})")
    return m, flags


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    rows, n = [], 0
    for s in spots():
        n += 1
        m, flags = check(s["id"], s["interior"])
        if flags:
            rows.append({**s, **m, "flags": flags})
    sev = {"tiles missing": 5, "flat tiles": 4, "black": 3, "underwater": 2, "too bright": 1, "dark": 1, "no sky": 0}
    rows.sort(key=lambda r: -max(v for k, v in sev.items() for f in r["flags"] if k in f))
    print(f"{n} spots checked, {len(rows)} flagged "
          f"({sum(1 for r in rows if r['in_game'])} of them can come up in Where in the Azeroth?)")
    kinds = {}
    for r in rows:
        for f in r["flags"]:
            k = next(k for k in sev if k in f)
            kinds[k] = kinds.get(k, 0) + 1
    print("by kind:", kinds)
    for r in rows[:60]:
        print(f"  {r['id']:18s} {r['zone'][:22]:22s} {'game' if r['in_game'] else '    '}  " + "; ".join(r["flags"]))
    if out:
        out.write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
