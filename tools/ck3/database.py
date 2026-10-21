"""Reads the game's own databases off disk: which key sits at which place, and what it is called.

The model gives a number where the game means a culture, a faith or a trait. That number is an
index into a database the engine loaded, and these files are that database. Nothing here talks to
the game; it is the same merge the engine does - the game's folder first, the active mods after it
in load order, a file at a virtual path replacing the one before it.

**Which number means which key is read from the running game** (`numbering.keys`), not guessed
from the file order. Only for cultures does the file order hold, and a save says so
(`culture_numbers`).
"""
import os
import re

from tools import paths
from tools.ck3 import guimap

# Where each database lives: every entry is a top-level key in the files of that folder. Since
# 1.20.0.2 a faith is one in `religion/faith_types` (103 on 1 October 2026), no longer inside a
# religion.
PLACES = {
    'culture': 'culture/cultures',
    'faith': 'religion/faith_types',
    'religion': 'religion/religion_types',
    'rite': 'religion/rite_types',
    'trait': 'traits',
    'government': 'governments',
}


def files(branch: str) -> list[tuple[str, str, str]]:
    """Every file of one database the engine has loaded, in load order, as (layer, virtual, full).

    The same replacement rule as the gui set: a mod file at a virtual path the game also has
    replaces it whole rather than merging into it. Sorting this list away would put a mod's
    `00_...txt` in front of the game's and lose exactly the entries a mod means to add.
    """
    layers = [('game', os.path.join(paths.require('GAME'), 'game', 'common'))]
    layers += [('mod', os.path.join(folder, 'common')) for folder in paths.mod_folders()]
    found: list[tuple[str, str, str]] = []
    for layer, base in layers:
        root = os.path.join(base, *branch.split('/'))
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if name.endswith('.txt'):
                found.append((layer, name, os.path.join(root, name)))
    return guimap.last_wins(found)


def entries(kind: str) -> list[tuple[str, str, str]]:
    """The keys of one database in the order the files give them, as (key, layer, file).

    Order is kept and never sorted, because the only orderings worth testing against the game are
    the ones the files actually produce.
    """
    return [(entry['key'], layer, virtual) for layer, virtual, full in files(PLACES[kind])
            for entry in guimap.read(full) if entry['key'] and entry['body']]


def named(kind: str, localization: dict[str, str] | None = None) -> dict[str, str]:
    """Key -> the sentence a player sees, for every entry that has one.

    The convention is measured rather than assumed: a culture and a faith are localized under
    their own key, a trait under `trait_<key>`. Running this is the check that the reader found
    real entries - a key that resolves to a sentence exists in two independent places.
    """
    localization = localization if localization is not None else guimap.localization()
    out: dict[str, str] = {}
    for key, _, _ in entries(kind):
        for candidate in (key, f'{kind}_{key}', f'{key}_name'):
            if candidate in localization:
                out[key] = localization[candidate]
                break
    return out


def main() -> None:
    localization = guimap.localization()
    print(f"{'database'!s:<12} {'keys'!s:>6} {'named'!s:>6} {'files'!s:>6}")
    for kind, branch in PLACES.items():
        print(f'{kind:<12} {len(entries(kind)):6d} {len(named(kind, localization)):6d} '
              f'{len(files(branch)):6d}')


CULTURE_ROW = re.compile(r'\n\t\t(\d+)=\{\n\t\t\tculture_template="([^"]+)"')


def culture_numbers(text: str) -> dict[int, str]:
    """Number -> culture, as the save of a state gives them.

    Cultures are the one database whose numbers the file order predicts: measured 27 August 2026,
    463 of 463 against a save. Faiths and traits do not follow it, so the game is asked for those
    (`numbering.keys`). A save is written by the engine and belongs to the state that wrote it.
    """
    return {int(n): key for n, key in CULTURE_ROW.findall(text)}


if __name__ == '__main__':
    main()
