r"""After a game patch: what held and what moved, one sentence per check.

Usage:
    python -m tools.ck3.patchround <pid>

On a loaded, paused game, started with `python -m tools.ck3.start_game`: a played state first,
then a second one, because where the player is kept is what two states share. It runs what was
done by hand until 21 November 2026, when 1.21.0.3 took a session to walk: the numbers on disk
(`tools.check`), the launcher file, the widget offsets, the character record against a save it
writes from the loaded state itself, the player, the six numberings, the player's seat on the
map, the windows the game builds that the files do not declare, and the tooltip root.

**A check that stops says why, and the round goes on**: after a patch the whole list is the
point, and the first thing that broke is seldom the only one. What the tools print on the way is
left out; every line here is an outcome. The save it writes carries the version and the time
after the name of the loaded save, and nothing is written over.
"""
import contextlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from collections.abc import Callable

from tools import paths, restore_launcher, terminal
from tools.ck3 import derive, model, numbering, place, savegame, states, windowmap


def disk() -> str:
    done = subprocess.run([sys.executable, '-m', 'tools.check'], capture_output=True, text=True,
                          encoding='utf-8', cwd=paths.PROJECT, check=False)
    if 'Traceback' in done.stderr:
        return f'the disk check stopped on {done.stderr.strip().splitlines()[-1]}'
    moved = re.findall(r'^DRIFTED (.+?): the document says (\d+), measured (\d+)', done.stdout, re.MULTILINE)
    if not moved:
        return 'every number on disk is the one the documents carry'
    return '{} numbers on disk moved:{}'.format(len(moved), ''.join(f'\n   {name}, from {was} to {now}' for name, was, now in moved))


def launcher() -> tuple[str, str]:
    """The version, and a sentence on the launcher file against the copy kept as a safety net."""
    now = json.loads(pathlib.Path(paths.require('GAME'), 'launcher', 'launcher-settings.json').read_text(encoding='utf-8'))
    kept = json.loads(pathlib.Path(restore_launcher.ORIGINAL).read_text(encoding='utf-8'))
    differ = sorted(key for key in now.keys() | kept.keys() if now.get(key) != kept.get(key))
    mods = json.loads(pathlib.Path(paths.require('DOCS'), 'dlc_load.json').read_text(encoding='utf-8'))['enabled_mods']
    return now['rawVersion'], 'the game is {}; the launcher file {}; {} mods are enabled'.format(
        now['version'], 'is the one kept as a safety net' if not differ else
        f"differs from the safety net in {', '.join(differ)}: copy it over the safety net", len(mods))


def record(pid: int, save: str) -> str:
    """The character record: derived against the save when this build has no derivation that
    holds, and laid beside the save either way. A second state only checks, because on a fresh
    state fields that differ on a played one hold the same number (Harold, 21 November 2026:
    strength and current strength)."""
    path = savegame.named(save)
    how = 'the derivation of this build was kept'
    if model.stored() is None or model.check(pid):
        rows = model.answer_key(path)
        built = model.build(pid, {h: rows[h] for h in sorted(rows)[::max(1, len(rows) // 80)][:80]},
                            against=os.path.basename(path))
        nowhere = [field for field, _, _ in model.WANTED if field not in built['fields'] and field not in built['indirect']]
        how = 'derived again, ' + (f"with no place for {', '.join(nowhere)}" if nowhere else 'every field found')
    counters, read, _, _, _ = model.compare(pid, path)
    wrong = [f'{field} ({total - good} of {total})' for field, (good, total) in sorted(counters.items()) if good < total]
    defects = model.check(pid)
    return 'the character record against {}: {}; over {} characters {}; {}'.format(
        os.path.basename(path), how, read,
        f"these disagree with the save: {', '.join(wrong)}" if wrong else 'every field agrees with the save',
        f"its own check fails: {'; '.join(defects)}" if defects else 'its own check holds')


def who(pid: int, save: str) -> str:
    number = savegame.player(savegame.unpack(savegame.named(save)))
    spots = model.derive_player(pid, int(number))
    handle, name = model.player(pid)
    return f'the save says the player is {number}, {len(spots)} places in the module hold that, and reading them back gives {handle}, {name}'


def numbers(pid: int) -> str:
    parts = []
    for kind in numbering.CLASSES:
        try:
            found = numbering.keys(pid, kind)
        except SystemExit as stop:
            parts.append(f'{kind} stopped: {stop}')
            continue
        known = numbering.on_disk(kind)
        parts.append(f'{kind} {len(found)} numbers, {sum(1 for key in found.values() if key in known)} of them on disk')
    return '; '.join(parts)


def seat(pid: int) -> str:
    handle, name = model.player(pid)
    return f'{name} sits on {place.Seats(pid).where(handle)}'


def windows(pid: int) -> str:
    game = windowmap.Game(pid)
    missing, live, _ = windowmap.unmapped(pid, game)
    root = derive.tooltip_root(pid, game.fields, game.root)
    return 'the game builds {} window objects under {} names, {}; the tooltip root is at {:x}'.format(
        sum(live.values()), len(live),
        f"and the files declare none of these: {', '.join(missing)}" if missing else 'all of them declared in the files', root)


def said(label: str, step: Callable[[], str]) -> str | None:
    """Run one check with what it prints on the way kept out, and say its outcome; a check that
    stops says why. The outcome comes back, or None when it stopped."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            outcome: str | None = step()
    except SystemExit as stop:
        outcome = None
        print(f'{label}: stopped: {stop}', flush=True)
    else:
        print(f'{label}: {outcome}', flush=True)
    return outcome


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    pid = int(sys.argv[1])
    version, sentence = launcher()
    print(f'launcher: {sentence}', flush=True)
    said('disk', disk)
    said('offsets', lambda: derive.fields_for(pid)[2])
    save = said('save', lambda: states.save(pid, version.replace('.', '_') + time.strftime('_%m%d_%H%M')))
    if save:
        said('record', lambda: record(pid, save))
        said('player', lambda: who(pid, save))
    said('numbering', lambda: numbers(pid))
    said('seat', lambda: seat(pid))
    said('windows', lambda: windows(pid))


if __name__ == '__main__':
    terminal.utf8()
    main()
