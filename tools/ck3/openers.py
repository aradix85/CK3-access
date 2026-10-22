r"""Which button opens which window? Clicks them and writes `reports\openers.json`.

**This cannot be read off disk, and that is measured, not assumed.** The gui files say which *view*
an `onclick` opens - `OpenGameViewData('my_realm')` - but nothing on disk binds a view to a window.
The nine view names whose window we already knew appear in the 515 files only as texture paths,
widget names and tooltip names, never as a declaration. That binding lives in the engine, so the
only honest way to it is to press the button and see what gets drawn.

**Only calls that do nothing but open a view are pressed.** A button can carry any code at all -
`ExecuteConsoleCommand`, a decision, an interaction - so the onclick has to be exactly one
Open/ToggleGameViewData call and nothing else before this will touch it. That rule is mechanical
rather than a list of dangerous-looking names, and it is what makes an unattended round safe. The
one exception is a button whose `shortcut` is the name of a window: it is pressed on that name, and
a click fires every onclick it has (`fires_for`).

**Four stop conditions, all measurable:** too little free memory, a channel that stops answering,
a clock that starts running, and a state that does not come back. The last one matters most - if a
click leaves something standing, every later measurement is contaminated.

Two traps that cost time on 25 August 2026, both worth keeping in mind when reading this:
Escape opens the pause menu when nothing is open, so it is only pressed when a click really opened
something; and a widget name can occur more than once in the tree. That second one used to mean
the row was skipped. It no longer does: the copies are filtered down to the ones really drawn, and
only what is left ambiguous after that is skipped, with both counts said out loud.

Usage:  python -m tools.ck3.openers <pid> [--beside | <button> <button> ...]
        python -m tools.ck3.openers <pid> --chain <window> <target>

The second form is one chain step by hand: in a window that is already open, find what brings the
target up, press it, and say what opened.

With button names, or with `--beside`, it is a trial: only those buttons, or all of them, and the
result goes beside the map into the scratch folder instead of over `reports\openers.json`. A round
on another state than the one the map was measured on is a trial by nature - on a nomadic ruler the
HUD is not the same, and writing over the map would replace one state's measurements by another's.
Runs without -debug_mode: the console is shut only when there is one.
"""
import json
import os
import pathlib
import re
import sys
import time
from typing import NotRequired, TypedDict

from tools import paths, terminal
from tools.ck3 import (
    channel,
    guimap,
    harvest,
    onscreen,
    pairing,
    widgettree,
    windowmap,
)
from tools.ck3.harvest import FREE_MEMORY_FLOOR, drawn_one, free_memory, game_date, paused

OUT = os.path.join(paths.REPORTS, 'openers.json')
USAGE = ('usage: python -m tools.ck3.openers <pid> [--beside | <button> <button> ...], '
         'or <pid> --chain <window> <target>')
ONLY_A_VIEW = re.compile(r"^\[\s*(?:Open|Toggle)GameView(?:Data)?\s*\(\s*'([^']+)'[^\[\]]*\)\s*\]$")
SETTLE = 1.8
# The window classes of this run, set by whoever starts one; unset, the first read of it breaks.
game_classes: set[int]


class Button(TypedDict):
    """A widget that opens a window when pressed, as `buttons_on_disk` finds it, and what a round
    adds once it pressed it: where, what opened, from where, whether the state came back - or why
    it was not pressed. One row of `reports\\openers.json`."""
    via: str
    target: str
    widget: str
    file: str
    under: NotRequired[bool]
    point: NotRequired[list[int]]
    box: NotRequired[list[int]]
    reason: NotRequired[str | None]
    opens: NotRequired[list[str] | None]
    found_in: NotRequired[str]
    state_returned: NotRequired[str]


class _Block(TypedDict):
    """A brace block on its way through `buttons_on_disk`."""
    name: str | None
    views: list[str | None]
    shortcut: str | None


# What has to happen before a window is drawn: ('view', name, None), ('variable', name, value) with
# None for a value when the variable only has to exist, or ('state', expression, window) when the
# window's `visible` is a data function that a toggle button declares as its `down`.
Goal = tuple[str, str, str | None]


class ChainRoute(TypedDict):
    """A window, or a view without a window name, that pressing inside another window brings up."""
    target: str | None
    sources: list[str]
    goal: Goal
    view: str | None


# A widget of an open window that the files say reaches a goal, with why it cannot be pressed.
Spot = TypedDict('Spot', {
    'address': int, 'rect': list[float], 'class': str | None, 'name': str,
    'also_does': list[str], 'why_not': str | None})

# A button that can take a click: its draw order, its rectangle on screen, and the widget.
Clickable = tuple[tuple[int, ...], float, float, float, float, pairing.Harvested]


def _opens(block: _Block, windows: set[str]) -> tuple[str, str] | None:
    """(how, window) when pressing this block opens a window: its one onclick only opens a view,
    or its shortcut is the name of a window. None when it does neither."""
    view = block['views'][0] if len(block['views']) == 1 else None
    if view:
        return 'onclick', view
    shortcut = block['shortcut']
    if shortcut is not None and shortcut in windows:
        return 'shortcut', shortcut
    return None


def buttons_on_disk() -> list[Button]:
    """Every widget that opens a window when pressed, with how it does it.

    **Two mechanisms, and looking at only one throws away the good half.** A button either carries
    `onclick = [OpenGameViewData('x')]`, or it carries `shortcut = "x"` and opens through the key
    binding of that name. The main tabs - council, court, decisions, factions, intrigue, military,
    my realm, activities - carry both, inside a `blockoverride` of their template, and a first round
    that read only the widget's own onclick credited them with a call from a neighbouring block.

    **The name sits one level above the trigger, with a `blockoverride` in between.** That is the
    engine's templating: a widget names itself and then fills in a named slot of its template, and
    the slot is not a child widget. Measured 25 August 2026 in `hud.gui`, where every main tab looks
    like this:

        widget_hud_main_tab = {
            name = "tab_my_realm_tutorial_uses_this"
            blockoverride "maintab_button"
            {
                onclick = "[ToggleGameView('my_realm')]"
                shortcut = "my_realm_window"
            }
        }

    So a trigger bubbles up through `blockoverride` blocks and through nothing else. Requiring the
    same block loses all eight main tabs; allowing the nearest named ancestor hangs a call on the
    container around the button, and the middle of a container is not the button - nine clicks of
    the first round landed on the portrait and opened `character_window`, and one landed on the
    speed bar and started the clock. That last one also defeated the rule that only view-opening
    calls get pressed, because `timeline_widget` had inherited such a call from a child.


    A shortcut is only accepted when its name is a window in `reports\\windows.json`. Most of the
    905 bindings are actions inside a window rather than openers, and pressing those unattended is
    how a round changes the game instead of measuring it.

    The files are read the way `guimap` reads them, as the engine loads them, so a block is a block
    whatever the lines look like, and a block whose name comes after its trigger is read whole.

    **A trigger whose name sits one level up is taken as well, and answered for by the namebearer.**
    310 blocks carry a call while carrying no name of their own but hanging directly under one that
    does; of those, 27 would pass the test above if the namebearer answered for them (counted with
    the line reader this replaced, which missed one row: a name written without quotes). They are only
    added where the name is still free, so a widget that opens a view itself always wins - the
    child is settled before its parent, and without that rule it would shadow the parent's own row.
    """
    windows = set(json.loads(pathlib.Path(windowmap.OUT).read_text(encoding='utf-8'))['windows'])
    found: dict[str, Button] = {}
    beneath: dict[str, Button] = {}
    for _layer, _virtual, path in guimap.files():
        _settle({'key': None, 'arg': None, 'value': None, 'body': guimap.read(path)},
                 os.path.basename(path), windows, found, beneath)
    for widget, row in beneath.items():
        found.setdefault(widget, row)
    return sorted(found.values(), key=lambda row: row['widget'])


def _settle(entry: guimap.Entry, file: str, windows: set[str], found: dict[str, Button],
            beneath: dict[str, Button]) -> _Block:
    """One block, its children settled first: each child that opens a window becomes a row under its
    own name or its parent's, and a nameless `blockoverride` carrying a call hands it upwards."""
    block: _Block = {'name': None, 'views': [], 'shortcut': None}
    body = entry['body'] or []
    for item in body:
        if item['key'] == 'name':
            block['name'] = item['value']
        elif item['key'] == 'shortcut':
            block['shortcut'] = item['value']
        elif (item['key'] or '').lower() == 'onclick':
            only = ONLY_A_VIEW.match((item['value'] or '').strip())
            block['views'].append(only.group(1) if only else None)
    for item in body:
        if item['body'] is None:
            continue
        inner = _settle(item, file, windows, found, beneath)
        if item['key'] == 'blockoverride' and not inner['name'] and (inner['views'] or inner['shortcut']):
            block['views'] += inner['views']
            block['shortcut'] = block['shortcut'] or inner['shortcut']
            continue
        opens = _opens(inner, windows)
        if opens and inner['name']:
            found.setdefault(inner['name'], {'via': opens[0], 'target': opens[1],
                                             'widget': inner['name'], 'file': file})
        elif opens and block['name']:
            beneath.setdefault(block['name'], {'via': opens[0], 'target': opens[1],
                                               'widget': block['name'], 'file': file, 'under': True})
    return block


def live_record(game: windowmap.Game, pid: int, window: str, address: int | None = None,
                nodes: widgettree.Nodes | None = None) -> tuple[pairing.Record, widgettree.Nodes, onscreen.Scales,
                                                             dict[int, str | None]]:
    """The widgets of the window that is drawn right now, in the shape the harvest writes them and
    the pairing reads them.

    The chain cannot use a harvested record: the buttons inside a window sit at addresses of this
    moment, and half of them are rows built from data that was not there when the harvest ran.

    **Hand in the address when you already know which object you mean.** A name is not unique among
    drawn windows: two events stack, both called `character_event`, and `drawn_one` then refuses
    rather than guess - which is right, and leaves the caller stuck if it threw away what it knew.
    The draw order says which is on top, so a caller that worked that out passes the address.

    **Hand in the tree as well when you already have one.** A caller that picked the window out of
    the drawn set has just walked it; walking it again costs seconds and cannot see anything new.
    """
    nodes = nodes if nodes is not None else game.tree()
    windows = [a for a, k in nodes.items() if k[0] in game_classes]
    if address is None:
        named = [a for a in windows if nodes[a][6] == window]
        if not named:
            raise SystemExit(f'{window} is not in the tree at all')
        address = drawn_one(nodes, named, window)
    family = harvest.subtree(nodes, address)
    addresses = [a for a, _, _ in family]
    # **Ask the scales for this window, not for the whole tree.** They come back four hundred
    # addresses per channel question, so over eighty-seven thousand nodes that is two hundred
    # questions where two will do - and on a keystroke that was most of the wait. What
    # `screen_pos` and `is_clipped` walk is this subtree plus the chain from the window up to the
    # root, so that is what is asked for, and the whole chain: a scale that was never asked for
    # stops `screen_pos` with a KeyError.
    needed = set(addresses)
    walk = address
    while walk in nodes:
        needed.add(walk)
        walk = nodes[walk][5]
    scales = onscreen.scales_for(needed)
    classes = widgettree.class_map(pid, {a: nodes[a][0] for a in needed})
    flags = onscreen.flags_for(addresses)      # every widget: it says drawn and it says usable
    alphas = onscreen.alphas_for(addresses)
    tree = [harvest.widget_record(nodes, a, d, i, scales, classes, flags, alphas)
            for a, d, i in family]
    return {'tree': tree}, nodes, scales, classes


CONDITION = re.compile(r"GetVariableSystem\.(HasValue|Exists)\(\s*'([^']+)'(?:\s*,\s*'([^']*)')?")
SETS = re.compile(r"GetVariableSystem\.(Set|Toggle|Clear)\(\s*'([^']+)'(?:\s*,\s*'([^']*)')?")
VIEW_CALL = re.compile(r"(?:Open|Toggle)GameView(?:Data)?\s*\(\s*'([^']+)'")


def goal_of(target: str, tables: guimap.Tables) -> Goal:
    """What has to happen before `target` is drawn: a view opens, a variable is set, or a state
    a button toggles comes on.

    Read from the target's own `visible` line, the last one after inheritance
    (`guimap.window_attributes`), because that is where the game states its own condition, and
    both forms occur: `houses_list` waits on a variable holding a value, `knight_permissions` on
    one merely existing. A target without such a condition is taken to be a view that some button
    opens, which is what every chain step before 31 August 2026 was.

    **A data function is the third form**, and the button that reaches it says so: the character
    filter windows wait on `[CharacterSelectionList.FiltersShown]`, and the button `filters` in
    `shared/lists.gui` declares exactly that as its `down` and toggles it with its click (read
    22 October 2026; pressing it on Saru drew `court_character_filter_window`). Such a goal still
    takes a view call carrying the window's name, as before.
    """
    visible = [value for key, value in guimap.window_attributes(target, tables)
               if key == 'visible' and value]
    if not visible:
        return ('view', target, None)
    found = CONDITION.search(visible[-1])
    if found:
        return ('variable', found.group(2), found.group(3) or None)
    return ('state', bare(visible[-1]), target)


def bare(expression: str) -> str:
    """An expression without its whitespace, so that two spellings of one condition compare equal."""
    return re.sub(r'\s+', '', expression)


def toggles(node: guimap.Node, goal: Goal) -> bool:
    """Is this widget the button whose `down` state is the condition the goal waits on?"""
    down = guimap.attribute(node, 'down')
    return goal[0] == 'state' and down is not None and bare(down) == goal[1]


def reaches(value: str, goal: Goal) -> bool:
    """Does this onclick reach the goal? Setting a variable counts, clearing it does not.

    The trap this exists for is a twin: next to the button that sets `dynasty_view_expand` to
    `houses` sits a nameless button with the same text and tooltip that sets it back to `none`.
    They differ only in their visibility condition, so a rule that matched the variable name alone
    would offer both and press the wrong one half the time.
    """
    if goal[0] in ('view', 'state'):
        found = VIEW_CALL.search(value)
        return bool(found and found.group(1) == (goal[1] if goal[0] == 'view' else goal[2]))
    for how, name, held in SETS.findall(value):
        if name != goal[1] or how == 'Clear':
            continue
        if goal[2] is None and how in ('Set', 'Toggle'):
            return True
        if goal[2] is not None and how == 'Set' and held == goal[2]:
            return True
    return False


def fires_for(source: guimap.Node | None, goal: Goal) -> tuple[list[str], list[str]]:
    """Every call this disk block fires, split into the ones that reach `goal` and the rest.

    **A click and a shortcut both fire every onclick of a block, in order.** Measured 21 October
    2026 on 1.20.1.1 with `onscreen.shown` and the screen as witnesses: a click on "Go to Capital"
    moved the camera and folded the menu it sits in, its two calls; the shortcuts L and Alt+S each
    did both of theirs, while a shortcut with one call left the menu standing. The rule that only
    the last one counts was read off clicks made while only a state byte of zero counted as drawn,
    and the holding view it was about carries 0x20 when it is open. The rest is reported beside
    the call that reaches the goal, because it can undo it: the domicile window's move button opens
    the planner and then closes the domicile window.

    **The accept test of `buttons_on_disk` is deliberately not used here, and that is the point of
    this route.** That one takes a widget only when its onclick is a view-opening call and nothing
    else, which is right for an unattended round over a bare screen. Inside a chain the window is
    already open, the target is known and the state is put back afterwards, so a second call is
    something to report rather than a reason to skip.
    """
    if source is None:
        return [], []
    wanted: list[str] = []
    others: list[str] = []
    toggle = toggles(source, goal)
    for key, value in source['attrs']:
        if key not in ('onclick', 'onrightclick') or not value:
            continue
        if key == 'onclick' and (toggle or reaches(value, goal)):
            wanted.append(value)
        else:
            others.append(f'{key}: {value}')
    return wanted, others


def chain_routes(start: set[str], tables: guimap.Tables) -> list[ChainRoute]:
    """Which windows can be reached by acting inside a window a player can already open. Disk only.

    Every window in `start` is expanded, and every onclick of each block - a click fires them all
    (`fires_for`) - is asked whether it reaches the goal of another window (`goal_of`, `reaches`). A
    call that opens a view whose name is no window name comes back as well, without a target: which
    window the engine puts behind such a view is not on disk, so pressing it is the measurement.

    One row per target or view, with every source that offers it, in sorted order: a call on disk
    can sit in a row the live window does not build, so the first source is not always the one
    that works - `culture_window` from the character finder was the case.

    **A state is offered only for a target nested in the source.** One data function stands for
    the filters of every character list, so a toggle reaches the filter window of its own window
    and no other: on Saru the button in the court window drew the court's own filter window.
    """
    table, local, known, _root = tables
    goals = {w: goal_of(w, tables) for w in known}
    found: dict[str, ChainRoute] = {}
    for source in sorted(start):
        tree = guimap.window(source, table, local, known)
        nodes: list[guimap.Node] = []
        stack = [tree]
        while stack:
            node = stack.pop()
            stack.extend(node['children'])
            nodes.append(node)
        inside = {guimap.attribute(node, 'name') for node in nodes} & known.keys()
        here = {target: goal for target, goal in goals.items() if goal[0] != 'state' or target in inside}
        for node in nodes:
            for key, value in node['attrs']:
                if key != 'onclick' or not value:
                    continue
                _offer(found, source, node, value, here, start, known)
    return sorted(found.values(), key=lambda row: (row['view'] or '', row['target'] or ''))


def _offer(found: dict[str, ChainRoute], source: str, node: guimap.Node, call: str,
           goals: dict[str, Goal], start: set[str], known: guimap.Known) -> None:
    """Every target and every unnamed view this one call of `node` brings up from `source`."""
    for target, goal in goals.items():
        if target not in start and (toggles(node, goal) or reaches(call, goal)):
            row = found.setdefault(target, {'target': target, 'sources': [], 'goal': goal,
                                            'view': None})
            if source not in row['sources']:
                row['sources'].append(source)
    for view in VIEW_CALL.findall(call):
        if view not in known:
            row = found.setdefault(view, {'target': None, 'sources': [],
                                          'goal': ('view', view, None), 'view': view})
            if source not in row['sources']:
                row['sources'].append(source)


def draw_order(record: pairing.Record) -> dict[str, tuple[int, ...]]:
    """Address -> its path of sibling numbers from the window down, which is the drawing order.

    The same rule that decides which of a stack of event windows lies on top decides which of two
    overlapping buttons gets a click: siblings are drawn in list order, so the larger path is drawn
    later and lies above. `index` is written into every harvest record for exactly this, so it
    cannot be lost by sorting.
    """
    by_address = {w['address']: w for w in record['tree']}
    order: dict[str, tuple[int, ...]] = {}

    def path_of(address: str) -> tuple[int, ...]:
        if address in order:
            return order[address]
        widget = by_address.get(address)
        if widget is None or widget['parent'] not in by_address:
            order[address] = (widget['index'],) if widget else ()
        else:
            order[address] = path_of(widget['parent']) + (widget['index'],)
        return order[address]

    for widget in record['tree']:
        path_of(widget['address'])
    return order


def clickable_map(record: pairing.Record, acting: set[str]) -> list[Clickable]:
    """The buttons of a window that can handle a click, with their draw order.

    **A button without an action of its own passes the click on**, so it does not belong here.
    Measured 30 August 2026 on the ledger, ten cases out of ten: every one of the category tabs is
    covered completely by a child called `tab_icon_frame_texture` that carries no onclick at all,
    and clicking the middle of that child switched the category every time. An earlier round
    concluded the opposite from a single case, and that case was rotten - the row it pressed sat in
    the pinned list, which was empty, so its call had no province behind it and could not have done
    anything whatever caught the click.

    `acting` is the set of addresses whose gui block carries an onclick.

    **A widget that is not drawn takes no clicks either, and geometry alone will not tell you.**
    The ledger keeps all eleven of its categories in one tree, laid out on top of each other at the
    same place; ten of them are switched off rather than moved away or clipped, by alpha on 1.19
    and by the state byte on 1.20. Counting those made every row of the category that *is* on show
    look covered - the province pin came out as unreachable under six rows of categories nobody
    could see. Drawn is `onscreen.shown_in_record`, over the whole parent chain.
    """
    order = draw_order(record)
    by_address = {widget['address']: widget for widget in record['tree']}
    out: list[Clickable] = []
    for widget in record['tree']:
        kind = widget['class'] or ''
        if 'Button' not in kind and 'Checkbox' not in kind:
            continue
        if widget['address'] not in acting:
            continue
        x, y, width, height = widget['screen_rect']
        if width <= 0 or height <= 0 or widget['clipped']:
            continue
        if not onscreen.shown_in_record(widget, by_address):
            continue
        out.append((order[widget['address']], x, y, width, height, widget))
    out.sort(key=lambda row: row[0])
    return out


def lands_on(buttons: list[Clickable], point: tuple[int, int]) -> pairing.Harvested | None:
    """Which widget handles a click at this point.

    Of two buttons that can act at the same place the later one is drawn on top and gets it; a
    button that cannot act is not in this list at all, because it hands the click on to whatever
    is under it.
    """
    best = None
    for _, x, y, width, height, widget in buttons:
        if x <= point[0] < x + width and y <= point[1] < y + height:
            best = widget
    return best


def reachable_point(buttons: list[Clickable], widget_address: int, rect: list[float]) -> tuple[int, int] | None:
    """A point on this widget that a click really reaches, or None if it is covered everywhere.

    The middle of a widget is the obvious place to click and it is often the wrong one, so this
    walks the rectangle instead of trusting its centre. The step is small because the gaps between
    the buttons a row is tiled with are small.
    """
    step: int = 6
    x, y, width, height = rect
    for offset_y in range(2, int(height) - 1, step):
        for offset_x in range(2, int(width) - 1, step):
            point = (int(x + offset_x), int(y + offset_y))
            top = lands_on(buttons, point)
            if top is not None and int(top['address'], 16) == widget_address:
                return point
    return None


def spots_for_goal(game: windowmap.Game, pid: int, window: str, goal: Goal,
                   tables: guimap.Tables) -> tuple[list[Spot], pairing.Record, set[str], widgettree.Nodes,
                                                          onscreen.Scales, dict[int, str | None]]:
    """Every widget of an open window that the files say reaches `goal`, aligned rather than guessed.

    The trigger for a chain step is usually nameless and usually a row built from data, so it can
    be addressed neither by name nor by eye. What can be addressed is its place: the expansion of
    the gui file and the live tree line up on class and child order, so the block that carries the
    call on disk gets an address and a rectangle from the game. Everything that is left after that
    is a question `on_screen` already answers.
    """
    record, nodes, scales, classes = live_record(game, pid, window)
    table, local, known, root = tables
    out: list[Spot] = []
    acting: set[str] = set()
    for source, built, _ in pairing.pairs(window, table, local, known, root, record=record):
        if source is not None and any(key == 'onclick' and value
                                      for key, value in source['attrs']):
            acting.add(built['address'])
        wanted, others = fires_for(source, goal)
        if not wanted:
            continue
        address = int(built['address'], 16)
        out.append({'address': address, 'rect': built['screen_rect'],
                    'class': built['class'], 'name': built['name'],
                    'also_does': others,
                    'why_not': on_screen(address, nodes, scales, classes)})
    return out, record, acting, nodes, scales, classes


def press_toward(game: windowmap.Game, window: str, goal: Goal,
                 tables: guimap.Tables) -> tuple[list[Spot], Spot | None, str | None]:
    """In `window`, open, press the first widget that reaches `goal` and a click can reach.

    A named one is pressed the way `quit_game.press` presses: the copy on screen, at its middle,
    with scale and class asked of the whole tree. Measured 21 September 2026 on `filters` in the
    ledger: the aligned point opened nothing, and this opened the filter window. A nameless one is
    pressed at a point a click reaches. Returns every widget that reaches the goal, the one pressed
    or None, and why nothing was pressed. The chain round and the step by hand both press here.
    """
    from tools.ck3 import quit_game  # it imports this module
    spots, record, acting, _, _, _ = spots_for_goal(game, game.pid, window, goal, tables)
    buttons = clickable_map(record, acting)
    reachable: list[tuple[Spot, tuple[int, int]]] = []
    for spot in spots:
        if spot['why_not'] is not None:
            continue
        point = reachable_point(buttons, spot['address'], spot['rect'])
        if point is not None:
            reachable.append((spot, point))
            continue
        x, y, w, h = spot['rect']
        top = lands_on(buttons, (int(x + w / 2), int(y + h / 2)))
        spot['why_not'] = 'covered everywhere, at its middle by {}'.format(
            (top['name'] or top['class']) if top else 'nothing readable')
    if not reachable:
        why = sorted({s['why_not'] or '' for s in spots})
        return spots, None, 'nothing in {} can be pressed for it: {}'.format(
            window, ', '.join(why) or 'no live widget carries the call')
    spot, point = reachable[0]
    if spot['name']:
        full = game.tree()
        refused = quit_game.press(full, onscreen.scales_for(list(full)),
                                  widgettree.class_map(game.pid, {a: k[0] for a, k in full.items()}),
                                  spot['name'])
        if refused:
            return spots, None, refused
    else:
        channel.ask(f'mouse {int(point[0])} {int(point[1])}')
    return spots, spot, None


def trigger_spots(row: Button, named: list[int], nodes: widgettree.Nodes) -> list[int]:
    """Where the click for this row could land: the widget itself, or its nameless children.

    A trigger whose name sits one level up cannot be addressed by name at all. The namebearer can
    be, and under it hangs one button per case, each with the same call and its own visibility
    condition - four government types under `tab_government_administration` on 29 August 2026, of
    which three lay beyond the right edge of the drawing area of that day, 1600 wide, while
    carrying alpha above zero. Which one is meant is therefore a question of geometry, and
    `on_screen` already asks it - against the drawing area of this run, not that one.
    """
    if not row.get('under'):
        return named
    return [a for a in nodes if nodes[a][5] in named and not nodes[a][6]]


def on_screen(address: int, nodes: widgettree.Nodes, scales: onscreen.Scales,
              classes: dict[int, str | None]) -> str | None:
    """Why this widget cannot be clicked, or None when it can.

    **Alpha is not the same question as drawn, and that difference nearly cost a stray click.**
    Measured 28 August 2026: all three widgets named `create_faith` pass the alpha and the size
    test from a bare screen, and all three hang inside a window whose flag byte is 0x18 - shut.
    A click at that point does not reach them; it lands on whatever really lies there, which is the
    map. So the nearest window ancestor has to be drawn as well.

    The four cheap tests come first and the channel questions last, because the disambiguation
    below runs this over every widget carrying a name - one of them 225 times: the state byte along
    the chain (0x08 on the widget or any ancestor, the nearest window included, is the game hiding
    it), and then `window_above`, whether a later window lies over the middle.

    **The edges come from the running game, and until 1 September 2026 they did not.** 1600x900
    stood here as a constant. The drawing area became 1920x1200 that day, after which every
    widget past x1600 or y900 was turned down as "off screen" - a sentence that reads like a
    measurement while being an assumption. `load_button` on the front end sits at 845,931 and was
    refused by it. `onscreen.drawing_area` asks Windows once per run instead.
    """
    if not onscreen.is_visible(nodes, address) or onscreen.is_clipped(nodes, address, scales, classes):
        return 'not visible'
    x, y = onscreen.screen_pos(nodes, address, scales)
    width, height = onscreen.screen_size(nodes, address, scales)
    if width <= 0 or height <= 0:
        return 'no size'
    screen_width, screen_height = onscreen.drawing_area()
    if x < 0 or y < 0 or x + width > screen_width or y + height > screen_height:
        return 'off screen'
    # **The game hides a widget with 0x08 in its state byte, on itself or on an ancestor, and leaves
    # alpha up** - a window as much as a button (`onscreen.flags_for`). One question for the chain.
    chain = []
    node = address
    while node in nodes:
        chain.append(node)
        node = nodes[node][5]
    if not onscreen.shown(nodes, [address]):
        return 'hidden by the game'
    above = window_above(address, chain, nodes, scales)
    if above is not None:
        return f'covered by {above}'
    return None


# The drawn windows of one tree that catch clicks, and every widget's place among its siblings,
# worked out once per tree: (which tree, sibling index, windows).
_above: tuple[tuple[int, int], dict[int, int], list[int]] | None = None


def window_above(address: int, chain: list[int], nodes: widgettree.Nodes, scales: onscreen.Scales) -> str | None:
    """A drawn window later in the tree whose rectangle holds this widget's middle, or None.

    **Later in the tree is drawn on top**: measured 21 September 2026 - of two event windows the
    one at path (0, 8, 0), in the layer `top`, caught a click meant for the one at (0, 7, 0) in the
    layer `events` - and the modding wiki says the same of the order in a file.
    **The window's rectangle stands in for what really catches a
    click**, which the wiki gives as: a visible widget that is not `alwaystransparent`, inside its
    window unless that window has `allow_outside`. Asking that of the gui files means aligning the
    window first, seconds per click; the rectangle predicts both measured cases - the full-screen
    event caught the click, and an `alwaystransparent` icon of the other event, lying outside its
    window, let one through. Its two blind spots: a see-through widget inside a window makes this
    refuse a click that would land, and a child outside a window with `allow_outside` that does
    catch is missed. A drawn window that lets the mouse through (0x20) never counts: the planner and
    `layer_window` cover the whole screen that way. The drawn windows and the order are worked out
    once per tree.
    """
    global _above
    key = (id(nodes), len(nodes))
    if _above is None or _above[0] != key:
        siblings: dict[int, int] = {}
        counts: dict[int, int] = {}
        for a, node in nodes.items():
            siblings[a] = counts.get(node[5], 0)
            counts[node[5]] = siblings[a] + 1
        windows = [a for a, node in nodes.items() if node[0] in game_classes]
        catching = [a for a, flag in onscreen.shown(nodes, windows).items()
                    if not flag & onscreen.PASSES_CLICKS]
        _above = (key, siblings, catching)
    _, index, drawn = _above

    def path(a: int) -> tuple[int, ...]:
        out = []
        while a in nodes:
            out.append(index[a])
            a = nodes[a][5]
        return tuple(reversed(out))

    x, y = onscreen.screen_pos(nodes, address, scales)
    width, height = onscreen.screen_size(nodes, address, scales)
    px, py = x + width / 2, y + height / 2
    mine, own = path(address), set(chain)
    for win in drawn:
        if win in own or path(win) <= mine:
            continue
        wx, wy = onscreen.screen_pos(nodes, win, scales)
        ww, wh = onscreen.screen_size(nodes, win, scales)
        if wx <= px < wx + ww and wy <= py < wy + wh:
            return nodes[win][6] or 'a window'
    return None


def press(address: int, nodes: widgettree.Nodes, scales: onscreen.Scales, classes: dict[int, str | None],
          row: Button | None = None) -> str | None:
    """Click the middle of a widget, but only if it is really on screen.

    The point is written into `row` when there is one: a click that lands somewhere else is then
    visible in the result without deriving the whole tree again to find out where it went.
    """
    reason = on_screen(address, nodes, scales, classes)
    if reason:
        return reason
    x, y = onscreen.screen_pos(nodes, address, scales)
    width, height = onscreen.screen_size(nodes, address, scales)
    click_x, click_y = int(x + width / 2), int(y + height / 2)
    if row is not None:
        row['point'] = [click_x, click_y]
        row['box'] = [round(x), round(y), round(width), round(height)]
    channel.ask(f'mouse {int(click_x)} {int(click_y)}')
    return None


def back_to(game: windowmap.Game, target: set[str]) -> bool:
    """Shut whatever opened, until `target` is drawn again.

    Escape only while something beyond `target` is drawn: with nothing more open, Escape opens the
    pause menu, and a window of `target` that a click shut does not come back from it either. This
    used to press on regardless, flipping the pause menu until its tries ran out.
    """
    for _ in range(4):
        drawn = game.state()[2]
        if drawn <= target:
            return drawn == target
        channel.ask('sendkey 27')
        time.sleep(1.5)
    return game.state()[2] == target


def subtree_of(nodes: widgettree.Nodes, window: str) -> set[int]:
    """The addresses under the drawn window object of that name. Every window is built up front,
    so a name with no object at all is a fault.

    Looking inside a window instead of inside the whole tree is what makes phase two work at all.
    Fourteen of the buttons carry a name that more than one widget in the tree has - one of them
    160 times - and from a neutral state there is no way to tell which was meant. Within one open
    window there almost always is exactly one.
    """
    candidates = [a for a, k in nodes.items() if k[6] == window and k[0] in game_classes]
    if not candidates:
        raise SystemExit(f'no window object called {window} in the tree')
    root = drawn_one(nodes, candidates, window)
    children: dict[int, list[int]] = {}
    for address, k in nodes.items():
        children.setdefault(k[5], []).append(address)
    seen: set[int] = set()
    stack = [root]
    while stack:
        address = stack.pop()
        seen.add(address)
        stack.extend(children.get(address, []))
    return seen


def try_button(game: windowmap.Game, row: Button, address: int, nodes: widgettree.Nodes,
               scales: onscreen.Scales, classes: dict[int, str | None], floor: set[str],
               date: str | None, number: int, total: int, where: str,
               fallback: set[str] | None = None) -> str:
    """Press one button, record what opened, and put the state back.

    Escape does not always shut only what the click opened: inside an open window it can close the
    window along with it, so the state comes back to the bare screen rather than to the state the
    click started from. That is not a contaminated measurement, it just means the parent has to be
    opened again - so a fall-back state is accepted and reported. Anything else stops the round,
    because a window left standing makes every measurement after it wrong.
    """
    row['reason'] = press(address, nodes, scales, classes, row)
    if row['reason'] is not None:
        row['opens'] = None
        return 'skipped'
    time.sleep(SETTLE)
    row['opens'] = sorted(game.state()[2] - floor)
    row['found_in'] = where
    landed = 'ok' if back_to(game, floor) else None
    if landed is None and fallback is not None and back_to(game, fallback):
        landed = 'fell back'
    row['state_returned'] = landed or 'stuck'
    print(f"{int(number):3d}/{int(total)} {row['widget']!s:<32} {row['target']!s:<24} {where!s:<18} opened {row['opens'] or 'nothing'}{'' if landed == 'ok' else '  (%s)' % (landed or 'STUCK')}")
    if landed is None:
        raise SystemExit('something stayed open after clicking {}; stopping, because every '
                         'measurement after this one would be contaminated'.format(row['widget']))
    if free_memory() < FREE_MEMORY_FLOOR:
        raise SystemExit(f'free memory {free_memory():.1f} GB is under the floor of {FREE_MEMORY_FLOOR:.1f} GB')
    if game_date(game.tree()) != date:
        raise SystemExit(f'the date moved from {date} to {game_date(game.tree())}: the clock is running')
    return landed


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(USAGE)
    pid = int(sys.argv[1])
    game = windowmap.Game(pid)
    global game_classes
    game_classes = game.window_classes
    if not paused(game):
        raise SystemExit('the clock is running; pause the game first, or the state is not repeatable')
    if game.console_open():
        game.set_console(False)

    rows = buttons_on_disk()
    wanted = [a for a in sys.argv[2:] if not a.startswith('--')]
    trial = bool(wanted) or '--beside' in sys.argv[2:]
    if wanted:
        missing = sorted(set(wanted) - {r['widget'] for r in rows})
        if missing:
            raise SystemExit('not a button on disk that only opens a view: {}'.format(', '.join(missing)))
        rows = [r for r in rows if r['widget'] in wanted]
    target = (os.path.join(paths.WORK, 'openers_trial.json') if trial else OUT)
    baseline = game.bare()
    nodes = game.tree()
    date = game_date(nodes)
    print(f'{len(rows)} buttons on disk open nothing but a view; fields {game.why}, date {date}, free memory {free_memory():.1f} GB')

    by_name: dict[str, list[int]] = {}
    for address, k in nodes.items():
        if k[6]:
            by_name.setdefault(k[6], []).append(address)
    scales = onscreen.scales_for(list(nodes))
    classes = widgettree.class_map(pid, {a: k[0] for a, k in nodes.items()})

    print('\nphase one: what is reachable without opening anything first')
    for number, row in enumerate(rows, 1):
        here = trigger_spots(row, by_name.get(row['widget'], []), nodes)
        if not here:
            row['reason'] = 'not in the tree from a neutral state'
        elif len(here) > 1:
            # A name that several widgets carry is not automatically hopeless: most of those
            # copies sit inside a window that is shut, and one of them is the button on screen.
            # Measured 28 August 2026 over the fourteen ambiguous names: filtering on what is
            # really drawn leaves exactly one for `ledger_window` and `confederation_button`,
            # nothing for eleven others, and for `create_faith` it correctly leaves nothing where
            # alpha alone would have offered a button inside a closed window.
            usable = [a for a in here if on_screen(a, nodes, scales, classes) is None]
            if len(usable) == 1:
                try_button(game, row, usable[0], nodes, scales, classes, baseline, date,
                           number, len(rows), 'the screen')
            else:
                row['reason'] = (f'{len(here)} widgets carry this name and {len(usable)} of them are on screen')
        else:
            try_button(game, row, here[0], nodes, scales, classes, baseline, date,
                       number, len(rows), 'the screen')
        if row.get('opens') is None:
            row['opens'] = None

    doors: dict[str, str] = {}
    for row in rows:
        opens = row.get('opens')
        if opens and len(opens) == 1:
            doors.setdefault(opens[0], row['widget'])
    print(f'\nphase two: {len(doors)} windows can be opened first, then looked inside')

    for window, opener in sorted(doors.items()):
        waiting = [r for r in rows if r['reason'] is not None]
        if not waiting:
            break
        here = [a for a in by_name.get(opener, []) if on_screen(a, nodes, scales, classes) is None]
        if len(here) != 1:
            continue
        if press(here[0], nodes, scales, classes) is not None:
            continue
        time.sleep(SETTLE)
        inside_nodes = game.tree()
        floor = game.state(inside_nodes)[2]
        held = subtree_of(inside_nodes, window)
        inside_scales = onscreen.scales_for(list(inside_nodes))
        inside_classes = widgettree.class_map(pid, {a: k[0] for a, k in inside_nodes.items()})
        found = 0
        for number, row in enumerate(waiting, 1):
            spots = trigger_spots(row, [a for a in held
                                        if inside_nodes[a][6] == row['widget']], inside_nodes)
            if len(spots) > 1:
                spots = [a for a in spots
                         if on_screen(a, inside_nodes, inside_scales, inside_classes) is None]
            if len(spots) != 1:
                continue
            found += 1
            landed = try_button(game, row, spots[0], inside_nodes, inside_scales, inside_classes,
                                floor, date, number, len(waiting), 'in ' + window,
                                fallback=baseline)
            if landed != 'fell back':
                continue
            # Escape took the parent with it, so open it again and read the tree afresh: the
            # addresses of a window are not the same after it has been closed and reopened.
            if press(here[0], nodes, scales, classes) is not None:
                break
            time.sleep(SETTLE)
            inside_nodes = game.tree()
            floor = game.state(inside_nodes)[2]
            held = subtree_of(inside_nodes, window)
            inside_scales = onscreen.scales_for(list(inside_nodes))
            inside_classes = widgettree.class_map(pid, {a: k[0] for a, k in inside_nodes.items()})

        print(f'   {window!s:<28} {int(found)} of the {len(waiting)} still waiting were in it')
        if not back_to(game, baseline):
            raise SystemExit(f'{window} would not close again')

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w', encoding='utf-8') as file:
        json.dump({'measured': time.strftime('%Y-%m-%d %H:%M'), 'game_date': date,
                   'buttons': rows}, file, ensure_ascii=False, indent=1)
    pressed = [r for r in rows if r.get('point')]
    opened = [r for r in pressed if r['opens']]
    agreed = [r for r in opened if any(r['target'] in w or w in r['target'] for w in r['opens'] or ())]
    print(f'\npressed {len(pressed)} of {len(rows)}, of those {len(opened)} opened a window and {len(agreed)} matched the view name')
    print('written to {}{}'.format(target, ' (a trial, beside the map)' if trial else ''))


def chain(pid: int, window: str, target: str) -> None:
    """One chain step by hand: in `window`, already open, find what brings `target` up, press the
    first widget a click can reach, and say what opened. It puts nothing back.

    Stops the moment it cannot say which widget it means, because a click on a wrong guess lands on
    whatever really lies at that point - and inside a window that is nearly always something else
    that opens.
    """
    global game_classes
    game = windowmap.Game(pid)
    game_classes = game.window_classes
    _, _, baseline = game.state()
    if window not in baseline:
        raise SystemExit(f'{window} is not open; open it first, this only does the step inside it')
    tables = guimap.tables()
    goal = goal_of(target, tables)
    if goal[0] == 'view':
        print(f'{target} is reached by opening the view {goal[1]}')
    elif goal[0] == 'state':
        print(f'{target} is reached by the button whose down state is {goal[1]}')
    else:
        print('{} is reached by setting {} to {}'.format(target, goal[1], goal[2] if goal[2] is not None else 'anything'))
    spots, pressed, why = press_toward(game, window, goal, tables)
    print(f'{len(spots)} widgets in {window} carry a call that does that')
    for spot in spots[:12]:
        print(f"   {spot['address']:x} {spot['class']!s:<12} {spot['name'] or '-'!s:<18} rect {spot['rect']} {spot['why_not'] or 'clickable and reachable'}")
        for call in spot['also_does'][:2]:
            print(f'        also: {call[:86]}')
    if pressed is None:
        print(why)
        return
    print(f"pressed {pressed['name'] or pressed['class']} at {pressed['address']:x}")
    for _ in range(6):
        time.sleep(SETTLE)
        _, _, drawn = game.state()
        opened = sorted(drawn - baseline)
        if opened:
            break
    print('opened: %s' % (', '.join(opened) or 'nothing'))


if __name__ == '__main__':
    terminal.utf8()
    if len(sys.argv) > 3 and sys.argv[2] == '--chain':
        chain(int(sys.argv[1]), sys.argv[3], sys.argv[4])
    else:
        main()
