"""The generic reading rule: a window as the sentences that come out of it.

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
"""
import glob
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'nvda'))

import derive
import guimap
import pairing
import paths
import speech

HARVEST = os.path.join(paths.PROJECT, 'harvest')


def models(node, chain=(), out=None):
    """Per widget on disk, the data models of the repeated containers above it, outermost first.

    That is what makes a row of a list one unit instead of as many units as there are rows, and the
    whole chain rather than the nearest one is what shows that a list sits inside a row of another.

    Everything under a `tooltipwidget` is left out, exactly as the alignment leaves it out: the
    game builds a tooltip only when the pointer arrives, so on disk it is a subtree nobody is
    reading here. It is not a detail - with tooltips `council_window` expands to 120,109 nodes
    against 23,699 without.
    """
    if node['type'] == 'tooltipwidget':
        return out if out is not None else {}
    if out is None:
        out = {}
    for key, value in node['attrs']:
        if key == 'datamodel':
            chain = chain + (value,)
    out[id(node)] = chain
    for child in node['children']:
        models(child, chain, out)
    return out


def live_order(by_parent, top):
    """The live widgets depth first in child order - the order the game draws them in."""
    out, work = [], [top]
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


def words_of(word):
    """A name in the game's spelling as words: GetSoldierCount -> soldier count, MAACap -> MAA cap.

    A run of capitals stays a run: the military view says MAA, and m a a is not a word.
    """
    out, piece = [], ''
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


def name_of(model):
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
    chains = [one for one in CHAIN.findall(call) if one.split('.')[-1] not in PLUMBING]
    head = chains[0] if chains else call
    kind = head.split('.')[0]
    word = head.split('.')[-1]
    for prefix in ('Get', 'Access'):
        if word.startswith(prefix):
            word = word[len(prefix):]
    for suffix in ('String', 'Text'):
        if word.endswith(suffix) and len(word) > len(suffix):
            word = word[:-len(suffix)]

    spelled = words_of(word)
    parts = spelled.lower().split()
    if any(part in GENERIC for part in parts):
        quoted = QUOTED.findall(call)
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


def fills(source):
    """The data function the gui file puts in this widget, if it puts one there."""
    if source is None:
        return None
    for key, value in source['attrs']:
        if key == 'text' and value and '[' in value:
            return value
    return None


def on_screen(node, by_address, area):
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

    What this cannot separate is the third state `brief\\stand.md` names: content the game stacks
    under itself, alpha 1 and unclipped, such as the ledger's eleven category tabs. The drawing-area
    test catches part of it because that content is parked far below, and nothing catches the rest.
    """
    width, height = area
    x, y, w, h = node['screen_rect']
    if x + w <= 0 or y + h <= 0 or x >= width or y >= height:
        return False
    if node['clipped']:
        return False
    seen = set()
    while node is not None and node['address'] not in seen:
        seen.add(node['address'])
        if (node['alpha'] or 0) <= 0:
            return False
        # 0x08 in the state byte is the game hiding the widget - a `visible` condition that is false
        # - while alpha stays up. Measured 21 September 2026: 40 of 260 texts in seven windows sat
        # under it, all in the character finder, such as "No matching Characters for current filter"
        # while it listed characters. A record from before 20 September carries no state.
        if (node.get('state') or 0) & 0x08:
            return False
        node = by_address.get(node['parent'])
    return True


EXPANDED = {}


def expansion(window, table, local, known):
    """The window as the gui files describe it, expanded once and then kept.

    **What this holds does not change while the game runs**: it comes from the gui files on disk,
    and those are read at startup and never written by this project. What does change is the live
    tree beside it, and that is read again every time.

    Measured 20 September 2026 on the character window: expanding it costs 1,9 of the 2,8 seconds
    a read takes, so a reader that opens the same window twice paid it twice. `brief\\stand.md`
    said this already happened; it did not.
    """
    if window not in EXPANDED:
        EXPANDED[window] = guimap.window(window, table, local, known)[0]
    return EXPANDED[window]


WORDS = None


def words_table():
    """The localisation, read once. 1173 files, so not per keystroke."""
    global WORDS
    if WORDS is None:
        WORDS = guimap.localization()
    return WORDS


GAP = re.compile(r'\[[^\]]*\]|\$[^$]*\$')


def explanation(address, by_address, source_of, localization):
    """What the game would show if you could hover here: the nearest tooltip up the chain.

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
        attrs = dict(source.get('attrs', ())) if source else {}
        key = attrs.get('tooltip') or attrs.get('tooltip_text')
        if key:
            sentence = localization.get(key.strip('"[] '))
            if sentence and not GAP.search(sentence):
                return guimap.strip_style(sentence).strip()
            return None
        address = by_address[address]['parent']
    return None


def rows_of(node, by_address, source_of):
    """The row this unit stands in, per list around it, outermost first, as live addresses.

    A list is the live widget whose source on disk carries a `datamodel`; its row is the child of it
    on the way down to the unit. Counting these instead of units is what makes "7 counties" into the
    one county the realm window shows, whose name, development, control and holding are seven units.
    A list whose widget the alignment did not pair is missing here, so the tuple can be shorter than
    the chain of models; the caller then treats the unit as a row of its own, as before.
    """
    rows, below, walk = [], node, by_address.get(node['parent'])
    while walk is not None:
        source = source_of.get(id(walk))
        if source is not None and any(key == 'datamodel' for key, _ in source.get('attrs', ())):
            rows.append(below['address'])
        below, walk = walk, by_address.get(walk['parent'])
    return tuple(reversed(rows))


def units(window, table, local, known, root, record):
    """Every unit this window says, in order, each with the list it belongs to."""
    tree = expansion(window, table, local, known)
    model_of = models(tree)
    source_of = {id(built): source
                 for source, built, _ in pairing.pairs(window, table, local, known, root, record,
                                                       tree)}

    area = record['size'] if 'size' in record else derive.drawing_area()
    words = words_table()
    by_address = {node['address']: node for node in record['tree']}
    by_parent, top = pairing.live_tree(record)
    out = []
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
                    'state': state_word(node, by_address),
                    'explain': explanation(node['address'], by_address, source_of, words),
                    'address': node['address'], 'parent': node['parent']})
    return out


SCREENS = None


def screen_rules():
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
    `list` with its count and its closing line is what the generic rule already does for every
    repeated container, so a file saying it changes nothing. `state` was a word per screen and is
    a field since 20 September 2026 that holds for every button in the game. And `explain` names a
    data function - `[EventOption.GetTooltip]` - which nothing here can evaluate; wiring it would
    be machinery for a case that cannot occur, and the explain key already says when there is no
    sentence to give.

    A patch that takes a function away costs its line its place and nothing else - it falls back
    into file order, and `tools\\ck3\\screens.py` says which one is gone.
    """
    global SCREENS
    if SCREENS is None:
        import screens
        SCREENS = {}
        for path in glob.glob(os.path.join(screens.SCREENS, '*.screen')):
            nodes = screens.read(path)
            rules = {'order': [], 'keys': {}}
            for entry in screens.entries(nodes):
                if entry['key'] == 'order' and entry['body']:
                    rules['order'] = [line['value'] and _function(line['value'])
                                      for line in entry['body']
                                      if line['key'] == 'read' and line['value']]
                elif entry['key'] == 'list' and entry['body']:
                    model = next((_function(line['value']) for line in entry['body']
                                  if line['key'] == 'of' and line['value']), None)
                    said = next((line['value'] for line in screens.entries(entry['body'])
                                 if line['key'] == 'key' and line['value']), None)
                    if model and said:
                        rules['keys'][model] = said.strip('"')
            for window in screens.references(nodes)[0]:
                SCREENS[window] = rules
    return SCREENS


def _function(value):
    """A data function as a key to compare on: brackets and the format tail taken off."""
    return (value or '').strip().lstrip('[').rstrip(']').split('|')[0].strip()


def in_order(window, found):
    """The units with what a screen file names first, first. Stable, so the rest keeps its order.

    A unit that belongs to a list takes the rank of its list, so a group never gets torn apart by
    one of its rows matching.

    **A line may name a widget instead of a data function, and it has to.** Not every text box is
    filled by one: `character_name` carries the name of the character and no function at all, so a
    screen file that points at `GetNameNoTooltip` matches nothing - while `tools\\ck3\\screens.py`
    reports it as fine, because that function does exist elsewhere in the gui set. That check
    proves a name is not gone; it does not prove it points at the widget you meant.
    """
    wanted = screen_rules().get(window, {}).get('order')
    if not wanted:
        return found
    rank = {name: place for place, name in enumerate(wanted)}

    def place_of(unit):
        for key in (_function(unit['model']) if unit['model'] else None,
                    _function(unit['fills']) if unit['fills'] else None,
                    unit['name']):
            if key and key in rank:
                return rank[key]
        return len(wanted)

    return sorted(found, key=place_of)


UNUSABLE = 0x06


def state_word(node, by_address):
    """`unavailable` in front of a line whose button the game has switched off, or nothing.

    **Measured 20 September 2026, and it is a field rather than a rule per screen.** The state
    byte at the offset the window flag sits at carries the low bits 0x02 and 0x04 together on a
    button the game has disabled: the save dialog's save button went from 0x00 to 0x06 and back
    while the name field was emptied and typed into, and the cancel button beside it - which the
    file leaves enabled - did not move. Over three windows and 6906 widgets no widget carried
    those bits without an `enabled` condition on itself or an ancestor.

    The word goes in front, because a state that arrives after the sentence arrives too late to
    act on (`brief\\schermen.md`). It is looked for up the chain: the text sits inside the button,
    and it is the button that is switched off.
    """
    walk, depth = node, 0
    while walk is not None and depth < 12:
        if (walk.get('state') or 0) & UNUSABLE:
            return 'unavailable'
        walk, depth = by_address.get(walk['parent']), depth + 1
    return None


def spoken(unit):
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
            said = '%s %s' % (label, said)
    return '%s, %s' % (unit['state'], said) if unit.get('state') else said


def joined(found):
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
    out, taken = [], set()
    for index, unit in enumerate(found):
        if index in taken:
            continue
        if not NUMBER.match(unit['text']):
            out.append(unit)
            continue
        partner = None
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
        out.append(dict(label, text='%s %s' % (label['text'], unit['text'])))
    return out


def sentences(found, window=None):
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
    keys = screen_rules().get(window, {}).get('keys', {}) if window else {}

    def chain_of(unit):
        return unit.get('models') or ((unit['model'],) if unit['model'] else ())

    out, at = [], 0
    while at < len(found):
        chain = chain_of(found[at])
        if not chain:
            out.append({'say': spoken(found[at]), 'explain': found[at]['explain']})
            at += 1
            continue
        outer = chain[0]
        group = []
        while at < len(found) and chain_of(found[at])[:1] == (outer,):
            group.append(found[at])
            at += 1
        # The rows are counted at the shallowest depth of the group, which is not always the outer
        # list itself: in the message settings every text sits one list deeper. A row is the live
        # widget the unit stands in, so the name, value and icon text of one entry count once.
        base = min(len(chain_of(unit)) for unit in group)

        def row_at(unit, depth):
            rows_up = unit.get('rows') or ()
            return rows_up[depth - 1] if len(rows_up) >= depth else unit['address']

        rows = {}
        for unit in group:
            entry = rows.setdefault(row_at(unit, base), ([], []))
            entry[0 if len(chain_of(unit)) == base else 1].append(unit)
        lines = []
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
                    word_inner = name_of(chain_of(inner[0])[base])
                    said_here[-1] += ', %d %s' % (len(inner_rows), word_inner)
            first = own[0] if own else None
            for index, say in enumerate(said_here):
                unit = own[index] if index < len(own) else first
                lines.append({'say': say, 'explain': unit['explain'] if unit else None})
        rows = [(own[0] if own else inner[0], inner) for own, inner in rows.values()]
        model = chain_of(rows[0][0])[-1]
        word = name_of(model)
        said = keys.get(_function(model))
        if len(rows) == 1 and not said:
            out += lines
            continue
        out.append({'say': '%d %s:%s' % (len(rows), word, ', ' + said if said else ''),
                    'explain': None})
        out += lines
        out.append({'say': 'end of the %s' % word, 'explain': None})
    return out


def read(window, table=None, local=None, known=None, root=None):
    """One harvested window as the lines it says."""
    if table is None:
        rows = guimap.files()
        table, local = guimap.type_table(rows)
        known = guimap.windows(rows)
    if root is None:
        root = pairing.root_finder(table)
    import json
    with open(os.path.join(HARVEST, window + '.json'), encoding='utf-8') as handle:
        record = json.load(handle)
    return sentences(units(window, table, local, known, root, record), window)


def live(pid, window=None, game=None, tables=None):
    """The window that is on top in the running game, as the lines it says.

    This is the other half of the same rule: the units come from the tree of this moment instead
    of from a harvested record, and everything after that is shared. Which window is on top is
    the draw order - siblings are drawn in list order and the tree keeps that order, so the
    highest path of sibling numbers is the one lying over the rest.

    `game` and `tables` are handed in by a caller that reads more than once. Building either costs
    seconds - a field check and a walk to the root, and the templates of 563 gui files - and
    neither changes while the game runs.
    """
    import collections
    import openers
    import windowmap

    if game is None:
        game = windowmap.Game(pid)
    openers.game_classes = game.window_classes      # live_record reads this module global
    nodes = game.tree()
    windows = [a for a, k in nodes.items() if k[0] in game.window_classes]
    flags = derive.flags_for(windows)

    index, seen = {}, collections.Counter()
    for address, node in nodes.items():
        index[address] = seen[node[5]]
        seen[node[5]] += 1

    def path(address):
        out = []
        while address in nodes:
            out.append(index[address])
            address = nodes[address][5]
        return tuple(reversed(out))

    drawn = [a for a in windows if flags.get(a) == 0]
    here = None
    if window is None:
        if not drawn:
            return None, []
        here = max(drawn, key=path)
        window = nodes[here][6]

    record, _, _, _ = openers.live_record(game, pid, window, here, nodes)
    if tables is None:
        rows = guimap.files()
        table, local = guimap.type_table(rows)
        known = guimap.windows(rows)
        tables = (table, local, known, pairing.root_finder(table))
    table, local, known, root = tables
    return window, sentences(units(window, table, local, known, root, record), window)


def main():
    windows = [name for name in sys.argv[1:] if not name.startswith('--')]
    aloud = '--speak' in sys.argv

    if '--live' in sys.argv:
        pid = int(windows[0])
        name, lines = live(pid, windows[1] if len(windows) > 1 else None)
        if name is None:
            print('no window is drawn; this is the main menu, and that is panels and not windows')
            return
        print('%s, %d lines' % (name, len(lines)))
        for line in lines:
            print('    %-60s %s' % (line['say'], line['explain'] or ''))
        if aloud:
            for line in lines:
                speech.output(line['say'], speech.QUEUE)
        return

    if not windows:
        windows = ['ingame_resign_confirmation']

    start = time.time()
    rows = guimap.files()
    table, local = guimap.type_table(rows)
    known = guimap.windows(rows)
    root = pairing.root_finder(table)
    print('the templates of %d gui files, once: %.1f s' % (len(rows), time.time() - start))

    for window in windows:
        start = time.time()
        lines = read(window, table, local, known, root)
        print('\n%s, %d lines, %.2f s' % (window, len(lines), time.time() - start))
        for line in lines:
            print('    %-60s %s' % (line['say'], line['explain'] or ''))
        if aloud:
            for line in lines:
                speech.output(line['say'], speech.QUEUE)


if __name__ == '__main__':
    main()
