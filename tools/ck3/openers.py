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
    """
    windows = set(json.load(open(os.path.join(paths.PROJECT, 'reports', 'windows.json'),
                                 encoding='utf-8'))['windows'])
    found = {}
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
    return sorted(found.values(), key=lambda row: row['widget'])





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
    """
    if not derive.is_visible(nodes, address) or derive.is_clipped(nodes, address, scales, classes):
        return 'not visible'
    x, y = derive.screen_pos(nodes, address, scales)
    width, height = derive.screen_size(nodes, address, scales)
    if width <= 0 or height <= 0:
        return 'no size'
    if x < 0 or y < 0 or x + width > 1600 or y + height > 900:
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
        here = by_name.get(row['widget'], [])
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
            spots = [a for a in held if inside_nodes[a][6] == row['widget']]
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



if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    main()
