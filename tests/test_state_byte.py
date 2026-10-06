"""What is drawn and what is switched off, decided from the state byte without a game.

**What this is guarding.** Until 3 October 2026 a window counted as drawn only with a state byte of
zero, and the activity planner - on the screen, read by the recogniser - carried 0x20, so the reader
found no window and every click into it was refused. 0x20 is the game letting the mouse through,
and only 0x08, on the widget or an ancestor, hides. The fixtures below are the values measured on
1.20.0.3: a drawn panel at 0x00 under a root at 0x20, a shut one at 0x18, the planner at 0x20.

**A toast is the same rule.** Until 6 October 2026 the reader decided for itself whether a toast
showed: it looked no higher than the toast container, took a byte it could not read as not hiding,
and read the text field of every widget, also where that field is the neighbour's. It asks
`derive.shown` now, up to the root, and reads text on the text classes only.
"""
from collections.abc import Callable, Iterable

import pytest

from tools.ck3 import derive, reader, reading

# address -> (vtable, x, y, width, height, parent, name, text), the shape `derive.widgets` returns
NODES: derive.Nodes = {
    1: (0, 0.0, 0.0, 1920.0, 1200.0, 0, 'root', ''),
    2: (0, 0.0, 0.0, 1920.0, 1200.0, 1, 'middle', ''),
    3: (0, 0.0, 0.0, 610.0, 1200.0, 2, 'character_window', ''),
    4: (0, 0.0, 0.0, 610.0, 1200.0, 2, 'council_window', ''),
    5: (0, 0.0, 0.0, 1920.0, 1200.0, 2, 'activity_planner', ''),
    6: (0, 10.0, 10.0, 50.0, 20.0, 4, 'button_inside_shut_window', ''),
    7: (0, 10.0, 10.0, 50.0, 20.0, 3, 'gone_between_walk_and_read', ''),
}
FLAGS = {1: 0x20, 2: 0x20, 3: 0x00, 4: 0x18, 5: 0x20, 6: 0x00}

# A toast container under a layer under the root. The default variant shows a title; the contest
# variant is shut; an icon beside the title carries the text of its neighbour in the pool; and one
# text box went away between the walk and the question, so its byte cannot be read.
TOAST: derive.Nodes = {
    11: (0, 0.0, 0.0, 1920.0, 1200.0, 0, 'root', ''),
    12: (0, 0.0, 0.0, 1920.0, 1200.0, 11, 'hud_layer', ''),
    13: (0, 800.0, 40.0, 320.0, 80.0, 12, 'toast_container_widget', ''),
    14: (0, 0.0, 0.0, 320.0, 80.0, 13, 'default', ''),
    15: (0, 0.0, 0.0, 320.0, 80.0, 13, 'contest', ''),
    16: (0, 10.0, 10.0, 300.0, 20.0, 14, 'title', 'Toast title'),
    17: (0, 10.0, 10.0, 300.0, 20.0, 15, 'title', 'Contest title'),
    18: (0, 0.0, 10.0, 8.0, 8.0, 14, 'icon', 'Neighbour'),
    19: (0, 10.0, 40.0, 300.0, 20.0, 14, 'gone', 'Gone'),
}
TOAST_FLAGS = {11: 0x20, 12: 0x20, 13: 0x00, 14: 0x00, 15: 0x18, 16: 0x00, 17: 0x00, 18: 0x20}
TOAST_CLASSES = {16: 'Textbox', 17: 'Textbox', 18: 'Icon', 19: 'Textbox'}
ABOVE: derive.Nodes = {a: TOAST[a] for a in (11, 12, 13)}


def flags_from(table: dict[int, int]) -> Callable[[Iterable[int]], dict[int, int]]:
    """`derive.flags_for` over a table: a byte that is not in it cannot be read, and is left out."""
    return lambda addresses: {a: table[a] for a in addresses if a in table}


def toast_with(monkeypatch: pytest.MonkeyPatch, flags: dict[int, int]) -> str | None:
    """The toast the reader would say with these state bytes."""
    def subtree(root: int) -> derive.Nodes:
        assert root == 13, 'only the container is walked'
        return {a: node for a, node in TOAST.items() if a >= 13}

    monkeypatch.setattr(derive, 'flags_for', flags_from(flags))
    monkeypatch.setattr(derive, 'widgets', subtree)
    monkeypatch.setattr(derive, 'class_map',
                        lambda _pid, addresses: {a: TOAST_CLASSES.get(a, 'Widget') for a in addresses})
    return reader.toast_text(0, [13], ABOVE)


def test_only_0x08_along_the_chain_hides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(derive, 'flags_for', flags_from(FLAGS))
    drawn = derive.shown(NODES, [3, 4, 5, 6, 7])
    assert drawn == {3: 0x00, 5: 0x20}, 'a window at 0x20 is drawn, one at 0x18 and all below it are not'
    assert drawn[5] & derive.PASSES_CLICKS and not drawn[3] & derive.PASSES_CLICKS


def test_switched_off_is_read_on_the_widget_itself() -> None:
    assert reading.state_word(0x06) == 'unavailable'      # where `enabled = no` sits
    assert reading.state_word(0x02) == 'unavailable'      # inherited by the text inside
    assert reading.state_word(0x20) is None
    assert reading.state_word(None) is None


def test_a_toast_says_only_its_drawn_text_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    said = toast_with(monkeypatch, TOAST_FLAGS)
    assert said == 'Toast title', 'the shut variant, the icon and the text box that went away say nothing'


def test_a_toast_is_hidden_from_above(monkeypatch: pytest.MonkeyPatch) -> None:
    assert toast_with(monkeypatch, {**TOAST_FLAGS, 12: 0x28}) is None, 'a hidden layer hides the toast'
    unreadable = {a: flag for a, flag in TOAST_FLAGS.items() if a != 12}
    assert toast_with(monkeypatch, unreadable) is None, 'an ancestor that cannot be read is not drawn'
    assert toast_with(monkeypatch, {**TOAST_FLAGS, 13: 0x18}) is None, 'a shut container says nothing'
