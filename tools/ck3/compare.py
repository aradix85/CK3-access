r"""After a patch: the harvest of the last version beside that of this one, a sentence per window.

Usage:  python -m tools.ck3.compare <folder of the old harvest>
        python -m tools.ck3.compare <folder of the old harvest> --set-aside <window> ...

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
written over. A window the map no longer knows is `gone`: 1.21 renamed the succession law window. Without it, every record of the folder that came from a player route is compared
with the record the harvest holds now, and the outcome goes to `reports\compare.json`.
"""
import json
import os
import pathlib
import shutil
import sys
from collections.abc import Mapping

from tools import paths, terminal
from tools.ck3 import harvest

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


def main() -> None:
    terminal.utf8()
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    folder = os.path.abspath(sys.argv[1])
    if sys.argv[2:3] == ['--set-aside']:
        set_aside(folder, sys.argv[3:])
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
