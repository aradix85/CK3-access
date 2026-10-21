"""The proof behind the beta gate: a failure speaks instead of falling silent.

Run it before every beta with `python -m tools.never_silent`, with a save loaded. It moves a field
offset and lets the ordinary start path trip over it, and that has to produce a sentence: a real
failure path in the product, not a handler written to make the seam fire. A link with the game that
is not there is proved without a game, in `tests/test_ask_retry.py`.

It puts a recorder in place of the NVDA client, so it needs no screen reader, talks over nobody,
and can check that braille arrived beside every spoken sentence. That last one is the defect
measured in the Fallout 4 mod and invisible to anyone who only listens.

**An empty answer is not a failure.** A keystroke that turns up nothing stays quiet; only a fault
speaks. So this proves what the failure exit does, and nothing about how much the layer says.
"""
import json
import os
from collections.abc import Callable
from typing import NoReturn

from tools import paths, terminal
from tools.ck3 import channel, derive
from tools.nvda import speech

# Takes the place of the NVDA client once `main` runs; importing this module changes nothing.
heard = speech.Recorder()


def _sentences_from(step: str, work: Callable[[], object]) -> list[str | None]:
    """Run one step and return the sentences it produced, or stop if it produced none."""
    before = len(heard.spoken)
    work()
    said = heard.spoken[before:]
    if not said:
        raise SystemExit(f'SILENT: {step} failed without a word. That is the whole point of this '
                         'proof, so nothing else here matters until it speaks.')
    return said


def _silence_expected(step: str, work: Callable[[], object]) -> None:
    """The counter-test, and the field step is worthless without it.

    A recheck turns a good derivation down on the main menu, so on that screen the moved-offset
    step would speak whether or not anything was moved - a measurement that does not move with
    what you change. So first prove the untouched derivation stays quiet.
    """
    before = len(heard.spoken)
    work()
    if len(heard.spoken) > before:
        raise SystemExit(f'{step} spoke, and it had no reason to: {heard.spoken[-1]}\nThat is most likely a game '
                         'sitting on the main menu, where the recheck turns down a derivation '
                         'that is perfectly good. Load a save and run this again.')


class _Enough(Exception):
    """Stops the run once the sentence is out."""


def _raises(call: Callable[[], object], expected: type[BaseException]) -> bool:
    """Does `call` raise `expected`? Here that exception is the outcome the proof wants."""
    try:
        call()
    except expected:
        return True
    return False


def field_moved(pid: int, fields: derive.Fields) -> None:
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

    def enough(pid: int) -> NoReturn:
        raise _Enough(pid)

    stored_at, derive_all = derive.STORED, derive.derive_all
    derive.STORED = copy
    derive.derive_all = enough
    try:
        if not _raises(lambda: derive.fields_for(pid), _Enough):
            raise SystemExit('a moved offset passed the check; the check is broken, not the offset')
    finally:
        derive.STORED, derive.derive_all = stored_at, derive_all
        derive.use_fields(fields)
        derive.configure_channel(fields)        # the moved copy reached the DLL too; put it back
        os.remove(copy)


def main() -> None:
    """The field step needs a game with the channel inside it, and a save loaded."""
    terminal.utf8()
    if not channel.alive():
        raise SystemExit('No game with the channel inside it is running. Start one, load a save and '
                         'run this again.')
    speech._client = heard
    pid = int(channel.ask('hello').split('\t')[1])
    fields = derive.stored()
    if not fields:
        raise SystemExit('There is no stored derivation to move an offset in. Let the game start '
                         'once and run this again.')
    _silence_expected('the derivation left alone', lambda: derive.fields_for(pid))
    said = _sentences_from('a field offset moved', lambda: field_moved(pid, fields))
    if heard.brailled != heard.spoken:
        raise SystemExit('speech and braille came out different, so one of the two channels is '
                         f'dropping sentences:\nspoken:   {heard.spoken}\nbrailled: {heard.brailled}')
    print(f'a field offset moved spoke {len(said)} time(s):')
    for sentence in said:
        print('   ', sentence)
    print('\nA real failure, no silence, braille alongside every sentence.')


if __name__ == '__main__':
    main()
