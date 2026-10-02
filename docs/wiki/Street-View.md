# Street View

## Opening one

![Dragging the figure onto a road](images/sv-drag-open.gif)

- **Drag the figure** off the AzerothGPS map onto a road. While you drag, the road network lights up
  (brightest under your pointer) and the street views show as dots. Let go and the nearest one opens.
- **Click the figure**, or type `/sv here`, to see the street view nearest you.
- Know its id? `/sv open <id>` opens it straight away (`/sv list` lists them all).
- **In a dungeon,** Shift-click a boss on its map to see him standing in his room (with AzerothGPS 1.1.0 or
  later; the top of the map says so when it works). Dragging the figure onto a dungeon's map works too.

## Looking around

![Walking a road with the arrows](images/sv-walk.gif)

- **Drag the picture** to look around. The scenery follows your pointer, up and down too.
- **The mouse wheel** zooms in and out.
- **The white arrows** on the ground point along the roads to the next street views. Click one to walk
  that way. They hide while you're dragging so they don't get in the way.
- The window's title tells you the zone and the map coordinates. Drag the title bar to move the window,
  drag the corner to resize it, and press Escape to close it.

## On the map

![The map beside a street view](https://github.com/user-attachments/assets/36d6fbc7-b4b3-44e6-855a-c3936359c79f)

While a street view is open, the AzerothGPS map shows where you're standing and which way you're looking,
and keeps up as you turn or walk. Walk with the arrows and the map moves along with you, centered on each
spot. Close the street view and the map goes back to where it was before your first step. If you move the
map yourself along the way, it stays where you put it.

![A dungeon's map: Shift-click a boss](https://github.com/user-attachments/assets/ec45b38f-a83c-434c-9190-b7520e50bbbf)

![Taragaman the Hungerer's street view](https://github.com/user-attachments/assets/be3221ea-86f3-4d11-832a-52071c88e70d)

## Good to know

- Every picture is a full 360-degree panorama rendered from the game world: about one every 200 yards
  along the roads, the streets of the cities and inside their buildings, a few dozen famous spots framed by
  hand, and the first dungeon boss.
- Left and right look swapped on your client? `/sv flipyaw` turns the views the other way.
