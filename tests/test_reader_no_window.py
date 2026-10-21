"""No window to read is said only when the player asked, with a key.

Shutting down, the game takes every window away seconds before it ends, and the reader said "no
window open" twice to a player who had just chosen Exit to Desktop (measured 21 October 2026). Her
decision the same day: when the game empties the screen by itself, the reader stays quiet.

A window the reader cannot read is said once: the layer count it changed is taken before the
failure, so the loop does not see the change again every round.
"""
from typing import NoReturn

import pytest

from tools.ck3 import guimap, reader, reading
from tools.nvda import speech


@pytest.fixture(autouse=True)
def no_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reading, 'live', lambda *_args, **_kwargs: (None, []))
    monkeypatch.setattr(reader.Reader, 'counts', lambda _self: {})


def bare() -> reader.Reader:
    """A reader standing on nothing, without a game: only what `refresh` touches."""
    found = reader.Reader.__new__(reader.Reader)
    found.pid, found.game, found.tables = 0, None, None    # type: ignore[assignment]
    return found


def test_a_key_on_no_window_is_answered(heard: speech.Recorder) -> None:
    assert bare().refresh(asked=True) is None
    assert len(heard.spoken) == 1


def test_the_game_emptying_the_screen_is_quiet(heard: speech.Recorder) -> None:
    assert bare().refresh(asked=False) is None
    assert heard.spoken == []


def test_a_window_it_cannot_read_is_said_once(monkeypatch: pytest.MonkeyPatch,
                                              heard: speech.Recorder) -> None:
    def unknown(*_args: object, **_kwargs: object) -> NoReturn:
        raise guimap.GuiError('no expansion for this window')
    monkeypatch.setattr(reading, 'live', unknown)
    monkeypatch.setattr(reader.Reader, 'counts', lambda _self: {1: 3})
    found = bare()
    assert found.refresh(asked=False) is None
    assert len(heard.spoken) == 1
    assert found.counted == {1: 3}      # what the loop compares with, so the next round is quiet
