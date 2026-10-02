"""The tree walk, checked without a game: a node the channel cannot read has to be heard.

**What this is guarding.** On 1.20.0.3 the walk skipped nodes it could not read in silence, and the
decisions window with its 526 widgets was missing from the tree while it was on the screen. The DLL
now reports such a node, and `derive.widgets` has to turn that report into a sentence a player
hears - once per address, because the reader walks the toast container every round.

The channel is replaced by a fixed answer and NVDA by a recorder, so what runs is the real walk
and the real seam.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'nvda'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'ck3'))
import speech
import derive

WIDGET = 'w\t1000\t5\t0\t0\t10\t10\t0\troot\t'


@pytest.fixture
def heard(monkeypatch):
    """A recorder in place of the NVDA client, and nothing said before this test."""
    recorder = speech.Recorder()
    monkeypatch.setattr(speech, '_client', recorder)
    monkeypatch.setattr(derive, '_MISSING_SAID', set())
    return recorder


def answer(monkeypatch, *lines):
    monkeypatch.setattr(derive.channel, 'ask', lambda command, timeout=60: '\n'.join(lines))


def test_a_whole_tree_says_nothing(heard, monkeypatch):
    answer(monkeypatch, WIDGET)
    assert list(derive.widgets(0x1000)) == [0x1000]
    assert heard.spoken == []


def test_an_unreadable_node_is_said_and_the_rest_still_comes_back(heard, monkeypatch):
    answer(monkeypatch, WIDGET, 'missing\t2000\tunreadable')
    assert list(derive.widgets(0x1000)) == [0x1000]
    assert len(heard.spoken) == 1
    assert 'could not be read' in heard.spoken[0]
    assert heard.brailled == heard.spoken


def test_the_same_node_is_said_once_and_a_new_one_again(heard, monkeypatch):
    answer(monkeypatch, WIDGET, 'missing\t2000\tunreadable')
    derive.widgets(0x1000)
    derive.widgets(0x1000)
    assert len(heard.spoken) == 1
    answer(monkeypatch, WIDGET, 'missing\t3000\tchild list unreadable')
    derive.widgets(0x1000)
    assert len(heard.spoken) == 2
