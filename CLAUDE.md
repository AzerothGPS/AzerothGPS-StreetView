# AzerothGPS StreetView

Companion addon to AzerothGPS (sibling checkout `../azerothgps`, public repo
AzerothGPS/AzerothGPS). This repo is **public** (since 2026-10-02): https://github.com/AzerothGPS/AzerothGPS-StreetView.
The full project plan is `docs/PLAN.md` in the private Dev repo (AzerothGPS-StreetView-Dev, checked out next
to this one); this repo is public, so the plan, the capture setup and anything about how the pictures are
made beyond offline rendering stay there.

## Rules

- Same hard rules as AzerothGPS (read its CLAUDE.md): the shipped addon is **display only**,
  no Blizzard files shipped, never execute shared data, flag gray areas.
- **Screenshots never go into git** (`build/` and `data/` are ignored). They're Blizzard
  content and large.
- Nothing personal in the repo: no Windows user names or paths, WoW account folder names,
  character names or emails. Author is "AzerothGPS".
- **Developer tools are not in this addon** (the user, 2026-09-30): they live in the private repo
  AzerothGPS/AzerothGPS-StreetView-Dev (checked out next to this one), one addon
  `AzerothGPS_StreetView_Dev`: the **manual** capture tool (it never moves the character or the camera:
  the player turns and presses the game's Set View keys; it only hides names and takes a screenshot per
  key press), `/sv demo [players] [rounds]` (a real
  Where in the Azeroth? game against bots, nothing sent) and the Report picture button (`/sv reports`).
  Never published; `sv.py install --dev` installs it. The shipped addon only offers hooks for it
  (`AzerothGPS_StreetView_Extend`, `ns.commands`, `Gm.internal`, `Gm.OnPanel`/`Gm.extraButtons`,
  `Gm.Skip`), and a test checks no dev tool ships.
- **The user's own screenshots are never shipped** (the user, 2026-09-28). Spots from
  the capture tool are `source: "manual"` (`pack.is_manual`): they stay in the master as ground
  truth for checking renders, and `build_packs` leaves them out. The raw screenshots don't stay
  in the game install: they live in `data/manual-captures/Screenshots` (git-ignored).
- **No automation of any kind in the game.** The street views are rendered offline (wow.export and
  Blender read the client's files; nothing runs the game) by the separate private repo
  AzerothGPS/streetview-harvester, on a capture PC. Never install anything from it into the game.
- **This repo is public** (the user, 2026-10-02): how the pictures are made beyond offline rendering, test
  setups, and anything that drives a character stay out of it (code, comments, docs, held.json reasons);
  they belong in the private Dev repo.
- American spelling in user-facing text.

## Size and shipping (the user: always consider the CurseForge limit)

- **One addon** (the user, 2026-09-29; split into two and back on 2026-10-03, keeping the alert): the pictures
  ship inside AzerothGPS_StreetView itself, no separate data packs. `packs.json` has a single pack
  `AzerothGPS_StreetView` (`in_viewer`, every continent); the build writes its pictures and real `Index.lua` to
  `build/packs/AzerothGPS_StreetView/`, and `sv.cmd install` / `sv.cmd release` lay them over the viewer's code
  (git has an empty `Index.lua` stub, loaded last by the toc). `install` removes the old
  Kalimdor/EasternKingdoms/Data pack folders (`pack.LEGACY_PACKS`); `check_zip` refuses a second toc.
  CurseForge refuses files of 2 GB or more: budget 1.8 GB for the whole zip; `build_packs` refuses more, and every
  build prints the projection to all planned spots.
- **No pictures found** (the user, 2026-10-03: a copy with the empty stub only, GitHub's source zip, an install
  cut short): Core.lua `ns.NeedData`/`ns.ShowDataNotice`: a chat line at login and the "Street View Pictures
  Missing" popup (AzerothGPS.Window: reinstall from CurseForge, `ns.PAGE_URL` to copy) on every way in: dragging or
  clicking the figure, `/sv here|open`, a boss's Shift-click (its hint still shows in a dungeon), Where in the
  Azeroth?'s button, `Gm.Start`, a game's link, an invitation accepted (Game.lua `NoData`, `io.noData`);
  `test_without_the_pictures_every_way_in_shows_the_notice`.
- **Shipped every ~200 yd** (the user, 2026-09-29): the capture renders every 100 yd into the master,
  `pack.ship_points` thins the packs to `ship_spacing_yd` (a spot is kept unless a kept one is within
  150 yd; neighbors end up ~180-200 yd apart), and the arrows reach `D.NEXT_RANGE` = 310 yd. That puts
  everything at about 0.85-0.9 GB (1,407 planned shipped spots, ~600 KB each).
- Measured: SD (512 side tiles, 256 up/down, q75) about 470 KB a spot, about 1.1 GB per
  continent; master/HD (1024/512) about 1.45 MB a spot. Check any change to tiles, quality or
  spacing against these before it goes in.
- HD packs: not made or shipped for now (the user may consider them later). Selling or
  paywalling them would clash with Blizzard's add-on policy (add-ons free) and Fan Content
  Policy (no selling game imagery): flag that if it comes up.
- Releases (CurseForge project 1721639), only when the user asks: bump the toc's version and add its
  `## <version>` section to CHANGELOG.md, commit and push, then `sv.cmd release --publish`. That builds the
  zip (code and pictures) here, checks it, and makes the GitHub release v<version> with the zip attached;
  publishing it runs .github/workflows/release.yml, which uploads the zip to CurseForge (requiring AzerothGPS)
  with the repo's `CF_API_TOKEN` secret, as AzerothGPS's own releases. (`--upload` sends it from this PC instead.)

## Talking to AzerothGPS

Only through its public API, the `AzerothGPS` global (`../azerothgps/addon/AzerothGPS/Api.lua`,
`docs/api.md` there). If StreetView needs more from the map, add it to that API (small,
additive, with a lupa test) rather than reaching into AzerothGPS's private namespace.

**The map follows the arrows** (the user, 2026-10-02; Viewer.lua `follow`): the first arrow clicked in a viewing saves
the map's view (`AzerothGPS.SaveView`), each spot walked to centers the map at its zoom (`LookAt`), and closing restores
the saved view (`RestoreView`), unless the player moved or zoomed the map meanwhile (`MapMoved`, checked against where
it was put last): then it's left alone for the rest of the viewing. Never during a game.

## Where in the Azeroth? (Street Guess, Game.lua)

A GeoGuessr-style game from the button above the figure: solo, party, whisper or Link, a level, 1/3/5 rounds.
**Levels** (the user, 2026-10-01): Normal, Heroic, Mythic (`Gm.LEVELS`), picked by the host or solo player and sent
in I and W; every player's map is held in its style (`Gm.LEVEL_STYLES`: "minimap" terrain, "zone" world map
revealed, "unrevealed" nothing revealed) through `AzerothGPS.HoldMap`'s opts.style (API version 9; older: unlocked,
a note printed).
Link (2026-09-30) is an open game: the host posts a plain-text code `AGPSSV-<id>-<rounds>` in say,
guild, the group or a numbered channel (panel buttons; chat needs the click); other players' chat
filter turns it into a `garrmission:agpssv:` link, and a click joins the game's hidden channel
`AGPSSV<id>` (messages go there) and whispers J to the host, who takes up to 10 (`Gm.MAX_PLAYERS`; same realm and
faction). Every game's lobby counts down 30 s for everyone who joined (I and W carry the seconds left);
the host can start sooner, and a party's starts once everyone answered.
**Addon message throttle** (the user, 2026-10-02): the client lets a prefix send 10 messages in a burst, then 1 a
second, and drops the rest silently (`SendAddonMessage` returns 3, AddonMessageThrottle; 8 is the server's channel
throttle); a game's start once sent a K per player, the roster and P at once, and with 9+ players round 1's street
view was lost. Every message goes through `Send`'s queue (`Gm.Pump`: `Gm.SEND_BURST` 8, then `Gm.SEND_RATE` a
second; the round's P/G/N/F/X/R first; 3, 8 or 11 (an encounter's lockdown) tried again, `Gm.SEND_TRIES`); whispers outside an instance aren't
throttled and go straight out. Games are capped at 10 players to stay well under it. Never call `io().send`
directly. **Game channels are left** `Gm.LEAVE_SECONDS` after the game ends (its F or X sent first), and
`Gm.SweepChannels` leaves any other `AGPSSV<digits>` channel (after a reload, every 30 s): channels per character
are few. The tests' `Net` throttles like the client (`net.dropped`).
A street view pops up for 30 s (no zone name or coordinates, no walking on, not marked on the map); in that
time the player double-clicks the map to place a guess (again to move it), and the one placed when the time
runs out counts. **The game's details are in the street view's top-right corner** (the user, 2026-10-01: the
level and worth on the map panel's title ran under its timer): a box with the level and round, the time
left large, the round's worth; in a result the points and the yards, at the end "You win!" or "Placed 4th"
(no line saying who won: the winner's name in the list rolls, a wave of size and the celebration's colors
through its letters, `V.AnimateHud`; the celebration's glow around the box as around the map's panel,
`Gm.CelebrateColor`); and under them the player list (`Gm.Board`: places, who guessed, the points, the totals; the
mouse wheel scrolls past 5, the player's own row pinned; solo, the rounds' scores). Its "-" folds it to the
time left, "+" opens it (kept in `ns.db.viewer.hudFolded`). `Gm.Hud` gives its text, `V.SetHud` draws it,
tests/test_game_ui.py on a frame mock. The map's panel keeps to little: the round and the time left on its
title (`Gm.PanelTitle`; the lobby and the end: the game's name and level), one line about the guess, and the
player list only while the street view doesn't show the game (the lobby, or closed);
only open-world and city spots are used, never instances or caves (the user, 2026-09-29: cities are in, Undercity's level too, placed on its continent by `Gm.OnMap`; any spot with a
`kind`, which the harvester's meta.json sets and the Index carries, or a level of 20000+ is skipped); street views come only from the map packs every player has (they're exchanged on joining; the
panel lists who lacks which, or has an older one). **The answer up close** (the user, 2026-10-02): a result's map left alone (`game.mapSet`, where the game put it) zooms in on the answer for its last `Gm.ANSWER_ZOOM_SECONDS` (`ZoomToAnswer`, `Gm.ANSWER_ZOOM_YD`); moved by the player, not that round. **A round's worth** (the user, 2026-10-01): 100 at a spot
by a point of interest, up to 200 far from any (`svtools/worth.py`: AzerothGPS's flight masters and map POIs,
Data/Pois.lua kinds 1-2, and every landmark; 100 within 100 yd, 200 from 1,000 yd, rounded to 5s; the Index's
`worth`); the host sends it in P (`game.worths`), so everyone scores alike. `Gm.Score(yd, worth)` gives 0 to the
worth (all of it within 25 yd, then `floor(worth * e^(-((yd - 25) / 1700) ^ 1.1))`: 92% at 200 yd, 78% at 500, 58%
at 1,000, 30% at 2,000, 7% at 4,000; tightened 2026-09-30); ties go to the closer guess: `Gm.Fine` gives a score
to the hundredth from where in its points' band of yards the guess was (100 points: 99.8 at 5 yd, 99.2 at 20),
shown only where players would tie (`Gm.ShowTied`), and `Gm.Standings`/`Gm.Winners` order by it after the whole
points (2026-09-30); the celebration needs 75% of what the rounds were worth (`Gm.Percent`): the player's solo,
the winner's otherwise). While a game is on the map is held (`AzerothGPS.HoldMap`, API
version 3): the route and directions panel hide, double-clicks are guesses, and the game's panel
sits in the directions' place; its X leaves and the route comes back. Players talk through addon
messages (prefix `AGPSSV`, the protocol is at the top of Game.lua). **Nothing is sent by itself** (the user,
2026-10-02): the menu has Solo and Link only; every game with others is an open game whose link the panel's buttons
put into the chat box (Party, Raid, Say, Guild, the channels, Target: a whisper to the target; `Gm.PostLink`,
`io.post` inserts, like linking a map position: the player presses Enter). The link says "[Join Where in the Azeroth?: Heroic, 3 rounds]": the code ends in
its level's letter (`AGPSSV-<id>-<rounds>-<N|H|M>`). An I invitation (bots, older clients) shows as such a link in
chat, never a popup; unclicked by the lobby's end, declined (`Ask`, `Gm.AnswerInvite`).
The logic runs through `Gm.io`; `tests/test_game.py` plays whole games between simulated players.
**A /reload doesn't end a game** (the user, 2026-10-01): PLAYER_LOGOUT saves it (`Gm.Snapshot`, plain data in
`AzerothGPSStreetViewDB.game`, the street view by id) and `Gm.TryResume` takes it up again once the windows are
built and PLAYER_ENTERING_WORLD says it was a reload (`ns.reloadedUI`); a real login drops it. GetTime() runs on
through a reload, so the deadlines hold; a game against bots keeps their answers (`game.botQueue`). The player
back sends R: the others whisper their S again, the host the round as it is (P, G with the seconds left, N, F).
`Gm.OnResume(fn)`: the dev addon seats its demo bots again. Any new game state must stay plain data.
**Names (2026-09-30):** WoW Forever's players have a first name and a surname (the client's regional unique
names: `UnitName` returns both; chat shows "First Surname"). `io.me` builds "First Surname-Realm" (`Gm.UnitFullName`), and
as a fallback J carries the host's name as the joiner sees it and W the joiner's as the host sees it, so
each side takes the others' spelling (`Gm.SameRoot` guards it: the same first name). The tests' `seen_as` covers it.

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
and Blender only read the client's files; nothing runs the game). Details: the Dev repo's `docs/PLAN.md` part 11.

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
python tools/sv.py install     # copy StreetView with its pictures into the game (--dev: + the private dev addon; --extras: only the extra AddOns folders, not the main game)
python tools/sv.py import      # the dev addon's capture screenshots -> stitched spots -> build/packs, then install
python tools/sv.py watch       # the same on every /reload
python tools/sv.py pull [--from //PC/agps-work] [--watch 10]  # harvested spots from the capture PC's share (LAN)
python tools/sv.py pull-media  # the CurseForge/wiki media the capture PC took -> ..\StreetView-media (Dev's docs/media-automation.md)
python tools/sv.py release     # dry run: build, zip and check the addon with its pictures (--publish: the GitHub release, then CurseForge)
python tools/sv.py build       # rebuild the pictures and print the size
python tools/sv.py media       # regenerate Media/ (Figure.tga, Probe.jpg)
python -m pytest tests -q
```

After install: `/reload` for changed Lua; **new files (images included) need a full game
restart**. AzerothGPS itself installs with `agps install-addon` from its own repo.

Every install also goes into each AddOns folder listed in `%USERPROFILE%\.agps-installs` (shared with
AzerothGPS's `install-addon`; a second test install, say), so one update reaches all of them. The dev addon
never moves the camera or the character (a test scans it). `sv.cmd compare --name N --render ID --grabs
<folder>` stitches window grabs of the game apart from the master and puts both into the dev addon's Compare
(build/compare, laid in by `install --dev`).

## Commits

Commit and push completed work to origin (the private repo), short imperative messages.

## Docs and the wiki

- `docs/curseforge.md`: the CurseForge page (settings and description); `CHANGELOG.md` has the release notes.
- `docs/wiki/`: the GitHub wiki's pages (`Home.md`, `_Sidebar.md`...), the source: edit here, then copy them into
  the wiki's own repo, `AzerothGPS-StreetView.wiki.git` (checked out next to this one, made 2026-10-02), commit as
  AzerothGPS and push. Its `images/` holds the logos and the GIFs (from the media folder; GIFs can't go through
  issue uploads); screenshots are issue #1 uploads (`docs/media-links.json`). The repo is public since 2026-10-02.

