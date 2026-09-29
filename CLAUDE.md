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
- **The user's own screenshots are never shipped** (the user, 2026-09-28). Spots from
  AGPS_Capture are `source: "manual"` (`pack.is_manual`): they stay in the master as ground
  truth for checking renders, and `build_packs` leaves them out. The raw screenshots don't stay
  in the game install: they live in `data/manual-captures/Screenshots` (git-ignored).
- **No automation of any kind on this PC's game.** Automated teleporting and capture live in
  the separate private repo AzerothGPS/streetview-harvester, for a private server on the
  other PC only. Never install anything from it into this PC's WoW folder.
- American spelling in user-facing text.

## Size and shipping (the user: always consider the CurseForge limit)

- CurseForge refuses files of 2 GB or more. `packs.json` has one SD pack per continent
  (Kalimdor with Zephras Isle; Eastern Kingdoms), each a separate CurseForge project that the
  viewer requires. Budget 1.8 GB per zip; `build_packs` refuses more, and every build prints the
  projection to all planned spots (100-yard spacing, about 4,120 spots).
- **Shipped every ~200 yd** (the user, 2026-09-29): the capture renders every 100 yd into the master,
  `pack.ship_points` thins the packs to `ship_spacing_yd` (a spot is kept unless a kept one is within
  150 yd; neighbors end up ~180-200 yd apart), and the arrows reach `D.NEXT_RANGE` = 310 yd. That puts
  everything at about 1.05 GB (Kalimdor + Zephras 0.41, Eastern Kingdoms ~0.63).
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

## Where in the Azeroth? (Street Guess, Game.lua)

A GeoGuessr-style game from the button above the figure: solo, party or whisper, 1/3/5 rounds.
A street view pops up for 30 s with a countdown on it and the panel (no zone name or coordinates,
no walking on, not marked on the map); in that time the player double-clicks the map to place a
guess (again to move it), and the one placed when the time runs out counts;
street views come only from the map packs every player has (they're exchanged on joining; the
panel lists who lacks which, or has an older one). `Gm.Score` gives 0-100 (full within 25 yd, then
`floor(100 * e^(-((yd - 25) / 3800) ^ 1.3))`: 88 at 800 yd, 72 at 1,600, 16 at 6,000; the last points the hardest;
the celebration needs an average round score of 75: the player's solo, the winner's otherwise). While a game is on the map is held (`AzerothGPS.HoldMap`, API
version 3): the route and directions panel hide, double-clicks are guesses, and the game's panel
sits in the directions' place; its X leaves and the route comes back. Players talk through addon
messages (prefix `AGPSSV`, the protocol is at the top of Game.lua), invitations are always asked.
The logic runs through `Gm.io`; `tests/test_game.py` plays whole games between simulated players.

**Broken pictures:** `pack.retake` holds spots back from the packs and lists them in
`build/retake.json` for the capture PC to take again: broken renders (8+ of the 16 side tiles one flat
color, measured once per import) and pictures players reported with Street Guess's "Report picture"
(saved in `AzerothGPSStreetViewDB.reported`, read from the game's WTF folder by `sv.cmd pull`/`build`).
Street Guess only picks spots whose files were there when the game last fully started
(`D.loadable`, saved on a fresh start): pictures installed after it show as plain green until a restart.

## Updating the street views (standing rule, 2026-09-29)

Every data update starts from the roads: compare the rendered spots with AzerothGPS's current
`Data/Roads.lua`. Spots whose road is gone are retired (left out of the packs, kept in the
master); new roads get spots on the render list. Then build, check sizes and the retake list, and
release. Rendering can run on any designated PC with the harvester repo's setup guide (wow.export
and Blender only read the client's files; nothing runs the game). Details: `PLAN.md` part 11.

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
python tools/sv.py pull [--from //PC/agps-work] [--watch 10]  # harvested spots from the capture PC's share (LAN)
python tools/sv.py release-data  # dry run: build, zip and check the packs (--upload: to CurseForge)
python tools/sv.py build       # rebuild the packs and print their sizes
python tools/sv.py media       # regenerate Media/ (Figure.tga, Probe.jpg)
python -m pytest tests -q
```

After install: `/reload` for changed Lua; **new files (images included) need a full game
restart**. AzerothGPS itself installs with `agps install-addon` from its own repo.

## Commits

Commit and push completed work to origin (the private repo), short imperative messages.
