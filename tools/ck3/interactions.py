r"""Who has which interaction switched on, read off the game's own menu, per character.

Usage:
    python -m tools.ck3.interactions <pid> <source>:<key>[:<step>] ...

A source is a window, the key that opens it, and a press inside it such as a tab:
`character_window:F1:CharacterWindow.SetTab('subjects')`. In each, every portrait that carries
`DefaultOnCharacterRightClick` is right clicked in turn, from one alignment, and of every menu that
comes up every row is read with its state byte, 0 on and 6 off (measured 29 October 2026), also
the rows in the flyout that each expander outside the debug categories opens beside the menu, the
grey "More..." as well as "2 more...". The player's own menu is written as "This is you". The
first source that shows a character wins.
Writes `reports\interactions.json`: per stand (the player's name) and character, the source, the
interactions on and off as `category/interaction`, the ones behind their category's expander - a
step by hand presses that first, `InteractionItem.OnClick@<category>>more` - and the categories
whose expander a click could not reach.

Why it exists: an interaction window opens from the menu of a character for whom the interaction is
valid, and which character that is per stand only the game says. On Ghur played one window of
twelve was open, the court position (29 October 2026).
"""
import json
import os
import pathlib
import re
import sys
import time
from typing import TypedDict

from tools import paths, terminal
from tools.ck3 import (
    channel,
    guimap,
    harvest,
    model,
    onscreen,
    openers,
    pairing,
    widgettree,
    windowmap,
)

MENU = 'character_interaction_menu_window'
RIGHT = openers.Goal('right', 'DefaultOnCharacterRightClick')
ITEM = openers.Goal('call', 'InteractionItem.OnClick')
EXPANDER = re.compile(r'^(\d+ more|More)\.\.\.$')
OUT = os.path.join(paths.REPORTS, 'interactions.json')


class Character(TypedDict):
    """One character's menu as this round read it."""
    source: str
    on: list[str]
    off: list[str]
    behind_expander: list[str]
    not_expanded: list[str]


def clean(text: str | None) -> str:
    return ' '.join(widgettree.strip_markup(text or '').split())


def category_of(record: pairing.Record, address: int) -> str | None:
    """The category a row of the menu stands in: the name in the nearest group above it that holds
    exactly one, six levels up in the harvested menu. None for a row of the flyout an expander
    opens beside the menu (`more_interactions_...`), whose nearest group with a name is the whole
    menu: that row belongs to the category whose expander opened it, and the flyout is why only
    one opens at a time (measured 29 October 2026). Sorting by height put rows under the wrong
    category, and so did the first name of the whole menu."""
    by_address = {int(w['address'], 16): w for w in record['tree']}
    walk = int(by_address[address]['parent'], 16)
    while walk in by_address:
        names = [clean(by_address[a]['text']) for a in openers.below(record, walk)
                 if by_address[a]['name'] == 'category_name' and clean(by_address[a]['text'])]
        if names:
            return names[0] if len(names) == 1 else None
        walk = int(by_address[walk]['parent'], 16)
    raise SystemExit(f'row {address:x} of the menu stands under no category')


def rows(record: pairing.Record) -> tuple[str, dict[int, tuple[str | None, str, int | None]]]:
    """The character the menu stands open for, and every drawn row: address -> (category or None in
    the flyout, text, state byte). The name is the heading that is drawn: on the player's own menu
    that is `character_name_me`, "This is you", while `character_name` stays built, hidden, with the
    name of the menu before it (measured 29 October 2026 on Saru)."""
    by_address = {w['address']: w for w in record['tree']}
    name = next(clean(w['text']) for w in record['tree']
                if w['name'] in ('character_name', 'character_name_me') and w['text']
                and onscreen.shown_in_record(w, by_address))
    out: dict[int, tuple[str | None, str, int | None]] = {}
    for widget in record['tree']:
        if widget['name'] != 'interaction_button' or not onscreen.shown_in_record(widget, by_address):
            continue
        address = int(widget['address'], 16)
        under = openers.below(record, address)
        text = ' '.join(clean(w['text']) for w in record['tree'] if int(w['address'], 16) in under and w['text'])
        out[address] = (category_of(record, address), text, widget['state'])
    return name, out


def read_menu(game: windowmap.Game, tables: guimap.Tables) -> Character:
    """Every row of the menu standing open. **One category is expanded at a time:** pressing a
    second expander shut the first (29 October 2026), so each is pressed and read in turn."""
    found: dict[str, tuple[str, int | None, bool]] = {}
    pressed: set[str] = set()
    expanders: set[str] = set()
    flyout = ''
    while True:
        spots, record, acting, _, _, _ = openers.spots_for_goal(game, game.pid, MENU, ITEM, tables)
        _, read = rows(record)
        here = {a: (c if c is not None else flyout, t, s) for a, (c, t, s) in read.items()}
        for category, text, state in here.values():
            if not category:
                raise SystemExit(f'{text} stands in a flyout no expander opened')
            if 'DEBUG' in category:
                continue
            if EXPANDER.match(text):
                expanders.add(category)
            else:
                found.setdefault(f'{category}/{text}', (category, state, bool(pressed)))
        buttons = openers.clickable_map(record, acting)
        chosen = None
        for spot in spots:
            if spot['address'] not in here or spot['why_not'] is not None:
                continue
            category, text, _ = here[spot['address']]
            if EXPANDER.match(text) and 'DEBUG' not in category and category not in pressed:
                point = openers.reachable_point(buttons, spot['address'], spot['rect'])
                if point is not None:
                    chosen = (spot, point, category)
                    break
        if chosen is None:
            return {'source': '', 'on': sorted(k for k, v in found.items() if v[1] == 0),
                    'off': sorted(k for k, v in found.items() if v[1] != 0),
                    'behind_expander': sorted(k for k, v in found.items() if v[2]),
                    'not_expanded': sorted(expanders - pressed)}
        spot, point, category = chosen
        pressed.add(category)
        flyout = category
        refused = openers.press_spot(game, ITEM, spot, point)
        if refused is not None:
            raise SystemExit(f'the expander of {category}: {refused}')
        time.sleep(0.8)


def menu_shown(nodes: widgettree.Nodes, menus: list[int], shown: bool, limit: float) -> bool:
    """Wait until the menu is drawn, or gone. It stands built before the click and was drawn
    0.02 to 0.05 seconds after it, so its state byte is read rather than the tree walked."""
    start = time.perf_counter()
    while time.perf_counter() - start < limit:
        if bool(onscreen.shown(nodes, menus)) == shown:
            return True
        time.sleep(0.03)
    return False


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    pid = int(sys.argv[1])
    game = windowmap.Game(pid)
    openers.game_classes = game.window_classes
    if not harvest.paused(game):
        raise SystemExit('the clock is running: pause the game first')
    _, player_name = model.player(pid)
    baseline = game.bare()
    tables = guimap.tables()
    seen: dict[str, Character] = {}
    for argument in sys.argv[2:]:
        source, key, *step = argument.split(':', 2)
        nodes, _ = harvest.open_window(game, source, windowmap.pressed(key), baseline)
        if nodes is None:
            raise SystemExit(f'{source} did not open along {key}')
        if step:
            why = openers.press_toward(game, source, openers.Goal('call', step[0]), tables)[2]
            if why is not None:
                raise SystemExit(f'{step[0]} in {source}: {why}')
            time.sleep(1.4)
        menus = [a for a, k in nodes.items() if k[6] == MENU and k[0] in game.window_classes]
        _, reachable, _ = openers.reachable_spots(game, source, RIGHT, tables)
        print(f'{argument}: {len(reachable)} portraits a right click reaches')
        for spot, point in reachable:
            openers.press_spot(game, RIGHT, spot, point)
            if not menu_shown(nodes, menus, True, 1.0):
                continue
            name, _ = rows(openers.live_record(game, pid, MENU)[0])
            if name not in seen:
                seen[name] = {**read_menu(game, tables), 'source': argument}
                print(f"   {name}: on {'; '.join(seen[name]['on'])}")
            channel.ask('sendkey 27')
            if not menu_shown(nodes, menus, False, 3.0):
                raise SystemExit('the menu did not shut on Escape')
        if not harvest.close_window(game, {'click': True}, baseline):
            raise SystemExit('the state did not come back')
    report = json.loads(pathlib.Path(OUT).read_text(encoding='utf-8')) if os.path.exists(OUT) else {}
    report[player_name] = {**report.get(player_name, {}), **seen}
    pathlib.Path(OUT).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(seen)} characters written to {OUT} under {player_name}')


if __name__ == '__main__':
    terminal.utf8()
    main()
