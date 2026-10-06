r"""The generic reading rule: a window as the sentences that come out of it.

This is the floor under the whole presentation layer. Given a window, it says which units come out
and in which order, from the shape of the window plus the meaning the gui files carry - so a window
nobody ever tuned still speaks, and a screen file only ever adds exceptions on top.

The rules it applies, and every one of them is generic:
  - a widget without text says nothing, so empty containers disappear on their own, and neither
    does one the game hides or one that is not on screen (`on_screen`);
  - the order is the child order of the tree, which is the order the designer wrote and the order
    the game draws in;
  - a repeated container is a list: it says once how many rows it has, then the rows, then that it
    ended; a list inside a row is folded into that row, and a list of one row is just the row
    (`sentences`);
  - the game's markup codes come off, because they are bytes and not words.

It runs on a harvested window, so it needs no running game: that is the point of doing this half
first. `live` is the other half, on the tree of this moment, and `reader.py` is what turns either
into one line per keystroke.

Usage:  python -m tools.ck3.reading [<window> ...]
        python -m tools.ck3.reading <pid> [<window>] --live [--speak]

Without `--live` it reads harvested windows, `ingame_resign_confirmation` when none is named. With
`--live` it reads the tree of the running game, the window on top unless one is named, and
`--speak` also says the lines through NVDA.
"""
import collections
import glob
import json
import os
import re
import sys
import time
from typing import TYPE_CHECKING, TypedDict

from tools import paths
from tools.ck3 import derive, guimap, pairing
from tools.nvda import speech

if TYPE_CHECKING:
    # `live` imports it where it runs, because it brings openers and the harvest along and the
    # harvested half of this module runs without them. Only the checker sees it here.
    from tools.ck3 import windowmap

HARVEST = os.path.join(paths.PROJECT, 'harvest')


class Unit(TypedDict):
    """One text on screen, with what the gui files say about it and where it stands."""
    text: str                   # what it says, the markup taken off
    model: str | None           # the innermost list it belongs to, or None
    models: tuple[str, ...]     # every list around it, outermost first
    rows: tuple[str, ...]       # per list around it, the row it stands in, as a live address
    fills: str | None           # the data function its gui file puts in it
    name: str
    state: str | None           # `unavailable`, or nothing
    explain: str | None         # the tooltip up the chain, when it is a whole sentence
    address: str
    parent: str


class Line(TypedDict):
    """One line a player hears, and the tooltip that explains it."""
    say: str
    explain: str | None


class ScreenRule(TypedDict):
    """What a screen file adds to one window: which lines come first, and which key a list takes."""
    order: list[str]
    keys: dict[str, str]


class Harvest(pairing.Record):
    """A harvested window as this module reads it: its widgets and the drawing area it was taken on."""
    size: list[int]


def models(node: guimap.Node, chain: tuple[str, ...] = (),
           out: dict[int, tuple[str, ...]] | None = None) -> dict[int, tuple[str, ...]]:
    """Per widget on disk, the data models of the repeated containers above it, outermost first.

    That is what makes a row of a list one unit instead of as many units as there are rows, and the
    whole chain rather than the nearest one is what shows that a list sits inside a row of another.

    Everything under a `tooltipwidget` is left out, exactly as the alignment leaves it out: the
    game builds a tooltip only when the pointer arrives, so on disk it is a subtree nobody is
    reading here. It is not a detail - with tooltips `council_window` expands to 120,109 nodes
    against 23,699 without.

    A `datamodel` is a value; one without is a file this reader cannot read, and it says so.
    """
    if node['type'] == 'tooltipwidget':
        return out if out is not None else {}
    if out is None:
        out = {}
    for key, value in node['attrs']:
        if key == 'datamodel':
            if value is None:
                raise guimap.GuiError(f"a datamodel without a value, in a {node['type']}")
            chain = chain + (value,)
    out[id(node)] = chain
    for child in node['children']:
        models(child, chain, out)
    return out


def live_order(by_parent: dict[str, list[pairing.Harvested]],
               top: pairing.Harvested) -> list[pairing.Harvested]:
    """The live widgets depth first in child order - the order the game draws them in."""
    out: list[pairing.Harvested] = []
    work = [top]
    while work:
        node = work.pop()
        out.append(node)
        work += reversed(by_parent.get(node['address'], []))
    return out


CHAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
QUOTED = re.compile(r"'([^']+)'")
# Engine helpers that wrap a value without saying anything about it. Skipping them is what turns
# `GetDataModelSize(LedgerWindow.GetWars)` into wars instead of into data model size.
PLUMBING = ('GetDataModelSize', 'Add_int32', 'Subtract_int32', 'Multiply_int32', 'Divide_int32',
            'Select_int32', 'Select_CString', 'Select_float', 'Select_CFixedPoint',
            'FixedPointToInt', 'Concatenate', 'AddTextIf', 'Localize')
GENERIC = ('value', 'text', 'name', 'size', 'count', 'string')


def words_of(word: str) -> str:
    """A name in the game's spelling as words: GetSoldierCount -> soldier count, MAACap -> MAA cap.

    A run of capitals stays a run: the military view says MAA, and m a a is not a word.
    """
    out: list[str] = []
    piece = ''
    for at, letter in enumerate(word):
        following = word[at + 1] if at + 1 < len(word) else ''
        starts = letter.isupper() and piece and (not piece[-1].isupper() or following.islower())
        if starts:
            out.append(piece)
            piece = ''
        piece += letter
    out.append(piece)
    return ' '.join(part if part.isupper() and len(part) > 1 else part.lower()
                    for part in out if part).strip()


def name_of(model: str) -> str:
    """A data function as a word for the player: GetOptions -> options, GetGold|0 -> gold.

    Three things have to come off, and each of them was a label that read as machinery. The tail
    after `|` is a formatting code. The arguments are not the subject - `GetOpinionOf( GetLiege )`
    is an opinion and not a liege - so the first call in the line wins over what sits inside it.
    And a wrapper that only counts or adds says nothing, so it is stepped over.

    Where the name that remains is generic, something else says it: a quoted argument is the
    game's own key for the thing - `GetTabItemsCount('family')` is the family - and failing that
    the type takes over, so `SkillItem.GetValue` reads as skill.
    """
    call = model.strip('[]').split('|')[0].strip()
    found: list[str] = CHAIN.findall(call)      # no groups in the pattern, so whole matches
    chains = [one for one in found if one.split('.')[-1] not in PLUMBING]
    head = chains[0] if chains else call
    kind = head.split('.')[0]
    word = head.split('.')[-1]
    for prefix in ('Get', 'Access'):
        word = word.removeprefix(prefix)
    for suffix in ('String', 'Text'):
        if word.endswith(suffix) and len(word) > len(suffix):
            word = word[:-len(suffix)]

    spelled = words_of(word)
    parts = spelled.lower().split()
    if any(part in GENERIC for part in parts):
        quoted: list[str] = QUOTED.findall(call)    # one group, so its text per match
        if quoted:
            return quoted[-1].replace('_', ' ').strip()
    if spelled.lower() in GENERIC:
        word = kind
        for suffix in ('Item', 'Window', 'View', 'Data'):
            if word.endswith(suffix) and len(word) > len(suffix):
                word = word[:-len(suffix)]
        spelled = words_of(word)
    return spelled.strip()


NUMBER = re.compile(r'^[\d+\-.,%/ ]+$')


def fills(source: guimap.Node | None) -> str | None:
    """The data function the gui file puts in this widget, if it puts one there."""
    if source is None:
        return None
    for key, value in source['attrs']:
        if key == 'text' and value and '[' in value:
            return value
    return None


def on_screen(node: pairing.Harvested, by_address: dict[str, pairing.Harvested],
              area: tuple[int, int]) -> bool:
    """Is this widget actually drawn, or only present in the tree?

    Four ways it can fail to be, and each one is a measurement rather than a guess. A row scrolled
    past the end of its list keeps alpha 1 and a rectangle, so `clipped` is the only thing that says
    so. Alpha belongs to the whole parent chain and not to the widget: one ancestor at zero and
    nothing below it is visible. A widget can be laid outside the drawing area entirely, which is
    where this game parks what it is not showing. And 0x08 in the state byte of the widget or an
    ancestor is the game hiding it with alpha left up - the fourth, since 21 September 2026.

    Measured 20 September 2026 over the harvest: of 1753 units 83 are clipped, 6 sit behind an
    ancestor at alpha zero and 139 lie outside the drawing area - 172 in all, one in ten. The worst
    window, `window_situation`, said 48 of its 82 lines to nobody.

    The so-called third state - content the game stacks under itself, alpha 1
    and unclipped, such as the ledger's eleven category tabs - is the hidden bit: in the ledger of
    21 September 2026, 4087 of the 4088 widgets below the drawing area carry it. A record from
    before 20 September carries no state byte, and there only the drawing-area test catches part.
    """
    width, height = area
    x, y, w, h = node['screen_rect']
    if x + w <= 0 or y + h <= 0 or x >= width or y >= height:
        return False
    if node['clipped']:
        return False
    seen: set[str] = set()
    walk: pairing.Harvested | None = node
    while walk is not None and walk['address'] not in seen:
        seen.add(walk['address'])
        if (walk['alpha'] or 0) <= 0:
            return False
        # 0x08 in the state byte is the game hiding the widget - a `visible` condition that is false
        # - while alpha stays up. Measured 21 September 2026: 40 of 260 texts in seven windows sat
        # under it, all in the character finder, such as "No matching Characters for current filter"
        # while it listed characters. A record from before 20 September carries no state.
        if (walk.get('state') or 0) & derive.HIDDEN:
            return False
        walk = by_address.get(walk['parent'])
    return True


EXPANDED: dict[str, guimap.Node] = {}


def expansion(window: str, table: guimap.Table, local: guimap.LocalTable,
              known: guimap.Known) -> guimap.Node:
    """The window as the gui files describe it, expanded once and then kept.

    **What this holds does not change while the game runs**: it comes from the gui files on disk,
    and those are read at startup and never written by this project. What does change is the live
    tree beside it, and that is read again every time.

    Measured 20 September 2026 on the character window: expanding it costs 1,9 of the 2,8 seconds
    a read takes, so a reader that opens the same window twice paid it twice.
    """
    if window not in EXPANDED:
        EXPANDED[window] = guimap.window(window, table, local, known)[0]
    return EXPANDED[window]


WORDS: dict[str, str] | None = None


def words_table() -> dict[str, str]:
    """The localisation, read once. Over a thousand files, so not per keystroke."""
    global WORDS
    if WORDS is None:
        WORDS = guimap.localization()
    return WORDS


GAP = re.compile(r'\[[^\]]*\]|\$[^$]*\$')


def explanation(address: str, by_address: dict[str, pairing.Harvested],
                source_of: dict[int, guimap.Node | None], localization: dict[str, str]) -> str | None:
    """The tooltip the gui files predict here: the nearest one up the chain.

    The game's own tooltip can be read while the game is in front, where its hover point follows the
    pointer; until the reader does that, this prediction is what the explain key says.

    **A tooltip hangs on the button, not on the text inside it.** Counted over the harvest on
    20 September 2026: of 1581 units 49 carry a tooltip themselves and 301 more have one on an
    ancestor, two hundred of those one single level up. Asking only the unit's own widget reaches
    three per cent of the screen; walking up reaches twenty-two.

    Returns the sentence when it is whole, and the key when it is not - because a tooltip with
    gaps in it is the game's own sum, and reading a skeleton full of holes is worse than saying
    that the build-up is missing. Of the 350 that have one, 190 resolve to a sentence and 32 of
    those have no gap at all; the rest is what taak 10 subtaak f has to rebuild.

    **These are harvest numbers and so a floor**: most of that round was opened through the
    console, and those windows carry captions without values. A round along the routes a player
    uses would raise them, tooltips least of all - they hang on buttons and icons, which are there
    either way.
    """
    while address in by_address:
        source = source_of.get(id(by_address[address]))
        attrs: dict[str | None, str | None] = dict(source['attrs']) if source else {}
        key = attrs.get('tooltip') or attrs.get('tooltip_text')
        if key:
            sentence = localization.get(key.strip('"[] '))
            if sentence and not GAP.search(sentence):
                return guimap.strip_style(sentence).strip()
            return None
        address = by_address[address]['parent']
    return None


def rows_of(node: pairing.Harvested, by_address: dict[str, pairing.Harvested],
            source_of: dict[int, guimap.Node | None]) -> tuple[str, ...]:
    """The row this unit stands in, per list around it, outermost first, as live addresses.

    A list is the live widget whose source on disk carries a `datamodel`; its row is the child of it
    on the way down to the unit. Counting these instead of units is what makes "7 counties" into the
    one county the realm window shows, whose name, development, control and holding are seven units.
    A list whose widget the alignment did not pair is missing here, so the tuple can be shorter than
    the chain of models; the caller then treats the unit as a row of its own, as before.
    """
    rows: list[str] = []
    below, walk = node, by_address.get(node['parent'])
    while walk is not None:
        source = source_of.get(id(walk))
        if source is not None and any(key == 'datamodel' for key, _ in source['attrs']):
            rows.append(below['address'])
        below, walk = walk, by_address.get(walk['parent'])
    return tuple(reversed(rows))


def units(window: str, tables: guimap.Tables, record: pairing.Record,
          area: tuple[int, int]) -> list[Unit]:
    """Every unit this window says, in order, each with the list it belongs to.

    `area` is the drawing area the record was taken on: stored with a harvested window, asked of
    Windows for a live one.
    """
    table, local, known, root = tables
    tree = expansion(window, table, local, known)
    model_of = models(tree)
    source_of = {id(built): source
                 for source, built, _ in pairing.pairs(window, table, local, known, root, record,
                                                       tree)}

    words = words_table()
    by_address = {node['address']: node for node in record['tree']}
    by_parent, top = pairing.live_tree(record)
    out: list[Unit] = []
    for node in live_order(by_parent, top):
        text = derive.strip_markup(node['text'] or '').strip()
        if not text or not on_screen(node, by_address, area):
            continue
        source = source_of.get(id(node))
        chain = model_of.get(id(source), ()) if source else ()
        out.append({'text': text, 'model': chain[-1] if chain else None, 'models': chain,
                    'rows': rows_of(node, by_address, source_of),
                    'fills': fills(source),
                    'name': node['name'],
                    'state': state_word(node.get('state')),
                    'explain': explanation(node['address'], by_address, source_of, words),
                    'address': node['address'], 'parent': node['parent']})
    return out


SCREENS: dict[str, ScreenRule] | None = None


def screen_rules() -> dict[str, ScreenRule]:
    """Per window, what a screen file adds on top of the reading rule.

    **A screen file is an exception on top of the reading rule, and this is where it is applied.**
    The format and its check have existed since 19 September 2026; nothing read them, so a file
    could be written, pass the check and change nothing at all.

    Two of the five blocks are read here. `order` says which lines come first, and everything it
    does not name keeps following in the order the gui files give. `key` says which key does
    something on a row, and it is hung on the line that counts the list rather than on every row:
    it is the same key for all of them, and a sentence repeated per option is the noise this
    project keeps deciding against.

    **The other three are deliberately not wired, and that is a finding rather than a gap.**
    `list` is what the generic rule already does for every repeated container - its count of rows
    once, a list inside a row folded into it, no announcement for one row - so a file saying it
    changes nothing. `state` was a word per screen and is
    a field since 20 September 2026 that holds for every button in the game. And `explain` names a
    data function - `[EventOption.GetTooltip]` - which nothing here can evaluate; wiring it would
    be machinery for a case that cannot occur, and the explain key already says when there is no
    sentence to give.

    A patch that takes a function away costs its line its place and nothing else - it falls back
    into file order, and `tools\\ck3\\screens.py` says which one is gone.
    """
    global SCREENS
    if SCREENS is None:
        from tools.ck3 import screens
        SCREENS = {}
        for path in glob.glob(os.path.join(screens.SCREENS, '*.screen')):
            nodes = screens.read(path)
            order: list[str] = []
            keys: dict[str, str] = {}
            for entry in guimap.walk(nodes):
                if entry['key'] == 'order' and entry['body']:
                    order = [_function(line['value']) for line in entry['body']
                             if line['key'] == 'read' and line['value']]
                elif entry['key'] == 'list' and entry['body']:
                    model = next((_function(line['value']) for line in entry['body']
                                  if line['key'] == 'of' and line['value']), None)
                    said = next((line['value'] for line in guimap.walk(entry['body'])
                                 if line['key'] == 'key' and line['value']), None)
                    if model and said:
                        keys[model] = said.strip('"')
            for window in screens.references(nodes)[0]:
                SCREENS[window] = {'order': order, 'keys': keys}
    return SCREENS


def _function(value: str | None) -> str:
    """A data function as a key to compare on: brackets and the format tail taken off."""
    return (value or '').strip().lstrip('[').rstrip(']').split('|')[0].strip()


def in_order(window: str, found: list[Unit]) -> list[Unit]:
    """The units with what a screen file names first, first. Stable, so the rest keeps its order.

    A unit that belongs to a list takes the rank of its list, so a group never gets torn apart by
    one of its rows matching.

    **A line may name a widget instead of a data function, and it has to.** Not every text box is
    filled by one: `character_name` carries the name of the character and no function at all, so a
    screen file that points at `GetNameNoTooltip` matches nothing - while `tools\\ck3\\screens.py`
    reports it as fine, because that function does exist elsewhere in the gui set. That check
    proves a name is not gone; it does not prove it points at the widget you meant.
    """
    rule = screen_rules().get(window)
    wanted = rule['order'] if rule else []
    if not wanted:
        return found
    rank = {name: place for place, name in enumerate(wanted)}

    def place_of(unit: Unit) -> int:
        for key in (_function(unit['model']) if unit['model'] else None,
                    _function(unit['fills']) if unit['fills'] else None,
                    unit['name']):
            if key and key in rank:
                return rank[key]
        return len(wanted)

    return sorted(found, key=place_of)


def state_word(state: int | None) -> str | None:
    """`unavailable` in front of a line whose button the game has switched off, or nothing.

    **A field rather than a rule per screen.** 0x02 in the state byte is `enabled` false on the
    widget or on any ancestor, and the game copies it down the whole subtree (`derive.flags_for`),
    so the text inside a switched-off button carries it itself. First seen 20 September 2026 on the
    save dialog: its save button went from 0x00 to 0x06 and back while the name field was emptied
    and typed into, and the cancel button beside it did not move.

    The word goes in front, because a state that arrives after the sentence arrives too late to
    act on.
    """
    return 'unavailable' if (state or 0) & derive.SWITCHED_OFF else None


def spoken(unit: Unit) -> str:
    """One unit as it is said.

    A number says nothing on its own: 89 is gold or prestige or a count of men, and a player who
    cannot see the icon beside it has no way to tell. The gui file does know - it says which data
    function fills that box - so the label comes from there. Measured 19 September 2026 over ten
    windows holding data: of 93 bare numbers, 83 carry such a function.

    Only a number gets one. A text that is already a word says what it is, and prefixing that
    would turn `Duke Marianos of Nobatia` into a form to be filled in.

    A state word goes in front of all of it, because it has to arrive before the words it changes
    the meaning of.
    """
    said = unit['text']
    if unit['fills'] and NUMBER.match(said):
        label = name_of(unit['fills'])
        if label:
            said = f'{label} {said}'
    return '{}, {}'.format(unit['state'], said) if unit['state'] else said


def joined(found: list[Unit]) -> list[Unit]:
    """A bare number and the label beside it under the same parent are one unit, label first.

    **The file order puts the value before the thing it is about**, so a reader that speaks one
    unit per keystroke says `56` and only then `Duke Marianos of Nobatia,`. Whoever is listening
    has to hold the number until the next press to know what it was, and in a list of ten that
    happens ten times.

    **The same parent is the whole rule, and it is narrow on purpose.** Counted over the harvest on
    20 September 2026: of 141 bare numbers, 13 have a label under the same parent, 78 have one
    beside them under a different parent, and 50 have no text beside them at all. Joining across
    parents is what looks tempting and is not safe - in that group of 78 the label sits before the
    number in some and after it in others, so half of them would be glued to the wrong word. Those
    13 are clean: `Duke Marianos of Nobatia, 56`, `Family 3`, `Courtiers 9`, `Ongoing Wars 54`,
    `Monthly Maintenance: -0.4`.
    **That number is a floor**: the harvest is mostly the console route and those windows carry
    captions without values, so a window with data holds far more numbers than this counts. The
    rule is narrow enough that more of them can only help it.

    **What it deliberately does not solve** is the opinion beside a portrait, which is what raised
    the question. Measured the same day on the character window: `+83` sits three levels below the
    ancestor it shares with `Spouse` and the label sits two, and the three portraits are each built
    differently. That is not a shape to write a rule on; it belongs in a screen file.
    """
    out: list[Unit] = []
    taken: set[int] = set()
    for index, unit in enumerate(found):
        if index in taken:
            continue
        if not NUMBER.match(unit['text']):
            out.append(unit)
            continue
        partner: int | None = None
        for other in (index - 1, index + 1):
            if other < 0 or other >= len(found) or other in taken:
                continue
            beside = found[other]
            if not NUMBER.match(beside['text']) and beside['parent'] == unit['parent']:
                partner = other
                break
        if partner is None:
            out.append(unit)
            continue
        label = found[partner]
        taken.add(partner)
        if partner < index and out and out[-1] is label:
            out.pop()
        merged = label.copy()
        merged['text'] = '{} {}'.format(label['text'], unit['text'])
        out.append(merged)
    return out


def sentences(found: list[Unit], window: str | None = None) -> list[Line]:
    """The units as the lines a player hears: each one what it says, and what explains it.

    **A line is a pair and not a string, since 20 September 2026.** The explain key needs the
    tooltip that belongs to the line the reader is standing on, and a list of strings has nowhere
    to keep it. The lines a list adds around its rows - its size and its end - explain nothing.

    **A list inside a row of another list is folded into that row, and a list of one row is not
    announced.** Decided 21 September 2026 with the player, after the message settings read as
    fourteen lists of one: every category row carries a list of its own, and grouping on the nearest
    list cut the outer list at each inner one - 56 of that window's 94 lines were announcements, and
    over the 25 windows with a player route 124 of 723. Now the outer list is said once with its
    real count, and a row carries its inner list: the one item when there is one - the chosen entry
    of a dropdown, "New Heir, Toast" - and how many when there are more, the items themselves waiting
    for a way to step into a row. The rows are the units at the shallowest depth of the group. A unit of an inner list belongs to the row before it, which is how the
    tree orders them; one that comes before any row becomes a row itself. A list of one row is that
    row, unless the screen file puts a key on the list - then the announcement carries the key.
    """
    found = in_order(window, joined(found)) if window else joined(found)
    rule = screen_rules().get(window) if window else None
    keys = rule['keys'] if rule else {}

    def row_at(unit: Unit, depth: int) -> str:
        """The live widget the unit stands in at this depth of lists, or the unit itself."""
        rows_up = unit['rows']
        return rows_up[depth - 1] if len(rows_up) >= depth else unit['address']

    out: list[Line] = []
    at = 0
    while at < len(found):
        chain = found[at]['models']
        if not chain:
            out.append({'say': spoken(found[at]), 'explain': found[at]['explain']})
            at += 1
            continue
        outer = chain[0]
        group: list[Unit] = []
        while at < len(found) and found[at]['models'][:1] == (outer,):
            group.append(found[at])
            at += 1
        # The rows are counted at the shallowest depth of the group, which is not always the outer
        # list itself: in the message settings every text sits one list deeper. A row is the live
        # widget the unit stands in, so the name, value and icon text of one entry count once.
        base = min(len(unit['models']) for unit in group)

        rows: dict[str, tuple[list[Unit], list[Unit]]] = {}
        for unit in group:
            entry = rows.setdefault(row_at(unit, base), ([], []))
            entry[0 if len(unit['models']) == base else 1].append(unit)
        # The first unit of every row, taken before the loop below pops one off a row that has no
        # unit of its own: after that pop a row with one inner unit is empty.
        firsts = [own[0] if own else inner[0] for own, inner in rows.values()]
        lines: list[Line] = []
        for own, inner in rows.values():
            said_here = [spoken(unit) for unit in own] or [spoken(inner.pop(0))]
            if inner:
                inner_rows = {row_at(one, base + 1) for one in inner}
                if len(inner_rows) == 1:
                    # One visible entry is said in full: the chosen value of a dropdown - "New
                    # Heir, Toast" - or the one county of a duchy, and a count would hide exactly
                    # what the row is about.
                    said_here[-1] += ', ' + ', '.join(spoken(one) for one in inner)
                else:
                    word_inner = name_of(inner[0]['models'][base])
                    said_here[-1] += f', {len(inner_rows)} {word_inner}'
            first = own[0] if own else None
            for index, say in enumerate(said_here):
                owner = own[index] if index < len(own) else first
                lines.append({'say': say, 'explain': owner['explain'] if owner else None})
        model = firsts[0]['models'][-1]
        word = name_of(model)
        said = keys.get(_function(model))
        if len(firsts) == 1 and not said:
            out += lines
            continue
        out.append({'say': f"{len(firsts)} {word}:{', ' + said if said else ''}",
                    'explain': None})
        out += lines
        out.append({'say': f'end of the {word}', 'explain': None})
    return out


def read(window: str, tables: guimap.Tables | None = None) -> list[Line]:
    """One harvested window as the lines it says.

    A window the harvest could not open has a record without widgets, and that is said rather than
    read as an empty window.
    """
    with open(os.path.join(HARVEST, window + '.json'), encoding='utf-8') as handle:
        loaded = json.load(handle)
    if not loaded.get('opened'):
        raise SystemExit(f'{window} was not opened in the harvest, so there is nothing to read')
    record: Harvest = loaded
    width, height = record['size']
    return sentences(units(window, tables or guimap.tables(), record, (width, height)), window)


def live(pid: int, window: str | None = None, game: 'windowmap.Game | None' = None,
         tables: guimap.Tables | None = None) -> tuple[str | None, list[Line]]:
    """The window that is on top in the running game, as the lines it says.

    This is the other half of the same rule: the units come from the tree of this moment instead
    of from a harvested record, and everything after that is shared. Which window is on top is
    the draw order - siblings are drawn in list order and the tree keeps that order, so the
    highest path of sibling numbers is the one lying over the rest.

    `game` and `tables` are handed in by a caller that reads more than once. Building either costs
    seconds - a field check and a walk to the root, and the templates of some six hundred gui files - and
    neither changes while the game runs.
    """
    from tools.ck3 import openers, windowmap

    if game is None:
        game = windowmap.Game(pid)
    openers.game_classes = game.window_classes      # live_record reads this module global
    nodes = game.tree()
    windows = [a for a, k in nodes.items() if k[0] in game.window_classes]
    drawn = derive.shown(nodes, windows)

    index: dict[int, int] = {}
    seen: collections.Counter[int] = collections.Counter()
    children: collections.defaultdict[int, list[int]] = collections.defaultdict(list)
    for address, node in nodes.items():
        index[address] = seen[node[5]]
        seen[node[5]] += 1
        children[node[5]].append(address)

    def path(address: int) -> tuple[int, ...]:
        out: list[int] = []
        while address in nodes:
            out.append(index[address])
            address = nodes[address][5]
        return tuple(reversed(out))

    def shows_text(top: int) -> bool:
        below: list[int] = []
        stack = [top]
        while stack:
            below.append(stack.pop())
            stack.extend(children[below[-1]])
        kinds = derive.class_map(pid, {a: nodes[a][0] for a in below})
        texts = [a for a in below
                 if kinds[a] in derive.TEXT_CLASSES and derive.strip_markup(nodes[a][7]).strip()]
        return bool(derive.shown(nodes, texts))

    here: int | None = None
    if window is None:
        # A window that lets the mouse through is drawn without being a panel: `layer_window` and
        # `achievement_popup_window` stand on every screen that way, and the activity planner is
        # one too. So a panel goes first, and one of those counts only while it shows text.
        solid = [a for a, flag in drawn.items() if not flag & derive.PASSES_CLICKS]
        clear = [a for a in drawn if a not in solid and shows_text(a)]
        if not solid and not clear:
            return None, []
        here = max(solid or clear, key=path)
        window = nodes[here][6]

    record, _, _, _ = openers.live_record(game, pid, window, here, nodes)
    return window, sentences(units(window, tables or guimap.tables(), record,
                                   derive.drawing_area()), window)


def main() -> None:
    windows = [name for name in sys.argv[1:] if not name.startswith('--')]
    aloud = '--speak' in sys.argv

    if '--live' in sys.argv:
        pid = int(windows[0])
        name, lines = live(pid, windows[1] if len(windows) > 1 else None)
        if name is None:
            print('no window is drawn; this is the main menu, and that is panels and not windows')
            return
        print(f'{name}, {len(lines)} lines')
        for line in lines:
            print(f"    {line['say']!s:<60} {line['explain'] or ''}")
        if aloud:
            for line in lines:
                speech.output(line['say'], speech.QUEUE)
        return

    if not windows:
        windows = ['ingame_resign_confirmation']

    start = time.time()
    tables = guimap.tables()
    print(f'the templates of the gui files, once: {time.time() - start:.1f} s')

    for window in windows:
        start = time.time()
        lines = read(window, tables)
        print(f'\n{window}, {len(lines)} lines, {time.time() - start:.2f} s')
        for line in lines:
            print(f"    {line['say']!s:<60} {line['explain'] or ''}")
        if aloud:
            for line in lines:
                speech.output(line['say'], speech.QUEUE)


if __name__ == '__main__':
    main()
