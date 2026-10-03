"""What is drawn and what is switched off, decided from the state byte without a game.

**What this is guarding.** Until 3 October 2026 a window counted as drawn only with a state byte of
zero, and the activity planner - on the screen, read by the recogniser - carried 0x20, so the reader
found no window and every click into it was refused. 0x20 is the game letting the mouse through,
and only 0x08, on the widget or an ancestor, hides. The fixtures below are the values measured on
1.20.0.3: a drawn panel at 0x00 under a root at 0x20, a shut one at 0x18, the planner at 0x20.
"""

from tools.ck3 import derive, reading

# address -> (vtable, x, y, width, height, parent, name, text), the shape `derive.widgets` returns
NODES = {
    1: (0, 0.0, 0.0, 1920.0, 1200.0, 0, 'root', ''),
    2: (0, 0.0, 0.0, 1920.0, 1200.0, 1, 'middle', ''),
    3: (0, 0.0, 0.0, 610.0, 1200.0, 2, 'character_window', ''),
    4: (0, 0.0, 0.0, 610.0, 1200.0, 2, 'council_window', ''),
    5: (0, 0.0, 0.0, 1920.0, 1200.0, 2, 'activity_planner', ''),
    6: (0, 10.0, 10.0, 50.0, 20.0, 4, 'button_inside_shut_window', ''),
    7: (0, 10.0, 10.0, 50.0, 20.0, 3, 'gone_between_walk_and_read', ''),
}
FLAGS = {1: 0x20, 2: 0x20, 3: 0x00, 4: 0x18, 5: 0x20, 6: 0x00}


def test_only_0x08_along_the_chain_hides(monkeypatch):
    monkeypatch.setattr(derive, 'flags_for', lambda addresses: {a: FLAGS[a] for a in addresses if a in FLAGS})
    drawn = derive.shown(NODES, [3, 4, 5, 6, 7])
    assert drawn == {3: 0x00, 5: 0x20}, 'a window at 0x20 is drawn, one at 0x18 and all below it are not'
    assert drawn[5] & derive.PASSES_CLICKS and not drawn[3] & derive.PASSES_CLICKS


def test_switched_off_is_read_on_the_widget_itself():
    assert reading.state_word({'state': 0x06}) == 'unavailable'      # where `enabled = no` sits
    assert reading.state_word({'state': 0x02}) == 'unavailable'      # inherited by the text inside
    assert reading.state_word({'state': 0x20}) is None
    assert reading.state_word({'state': None}) is None
