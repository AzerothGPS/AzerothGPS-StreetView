"""Pull finished spots from the capture PC over the LAN.

The capture PC shares its streetview-harvester work folder read-only (the harvester's
tools/share-work.ps1, share name agps-work). Only spots that are new or changed since the last
pull are copied (compared by their meta.json, which the harvester writes last), then imported
exactly like import-harvest. The review pictures of the pilot come along into
build/harvest-review/.

The share path is remembered in build/harvest-source.txt (build/ is never in git).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from . import pack

SOURCE_FILE = "harvest-source.txt"
PULLED_FILE = "harvest-pulled.json"


def resolve_source(arg: str | None, build: Path) -> Path:
    """The share: --from (then remembered), else AGPS_HARVEST, else the remembered one."""
    remembered = build / SOURCE_FILE
    if arg:
        build.mkdir(parents=True, exist_ok=True)
        remembered.write_text(arg.strip(), encoding="utf-8")
        return Path(arg.strip())
    if os.environ.get("AGPS_HARVEST"):
        return Path(os.environ["AGPS_HARVEST"])
    if remembered.exists():
        return Path(remembered.read_text(encoding="utf-8").strip())
    raise SystemExit(r"No capture share yet: pass --from \\<capture PC name>\agps-work once.")


def pull(src: Path, build: Path, log=print) -> dict:
    """Copy new or changed spots from <src>/out, import them, and fetch <src>/review/*.jpg."""
    try:
        os.listdir(src)
    except OSError as e:
        # 5 access denied, 1326 unknown user or bad password, 86 bad password, 1331 account
        # disabled, 1907 password must change: all mean this PC hasn't signed in to the share yet
        if isinstance(e, PermissionError) or getattr(e, "winerror", None) in (5, 86, 1326, 1331, 1907):
            raise SystemExit(f"{src}: access denied. Sign in to the capture PC once: Win+R, type "
                             f"{str(src)}, enter that PC's Windows sign-in and tick 'Remember my "
                             "credentials'.")
        raise SystemExit(f"{src} isn't reachable ({e.strerror}): is the capture PC on and the share set up?")
    out = src / "out"
    if not out.is_dir():  # the harvester hasn't finished a spot yet
        return {"points": 0, "images": 0, "skipped": 0, "reviews": 0, "on_share": 0}
    pulled_file = build / PULLED_FILE
    pulled = json.loads(pulled_file.read_text(encoding="utf-8")) if pulled_file.exists() else {}
    staging = build / "harvest-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staged = {}
    for meta in sorted(out.glob("*/meta.json")):
        # (a spot the capture PC is rendering again right now: its files come and go under us;
        # it's skipped and pulled next time)
        try:
            digest = hashlib.sha1(meta.read_bytes()).hexdigest()
            if pulled.get(meta.parent.name) == digest:
                continue
            shutil.copytree(meta.parent, staging / meta.parent.name)
        except (OSError, shutil.Error):
            shutil.rmtree(staging / meta.parent.name, ignore_errors=True)
            continue
        staged[meta.parent.name] = digest
    stats = {"points": 0, "images": 0, "skipped": 0}
    if staged:
        stats = pack.import_harvest(staging, build, log=log)
        for name, digest in staged.items():
            pid = json.loads((staging / name / "meta.json").read_text(encoding="utf-8")).get("id")
            if pid and len(list((build / "master" / pid / "cube").glob("*.jpg"))) == 24:
                pulled[name] = digest  # skipped spots are tried again on the next pull
        shutil.rmtree(staging)
        pulled_file.write_text(json.dumps(pulled, indent=1), encoding="utf-8")
    stats["reviews"] = 0
    review = src / "review"
    if review.is_dir():
        dst = build / "harvest-review"
        dst.mkdir(parents=True, exist_ok=True)
        for f in review.glob("*.jpg"):
            t = dst / f.name
            if not t.exists() or t.stat().st_mtime < f.stat().st_mtime:
                shutil.copy2(f, t)
                stats["reviews"] += 1
    stats["on_share"] = sum(1 for _ in out.glob("*/meta.json"))
    return stats
