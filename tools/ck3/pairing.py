"""Pairs the widget tree on disk with the widget tree the game actually built.

The gui files say *why* a widget shows what it shows; the harvested tree says *that* it is there
and what it currently reads. Neither half is worth much alone: a quarter of the harvested widgets
can be found back on disk by their name, and the rest carry a name that repeats, or none at all.
This pairs the two on structure instead - class and child order - so the name is free to be used
as a scorecard afterwards. Measured 27 August 2026 over six windows holding 6584 named live
widgets: 6477 of them come out on the right name, 98.4 per cent, without a name ever entering the
alignment. Seven land on a different name and the rest find no source at all.

Nothing here talks to the game. It reads `harvest\\` and the gui files, so it runs with the game
shut down, which is the whole point: this is the half of the sweep that needs no running game.
"""
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import derive
import guimap
import paths

HARVEST = os.path.join(paths.PROJECT, 'harvest')

# The head of a data function call: `[Character.GetName]` names Character, `[GetPlayer]` names
# GetPlayer. Only the head is taken, because that is the object the text is about and the rest is
# the question asked of it.
FUNCTION = re.compile(r'\[([A-Za-z_][A-Za-z_0-9]*)')

# `@warning_icon!` is an icon the game draws in place of the token, so it is in the localization
# and never in the text. Sibling of `guimap.strip_style`, which does the same for `#weak ... #!`.
ICON = re.compile(r'@\w+!')

# Which gui type becomes which C++ class. Derived 27 August 2026, not copied from a wiki: over all
# 178 harvested windows, every name that occurs exactly once in the live tree and resolves to one
# inheritance root on disk was tallied - 7299 such names, 24 roots, and each root pointed at
# exactly one class with no exceptions. Everything absent from this table is a property block:
# `size`, `state`, `fontcolor`, `modify_texture` and the like never reach the tree in memory.
CLASS_OF = {'icon': 'Icon', 'game_button': 'PushButton', 'vbox': 'VBoxLayout',
            'textbox': 'Textbox', 'widget': 'Widget', 'hbox': 'HBoxLayout', 'window': 'Window',
            'scrollarea': 'ScrollArea', 'editbox': 'Editbox', 'fixedgridbox': 'FixedGridBox',
            'flowcontainer': 'FlowContainer', 'container': 'Container', 'scrollbar': 'ScrollBar',
            'button_group': 'ButtonGroup', 'checkbutton': 'CheckButton',
            'progressbar': 'ProgressBar', 'dropDown': 'Dropdown', 'margin_widget': 'MarginWidget',
            'dynamicgridbox': 'DynamicGridBox', 'cameracontrolwidget': 'CameraControl',
            'overlappingitembox': 'OverlappingItemBox', 'zoomarea': 'ZoomArea',
            'portrait_button': '.?AVCGuiPortraitButton'}


def root_finder(table):
    """Type name -> the end of its inheritance chain, remembered, because the walk repeats itself
    tens of thousands of times over one window."""
    known = {}

    def root(name):
        if name not in known:
            seen, walk = set(), name
            while walk and walk not in seen:
                seen.add(walk)
                found = table.get(walk)
                if not found or found['parent'] == walk:
                    break
                walk = found['parent']
            known[name] = walk
        return known[name]
    return root


def attribute(node, key):
    for name, value in node['attrs']:
        if name == key:
            return value
    return None


def widget_children(node, root):
    """The children of a node that can reach the live tree, in file order.

    A `tooltipwidget` is not followed: the engine builds a tooltip when the pointer arrives, so on
    disk it is there and in memory it never is. Leaving them in put 120109 nodes of council_window
    against 5892 live ones; taking them out leaves 23699, and the rest of that gap is property
    blocks. A block that is not a widget is still walked through, because a widget can sit inside
    one and then belongs at its parent's place.

    **Inside a scroll area the engine puts the scrollbar last, whatever the file says.** Measured
    30 August 2026 on the ledger: the file declares the scrollbar and then the content, the game
    built the content and then the scrollbar, and since this alignment runs on class and order the
    two rows could not both match. The content lost, so the whole list under it came out with no
    source - eleven category buttons of the ledger, the counties among them, and everything below
    them. Reordering here rather than in the alignment keeps the rule where the reason for it is.
    """
    out = []
    for child in node['children']:
        if child['type'] == 'tooltipwidget':
            continue
        if root(child['type']) in CLASS_OF:
            out.append(child)
        else:
            out += widget_children(child, root)
    if root(node['type']) == 'scrollarea' and len(out) > 1:
        out.sort(key=lambda child: root(child['type']) == 'scrollbar')
    return out


PAIR, MISMATCH, REPEAT, LIVE_ONLY, DISK_ONLY = 0.0, 3.0, 0.3, 2.0, 1.0

# What wins when two moves cost the same. Spelled out, because leaving it to `min` means the
# alphabet of the internal labels decides it: renaming the moves into English moved 34 texts
# between the tallies before this was here, which is a difference no reader could have predicted
# from the code. A real correspondence goes first, a repeat before a gap, and a widget that the
# game did not build before one the files do not describe.
ORDER = {'pair': 0, 'repeat': 1, 'disk': 2, 'live': 3}


def align_row(disk, live, root):
    """Two rows of children laid against each other on class and order alone.

    Four moves, because the difference runs both ways. A widget can sit on disk and never be
    built - a branch behind a condition that is false right now. And one template row on disk can
    become as many live rows as there are records behind it, which is `REPEAT`: the same disk node
    takes another live node of the same class with it. Without that move every list in the game
    aligns one row deep and then slips for the rest of the window.

    Returns the pairs in order; a live node with no source on disk comes back paired with None,
    which is a finding rather than a gap - it says the game built something the files do not
    describe at that place.
    """
    n, m = len(disk), len(live)
    cost = [[0.0] * (m + 1) for _ in range(n + 1)]
    came = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0], came[i][0] = cost[i - 1][0] + DISK_ONLY, 'disk'
    for j in range(1, m + 1):
        cost[0][j], came[0][j] = cost[0][j - 1] + LIVE_ONLY, 'live'
    for i in range(1, n + 1):
        on_disk = CLASS_OF.get(root(disk[i - 1]['type']))
        for j in range(1, m + 1):
            same = on_disk == live[j - 1]['class']
            best = min((cost[i - 1][j - 1] + (PAIR if same else MISMATCH), ORDER['pair'], 'pair'),
                       (cost[i - 1][j] + DISK_ONLY, ORDER['disk'], 'disk'),
                       (cost[i][j - 1] + (REPEAT if same else LIVE_ONLY),
                        ORDER['repeat' if same else 'live'], 'repeat' if same else 'live'))
            cost[i][j], came[i][j] = best[0], best[2]
    out, i, j = [], n, m
    while i or j:
        step = came[i][j]
        if step == 'pair':
            out.append((disk[i - 1], live[j - 1])); i -= 1; j -= 1
        elif step == 'repeat':
            out.append((disk[i - 1], live[j - 1])); j -= 1
        elif step == 'disk':
            i -= 1
        else:
            out.append((None, live[j - 1])); j -= 1
    return list(reversed(out))


def live_tree(record):
    """The harvest is a flat list with an address and a parent address; this is it as a tree."""
    by_parent = collections.defaultdict(list)
    for widget in record['tree']:
        by_parent[widget['parent']].append(widget)
    for address in by_parent:
        by_parent[address].sort(key=lambda w: w['index'])
    return by_parent, min(record['tree'], key=lambda w: w['depth'])


def pairs(window, table, local, known, root, record=None):
    """Every live widget of one window with its source on disk, and the data context it inherits.

    The context rides along because a widget almost never names its own subject: the window says
    `datacontext = "[CharacterWindow.GetCharacter]"` and everything under it says
    `[Character.GetName]`. A text key read without that chain gives you a sentence and no idea who
    it is about.
    A live widget whose parent has no source on disk is still walked, and still counted, with no
    source of its own. Skipping it looks tidy and quietly shrinks the denominator: everything
    below an unmatched node vanished from the tally, so the share of texts whose origin is known
    was measured against a total that had already dropped the hard cases.

    `record` is normally read from the harvest, but a caller can hand one in that it built from the
    tree of the moment. That is what the chain needs: to press a button inside a window you have to
    align the window that is open right now, not the one that was harvested days ago.
    """
    if record is None:
        record = json.load(open(os.path.join(HARVEST, window + '.json'), encoding='utf-8'))
    by_parent, top = live_tree(record)
    disk_tree, _ = guimap.window(window, table, local, known)

    out, work = [], [(disk_tree, top, ())]
    while work:
        source, built, context = work.pop()
        if source is None:
            out.append((None, built, context))
            for child in by_parent.get(built['address'], []):
                work.append((None, child, context))
            continue
        own = attribute(source, 'datacontext')
        here = context + ((own,) if own else ())
        out.append((source, built, here))
        for child_source, child_built in align_row(widget_children(source, root),
                                                   by_parent.get(built['address'], []), root):
            work.append((child_source, child_built, here))
    return out


def text_source(source, localization):
    """What fills this widget: a key, a data function, both, or a placeholder.

    `DEFAULT_TEXT` is its own answer and not a failure. It is what the gui file carries where the
    code sets the text at run time, so for those widgets the files positively cannot tell you what
    will be on screen - only a running game can. Counting them as ordinary keys made the agreement
    between key and screen look like 57 per cent.

    A localization value can also quote another key, written `$OTHER_KEY$`. That is a third thing
    again: the sentence is fixed but not here, so reading this file alone gives you the wrong words
    - `DIARCHY_WINDOW_HEADER` is `$game_concept_diarchy$` on disk and "Power Sharing" on screen.
    """
    if source is None:
        return 'no key on disk'
    if source == guimap.PLACEHOLDER:
        return 'placeholder, code fills it'
    if '[' in source:
        return 'data function'
    if source not in localization:
        return 'key not in localization'
    value = localization[source]
    if '[' in value:
        return 'data function through key'
    return 'key quoting another key' if '$' in value else 'plain key'


REPORT = os.path.join(paths.PROJECT, 'reports', 'pairing.json')


def sweep():
    """Every harvested window paired, as one tally. Takes about three minutes."""
    rows = guimap.files()
    table, local = guimap.type_table(rows)
    known = guimap.windows(rows)
    root = root_finder(table)
    localization = guimap.localization()

    count = collections.Counter()
    functions = collections.Counter()
    unplaced = collections.Counter()
    for record_path in sorted(glob.glob(os.path.join(HARVEST, '*.json'))):
        window = os.path.basename(record_path)[:-5]
        record = json.load(open(record_path, encoding='utf-8'))
        if not record.get('opened') or window not in known:
            continue
        count['windows'] += 1
        count['widgets in harvest'] += len(record['tree'])
        seen = 0
        rows_here = pairs(window, table, local, known, root)
        by_address = {built['address']: source for source, built, _ in rows_here}
        for source, built, context in rows_here:
            seen += 1
            if not built['text']:
                continue
            count['texts'] += 1
            if source is None:
                # A button carries its caption itself and the engine hangs a text box under it to
                # draw it. That box is not in the file, so the alignment cannot pair it - but its
                # parent is paired and does carry the text. This is the widget above answering for
                # it, not a guess: the check below compares the caption with what was on screen.
                above = by_address.get(built['parent'])
                if above is not None and attribute(above, 'text'):
                    count['caption of the widget above'] += 1
                    source = above
                else:
                    count['no source on disk'] += 1
                    unplaced[window] += 1
                    continue
            count['paired'] += 1
            if context:
                count['with data context'] += 1
            key = attribute(source, 'text')
            kind = text_source(key, localization)
            count[kind] += 1
            if kind == 'data function':
                for name in FUNCTION.findall(key):
                    functions[name] += 1
            if kind == 'plain key':
                shown = derive.strip_markup(built['text'] or '').strip()
                expected = ICON.sub('', guimap.strip_style(localization[key])).strip()
                count['plain key agrees' if shown == expected else 'plain key differs'] += 1
        if seen != len(record['tree']):
            raise AssertionError('%s: the walk saw %d of the %d harvested widgets - a share of '
                                 'texts is only worth anything against the whole tree'
                                 % (window, seen, len(record['tree'])))
    count['data functions together'] = (count['data function']
                                        + count['data function through key'])
    return count, functions, unplaced


def main():
    count, functions, unplaced = sweep()
    report = dict(count)
    report['top functions'] = dict(functions.most_common(20))
    # Which windows the leftover texts sit in, per window. Without this the share that lands in
    # the developers' own windows - the reason for leaving the rest alone - is a number nobody can
    # recompute after the next round, and it quietly ages into a claim no one can check.
    report['no source on disk, per window'] = dict(unplaced.most_common())
    json.dump(report, open(REPORT, 'w', encoding='utf-8'), indent=1, sort_keys=True)
    width = max(len(k) for k in count)
    for key in sorted(count):
        print('%-*s %6d' % (width, key, count[key]))
    print('\nwritten to %s' % os.path.relpath(REPORT, paths.PROJECT))


if __name__ == '__main__':
    main()
