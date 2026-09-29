-- Street Guess: a GeoGuessr-style game on the AzerothGPS map. Everyone gets the same street view
-- (no zone name or coordinates) and has 30 seconds to look around and double-click the map where
-- they think it is (again to move the guess: the one placed when the time runs out counts): the
-- closer, the more points (0-100 a round, the first ones easy, the last hard).
-- Street views come only from the map packs every player has; the panel says who lacks which.
-- Solo, with the party, or with one player by whisper; 1, 3 or 5 rounds.
--
-- While a game is on, the map is held (AzerothGPS.HoldMap): the route and its directions panel
-- aren't shown (the route goes on; the arrow window still guides) and the game's panel takes the
-- directions' place; its X leaves the game and brings the route back.
--
-- Players talk through addon messages (prefix "AGPSSV", to the party or the one player whispered)
-- and only about the game: an invitation is always asked before joining. The host picks the
-- street views and paces the rounds; each player scores their own guess and tells the others.
--   I:id:rounds:packs      invitation (host)          J:id:packs / D:id / B:id   join / decline / busy
--   K:id:name:packs        a player's packs (host)    (packs: Kalimdor/2026.09.29,EasternKingdoms/...)
--   L:id:name,name,...     the players (host)         Q:id                 a player left
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
Gm.RESULT_SECONDS = 7 -- the round's result, before the next round
Gm.JOIN_SECONDS = 20 -- the host waits this long for answers to an invitation
Gm.PROPOSE_SECONDS = 3 -- ... and this long for the players to say they have the next street view
Gm.GRACE_SECONDS = 3 -- a round ends this long after the guessing time, whoever hasn't answered
Gm.MAX_TRIES = 5 -- street views tried until everyone has one
Gm.FULL_YD = 25 -- a guess this close gets all 100 points
Gm.SCALE_YD = 3000 -- ... then 100 * e^(-(yards - 25) / 3000): 90 points ~340 yd off, 60 ~1,550, 40 ~2,800
Gm.TERRAIN_MAX_YD = 2500 -- the result: guess and spot shown together up to this zoom (the terrain map's widest)
Gm.SPOT_ZOOM_YD = 600 -- ... else the spot alone, this zoomed
Gm.CELEBRATE_SOLO = 60 -- solo: the average round score that earns the celebration
Gm.ROUNDS = { 1, 3, 5 }

---------------------------------------------------------------------------------------------
-- Pure helpers

-- Points (0-100) for a guess `yards` off (nil: no guess, or on another continent).
function Gm.Score(yards)
  if not yards then return 0 end
  if yards <= Gm.FULL_YD then return 100 end
  return math.floor(100 * math.exp(-(yards - Gm.FULL_YD) / Gm.SCALE_YD) + 0.5)
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
    if not used[id] and type(p.cont) == "number" and p.cont < 10000
        and (not allowed or (p.pack and allowed[Gm.PackKey(p.pack.name)])) then
      ids[#ids + 1] = id
    end
  end
  if #ids == 0 then return nil end
  table.sort(ids) -- (the same pick for the same numbers: tests)
  return D.byId[ids[(rnd or math.random)(#ids)]]
end

-- The players by total so far (ties by name): { { name, total, last, rounds }, ... }.
function Gm.Standings(g)
  local list = {}
  for _, name in ipairs(g.order) do
    local pl = g.players[name]
    local total, n = 0, 0
    for r = 1, g.round do
      if pl.scores[r] then total, n = total + pl.scores[r], n + 1 end
    end
    list[#list + 1] = { name = name, total = total, last = pl.scores[g.round], rounds = n }
  end
  table.sort(list, function(a, b)
    if a.total ~= b.total then return a.total > b.total end
    return a.name < b.name
  end)
  return list
end

-- The names tied at the top (none when nobody scored).
function Gm.Winners(list)
  local out = {}
  local top = list[1] and list[1].total or 0
  if top <= 0 then return out end
  for _, s in ipairs(list) do
    if s.total == top then out[#out + 1] = s.name end
  end
  return out
end

-- Solo: the average round score over the rounds played.
function Gm.Average(g)
  local pl = g.players[g.me]
  local total = 0
  for r = 1, g.round do total = total + (pl and pl.scores[r] or 0) end
  return g.round > 0 and math.floor(total / g.round + 0.5) or 0
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
  me = function()
    local n, r = UnitFullName("player")
    r = (r and r ~= "") and r or (GetNormalizedRealmName and GetNormalizedRealmName()) or ""
    return r ~= "" and (n .. "-" .. r) or n
  end,
  send = function(msg, chatType, target)
    if C_ChatInfo and C_ChatInfo.SendAddonMessage then C_ChatInfo.SendAddonMessage(Gm.PREFIX, msg, chatType, target) end
  end,
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
  follow = function() end, showMap = function() end, world = function() end, changed = function() end, ask = function() end,
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

local function AddPlayer(name)
  if not game.players[name] then
    game.players[name] = { name = name, scores = {}, guesses = {} }
    game.order[#game.order + 1] = name
  end
end

local function RemovePlayer(name)
  if not game.players[name] then return end
  game.players[name] = nil
  for i, n in ipairs(game.order) do
    if n == name then table.remove(game.order, i) break end
  end
end

-- To everyone else in the game: the party's channel, or a whisper each.
local function ToOthers(...)
  if game.mode == "solo" then return end
  local msg = Gm.Encode(...)
  if game.mode == "party" then
    io().send(msg, game.channel)
  else
    for _, name in ipairs(game.order) do
      if name ~= game.me then io().send(msg, "WHISPER", name) end
    end
    if game.phase == "invite" and game.target then io().send(msg, "WHISPER", game.target) end
  end
end

local function NewGame(mode, rounds, host, id)
  local me = io().me()
  game = { id = id or tostring(io().random(100000, 999999)), mode = mode, rounds = rounds, host = host or me, me = me,
    players = {}, order = {}, round = 0, used = {}, phase = "wait", packs = {}, report = {} }
  game.isHost = game.host == me
  game.packs[me] = Gm.MyPacks()
  AddPlayer(game.host)
  if not game.isHost then AddPlayer(me) end
end

local Look, Result, Over, NextRound, Submit

-- The game ends (reason: why, when it didn't run its rounds). The panel stays until its X.
Over = function(reason)
  if not game then return end
  game.phase = "over"
  game.reason = reason
  io().close()
  local list = Gm.Standings(game)
  game.winners = Gm.Winners(list)
  if game.mode == "solo" then
    game.celebrate = not reason and Gm.Average(game) >= Gm.CELEBRATE_SOLO
  else
    game.celebrate = not reason and #game.winners > 0
  end
  Changed()
end

-- host: the next street view, asked of the players first
local function Propose()
  local p = Gm.PickSpot(game.used, function(n) return io().random(1, n) end, game.common)
  if not p then return Over("No street views are installed") end
  game.used[p.id] = true
  game.spot = p
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
  io().follow()
  if game.spot then io().open(game.spot, io().random() * 2 * math.pi) end
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
  -- the map: the guess and the spot together while that fits on the terrain map; else the spot
  -- alone; a guess on another continent: the world
  local s = game.spot
  if g and g.x then game.reveal = { t0 = Now() } end
  if s then
    local fit = g and g.yards and math.max(250, g.yards * 0.65 + 80)
    if fit and fit <= Gm.TERRAIN_MAX_YD then
      io().lookAt(s.cont, (s.x + g.x) / 2, (s.y + g.y) / 2, fit)
    elseif g and g.x and not g.yards then
      io().world(s)
    else
      io().lookAt(s.cont, s.x, s.y, Gm.SPOT_ZOOM_YD)
    end
  end
  ToOthers("S", game.id, game.round, score, g and g.yards and math.floor(g.yards + 0.5) or "",
    g and g.cont or "", g and g.x and math.floor(g.x + 0.5) or "", g and g.y and math.floor(g.y + 0.5) or "")
  if game.mode == "solo" then
    return Result()
  end
  game.phase = "wait"
  Changed()
end

Result = function()
  io().close()
  game.phase = "result"
  game.deadline = Now() + Gm.RESULT_SECONDS
  if not game.guess then -- (the host ended the round before this player's time was up)
    local g = game
    Submit()
    if game ~= g then return end
    game.phase = "result"
  end
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
  ToOthers("L", game.id, table.concat(game.order, ","))
  NextRound()
end

-- Everyone asked has answered the invitation.
local function AllAnswered()
  local n = 0
  for _ in pairs(game.answers) do n = n + 1 end
  if game.mode == "whisper" then return n >= 1 end
  return n >= io().groupSize() - 1
end

-- Start a game as its host. mode: "solo", "party" or "whisper" (target: the player's name).
function Gm.Start(mode, rounds, target)
  if game and game.phase ~= "over" then
    io().print("A game is already on.")
    return false
  end
  if mode == "party" and not io().group() then
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
  game.channel = mode == "party" and io().group() or nil
  game.target = mode == "whisper" and target or nil
  io().hold(true)
  io().showMap()
  if mode == "solo" then
    NextRound()
    return true
  end
  game.phase = "invite"
  game.answers = {}
  game.deadline = Now() + Gm.JOIN_SECONDS
  ToOthers("I", game.id, rounds, Gm.PackField(game.packs[game.me]))
  Changed()
  return true
end

-- host: start without waiting for the rest of the answers
function Gm.StartNow()
  if game and game.isHost and game.phase == "invite" then Begin() end
end

-- Leave the game (its X): the map shows the route again.
function Gm.Leave()
  if not game then return end
  if game.phase ~= "over" and game.mode ~= "solo" then
    ToOthers(game.isHost and "X" or "Q", game.id)
  end
  game = nil
  io().close()
  io().hold(false)
  io().follow()
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
  local ph = game.phase
  if ph == "look" and now >= game.deadline then -- the time is up: the guess placed counts
    io().close()
    Submit()
  end
  if ph == "joined" and now >= game.deadline then
    return Over("The game started without you")
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
    if game.phase ~= "invite" then ToOthers("L", game.id, table.concat(game.order, ",")) end
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
      game.deadline = Now() + Gm.JOIN_SECONDS + 10 -- (no word from the host by then: it started without us)
      io().send(Gm.Encode("J", id, Gm.PackField(game.packs[game.me])), reply, to)
      io().hold(true)
      io().showMap()
      Changed()
    end, function()
      io().send(Gm.Encode("D", id), reply, to)
    end)
    return
  end
  if not game or id ~= game.id then return end
  local round = tonumber(f[2])
  if game.isHost then
    if kind == "J" and game.phase == "invite" then
      AddPlayer(sender)
      game.answers[sender] = true
      game.packs[sender] = Gm.ParsePacks(f[2])
      Compare()
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
    if sender ~= game.host and kind ~= "S" and kind ~= "Q" then return end -- (the host runs the game)
    if kind == "K" and f[2] then
      game.packs[f[2]] = Gm.ParsePacks(f[3])
      Compare()
      Changed()
    elseif kind == "L" then
      if not (","  .. (f[2] or "") .. ","):find("," .. game.me .. ",", 1, true) then
        return Over("The game started without you")
      end
      local keep = {}
      for name in (f[2] or ""):gmatch("[^,]+") do
        keep[name] = true
        AddPlayer(name)
      end
      for i = #game.order, 1, -1 do
        local name = game.order[i]
        if not keep[name] then RemovePlayer(name) end
      end
      Changed()
    elseif kind == "P" and round and f[3] then
      game.round = round
      game.phase = "ready"
      game.spot = D.byId[f[3]]
      local reply = game.mode == "whisper" and "WHISPER" or game.channel
      io().send(Gm.Encode(game.spot and "O" or "M", game.id, round), reply, game.mode == "whisper" and game.host or nil)
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
  if not game or game.mode ~= "party" or game.phase == "over" then return end
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
local LINE_COLOR = { 1, 1, 1 }
local OTHER_COLORS = { { 0.4, 0.8, 1 }, { 0.6, 1, 0.5 }, { 1, 0.6, 1 }, { 1, 0.75, 0.4 }, { 0.75, 0.7, 1 } }
Gm.REVEAL_SECONDS = 1.5

-- How far the line has grown (0-1).
function Gm.RevealProgress()
  local r = game and game.reveal
  if not r then return 1 end
  return math.min(1, (Now() - r.t0) / Gm.REVEAL_SECONDS)
end

function Gm.Draw(ctx)
  if not game then return end
  local ph = game.phase
  local API = _G.AzerothGPS
  local base = API and API.BaseContinent and API.BaseContinent(ctx.cont) or ctx.cont
  if ph == "look" then -- the guess placed so far (not the answer yet)
    local pg = game.pending
    if pg and pg.cont == base then
      ctx.Dot(pg.x, pg.y, { 0, 0, 0 }, 15, 0.8)
      ctx.Dot(pg.x, pg.y, GUESS_COLOR, 11, 1)
    end
    return
  end
  if not game.spot then return end
  if ph ~= "wait" and ph ~= "result" and ph ~= "over" then return end
  local s = game.spot
  if s.cont ~= base then return end
  local t = Gm.RevealProgress()
  if ph ~= "wait" and t >= 1 then -- the others' guesses
    local k = 0
    for _, name in ipairs(game.order) do
      if name ~= game.me then
        k = k + 1
        local g = game.players[name].guesses[game.round]
        if g and g.x and g.cont == base then
          local c = OTHER_COLORS[(k - 1) % #OTHER_COLORS + 1]
          ctx.Line(g.x, g.y, s.x, s.y, c, 2, 0.7, true)
          ctx.Dot(g.x, g.y, c, 9, 1)
        end
      end
    end
  end
  local g = game.guess
  if g and g.x and g.cont == base then
    ctx.Line(g.x, g.y, g.x + (s.x - g.x) * t, g.y + (s.y - g.y) * t, LINE_COLOR, 3, 0.95, true)
    ctx.Dot(g.x, g.y, GUESS_COLOR, 11, 1)
  end
  if t >= 1 or not (g and g.x) then ctx.Dot(s.x, s.y, SPOT_COLOR, 14, 1) end
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
local function Chip(parent, text, width, onClick)
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
  fly.step = step
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
    local name = UnitIsPlayer and UnitIsPlayer("target") and not UnitIsUnit("target", "player") and GetUnitName("target", true)
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
  local s1 = Step("mode", { solo, party, whisper })
  for _, c in ipairs({ solo, party, whisper }) do c:SetParent(s1) end

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

  -- the slide: the width eases toward its target (0: closing)
  fly:SetScript("OnUpdate", function(self, dt)
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
local ROWS = 8

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
  local ok, start = pcall(CreateFrame, "Button", nil, panel, "UIPanelButtonTemplate")
  if not ok or not start then start = Chip(panel, "Start now", 90) end
  start:SetSize(90, 20)
  start:SetText("Start now")
  start:SetScript("OnClick", function() Gm.StartNow() end)
  start:Hide()
  panel.start = start
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
  local roundText = game.round > 0 and string.format("  |cffffffffRound %d of %d|r", game.round, game.rounds) or ""
  panel.title:SetText("|cffffd100Street Guess|r" .. (game.mode == "solo" and "  |cff9d9d9dsolo|r" or "") .. roundText)
  local status
  if ph == "invite" then
    local n = #game.order - 1
    status = game.mode == "whisper" and ("Waiting for " .. Short(game.target) .. " to answer...")
      or string.format("Invited your party: %d joined so far.", n)
  elseif ph == "joined" then
    status = "You joined " .. Short(game.host) .. "'s game. Waiting for it to start..."
  elseif ph == "propose" or ph == "ready" then
    status = "Getting the next street view ready..."
  elseif ph == "look" then
    status = game.missing and "|cffff8080You don't have this street view (update your StreetView packs): guess anyway!|r"
      or (game.pending and "Guess placed. |cffffd100Double-click|r again to move it; it counts when the time runs out."
        or "Where is this? |cffffd100Double-click the map|r where you think it is.")
  elseif ph == "wait" then
    status = GuessLine(game.guess) .. "\n|cff9d9d9dWaiting for the others...|r"
  elseif ph == "result" then
    local nextIn = game.round < game.rounds and (game.isHost or game.mode ~= "solo") and "\n|cff9d9d9dNext round in a moment|r" or ""
    status = GuessLine(game.guess) .. nextIn
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
      row.name:SetText("Rounds: " .. table.concat(parts, ", "))
      row.last:SetText("")
      row.total:SetText(ph == "over" and "" or string.format("Average %d", Gm.Average(game)))
      row.name:ClearAllPoints()
      row.name:SetPoint("TOPLEFT", panel, "TOPLEFT", 10, y)
      row.total:ClearAllPoints()
      row.total:SetPoint("TOPRIGHT", panel, "TOPRIGHT", -10, y)
      rowsShown = 1
    end
  else
    local list = Gm.Standings(game)
    local showScores = game.round > 0
    for i, s in ipairs(list) do
      if i > ROWS then break end
      local row = panel.rows[i]
      local me = s.name == game.me
      local done = s.last ~= nil
      local lastText = ""
      if showScores then
        if ph == "result" or ph == "over" or me then
          lastText = done and (ScoreColor(s.last) .. "+" .. s.last .. "|r") or "|cff808080-|r"
        else
          lastText = done and "|cff40ff40guessed|r" or "|cff808080...|r"
        end
      end
      row.name:SetText(string.format("%d. %s%s|r", i, me and "|cffffd100" or "|cffffffff", Short(s.name)))
      row.last:SetText(lastText)
      row.total:SetText(showScores and tostring(s.total) or "")
      row.name:ClearAllPoints()
      row.name:SetPoint("TOPLEFT", panel, "TOPLEFT", 10, y - (i - 1) * 14)
      row.last:ClearAllPoints()
      row.last:SetPoint("TOPRIGHT", panel, "TOPRIGHT", -52, y - (i - 1) * 14)
      row.total:ClearAllPoints()
      row.total:SetPoint("TOPRIGHT", panel, "TOPRIGHT", -10, y - (i - 1) * 14)
      rowsShown = i
    end
  end
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
  if (ph == "look" or ph == "invite") and game.deadline then
    local left = game.deadline - Now()
    local color = left <= 5 and "|cffff5050" or (ph == "look" and "|cffffd100" or "|cffffffff")
    panel.timer:SetText(color .. Clock(left) .. "|r")
    if V and V.SetTimer then V.SetTimer(ph == "look" and (color .. Clock(left) .. "|r") or nil) end
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
  gameButton:SetPoint("BOTTOM", figure, "TOP", 0, 4)
  local bg = gameButton:CreateTexture(nil, "BACKGROUND")
  bg:SetAllPoints()
  bg:SetTexture("Interface\\Minimap\\UI-Minimap-Background")
  local icon = gameButton:CreateTexture(nil, "ARTWORK")
  icon:SetSize(18, 18)
  icon:SetPoint("CENTER")
  icon:SetTexture("Interface\\Icons\\INV_Misc_Map_01")
  icon:SetTexCoord(0.08, 0.92, 0.08, 0.92)
  gameButton:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
  gameButton:RegisterForClicks("LeftButtonUp")
  gameButton:SetScript("OnClick", function()
    if game then
      if game.phase == "over" then Gm.Leave() else io().print("A game is on: its X leaves it.") end
      return
    end
    if fly:IsShown() and fly.target > 0 then HideMenu() else ShowMenu("mode") end
  end)
  gameButton:SetScript("OnEnter", function(self)
    GameTooltip:SetOwner(self, "ANCHOR_LEFT")
    GameTooltip:AddLine("Street Guess")
    GameTooltip:AddLine("Where is this street view? You have 30 seconds to look around and double-click the map where you think it is (again to move it).", 1, 1, 1, true)
    GameTooltip:AddLine("Solo, with your party, or with one player by whisper.", 0.8, 0.8, 0.8, true)
    GameTooltip:Show()
  end)
  gameButton:SetScript("OnLeave", GameTooltip_Hide)
end

-- The invitation, asked before joining.
local function Ask(sender, rounds, onYes, onNo)
  if not (StaticPopupDialogs and StaticPopup_Show) then
    io().print(Short(sender) .. " invited you to Street Guess, but this client can't ask: declined.")
    return onNo()
  end
  StaticPopupDialogs.AGPS_STREETGUESS_INVITE = StaticPopupDialogs.AGPS_STREETGUESS_INVITE or {
    text = "%s invites you to Street Guess (%s). Join?",
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
    ns.Print("Street Guess needs a newer AzerothGPS (API version 3).")
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
  io_.world = function(s) -- (a guess on another continent: zoomed out to the world)
    if API.ShowWorld then API.ShowWorld() elseif API.LookAt then API.LookAt(s.cont, s.x, s.y, 6000) end
  end
  io_.follow = function() if API.Follow then API.Follow() end end
  io_.showMap = function() if API.ShowMap then API.ShowMap() end end
  io_.changed = function()
    Gm.Refresh()
    if ns.Figure then ns.Figure.Refresh() end
    API.Redraw()
  end
  io_.ask = Ask

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
    end
    if game and game.reveal and Now() - game.reveal.t0 <= Gm.REVEAL_SECONDS + 0.1 then API.Redraw() end
    if game and game.celebrate and panel:IsShown() then Celebrate(t) end
  end)
end
