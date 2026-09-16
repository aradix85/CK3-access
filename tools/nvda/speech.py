"""Thin seam to NVDA. Everything the user needs to hear passes through here.

Two functions: `output` says something, `failure` says something went wrong. That is the whole
layer, and it is meant to stay that way.

Two modes:
  REPLACE - silence anything speaking and speak. For an answer to a keystroke.
  QUEUE   - join the back of the line. For a run of lines that belong together.

Deliberately no interrupt-and-resume: it interrupts and then carries on with the old sentence,
which feels as though nothing happened.

Braille always goes with it. There is no call here that only speaks, because that is exactly how
the Fallout 4 accessibility mod lost its braille display, and the Skyrim Access mod this project
takes as a reference never calls brailleMessage at all. One omission in one place is enough to
lose a whole channel. A braille text that differs from the speech is allowed but is the
exception, and needs a reason at the call site; a shorter wording of the same sentence is not one.

**Nothing speaks when there is nothing to say.** A keystroke that turns up an empty list stays
quiet - decided 16 September 2026 - and there is no wrapper here that checks whether a handler
produced anything. Only a real fault speaks, through `failure`.

The client is a module attribute and is built on first use, so a test can put a recorder in its
place and this file imports on a machine with no NVDA. That one indirection is all the seam has.

The DLL can do more than this uses. nvdaController_speakSsml takes a symbol level and a priority
- NORMAL 0, NEXT 1, NOW 2 - and setOnSsmlMarkReachedCallback reports back where the speech is.
See nvdaController.h next to this file. Two measured facts before building on it: passing
speakSsml's fourth parameter, asynchronous, as false blocks until the speech finishes and then
returns error 1223; and NEXT can discard speech that is already waiting rather than merely
overtaking it.

No worker thread, and that is measured rather than skipped. The Skyrim Access mod hands its text
to one because nvdaController_* reaches NVDA over SendMessage and would stall the game's input
thread. This seam runs in its own process beside the game, and handing over a sentence costs
0.44 ms (27 July 2026, `brief\\niet_doen.md`), so there is nothing to absorb.
"""
import ctypes
import os
import sys

DLL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvdaControllerClient.dll')
REPLACE, QUEUE = 'replace', 'queue'

_client = None


def client():
    global _client
    if _client is None:
        _client = ctypes.windll.LoadLibrary(DLL)
    return _client


class Recorder:
    """A stand-in client that keeps what it was given. For tests and for the beta gate."""

    def __init__(self):
        self.spoken = []
        self.brailled = []
        self.cancels = 0

    def nvdaController_testIfRunning(self):
        return 0

    def nvdaController_speakText(self, text):
        self.spoken.append(text.value)
        return 0

    def nvdaController_brailleMessage(self, text):
        self.brailled.append(text.value)
        return 0

    def nvdaController_cancelSpeech(self):
        self.cancels += 1
        return 0


def nvda_running():
    return client().nvdaController_testIfRunning() == 0


def silence():
    client().nvdaController_cancelSpeech()


def output(text, mode=REPLACE, braille=None):
    """Speak, and write to the braille display in the same breath.

    braille=None means the same text, which is what almost every call wants: the user reads
    braille and listens at once, so two forms that can drift apart are two forms that can no
    longer be checked against each other.
    """
    if mode == REPLACE:
        silence()
    elif mode != QUEUE:
        raise ValueError('unknown mode: %r' % mode)

    error = client().nvdaController_speakText(ctypes.c_wchar_p(text))
    if error:
        raise OSError('NVDA returned error code %d on speech' % error)

    error = client().nvdaController_brailleMessage(
        ctypes.c_wchar_p(text if braille is None else braille))
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
