"""AzerothGPS StreetView developer tool.

  sv.cmd install [--capture]      copy the viewer and the built packs into the game's AddOns folder
                                  (--capture adds the manual AGPS_Capture dev tool)
  sv.cmd import                   AGPS_Capture screenshots -> stitched spots -> the packs, then install
  sv.cmd watch                    the same by itself on every /reload (Ctrl+C stops)
  sv.cmd stitch [--id ID] [--force]  (re)stitch imported spots
  sv.cmd import-harvest <folder>  spots stitched by streetview-harvester -> the packs, then install
  sv.cmd build                    rebuild the packs (build/packs/) and print their sizes
  sv.cmd release-data [--upload]  zip the packs for CurseForge and check them (a dry run);
                                  --upload sends them (needs CF_API_TOKEN and the project ids in packs.json)
  sv.cmd media                    regenerate the addon's own art (Media/)

The packs are in packs.json (one per continent, each under CurseForge's limit). The game folder
defaults to C:\\Program Files (x86)\\World of Warcraft\\_classic_beta_ (set AGPS_WOW or pass
--wow). sv.cmd runs this with the AzerothGPS venv's Python (Pillow, numpy, lupa).
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
    for pk in pack.CONFIG["sd"]["packs"]:
        built = BUILD / "packs" / pk["name"]
        if (built / "Index.lua").exists():
            parts.append((built, pk["name"]))
    if capture:
        parts.append((ROOT / "tools" / "AGPS_Capture", "AGPS_Capture"))
    legacy = addons / pack.LEGACY_PACK
    if legacy.exists():
        shutil.rmtree(legacy)  # (the single pack of the first builds, now split per continent)
        print(f"removed the old {pack.LEGACY_PACK}")
    new = 0
    for src, name in parts:
        n = mirror(src, addons / name)
        new += n
        print(f"installed {name}" + (f" ({n} new files)" if n else ""))
    if new:
        print("New files: restart the game completely (a /reload doesn't see new files).")
    else:
        print("Only changed files: /reload in game.")


def build_and_report(flush: bool = False) -> list[dict]:
    reports = pack.build_packs(BUILD)
    print(pack.budget(reports), flush=flush)
    return reports


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wow", type=Path, default=DEFAULT_WOW, help="the _classic_beta_ folder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_inst = sub.add_parser("install")
    p_inst.add_argument("--capture", action="store_true", help="also install the manual AGPS_Capture dev tool")
    p_imp = sub.add_parser("import")
    p_imp.add_argument("--no-install", action="store_true")
    p_imp.add_argument("--no-stitch", action="store_true", help="skip stitching (faster)")
    p_st = sub.add_parser("stitch")
    p_st.add_argument("--id", action="append", help="only this spot (repeatable)")
    p_st.add_argument("--force", action="store_true", help="restitch spots that have a cube")
    p_st.add_argument("--no-install", action="store_true")
    p_h = sub.add_parser("import-harvest")
    p_h.add_argument("folder", type=Path)
    p_h.add_argument("--no-install", action="store_true")
    sub.add_parser("build")
    p_r = sub.add_parser("release-data")
    p_r.add_argument("--upload", action="store_true", help="upload to CurseForge (otherwise a dry run)")
    p_r.add_argument("--version", help="the packs' version (default: today, YYYY.MM.DD)")
    sub.add_parser("media")
    p_w = sub.add_parser("watch")
    p_w.add_argument("--every", type=float, default=3.0, help="seconds between checks")
    a = ap.parse_args(argv)

    if a.cmd == "install":
        install(a.wow, a.capture)
    elif a.cmd == "import":
        stats = pack.import_captures(a.wow, BUILD)
        k = 0 if a.no_stitch else pack.stitch_points(a.wow, BUILD)
        print(f"imported {stats['captures']} spots ({stats['missing']} screenshots not found, "
              f"{stats['skipped']} unfinished captures skipped); {k} newly stitched.")
        build_and_report()
        if not a.no_install:
            install(a.wow, False)
    elif a.cmd == "stitch":
        k = pack.stitch_points(a.wow, BUILD, only=set(a.id) if a.id else None, force=a.force)
        print(f"stitched {k} spots.")
        build_and_report()
        if not a.no_install:
            install(a.wow, False)
    elif a.cmd == "import-harvest":
        stats = pack.import_harvest(a.folder, BUILD)
        print(f"imported {stats['points']} harvested spots ({stats['skipped']} skipped).")
        build_and_report()
        if not a.no_install:
            install(a.wow, False)
    elif a.cmd == "build":
        build_and_report()
    elif a.cmd == "release-data":
        from svtools import release
        release.release_data(BUILD, ROOT / "dist", a.version, upload=a.upload)
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
            print(f"[{stamp}] {stats['captures']} spots in the list, {k} newly stitched.", flush=True)
            build_and_report(flush=True)
            if k:
                install(wow, False)
            else:
                print(f"[{stamp}] nothing new to install.", flush=True)
        except Exception as e:  # (keep watching: the next save may be fine)
            print(f"[{stamp}] import failed: {e!r}", flush=True)


if __name__ == "__main__":
    main()
