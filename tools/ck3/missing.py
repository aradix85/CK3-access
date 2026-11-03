r"""Which mapped windows have no record from a player's route yet, and how a player gets to each.

Usage:
    python -m tools.ck3.missing

Writes `reports\missing.json` and prints the total with how many are still to do for play, every
group with its windows, the views on disk and the keys no round pressed. The
list is reckoned from the map (`reports\windows.json`), the harvest and the gui files every time it
runs, so it cannot age the way a list kept by hand does: on 24 October 2026 TE DOEN named 3 of the
199 windows without a player record, and covered most of the rest with one sentence.

A window has a player record when its harvest record opened it along a key, a click, a chain or by
hand. The console builds a window without its data context, so a console record does not count.

**The group says how a player gets there, read off the files; the first that fits wins.**
- `developer`: the developers' own tooling (`pairing.developer_window`); nobody plays in it.
- `multiplayer`: multiplayer, the social network and the Paradox account, by their gui folders
  and file names.
- `decided`: a window with a decision of its own in `DECIDED`, with the reason and its date.
  `CLOSED` marks one that only luck, the AI or an uncertain search brings up, or whose one attempt
  failed; `NOT_FOR_PLAY` one a blind player gains nothing from. Both are reopened only on negative
  feedback from players.
- `event`: declared in `gui/event_windows/` - it opens when the game fires an event.
- `interaction`: declared in a `gui/interaction_*.gui` file - it opens from a character
  interaction, usually from the menu a right click on a portrait brings up.
- `chain`: the target of a chain route on disk (`openers.chain_routes`) from a window a player
  can open; a chain round on a state that has what the button needs reaches it.
- `no window route on disk`: no file names a call that opens it - the army, the map, the dynasty
  tree, menus. Some of these sit behind a view (below); for the rest a person has to find the way,
  with `tools.ck3.hand` once it is known.

The first three fall away (`FALL_AWAY`); the report counts every other window as still to do for play.

**The views come apart from the groups**, because which window the engine puts behind a view is
not on disk: `OpenGameView('inventory')` names no window, and only a round that presses it sees
which one comes up. So the report lists every view a button on disk opens that no round has
reached yet, with the windows that carry such a button, and does not guess the window; a view a
round reached comes with the windows it brought up (`harvest.reached_views`).

Beside its group every window carries its state: a console record, a record of a window that did
not open with the reason, drawn always (in every record's baseline), never tried with the reason
the map gives, or, for a window in `DECIDED`, the reason given there.

**The keys no round has pressed come last:** a window with a player record whose files declare
keys a key round may press (`windowmap.presses_for`) and that has no row in
`reports\window_keys.json` yet. On 24 October 2026 TE DOEN still counted nine of those by hand
from two days before, and ten had no round.
"""
import json
import os
import pathlib
from collections.abc import Mapping
from typing import TypedDict

from tools import paths, terminal
from tools.ck3 import guimap, harvest, openers, pairing, windowmap

REPORT = os.path.join(paths.REPORTS, 'missing.json')
GROUPS = ('developer', 'multiplayer', 'decided', 'event', 'interaction', 'chain', 'no window route on disk')
# The groups that fall away; every other window still matters for play, and that count is the one she
# hears (her request, 2 November 2026).
FALL_AWAY = ('developer', 'multiplayer', 'decided')
# Her decisions of 29 October and 2 November 2026: a window only luck, the AI or a search that may not
# succeed brings up, and a window whose one attempt failed, is done without a harvest when a player
# does not need it; it is opened again only when players report a problem.
CLOSED = ('closed without a harvest: one attempt failed, or only luck, the AI or an uncertain search '
          'brings it up; reopened only on negative feedback from players (2 November 2026)')
# Her decision of 2 November 2026: what a blind player gains nothing from is done as well, and said so.
NOT_FOR_PLAY = ('not important for play: appearance, customisation, achievements or setup a blind player '
                'gains nothing from; reopened only on negative feedback from players (2 November 2026)')
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
    'window_situation',                                     # no situation of ours uses it
    'window_situation_participant_groups',
    'create_ceremonial_claimant_faction_against_interaction_window',  # off for Omiwa (2 November 2026)
), CLOSED) | dict.fromkeys((
    'window_barbershop', 'character_name_window', 'colorpicker_window', 'portrait_window',
    'coa_window', 'dynasty_customization_window', 'dynasty_house_customization_window',
    'title_customization_window', 'window_court_visuals', 'reforge_artifact_window', 'artifact_kill_list',
    'ruler_designer', 'load_ruler_window', 'save_ruler_window', 'game_rules', 'game_rules_preset',
    'achievements_window', 'dlc_info', 'tutorial_window',
), NOT_FOR_PLAY)


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


def state_of(window: str, record: Mapping[str, object] | None, baseline: set[str],
             mapped: dict[str, object]) -> str:
    """Where a window without a player record stands, in the words the record or the map use."""
    if record is not None and record.get('opened'):
        return 'console record'
    if record is not None:
        return f"did not open: {record['reason']}"
    if window in baseline:
        return 'drawn always, so in every capture'
    return f"not tried: {mapped['reason']}"


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


def reckon() -> tuple[dict[str, dict[str, Missing]], dict[str, list[str]], dict[str, list[str]],
                      dict[str, list[str]]]:
    """Every window of the map without a player record, by group; every view a button on disk
    opens that no round reached, with the windows that carry such a button; every one a round
    reached, with the windows it brought up; and the windows whose keys no round pressed."""
    mapped: dict[str, dict[str, object]] = json.loads(pathlib.Path(harvest.MAP).read_text(encoding='utf-8'))['windows']
    records = harvest.records_on_disk()
    baseline: set[str] = set()
    for record in records.values():
        if record['opened']:
            baseline.update(record['baseline'])
    played = {w for w, r in records.items() if harvest.player_route(r)}
    keyed = {w for w, m in mapped.items() if m.get('shortcut')}
    routes = openers.chain_routes(played | keyed, guimap.tables())
    chained = {row['target'] for row in routes if row['target']}
    on_disk = {row['view']: sorted(row['sources']) for row in routes if row['view'] and not row['target']}
    reached = harvest.reached_views(records, harvest.measured_buttons())
    out: dict[str, dict[str, Missing]] = {group: {} for group in GROUPS}
    for window in sorted(set(mapped) - played):
        gui_file = str(mapped[window]['file'])
        out[group_of(window, gui_file, chained)][window] = {
            'file': gui_file, 'state': DECIDED.get(window) or state_of(window, records.get(window), baseline, mapped[window])}
    return (out, {v: s for v, s in on_disk.items() if v not in reached},
            {v: reached[v] for v in on_disk if v in reached}, keys_not_pressed(played))


def main() -> None:
    terminal.utf8()
    groups, views, reached, keys = reckon()
    total = sum(len(windows) for windows in groups.values())
    to_do = sum(len(windows) for group, windows in groups.items() if group not in FALL_AWAY)
    report = {'harvest': pairing.harvested_at(), 'without a player record': total,
              'still to do for play': to_do,
              'counts': {group: len(windows) for group, windows in groups.items()}, 'groups': groups,
              'views not reached': views, 'views reached': reached,
              'windows whose keys no round pressed': len(keys), 'keys not pressed': keys}
    pathlib.Path(REPORT).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{total} mapped windows without a player record, {to_do} of them still to do for play')
    for group, windows in groups.items():
        print(f'\n{group}: {len(windows)}')
        for window, row in windows.items():
            print(f"  {window} - {row['state']}")
    print(f'\nviews a button on disk opens that no round reached: {len(views)}')
    for view, sources in views.items():
        print(f"  {view} - from {', '.join(sources)}")
    print(f'\nviews a round reached: {len(reached)}')
    for view, opened in reached.items():
        print(f"  {view} - {', '.join(opened)}")
    print(f'\nwindows with a player record whose keys no round pressed: {len(keys)}')
    for window, bindings in keys.items():
        print(f"  {window} - {', '.join(bindings)}")
    print(f'\nwritten to {os.path.relpath(REPORT, paths.PROJECT)}')


if __name__ == '__main__':
    main()
