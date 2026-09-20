"""Shuts the game down the way a player does, and never any other way.

The game is not killed. A hard kill leaves CK3 no chance to release what it holds - and on this
machine the graphics chip has no memory of its own but borrows the system's, so what a killed
process leaves behind is left behind in a driver. Whether that is what put this laptop down five
times between 24 August and 19 September 2026 is not measured and is not claimed here; what is
measured is that of all those shutdowns exactly one wrote the exit autosave that CK3 writes when
it ends properly, so every other time it was shot.

So this presses the buttons: the pause menu, then Exit to Desktop, or on the main menu the exit
button there. If a step does not land it says what it saw and leaves the game running. There is
no fallback that kills it - that would be the very thing this exists to stop, and a fallback that
quietly does the dangerous thing is worse than no tool at all.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'nvda'))

import channel
import derive
import vtablemap
import windowmap

PAUSE_MENU, CONFIRMATION = 'ingame_pausemenu', 'ingame_resign_confirmation'


def look(root, pid, window_classes):
    """The tree of this moment, with what is drawn and where it is."""
    nodes = derive.widgets(root)
    windows = [a for a, k in nodes.items() if k[0] in window_classes]
    flags = derive.flags_for(windows)
    drawn = {nodes[a][6] for a in windows if flags.get(a) == 0}
    return nodes, derive.scales_for(list(nodes)), drawn


def press(nodes, scales, name, drawn_in=None):
    """Click the middle of a named widget. Returns what it clicked, or None if it is not there."""
    found = [a for a, k in nodes.items() if k[6] == name]
    if drawn_in is not None:
        found = [a for a in found if a in drawn_in]
    if not found:
        return None
    x, y = derive.screen_pos(nodes, found[0], scales)
    width, height = derive.screen_size(nodes, found[0], scales)
    if width <= 0 or height <= 0:
        return None
    channel.ask('mouse %d %d 1' % (int(x + width / 2), int(y + height / 2)))
    return name


def gone(pid, seconds=40):
    """Wait until the channel stops answering, which is the game being gone.

    It asks `alive` rather than `ask`, because here the link disappearing is what success looks
    like: going through `ask` made a clean shutdown speak the failure sentence for a game that had
    done exactly what it was told.
    """
    for _ in range(seconds):
        if not channel.alive():
            channel.close()
            return True
        time.sleep(1)
    return False


def quit_game(pid):
    fields = derive.stored()
    if fields is None:
        fields, _ = derive.fields_for(pid)      # only a loaded game can derive them
    derive.configure_channel(fields)
    derive.use_fields(fields)           # flags_for reads the offsets from here, not from the DLL
    vtablemap.configure(pid)
    window_classes = windowmap.classes(pid)
    root, _ = derive.quick_root(fields, pid)

    nodes, scales, drawn = look(root, pid, window_classes)

    if press(nodes, scales, 'exit_game_button'):
        print('pressed exit game on the main menu')
    else:
        # Escape shuts one open window at a time and only opens the pause menu when nothing is
        # open, so this steps through what is open rather than pressing once and giving up.
        for _ in range(5):
            if PAUSE_MENU in drawn:
                break
            channel.ask('sendkey 27')
            time.sleep(2.0)
            nodes, scales, drawn = look(root, pid, window_classes)
        if PAUSE_MENU not in drawn:
            raise SystemExit('the pause menu did not come up, so nothing was pressed')
        if not press(nodes, scales, 'exit_button'):
            raise SystemExit('the pause menu is up but carries no exit button')
        time.sleep(2.0)
        nodes, scales, drawn = look(root, pid, window_classes)
        if CONFIRMATION not in drawn:
            raise SystemExit('the confirmation did not come up; the game is untouched')
        if not press(nodes, scales, 'descktop_button'):
            raise SystemExit('the confirmation is up but carries no exit to desktop button')
        print('pressed exit to desktop')

    if gone(pid):
        print('the game is gone, and it ended itself')
    else:
        print('the game is still there after forty seconds. It is not killed; look at the screen.')


if __name__ == '__main__':
    quit_game(int(sys.argv[1]))
