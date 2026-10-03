"""Releasing AzerothGPS StreetView to CurseForge: two addons, two projects (the user, 2026-10-03: the
pictures a download of their own, so a code update doesn't download them again).

- `sv.py release`: the viewer, AzerothGPS_StreetView (its code from git), zipped as
  AzerothGPS_StreetView-<toc version>.zip. --publish makes the GitHub release v<version> with it and the
  CHANGELOG.md section as notes; publishing that release runs .github/workflows/release.yml, which uploads it
  to the viewer's CurseForge project (packs.json viewer.curseforge_project, requiring AzerothGPS).
- `sv.py release-data`: the pictures, AzerothGPS_StreetView_DataPack (built here: they're never in git), zipped as
  AzerothGPS_StreetView_DataPack-<YYYY.MM.DD>.zip. --publish makes the GitHub release data-v<version>, and the
  workflow uploads it to the pictures' project (packs.json data.curseforge_project, requiring the viewer).

--upload sends a zip to CurseForge from here instead (CF_API_TOKEN set on this PC). Every upload or publish is
recorded in data-releases.jsonl (committed).

Checks before anything leaves: under the budget; only the addon's folder with its toc; the viewer's zip has
code and media but no pictures, the pictures' zip its Index.lua and the pictures; nothing personal in the text
files; no empty build.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import zipfile
from pathlib import Path

from . import pack

# Text that must never ship: Windows user folders, e-mail addresses, WoW account folder names.
PERSONAL = [re.compile(r"[A-Za-z]:[\\/]+Users[\\/]", re.I), re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
            re.compile(r"\d{6,}#\d")]


def zip_addon(sources: list[Path], name: str, dist: Path, version: str) -> Path:
    """dist/<name>-<version>.zip with the addon's folder at its top, the sources laid over each
    other in order. JPEGs stored, not deflated: they don't shrink and it's faster."""
    dist.mkdir(parents=True, exist_ok=True)
    out = dist / f"{name}-{version}.zip"
    if out.exists():
        out.unlink()
    files: dict = {}
    for src in sources:
        for f in src.rglob("*"):
            if f.is_file() and not any(part.startswith(".") for part in f.relative_to(src).parts):
                files[f.relative_to(src).as_posix()] = f
    with zipfile.ZipFile(out, "w") as z:
        for rel in sorted(files):
            f = files[rel]
            z.write(f, f"{name}/{rel}", zipfile.ZIP_STORED if f.suffix.lower() == ".jpg" else zipfile.ZIP_DEFLATED)
    return out


SHIPS = re.compile(r"^[^/]+/(?:[^/]+\.(?:toc|lua)|Media/[^/]+\.(?:tga|jpg|blp)|Images/.+\.jpg)$", re.I)


def check_zip(path: Path, name: str, budget: int, pictures: bool | None = None) -> list[str]:
    """What's wrong with the addon zip (empty list: fine). pictures: True for the pictures' addon (its
    Index.lua and Images/ must be there), False for the viewer (no Images/), None: either."""
    problems = []
    size = path.stat().st_size
    if size > budget:
        problems.append(f"{path.name} is {size / 1e9:.2f} GB, over the {budget / 1e9:.1f} GB budget")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if f"{name}/{name}.toc" not in names:
            problems.append(f"{name}/{name}.toc missing")
        # (a toc of another addon in the folder: the game would see two; 2026-10-03, a pack's left in the build)
        for n in names:
            if n.lower().endswith(".toc") and n != f"{name}/{name}.toc":
                problems.append(f"{n}: a second toc")
        images =[n for n in names if n.startswith(f"{name}/Images/")]
        if pictures is True:
            if f"{name}/Index.lua" not in names:
                problems.append(f"{name}/Index.lua missing")
            if not images:
                problems.append("no pictures in the pictures' zip")
        elif pictures is False and images:
            problems.append(f"{len(images)} pictures in the viewer's zip (they ship in their own addon)")
        for info in z.infolist():
            n = info.filename
            if not n.startswith(name + "/"):
                problems.append(f"{n}: outside the addon's folder")
            elif not SHIPS.match(n):
                problems.append(f"{n}: not a file the addon ships")
            if n.endswith((".toc", ".lua", ".txt")):
                text = z.read(info).decode("utf-8", "replace")
                for rx in PERSONAL:
                    if rx.search(text):
                        problems.append(f"{n}: looks personal ({rx.pattern})")
    return problems


def toc_version(viewer: Path) -> str:
    m = re.search(r"^## Version:\s*(\S+)", (viewer / f"{viewer.name}.toc").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "0"


def changelog_section(path: Path, version: str) -> str:
    """CHANGELOG.md's "## <version>" section (the release notes CurseForge shows), without its heading;
    empty when there's none."""
    if not path.exists():
        return ""
    out, on = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if on:
                break
            on = line[3:].strip() == version
            continue
        if on:
            out.append(line)
    return "\n".join(out).strip()


DATA_CHANGELOG = "CHANGELOG-DataPack.md"  # (the DataPack's own: a "## <YYYY.MM.DD>" section a version)


def data_notes(spots: int, version: str, changelog: Path | None = None) -> str:
    """The pictures' release notes: CHANGELOG-DataPack.md's section for the version, else a line of its own."""
    notes = changelog_section(changelog or pack.ROOT / DATA_CHANGELOG, version)
    return notes or (f"The street view pictures of {version}: {spots:,} street views. Needs AzerothGPS StreetView, "
                     "which needs AzerothGPS. Pictures of World of Warcraft (c) Blizzard Entertainment.")


def publish(z: Path, version: str, log=print, run=None, tag: str | None = None, title: str | None = None,
            notes: str | None = None) -> str:
    """The GitHub release <tag> (default v<version>) of the committed and pushed HEAD, with the zip attached
    and the notes (default: CHANGELOG.md's section for the version); its workflow then uploads the zip to
    CurseForge. Its URL."""
    import subprocess
    import tempfile
    run = run or (lambda cmd: subprocess.run(cmd, cwd=pack.ROOT, capture_output=True, text=True, check=True).stdout)
    if run(["git", "status", "--porcelain", "--untracked-files=no"]).strip():
        raise SystemExit("Not published: commit your changes first (the release is made from the pushed HEAD).")
    run(["git", "fetch", "-q", "origin"])
    head = run(["git", "rev-parse", "HEAD"]).strip()
    if head != run(["git", "rev-parse", "origin/main"]).strip():
        raise SystemExit("Not published: push first (HEAD isn't origin/main).")
    if notes is None:
        notes = changelog_section(pack.ROOT / "CHANGELOG.md", version)
        if not notes:
            raise SystemExit(f"Not published: no '## {version}' section in CHANGELOG.md.")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(notes)
    tag = tag or f"v{version}"
    url = run(["gh", "release", "create", tag, str(z), "--target", head,
               "--title", title or f"AzerothGPS StreetView {version}", "--notes-file", f.name]).strip()
    log(f"  published {url}: its workflow uploads the zip to CurseForge")
    return url


def _record(entry: dict) -> None:
    with (pack.ROOT / "data-releases.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(dict(entry, at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))) + "\n")


def _upload(z: Path, project, requires, display: str, notes: str, log) -> dict:
    token = os.environ.get("CF_API_TOKEN")
    if not token or not project:
        raise SystemExit("To upload: set CF_API_TOKEN, and the project in packs.json.")
    from . import curseforge

    gv, what = curseforge.game_version(token)
    log(f"game version: {gv} {what}")
    res = curseforge.upload(token, project, str(z), curseforge.metadata(display, notes, gv, requires))
    log(f"  uploaded {z.name}: {res}")
    return res


def release_viewer(dist: Path, version: str | None = None, upload: bool = False, cfg: dict | None = None,
                   log=print, viewer: Path | None = None, publish_it: bool = False) -> list[dict]:
    """Zip and check the viewer (its code, no pictures); --publish / --upload send it on."""
    cfg = cfg or pack.CONFIG
    name = cfg["viewer"]["name"]
    viewer = viewer or pack.ROOT / "addon" / name
    version = version or toc_version(viewer)
    z = zip_addon([viewer], name, dist, version)
    problems = check_zip(z, name, cfg["budget_bytes"], pictures=False)
    for p in problems:
        log(f"  PROBLEM {p}")
    if problems:
        raise SystemExit("Not released: fix the problems above first.")
    log(f"  {z.name}: {z.stat().st_size / 1e6:.2f} MB (the viewer's code; the pictures: sv.cmd release-data)")
    ready = [{"zip": z, "version": version}]
    if publish_it:
        url = publish(z, version, log)
        _record({"addon": name, "version": version, "bytes": z.stat().st_size, "github_release": url})
    elif upload:
        notes = changelog_section(pack.ROOT / "CHANGELOG.md", version)
        res = _upload(z, cfg["viewer"].get("curseforge_project"), cfg["viewer"].get("curseforge_requires"),
                      f"AzerothGPS StreetView {version}", notes, log)
        _record({"addon": name, "version": version, "bytes": z.stat().st_size, "curseforge": res})
    else:
        log(f"Dry run: {z} is ready. Nothing was uploaded (--publish or --upload does that).")
    return ready


def release_data(build: Path, dist: Path, version: str | None = None, upload: bool = False,
                 cfg: dict | None = None, log=print, publish_it: bool = False) -> list[dict]:
    """Build, zip and check the pictures' addon; --publish / --upload send it on."""
    cfg = cfg or pack.CONFIG
    data = cfg["data"]
    name = data["name"]
    version = version or dt.date.today().strftime("%Y.%m.%d")
    reports = pack.build_packs(build, version, cfg)
    log(pack.budget(reports, cfg))
    spots = sum(r["points"] for r in reports)
    if not spots:
        raise SystemExit("No street views built yet: nothing to release.")
    z = zip_addon([build / "packs" / name], name, dist, version)
    problems = check_zip(z, name, cfg["budget_bytes"], pictures=True)
    for p in problems:
        log(f"  PROBLEM {p}")
    if problems:
        raise SystemExit("Not released: fix the problems above first.")
    log(f"  {z.name}: {z.stat().st_size / 1e6:.1f} MB, {spots} street views"
        + ("" if data.get("curseforge_project") else "  (no data.curseforge_project in packs.json yet)"))
    ready = [{"zip": z, "spots": spots, "version": version}]
    entry = {"addon": name, "version": version, "pictures": version, "spots": spots, "bytes": z.stat().st_size}
    if publish_it:
        url = publish(z, version, log, tag=f"data-v{version}", title=f"{data['title']} {version}",
                      notes=data_notes(spots, version))
        _record(dict(entry, github_release=url))
    elif upload:
        res = _upload(z, data.get("curseforge_project"), data.get("curseforge_requires"),
                      f"{data['title']} {version}", data_notes(spots, version), log)
        _record(dict(entry, curseforge=res))
    else:
        log(f"Dry run: {z} is ready. Nothing was uploaded (--publish or --upload does that).")
    return ready
