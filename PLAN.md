# AzerothGPS-StreetView project plan

Written 2026-09-28. This file is the brief for two Claude sessions:

- **LOCAL**: the main PC that has the AzerothGPS repo and the real WoW Forever beta client.
- **REMOTE**: the capture PC that runs a WoW Forever private server plus a client, teleports around the world, takes clean 360 degree screenshots, and sends them back to LOCAL.

**Status 2026-09-28:** the REMOTE tools (Parts 2 and 5: AGPS_Harvester, driver, stitcher, point generator) are built in the private repo AzerothGPS/streetview-harvester; start from its README. LOCAL imports its exports with `tools/sv.py import-harvest`.

**Distribution decided 2026-09-28:** 100-yard spacing; one standard (SD) pack per continent on CurseForge, each a required dependency of the viewer and under the 2 GB file limit (`packs.json`, README Releases); no HD packs for now. This supersedes Part 4.1 and 4.8's pack layout where they differ.

Sections are tagged LOCAL or REMOTE. REMOTE owns Part 2 and Part 6. LOCAL owns Parts 3, 4, 5. Both follow the interfaces in Part 1 and Part 7.

REMOTE: there is no guide to follow. A Reddit post exists that claims a personal WoW Forever server on 1.60.1, but it cannot be read from these sessions, so the server is planned from first principles in 2.1. The user's part on the capture PC is small and fixed: install Battle.net, sign in, download the WoW Forever beta client, sign out, leave. Everything after that is yours. Never open Battle.net, never sign in to anything, never type the user's credentials anywhere.

Be honest early: the beta client is weeks old and its network protocol (opcodes, packet layouts, the login flow) changes with every build. No public emulator may support it yet. 2.1 time boxes that research and defines two fallbacks that still deliver the screenshots. Report which track you are on before spending more than a day on it.

---

## 0. Ground truth (verified, do not rediscover)

### 0.1 AzerothGPS, the dependency

- Repo: https://github.com/AzerothGPS/AzerothGPS (public, All Rights Reserved, anonymous authorship "AzerothGPS"). Local checkout on LOCAL: `Documents\Claude\azerothgps`. Current release 1.0.6.
- Target client: **WoW Forever beta**, product `wow_classic_beta`, build **1.60.1.70009**, `## Interface: 16001`. Modern engine and API (C_Map, C_Timer, C_ChatInfo, FileDataIDs, atlases) on the Classic era world. Continents (instance/map IDs): **0** Eastern Kingdoms, **1** Kalimdor, **2991** Zephras Isle. Underground city levels use pseudo continents (Undercity = 10001, base 0).
- Coordinates: the addon stores world yards `(cont, x, y)` where **x points north and y points west**, in the order `UnitPosition` returns them. That is the same axis convention MaNGOS, Trinity and AzerothCore style servers print in `.gps` (X north, Y west), so an AzerothGPS point should feed `.go xyz X Y [Z] [map]` without swapping. Confirm once with the calibration in 2.7 before trusting it.
- Map coordinates `(uiMapID, u, v)`, u east, v south, 0 to 1, converted through `ns.Maps[id].bounds = {minX, minY, maxX, maxY}`:
  `u = (maxY - y) / (maxY - minY)`, `v = (maxX - x) / (maxX - minX)`, and the inverse. Python mirror: `app/azerothgps/routing/coords.py`. Full write up: `docs/coordinates.md`.
- Road network: `addon/AzerothGPS/Data/Roads.lua`, `ns.Roads[cont] = { n = {x1,y1,x2,y2,...}, e = { {a, b, len, src, x,y, x,y, ...}, ... } }`. Nodes are a flat 1 based array in world yards. Each edge polyline runs from node a to node b. Kalimdor has about 1700 edges, Eastern Kingdoms about 750, Zephras Isle about 80. POIs are in `Data/Pois.lua` as `{kind, x, y, name, id, faction, level?}`. Terrain grids (`Data/Terrain.lua`, cells 0 open, 1 water, 2 blocked) tell which points are in water.
- **There is no public API yet.** Everything lives in the private namespace `ns`. The pieces StreetView needs are `ns.Geo` (PlayerWorld, Facing, MapCont, Base), `ns.GPS.LocateWorld(cont, x, y)` (world to uiMapID + 0..1), `ns.Layers.MapToWorld`, `ns.Nav` (stops, route, Status, StepsText, Version), `ns.Turns` (Maneuvers, Path, Target). Part 3 adds the export.
- Route information UI: the unnamed `navPanel` child at the top of `AzerothGPSFrame` (GPSFrame.lua around lines 3280 to 3369) with `navText` and `stepsText`, a close X, a collapse toggle and a "+" for all steps. The direction arrow window `AzerothGPSArrow` (Arrow.lua) is the only existing pop out style window. There is no panel registration or plugin mechanism.
- Addon messaging already in use: prefix `"AzerothGPS"`, `C_ChatInfo.SendAddonMessage`, listened on WHISPER, PARTY, RAID, INSTANCE_CHAT, tab separated fields, sender's own messages ignored, incoming data validated and shown in a StaticPopup before use. No LibStub, no AceComm. `SetItemRef` is hooked for Blizzard `worldmap:` links; no custom `|H` links yet.
- Shipped media: uncompressed 32 bit TGA, power of two, referenced without extension. From CLAUDE.md: new files need a full game restart, changed images usually too. Some old Blizzard button art is missing on this client; wrap modern templates in `pcall` with fallbacks.
- Known client quirks: `GetUnitSpeed` and some C_Minimap values are secret in combat (`issecretvalue`, use `ns.IsSecret`), UI scale cannot be changed (effective scale 0.64), Undercity reports z = 0 and `IsIndoors() = false`, `C_TaxiMap` has no known/unknown state until `TAXIMAP_OPENED`, `GetSpellInfo` is unreliable.
- Tooling: `agps.cmd` runs the venv at `%USERPROFILE%\.venvs\azerothgps`. `agps gen-addon-data` writes `Data/*.lua`; `agps install-addon` copies into `C:\Program Files (x86)\World of Warcraft\_classic_beta_\Interface\AddOns\AzerothGPS` (addon name hard coded, needs a parameter for the new addons); `agps probes` reads `AzerothGPSDB.probes`; `agps watch-roads` must keep running during sessions. Pure Lua is tested with lupa in `app/tests/test_addon_lua.py`; `test_toc_lists_every_file` requires every addon file to be in the toc.
- Release: a `v*` tag triggers `.github/workflows/release.yml` (tag must match the toc version, the CHANGELOG section becomes the notes, zip, GitHub release, CurseForge upload to project 1712208). Tag only when the user asks. This workflow zips the addon from the repo, so it can never carry the StreetView image packs (see 4.8).

### 0.2 Verified client API facts for this plan

- Custom textures may be **BLP, TGA, PNG or JPEG**; dimensions must be **powers of two** (not necessarily square, 1024x512 is fine). PNG paths must include the `.png` extension in `SetTexture`. Source: warcraft.wiki.gg pages TextureBase:SetTexture, BLP files, TGA files.
- **Shipped StreetView images are JPEG, not PNG.** Measured on WoW map art (three 2048x1024 crops of the Durotar art, Pillow, 2026-09-28): a 1024x512 image is about 934 KB as PNG and 144 KB as JPEG quality 85 (105 KB at quality 75); a 2048x1024 panorama is about 2.9 MB as PNG and 428 KB as JPEG quality 85. PNG would put the preview tier alone at about 3.7 GB per continent, over CurseForge's 2 GB per file limit. JPEG loading is documented but **not yet verified on the 1.60 client**: milestone 0 in Part 7 runs that probe first. If JPEG fails, fall back to BLP with DXT1 compression (fixed 341 KB per 1024x512 with mipmaps), never PNG. Raw captures and intermediate files stay PNG (lossless) and are never shipped.
- `SaveView(2..5)` / `SetView(1..5)`: view 1 is always first person, views 2 to 5 are saved camera positions that persist across sessions. `FlipCameraYaw(degrees)` rotates the camera around the vertical axis. `MoveViewUpStart/Stop`, `MoveViewDownStart/Stop`, `CameraZoomIn/Out` exist. `Screenshot()` exists.
- `SendChatMessage` to SAY or YELL in the open world needs a hardware event on modern clients. Code that runs inside a key binding handler counts as a hardware event, which the harvester relies on (2.3).

### 0.3 Non negotiables (from the AzerothGPS rules)

1. The public addons (`AzerothGPS`, `AzerothGPS_StreetView`, the data packs) stay **display and communication only**. No automation, no protected calls, no executing data received from other players. Everything in Part 2 (harvester) is private server tooling and is **never** installed on the Blizzard client and never shipped.
2. No Blizzard files shipped. Screenshots of the game world are a **gray area**: they are derivative of Blizzard art. Blizzard's Fan Content Policy allows non commercial use of screenshots; the addon policy requires free, readable addons. Ship them, but keep the data pack a separate addon so the core addons stay clean, credit Blizzard in the data pack README, and revisit before public release.
3. Nothing personal in any public repo or zip: no real names, emails, Windows user paths, account or character names, no IP addresses of the capture machine, no server credentials.
4. American spelling in all user facing text and docs.

---

## 1. Architecture

```
LOCAL (main PC)                                  REMOTE (capture PC)
------------------------------------            --------------------------------------------
azerothgps repo                                  private server (core from the reddit post)
  agps sv-points  ---- capture_points.json --->  WoW Forever client (separate install)
  receiver (HTTP, LAN/Tailscale) <--- uploads --  AGPS_Harvester addon  <-> driver.py
  agps sv-build  ---> AzerothGPS_StreetView_Data     (camera poses, GM teleports)   (keys, capture, QA)
                                                  stitch.py (reproject, tile, JPEG)
AzerothGPS (public API added)
AzerothGPS_StreetView (viewer, mini game, multiplayer)
AzerothGPS_StreetView_Data (preview JPEGs, all continents) + AzerothGPS_StreetView_HD_<cont> (optional)
```

| Id | Component | Owner | Repo |
|---|---|---|---|
| A | AzerothGPS public API and panel hooks | LOCAL | AzerothGPS/AzerothGPS |
| B | `AzerothGPS_StreetView` addon | LOCAL | AzerothGPS/AzerothGPS-StreetView (public) |
| C | `AzerothGPS_StreetView_Data` (preview tier, all continents) and optional `AzerothGPS_StreetView_HD_<cont>` packs | generated | **not in any git repo**; built on LOCAL and uploaded to CurseForge by `agps sv-release` (4.8) |
| D | `agps sv-points`, `agps sv-build`, `agps sv-receive` | LOCAL | AzerothGPS/AzerothGPS (tooling only, nothing shipped in the addon zip) |
| E | Harvester: `SERVER.md`, `AGPS_Harvester` addon, `driver.py`, `stitch.py` (Track 1) or `render.py` (Track 2) | REMOTE | **private** repo `AzerothGPS/streetview-harvester` (private server automation must not sit in the public repos) |
| F | `AGPS_Capture` manual capture addon and `agps sv-import-screenshots` (Track 3) | LOCAL | AzerothGPS/AzerothGPS tooling folder, not in the addon zip |

Data flow: LOCAL generates the capture list from the road network (Part 5) and sends it to REMOTE. REMOTE captures, stitches, tiles, and uploads finished images plus manifests (Part 6). LOCAL builds the data pack and tests the viewer on the real client. Raw shots are uploaded for the pilot batch and for retakes the user asks for; full runs upload processed images only.

---

## 2. REMOTE: capture rig

### 2.1 Handoff, then pick a track (REMOTE, first two days)

**What the user does on the capture PC before handing over** (tell them this list if anything is missing):

1. Windows 11, a GPU that runs WoW at max settings at 1920x1080, 100 GB free, Claude Code installed with this plan and `capture_points.json` copied over.
2. Install Battle.net, sign in, install the **WoW Forever beta** (product `wow_classic_beta`; the folder will be `...\World of Warcraft\_classic_beta_`). Let it finish and launch it once to the character screen so Config.wtf and the CASC cache exist. Log out, quit the game, sign out of Battle.net, quit Battle.net.
3. Leave the PC on with Claude Code open. From here on the user does nothing on this machine except approve installs.

**What you do first, in this order:**

1. Copy the client out of Battle.net's control: `robocopy "C:\Program Files (x86)\World of Warcraft\_classic_beta_" "D:\WoWForeverPS\_classic_beta_" /E /MT:16`, plus the sibling `Data` folder if the CASC storage lives beside it (check `.build.info` and where `Data\data\*.idx` are; copy the whole `World of Warcraft` folder if unsure). Record the build from `.build.info` (expect 1.60.1.70009 or newer). Never run the automation against the Battle.net managed copy, and never start Battle.net again.
2. Install tooling with winget (ask for approval once): Git, Python 3.12, CMake, Visual Studio 2022 Build Tools with C++, MariaDB or MySQL 8, 7-Zip, Blender 4.x (for Track 2), Node LTS (wow.export needs it only if built from source).
3. Time box **one day** of research for Track 1 and write the findings to `harvester/SERVER.md`:
   - GitHub code and repo search for `70009`, `1.60.1`, `wow_classic_beta`, `WowClassicB`, `Forever` together with `emulator`, `sandbox`, `worldserver`, `bnetserver`. Also check the branch lists of TrinityCore (master targets current retail; look for a classic era or forever branch), the Arctium WoW Launcher releases (it patches a running client so it accepts a custom server; check whether it recognizes the beta executable), and the AzerothCore and CMaNGOS org pages (they are 3.3.5 and 1.12 protocol, not usable directly).
   - Confirm what launching the copied client directly does with `SET portal "127.0.0.1"` in `WTF\Config.wtf` (it should reach a login screen and fail to connect, which proves the client runs without Battle.net).
   - The decision rule: Track 1 only if a core (or sandbox) explicitly supports this client build's login and world protocol today. "Close" builds do not count; opcodes shift per build and reversing them is out of scope. Otherwise go to Track 2 and say so.

**Track 1: private server (best output, least likely to exist).** A modern engine client needs: a Battle.net style login service (REST on 8081 plus TLS on 1119), a world server (8085), MariaDB, and data extracted from the client (db2, maps, vmaps, mmaps) with the core's own CASC extractors. Client side it needs the connection patch (Arctium launcher or the core's patcher) and `SET portal "127.0.0.1"`. Then, on the server console, create a local test account (generate the password, store it only in `harvester/.env`, never in chat or git) and set GM level 3, log in through the launcher, and record in `SERVER.md` which of these exist with exact syntax from `.help`: `.go xyz X Y [Z] [map]`, `.gps`, `.gm on`, `.gm visible off`, `.gm fly on`, `.modify morph <displayId>`, `.wchange <type> <grade>`, any set time command, `.unaura all`. Confirm commands typed into SAY are parsed (Trinity style cores hand any message starting with `.` to the command handler). Note whether creatures spawn: a bare core gives empty streets, which is acceptable for the first dataset, and note the map ids (expected 0, 1, 2991). Then continue with 2.2 to 2.7.

**Track 2: offline rendering from the client files (no server, fully automatic, ToS neutral).** See 2.8. Same capture list, same output format, same upload. The look is a render, not the game: no sky shader, approximate lighting and fog, no ground clutter, no creatures. Good enough for the mini game and for the viewer's first release, and the pipeline keeps working after the beta ends.

**Track 3: manual capture on the live client (LOCAL, pilot and ground truth).** See 2.9. The user rides to points on the real beta and presses one key per point; an addon does the 26 poses and screenshots. Allowed by the addon policy because movement stays with the player. Use it for the 100 point pilot now, regardless of which track REMOTE lands on, so the viewer work is not blocked.

### 2.2 Machine and client setup

1. Dedicated client copy for the private server, e.g. `D:\WoWForeverPS\_classic_beta_`. Never install `AGPS_Harvester` into the Blizzard managed install.
2. GM character: one race, kept for the whole project so eye height (the Street View camera height) is consistent. Suggested: Orc or Human. Level does not matter with `.gm on`.
3. Window: **windowed, borderless, fixed size**, render area a known size such as 1920x1080, Windows display scale 100%, no HDR. Exclusive fullscreen breaks desktop capture.
4. Graphics: Options, Graphics: quality slider 10, Render Scale 100%, anti aliasing at max (MSAA 8x if offered plus the post process AA), View Distance 10, Environment Detail 10, Ground Clutter 10, Texture Resolution High, Filtering 16x, Projected Textures on, Shadows Ultra, Liquid Detail Good, Sunshafts High, Particle Density Ultra, SSAO High, Depth Effects High, Outline Mode off. Then force the ones that matter with `/console` and check with `/dump GetCVar("farclip")`: `farclip` max, `horizonStart` max, `weatherDensity 0` (no rain or snow particles), `renderScale 1`, `groundEffectDensity` max, `groundEffectDist` max, `terrainLodDist` max. Names vary by build: run `/console cvarlist` and record what exists.
5. Clean scene cvars (set once, they persist in Config.wtf):
   - Nameplates off: `nameplateShowAll 0`, `nameplateShowEnemies 0`, `nameplateShowFriends 0`, `nameplateShowSelf 0`.
   - Names off: `UnitNameNPC 0`, `UnitNameFriendlyNPCName 0`, `UnitNameEnemyNPCName 0`, `UnitNameNonCombatCreatureName 0`, `UnitNameFriendlySpecialNPCName 0`, `UnitNameFriendlyPlayerName 0`, `UnitNameEnemyPlayerName 0`, `UnitNameOwn 0`, `UnitNamePlayerGuild 0`, `UnitNameGuildTitle 0`, `UnitNameHostleNPC 0` (check exact names with `cvarlist Unit`).
   - Bubbles and text off: `chatBubbles 0`, `chatBubblesParty 0`, `floatingCombatTextCombatDamage 0`, `scriptErrors 0`.
   - Camera: `cameraSmoothStyle 0`, `cameraViewBlendStyle 1` (instant view changes), `cameraYawMoveSpeed` and `cameraPitchMoveSpeed` at known values (record them), ActionCam off (`test_cameraDynamicPitch 0`, `test_cameraOverShoulder 0`, `test_cameraHeadMovementStrength 0`).
   - UI hidden during capture with Alt+Z. The addon does not hide UIParent itself; the beacon frame is parented to `WorldFrame` so it stays visible.
6. Server side per session: `.gm on` (no aggro, invulnerable), `.gm visible off`, clear weather with `.wchange` at grade 0, `.modify morph <invisible display id>` if the character shows in shots (the invisible trigger model is displayId 11686 on Classic data; verify on this core), no mount, no pet, `.unaura all`.
7. Time of day: Street View tolerates varied lighting, but the mini game looks better with consistent daylight. If the core has a set time command, use it; otherwise capture in in-game daytime windows and record the game time per point in the manifest so a later pass can retake night shots.

### 2.3 `AGPS_Harvester` addon (REMOTE only, Lua)

Files: `AGPS_Harvester.toc` (`## Interface: 16001`, `## SavedVariables: AGPSHarvesterDB`), `Bindings.xml`, `Points.lua` (generated from `capture_points.json`, see Part 5), `Core.lua`.

Key bindings (Bindings.xml, so a real key press is the hardware event that allows `SendChatMessage`):

| Binding | Key (driver presses) | Action |
|---|---|---|
| `AGPSH_GOTO` | F5 | Teleport to the current point: builds `.go xyz X Y Z MAP` (Z omitted when unknown so the server uses ground height) and sends it with `SendChatMessage(cmd, "SAY")`. State BUSY. |
| `AGPSH_POSE` | F6 | Advance to the next camera pose in the sequence and apply it. State READY after the settle delay. |
| `AGPSH_NEXT` | F7 | Advance the point index (walks the retake list when one is selected). |
| `AGPSH_RESET` | F8 | `SetView(1)` and clear the pose index. |

Chat commands (`/agpsh`) for the human or the driver: `/agpsh point <id>` (jump to a point id), `/agpsh list <name>` (select a capture list subset such as `durotar`), `/agpsh status`, `/agpsh calib` (print `UnitPosition` and the map position for 2.7).

Camera pose sequence (26 poses, all from one eye point):

- Pitch rings via saved views: **view 2 = level (0 degrees)**, **view 3 = up 45**, **view 4 = down 45**, **view 5 = straight up (zenith)**. The nadir uses `SetView(1)` then `MoveViewDownStart()` for 3 seconds, which hits the pitch clamp deterministically. Zoom for views 2 to 5 must be 0 (first person) or the minimum third person distance (`CameraZoomIn(50)` then `CameraZoomOut(0.5)`) so the camera stays at the head. Set the four views once by hand (mouse look to the pitch, then `/run SaveView(n)`); they persist across sessions and teleports. Phase R1 verifies they are repeatable.
- Yaw: for each ring, `SetView(k)` then `FlipCameraYaw(45 * i)` for i = 0..7. Zenith and nadir are captured once each. Order: level ring, up ring, down ring, zenith, nadir. Pose index 0..25, file name `y{yaw:03d}_p{pitch:+03d}`.
- After each pose the addon waits `settle` (default 0.35 s, one full frame after the camera blend) and sets the beacon to READY.

State beacon: a `WorldFrame` child at the top left, a 16x16 px solid color square, plus a second 16x16 square to its right whose gray level encodes the pose index (value = 40 + 8 * index). Colors: red BUSY (teleporting or waiting for streaming), green READY (pose applied, frame settled), blue POINT_DONE, yellow ERROR (position mismatch after teleport or a loading screen still up), magenta LIST_DONE. The driver crops the top left 64x32 px out of every image.

Teleport readiness: after GOTO, poll `UnitPosition` every 0.1 s until it is within 2 yards of the target (for cross map teleports wait for `PLAYER_ENTERING_WORLD` first), then wait `stream` seconds (default 4, first visit to an area 8) for textures and models to stream in, then READY. If the position never matches within 15 s, ERROR; the driver logs it and moves on, and the point goes on the retake list.

Guard: in `PLAYER_LOGIN`, if `GetRealmName()` is not the private realm name stored in `AGPSHarvesterDB.realm`, disable every binding and print a warning. This addon must never act on a Blizzard realm.

### 2.4 `driver.py` (REMOTE, Python 3.12)

Dependencies: `dxcam` (DXGI desktop duplication, fall back to `mss`), `pydirectinput` (scan code key presses the game accepts), `pywin32` (find the WoW window, bring it to front, read its client rect), `numpy`, `Pillow`, `requests`.

Loop per capture point:

1. Read `capture_points.json` and `progress.jsonl`; skip points already `done`. Resume is a first class feature: each point's result is appended to `progress.jsonl` the moment it finishes.
2. Press F7 (NEXT) then F5 (GOTO). Poll the beacon at 10 Hz until green or yellow (timeout 30 s). On yellow log `teleport_failed` and continue.
3. For pose 0..25: press F6, wait for green with the expected gray index, grab the frame with dxcam, crop the beacon corner and a 24 px safety border, save `raw/<cont>/<point_id>/<pose_name>.png`. Reject a loading screen or a black frame (mean luminance and edge density thresholds) and retry the pose once.
4. When the beacon turns blue, run the quick QA (2.5 step 0) and write the point record to `progress.jsonl`: point id, cont, requested x/y/z, in game time, wall clock, client build, graphics preset hash.
5. Every N points (default 200) or on error: run `stitch.py` on finished points and upload (Part 6). Every 1500 points type `/reload` to keep the client's memory in check and re-verify the cvars.

Throughput budget: 26 poses x 0.5 s + teleport 5 s + streaming 4 s is roughly 25 s per point. 4000 points per continent is about 28 hours, so plan overnight batches with resume. Run Durotar and Orgrimmar first (the user plays Horde and validates there), then the rest of Kalimdor, then Eastern Kingdoms, then Zephras Isle.

Safety: the driver sends keys only when the WoW window is in the foreground with the expected title, stops on any exception, never retries a teleport more than twice, and halts after the current point when a `STOP` file appears in the working folder.

### 2.5 `stitch.py` (REMOTE)

0. QA per point: reject frames that are mostly one color, contain the loading screen, or have the underwater blur. Points with more than 2 rejected poses go on the retake list.
1. FOV calibration (once per window size): WoW keeps a fixed vertical FOV and widens horizontally on wide windows. Measure it: capture yaw 0 and yaw 10 at the same pitch, find a sharp landmark, measure its horizontal pixel shift, `focal_px = shift / tan(10 deg)`, `hfov = 2 * atan(width / 2 / focal_px)`. Store in `calibration.json`. Expect roughly 90 to 100 degrees horizontal at 16:9.
2. Reprojection: every pose is a pinhole render with a known yaw, pitch and focal length, so the equirectangular panorama is built analytically. For each output pixel compute the view direction, pick the pose whose forward axis is closest, project into that image, bilinear sample, and blend the two nearest poses by angular distance across the overlap. No feature matching. Output `pano_2048x1024.png` (lossless intermediate, not shipped).
3. Tiers and tiles (all powers of two, baseline JPEG, no alpha, no EXIF, sRGB, 4:2:0 chroma subsampling; quality set per tier in `tiers.json` so it can be tuned without code changes):
   - **preview**: one 1024x512 `preview.jpg` per point, quality 85, about 144 KB (mini game and quick look).
   - **hd**: 2048x1024 split into 8 tiles of 512x512, 4 columns by 2 rows (`hd/t{col}{row}.jpg`, t00 to t31), quality 80, about 400 KB per point in total, for the smooth Street View mode.
   - **views**: the 26 raw frames resized to 1024x512 (`v_y000_p+00.jpg` ...), quality 80, for the discrete viewer mode. About 3.5 MB per point, so **pilot and local testing only, never shipped**.
   - Upload the raw lossless PNGs only for the pilot and for retakes the user asks for.
   - `contact.jpg` (raw thumbnails in a strip) for human review, never shipped.
4. Write `meta.json` per point (Part 6).

The first viewer milestone (4.2) uses the discrete views and does not need stitching. Stitching lands after the pilot proves pose repeatability.

### 2.6 REMOTE phases and acceptance

| Phase | Deliverable | Acceptance |
|---|---|---|
| R0 Track decision | Client copied out of Battle.net's control, tooling installed, one day of Track 1 research, `SERVER.md` with the verdict | Track 1: a local account logs in, `.gps` prints coordinates, `.go xyz` moves the character, `.gm on` works. Track 2: one Durotar tile exported and rendered from a known point with landmarks in the right compass directions |
| R1 Rig prototype | Track 1: `AGPS_Harvester` + `driver.py` capture one point in Orgrimmar's Valley of Strength, 26 raw PNGs with the beacon handshake. Track 2: `render.py` renders the same point | Run the point three times: per pose pixel difference under 1 percent on a static scene, no UI, no nameplates, no character model, horizon level in view 2 |
| R2 Pilot | 100 points from the `durotar` and `orgrimmar` subsets, views + stitched preview + manifest uploaded to LOCAL | LOCAL loads them in the viewer on the real client; the user signs off on image quality and camera height |
| R3 Continent runs | Kalimdor, then Eastern Kingdoms, then Zephras Isle; retake pass; hd tiles | Under 3 percent of points still on the retake list after the retake pass |
| R4 Maintenance | Rerun subsets after client patches change art, regenerate points when roads change | Documented `--only <subset>` and `--retake <file>` flows |

### 2.7 Coordinate calibration (in R0, five minutes)

1. Stand somewhere distinctive (the Orgrimmar bank door). Run `.gps` and note X, Y, Z, map.
2. Run `/agpsh calib`, which prints `UnitPosition("player")` in the order the addon uses (x, y, instance) and `C_Map.GetPlayerMapPosition`.
3. They must match with no axis swap. Then `.go xyz <X> <Y>` with the AzerothGPS point for the same door from `capture_points.json` and confirm you land on it. Record the result in `SERVER.md`. If the server swaps axes, the fix goes in the addon's GOTO builder only, never in the point data.

### 2.8 Track 2: offline render pipeline (REMOTE fallback)

Goal: the same 26 pose images per capture point, produced by rendering the client's own map data, with no game process and no server.

1. **Export.** Use wow.export (Kruithne, open source, reads the CASC install directly; point it at `D:\WoWForeverPS`) to export the ADT tiles that contain capture points, with terrain, textures, WMOs, M2 doodads and liquid. Tiles are 533.33 yards; `tile_x = 32 - y / 533.33`, `tile_y = 32 - x / 533.33` in AzerothGPS world coordinates (see `docs/coordinates.md`). Export by zone subset, starting with Durotar and Orgrimmar. If wow.export's UI is the only way to drive it, use its Blender add-on and its export manifests, and script the tile selection from the point list; check first whether the current version has a command line or RPC mode. Fallback exporter: the AzerothGPS Python CASC/ADT reader in `app/` already parses ADT and WMO placement (see `docs/coordinates.md` interiors section); extending it to write glTF is possible but is a week of work, so prefer wow.export.
2. **Scene.** Blender 4.x headless (`blender -b scene.blend -P render.py -- --points batch.json`). Import the tiles with the wow.export Blender add-on once per zone and save a `.blend` per zone. Convert WoW axes to Blender: AzerothGPS x (north) and y (west) map to a right handed scene with north as +Y and east as +X, so Blender `(X, Y, Z) = (-y, x, z)`. Verify with two known landmarks before rendering anything. Lighting: a sun lamp at a fixed noon angle, a sky texture (Nishita) for the sky, world fog color and distance taken from the zone's Light.db2 entry if the DB2 reader can fetch it, otherwise a neutral warm daylight. EEVEE for speed; Cycles only if EEVEE artifacts are unacceptable.
3. **Camera.** Eye height 2.0 yards above the terrain sample at the point (match the in-game camera height measured in Track 3 if available). Render the 26 poses with a 90 degree horizontal FOV at 1024x1024 (poses then feed `stitch.py` with an exact FOV, no calibration), or render one equirectangular image directly with Cycles' panoramic camera at 2048x1024 and skip stitching. Prefer the equirect path when Cycles speed allows (target under 20 seconds per point on the GPU).
4. **Output.** Identical to Track 1: `preview.jpg` 1024x512, `hd/t00..t31.jpg`, `meta.json` with `"rig": "render-v1"`, uploaded through Part 6. The viewer does not care which track produced a point, but the data pack README states it.
5. **QA.** Render a contact sheet per zone and compare a handful of points against Track 3 screenshots of the same spots; adjust lighting and fog until the mini game feels fair (landmarks recognizable, colors close).

### 2.9 Track 3: manual capture on the live client (LOCAL, ToS compatible)

Addon `AGPS_Capture` (kept out of the public release, but it uses only public API and never moves the character, so it is fine to run on the real beta):

- One key binding, `AGPSC_CAPTURE`. On press: save the current nameplate and name cvars, set the clean scene cvars from 2.2 item 5, hide the UI, then run the 26 pose sequence from 2.3 with `Screenshot()` after each pose, spaced 1.1 seconds apart because screenshot files are named to the second. Restore the cvars and the UI at the end and print the point id it assumed (nearest capture point within 15 yards of the player from `Points.lua`, or the raw position if none).
- Before the session: `screenshotFormat tga` and `screenshotQuality 10`, windowed borderless at the same size REMOTE uses, graphics at max, first person or minimum zoom, mount dismissed, pet dismissed.
- After the session, `agps sv-import-screenshots --since <time>` on LOCAL groups the files in `Screenshots\` into points by their timestamps and the printed point ids, resizes them to the `views` tier, and drops them into `data/streetview/incoming/` like an upload. Then `agps sv-build` as usual.
- Cost: about 45 seconds per point including riding, so the 100 point Durotar and Orgrimmar pilot is an evening. It also produces the ground truth for camera height and colors that 2.8 calibrates against.

---

## 3. LOCAL: AzerothGPS changes (public API, small and safe)

Add in `Core.lua` after the modules initialize, and document in `docs/api.md`:

```lua
_G.AzerothGPS = {
  version = ns.VERSION,
  Geo = { PlayerWorld = ns.Geo.PlayerWorld, Facing = ns.Geo.Facing, MapCont = ns.Geo.MapCont, Base = ns.Geo.Base },
  LocateWorld = ns.GPS.LocateWorld,       -- cont, x, y  -> uiMapID, name, u, v
  MapToWorld  = ns.Layers.MapToWorld,     -- uiMapID, u, v -> x, y, cont
  Nav = { Stops = function() return ns.Nav.stops end, Route = function() return ns.Nav.route end,
          Version = ns.Nav.Version, Status = ns.Nav.Status, Steps = ns.Nav.Steps },
  Turns = { Maneuvers = ns.Turns.Maneuvers, Path = ns.Turns.Path },
  Roads = ns.Roads,                        -- read only by convention
  Pois = ns.Pois,
  RegisterCallback = ns.RegisterCallback,  -- "RouteChanged", "Redraw", "MapClick", "MapChanged"
  RegisterPanel = ns.GPS.RegisterPanel,
  AddPin = ns.GPS.AddPin, RemovePin = ns.GPS.RemovePin, DrawLine = ns.GPS.DrawLine,
  SetBrowse = ns.GPS.SetBrowse,            -- true: stop following the player, allow free pan and zoom
  MapToScreen = ns.GPS.MapToScreen,        -- for overlays drawn by other addons
}
```

- **Callbacks**: a small list per event, fired inside `pcall`. `RouteChanged` when `Nav.Version()` changes, `Redraw` after each `G.Update`, `MapClick(cont, x, y, button)` when the user clicks the canvas while a registered panel asked for clicks (never steal normal clicks), `MapChanged(uiMapID)`.
- **RegisterPanel(name, opts)**: lets another addon put a frame in the nav panel slot at the top of the map, where route information is shown. Opts: `frame`, `height`, `priority`, `popOut` (called when the user hits the pop out button). While a foreign panel is shown, the route texts stack below it or collapse (user setting). This is the hook the mini game uses to show round, timer and leader on the GPS window itself.
- **Pins and lines**: `AddPin(cont, x, y, {icon, color, label, onClick})` returns a handle; `DrawLine(cont, x1, y1, x2, y2, color)` for the guess to answer line. Both live in `keepLayer` and `lineLayer` and rotate with the map.
- **Coverage layer**: `ns.Layers` gets a generic dots layer type so StreetView can register its capture points as small blue dots that render only past a zoom threshold (the equivalent of Google's blue lines).
- `agps install-addon --name AzerothGPS_StreetView --src <path>` (and the data packs) so one installer serves every addon.
- Tests: a lupa test that `_G.AzerothGPS` exposes the documented keys and that callbacks fire on route change.
- Bump AzerothGPS to 1.1.0, CHANGELOG "Public API for companion addons". Nothing changes for players.

---

## 4. LOCAL: `AzerothGPS_StreetView` addon

`## Interface: 16001`, `## Dependencies: AzerothGPS`, `## OptionalDeps: AzerothGPS_StreetView_Data, AzerothGPS_StreetView_HD_0, AzerothGPS_StreetView_HD_1, AzerothGPS_StreetView_HD_2991`, `## SavedVariables: AzerothGPSStreetViewDB`. Files: `Core.lua`, `Data.lua` (registry of installed packs), `Viewer.lua`, `Coverage.lua`, `Game.lua`, `Sync.lua`, `Panel.lua`, `Options.lua`, `Config.lua`, `Media/`.

### 4.1 Data pack format (`AzerothGPS_StreetView_Data` and `AzerothGPS_StreetView_HD_<cont>`)

- `Index.lua`: `AzerothGPS_StreetViewData[<cont>] = { version = "2026.10.15", hash = "<sha1 of the point list>", tiers = {"preview"}, ext = "jpg", points = { [id] = { x, y, h, e, t, n = {id, id, ...} }, ... } }` where `h` is the road heading in degrees (0 north, counter clockwise like `GetPlayerFacing`), `e` the edge index, `t` the 0..1 position along it, `n` the neighbor point ids (previous and next along the road plus junction neighbors within 40 yards).
- Images: `Images/<cont>/<id>/preview.jpg` (1024x512) in the main data pack; `Images/<id>/hd/t00.jpg ... t31.jpg` (512x512 each) in the optional HD pack for that continent; `Images/<id>/v_y000_p+00.jpg` and so on only in local test packs. Paths always carry the extension, taken from the pack's `ext` field so a BLP fallback needs no viewer change.
- Two kinds of pack: `AzerothGPS_StreetView_Data` holds the preview tier for every continent in one addon (one CurseForge project); `AzerothGPS_StreetView_HD_<cont>` (one per continent, each its own CurseForge project) registers `AzerothGPS_StreetViewData[<cont>].hd = true` and adds the tiles. The viewer works with the main pack alone and uses HD tiles wherever an HD pack is installed.
- `Data.lua` in the main addon discovers packs after `ADDON_LOADED` and refuses a pack whose `version` is older than the viewer's minimum.
- Size budget: CurseForge rejects any file of 2 GB or more, so keep every zip under **1.8 GB** for headroom. Estimates at about 4000 points per continent, to be replaced by the real counts from `agps sv-points`:

  | Pack | Per point | Estimated zip |
  |---|---|---|
  | `AzerothGPS_StreetView_Data`, preview JPEG q85, all continents | 144 KB | about 1.2 GB |
  | `AzerothGPS_StreetView_HD_<cont>`, tiles JPEG q80 | about 400 KB | about 1.6 GB each |

  `agps sv-build` computes the real zip sizes and stops with an error when a pack would pass 1.8 GB, listing the levers in order: lower JPEG quality (to 75), then split the main pack into one pack per continent, then 100 yard spacing. Zip does not shrink JPEG, so the zip size is the sum of the files plus about 1 percent.
- Memory in game: textures load only when shown. The viewer caps its cache at 32 textures (a 1024x512 texture is about 2 MB of video memory, so about 64 MB at most). The Lua index costs well under 2 MB for all continents.

### 4.2 Viewer window

- Frame `AzerothGPSStreetView`, movable, resizable, 16:9, default 640x360, its own strata, position and size remembered like the arrow window. The title shows zone name and coordinates only outside game mode.
- **Discrete mode (milestone S1)**: one view image at a time, buttons and keys to turn left and right in 45 degree steps, look up, level, down, plus zenith and nadir. Crossfade 0.15 s between images.
- **Panorama mode (milestone S2, needs hd tiles)**: draws the 4x2 tile grid into a clipped canvas and pans it by yaw (wrapping) and pitch with drag or buttons, using the same tile cropping technique the GPS frame uses for map tiles. A compass strip at the bottom shows north and the road heading.
- Navigation between points: chevrons on the image at the neighbor headings; clicking moves to that neighbor and keeps the current yaw. Keyboard: arrows turn, W and S move along the road heading.
- "Show on map": pin on the GPS frame plus a view cone that rotates with the current yaw.
- Preloading: `SetTexture` on the neighbors and the current pitch ring into hidden textures so turning is instant, capped at 32 cached textures.

### 4.3 Map integration

- Coverage dots on the GPS frame through the coverage layer from Part 3, visible past a zoom threshold, blue, larger on hover.
- Click a dot (or shift click near a road) to open the nearest point in the viewer.
- Route peek: when a route exists, a Peek button shows the street view at the next maneuver, oriented toward the turn (yaw = maneuver heading). Next cycles through the maneuvers.
- `/sv here` opens the closest capture point to the player oriented to the player's facing. Useful for testing image alignment on the real client.

### 4.4 Mini game, single player (milestone S3)

Rules, configurable in Options and as `/sv game` arguments:

- Region: a zone (uiMapID), a continent, or everywhere with data. Point pool = points inside the region minus the last 50 played (stored in the DB).
- Rounds: default 5 (1 to 20). Seconds per round: default 60 (10 to 300). Peek: whether the player may turn and look around (default yes) and move to neighbors (default no).
- Round flow: the viewer shows the preview for a random point with the location hidden (title and coordinates hidden, coverage dots hidden, the GPS frame in browse mode zoomed out to the region). The countdown runs in the panel. The player clicks the map to place a guess pin and can move it until time runs out or they press Lock In. At round end the true location pin drops, a line is drawn to the guess, and the distance and percentage are shown.
- Scoring: `d` is the straight line distance in yards between guess and truth after `MapToWorld` on the guess's map; a guess on another continent scores 0. `pct = 100 * exp(-d / R)` with `R = 0.08 * diagonal(region)` in yards (zone diagonal for zone games, continent diagonal for continent games). Guesses within 25 yards score 100. One decimal. Total = sum of rounds; the panel shows total and average.
- A result panel per round and a final screen with per round rows. `/sv game again` reuses the settings.
- Nothing about the answer leaves the addon before the round ends: the point id lives in a local and is never written to the DB or chat until the reveal.

### 4.5 Multiplayer sync, chat link, scoreboard (milestone S4)

Transport: addon messages, prefix `AGPSSV`, on PARTY, RAID and INSTANCE_CHAT (grouped play) and GUILD, plus WHISPER for late joiners. Messages are tab separated, at most 240 bytes, version tagged, every field validated, never executed. Own messages are ignored, as in Import.lua.

Invite link: `|Hgarrmission:agpssv:<gameCode>|h[AzerothGPS StreetView game: click to join]|h` posted to the chosen channel through `SendChatMessage` from the user's button click. The `SetItemRef` hook recognizes `garrmission:agpssv:` and opens the join prompt. This is the custom link trick WeakAuras and ElvUI use; verify it on the 1.60 client with a probe first and keep the typed `/sv join <code>` fallback from day one.

Protocol (host authoritative, `GetServerTime()` for clocks):

| Msg | Fields | Notes |
|---|---|---|
| `H` hello | proto, addon version, pack versions per cont | sent on join |
| `G` game | code, host, region kind, region id, rounds, seconds, peek flags, pack hash | players with a different pack hash get a warning; the host excludes points they lack |
| `J` join, `L` leave | code, name | host keeps the roster |
| `R` round | code, n, point id, start server time | everyone starts the countdown from the same server time; the point id goes only over addon channels, never printed |
| `P` guess | code, n, cont, x, y, locked | sent on lock in or time out; others see "guessed" but not where until the reveal |
| `S` score | code, n, name, d, pct | host computes and broadcasts after all guesses or time out, batched 4 players per message |
| `F` final | code, rows | totals sorted; ties broken by lower total distance |

Scoreboard: a row per player with round scores, total and rank; the leader is highlighted and the panel shows "Leader: Name, 412.3". Late joiners get the standings by WHISPER from the host. Host migrates to the next roster member if the host leaves. Rate limit: at most one message per player per second in normal play.

### 4.6 Panel in the AzerothGPS window and pop out

Through `RegisterPanel`: a compact strip in the route information slot at the top of the GPS frame with round `n/N`, countdown, your score, the leader, and Lock In and Pop Out buttons. Pop Out opens the viewer window with a scoreboard tab. When the viewer is open the strip collapses to one line. Everything the strip shows is also in the viewer, so a player can play from either window. Setting: "Show game panel on the map" (default on).

### 4.7 Options and commands

`/sv` and `/streetview`: `show|hide|toggle`, `here`, `open <pointId>`, `peek`, `game [zone|continent|all] [rounds] [seconds]`, `host`, `join <code>`, `leave`, `board`, `coverage on|off`, `packs`, `debug`. Options page in the Settings category next to AzerothGPS.

### 4.8 Releasing the data packs (separate from the code release)

The images never go into git. GitHub blocks files over 100 MB, warns on repositories over 1 GB, and caps release assets at 2 GB, and the existing tag workflow zips straight from the repo. So:

- **Code** (`AzerothGPS_StreetView`) releases exactly like AzerothGPS: public repo, `v*` tag, `release.yml`, GitHub release plus CurseForge upload. It carries no images.
- **Data** is built and uploaded from LOCAL by a new command, `agps sv-release --pack <name> [--dry-run]`:
  1. Runs `agps sv-build` for that pack from `data/streetview/incoming/` into `data/streetview/dist/<pack>/`, then zips it (`<pack>-<version>.zip`, stored rather than deflated, since JPEG does not compress).
  2. Checks: every image is a power of two JPEG, every image `Index.lua` names exists and vice versa, the toc lists the Lua files, nothing in the zip besides the toc, `Index.lua`, `Images/` and the README, zip under 1.8 GB, and nothing personal in the zip (the same scan the code release uses).
  3. Uploads with the existing `.github/scripts/curseforge.py` logic, reused as a module, to that pack's CurseForge project id from `data/streetview/projects.json`, using the `CF_API_TOKEN` environment variable on LOCAL (never committed). `--dry-run` does everything except the upload.
  4. Records the upload (pack, version, CurseForge file id, size, point count, sha1 of the zip) in `data/streetview/releases.jsonl`, which is committed so the history is public without the images.
- **Versioning**: data packs use a date version (`2026.10.15`). The viewer's toc lists them as optional dependencies, and `Data.lua` warns in chat when a pack is older than the minimum the viewer needs.
- **CurseForge projects**: one project for the viewer, one for `AzerothGPS_StreetView_Data`, and one per HD pack. These are different content, not cosmetic variants, so separate projects fit the moderation policy. The data project descriptions say plainly that the images are screenshots of World of Warcraft (or renders from its files for Track 2 points), credit Blizzard Entertainment, and point to the viewer.
- **Moderation check before scale**: the first data upload is a small pack (the 100 point pilot, about 15 MB). Wait for CurseForge moderation to approve it before capturing whole continents. If it is rejected on copyright grounds, stop and bring the reason to the user; alternatives such as GitHub releases or Wago carry the same copyright question and are the user's decision.

---

## 5. LOCAL: capture list generation (`agps sv-points`)

Input: the road, POI, terrain and map bounds data through the Python generators (not by parsing Lua). Output: `data/streetview/capture_points.json` and `harvester/addon/AGPS_Harvester/Points.lua` for REMOTE.

Rules:

- Walk every edge polyline; place a point every `spacing` yards (default 75) starting at node a, plus every node. Snap to the polyline. Drop a point if another is within 30 yards (junction dedupe).
- Add POIs of kinds inn, flight master, bank, auction house, zeppelin and boat docks, and zone entrances, offset 5 yards along the nearest road so the camera is not inside the NPC.
- Skip city levels (pseudo continents), caves, capital interiors and any point whose terrain cell is water. Undercity and other interiors come later with explicit Z from `ns.CityHeights`.
- Stable ids: `f"{cont}-{round(x)}-{round(y)}"`. Re-running with the same roads keeps ids; new roads add ids; the harvester captures only ids missing from the manifest.
- Per point: `cont, x, y, z (null), heading` (direction of travel along the edge from a to b), `edge, t, neighbors, zone uiMapID, zone name`, plus `subsets` tags (`durotar`, `orgrimmar`, `kalimdor`, ...) for pilot selection.
- Print counts per zone and the estimated capture hours at 25 s per point so the user can adjust `spacing` before sending the list to REMOTE.

`agps sv-build --incoming data/streetview/incoming --out addon-data/` builds the data pack addons from the uploaded images and manifests, writes `Index.lua`, checks that every image is a power of two JPEG (or BLP if the probe forced the fallback), and reports the zip size per pack against the 1.8 GB budget. `--include-views` adds the views tier for local test packs only; `agps sv-release` refuses a pack built with it.

---

## 6. Transfer between machines

Receiver on LOCAL: `agps sv-receive --port 8765 --token <random>` (FastAPI or `http.server`, LAN only, or over Tailscale if REMOTE is off site). Endpoints: `POST /upload/<point_id>` (multipart: `meta.json` + JPEGs, plus raw PNGs for the pilot and retakes), `GET /status` (ids already received, so REMOTE skips them), `GET /retake` (ids LOCAL wants redone). Files land in `data/streetview/incoming/<cont>/<point_id>/`. The token lives in an environment variable on both machines, never in git.

Fallback when HTTP is awkward: a shared folder or Syncthing on `data/streetview/incoming` with the same layout.

Manifest record (`meta.json` per point, also appended to `manifest.jsonl` per batch):

```json
{"id": "1-1629--4373", "cont": 1, "x": 1629.4, "y": -4373.1, "z": 31.2, "heading": 270,
 "actual": {"x": 1629.4, "y": -4373.0, "z": 31.2}, "game_time": "12:40", "captured": "2026-10-02T03:14:00Z",
 "client_build": "1.60.1.70009", "rig": "v1", "fov_h": 96.5, "tiers": ["preview", "hd", "views"], "quality": {"preview": 85, "hd": 80, "views": 80},
 "files": {"preview.jpg": "sha1...", "hd/t00.jpg": "sha1...", "v_y000_p+00.jpg": "sha1..."},
 "qa": {"rejected_poses": [], "night": false}}
```

---

## 7. Milestones and order of work

| # | Where | Milestone | Depends on |
|---|---|---|---|
| 0 | LOCAL | JPEG probe on the 1.60 client: a throwaway addon with one 1024x512 and one 512x512 JPEG shown with `SetTexture("Interface\\AddOns\\<name>\\test.jpg")` after a full game restart; record the result in `AzerothGPSDB.probes`. If either fails, switch every tier to BLP DXT1 before anything else is built | none |
| 1 | LOCAL | Part 3 public API in AzerothGPS 1.1.0, `install-addon --name`, lupa tests | none |
| 2 | LOCAL | `agps sv-points`; send `capture_points.json`, `Points.lua` and the receiver URL and token to REMOTE | none |
| R0 | REMOTE | Client copy, tooling, Track 1 research, `SERVER.md` verdict, calibration 2.7 (Track 1) or axis check (Track 2) | user handoff (2.1) |
| L1 | LOCAL | Track 3 `AGPS_Capture` addon and `agps sv-import-screenshots`; the user captures the 100 point Durotar + Orgrimmar pilot on the real beta | 2 |
| R1 | REMOTE | Rig prototype and repeatability test on the chosen track | R0, 2 |
| 3 | LOCAL | S1 viewer in discrete mode with the Track 3 pilot pack | 1, L1 |
| R2 | REMOTE | Pilot: the same 100 points from REMOTE's track, uploaded, compared side by side with the Track 3 pack | R1, receiver |
| 4 | LOCAL | `agps sv-build`, pilot pack installed, coverage dots, click to open, route peek, `/sv here` | 3 |
| 5 | LOCAL | S3 single player mini game with panel and pop out | 4 |
| R3 | REMOTE | Continent runs with stitching and hd tiles, retake pass | R2 sign off |
| 6 | LOCAL | S2 panorama mode with hd tiles | R3 partial |
| 7 | LOCAL | S4 multiplayer sync, chat link, scoreboard, host migration; two client test with a second account or a guild mate | 5 |
| 7b | LOCAL | `agps sv-release`; upload the 100 point pilot as `AzerothGPS_StreetView_Data` and wait for CurseForge moderation (4.8) | 4, R2 |
| 8 | LOCAL | Packaging: viewer release, full preview data pack, HD packs per continent, CurseForge listings with Blizzard credit, ToS review | 6, 7, 7b approved, R3 |

Do not start a milestone until the previous one passed its in-game check on the real client (the AzerothGPS rule).

---

## 8. Risks and gray areas (flag, do not hide)

- **No emulator for the beta protocol**: the most likely outcome of the Track 1 research is "nothing supports this build". That is why Track 2 exists and why Track 3 runs now. Do not sink more than a day into Track 1 without a working login.
- **Private server with a Blizzard client**: the client EULA forbids it. This is the user's decision for the capture machine only; keep every trace (harvester addon, driver, server notes) out of the public repos and off the Blizzard install. Track 2 avoids the issue entirely; Track 3 is within the addon policy.
- **Shipping screenshots** in a public addon (0.3 item 2). Decide before milestone 8.
- **Data size**: CurseForge rejects files of 2 GB or more. With JPEG the preview tier for all continents is about 1.2 GB and each HD pack about 1.6 GB, both estimated from map art rather than real screenshots. `agps sv-build` enforces a 1.8 GB budget; the levers in order are JPEG quality, splitting packs per continent, then wider spacing. PNG would have been about 3.7 GB per continent for the preview tier alone.
- **JPEG support on the beta client** is documented but untested; milestone 0 probes it, and BLP DXT1 is the fallback.
- **CurseForge moderation** forbids copyrighted material used without permission, and every image is Blizzard content. The pilot upload in milestone 7b tests this before the expensive capture runs.
- **Pose repeatability**: if `SetView` pitches drift, stitching produces seams. Discrete mode does not care, so it ships first.
- **Beta client churn**: the beta build changes weekly until the 2026-11-04 launch; art changes make some captures stale. Record `client_build` per point and plan a retake pass after launch.
- **Custom hyperlinks** may not survive on this client; the typed `/sv join` fallback exists from day one.
- **Addon message limits**: 255 bytes per message and client side throttling; the protocol keeps the point id out of chat text and batches score messages.
- **Secret values**: some unit and map values are secret in combat on this client; the game logic must tolerate `issecretvalue` results and pause the countdown display instead of erroring.
- **Empty streets**: if the private server core has no creature spawns, NPCs and mobs will be missing from the shots. Note it in `SERVER.md` after R0 so the user can decide whether to populate the spawn tables.

## 9. Decisions needed from the user

1. Point spacing (75 yards suggested) once `agps sv-points` prints the counts and hours.
2. Public or private repo for `AzerothGPS-StreetView` from the start (public suggested; the harvester stays private either way).
3. Whether the capture PC is on the LAN (HTTP receiver) or remote (Tailscale or Syncthing).
4. Which race the capture character uses (fixes the camera height for the whole dataset, Tracks 1 and 3).
5. After R2: whether the Track 2 render look is acceptable for the public data packs, or whether only real screenshots (Track 1 or Track 3) may ship. That choice sets how many points the user is willing to capture by hand.
