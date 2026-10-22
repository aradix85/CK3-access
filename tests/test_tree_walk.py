"""The tree walk, checked without a game: a node the channel cannot read has to be heard.

**What this is guarding.** On 1.20.0.3 the walk skipped nodes it could not read in silence, and the
decisions window with its 526 widgets was missing from the tree while it was on the screen. The DLL
now reports such a node, and `widgettree.widgets` has to turn that report into a sentence a player
hears - once per address, because the reader walks the toast container every round.

The channel is replaced by a fixed answer and NVDA by a recorder, so what runs is the real walk
and the real seam.
"""

import pytest

from tools.ck3 import channel, widgettree
from tools.nvda import speech

WIDGET = 'w\t1000\t5\t0\t0\t10\t10\t0\troot\t'


@pytest.fixture(autouse=True)
def nothing_said_before(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(widgettree, '_MISSING_SAID', set())
    # Game process 7, where vtable 5 is a text box and every other one is not.
    monkeypatch.setattr(widgettree, '_TEXT_VTABLES', {7: {5}})


def answer(monkeypatch: pytest.MonkeyPatch, *lines: str) -> None:
    monkeypatch.setattr(channel, 'ask', lambda command, **_keywords: 'channel\t7\tbuilt today' if command == 'hello'
                        else '\n'.join(lines))


def test_a_whole_tree_says_nothing(heard: speech.Recorder, monkeypatch: pytest.MonkeyPatch) -> None:
    answer(monkeypatch, WIDGET)
    assert list(widgettree.widgets(0x1000)) == [0x1000]
    assert heard.spoken == []


def test_an_unreadable_node_is_said_and_the_rest_still_comes_back(heard: speech.Recorder,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    answer(monkeypatch, WIDGET, 'missing\t2000\tunreadable')
    assert list(widgettree.widgets(0x1000)) == [0x1000]
    assert len(heard.spoken) == 1
    said = heard.spoken[0]
    assert said is not None and 'could not be read' in said
    assert heard.brailled == heard.spoken


def test_the_same_node_is_said_once_and_a_new_one_again(heard: speech.Recorder,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    answer(monkeypatch, WIDGET, 'missing\t2000\tunreadable')
    widgettree.widgets(0x1000)
    widgettree.widgets(0x1000)
    assert len(heard.spoken) == 1
    answer(monkeypatch, WIDGET, 'missing\t3000\tchild list unreadable')
    widgettree.widgets(0x1000)
    assert len(heard.spoken) == 2


def test_a_text_cut_short_names_its_widget(heard: speech.Recorder, monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    """The line in the terminal names the widget and the ones above it, so a loss that will not come
    back on demand still says where it was."""
    answer(monkeypatch, WIDGET, 'w\t2000\t5\t0\t0\t10\t10\t1000\tlong_text\tx',
           'missing\t2000\ttext of 65296 characters cut short')
    widgettree.widgets(0x1000)
    assert '(long_text < root)' in capsys.readouterr().err
    assert len(heard.spoken) == 1


def test_a_text_cut_short_on_another_class_is_no_loss(heard: speech.Recorder, monkeypatch: pytest.MonkeyPatch,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    """The text field of a progress bar holds something else, and nothing believes it."""
    answer(monkeypatch, WIDGET, 'w\t2000\t6\t0\t0\t10\t10\t1000\tconstruct_progressbar\tx',
           'missing\t2000\ttext of 262148 characters cut short')
    widgettree.widgets(0x1000)
    assert capsys.readouterr().err == ''
    assert heard.spoken == []
