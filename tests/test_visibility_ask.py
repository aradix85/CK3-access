"""The visibility derivation in the product asks the player for F1 and sends no key, without a game.

Her decision, 21 October 2026: the product never sends a key, so a start that has to derive the
visibility offsets again asks the player to press F1 twice and watches memory move; the tools keep
pressing it themselves. The memory of two window objects is faked, and it moves when the player is
asked, the way it moves when a person presses F1.
"""
import struct
import time

import pytest

from tools.ck3 import channel, derive
from tools.nvda import speech

SUBJECT, CONTROL = 0x1000, 0x2000
FLAG, ALPHA, COUNTER, SIZE = 0x0D0, 0x108, 0x3AC, 0x3F0


def chunk(open_window: bool, ticks: int) -> bytes:
    data = bytearray(SIZE)
    data[FLAG] = 0x00 if open_window else 0x18
    struct.pack_into('<f', data, ALPHA, 1.0 if open_window else 0.0)
    struct.pack_into('<I', data, COUNTER, ticks)
    return bytes(data)


def test_the_player_is_asked_and_no_key_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A counter ticks in both windows at every look, as the game's does, and the player presses
    only at the sixth look after being asked: a tick is no press (21 November 2026)."""
    asked: list[str] = []
    state = {'open': False, 'looks': 0, 'press_at': -1}

    def said(text: str, *_args: object, **_keywords: object) -> None:
        asked.append(text)
        state['press_at'] = state['looks'] + 12      # two reads a look

    def refused(command: str, **_keywords: object) -> str:
        raise AssertionError(f'the product sent {command!r}')

    def read(address: int, _count: int) -> bytes:
        state['looks'] += 1
        if state['looks'] == state['press_at']:
            state['open'] = not state['open']       # the player presses F1
        return chunk(bool(state['open']) and address == SUBJECT, state['looks'] // 2)

    monkeypatch.setattr(speech, 'output', said)
    monkeypatch.setattr(channel, 'ask', refused)
    monkeypatch.setattr(channel, 'read', read)
    monkeypatch.setattr(time, 'sleep', lambda _seconds: None)
    named = {derive.SUBJECT: SUBJECT, derive.CONTROL: CONTROL}
    fields = derive.visibility_fields({}, named, player=True, size=SIZE)  # type: ignore[typeddict-item]
    assert (fields['flag'], fields['alpha']) == (FLAG, ALPHA)
    assert len(asked) == 2 and all('F1' in text for text in asked)
    with pytest.raises(AssertionError, match='sendkey 112'):
        derive.visibility_fields({}, named, player=False, size=SIZE)  # type: ignore[typeddict-item]
