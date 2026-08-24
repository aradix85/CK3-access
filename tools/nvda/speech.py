"""Thin seam to NVDA. Everything the user needs to hear passes through here.

Two modes:
  REPLACE - silence anything speaking and speak. For an answer to a keystroke.
  QUEUE   - join the back of the line. For a run of lines that belong together.

Deliberately no interrupt-and-resume: the user plays at speed zero and reads afterwards, so
nothing arrives that is allowed to cut across his reading.
"""
import ctypes, os

DLL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvdaControllerClient.dll')
REPLACE, QUEUE = 'vervang', 'wachtrij'

_client = ctypes.windll.LoadLibrary(DLL)


def nvda_running():
    return _client.nvdaController_testIfRunning() == 0


def silence():
    _client.nvdaController_cancelSpeech()


def speak(text, mode=REPLACE, braille=None):
    if mode == REPLACE:
        silence()
    elif mode != QUEUE:
        raise ValueError('onbekende modus: %r' % mode)

    error = _client.nvdaController_speakText(ctypes.c_wchar_p(text))
    if error:
        raise OSError('NVDA gaf foutcode %d' % error)
    if braille:
        _client.nvdaController_brailleMessage(ctypes.c_wchar_p(braille))
