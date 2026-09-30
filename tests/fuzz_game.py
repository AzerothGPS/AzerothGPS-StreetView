"""Random Where in the Azeroth? games between simulated players, looking for errors.

Not part of the normal test run (slow): `python tests/fuzz_game.py [minutes] [seed] [report file]`.
Each game picks a mode (solo, party, whisper, raid), 1-40 players, 1/3/5 rounds, and random
behavior: guesses anywhere (other continents, Zephras Isle, Undercity's level), solo submits,
players leaving or dropping out, declined invitations, busy players, lacking packs, lost or late
messages, the map window's buttons (show again, report). Any Lua error, a game that never ends,
or results that disagree between players is reported with the seed to replay it.
"""

import random
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_game as T  # noqa: E402  (the harness: Player, Net, Clock, PACK)

CONTS = [0, 1, 2991, 10001]
EXTRA = "\n".join(f'  {{ id = "{c}-{x}-{y}", cont = {c}, x = {x}, y = {y} }},'
                  for c, x, y in [(0, 1500, -800), (1, -600, -4400), (2991, 1800, 600), (0, 4000, 2500),
                                  (1, 9900, 2400), (0, -8600, 700)])
PACK = T.PACK.replace("points = {", "points = {\n" + EXTRA, 1)


class LossyNet(T.Net):
    def __init__(self, rng, loss=0.0, delay=0.0):
        super().__init__()
        self.rng, self.loss, self.delay, self.late = rng, loss, delay, []

    def deliver(self):
        n = 0
        held, self.late = self.late, []
        queue, self.queue = held + self.queue, []
        for sender, msg, chat, target in queue:
            if self.delay and self.rng.random() < self.delay:
                self.late.append((sender, msg, chat, target))  # (arrives on a later tick)
                continue
            for name, p in list(self.players.items()):
                if not self.hears(name, sender, chat, target):
                    continue
                if self.loss and self.rng.random() < self.loss:
                    continue
                p.G.OnMessage(msg, chat, sender)
                n += 1
        return n


def names(n):
    return [f"P{i:02d}-Realm" for i in range(1, n + 1)]


def make_game(rng):
    mode = rng.choice(["solo", "party", "whisper", "raid", "open"])
    n = {"solo": 1, "whisper": 2, "party": rng.randint(2, 5), "raid": rng.randint(2, 40), "open": rng.randint(2, 42)}[mode]
    if mode == "solo" and rng.random() < 0.3:
        n = rng.randint(2, 6)  # (others in the group who aren't playing)
    lossy = rng.random() < 0.2
    net = LossyNet(rng, loss=rng.choice([0.0, 0.02, 0.1]) if lossy else 0.0,
                   delay=rng.choice([0.0, 0.2]) if lossy else 0.0)
    clock = T.Clock()
    group = {"party": "PARTY", "raid": "RAID"}.get(mode, "PARTY" if n > 1 and mode == "solo" else None)
    players = []
    for i, name in enumerate(names(n)):
        pack = PACK
        if i and rng.random() < 0.15:  # (a player lacking some street views)
            for sid in rng.sample(["0-300-300", "0-900-900", "1-100-100", "1-2000-500"], rng.randint(1, 3)):
                pack = pack.replace(f'id = "{sid}"', f'id = "{sid}-gone"')
        p = T.Player(name, clock, net, pack=pack, group=group, answer=(i == 0 or rng.random() > 0.1))
        p.random = (lambda r: (lambda a=None, b=None: r.random() if a is None else r.randint(a, b)))(random.Random(rng.random()))
        players.append(p)
    return mode, players, clock, net


def spot_guess(rng, p):
    g = p.game
    s = g and g.spot
    if s and rng.random() < 0.6:  # near the answer
        d = rng.choice([0, 20, 200, 800, 3000, 9000])
        a = rng.random() * 6.283
        return s.x + d * __import__("math").cos(a), s.y + d * __import__("math").sin(a), rng.choice([s.cont, s.cont, 0, 1])
    return rng.uniform(-12000, 12000), rng.uniform(-6000, 6000), rng.choice(CONTS)


def play(seed, log):
    rng = random.Random(seed)
    mode, players, clock, net = make_game(rng)
    host = players[0]
    rounds = rng.choice([1, 3, 5])
    # busy players: already in a solo game
    busy = set()
    for p in players[1:]:
        if rng.random() < 0.05:
            p.G.Start("solo", 1)
            busy.add(p.name)
    target = players[1].name.split("-")[0] if mode == "whisper" else None
    started = host.G.Start("party" if mode == "raid" else mode, rounds, target)
    if not started:
        return f"{mode}: Start refused ({host.printed[-1:] })"
    # an open game: strangers click the posted link, some after it started or once it's full
    clicks = {}
    if mode == "open":
        host.G.PostLink("SAY")
        link = f"garrmission:agpssv:{host.game.id}:{rounds}:{host.name.split('-')[0]}"
        for p in players[1:]:
            clicks[p.name] = clock.t + rng.uniform(0.5, 38)
    t_end = clock.t + 60 + rounds * 60 + 120
    left, dropped, gone, snap = set(), set(), set(), {}
    while clock.t < t_end:
        clock.t += 0.5
        for p in players:
            if p.name in clicks and clock.t >= clicks[p.name]:
                clicks.pop(p.name)
                p.G.OnLink(link)
        for p in players:  # (a player who dropped out of the group still runs their own game)
            if p.name in gone:
                continue  # (disconnected: their client is gone)
            p.G.Tick()
            g = p.game
            if not g:
                continue
            if g.phase == "over" and p.name not in snap:  # (the result, before it closes itself)
                snap[p.name] = {
                    "reason": g.reason, "round": g.round,
                    "scores": {n: tuple(g.players[n].scores[r] for r in range(1, (g.round or 0) + 1))
                               for n in g.order.values() if g.players[n]},
                    "winners": list(g.winners.values()) if g.winners else []}
                continue
            r = rng.random()
            if g.phase == "look":
                if r < 0.08:
                    x, y, c = spot_guess(rng, p)
                    p.G.Guess(x, y, c)
                elif r < 0.09 and g.mode == "solo":
                    p.G.SubmitNow()
                elif r < 0.095:
                    p.G.ShowAgain()
            if r < 0.0003 and p is not host and p.name in net.players:  # someone disconnects mid-game
                net.players.pop(p.name)
                gone.add(p.name)
                for q in net.players.values():  # (the game drops them from the group a little later)
                    q.inGroupGone = True
                continue
            if r > 0.9995 and p.name not in left:  # someone leaves mid-game
                left.add(p.name)
                p.G.Leave()
            elif r > 0.999 and p is not host and p.name in net.players:  # someone drops out of the group
                net.players.pop(p.name)
                dropped.add(p.name)
                p.group = None
                p.G.OnRoster()
                for q in net.players.values():
                    q.G.OnRoster()
        net.deliver()
        if gone and rng.random() < 0.1:  # (the group roster catches up with a disconnect)
            for q in net.players.values():
                q.G.OnRoster()
        if not clicks and all((not p.game) or p.game.phase == "over" for p in players):
            for p in players:  # (take the last results)
                g = p.game
                if g and p.name not in snap:
                    snap[p.name] = {"reason": g.reason, "round": g.round,
                                    "scores": {n: tuple(g.players[n].scores[r] for r in range(1, (g.round or 0) + 1))
                                               for n in g.order.values() if g.players[n]},
                                    "winners": list(g.winners.values()) if g.winners else []}
            break
    # --- checks ---
    problems, warnings = [], []
    live = [p for p in players if p.game]
    for p in live:
        g = p.game
        if p.name in gone:
            continue
        if g.phase != "over":
            (warnings if (net.loss or net.delay) else problems).append(f"{p.name} still in phase {g.phase} (round {g.round}/{g.rounds}) after {t_end - 1000:.0f}s")
        if g.round and g.round > g.rounds:
            problems.append(f"{p.name}: round {g.round} > {g.rounds}")
        for name in list(g.order.values()) if g.order else []:
            pl = g.players[name]
            if not pl:
                problems.append(f"{p.name}: {name} in order but not in players")
                continue
            for r in range(1, (g.round or 0) + 1):
                sc = pl.scores[r]
                if sc is not None and not (0 <= sc <= 100 and int(sc) == sc):
                    problems.append(f"{p.name}: {name} round {r} score {sc}")
    # everyone who finished normally agrees on the results (no message loss only)
    if not net.loss and not net.delay:
        out = left | dropped | gone | busy
        done = [n for n, v in snap.items() if not v["reason"] and n not in out]
        if len(done) > 1:
            def table(n):
                return {k: v for k, v in snap[n]["scores"].items() if k not in out}
            ref = table(done[0])
            for n in done[1:]:
                tb = table(n)
                if tb != ref:
                    diff = {k: (ref.get(k), tb.get(k)) for k in set(ref) | set(tb) if ref.get(k) != tb.get(k)}
                    problems.append(f"results differ between {done[0]} and {n}: {dict(list(diff.items())[:3])}")
                    break
            for n in done[1:]:
                if snap[n]["winners"] != snap[done[0]]["winners"]:
                    problems.append(f"winners differ: {done[0]} {snap[done[0]]['winners']} vs {n} {snap[n]['winners']}")
                    break
    desc = (f"{mode:7s} players={len(players):2d} rounds={rounds} loss={net.loss} delay={net.delay} "
            f"left={len(left)} dropped={len(dropped)} gone={len(gone)} busy={len(busy)} finished={len(snap)}/{len(players)}"
            + (f" reason={live[0].game.reason!r}" if live and live[0].game.reason else ""))
    return desc, problems, warnings


def signature(pr):
    import re
    return re.sub(r"P\d\d-Realm|\d+", "#", pr.splitlines()[0])[:120]


def main():
    minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 5
    seed0 = int(sys.argv[2]) if len(sys.argv) > 2 else int(time.time())
    report = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    fails, warns, modes = {}, {}, {}
    t0, i = time.time(), 0
    last = t0
    while time.time() - t0 < minutes * 60:
        seed = seed0 + i
        i += 1
        try:
            out = play(seed, print)
            desc, problems, warnings = (out, [], []) if isinstance(out, str) else out
        except Exception as e:  # (a Lua error surfaces here)
            desc, problems, warnings = "crashed", [f"{type(e).__name__}: {e}"], []
        m = desc.split()[0]
        modes[m] = modes.get(m, 0) + 1
        for pr in problems:
            fails.setdefault(signature(pr), []).append((seed, desc, pr))
        for pr in warnings:
            warns.setdefault(signature(pr), []).append((seed, desc, pr))
        if time.time() - last > 60 or time.time() - t0 >= minutes * 60:
            last = time.time()
            lines = [f"{i} games in {time.time() - t0:.0f}s, seeds {seed0}..{seed0 + i - 1}: {modes}",
                     f"{sum(len(v) for v in fails.values())} problems in {len(fails)} kinds; "
                     f"{sum(len(v) for v in warns.values())} warnings (message loss) in {len(warns)} kinds"]
            for kind, items in sorted(fails.items(), key=lambda kv: -len(kv[1])):
                seed, desc, pr = items[0]
                lines.append(f"PROBLEM x{len(items)}: {pr.splitlines()[0][:200]}\n    first: seed={seed} {desc}")
            for kind, items in sorted(warns.items(), key=lambda kv: -len(kv[1]))[:10]:
                seed, desc, pr = items[0]
                lines.append(f"warning x{len(items)}: {pr.splitlines()[0][:160]}\n    first: seed={seed} {desc}")
            text = "\n".join(lines)
            if report:
                report.write_text(text + "\n", encoding="utf-8")
            else:
                print(text, flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
