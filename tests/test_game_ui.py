"""Where in the Azeroth?'s windows under lupa, on a stand-in for the game's frames: Game.lua's panel on the
map and Viewer.lua's corner box (the user, 2026-10-01: the game's details in the street view's top-right
corner, the map's panel kept short). They draw without errors and show what the game's state says."""

import pytest

from test_game import ADDON, Clock, Net, Player, plain, run

lupa = pytest.importorskip("lupa")

# Any method (a capitalized key) is a no-op, except the ones that keep what the tests check (text, shown)
# and the sizes the layouts read; other fields are nil until the code sets them.
FRAMES = r"""
local function Plain(s) return (tostring(s or ""):gsub("|c%x%x%x%x%x%x%x%x", ""):gsub("|r", "")) end
local Methods = {
  SetText = function(self, s) self._text = s end,
  GetText = function(self) return self._text end,
  SetScript = function(self, ev, fn) self._scripts[ev] = fn end,
  GetScript = function(self, ev) return self._scripts[ev] end,
  Show = function(self) self._shown = true end,
  Hide = function(self) self._shown = false end,
  IsShown = function(self) return self._shown end,
  IsVisible = function(self) return self._shown end,
  SetShown = function(self, on) self._shown = on and true or false end,
  SetSize = function(self, w, h) self._w, self._h = w, h end,
  SetWidth = function(self, w) self._w = w end,
  SetHeight = function(self, h) self._h = h end,
  GetWidth = function(self) return self._w or 400 end,
  GetHeight = function(self) return self._h or 200 end,
  GetStringWidth = function(self) return #Plain(self._text) * 6 end,
  GetStringHeight = function(self) return self._text and 12 or 0 end,
  GetFrameLevel = function() return 1 end,
  GetEffectiveScale = function() return 1 end,
  GetScale = function() return 1 end,
  GetLeft = function() return 0 end,
  GetTop = function() return 0 end,
  GetRight = function() return 0 end,
  GetBottom = function() return 0 end,
  GetCenter = function() return 0, 0 end,
  GetFrameStrata = function() return "HIGH" end,
  GetChildren = function() end,
  GetRegions = function() end,
  GetPoint = function() return "CENTER", nil, "CENTER", 0, 0 end,
}
local Make
Make = function(kind)
  return setmetatable({ _scripts = {}, _shown = true, _kind = kind }, { __index = function(_, k)
    if Methods[k] then return Methods[k] end
    if k == "CreateFontString" then return function() return Make("FontString") end end
    if k == "CreateTexture" then return function() return Make("Texture") end end
    if k:match("^%u") then return function() end end
  end })
end
FRAMES_MADE = {}
function CreateFrame(kind, name, parent, template)
  if template == "PortraitFrameTemplate" then error("not on this client") end -- (the viewer's own title bar)
  local f = Make(kind)
  FRAMES_MADE[#FRAMES_MADE + 1] = f
  if name then _G[name] = f end
  return f
end
UIParent, GameTooltip = Make("Frame"), Make("Frame")
UISpecialFrames = {}
GameTooltip_Hide = function() end
GetCursorPosition = function() return 0, 0 end
AzerothGPS = { version = 11,
  MapButtonParent = function() return Make("Frame") end,
  HoldMap = function() end, SetOverlay = function() end, Redraw = function() end, View = function() end,
  BaseContinent = function(c) return c end,
}
"""


def with_windows(p):
    """Player p with the viewer and the map's panel built (the game's io opens the real viewer): its panel."""
    lua = p.lua
    lua.execute(FRAMES)
    p.ns.db = lua.eval("{ viewer = {} }")
    load = lua.eval("function(src, name) return assert(load(src, '@' .. name)) end")
    load((ADDON / "Viewer.lua").read_text(encoding="utf-8"), "Viewer.lua")("AzerothGPS_StreetView", p.ns)
    p.G.Init(lua.eval("CreateFrame('Button')"))
    panels = []
    p.G.OnPanel(lambda pn: panels.append(pn))
    return panels[0]


@pytest.fixture
def ui():
    clock, net = Clock(), Net()
    p = Player("Me-Realm", clock, net)
    return p, clock, net, with_windows(p), p.lua


def shown_rows(rows):
    """The shown rows of a list (the corner box's or the panel's) as plain text."""
    out = []
    for i in range(1, len(rows) + 1):
        r = rows[i]
        if r.name._shown:
            out.append((plain(r.name._text), plain(r.last._text), plain(r.total._text)))
    return out


def corner_box(lua):
    boxes = [f for f in lua.eval("FRAMES_MADE").values() if f.head is not None and f.big is not None]
    assert len(boxes) == 1
    return boxes[0]


def test_the_street_view_has_the_games_details_and_the_map_little(ui):
    p, clock, net, panel, lua = ui
    assert p.G.Start("solo", 3, None, "heroic")
    box = corner_box(lua)
    assert box._shown and plain(box.head._text) == "Heroic  Round 1 of 3" and plain(box.big._text) == "0:30"
    assert plain(box.lines[1]._text) == "worth up to 100" and not box.lines[2]._shown
    # the map: the round and the time left; no level, no worth (they overflowed it under the timer)
    assert plain(panel.title._text) == "Round 1 of 3" and plain(panel.timer._text) == "0:30"
    assert plain(panel.status._text) == "Double-click the map where you think it is."
    assert not panel.rows[1].name._shown  # (no "Round score: -  Average 0" before a score)
    p.G.Guess(300, 310, 0)  # 10 yd off
    assert plain(panel.status._text) == "Guess placed. Double-click to move it." and panel.submit._shown
    run(net, clock, 31)
    p.G.RefreshTimer()  # (the driver's tick, ten times a second in the game)
    assert p.game.phase == "result" and plain(box.big._text) == "+100" and plain(panel.timer._text) == ""
    assert plain(box.lines[3]._text) == "next round in 0:09" and not box.lines[4]._shown
    # the scores: in the street view's box while it's up, not on the map
    assert shown_rows(box.rows) == [("Round score: 100", "", "Average 100")] and shown_rows(panel.rows) == []
    # the street view closed: its box goes, the scores and Show Street View come to the map; opened again,
    # the other way round
    p.ns.Viewer.CloseGame()
    p.G.RefreshTimer()
    assert not box._shown and panel.reopen._shown
    assert shown_rows(panel.rows) == [("Round score: 100", "", "Average 100")]
    p.G.ShowAgain()
    p.G.RefreshTimer()
    assert box._shown and not panel.reopen._shown and shown_rows(panel.rows) == []
    run(net, clock, 10)
    p.G.RefreshTimer()
    assert p.game.round == 2 and plain(box.head._text) == "Heroic  Round 2 of 3"
    assert shown_rows(box.rows) == [("Round scores: 100, -", "", "Average 100")]  # (not halved by this round)
    # "-" folds the box to the time left, "+" opens it again; kept for the next street views
    box.fold._scripts["OnClick"](box.fold)
    assert plain(box.fold.label._text) == "+" and box.big._shown and plain(box.big._text) == "0:29"
    assert not box.head._shown and not box.lines[1]._shown and shown_rows(box.rows) == []
    run(net, clock, 31 + 10)
    p.G.RefreshTimer()
    assert p.game.round == 3 and not box.head._shown and box.big._shown
    box.fold._scripts["OnClick"](box.fold)
    assert plain(box.fold.label._text) == "-" and box.head._shown and box.lines[1]._shown
    assert len(shown_rows(box.rows)) == 1


def test_a_big_games_list_scrolls_in_the_street_view():
    clock, net = Clock(), Net()
    names = ("Ann", "Bob", "Cid", "Dan", "Eve", "Fay", "Gus")
    ps = [Player(n + "-Realm", clock, net, group="PARTY") for n in names]
    panel = with_windows(ps[0])
    lua = ps[0].lua
    assert ps[0].G.Start("party", 1)
    assert [r[0] for r in shown_rows(panel.rows)] == ["1. Ann (you)"]  # (the lobby: the list on the map)
    net.deliver()
    net.deliver()
    run(net, clock, 1)
    ps[0].G.RefreshTimer()
    box = corner_box(lua)
    assert ps[0].game.phase == "look" and box._shown and shown_rows(panel.rows) == []
    assert [r[0] for r in shown_rows(box.rows)] == ["1. Ann (you)", "2. Bob", "3. Cid", "4. Dan", "5. Eve"]
    assert box.list._shown and plain(box.lines[2]._text) == "0 of 7 guessed"
    ps[0].ns.Viewer.OnHudWheel(-1)  # (the wheel down over the list)
    assert [r[0] for r in shown_rows(box.rows)] == ["2. Bob", "3. Cid", "4. Dan", "5. Eve", "6. Fay", "1. Ann (you)"]
    ps[0].ns.Viewer.OnHudWheel(-5)  # (no farther than the end)
    assert [r[0] for r in shown_rows(box.rows)][0] == "3. Cid" and panel.scroll == 2


def test_the_winners_name_rolls_and_the_box_glows():
    # the user, 2026-10-01: the victory glow on the street view's box too, and the winner's name in first
    # place rolling (size and color) instead of a line saying who won
    clock, net = Clock(), Net()
    ann = Player("Ann-Realm", clock, net, group="PARTY")
    Player("Bob-Realm", clock, net, group="PARTY")
    panel = with_windows(ann)
    lua = ann.lua
    ann.G.Start("party", 1)
    net.deliver()
    net.deliver()
    run(net, clock, 1)
    ann.G.Guess(300, 310, 0)  # 10 yd off: all of it, the celebration
    run(net, clock, 32 + 11)
    ann.G.RefreshTimer()
    box = corner_box(lua)
    assert ann.game.phase == "over" and ann.game.celebrate
    assert box.glow._shown and box.wash._shown and panel.glow._shown  # (the box glows as the panel does)
    assert box._scripts["OnUpdate"] is not None  # (in motion)
    wave = box.waves[1]
    letters = [wave.letters[i] for i in range(1, wave.n + 1)]
    assert plain(box.rows[1].name._text) == "1." and "".join(str(l._text) for l in letters) == "Ann"
    assert plain(wave.you._text) == "(you)" and box.rows[2].name._shown and not (len(box.waves) > 1 and box.waves[2].on)
    assert plain(box.big._text) == "You win!" and [plain(box.lines[1]._text)][0].startswith("closes in")
    for t in (0.0, 0.3, 1.7):  # (a few frames of the motion: no errors)
        ann.ns.Viewer.AnimateHud(t)
    # folded: the glow stays, the list (and its rolling name) goes
    box.fold._scripts["OnClick"](box.fold)
    assert box.glow._shown and not wave.on and not letters[0]._shown


def test_a_reload_brings_the_game_back_on_the_windows(ui):
    # the user, 2026-10-01: a /reload mustn't end the game. Saved as the UI unloads (ns.db.game), taken up
    # again once the windows are built and the reload is known (PLAYER_ENTERING_WORLD's isReloadingUi)
    from test_game import saved
    p, clock, net, panel, lua = ui
    p.G.Start("solo", 3, None, "mythic")
    run(net, clock, 4)
    src = saved(p.G.Snapshot(True))
    del net.players["Me-Realm"]
    clock.t += 7
    q = Player("Me-Realm", clock, net)
    panel2 = with_windows(q)
    assert q.game is None  # (the reload not known yet: nothing taken up)
    q.ns.db.game = q.lua.eval(src)
    q.ns.reloadedUI = True
    q.G.TryResume()
    box = corner_box(q.lua)
    assert q.game.phase == "look" and q.game.level == "mythic" and q.ns.db.game is None
    assert box._shown and plain(box.head._text) == "Mythic  Round 1 of 3" and plain(panel2.title._text) == "Round 1 of 3"
    q.G.TryResume()  # (once only)
    # a real login: a game saved before is dropped
    r = Player("Me-Realm", clock, net)
    with_windows(r)
    r.ns.db.game = r.lua.eval(src)
    r.ns.reloadedUI = False
    r.G.TryResume()
    assert r.game is None and r.ns.db.game is None


def test_a_game_without_street_views_ends_on_the_panel(ui):
    p, clock, net, panel, lua = ui
    p.G.Usable = lambda pt: False
    p.G.Start("solo", 1)
    assert p.game.phase == "over" and p.game.reason == "No street views are installed"
    assert plain(panel.title._text) == "Where in the Azeroth?  Normal" and not panel.reopen._shown
    p.G.RefreshTimer()  # (no endless redraw: the panel and its timer agree there's nothing to show again)
    assert not panel.reopen._shown
