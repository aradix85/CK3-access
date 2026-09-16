"""The speech seam, checked without a sound card.

Five cases, because the seam is two functions. A recorder stands in for the NVDA client, so what
runs here is the real `output` and the real `failure` rather than a stand-in for them.

**What this is guarding.** On 15 September 2026 the seam was changed and its one caller was not,
so the beta gate called a function that no longer existed and nobody noticed until the next
session read the file.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'nvda'))
import speech


@pytest.fixture
def heard():
    """A recorder in place of the NVDA client, put back afterwards."""
    recorder = speech.Recorder()
    previous = speech._client
    speech._client = recorder
    yield recorder
    speech._client = previous


def test_speech_and_braille_carry_the_same_text(heard):
    speech.output('the council has five seats')
    assert heard.spoken == ['the council has five seats']
    assert heard.brailled == ['the council has five seats']


def test_a_different_braille_text_is_possible_because_it_is_the_exception(heard):
    speech.output('the council has five seats', braille='council 5')
    assert heard.spoken == ['the council has five seats']
    assert heard.brailled == ['council 5']


def test_replace_silences_first_and_queue_does_not(heard):
    speech.output('first', speech.REPLACE)
    assert heard.cancels == 1
    speech.output('second', speech.QUEUE)
    assert heard.cancels == 1


def test_an_unknown_mode_breaks_where_it_happens(heard):
    with pytest.raises(ValueError):
        speech.output('text', 'sideways')


def test_a_failure_is_written_out_even_when_it_cannot_be_spoken(capsys):
    """The one place in the seam allowed to swallow, and the reason it is allowed.

    An exit that raises while carrying a failure loses the failure it was carrying. So the
    sentence goes to stderr first, which cannot fall over, and only then to NVDA.
    """
    class Deaf(speech.Recorder):
        def nvdaController_speakText(self, text):
            raise OSError('NVDA is gone')

    previous = speech._client
    speech._client = Deaf()
    try:
        sentence = speech.failure('the game', 'the link with it is gone', 'start it again')
    finally:
        speech._client = previous

    assert sentence == 'the game: the link with it is gone, start it again'
    assert sentence in capsys.readouterr().err
