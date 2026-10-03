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
    if k == "CreateFontString" then return function() local f = Make("FontString") FONTS[#FONTS + 1] = f return f end end
    if k == "CreateTexture" then return function() return Make("Texture") end end
    if k:match("^%u") then return function() end end
  end })
end
FRAMES_MADE, FONTS = {}, {}
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
  MapButtonParent = function() return Make("Frame") end, MapCanvas = function() return Make("Frame") end,
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
    lua.execute("SlashCmdList = SlashCmdList or {}")
    load((ADDON / "Core.lua").read_text(encoding="utf-8"), "Core.lua")("AzerothGPS_StreetView", p.ns)
    p.ns.db = lua.eval("{ viewer = {} }")
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


def test_a_spot_with_a_title_of_its_own_shows_it(ui):
    # (the dev addon's comparisons: "Thunder Bluff: In Game" in the title, not the zone and coordinates)
    p, clock, net, panel, lua = ui
    spot = lua.eval("""{ id = "tb-game", cont = 1, x = -1248.3, y = 68.1, facing = 1, cube = { pad = 0.08 },
      title = "Thunder Bluff: In Game", pack = { root = "R\\\\", ext = "jpg" } }""")
    p.ns.Viewer.Open(spot)
    titles = [str(f._text) for f in lua.eval("FONTS").values() if f._text is not None]
    assert "Thunder Bluff: In Game" in titles
    assert not any("57.2" in t for t in titles)  # (not the zone and coordinates)


def test_the_media_hooks_set_the_view_the_window_and_the_menu(ui):
    # (the dev addon's media shots for the CurseForge page and the wiki: our own windows put in a set state)
    p, clock, net, panel, lua = ui
    V = p.ns.Viewer
    spot = lua.eval("""{ id = "m1", cont = 1, x = -1248.3, y = 68.1, facing = 1, cube = { pad = 0.08 },
      title = "Media", pack = { root = "R\\\\", ext = "jpg" } }""")
    V.Open(spot)
    assert V.LookAt(1.5, 20, 60)
    cur = V.Current()
    assert abs(V.Heading() - 1.5) < 1e-9 and cur.lat == 20 and cur.fov == 60
    assert V.LookAt(None, 120, 5)  # (clamped: no farther up than the viewer goes, no closer zoom)
    assert cur.lat == 85 and cur.fov == 40
    lon = cur.lon
    assert V.Pan(10, -100) and cur.lon == lon + 10 and cur.lat == -15
    assert V.Pan(0, -100) and cur.lat == -85
    V.Place(900, 0, 40)
    assert lua.eval("AzerothGPSStreetViewFrame")._w == 900
    V.Place(5000)
    assert lua.eval("AzerothGPSStreetViewFrame")._w == 1400  # (the viewer's widest)
    # the corner box folded and opened as its button does
    p.G.Start("solo", 3)
    box = corner_box(lua)
    V.SetHudFolded(True)
    assert plain(box.fold.label._text) == "+" and not box.head._shown
    V.SetHudFolded(False)
    assert plain(box.fold.label._text) == "-" and box.head._shown
    # the game's menu at a step (its frame given: the chips are its children), then folded away
    step = p.G.OpenMenu("level")
    fly = [f for f in lua.eval("FRAMES_MADE").values() if f.steps is not None][0]
    same = lua.eval("rawequal")
    assert same(step, fly.steps["level"]) and fly.step == "level" and step._shown and not fly.steps["mode"]._shown
    assert p.G.OpenMenu(None) is True and fly.target == 0


def test_a_players_marker_tooltip_shows_without_the_mouse():
    # (the dev addon's media shots: the tooltip of a player's marker in a round's result)
    clock, net = Clock(), Net()
    ann = Player("Ann-Realm", clock, net, group="PARTY")
    Player("Bob-Realm", clock, net, group="PARTY")
    with_windows(ann)
    lua = ann.lua
    ann.G.Start("party", 1)
    net.deliver()
    net.deliver()
    run(net, clock, 1)
    assert not ann.G.marks.Hover("Bob")  # (nothing drawn yet)
    ann.G.Guess(300, 310, 0)
    run(net, clock, 32)
    assert ann.game.phase == "result"
    ctx = lua.eval("""{ cont = 0, scale = 1, zoom = 1000, ToScreen = function(x, y) return x / 10, y / 10 end,
      Dot = function() end, Line = function() end, Icon = function() end }""")
    ann.G.Draw(ctx)
    assert ann.G.marks.Hover("Ann")
    assert plain(lua.eval("GameTooltip")._text) == "You"  # (Gm.PlayerTip's first line for your own)


def test_a_game_without_street_views_ends_on_the_panel(ui):
    p, clock, net, panel, lua = ui
    p.G.Usable = lambda pt: False
    p.G.Start("solo", 1)
    assert p.game.phase == "over" and p.game.reason == "No street views are installed"
    assert plain(panel.title._text) == "Where in the Azeroth?  Normal" and not panel.reopen._shown
    p.G.RefreshTimer()  # (no endless redraw: the panel and its timer agree there's nothing to show again)
    assert not panel.reopen._shown


def test_shift_click_on_a_boss_opens_its_street_view(ui):
    # the user, 2026-10-02: Shift + left-click a boss in a dungeon's map for its street view (AzerothGPS API 12),
    # said at the top of the map when StreetView is installed; the figure finds a dungeon's spots on its map too
    p, clock, net, panel, lua = ui
    lua.execute("""
      SHIFT = {}
      AzerothGPS.OnIconShiftClick = function(owner, fn, hint) SHIFT.owner, SHIFT.fn, SHIFT.hint = owner, fn, hint end
      AzerothGPS.LocateWorld = function() end
      UIErrorsFrame = { AddMessage = function(self, m) SHIFT.err = m end }
    """)
    spot = p.D.byId["20036-1-1"]
    spot.cube, spot.facing = lua.eval("{ pad = 0.08 }"), 0
    load = lua.eval("function(src, name) return assert(load(src, '@' .. name)) end")
    load((ADDON / "Figure.lua").read_text(encoding="utf-8"), "Figure.lua")("AzerothGPS_StreetView", p.ns)
    p.ns.Figure.Init()
    S = lua.globals().SHIFT
    assert S.owner == "StreetView" and p.ns.Figure.Level(20036) == 20036
    boss = lua.eval('{ kind = "boss", name = "Boss", x = 5, y = 1, cont = 20036 }')
    assert S.fn(boss) is True
    assert p.ns.Viewer.Current().p.id == "20036-1-1" and abs(p.ns.Viewer.Heading()) < 1e-6  # (looking at the boss: north)
    assert p.ns.Viewer.Current().fov == 110  # (opens zoomed out, as every street view: the user, 2026-10-02)
    assert S.hint(boss) == "its street view" and S.hint(lua.eval('{ kind = "boss", cont = 20036 }')) == "its street view"
    far = lua.eval('{ kind = "boss", name = "Far Boss", x = 500, y = 1, cont = 20036 }')
    assert S.fn(far) is True and S.err == "No street view of Far Boss yet" and S.hint(far) is None
    assert S.hint(lua.eval('{ kind = "boss", cont = 20389 }')) is None  # (a dungeon without street views: no hint)


def test_a_party_invitation_is_a_link_in_chat_not_a_popup():
    # the user, 2026-10-02: the level and rounds shown before joining, and an invitation a link in chat (party, raid,
    # whisper) rather than a popup: no spam invites, nothing in the way while navigating
    clock, net = Clock(), Net()
    ann = Player("Ann-Realm", clock, net, group="PARTY")
    bob = Player("Bob-Realm", clock, net, group="PARTY")
    with_windows(bob)  # (Bob's game asks the real way: Gm.Init set io.ask)
    lua = bob.lua
    lua.execute("StaticPopup_Show = function() error('no popups') end")
    ann.G.Start("party", 3, None, "heroic")
    net.deliver()
    line = next(s for s in bob.printed if "invites you" in s)
    assert "Ann invites you to play:" in line and "[Join Where in the Azeroth?: Heroic, 3 rounds]" in line
    link = line.split("|H")[1].split("|h")[0]
    assert bob.game is None  # (nothing until the click)
    assert bob.G.OnLink(link) and bob.game.phase == "joined" and bob.game.level == "heroic"
    assert not bob.G.OnLink(link) and "no longer open" in bob.printed[-1]  # (once only)


def test_the_map_follows_the_arrows_and_goes_back_on_close(ui):
    # the user, 2026-10-02: walking by the arrows, the map centers on each spot; closing puts it back where it was before
    # the first arrow, unless the player moved the map meanwhile (then it's left alone for the rest of that viewing)
    p, clock, net, panel, lua = ui
    lua.execute("""
      MAP = { x = 0, y = 0, cont = 1, zoom = 500, calls = {} }
      AzerothGPS.LocateWorld = function() end
      AzerothGPS.View = function() return MAP.x, MAP.y, MAP.cont, 0, 1, MAP.zoom end
      AzerothGPS.SaveView = function() return { x = MAP.x, y = MAP.y, cont = MAP.cont, zoom = MAP.zoom } end
      AzerothGPS.LookAt = function(c, x, y, z) MAP.cont, MAP.x, MAP.y, MAP.zoom = c, x, y, z; table.insert(MAP.calls, "look") end
      AzerothGPS.RestoreView = function(v) MAP.cont, MAP.x, MAP.y, MAP.zoom = v.cont, v.x, v.y, v.zoom; table.insert(MAP.calls, "restore") end
      UIErrorsFrame = { AddMessage = function() end }
    """)
    p.D.Load(lua.eval("""{ { name = "t", root = "R\\\\", ext = "jpg", points = {
      { id = "1-100-100", cont = 1, x = 100, y = 100 }, { id = "1-100-300", cont = 1, x = 100, y = 300 },
      { id = "1-100-500", cont = 1, x = 100, y = 500 } } } }"""))
    V, M = p.ns.Viewer, lua.globals().MAP
    west = 1.5707963
    V.Open(p.D.byId["1-100-100"], west)
    frame = lua.eval("AzerothGPSStreetViewFrame")
    V.GoToward(west)
    assert V.Current().p.id == "1-100-300" and (M.x, M.y, M.zoom) == (100, 300, 500)  # (the map on the spot, its zoom)
    V.GoToward(west)
    assert (M.x, M.y) == (100, 500)
    frame._scripts["OnHide"](frame)  # (closed: back where it was before the first arrow)
    assert (M.x, M.y, M.zoom) == (0, 0, 500) and list(M.calls.values())[-1] == "restore"
    # moved by the player after the first arrow: the map left alone for the rest of the viewing
    V.Open(p.D.byId["1-100-100"], west)
    V.GoToward(west)
    M.x, M.y = 777, 888  # (dragged)
    V.GoToward(west)
    assert (M.x, M.y) == (777, 888)
    frame._scripts["OnHide"](frame)
    assert (M.x, M.y) == (777, 888) and list(M.calls.values())[-1] == "look"
    # no arrow clicked: closing leaves the map alone
    n = len(M.calls)
    V.Open(p.D.byId["1-100-100"], west)
    frame._scripts["OnHide"](frame)
    assert len(M.calls) == n


def test_without_the_pictures_every_way_in_shows_the_notice(ui):
    # the user, 2026-10-03: the pictures are a download of their own, AzerothGPS_StreetView_DataPack (an unlisted
    # CurseForge project StreetView's requires); without them the figure, a boss's Shift-click and Where in the
    # Azeroth? (its button, a link, an invitation) show the same notice, and go no further
    p, clock, net, panel, lua = ui
    game_button = [f for f in lua.eval("FRAMES_MADE").values()
                   if f._kind == "Button" and f._w == 28 and f._scripts["OnClick"] is not None][0]
    p.D.Load(lua.eval("{}"))
    assert not p.ns.HasData()
    lua.execute("""
      SHIFT, ROADS, NOTICES = {}, 0, 0
      AzerothGPS.OnIconShiftClick = function(owner, fn, hint) SHIFT.fn, SHIFT.hint = fn, hint end
      AzerothGPS.LocateWorld = function() end
      AzerothGPS.ShowRoads = function() ROADS = ROADS + 1 end
      UIErrorsFrame = { AddMessage = function() end }
      AzerothGPS.Window = function(name, w, h, title)
        local f = CreateFrame("Frame", name) f.top, f.title = -30, title f:Hide() return f
      end
    """)
    # why: not installed, turned off, or loaded with nothing in it
    lua.execute('C_AddOns = { GetAddOnInfo = function() return "AzerothGPS_StreetView_DataPack", "", "", false, "MISSING" end,'
                ' IsAddOnLoaded = function() return false end }')
    assert p.ns.DataState() == "missing"
    lua.execute('C_AddOns.GetAddOnInfo = function() return "AzerothGPS_StreetView_DataPack", "", "", false, "DISABLED" end')
    assert p.ns.DataState() == "disabled" and "turned off" in p.ns.DataNoticeText("disabled")
    lua.execute('C_AddOns.IsAddOnLoaded = function() return true end')
    assert p.ns.DataState() == "empty" and "Reinstall" in p.ns.DataNoticeText("empty")
    lua.execute('C_AddOns = nil')
    assert p.ns.DataState() == "missing"
    # the notice: AzerothGPS's popup window, the download's name and its page to copy
    p.ns.ShowDataNotice()
    w = lua.globals().AzerothGPSStreetViewDataNotice
    assert w._shown and w.title == "Street View Pictures Missing"
    assert "AzerothGPS StreetView DataPack" in w.text._text and "restart the game" in w.text._text
    assert w.box._text == p.ns.DATAPACK_URL
    # (by project id, whatever its address; the DataPack's own once packs.json has it, StreetView's until then)
    import json
    data_id = json.loads((ADDON.parents[1] / "packs.json").read_text(encoding="utf-8"))["data"]["curseforge_project"]
    assert p.ns.DATAPACK_URL == f"https://www.curseforge.com/projects/{data_id or 1721639}"
    w.Hide(w)
    # every way in shows it, and goes no further
    show = p.ns.ShowDataNotice
    p.ns.ShowDataNotice = lua.eval("function(show) return function() NOTICES = NOTICES + 1 show() end end")(show)
    G = lua.globals()
    load = lua.eval("function(src, name) return assert(load(src, '@' .. name)) end")
    load((ADDON / "Figure.lua").read_text(encoding="utf-8"), "Figure.lua")("AzerothGPS_StreetView", p.ns)
    p.ns.Figure.Init()
    p.ns.Figure.Pick()  # (dragging the figure)
    assert G.NOTICES == 1 and G.ROADS == 0
    boss = lua.eval('{ kind = "boss", name = "Boss", x = 5, y = 1, cont = 20036 }')
    assert G.SHIFT.hint(boss) == "its street view"  # (still offered in a dungeon: the click says where to get them)
    assert G.SHIFT.fn(boss) is True and G.NOTICES == 2 and p.ns.Viewer.Current() is None
    p.ns.Here()  # (/sv here, the figure's plain click)
    assert G.NOTICES == 3
    p.G.io.noData = lua.eval("function() NOTICES = NOTICES + 1 end")  # (the real io's: ns.ShowDataNotice)
    game_button._scripts["OnClick"](game_button)  # (Where in the Azeroth?'s button: no menu)
    assert G.NOTICES == 4
    assert not p.G.Start("solo", 3) and G.NOTICES == 5 and p.game is None
    assert not p.G.OnLink("garrmission:agpssv:123456:3:Ann-Realm") and G.NOTICES == 6 and p.game is None
    assert lua.globals().AzerothGPSStreetViewDataNotice._shown


def test_without_azerothgps_a_notice_says_so(ui):
    # the user, 2026-10-03: installed without AzerothGPS, a popup says so (the toc lists it as an optional dependency,
    # so StreetView still loads: a required one left it unloaded, nothing said); turned off or too old too
    p, clock, net, panel, lua = ui
    toc = (ADDON / "AzerothGPS_StreetView.toc").read_text(encoding="utf-8")
    assert "## OptionalDeps: AzerothGPS" in toc and "## Dependencies:" not in toc
    G = lua.globals()
    lua.execute("AzerothGPS.version = 12")
    assert p.ns.CheckAzerothGPS() is None and G.AzerothGPSStreetViewNeedsAzerothGPS is None  # (all is well)
    lua.execute("AzerothGPS.version = 11")
    assert p.ns.AzerothGPSState() == "old" and "1.1.0 or later" in p.ns.AzerothGPSNoticeText("old")
    saved = G.AzerothGPS
    lua.execute("AzerothGPS = nil")
    lua.execute('C_AddOns = { GetAddOnInfo = function() return "AzerothGPS", "", "", false, "DISABLED" end }')
    assert p.ns.AzerothGPSState() == "disabled" and "turned off" in p.ns.AzerothGPSNoticeText("disabled")
    lua.execute('C_AddOns = { GetAddOnInfo = function() return nil, nil, nil, false, "MISSING" end }')
    lua.execute("PRINTED = {} print = function(...) PRINTED[#PRINTED + 1] = table.concat({ ... }, ' ') end")
    assert p.ns.CheckAzerothGPS() == "missing"
    # the notice made here, in AzerothGPS's window style (its own Window isn't there): what's needed and its page
    w = G.AzerothGPSStreetViewNeedsAzerothGPS
    assert w._shown and "needs AzerothGPS" in w.text._text and "restart the game" in w.text._text
    assert w.box._text == p.ns.AZEROTHGPS_URL == "https://www.curseforge.com/projects/1712208"
    assert any("needs AzerothGPS" in m for m in G.PRINTED.values())  # (and in chat)
    G.AzerothGPS = saved
