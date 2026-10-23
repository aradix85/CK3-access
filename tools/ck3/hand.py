r"""Windows by hand, along presses the files cannot route.

Usage:
    python -m tools.ck3.hand <pid> <source> <key | button:name> <step> [<step> ...]

Opens `source` by its key, or by pressing a button by name, as the migration window opens from the
nomad's bar. Then per step, written `<call>=<target>`: press inside the window standing open the
first widget whose onclick carries `call`, or for `goal:<window>` what the files say reaches that
window; wait for `target`, record it into the harvest, and go on from it. A step without `=target`
only changes the window standing open, as a tab does: the hostage exchange sits in the war
overview's peace terms, which the engine shows once a terms tab is pressed. A record it replaces
goes aside into `harvest-<date>-replaced`. The state is put back, or nothing is written.

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

from tools import paths, terminal
from tools.ck3 import derive, guimap, harvest, model, openers, windowmap


def main() -> None:
    if len(sys.argv) < 5:
        raise SystemExit(__doc__)
    pid, source, how = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    steps = [step.partition('=')[::2] for step in sys.argv[4:]]
    game = windowmap.Game(pid)
    openers.game_classes = game.window_classes
    if not harvest.paused(game):
        raise SystemExit('the clock is running: pause the game first')
    windows: dict[str, windowmap.Route] = json.loads(pathlib.Path(harvest.MAP).read_text(encoding='utf-8'))['windows']
    row: windowmap.Route = ({'click': True, 'button': how[len('button:'):], 'drawn': True}
                            if how.startswith('button:') else {'shortcut': how})
    baseline = game.bare()
    nodes = game.tree()
    player, player_name = model.player(pid)
    header: harvest.Header = {'measured': time.strftime('%Y-%m-%d %H:%M'), 'exe': derive.build_key(),
                              'game_date': harvest.game_date(nodes), 'baseline': sorted(baseline),
                              'player': player, 'player_name': player_name,
                              'fields': {k: v for k, v in game.fields.items() if isinstance(v, int)}}
    back: windowmap.Route = {'click': True}
    tables = guimap.tables()
    started = time.time()
    opened_source, attempts = harvest.open_window(game, source, row, baseline)
    if opened_source is None:
        harvest.close_window(game, back, baseline)
        raise SystemExit(f'{source} did not open along {how}')
    route = f'hand: {how}'
    records: list[harvest.Record] = []
    for call, target in steps:
        goal = (openers.goal_of(call[len('goal:'):], tables) if call.startswith('goal:')
                else openers.Goal('call', call))
        nodes, opened, spot, why = harvest.chain_press(game, source, goal, tables)
        print(f"in {source} pressed {(spot['name'] or spot['class']) if spot else None}; "
              f"opened {', '.join(sorted(opened)) or 'nothing'}{'; ' + why if why else ''}")
        if not target and spot is not None:
            route += f', {call} in {source}'
            continue
        if target not in opened:
            break
        route += f', {call} in {source}'
        records.append(harvest.record_window(game, target, nodes, header, route, attempts,
                                             (windows.get(target) or {}).get('file'), started))
        source = target
    if not harvest.close_window(game, back, baseline):
        raise SystemExit('the state did not come back; nothing written')
    aside = os.path.join(paths.PROJECT, 'harvest-{}-replaced'.format(time.strftime('%Y-%m-%d')))
    for record in records:
        record['seconds'] = round(time.time() - started, 1)
        path = os.path.join(harvest.OUT, record['window'] + '.json')
        if os.path.exists(path):
            os.makedirs(aside, exist_ok=True)
            os.replace(path, os.path.join(aside, record['window'] + '.json'))
        pathlib.Path(path).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f"{record['window']}: {int(record['widgets'])} widgets, "
              f"{int(record['confirmed'])}/{int(record['boxes'])} text boxes confirmed")


if __name__ == '__main__':
    terminal.utf8()
    main()
