"""The start waits for the channel in silence, and speaks only when it never comes.

**What this is guarding.** On 21 October 2026 a start that worked said "the link with it is gone":
the wait asked through `channel.ask`, which speaks the moment no pipe is there, and the DLL had not
opened it yet. Checked without a game: the injector, the pipe and the path to
the exe are stand-ins, and a recorder takes NVDA's place.
"""
import pathlib
import time

import pytest

from tools import paths
from tools.ck3 import channel, inject, start_game
from tools.nvda import speech


@pytest.fixture
def no_game(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setattr(paths, 'require', lambda _name: str(tmp_path / 'ck3.exe'))
    monkeypatch.setattr(inject, 'start_with_dll', lambda _exe, _dll, _arguments: 4242)


class SlowPipe:
    """Shut for the first three looks and open after that, like a DLL slow to open its pipe. Asking
    while it is shut speaks, as the real `channel.ask` does."""

    def __init__(self) -> None:
        self.looks = 0

    def _open(self) -> bool:
        self.looks += 1
        return self.looks > 3

    def alive(self) -> bool:
        return self._open()

    def ask(self, _command: str, timeout: float = 60.0) -> str:
        assert 0 < timeout < 60.0, 'the start gives its question a time limit of its own'
        if not self._open():
            raise OSError(speech.failure('the game', 'the link with it is gone', 'start the game again'))
        return 'channel\t4242\tbuilt today\n'


@pytest.mark.usefixtures('no_game')
def test_a_pipe_that_is_not_there_yet_is_waited_for_in_silence(
        monkeypatch: pytest.MonkeyPatch, heard: speech.Recorder) -> None:
    pipe = SlowPipe()
    monkeypatch.setattr(channel, 'alive', pipe.alive)
    monkeypatch.setattr(channel, 'ask', pipe.ask)
    monkeypatch.setattr(time, 'sleep', lambda _seconds: None)

    assert start_game.start() == (4242, 'channel\t4242\tbuilt today')
    assert pipe.looks > 3
    assert heard.spoken == []


@pytest.mark.usefixtures('no_game')
def test_a_channel_that_never_answers_says_so_once(
        monkeypatch: pytest.MonkeyPatch, heard: speech.Recorder) -> None:
    monkeypatch.setattr(channel, 'alive', lambda: False)

    with pytest.raises(OSError, match='did not answer'):
        start_game.start(timeout=0.0)
    assert len(heard.spoken) == 1
    said = heard.spoken[0]
    assert said is not None and said.startswith('the game: the channel did not answer')
