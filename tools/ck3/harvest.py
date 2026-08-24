r"""Phase 1 of the sweep: harvest one window at a time, raw.

Phase 0 said which window can be opened by which route; this one records what is inside. Per
window: open it, wait until the flag says it is drawn, write down every widget with every field -
including the ones nothing uses today - take a capture and run the recogniser over it, close it,
and check that the state before it returns.

**Raw material, not conclusions.** Whatever gets interpreted here is interpreted once, by today's
understanding, and a second pass would need the game running again. Numbers are cheap to store and
expensive to re-measure.

**Four stop conditions, all measurable**, because a round of two hundred windows that goes wrong in
the middle is worse than one that stops: too little free memory, a channel that stops answering, a
window that will not open after three tries, and a state that does not come back. The last one
matters most - if something stays open, every later measurement is contaminated.

Resumable: what is already on disk is skipped, so a stopped round continues where it left off.

Usage:  python tools\ck3\harvest.py <pid> [<window> ...]
"""
import ctypes
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import channel
import derive
import ocr
import paths
import windowgrab
import windowmap

OUT = os.path.join(paths.PROJECT, 'harvest')
MAP = os.path.join(paths.REPORTS, 'windows.json')
FREE_MEMORY_FLOOR = 2.0          # gigabytes; the game itself uses about 16
OPEN_TRIES = 3
# The HUD is drawn in every game state and never opens or closes, so it belongs in the baseline
# rather than in the round. Without this the guard against leftovers fires on it and nothing runs;
# with it, any *other* window in the baseline still stops the round, which is the point.
ALWAYS_DRAWN = {'toolbars_window'}


class _Memory(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                ('total', ctypes.c_ulonglong), ('free', ctypes.c_ulonglong),
                ('total_page', ctypes.c_ulonglong), ('free_page', ctypes.c_ulonglong),
                ('total_virtual', ctypes.c_ulonglong), ('free_virtual', ctypes.c_ulonglong),
                ('extended', ctypes.c_ulonglong)]


def free_memory():
    """Free physical memory in gigabytes, straight from Windows."""
    status = _Memory()
    status.length = ctypes.sizeof(_Memory)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.free / (1024.0 ** 3)


def game_date(nodes):
    """The date the game is showing, from the widget that carries it.

    The widget is called `date_text_sp`, measured 24 August 2026 by looking for the one text in the
    tree carrying a month name - exactly one widget does. Guessing at `date` finds nothing, and
    then the pause check silently has nothing to compare.
    """
    for k in nodes.values():
        if k[6] == 'date_text_sp' and k[7]:
            return derive.strip_markup(k[7])
    return None


def paused(game, seconds=6.0):
    """Is the clock standing still? Measured, not assumed - a running clock makes the round
    unrepeatable and can kill the character halfway through."""
    first = game_date(game.tree())
    if first is None:
        raise SystemExit('no date widget in the tree: this needs a loaded game, and without it '
                         'there is no way to tell whether the clock is running')
    time.sleep(seconds)
    return first == game_date(game.tree())


def subtree(nodes, root):
    """Every widget below this window, breadth first, with the depth kept."""
    children = {}
    for address, k in nodes.items():
        children.setdefault(k[5], []).append(address)
    out, todo = [], [(root, 0)]
    while todo:
        address, depth = todo.pop(0)
        out.append((address, depth))
        if depth < 40:
            todo.extend((child, depth + 1) for child in sorted(children.get(address, [])))
    return out


def widget_record(nodes, address, depth, scales, classes, flags, alphas):
    """One widget, with every field this project can read - also the ones nothing uses yet.

    **Text only from a text box.** The offset that holds the shown string belongs to `Textbox`;
    on any other class it lands on something else and comes back as unreadable bytes that look
    like a reading error. Measured 24 August 2026, and `reports\\textfield.json` says the same
    thing from the other side: the search for a text field per class found a hit for `Textbox`
    and for nothing else. So other classes get null here, with their class recorded, rather than
    noise that a later pass would have to learn to distrust.
    """
    vtable, x, y, width, height, parent, name, text = nodes[address]
    screen_x, screen_y = derive.screen_pos(nodes, address, scales)
    drawn_width, drawn_height = derive.screen_size(nodes, address, scales)
    own, above = scales.get(address, (1.0, 1.0))
    kind = classes.get(address)
    return {'address': '%x' % address, 'parent': '%x' % parent, 'depth': depth,
            'class': kind, 'name': name, 'text': text if kind == 'Textbox' else None,
            'own_rect': [x, y, width, height],
            'screen_rect': [screen_x, screen_y, drawn_width, drawn_height],
            'scale': [own, above], 'alpha': alphas.get(address),
            'window_flag': flags.get(address),
            'clipped': derive.is_clipped(nodes, address, scales, classes)}


def alphas_for(addresses):
    """Alpha of many widgets in as few channel questions as possible, the way flags_for does it."""
    out, items = {}, sorted(addresses)
    offset = derive._visibility_offset('alpha')
    import struct
    for start in range(0, len(items), 400):
        part = items[start:start + 400]
        ask = 'readmany 4 ' + ' '.join('%x' % (a + offset) for a in part)
        for line in channel.ask(ask, timeout=120).split('\n'):
            d = line.split('\t')
            if d[0] == 'l' and len(d) > 2 and d[2] != 'unreadable':
                out[int(d[1], 16) - offset] = struct.unpack('<f', bytes.fromhex(d[2]))[0]
    return out


def capture(pid, name):
    """The window as pixels, plus everything the recogniser reads in it, with positions."""
    image, width, height = windowgrab.grab(pid)
    path = os.path.join(OUT, name + '.jpg')
    image.convert('RGB').save(path, 'JPEG', quality=70)
    lines = ocr.read_image(image)
    return {'capture': os.path.basename(path), 'size': [width, height],
            'recognised': [{'rect': [line[0], line[1], line[2], line[3]], 'text': line[4]}
                           for line in lines]}


def open_window(game, name, row, baseline):
    """Open one window along the route phase 0 found for it, and prove it is drawn.

    Waits on the flag, never on the clock: a window fades in, so a fixed sleep either wastes time
    or measures a window that is not there yet.

    **Poll the one window, not the whole tree - but only where that is allowed.** The first version
    asked `state()` twelve times per attempt and each of those walks all 78,000 nodes, so a window
    that refuses cost a hundred seconds; over a full round that is half an hour of waiting for
    nothing. A shortcut toggles a window object that already exists, so its address can be looked
    up once and its flag read with a single channel question.
    **`GUI.CreateWidget` may not use that shortcut**, and that is measured, not reasoned: it builds
    a *new* object, so polling the address of the parked one that happens to carry the same name
    reports failure while the window is in fact open - `levy_view` harvested fine in the run of
    twenty and then "failed" the moment this optimisation was applied to it. Worse, a false failure
    leaves the created widget standing. So that route keeps polling the tree.
    """
    if row.get('shortcut'):
        nodes = game.tree()
        address = next((a for a, k in nodes.items()
                        if k[6] == name and k[0] in game.window_classes), None)
    else:
        address = None
    # Phase 0 already tried every window once. Where it saw nothing drawn, three attempts buy
    # nothing and cost a minute each, so those get one - which over a full round is the difference
    # between ten minutes and half an hour of proving the same negative.
    tries = OPEN_TRIES if row.get('drawn') else 1
    for attempt in range(1, tries + 1):
        if row.get('shortcut'):
            channel.ask('sendkey %d' % (111 + int(row['shortcut'][1:])))
            for _ in range(14):
                time.sleep(0.6)
                if derive.flags_for([address]).get(address, 0xFF) == 0x00:
                    return game.tree(), attempt
        else:
            game.command('GUI.CreateWidget %s %s' % (row['file'], name))
            for _ in range(5):
                time.sleep(1.0)
                nodes, _, drawn = game.state()
                if name in drawn - baseline:
                    return nodes, attempt
    return None, tries


def close_window(game, name, row, baseline, limit=12):
    """Shut it again and wait until the state before it is back. Anything left open contaminates
    every window after this one, which is why this is a stop condition and not a warning."""
    for _ in range(limit):
        if row.get('shortcut'):
            channel.ask('sendkey %d' % (111 + int(row['shortcut'][1:])))
        else:
            game.command('GUI.ClearWidgets')
        time.sleep(1.2)
        _, _, drawn = game.state()
        if drawn == baseline:
            return True
        channel.ask('sendkey 27')
    return False


def drawn_one(candidates, name):
    """Of several window objects carrying the same name, the one that is actually drawn.

    `GUI.CreateWidget` builds a *new* object while the parked one keeps its name, so the tree holds
    two of them. Taking whichever comes first harvests the empty shell, and the whole window then
    looks like it contains nothing. Measured 24 August 2026 on `army_window`: two objects, both 292
    widgets; the parked one at flag 0x24 carried no text at all and the drawn one at flag 0x00
    carried Army, Always Raid and Commander. A whole round of 178 windows was taken from the wrong
    side of that fork before this was noticed.
    """
    if len(candidates) == 1:
        return candidates[0]
    flags = derive.flags_for(candidates)
    drawn = [a for a in candidates if flags.get(a, 0xFF) == 0x00]
    if len(drawn) == 1:
        return drawn[0]
    if not drawn:
        raise SystemExit('%s: %d objects carry this name and none of them is drawn'
                         % (name, len(candidates)))
    raise SystemExit('%s: %d objects carry this name and %d of them are drawn, so which one holds '
                     'the content cannot be decided here' % (name, len(candidates), len(drawn)))


def harvest(game, name, row, baseline, header):
    """One window, from opening to the state coming back. Returns the record, or a reason."""
    started = time.time()
    nodes, attempts = open_window(game, name, row, baseline)
    if nodes is None:
        return {'window': name, 'opened': False,
                'reason': 'did not open in %d %s'
                          % (attempts, 'try' if attempts == 1 else 'tries')}, 'not opened'

    windows = [a for a, k in nodes.items() if k[0] in game.window_classes]
    named = [a for a in windows if nodes[a][6] == name]
    address = drawn_one(named, name)
    family = subtree(nodes, address)
    addresses = [a for a, _ in family]
    scales = derive.scales_for(list(nodes))
    classes = derive.class_map(game.pid, {a: k[0] for a, k in nodes.items()})
    flags = derive.flags_for([a for a in addresses if a in windows])
    alphas = alphas_for(addresses)
    record = dict(header)
    record.update({
        'window': name, 'opened': True, 'attempts': attempts, 'file': row.get('file'),
        'route': 'shortcut ' + row['shortcut'] if row.get('shortcut') else 'GUI.CreateWidget',
        'address': '%x' % address, 'widgets': len(family),
        'tree_size': len(nodes), 'seconds': round(time.time() - started, 1)})
    record.update(capture(game.pid, name))
    record['tree'] = [widget_record(nodes, a, d, scales, classes, flags, alphas)
                      for a, d in family]
    if not close_window(game, name, row, baseline):
        return record, 'state did not come back'
    record['seconds'] = round(time.time() - started, 1)
    return record, None


def main():
    pid = int(sys.argv[1])
    wanted = sys.argv[2:]
    os.makedirs(OUT, exist_ok=True)
    windows = json.load(open(MAP, encoding='utf-8'))['windows']
    names = wanted or sorted(windows)

    game = windowmap.Game(pid)
    if not paused(game):
        raise SystemExit('the clock is running: pause the game first, or the state is not '
                         'repeatable and the character can die halfway through')
    game.command('GUI.ClearWidgets')
    time.sleep(1.0)
    nodes, _, baseline = game.state()
    header = {'measured': time.strftime('%Y-%m-%d %H:%M'), 'exe': derive.build_key(),
              'game_date': game_date(nodes), 'baseline': sorted(baseline),
              'fields': {k: v for k, v in game.fields.items() if isinstance(v, int)}}
    print('baseline %s, date %s, free memory %.1f GB'
          % (sorted(baseline) or 'nothing drawn', header['game_date'], free_memory()))

    left_over = [n for n in names if n in baseline and n not in ALWAYS_DRAWN]
    if left_over:
        raise SystemExit('these are already open before the round starts: %s. A window in the '
                         'baseline can never be seen to open, so it would be recorded as a '
                         'failure; and if it is there because an earlier run left it standing, '
                         'every measurement after it is contaminated. Close it first.'
                         % ', '.join(left_over))
    names = [n for n in names if n not in ALWAYS_DRAWN]

    done = failed = 0
    for number, name in enumerate(names, 1):
        target = os.path.join(OUT, name + '.json')
        if os.path.exists(target):
            continue
        if free_memory() < FREE_MEMORY_FLOOR:
            raise SystemExit('stopping: %.1f GB free, below the floor of %.1f'
                             % (free_memory(), FREE_MEMORY_FLOOR))
        if 'channel' not in channel.ask('hello'):
            raise SystemExit('stopping: the channel no longer answers')
        record, reason = harvest(game, name, windows[name], baseline, header)
        json.dump(record, open(target, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        if reason == 'state did not come back':
            raise SystemExit('stopping after %s: %s' % (name, reason))
        done += reason is None
        failed += reason is not None
        print('%3d/%d %-34s %s' % (number, len(names), name,
                                   reason or '%d widgets, %d recognised lines, %.0fs'
                                   % (record['widgets'], len(record['recognised']),
                                      record['seconds'])))
    print('harvested %d, failed to open %d, written to %s' % (done, failed, OUT))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    main()
