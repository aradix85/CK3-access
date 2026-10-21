"""No window to read is said only when the player asked, with a key.

Shutting down, the game takes every window away seconds before it ends, and the reader said "no
window open" twice to a player who had just chosen Exit to Desktop (measured 21 October 2026). Her
decision the same day: when the game empties the screen by itself, the reader stays quiet.
"""
import pytest

from tools.ck3 import reader, reading
from tools.nvda import speech


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> speech.Recorder:
    recorder = speech.Recorder()
    monkeypatch.setattr(speech, '_client', recorder)
    monkeypatch.setattr(reading, 'live', lambda *_args, **_kwargs: (None, []))
    monkeypatch.setattr(reader.Reader, 'counts', lambda _self: {})
    return recorder


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
