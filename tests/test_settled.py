"""`harvest.settled` without the game: a layout that comes to rest, an animation that never does,
and a window that keeps changing.

The harvest waits for a window's layout before it records it. On 12 November 2026 a chain round on
Saru stopped at a nomad's domicile, where the icon of an empty building slot bobs up and down for as
long as the window stands: the same two widgets moved in every read.
"""
import itertools
import time
from collections.abc import Iterable, Iterator
from typing import cast

import pytest

from tools.ck3 import harvest, widgettree, windowmap

WINDOW = 1


def tree(first: float, second: float) -> widgettree.Nodes:
    """A window with two children, each at its own height."""
    return {WINDOW: (0, 0.0, 0.0, 100.0, 100.0, 0, 'window', ''),
            2: (0, 0.0, first, 10.0, 10.0, WINDOW, '', ''),
            3: (0, 0.0, second, 10.0, 10.0, WINDOW, '', '')}


class Reads:
    """A game that hands out one tree per read."""

    def __init__(self, trees: Iterable[widgettree.Nodes]) -> None:
        self.trees: Iterator[widgettree.Nodes] = iter(trees)

    def tree(self) -> widgettree.Nodes:
        return next(self.trees)


def settled(trees: Iterable[widgettree.Nodes]) -> widgettree.Nodes:
    reads = Reads(trees)
    return harvest.settled(cast(windowmap.Game, reads), reads.tree(), WINDOW)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, 'sleep', lambda _: None)


def test_a_layout_that_comes_to_rest_is_returned_where_it_rests() -> None:
    assert settled([tree(389, 0), tree(911, 0), tree(911, 0)])[2][2] == 911


def test_the_same_widgets_moving_in_every_read_are_an_animation(capsys: pytest.CaptureFixture[str]) -> None:
    bobbing = (tree(height, 0) for height in itertools.cycle([-0.2, -3.8, -1.3]))
    assert settled(bobbing)[3][2] == 0
    assert '1 widgets below 1 never stand still' in capsys.readouterr().out


def test_other_widgets_moving_from_read_to_read_is_no_animation() -> None:
    turns = (tree(read // 2, (read + 1) // 2) for read in itertools.count())
    with pytest.raises(SystemExit, match='still moving'):
        settled(turns)
