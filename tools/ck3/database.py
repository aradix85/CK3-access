"""Reads the game's own databases off disk: which key sits at which place, and what it is called.

The model gives a number where the game means a culture, a faith or a trait. That number is an
index into a database the engine loaded, and these files are that database. Nothing here talks to
the game; it is the same merge the engine does - the game's folder first, the active mods after it
in load order, a file at a virtual path replacing the one before it.

**Which number means which key is read from a save, not guessed from the file order.** A save is
written by the engine and carries all three lists, and it needs no running game. See `numbering`
for what that measurement showed, including where the file order does hold and where it does not.
"""
import os
import pathlib
import re

from tools import paths
from tools.ck3 import guimap, savegame

# Where each database lives, and how deep its entries sit. Since 1.20.0.2 a faith is a top-level key
# in `religion/faith_types`; before that it hung inside a religion under `faiths`, and mods written for
# 1.19 still do it that way, so both places are read. Measured 1 October 2026: 103 faiths in the game's
# own `faith_types`, none left inside a vanilla religion, 97 inside the religions of RICE. Whether 1.20
# still loads that old form, and in which order it takes the two folders, only the running game says
# (`numbering.keys`). `common\religion` holds no `religions` folder at all.
PLACES = {
    'culture': (('culture/cultures', ()),),
    'faith': (('religion/faith_types', ()), ('religion/religion_types', ('faiths',))),
    'religion': (('religion/religion_types', ()),),
    'rite': (('religion/rite_types', ()),),
    'trait': (('traits', ()),),
    'government': (('governments', ()),),
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
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for row in reversed(found):
        if row[1] not in seen:
            seen.add(row[1])
            out.append(row)
    return list(reversed(out))


def entries(kind: str) -> list[tuple[str, str, str]]:
    """The keys of one database in the order the files give them, as (key, layer, file).

    Order is kept and never sorted, because the only orderings worth testing against the game are
    the ones the files actually produce.
    """
    out: list[tuple[str, str, str]] = []
    for branch, inside in PLACES[kind]:
        for layer, virtual, full in files(branch):
            nodes = guimap.parse(pathlib.Path(full).read_text(encoding='utf-8-sig', errors='replace'))
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
    text = savegame.unpack(savegame.newest_readable_save())
    print(f"{'database'!s:<12} {'keys'!s:>6} {'named'!s:>6} {'files'!s:>6} {'numbered'!s:>8} {'file order agrees'}")
    for kind, layers in PLACES.items():
        rows = entries(kind)
        keys = [k for k, _, _ in rows]
        names = named(kind, localization)
        try:
            numbers = numbering(kind, text)
        except KeyError:
            numbers = {}
        agree = sum(1 for n, key in numbers.items() if n < len(keys) and keys[n] == key)
        print(f'{kind:<12} {len(keys):6d} {len(names):6d} {sum(len(files(b)) for b, _ in layers):6d} {len(numbers):8d} {agree}')


FAITH_ROW = re.compile(r'(\d+)=\{\s*faith_type=\w+\s+tag="([^"]+)"')
CULTURE_ROW = re.compile(r'\n\t\t(\d+)=\{\n\t\t\tculture_template="([^"]+)"')


def numbering(kind: str, text: str | None = None) -> dict[int, str]:
    """Number -> key, taken from the save rather than guessed from the file order.

    **The engine's numbering is not one rule.** Measured 27 August 2026 against the save of
    1067-11-23: the 463 cultures come out in exactly the order the files give them, all 463 of
    them. The 237 faiths do not - they are grouped per religion, and only fall into place, all 237,
    once the religions are taken in the engine's own order, which is neither the file order (36 of
    94) nor alphabetical (1 of 94). The 342 traits agree to number 300 and then diverge where the
    mods add theirs, and no mod order tried so far explains it.

    So the numbering is read here and not derived. A save is written by the engine, it carries all
    three lists, and it needs no running game - which makes it a better source than a rule that
    holds for one database and not the next.
    """
    text = text if text is not None else savegame.unpack(savegame.newest_readable_save())
    if kind == 'culture':
        return {int(n): key for n, key in CULTURE_ROW.findall(text)}
    if kind == 'trait':
        return dict(enumerate((savegame.block(text, 'traits_lookup') or '').split()))
    if kind in ('faith', 'religion'):
        block = savegame.block(text, 'religion') or ''
        inner = 'religions' if kind == 'religion' else 'faiths'
        at = block.find(f'\n\t{inner}={{')
        rows = savegame.block(block[at:], inner) if at >= 0 else None
        if rows is None:
            raise SystemExit(f'the save has no {inner} block under religion, so the {kind} numbering '
                             'cannot be read from it')
        pattern = (FAITH_ROW if kind == 'faith'
                   else re.compile(r'(\d+)=\{\s*religion_type=\w+\s+tag="([^"]+)"'))
        return {int(n): key for n, key in pattern.findall(rows)}
    raise KeyError(f'no numbering known for {kind!r}')


if __name__ == '__main__':
    main()
