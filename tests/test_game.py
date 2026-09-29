"""Street Guess (Game.lua) under lupa: scoring, and whole games between simulated players.

Each player is its own Lua runtime with Data.lua and Game.lua loaded; Gm.io is replaced by a
fake that records what the game shows and routes addon messages between the players.
"""

import math
from pathlib import Path

import pytest

lupa = pytest.importorskip("lupa")

ADDON = Path(__file__).resolve().parents[1] / "addon" / "AzerothGPS_StreetView"

PACK = """{ { name = "t", root = "R\\\\", ext = "jpg", points = {
  { id = "1-100-100", cont = 1, x = 100, y = 100 },
  { id = "1-2000-500", cont = 1, x = 2000, y = 500 },
  { id = "0-300-300", cont = 0, x = 300, y = 300 },
  { id = "0-900-900", cont = 0, x = 900, y = 900 },
  { id = "1-5000-5000", cont = 1, x = 5000, y = 5000 },
  { id = "20036-1-1", cont = 20036, x = 1, y = 1 },
} } }"""


class Clock:
    t = 1000.0


class Player:
    def __init__(self, name, clock, net, pack=PACK, group=None, answer=True):
        self.name, self.clock, self.net, self.answer = name, clock, net, answer
        self.lua = lupa.LuaRuntime()
        self.ns = self.lua.table()
        for f in ("Data.lua", "Game.lua"):
            fn = self.lua.eval("function(src, name) return assert(load(src, '@' .. name)) end")(
                (ADDON / f).read_text(encoding="utf-8"), f)
            fn("AzerothGPS_StreetView", self.ns)
        self.D, self.G = self.ns.Data, self.ns.Game
        self.D.Load(self.lua.eval(pack))
        self.shown = []  # street views opened
        self.closed = 0
        self.held = []
        self.printed = []
        self.looked = []
        self.group = group  # the party's channel, or None
        io = self.lua.table_from({
            "now": lambda: clock.t,
            "me": lambda: name,
            "send": self.send,
            "group": lambda: self.group,
            "groupSize": lambda: len(net.players),
            "inGroup": lambda n: n in net.players,
            "random": self.random,
            "open": lambda p, h: self.shown.append(p.id),
            "close": self.close,
            "hold": lambda on: self.held.append(bool(on)),
            "lookAt": lambda c, x, y, z: self.looked.append((c, x, y, z)),
            "world": lambda spot: self.looked.append("world"),
            "follow": lambda: None,
            "showMap": lambda: None,
            "changed": lambda: None,
            "ask": self.ask,
            "print": lambda *a: self.printed.append(" ".join(str(x) for x in a)),
        })
        self.G.io = io
        net.players[name] = self

    def random(self, a=None, b=None):
        if a is None:
            return 0.25
        return a  # (the first street view in id order, then the next unused one)

    def close(self):
        self.closed += 1

    def send(self, msg, chat, target=None):
        self.net.queue.append((self.name, msg, chat, target))

    def ask(self, sender, rounds, yes, no):
        (yes if self.answer else no)()

    @property
    def game(self):
        return self.G.Current()


class Net:
    def __init__(self):
        self.players, self.queue = {}, []

    def deliver(self):
        """Hand every queued message to its receivers (party: everyone else; whisper: one)."""
        n = 0
        while self.queue:
            sender, msg, chat, target = self.queue.pop(0)
            for name, p in list(self.players.items()):
                if name == sender:
                    continue
                if chat == "WHISPER" and name != target:
                    continue
                p.G.OnMessage(msg, chat, sender)
                n += 1
        return n


def run(net, clock, seconds, step=0.5):
    """Let `seconds` pass: every player's clock ticks and messages flow."""
    end = clock.t + seconds
    while clock.t < end:
        clock.t += step
        for p in list(net.players.values()):
            p.G.Tick()
        net.deliver()


def scores(p, name):
    pl = p.game.players[name]
    return [pl.scores[r] for r in range(1, p.game.round + 1)]


# ---------------------------------------------------------------------------------------------


@pytest.fixture
def solo():
    clock, net = Clock(), Net()
    return Player("Me-Realm", clock, net), clock, net


def test_score_is_easy_at_first_and_hard_at_the_end(solo):
    p, _, _ = solo
    S = p.G.Score
    assert S(None) == 0
    assert S(0) == 100 and S(25) == 100
    assert S(340) == 90 and S(1550) == 60 and S(2800) == 40
    prev = 101
    for yd in range(0, 20000, 50):
        assert S(yd) <= prev
        prev = S(yd)
    # the band of distances earning 1-40 points is far wider than the one earning 90-100
    def band(lo, hi):
        yds = [yd for yd in range(0, 30000, 5) if lo <= S(yd) <= hi]
        return max(yds) - min(yds)
    assert band(1, 40) > 20 * band(90, 100)


def test_messages_round_trip(solo):
    p, _, _ = solo
    msg = p.G.Encode("S", "123", 2, 57, 1234, 1, -500, 300)
    assert msg == "S:123:2:57:1234:1:-500:300"
    kind, f = p.lua.eval("function(G, m) local k, f = G.Decode(m) return k, f end")(p.G, msg)
    assert kind == "S" and [f[i] for i in range(1, 8)] == ["123", "2", "57", "1234", "1", "-500", "300"]
    assert p.G.Decode("hello") is None and p.G.Decode("") is None


def test_spots_are_on_continents_and_never_twice(solo):
    p, _, _ = solo
    used = p.lua.table()
    seen = set()
    for _ in range(5):
        s = p.G.PickSpot(used, lambda n: 1)
        assert s.cont < 10000 and s.id not in seen
        seen.add(s.id)
        used[s.id] = True
    assert p.G.PickSpot(used, lambda n: 1) is None  # (only the dungeon's is left)


def test_solo_game_runs_its_rounds_and_averages(solo):
    p, clock, net = solo
    assert p.G.Start("solo", 3)
    assert p.held == [True] and p.game.phase == "look" and p.shown == ["0-300-300"]
    run(net, clock, 5)
    p.G.Guess(900, 900, 0)  # placed while the street view is up...
    p.G.Guess(310, 300, 0)  # ... and moved: the last one counts
    assert p.game.phase == "look" and p.game.pending.x == 310 and p.closed == 0  # (it waits for the timer)
    run(net, clock, 26)  # the 30 seconds are up: 10 yd off, all the points
    assert p.game.phase == "result" and scores(p, "Me-Realm") == [100] and p.closed >= 1
    assert p.looked  # the map shows the guess and the spot
    run(net, clock, 8)
    assert p.game.round == 2 and p.game.phase == "look" and p.shown[-1] == "0-900-900"
    p.G.Guess(900, 900, 1)  # the wrong continent: nothing
    run(net, clock, 31)
    assert scores(p, "Me-Realm") == [100, 0]
    run(net, clock, 8)
    run(net, clock, 31)  # no guess in the 30 seconds: nothing
    assert scores(p, "Me-Realm") == [100, 0, 0]
    run(net, clock, 8)
    g = p.game
    assert g.phase == "over" and p.G.Average(g) == 33 and not g.celebrate
    p.G.Leave()
    assert p.G.Current() is None and p.held == [True, False]


def test_solo_celebrates_a_good_average(solo):
    p, clock, net = solo
    p.G.Start("solo", 1)
    s = p.game.spot
    p.G.Guess(s.x + 300, s.y, s.cont)
    run(net, clock, 31 + 8)
    assert p.game.phase == "over" and p.G.Average(p.game) == 91 and p.game.celebrate


def party(n=2, **kw):
    clock, net = Clock(), Net()
    players = [Player(name, clock, net, group="PARTY", **kw) for name in ("Ann-Realm", "Bob-Realm", "Cid-Realm")[:n]]
    return players, clock, net


def test_party_game_between_two_players():
    (a, b), clock, net = party(2)
    assert a.G.Start("party", 1)
    assert a.game.phase == "invite"
    net.deliver()  # the invitation, B joins
    assert b.game.phase == "joined" and b.held == [True]
    net.deliver()  # the answer
    run(net, clock, 1)  # everyone answered: the round starts
    assert a.game.phase == "look" and b.game.phase == "look"
    assert a.shown == b.shown == ["0-300-300"]
    assert list(b.game.order.values()) == ["Ann-Realm", "Bob-Realm"]
    a.G.Guess(300, 400, 0)  # 100 yd off
    b.G.Guess(300, 3300, 0)  # 3,000 yd off
    run(net, clock, 5)
    assert a.game.phase == "look" and b.game.players["Ann-Realm"].scores[1] is None  # (nothing sent before the time's up)
    run(net, clock, 27)  # the time is up: both guesses in, the round's result
    assert a.game.phase == "result" and b.game.phase == "result"
    assert b.game.players["Ann-Realm"].scores[1] == a.G.Score(100)
    assert b.game.players["Ann-Realm"].guesses[1].x == 300  # (her guess shows on B's map)
    run(net, clock, 8)
    for p in (a, b):
        assert p.game.phase == "over" and list(p.game.winners.values()) == ["Ann-Realm"] and p.game.celebrate


def test_the_round_ends_when_time_is_up_for_someone_silent():
    (a, b), clock, net = party(2)
    a.G.Start("party", 1)
    run(net, clock, 2)
    assert a.game.phase == "look"
    a.G.Guess(300, 300, 0)
    net.players.pop("Bob-Realm")  # (B's game went quiet)
    run(net, clock, 36)
    assert a.game.phase in ("result", "over")
    assert scores(a, "Ann-Realm") == [100]


def test_a_player_who_leaves_is_taken_off_the_list():
    (a, b, c), clock, net = party(3)
    a.G.Start("party", 3)
    run(net, clock, 1)
    assert len(c.game.order) == 3
    b.G.Leave()
    run(net, clock, 1)
    assert list(a.game.order.values()) == ["Ann-Realm", "Cid-Realm"]
    assert list(c.game.order.values()) == ["Ann-Realm", "Cid-Realm"]
    # leaving the party counts too
    net.players.pop("Cid-Realm")
    a.G.OnRoster()
    assert a.game.phase == "over" and a.game.reason  # (nobody left to play with)


def test_the_host_leaving_ends_the_game():
    (a, b), clock, net = party(2)
    a.G.Start("party", 3)
    run(net, clock, 1)
    a.G.Leave()
    net.deliver()
    assert b.game.phase == "over" and "ended" in b.game.reason


def test_a_street_view_someone_lacks_is_swapped():
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net, group="PARTY")
    lacking = PACK.replace('{ id = "0-300-300", cont = 0, x = 300, y = 300 },', "")
    b = Player("Bob-Realm", clock, net, pack=lacking, group="PARTY")
    a.G.Start("party", 1)
    run(net, clock, 2)
    assert a.game.phase == "look" and a.shown == b.shown == ["0-900-900"]


def test_declined_whisper_ends_the_game():
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net)
    Player("Bob-Realm", clock, net, answer=False)
    assert a.G.Start("whisper", 3, "Bob")  # (her realm is added)
    net.deliver()
    net.deliver()
    assert a.game.phase == "over" and "declined" in a.game.reason


def test_whisper_game_plays_through():
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net)
    b = Player("Bob-Realm", clock, net)
    a.G.Start("whisper", 1, "Bob-Realm")
    run(net, clock, 2)
    assert b.game.phase == "look" and b.game.mode == "whisper"
    b.G.Guess(300, 300, 0)
    a.G.Guess(900, 900, 0)
    run(net, clock, 31 + 9)
    assert a.game.phase == "over" and list(a.game.winners.values()) == ["Bob-Realm"]
    assert list(b.game.winners.values()) == ["Bob-Realm"]
    assert all(target == "Bob-Realm" or target == "Ann-Realm" for _, _, _, target in net.queue)


def test_busy_players_are_not_asked():
    (a, b), clock, net = party(2)
    b.G.Start("solo", 1)
    a.G.Start("party", 1)
    net.deliver()
    net.deliver()
    assert b.game.mode == "solo"  # (still in its own game)
    assert a.game.answers["Bob-Realm"] is False


TWO_PACKS = """{
  { name = "AzerothGPS_StreetView_Kalimdor", version = "2026.09.29", root = "K\\\\", points = {
    { id = "1-100-100", cont = 1, x = 100, y = 100 },
    { id = "1-2000-500", cont = 1, x = 2000, y = 500 },
  } },
  { name = "AzerothGPS_StreetView_EasternKingdoms", version = "2026.09.29", root = "E\\\\", points = {
    { id = "0-300-300", cont = 0, x = 300, y = 300 },
    { id = "0-900-900", cont = 0, x = 900, y = 900 },
  } },
}"""


def pack_players(b_pack):
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net, pack=TWO_PACKS, group="PARTY")
    b = Player("Bob-Realm", clock, net, pack=b_pack, group="PARTY")
    return a, b, clock, net


def report(p):
    return {r.name: (list(r.missing.values()), list(r.older.values())) for r in p.game.report.values()}


def test_street_views_come_only_from_packs_everyone_has():
    only_k = TWO_PACKS.split("  { name = \"AzerothGPS_StreetView_EasternKingdoms\"")[0] + "}"
    a, b, clock, net = pack_players(only_k)
    a.G.Start("party", 3)
    net.deliver()
    net.deliver()
    # the host sees who lacks which pack as soon as they join
    assert report(a) == {"Bob-Realm": (["EasternKingdoms"], [])}
    run(net, clock, 1)
    assert report(b) == {"Bob-Realm": (["EasternKingdoms"], [])}  # (everyone sees it)
    assert a.G.PackTitle("EasternKingdoms") == "Eastern Kingdoms"
    for _ in range(2):
        run(net, clock, 2)
        assert a.game.phase == "look" and a.game.spot.cont == 1  # (Kalimdor's only)
        a.G.Guess(a.game.spot.x, a.game.spot.y, 1)
        b.G.Guess(0, 0, 1)
        run(net, clock, 31 + 8)
    assert sorted(a.shown) == sorted(b.shown) == ["1-100-100", "1-2000-500"]


def test_an_older_pack_is_reported():
    older = TWO_PACKS.replace('"AzerothGPS_StreetView_Kalimdor", version = "2026.09.29"',
                              '"AzerothGPS_StreetView_Kalimdor", version = "2026.09.20"')
    a, b, clock, net = pack_players(older)
    a.G.Start("party", 1)
    net.deliver()
    net.deliver()
    assert report(a) == {"Bob-Realm": ([], ["Kalimdor"])}


def test_no_pack_in_common_ends_before_it_starts():
    a, b, clock, net = pack_players(PACK)  # (Bob's is another pack altogether)
    a.G.Start("party", 1)
    run(net, clock, 2)
    assert a.game.phase == "over" and "no map pack" in a.game.reason
    assert b.game.phase == "over"


def test_the_result_shows_both_only_when_they_fit_on_the_terrain_map(solo):
    p, clock, net = solo
    p.G.Start("solo", 3)
    s = p.game.spot  # (0-300-300)
    p.G.Guess(s.x + 400, s.y, s.cont)  # 400 yd off: both on the map, around the middle
    run(net, clock, 31)
    c, x, y, z = p.looked[-1]
    assert (c, x, y) == (0, 500, 300) and z <= p.G.TERRAIN_MAX_YD
    run(net, clock, 8)
    s = p.game.spot  # (0-900-900)
    p.G.Guess(s.x + 6000, s.y, s.cont)  # 6,000 yd off: too far to fit, just the spot
    run(net, clock, 31)
    assert p.looked[-1] == (0, 900, 900, p.G.SPOT_ZOOM_YD)
    run(net, clock, 8)
    s = p.game.spot
    p.G.Guess(0, 0, 1 - s.cont)  # the other continent: the world
    run(net, clock, 31)
    assert p.looked[-1] == "world"


def test_a_guess_on_the_other_continent_is_drawn_through_the_world_map(solo):
    p, clock, net = solo
    lua = p.lua
    # AzerothGPS's API: the continents side by side on the world map (continent 1 = 0 + 10,000 yd)
    lua.execute("""AzerothGPS = { BaseContinent = function(c) return c end,
      ToContinent = function(from, x, y, to) if from == to then return x, y end
        return x + (from - to) * 10000, y end }""")
    p.G.Start("solo", 1)
    s = p.game.spot  # (on continent 0)
    p.G.Guess(50, 60, 1)
    run(net, clock, 31)
    assert p.looked[-1] == "world"
    clock.t += 5  # (the line has grown all the way)
    drawn = []
    ctx = lua.table_from({"cont": 0})
    ctx.Line = lambda *a: drawn.append(("line",) + tuple(a[:4]))
    ctx.Dot = lambda *a: drawn.append(("dot",) + tuple(a[:2]))
    p.G.Draw(ctx)
    assert ("dot", 10050, 60) in drawn  # the guess, placed on continent 0's coordinates
    assert ("line", 10050, 60, s.x, s.y) in drawn  # the dotted line to the answer
    assert ("dot", s.x, s.y) in drawn  # the answer
