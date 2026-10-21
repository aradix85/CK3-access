"""What the tests share: NVDA replaced by a recorder, so a test hears what a player would."""
import pytest

from tools.nvda import speech


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> speech.Recorder:
    """A recorder in place of the NVDA client, put back afterwards."""
    recorder = speech.Recorder()
    monkeypatch.setattr(speech, '_client', recorder)
    return recorder
