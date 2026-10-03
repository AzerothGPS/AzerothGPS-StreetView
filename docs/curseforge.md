# CurseForge page: AzerothGPS StreetView

What goes on the CurseForge project page (Description, in CurseForge's Markdown editor), with the
project's settings. The images are links: screenshots uploaded to issue #1 (`docs/media-links.json` maps each
file to its link), GIFs from the wiki's `images/` folder, the logo from `assets/`. They open for everyone once
the repo is public. The voice is the same as AzerothGPS's page: talk to the player, keep it casual.

## Project settings

- **Name:** AzerothGPS StreetView
- **Summary** (the one-liner, up to 255 characters): Stand on any road in Azeroth and look around, then
  play Where in the Azeroth?, a GeoGuessr-style guessing game for up to 10 players.
- **Game:** World of Warcraft, the WoW Forever (Classic 1.60) flavor
- **Categories:** Map & Minimap (main), Minigames, Quests & Leveling
- **Required dependency:** AzerothGPS
- **License:** All Rights Reserved
- **Avatar:** `assets/logo.png`
- **AzerothGPS link** in the description: its GitHub page for now; swap in its CurseForge page once it has one.
- **Links:** Issues: https://github.com/AzerothGPS/AzerothGPS-StreetView/issues · Wiki:
  https://github.com/AzerothGPS/AzerothGPS-StreetView/wiki · Source: https://github.com/AzerothGPS/AzerothGPS-StreetView ·
  Discord: https://discord.gg/gktYHzs2c

---

## Description

**Ever wanted to stand on a road in Azeroth and just look around?** AzerothGPS StreetView adds
street-level views to the [AzerothGPS](https://github.com/AzerothGPS/AzerothGPS) map. Drag the little
figure off the map onto a road and a full 360-degree view of that exact spot pops up. Look around, look
up, zoom in, and follow the arrows on the ground to walk down the road.

<p align="center"><img src="https://raw.githubusercontent.com/wiki/AzerothGPS/AzerothGPS-StreetView/images/sv-drag-open.gif" alt="Dragging the figure onto a road opens its street view" width="640"></p>

### Go take a look

- **Over 1,600 street views** along the roads of the Eastern Kingdoms, Kalimdor and Zephras Isle,
  roughly one every 200 yards.
- **The cities too:** walk the streets of Stormwind, Orgrimmar, Darnassus and Thunder Bluff, wander the
  Undercity's halls and canals, and head down into Ironforge.
- **Step inside:** Stormwind Keep and the Cathedral, the inns, Thunder Bluff's tents, Orgrimmar's halls and
  Ironforge's great underground city, all lit the way they glow in the game.
- **Famous spots, picked by hand:** Booty Bay, Gadgetzan, Lakeshire, the Crossroads, Light's Hope Chapel
  and a few dozen more, each one framed so you know it the second it opens.
- **Look anywhere:** drag the picture around, and the mouse wheel zooms.
- **Walk the roads:** click the white arrows on the ground to hop to the next spot.
- **The map follows along:** AzerothGPS shows where you're standing and which way you're looking.
- **Nothing else to download:** every picture ships inside the addon.

<p align="center"><img src="https://github.com/user-attachments/assets/a488152a-0bad-467f-83fc-bc0218abcb0c" alt="Booty Bay at dusk in the street view" width="820"></p>

---

<p align="center"><img src="https://raw.githubusercontent.com/AzerothGPS/AzerothGPS-StreetView/main/assets/where-in-the-azeroth-300.png" alt="Where in the Azeroth?" width="260"></p>

### Where in the Azeroth?

Think GeoGuessr, but for Azeroth. You get dropped into a street view with no zone name and no
coordinates. Look around, work out where you are, and double-click the map. The closer your guess, the
more points you score.

<p align="center"><img src="https://raw.githubusercontent.com/wiki/AzerothGPS/AzerothGPS-StreetView/images/game-round.gif" alt="A round of Where in the Azeroth?" width="640"></p>

- **Play however you like:** on your own, against four bots named after Classic legends (Thrall, Jaina,
  Hogger, Leeroy...), or with others: the game's link drops into your chat box for your party, raid, a
  friend by whisper, guild or any channel, you hit Enter, and whoever clicks it joins. **Up to 10 players.**
- **Pick your difficulty:** Normal plays on the terrain map, Heroic on the world map with every zone
  revealed, and Mythic on the bare world map with nothing revealed at all. Everyone in the game gets the
  same one.
- **1, 3 or 5 rounds**, 30 seconds each.
- **The middle of nowhere pays more:** a spot near a town or landmark is worth 100 points, a lonely road
  out in the wilds up to 200. You get all of it within 25 yards and it drops off fast, so knowing the
  zone isn't enough. Closest guess wins a tie.
- **Everything's right on the picture:** the street view's corner shows the time left, what the round is
  worth and the live player list (who's guessed, never where). Want a clear view? Hit **-** and it
  shrinks down to just the timer.
- **A proper finish:** the winner's name rolls through the colors, and a really good game gets a glowing
  celebration.
- **Fair play:** the map hides your route, dungeons and boats while you play, and only street views every
  player has get used.
- **Safe to /reload:** the game picks up right where it left off and catches up on what everyone else
  did.

<p align="center"><img src="https://github.com/user-attachments/assets/cacff4cd-8867-4aa7-aca1-963a21cd0a6a" alt="Everyone's guesses on the map after a round" width="820"></p>

### Getting started

1. Install **AzerothGPS** and **AzerothGPS StreetView**, then restart the game.
2. Open the AzerothGPS map and drag the figure onto a road.
3. Feel like playing? Click **Where in the Azeroth?** above the figure.

Handy commands: `/sv here` (the street view nearest you), `/sv list`, `/sv hide`. The full rundown of
everything is on the **[wiki](https://github.com/AzerothGPS/AzerothGPS-StreetView/wiki)**.

### Help and feedback

- **Wiki:** how everything works, every command and what's covered, on the
  **[StreetView wiki](https://github.com/AzerothGPS/AzerothGPS-StreetView/wiki)**.
- **Discord:** questions, ideas and news on the **[AzerothGPS Discord](https://discord.gg/gktYHzs2c)**. Come hang out.
- **A picture looks broken?** Open an issue on [GitHub](https://github.com/AzerothGPS/AzerothGPS-StreetView/issues)
  or post in the Discord, with the zone and the coordinates from the street view's title bar.

### What's next

- **Dungeons, boss by boss:** Shift-click a boss on a dungeon's map and see him standing in his room.
  The first one, Taragaman the Hungerer in Ragefire Chasm, is already in (with AzerothGPS 1.1.0 or
  later; the top of the map tells you when it works). More bosses, entrances and the stairs between floors
  are on the way. They're in the viewer only, never in the game.
- **A few more spots:** the Great Forge and some of Darnassus' tree houses are getting a last bit of polish.

<p align="center"><img src="https://raw.githubusercontent.com/wiki/AzerothGPS/AzerothGPS-StreetView/images/dungeon-boss-shift-click.gif" alt="Shift-click a boss on a dungeon's map for his street view" width="640"></p>

### Notes

StreetView only shows you pictures. It never moves your character, presses keys or plays for you.
Players in a game only talk through the addon's own messages. Invites are links you send yourself (they go
into your chat box, like linking a map position), and you only ever join by clicking one, which tells you
the level and the rounds first. No popups.

_AzerothGPS StreetView is a fan-made addon and is not affiliated with or endorsed by Blizzard
Entertainment. World of Warcraft and Azeroth are trademarks of Blizzard Entertainment, Inc. Pictures of
World of Warcraft © Blizzard Entertainment._
