r"""Which button opens which window? Clicks them and writes `reports\openers.json`.

**This cannot be read off disk, and that is measured, not assumed.** The gui files say which *view*
an `onclick` opens - `OpenGameViewData('my_realm')` - but nothing on disk binds a view to a window.
The nine view names whose window we already knew appear in the 515 files only as texture paths,
widget names and tooltip names, never as a declaration. That binding lives in the engine, so the
only honest way to it is to press the button and see what gets drawn.

**Only calls that do nothing but open a view are pressed.** A button can carry any code at all -
`ExecuteConsoleCommand`, a decision, an interaction - so the onclick has to be exactly one
Open/ToggleGameViewData call and nothing else before this will touch it. That rule is mechanical
rather than a list of dangerous-looking names, and it is what makes an unattended round safe.

**Four stop conditions, all measurable:** too little free memory, a channel that stops answering,
a clock that starts running, and a state that does not come back. The last one matters most - if a
click leaves something standing, every later measurement is contaminated.

Two traps that cost time on 25 August 2026, both worth keeping in mind when reading this:
Escape opens the pause menu when nothing is open, so it is only pressed when a click really opened
something; and a widget name can occur more than once in the tree. That second one used to mean
the row was skipped. It no longer does: the copies are filtered down to the ones really drawn, and
only what is left ambiguous after that is skipped, with both counts said out loud.

Usage:  python tools\ck3\openers.py <pid>
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import channel
import derive
import guimap
import paths
import vtablemap
import windowmap
from harvest import free_memory, game_date, paused, drawn_one, FREE_MEMORY_FLOOR

OUT = os.path.join(paths.PROJECT, 'reports', 'openers.json')
ONLY_A_VIEW = re.compile(r"^\[\s*(?:Open|Toggle)GameView(?:Data)?\s*\(\s*'([^']+)'[^\[\]]*\)\s*\]$")
NAME = re.compile(r'\bname\s*=\s*"([^"]+)"')
SHORTCUT = re.compile(r'\bshortcut\s*=\s*"([^"]+)"')
ONCLICK = re.compile(r'\bonclick\s*=\s*(.+)', re.I)
SETTLE = 1.8
game_classes = set()


def buttons_on_disk():
    """Every widget that opens a window when pressed, with how it does it.

    **Two mechanisms, and looking at only one throws away the good half.** A button either carries
    `onclick = [OpenGameViewData('x')]`, or it carries `shortcut = "x"` and opens through the key
    binding of that name. The main tabs - council, court, decisions, factions, intrigue, military,
    my realm, activities - are all of the second kind and have no onclick at all, which is why a
    first round that only read onclicks appeared to confirm them: the call it credited them with
    came from a neighbouring block.

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

    Blocks are followed by counting braces, not by the shape of a line, because a gui file closes a
    block on a line that also carries content. A block whose name comes after its trigger is common,
    so nothing is decided until the block closes.

    **A trigger whose name sits one level up is taken as well, and answered for by the namebearer.**
    310 blocks carry a call while carrying no name of their own but hanging directly under one that
    does; of those, 27 would pass the test above if the namebearer answered for them. They are only
    added where the name is still free, so a widget that opens a view itself always wins - the
    child closes before its parent, and without that rule it would shadow the parent's own row.
    """
    windows = set(json.load(open(os.path.join(paths.PROJECT, 'reports', 'windows.json'),
                                 encoding='utf-8'))['windows'])
    found = {}
    beneath = {}
    for root, _, names in os.walk(paths.GAME):
        for name in sorted(names):
            if not name.endswith('.gui'):
                continue
            stack, last = [], ''
            for line in open(os.path.join(root, name), encoding='utf-8-sig', errors='replace'):
                for piece in re.split(r'([{}])', line.split('#')[0]):
                    if piece == '{':
                        stack.append({'name': None, 'views': [], 'shortcut': None,
                                      'opener': last})
                    elif piece == '}':
                        if not stack:
                            continue
                        block = stack.pop()
                        carries = block['views'] or block['shortcut']
                        if not block['name'] and carries and stack \
                                and block['opener'].startswith('blockoverride'):
                            stack[-1]['views'] += block['views']
                            stack[-1]['shortcut'] = stack[-1]['shortcut'] or block['shortcut']
                            continue
                        row = None
                        if block['name'] and len(block['views']) == 1 and block['views'][0]:
                            row = {'via': 'onclick', 'target': block['views'][0]}
                        elif block['name'] and block['shortcut'] in windows:
                            row = {'via': 'shortcut', 'target': block['shortcut']}
                        if row:
                            row.update({'widget': block['name'], 'file': name})
                            found.setdefault(block['name'], row)
                        elif not block['name'] and stack and stack[-1]['name']:
                            if len(block['views']) == 1 and block['views'][0]:
                                row = {'via': 'onclick', 'target': block['views'][0]}
                            elif block['shortcut'] in windows:
                                row = {'via': 'shortcut', 'target': block['shortcut']}
                            if row:
                                row.update({'widget': stack[-1]['name'], 'file': name,
                                            'under': True})
                                beneath.setdefault(stack[-1]['name'], row)
                    elif stack:
                        if piece.strip():
                            last = piece.strip().splitlines()[-1].strip()
                        named = NAME.search(piece)
                        if named:
                            stack[-1]['name'] = named.group(1)
                        short = SHORTCUT.search(piece)
                        if short:
                            stack[-1]['shortcut'] = short.group(1)
                        click = ONCLICK.search(piece)
                        if click:
                            only = ONLY_A_VIEW.match(click.group(1).strip().strip('"'))
                            stack[-1]['views'].append(only.group(1) if only else None)
                    elif piece.strip():
                        last = piece.strip().splitlines()[-1].strip()
    for widget, row in beneath.items():
        found.setdefault(widget, row)
    return sorted(found.values(), key=lambda row: row['widget'])





def live_record(game, pid, window):
    """The window that is drawn right now, in the shape the harvest writes and the pairing reads.

    The chain cannot use a harvested record: the buttons inside a window sit at addresses of this
    moment, and half of them are rows built from data that was not there when the harvest ran.
    """
    import harvest
    nodes = game.tree()
    windows = [a for a, k in nodes.items() if k[0] in game_classes]
    named = [a for a in windows if nodes[a][6] == window]
    if not named:
        raise SystemExit('%s is not in the tree at all' % window)
    address = drawn_one(named, window)
    family = harvest.subtree(nodes, address)
    addresses = [a for a, _, _ in family]
    scales = derive.scales_for(list(nodes))
    classes = derive.class_map(pid, {a: k[0] for a, k in nodes.items()})
    flags = derive.flags_for([a for a in addresses if a in windows])
    alphas = harvest.alphas_for(addresses)
    tree = [harvest.widget_record(nodes, a, d, i, scales, classes, flags, alphas)
            for a, d, i in family]
    return {'window': window, 'tree': tree}, nodes, scales, classes


CONDITION = re.compile(r"GetVariableSystem\.(HasValue|Exists)\(\s*'([^']+)'(?:\s*,\s*'([^']*)')?")
SETS = re.compile(r"GetVariableSystem\.(Set|Toggle|Clear)\(\s*'([^']+)'(?:\s*,\s*'([^']*)')?")


def goal_of(target, known=None):
    """What has to happen before `target` is drawn: a view opens, or a variable is set.

    Read from the target's own `visible` line, because that is where the game states its own
    condition, and both forms occur: `houses_list` waits on a variable holding a value,
    `knight_permissions` on one merely existing. A target without such a condition is taken to be
    a view that some button opens, which is what every chain step before 31 August 2026 was.
    """
    entry = (known if known is not None else guimap.windows()).get(target, (None, None))[1]
    for item in (entry or {}).get('body', ()):
        if item.get('key') == 'visible' and item.get('value'):
            found = CONDITION.search(item['value'])
            if found:
                return ('variable', found.group(2), found.group(3) or None)
    return ('view', target, None)


def reaches(value, goal):
    """Does this onclick reach the goal? Setting a variable counts, clearing it does not.

    The trap this exists for is a twin: next to the button that sets `dynasty_view_expand` to
    `houses` sits a nameless button with the same text and tooltip that sets it back to `none`.
    They differ only in their visibility condition, so a rule that matched the variable name alone
    would offer both and press the wrong one half the time.
    """
    if goal[0] == 'view':
        found = re.search(r"(?:Open|Toggle)GameView(?:Data)?\s*\(\s*'([^']+)'", value)
        return bool(found and found.group(1) == goal[1])
    for how, name, held in SETS.findall(value):
        if name != goal[1] or how == 'Clear':
            continue
        if goal[2] is None and how in ('Set', 'Toggle'):
            return True
        if goal[2] is not None and how == 'Set' and held == goal[2]:
            return True
    return False


def fires_for(source, goal):
    """The call this disk block really fires, split into the one that reaches `goal` and the rest.

    **A block may write `onclick` twice, and only the last one counts.** That is not a detail: in
    `window_ledger.gui` both orders occur. One row lists the `holding_view` call first and a coat
    of arms handler after it, another lists them the other way round, and the engine keeps the
    later definition - the same last-wins rule that decides which mod redefines a template. Taking
    any occurrence therefore points at rows that cannot open anything, and pressing one is a click
    that lands somewhere and does something else. Measured 30 August 2026: of the 26 ledger rows
    the files hang a `holding_view` call on, pressing one whose call is shadowed opened nothing.

    **The accept test of `buttons_on_disk` is deliberately not used here, and that is the point of
    this route.** That one takes a widget only when its onclick is a view-opening call and nothing
    else, which is right for an unattended round over a bare screen. Inside a chain the window is
    already open, the target is known and the state is put back afterwards, so a second call is
    something to report rather than a reason to skip.
    """
    if source is None:
        return [], []
    last, others = {}, []
    for key, value in source.get('attrs', ()):
        if key not in ('onclick', 'onrightclick') or not value:
            continue
        if key in last:
            others.append('shadowed %s: %s' % (key, last[key]))
        last[key] = value
    wanted = []
    for key, value in last.items():
        if key == 'onclick' and reaches(value, goal):
            wanted.append(value)
        else:
            others.append('%s: %s' % (key, value))
    return wanted, others


def draw_order(record):
    """Address -> its path of sibling numbers from the window down, which is the drawing order.

    The same rule that decides which of a stack of event windows lies on top decides which of two
    overlapping buttons gets a click: siblings are drawn in list order, so the larger path is drawn
    later and lies above. `index` is written into every harvest record for exactly this, so it
    cannot be lost by sorting.
    """
    by_address = {w['address']: w for w in record['tree']}
    paths = {}

    def path_of(address):
        if address in paths:
            return paths[address]
        widget = by_address.get(address)
        if widget is None or widget['parent'] not in by_address:
            paths[address] = (widget['index'],) if widget else ()
        else:
            paths[address] = path_of(widget['parent']) + (widget['index'],)
        return paths[address]

    for widget in record['tree']:
        path_of(widget['address'])
    return paths


def clickable_map(record, acting=None):
    """The buttons of a window that can handle a click, with their draw order.

    **A button without an action of its own passes the click on**, so it does not belong here.
    Measured 30 August 2026 on the ledger, ten cases out of ten: every one of the category tabs is
    covered completely by a child called `tab_icon_frame_texture` that carries no onclick at all,
    and clicking the middle of that child switched the category every time. An earlier round
    concluded the opposite from a single case, and that case was rotten - the row it pressed sat in
    the pinned list, which was empty, so its call had no province behind it and could not have done
    anything whatever caught the click.

    `acting` is the set of addresses whose gui block carries an onclick. Without it every button
    counts, which is the old behaviour and is only right when nothing better is known.

    **A widget that is not drawn takes no clicks either, and geometry alone will not tell you.**
    The ledger keeps all eleven of its categories in one tree, laid out on top of each other at the
    same place; ten of them are switched off by alpha rather than moved away or clipped. Counting
    those made every row of the category that *is* on show look covered - the province pin came out
    as unreachable under six rows of categories nobody could see. Alpha is a property of the whole
    parent chain, so it is multiplied along it, exactly as the harvest does when it decides which
    text boxes the recogniser ought to find.
    """
    paths = draw_order(record)
    by_address = {widget['address']: widget for widget in record['tree']}
    out = []
    for widget in record['tree']:
        kind = widget['class'] or ''
        if 'Button' not in kind and 'Checkbox' not in kind:
            continue
        if acting is not None and widget['address'] not in acting:
            continue
        x, y, width, height = widget['screen_rect']
        if width <= 0 or height <= 0 or widget['clipped']:
            continue
        alpha, node, steps = 1.0, widget, 0
        while node is not None and steps < 40:
            alpha *= node['alpha'] if node['alpha'] is not None else 1.0
            node = by_address.get(node['parent'])
            steps += 1
        if alpha <= 0.0:
            continue
        out.append((paths[widget['address']], x, y, width, height, widget))
    out.sort(key=lambda row: row[0])
    return out


def lands_on(buttons, point):
    """Which widget handles a click at this point.

    Of two buttons that can act at the same place the later one is drawn on top and gets it; a
    button that cannot act is not in this list at all, because it hands the click on to whatever
    is under it.
    """
    best = None
    for path, x, y, width, height, widget in buttons:
        if x <= point[0] < x + width and y <= point[1] < y + height:
            best = widget
    return best


def reachable_point(buttons, widget_address, rect, step=6):
    """A point on this widget that a click really reaches, or None if it is covered everywhere.

    The middle of a widget is the obvious place to click and it is often the wrong one, so this
    walks the rectangle instead of trusting its centre. The step is small because the gaps between
    the buttons a row is tiled with are small.
    """
    x, y, width, height = rect
    for offset_y in range(2, int(height) - 1, step):
        for offset_x in range(2, int(width) - 1, step):
            point = (int(x + offset_x), int(y + offset_y))
            top = lands_on(buttons, point)
            if top is not None and int(top['address'], 16) == widget_address:
                return point
    return None


def gui_tables():
    """The expansion tables, read once. Building them walks 563 files, so a sweep that rebuilds
    them per window spends its time there instead of in the game."""
    import pairing
    rows = guimap.files()
    table, local = guimap.type_table(rows)
    return table, local, guimap.windows(rows), pairing.root_finder(table)


def spots_for_goal(game, pid, window, goal, tables=None):
    """Every widget of an open window that the files say reaches `goal`, aligned rather than guessed.

    The trigger for a chain step is usually nameless and usually a row built from data, so it can
    be addressed neither by name nor by eye. What can be addressed is its place: the expansion of
    the gui file and the live tree line up on class and child order, so the block that carries the
    call on disk gets an address and a rectangle from the game. Everything that is left after that
    is a question `on_screen` already answers.
    """
    import pairing
    record, nodes, scales, classes = live_record(game, pid, window)
    table, local, known, root = tables or gui_tables()
    out, acting = [], set()
    for source, built, _ in pairing.pairs(window, table, local, known, root, record=record):
        if source is not None and any(key == 'onclick' and value
                                      for key, value in source.get('attrs', ())):
            acting.add(built['address'])
        wanted, others = fires_for(source, goal)
        if not wanted:
            continue
        address = int(built['address'], 16)
        out.append({'address': address, 'rect': built['screen_rect'],
                    'class': built['class'], 'name': built['name'],
                    'calls': wanted, 'also_does': others,
                    'why_not': on_screen(address, nodes, scales, classes)})
    return out, record, acting, nodes, scales, classes


def trigger_spots(row, named, nodes):
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


def on_screen(address, nodes, scales, classes):
    """Why this widget cannot be clicked, or None when it can.

    **Alpha is not the same question as drawn, and that difference nearly cost a stray click.**
    Measured 28 August 2026: all three widgets named `create_faith` pass the alpha and the size
    test from a bare screen, and all three hang inside a window whose flag byte is 0x18 - shut.
    A click at that point does not reach them; it lands on whatever really lies there, which is the
    map. So the nearest window ancestor has to be drawn as well.

    The four cheap tests come first and the flag is asked last, because that one is a channel
    question and the disambiguation below runs this over every widget carrying a name - one of
    them 225 times.

    **The edges come from the running game, and until 1 September 2026 they did not.** 1600x900
    stood here as a constant. The drawing area became 1920x1200 that day, after which every
    widget past x1600 or y900 was turned down as "off screen" - a sentence that reads like a
    measurement while being an assumption. `load_button` on the front end sits at 845,931 and was
    refused by it. `derive.drawing_area` asks Windows once per run instead.
    """
    if not derive.is_visible(nodes, address) or derive.is_clipped(nodes, address, scales, classes):
        return 'not visible'
    x, y = derive.screen_pos(nodes, address, scales)
    width, height = derive.screen_size(nodes, address, scales)
    if width <= 0 or height <= 0:
        return 'no size'
    screen_width, screen_height = derive.drawing_area()
    if x < 0 or y < 0 or x + width > screen_width or y + height > screen_height:
        return 'off screen'
    node = nodes[address][5]
    while node in nodes:
        if nodes[node][0] in game_classes:
            if derive.flags_for([node]).get(node, 0xFF) != 0x00:
                return 'its window is not drawn'
            break
        node = nodes[node][5]
    return None


def press(address, nodes, scales, classes, row):
    """Click the middle of a widget, but only if it is really on screen.

    The point is written into the record: a click that lands somewhere else is then visible in the
    result without deriving the whole tree again to find out where it went.
    """
    reason = on_screen(address, nodes, scales, classes)
    if reason:
        return reason
    x, y = derive.screen_pos(nodes, address, scales)
    width, height = derive.screen_size(nodes, address, scales)
    row['point'] = [int(x + width / 2), int(y + height / 2)]
    row['box'] = [round(x), round(y), round(width), round(height)]
    channel.ask('mouse %d %d 1' % tuple(row['point']))
    return None



def back_to(game, baseline, tries=4):
    """Shut whatever opened. Escape only when something is open, or it opens the pause menu."""
    for _ in range(tries):
        if game.state()[2] == baseline:
            return True
        channel.ask('sendkey 27')
        time.sleep(1.5)
    return game.state()[2] == baseline


def subtree_of(nodes, window):
    """The addresses under the drawn window object of that name, or None.

    Looking inside a window instead of inside the whole tree is what makes phase two work at all.
    Fourteen of the buttons carry a name that more than one widget in the tree has - one of them
    160 times - and from a neutral state there is no way to tell which was meant. Within one open
    window there almost always is exactly one.
    """
    candidates = [a for a, k in nodes.items() if k[6] == window and k[0] in game_classes]
    if not candidates:
        return None
    root = drawn_one(candidates, window)
    children = {}
    for address, k in nodes.items():
        children.setdefault(k[5], []).append(address)
    seen, stack = set(), [root]
    while stack:
        address = stack.pop()
        seen.add(address)
        stack.extend(children.get(address, []))
    return seen


def try_button(game, row, address, nodes, scales, classes, floor, date, number, total, where,
               fallback=None):
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
    row['state_returned'] = landed is not None
    print('%3d/%d %-32s %-24s %-18s opened %s%s'
          % (number, total, row['widget'], row['target'], where,
             row['opens'] or 'nothing', '' if landed == 'ok' else '  (%s)' % (landed or 'STUCK')))
    if landed is None:
        raise SystemExit('something stayed open after clicking %s; stopping, because every '
                         'measurement after this one would be contaminated' % row['widget'])
    if free_memory() < FREE_MEMORY_FLOOR:
        raise SystemExit('free memory %.1f GB is under the floor of %.1f GB'
                         % (free_memory(), FREE_MEMORY_FLOOR))
    if game_date(game.tree()) != date:
        raise SystemExit('the date moved from %s to %s: the clock is running'
                         % (date, game_date(game.tree())))
    return landed



def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    pid = int(sys.argv[1])
    vtablemap.configure(pid)
    fields, why = derive.fields_for(pid)
    derive.configure_channel(fields)
    derive.use_fields(fields)
    game = windowmap.Game(pid)
    global game_classes
    game_classes = game.window_classes
    if not paused(game):
        raise SystemExit('the clock is running; pause the game first, or the state is not repeatable')
    game.set_console(False)

    rows = buttons_on_disk()
    nodes, _, baseline = game.state()
    if baseline:
        raise SystemExit('these are open before the round starts: %s. Close them first, or every '
                         'window this round sees will be attributed to a click that did not open it'
                         % ', '.join(sorted(baseline)))
    date = game_date(nodes)
    print('%d buttons on disk open nothing but a view; fields %s, date %s, free memory %.1f GB'
          % (len(rows), why, date, free_memory()))

    by_name = {}
    for address, k in nodes.items():
        if k[6]:
            by_name.setdefault(k[6], []).append(address)
    scales = derive.scales_for(list(nodes))
    classes = derive.class_map(pid, {a: k[0] for a, k in nodes.items()})

    print('\nphase one: what is reachable without opening anything first')
    done = {}
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
                row['reason'] = ('%d widgets carry this name and %d of them are on screen'
                                 % (len(here), len(usable)))
        else:
            try_button(game, row, here[0], nodes, scales, classes, baseline, date,
                       number, len(rows), 'the screen')
        if row.get('opens') is None:
            row['opens'] = None
        done[row['widget']] = row

    doors = {}
    for row in rows:
        if row.get('opens') and len(row['opens']) == 1:
            doors.setdefault(row['opens'][0], row['widget'])
    print('\nphase two: %d windows can be opened first, then looked inside' % len(doors))

    for window, opener in sorted(doors.items()):
        waiting = [r for r in rows if r['reason'] is not None]
        if not waiting:
            break
        here = [a for a in by_name.get(opener, []) if on_screen(a, nodes, scales, classes) is None]
        if len(here) != 1:
            continue
        blank = {}
        if press(here[0], nodes, scales, classes, blank) is not None:
            continue
        time.sleep(SETTLE)
        inside_nodes = game.tree()
        floor = game.state(inside_nodes)[2]
        held = subtree_of(inside_nodes, window)
        if not held:
            back_to(game, baseline)
            continue
        inside_scales = derive.scales_for(list(inside_nodes))
        inside_classes = derive.class_map(pid, {a: k[0] for a, k in inside_nodes.items()})
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
            if press(here[0], nodes, scales, classes, {}) is not None:
                break
            time.sleep(SETTLE)
            inside_nodes = game.tree()
            floor = game.state(inside_nodes)[2]
            held = subtree_of(inside_nodes, window) or set()
            inside_scales = derive.scales_for(list(inside_nodes))
            inside_classes = derive.class_map(pid, {a: k[0] for a, k in inside_nodes.items()})

        print('   %-28s %d of the %d still waiting were in it' % (window, found, len(waiting)))
        if not back_to(game, baseline):
            raise SystemExit('%s would not close again' % window)

    with open(OUT, 'w', encoding='utf-8') as file:
        json.dump({'measured': time.strftime('%Y-%m-%d %H:%M'), 'game_date': date,
                   'buttons': rows}, file, ensure_ascii=False, indent=1)
    pressed = [r for r in rows if r.get('point')]
    opened = [r for r in pressed if r['opens']]
    agreed = [r for r in opened if any(r['target'] in w or w in r['target'] for w in r['opens'])]
    print('\npressed %d of %d, of those %d opened a window and %d matched the view name'
          % (len(pressed), len(rows), len(opened), len(agreed)))
    print('written to %s' % OUT)



def chain(pid, window, target, press_it=True):
    """One chain step: open `window`, find what brings `target` up inside it, press it, put it back.

    Stops the moment it cannot say which widget it means, because a click on a wrong guess lands on
    whatever really lies at that point - and inside a window that is nearly always something else
    that opens.
    """
    global game_classes
    game = windowmap.Game(pid)
    game_classes = game.window_classes
    nodes, _, baseline = game.state()
    if window not in baseline:
        raise SystemExit('%s is not open; open it first, this only does the step inside it'
                         % window)
    tables = gui_tables()
    goal = goal_of(target, tables[2])
    if goal[0] == 'view':
        print('%s is reached by opening the view %s' % (target, goal[1]))
    else:
        print('%s is reached by setting %s to %s'
              % (target, goal[1], goal[2] if goal[2] is not None else 'anything'))
    spots, record, acting, nodes, scales, classes = spots_for_goal(game, pid, window, goal, tables)
    print('%d widgets in %s carry a call that does that' % (len(spots), window))
    usable = []
    buttons = clickable_map(record, acting)
    for spot in spots:
        if spot['why_not'] is not None:
            continue
        x, y, w, h = spot['rect']
        point = reachable_point(buttons, spot['address'], spot['rect'])
        spot['point'] = point
        if point is not None:
            usable.append(spot)
        else:
            top = lands_on(buttons, (int(x + w / 2), int(y + h / 2)))
            spot['why_not'] = 'covered everywhere, at its middle by %s' % (
                (top['name'] or top['class']) if top else 'nothing readable')
    for spot in spots[:12]:
        print('   %x %-12s %-18s rect %s %s'
              % (spot['address'], spot['class'], spot['name'] or '-', spot['rect'],
                 spot['why_not'] or 'CLICKABLE and reachable'))
        for call in spot['also_does'][:2]:
            print('        also: %s' % call[:86])
    print('%d of them can actually be reached by a click' % len(usable))
    if not press_it or not usable:
        return spots
    spot = usable[0]
    point = spot['point']
    print('pressing %x at %d,%d' % (spot['address'], point[0], point[1]))
    channel.ask('mouse %d %d 1' % point)
    for _ in range(6):
        time.sleep(SETTLE)
        _, _, drawn = game.state()
        opened = sorted(drawn - baseline)
        if opened:
            break
    print('opened: %s' % (', '.join(opened) or 'nothing'))
    return spots


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    if len(sys.argv) > 3 and sys.argv[2] == '--chain':
        chain(int(sys.argv[1]), sys.argv[3], sys.argv[4])
    else:
        main()
