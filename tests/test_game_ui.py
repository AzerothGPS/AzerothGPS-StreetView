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


@pytest.fixture
def ui():
    clock, net = Clock(), Net()
    p = Player("Me-Realm", clock, net)
    lua = p.lua
    lua.execute(FRAMES)
    p.ns.db = lua.eval("{ viewer = {} }")
    load = lua.eval("function(src, name) return assert(load(src, '@' .. name)) end")
    load((ADDON / "Viewer.lua").read_text(encoding="utf-8"), "Viewer.lua")("AzerothGPS_StreetView", p.ns)
    p.G.Init(lua.eval("CreateFrame('Button')"))  # (the map's panel; the game's io opens the real viewer)
    panels = []
    p.G.OnPanel(lambda pn: panels.append(pn))
    return p, clock, net, panels[0], lua


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
    assert panel.rows[1].name._shown and plain(panel.rows[1].total._text) == "Average 100"
    # the street view closed: its box goes and Show Street View comes; opened again, the other way round
    p.ns.Viewer.CloseGame()
    p.G.RefreshTimer()
    assert not box._shown and panel.reopen._shown
    p.G.ShowAgain()
    p.G.RefreshTimer()
    assert box._shown and not panel.reopen._shown
    run(net, clock, 10)
    assert p.game.round == 2 and plain(box.head._text) == "Heroic  Round 2 of 3"
    assert plain(panel.rows[1].total._text) == "Average 100"  # (not halved by the round being played)


def test_a_game_without_street_views_ends_on_the_panel(ui):
    p, clock, net, panel, lua = ui
    p.G.Usable = lambda pt: False
    p.G.Start("solo", 1)
    assert p.game.phase == "over" and p.game.reason == "No street views are installed"
    assert plain(panel.title._text) == "Where in the Azeroth?  Normal" and not panel.reopen._shown
    p.G.RefreshTimer()  # (no endless redraw: the panel and its timer agree there's nothing to show again)
    assert not panel.reopen._shown
