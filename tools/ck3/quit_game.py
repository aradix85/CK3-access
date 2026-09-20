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
import openers
import vtablemap
import windowmap

PAUSE_MENU, CONFIRMATION = 'ingame_pausemenu', 'ingame_resign_confirmation'


def look(root, pid, window_classes):
    """The tree of this moment, with what is drawn, where it is, and what class each node is."""
    nodes = derive.widgets(root)
    windows = [a for a, k in nodes.items() if k[0] in window_classes]
    flags = derive.flags_for(windows)
    drawn = {nodes[a][6] for a in windows if flags.get(a) == 0}
    classes = derive.class_map(pid, {a: k[0] for a, k in nodes.items()})
    return nodes, derive.scales_for(list(nodes)), drawn, classes


def press(nodes, scales, classes, name):
    """Click the widget with this name that is really on screen. Returns None, or why not.

    **Taking the first widget with the right name is what broke this.** Measured 20 September
    2026: after an aborted window round the pause menu was drawn and this still reported three
    times over that the confirmation never came up. A name is not an address - `GUI.CreateWidget`
    leaves a parked second window object of the same name behind, and a posted click lands on
    whatever lies on top rather than on what you pointed at. `openers.on_screen` asks both
    questions per copy: alpha along the parent chain, a size, a rectangle inside the drawing area,
    and the flag byte of the window it hangs in. The copy that answers None is the one on screen.

    **A refusal carries the reason**, because a shutdown route that says only "it did not work"
    leaves the game standing with nothing to go on - and this is the one route that may never be
    replaced by a hard kill.
    """
    found = [a for a, k in nodes.items() if k[6] == name]
    if not found:
        return 'there is no widget called %s' % name
    refused = []
    for address in found:
        reason = openers.on_screen(address, nodes, scales, classes)
        if reason is None:
            x, y = derive.screen_pos(nodes, address, scales)
            width, height = derive.screen_size(nodes, address, scales)
            channel.ask('mouse %d %d 1' % (int(x + width / 2), int(y + height / 2)))
            return None
        refused.append(reason)
    return '%s is in the tree %d time(s) and none of them can be clicked: %s' % (
        name, len(found), ', '.join(sorted(set(refused))))


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
    derive.use_screen(pid)              # on_screen asks the drawing area of this run, not a constant
    vtablemap.configure(pid)
    window_classes = windowmap.classes(pid)
    openers.game_classes = window_classes
    root, _ = derive.quick_root(fields, pid)

    nodes, scales, drawn, classes = look(root, pid, window_classes)

    if press(nodes, scales, classes, 'exit_game_button') is None:
        print('pressed exit game on the main menu')
    else:
        # Escape shuts one open window at a time and only opens the pause menu when nothing is
        # open, so this steps through what is open rather than pressing once and giving up.
        for _ in range(5):
            if PAUSE_MENU in drawn:
                break
            channel.ask('sendkey 27')
            time.sleep(2.0)
            nodes, scales, drawn, classes = look(root, pid, window_classes)
        if PAUSE_MENU not in drawn:
            raise SystemExit('the pause menu did not come up, so nothing was pressed')
        why = press(nodes, scales, classes, 'exit_button')
        if why:
            raise SystemExit('the pause menu is up but %s' % why)
        time.sleep(2.0)
        nodes, scales, drawn, classes = look(root, pid, window_classes)
        if CONFIRMATION not in drawn:
            raise SystemExit('the exit button was pressed and the confirmation did not come up. '
                             'Drawn right now: %s' % (', '.join(sorted(drawn)) or 'nothing'))
        why = press(nodes, scales, classes, 'descktop_button')
        if why:
            raise SystemExit('the confirmation is up but %s' % why)
        print('pressed exit to desktop')

    if gone(pid):
        print('the game is gone, and it ended itself')
    else:
        print('the game is still there after forty seconds. It is not killed; look at the screen.')


if __name__ == '__main__':
    quit_game(int(sys.argv[1]))
