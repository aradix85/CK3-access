"""The screen files: what the product says about a screen, and in which order.

A screen file holds exceptions, never a description of a whole screen: what to read first, what
to keep quiet about, how a repeated row reads. Whatever it does not name is read in the order the
gui files give. A file that falls behind a patch therefore costs detail and never the screen
itself, which is the difference with a mod that replaces the window outright.

It is written in the game's own format and read with the game's own reader, so a tester who mods
already knows it and there is no second parser to keep working.

This is the mechanical half of that promise: every screen file points at the game through data
functions and widget names, and a patch can take those away. This says which ones are gone,
before a player hears a screen go quiet.

Nothing here talks to the game. It reads `screens\\` and the gui files.
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import guimap
import paths

SCREENS = os.path.join(paths.PROJECT, 'screens')

# A data function as the gui files write it: `EventOption.GetText`, `Character.GetName`.
FUNCTION = re.compile(r'\b([A-Z][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)')


def entries(nodes):
    """Every entry in a screen file, at any depth."""
    for entry in nodes:
        yield entry
        if entry['body']:
            for deeper in entries(entry['body']):
                yield deeper


def read(path):
    """One screen file, parsed."""
    with open(path, encoding='utf-8') as handle:
        return guimap.parse(handle.read())


def references(nodes):
    """What a screen file points at: its windows, its data functions, its widget names."""
    windows, functions, names = [], set(), set()
    for entry in entries(nodes):
        value = entry['value']
        if value is None:
            continue
        if entry['key'] == 'window':
            windows.append(value)
        elif entry['key'] == 'widget':
            names.add(value)
        functions.update(FUNCTION.findall(value))
    return windows, functions, names


def window_contents(node, text, names):
    """Every attribute value and every widget name below this node."""
    for key, value in node['attrs']:
        if value is None:
            continue
        text.append(value)
        if key == 'name':
            names.add(value)
    for child in node['children']:
        window_contents(child, text, names)


def check(folder=SCREENS):
    """Every screen file against the gui files as they are on disk right now."""
    rows = guimap.files()
    table, local = guimap.type_table(rows)
    known = guimap.windows(rows)

    gone = 0
    for path in sorted(glob.glob(os.path.join(folder, '*.screen'))):
        name = os.path.basename(path)
        windows, functions, widgets = references(read(path))

        missing, text, present = [], [], set()
        for window in windows:
            if window not in known:
                missing.append('the window ' + window)
                continue
            tree, _ = guimap.window(window, table, local, known)
            window_contents(tree, text, present)
        blob = '\n'.join(text)

        missing += sorted(one for one in functions if one not in blob)
        missing += sorted('the widget ' + one for one in widgets if one not in present)
        for one in missing:
            print('%s points at %s, and the gui files no longer have it.' % (name, one))
        gone += len(missing)

        print('%s: %d windows, %d data functions and %d widget names, %d of them gone.'
              % (name, len(windows), len(functions), len(widgets), len(missing)))
    return gone


def main():
    gone = check()
    if gone:
        print('%d references are gone. Those screens read the wrong thing, or nothing.' % gone)
    else:
        print('Every screen file still fits the gui files on disk.')
    sys.exit(1 if gone else 0)


if __name__ == '__main__':
    main()
