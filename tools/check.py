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
import re
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


CHANNEL_PARSE = re.compile(r'(?:strcmp|strncmp|sscanf)\(command,\s*"([a-z_]+(?: [a-z_]+)?)')
# Backticked phrases that look like a command but belong to someone else's vocabulary.
NOT_OURS = {'git': 'a program', 'effect': "the game's own console", 'answer': 'a channel reply'}


def _documents():
    """The markdown in the project root and in `brief\\`. On a clone the second is not there."""
    return sorted(glob.glob(os.path.join(PROJ, '*.md'))
                  + glob.glob(os.path.join(PROJ, 'brief', '*.md')))


def channel_commands():
    """Every command the DLL accepts, read out of its dispatch chain."""
    source = open(os.path.join(PROJ, 'dll', 'channel.cpp'), encoding='utf-8',
                  errors='replace').read()
    return set(CHANNEL_PARSE.findall(source))


def channel_names():
    """Command names the documents claim, checked against the DLL - both directions.

    **Why this exists.** `toetsen aan` and `toetsen uit` survived a month in the documentation
    after the protocol was translated, because nothing checks a command name. Paths are verified,
    numbers are verified, duplicates are reported - a command name was verified by nobody, which is
    exactly the half-finished rename this project has already paid for twice.

    **What counts as a claim, and why the rule is this narrow.** A backticked phrase of two
    lowercase words, or one word followed by a `<placeholder>`. A wider rule is useless: widget
    names, function names and script names are all single lowercase tokens, and requiring those to
    be commands produced 223 false alarms against 31 real hits. Two words with a space between them
    is what a command looks like and almost nothing else does.

    Returns (problems, how many claims were checked).
    """
    known = channel_commands()
    claim = re.compile(r'^([a-z_]+)(?: ([a-z_]+)| (<[^>]+>))$')
    problems, checked = [], 0
    for path in _documents():
        for number, line in enumerate(open(path, encoding='utf-8'), 1):
            for piece in re.findall(r'`([^`]+)`', line):
                piece = piece.replace('\\|', '|').split('|')[0].strip()
                found = claim.match(piece)
                if not found or found.group(1) in NOT_OURS:
                    continue
                checked += 1
                if found.group(1) not in known and piece not in known:
                    problems.append('%s line %d: `%s` is not a channel command'
                                    % (os.path.relpath(path, PROJ), number, piece))
    text = ' '.join(open(p, encoding='utf-8').read() for p in _documents())
    for command in sorted(known):
        if '`%s' % command not in text:
            problems.append('the DLL accepts `%s` and no document mentions it' % command)
    return problems, checked


def gui_merged(with_mods):
    """Gui files as the engine sees them: the three layers merged, mods on top."""
    import guimap
    return len(guimap.files(with_mods=with_mods))


def gui_templates(scope):
    """Templates in the merged set. `type` and `template` are global, `local_type` is not."""
    import guimap
    table, local = guimap.type_table()
    return len(table if scope == 'global' else local)


def gui_windows():
    import guimap
    return len(guimap.windows())


DLC_CHECK = re.compile(r"HasDlcFeature\(\s*'([^']+)'\s*\)")


def gui_dlc(what):
    """How the gui set gates content behind an expansion, counted over the merged files.

    Measured 27 August 2026 over the expansion of all 196 windows: **not one window block carries
    such a check.** Every one of them sits on the `visible` of a widget deeper down, and 114 of the
    117 windows that touch a feature at all reach it through three shared portrait templates that
    hide one status icon. So an expansion never removes a window from a tester's game, only parts
    inside one - which is what a beta report has to be read against.

    Kept cheap on purpose: a text scan over the 563 files, not an expansion of every window, which
    takes five minutes. If a patch changes how the game gates things, these two numbers move and
    the expensive question is worth asking again.
    """
    found = set()
    total = 0
    for _, _, full in guimap_files():
        for name in DLC_CHECK.findall(open(full, encoding='utf-8-sig', errors='replace').read()):
            found.add(name)
            total += 1
    return total if what == 'checks' else len(found)


def guimap_files():
    import guimap
    return guimap.files()


def database_entries(kind, what, save=None):
    """Entries of one of the game's databases, merged the way the engine merges them.

    `named` is the check rather than a statistic: a key that also resolves to a sentence in the
    localization files exists in two independent places, so a reader that walked into the wrong
    part of the file would show up here as a gap rather than as a plausible list.

    **`numbered` needs the save named, not the newest one.** The engine's numbering belongs to the
    state that wrote it, so a save made under a different set of mods gives a different answer:
    measured 29 August 2026, the claim of 463 fell to 244 the moment a save from before the mods
    became the newest file in the folder. Reading whichever save is newest makes this claim say
    something other than what its counting rule says, and the failure looks like a broken reader.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ck3'))
    import database
    if what == 'keys':
        return len(database.entries(kind))
    if what == 'named':
        return len(database.named(kind))
    import savegame
    keys = [k for k, _, _ in database.entries(kind)]
    text = savegame.unpack(_path(save)) if save else None
    return sum(1 for n, key in database.numbering(kind, text).items()
               if n < len(keys) and keys[n] == key)


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

    **A bare name with no folder in front of it counts too, and that gap cost something.** A
    document promised a `.bat` on the desktop that would restore the launcher, said it had been
    tested, and said there was an agreement with the user that he would hear it fail. The file did
    not exist and he had never asked for it. Nothing caught that, because the name carried no
    separator and the check skipped it. So: a name ending in an extension we write ourselves has to
    exist somewhere under this project.

    That only works with a convention, and here it is: **backticks mean the thing exists.** A file
    that was removed - invoer.py, lees_scherm.py, lezer.py - is named in plain text, so a reader
    still finds it and this check does not trip over it. Without that rule the check reported ten
    deliberate mentions next to two real problems, which is how a control teaches people to ignore
    it.
    """
    tops = {name.lower() for name in os.listdir(PROJ)}
    ours = ('.py', '.bat', '.ps1', '.cpp', '.ahk')
    on_disk = set()
    for root, _, names in os.walk(PROJ):
        if '.git' in root or '__pycache__' in root:
            continue
        on_disk.update(name.lower() for name in names)
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
                if any(c in part for c in '<>*|=') or part.startswith('.'):
                    continue
                if os.sep not in part:
                    if not part.lower().endswith(ours):
                        continue
                    seen += 1
                    if part.lower() not in on_disk:
                        missing.append((os.path.relpath(doc, PROJ), number, part))
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


def harvest_total(part, field):
    """A number summed over the harvest records: how big the round was, and how good.

    `harvest\\` stays out of the repo, so on a clone this measures nothing and the claim will
    drift - which is right, because the number belongs to a round on this machine. What it buys is
    that the quality of a round is a figure that can be recomputed instead of a sentence somebody
    typed. `boxes` counts the text boxes of a window that should be on screen, `confirmed` how many
    of them the recogniser read back; the ratio of the two is what says whether a capture was blind.
    """
    total = 0
    for name in sorted(glob.glob(os.path.join(_path(part), '*.json'))):
        record = json.load(open(name, encoding='utf-8'))
        if field == 'windows':
            total += 1 if record.get('opened') else 0
        else:
            total += record.get(field, 0)
    return total


_MAP = {}


def map_layer(what):
    """A count of the static map layer, recomputed from the game files.

    Every one of these is held on the first call, because building the layer walks a 9216x4608
    image: the first claim pays for it and the rest come free. They are here because the map layer
    ships and a player hears what it says - how many counties border yours, and whether the capital
    a title names resolves to a place at all. A mod that adds a county moves these numbers, and
    that is exactly what a claim is for.
    """
    import mapdata
    if not _MAP:
        numbers = mapdata.province_image()
        _MAP['pairs'] = len(mapdata.touching(numbers))
        world = mapdata.Map()
        _MAP['provinces'] = len(world.centres)
        _MAP['counties'] = len(set(world.county_of.values()))
        _MAP['neighboured'] = len(world.neighbours)
        _MAP['titles'] = len(world.titles)
        _MAP['capitals'] = sum(1 for row in world.titles.values() if 'capital' in row)
        _MAP['placed'] = sum(1 for key in world.titles if world.county_for(key))
    return _MAP[what]


MEASURES = {'bytes': bytes_of, 'lines': lines_of, 'files': files_in,
            'json_field': json_field, 'json_keys': json_keys,
            'type_names': type_names_in_exe, 'widget_vtables': widget_vtables,
            'gamestate_mb': gamestate_mb, 'repo_files': repo_files,
            'mod_windows': mod_windows, 'harvest_total': harvest_total,
            'gui_merged': gui_merged, 'gui_templates': gui_templates,
            'gui_windows': gui_windows, 'gui_dlc': gui_dlc,
            'database_entries': database_entries, 'map_layer': map_layer}



def quoted_numbers(claims):
    """Claims that a document repeats, checked against the file that repeats them.

    A number in `claims.json` is recomputed here, but a copy of it in `README.md` is not: it ages
    silently, and the reader outside this project has no way to tell. So a claim may name the files
    that quote it in `quoted_in`, and this asserts the measured value still occurs there. It is the
    same convention as backticks for paths - saying it out loud is what makes it checkable.

    Returns (problems, how many quotes were checked).
    """
    problems, seen = [], 0
    for claim in claims:
        for name in claim.get('quoted_in', ()):
            seen += 1
            path = os.path.join(PROJ, name)
            if not os.path.exists(path):
                problems.append('%s quotes %s, which does not exist' % (claim['name'], name))
                continue
            measure = MEASURES[claim['measure']]
            measured = str(measure(*claim.get('arguments', [])))
            text = open(path, encoding='utf-8').read()
            if not re.search(r'(?<![\d.])%s(?![\d])' % re.escape(measured), text):
                problems.append('%s says %s, and %s does not'
                                % (claim['name'], measured, name))
    return problems, seen


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

    wrong, claimed = channel_names()
    for problem in wrong:
        print('STALE   %s' % problem)
    print('%d of the %d channel commands named in the documents exist.'
          % (claimed - len(wrong), claimed))

    quotes, counted = quoted_numbers(claims)
    for problem in quotes:
        print('QUOTED  %s' % problem)
    print('%d of the %d numbers a document quotes are still the measured ones.'
          % (counted - len(quotes), counted))
    return 1 if drifted or missing or wrong or quotes else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main('--all' in sys.argv))
