"""The channel's one retry, and when a missing link is said, checked without a game.

A link that breaks during a question is closed and tried once more, so a pipe the DLL opened again
answers. If it stays shut, the game has ended: `Gone`, without a word. A link that is not there to
begin with is said once, and not tried twice.
"""
import io

import pytest

from tools.ck3 import channel
from tools.nvda import speech


class BrokenLink:
    """A connection that fails on first use, the way the pipe does once the game has gone."""

    def __init__(self) -> None:
        self.closed = False

    def fileno(self) -> int:
        raise OSError('the pipe is gone')

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> speech.Recorder:
    """NVDA replaced by a recorder, and the pipe pointed at a name nobody opened."""
    recorder = speech.Recorder()
    monkeypatch.setattr(speech, '_client', recorder)
    monkeypatch.setattr(channel, 'PIPE', channel.PIPE + '_nobody_opened')
    return recorder


def test_a_broken_link_is_tried_once_more(monkeypatch: pytest.MonkeyPatch) -> None:
    links: list[BrokenLink] = []

    def connect() -> BrokenLink:
        links.append(BrokenLink())
        return links[-1]

    monkeypatch.setattr(channel, '_connect', connect)
    monkeypatch.setattr(channel, '_connection', None)
    with pytest.raises(OSError, match='the pipe is gone'):
        channel.ask('hello')
    assert len(links) == 2
    assert all(link.closed for link in links)
    assert channel._connection is None


def test_a_link_that_breaks_and_stays_shut_ends_without_a_word(
        monkeypatch: pytest.MonkeyPatch, heard: speech.Recorder) -> None:
    monkeypatch.setattr(channel, '_connection', BrokenLink())
    with pytest.raises(channel.Gone):
        channel.ask('waitkey 400')
    assert heard.spoken == []


def test_a_link_that_is_not_there_is_said_once(monkeypatch: pytest.MonkeyPatch, heard: speech.Recorder) -> None:
    attempts: list[int] = []
    connect = channel._connect

    def counted() -> io.FileIO:
        attempts.append(1)
        return connect()

    monkeypatch.setattr(channel, '_connect', counted)
    monkeypatch.setattr(channel, '_connection', None)
    with pytest.raises(OSError) as raised:
        channel.ask('hello')
    assert not isinstance(raised.value, channel.Gone)
    assert len(heard.spoken) == 1 and heard.brailled == heard.spoken
    assert len(attempts) == 1
