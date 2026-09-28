# AzerothGPS StreetView

A companion addon for [AzerothGPS](https://github.com/AzerothGPS/AzerothGPS) on World of
Warcraft: Forever. Drag the little figure off the AzerothGPS map: the road network lights up,
the road under the pointer brightest, with the street views as dots. Drop it and the nearest
view opens in its own window, where you can look around and walk ahead. The spot and the
direction you look show on the map.

Later: a geo-guessing mini game with rounds, scores and multiplayer games (see `PLAN.md`).

Status: early development, private.

## Layout

- `addon/AzerothGPS_StreetView/`: the addon (needs AzerothGPS with its public API, `docs/api.md`
  in that repo).
  - `Data.lua`: the installed views and the view maths (tested under lupa).
  - `Viewer.lua`: the street view window.
  - `Figure.lua`: the figure on the map, the road highlight and the view marker.
  - `Core.lua`: settings and `/sv` commands.
  - `Media/`: our own art, made by `tools/sv.py media`.
- `tools/AGPS_Capture/`: manual developer addon for example views on your own client. It
  never moves the character or the camera: you turn and press the game's own Set View keys,
  and it hides names and takes one screenshot per key press. Never shipped, and only
  installed on request (`sv.py install --capture`). The automated capture for a private
  server lives in the separate private repo AzerothGPS/streetview-harvester.
- `tools/sv.py`: install the addons; import manual captures (`import`) or points exported by
  the harvester on the capture PC (`import-harvest <folder>`) into the data pack.
- `build/`: the generated `AzerothGPS_StreetView_Data` pack (git-ignored).
- `tests/`: `python -m pytest tests -q`.

## Taking example views on your own PC (manual)

1. `python tools/sv.py install --capture`, then restart the game completely.
2. One time, in first person (mouse wheel all the way in), turning with the right mouse
   button: look level and type `/svcap save level`, look up about 45 degrees and
   `/svcap save up`, down about 45 degrees and `/svcap save down`, straight up and
   `/svcap save zenith`.
3. Bind the game's own Set View 2 to Set View 5 keys (Key Bindings > Camera) and the addon's
   "Capture a street view shot" key (Key Bindings > AddOns).
4. Stand on a road, not mounted, no target, and press the capture key. A guide at the top of
   the screen says which way to turn (right mouse button) and which Set View key to press;
   press the capture key for each of the 26 shots. Take a step to cancel.
5. Repeat 50 to 100 yards apart, then `/reload` so the game saves the list.
6. `python tools/sv.py import` builds the data pack and installs it (not the capture tool).
   Restart the game (new files).
7. Drag the figure from the map onto the road.

Run the tools with the AzerothGPS venv's Python (it has Pillow and lupa).
