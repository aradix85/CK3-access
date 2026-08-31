"""Thin seam to NVDA. Everything the user needs to hear passes through here.

Two modes:
  REPLACE - silence anything speaking and speak. For an answer to a keystroke.
  QUEUE   - join the back of the line. For a run of lines that belong together.

Deliberately no interrupt-and-resume: it interrupts and then carries on with the old sentence,
which feels as though nothing happened.

Braille always goes with it. There is no call here that only speaks, because that is exactly
how the Fallout 4 accessibility mod lost its braille display: one omission in one place is
enough to lose a whole channel.

The DLL can do more than this seam uses. nvdaController_speakSsml takes a symbol level and a
priority - NORMAL 0, NEXT 1, NOW 2 - and setOnSsmlMarkReachedCallback reports back where the
speech is. See nvdaController.h next to this file. Two measured facts before building on it:
passing speakSsml's fourth parameter, asynchronous, as false blocks until the speech finishes and
then returns error 1223; and NEXT can discard speech that is already waiting rather than merely
overtaking it.
"""
import ctypes
import os
import sys

DLL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvdaControllerClient.dll')
REPLACE, QUEUE = 'replace', 'queue'

_client = ctypes.windll.LoadLibrary(DLL)


def nvda_running():
    return _client.nvdaController_testIfRunning() == 0


def silence():
    _client.nvdaController_cancelSpeech()


def output(text, mode=REPLACE, braille=None):
    """Speak and write to the braille display. braille=None means: the same text."""
    if mode == REPLACE:
        silence()
    elif mode != QUEUE:
        raise ValueError('unknown mode: %r' % mode)

    error = _client.nvdaController_speakText(ctypes.c_wchar_p(text))
    if error:
        raise OSError('NVDA returned error code %d on speech' % error)

    error = _client.nvdaController_brailleMessage(ctypes.c_wchar_p(braille or text))
    if error:
        raise OSError('NVDA returned error code %d on braille' % error)


def failure(where, what, remedy, mode=REPLACE):
    """The exit for a failure: one sentence carrying where, what, and what to do now.

    No error code, no path, no exclamation mark without words. A player cannot act on an offset
    or a traceback, and a tester who hears nothing cannot report anything at all.

    This is the one place in the seam that is allowed to swallow, and the reason is the rule
    itself. Everywhere else an exception breaks where it happens, but an exit that raises while
    carrying a failure loses that failure. So the sentence goes to stderr first, which cannot
    fail, and only then to NVDA. It returns the sentence, so a caller can raise with the same
    words the player just heard.
    """
    sentence = '%s: %s, %s' % (where, what, remedy)
    print(sentence, file=sys.stderr, flush=True)
    try:
        output(sentence, mode)
    except Exception as trouble:
        print('that sentence did not reach NVDA: %s' % trouble, file=sys.stderr, flush=True)
    return sentence
