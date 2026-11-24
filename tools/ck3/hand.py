r"""Windows by hand, along presses the files cannot route.

Usage:
    python -m tools.ck3.hand <pid> <source> <key | button:name | event:id | standing:how> [<step> ...]

Opens `source` by its key, by pressing a button by name, as the migration window opens from the
nomad's bar, or by firing an event from the console, which the game shows in its own window with
its data (`windowmap.pressed`); without steps, `source` itself is recorded. Then per step, written
`<call>=<target>`: press inside the window standing open the first widget whose onclick carries
`call`, for `right:<call>` click those whose onrightclick carries it with the right button, in turn
until a window comes up, as the menu of interactions opens on a portrait - with `@<text>`, until
one comes up that shows the text in a drawn widget, such as a character's name - or for `goal:<window>`
what the files say reaches that window; `<call>@<text>` takes the first whose row shows that text,
where rows share a call, as the activities do, and `<call>@<group>><text>` the one alone under the
nearest heading `group`, as the expander of one category of the interaction menu
(`InteractionItem.OnClick@Vassal>2 more`); `button:<name>` clicks the widget of that name in the
window, for one no gui file puts there, as the game hangs a decision's own widget into the decision
(`press_named`); `hover:<name>` rests the real pointer on the drawn
widget of that name, for buttons the game shows only while the mouse is over something, as the
memories and the inventory sit behind the main portrait of the character window; it takes the
foreground until the walk ends. Wait for `target`, record it into the harvest, and go on from it.
A step without `=target` only changes the window standing open, as a tab does: the hostage exchange
sits in the war overview's peace terms, which the engine shows once a terms tab is pressed. A
window on the way that already has a record from a player route keeps it, as in the chain round,
with the view of its step written into it; the last target is always recorded. A step's view is
every view the pressed widget opens by the files whose name is no window name, whether the step
named a goal or a call (`Spot['fires']`). A record it replaces goes aside
into `harvest-<date>-replaced`, or into `harvest-<date>-console-replaced` when the console made it.
The state is put back, or nothing is written.

**With `standing:<how>` the source stands open already**, after something this tool does not press:
a place on the map clicked with the real mouse, the clock, a key in a second window. `how` says in
words what brought it up, and the route keeps it. Nothing is opened and nothing is put back: the
steps go from the source as it stands, the records are written, and the last window recorded gets
its keys pressed where it stands, Escape last, into `reports\window_keys.json`, as the watcher does
(`windowmap.keys_in_place`), because the key round cannot open it again. Such a record names no
bare screen: none is measured with a window standing.

The route of every record says what was pressed, starting with `hand:`. Made on 22 October 2026,
after the filter presets, the settings window and the court appointment with its filter had each
taken a throwaway script: the appointment opens from a vacant court position, whose onclick calls
`CourtPositionType.OpenAppointWindow` and opens no view, so no chain on disk reaches it.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import pathlib
import sys
import time
from collections.abc import Callable

from tools import paths, terminal, windowgrab
from tools.ck3 import guimap, harvest, modifiers, onscreen, openers, widgettree, windowmap
from tools.nvda import speech

user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.GetForegroundWindow.restype = wt.HWND
user32.IsWindow.argtypes = [wt.HWND]
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
# How long the pointer rests before the game has run its hover state: a second and a half was enough
# for a button and a portrait (brief\invoer.md, hovering).
HOVER_SECONDS: float = 1.5

# One step as this tool takes it: what to press, and the window that comes up, or '' for a step that
# only changes the window standing open.
Step = tuple[str, str]


def route_of(route: str, window: str) -> tuple[str, str, list[Step]] | None:
    """(source, its press, the steps) of a `hand:` route as the record of `window` keeps it, so the
    route can be walked again (`windowmap.window_keys_round`). A step's target is the window the
    next step is pressed in, and the last one's is `window`.

    None for a route this tool cannot walk again: one from a window that stood open already, one
    with a step it does not take, such as a place on the map clicked with the real mouse, and one
    written before this tool."""
    if not route.startswith('hand: ') or route.startswith('hand: standing:'):
        return None
    how, *rest = route[len('hand: '):].split(', ')
    parsed = [part.rpartition(' in ') for part in rest]
    if any(not sep for _, sep, _ in parsed):
        return None
    steps: list[Step] = []
    for number, (step, _, source) in enumerate(parsed):
        after = parsed[number + 1][2] if number + 1 < len(parsed) else window
        steps.append((step, '' if after == source else after))
    return (parsed[0][2] if parsed else window), how, steps


class Pointer:
    """The player's front window and pointer, taken only for a hover and given back once.

    The game follows the real pointer only while it is in front (measured 6 October 2026), so a
    hover is the one step that takes the foreground, and NVDA says so first, as the key test does."""

    def __init__(self, pid: int) -> None:
        self.game_window = windowgrab.window_of(pid)[0]
        self.hers: int | None = None
        self.where = wt.POINT()

    def rest_on(self, x: float, y: float) -> bool:
        """The pointer on this point of the drawing area, with the game in front."""
        if self.hers is None:
            self.hers = int(user32.GetForegroundWindow() or 0)
            user32.GetCursorPos(ctypes.byref(self.where))
            speech.output('the hand round takes the game to the front to hover; please do not type')
            time.sleep(2)
        if not modifiers.bring(self.game_window):
            return False
        point = wt.POINT(int(x), int(y))
        user32.ClientToScreen(self.game_window, ctypes.byref(point))
        user32.SetCursorPos(point.x, point.y)
        time.sleep(HOVER_SECONDS)
        return True

    def give_back(self) -> None:
        if self.hers is None:
            return
        user32.SetCursorPos(self.where.x, self.where.y)
        if self.hers and user32.IsWindow(self.hers) and not modifiers.bring(self.hers):
            speech.failure('the hand round', 'it could not give your window the foreground back',
                           'switch to it yourself with Alt+Tab')
        else:
            speech.output('the hand round is done hovering, the foreground is yours again')
        self.hers = None


def hover_point(game: windowmap.Game, source: str, name: str) -> tuple[float, float] | str:
    """The middle of the drawn widget `name` in `source`, or why there is none."""
    nodes, _, _ = game.state()
    named = [a for a in openers.subtree_of(nodes, source) if nodes[a][6] == name]
    drawn = onscreen.shown(nodes, named)
    address = next((a for a in named if a in drawn), None)
    if address is None:
        return f'no {name} drawn in {source}'
    scales = onscreen.scales_for(list(nodes))
    x, y = onscreen.screen_pos(nodes, address, scales)
    w, h = onscreen.screen_size(nodes, address, scales)
    return x + w / 2, y + h / 2


def press_named(game: windowmap.Game, source: str, name: str) -> tuple[widgettree.Nodes, set[str], str | None]:
    """In `source`, standing open, click the first widget called `name` that a click reaches, and
    wait for what comes up: the tree then, the windows the press brought up, and why nothing was
    pressed.

    For a widget no gui file puts in its window, which the alignment of a call cannot find: the
    game hangs a decision's own widget into `decisiondetail_view` from gui\\decision_view_widgets
    when the decision opens, and the lease of baronies and the title selector open from buttons in
    it (measured 17 November 2026 on Harold)."""
    nodes, _, before = game.state()
    under = openers.subtree_of(nodes, source)
    scales = onscreen.scales_for(list(nodes))
    classes = widgettree.class_map(game.pid, {a: k[0] for a, k in nodes.items()})
    refused: list[str] = []
    for address in [a for a in nodes if a in under and nodes[a][6] == name]:
        why = openers.press(address, nodes, scales, classes)
        if why is None:
            return (*harvest.came_up(game, before, 6), None)
        refused.append(why)
    return nodes, set(), f"no {name} in {source} takes a click: {', '.join(sorted(set(refused))) or 'none is there'}"


def walk(game: windowmap.Game, source: str, steps: list[Step], route: str, tables: guimap.Tables,
         reached: Callable[[str, widgettree.Nodes, str, list[str]], None]) -> str | None:
    """In `source`, standing open, press each step in turn, and hand every window a step brings up
    to `reached`, with the route so far and the views the pressed widget opens by the files whose
    name is no window name. None once the last step is done, else why the walk stopped; the caller puts the
    state back. A hover's foreground and pointer go back before this returns."""
    known = tables[2]
    pointer: Pointer | None = None
    try:
        for step, target in steps:
            if step.startswith('hover:'):
                name = step[len('hover:'):]
                point = hover_point(game, source, name)
                if isinstance(point, str):
                    return f'{step} in {source}: {point}'
                pointer = pointer or Pointer(game.pid)
                if not pointer.rest_on(*point):
                    return f'{step} in {source}: the game did not come to the front'
                print(f'in {source} hovered {name}')
                if target:
                    return f'{step} in {source}: a hover opens no window, so it takes no target'
                route += f', {step} in {source}'
                continue
            fires: list[str] = []
            if step.startswith('button:'):
                nodes, opened, why = press_named(game, source, step[len('button:'):])
                pressed = None if why else step[len('button:'):]
            else:
                call, at, showing = step.partition('@')
                goal = (openers.goal_of(call[len('goal:'):], tables) if call.startswith('goal:')
                        else openers.Goal('right', call[len('right:'):]) if call.startswith('right:')
                        else openers.Goal('call', call))
                nodes, opened, spot, why = harvest.chain_press(game, source, goal, tables, showing if at else None)
                pressed = (spot['name'] or spot['class']) if spot else None
                fires = spot['fires'] if spot else []
            print(f"in {source} pressed {pressed}; "
                  f"opened {', '.join(sorted(opened)) or 'nothing'}{'; ' + why if why else ''}")
            if pressed is None or (target and target not in opened):
                return f"{step} in {source} brought up {', '.join(sorted(opened)) or 'nothing'}{'; ' + why if why else ''}"
            route += f', {step} in {source}'
            if target:
                reached(target, nodes, route, sorted({view for call in fires
                                                      for view in openers.VIEW_CALL.findall(call) if view not in known}))
                source = target
    finally:
        if pointer is not None:
            pointer.give_back()
    return None


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    pid, source, how = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    steps = [step.partition('=')[::2] for step in sys.argv[4:]]
    # A route is kept as its steps joined by ', ', and `route_of` splits it there again.
    if any(', ' in step for step, _ in steps):
        raise SystemExit("a step holds ', ', which a route cannot keep: give the call up to its comma")
    game = windowmap.Game(pid)
    openers.game_classes = game.window_classes
    if not harvest.paused(game):
        raise SystemExit('the clock is running: pause the game first')
    windows: dict[str, windowmap.Route] = json.loads(pathlib.Path(harvest.MAP).read_text(encoding='utf-8'))['windows']
    along(pid, game, windows, guimap.tables(), source, how, steps)


def along(pid: int, game: windowmap.Game, windows: dict[str, windowmap.Route], tables: guimap.Tables,
          source: str, how: str, steps: list[Step]) -> None:
    """Walk one route and write its records, with the game, the map and the gui tables handed in.

    A round of many routes loads them once (`compare.again`): started once per route, a round spent
    a minute of every eighty seconds loading the derivation, the gui files, the localization and
    the recogniser (measured 24 November 2026, 55 windows in 72 minutes)."""
    standing = how.startswith('standing:')
    back: windowmap.Route = {'click': True}
    started = time.time()
    opened_source: widgettree.Nodes | None
    if standing:
        if not how[len('standing:'):].strip():
            raise SystemExit('standing: says in words what brought the window up, for the route')
        opened_source, _, drawn = game.state()
        if source not in drawn:
            raise SystemExit(f"{source} does not stand open; drawn: {', '.join(sorted(drawn))}")
        attempts, header = 1, harvest.header(game, set())
    else:
        row = windowmap.pressed(how)
        baseline = game.bare()
        header = harvest.header(game, baseline)
        opened_source, attempts = harvest.open_window(game, source, row, baseline)
        if opened_source is None:
            harvest.close_window(game, back, baseline)
            raise SystemExit(f'{source} did not open along {how}')
    records: list[harvest.Record] = []
    noted: list[tuple[str, str]] = []
    if not steps:
        records.append(harvest.record_window(game, source, opened_source, header, f'hand: {how}', attempts,
                                             (windows.get(source) or {}).get('file'), started, []))

    def reached(target: str, nodes: widgettree.Nodes, route: str, views: list[str]) -> None:
        if target == steps[-1][1] or not harvest.player_record(target):
            records.append(harvest.record_window(game, target, nodes, header, route, attempts,
                                                 (windows.get(target) or {}).get('file'), started, views))
        else:
            noted.extend((target, view) for view in views)

    why = walk(game, source, steps, f'hand: {how}', tables, reached)
    if why:
        print(f'stopped: {why}')
    if not standing and not harvest.close_window(game, row if row.get('event') else back, baseline):
        raise SystemExit('the state did not come back; nothing written')
    for window, view in noted:
        harvest.note_view(window, view)
    for record in records:
        record['seconds'] = round(time.time() - started, 1)
        path = os.path.join(harvest.OUT, record['window'] + '.json')
        if os.path.exists(path):
            aside = os.path.join(paths.PROJECT, 'harvest-{}-{}replaced'.format(
                time.strftime('%Y-%m-%d'), '' if harvest.player_record(record['window']) else 'console-'))
            os.makedirs(aside, exist_ok=True)
            os.replace(path, os.path.join(aside, record['window'] + '.json'))
        pathlib.Path(path).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"{record['window']}: {int(record['widgets'])} widgets, "
              f"{int(record['confirmed'])}/{int(record['boxes'])} text boxes confirmed")
    if standing and records and not why:
        last = records[-1]['window']
        keys = windowmap.keys_in_place(game, last)
        if isinstance(keys, str):
            raise SystemExit(keys)
        windowmap.store_window_keys(pid, {last: keys})
        print(f"standing now: {', '.join(sorted(game.state()[2]))}")


if __name__ == '__main__':
    terminal.utf8()
    main()
