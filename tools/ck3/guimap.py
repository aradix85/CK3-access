"""Reads the meaning out of the gui files: which widget shows what.

The tree in memory says *that* a widget exists and what it currently says. These files say
*why*: which data function fills it, which localization key it carries, which tooltip hangs on
it. That is the half of the sweep that needs no running game.

Nothing here talks to the game. It reads the three gui layers the engine merges - `game\\gui`,
`clausewitz\\gui` and `jomini` - plus the gui files of the active mods, and answers questions
about them.

**Read every file as `utf-8-sig`.** Forty-one of them start with a byte order mark right before
the first line, and a plain `utf-8` read swallows that line without a word.
"""
import os
import pathlib
import re
from collections.abc import Callable, Iterator
from typing import TypedDict

from tools import paths

# One token: its kind, its text, and the line it starts on.
Token = tuple[str, str, int]
# One gui file: its layer, its virtual path, and where it sits on disk.
Row = tuple[str, str, str]


class Entry(TypedDict):
    """One entry of a parsed file, in one of the four shapes `parse` describes."""
    key: str | None
    arg: str | None
    value: str | None
    body: 'list[Entry] | None'


class Definition(TypedDict):
    """A template: what it inherits from, its own body, and where it is written."""
    parent: str | None
    body: list[Entry]
    file: str
    layer: str


class Node(TypedDict):
    """A widget expanded: its attributes as (key, value), and its children built the same way."""
    type: str | None
    attrs: list[tuple[str | None, str | None]]
    children: 'list[Node]'


# Template name -> definition, global; (file, name) -> definition for `local_type` and
# `local_template`.
Table = dict[str | None, Definition]
LocalTable = dict[tuple[str, str | None], Definition]
# An entry with the file it is written in, which is where a local name in it is looked up.
Scoped = tuple[Entry, str]
# Slot -> the `blockoverride` that fills it.
Overrides = dict[str | None, Scoped]
# Window name -> the file it is written in, and its entry.
Known = dict[str, tuple[str, Entry]]
# Type name -> the end of its inheritance chain, as `root_finder` builds it.
Root = Callable[[str | None], str | None]
# Everything a window is expanded with, as `tables` builds it once.
Tables = tuple[Table, LocalTable, Known, Root]


class GuiError(Exception):
    """Raised where a file does not fit the grammar. Swallowed nowhere but in
    `pairing`, where a decision without a gui file of its own is counted as a live widget the files
    do not describe: a file this reader cannot read is a hole in the meaning of some window, and a
    hole that reports itself is worth more than a tree that quietly misses a branch."""


TOKEN = re.compile(r'''
      (?P<space>\s+)
    | (?P<comment>\#[^\n]*)
    | (?P<string>"(?:[^"\\]|\\.)*")
    | (?P<punct>[{}=])
    | (?P<word>[^\s{}="\#]+)
''', re.VERBOSE)


def tokens(text: str) -> list[Token]:
    """The file as a flat list of (kind, text, line). Comments and whitespace are dropped here so
    the parser never has to think about them, and a `#` inside a quoted string stays inside it -
    `default_format = "#medium"` is a value, not a comment, and reading it as one silently eats
    the rest of the line.

    The line number rides along because a parser that only says *what* it choked on leaves you
    grepping through a hundred thousand lines for the one that did it."""
    out: list[Token] = []
    at, line = 0, 1
    while at < len(text):
        found = TOKEN.match(text, at)
        # Every alternative of TOKEN is a named group, so a match always names its kind.
        if not found or found.lastgroup is None:
            raise GuiError(f'line {int(line)}: cannot read character {text[at]!r}')
        body = found.group()
        at = found.end()
        kind = found.lastgroup
        if kind not in ('space', 'comment'):
            out.append((kind, body[1:-1] if kind == 'string' else body, line))
        line += body.count('\n')
    return out


def _entry(key: str | None, arg: str | None = None, value: str | None = None,
           body: list[Entry] | None = None) -> Entry:
    return {'key': key, 'arg': arg, 'value': value, 'body': body}


def parse(text: str) -> list[Entry]:
    """A gui file as a list of entries. An entry is a key with at most one of a value and a body.

    Four shapes, because the grammar is not plain key-value:
        `key = value`            an attribute
        `key = { ... }`          a child - a widget, or a property group like `size`
        `type NAME = PARENT {}`  a template definition, `arg` holds NAME and `value` PARENT
        `block "NAME" { ... }`   a named slot, and `blockoverride` the thing that fills it
    A bare token inside a block, as in `size = { 0 310 }`, becomes an entry without a key.
    """
    found = tokens(text)
    at, out = _block(found, 0, out=[])
    if at != len(found):
        raise GuiError(f'stray {found[at][1]!r} after the last block')
    return out


def _block(found: list[Token], at: int, out: list[Entry]) -> tuple[int, list[Entry]]:
    """Entries until the matching `}` or the end of the file. Returns where it stopped."""
    while at < len(found):
        kind, body = found[at][0], found[at][1]
        if body == '}' and kind == 'punct':
            return at + 1, out
        at, entry = _one(found, at)
        out.append(entry)
    return at, out


def _want(found: list[Token], at: int, body: str) -> int:
    if at >= len(found) or found[at][1] != body:
        if at >= len(found):
            raise GuiError(f'expected {body!r} at the end of the file')
        raise GuiError(f'line {int(found[at][2])}: expected {body!r}, found {found[at][1]!r}')
    return at + 1


def _skip_equals(found: list[Token], at: int) -> int:
    """`block "x" {}` and `block = "x" {}` both occur, and so do both spellings of
    `blockoverride`. Measured 26 August 2026: eleven of the 563 files use the second form, and a
    reader that knows only the first stops dead on them."""
    return at + 1 if at < len(found) and found[at][1] == '=' and found[at][0] == 'punct' else at


def _body(found: list[Token], at: int) -> tuple[int, list[Entry]]:
    at = _want(found, at, '{')
    return _block(found, at, out=[])


def _one(found: list[Token], at: int) -> tuple[int, Entry]:
    """One entry, starting at `at`."""
    kind, word, line = found[at]
    at += 1
    if kind == 'punct':
        if word == '{':
            # An unnamed block inside a block. No gui file does this, but the game's script files
            # do - a list whose items are themselves blocks - and the same grammar reads both, so
            # refusing here would mean a second parser for the data folders.
            at, body = _block(found, at, out=[])
            return at, _entry(None, body=body)
        raise GuiError(f'line {int(line)}: a stray {word!r}')

    if word in ('block', 'blockoverride'):
        at = _skip_equals(found, at)
        name = found[at][1]
        at, body = _body(found, at + 1)
        return at, _entry(word, arg=name, body=body)

    if word == 'types':
        name = found[at][1]
        at, body = _body(found, at + 1)
        return at, _entry(word, arg=name, body=body)

    if word in ('template', 'local_template'):
        at = _skip_equals(found, at)
        name = found[at][1]
        at, body = _body(found, at + 1)
        return at, _entry(word, arg=name, body=body)

    if word in ('type', 'local_type'):
        name = found[at][1]
        at = _want(found, at + 1, '=')
        parent = found[at][1]
        at += 1
        if at < len(found) and found[at][1] == '{':
            at, body = _body(found, at)
            return at, _entry(word, arg=name, value=parent, body=body)
        return at, _entry(word, arg=name, value=parent)

    if at < len(found) and found[at][1] == '=' and found[at][0] == 'punct':
        at += 1
        if found[at][1] == '{' and found[at][0] == 'punct':
            at, body = _body(found, at)
            return at, _entry(word, body=body)
        return at + 1, _entry(word, value=found[at][1])

    if at < len(found) and found[at][1] == '{' and found[at][0] == 'punct':
        at, body = _body(found, at)
        return at, _entry(word, body=body)

    return at, _entry(None, value=word)


def files(with_mods: bool = True) -> list[Row]:
    """Every gui file the engine has loaded, **in load order**, as (layer, virtual path, disk path).

    The virtual path is what the console wants and what the layers share: `game/gui/hud.gui`,
    `clausewitz/gui/x.gui` and `jomini/gui/x.gui` all live under `gui/` as far as the engine is
    concerned. A file at a virtual path that already exists replaces it completely; that is
    exactly how Agami's mod fell apart, so the replacement is modelled rather than merged.

    **The order is the point and must not be sorted away.** Templates are global and the last
    definition wins, so a mod that redefines `portrait_status_icons_small` only shows up if its
    file comes after the game's. Sorting this list by path put the mod's `00_...gui` first and
    the redefinition vanished - measured 26 August 2026 against the harvest, where two widget
    names of the Historical Figure mod were missing from 70 windows.
    """
    game = paths.require('GAME')
    layers = [('clausewitz', os.path.join(game, 'clausewitz')),
              ('jomini', os.path.join(game, 'jomini')),
              ('game', os.path.join(game, 'game'))]
    if with_mods:
        layers += [('mod', folder) for folder in paths.mod_folders()]
    found: list[Row] = []
    for layer, base in layers:
        for root, _, names in os.walk(base):
            for name in sorted(names):
                if not name.endswith('.gui'):
                    continue
                full = os.path.join(root, name)
                virtual = os.path.relpath(full, base).replace(os.sep, '/')
                found.append((layer, virtual, full))
    return last_wins(found)


def last_wins(found: list[Row]) -> list[Row]:
    """Of the files at one virtual path, the last in load order, which replaces the rest whole."""
    out: list[Row] = []
    seen: set[str] = set()
    for row in reversed(found):
        if row[1] not in seen:
            seen.add(row[1])
            out.append(row)
    return list(reversed(out))


def read(path: str) -> list[Entry]:
    return parse(pathlib.Path(path).read_text(encoding='utf-8-sig', errors='replace'))


MAX_DEPTH = 60


def walk(nodes: list[Entry]) -> Iterator[Entry]:
    """Every entry in a parsed file, at any depth."""
    for entry in nodes:
        yield entry
        if entry['body']:
            yield from walk(entry['body'])


def type_table(rows: list[Row] | None = None) -> tuple[Table, LocalTable]:
    """Every template the engine knows, as name -> definition.

    Three keywords, and the difference is reach. `type` and `template` are global: a window in one
    file uses one that is defined in another, and 78 per cent of the widget names in the harvest
    come from such shared definitions. The common ones - `tooltip_es`, `Font_Size_Small` - sit in
    the preload folder and are pulled in tens of thousands of times, so treating `template` as
    file-local leaves the reader blind to most of what a widget inherits. Only `local_type` holds
    inside its own file, which is what its name says, and so does `local_template`.

    Later layers win, which is why `files()` hands them over in the order the engine loads them.
    """
    table: Table = {}
    local: LocalTable = {}
    for layer, virtual, full in (rows if rows is not None else files()):
        for entry in walk(read(full)):
            if entry['key'] in ('type', 'template'):
                table[entry['arg']] = {'parent': entry['value'], 'body': entry['body'] or [],
                                       'file': virtual, 'layer': layer}
            elif entry['key'] in ('local_type', 'local_template'):
                local[(virtual, entry['arg'])] = {'parent': entry['value'],
                                                  'body': entry['body'] or [],
                                                  'file': virtual, 'layer': layer}
    return table, local


class Templates:
    """The template tables. A local name is looked up in the file of the entry that uses it, and
    that is not the window's file when the entry came in through a template written elsewhere:
    measured 21 October 2026 on 1.20.1.2, `era_innov_blockers` is local to cooltip.gui and used
    there, by tooltips that three windows in other files pull in."""

    def __init__(self, table: Table, local: LocalTable) -> None:
        self.table, self.local = table, local

    def look_up(self, name: str, scope: str) -> Definition | None:
        return self.local.get((scope, name)) or self.table.get(name)

    def inherited(self, name: str | None, scope: str) -> list[Scoped]:
        """The bodies of the inheritance chain, the base first, each entry with its own file.

        `type textbox = textbox` is how the engine's own widgets get their defaults, so a type
        whose parent is itself is where the chain ends and the C++ begins."""
        bodies: list[list[Scoped]] = []
        while name:
            found = self.look_up(name, scope)
            if found is None:
                break
            bodies.append([(entry, found['file']) for entry in found['body']])
            if found['parent'] == name:
                break
            if len(bodies) > MAX_DEPTH:
                raise GuiError(f'{scope}: the inheritance of {name!r} goes round')
            name, scope = found['parent'], found['file']
        return [scoped for body in reversed(bodies) for scoped in body]


def _inline_using(nodes: list[Scoped], templates: Templates, depth: int = 0) -> list[Scoped]:
    """`using = X` drops the body of template X in at that spot, each entry keeping its file.

    Only its own body, not the bodies of its ancestors: `using = Font_Size_Small` inside a button
    is meant to add a font size, not to make the button inherit whatever textbox happens to
    default to."""
    out: list[Scoped] = []
    for entry, scope in nodes:
        name = entry['value']
        if entry['key'] != 'using' or not name:
            out.append((entry, scope))
            continue
        found = templates.look_up(name, scope)
        if found is None:
            raise GuiError(f'{scope}: using = {name}, and no template has that name')
        if depth >= MAX_DEPTH:
            raise GuiError(f'{scope}: using = {name} nests deeper than {MAX_DEPTH}')
        out += _inline_using([(inner, found['file']) for inner in found['body']], templates,
                             depth + 1)
    return out


def _fill_blocks(nodes: list[Scoped], overrides: Overrides, templates: Templates,
                 seen: frozenset[str | None] = frozenset()) -> list[Scoped]:
    """Named slots take the content that was written for them, or their own default.

    `seen` holds the slots being filled right now. Content written for a slot can declare a slot
    of the same name again, and then filling it means filling it forever - measured on 39 of the
    196 windows, which ran Python out of stack before anything said why. The engine fills it once,
    so the repeat is left out."""
    out: list[Scoped] = []
    for entry, scope in nodes:
        if entry['key'] == 'blockoverride':
            continue
        if entry['key'] != 'block':
            out.append((entry, scope))
            continue
        if entry['arg'] in seen:
            continue
        source, where = overrides.get(entry['arg'], (entry, scope))
        content = [(inner, where) for inner in source['body'] or []]
        out += _fill_blocks(_inline_using(content, templates), overrides, templates,
                            seen | {entry['arg']})
    return out


def build(key: str | None, body: list[Entry], scope: str, templates: Templates,
          overrides: Overrides | None = None, depth: int = 0, in_tooltip: bool = False,
          above: tuple[tuple[Entry, Overrides], ...] = ()) -> Node:
    """One widget, fully expanded: inherited defaults, mixed-in templates, slots filled.

    Every block becomes a node, including property groups like `size` and `state`. Nothing has to
    guess which keys are widgets and which are properties: a key that is not a template simply
    finds no defaults, and its own body is all there is. Guessing that list is how a reader starts
    quietly dropping the containers it did not recognise.

    **A tooltip inside a tooltip is not expanded, and that boundary is measured rather than
    chosen for tidiness.** The deepest paths in `character_window` run portrait button ->
    tooltipwidget -> coat of arms -> tooltipwidget -> coat of arms, without end: on screen the
    engine builds a tooltip only when the pointer arrives, so on disk the definition is allowed to
    be circular. Expanding it anyway turned one window into three and a half million nodes.

    **A widget met again inside itself, with the same slots filled, stays an empty node of its
    type**, because building it would repeat the same expansion without end. Measured 21 October
    2026 on 1.20.1.2, in two of 282 windows: `dynasty_tree_item` sits in an `item` marked
    `recursive = yes`, and `current_struggle_phase_progress` comes back through the slots of the
    phase banner. Cutting on the entry alone also cut finite nestings, a scroll box inside a
    scroll box among them, and cost `window_tgp_dynastic_cycle` 17 paired names; the pairing of
    the harvest stays the same with this rule. Past MAX_DEPTH is then a GuiError: the deepest
    window goes 46 levels down.
    """
    if depth >= MAX_DEPTH:
        raise GuiError(f'{scope}: {key} lies deeper than {MAX_DEPTH} widgets')

    nodes = _inline_using(templates.inherited(key, scope) + [(entry, scope) for entry in body],
                          templates)

    effective: Overrides = dict(overrides or {})
    for entry, where in nodes:
        if entry['key'] == 'blockoverride':
            effective[entry['arg']] = (entry, where)
    flat = _fill_blocks(nodes, effective, templates)

    node: Node = {'type': key, 'attrs': [], 'children': []}
    for entry, where in flat:
        if entry['body'] is None:
            node['attrs'].append((entry['key'], entry['value']))
        elif entry['key'] == 'tooltipwidget' and in_tooltip:
            continue
        elif any(entry is earlier and _same(slots, effective) for earlier, slots in above):
            node['children'].append({'type': entry['key'], 'attrs': [], 'children': []})
        else:
            node['children'].append(build(entry['key'], entry['body'], where, templates, effective,
                                          depth + 1,
                                          in_tooltip or entry['key'] == 'tooltipwidget',
                                          above + ((entry, effective),)))
    return node


def _same(one: Overrides, other: Overrides) -> bool:
    """Do these slots take their content from the same `blockoverride` entries?"""
    return one.keys() == other.keys() and all(one[slot][0] is other[slot][0] for slot in one)


def attribute(node: Node, key: str) -> str | None:
    """The value of the first attribute with this key, or None when the widget has none."""
    for name, value in node['attrs']:
        if name == key:
            return value
    return None


def windows(rows: list[Row] | None = None, table: Table | None = None) -> Known:
    """Every window on disk, as name -> (virtual path, its entry).

    The same list `reports\\windows.json` is built from, but with the body attached, so a caller
    can go straight from a window name to what it is made of.

    **Two shapes, and reading only the first missed a whole kind.** A literal `window = { name }`
    is counted wherever it sits, which is how `colorpicker_window` comes along from inside a type
    definition. But a window may also be declared through a type of its own that inherits from
    `window`, and Agami's mod laid bare on 29 August 2026 that the map had never seen those - among
    them event windows and the confirmation dialogs, which is the one thing a blind player cannot
    be left without. **Counted at any depth, and the live tree is why.** The rule here used to be
    top level only, reasoning that a window-derived type used inside another window is a part of
    it. The game disagrees: `window_character_filter = { name = "vassal_filter_window" }` sits
    inside the character window and comes out as its own window object with its own name.

    **A third shape, found 20 September 2026 and the reason the map was never complete.** A type
    can inherit from `window` and carry the name itself - `type window_character_filter = window {
    name = "character_filter_window" }` - and it may sit inside a `types` block, a level below
    where the shape above looks. Forty windows are declared that way, the search filter and the
    ledger's filter among them.

    **Stop enumerating shapes here.** This is the second time a shape nobody thought of was
    missing, and a window the map does not know cannot even refuse - it is absent from the count
    rather than reported. The closed test is `windowmap.unmapped`, which asks the running game:
    the engine builds every window up front, so the live tree is the whole list.
    """
    rows = rows if rows is not None else files()
    if table is None:
        table, _ = type_table(rows)
    root = root_finder(table)
    out: Known = {}
    for _, virtual, full in rows:
        entries = read(full)
        for entry in walk(entries):
            if entry['key'] != 'window' or not entry['body']:
                continue
            name = None
            for inner in entry['body']:
                if inner['key'] == 'name':
                    name = inner['value']
                    break
            if name:
                out[name] = (virtual, entry)
        for entry in walk(entries):
            if entry['key'] == 'window' or not entry['body']:
                continue
            if root(entry['key']) != 'window':
                continue
            for inner in entry['body']:
                if inner['key'] == 'name' and inner['value']:
                    out.setdefault(inner['value'], (virtual, entry))
                    break
    for type_name, found in table.items():
        if root(found['parent']) != 'window':
            continue
        for inner in found['body']:
            if inner['key'] == 'name' and inner['value']:
                # An instance of the type with an empty body: `build` takes the type's own body
                # from the table, and handing it in as well built these windows twice over
                # (measured 21 October 2026: character_filter_window 6138 nodes against 3070).
                out.setdefault(inner['value'], (found['file'],
                                                {'key': type_name, 'arg': None,
                                                 'value': found['parent'],
                                                 'body': []}))
                break
    return out


def root_finder(table: Table) -> Root:
    """Type name -> the end of its inheritance chain, remembered, because the walk repeats itself
    tens of thousands of times over one window."""
    known: dict[str | None, str | None] = {}

    def root(name: str | None) -> str | None:
        if name not in known:
            seen: set[str] = set()
            walk = name
            while walk and walk not in seen:
                seen.add(walk)
                found = table.get(walk)
                if not found or found['parent'] == walk:
                    break
                walk = found['parent']
            known[name] = walk
        return known[name]
    return root


def tables() -> Tables:
    """Everything a window is expanded with, built once.

    Some six hundred files, a few seconds, and nothing in them changes while the game runs, so a
    caller that expands more than one window builds this once and hands it on. The templates are
    read once here and handed to `windows`, which would otherwise read them a second time.
    """
    rows = files()
    table, local = type_table(rows)
    return table, local, windows(rows, table), root_finder(table)


def window(name: str, table: Table | None = None, local: LocalTable | None = None,
           known: Known | None = None) -> Node:
    """A window resolved into a widget tree. A file that does not fit the grammar raises GuiError.

    **Build it under the key the block was written with, not under `window`.** A window declared
    through a type of its own inherits everything it is made of from that type, and building it as
    a plain `window` throws all of that away: measured 30 August 2026, `scheme_failed_event` came
    out as two nodes against 283 live ones, and every text in the 22 windows of that shape was left
    without a source. Under its own key it expands like any other.

    **The file list is only walked when it is needed.** It used to be fetched at the top whatever
    the caller handed in, and with the tables passed in that is dead work: measured 20 September
    2026, walking 4595 folders cost 0,76 of the 2,8 seconds a read of the character window took -
    on every single read.
    """
    rows = None
    if table is None or local is None:
        rows = files()
        table, local = type_table(rows)
    if known is None:
        known = windows(rows if rows is not None else files())
    if name not in known:
        raise GuiError(f'no window named {name!r} on disk')
    virtual, entry = known[name]
    return build(entry['key'], entry['body'] or [], virtual, Templates(table, local))


DECISION_WIDGETS = 'gui/decision_view_widgets/'


def decision_widget(name: str, table: Table | None = None, local: LocalTable | None = None,
                    rows: list[Row] | None = None) -> Node:
    """The own gui of a decision, resolved into a widget tree like a window.

    A decision can name a gui file of its own with `widget = { gui = "..." }` in common\\decisions,
    and the engine puts that file's widget into `custom_widgets_container` of the decision window.
    Which one depends on the decision that is open, so the files of the window cannot say it and
    the live tree can: the child there carries the name of its file. Measured 1 October 2026 on
    1.20: 91 such references to 15 files, and the top block of each file is a widget with exactly
    the file's name. The last file of that name in load order wins, as everywhere in the engine.
    """
    rows = rows if rows is not None else files()
    if table is None or local is None:
        table, local = type_table(rows)
    wanted = DECISION_WIDGETS + name.lower() + '.gui'
    found = [(virtual, full) for _, virtual, full in rows if virtual.replace('\\', '/').lower() == wanted]
    if not found:
        raise GuiError(f'no decision widget {name!r} on disk')
    virtual, full = found[-1]
    for entry in read(full):
        if entry['body'] and any(inner['key'] == 'name' and inner['value'] == name
                                 for inner in entry['body']):
            return build(entry['key'], entry['body'], virtual, Templates(table, local))
    raise GuiError(f'{virtual} has no block named {name!r}')


LOCALIZATION = re.compile(r'^\s*([^\s:#][^\s:]*):\s*\d*\s*"(.*)"\s*$')


def localization(language: str = 'english') -> dict[str, str]:
    """Key -> sentence, from the localization files of the game and of the active mods.

    This is the other half of the meaning: the gui file says which key a widget carries, and this
    says what that key reads as. A mod that ships a key of the same name replaces it, so the mods
    come last here as well.
    """
    folders = [os.path.join(paths.require('GAME'), 'game', 'localization', language)]
    for folder in paths.mod_folders():
        folders.append(os.path.join(folder, 'localization', language))
    out: dict[str, str] = {}
    for base in folders:
        if not os.path.isdir(base):
            continue
        for root, _, names in os.walk(base):
            for name in sorted(names):
                if not name.endswith('.yml'):
                    continue
                with open(os.path.join(root, name), encoding='utf-8-sig',
                                 errors='replace') as file:
                    for line in file:
                        found = LOCALIZATION.match(line)
                        if found:
                            out[found.group(1)] = found.group(2)
    return out


STYLE = re.compile(r'#[A-Za-z0-9_;:,]+\s|#!')
PLACEHOLDER = 'DEFAULT_TEXT'


def strip_style(text: str | None) -> str:
    """The style markup as it is written in the localization files: `#weak ... #!`.

    A different thing from `widgettree.strip_markup`, which strips the byte codes the game has
    already turned that into by the time the text sits in a widget. Comparing the two sides without
    this makes every styled sentence look like a mismatch.
    """
    return STYLE.sub('', text or '')
