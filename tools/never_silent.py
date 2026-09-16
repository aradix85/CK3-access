"""The proof behind the beta gate: a failure speaks instead of falling silent.

Run it before every beta with `python tools/never_silent.py`. It takes the link with the game
away and it moves a field offset, and both have to produce a sentence. Two steps, both of them a
real failure path in the product - there is nothing here that exercises the seam against handlers
written to make it fire.

It puts a recorder in place of the NVDA client, so it needs no screen reader, talks over nobody,
and can check that braille arrived beside every spoken sentence. That last one is the defect
measured in the Fallout 4 mod and invisible to anyone who only listens.

**An empty answer is not a failure.** A keystroke that turns up nothing stays quiet; only a fault
speaks. So this proves what the failure exit does, and nothing about how much the layer says.
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

heard = speech.Recorder()
speech._client = heard


def _sentences_from(step, work):
    """Run one step and return the sentences it produced, or stop if it produced none."""
    before = len(heard.spoken)
    work()
    said = heard.spoken[before:]
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
    before = len(heard.spoken)
    work()
    if len(heard.spoken) > before:
        raise SystemExit('%s spoke, and it had no reason to: %s\nThat is most likely a game '
                         'sitting on the main menu, where the recheck turns down a derivation '
                         'that is perfectly good. Load a save and run this again.'
                         % (step, heard.spoken[-1]))


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
    nobody opened to reach the same place.
    """
    said = {}
    try:
        pid = int(channel.ask('hello').split('\t')[1])
    except OSError:
        if not heard.spoken:
            raise SystemExit('SILENT: the link with the game is gone and nothing said so. That is '
                             'the whole point of this proof, so nothing else here matters until '
                             'it speaks.')
        raise SystemExit('The link with the game is gone and it said so, which is the first step. '
                         'The second needs a game with the channel inside it, so this proof is '
                         'not finished. Start the game and run it again.')

    said['the link with the game taken away'] = _sentences_from(
        'the link with the game taken away', link_taken_away)

    fields = derive.stored()
    if not fields:
        raise SystemExit('The first step spoke. There is no stored derivation to move an offset '
                         'in, so the second cannot run. Let the game start once and run it again.')
    _silence_expected('the derivation left alone', lambda: derive.fields_for(pid))
    said['a field offset moved'] = _sentences_from(
        'a field offset moved', lambda: field_moved(pid, fields))

    if heard.brailled != heard.spoken:
        raise SystemExit('speech and braille came out different, so one of the two channels is '
                         'dropping sentences:\nspoken:   %s\nbrailled: %s'
                         % (heard.spoken, heard.brailled))

    for step, sentences in said.items():
        print('%s spoke %d time(s):' % (step, len(sentences)))
        for sentence in sentences:
            print('   ', sentence)

    if len(set(heard.spoken)) < 2:
        raise SystemExit('Both steps spoke, but with the same words, so a tester cannot tell them '
                         'apart. That counts as a failure.')
    print('\nTwo real failures, %d different sentences, no silence, braille alongside every one.'
          % len(set(heard.spoken)))


if __name__ == '__main__':
    main()
