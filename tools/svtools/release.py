"""Releasing the continent packs to CurseForge (sv.py release-data).

The pictures never go into git, so the packs can't be released by the tag workflow (that one
releases the viewer's code). This builds each pack with a date version, zips it, checks it,
and with --upload sends each zip to its own CurseForge project (packs.json: curseforge_project).
The viewer's CurseForge project lists the packs as required dependencies (curseforge_slug), so
installing the viewer brings them. Every upload is recorded in data-releases.jsonl (committed).

Checks before anything leaves: every zip under the budget; only the pack's own folder, its toc,
Index.lua and JPEG tiles inside; nothing personal in the text files; no empty pack.
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


def zip_pack(folder: Path, dist: Path, version: str) -> Path:
    """dist/<name>-<version>.zip with the pack's folder at its top (JPEGs stored, not deflated:
    they don't shrink and it's faster)."""
    dist.mkdir(parents=True, exist_ok=True)
    out = dist / f"{folder.name}-{version}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w") as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file():
                arc = f"{folder.name}/{f.relative_to(folder).as_posix()}"
                z.write(f, arc, zipfile.ZIP_STORED if f.suffix.lower() == ".jpg" else zipfile.ZIP_DEFLATED)
    return out


def check_zip(path: Path, name: str, budget: int) -> list[str]:
    """What's wrong with a pack zip (empty list: fine)."""
    problems = []
    size = path.stat().st_size
    if size > budget:
        problems.append(f"{path.name} is {size / 1e9:.2f} GB, over the {budget / 1e9:.1f} GB budget")
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            n = info.filename
            if not n.startswith(name + "/"):
                problems.append(f"{n}: outside the pack's folder")
            elif not (n == f"{name}/{name}.toc" or n == f"{name}/Index.lua"
                      or (n.startswith(f"{name}/Images/") and n.lower().endswith(".jpg"))):
                problems.append(f"{n}: not a file a pack ships")
            if n.endswith((".toc", ".lua")):
                text = z.read(info).decode("utf-8", "replace")
                for rx in PERSONAL:
                    if rx.search(text):
                        problems.append(f"{n}: looks personal ({rx.pattern})")
    return problems


def release_data(build: Path, dist: Path, version: str | None = None, upload: bool = False,
                 cfg: dict | None = None, log=print) -> list[dict]:
    cfg = cfg or pack.CONFIG
    version = version or dt.date.today().strftime("%Y.%m.%d")
    reports = pack.build_packs(build, version, cfg)
    log(pack.budget(reports, cfg))
    ready = []
    bad = False
    for r in reports:
        pk = next(p for p in cfg["sd"]["packs"] if p["name"] == r["name"])
        if not r["points"]:
            log(f"  {r['name']}: no spots yet, not released")
            continue
        z = zip_pack(build / "packs" / r["name"], dist, version)
        problems = check_zip(z, r["name"], cfg["budget_bytes"])
        for p in problems:
            log(f"  PROBLEM {p}")
        bad = bad or bool(problems)
        log(f"  {z.name}: {z.stat().st_size / 1e6:.1f} MB, {r['points']} spots"
            + ("" if pk.get("curseforge_project") else "  (no curseforge_project in packs.json yet)"))
        ready.append({"pack": pk, "zip": z, "report": r})
    if bad:
        raise SystemExit("Not released: fix the problems above first.")
    if not upload:
        log(f"Dry run: {len(ready)} zips in {dist}. Nothing was uploaded (--upload does that).")
        return ready
    token = os.environ.get("CF_API_TOKEN")
    missing = [x["pack"]["name"] for x in ready if not x["pack"].get("curseforge_project")]
    if not token or missing:
        raise SystemExit("To upload: set CF_API_TOKEN, and curseforge_project in packs.json for "
                         + (", ".join(missing) if missing else "every pack") + ".")
    from . import curseforge

    gv, what = curseforge.game_version(token)
    log(f"game version: {gv} {what}")
    record = pack.ROOT / "data-releases.jsonl"
    for x in ready:
        pk, r = x["pack"], x["report"]
        notes = (f"Street views of {pk['title']}: {r['points']} spots. Screenshots of World of Warcraft "
                 "(c) Blizzard Entertainment. Needs AzerothGPS StreetView.")
        res = curseforge.upload(token, pk["curseforge_project"], str(x["zip"]),
                                curseforge.metadata(f"StreetView {pk['title']} {version}", notes, gv))
        log(f"  uploaded {x['zip'].name}: {res}")
        with record.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"pack": pk["name"], "version": version, "spots": r["points"],
                                "bytes": x["zip"].stat().st_size, "curseforge": res,
                                "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}) + "\n")
    return ready
