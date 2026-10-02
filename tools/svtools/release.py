"""Releasing AzerothGPS StreetView to CurseForge (`sv.py release`): the viewer's code and its
pictures in one addon zip (the user, 2026-09-29: no separate data packs).

The pictures never go into git, so the tag workflow can't release them: it makes a code-only
GitHub release. This builds the pictures (the packs.json pack `in_viewer`), lays them and the
real Index.lua over the viewer's code in one zip, checks it, and with --upload sends it to the
viewer's CurseForge project (packs.json viewer.curseforge_project), requiring AzerothGPS. Every
upload is recorded in data-releases.jsonl (committed).

Checks before anything leaves: under the budget; only the viewer's folder, with its toc files,
Lua, Media and JPEG tiles; nothing personal in the text files; no empty build.
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
    other in order (the viewer's code, then its pictures and Index.lua). JPEGs stored, not
    deflated: they don't shrink and it's faster."""
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


def check_zip(path: Path, name: str, budget: int) -> list[str]:
    """What's wrong with the addon zip (empty list: fine)."""
    problems = []
    size = path.stat().st_size
    if size > budget:
        problems.append(f"{path.name} is {size / 1e9:.2f} GB, over the {budget / 1e9:.1f} GB budget")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if f"{name}/{name}.toc" not in names:
            problems.append(f"{name}/{name}.toc missing")
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


def release_data(build: Path, dist: Path, version: str | None = None, upload: bool = False,
                 cfg: dict | None = None, log=print, viewer: Path | None = None) -> list[dict]:
    """Build, zip and check the addon (code and pictures); --upload sends it to CurseForge."""
    cfg = cfg or pack.CONFIG
    viewer = viewer or pack.ROOT / "addon" / cfg["viewer"]["name"]
    name = cfg["viewer"]["name"]
    version = version or toc_version(viewer)
    data_version = dt.date.today().strftime("%Y.%m.%d")
    reports = pack.build_packs(build, data_version, cfg)
    log(pack.budget(reports, cfg))
    spots = sum(r["points"] for r in reports)
    if not spots:
        raise SystemExit("No street views built yet: nothing to release.")
    sources = [viewer] + [build / "packs" / pk["name"] for pk in cfg["sd"]["packs"] if pk.get("in_viewer")]
    z = zip_addon(sources, name, dist, version)
    problems = check_zip(z, name, cfg["budget_bytes"])
    for p in problems:
        log(f"  PROBLEM {p}")
    if problems:
        raise SystemExit("Not released: fix the problems above first.")
    log(f"  {z.name}: {z.stat().st_size / 1e6:.1f} MB, {spots} street views"
        + ("" if cfg["viewer"].get("curseforge_project") else "  (no viewer.curseforge_project in packs.json yet)"))
    ready = [{"zip": z, "spots": spots, "version": version}]
    if not upload:
        log(f"Dry run: {z} is ready. Nothing was uploaded (--upload does that).")
        return ready
    token = os.environ.get("CF_API_TOKEN")
    project = cfg["viewer"].get("curseforge_project")
    if not token or not project:
        raise SystemExit("To upload: set CF_API_TOKEN, and viewer.curseforge_project in packs.json.")
    from . import curseforge

    gv, what = curseforge.game_version(token)
    log(f"game version: {gv} {what}")
    notes = changelog_section(pack.ROOT / "CHANGELOG.md", version) + (
        f"\n\n{spots} street views (pictures {data_version}). Pictures of World of Warcraft (c) Blizzard "
        "Entertainment. Needs AzerothGPS.")
    res = curseforge.upload(token, project, str(z),
                            curseforge.metadata(f"AzerothGPS StreetView {version}", notes, gv,
                                                cfg["viewer"].get("curseforge_requires")))
    log(f"  uploaded {z.name}: {res}")
    record = pack.ROOT / "data-releases.jsonl"
    with record.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"addon": name, "version": version, "pictures": data_version, "spots": spots,
                            "bytes": z.stat().st_size, "curseforge": res,
                            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}) + "\n")
    return ready
