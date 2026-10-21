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

**Leaving a loaded game, the game writes its exit save**, and this says whether it did: that is
the check that it ended itself. With `save_on_exit` on in its settings it wrote one every time it
left a loaded game, and none leaving the main menu (measured 21 October 2026, 1.20.1.1).
"""
import os
import sys
import time

from tools import paths
from tools.ck3 import channel, derive, onscreen, openers, widgettree

PAUSE_MENU, CONFIRMATION = 'ingame_pausemenu', 'ingame_resign_confirmation'
# The game's own yes-or-no dialog, in shared/dialogs.gui. Escape on it says no.
QUESTION = 'basic_confirmation_popup'
# EXIT_SAVE_NAME in the game's common/defines/00_defines.txt.
EXIT_SAVE = 'autosave_exit.ck3'


def ready(pid: int) -> tuple[int, set[int]]:
    """The root of the running game's tree and its window classes, with everything `look` and
    `press` ask for handed to the channel and to derive.

    **The stored derivation is used without its recheck.** On the main menu the recheck turns a
    good derivation down and derives again for minutes (`tools/never_silent.py`), and leaving the
    game has to work there. Only a build without one derives it, and that needs a loaded game.
    """
    _, root, _ = derive.fields_for(pid, recheck=False)
    window_classes = derive.window_classes_of(pid)
    openers.game_classes = window_classes
    return root, window_classes


def look(root: int, pid: int, window_classes: set[int]) -> tuple[widgettree.Nodes, onscreen.Scales, set[str],
                                                                dict[int, str | None]]:
    """The tree of this moment, with what is drawn, where it is, and what class each node is."""
    nodes = widgettree.widgets(root)
    windows = [a for a, k in nodes.items() if k[0] in window_classes]
    drawn = {nodes[a][6] for a in onscreen.shown(nodes, windows)}
    classes = widgettree.class_map(pid, {a: k[0] for a, k in nodes.items()})
    return nodes, onscreen.scales_for(list(nodes)), drawn, classes


def press(nodes: widgettree.Nodes, scales: onscreen.Scales, classes: dict[int, str | None], name: str) -> str | None:
    """Click the widget with this name that is really on screen. Returns None, or why not.

    **Taking the first widget with the right name is what broke this.** Measured 20 September
    2026: after an aborted window round the pause menu was drawn and this still reported three
    times over that the confirmation never came up. A name is not an address - `GUI.CreateWidget`
    leaves a parked second window object of the same name behind, and a posted click lands on
    whatever lies on top rather than on what you pointed at. `openers.on_screen` asks both
    questions per copy: alpha along the parent chain, clipping, a size, a rectangle inside the
    drawing area, the state byte along the chain (the game hiding it, or its window not drawn), and
    whether a window later in the tree lies over its middle. The copy that answers None is the one
    on screen.

    **A refusal carries the reason**, because a shutdown route that says only "it did not work"
    leaves the game standing with nothing to go on - and this is the one route that may never be
    replaced by a hard kill.
    """
    found = [a for a, k in nodes.items() if k[6] == name]
    if not found:
        return f'there is no widget called {name}'
    refused = []
    for address in found:
        reason = openers.press(address, nodes, scales, classes)
        if reason is None:
            return None
        refused.append(reason)
    return f"{name} is in the tree {len(found)} time(s) and none of them can be clicked: {', '.join(sorted(set(refused)))}"


def listed(drawn: set[str]) -> str:
    return ', '.join(sorted(drawn)) or 'nothing'


def escape_to(root: int, pid: int, window_classes: set[int], menus: set[str]
              ) -> tuple[widgettree.Nodes, onscreen.Scales, set[str], dict[int, str | None]]:
    """Escape until one of `menus` is drawn, and what is drawn then; stop if it does not come.

    Escape shuts one open window at a time and only opens the pause menu when nothing is open, so
    this steps through what is open rather than pressing once and giving up. A window holding
    unfinished work asks first - the activity planner whether its plan may go - and the answer is
    yes, as a player has to give it to get past; Escape there would say no and keep it standing.
    """
    nodes, scales, drawn, classes = look(root, pid, window_classes)
    for _ in range(5):
        if drawn & menus:
            return nodes, scales, drawn, classes
        if QUESTION in drawn:
            why = press(nodes, scales, classes, 'accept_button')
            if why:
                raise SystemExit(f'the game asks a question and {why}')
            print('the game asked a question, answered yes')
        else:
            channel.ask('sendkey 27')
        time.sleep(2.0)
        nodes, scales, drawn, classes = look(root, pid, window_classes)
    if not drawn & menus:
        raise SystemExit(f'{listed(menus)} did not come up; drawn: {listed(drawn)}')
    return nodes, scales, drawn, classes


def exit_save_since(moment: float) -> bool:
    path = os.path.join(paths.require('SAVES'), EXIT_SAVE)
    return os.path.exists(path) and os.path.getmtime(path) >= moment


def gone() -> bool:
    """Wait until the channel stops answering, which is the game being gone. It asks `alive`,
    because here the link disappearing is what success looks like."""
    seconds: int = 40
    for _ in range(seconds):
        if not channel.alive():
            channel.close()
            return True
        time.sleep(1)
    return False


def quit_game(pid: int) -> None:
    root, window_classes = ready(pid)
    nodes, scales, drawn, classes = look(root, pid, window_classes)

    left_at: float | None = None        # the moment a loaded game was left, after which its exit save comes
    if press(nodes, scales, classes, 'exit_game_button') is None:
        print('pressed exit game on the main menu')
    else:
        # On the setup screen of a bookmark Escape brings up the exit confirmation itself, with no
        # pause menu in between (measured 21 October 2026).
        nodes, scales, drawn, classes = escape_to(root, pid, window_classes, {PAUSE_MENU, CONFIRMATION})
        if CONFIRMATION not in drawn:
            why = press(nodes, scales, classes, 'exit_button')
            if why:
                raise SystemExit(f'the pause menu is up but {why}')
            time.sleep(2.0)
            nodes, scales, drawn, classes = look(root, pid, window_classes)
        if CONFIRMATION not in drawn:
            raise SystemExit(f'neither the pause menu nor the exit confirmation came up as it should, so nothing more was pressed. Drawn right now: {listed(drawn)}')
        left_at = time.time()
        why = press(nodes, scales, classes, 'descktop_button')
        if why:
            raise SystemExit(f'the confirmation is up but {why}')
        print('pressed exit to desktop')

    if not gone():
        print('the game is still there after forty seconds. It is not killed; look at the screen.')
    elif left_at is not None and not exit_save_since(left_at):
        print('the game is gone, and it wrote no exit save')
    else:
        print('the game is gone, and it ended itself' + ('' if left_at is None else ': its exit save is written'))


if __name__ == '__main__':
    quit_game(int(sys.argv[1]))
