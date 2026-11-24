r"""After a patch: the harvest of the last version beside that of this one, a sentence per window.

Usage:  python -m tools.ck3.compare <folder of the old harvest>
        python -m tools.ck3.compare <folder of the old harvest> --set-aside <window> ...
        python -m tools.ck3.compare <folder of the old harvest> --again <pid> [<window> ...]

A patch changes windows, and which ones only the game can say: laid against the files of 1.21,
the harvest of 1.20 pointed at fifteen windows by their texts and at more by their structure, with
no score per window from before to hold it against (24 November 2026). So a window is opened
again along the route its old record keeps, and the two records are laid side by side.

**What is compared is the names**, the distinct names of the widgets in the window. A name comes
from a gui file, so it is the same on every state and every date; a text is not, and neither is
how many rows a list has. A window the patch left alone carries the names it carried.

`--set-aside` moves the old record of each window named, with its capture, out of the harvest into
the folder, where it is the baseline: the rounds of `harvest` skip a window that has a record, and
`hand` puts one it replaces into a folder of its own date. A record already in the folder is never
written over.

`--again` does the round for the state that is loaded: every record of an older build whose player
is the one being played now is set aside and its window opened again along the route the record
names - a key, a click or a chain through `harvest`, a hand route through `hand`, its source on
the key the map names now. A route that opens nothing leaves a refusal with its reason, so the
comparison says `lost` and not `waiting`. What the clock brought up, what stood open already and
a step taken with the real mouse cannot be walked again; those are listed and left in place.

Without either, every record of the folder that came from a player route is compared with the
record the harvest holds now, and the outcome goes to `reports\compare.json`. A window the map no
longer knows is `gone`: 1.21 renamed the succession law window.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
from collections.abc import Mapping

from tools import paths, terminal
from tools.ck3 import derive, hand, harvest, model

REPORT = os.path.join(paths.REPORTS, 'compare.json')
SHOWN = 6           # names a sentence spells out before it only counts


def names(record: Mapping[str, object]) -> set[str]:
    """Every distinct name a widget of this window carries."""
    tree: list[dict[str, object]] = record['tree']  # type: ignore[assignment]
    return {str(widget['name']) for widget in tree if widget['name']}


def _listed(found: set[str]) -> str:
    first = sorted(found)[:SHOWN]
    return ', '.join(first) + (f' and {len(found) - SHOWN} more' if len(found) > SHOWN else '')


def verdict(old: Mapping[str, object], new: Mapping[str, object] | None) -> tuple[str, str]:
    """(kind, sentence) for one window: `waiting` while no record of another build stands beside
    the old one, `lost` when its route no longer opens it, `same` or `changed` by its names."""
    if new is None or new.get('exe') == old['exe']:
        return 'waiting', 'not opened again on this build yet'
    if not new['opened']:
        return 'lost', f"the route no longer opens it: {new['reason']}"
    route = '' if new['route'] == old['route'] else f"; opened by {new['route']}, was {old['route']}"
    was, now = names(old), names(new)
    if was == now:
        return 'same', f'the same {len(now)} names' + route
    parts = []
    if now - was:
        parts.append(f'{len(now - was)} names new ({_listed(now - was)})')
    if was - now:
        parts.append(f'{len(was - now)} gone ({_listed(was - now)})')
    return 'changed', f"{', '.join(parts)}, {len(was & now)} kept" + route


def set_aside(folder: str, windows: list[str]) -> None:
    """Move the record and the capture of each window from the harvest into `folder`."""
    os.makedirs(folder, exist_ok=True)
    for window in windows:
        for suffix in ('.json', '.jpg'):
            source = os.path.join(harvest.OUT, window + suffix)
            target = os.path.join(folder, window + suffix)
            if os.path.exists(target):
                raise SystemExit(f'{target} exists already: a baseline is never written over')
            if os.path.exists(source):
                shutil.move(source, target)
            elif suffix == '.json':
                raise SystemExit(f'the harvest holds no record of {window}')
        print(f'{window}: set aside')


def compared(folder: str) -> dict[str, tuple[str, str]]:
    """Window -> (kind, sentence), for every record of `folder` that came from a player route."""
    now = harvest.records_on_disk()
    mapped = json.loads(pathlib.Path(harvest.MAP).read_text(encoding='utf-8'))['windows']
    out = {}
    for path in sorted(pathlib.Path(folder).glob('*.json')):
        old = json.loads(path.read_text(encoding='utf-8'))
        if not harvest.player_route(old):
            continue
        # A window the map of this build does not know has no route to try: the patch took it away.
        out[str(old['window'])] = (verdict(old, now.get(old['window'])) if old['window'] in mapped else
                                   ('gone', 'the game no longer has a window of this name'))
    return out


def commands(old: Mapping[str, object], mapped: Mapping[str, Mapping[str, object]]) -> list[str] | None:
    """The arguments that open this record's window again along its own route, after
    `python -m tools.ck3.<first> <pid>`; None for a route no tool can walk again.

    **A hand route opens its source on the key the map names now**, not the one in the record: 1.21
    moved the court to F6 and the decisions to F9, and a route of 1.20 says F5 and F8."""
    window, route = str(old['window']), str(old['route'])
    kind = route.split(' ')[0]
    if kind == 'shortcut':
        # A window whose key the patch took away has only its button left, as the activity list
        # of 1.21; without a key `harvest` would build it through the console, with no data in it.
        return ['harvest', window] if mapped.get(window, {}).get('shortcut') else ['harvest', '--click', window]
    if kind == 'click':
        return ['harvest', '--click', window]
    if kind == 'chain':
        # The chain round is asked for a view where the record came up along one: the files name
        # the view a button opens, and which window stands behind it only a round sees.
        views: list[str] = old.get('views') or []  # type: ignore[assignment]
        return ['harvest', '--chain', *(views or [window])]
    walked = hand.route_of(route, window)
    if walked is None:
        return None
    source, how, steps = walked
    key_now = mapped.get(source, {}).get('shortcut')
    if key_now and not how.startswith(('button:', 'event:')):
        how = str(key_now)
    return ['hand', source, how, *(f'{step}={target}' if target else step for step, target in steps)]


def again(folder: str, pid: int, wanted: list[str]) -> None:
    """Set aside and open again every record of an older build that the player loaded now made.

    Two passes, so that a round that stopped goes on where it was: first every such record still in
    the harvest goes aside, then every record of this player in the folder whose window has no
    record yet is opened again. A window that was refused is tried again only when it is named.
    **The chains go last**: one whose source this state cannot open costs four minutes, as the
    guest list did without a feast (24 November 2026)."""
    mapped = json.loads(pathlib.Path(harvest.MAP).read_text(encoding='utf-8'))['windows']
    player = model.player(pid)[1]
    build = derive.build_key()
    left = []
    for window, old in sorted(harvest.records_on_disk().items()):
        if not harvest.player_route(old) or old['exe'] == build or old['player_name'] != player:  # type: ignore[typeddict-item]
            continue
        if wanted and window not in wanted:
            continue
        if window in mapped and commands(old, mapped) is None:
            left.append(f"{window}: {old['route']}")  # type: ignore[typeddict-item]
        else:
            set_aside(folder, [window])
    todo: list[tuple[list[str], str]] = []
    for path in sorted(pathlib.Path(folder).glob('*.json')):
        old = json.loads(path.read_text(encoding='utf-8'))
        window = str(old['window'])
        if not harvest.player_route(old) or old['player_name'] != player or window not in mapped:
            continue
        if wanted and window not in wanted:
            continue
        target = os.path.join(harvest.OUT, window + '.json')
        if os.path.exists(target):
            if window not in wanted or json.loads(pathlib.Path(target).read_text(encoding='utf-8'))['opened']:
                continue
            os.remove(target)
        arguments = commands(old, mapped)
        if arguments is not None:
            todo.append((arguments, window))
    todo.sort(key=lambda pair: (pair[0][:2] == ['harvest', '--chain'], pair[1]))
    for number, (arguments, window) in enumerate(todo, 1):
        target = os.path.join(harvest.OUT, window + '.json')
        if os.path.exists(target):          # an earlier route of this round brought it up already
            continue
        done = subprocess.run([sys.executable, '-u', '-m', f'tools.ck3.{arguments[0]}', str(pid), *arguments[1:]],
                              capture_output=True, text=True, encoding='utf-8', errors='replace',
                              cwd=paths.PROJECT, check=False)
        said = [line for line in (done.stdout + done.stderr).splitlines() if line.strip() and 'RapidOCR' not in line]
        last = said[-1].strip() if said else 'it said nothing'
        if not os.path.exists(target):
            refusal = {'window': window, 'opened': False, 'state_returned': True,
                       'reason': f"{' '.join(arguments)}: {last}"}
            pathlib.Path(target).write_text(json.dumps(refusal, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'{number}/{len(todo)} {window}: {last}', flush=True)
        if 'did not come back' in last:
            raise SystemExit(f'stopping after {window}: the state did not come back')
    print(f'\nnot walked again, {len(left)}:')
    for line in left:
        print('  ' + line)


def main() -> None:
    terminal.utf8()
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    folder = os.path.abspath(sys.argv[1])
    if sys.argv[2:3] == ['--set-aside']:
        set_aside(folder, sys.argv[3:])
        return
    if sys.argv[2:3] == ['--again']:
        again(folder, int(sys.argv[3]), sys.argv[4:])
        return
    found = compared(folder)
    counts: dict[str, int] = {}
    for window, (kind, sentence) in found.items():
        counts[kind] = counts.get(kind, 0) + 1
        if kind != 'waiting':
            print(f'{window}: {sentence}')
    report = {'baseline': os.path.basename(folder), 'counts': counts,
              'windows': {window: {'kind': kind, 'says': sentence} for window, (kind, sentence) in found.items()}}
    pathlib.Path(REPORT).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f"\n{len(found)} windows in the baseline: " + ', '.join(f'{count} {kind}' for kind, count in sorted(counts.items())))
    print(f'written to {os.path.relpath(REPORT, paths.PROJECT)}')


if __name__ == '__main__':
    main()
