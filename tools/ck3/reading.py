"""The generic reading rule: a window as the sentences that come out of it.

This is the floor under the whole presentation layer. Given a window, it says which units come out
and in which order, from the shape of the window plus the meaning the gui files carry - so a window
nobody ever tuned still speaks, and a screen file only ever adds exceptions on top.

The rules it applies, and every one of them is generic:
  - a widget without text says nothing, so empty containers disappear on their own;
  - the order is the child order of the tree, which is the order the designer wrote and the order
    the game draws in;
  - a repeated container is a list: it says how many there are, then the rows, then that it ended;
  - the game's markup codes come off, because they are bytes and not words.

It runs on a harvested window, so it needs no running game: that is the point of doing this half
first. `live` is the other half, on the tree of this moment, and `reader.py` is what turns either
into one line per keystroke.
"""
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


def models(node, model=None, out=None):
    """Per widget on disk, the data model of the nearest repeated container above it.

    That is what makes a row of a list one unit instead of as many units as there are rows.

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
            model = value
    out[id(node)] = model
    for child in node['children']:
        models(child, model, out)
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

    Three ways it can fail to be, and each one is a measurement rather than a guess. A row scrolled
    past the end of its list keeps alpha 1 and a rectangle, so `clipped` is the only thing that says
    so. Alpha belongs to the whole parent chain and not to the widget: one ancestor at zero and
    nothing below it is visible. And a widget can be laid outside the drawing area entirely, which
    is where this game parks what it is not showing.

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
        node = by_address.get(node['parent'])
    return True


def units(window, table, local, known, root, record):
    """Every unit this window says, in order, each with the list it belongs to."""
    tree, _ = guimap.window(window, table, local, known)
    model_of = models(tree)
    source_of = {id(built): source
                 for source, built, _ in pairing.pairs(window, table, local, known, root, record,
                                                       tree)}

    area = record['size'] if 'size' in record else derive.drawing_area()
    by_address = {node['address']: node for node in record['tree']}
    by_parent, top = pairing.live_tree(record)
    out = []
    for node in live_order(by_parent, top):
        text = derive.strip_markup(node['text'] or '').strip()
        if not text or not on_screen(node, by_address, area):
            continue
        source = source_of.get(id(node))
        out.append({'text': text, 'model': model_of.get(id(source)) if source else None,
                    'fills': fills(source)})
    return out


def spoken(unit):
    """One unit as it is said.

    A number says nothing on its own: 89 is gold or prestige or a count of men, and a player who
    cannot see the icon beside it has no way to tell. The gui file does know - it says which data
    function fills that box - so the label comes from there. Measured 19 September 2026 over ten
    windows holding data: of 93 bare numbers, 83 carry such a function.

    Only a number gets one. A text that is already a word says what it is, and prefixing that
    would turn `Duke Marianos of Nobatia` into a form to be filled in.
    """
    if unit['fills'] and NUMBER.match(unit['text']):
        label = name_of(unit['fills'])
        if label:
            return '%s %s' % (label, unit['text'])
    return unit['text']


def sentences(found):
    """The units as the lines a player hears, with a list saying its size and its end."""
    out, at = [], 0
    while at < len(found):
        model = found[at]['model']
        if model is None:
            out.append(spoken(found[at]))
            at += 1
            continue
        rows = []
        while at < len(found) and found[at]['model'] == model:
            rows.append(spoken(found[at]))
            at += 1
        word = name_of(model)
        out.append('%d %s:' % (len(rows), word))
        out += rows
        out.append('end of the %s' % word)
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
    return sentences(units(window, table, local, known, root, record))


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
    if window is None:
        if not drawn:
            return None, []
        window = nodes[max(drawn, key=path)][6]

    record, _, _, _ = openers.live_record(game, pid, window)
    if tables is None:
        rows = guimap.files()
        table, local = guimap.type_table(rows)
        known = guimap.windows(rows)
        tables = (table, local, known, pairing.root_finder(table))
    table, local, known, root = tables
    return window, sentences(units(window, table, local, known, root, record)), windows


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
            print('    ' + line)
        if aloud:
            for line in lines:
                speech.output(line, speech.QUEUE)
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
            print('    ' + line)
        if aloud:
            for line in lines:
                speech.output(line, speech.QUEUE)


if __name__ == '__main__':
    main()
