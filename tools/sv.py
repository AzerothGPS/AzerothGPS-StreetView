"""AzerothGPS StreetView developer tool.

  python tools/sv.py install [--capture]      copy the addons into the game's AddOns folder
                                             (--capture adds the manual AGPS_Capture dev tool)
  python tools/sv.py import                   screenshots from AGPS_Capture -> the data pack, then install
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
    sub.add_parser("build")
    sub.add_parser("media")
    a = ap.parse_args(argv)

    if a.cmd == "install":
        install(a.wow, a.capture)
    elif a.cmd == "import":
        stats = pack.import_captures(a.wow, BUILD)
        n, size = pack.build_pack(BUILD)
        print(f"imported {stats['captures']} spots ({stats['images']} pictures; {stats['missing']} screenshots not found,"
              f" {stats['skipped']} unfinished captures skipped). The pack has {n} street views, {size / 1e6:.1f} MB.")
        if not a.no_install:
            install(a.wow, False)
    elif a.cmd == "build":
        n, size = pack.build_pack(BUILD)
        print(f"{n} street views, {size / 1e6:.1f} MB")
    elif a.cmd == "media":
        from svtools import media
        media.make(ROOT / "addon" / "AzerothGPS_StreetView" / "Media")


if __name__ == "__main__":
    main()
