"""AzerothGPS StreetView developer tool.

  python tools/sv.py install [--capture]      copy the addons into the game's AddOns folder
                                             (--capture adds the manual AGPS_Capture dev tool)
  python tools/sv.py import                   screenshots from AGPS_Capture -> the data pack (and
                                             360-degree panoramas of new spots), then install
  python tools/sv.py stitch [--id ID] [--force]  (re)build the panoramas of imported spots
  python tools/sv.py import-harvest <folder>  points exported by streetview-harvester -> the data pack, then install
  python tools/sv.py build                    rewrite the data pack's Index.lua from build/points.json
  python tools/sv.py media                    regenerate the addon's own art (Media/)

The game folder defaults to C:\\Program Files (x86)\\World of Warcraft\\_classic_beta_
(set AGPS_WOW or pass --wow to change it). Run with the AzerothGPS venv's Python (Pillow).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from svtools import pack  # noqa: E402

DEFAULT_WOW = Path(os.environ.get("AGPS_WOW", r"C:\Program Files (x86)\World of Warcraft\_classic_beta_"))
BUILD = ROOT / "build"


def mirror(src: Path, dst: Path) -> int:
    """Copy src over dst and delete what src no longer has. Returns the number of files that
    are new in dst (new files need a full game restart, changed Lua only /reload)."""
    new = sum(1 for f in src.rglob("*") if f.is_file() and not (dst / f.relative_to(src)).exists())
    shutil.copytree(src, dst, dirs_exist_ok=True)
    for f in sorted(dst.rglob("*"), reverse=True):
        rel = f.relative_to(dst)
        if not (src / rel).exists():
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
    return new


def install(wow: Path, capture: bool) -> None:
    addons = wow / "Interface" / "AddOns"
    if not addons.is_dir():
        sys.exit(f"No AddOns folder at {addons}")
    parts = [(ROOT / "addon" / "AzerothGPS_StreetView", "AzerothGPS_StreetView")]
    if (BUILD / pack.PACK / "Index.lua").exists():
        parts.append((BUILD / pack.PACK, pack.PACK))
    if capture:
        parts.append((ROOT / "tools" / "AGPS_Capture", "AGPS_Capture"))
    new = 0
    for src, name in parts:
        n = mirror(src, addons / name)
        new += n
        print(f"installed {name}" + (f" ({n} new files)" if n else ""))
    if new:
        print("New files: restart the game completely (a /reload doesn't see new files).")
    else:
        print("Only changed files: /reload in game.")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wow", type=Path, default=DEFAULT_WOW, help="the _classic_beta_ folder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_inst = sub.add_parser("install")
    p_inst.add_argument("--capture", action="store_true", help="also install the manual AGPS_Capture dev tool")
    p_imp = sub.add_parser("import")
    p_imp.add_argument("--no-install", action="store_true")
    p_imp.add_argument("--no-stitch", action="store_true", help="skip the panoramas (faster)")
    p_st = sub.add_parser("stitch")
    p_st.add_argument("--id", action="append", help="only this spot (repeatable)")
    p_st.add_argument("--force", action="store_true", help="rebuild panoramas that exist")
    p_st.add_argument("--size", type=int, default=1024, help="cube tile size in pixels")
    p_st.add_argument("--no-install", action="store_true")
    p_h = sub.add_parser("import-harvest")
    p_h.add_argument("folder", type=Path)
    p_h.add_argument("--no-install", action="store_true")
    sub.add_parser("build")
    sub.add_parser("media")
    p_w = sub.add_parser("watch")
    p_w.add_argument("--every", type=float, default=3.0, help="seconds between checks")
    a = ap.parse_args(argv)

    if a.cmd == "install":
        install(a.wow, a.capture)
    elif a.cmd == "import":
        stats = pack.import_captures(a.wow, BUILD)
        if not a.no_stitch:
            pack.stitch_points(a.wow, BUILD)
        n, size = pack.build_pack(BUILD)
        print(f"imported {stats['captures']} spots ({stats['images']} pictures; {stats['missing']} screenshots not found,"
              f" {stats['skipped']} unfinished captures skipped). The pack has {n} street views, {size / 1e6:.1f} MB.")
        print(pack.budget(BUILD))
        if not a.no_install:
            install(a.wow, False)
    elif a.cmd == "stitch":
        k = pack.stitch_points(a.wow, BUILD, a.size, set(a.id) if a.id else None, a.force)
        n, size = pack.build_pack(BUILD)
        print(f"stitched {k} panoramas. The pack has {n} street views, {size / 1e6:.1f} MB.")
        print(pack.budget(BUILD))
        if not a.no_install:
            install(a.wow, False)
    elif a.cmd == "import-harvest":
        stats = pack.import_harvest(a.folder, BUILD)
        n, size = pack.build_pack(BUILD)
        print(f"imported {stats['points']} harvested points ({stats['images']} pictures, {stats['skipped']} skipped). The pack has {n} street views, {size / 1e6:.1f} MB.")
        if not a.no_install:
            install(a.wow, False)
    elif a.cmd == "build":
        n, size = pack.build_pack(BUILD)
        print(f"{n} street views, {size / 1e6:.1f} MB")
    elif a.cmd == "media":
        from svtools import media
        media.make(ROOT / "addon" / "AzerothGPS_StreetView" / "Media")
    elif a.cmd == "watch":
        watch(a.wow, a.every)


def watch(wow: Path, every: float) -> None:
    """Import new spots on their own: whenever the game saves AGPS_Capture's list (on /reload
    or logging out), import and stitch what's new, then install. Stop with Ctrl+C."""
    import time

    def stamps():
        return {f: (f.stat().st_mtime, f.stat().st_size)
                for f in (wow / "WTF" / "Account").glob("*/SavedVariables/AGPS_Capture.lua")}

    seen = stamps()
    print(f"watching {len(seen)} saved capture list(s); /reload in game after capturing. Ctrl+C stops.", flush=True)
    while True:
        time.sleep(every)
        now = stamps()
        if now == seen:
            continue
        time.sleep(every)  # (let the game finish writing)
        if stamps() != now:
            continue
        seen = stamps()
        stamp = time.strftime("%H:%M:%S")
        try:
            stats = pack.import_captures(wow, BUILD)
            k = pack.stitch_points(wow, BUILD)
            n, size = pack.build_pack(BUILD)
            print(f"[{stamp}] {stats['captures']} spots in the list, {k} new stitched; "
                  f"the pack has {n} street views, {size / 1e6:.1f} MB.", flush=True)
            print(pack.budget(BUILD), flush=True)
            if k:
                install(wow, False)
            else:
                print(f"[{stamp}] nothing new to install.", flush=True)
        except Exception as e:  # (keep watching: the next save may be fine)
            print(f"[{stamp}] import failed: {e!r}", flush=True)


if __name__ == "__main__":
    main()
