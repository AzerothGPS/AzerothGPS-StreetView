# AzerothGPS StreetView

Companion addon to AzerothGPS (sibling checkout `../azerothgps`, public repo
AzerothGPS/AzerothGPS). This repo is **private**: https://github.com/AzerothGPS/AzerothGPS-StreetView.
`PLAN.md` is the full project plan (capture rig on a second PC, data packs, mini game).

## Rules

- Same hard rules as AzerothGPS (read its CLAUDE.md): the shipped addon is **display only**,
  no Blizzard files shipped, never execute shared data, flag gray areas.
- **Screenshots never go into git** (`build/` and `data/` are ignored). They're Blizzard
  content and large.
- Nothing personal in the repo: no Windows user names or paths, WoW account folder names,
  character names or emails. Author is "AzerothGPS".
- `tools/AGPS_Capture` is a **manual** developer tool for the user's real Blizzard account:
  it never moves the character or the camera (the user turns and presses the game's Set View
  keys; it only hides names and takes a screenshot per key press). Never published, and
  `sv.py install` leaves it out unless `--capture` is passed.
- **No automation of any kind on this PC's game.** Automated teleporting and capture live in
  the separate private repo AzerothGPS/streetview-harvester, for a private server on the
  other PC only. Never install anything from it into this PC's WoW folder.
- American spelling in user-facing text.

## Size and shipping (the user: always consider the CurseForge limit)

- CurseForge refuses files of 2 GB or more. `packs.json` has one SD pack per continent
  (Kalimdor with Zephras Isle; Eastern Kingdoms), each a separate CurseForge project that the
  viewer requires. Budget 1.8 GB per zip; `build_packs` refuses more, and every build prints the
  projection to all planned spots (100-yard spacing, about 4,120 spots).
- Measured: SD (512 side tiles, 256 up/down, q75) about 470 KB a spot, about 1.1 GB per
  continent; master/HD (1024/512) about 1.45 MB a spot. Check any change to tiles, quality or
  spacing against these before it goes in.
- HD packs: not made or shipped for now (the user may consider them later). Selling or
  paywalling them would clash with Blizzard's add-on policy (add-ons free) and Fan Content
  Policy (no selling game imagery): flag that if it comes up.
- Releases: the viewer by tag (workflow); the packs by `sv.cmd release-data --upload`, only when
  the user asks.

## Talking to AzerothGPS

Only through its public API, the `AzerothGPS` global (`../azerothgps/addon/AzerothGPS/Api.lua`,
`docs/api.md` there). If StreetView needs more from the map, add it to that API (small,
additive, with a lupa test) rather than reaching into AzerothGPS's private namespace.

## Coordinates and views

- World yards, x north, y west (AzerothGPS's convention). Headings are radians
  counter-clockwise from north (`GetPlayerFacing`'s convention).
- A point's views: yaw index 0..7 (counter-clockwise; the capture measures the facing of each shot) at pitches -45, 0, 45 plus straight up and down; file
  names `y<deg>_p<+/-deg>` (`Data.lua` `D.PoseName`, `tools/svtools/pack.py` `pose_name`,
  the capture addon's list: keep all three in step; a test checks it).
- `facing` in the pack is the heading of view 0. Image names are always counter-clockwise
  indexes: the manual capture names each shot from its measured facing, and the harvester
  normalizes with its calibrated `yaw_sign`. `D.yawSign` stays 1 (`/sv flipyaw` is a fallback).
- Images: 1024x512 JPEG (power of two). JPEG support on this client is checked with
  `/sv probe`; if it fails, switch the pack to BLP.

## Commands

Use the AzerothGPS venv: `%USERPROFILE%\.venvs\azerothgps\Scripts\python.exe`.

```
python tools/sv.py install     # copy StreetView and the continent packs into the game (--capture: + manual AGPS_Capture)
python tools/sv.py import      # AGPS_Capture screenshots -> stitched spots -> build/packs, then install
python tools/sv.py watch       # the same on every /reload
python tools/sv.py release-data  # dry run: build, zip and check the packs (--upload: to CurseForge)
python tools/sv.py build       # rebuild the packs and print their sizes
python tools/sv.py media       # regenerate Media/ (Figure.tga, Probe.jpg)
python -m pytest tests -q
```

After install: `/reload` for changed Lua; **new files (images included) need a full game
restart**. AzerothGPS itself installs with `agps install-addon` from its own repo.

## Commits

Commit and push completed work to origin (the private repo), short imperative messages.
