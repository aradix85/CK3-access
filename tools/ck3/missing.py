r"""Which mapped windows have no record from a player's route yet, and how a player gets to each.

Usage:
    python -m tools.ck3.missing

Writes `reports\missing.json` and prints every group with its windows, and the views on disk. The
list is reckoned from the map (`reports\windows.json`), the harvest and the gui files every time it
runs, so it cannot age the way a list kept by hand does: on 24 October 2026 TE DOEN named 3 of the
199 windows without a player record, and covered most of the rest with one sentence.

A window has a player record when its harvest record opened it along a key, a click, a chain or by
hand. The console builds a window without its data context, so a console record does not count.

**The group says how a player gets there, read off the files; the first that fits wins.**
- `developer`: the developers' own tooling (`pairing.developer_window`); nobody plays in it.
- `multiplayer`: multiplayer, the social network and the Paradox account, by their gui folders
  and file names. This and the one above fall away (BRIEF.md, TE DOEN, the sessions per state).
- `decided`: a window with a decision of its own in `DECIDED`, with the reason and its date; the
  ones only luck, the AI or an uncertain search brings up carry `DEFERRED` and are taken when they
  come up in play.
- `event`: declared in `gui/event_windows/` - it opens when the game fires an event.
- `interaction`: declared in a `gui/interaction_*.gui` file - it opens from a character
  interaction, usually from the menu a right click on a portrait brings up.
- `chain`: the target of a chain route on disk (`openers.chain_routes`) from a window a player
  can open; a chain round on a state that has what the button needs reaches it.
- `no window route on disk`: no file names a call that opens it - the army, the map, the dynasty
  tree, menus. Some of these sit behind a view (below); for the rest a person has to find the way,
  with `tools.ck3.hand` once it is known.

**The views come apart from the groups**, because which window the engine puts behind a view is
not on disk: `OpenGameView('inventory')` names no window, and only a round that presses it sees
which one comes up (`brief\vensters.md`, the measured couplings). So the report lists every view a
button on disk opens, with the windows that carry such a button, and does not guess the window.

Beside its group every window carries its state: a console record, a record of a window that did
not open with the reason, drawn always (in every record's baseline), or never tried with the
reason the map gives.

**The keys no round has pressed come last:** a window with a player record whose files declare
keys a key round may press (`windowmap.presses_for`) and that has no row in
`reports\window_keys.json` yet. On 24 October 2026 TE DOEN still counted nine of those by hand
from two days before, and ten had no round.
"""
import json
import os
import pathlib
from typing import TypedDict

from tools import paths, terminal
from tools.ck3 import guimap, harvest, openers, pairing, windowmap

REPORT = os.path.join(paths.REPORTS, 'missing.json')
GROUPS = ('developer', 'multiplayer', 'decided', 'event', 'interaction', 'chain', 'no window route on disk')
# Her decision of 29 October 2026: a window only luck, the AI or a search that may not succeed brings
# up, which a player does not need harvested, waits until it comes up in play and is then taken by hand
# in one go; so does a window whose one attempt failed.
DEFERRED = ('deferred: only luck, the AI or an uncertain search brings it up; take it when it comes up '
            'in play (29 October 2026)')
# Windows a decision took out of the work, each with why and when. A group that falls away as a
# whole is a rule above, not a row here.
DECIDED = {
    'religion_window': 'no player route in 1.20; the Rites tab of Faith Details holds its lists '
                       '(measured 24 October 2026)',
    'rite_window': 'no player route in 1.20; the Rites tab of Faith Details holds its lists '
                   '(measured 24 October 2026)',
    'base_dialog': 'a template the game never builds under that name; its four instances each '
                   'carry a name of their own (read 23 October 2026)',
    'achievement_popup_window': 'drawn always, so in every capture (21 October 2026)',
    'layer_window': 'drawn always, so in every capture (21 October 2026)',
    'toolbars_window': 'the console draws it while it stands open, so in every console capture '
                       '(measured 21 October 2026)',
    'JominiMusicPlayerView': 'visible = no after inheritance: the console made it and it was not '
                             'drawn (read 24 October 2026)',
    'jomini_notification_sidebar': 'visible = no after inheritance: the console made it and it was '
                                   'not drawn (read 24 October 2026)',
} | dict.fromkeys((
    'character_ally_list_subview',                          # a war target that has allies
    'call_ally_interaction_notification_window',            # the four the AI sends the player
    'character_interaction_notification_window',
    'interfere_in_war_interaction_notification_window',
    'marriage_interaction_notification_window',
    'accolade_view',                                        # a stand with an accolade
    'create_accolade_view',
    'accolade_attribute_selection_view',
    'activity_list_detail_invite',                          # somebody invites the player
    'window_barbershop',                                    # no button on disk opens it
    'character_name_window',
    'colorpicker_window',
    'portrait_window',
    'window_situation',                                     # no situation of ours uses it
    'window_situation_participant_groups',
), DEFERRED)


class Missing(TypedDict):
    """One window without a player record: its gui file and where it stands."""
    file: str
    state: str


def multiplayer_window(path: str) -> bool:
    """Multiplayer, the social network or the Paradox account, by where the gui file sits and
    what it is called: `gui/social/`, `gui/pdx_account/`, `multiplayer_types.gui`,
    `frontend_mp_game_setup.gui`, `window_lobby_helper.gui`."""
    name = path.rsplit('/', 1)[-1]
    return (path.startswith(('gui/social/', 'gui/pdx_account/'))
            or 'multiplayer' in name or '_mp_' in name or 'lobby' in name)


def group_of(window: str, path: str, chained: set[str]) -> str:
    """The first group in `GROUPS` that fits this window."""
    if pairing.developer_window(window, path):
        return 'developer'
    if multiplayer_window(path):
        return 'multiplayer'
    if window in DECIDED:
        return 'decided'
    if path.startswith('gui/event_windows/'):
        return 'event'
    if path.rsplit('/', 1)[-1].startswith('interaction_'):
        return 'interaction'
    if window in chained:
        return 'chain'
    return 'no window route on disk'


def state_of(window: str, record: dict[str, object] | None, baseline: set[str],
             mapped: dict[str, object]) -> str:
    """Where a window without a player record stands, in the words the record or the map use."""
    if record is not None and record.get('opened'):
        return 'console record'
    if record is not None:
        return f"did not open: {record.get('reason')}"
    if window in baseline:
        return 'drawn always, so in every capture'
    return f"not tried: {mapped.get('reason') or 'no route'}"


def player_route(record: dict[str, object]) -> bool:
    """Did this record open its window the way a player does? A console record did not."""
    return bool(record.get('opened')) and not str(record.get('route', '')).startswith('GUI.CreateWidget')


def keys_not_pressed(played: set[str]) -> dict[str, list[str]]:
    """Window -> the bindings a key round would press in it, for every window with a player record
    and no row in `reports\\window_keys.json`. `window_bindings` files a key under the innermost
    window it sits in, so a nested window without a record comes back too, and is left out."""
    left = played - set(json.loads(pathlib.Path(windowmap.WINDOW_KEYS).read_text(encoding='utf-8')))
    bound = windowmap.shortcut_file()
    out = {}
    for window, rows in sorted(windowmap.window_bindings(left).items()):
        keys = windowmap.presses_for(rows, bound)
        if window in left and keys:
            out[window] = sorted({binding for binding, _, _ in keys})
    return out


def reckon() -> tuple[dict[str, dict[str, Missing]], dict[str, list[str]], dict[str, list[str]]]:
    """Every window of the map without a player record, by group; every view a button on disk
    opens, with the windows that carry such a button; and the windows whose keys no round pressed."""
    mapped: dict[str, dict[str, object]] = json.loads(pathlib.Path(harvest.MAP).read_text(encoding='utf-8'))['windows']
    records: dict[str, dict[str, object]] = {}
    baseline: set[str] = set()
    for found in pathlib.Path(paths.HARVEST).glob('*.json'):
        record = json.loads(found.read_text(encoding='utf-8'))
        records[str(record.get('window', found.stem))] = record
        baseline.update(record.get('baseline') or [])
    played = {w for w, r in records.items() if player_route(r)}
    keyed = {w for w, m in mapped.items() if m.get('shortcut')}
    routes = openers.chain_routes(played | keyed, guimap.tables())
    chained = {row['target'] for row in routes if row['target']}
    views = {row['view']: sorted(row['sources']) for row in routes if row['view'] and not row['target']}
    out: dict[str, dict[str, Missing]] = {group: {} for group in GROUPS}
    for window in sorted(set(mapped) - played):
        gui_file = str(mapped[window]['file'])
        out[group_of(window, gui_file, chained)][window] = {
            'file': gui_file, 'state': DECIDED.get(window) or state_of(window, records.get(window), baseline, mapped[window])}
    return out, views, keys_not_pressed(played)


def main() -> None:
    terminal.utf8()
    groups, views, keys = reckon()
    total = sum(len(windows) for windows in groups.values())
    report = {'harvest': pairing.harvested_at(), 'without a player record': total,
              'counts': {group: len(windows) for group, windows in groups.items()}, 'groups': groups,
              'views on disk': views, 'windows whose keys no round pressed': len(keys),
              'keys not pressed': keys}
    pathlib.Path(REPORT).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{total} mapped windows without a player record')
    for group, windows in groups.items():
        print(f'\n{group}: {len(windows)}')
        for window, row in windows.items():
            print(f"  {window} - {row['state']}")
    print(f'\nviews a button on disk opens: {len(views)}')
    for view, sources in views.items():
        print(f"  {view} - from {', '.join(sources)}")
    print(f'\nwindows with a player record whose keys no round pressed: {len(keys)}')
    for window, bindings in keys.items():
        print(f"  {window} - {', '.join(bindings)}")
    print(f'\nwritten to {os.path.relpath(REPORT, paths.PROJECT)}')


if __name__ == '__main__':
    main()
