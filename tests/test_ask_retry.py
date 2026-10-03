"""The channel's one retry, checked without a game.

A link that breaks during a question is closed and tried once more, so a pipe the DLL opened again
answers. A link that will not open at all is not tried twice: opening it already said so out loud,
and a second try would say it again.
"""
from typing import NoReturn

import pytest

from tools.ck3 import channel


class BrokenLink:
    """A connection that fails on first use, the way the pipe does once the game has gone."""

    def __init__(self) -> None:
        self.closed = False

    def fileno(self) -> int:
        raise OSError('the pipe is gone')

    def close(self) -> None:
        self.closed = True


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


def test_a_link_that_will_not_open_is_not_tried_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    def connect() -> NoReturn:
        attempts.append(1)
        raise OSError('the link is gone')

    monkeypatch.setattr(channel, '_connect', connect)
    monkeypatch.setattr(channel, '_connection', None)
    with pytest.raises(OSError, match='the link is gone'):
        channel.ask('hello')
    assert len(attempts) == 1
