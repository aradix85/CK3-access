r"""Play states: wait until a game is up, save it, type into the console, play someone else.

Usage:
    python tools\ck3\states.py <pid> wait               until a game is on screen, asked of the recogniser
    python tools\ck3\states.py <pid> save [suffix]      save through the pause menu, never over a save
    python tools\ck3\states.py <pid> console <command>  type one console command; needs -debug_mode
    python tools\ck3\states.py <pid> new <title key>    on the setup screen of a bookmark: start at
                                                        random, play the holder of the title, save

Five play states were made this way on 1.20.0.3, on 1 October 2026, and these are what it took:

- **The save dialog proposes the name of the save just loaded**, so saving at once overwrites it.
  `save` types a suffix after the proposal when given one, and refuses any name an existing save
  begins with - the game puts the date behind it, so a match on the start is a match.
- **`-play=<title>` chooses nobody on the setup screen**, with or without -debug_mode and -skip;
  `-bookmark=<name>` does set the date. So `new` clicks Random Character and Start where the
  recogniser finds them, saves once to read the running number of the title's holder from that save,
  and switches with the console command play.
- **play takes the number in the running game, not the historical one** from the history files;
  with the historical number nothing happens. The switch is checked with `model.player` before the
  state is saved.
- **The console is not a window class**, so a check on drawn windows never sees it open; whether it
  is open is its own state byte.
- **Whether a game is up is asked of the recogniser, not of memory:** 1.20 reaches the main menu at
  about 6 GB, where 1.19 needed 13.
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import channel
import derive
import model
import openers
import paths
import savegame
import vtablemap
import windowmap
from quit_game import PAUSE_MENU, look, press

IN_GAME = re.compile(r'\bPaused\b|Domain Holdings|Pinned Characters')
MAIN_MENU = ('New Game', 'Load')


def _ready(pid):
    """The tree of the running game with everything `look` and `press` ask for."""
    fields = derive.stored() or derive.fields_for(pid)[0]
    derive.configure_channel(fields)
    derive.use_fields(fields)
    derive.use_screen(pid)
    vtablemap.configure(pid)
    window_classes = windowmap.classes(pid)
    openers.game_classes = window_classes
    root, _ = derive.quick_root(fields, pid)
    return root, window_classes


def _screen(pid):
    import ocr
    import windowgrab
    image, _, _ = windowgrab.grab(pid)
    return ocr.read_image(image)


def wait(pid, timeout=900):
    """'game' once a game is on screen, 'menu' on the main menu; stops when the game is gone."""
    import psutil
    start = time.time()
    while time.time() - start < timeout:
        if not psutil.pid_exists(pid):
            raise SystemExit('the game is gone while waiting for it')
        words = [t for *_, t in _screen(pid)]
        text = ' | '.join(words)
        if IN_GAME.search(text) and 'Loading' not in text:
            return 'game'
        if all(w in words for w in MAIN_MENU):
            return 'menu'
        time.sleep(15)
    raise SystemExit('no game and no main menu on screen after %d seconds' % timeout)


def save(pid, suffix=''):
    """Save through the pause menu; the name of the new save comes back."""
    before = set(os.listdir(paths.SAVES))
    root, classes_of_windows = _ready(pid)
    nodes, scales, drawn, classes = look(root, pid, classes_of_windows)
    for _ in range(5):
        if PAUSE_MENU in drawn:
            break
        channel.ask('sendkey 27')
        time.sleep(2.0)
        nodes, scales, drawn, classes = look(root, pid, classes_of_windows)
    if PAUSE_MENU not in drawn:
        raise SystemExit('the pause menu did not come up; drawn: %s' % ', '.join(sorted(drawn)))
    why = press(nodes, scales, classes, 'save_button')
    if why:
        raise SystemExit('the pause menu is up, but its save button: %s' % why)
    for _ in range(10):
        time.sleep(1.0)
        nodes, scales, drawn, classes = look(root, pid, classes_of_windows)
        if 'save_game_window' in drawn:
            break
    else:
        raise SystemExit('the save dialog did not come up; drawn: %s' % ', '.join(sorted(drawn)))
    if suffix:
        why = press(nodes, scales, classes, 'save_name')
        if why:
            raise SystemExit('the name field: %s' % why)
        time.sleep(0.5)
        channel.ask('sendkey 35')                     # End: a click puts the cursor where it lands
        for ch in suffix:
            channel.ask('sendchar %d' % ord(ch))
        time.sleep(1.0)
        nodes, scales, drawn, classes = look(root, pid, classes_of_windows)
    named = [derive.strip_markup(k[7]) for k in nodes.values() if k[6] == 'save_name' and k[7]]
    name = named[0] if named else None
    if not name or any(f.startswith(name) for f in before):
        channel.ask('sendkey 27')                     # leave the dialog and the pause menu as found
        time.sleep(1.0)
        channel.ask('sendkey 27')
        raise SystemExit('refusing to save: a save beginning with %r already exists' % name)
    why = press(nodes, scales, classes, 'save_button')   # the dialog covers the pause menu's own
    if why:
        raise SystemExit('the save dialog is up, but its save button: %s' % why)
    for _ in range(60):
        time.sleep(1.0)
        new = set(os.listdir(paths.SAVES)) - before
        if new:
            time.sleep(3.0)
            channel.ask('sendkey 27')                 # the pause menu shuts again
            return sorted(new)[0]
    raise SystemExit('no new save appeared within a minute')


def console(pid, command):
    """Type one command into the console and shut it again. What the console answers is not read."""
    root, classes_of_windows = _ready(pid)

    def is_open():
        nodes, scales, _, classes = look(root, pid, classes_of_windows)
        found = [a for a, k in nodes.items() if k[6] == 'console_window']
        return bool(found) and derive.flags_for(found).get(found[0]) == 0, nodes, scales, classes

    opened, nodes, scales, classes = is_open()
    if not opened:
        channel.ask('sendkey 192')
        time.sleep(2.0)
        opened, nodes, scales, classes = is_open()
    if not opened:
        raise SystemExit('the console did not open; was the game started with -debug_mode?')
    why = press(nodes, scales, classes, 'console_edit')
    if why:
        raise SystemExit('the console is open, but its input line: %s' % why)
    for _ in range(60):
        channel.ask('sendkey 8')
    for ch in command:
        channel.ask('sendchar %d' % ord(ch))
    channel.ask('sendkey 13')
    time.sleep(2.0)
    channel.ask('sendkey 192')
    time.sleep(1.0)


def _click_text(pid, wanted, tries):
    for _ in range(tries):
        for x, y, w, h, text in _screen(pid):
            if text.strip() == wanted:
                channel.ask('mouse %d %d 1' % (x + w // 2, y + h // 2))
                return
        time.sleep(10)
    raise SystemExit('never saw %r on the screen' % wanted)


def holder(save_name, title):
    """The running number of whoever holds the title, out of a save of that game."""
    text = savegame.unpack(os.path.join(paths.SAVES, save_name))
    at = text.find('\tkey=%s\n' % title)
    if at < 0:
        raise SystemExit('%s is not in %s' % (title, save_name))
    entry = text.rfind('\n', 0, text.rfind('={', 0, at))
    found = re.search(r'\bholder=(\d+)', text[entry:at + 1500])
    if not found:
        raise SystemExit('%s has no holder in %s' % (title, save_name))
    return int(found.group(1))


def new(pid, title):
    """From the setup screen: start at random, play the holder of the title, save. Both saves."""
    _click_text(pid, 'Random Character', tries=40)
    time.sleep(3.0)
    _click_text(pid, 'Start', tries=6)
    if wait(pid) != 'game':
        raise SystemExit('Start did not lead into a game')
    time.sleep(20)
    first = save(pid)
    number = holder(first, title)
    console(pid, 'play %d' % number)
    time.sleep(4.0)
    now = model.player(pid)
    if now[0] != number:
        raise SystemExit('play %d did not take: the player is %s' % (number, now))
    return first, save(pid)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    pid, what = int(sys.argv[1]), sys.argv[2]
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    if what == 'wait':
        print(wait(pid))
    elif what == 'save':
        print('written:', save(pid, sys.argv[3] if len(sys.argv) > 3 else ''))
    elif what == 'console' and len(sys.argv) > 3:
        console(pid, ' '.join(sys.argv[3:]))
        print('typed:', ' '.join(sys.argv[3:]))
    elif what == 'new' and len(sys.argv) > 3:
        first, second = new(pid, sys.argv[3])
        print('written:', first, 'and', second)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
