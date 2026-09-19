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
first. What it cannot show is how it feels to step through it one key at a time - that needs the
live half, and this is what that half will call.
"""
import os
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


def name_of(model):
    """A data model as a word for the player: GetOptions -> options."""
    word = model.strip('[]').split('.')[-1].split('(')[0]
    for prefix in ('Get', 'Access'):
        if word.startswith(prefix):
            word = word[len(prefix):]
    out = ''
    for letter in word:
        out += (' ' if out and letter.isupper() else '') + letter.lower()
    return out


def units(window, table, local, known, root, record):
    """Every unit this window says, in order, each with the list it belongs to."""
    tree, _ = guimap.window(window, table, local, known)
    model_of = models(tree)
    source_of = {id(built): source
                 for source, built, _ in pairing.pairs(window, table, local, known, root, record,
                                                       tree)}

    by_parent, top = pairing.live_tree(record)
    out = []
    for node in live_order(by_parent, top):
        text = derive.strip_markup(node['text'] or '').strip()
        if not text:
            continue
        source = source_of.get(id(node))
        out.append({'text': text, 'model': model_of.get(id(source)) if source else None})
    return out


def sentences(found):
    """The units as the lines a player hears, with a list saying its size and its end."""
    out, at = [], 0
    while at < len(found):
        model = found[at]['model']
        if model is None:
            out.append(found[at]['text'])
            at += 1
            continue
        rows = []
        while at < len(found) and found[at]['model'] == model:
            rows.append(found[at]['text'])
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


def main():
    windows = [name for name in sys.argv[1:] if not name.startswith('--')]
    aloud = '--speak' in sys.argv
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
