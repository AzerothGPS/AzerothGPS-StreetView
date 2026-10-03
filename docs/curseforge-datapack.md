# CurseForge page: AzerothGPS StreetView DataPack

The pictures' own project (the user, 2026-10-03: split from the viewer so a code update doesn't download them
again). Its files are made by `sv.cmd release-data --publish` (the GitHub release `data-v<YYYY.MM.DD>`, uploaded
by the release workflow to `packs.json` `data.curseforge_project`). Same voice as the viewer's page. The project
is **unlisted** (the user, 2026-10-03): not in search or on the profile, but reachable by its link and usable as a
dependency; StreetView's project requires it (Default Relations).

## Project settings

- **Name:** AzerothGPS StreetView DataPack (project 1724916)
- **Summary** (up to 255 characters): The street view pictures for AzerothGPS StreetView: over 1,800
  panoramas of Azeroth's roads, cities and dungeon bosses. Needs AzerothGPS StreetView.
- **Game:** World of Warcraft, the WoW Forever (Classic 1.60) flavor
- **Categories:** Map & Minimap
- **Relations:** none needed (StreetView's project requires this one); **Visibility:** unlisted
- **License:** All Rights Reserved
- **Avatar:** `assets/logo.png`
- **Links:** Issues: https://github.com/AzerothGPS/AzerothGPS-StreetView/issues · Wiki:
  https://github.com/AzerothGPS/AzerothGPS-StreetView/wiki · Source: https://github.com/AzerothGPS/AzerothGPS-StreetView ·
  Discord: https://discord.gg/gktYHzs2c
- **Its page in the game:** the viewer's "Street View Pictures Missing" notice shows
  https://www.curseforge.com/projects/<id> (Core.lua `ns.DATAPACK_URL`; a test keeps it in step with packs.json
  `data.curseforge_project`).

---

## Description

<p align="center"><img src="https://raw.githubusercontent.com/AzerothGPS/AzerothGPS-StreetView/main/assets/logo.png" alt="AzerothGPS StreetView" width="300"></p>

**These are the pictures for [AzerothGPS StreetView](https://www.curseforge.com/wow/addons/azerothgps-streetview).**
Install both: StreetView is the viewer and the game, this is everything it shows.

### What's in it

- **Over 1,800 street views**, each a full 360-degree panorama: the roads of the Eastern Kingdoms, Kalimdor
  and Zephras Isle about every 200 yards, the streets and halls of the capitals, a few dozen famous spots,
  and every dungeon and raid boss in their room.
- **Wildlife** along the roads, the creatures that live there.

### Why a separate download?

The pictures are big (about 1.2 GB) and change only when new street views come out. Keeping them apart means
an update of StreetView itself is a quick download, and this one updates only when there's something new to
see.

### Installing

1. Install **AzerothGPS StreetView**: the CurseForge app brings this one and AzerothGPS along. (By hand:
   install all three.)
2. Restart the game completely (new pictures only load on a full start, not on a `/reload`).

Without this one, StreetView tells you where to get it when you try to look around, Shift-click a boss or play
Where in the Azeroth?.

Pictures of World of Warcraft (c) Blizzard Entertainment.
