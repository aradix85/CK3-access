"""Recomputes the checkable numbers in the documentation and reports what has drifted.

Runs without the game. The claims live in `reports\\claims.json`, not here: what is claimed
is a matter of agreement and belongs in data, how it is measured is code and belongs here.

Every claim carries its own counting rule. A number without one is not a measurement but a
memory, and that is exactly how this document drifted before.

Besides the numbers it checks the names: every project path a document mentions has to exist. And it
holds the changelog to one short line per change.

Usage:  python -m tools.check [--all]
"""
import ast
import fnmatch
import glob
import json
import os
import pathlib
import re
import sys
from collections.abc import Callable, Iterator
from typing import NotRequired, TypedDict

from tools import paths, terminal

PROJ = paths.PROJECT


class Claim(TypedDict):
    """One entry of `reports\\claims.json`: a number, and the measure that recomputes it."""
    name: str
    measure: str
    arguments: NotRequired[list[str | bool]]
    claimed: int
    counting_rule: str
    quoted_in: NotRequired[list[str]]


def _path(part: str) -> str:
    """Placeholders instead of absolute paths, so a claim is not tied to one machine.

    `<workshop>` is derived from the game folder rather than written down: the Steam library that
    holds the game holds the workshop content two levels up, whichever drive it is on.
    """
    game = paths.require('GAME')
    workshop = os.path.join(os.path.dirname(os.path.dirname(game)), 'workshop', 'content', '1158310')
    return (part.replace('<game>', game).replace('<project>', PROJ)
            .replace('<documents>', paths.require('DOCS')).replace('<workshop>', workshop))


def bytes_of(part: str) -> int:
    return os.path.getsize(_path(part))


def lines_of(part: str) -> int:
    with open(_path(part), 'rb') as file:
        return sum(1 for _ in file)


def files_in(part: str, pattern: str) -> int:
    root = _path(part)
    return sum(len(glob.glob(os.path.join(map_, pattern))) for map_, _, _ in os.walk(root))


def json_field(part: str, *keys: str) -> object:
    value = json.loads(pathlib.Path(_path(part)).read_text(encoding='utf-8'))
    for build_key in keys:
        value = value[build_key]
    return value


def json_keys(part: str, *skip: str) -> int:
    value = json.loads(pathlib.Path(_path(part)).read_text(encoding='utf-8'))
    return len([k for k in value if k not in skip])


def type_names_in_exe() -> int:
    from tools.ck3 import memory
    return memory.type_name_count()


def widget_vtables() -> int:
    from tools.ck3 import memory
    return len(memory.widget_vtables())


# The dispatch chain names each command once as `is("word")`, or as `strcmp(command, "...")` when
# the command is a fixed phrase such as `keys on`.
CHANNEL_PARSE = re.compile(r'(?:\bstrcmp\(command,\s*|\bis\()"([a-z_]+(?: [a-z_]+)?)"')
# Backticked phrases that look like a command but belong to someone else's vocabulary.
NOT_OURS = {'git': 'a program', 'effect': "the game's own console"}


def _documents() -> list[str]:
    """The markdown in the project root and in `brief\\`. On a clone the second is not there."""
    return sorted(glob.glob(os.path.join(PROJ, '*.md'))
                  + glob.glob(os.path.join(PROJ, 'brief', '*.md')))


def channel_commands() -> set[str]:
    """Every command the DLL accepts, read out of its dispatch chain."""
    source = pathlib.Path(os.path.join(PROJ, 'dll', 'channel.cpp')).read_text(encoding='utf-8', errors='replace')
    return set(CHANNEL_PARSE.findall(source))


def channel_names() -> tuple[list[str], int]:
    """Command names the documents claim, checked against the DLL - both directions.

    **Why this exists.** `toetsen aan` and `toetsen uit` survived a month in the documentation
    after the protocol was translated, because nothing checks a command name. Paths are verified,
    numbers are verified, duplicates are reported - a command name was verified by nobody, which is
    exactly the half-finished rename this project has already paid for twice.

    **What counts as a claim, and why the rule is this narrow.** A backticked phrase of two
    lowercase words, or one word followed by one or more `<placeholder>`s - `mouse <x> <y> <knop>`
    and `combo <ms> <modifier>... <key>` slipped through while only one placeholder counted. A wider
    rule is useless: widget names, function names and script names are all single lowercase tokens,
    and requiring those to be commands produced 223 false alarms against 31 real hits. Two words with
    a space between them is what a command looks like and almost nothing else does.

    Returns (problems, how many claims were checked).
    """
    known = channel_commands()
    claim = re.compile(r'^([a-z_]+)(?: ([a-z_]+)|(?: <[^>]+>(?:\.\.\.)?)+(?: \.\.\.)?)$')
    problems: list[str] = []
    checked = 0
    for path in _documents():
        with open(path, encoding='utf-8') as file:
            for number, line in enumerate(file, 1):
                for piece in re.findall(r'`([^`]+)`', line):
                    piece = piece.replace('\\|', '|').split('|')[0].strip()
                    found = claim.match(piece)
                    if not found or found.group(1) in NOT_OURS:
                        continue
                    checked += 1
                    if found.group(1) not in known and piece not in known:
                        problems.append(f'{os.path.relpath(path, PROJ)} line {int(number)}: `{piece}` is not a channel command')
    text = ' '.join(pathlib.Path(p).read_text(encoding='utf-8') for p in _documents())
    for command in sorted(known):
        if f'`{command}' not in text:
            problems.append(f'the DLL accepts `{command}` and no document mentions it')
    return problems, checked


def gui_merged(with_mods: bool) -> int:
    """Gui files as the engine sees them: the three layers merged, mods on top."""
    from tools.ck3 import guimap
    return len(guimap.files(with_mods=with_mods))


def gui_templates(scope: str) -> int:
    """Templates in the merged set. `type` and `template` are global, `local_type` and
    `local_template` are not."""
    from tools.ck3 import guimap
    table, local = guimap.type_table()
    return len(table if scope == 'global' else local)


def gui_windows() -> int:
    from tools.ck3 import guimap
    return len(guimap.windows())


_LEDGER: dict[str, int] = {}


def ledger_buildings(what: str) -> int:
    """What a building box in the ledger can actually do when it is clicked.

    `window_ledger.gui` gives `building_button` two onclicks: the first opens
    `holding_view`, the second calls `GUIBuildingItem.OnClick`. **A click fires
    both, in order** (measured 21 October 2026, `openers.fires_for`), so every box
    calls the holding view. This count said zero from 13 September until then: it
    kept only the last action per key, on three clicks that drew no
    `holding_view` - while a window counted as drawn only at state byte zero, and
    the open holding view carries 0x20. Whether the second call undoes the first
    is measured with `onscreen.shown`, not read off the file.

    `boxes` counts `widget_building_item_ledger` nodes in the expanded ledger.
    `acting` counts widgets inside those boxes carrying onclick, onrightclick,
    shortcut or ondoubleclick - one per box, so nothing lies on top that could
    swallow the click. `opens_holding_view` counts the ones that call the
    holding view among their actions.
    """
    from tools.ck3 import guimap
    doing = ('onclick', 'onrightclick', 'shortcut', 'ondoubleclick')

    def walk(node: guimap.Node) -> Iterator[guimap.Node]:
        yield node
        for child in node['children']:
            yield from walk(child)

    if not _LEDGER:
        tree = guimap.window('ledger_window')
        boxes = [n for n in walk(tree) if n['type'] == 'widget_building_item_ledger']
        acting = 0
        reaching = 0
        for box in boxes:
            for node in walk(box):
                actions = [value for key, value in node['attrs'] if key in doing and value]
                if actions:
                    acting += 1
                if any('holding_view' in str(value) for value in actions):
                    reaching += 1
        _LEDGER.update(boxes=len(boxes), acting=acting, opens_holding_view=reaching)
    if what not in _LEDGER:
        raise KeyError(f'no such ledger building count: {what!r}')
    return _LEDGER[what]


DLC_CHECK = re.compile(r"HasDlcFeature\(\s*'([^']+)'\s*\)")


def gui_dlc(what: str) -> int:
    """How the gui set gates content behind an expansion, counted over the merged files.

    Measured 27 August 2026 over the expansion of all 196 windows, and again over all 282 on
    1 October 2026 on 1.20.0.2 and on 21 October 2026 on 1.20.1.1: **not one window block carries
    such a check**, while 39 of them carry a
    `visible` of their own. Every check sits on the `visible` of a widget deeper down, and on 1.20
    147 of the 150 windows that touch a feature at all do so through `all_under_heaven`. So an expansion never removes a window from a tester's game, only parts
    inside one - which is what a beta report has to be read against.

    Kept cheap on purpose: a text scan over the merged files, not an expansion of every window, which
    takes five minutes. If a patch changes how the game gates things, these two numbers move and
    the expensive question is worth asking again.
    """
    from tools.ck3 import guimap
    found = set()
    total = 0
    for _, _, full in guimap.files():
        for name in DLC_CHECK.findall(pathlib.Path(full).read_text(encoding='utf-8-sig', errors='replace')):
            found.add(name)
            total += 1
    return total if what == 'checks' else len(found)


def database_entries(kind: str, what: str) -> int:
    """Entries of one of the game's databases, merged the way the engine merges them.

    `named` is the check rather than a statistic: a key that also resolves to a sentence in the
    localization files exists in two independent places, so a reader that walked into the wrong
    part of the file would show up here as a gap rather than as a plausible list.
    """
    from tools.ck3 import database
    if what == 'keys':
        return len(database.entries(kind))
    return len(database.named(kind))


def cultures_numbered(save: str) -> int:
    """Cultures whose number in this save is their place in the file order.

    **The save is named, never the newest one.** The engine's numbering belongs to the state that
    wrote it, so a save made under a different set of mods gives a different answer: measured 29
    August 2026, the claim of 463 fell to 244 the moment a save from before the mods became the
    newest file in the folder.
    """
    from tools.ck3 import database, savegame
    keys = [k for k, _, _ in database.entries('culture')]
    return sum(1 for n, key in database.culture_numbers(savegame.unpack(_path(save))).items()
               if n < len(keys) and keys[n] == key)


_ignore_lines: list[str] | None = None


def ignored(relative: str) -> bool:
    """Does `.gitignore` exclude this path? The same question `git init` asks.

    Two callers need it for opposite reasons: counting what goes into the repo, and knowing that
    a document which is *not* in the repo is expected to be missing from a clone. The file is read
    once - the walk below asks this for every file on disk, harvest rounds included.
    """
    global _ignore_lines
    if _ignore_lines is None:
        _ignore_lines = []
        with open(os.path.join(PROJ, '.gitignore'), encoding='utf-8') as file:
            for line in file:
                line = line.split('#')[0].strip().rstrip('/')
                if line:
                    _ignore_lines.append(line)
    parts = relative.replace('\\', '/').split('/')
    branches = ['/'.join(parts[:i + 1]) for i in range(len(parts))]
    return any(fnmatch.fnmatch(branch, line) for line in _ignore_lines for branch in branches)


def repo_files() -> int:
    """Counts what a `git init` would take into the repo: everything .gitignore does not exclude."""
    count = 0
    for map_, _, files in os.walk(PROJ):
        if '.git' in map_.split(os.sep):
            continue
        for name in files:
            if not ignored(os.path.relpath(os.path.join(map_, name), PROJ)):
                count += 1
    return count


def unseen_texts(what: str) -> int:
    """Texts in the harvest that are in the tree but not on the screen.

    `texts` counts what the text boxes hold once the markup is stripped, `all` how many of those the
    reading rule skips (`reading.on_screen`): outside the drawing area the record was taken at,
    clipped inside a scroll area, under an ancestor at alpha zero, or under one carrying 0x08 in its
    state byte. That decides how much a window says to nobody.
    """
    from tools.ck3 import reading, widgettree
    texts = unseen = 0
    for name in sorted(glob.glob(os.path.join(paths.HARVEST, '*.json'))):
        record = json.loads(pathlib.Path(name).read_text(encoding='utf-8'))
        if not record['opened']:
            continue            # a refusal record: a reason and no window, so nothing to read
        by_address = {node['address']: node for node in record['tree']}
        for node in record['tree']:
            if widgettree.strip_markup(node['text'] or '').strip():
                texts += 1
                unseen += not reading.on_screen(node, by_address, record['size'])
    return {'texts': texts, 'all': unseen}[what]


def document_paths() -> tuple[int, list[tuple[str, int, str]]]:
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
    on_disk: set[str] = set()
    for root, _, names in os.walk(PROJ):
        if '.git' in root or '__pycache__' in root:
            continue
        on_disk.update(name.lower() for name in names)
    docs = _documents()
    missing: list[tuple[str, int, str]] = []
    seen = 0
    for doc in docs:
        fenced = False
        with open(doc, encoding='utf-8') as file:
            for number, line in enumerate(file, 1):
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



def mod_windows(part: str) -> int:
    """Windows in the map whose gui file is not part of the game itself.

    The window map is measured on one machine, with mods enabled, and it ships. Anything in it that
    a mod put there would be a window nobody else can open. Measured 24 August 2026 with five mods
    loaded: none of them defines a window at all, so this has to stay zero. If it ever is not, the
    map was regenerated with a mod that does replace or add screens.
    """
    from tools.ck3 import guimap
    rows = json.loads(pathlib.Path(_path(part)).read_text(encoding='utf-8'))['windows']
    vanilla = {virtual for _, virtual, _ in guimap.files(with_mods=False)}
    return sum(1 for row in rows.values() if row['file'] not in vanilla)


def harvest_total(part: str, field: str) -> int:
    """A number summed over the harvest records: how big the round was, and how good.

    `harvest\\` stays out of the repo, so on a clone this measures nothing and the claim will
    drift - which is right, because the number belongs to a round on this machine. What it buys is
    that the quality of a round is a figure that can be recomputed instead of a sentence somebody
    typed. `boxes` counts the text boxes of a window that should be on screen, `confirmed` how many
    of them the recogniser read back; the ratio of the two is what says whether a capture was blind.
    """
    total = 0
    for name in sorted(glob.glob(os.path.join(_path(part), '*.json'))):
        record = json.loads(pathlib.Path(name).read_text(encoding='utf-8'))
        if field == 'windows':
            total += 1 if record.get('opened') else 0
        else:
            total += record.get(field, 0)
    return total


_MAP: dict[str, int] = {}


def map_layer(what: str) -> int:
    """A count of the static map layer, recomputed from the game files.

    Every one of these is held on the first call, because building the layer walks a 9216x4608
    image: the first claim pays for it and the rest come free. They are here because the map layer
    ships and a player hears what it says - how many counties border yours, and whether the capital
    a title names resolves to a place at all. A mod that adds a county moves these numbers, and
    that is exactly what a claim is for.
    """
    from tools.ck3 import mapdata
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


def _shortcut_rows() -> list[tuple[str, str]]:
    """Every binding of `shortcuts.shortcuts` as (name, keys), read here rather than through
    `windowmap`, because a check that uses the code it checks measures itself."""
    path = os.path.join(paths.require('GAME'), 'game', 'gui', 'shortcuts.shortcuts')
    text = pathlib.Path(path).read_text(encoding='utf-8-sig', errors='replace')
    return re.findall(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"', text, re.MULTILINE)


def shortcuts(what: str) -> int:
    """How many key bindings the game defines, counted by kind.

    **This claim exists because the number that stood here before was nine.** `windowmap` pressed
    the function keys, found nine windows that way, and the documents carried "nine shortcuts" as
    if that were the total. It was the total of what had been tried. The file bound 909 on 1.19.0.6.

    The counting rule, and it matters because the raw total flatters: a name starting with an
    underscore is the engine's generic entry for one key combination - `_alt_f7` - and not an
    action of the game. Those are counted apart. What is left are the named game actions, split
    by whether the binding needs shift, ctrl or alt.
    """
    rows = _shortcut_rows()
    named = [(n, k) for n, k in rows if not n.startswith('_')]
    # A binding with an empty key string is declared and bound to nothing - `event_option_14`,
    # `menu_14`, `sub_tab_14`, `tab_14`. Counting those among the keys we could press was wrong
    # here on 1 September 2026 and the sweep found it: 119 became 115 the moment a key was needed.
    bound = [(n, k) for n, k in named if k.strip()]
    plain = [(n, k) for n, k in bound if not re.search(r'alt|ctrl|shift', k, re.IGNORECASE)]
    if what == 'bindings':
        return len(rows)
    if what == 'named':
        return len(named)
    if what == 'unbound':
        return len(named) - len(bound)
    if what == 'plain':
        return len(plain)
    if what == 'modified':
        return len(bound) - len(plain)
    raise KeyError(f'no such shortcut count: {what!r}')


def shortcut_words(what: str) -> int:
    """How far a shortcut can be given a meaning from disk alone.

    A binding names itself and its keys and says nothing about what it does. The widget that
    declares `shortcut = "<name>"` carries a text key and a tooltip key, and those resolve
    through the localisation the engine merges. This counts how far that join reaches, because a
    help list for a player is only worth the meanings in it.

    `declared` counts bindings that at least one widget declares; `worded` counts those whose text
    or tooltip key is in the localisation. The difference is texts that are a data function and
    therefore need the running game.

    **Every `shortcut` line of a block counts, not the first.** A widget may declare several - the
    speed buttons on the HUD carry four - and until 2 October 2026 only the first was read, which
    gave 173 where 192 are declared. A name computed in the file itself, such as
    `[Concatenate('tab_', ...)]`, is no binding name and is not counted here.
    """
    from tools.ck3 import guimap
    bindings = {n for n, _ in _shortcut_rows() if not n.startswith('_')}

    def value_of(body: list[guimap.Entry], key: str) -> str | None:
        for child in body:
            if child['key'] == key:
                return child['value']
        return None

    found: dict[str, list[tuple[str | None, str | None]]] = {}

    for _, _, full in guimap.files():
        for node in guimap.walk(guimap.read(full)):
            body = node['body'] or []
            for child in body:
                value = child['value']
                if child['key'] == 'shortcut' and value:
                    found.setdefault(value, []).append((value_of(body, 'text'), value_of(body, 'tooltip')))
    declared = bindings & set(found)
    if what == 'declared':
        return len(declared)
    # A computed name - [Concatenate('tab_', ...)], [Select_CString(..., 'tab_3', 'tab_2')] - covers
    # a binding that one of its quoted pieces names outright, or as a prefix with only digits after.
    pieces = {piece for value in found if value.startswith('[')
              for piece in re.findall(r"'([A-Za-z_][A-Za-z0-9_]*)'", value)}
    computed = {n for n in bindings - declared
                if any(n == p or (n.startswith(p) and n[len(p):].isdigit()) for p in pieces)}
    if what == 'computed':
        return len(computed)
    if what == 'nowhere':
        return len(bindings - declared - computed)
    words = guimap.localization()
    worded = {n for n in declared
              if any((k or '').strip('"') in words for pair in found[n] for k in pair)}
    if what == 'worded':
        return len(worded)
    raise KeyError(f'no such shortcut word count: {what!r}')


# Each takes its own arguments, from the claim's `arguments`.
MEASURES: dict[str, Callable[..., object]] = {
            'bytes': bytes_of, 'lines': lines_of, 'files': files_in,
            'json_field': json_field, 'json_keys': json_keys,
            'type_names': type_names_in_exe, 'widget_vtables': widget_vtables,
            'repo_files': repo_files,
            'mod_windows': mod_windows, 'harvest_total': harvest_total,
            'gui_merged': gui_merged, 'gui_templates': gui_templates,
            'gui_windows': gui_windows, 'gui_dlc': gui_dlc,
            'ledger_buildings': ledger_buildings,
            'database_entries': database_entries, 'cultures_numbered': cultures_numbered, 'map_layer': map_layer,
            'shortcuts': shortcuts, 'shortcut_words': shortcut_words,
            'unseen_texts': unseen_texts}



def quoted_numbers(claims: list[Claim], measured: dict[str, object]) -> tuple[list[str], int, int]:
    """Claims that a document repeats, checked against the file that repeats them.

    A number in `claims.json` is recomputed here, but a copy of it in `README.md` is not: it ages
    silently, and the reader outside this project has no way to tell. So a claim may name the files
    that quote it in `quoted_in`, and this asserts the measured value still occurs there. It is the
    same convention as backticks for paths - saying it out loud is what makes it checkable.

    **A quoted document that `.gitignore` excludes may simply not be there, and that is not a
    problem.** The maintainer's working notes quote these numbers and stay out of the repo, so on
    anyone else's clone those files are absent by design - reporting them would hand a contributor
    a page of failures about documents `CONTRIBUTING.md` tells them they are not missing. A file
    that *should* be in the repo and is gone is still a problem.

    Returns (problems, how many quotes were checked, how many were not on this disk).
    """
    problems: list[str] = []
    seen, absent = 0, 0
    for claim in claims:
        for name in claim.get('quoted_in', ()):
            path = os.path.join(PROJ, name)
            if not os.path.exists(path):
                if ignored(name):
                    absent += 1
                    continue
                problems.append('{} quotes {}, which does not exist'.format(claim['name'], name))
                continue
            seen += 1
            value = str(measured[claim['name']])
            text = pathlib.Path(path).read_text(encoding='utf-8')
            if not re.search(rf'(?<![\d.]){re.escape(value)}(?![\d])', text):
                problems.append('{} says {}, and {} does not'.format(claim['name'], value, name))
    return problems, seen, absent


RUN_MODULE = re.compile(r'python(?: -u)? -m (tools(?:\.\w+)+)')
RUN_FILE = re.compile(r'python(?: -u)? +\S*tools[\\/]\S+\.py')
# A script named by its file with arguments after it, between backticks as states.py <pid> wait once
# stood in the notes: read as a start, and one that no longer works. A name alone is not a start.
RUN_NAME = re.compile(r'`(?:\S*[\\/])?([a-z_]+)\.py [^`]+`')


def script_runs() -> tuple[list[str], int]:
    """How the documents and the scripts themselves say to start a script, checked against the package.

    Since 3 October 2026 `tools` is a package, and a script starts from the project folder as
    `python -m tools.ck3.states`. Started by its file path it no longer finds its imports, so a start
    by path is wrong wherever it stands, and a start by module has to name a module that exists.
    """
    texts = _documents() + sorted(glob.glob(os.path.join(PROJ, 'tools', '**', '*.py'), recursive=True))
    wrong: list[str] = []
    seen = 0
    for path in texts:
        name = os.path.relpath(path, PROJ)
        with open(path, encoding='utf-8') as file:
            for number, line in enumerate(file, 1):
                for found in RUN_MODULE.finditer(line):
                    if line[found.end():found.end() + 2] == '.<':
                        continue                    # `tools.ck3.<name>` is a placeholder, not a start
                    module = found.group(1)
                    seen += 1
                    if not os.path.exists(os.path.join(PROJ, *module.split('.')) + '.py'):
                        wrong.append(f'{name} line {int(number)} starts {module}, which does not exist')
                for run in RUN_FILE.findall(line):
                    wrong.append(f'{name} line {int(number)} starts {run} by its path, which no longer works')
                for script in RUN_NAME.findall(line):
                    wrong.append(f'{name} line {int(number)} starts {script}.py by its file name; write it '
                                 'as python -m tools.<package>.<module>')
    return wrong, seen


DEFINES = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign,
           ast.AnnAssign)


def scripts() -> list[str]:
    """Every Python file of the tools and the tests."""
    return sorted(glob.glob(os.path.join(PROJ, 'tools', '**', '*.py'), recursive=True)
                  + glob.glob(os.path.join(PROJ, 'tests', '*.py')))


def loading_work(files: list[str]) -> list[str]:
    """Every statement at the top level of these files that does work as the file is loaded.

    **Loading is not starting.** On 3 October 2026 a check that only loaded each script to test its
    imports put the launcher file of 1.19 back through `tools\\restore_launcher.py`. So the top level
    only defines - imports, also those under `if TYPE_CHECKING:`, functions, classes, names and the
    docstring - and the work starts under `if __name__ == '__main__':`. A call, a loop, a `try` or a
    `with` up there is reported.
    """
    found: list[str] = []
    for path in files:
        tree = ast.parse(pathlib.Path(path).read_text(encoding='utf-8'))
        for at, node in enumerate(tree.body):
            docstring = (at == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                         and isinstance(node.value.value, str))
            guard = isinstance(node, ast.If) and ast.unparse(node.test) in ("__name__ == '__main__'",
                                                                             'TYPE_CHECKING')
            if not (isinstance(node, DEFINES) or docstring or guard):
                line = ast.unparse(node).splitlines()[0]
                found.append(f'{os.path.relpath(path, PROJ)} line {node.lineno} works when loaded: {line[:70]}')
    return found


CHANGELOG_LINE = 180    # characters in one entry of CHANGELOG.md: one change, said as its outcome
CHANGELOG_DAY = 12      # entries under one date; a day with more is a day not yet summed up


def changelog_size() -> list[str]:
    """Entries of CHANGELOG.md that are too long, lines that are not one entry, and days with too many.

    **Why this exists.** The changelog is one short line per outcome, and asking for that did not
    hold: by 22 October 2026 it had 135 entries, the longest 331 characters and one day 51 of them.
    """
    problems = []
    day: str | None = None
    count = 0
    text = pathlib.Path(os.path.join(PROJ, 'CHANGELOG.md')).read_text(encoding='utf-8')
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith('## '):
            day, count = line[3:], 0
        elif day is None or not line:
            continue
        elif not line.startswith('- '):
            problems.append(f'CHANGELOG.md line {number} is not a date or a one-line entry')
        else:
            count += 1
            if len(line) > CHANGELOG_LINE:
                problems.append(f'CHANGELOG.md line {number} has {len(line)} characters, more than {CHANGELOG_LINE}')
            if count == CHANGELOG_DAY + 1:
                problems.append(f'CHANGELOG.md has more than {CHANGELOG_DAY} entries under {day}')
    return problems


def stale_reports() -> list[str]:
    """A report drawn from the harvest that describes another harvest than the one on disk.

    The claims on `reports\\pairing.json` are checked against the report, not against the harvest
    it was drawn from: from September to 21 October 2026 the report described an older harvest than
    the one on disk, and every claim on it still matched. A clone without a harvest has nothing to
    compare.
    """
    from tools.ck3 import pairing
    if not glob.glob(os.path.join(paths.HARVEST, '*.json')):
        return []
    described = json.loads(pathlib.Path(pairing.REPORT).read_text(encoding='utf-8')).get('harvest')
    on_disk = pairing.harvested_at()
    if described == on_disk:
        return []
    return [(f'reports\\pairing.json describes the harvest of {described}, and the one on disk is of '
             f'{on_disk}; run python -m tools.ck3.pairing')]


def main(all_of_them: bool) -> int:
    """The checks that need nothing but this repository first, then the claims, which stop at the
    first input this machine lacks: the game, the Documents folder, a built DLL, a harvest."""
    seen, missing = document_paths()
    for doc, number, part in missing:
        print(f'GONE    {doc} line {int(number)} names {part}')
    print(f'{int(seen - len(missing))} of the {int(seen)} project paths named in the documents exist.')

    wrong, claimed = channel_names()
    for problem in wrong:
        print(f'STALE   {problem}')
    print(f'{int(claimed - len(wrong))} of the {int(claimed)} channel commands named in the documents exist.')

    runs, started = script_runs()
    for problem in runs:
        print(f'RUN     {problem}')
    print(f"{int(started - len([r for r in runs if 'does not exist' in r]))} of the {int(started)} script starts named in documents and code are modules that exist.")

    stale = stale_reports()
    for problem in stale:
        print(f'STALE   {problem}')

    long = changelog_size()
    for problem in long:
        print(f'LONG    {problem}')

    claims: list[Claim] = json.loads(pathlib.Path(os.path.join(PROJ, 'reports', 'claims.json')).read_text(encoding='utf-8'))
    drifted = []
    measured: dict[str, object] = {}
    for claim in claims:
        measured[claim['name']] = value = MEASURES[claim['measure']](*claim.get('arguments', []))
        matches = str(value) == str(claim['claimed'])
        if all_of_them or not matches:
            print('{} {}: the document says {}, measured {}'.format('   ' if matches else 'DRIFTED', claim['name'],
                     claim['claimed'], value))
            if not matches:
                print('        counting rule: {}'.format(claim['counting_rule']))
        if not matches:
            drifted.append(claim['name'])
    print()
    if drifted:
        print(f'{len(drifted)} of the {len(claims)} numbers no longer match the disk.')
    else:
        print(f'All {len(claims)} numbers match the disk.')

    quotes, counted, absent = quoted_numbers(claims, measured)
    for problem in quotes:
        print(f'QUOTED  {problem}')
    print(f"{int(counted - len(quotes))} of the {int(counted)} numbers a document quotes are still the measured ones.{'' if not absent else f' {int(absent)} more are quoted only in documents that are not in this repository, so they cannot be checked here.'}")
    return 1 if drifted or missing or wrong or quotes or runs or stale or long else 0


if __name__ == '__main__':
    terminal.utf8()
    sys.exit(main('--all' in sys.argv))
