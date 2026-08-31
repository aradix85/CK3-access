"""The proof behind the beta gate: every failure speaks, and none of them is silent.

Run it before every beta with `python tools/never_silent.py`. It takes the link with the game
away and it moves a field offset, and it counts the sentences that reached the speech seam. Two
different sentences and no silence is a pass; anything else names the step that stayed quiet.

Counting rather than listening, because nothing can read back what NVDA said: this wraps the one
exit every sentence passes through and records what was handed to it. The player hears that same
seam, so a sentence counted here is a sentence spoken - and it really is spoken, the wrapper
passes it on.

Silence is the failure mode a blind tester cannot report. A tester who hears nothing does not
know whether the window was empty, the tool fell over, or the game did something else, so this
proof is the gate: without it every other test is worth less than it looks.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'nvda'))
sys.path.insert(0, os.path.join(HERE, 'ck3'))
import paths
import speech
import channel
import derive

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

_spoken = []
_seam = speech.output


def _record(text, mode=speech.REPLACE, braille=None):
    _spoken.append(text)
    _seam(text, mode, braille)


speech.output = _record


def _sentences_from(step, work):
    """Run one step and return the sentences it produced, or stop if it produced none."""
    before = len(_spoken)
    work()
    said = _spoken[before:]
    if not said:
        raise SystemExit('SILENT: %s failed without a word. That is the whole point of this '
                         'proof, so nothing else here matters until it speaks.' % step)
    return said


def _silence_expected(step, work):
    """The counter-test, and the field step is worthless without it.

    A recheck turns a good derivation down on the main menu, so on that screen the moved-offset
    step would speak whether or not anything was moved - a measurement that does not move with
    what you change. So first prove the untouched derivation stays quiet.
    """
    before = len(_spoken)
    work()
    if len(_spoken) > before:
        raise SystemExit('%s spoke, and it had no reason to: %s\nThat is most likely a game '
                         'sitting on the main menu, where the recheck turns down a derivation '
                         'that is perfectly good. Load a save and run this again.'
                         % (step, _spoken[-1]))


def link_taken_away():
    """Ask the channel something over a pipe name that cannot exist.

    Pointing at a name nobody opened is the same failure at the same place as a game that is not
    running, and it does not care whether a game happens to be up - so this half of the proof
    stays runnable while the other half needs a live game.
    """
    real = channel.PIPE
    channel.PIPE = real + '_taken_away'
    channel.close()
    try:
        channel.ask('hello')
        raise SystemExit('the channel answered on a pipe that nobody opened; this proof is broken')
    except OSError:
        pass
    finally:
        channel.PIPE = real
        channel.close()


class _Enough(Exception):
    """Stops the run once the sentence is out."""


def field_moved(pid, fields):
    """Move an offset in a copy of the derivation and let the ordinary start path trip over it.

    The copy is what keeps this safe to run: `reports\\fields.json` is never touched, so a proof
    that dies halfway cannot leave the machine with a broken derivation.

    It stops the moment the sentence is out. Letting it run on would derive everything again,
    seven minutes for a step whose answer is already known, and a proof nobody runs proves nothing.
    """
    moved = dict(fields, size=fields['size'] + 8)
    copy = os.path.join(paths.WORK, 'fields_moved.json')
    os.makedirs(paths.WORK, exist_ok=True)
    with open(copy, 'w') as file:
        json.dump(moved, file)

    def enough(*_):
        raise _Enough()

    stored_at, derive_all = derive.STORED, derive.derive_all
    derive.STORED = copy
    derive.derive_all = enough
    try:
        derive.fields_for(pid)
        raise SystemExit('a moved offset passed the check; the check is broken, not the offset')
    except _Enough:
        pass
    finally:
        derive.STORED, derive.derive_all = stored_at, derive_all
        derive.use_fields(fields)
        os.remove(copy)


def main():
    """Ask for the game first, because that answer decides how honest the first step can be.

    With no game running the link really is gone, and asking it anything is the first step
    itself - no pretending needed. With a game running the pipe has to be pointed somewhere
    nobody opened to reach the same place. Asking first also keeps the proof from saying the
    same sentence twice, which would leave a listener wondering which one was the test.
    """
    said = {}
    pid = None
    try:
        pid = int(channel.ask('hello').split('\t')[1])
    except OSError:
        if not _spoken:
            raise SystemExit('SILENT: the link with the game is gone and nothing said so. That is '
                             'the whole point of this proof, so nothing else here matters until '
                             'it speaks.')
        said['the link with the game gone'] = _spoken[:]

    if pid is None:
        raise SystemExit('The first step spoke. The second needs a game with the channel inside '
                         'it, and there is none, so this proof is not finished. Start the game '
                         'and run it again.')

    said['the link with the game taken away'] = _sentences_from(
        'the link with the game taken away', link_taken_away)

    fields = derive.stored()
    if not fields:
        raise SystemExit('The first step spoke. There is no stored derivation to move an offset '
                         'in, so the second cannot run. Let the game start once and run it again.')
    _silence_expected('the derivation left alone', lambda: derive.fields_for(pid))
    said['a field offset moved'] = _sentences_from(
        'a field offset moved', lambda: field_moved(pid, fields))

    for step, sentences in said.items():
        print('%s spoke %d time(s):' % (step, len(sentences)))
        for sentence in sentences:
            print('   ', sentence)

    heard = {sentence for sentences in said.values() for sentence in sentences}
    if len(heard) < 2:
        raise SystemExit('Both steps spoke, but with the same words, so a tester cannot tell them '
                         'apart. That counts as a failure.')
    print('\nTwo failures, %d different sentences, no silence.' % len(heard))


if __name__ == '__main__':
    main()
