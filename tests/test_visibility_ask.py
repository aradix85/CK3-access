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
FLAG, ALPHA = 0x0D0, 0x108


def chunk(open_window: bool) -> bytes:
    data = bytearray(derive.CHUNK)
    data[FLAG] = 0x00 if open_window else 0x18
    struct.pack_into('<f', data, ALPHA, 1.0 if open_window else 0.0)
    return bytes(data)


def test_the_player_is_asked_and_no_key_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    state = {'open': False}

    def said(text: str, *_args: object, **_keywords: object) -> None:
        asked.append(text)
        state['open'] = not state['open']           # the player presses F1

    def refused(command: str, **_keywords: object) -> str:
        raise AssertionError(f'the product sent {command!r}')

    monkeypatch.setattr(speech, 'output', said)
    monkeypatch.setattr(channel, 'ask', refused)
    monkeypatch.setattr(channel, 'read', lambda address, _count: chunk(state['open'] and address == SUBJECT))
    monkeypatch.setattr(time, 'sleep', lambda _seconds: None)
    named = {derive.SUBJECT: SUBJECT, derive.CONTROL: CONTROL}
    fields = derive.visibility_fields({}, named, player=True)  # type: ignore[typeddict-item]
    assert (fields['flag'], fields['alpha']) == (FLAG, ALPHA)
    assert len(asked) == 2 and all('F1' in text for text in asked)
    with pytest.raises(AssertionError, match='sendkey 112'):
        derive.visibility_fields({}, named, player=False)  # type: ignore[typeddict-item]
