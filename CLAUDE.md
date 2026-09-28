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
- `facing` in the pack is the heading of view 0. `D.yawSign` says which way FlipCameraYaw
  turned (`/sv flipyaw` switches it if left and right come out swapped).
- Images: 1024x512 JPEG (power of two). JPEG support on this client is checked with
  `/sv probe`; if it fails, switch the pack to BLP.

## Commands

Use the AzerothGPS venv: `%USERPROFILE%\.venvs\azerothgps\Scripts\python.exe`.

```
python tools/sv.py install     # copy StreetView and the data pack into the game (--capture: + manual AGPS_Capture)
python tools/sv.py import      # AGPS_Capture screenshots -> build/AzerothGPS_StreetView_Data, then install
python tools/sv.py build       # rewrite the pack's Index.lua from build/points.json
python tools/sv.py media       # regenerate Media/ (Figure.tga, Probe.jpg)
python -m pytest tests -q
```

After install: `/reload` for changed Lua; **new files (images included) need a full game
restart**. AzerothGPS itself installs with `agps install-addon` from its own repo.

## Commits

Commit and push completed work to origin (the private repo), short imperative messages.
