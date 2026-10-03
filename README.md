<p align="center">
  <img src="assets/logo.png" alt="AGPS StreetView logo" width="320">
</p>

# AzerothGPS StreetView

[![Release build](https://github.com/AzerothGPS/AzerothGPS-StreetView/actions/workflows/release.yml/badge.svg)](https://github.com/AzerothGPS/AzerothGPS-StreetView/actions/workflows/release.yml)
![WoW Forever 1.60.1](https://img.shields.io/badge/WoW%20Forever-1.60.1-1f6feb)
![Interface 16001](https://img.shields.io/badge/interface-16001-555555)
![Lua 5.1](https://img.shields.io/badge/Lua-5.1-2C2D72?logo=lua&logoColor=white)
[![Needs AzerothGPS](https://img.shields.io/badge/needs-AzerothGPS-6f42c1)](https://github.com/AzerothGPS/AzerothGPS)

A companion addon for [AzerothGPS](https://github.com/AzerothGPS/AzerothGPS) on World of
Warcraft: Forever. Drag the little figure off the AzerothGPS map: the road network lights up,
the road under the pointer brightest, with the street views as dots. Drop it and the nearest
view opens in its own window, where you can look around and walk ahead. The spot and the
direction you look show on the map.

<p align="center"><img src="https://github.com/user-attachments/assets/a488152a-0bad-467f-83fc-bc0218abcb0c" alt="Booty Bay at dusk in the street view" width="820"></p>

Street views cover the open world of the Eastern Kingdoms, Kalimdor and Zephras Isle, a spot about
every 200 yards along the roads (over 1,600 in all), plus the capitals' streets and halls (Stormwind,
Orgrimmar, Ironforge, Darnassus, Thunder Bluff, the Undercity) and a few dozen famous spots, and they
all ship inside the addon. In a dungeon, Shift-click a boss on its map (AzerothGPS 1.1 or newer) to see
him standing in his room. (A copy without the pictures, such as GitHub's source code, says so and points
to the CurseForge download.)

<p align="center">
  <img src="https://raw.githubusercontent.com/wiki/AzerothGPS/AzerothGPS-StreetView/images/sv-drag-open.gif" alt="Dragging the figure onto a road opens its street view" width="400">
  <img src="https://raw.githubusercontent.com/wiki/AzerothGPS/AzerothGPS-StreetView/images/dungeon-boss-shift-click.gif" alt="Shift-click a boss on a dungeon's map for his street view" width="400">
</p>

Status: 1.0.0 in preparation (CurseForge release planned). More: the [wiki](https://github.com/AzerothGPS/AzerothGPS-StreetView/wiki).

## Where in the Azeroth?

<p align="center">
  <img src="assets/where-in-the-azeroth.png" alt="Where in the Azeroth? logo" width="420">
</p>

A GeoGuessr-style game on the AzerothGPS map, from the button above the figure. A street view pops
up with no zone name or coordinates; look around, then double-click the map where you think it
is. When the time is up the answer shows on the map with a dotted line from your guess, and the
closer you were, the more points you get.

<p align="center"><img src="https://raw.githubusercontent.com/wiki/AzerothGPS/AzerothGPS-StreetView/images/game-round.gif" alt="A round of Where in the Azeroth?" width="640"></p>

- **Modes:** Solo (by yourself, or Against Bots: four opponents named after famous characters of
  Classic Azeroth, played inside your own game) and Link: the game's link goes into your chat box for
  your party, raid, a whisper to your target, say, guild or a numbered channel; you send it, and whoever
  clicks it joins (it shows the level and rounds first), up to 10 players on your realm and faction.
  Nothing is sent without you, and there are no popups.
- **Rounds:** 1, 3 or 5. Each street view shows for 30 seconds, its top-right corner showing the level,
  the round, the time left, what the round is worth and the player list (- folds it to the time left); the
  guess placed when the time runs out counts (double-click again to move it). 10 seconds between
  rounds, counted down under the title.
- **Levels:** the host or solo player picks Normal (the terrain map), Heroic (the world map, every
  zone revealed) or Mythic (the world map with nothing revealed); every player's map is locked to it
  for the game (AzerothGPS 1.1 or newer).
- **Lobby:** a multiplayer game starts 30 seconds after the host starts it, counted down for every
  player whenever they joined; the host can start sooner.
- **Scoring:** a round is worth 100 points at a spot by a town, flight master, named place or
  landmark, and up to 200 far from any of them (the panel says what it's worth). The points fall with
  the distance: all of it within 25 yards, 92% at 200, 78% at 500, 58% at 1,000, 30% at 2,000, 7% at
  4,000, nothing on another continent. Players with the same points are told apart by who was closer,
  shown with decimals (for example 99.8 and 99.6).
- **Scoreboard:** five players at a time, the mouse wheel scrolls the rest, and your own row stays
  pinned under them. The others show "guessed" as soon as they place a guess; their points stay
  hidden until the round's result. Hover a player's marker on the map for their name and scores.
- **Fair play:** only open-world and city spots are used (never dungeons or caves), and only spots
  from map packs every player has. During a game the map hides your route, dungeons and transports,
  and your view comes back as it was when the game ends. Scoring 75% or more of what the rounds were
  worth earns a celebration.

<p align="center"><img src="https://github.com/user-attachments/assets/cacff4cd-8867-4aa7-aca1-963a21cd0a6a" alt="Everyone's guesses on the map after a round" width="820"></p>

Players' games talk only through the addon's own messages (prefix `AGPSSV`); you join a game only by
clicking its link. Players are named as the game shows them: WoW Forever's first and last names.

## Layout

- `addon/AzerothGPS_StreetView/`: the addon (needs AzerothGPS with its public API, `docs/api.md`
  in that repo).
  - `Data.lua`: the installed views and the view maths (tested under lupa).
  - `Viewer.lua`: the street view window.
  - `Figure.lua`: the figure on the map, the road highlight and the view marker.
  - `Game.lua`: Where in the Azeroth? (the rules and messages under lupa in `tests/test_game.py`, random
    games in `tests/fuzz_game.py`).
  - `Core.lua`: settings and `/sv` commands.
  - `Media/`: our own art, made by `tools/sv.py media`: `Figure.tga` (64x64, from
    `assets/figure.png`: the map's drag figure), `Logo.tga` (128x128, from `assets/logo.png`:
    the addon icon and the viewer's portrait) and the JPEG test card.
- `assets/`: the full-size art: `logo.png` (also for the CurseForge page), `figure.png`, the game's
  `where-in-the-azeroth.png` and the orc guess animations.
- `docs/`: `curseforge.md` (the CurseForge page's description) and `wiki/` (the GitHub wiki's pages).
- The developer tools are in the private repo AzerothGPS/AzerothGPS-StreetView-Dev (clone it next
  to this one): one addon with the manual capture tool for example views on your own client
  (it never moves the character or the camera: you turn and press the game's own Set View keys,
  and it hides names and takes one screenshot per key press), `/sv demo` (a game against bots) and
  Report picture. Never shipped; installed with `sv.cmd install --dev`. The pictures are rendered
  offline (wow.export and Blender, reading the client's files) by the separate private repo
  AzerothGPS/streetview-harvester.
- `tools/sv.py`: install the addons; import manual captures (`import`) or points exported by
  the harvester on the capture PC (`import-harvest <folder>`) into the pictures.
- `packs.json`: how the pictures ship (inside the viewer: continents, tile sizes, spacing, the
  CurseForge project, the size budget).
- `build/` (git-ignored): `master/<id>/` each spot's tiles at full resolution,
  `packs/AzerothGPS_StreetView/` the shipped pictures and their `Index.lua`, laid over the
  viewer's code (whose `Index.lua` in git is an empty stub) by `install` and `release`.
- `tests/`: `python -m pytest tests -q`.

## Taking example views on your own PC (manual)

1. `sv.cmd install --dev` (needs the AzerothGPS-StreetView-Dev checkout), then restart the game completely.
2. One time, in first person (mouse wheel all the way in), turning with the right mouse
   button: look level and type `/svcap save level`, look up about 50 degrees and
   `/svcap save up`, down about 50 degrees and `/svcap save down`, straight up and
   `/svcap save zenith`. (Steep up and down views leave no gaps above and below in the
   panorama; the stitch measures the real angles, so they needn't be exact.)
3. Bind the game's own Set View 2 to Set View 5 keys (Key Bindings > Camera) and the addon's
   "Capture a street view shot" key (Key Bindings > AddOns).
4. Stand on a road, not mounted, no target, and press the capture key. A guide at the top of
   the screen says which way to turn (right mouse button) and which Set View key to press;
   press the capture key for each of the 28 shots (8 directions at level, up and down, then
   straight up and straight down twice each, 90 degrees apart). Take a step to cancel.
5. Repeat 50 to 100 yards apart, then `/reload` so the game saves the list.
   With `sv.cmd watch` running, the import below happens by itself on every `/reload`.
6. `sv.cmd import` builds the pictures, stitches each new spot into a 360-degree panorama
   (about 40 seconds a spot; `sv.cmd stitch --force` redoes them), and installs it (not the
   capture tool). Restart the game (new files).
7. Drag the figure from the map onto the road. Drag the picture to look around, the mouse
   wheel zooms. White arrows on the ground point along the roads and toward nearby street views
   (hidden while you drag); click one to go that way.

`sv.cmd` in this folder runs `tools/sv.py` with the AzerothGPS venv's Python (it has Pillow
and lupa). It works from any folder in PowerShell or Command Prompt when called by its full
path, for example `C:\Users\<you>\OneDrive\Documents\Claude\AzerothGPS-StreetView\sv.cmd import`.

## Releases

One addon on CurseForge: the viewer's code and every picture together.

1. Bump `## Version` in the viewer's toc, add a `## <version>` section to `CHANGELOG.md`, commit and push.
2. `sv.cmd release --publish` builds the pictures, lays them over the code in one zip, checks it (under
   the budget, only addon files, one toc, nothing personal) and makes the GitHub release `v<version>`
   with it; its workflow (`.github/workflows/release.yml`) uploads the zip to CurseForge, requiring
   AzerothGPS. Without `--publish` it's a dry run; `--upload` sends it from this PC instead
   (`CF_API_TOKEN` set). Releases are logged in `data-releases.jsonl`.

The zip must stay under CurseForge's 2 GB limit (budget 1.8 GB): shipping a spot every ~200 yards
puts every continent at about 0.85 GB. Every build prints the size and its projection to all
planned spots. HD pictures are not made for now; the master tiles keep full resolution so they
can be later.
