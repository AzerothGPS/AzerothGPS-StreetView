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
- `tools/AGPS_Capture/`: developer addon that takes the 26 views of a spot on your own client.
  Never shipped.
- `tools/sv.py`: install the addons, import captured screenshots into the data pack.
- `build/`: the generated `AzerothGPS_StreetView_Data` pack (git-ignored).
- `tests/`: `python -m pytest tests -q`.

## Taking example views on your own PC

1. `python tools/sv.py install`, then restart the game completely.
2. In game, one time, in first person (mouse wheel all the way in), turning with the right
   mouse button: look level and type `/svcap save level`, look up about 45 degrees and
   `/svcap save up`, down about 45 degrees and `/svcap save down`, straight up and
   `/svcap save zenith`.
3. Bind a key under Key Bindings > AddOns, or use `/svcap go`. Stand on a road, not mounted,
   with no target, and press it. Keep still for about 35 seconds.
4. Repeat along a road, 50 to 100 yards apart. Then log out or `/reload` so the game saves
   the capture list.
5. `python tools/sv.py import` builds the pack and installs it. Restart the game (new files).
6. Drag the figure from the map onto the road.

Run the tools with the AzerothGPS venv's Python (it has Pillow and lupa).
