r"""Windows by hand, along presses the files cannot route.

Usage:
    python -m tools.ck3.hand <pid> <source> <key | button:name | event:id> [<step> ...]

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
(`InteractionItem.OnClick@Vassal>2 more`). Wait for `target`, record it into the harvest, and
go on from it. A step without `=target` only changes the window standing open, as a tab does: the
hostage exchange sits in the war overview's peace terms, which the engine shows once a terms tab is
pressed. A window on the way that already has a record from a player route keeps it, as in the
chain round, with the view of its step written into it; the last target is always recorded. A
step's view is the one `goal:<window>` waits on, when its name is no window name. A record it
replaces goes aside into `harvest-<date>-replaced`, or into `harvest-<date>-console-replaced` when
the console made it. The state is put back, or nothing is written.

The route of every record says what was pressed, starting with `hand:`. Made on 22 October 2026,
after the filter presets, the settings window and the court appointment with its filter had each
taken a throwaway script: the appointment opens from a vacant court position, whose onclick calls
`CourtPositionType.OpenAppointWindow` and opens no view, so no chain on disk reaches it.
"""
import json
import os
import pathlib
import sys
import time
from collections.abc import Callable

from tools import paths, terminal
from tools.ck3 import guimap, harvest, openers, widgettree, windowmap

# One step as this tool takes it: what to press, and the window that comes up, or '' for a step that
# only changes the window standing open.
Step = tuple[str, str]


def route_of(route: str, window: str) -> tuple[str, str, list[Step]] | None:
    """(source, its press, the steps) of a `hand:` route as the record of `window` keeps it, so the
    route can be walked again (`windowmap.window_keys_round`). A step's target is the window the
    next step is pressed in, and the last one's is `window`.

    None for a route this tool cannot walk again: one with a step it does not take, such as a place
    on the map clicked with the real mouse, and one written before this tool."""
    if not route.startswith('hand: '):
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


def walk(game: windowmap.Game, source: str, steps: list[Step], route: str, tables: guimap.Tables,
         reached: Callable[[str, widgettree.Nodes, str, list[str]], None]) -> str | None:
    """In `source`, standing open, press each step in turn, and hand every window a step brings up
    to `reached`, with the route so far and the view its step waited on when that view's name is no
    window name. None once the last step is done, else why the walk stopped; the caller puts the
    state back."""
    known = tables[2]
    for step, target in steps:
        call, at, showing = step.partition('@')
        goal = (openers.goal_of(call[len('goal:'):], tables) if call.startswith('goal:')
                else openers.Goal('right', call[len('right:'):]) if call.startswith('right:')
                else openers.Goal('call', call))
        nodes, opened, spot, why = harvest.chain_press(game, source, goal, tables, showing if at else None)
        print(f"in {source} pressed {(spot['name'] or spot['class']) if spot else None}; "
              f"opened {', '.join(sorted(opened)) or 'nothing'}{'; ' + why if why else ''}")
        if spot is None or (target and target not in opened):
            return f"{step} in {source} brought up {', '.join(sorted(opened)) or 'nothing'}{'; ' + why if why else ''}"
        route += f', {step} in {source}'
        if target:
            reached(target, nodes, route, [goal.name] if goal.kind == 'view' and goal.name not in known else [])
            source = target
    return None


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    pid, source, how = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    steps = [step.partition('=')[::2] for step in sys.argv[4:]]
    game = windowmap.Game(pid)
    openers.game_classes = game.window_classes
    if not harvest.paused(game):
        raise SystemExit('the clock is running: pause the game first')
    windows: dict[str, windowmap.Route] = json.loads(pathlib.Path(harvest.MAP).read_text(encoding='utf-8'))['windows']
    row = windowmap.pressed(how)
    baseline = game.bare()
    header = harvest.header(game, baseline)
    back: windowmap.Route = {'click': True}
    tables = guimap.tables()
    started = time.time()
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
    if not harvest.close_window(game, row if row.get('event') else back, baseline):
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


if __name__ == '__main__':
    terminal.utf8()
    main()
