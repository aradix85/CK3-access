"""Recomputes the checkable numbers in the documentation and reports what has drifted.

Runs without the game. The claims live in `reports\\claims.json`, not here: what is claimed
is a matter of agreement and belongs in data, how it is measured is code and belongs here.

Every claim carries its own counting rule. A number without one is not a measurement but a
memory, and that is exactly how this document drifted before.

Besides the numbers it checks the names: every project path a document mentions has to exist.

Usage:  python tools\\check.py [--all]
"""
import glob
import io
import json
import os
import sys
import zipfile
import fnmatch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ck3'))

import paths

PROJ = paths.PROJECT
GAME = paths.GAME
DOCS = paths.DOCS


def _path(part):
    """Placeholders instead of absolute paths, so a claim is not tied to one machine.

    `<workshop>` is derived from the game folder rather than written down: the Steam library that
    holds the game holds the workshop content two levels up, whichever drive it is on.
    """
    workshop = os.path.join(os.path.dirname(os.path.dirname(GAME)), 'workshop', 'content', '1158310')
    return (part.replace('<game>', GAME).replace('<project>', PROJ)
            .replace('<documents>', DOCS).replace('<workshop>', workshop))


def bytes_of(part):
    return os.path.getsize(_path(part))


def lines_of(part):
    with open(_path(part), 'rb') as file:
        return sum(1 for _ in file)


def files_in(part, pattern):
    root = _path(part)
    return sum(len(glob.glob(os.path.join(map_, pattern))) for map_, _, _ in os.walk(root))


def json_field(part, *keys):
    value = json.load(open(_path(part), encoding='utf-8'))
    for build_key in keys:
        value = value[build_key]
    return value


def json_keys(part, *skip):
    value = json.load(open(_path(part), encoding='utf-8'))
    return len([k for k in value if k not in skip])


def type_names_in_exe():
    import memory
    return memory.type_name_count()


def widget_vtables():
    import memory
    return len(memory.widget_vtables())


def gamestate_mb(part):
    with open(_path(part), 'rb') as file:
        raw = file.read()
    start = raw.find(b'PK\x03\x04')
    with zipfile.ZipFile(io.BytesIO(raw[start:])) as package:
        return round(package.infolist()[0].file_size / 1048576.0, 1)


def repo_files():
    """Counts what a `git init` would take into the repo: everything .gitignore does not exclude."""
    lines = []
    for line in open(os.path.join(PROJ, '.gitignore'), encoding='utf-8'):
        line = line.split('#')[0].strip().rstrip('/')
        if line:
            lines.append(line)
    count = 0
    for map_, _, files in os.walk(PROJ):
        if '.git' in map_.split(os.sep):
            continue
        for name in files:
            parts = os.path.relpath(os.path.join(map_, name), PROJ).replace('\\', '/').split('/')
            branches = ['/'.join(parts[:i + 1]) for i in range(len(parts))]
            if not any(fnmatch.fnmatch(branch, line) for line in lines for branch in branches):
                count += 1
    return count


def document_paths():
    """Every project path named in a document, checked against the disk.

    A number that drifts is caught by the claims above; a *name* that drifts was not caught by
    anything. After the rename round of 24 August 2026 the path list in the working documents
    pointed at twenty-one files that no longer existed, and a fresh session would have run them.
    Only paths that start with a folder of this project are checked - `game\\` and `logs\\` live
    elsewhere and are not ours to verify.
    """
    tops = {name.lower() for name in os.listdir(PROJ)}
    docs = sorted(glob.glob(os.path.join(PROJ, '*.md')) + glob.glob(os.path.join(PROJ, 'brief', '*.md')))
    missing, seen = [], 0
    for doc in docs:
        fenced = False
        for number, line in enumerate(open(doc, encoding='utf-8'), 1):
            if line.startswith('```'):
                fenced = not fenced
                continue
            parts = ([line.strip().split(' ')[0]] if fenced
                     else [p.strip() for p in line.split('`')[1::2]])
            for part in parts:
                part = part.rstrip('.,;:').replace('/', os.sep)
                if os.sep not in part or any(c in part for c in '<>*|='):
                    continue
                if part.split(os.sep)[0].lower() not in tops:
                    continue
                seen += 1
                if not os.path.exists(os.path.join(PROJ, part)):
                    missing.append((os.path.relpath(doc, PROJ), number, part))
    return seen, missing


def mod_windows(part):
    """Windows in the map whose gui file is not part of the game itself.

    The window map is measured on one machine, with mods enabled, and it ships. Anything in it that
    a mod put there would be a window nobody else can open. Measured 24 August 2026 with five mods
    loaded: none of them defines a window at all, so this has to stay zero. If it ever is not, the
    map was regenerated with a mod that does replace or add screens.
    """
    rows = json.load(open(_path(part), encoding='utf-8'))['windows']
    count = 0
    for row in rows.values():
        rel = (row.get('file') or '').replace('/', os.sep)
        if not any(os.path.exists(os.path.join(GAME, layer, rel))
                   for layer in ('game', 'clausewitz', 'jomini')):
            count += 1
    return count


MEASURES = {'bytes': bytes_of, 'lines': lines_of, 'files': files_in,
            'json_field': json_field, 'json_keys': json_keys,
            'type_names': type_names_in_exe, 'widget_vtables': widget_vtables,
            'gamestate_mb': gamestate_mb, 'repo_files': repo_files,
            'mod_windows': mod_windows}


def main(all_of_them):
    claims = json.load(open(os.path.join(PROJ, 'reports', 'claims.json'),
                                encoding='utf-8'))
    drifted = []
    for claim in claims:
        measure = MEASURES[claim['measure']]
        measured = measure(*claim.get('arguments', []))
        matches = str(measured) == str(claim['claimed'])
        if all_of_them or not matches:
            print('%s %s: the document says %s, measured %s'
                  % ('   ' if matches else 'DRIFTED', claim['name'],
                     claim['claimed'], measured))
            if not matches:
                print('        counting rule: %s' % claim['counting_rule'])
        if not matches:
            drifted.append(claim['name'])

    print('')
    if drifted:
        print('%d of the %d numbers no longer match the disk.'
              % (len(drifted), len(claims)))
    else:
        print('All %d numbers match the disk.' % len(claims))

    seen, missing = document_paths()
    for doc, number, part in missing:
        print('GONE    %s line %d names %s' % (doc, number, part))
    print('%d of the %d project paths named in the documents exist.'
          % (seen - len(missing), seen))
    return 1 if drifted or missing else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main('--all' in sys.argv))
