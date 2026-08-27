"""Reads the game's own databases off disk: which key sits at which place, and what it is called.

The model gives a number where the game means a culture, a faith or a trait. That number is an
index into a database the engine loaded, and these files are that database. Nothing here talks to
the game; it is the same merge the engine does - the game's folder first, the active mods after it
in load order, a file at a virtual path replacing the one before it.

**What this does not do is decide what the number means.** The ordering the engine numbers by is
not written down anywhere on disk, and the two numbers the working notes carry have no counting
rule behind them, so no ordering here is claimed to be the engine's until it has been checked
against several characters read out of a running game. This file gives the candidates; the check
is a separate step and it needs the game.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import guimap
import paths

# Where each database lives, and how deep its entries sit. A faith is not a top-level key: it hangs
# inside a religion under `faiths`, which is why a line reader looking at column zero finds none of
# them. Measured 27 August 2026 - `common\religion` holds no `religions` folder at all.
PLACES = {
    'culture': ('culture/cultures', ()),
    'faith': ('religion/religion_types', ('faiths',)),
    'religion': ('religion/religion_types', ()),
    'trait': ('traits', ()),
    'government': ('governments', ()),
}


def files(branch):
    """Every file of one database the engine has loaded, in load order, as (layer, virtual, full).

    The same replacement rule as the gui set: a mod file at a virtual path the game also has
    replaces it whole rather than merging into it. Sorting this list away would put a mod's
    `00_...txt` in front of the game's and lose exactly the entries a mod means to add.
    """
    layers = [('game', os.path.join(paths.GAME, 'game', 'common'))]
    layers += [('mod', os.path.join(folder, 'common')) for folder in paths.mod_folders()]
    found = []
    for layer, base in layers:
        root = os.path.join(base, *branch.split('/'))
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.endswith('.txt'):
                found.append((layer, name, os.path.join(root, name)))
    out, seen = [], set()
    for row in reversed(found):
        if row[1] not in seen:
            seen.add(row[1])
            out.append(row)
    return list(reversed(out))


def entries(kind):
    """The keys of one database in the order the files give them, as (key, layer, file).

    Order is kept and never sorted, because the only orderings worth testing against the game are
    the ones the files actually produce.
    """
    branch, inside = PLACES[kind]
    out = []
    for layer, virtual, full in files(branch):
        nodes = guimap.parse(open(full, encoding='utf-8-sig', errors='replace').read())
        for entry in nodes:
            if not entry['key'] or not entry['body']:
                continue
            if not inside:
                out.append((entry['key'], layer, virtual))
                continue
            for deeper in entry['body']:
                if deeper['key'] == inside[0] and deeper['body']:
                    for leaf in deeper['body']:
                        if leaf['key'] and leaf['body']:
                            out.append((leaf['key'], layer, virtual))
    return out


def named(kind, localization=None):
    """Key -> the sentence a player sees, for every entry that has one.

    The convention is measured rather than assumed: a culture and a faith are localized under
    their own key, a trait under `trait_<key>`. Running this is the check that the reader found
    real entries - a key that resolves to a sentence exists in two independent places.
    """
    localization = localization if localization is not None else guimap.localization()
    out = {}
    for key, _, _ in entries(kind):
        for candidate in (key, '%s_%s' % (kind, key), '%s_name' % key):
            if candidate in localization:
                out[key] = localization[candidate]
                break
    return out


def main():
    localization = guimap.localization()
    print('%-12s %6s %6s %6s   %s' % ('database', 'keys', 'named', 'files', 'first three'))
    for kind in PLACES:
        rows = entries(kind)
        keys = [k for k, _, _ in rows]
        names = named(kind, localization)
        print('%-12s %6d %6d %6d   %s'
              % (kind, len(keys), len(names), len(files(PLACES[kind][0])),
                 ', '.join(keys[:3])))
        doubled = len(keys) - len(set(keys))
        if doubled:
            print('%12s %d keys appear more than once - a later file redefines an earlier one'
                  % ('', doubled))


if __name__ == '__main__':
    main()
