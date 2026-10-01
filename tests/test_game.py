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
  { id = "20036-1-1", cont = 20036, x = 1, y = 1, kind = "instance" },
  { id = "10001-1600-240", cont = 10001, x = 1600, y = 240 },
  { id = "1-8000-8000", cont = 1, x = 8000, y = 8000, kind = "cave" },
} } }"""


class Clock:
    t = 1000.0


class Player:
    def __init__(self, name, clock, net, pack=PACK, group=None, answer=True, seen_as=None):
        self.name, self.clock, self.net, self.answer = name, clock, net, answer
        self.seen_as = seen_as or name  # (how the others' messages name this player: WoW Forever's "First Surname")
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
        self.map_view = None  # (the map's center and zoom, when a test gives one: the result animates from it)
        self.map_state = None  # (the map before the game: restored when it ends)
        self.group = group  # the party's channel, or None
        self.posted = []  # (text, chatType, index) posted in chat
        io = self.lua.table_from({
            "joinChannel": lambda ch: net.channels.setdefault(ch, set()).add(name),
            "leaveChannel": lambda ch: net.channels.get(ch, set()).discard(name),
            "post": lambda text, chat, index=None: self.posted.append((text, chat, index)),
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
            "view": lambda: self.map_view,
            "mapState": lambda: self.map_state,
            "follow": lambda: self.looked.append("follow"),
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
        self.players, self.queue, self.channels = {}, [], {}

    def seen(self, sender):
        """The sender's name as the others' messages carry it."""
        p = self.players.get(sender)
        return p.seen_as if p else sender

    def hears(self, name, sender, chat, target):
        """Whether `name` gets a message (party: everyone else; whisper: one; a channel: its members)."""
        if name == sender:
            return False
        if chat == "WHISPER":
            return name == target or self.seen(name) == target
        if chat == "CHANNEL":
            return name in self.channels.get(target, ()) and sender in self.channels.get(target, ())
        return True

    def deliver(self):
        """Hand every queued message to its receivers."""
        n = 0
        while self.queue:
            sender, msg, chat, target = self.queue.pop(0)
            for name, p in list(self.players.items()):
                if not self.hears(name, sender, chat, target):
                    continue
                p.G.OnMessage(msg, chat, self.seen(sender))
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
    assert S(26) == 99  # (100 only within 25 yd)
    assert S(200) == 92 and S(500) == 78 and S(1000) == 58 and S(2000) == 30 and S(4000) == 7 and S(6000) == 1
    assert S(10000) == 0  # (a zone away is worth little: the user, 2026-09-30)
    prev = 101
    for yd in range(0, 20000, 50):
        assert S(yd) <= prev
        prev = S(yd)
    # the band of distances earning 1-40 points is far wider than the one earning 90-100
    def band(lo, hi):
        yds = [yd for yd in range(0, 30000, 5) if lo <= S(yd) <= hi]
        return max(yds) - min(yds)
    assert band(1, 40) > 10 * band(90, 100)


WORTH_PACK = PACK.replace('{ id = "0-300-300", cont = 0, x = 300, y = 300 }',
                          '{ id = "0-300-300", cont = 0, x = 300, y = 300, worth = 200 }')


def test_a_rounds_worth_scales_its_points(solo):
    # the user, 2026-10-01: 100 by a point of interest, up to 200 far from any
    p, _, _ = solo
    G = p.G
    S = G.Score
    assert S(0, 160) == 160 and S(25, 200) == 200 and S(26, 200) == 199
    assert S(500, 200) == 156 and S(1000, 200) == 116 and S(None, 200) == 0
    assert S(500) == S(500, 100) == 78  # (no worth given: 100, as before)
    prev = 201
    for yd in range(0, 20000, 50):
        assert S(yd, 200) <= prev
        prev = S(yd, 200)
    assert G.Worth(None) == 100 and G.Worth(p.lua.eval("{ worth = 150 }")) == 150
    assert G.Worth(p.lua.eval("{ worth = 500 }")) == 200 and G.Worth(p.lua.eval("{ worth = 20 }")) == 100
    # ties still break by distance, inside the round's own bands
    for yd in range(0, 6000, 37):
        sc = S(yd, 180)
        f = G.Fine(sc, yd, 180)
        assert sc - 1 < f <= sc or sc == 0
    assert G.Fine(180, 0, 180) == 180 and G.Fine(180, 25, 180) == 179.01


def test_the_host_sends_the_worth_and_everyone_scores_by_it():
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net, group="PARTY", pack=WORTH_PACK)
    b = Player("Bob-Realm", clock, net, group="PARTY",  # (an older Index: no worth there)
               pack=PACK)
    assert a.G.Start("party", 1)
    net.deliver()
    net.deliver()
    run(net, clock, 1)
    assert a.game.phase == "look" and b.game.phase == "look"
    assert a.game.worths[1] == 200 and b.game.worths[1] == 200  # (the host's: everyone scores alike)
    a.G.Guess(300, 400, 0)  # 100 yd off
    b.G.Guess(300, 1300, 0)  # 1,000 yd off
    run(net, clock, 32)
    assert a.game.players["Bob-Realm"].scores[1] == b.G.Score(1000, 200) == 116
    assert b.game.players["Ann-Realm"].scores[1] == a.G.Score(100, 200)


def test_the_celebration_is_by_the_share_of_the_worth(solo):
    clock, net = Clock(), Net()
    p = Player("Me-Realm", clock, net, pack=WORTH_PACK)
    p.G.Start("solo", 1)
    p.G.Guess(300, 1300, 0)  # 1,000 yd off a 200 spot: 116 points, over 75, but 58% of what it was worth
    run(net, clock, 31 + 11)
    assert p.game.phase == "over" and p.G.Average(p.game) == 116 and not p.game.celebrate
    q = Player("You-Realm", clock, net, pack=WORTH_PACK)
    q.G.Start("solo", 1)
    q.G.Guess(300, 400, 0)  # 100 yd off: 96%
    run(net, clock, 31 + 11)
    assert q.game.celebrate and 96 <= q.G.Percent(q.game, "You-Realm") < 97


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
    for _ in range(6):  # (the five on the continents and Undercity's)
        s = p.G.PickSpot(used, lambda n: 1)
        assert s.cont < 20000 and s.id not in seen and s.kind is None
        seen.add(s.id)
        used[s.id] = True
    assert p.G.PickSpot(used, lambda n: 1) is None  # (only the dungeon's and the cave's are left)


def test_solo_game_runs_its_rounds_and_averages(solo):
    p, clock, net = solo
    assert p.G.Start("solo", 3)
    assert p.held == [True] and p.game.phase == "look" and p.shown == ["0-300-300"]
    assert p.looked == ["world"]  # (the round starts on the world map)
    run(net, clock, 5)
    p.G.Guess(900, 900, 0)  # placed while the street view is up...
    p.G.Guess(310, 300, 0)  # ... and moved: the last one counts
    assert p.game.phase == "look" and p.game.pending.x == 310 and p.closed == 0  # (it waits for the timer)
    run(net, clock, 26)  # the 30 seconds are up: 10 yd off, all the points
    assert p.game.phase == "result" and scores(p, "Me-Realm") == [100] and p.closed == 0  # (the street view stays up)
    assert p.looked  # the map shows the guess and the spot
    run(net, clock, 11)  # (past the 10 s result)
    assert p.game.round == 2 and p.game.phase == "look" and p.shown[-1] == "0-900-900"
    p.G.Guess(900, 900, 1)  # the wrong continent: nothing
    run(net, clock, 31)
    assert scores(p, "Me-Realm") == [100, 0]
    run(net, clock, 11)  # (past the 10 s result)
    run(net, clock, 31)  # no guess in the 30 seconds: nothing
    assert scores(p, "Me-Realm") == [100, 0, 0]
    run(net, clock, 11)  # (past the 10 s result)
    g = p.game
    assert g.phase == "over" and p.G.Average(g) == 33 and not g.celebrate
    p.G.Leave()
    assert p.G.Current() is None and p.held == [True, False]


def test_solo_celebrates_a_good_average(solo):
    p, clock, net = solo
    p.G.Start("solo", 1)
    s = p.game.spot
    p.G.Guess(s.x + 100, s.y, s.cont)
    run(net, clock, 31 + 11)
    assert p.game.phase == "over" and p.G.Average(p.game) == 96 and p.game.celebrate


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
    run(net, clock, 11)  # (past the 10 s result)
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
        run(net, clock, 31 + 11)
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
    assert (c, x, y) == (0, 500, 300) and z <= p.G.FIT_MAX_YD
    run(net, clock, 11)  # (past the 10 s result)
    s = p.game.spot  # (0-900-900)
    p.G.Guess(s.x + 20000, s.y, s.cont)  # 20,000 yd off: too far to fit, just the spot
    run(net, clock, 31)
    assert p.looked[-1] == (0, 900, 900, p.G.SPOT_ZOOM_YD)
    run(net, clock, 11)  # (past the 10 s result)
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


def test_the_result_pans_and_zooms_out_smoothly_from_where_the_map_is(solo):
    p, clock, net = solo
    p.G.Start("solo", 1)
    s = p.game.spot  # (0-300-300)
    p.G.io.view = p.lua.eval("function() return 0, 0, 0, 300 end")  # the player's map: at (0, 0), 300 yd out
    p.G.Guess(s.x + 1000, s.y, s.cont)  # 1,000 yd off: fits on the terrain map
    run(net, clock, 30)  # (right when the time runs out)
    assert p.game.pan and p.G.RevealProgress() == 0  # (the line waits for the zoom)
    zooms = []
    for _ in range(12):
        clock.t += 0.1
        p.G.Animate()
        zooms.append(p.looked[-1][3])
    assert zooms == sorted(zooms) and zooms[0] > 300  # zooming out steadily
    c, x, y, z = p.looked[-1]
    assert (c, x, y) == (0, 800, 300) and z == pytest.approx(1000 * 0.65 + 80)
    assert p.game.pan is None


def test_solo_can_submit_before_the_time_runs_out(solo):
    p, clock, net = solo
    p.G.Start("solo", 1)
    s = p.game.spot
    p.G.SubmitNow()  # (nothing placed yet: nothing to submit)
    assert p.game.phase == "look"
    run(net, clock, 3)
    p.G.Guess(s.x, s.y, s.cont)
    p.G.SubmitNow()
    assert p.game.phase == "result" and scores(p, "Me-Realm") == [100] and p.closed == 0  # (the street view stays up)


def test_party_players_cant_submit_early():
    (a, b), clock, net = party(2)
    a.G.Start("party", 1)
    run(net, clock, 2)
    a.G.Guess(300, 300, 0)
    a.G.SubmitNow()
    assert a.game.phase == "look"


def test_the_round_result_fits_everyones_guesses_and_colors_them():
    (a, b, c), clock, net = party(3)
    a.G.Start("party", 1)
    run(net, clock, 2)
    assert a.game.phase == "look"
    a.G.Guess(300, 400, 0)  # 100 yd off
    b.G.Guess(300, 3300, 0)  # 3,000 yd off
    c.G.Guess(300, 20000, 0)  # far off: doesn't fit with the others, left out of the view
    run(net, clock, 32)
    assert a.game.phase == "result"
    # the answer (300, 300) with A's and B's guesses: centered between, zoomed to fit
    c0, x, y, z = a.looked[-1]
    assert (c0, x, y) == (0, 300, 1800) and z == pytest.approx(3000 * 0.65 + 80)
    # looks: an orc each (a party), in the host's roster order, the same on every player's screen
    for p in (a, b, c):
        assert [p.game.looks[n].orc for n in ("Ann-Realm", "Bob-Realm", "Cid-Realm")] == [1, 2, 3]
    ca = a.G.PlayerColor(a.game, "Bob-Realm")
    assert list(ca.values()) == list(a.G.ORCS[2].color.values())
    assert a.G.ColorCode(ca).startswith("|cff") and len(a.G.ColorCode(ca)) == 10


def test_fit_view_falls_back_to_the_answer_alone(solo):
    p, _, _ = solo
    spot = p.lua.eval("{ x = 0, y = 0 }")
    near = p.lua.eval("{ { x = 400, y = 0 } }")
    assert p.G.FitView(spot, near) == (200, 0, 400 * 0.65 + 80)
    far = p.lua.eval("{ { x = 400, y = 0 }, { x = 20000, y = 0 } }")
    assert p.G.FitView(spot, far) is None


def test_no_celebration_below_75(solo):
    p, clock, net = solo
    p.G.Start("solo", 1)
    s = p.game.spot
    p.G.Guess(s.x + 600, s.y, s.cont)  # ~73 points: good, but not a celebration
    run(net, clock, 31 + 11)
    assert p.game.phase == "over" and 70 <= p.G.Average(p.game) < 75 and not p.game.celebrate


def test_a_party_winner_under_75_gets_no_celebration():
    (a, b), clock, net = party(2)
    a.G.Start("party", 1)
    run(net, clock, 2)
    a.G.Guess(300, 3300, 0)  # 3,000 yd off: wins, but only 15
    b.G.Guess(300, 9300, 0)
    run(net, clock, 32 + 11)
    assert a.game.phase == "over" and list(a.game.winners.values()) == ["Ann-Realm"] and not a.game.celebrate


def test_a_guess_5000_yd_off_still_shows_both(solo):
    p, clock, net = solo
    p.G.Start("solo", 1)
    s = p.game.spot
    p.G.Guess(s.x + 5000, s.y, s.cont)  # a tight fit: at the terrain view's widest, not the map art
    run(net, clock, 31)
    c, x, y, z = p.looked[-1]
    assert (c, x, y) == (s.cont, s.x + 2500, s.y) and z == p.G.FIT_MAX_YD < 3000


def test_a_raid_gets_colored_squares_and_solo_a_random_orc(solo):
    p, clock, net = solo
    g = p.lua.eval("{ mode = 'party', channel = 'RAID', me = 'P1' }")
    roster = p.lua.table_from([f"P{i}" for i in range(1, 41)])
    p.G.AssignLooks(g, roster)
    assert g.looks["P1"].orc == 1  # (the player's own guess: an orc)
    colors = {tuple(g.looks[f"P{i}"].color.values()) for i in range(2, 41)}
    assert len(colors) == 39  # everyone else a different color
    # a party of 5: five different orcs, no squares
    g = p.lua.eval("{ mode = 'party', channel = 'PARTY', me = 'P1' }")
    p.G.AssignLooks(g, p.lua.table_from([f"P{i}" for i in range(1, 6)]))
    assert sorted(g.looks[f"P{i}"].orc for i in range(1, 6)) == [1, 2, 3, 4, 5]
    # solo: a random one of the five
    g = p.lua.eval("{ mode = 'solo', me = 'P1' }")
    p.G.AssignLooks(g, p.lua.table_from(["P1"]), lambda n: 4)
    assert g.looks["P1"].orc == 4


def test_a_finished_game_closes_after_a_minute(solo):
    p, clock, net = solo
    p.G.Start("solo", 1)
    run(net, clock, 31 + 11)
    assert p.game.phase == "over"
    run(net, clock, 50)
    assert p.G.Current() is not None  # (still showing the result)
    run(net, clock, 11)
    assert p.G.Current() is None and p.held == [True, False]  # back to the map and the route


def test_leaving_restores_the_map_as_it_was(solo):
    p, clock, net = solo
    # looking somewhere else before the game: back there
    p.map_state = p.lua.eval("{ following = false, x = 1000, y = 2000, cont = 1, zoom = 700 }")
    p.G.Start("solo", 1)
    p.G.Leave()
    assert p.looked[-1] == (1, 1000, 2000, 700)
    # following the player before: following again
    p.map_state = p.lua.eval("{ following = true, x = 5, y = 5, cont = 1, zoom = 300 }")
    p.G.Start("solo", 1)
    p.G.Leave()
    assert p.looked[-1] == "follow"
    # AzerothGPS saved the whole view (a continent or world map browsed): that, as it was
    p.G.io.restore = lambda saved: p.looked.append(("restore", saved.map))
    p.map_state = p.lua.eval('{ following = false, x = 1, y = 1, cont = 1, zoom = 9000, saved = { map = "Kalimdor" } }')
    p.G.Start("solo", 1)
    p.G.Leave()
    assert p.looked[-1] == ("restore", "Kalimdor")


def test_reported_and_unloadable_spots_are_never_picked(solo):
    p, clock, net = solo
    p.lua.execute("function _usable(G) G.Usable = function(pt) return pt.id ~= '0-300-300' and pt.id ~= '0-900-900' end end")
    p.lua.globals()._usable(p.G)
    p.G.Start("solo", 1)
    assert p.game.spot.id not in ("0-300-300", "0-900-900")


def test_city_level_spots_are_placed_on_their_continent(solo):
    p, _, _ = solo
    uc = p.lua.eval('function(G) return G.OnMap({ id = "10001-1600-240", cont = 10001, x = 1600, y = 240, pack = "k" },'
                    ' function(c) return c == 10001 and 0 or c end) end')(p.G)
    assert uc.cont == 0 and uc.id == "10001-1600-240" and uc.x == 1600 and uc.pack == "k"
    same = p.lua.eval('function(G) local q = { cont = 1, x = 5, y = 5 } return G.OnMap(q, function(c) return 0 end) == q end')(p.G)
    assert same  # (spots on a continent are used as they are)


def test_the_street_view_stays_up_after_the_round_until_leaving(solo):
    p, clock, net = solo
    p.G.Start("solo", 2)
    s = p.game.spot
    p.G.Guess(s.x + 50, s.y, s.cont)
    run(net, clock, 31)
    assert p.game.phase == "result" and p.closed == 0  # (still showing the round's street view)
    run(net, clock, 11)
    assert p.game.round == 2 and len(p.shown) == 2  # (the next round's replaces it)
    run(net, clock, 31 + 11)
    assert p.game.phase == "over" and p.closed == 0  # (the last one stays too)
    p.G.ShowAgain()
    assert p.shown[-1] == p.shown[1]  # (and can be shown again from the panel)
    p.G.Leave()
    assert p.closed == 1


def test_a_raid_of_40_with_long_names_all_know_each_other():
    # (the roster doesn't fit in one addon message: it goes in parts, each under 255 bytes)
    clock, net = Clock(), Net()
    names = [f"Longplayername{i:02d}-Argentdawnrealm" for i in range(40)]
    ps = [Player(n, clock, net, group="RAID") for n in names]
    sent = []
    orig = ps[0].send
    ps[0].send = lambda msg, chat, target=None: (sent.append(msg), orig(msg, chat, target))
    ps[0].G.io.send = ps[0].send
    assert ps[0].G.Start("party", 1)
    run(net, clock, 2)
    assert all(len(m) <= 255 for m in sent)
    assert sum(1 for m in sent if m.startswith("L:")) > 1
    for p in ps:
        assert p.game.phase == "look" and len(p.game.order) == 40, p.name
    for i, p in enumerate(ps):
        p.G.Guess(300, 300 + i * 50, 0)
    run(net, clock, 35)
    for p in ps:  # (everyone has everyone's score)
        assert all(p.game.players[n].scores[1] is not None for n in names), p.name


def test_the_game_ends_when_the_host_goes_silent():
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net)
    b = Player("Bob-Realm", clock, net)
    a.G.Start("whisper", 3, "Bob-Realm")
    run(net, clock, 2)
    assert b.game.phase == "look"
    net.players.pop("Ann-Realm")  # (the host went offline)
    for _ in range(int((b.G.LOOK_SECONDS + b.G.HOST_SILENT_SECONDS + 5) / 0.5)):
        clock.t += 0.5
        b.G.Tick()
    assert b.game.phase == "over" and "Lost touch" in b.game.reason


def test_a_players_marker_tooltip_names_them_with_their_scores():
    (a, b), clock, net = party(2)
    a.G.Start("party", 3)
    run(net, clock, 2)
    a.G.Guess(300, 400, 0)  # 100 yd off
    b.G.Guess(300, 3300, 0)
    run(net, clock, 31)
    tip = [l[1] for l in a.G.PlayerTip(a.game, "Bob-Realm").values()]
    assert tip[0] == "Bob" and tip[1].startswith("Round 1: ") and "3,000 yd off" in tip[1]
    assert [l[1] for l in a.G.PlayerTip(a.game, "Ann-Realm").values()][0] == "You"
    run(net, clock, 11 + 2)
    b.G.Guess(1, 1, 1)  # (another continent)
    run(net, clock, 31)
    tip = [l[1] for l in a.G.PlayerTip(a.game, "Bob-Realm").values()]
    assert "another continent" in tip[1] and tip[2].startswith("Total: ")
    assert len(a.G.PlayerTip(a.game, "Nobody-Realm")) == 0


def test_standings_can_leave_out_the_round_being_played():
    (a, b), clock, net = party(2)
    a.G.Start("party", 3)
    run(net, clock, 2)
    a.G.Guess(300, 300, 0)
    b.G.Guess(300, 3300, 0)
    run(net, clock, 31)  # (round 1's result)
    run(net, clock, 11 + 2)
    g = a.game
    g.players["Bob-Realm"].scores[2] = 100  # (as if Bob's round 2 guess came in during the round)
    shown = {s.name: s.total for s in a.G.Standings(g, g.round - 1).values()}
    assert shown["Bob-Realm"] == scores(a, "Bob-Realm")[0]  # (only round 1 counts before round 2's result)
    assert {s.name: s.total for s in a.G.Standings(g).values()}["Bob-Realm"] == shown["Bob-Realm"] + 100


def test_the_lobby_counts_down_the_same_for_everyone_who_joins():
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net, group="PARTY")
    b = Player("Bob-Realm", clock, net, group="PARTY")
    c = Player("Cid-Realm", clock, net, group="PARTY")
    c.ask = lambda sender, rounds, yes, no: c.later.append(yes)  # (Cid answers late)
    c.later = []
    c.G.io.ask = c.ask
    assert a.G.JOIN_SECONDS == 30
    a.G.Start("party", 1)
    start = a.game.deadline
    run(net, clock, 1)
    assert b.game.phase == "joined" and abs(b.game.startAt - start) <= 1
    run(net, clock, 11)
    c.later[0]()  # (clicks Join 12 s in)
    net.deliver()
    assert c.game.phase == "joined" and abs(c.game.startAt - start) <= 1  # (18 s left, not 30)
    run(net, clock, 2)
    assert a.game.phase == "look"  # (everyone answered: no need to wait)


def test_the_lobby_waits_for_the_countdown_until_everyone_answered():
    (a, b, c), clock, net = party(3)
    c.G.io.ask = lambda sender, rounds, yes, no: None  # (Cid never answers)
    a.G.Start("party", 1)
    run(net, clock, 20)
    assert a.game.phase == "invite" and b.game.phase == "joined" and b.game.startAt - clock.t == pytest.approx(10, abs=1)
    run(net, clock, 11)
    assert a.game.phase == "look" and b.game.phase == "look"


def open_game(n=3, rounds=1):
    clock, net = Clock(), Net()
    ps = [Player(f"P{i:02d}-Realm", clock, net) for i in range(n)]  # (no party: strangers)
    assert ps[0].G.Start("open", rounds)
    return ps, clock, net


def test_an_open_game_is_joined_from_its_link_in_chat():
    (a, b, c), clock, net = open_game(3)
    g = a.game
    assert g.open and g.phase == "invite" and net.queue == []  # (no invitation: the link is posted)
    assert a.G.PostLink("SAY")
    assert not a.G.PostLink("GUILD")  # (not again so soon)
    text, chat, _ = a.posted[0]
    assert chat == "SAY" and text == f"AGPSSV-{g.id}-1"  # (just the code: the link, for the players who can click it)
    shown = b.G.Linkify(text, "P00")  # (chat gives the author without the realm on the same realm)
    assert "|Hgarrmission:agpssv:" + g.id + ":1:P00|h" in shown and "AGPSSV-" not in shown
    link = shown.split("|H")[1].split("|h")[0]
    run(net, clock, 5)
    assert b.G.OnLink(link) and b.game.phase == "joined" and not b.game.startAt
    run(net, clock, 1)
    assert b.game.startAt == pytest.approx(g.deadline, abs=1)  # (the host's countdown)
    assert list(g.order.values()) == ["P00-Realm", "P01-Realm"] and a.game.phase == "invite"
    assert c.G.OnLink(link)
    run(net, clock, 30)
    for p in (a, b, c):
        assert p.game.phase == "look" and len(p.game.order) == 3, p.name
    for p in (a, b, c):
        p.G.Guess(300, 300, 0)
    run(net, clock, 45)
    assert all(v is not None for v in (a.game.players["P02-Realm"].scores[1], c.game.players["P01-Realm"].scores[1]))
    assert a.game.phase == "over"
    for p in (a, b, c):
        p.G.Leave()
    assert all(not m for m in net.channels.values())  # (everyone left the game's channel)


def test_an_open_game_turns_late_and_extra_players_away():
    (a, b), clock, net = open_game(2)
    link = f"garrmission:agpssv:{a.game.id}:1:P00-Realm"
    a.G.StartNow()  # (nobody yet: over)
    assert a.game.phase == "over"
    assert b.G.OnLink(link)
    run(net, clock, 1)
    assert b.game.phase == "over" and "over" in b.game.reason
    b.G.Leave()
    a.G.Leave()
    # full: the 40 players
    ps, clock, net = open_game(41)
    link = f"garrmission:agpssv:{ps[0].game.id}:1:P00-Realm"
    for p in ps[1:]:
        assert p.G.OnLink(link)
        net.deliver()
    assert ps[40].game.phase == "over" and "full" in ps[40].game.reason
    run(net, clock, 1)
    assert ps[0].game.phase == "look" and len(ps[0].game.order) == 40  # (full: it started)
    assert all(p.game.phase == "look" for p in ps[1:40])


def test_a_link_clicked_as_the_game_starts_stays_out_of_it():
    # (fuzz seed 3685: "started without you", then the first round's P brought the player back in)
    (a, b, c), clock, net = open_game(3)
    link = f"garrmission:agpssv:{a.game.id}:1:P00-Realm"
    b.G.OnLink(link)
    run(net, clock, 1)
    c.G.OnLink(link)  # (its J is on the way as the host starts)
    a.G.StartNow()
    run(net, clock, 3)
    assert c.game.phase == "over" and list(a.game.order.values()) == ["P00-Realm", "P01-Realm"]
    run(net, clock, 40)
    assert c.game.phase == "over" and c.game.round == 0


def test_a_link_to_a_host_who_never_answers_gives_up():
    (a, b), clock, net = open_game(2)
    link = f"garrmission:agpssv:{a.game.id}:3:P00-Realm"
    net.players.pop("P00-Realm")  # (the host went offline)
    assert b.G.OnLink(link)
    run(net, clock, 11)
    assert b.game.phase == "over" and "No answer" in b.game.reason


def test_join_codes_parse_only_real_rounds(solo):
    p, _, _ = solo
    assert p.G.ParseJoinCode("hey AGPSSV-123456-3 come") == ("123456", 3)
    assert p.G.ParseJoinCode("AGPSSV-123456-4") is None and p.G.ParseJoinCode("hello") is None
    assert p.G.Linkify("no code here", "Bob") == "no code here"
    assert p.G.OnLink("garrmission:other") is False


def test_fine_scores_break_ties_by_distance(solo):
    p, _, _ = solo
    G = p.G
    assert G.Fine(100, 0) == 100 and G.Fine(100, 10) == 99.6 and G.Fine(100, 25) == 99.01
    assert G.Fine(0, 20000) == 0 and G.Fine(0, None) == 0
    prev = 101
    for yd in range(0, 12000, 7):  # (the closer, the higher; never below the points under it)
        sc = G.Score(yd)
        f = G.Fine(sc, yd)
        assert f <= prev + 1e-9 and (sc == 0 or sc - 1 < f <= sc), (yd, sc, f)
        prev = f


def test_the_same_points_go_to_the_closer_guess():
    (a, b, c), clock, net = party(3)
    a.G.Start("party", 1)
    run(net, clock, 2)
    s = a.game.spot
    a.G.Guess(s.x + 20, s.y, s.cont)  # 100 points, 20 yd off
    b.G.Guess(s.x + 5, s.y, s.cont)  # 100 points, 5 yd off: wins
    c.G.Guess(s.x + 4000, s.y, s.cont)
    run(net, clock, 31 + 11)
    for p in (a, b, c):
        g = p.game
        assert g.phase == "over" and list(g.winners.values()) == ["Bob-Realm"] and g.tiebreak, p.name
        st = list(p.G.Standings(g).values())
        assert [s.name for s in st] == ["Bob-Realm", "Ann-Realm", "Cid-Realm"]
        assert st[0].total == st[1].total == 100 and st[0].fine == 99.8 and st[1].fine == 99.21
    tip = [l[1] for l in a.G.PlayerTip(a.game, "Bob-Realm").values()]
    assert tip[1].startswith("Round 1: 99.8 points")
    assert [l[1] for l in a.G.PlayerTip(a.game, "Cid-Realm").values()][1].startswith("Round 1: 7 points")


def test_tied_numbers_show_decimals_only_when_tied(solo):
    p, _, _ = solo
    show = lambda rows: list(p.G.ShowTied(p.lua.table_from([p.lua.table_from(r) for r in rows])).values())
    assert show([(100, 99.8), (100, 99.6), (92, 91.5)]) == ["99.8", "99.6", "92"]
    assert show([(100, 99.96), (100, 99.92)]) == ["99.96", "99.92"]
    assert show([(0, 0), (0, 0)]) == ["0", "0"]
    assert show([(57, 56.5), (57, 56.5)]) == ["56.50", "56.50"]  # (a real tie: the same distance)


def test_first_and_last_names_end_up_the_same_everywhere():
    # (WoW Forever: the others see "Ann Smith-Realm" while Ann's own game may call her "Ann-Realm")
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net, group="PARTY", seen_as="Ann Smith-Realm")
    b = Player("Bob-Realm", clock, net, group="PARTY", seen_as="Bob Jones-Realm")
    assert a.G.Start("party", 1)
    run(net, clock, 2)
    for p in (a, b):
        assert p.game.phase == "look" and sorted(p.game.order.values()) == ["Ann Smith-Realm", "Bob Jones-Realm"], p.name
    assert a.game.me == "Ann Smith-Realm" and a.game.isHost and b.game.me == "Bob Jones-Realm"
    assert a.G.Short("Ann Smith-Realm") == "Ann Smith"
    a.G.Guess(300, 300, 0)
    b.G.Guess(300, 3300, 0)
    run(net, clock, 31 + 11)
    for p in (a, b):
        assert p.game.phase == "over" and list(p.game.winners.values()) == ["Ann Smith-Realm"], p.name
        assert all(v is not None for v in (p.game.players["Bob Jones-Realm"].scores[1],))


def test_an_open_game_with_first_and_last_names():
    clock, net = Clock(), Net()
    a = Player("Ann-Realm", clock, net, seen_as="Ann Smith-Realm")
    b = Player("Bob-Realm", clock, net, seen_as="Bob Jones-Realm")
    a.G.Start("open", 1)
    shown = b.G.Linkify(a.G.JoinText(), "Ann Smith")  # (the chat's author: first and last name)
    assert b.G.OnLink(shown.split("|H")[1].split("|h")[0])
    run(net, clock, 31)
    for p in (a, b):
        assert p.game.phase == "look" and sorted(p.game.order.values()) == ["Ann Smith-Realm", "Bob Jones-Realm"], p.name


def test_the_scoreboard_shows_five_and_scrolls(solo):
    p, _, _ = solo
    def rows(n, offset):
        r, off = p.G.BoardRows(n, offset)
        return list(r.values()), off
    assert p.G.BOARD_ROWS == 5
    assert rows(3, 0) == ([1, 2, 3], 0)
    assert rows(5, 2) == ([1, 2, 3, 4, 5], 0)  # (five fit: nothing to scroll)
    assert rows(12, 3) == ([4, 5, 6, 7, 8], 3)
    assert rows(12, 99) == ([8, 9, 10, 11, 12], 7)  # (scrolled past the end: the last five)
    assert rows(12, -4) == ([1, 2, 3, 4, 5], 0)
    # this player's own row, pinned under the five when it isn't among them
    rows3 = lambda n, offset, mine: (lambda r: (list(r[0].values()), r[1]))(p.G.BoardRows(n, offset, mine))
    assert rows3(12, 0, 3) == ([1, 2, 3, 4, 5], 0)
    assert rows3(12, 0, 9) == ([1, 2, 3, 4, 5, 9], 0)
    assert rows3(12, 6, 2) == ([7, 8, 9, 10, 11, 2], 6)
    assert rows3(4, 0, 4) == ([1, 2, 3, 4], 0)


def test_the_others_see_that_a_player_guessed_but_not_where():
    (a, b), clock, net = party(2)
    a.G.Start("party", 1)
    run(net, clock, 2)
    b.G.Guess(300, 3300, 0)
    b.G.Guess(300, 3000, 0)  # (moved: nothing more is sent)
    sent = [m for _, m, _, _ in net.queue]
    assert sent == [f"Y:{a.game.id}:1"]
    run(net, clock, 1)
    bob = a.game.players["Bob-Realm"]
    assert bob.placed[1] and bob.scores[1] is None and bob.guesses[1] is None
    assert not (a.game.players["Ann-Realm"].placed or {}).get(1)


def test_against_bots_plays_a_whole_game_without_the_network(solo):
    p, clock, net = solo
    assert p.G.Start("bots", 3)
    g = p.game
    assert g.bots and g.mode == "party" and not g.channel
    run(net, clock, 3)
    g = p.game
    assert g.phase == "look" and len(g.order) == 1 + p.G.BOT_COUNT
    bots = [n for n in g.order.values() if n != "Me-Realm"]
    names = {n.split("-")[0] for n in bots}
    assert len(names) == p.G.BOT_COUNT and names <= set(p.G.BOT_NAMES.values())
    run(net, clock, 20)  # (the bots have placed their guesses, but where only shows when the time's up)
    g = p.game
    assert all(g.players[n].placed[1] and g.players[n].scores[1] is None for n in bots)
    p.G.Guess(g.spot.x + 30, g.spot.y, g.spot.cont)
    run(net, clock, 3 * 50)
    g = p.game
    assert g.phase == "over" and not g.reason and len(g.winners) >= 1
    for n in list(g.order.values()):
        assert all(g.players[n].scores[r] is not None for r in range(1, 4)), n
    assert net.queue == []  # (nothing went onto the network)
    p.G.Leave()


def test_bot_names_are_twenty_and_distinct(solo):
    p, _, _ = solo
    names = list(p.G.BOT_NAMES.values())
    assert len(names) == 20 and len(set(names)) == 20


def test_no_developer_tools_ship():
    # (the demo, reporting pictures and the capture tool are in the private AzerothGPS_StreetView_Dev)
    shipped = "".join(f.read_text(encoding="utf-8") for f in ADDON.glob("*.lua"))
    for word in ("Report picture", "DEMO_NAMES", "/sv demo", "db.reported", "AGPSCapture"):
        assert word not in shipped, word

