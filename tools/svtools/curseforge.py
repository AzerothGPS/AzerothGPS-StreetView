"""CurseForge uploads for AzerothGPS StreetView: the viewer (the release workflow) and the
continent packs (sv.py release-data). Adapted from AzerothGPS's .github/scripts/curseforge.py,
plus project relations (the viewer requires AzerothGPS and the continent packs).

Only the standard library: runs on a plain GitHub runner too.
  python tools/svtools/curseforge.py --dry-run                      the game version to upload for
  python tools/svtools/curseforge.py --project ID --zip Z --display "..." --changelog notes.md \\
      [--requires slug,slug]                                        upload
Environment: CF_API_TOKEN; optional CF_GAME_VERSION_ID (skips the lookup) or CF_GAME_VERSION
(the name to look for, default "1.60.1").
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import uuid

API = "https://wow.curseforge.com/api"
AGENT = "AzerothGPS-StreetView-release"


def get(path: str, token: str):
    req = urllib.request.Request(API + path, headers={"X-Api-Token": token, "User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def game_version(token: str) -> tuple[int, str]:
    """The game version to upload for: CF_GAME_VERSION_ID, else the one named CF_GAME_VERSION."""
    if os.environ.get("CF_GAME_VERSION_ID"):
        return int(os.environ["CF_GAME_VERSION_ID"]), "(set by CF_GAME_VERSION_ID)"
    want = os.environ.get("CF_GAME_VERSION", "1.60.1")
    types = {t["id"]: t for t in get("/game/version-types", token)}
    found = [v for v in get("/game/versions", token) if v.get("name") == want]
    if len(found) != 1:
        sys.exit(f"expected exactly one game version named {want!r}, found {len(found)}: set CF_GAME_VERSION_ID")
    t = types.get(found[0].get("gameVersionTypeID"), {})
    return found[0]["id"], f"{found[0]['name']} ({t.get('name')})"


def metadata(display: str, changelog: str, gv: int, requires: list[str] | None = None) -> dict:
    meta = {"changelog": changelog, "changelogType": "markdown", "displayName": display,
            "gameVersions": [gv], "releaseType": "release"}
    if requires:
        meta["relations"] = {"projects": [{"slug": s, "type": "requiredDependency"} for s in requires]}
    return meta


def upload(token: str, project: str | int, zip_path: str, meta: dict) -> dict:
    boundary = uuid.uuid4().hex
    with open(zip_path, "rb") as f:
        data = f.read()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"metadata\"\r\n\r\n{json.dumps(meta)}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(zip_path)}\"\r\n"
        "Content-Type: application/zip\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(f"{API}/projects/{project}/upload-file", data=body, method="POST", headers={
        "X-Api-Token": token, "Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="only look up the game version")
    p.add_argument("--project")
    p.add_argument("--zip")
    p.add_argument("--display")
    p.add_argument("--changelog", help="a file with the changelog (Markdown)")
    p.add_argument("--requires", default="", help="slugs of required projects, comma-separated")
    a = p.parse_args()
    token = os.environ.get("CF_API_TOKEN")
    if not token:
        sys.exit("CF_API_TOKEN is needed")
    gv, what = game_version(token)
    print(f"game version: {gv} {what}")
    if a.dry_run:
        return 0
    if not (a.project and a.zip and a.display and a.changelog):
        sys.exit("--project, --zip, --display and --changelog are needed to upload")
    requires = [s.strip() for s in a.requires.split(",") if s.strip()]
    changelog = open(a.changelog, encoding="utf-8").read()
    res = upload(token, a.project, a.zip, metadata(a.display, changelog, gv, requires))
    print(f"uploaded to CurseForge: {res}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
