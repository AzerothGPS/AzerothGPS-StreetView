"""AzerothGPS StreetView developer tool.

  sv.cmd install [--dev]          copy the viewer with its built pictures into the game's AddOns folder
                                  (--dev adds the private developer addon AzerothGPS_StreetView_Dev from
                                  the AzerothGPS-StreetView-Dev checkout next to this one: the manual
                                  capture tool, /sv demo against bots, Report picture)
  sv.cmd import                   the dev addon's capture screenshots -> stitched spots -> the packs, then install
  sv.cmd watch                    the same by itself on every /reload (Ctrl+C stops)
  sv.cmd stitch [--id ID] [--force]  (re)stitch imported spots
  sv.cmd import-harvest <folder>  spots stitched by streetview-harvester -> the packs, then install
  sv.cmd pull [--from //PC/agps-work] [--watch MIN]
                                  the same straight from the capture PC's share over the LAN (new
                                  and changed spots only; --from is remembered; --watch repeats)
  sv.cmd build                    rebuild the pictures (build/packs/) and print their size
  sv.cmd roads                    road sync: retire spots whose road is gone, list spots for new roads
  sv.cmd release [--upload]       zip the addon with its pictures for CurseForge and check it (a dry run);
                                  --upload sends it (needs CF_API_TOKEN and viewer.curseforge_project in packs.json)
  sv.cmd landmarks                landmarks.json (famous stops that always ship): merge the spots marked
                                  in game with the dev addon's /sv mark, and list them
  sv.cmd media                    regenerate the addon's own art (Media/)
  sv.cmd compare --name N --render ID   a spot as rendered and as captured in the game (on the private
                                  test server, --capture-wow), for the dev addon's Compare; then install --dev

The pictures ship inside the viewer addon (packs.json, under CurseForge's limit). The game folder
defaults to C:\\Program Files (x86)\\World of Warcraft\\_classic_beta_ (set AGPS_WOW or pass
--wow); every install also goes into each AddOns folder listed in %USERPROFILE%\\.agps-installs (shared
with AzerothGPS's install-addon: the capture PC's private test client, through its share). sv.cmd runs
this with the AzerothGPS venv's Python (Pillow, numpy, lupa).
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
# More AddOns folders every install also goes into, one per line ("#" comments): AzerothGPS's list (its
# cli.py EXTRA_INSTALLS), in the user's home folder so the paths stay out of git. The private test client's,
# which runs on the capture PC (streetview-harvester's SERVER.md: its share), never on the main PC's game.
EXTRA_INSTALLS = Path.home() / ".agps-installs"
BUILD = ROOT / "build"


def extra_addons_dirs() -> list[Path]:
    if not EXTRA_INSTALLS.is_file():
        return []
    return [Path(s.strip()) for s in EXTRA_INSTALLS.read_text(encoding="utf-8").splitlines()
            if s.strip() and not s.strip().startswith("#")]


def mirror(src: Path | list[Path], dst: Path) -> int:
    """Copy src over dst and delete what src no longer has. Several sources are laid over each
    other in order (the viewer's code, then its built pictures and Index.lua). Copies only files
    that changed (size or time). Returns the number of files that are new in dst (new files need a
    full game restart, changed Lua only /reload)."""
    want: dict = {}
    for s in ([src] if isinstance(src, Path) else src):
        for f in s.rglob("*"):
            if f.is_file():
                want[f.relative_to(s)] = f
    new = 0
    for rel, f in want.items():
        d = dst / rel
        if not d.exists():
            new += 1
        elif d.stat().st_size == f.stat().st_size and d.stat().st_mtime >= f.stat().st_mtime:
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
    keep_dirs = {p for rel in want for p in rel.parents}
    for f in sorted(dst.rglob("*"), reverse=True):
        rel = f.relative_to(dst)
        if f.is_dir():
            if rel not in keep_dirs:
                shutil.rmtree(f)
        elif rel not in want:
            f.unlink()
    return new


DEV_ADDON = ROOT.parent / "AzerothGPS-StreetView-Dev" / "addon" / "AzerothGPS_StreetView_Dev"
OLD_DEV = ["AGPS_Capture"]  # (the capture tool's own addon, before the dev tools were one addon)


def install(wow: Path, dev: bool) -> None:
    addons = wow / "Interface" / "AddOns"
    if not addons.is_dir():
        sys.exit(f"No AddOns folder at {addons}")
    install_into(addons, dev)


def install_into(addons: Path, dev: bool) -> None:
    # the viewer: its code with the built pictures and Index.lua laid over it (one addon)
    viewer = [ROOT / "addon" / "AzerothGPS_StreetView"]
    parts = []
    for pk in pack.CONFIG["sd"]["packs"]:
        built = BUILD / "packs" / pk["name"]
        if (built / "Index.lua").exists():
            if pk.get("in_viewer"):
                viewer.append(built)
            else:
                parts.append((built, pk["name"]))
    parts.insert(0, (viewer, "AzerothGPS_StreetView"))
    if dev:
        if not DEV_ADDON.is_dir():
            sys.exit(f"No developer addon at {DEV_ADDON} (clone AzerothGPS/AzerothGPS-StreetView-Dev next to this repo)")
        # (with the comparisons sv.cmd compare built: their pictures and CompareData.lua over the stub)
        dev_src = [DEV_ADDON] + ([BUILD / "compare"] if (BUILD / "compare").is_dir() else [])
        parts.append((dev_src, "AzerothGPS_StreetView_Dev"))
        for old in OLD_DEV:
            if (addons / old).exists():
                shutil.rmtree(addons / old)
                print(f"removed the old {old} (it's in AzerothGPS_StreetView_Dev now)")
    for old in pack.LEGACY_PACKS:  # (earlier layouts: the pictures are in the viewer now)
        if (addons / old).exists():
            shutil.rmtree(addons / old)
            print(f"removed the old {old}")
    new = 0
    for src, name in parts:
        n = mirror(src, addons / name)
        new += n
        print(f"installed {name}" + (f" ({n} new files)" if n else ""))
    if new:
        print("New files: restart the game completely (a /reload doesn't see new files).")
    else:
        print("Only changed files: /reload in game.")


def install_all(wow: Path, dev: bool) -> None:
    """The game folder given, then (for the default game) every AddOns folder in EXTRA_INSTALLS."""
    print(f"-> {wow}")
    install(wow, dev)
    if wow != DEFAULT_WOW:
        return
    main = (wow / "Interface" / "AddOns").resolve()
    for extra in extra_addons_dirs():
        if not extra.is_dir():
            print(f"-> {extra}: no AddOns folder there (listed in {EXTRA_INSTALLS}); skipped")
        elif extra.resolve() != main:
            print(f"-> {extra}")
            install_into(extra, dev)


def build_and_report(flush: bool = False) -> list[dict]:
    # (pictures players reported in Street Guess, from the game's saved settings: held back, taken again)
    reports = pack.build_packs(BUILD, reported=pack.reported_in_game(DEFAULT_WOW))
    print(pack.budget(reports), flush=flush)
    return reports


def pull_loop(wow: Path, src_arg: str | None, every_min: float | None, do_install: bool) -> None:
    import time
    from svtools import pull
    src = pull.resolve_source(src_arg, BUILD)
    while True:
        stats = pull.pull(src, BUILD)
        print(f"{time.strftime('%H:%M')} {src}: {stats['on_share']} spots on the share, "
              f"{stats['points']} new imported ({stats['skipped']} skipped), "
              f"{stats['reviews']} review pictures -> {BUILD / 'harvest-review'}", flush=True)
        if stats["points"]:
            build_and_report(flush=True)
            if do_install:
                install_all(wow, False)
        if not every_min:
            return
        time.sleep(every_min * 60)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wow", type=Path, default=DEFAULT_WOW, help="the _classic_beta_ folder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_inst = sub.add_parser("install")
    p_inst.add_argument("--dev", "--capture", dest="dev", action="store_true",
                        help="also install the private developer addon (capture, bot demo, Report picture)")
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
    p_p = sub.add_parser("pull")
    p_p.add_argument("--from", dest="src", help=r"the capture PC's share, e.g. //CAPTURE-PC/agps-work (remembered)")
    p_p.add_argument("--watch", type=float, metavar="MIN", help="pull again every MIN minutes (Ctrl+C stops)")
    p_p.add_argument("--no-install", action="store_true")
    sub.add_parser("build")
    p_rd = sub.add_parser("roads", help="road sync: retire spots whose road is gone, list spots for new roads")
    p_rd.add_argument("--agps", type=Path, default=ROOT.parent / "azerothgps", help="the AzerothGPS checkout")
    p_rd.add_argument("--harvester", type=Path, default=ROOT.parent / "streetview-harvester")
    p_r = sub.add_parser("release", aliases=["release-data"], help="the addon with its pictures, zipped for CurseForge")
    p_r.add_argument("--upload", action="store_true", help="upload to CurseForge (otherwise a dry run)")
    p_r.add_argument("--version", help="the packs' version (default: today, YYYY.MM.DD)")
    sub.add_parser("landmarks", help="landmarks.json: merge the spots marked in game (/sv mark) and list them")
    sub.add_parser("media")
    p_w = sub.add_parser("watch")
    p_w.add_argument("--every", type=float, default=3.0, help="seconds between checks")
    p_c = sub.add_parser("compare", help="a spot as rendered and as captured in the game, for the dev addon's Compare")
    p_c.add_argument("--name", required=True, help='the comparison\'s name, e.g. "Thunder Bluff"')
    p_c.add_argument("--render", required=True, help="the rendered spot's id (build/master), e.g. 1--1248-68")
    p_c.add_argument("--capture-wow", type=Path,
                     help="the game folder whose capture tool's spots to take (else --grabs)")
    p_c.add_argument("--grabs", type=Path, help="window grabs instead (k<k>_v<n>.png, k<k>_nadir.png: harvester.gm --shot)")
    p_c.add_argument("--facing", type=float, help="the grabs' first facing (default: the render's)")
    p_c.add_argument("--rings", help='which grabs make which ring, with their rough pitch, e.g. '
                     '"p0=nadir@-88,p2=down@-38,p4=level@8,p5=up@35,p6=zenith@60"')
    p_c.add_argument("--no-install", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "install":
        install_all(a.wow, a.dev)
    elif a.cmd == "import":
        stats = pack.import_captures(a.wow, BUILD)
        k = 0 if a.no_stitch else pack.stitch_points(a.wow, BUILD)
        print(f"imported {stats['captures']} spots ({stats['missing']} screenshots not found, "
              f"{stats['skipped']} unfinished captures skipped); {k} newly stitched.")
        build_and_report()
        if not a.no_install:
            install_all(a.wow, False)
    elif a.cmd == "stitch":
        k = pack.stitch_points(a.wow, BUILD, only=set(a.id) if a.id else None, force=a.force)
        print(f"stitched {k} spots.")
        build_and_report()
        if not a.no_install:
            install_all(a.wow, False)
    elif a.cmd == "import-harvest":
        stats = pack.import_harvest(a.folder, BUILD)
        print(f"imported {stats['points']} harvested spots ({stats['skipped']} skipped).")
        build_and_report()
        if not a.no_install:
            install_all(a.wow, False)
    elif a.cmd == "pull":
        pull_loop(a.wow, a.src, a.watch, not a.no_install)
    elif a.cmd == "build":
        build_and_report()
    elif a.cmd == "roads":
        from svtools import roads
        result = roads.run(BUILD, a.agps, a.harvester, pack.CONFIG)
        print(roads.report(result))
        print(f"written: {BUILD / 'road-diff.json'} (retired: out of the packs; add: the harvester's render list)")
        build_and_report()
    elif a.cmd in ("release", "release-data"):
        from svtools import release
        release.release_data(BUILD, ROOT / "dist", a.version, upload=a.upload)
    elif a.cmd == "landmarks":
        from svtools import landmarks
        doc = landmarks.load()
        marks = landmarks.read_marks(Path(a.wow)) if getattr(a, "wow", None) else []
        n = landmarks.merge_marks(doc, marks)
        if n:
            landmarks.save(doc)
        print(f"{len(marks)} marks in the game's SavedVariables, {n} landmarks updated")
        for line in landmarks.report(doc):
            print("  " + line)
    elif a.cmd == "media":
        from svtools import media
        media.make(ROOT / "addon" / "AzerothGPS_StreetView" / "Media")
    elif a.cmd == "watch":
        watch(a.wow, a.every)
    elif a.cmd == "compare":
        from svtools import compare
        if not (a.grabs or a.capture_wow):
            sys.exit("compare needs --grabs <folder> or --capture-wow <game folder>")
        rp = compare.parse_ring_pitches(a.rings)
        compare.build_set(a.name, a.render, a.capture_wow, BUILD, grabs=a.grabs, facing=a.facing,
                          rings={k: r for k, (r, _) in rp.items()} or None,
                          pitches={r: p for r, p in rp.values() if p is not None} or None)
        if not a.no_install:
            install_all(a.wow, True)


def watch(wow: Path, every: float) -> None:
    """Import new spots on their own: whenever the game saves the capture tool's list (on /reload
    or logging out), import and stitch what's new, then install. Stop with Ctrl+C."""
    import time

    def stamps():
        return {f: (f.stat().st_mtime, f.stat().st_size)
                for name in pack.CAPTURE_SAVES for f in (wow / "WTF" / "Account").glob(f"*/SavedVariables/{name}")}

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
                install_all(wow, False)
            else:
                print(f"[{stamp}] nothing new to install.", flush=True)
        except Exception as e:  # (keep watching: the next save may be fine)
            print(f"[{stamp}] import failed: {e!r}", flush=True)


if __name__ == "__main__":
    main()
