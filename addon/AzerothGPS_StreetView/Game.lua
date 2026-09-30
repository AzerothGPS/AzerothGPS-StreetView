-- Where in the Azeroth? (Street Guess): a GeoGuessr-style game on the AzerothGPS map. Everyone gets the same street view
-- (no zone name or coordinates) and has 30 seconds to look around and double-click the map where
-- they think it is (again to move the guess: the one placed when the time runs out counts): the
-- closer, the more points (0-100 a round, the first ones easy, the last hard).
-- Street views come only from the map packs every player has; the panel says who lacks which.
-- Solo, with the party, with one player by whisper, or an open game (a link posted in chat: whoever
-- clicks it joins, up to 40); 1, 3 or 5 rounds. The lobby counts down 30 s, the same for everyone.
--
-- While a game is on, the map is held (AzerothGPS.HoldMap): the route and its directions panel
-- aren't shown (the route goes on; the arrow window still guides) and the game's panel takes the
-- directions' place; its X leaves the game and brings the route back.
--
-- Players talk through addon messages (prefix "AGPSSV", to the party, the one player whispered or an
-- open game's hidden channel "AGPSSV<id>") and only about the game: an invitation is always asked
-- before joining (an open game's link is the asking: clicking it joins). The host picks the
-- street views and paces the rounds; each player scores their own guess and tells the others.
--   I:id:rounds:packs:secs invitation (host)          J:id:packs / D:id / B:id   join / decline / busy
--   (J's 3rd field: the host's name as the joiner sees it; W's 3rd: the one who joined, as the host
--   sees them: WoW Forever's names are "First Surname", and each side takes the others' spelling)
--   W:id:secs:name         the lobby's seconds left (host, on each join)   U:id:why   (host) can't join:
--                          full / started / over (an open game's J, whispered)
--   K:id:name:packs        a player's packs (host)    (packs: Kalimdor/2026.09.29,EasternKingdoms/...)
--   L:id:ver:part:parts:name,name,...   the players (host), split over as many messages as a raid's
--                          names need (an addon message holds 255 bytes)   Q:id   a player left
--   P:id:round:spot        the next street view (host)   O:id:round / M:id:round   have it / missing
--   G:id:round             the round starts (host)    S:id:round:score:yards:cont:x:y   a guess
--   N:id:round             the round is over (host)   F:id  the game is over   X:id  the host ended it
-- The logic below has no frames (tests/test_game.py drives it under lupa through Gm.io); the
-- window parts are at the end, built by Gm.Init.
local _, ns = ...

local Gm = {}
ns.Game = Gm
local D = ns.Data

Gm.PREFIX = "AGPSSV"
Gm.LOOK_SECONDS = 30 -- the street view shows this long: the time to guess
Gm.MSG_MAX = 240 -- an addon message's length, with room to spare (the game's limit is 255 bytes)
Gm.HOST_SILENT_SECONDS = 75 -- no word from the host this long (they went offline): the game is over
Gm.RESULT_SECONDS = 10 -- the round's result, before the next round (the user, 2026-09-29)
Gm.OVER_SECONDS = 60 -- the final result stays this long, then the game closes and the map is the map again
Gm.BOARD_ROWS = 3 -- the scoreboard's players at first ("-"); its "+" shows up to
Gm.BOARD_ROWS_MAX = 8 -- ... this many (the user, 2026-09-30)
Gm.MENU_IDLE_SECONDS = 20 -- the game's menu, left alone this long (no choice, no mouse over it), closes
Gm.JOIN_SECONDS = 30 -- the lobby: the game starts this long after the host starts it (the host can start
-- it sooner; a party's starts as soon as everyone answered), counted down for every player who joined
Gm.MAX_PLAYERS = 40 -- an open game (the link posted in chat) takes this many, then starts
Gm.LINK_ANSWER_SECONDS = 10 -- a link clicked: no word from its host this long, the game is gone
Gm.POST_COOLDOWN = 5 -- the link posted: again after this long (no spamming the channels)
Gm.PROPOSE_SECONDS = 3 -- ... and this long for the players to say they have the next street view
Gm.GRACE_SECONDS = 3 -- a round ends this long after the guessing time, whoever hasn't answered
Gm.MAX_TRIES = 5 -- street views tried until everyone has one
Gm.FULL_YD = 25 -- a guess this close gets all 100 points
Gm.SCALE_YD = 1700 -- ... then 100 * e^(-((yards - 25) / 1700) ^ 1.1), rounded down: 99 just past 25 yd, 92 at
Gm.SCORE_POWER = 1.1 -- 200 yd, 78 at 500, 58 at 1,000, 30 at 2,000, 7 at 4,000, 1 at 6,000 (tightened by the
-- user, 2026-09-30: somewhere in the right zone is no longer nearly full marks)
Gm.FIT_MAX_YD = 2950 -- the result: guess and answer shown together up to this zoom (yards from the middle to
-- the edge), the terrain view's widest (AzerothGPS shows map art past 3000: the view never flips style;
-- right-click still goes out to the continent); farther apart, the answer alone
Gm.PAN_SECONDS = 0.9 -- ... the map pans and zooms out to them this smoothly, then the line grows
Gm.SPOT_ZOOM_YD = 600 -- ... else the spot alone, this zoomed
Gm.CELEBRATE_MIN = 75 -- the average round score that earns the celebration (solo: the player's; else the winner's)
Gm.ROUNDS = { 1, 3, 5 }
-- Each player's look: their icon on the map and their color (their name on the scoreboard, their
-- dotted line). Up to 5 players (solo, whisper, a party): one of the user's orc animations each
-- (Media/Guess<n>.tga, the color its skin's); solo, a random one. A raid: the player's own guess
-- is an orc, everyone else's a colored square, from 40 colors. Given in the host's roster order (L),
-- so every player sees the same looks.
Gm.MY_COLOR = { 1, 1, 1 } -- (before looks are given out)
Gm.ORCS = {
  { name = "green", color = { 0.58, 0.8, 0.35 } },
  { name = "Mag'har brown", color = { 0.85, 0.6, 0.4 } },
  { name = "olive", color = { 0.66, 0.7, 0.38 } },
  { name = "golden", color = { 0.95, 0.84, 0.3 } },
  { name = "forest green", color = { 0.3, 0.72, 0.34 } },
}
-- 40 colors for a raid's squares: hues spread by the golden angle, two strengths, three brightnesses
Gm.RAID_COLORS = {}
for i = 0, 39 do
  local h, sat, v = (i * 0.618034) % 1, (i % 2 == 0) and 0.75 or 0.5, ({ 1, 0.85, 0.7 })[i % 3 + 1]
  local k = math.floor(h * 6)
  local f = h * 6 - k
  local pp, q, t = v * (1 - sat), v * (1 - f * sat), v * (1 - (1 - f) * sat)
  local rgb = ({ { v, t, pp }, { q, v, pp }, { pp, v, t }, { pp, q, v }, { t, pp, v }, { v, pp, q } })[k % 6 + 1]
  Gm.RAID_COLORS[i + 1] = rgb
end

---------------------------------------------------------------------------------------------
-- Pure helpers

-- Points (0-100) for a guess `yards` off (nil: no guess, or on another continent).
function Gm.Score(yards)
  if not yards then return 0 end
  if yards <= Gm.FULL_YD then return 100 end
  return math.floor(100 * math.exp(-((yards - Gm.FULL_YD) / Gm.SCALE_YD) ^ Gm.SCORE_POWER))
end

function Gm.Encode(...)
  local t = { ... }
  for i = 1, select("#", ...) do t[i] = t[i] == nil and "" or tostring(t[i]) end
  return table.concat(t, ":")
end

-- kind, { fields } of a message (nil if it isn't one).
function Gm.Decode(msg)
  if type(msg) ~= "string" or msg == "" or #msg > 255 then return nil end
  local parts = {}
  for f in (msg .. ":"):gmatch("([^:]*):") do parts[#parts + 1] = f end
  local kind = table.remove(parts, 1)
  if not kind:match("^%u$") then return nil end
  return kind, parts
end

-- A pack's key in messages ("AzerothGPS_StreetView_EasternKingdoms" -> "EasternKingdoms"), and
-- how players read it ("Eastern Kingdoms").
function Gm.PackKey(name)
  return (tostring(name or "?"):gsub("^AzerothGPS_StreetView_", ""):gsub("[:,/]", ""))
end
function Gm.PackTitle(key)
  return (key:gsub("(%l)(%u)", "%1 %2"):gsub("_", " "))
end

-- Packs as a message field ({ key = version } -> "EasternKingdoms/2026.09.29,Kalimdor/...").
function Gm.PackField(t)
  local out = {}
  for k, v in pairs(t) do out[#out + 1] = k .. "/" .. (tostring(v):gsub("[:,/]", "")) end
  table.sort(out)
  return table.concat(out, ",")
end
function Gm.ParsePacks(field)
  local t = {}
  for item in (field or ""):gmatch("[^,]+") do
    local k, v = item:match("^([^/]+)/?(.*)$")
    if k then t[k] = v end
  end
  return t
end
-- This player's installed packs: { key = version }.
function Gm.MyPacks()
  local t = {}
  for _, pk in ipairs(D.packs or {}) do t[Gm.PackKey(pk.name)] = tostring(pk.version or "") end
  return t
end

-- The packs to play from and who lacks what, over all the players' packs: common = { key = true }
-- (every player has it), report = { { name, missing = { key, ... }, older = { key, ... } }, ... }.
-- Players whose packs aren't known yet don't count.
function Gm.ComparePacks(g)
  local all, newest = {}, {}
  for _, name in ipairs(g.order) do
    for k, v in pairs(g.packs[name] or {}) do
      all[k] = true
      if not newest[k] or v > newest[k] then newest[k] = v end
    end
  end
  local common, report = {}, {}
  for k in pairs(all) do common[k] = true end
  for _, name in ipairs(g.order) do
    local mine = g.packs[name]
    if mine then
      local miss, older = {}, {}
      for k in pairs(all) do
        if not mine[k] then
          miss[#miss + 1] = k
          common[k] = nil
        elseif mine[k] < newest[k] then
          older[#older + 1] = k -- (fewer street views, maybe: a round checks everyone has its one)
        end
      end
      table.sort(miss)
      table.sort(older)
      if #miss > 0 or #older > 0 then report[#report + 1] = { name = name, missing = miss, older = older } end
    end
  end
  return common, report
end

-- A random street view for a round: on a continent (not a dungeon), not in `used` yet, in one of
-- the `allowed` packs (keys; nil: any). rnd(n) gives 1..n (math.random).
function Gm.PickSpot(used, rnd, allowed)
  local ids = {}
  for id, p in pairs(D.byId) do
    -- (the continents and the cities, Undercity's level included; never instances or caves: those
    -- are levels of 20000 and up, or have a p.kind. The user, 2026-09-29)
    if not used[id] and type(p.cont) == "number" and p.cont < 20000 and not p.kind
        and (not allowed or (p.pack and allowed[Gm.PackKey(p.pack.name)]))
        and (not Gm.Usable or Gm.Usable(p)) then
      ids[#ids + 1] = id
    end
  end
  if #ids == 0 then return nil end
  table.sort(ids) -- (the same pick for the same numbers: tests)
  return D.byId[ids[(rnd or math.random)(#ids)]]
end

-- The spot as the game uses it: on its base continent (a city level such as Undercity's is drawn in
-- its continent's coordinates, and guesses are placed on the continent). A copy; the pictures stay the spot's.
function Gm.OnMap(p, base)
  if not (p and base and p.cont >= 10000) then return p end
  local c = base(p.cont)
  if not c or c == p.cont then return p end
  local q = {}
  for k, v in pairs(p) do q[k] = v end
  q.cont = c
  return q
end

-- Ties broken by distance (the user, 2026-09-30: as few ties as can be): a score to the hundredth,
-- lower the farther into its points' band of yards the guess was, and always above the points below
-- (100 points: 100 at 0 yd, 99.6 at 10 yd, 99.0 at 25 yd; 92 points: 92.0 to 91.01). The points stay
-- whole; the fine score only orders players who'd tie and is shown only then (Gm.ShowTied). Every
-- client works it out alike from the yards in S (whole yards).
local function BandEdge(n) -- the yards up to which a guess earns at least n points (1-100)
  if n >= 100 then return Gm.FULL_YD end
  return Gm.FULL_YD + Gm.SCALE_YD * (-math.log(n / 100)) ^ (1 / Gm.SCORE_POWER)
end
function Gm.Fine(score, yards)
  if not score or score <= 0 or not yards then return score or 0 end
  yards = math.floor(yards + 0.5)
  local lo = score >= 100 and 0 or BandEdge(score + 1)
  local hi = BandEdge(score)
  local pos = hi > lo and math.min(1, math.max(0, (yards - lo) / (hi - lo))) or 0
  return math.floor((score - 0.99 * pos) * 100 + 0.5) / 100
end

-- A player's fine score for round r.
function Gm.RoundFine(pl, r)
  local sc, gs = pl.scores[r], pl.guesses[r]
  return Gm.Fine(sc, gs and gs.yards)
end

-- The players by total so far: { { name, total, fine, last, lastFine, rounds }, ... }; a tie on the
-- total goes to the closer guesses (`fine`: the total less the average of the rounds' fractions, so it
-- stays between the total and the one below), then by name. `upto`: count only the rounds up to it
-- (the round being played isn't shown before its result).
function Gm.Standings(g, upto)
  upto = upto or g.round
  local list = {}
  for _, name in ipairs(g.order) do
    local pl = g.players[name]
    local total, fine, n = 0, 0, 0
    for r = 1, upto do
      if pl.scores[r] then
        total, fine, n = total + pl.scores[r], fine + Gm.RoundFine(pl, r), n + 1
      end
    end
    list[#list + 1] = { name = name, total = total, fine = total - (total - fine) / math.max(1, n),
      last = pl.scores[upto], lastFine = pl.scores[upto] and Gm.RoundFine(pl, upto) or nil, rounds = n }
  end
  table.sort(list, function(a, b)
    if a.total ~= b.total then return a.total > b.total end
    if math.abs(a.fine - b.fine) > 1e-6 then return a.fine > b.fine end
    return a.name < b.name
  end)
  return list
end

-- The names at the top (none when nobody scored): more than one only when even the distances tie.
function Gm.Winners(list)
  local out = {}
  local top = list[1]
  if not top or top.total <= 0 then return out end
  for _, s in ipairs(list) do
    if s.total == top.total and math.abs(s.fine - top.fine) <= 1e-6 then out[#out + 1] = s.name end
  end
  return out
end

-- The scoreboard's rows (ranks), from `n` players: the top Gm.BOARD_ROWS (the panel's "+": the top
-- Gm.BOARD_ROWS_MAX), and this player's own rank (`mine`) after them when it's lower down.
function Gm.BoardRows(n, mine, expanded)
  local out = {}
  local limit = math.min(n, expanded and Gm.BOARD_ROWS_MAX or Gm.BOARD_ROWS)
  for i = 1, limit do out[i] = i end
  if mine and mine > limit and mine <= n then out[#out + 1] = mine end
  return out
end

-- How to show numbers side by side ({ { whole, fine }, ... } -> strings): whole, unless another shows
-- the same, then with the decimals that tell them apart (one, else two).
function Gm.ShowTied(list)
  local out = {}
  local function Count(fmt, i)
    local k, mine = 0, fmt(list[i])
    for j = 1, #list do
      if fmt(list[j]) == mine then k = k + 1 end
    end
    return k, mine
  end
  local whole = function(e) return tostring(e[1]) end
  local one = function(e) return string.format("%.1f", math.floor((e[2] or e[1]) * 10 + 1e-6) / 10) end
  local two = function(e) return string.format("%.2f", e[2] or e[1]) end
  for i = 1, #list do
    local k, s = Count(whole, i)
    if k > 1 and list[i][1] > 0 then
      k, s = Count(one, i)
      if k > 1 then k, s = Count(two, i) end
    end
    out[i] = s
  end
  return out
end

-- A player's look ({ orc = n } or { color = { r, g, b } }; nil until given out) and color.
function Gm.PlayerLook(g, name)
  return g.looks and g.looks[name]
end
function Gm.PlayerColor(g, name)
  local look = Gm.PlayerLook(g, name)
  if not look then return Gm.MY_COLOR end
  return look.orc and Gm.ORCS[look.orc].color or look.color
end

-- Give out the looks, in `roster` order (the host's): who has one keeps it. rnd(n): 1..n.
function Gm.AssignLooks(g, roster, rnd)
  g.looks = g.looks or {}
  local raid = g.channel == "RAID" or #roster > #Gm.ORCS
  if g.mode == "solo" then
    g.looks[g.me] = g.looks[g.me] or { orc = (rnd or math.random)(#Gm.ORCS) }
    return
  end
  local usedOrc, usedColor = {}, {}
  for _, look in pairs(g.looks) do
    if look.orc then usedOrc[look.orc] = true end
    if look.color then usedColor[look.color] = true end
  end
  for _, name in ipairs(roster) do
    if not g.looks[name] then
      if raid and name ~= g.me then
        for _, c in ipairs(Gm.RAID_COLORS) do
          if not usedColor[c] then
            g.looks[name], usedColor[c] = { color = c }, true
            break
          end
        end
      else
        for k = 1, #Gm.ORCS do
          if not usedOrc[k] then
            g.looks[name], usedOrc[k] = { orc = k }, true
            break
          end
        end
      end
      g.looks[name] = g.looks[name] or { color = Gm.RAID_COLORS[1] } -- (more players than looks)
    end
  end
end
function Gm.ColorCode(c)
  return string.format("|cff%02x%02x%02x", math.floor(c[1] * 255 + 0.5), math.floor(c[2] * 255 + 0.5), math.floor(c[3] * 255 + 0.5))
end

-- Where the map should look to show the answer and the guesses (points { x, y } on the answer's
-- continent): x, y and zoom (yards to the edge) when they fit on the map together (FIT_MAX_YD), else
-- nil (then the answer alone).
function Gm.FitView(spot, points)
  local x0, x1, y0, y1 = spot.x, spot.x, spot.y, spot.y
  for _, q in ipairs(points) do
    x0, x1 = math.min(x0, q.x), math.max(x1, q.x)
    y0, y1 = math.min(y0, q.y), math.max(y1, q.y)
  end
  local half = math.max(x1 - x0, y1 - y0) / 2
  local zoom = math.max(250, half * 1.3 + 80) -- (a margin around them)
  if zoom > Gm.FIT_MAX_YD then
    if half > Gm.FIT_MAX_YD * 0.95 then return nil end -- (not both on the terrain view, even tight)
    zoom = Gm.FIT_MAX_YD
  end
  return (x0 + x1) / 2, (y0 + y1) / 2, zoom
end

-- Solo: the average round score over the rounds played.
function Gm.Average(g)
  local pl = g.players[g.me]
  local total = 0
  for r = 1, g.round do total = total + (pl and pl.scores[r] or 0) end
  return g.round > 0 and math.floor(total / g.round + 0.5) or 0
end

-- A player's guess marker's tooltip (mouse over it in a round's result or the final one): their
-- name, the round's score and distance, and their total. { { text, r, g, b }, ... }
function Gm.PlayerTip(g, name)
  local pl = g and g.players[name]
  if not pl then return {} end
  local c = Gm.PlayerColor(g, name)
  local lines = { { (name == g.me and "You" or Gm.Short(name)), c[1], c[2], c[3] } }
  local r = g.round
  local sc, gs = pl.scores[r], pl.guesses[r]
  -- (as the scoreboard shows them: with decimals where another player has the same)
  local rounds, totals, me, st = {}, {}, nil, nil
  for _, s in ipairs(Gm.Standings(g)) do
    local other = g.players[s.name]
    if other.scores[r] then rounds[#rounds + 1] = { other.scores[r], Gm.RoundFine(other, r) } end
    totals[#totals + 1] = { s.total, s.fine }
    if s.name == name then
      me, st = #totals, other.scores[r] and #rounds or nil
    end
  end
  if sc then
    local yd = gs and gs.yards
    lines[#lines + 1] = { string.format("Round %d: %s points%s", r, Gm.ShowTied(rounds)[st] or tostring(sc),
      yd and (" (" .. Gm.Yards(yd) .. " yd off)") or (gs and gs.x and " (another continent)" or "")), 1, 1, 1 }
  end
  if r > 1 then
    lines[#lines + 1] = { string.format("Total: %s after %d rounds", Gm.ShowTied(totals)[me], r), 0.8, 0.8, 0.8 }
  end
  return lines
end

function Gm.Yards(n)
  n = math.floor(n + 0.5)
  if n >= 1000 then return string.format("%d,%03d", math.floor(n / 1000), n % 1000) end
  return tostring(n)
end

---------------------------------------------------------------------------------------------
-- The game (one at a time). Everything that touches the game client goes through Gm.io.

local game

-- Default io: the game client (tests replace it).
Gm.io = {
  now = function() return GetTime() end,
  base = function(c) -- (a city level's continent: AzerothGPS.BaseContinent)
    local API = _G.AzerothGPS
    return API and API.BaseContinent and API.BaseContinent(c) or c
  end,
  me = function() -- (as the others see this player: "First Surname-Realm" in WoW Forever)
    local n = Gm.UnitFullName("player")
    local r = GetNormalizedRealmName and GetNormalizedRealmName() or ""
    if r == "" and UnitFullName then r = select(2, UnitFullName("player")) or "" end
    return r ~= "" and (n .. "-" .. r) or n
  end,
  send = function(msg, chatType, target)
    if not (C_ChatInfo and C_ChatInfo.SendAddonMessage) then return end
    if chatType == "CHANNEL" and type(target) == "string" then -- (an open game's channel, by name)
      local index = GetChannelName(target)
      if not index or index == 0 then return end
      target = index
    end
    C_ChatInfo.SendAddonMessage(Gm.PREFIX, msg, chatType, target)
  end,
  -- an open game's hidden chat channel (its addon messages; never shown in a chat window)
  joinChannel = function(name) if JoinTemporaryChannel then JoinTemporaryChannel(name) end end,
  leaveChannel = function(name) if LeaveChannelByName then LeaveChannelByName(name) end end,
  post = function(text, chatType, index) SendChatMessage(text, chatType, nil, index) end,
  group = function() -- the party's channel, nil when not in one
    if IsInRaid and IsInRaid() then return "RAID" end
    if IsInGroup and IsInGroup() then return "PARTY" end
  end,
  groupSize = function() return GetNumGroupMembers and GetNumGroupMembers() or 0 end,
  inGroup = function(name)
    local short = Ambiguate(name, "none")
    if UnitInParty and UnitInParty(short) then return true end
    return UnitInRaid and UnitInRaid(short) ~= nil or false
  end,
  random = function(a, b) if a then return math.random(a, b) end return math.random() end,
  -- the rest: the viewer, the map and the panel (Gm.Init sets them)
  open = function() end, close = function() end, hold = function() end, lookAt = function() end,
  follow = function() end, showMap = function() end, world = function() end, view = function() end,
  mapState = function() end, changed = function() end, ask = function() end,
  print = function(...) if ns.Print then ns.Print(...) end end,
}
local io = function() return Gm.io end

function Gm.Current() return game end
function Gm.Active() return game ~= nil end
function Gm.Playing() return game ~= nil and game.phase ~= "over" end

local function Changed() io().changed() end
local function Now() return io().now() end

local function Short(name) return (name or "?"):match("^([^-]+)") or name end
Gm.Short = Short

-- WoW Forever's players have a first name and a surname (the client's "regional unique names":
-- UnitName gives both, the chat shows "First Surname"). A unit's name that way (else just the name).
function Gm.UnitFullName(unit)
  local n, second = UnitName(unit)
  if not n then return nil end
  if RegionalUniqueNamesEnabled and RegionalUniqueNamesEnabled() and second and second ~= "" then
    local c = Constants and Constants.CharacterNameSeparatorConsts
    return n .. (c and c.CHARACTERNAME_SURNAME_SEPARATOR or " ") .. second
  end
  return n
end

-- The same player's names however they're written (the first name alike: "Ann-Realm", "Ann Smith",
-- "Ann-Smith-Realm"): what this player calls themselves and what the others see can differ, and
-- each side tells the other (J, W) so everyone ends up with the same.
function Gm.SameRoot(a, b)
  a, b = tostring(a or ""):match("^[^%s%-]+"), tostring(b or ""):match("^[^%s%-]+")
  return a ~= nil and b ~= nil and a:lower() == b:lower()
end

local function AddPlayer(name)
  if not game.players[name] then
    game.players[name] = { name = name, scores = {}, guesses = {} }
    game.order[#game.order + 1] = name
  end
end

-- A player's name as the others see it, instead of the one they had (their own or the host's).
local function Rename(old, new)
  if not new or new == "" or old == new or not game.players[old] or game.players[new] then return end
  local pl = game.players[old]
  pl.name = new
  game.players[new], game.players[old] = pl, nil
  for i, n in ipairs(game.order) do
    if n == old then game.order[i] = new end
  end
  for _, t in ipairs({ game.packs, game.looks, game.answers or {}, game.acks or {} }) do
    if t[old] ~= nil then t[new], t[old] = t[old], nil end
  end
  if game.me == old then game.me = new end
  if game.host == old then game.host = new end
  game.isHost = game.host == game.me
end

local function RemovePlayer(name)
  if not game.players[name] then return end
  game.players[name] = nil
  for i, n in ipairs(game.order) do
    if n == name then table.remove(game.order, i) break end
  end
end

-- An open game's channel: its name from the game's id, joined and left through io (guarded: the
-- tests' io and older ones may lack them).
function Gm.ChannelName(id) return "AGPSSV" .. id end
local function JoinChannel(name) if io().joinChannel then io().joinChannel(name) end end
local function LeaveChannel(g) if g and g.open and g.chanName and io().leaveChannel then io().leaveChannel(g.chanName) end end
-- (the target that goes with game.channel: an open game's channel name, else none)
local function ChanTarget() return game.open and game.chanName or nil end

-- To everyone else in the game: the party's channel (an open game's own), or a whisper each.
local function ToOthers(...)
  if game.mode == "solo" then return end
  local msg = Gm.Encode(...)
  if game.mode == "party" then
    io().send(msg, game.channel, ChanTarget())
  else
    for _, name in ipairs(game.order) do
      if name ~= game.me then io().send(msg, "WHISPER", name) end
    end
    if game.phase == "invite" and game.target then io().send(msg, "WHISPER", game.target) end
  end
end

-- The players (host), in as many L messages as it takes: a raid's "Name-Realm"s don't fit in one.
local function SendRoster()
  game.rosterVer = (game.rosterVer or 0) + 1
  local room = Gm.MSG_MAX - #Gm.Encode("L", game.id, game.rosterVer, 99, 99, "")
  local parts, cur, len = {}, {}, 0
  for _, name in ipairs(game.order) do
    if #cur > 0 and len + 1 + #name > room then
      parts[#parts + 1] = table.concat(cur, ",")
      cur, len = {}, 0
    end
    len = len + (#cur > 0 and 1 or 0) + #name
    cur[#cur + 1] = name
  end
  parts[#parts + 1] = table.concat(cur, ",")
  for k, names in ipairs(parts) do ToOthers("L", game.id, game.rosterVer, k, #parts, names) end
end

local function NewGame(mode, rounds, host, id)
  LeaveChannel(game) -- (the last game, over but not closed yet)
  local me = io().me()
  game = { id = id or tostring(io().random(100000, 999999)), mode = mode, rounds = rounds, host = host or me, me = me,
    players = {}, order = {}, round = 0, used = {}, phase = "wait", packs = {}, report = {}, looks = {} }
  game.isHost = game.host == me
  game.packs[me] = Gm.MyPacks()
  AddPlayer(game.host)
  if not game.isHost then AddPlayer(me) end
end

local Look, Result, Over, NextRound, Submit

-- The map for the result: the answer with this player's guess (and, `all`, everyone's) while they
-- fit on the terrain map together, panned there smoothly; else the answer alone; this player's guess
-- on another continent: the world.
local function ShowResult(all)
  local s, g = game.spot, game.guess
  if not s then return end
  if g and g.x and not g.yards then return io().world(s) end
  local pts = {}
  if g and g.x then pts[1] = g end
  local x, y, zoom = Gm.FitView(s, pts)
  if not x then return io().lookAt(s.cont, s.x, s.y, Gm.SPOT_ZOOM_YD) end
  if all then -- the others' guesses too, nearest first, as many as still fit
    local others = {}
    for _, name in ipairs(game.order) do
      local q = name ~= game.me and game.players[name].guesses[game.round]
      if q and q.x and q.cont == s.cont then others[#others + 1] = q end
    end
    table.sort(others, function(p, q)
      return (p.x - s.x) ^ 2 + (p.y - s.y) ^ 2 < (q.x - s.x) ^ 2 + (q.y - s.y) ^ 2
    end)
    for _, q in ipairs(others) do
      pts[#pts + 1] = q
      local x2, y2, z2 = Gm.FitView(s, pts)
      if not x2 then
        pts[#pts] = nil
        break
      end
      x, y, zoom = x2, y2, z2
    end
  end
  local vx, vy, vc, vz = io().view()
  if vx and vc == s.cont and vz and vz > 0 then -- (animated from where the map is: Gm.Animate)
    game.pan = { t0 = Now(), cont = s.cont, x0 = vx, y0 = vy, z0 = vz, x1 = x, y1 = y, z1 = zoom }
    if game.reveal and Now() - game.reveal.t0 < 0.05 then game.reveal.t0 = Now() + Gm.PAN_SECONDS end
  else
    io().lookAt(s.cont, x, y, zoom)
  end
end

-- The game ends (reason: why, when it didn't run its rounds). The panel stays until its X.
Over = function(reason)
  if not game then return end
  game.phase = "over"
  game.reason = reason
  game.closeAt = Now() + Gm.OVER_SECONDS
  -- (the last round's street view stays up: the user, 2026-09-30; leaving closes it)
  local list = Gm.Standings(game)
  game.winners = Gm.Winners(list)
  game.tiebreak = #game.winners == 1 and list[2] ~= nil and list[2].total == list[1].total
  if game.mode == "solo" then
    game.celebrate = not reason and Gm.Average(game) >= Gm.CELEBRATE_MIN
  else
    local top = list[1]
    game.celebrate = not reason and #game.winners > 0 and top ~= nil
      and top.total / math.max(1, game.round) >= Gm.CELEBRATE_MIN
  end
  Changed()
end

-- host: the next street view, asked of the players first
local function Propose()
  local p = Gm.PickSpot(game.used, function(n) return io().random(1, n) end, game.common)
  if not p then return Over("No street views are installed") end
  game.used[p.id] = true
  game.spot = Gm.OnMap(p, io().base)
  if game.mode == "solo" then return Look() end
  game.phase = "propose"
  game.acks = {}
  game.deadline = Now() + Gm.PROPOSE_SECONDS
  ToOthers("P", game.id, game.round, p.id)
  Changed()
end

NextRound = function()
  game.round = game.round + 1
  game.tries = 0
  Propose()
end

-- The street view shows (a random way to look), the countdown runs.
Look = function()
  game.phase = "look"
  game.deadline = Now() + Gm.LOOK_SECONDS
  game.roundEnd = game.deadline + Gm.GRACE_SECONDS
  game.guess, game.reveal, game.pending = nil, nil, nil
  game.missing = game.spot == nil
  io().world(game.spot) -- (every round starts from the whole world: no hint where to look)
  game.heading = io().random() * 2 * math.pi
  if game.spot then io().open(game.spot, game.heading) end
  Changed()
end

-- This player's guess is in (g: { x, y, cont, yards, score }; nil: none in time).
local function Scored(g)
  local score = g and g.score or 0
  game.guess = g or { score = 0, none = true }
  local mine = game.players[game.me]
  if mine then
    mine.scores[game.round] = score
    mine.guesses[game.round] = g
  end
  if g and g.x then game.reveal = { t0 = Now() } end
  ShowResult()
  ToOthers("S", game.id, game.round, score, g and g.yards and math.floor(g.yards + 0.5) or "",
    g and g.cont or "", g and g.x and math.floor(g.x + 0.5) or "", g and g.y and math.floor(g.y + 0.5) or "")
  if game.mode == "solo" then
    return Result()
  end
  game.phase = "wait"
  Changed()
end

Result = function()
  -- (the round's street view stays up until the next one replaces it: the user, 2026-09-30)
  game.phase = "result"
  game.deadline = Now() + Gm.RESULT_SECONDS
  if not game.guess then -- (the host ended the round before this player's time was up)
    local g = game
    Submit()
    if game ~= g then return end
    game.phase = "result"
  end
  if game.mode ~= "solo" then ShowResult(true) end -- (everyone's guesses in view)
  Changed()
end

-- Who lacks which pack, again (the players or their packs changed).
local function Compare()
  game.common, game.report = Gm.ComparePacks(game)
end

local function Begin()
  if #game.order < 2 then
    return Over(game.mode == "whisper" and (Short(game.target) .. " didn't join") or "No one joined (they need AzerothGPS StreetView)")
  end
  Compare()
  if next(game.common) == nil then
    ToOthers("X", game.id)
    return Over("There's no map pack every player has")
  end
  for _, name in ipairs(game.order) do ToOthers("K", game.id, name, Gm.PackField(game.packs[name] or {})) end
  Gm.AssignLooks(game, game.order, function(n) return io().random(1, n) end)
  SendRoster()
  NextRound()
end

-- Everyone asked has answered the invitation.
local function AllAnswered()
  local n = 0
  for _ in pairs(game.answers) do n = n + 1 end
  if game.mode == "whisper" then return n >= 1 end
  if game.open then return #game.order >= Gm.MAX_PLAYERS end -- (anyone may still click the link)
  return n >= io().groupSize() - 1
end

-- Start a game as its host. mode: "solo", "party", "whisper" (target: the player's name) or "open"
-- (a party of whoever clicks the link the host posts in chat, up to Gm.MAX_PLAYERS, over the game's
-- own hidden channel).
function Gm.Start(mode, rounds, target)
  if game and game.phase ~= "over" then
    io().print("A game is already on.")
    return false
  end
  local open = mode == "open"
  if open then mode = "party" end
  if mode == "party" and not open and not io().group() then
    io().print("You're not in a party.")
    return false
  end
  if mode == "whisper" then
    target = target and strtrim and strtrim(target) or target
    if not target or target == "" then
      io().print("Whose name? Target a player or type their name.")
      return false
    end
    if not target:find("-", 1, true) then
      local realm = io().me():match("%-(.+)$")
      if realm then target = target .. "-" .. realm end
    end
    if target == io().me() then
      io().print("Invite someone else.")
      return false
    end
  end
  if next(D.byId) == nil then
    io().print("No street views are installed.")
    return false
  end
  NewGame(mode, rounds)
  game.before = io().mapState()
  game.channel = mode == "party" and io().group() or nil
  if open then
    game.open, game.channel, game.chanName = true, "CHANNEL", Gm.ChannelName(game.id)
    JoinChannel(game.chanName)
  end
  game.target = mode == "whisper" and target or nil
  io().hold(true)
  io().showMap()
  if mode == "solo" then
    Gm.AssignLooks(game, game.order, function(n) return io().random(1, n) end)
    NextRound()
    return true
  end
  game.phase = "invite"
  game.answers = {}
  game.deadline = Now() + Gm.JOIN_SECONDS
  -- (the seconds left: the lobby's countdown, the same for everyone)
  if not open then ToOthers("I", game.id, rounds, Gm.PackField(game.packs[game.me]), Gm.JOIN_SECONDS) end
  Changed()
  return true
end

-- The lobby's seconds left (host), whole.
local function SecondsLeft() return math.max(0, math.ceil(game.deadline - Now())) end

-- An open game's invitation, as posted in chat: just its code (chat can't carry an addon's own
-- links); players with StreetView see it as the link to click (Gm.Linkify). (The user, 2026-09-30:
-- no more text around it.)
function Gm.JoinText(g)
  g = g or game
  return string.format("AGPSSV-%s-%d", g.id, g.rounds)
end

-- The game's id and rounds in a chat line with its code, else nil.
function Gm.ParseJoinCode(text)
  local id, rounds = tostring(text or ""):match("AGPSSV%-(%d+)%-(%d+)")
  rounds = tonumber(rounds)
  if not id then return nil end
  for _, n in ipairs(Gm.ROUNDS) do
    if n == rounds then return id, rounds end
  end
end

-- A chat line with the code, the code a link (to Gm.OnLink) to join `author`'s game.
function Gm.Linkify(text, author)
  if type(text) ~= "string" or not author or author == "" then return text end
  local id, rounds = Gm.ParseJoinCode(text)
  if not id then return text end
  author = author:gsub(":", "")
  local link = string.format("|cff66ccff|Hgarrmission:agpssv:%s:%d:%s|h[Join Where in the Azeroth?]|h|r", id, rounds, author)
  return (text:gsub("AGPSSV%-%d+%-%d+", function() return link end, 1))
end

-- The link clicked (its "garrmission:agpssv:id:rounds:host").
function Gm.OnLink(link)
  local id, rounds, host = tostring(link):match("^garrmission:agpssv:(%d+):(%d+):(.+)$")
  if id then return Gm.JoinLink(host, id, tonumber(rounds)) end
  return false
end

-- Join an open game from its link: the game's channel, and a J whispered to its host (who answers
-- with the lobby's seconds left, W, or why not, U).
function Gm.JoinLink(host, id, rounds)
  if not host or not id or not rounds then return false end
  if not host:find("-", 1, true) then
    local realm = io().me():match("%-(.+)$")
    if realm then host = host .. "-" .. realm end
  end
  if host == io().me() then
    io().print("That's your own game: post the link for others to click.")
    return false
  end
  if game and game.phase ~= "over" then
    if game.id ~= id then io().print("A game is already on.") end
    return false
  end
  if next(D.byId) == nil then
    io().print("No street views are installed.")
    return false
  end
  NewGame("party", rounds, host, id)
  game.open, game.channel, game.chanName = true, "CHANNEL", Gm.ChannelName(id)
  JoinChannel(game.chanName)
  game.phase = "joined"
  game.before = io().mapState()
  game.askedAt = Now()
  game.deadline = Now() + Gm.JOIN_SECONDS + 10
  game.heardHost = Now()
  io().send(Gm.Encode("J", id, Gm.PackField(game.packs[game.me]), host), "WHISPER", host)
  io().hold(true)
  io().showMap()
  Changed()
  return true
end

-- Host of an open game: post the link (chatType "SAY", "GUILD", "PARTY", "RAID" or "CHANNEL" with
-- the channel's number). A click's work (the game's chat needs one for say and the channels).
function Gm.PostLink(chatType, index)
  if not (game and game.isHost and game.open and game.phase == "invite") then return false end
  local now = Now()
  if game.postedAt and now - game.postedAt < Gm.POST_COOLDOWN then return false end
  game.postedAt, game.postReady = now, nil
  if io().post then io().post(Gm.JoinText(game), chatType, index) end
  Changed()
  return true
end

-- host: start without waiting for the rest of the answers
function Gm.StartNow()
  if game and game.isHost and game.phase == "invite" then Begin() end
end

-- For the developer tools (the private AzerothGPS_StreetView_Dev addon, never shipped): the
-- game's internals, to set up a game without a group.
Gm.internal = {
  NewGame = function(...) return NewGame(...) end,
  AddPlayer = function(name) return AddPlayer(name) end,
  Over = function(reason) return Over(reason) end,
  ShowResult = function(all) return ShowResult(all) end,
  Changed = function() return Changed() end,
}

-- Leave the game (its X): the map shows the route again.
function Gm.Leave()
  if not game then return end
  if game.phase ~= "over" and game.mode ~= "solo" then
    ToOthers(game.isHost and "X" or "Q", game.id)
  end
  local before = game.before
  LeaveChannel(game)
  game = nil
  io().close()
  io().hold(false)
  -- back to the map as it was: the whole view AzerothGPS saved (a continent or world map browsed
  -- stays that map, not a terrain view of it; API version 8), else following the player, or the
  -- view they had
  if before and before.saved and io().restore then
    io().restore(before.saved)
  elseif before and not before.following and before.x then
    io().lookAt(before.cont, before.x, before.y, before.zoom)
  else
    io().follow()
  end
  Changed()
end

-- A double-click on the map: the guess (continent: the base one, AzerothGPS.BaseContinent).
-- It's only placed: another double-click moves it, and the one placed when the time runs out counts.
function Gm.Guess(x, y, cont)
  if not game or game.phase ~= "look" then return end
  game.pending = { x = x, y = y, cont = cont }
  Changed()
end

-- The time is up: the guess placed (if any) is scored.
Submit = function()
  local pg = game.pending
  if not pg then return Scored(nil) end
  local s = game.spot
  local g = { x = pg.x, y = pg.y, cont = pg.cont }
  if s and pg.cont == s.cont then
    g.yards = math.sqrt((pg.x - s.x) ^ 2 + (pg.y - s.y) ^ 2)
  end
  g.score = Gm.Score(g.yards)
  Scored(g)
end

-- The round's street view again (closed during the round).
function Gm.ShowAgain()
  if game and game.spot and not game.missing and game.phase ~= "invite" and game.phase ~= "joined" then
    io().open(game.spot, game.heading)
  end
end


-- Solo: the guess placed is final now (no waiting for the timer).
function Gm.SubmitNow()
  if not game or game.mode ~= "solo" or game.phase ~= "look" or not game.pending then return end
  Submit()
end

-- Has every player still in the game scored this round?
local function AllScored()
  for _, name in ipairs(game.order) do
    if not game.players[name].scores[game.round] then return false end
  end
  return true
end

-- The clock: called often (the panel's driver; tests call it with their time).
function Gm.Tick()
  if not game then return end
  local now = Now()
  if game.phase == "over" then -- (the final result's time is up: back to the map, and the route)
    if game.closeAt and now >= game.closeAt then Gm.Leave() end
    return
  end
  local ph = game.phase
  if ph == "look" and now >= game.deadline then -- the time is up: the guess placed counts
    Submit()
  end
  if ph == "joined" and now >= game.deadline then
    return Over("The game started without you")
  end
  if ph == "joined" and game.open and not game.startAt and now - game.askedAt >= Gm.LINK_ANSWER_SECONDS then
    return Over("No answer from " .. Short(game.host) .. ": the game is over, or they're offline")
  end
  -- (the host went offline or out of reach: nothing more will come)
  if not game.isHost and ph ~= "joined" and game.heardHost and now - game.heardHost > Gm.HOST_SILENT_SECONDS then
    return Over("Lost touch with " .. Short(game.host) .. " (the host)")
  end
  if not game or not game.isHost then return end
  ph = game.phase
  if ph == "invite" and (now >= game.deadline or AllAnswered()) then
    Begin()
  elseif ph == "propose" then
    local all, missing = true, false
    for _, name in ipairs(game.order) do
      if name ~= game.me then
        local a = game.acks[name]
        if a == nil then all = false elseif a == "missing" then missing = true end
      end
    end
    if all or now >= game.deadline then
      if missing and game.tries < Gm.MAX_TRIES then
        game.tries = game.tries + 1
        Propose()
      else
        ToOthers("G", game.id, game.round)
        Look()
      end
    end
  elseif (ph == "look" or ph == "wait") and game.mode ~= "solo" and (AllScored() or now >= game.roundEnd) then
    if ph == "look" then Submit() end
    ToOthers("N", game.id, game.round)
    Result()
  elseif ph == "result" and now >= game.deadline then
    if game.round < game.rounds then
      NextRound()
    else
      ToOthers("F", game.id)
      Over()
    end
  end
end

-- Someone left: off the list; the host leaving ends the game.
local function Gone(name)
  if not game or not game.players[name] or name == game.me then return end
  if name == game.host then
    RemovePlayer(name)
    return Over(Short(name) .. " (the host) left: the game is over")
  end
  RemovePlayer(name)
  if game.isHost then
    if #game.order < 2 and game.phase ~= "invite" and game.phase ~= "over" then
      return Over("Everyone else left")
    end
    if game.phase ~= "invite" then SendRoster() end
  end
  Changed()
end

-- An addon message (prefix already checked) from `sender` ("Name-Realm") on `channel`.
function Gm.OnMessage(msg, channel, sender)
  if not sender or sender == io().me() then return end
  if not sender:find("-", 1, true) then
    local realm = io().me():match("%-(.+)$")
    if realm then sender = sender .. "-" .. realm end
  end
  local kind, f = Gm.Decode(msg)
  if not kind then return end
  local id = f[1]
  if kind == "I" then
    local rounds = tonumber(f[2])
    if not id or not rounds then return end
    local reply = channel == "WHISPER" and "WHISPER" or channel
    local to = channel == "WHISPER" and sender or nil
    local left, heard = tonumber(f[4]) or Gm.JOIN_SECONDS, Now() -- (the lobby's countdown)
    if game and game.phase ~= "over" then
      io().send(Gm.Encode("B", id), reply, to)
      return
    end
    io().ask(sender, rounds, function()
      if game and game.phase ~= "over" then return io().send(Gm.Encode("B", id), reply, to) end
      NewGame(channel == "WHISPER" and "whisper" or "party", rounds, sender, id)
      game.channel = channel ~= "WHISPER" and channel or nil
      game.packs[sender] = Gm.ParsePacks(f[3])
      game.phase = "joined"
      game.before = io().mapState()
      game.startAt = heard + left
      game.deadline = game.startAt + 10 -- (no word from the host by then: it started without us)
      game.heardHost = Now()
      io().send(Gm.Encode("J", id, Gm.PackField(game.packs[game.me]), sender), reply, to) -- (the host as seen here)
      io().hold(true)
      io().showMap()
      Changed()
    end, function()
      io().send(Gm.Encode("D", id), reply, to)
    end)
    return
  end
  if kind == "J" and channel == "WHISPER" and id and (not game or id ~= game.id or game.phase == "over") then
    return io().send(Gm.Encode("U", id, "over"), "WHISPER", sender) -- (a link to a game that's over)
  end
  if not game or id ~= game.id then return end
  if sender == game.host then game.heardHost = Now() end
  local round = tonumber(f[2])
  if game.isHost then
    if kind == "J" and game.open and game.phase ~= "invite" and not game.players[sender] then
      io().send(Gm.Encode("U", game.id, "started"), "WHISPER", sender)
    elseif kind == "J" and game.open and #game.order >= Gm.MAX_PLAYERS and not game.players[sender] then
      io().send(Gm.Encode("U", game.id, "full"), "WHISPER", sender)
    elseif kind == "J" and game.phase == "invite" then
      if f[3] and f[3] ~= game.me and Gm.SameRoot(f[3], game.me) then Rename(game.me, f[3]) end -- (as the others see us)
      AddPlayer(sender)
      game.answers[sender] = true
      game.packs[sender] = Gm.ParsePacks(f[2])
      Compare()
      -- the lobby's seconds left, to whoever just joined (a party: everyone, the same countdown)
      if game.open then
        if game.deadline - Now() < 3 then -- (joined at the last moment: time to hear the channel)
          game.deadline = Now() + 3
          ToOthers("W", game.id, SecondsLeft())
        end
        io().send(Gm.Encode("W", game.id, SecondsLeft(), sender), "WHISPER", sender)
      else
        ToOthers("W", game.id, SecondsLeft(), sender) -- (sender: the one who joined, as seen here)
      end
      Changed()
    elseif (kind == "D" or kind == "B") and game.phase == "invite" then
      game.answers[sender] = false
      if game.mode == "whisper" then
        return Over(Short(sender) .. (kind == "B" and " is in another game" or " declined"))
      end
      Changed()
    elseif (kind == "O" or kind == "M") and game.phase == "propose" and round == game.round and game.players[sender] then
      game.acks[sender] = kind == "M" and "missing" or true
    end
  else
    -- (the host's name as it arrives, when it's written otherwise than the link or invitation had it)
    if sender ~= game.host and game.phase == "joined" and (kind == "W" or kind == "U")
      and Gm.SameRoot(sender, game.host) and not game.players[sender] then
      Rename(game.host, sender)
    end
    if sender ~= game.host and kind ~= "S" and kind ~= "Q" then return end -- (the host runs the game)
    if game.phase == "over" then return end -- (turned away or ended: a round starting doesn't bring it back)
    if kind == "W" and game.phase == "joined" then -- (the lobby's seconds left)
      if f[3] and f[3] ~= game.me and not game.nameSet and Gm.SameRoot(f[3], game.me) then Rename(game.me, f[3]) end
      if f[3] == game.me then game.nameSet = true end
      local left = tonumber(f[2])
      if left then
        game.startAt = Now() + left
        game.deadline = game.startAt + 10
        Changed()
      end
    elseif kind == "U" and game.phase == "joined" then -- (the host turned the join down)
      local why = { full = "'s game is full", started = "'s game already started", over = "'s game is over" }
      return Over(Short(sender) .. (why[f[2]] or " turned the join down"))
    elseif kind == "K" and f[2] then
      game.packs[f[2]] = Gm.ParsePacks(f[3])
      Compare()
      Changed()
    elseif kind == "L" then
      -- (a part of the roster; applied once every part of its version is in)
      local ver, part, parts = tonumber(f[2]), tonumber(f[3]), tonumber(f[4])
      if not (ver and part and parts) or parts < 1 or parts > 40 or part < 1 or part > parts then return end
      if ver < (game.rosterVer or 0) then return end -- (an older roster, late)
      if ver > (game.rosterVer or 0) or not game.rosterParts then game.rosterVer, game.rosterParts = ver, {} end
      game.rosterParts[part] = f[5] or ""
      for k = 1, parts do
        if not game.rosterParts[k] then return end
      end
      local list = table.concat(game.rosterParts, ",", 1, parts)
      game.rosterParts = {}
      if not (","  .. list .. ","):find("," .. game.me .. ",", 1, true) then
        return Over("The game started without you")
      end
      local keep, roster = {}, {}
      for name in list:gmatch("[^,]+") do
        keep[name] = true
        roster[#roster + 1] = name
        AddPlayer(name)
      end
      Gm.AssignLooks(game, roster)
      for i = #game.order, 1, -1 do
        local name = game.order[i]
        if not keep[name] then RemovePlayer(name) end
      end
      Changed()
    elseif kind == "P" and round and f[3] then
      game.round = round
      game.phase = "ready"
      game.spot = Gm.OnMap(D.byId[f[3]], io().base)
      local reply = game.mode == "whisper" and "WHISPER" or game.channel
      io().send(Gm.Encode(game.spot and "O" or "M", game.id, round), reply, game.mode == "whisper" and game.host or ChanTarget())
      Changed()
    elseif kind == "G" and round == game.round then
      Look()
    elseif kind == "N" and round == game.round then
      Result()
    elseif kind == "F" then
      Over()
    elseif kind == "X" then
      Over(Short(sender) .. " ended the game")
    end
  end
  if kind == "S" and round and game.players[sender] then
    local pl = game.players[sender]
    pl.scores[round] = tonumber(f[3]) or 0
    local x, y, c = tonumber(f[6]), tonumber(f[7]), tonumber(f[5])
    pl.guesses[round] = x and { x = x, y = y, cont = c, yards = tonumber(f[4]) } or nil
    Changed()
  elseif kind == "Q" then
    Gone(sender)
  end
end

-- The party changed: whoever isn't in it any more has left the game.
function Gm.OnRoster()
  if not game or game.mode ~= "party" or game.open or game.phase == "over" then return end -- (an open game: no party)
  if not io().group() then return Over("You left the party") end
  for i = #game.order, 1, -1 do
    local name = game.order[i]
    if name ~= game.me and not io().inGroup(name) then Gone(name) end
  end
end

---------------------------------------------------------------------------------------------
-- On the map: the guess, the street view's real spot and a dotted line between them, growing
-- from the guess; in the round's result the other players' guesses too.

local GUESS_COLOR = { 1, 0.35, 0.3 }
local SPOT_COLOR = { 1, 0.82, 0.1 }
Gm.REVEAL_SECONDS = 1.5

-- How far the line has grown (0-1).
function Gm.RevealProgress()
  local r = game and game.reveal
  if not r then return 1 end
  return math.max(0, math.min(1, (Now() - r.t0) / Gm.REVEAL_SECONDS))
end

-- The map's pan and zoom out to the guess and the spot (every frame while it runs).
function Gm.Animate()
  local pn = game and game.pan
  if not pn then return end
  local k = math.min(1, (Now() - pn.t0) / Gm.PAN_SECONDS)
  local e = k < 0.5 and 2 * k * k or 1 - (-2 * k + 2) ^ 2 / 2
  local z = math.exp(math.log(pn.z0) + (math.log(pn.z1) - math.log(pn.z0)) * e) -- (an even zoom speed)
  io().lookAt(pn.cont, pn.x0 + (pn.x1 - pn.x0) * e, pn.y0 + (pn.y1 - pn.y0) * e, z)
  if k >= 1 then game.pan = nil end
end

-- A marker on the map at world (x, y): "guess" (a player's: their orc, variant `orc`) or "answer"
-- (the routes' star marker); a square dot where the map's icons aren't available (tests).
local function Mark(ctx, kind, x, y, orc)
  if Gm.marks then
    local sx, sy = ctx.ToScreen(x, y)
    return Gm.marks.Put(kind, sx, sy, orc)
  end
  if kind == "guess" then
    ctx.Dot(x, y, { 0, 0, 0 }, 15, 0.8)
    ctx.Dot(x, y, GUESS_COLOR, 11, 1)
  else
    ctx.Dot(x, y, SPOT_COLOR, 14, 1)
  end
end

-- A player's guess on the map: their orc, or (a raid's others) a colored square; `name` labels it.
local function PlayerMark(ctx, name, x, y, label)
  local look = Gm.PlayerLook(game, name)
  local orc = look and look.orc or (name == game.me and 1)
  if orc then
    Mark(ctx, "guess", x, y, orc)
  else
    ctx.Dot(x, y, { 0, 0, 0 }, 11, 0.8)
    ctx.Dot(x, y, Gm.PlayerColor(game, name), 8, 1)
  end
  if Gm.marks and (label or game.phase == "result" or game.phase == "over") then
    local lx, ly = ctx.ToScreen(x, y)
    if label then Gm.marks.Label(lx, ly + (orc and 20 or 0), Short(name), Gm.PlayerColor(game, name)) end
    -- (in the results: mouse over the marker for the name and scores; party and raid games)
    if game.mode ~= "solo" and (game.phase == "result" or game.phase == "over") and Gm.marks.Hot then
      Gm.marks.Hot(lx, ly + (orc and 8 or 0), name)
    end
  end
end

local DrawOn
function Gm.Draw(ctx)
  if Gm.marks then Gm.marks.Begin() end
  DrawOn(ctx)
  if Gm.marks then Gm.marks.End() end
end

DrawOn = function(ctx)
  if not game then return end
  local ph = game.phase
  local API = _G.AzerothGPS
  local base = API and API.BaseContinent and API.BaseContinent(ctx.cont) or ctx.cont
  -- a point in the view's coordinates: on the other continent too, through the world map
  -- (AzerothGPS.ToContinent; nil where it can't be placed)
  local function At(cont, x, y)
    if cont == base then return x, y end
    if API and API.ToContinent then return API.ToContinent(cont, x, y, ctx.cont) end
  end
  if ph == "look" then -- the guess placed so far (not the answer yet)
    local pg = game.pending
    local px, py -- (not `pg and At(...)`: `and` keeps only a call's first value)
    if pg then px, py = At(pg.cont, pg.x, pg.y) end
    if px then PlayerMark(ctx, game.me, px, py) end
    return
  end
  if not game.spot then return end
  if ph ~= "wait" and ph ~= "result" and ph ~= "over" then return end
  local sx, sy = At(game.spot.cont, game.spot.x, game.spot.y)
  if not sx then return end
  local t = Gm.RevealProgress()
  if ph ~= "wait" and t >= 1 then -- the others' guesses, in their colors, with their names
    for _, name in ipairs(game.order) do
      if name ~= game.me then
        local g = game.players[name].guesses[game.round]
        local gx, gy
        if g and g.x and g.cont then gx, gy = At(g.cont, g.x, g.y) end
        if gx then
          ctx.Line(gx, gy, sx, sy, Gm.PlayerColor(game, name), 2, 0.85, true)
          PlayerMark(ctx, name, gx, gy, true)
        end
      end
    end
  end
  local g = game.guess
  local gx, gy
  if g and g.x then gx, gy = At(g.cont, g.x, g.y) end
  if gx then
    ctx.Line(gx, gy, gx + (sx - gx) * t, gy + (sy - gy) * t, Gm.PlayerColor(game, game.me), 3, 0.95, true)
    PlayerMark(ctx, game.me, gx, gy)
  end
  if t >= 1 or not gx then Mark(ctx, "answer", sx, sy) end
end

---------------------------------------------------------------------------------------------
-- The window parts: the game button above the figure, the menu that slides out of it, the panel
-- in the directions' place, the invitation. Built by Gm.Init once the figure is on the map.

local API, gameButton, fly, panel
local MENU_H, MENU_EASE = 26, 14
local CELEBRATE = { { 1, 0.85, 0.35 }, { 0.45, 0.95, 0.85 }, { 1, 0.6, 0.85 }, { 0.6, 0.75, 1 } }

local function Clock(sec)
  sec = math.max(0, math.ceil(sec))
  return string.format("%d:%02d", math.floor(sec / 60), sec % 60)
end

-- A small gold-edged button (AzerothGPS's map draws its own the same way).
local Chip
function Gm.Chip(...) return Chip(...) end
Chip = function(parent, text, width, onClick)
  local b = CreateFrame("Button", nil, parent)
  b:SetSize(width, MENU_H - 6)
  local edge = b:CreateTexture(nil, "BACKGROUND")
  edge:SetAllPoints()
  edge:SetColorTexture(1, 0.82, 0, 0.55)
  local fill = b:CreateTexture(nil, "BORDER")
  fill:SetPoint("TOPLEFT", 1, -1)
  fill:SetPoint("BOTTOMRIGHT", -1, 1)
  fill:SetColorTexture(0.12, 0.07, 0.03, 1)
  b.fill = fill
  local hover = b:CreateTexture(nil, "HIGHLIGHT")
  hover:SetAllPoints(fill)
  hover:SetColorTexture(1, 1, 1, 0.15)
  b.label = b:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
  b.label:SetPoint("CENTER", 0, 0)
  b.label:SetText(text)
  b:SetScript("OnClick", onClick)
  b:SetScript("OnLeave", GameTooltip_Hide)
  return b
end

local function Tip(b, title, text)
  b:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_TOP")
    GameTooltip:SetText(title, 1, 1, 1)
    if text then GameTooltip:AddLine(type(text) == "function" and text() or text, nil, nil, nil, true) end
    GameTooltip:Show()
  end)
end

-- The menu: slides out to the left of the game button. Step 1: solo, party or whisper; step 2:
-- how many rounds (whisper: and whose name).
local function ShowMenu(step)
  fly.step, fly.idle = step, 0
  for _, s in pairs(fly.steps) do s:Hide() end
  local s = fly.steps[step]
  s:Show()
  fly.target = s.width
  if not fly:IsShown() then
    fly.w = 1
    fly:SetWidth(1)
    fly:Show()
  end
  if step == "whisper" then
    local name = UnitIsPlayer and UnitIsPlayer("target") and not UnitIsUnit("target", "player") and Gm.UnitFullName("target")
    s.box:SetText(name or s.box:GetText() or "")
    s.box:SetFocus()
    s.box:HighlightText()
  end
end

local function HideMenu()
  if fly then fly.target = 0 end
end

local function Choose(rounds)
  local mode = fly.mode
  local target = mode == "whisper" and fly.steps.whisper.box:GetText() or nil
  if mode == "whisper" then fly.steps.whisper.box:ClearFocus() end
  if Gm.Start(mode, rounds, target) then HideMenu() end
end

local function BuildMenu(parent)
  fly = CreateFrame("Frame", nil, parent, "BackdropTemplate")
  fly:SetPoint("RIGHT", gameButton, "LEFT", -4, 0)
  fly:SetHeight(MENU_H)
  fly:SetClipsChildren(true)
  fly:SetFrameLevel(gameButton:GetFrameLevel() + 2)
  fly:EnableMouse(true)
  if fly.SetBackdrop then
    fly:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8", edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 1 })
    fly:SetBackdropColor(0, 0, 0, 0.8)
    fly:SetBackdropBorderColor(1, 0.82, 0, 0.5)
  end
  fly:Hide()
  fly.steps, fly.w, fly.target = {}, 0, 0
  -- (each step laid out left to right from the menu's left edge: it slides out with it)
  local function Step(name, items)
    local s = CreateFrame("Frame", nil, fly)
    s:SetPoint("TOPLEFT", 0, 0)
    s:SetHeight(MENU_H)
    local x = 4
    for _, it in ipairs(items) do
      it:SetPoint("LEFT", s, "LEFT", x, 0)
      x = x + it:GetWidth() + 3
    end
    s.width = x + 1
    s:SetWidth(s.width)
    s:Hide()
    fly.steps[name] = s
    return s
  end
  local solo = Chip(fly, "Solo", 44, function() fly.mode = "solo" ShowMenu("rounds") end)
  Tip(solo, "Solo", "Play by yourself: your average round score at the end.")
  local party = Chip(fly, "Party", 48, function()
    if not io().group() then return io().print("You're not in a party.") end
    fly.mode = "party"
    ShowMenu("rounds")
  end)
  Tip(party, "Party", function()
    return io().group() and "Invite your party: everyone with StreetView is asked to join." or "|cffff6060Join a party first.|r"
  end)
  local whisper = Chip(fly, "Whisper", 60, function() fly.mode = "whisper" ShowMenu("whisper") end)
  Tip(whisper, "Whisper", "Play against one player: your target, a name you type, or shift-click their name in chat.")
  local link = Chip(fly, "Link", 40, function() fly.mode = "open" ShowMenu("rounds") end)
  Tip(link, "Link", "An open game: post its link in say, guild or a channel, and whoever clicks it joins (they need"
    .. " AzerothGPS StreetView; your realm and faction), up to " .. Gm.MAX_PLAYERS .. " players.")
  local s1 = Step("mode", { solo, party, whisper, link })
  for _, c in ipairs({ solo, party, whisper, link }) do c:SetParent(s1) end

  local function RoundChips(parent)
    local list = {}
    for _, n in ipairs(Gm.ROUNDS) do
      local c = Chip(parent, tostring(n), 24, function() Choose(n) end)
      Tip(c, n == 1 and "1 round" or (n .. " rounds"))
      list[#list + 1] = c
    end
    return list
  end
  local back1 = Chip(fly, "<", 20, function() ShowMenu("mode") end)
  local label = CreateFrame("Frame", nil, fly)
  label:SetSize(46, MENU_H - 6)
  local lt = label:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  lt:SetPoint("CENTER")
  lt:SetText("Rounds")
  local items = { back1, label }
  for _, c in ipairs(RoundChips(fly)) do items[#items + 1] = c end
  local s2 = Step("rounds", items)
  for _, c in ipairs(items) do c:SetParent(s2) end

  local back2 = Chip(fly, "<", 20, function() fly.steps.whisper.box:ClearFocus() ShowMenu("mode") end)
  local box = CreateFrame("EditBox", nil, fly, "InputBoxTemplate")
  box:SetSize(96, 18)
  box:SetAutoFocus(false)
  box:SetMaxLetters(48)
  box:SetScript("OnEscapePressed", function(self) self:ClearFocus() HideMenu() end)
  box:SetScript("OnEnterPressed", function(self) self:ClearFocus() Choose(3) end)
  local spacer = CreateFrame("Frame", nil, fly) -- (InputBoxTemplate's border sticks out on the left)
  spacer:SetSize(4, 1)
  local items3 = { back2, spacer, box }
  for _, c in ipairs(RoundChips(fly)) do items3[#items3 + 1] = c end
  local s3 = Step("whisper", items3)
  for _, c in ipairs(items3) do c:SetParent(s3) end
  s3.box = box

  -- the slide: the width eases toward its target (0: closing); left open with nothing chosen and
  -- the mouse elsewhere for Gm.MENU_IDLE_SECONDS, it closes by itself (typing a name counts as using it)
  fly:SetScript("OnUpdate", function(self, dt)
    if self.target > 0 then
      local busy = self:IsMouseOver() or gameButton:IsMouseOver() or box:HasFocus()
      self.idle = busy and 0 or (self.idle or 0) + dt
      if self.idle >= Gm.MENU_IDLE_SECONDS then HideMenu() end
    end
    local w = self.w + (self.target - self.w) * math.min(1, dt * MENU_EASE)
    if math.abs(self.target - w) < 0.5 then w = self.target end
    self.w = w
    if w < 1 and self.target == 0 then
      self:Hide()
      return
    end
    self:SetWidth(math.max(1, w))
  end)
end

-- The panel: where the directions are, while a game is on.
local ROWS = Gm.BOARD_ROWS_MAX + 1 -- (the rows' font strings: the most shown, and this player's own below them)

local function BuildPanel(parent)
  panel = CreateFrame("Frame", nil, parent, "BackdropTemplate")
  panel:SetPoint("TOPLEFT", 4, -4)
  panel:SetPoint("TOPRIGHT", -4, -4)
  panel:SetHeight(60)
  panel:SetFrameLevel(parent:GetFrameLevel() + 30)
  panel:EnableMouse(true) -- (clicks on it aren't the map's)
  if panel.SetBackdrop then
    panel:SetBackdrop({ bgFile = "Interface\\Buttons\\WHITE8X8" })
    panel:SetBackdropColor(0, 0, 0, 0.75)
  end
  panel:Hide()
  -- the celebration: a soft glow around the panel, its colors drifting
  local glow = CreateFrame("Frame", nil, panel, "BackdropTemplate")
  glow:SetPoint("TOPLEFT", -3, 3)
  glow:SetPoint("BOTTOMRIGHT", 3, -3)
  glow:SetFrameLevel(panel:GetFrameLevel() - 1)
  if glow.SetBackdrop then
    glow:SetBackdrop({ edgeFile = "Interface\\Buttons\\WHITE8X8", edgeSize = 3 })
  end
  glow:Hide()
  panel.glow = glow
  local wash = panel:CreateTexture(nil, "BORDER")
  wash:SetAllPoints()
  wash:SetColorTexture(1, 1, 1, 0)
  wash:Hide()
  panel.wash = wash

  panel.title = panel:CreateFontString(nil, "OVERLAY", "GameFontNormal")
  panel.title:SetPoint("TOPLEFT", 6, -6)
  panel.title:SetJustifyH("LEFT")
  panel.timer = panel:CreateFontString(nil, "OVERLAY", "GameFontNormalLarge")
  panel.timer:SetPoint("TOPRIGHT", -28, -4)
  panel.timer:SetJustifyH("RIGHT")
  local close = CreateFrame("Button", nil, panel, "UIPanelCloseButton")
  close:SetSize(22, 22)
  close:SetPoint("TOPRIGHT", 0, -1)
  close:SetScript("OnClick", function() Gm.Leave() end)
  close:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_TOP")
    local over = game and game.phase == "over"
    GameTooltip:SetText(over and "Close" or (game and game.isHost and game.mode ~= "solo" and "End the game" or "Leave the game"), 1, 1, 1)
    GameTooltip:AddLine("Back to the map, and to your route if you had one.", nil, nil, nil, true)
    GameTooltip:Show()
  end)
  close:SetScript("OnLeave", GameTooltip_Hide)
  panel.status = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  panel.status:SetPoint("TOPLEFT", panel.title, "BOTTOMLEFT", 0, -4)
  panel.status:SetPoint("RIGHT", -8, 0)
  panel.status:SetJustifyH("LEFT")
  panel.rows = {}
  for i = 1, ROWS do
    local r = {}
    r.name = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    r.name:SetJustifyH("LEFT")
    r.total = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    r.total:SetJustifyH("RIGHT")
    r.last = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
    r.last:SetJustifyH("RIGHT")
    r.name:SetPoint("LEFT", panel, "LEFT", 10, 0)
    r.total:SetPoint("RIGHT", panel, "RIGHT", -10, 0)
    r.last:SetPoint("RIGHT", panel, "RIGHT", -64, 0)
    panel.rows[i] = r
  end
  -- the scoreboard's "+" / "-": more players shown, or the top three again (the same buttons as
  -- AzerothGPS's dungeon floor ones; on the row with the panel's other buttons)
  local okT, toggle = pcall(CreateFrame, "Button", nil, panel, "UIPanelButtonTemplate")
  if not okT or not toggle then toggle = Chip(panel, "+", 28) end
  toggle:SetSize(28, 20)
  toggle:SetText("+")
  toggle:SetScript("OnClick", function()
    panel.expanded = not panel.expanded
    Gm.Refresh()
  end)
  toggle:SetScript("OnLeave", GameTooltip_Hide)
  toggle:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_TOP")
    GameTooltip:SetText(panel.expanded and ("Show the top " .. Gm.BOARD_ROWS) or ("Show up to " .. Gm.BOARD_ROWS_MAX .. " players"), 1, 1, 1)
    GameTooltip:Show()
  end)
  toggle:Hide()
  panel.boardToggle = toggle
  local ok, start = pcall(CreateFrame, "Button", nil, panel, "UIPanelButtonTemplate")
  if not ok or not start then start = Chip(panel, "Start now", 90) end
  start:SetSize(90, 20)
  start:SetText("Start now")
  start:SetScript("OnClick", function() Gm.StartNow() end)
  start:Hide()
  panel.start = start
  -- an open game's host: post the link (where: say, guild, the group, the numbered channels joined)
  panel.postLabel = panel:CreateFontString(nil, "OVERLAY", "GameFontHighlightSmall")
  panel.postLabel:SetText("Post the link:")
  panel.postLabel:Hide()
  panel.posts = {}
  local function Post(text, width, chatType, index, tip)
    local b = Chip(panel, text, width, function() Gm.PostLink(chatType, index) end)
    Tip(b, "Post the link in " .. tip, "Players with AzerothGPS StreetView click it to join.")
    b.shown = function()
      if chatType == "GUILD" then return IsInGuild and IsInGuild() end
      if chatType == "PARTY" then return IsInGroup and IsInGroup() and not (IsInRaid and IsInRaid()) end
      if chatType == "RAID" then return IsInRaid and IsInRaid() end
      if chatType == "CHANNEL" then
        local n, name = GetChannelName(index)
        if not n or n == 0 or not name then return false end
        b.label:SetText((name:match("^([^%-]+)") or name):gsub("%s+$", ""))
        b:SetWidth(math.max(44, b.label:GetStringWidth() + 14))
        return true
      end
      return true
    end
    b:Hide()
    panel.posts[#panel.posts + 1] = b
  end
  Post("Say", 36, "SAY", nil, "say")
  Post("Guild", 44, "GUILD", nil, "guild chat")
  Post("Party", 44, "PARTY", nil, "party chat")
  Post("Raid", 40, "RAID", nil, "raid chat")
  for i = 1, 4 do Post("/" .. i, 44, "CHANNEL", i, "chat channel " .. i) end
  -- solo: done guessing before the time runs out
  local ok2, submit = pcall(CreateFrame, "Button", nil, panel, "UIPanelButtonTemplate")
  if not ok2 or not submit then submit = Chip(panel, "Submit guess", 100) end
  submit:SetSize(100, 20)
  submit:SetText("Submit guess")
  submit:SetScript("OnClick", function() Gm.SubmitNow() end)
  submit:Hide()
  panel.submit = submit
  -- this round's street view closed during the round: open it again
  local ok3, reopen = pcall(CreateFrame, "Button", nil, panel, "UIPanelButtonTemplate")
  if not ok3 or not reopen then reopen = Chip(panel, "Show Street View", 120) end
  reopen:SetSize(120, 20)
  reopen:SetText("Show Street View")
  reopen:SetScript("OnClick", function() Gm.ShowAgain() end)
  reopen:Hide()
  panel.reopen = reopen
  for _, fn in ipairs(Gm.panelHooks) do fn(panel) end
end

-- More buttons on the game's panel (the dev addon's): fn(panel) once it's built; a button added to
-- Gm.extraButtons as { button, shown = function(game), refresh = function(game) } is laid out with the rest.
Gm.panelHooks, Gm.extraButtons = {}, {}
function Gm.OnPanel(fn)
  if panel then fn(panel) else Gm.panelHooks[#Gm.panelHooks + 1] = fn end
end

-- One line about this player's guess.
local function GuessLine(g)
  if not g then return "" end
  if g.none then return "|cffff8080No guess in time: 0 points|r" end
  if not g.yards then return "|cffff8080Another continent: 0 points|r" end
  return string.format("|cffffffff%s yards away:|r |cffffd100%d points|r", Gm.Yards(g.yards), g.score)
end

local function ScoreColor(n)
  if not n then return "|cff808080" end
  if n >= 90 then return "|cff40ff40" elseif n >= 60 then return "|cffc0ff60" elseif n >= 30 then return "|cffffd100" end
  return "|cffff9060"
end

-- Where the panel starts: right of the map window frame's round portrait when that shows (as
-- AzerothGPS's own top panel does).
local function PanelLeft()
  if API.TopPanelInset then return API.TopPanelInset() end
  local f = API.MapFrame and API.MapFrame()
  if f then
    for _, c in ipairs({ f:GetChildren() }) do
      if c:IsShown() and (c.PortraitContainer or c.GetPortrait) then return 46 end
    end
  end
  return 4
end

-- Redraw the panel from the game's state.
function Gm.Refresh()
  if not panel then return end
  if not game then
    panel:Hide()
    return
  end
  panel:ClearAllPoints()
  panel:SetPoint("TOPLEFT", PanelLeft(), -4)
  panel:SetPoint("TOPRIGHT", -4, -4)
  panel:Show()
  local ph = game.phase
  -- (a game started, by the menu or an invitation accepted: the menu folds away)
  if ph ~= "over" and fly and fly:IsShown() and fly.target > 0 then HideMenu() end
  local roundText = game.round > 0 and string.format("  |cffffffffRound %d of %d|r", game.round, game.rounds) or ""
  panel.title:SetText("|cffffd100Where in the Azeroth?|r" .. roundText)
  local status
  if ph == "invite" then
    local n = #game.order - 1
    if game.open then
      status = string.format("Open game: %d joined so far (up to %d). Post the link: whoever clicks it joins.",
        n, Gm.MAX_PLAYERS - 1)
    else
      status = game.mode == "whisper" and ("Waiting for " .. Short(game.target) .. " to answer...")
        or string.format("Invited your party: %d joined so far.", n)
    end
  elseif ph == "joined" then
    status = game.open and not game.startAt and ("Joining " .. Short(game.host) .. "'s game...")
      or ("You joined " .. Short(game.host) .. "'s game. It starts when the countdown ends.")
  elseif ph == "propose" or ph == "ready" then
    status = "Getting the next street view ready..."
  elseif ph == "look" then
    status = game.missing and "|cffff8080You don't have this street view (update AzerothGPS StreetView): guess anyway!|r"
      or (game.pending and (game.mode == "solo" and "Guess placed. |cffffd100Double-click|r again to move it, or submit it."
          or "Guess placed. |cffffd100Double-click|r again to move it; it counts when the time runs out.")
        or "Where is this? |cffffd100Double-click the map|r where you think it is.")
  elseif ph == "wait" then
    status = GuessLine(game.guess) .. "\n|cff9d9d9dWaiting for the others...|r"
  elseif ph == "result" then
    status = GuessLine(game.guess) -- (the countdown to the next round: the panel's timer)
  elseif ph == "over" then
    if game.reason then
      status = "|cffff8080" .. game.reason .. "|r"
    elseif game.mode == "solo" then
      local avg = Gm.Average(game)
      status = string.format("Average round score: %s%d|r", ScoreColor(avg), avg)
        .. (game.celebrate and "  |cffffd100Well done!|r" or "")
    else
      local w = game.winners or {}
      if #w == 0 then
        status = "No one scored."
      elseif #w == 1 then
        status = (w[1] == game.me and "|cffffd100You win!|r" or ("|cffffd100" .. Short(w[1]) .. " wins!|r"))
      else
        local names = {}
        for _, n in ipairs(w) do names[#names + 1] = Short(n) end
        status = "|cffffd100A tie: " .. table.concat(names, " and ") .. "!|r"
      end
      if game.guess and game.mode ~= "solo" then status = GuessLine(game.guess) .. "\n" .. status end
    end
  end
  -- who lacks which pack (their street views aren't used)
  local lacks = {}
  for _, r in ipairs(game.report or {}) do
    local what = {}
    for _, k in ipairs(r.missing) do what[#what + 1] = Gm.PackTitle(k) end
    for _, k in ipairs(r.older) do what[#what + 1] = "older " .. Gm.PackTitle(k) end
    lacks[#lacks + 1] = (r.name == game.me and "You" or Short(r.name)) .. ": " .. table.concat(what, ", ")
  end
  if #lacks > 0 then
    status = (status or "") .. "\n|cffff9060Missing map packs|r |cff9d9d9d(their street views aren't used)|r\n|cffffb080"
      .. table.concat(lacks, "\n") .. "|r"
  end
  panel.status:SetText(status or "")
  -- the players (solo: the rounds' scores)
  local rowsShown = 0
  local y = -8 - panel.title:GetStringHeight() - 4 - panel.status:GetStringHeight() - 6
  if game.mode == "solo" then
    local pl = game.players[game.me]
    if pl and game.round > 0 then
      local parts = {}
      for r = 1, game.round do
        local sc = pl.scores[r]
        parts[#parts + 1] = sc and (ScoreColor(sc) .. sc .. "|r") or "|cff808080-|r"
      end
      local row = panel.rows[1]
      -- (each round's score, not rounds left: the user read "Rounds: 0" as that)
      row.name:SetText((#parts > 1 and "Round scores: " or "Round score: ") .. table.concat(parts, ", "))
      row.last:SetText("")
      row.total:SetText(ph == "over" and "" or string.format("Average %d", Gm.Average(game)))
      row.name:ClearAllPoints()
      row.name:SetPoint("TOPLEFT", panel, "TOPLEFT", 10, y)
      row.total:ClearAllPoints()
      row.total:SetPoint("TOPRIGHT", panel, "TOPRIGHT", -10, y)
      rowsShown = 1
    end
  else
    -- (until a round's result, its points stay hidden: the others only show that they guessed, and
    -- the totals and the order are the earlier rounds')
    local open = ph ~= "result" and ph ~= "over"
    local list = Gm.Standings(game, open and math.max(0, game.round - 1) or nil)
    local showScores = game.round > 0
    -- (the same points shown with decimals: the closer guess higher)
    local rs, ts = {}, {}
    for i, s in ipairs(list) do
      local pl = game.players[s.name]
      rs[i] = pl.scores[game.round] and { pl.scores[game.round], Gm.RoundFine(pl, game.round) } or { -1 - i }
      ts[i] = { s.total, s.fine }
    end
    local roundText, totalText = Gm.ShowTied(rs), Gm.ShowTied(ts)
    if panel.boardGame ~= game.id then panel.boardGame, panel.expanded = game.id, false end -- (a new game: 3 again)
    local mine
    for i, s in ipairs(list) do
      if s.name == game.me then mine = i end
    end
    local ranks = Gm.BoardRows(#list, mine, panel.expanded)
    for k, i in ipairs(ranks) do
      local s = list[i]
      local row = panel.rows[k]
      local me = s.name == game.me
      local cur = game.players[s.name] and game.players[s.name].scores[game.round]
      local done = cur ~= nil
      local lastText = ""
      if showScores then
        if ph == "result" or ph == "over" or me then
          lastText = done and (ScoreColor(cur) .. "+" .. ((ph == "result" or ph == "over") and roundText[i] or cur) .. "|r")
            or "|cff808080-|r"
        else
          lastText = done and "|cff40ff40guessed|r" or "|cff808080...|r"
        end
      end
      row.name:SetText(string.format("%d. %s%s|r%s", i, Gm.ColorCode(Gm.PlayerColor(game, s.name)), Short(s.name),
        me and " |cff9d9d9d(you)|r" or ""))
      row.last:SetText(lastText)
      row.total:SetText(showScores and totalText[i] or "")
      row.name:ClearAllPoints()
      row.name:SetPoint("TOPLEFT", panel, "TOPLEFT", 10, y - (k - 1) * 14)
      row.last:ClearAllPoints()
      row.last:SetPoint("TOPRIGHT", panel, "TOPRIGHT", -52, y - (k - 1) * 14)
      row.total:ClearAllPoints()
      row.total:SetPoint("TOPRIGHT", panel, "TOPRIGHT", -10, y - (k - 1) * 14)
      rowsShown = k
    end
    -- "+": more of the players (up to Gm.BOARD_ROWS_MAX); "-": back to the top Gm.BOARD_ROWS
    local more = #list > Gm.BOARD_ROWS
    panel.boardToggle:SetShown(more)
    if more then panel.boardToggle:SetText(panel.expanded and "-" or "+") end
  end
  if game.mode == "solo" then panel.boardToggle:Hide() end
  for i = 1, ROWS do
    local row = panel.rows[i]
    local on = i <= rowsShown
    row.name:SetShown(on)
    row.last:SetShown(on)
    row.total:SetShown(on)
  end
  local h = -y + rowsShown * 14 + 4
  panel.start:SetShown(game.isHost and ph == "invite" and #game.order > 1)
  if panel.start:IsShown() then
    panel.start:ClearAllPoints()
    panel.start:SetPoint("TOPLEFT", panel, "TOPLEFT", 8, -h)
    h = h + 24
  end
  local posting = game.isHost and game.open and ph == "invite"
  panel.postLabel:SetShown(posting)
  local cooling = posting and game.postedAt and Now() - game.postedAt < Gm.POST_COOLDOWN
  local x = 8
  if posting then
    panel.postLabel:ClearAllPoints()
    panel.postLabel:SetPoint("TOPLEFT", panel, "TOPLEFT", x, -h - 4)
    x = x + panel.postLabel:GetStringWidth() + 6
  end
  for _, b in ipairs(panel.posts) do
    local on = posting and b.shown() and true or false
    b:SetShown(on)
    if on then
      b:ClearAllPoints()
      b:SetPoint("TOPLEFT", panel, "TOPLEFT", x, -h)
      b:SetAlpha(cooling and 0.4 or 1)
      x = x + b:GetWidth() + 3
    end
  end
  if posting then h = h + 22 end
  panel.submit:SetShown(game.mode == "solo" and ph == "look" and game.pending ~= nil)
  local reopen = (ph == "look" or ph == "wait" or ph == "result" or ph == "over") and game.spot ~= nil
    and not game.missing and not (ns.Viewer.Current() and ns.Viewer.Current().game)
  panel.reopen:SetShown(reopen)
  local list, extra = { panel.boardToggle, panel.submit, panel.reopen }, panel.boardToggle:IsShown()
  for _, e in ipairs(Gm.extraButtons) do
    local on = e.shown(game) and true or false
    e.button:SetShown(on)
    if on then
      extra = true
      if e.refresh then e.refresh(game) end
    end
    list[#list + 1] = e.button
  end
  if panel.submit:IsShown() or reopen or extra then
    local x = 8
    for _, b in ipairs(list) do
      if b:IsShown() then
        b:ClearAllPoints()
        b:SetPoint("TOPLEFT", panel, "TOPLEFT", x, -h)
        x = x + b:GetWidth() + 6
      end
    end
    h = h + 24
  end
  panel:SetHeight(math.max(40, h))
  panel.glow:SetShown(game.celebrate == true)
  panel.wash:SetShown(game.celebrate == true)
  Gm.RefreshTimer()
end

function Gm.RefreshTimer()
  local V = ns.Viewer
  if not panel or not game then
    if V and V.SetTimer then V.SetTimer(nil) end
    return
  end
  local ph = game.phase
  if ph == "result" and game.deadline and game.round < game.rounds then -- (the next round, counted down)
    panel.timer:SetText("|cff9d9d9dnext round in " .. Clock(game.deadline - Now()) .. "|r")
    if V and V.SetTimer then V.SetTimer(nil) end
    return
  end
  if ph == "over" and game.closeAt then -- (closing by itself)
    panel.timer:SetText("|cff9d9d9dcloses in " .. Clock(game.closeAt - Now()) .. "|r")
    if V and V.SetTimer then V.SetTimer(nil) end
    return
  end
  if (ph == "look" or ph == "wait" or ph == "result" or ph == "over") and panel.reopen then
    local want = not game.missing and not (V and V.Current() and V.Current().game)
    if want ~= panel.reopen:IsShown() then Gm.Refresh() end
  end
  if ph == "invite" or ph == "joined" then -- (the lobby: when the game starts, the same for everyone)
    local at = ph == "invite" and game.deadline or game.startAt
    if at then
      local left = at - Now()
      panel.timer:SetText("|cff9d9d9dstarts in|r " .. (left <= 5 and "|cffff5050" or "|cffffffff") .. Clock(left) .. "|r")
      if game.postedAt and ph == "invite" and Now() - game.postedAt >= Gm.POST_COOLDOWN and panel.postLabel:IsShown()
        and not game.postReady then
        game.postReady = true -- (the post buttons bright again)
        Gm.Refresh()
      end
    else
      panel.timer:SetText("")
    end
    if V and V.SetTimer then V.SetTimer(nil) end
  elseif ph == "look" and game.deadline then
    local left = game.deadline - Now()
    local color = left <= 5 and "|cffff5050" or "|cffffd100"
    panel.timer:SetText(color .. Clock(left) .. "|r")
    if V and V.SetTimer then V.SetTimer(color .. Clock(left) .. "|r") end
  else
    panel.timer:SetText("")
    if V and V.SetTimer then V.SetTimer(nil) end
  end
end

-- The drift of the celebration's colors.
local function Celebrate(t)
  local n = #CELEBRATE
  local f = (t * 0.35) % n
  local i = math.floor(f)
  local k = f - i
  local a, b = CELEBRATE[i + 1], CELEBRATE[(i + 1) % n + 1]
  local r, g, bl = a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k, a[3] + (b[3] - a[3]) * k
  local pulse = 0.55 + 0.35 * math.sin(t * 2.4)
  if panel.glow.SetBackdropBorderColor then panel.glow:SetBackdropBorderColor(r, g, bl, pulse) end
  panel.wash:SetColorTexture(r, g, bl, 0.08 + 0.05 * math.sin(t * 2.4))
end

-- The game button: above the figure on the map.
local function BuildButton(parent, figure)
  gameButton = CreateFrame("Button", nil, parent)
  gameButton:SetSize(28, 28)
  -- (placed by Figure.lua: under the figure, in AzerothGPS's bottom-right column)
  local icon = gameButton:CreateTexture(nil, "ARTWORK") -- (the orc on a black circle: Media/GameIcon.tga)
  icon:SetAllPoints()
  icon:SetTexture("Interface\\AddOns\\AzerothGPS_StreetView\\Media\\GameIcon")
  gameButton:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
  gameButton:RegisterForClicks("LeftButtonUp")
  gameButton:SetScript("OnClick", function()
    if fly:IsShown() and fly.target > 0 then return HideMenu() end -- (open: the click closes it, game or not)
    if game then
      if game.phase == "over" then Gm.Leave() else io().print("A game is on: its X leaves it.") end
      return
    end
    if fly:IsShown() and fly.target > 0 then HideMenu() else ShowMenu("mode") end
  end)
  gameButton:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:AddLine("Where in the Azeroth?")
    GameTooltip:AddLine("Where is this street view? You have 30 seconds to look around and double-click the map where you think it is (again to move it).", 1, 1, 1, true)
    GameTooltip:AddLine("Solo, with your party, or with one player by whisper.", 0.8, 0.8, 0.8, true)
    GameTooltip:Show()
  end)
  gameButton:SetScript("OnLeave", GameTooltip_Hide)
end

-- The map's markers for the game (Gm.marks): textures on AzerothGPS's map canvas, placed on every
-- redraw at the points Gm.Draw gives. A guess is an animated orc (Media/Guess<n>.tga: its frames
-- side by side, one a second), the answer the star the routes use for their stops.
local GUESS_TEX = "Interface\\AddOns\\AzerothGPS_StreetView\\Media\\Guess"
local GUESS_FRAMES, GUESS_SHEET_FRAMES, GUESS_FRAME_SECONDS = 2, 2, 1 -- (each 128 wide: 2 frames of 64)
local STAR_TEX = "Interface\\TargetingFrame\\UI-RaidTargetingIcon_1"
local function BuildMarks(canvas)
  local layer = CreateFrame("Frame", nil, canvas)
  layer:SetAllPoints()
  layer:SetFrameLevel(canvas:GetFrameLevel() + 25)
  local pool, used = { guess = {}, answer = {}, label = {}, hot = {} }, { guess = 0, answer = 0, label = 0, hot = 0 }
  local function Get(kind)
    local n = used[kind] + 1
    used[kind] = n
    local t = pool[kind][n]
    if not t then
      t = layer:CreateTexture(nil, "OVERLAY")
      if kind == "guess" then
        t:SetSize(30, 30)
      else
        t:SetTexture(STAR_TEX)
        t:SetSize(22, 22)
      end
      pool[kind][n] = t
    end
    return t
  end
  local M = {}
  function M.Begin() used.guess, used.answer, used.label, used.hot = 0, 0, 0, 0 end
  -- a spot over a player's marker that shows their name and scores when the mouse is on it
  function M.Hot(sx, sy, name)
    local n = used.hot + 1
    used.hot = n
    local f = pool.hot[n]
    if not f then
      f = CreateFrame("Frame", nil, layer)
      f:SetSize(26, 26)
      f:EnableMouse(true)
      f:SetScript("OnEnter", function(self)
        if not (GameTooltip and game) then return end
        GameTooltip:SetOwner(self, "ANCHOR_RIGHT")
        for i, l in ipairs(Gm.PlayerTip(game, self.name)) do
          if i == 1 then GameTooltip:SetText(l[1], l[2], l[3], l[4]) else GameTooltip:AddLine(l[1], l[2], l[3], l[4]) end
        end
        GameTooltip:Show()
      end)
      f:SetScript("OnLeave", function() if GameTooltip then GameTooltip:Hide() end end)
      pool.hot[n] = f
    end
    f.name = name
    f:ClearAllPoints()
    f:SetPoint("CENTER", layer, "CENTER", sx, sy)
    f:Show()
  end
  -- a player's name by their guess
  function M.Label(sx, sy, text, c)
    local n = used.label + 1
    used.label = n
    local f = pool.label[n]
    if not f then
      f = layer:CreateFontString(nil, "OVERLAY", "GameFontNormalSmall")
      f:SetShadowOffset(1, -1)
      pool.label[n] = f
    end
    f:SetText(text)
    f:SetTextColor(c[1], c[2], c[3])
    f:ClearAllPoints()
    f:SetPoint("BOTTOM", layer, "CENTER", sx, sy + 7)
    f:Show()
  end
  function M.Put(kind, sx, sy, orc)
    local t = Get(kind)
    if kind == "guess" and t.orc ~= (orc or 1) then
      t.orc = orc or 1
      t:SetTexture(GUESS_TEX .. t.orc)
    end
    t:ClearAllPoints()
    t:SetPoint("CENTER", layer, "CENTER", sx, sy + (kind == "guess" and 8 or 0)) -- (the orc sits on the spot)
    t:Show()
  end
  function M.End()
    for kind, list in pairs(pool) do
      for i = used[kind] + 1, #list do list[i]:Hide() end
    end
  end
  -- the orc's frames (the driver calls this every tenth of a second)
  function M.Animate(now)
    local f = math.floor(now / GUESS_FRAME_SECONDS) % GUESS_FRAMES
    local w = 1 / GUESS_SHEET_FRAMES
    for _, t in ipairs(pool.guess) do t:SetTexCoord(f * w, (f + 1) * w, 0, 1) end
  end
  function M.Clear()
    M.Begin()
    M.End()
  end
  return M
end

-- The invitation, asked before joining.
local function Ask(sender, rounds, onYes, onNo)
  if not (StaticPopupDialogs and StaticPopup_Show) then
    io().print(Short(sender) .. " invited you to play Where in the Azeroth?, but this client can't ask: declined.")
    return onNo()
  end
  StaticPopupDialogs.AGPS_STREETGUESS_INVITE = StaticPopupDialogs.AGPS_STREETGUESS_INVITE or {
    text = "%s invites you to play Where in the Azeroth? (%s). Join?",
    button1 = "Join",
    button2 = "No thanks",
    OnAccept = function(self, data) local d = data or self.data if d then d.yes() end end,
    OnCancel = function(self, data) local d = data or self.data if d then d.no() end end,
    timeout = Gm.JOIN_SECONDS,
    whileDead = true,
    hideOnEscape = true,
    preferredIndex = 3,
  }
  local answered = false
  local data = {
    yes = function() if not answered then answered = true onYes() end end,
    no = function() if not answered then answered = true onNo() end end,
  }
  local dlg = StaticPopup_Show("AGPS_STREETGUESS_INVITE", Short(sender), rounds == 1 and "1 round" or (rounds .. " rounds"), data)
  if dlg then dlg.data = data else data.no() end
end

function Gm.Init(figureButton)
  if gameButton then return end
  API = _G.AzerothGPS
  if type(API) ~= "table" or not API.MapButtonParent then return end
  local parent = API.MapButtonParent()
  if not parent or not figureButton then return end
  if not API.HoldMap then -- (an AzerothGPS without the game's API: no game)
    ns.Print("Where in the Azeroth? needs a newer AzerothGPS (API version 3).")
    return
  end
  BuildButton(parent, figureButton)
  BuildMenu(parent)
  BuildPanel(parent)

  local io_ = Gm.io
  io_.open = function(p, heading) ns.Viewer.Open(p, heading, true) end
  io_.close = function() ns.Viewer.CloseGame() end
  io_.hold = function(on)
    API.HoldMap("StreetGuess", on, function(x, y, cont) Gm.Guess(x, y, API.BaseContinent(cont)) end)
  end
  io_.lookAt = function(cont, x, y, zoom) if API.LookAt then API.LookAt(cont, x, y, zoom) end end
  io_.view = function() -- the map's center, continent (the base one) and zoom (yards to the edge)
    local x, y, c, _, sc, half = API.View()
    if x and sc and sc > 0 and half then return x, y, API.BaseContinent(c), half / sc end
  end
  -- the map as it is: following the player (its center on them), or where it looks
  io_.mapState = function()
    local saved = API.SaveView and API.SaveView() -- (the whole view: restored by io_.restore)
    local x, y, c, zoom = io_.view()
    if not x then return saved and { saved = saved } or nil end
    local px, py, pc = API.PlayerWorld()
    local following = px ~= nil and API.BaseContinent(pc) == c and (px - x) ^ 2 + (py - y) ^ 2 < 25
    return { following = following, x = x, y = y, cont = c, zoom = zoom, saved = saved }
  end
  if API.RestoreView then io_.restore = function(saved) API.RestoreView(saved) end end
  io_.world = function(s) -- (the start of a round; a guess on another continent: the whole world)
    if API.ShowWorld then API.ShowWorld() elseif s and API.LookAt then API.LookAt(s.cont, s.x, s.y, 6000) end
  end
  io_.follow = function() if API.Follow then API.Follow() end end
  io_.showMap = function() if API.ShowMap then API.ShowMap() end end
  io_.changed = function()
    if not game and Gm.marks then Gm.marks.Clear() end
    Gm.Refresh()
    if ns.Figure then ns.Figure.Refresh() end
    API.Redraw()
  end
  io_.ask = Ask

  local canvas = API.MapCanvas and API.MapCanvas()
  if canvas then Gm.marks = BuildMarks(canvas) end
  Gm.Usable = function(p)
    if Gm.Skip and Gm.Skip(p) then return false end -- (the dev addon's reported pictures)
    return not (D.loadable and not D.loadable[p.id])
  end
  API.SetOverlay("StreetGuess", Gm.Draw)
  -- Whisper: shift-click a player's name in chat to fill the name box
  if hooksecurefunc and SetItemRef then
    hooksecurefunc("SetItemRef", function(link)
      local box = fly and fly.steps.whisper and fly.steps.whisper.box
      if not (box and fly:IsShown() and fly.step == "whisper") then return end
      local shift = (IsModifiedClick and IsModifiedClick("CHATLINK")) or (IsShiftKeyDown and IsShiftKeyDown())
      local name = shift and type(link) == "string" and link:match("^player:([^:]+)")
      if name then
        box:SetText(name)
        box:SetFocus()
        box:SetCursorPosition(#name)
      end
    end)
  end
  if API.OnLayout then API.OnLayout("StreetGuess", function() Gm.Refresh() end) end -- (the frame's portrait on or off)

  if C_ChatInfo and C_ChatInfo.RegisterAddonMessagePrefix then C_ChatInfo.RegisterAddonMessagePrefix(Gm.PREFIX) end
  -- an open game's link: its code in chat shown as a link to click; the click joins (the
  -- "garrmission" link type: the game's own click handling leaves it alone)
  if ChatFrame_AddMessageEventFilter then
    local function Linkify(_, _, msg, author, ...)
      if type(msg) == "string" and msg:find("AGPSSV%-%d") then
        local new = Gm.Linkify(msg, author)
        if new ~= msg then return false, new, author, ... end
      end
      return false
    end
    for _, e in ipairs({ "CHAT_MSG_SAY", "CHAT_MSG_YELL", "CHAT_MSG_GUILD", "CHAT_MSG_OFFICER", "CHAT_MSG_PARTY",
      "CHAT_MSG_PARTY_LEADER", "CHAT_MSG_RAID", "CHAT_MSG_RAID_LEADER", "CHAT_MSG_RAID_WARNING", "CHAT_MSG_WHISPER",
      "CHAT_MSG_WHISPER_INFORM", "CHAT_MSG_CHANNEL" }) do
      ChatFrame_AddMessageEventFilter(e, Linkify)
    end
    -- (the game's hidden channel: no "joined channel" lines)
    local function Hidden(_, _, ...)
      for i = 1, select("#", ...) do
        local v = select(i, ...)
        if type(v) == "string" and v:find("AGPSSV%d%d%d") then return true end
      end
      return false
    end
    ChatFrame_AddMessageEventFilter("CHAT_MSG_CHANNEL_NOTICE", Hidden)
    ChatFrame_AddMessageEventFilter("CHAT_MSG_CHANNEL_NOTICE_USER", Hidden)
  end
  if hooksecurefunc and SetItemRef then
    hooksecurefunc("SetItemRef", function(link)
      if type(link) == "string" and link:find("^garrmission:agpssv:") then
        local ok, err = pcall(Gm.OnLink, link)
        if not ok then ns.Print("|cffff6060joining failed:|r " .. tostring(err)) end
      end
    end)
  end
  local ev = CreateFrame("Frame")
  ev:RegisterEvent("CHAT_MSG_ADDON")
  ev:RegisterEvent("GROUP_ROSTER_UPDATE")
  ev:SetScript("OnEvent", function(_, event, prefix, msg, channel, sender)
    if event == "CHAT_MSG_ADDON" then
      if prefix == Gm.PREFIX then
        local ok, err = pcall(Gm.OnMessage, msg, channel, sender)
        if not ok then ns.Print("|cffff6060game message failed:|r " .. tostring(err)) end
      end
    else
      pcall(Gm.OnRoster)
    end
  end)

  -- the clock, the timer text, the reveal and the celebration
  local acc, t = 0, 0
  local driver = CreateFrame("Frame")
  driver:SetScript("OnUpdate", function(_, dt)
    t = t + dt
    if not game then return end
    acc = acc + dt
    if acc >= 0.1 then
      acc = 0
      local ok, err = pcall(Gm.Tick)
      if not ok then ns.Print("|cffff6060game clock failed:|r " .. tostring(err)) end
      Gm.RefreshTimer()
      if Gm.marks then Gm.marks.Animate(GetTime()) end
    end
    if game and game.pan then Gm.Animate() end
    if game and game.reveal and Now() - game.reveal.t0 <= Gm.REVEAL_SECONDS + 0.1 then API.Redraw() end
    if game and game.celebrate and panel:IsShown() then Celebrate(t) end
  end)
  return gameButton
end
