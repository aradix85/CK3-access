"""What a chain step waits for, read off gui text written for the test, without the game.

On 22 October 2026 the filter windows had no chain route at all: a window declared as a type stood
in the map with an empty body, so its `visible` rule went unread, an instance's own name lost to
the name its type wrote first, and a condition that is a data function had no goal kind. Pressing
the button `filters` in the court window on Saru drew the court's own filter window.
"""
import pathlib

from tools.ck3 import guimap, openers

TYPES = ('types T {'
         ' type list_filter = window { name = "list_filter" visible = "[List.FiltersShown]" }'
         ' type ledger_filter = window { name = "ledger_filter" visible = "[GetVariableSystem.Exists(\'filters\')]" }'
         ' type filter_button = button { down = "[ List.FiltersShown ]" onclick = "[List.OnToggleFilters]" } }')
WINDOWS = ('window = { name = "court" filter_button = {} list_filter = { name = "court_filter" } }'
           ' window = { name = "finder" filter_button = {} list_filter = { name = "finder_filter" } }'
           ' window = { name = "ledger" button = { onclick = "[GetVariableSystem.Toggle(\'filters\')]" } }')


def tables(tmp_path: pathlib.Path) -> guimap.Tables:
    full = tmp_path / 'gui_windows.gui'
    full.write_text(TYPES + ' ' + WINDOWS, encoding='utf-8')
    rows: list[guimap.Row] = [('game', 'gui/windows.gui', str(full))]
    table, local = guimap.type_table(rows)
    return table, local, guimap.windows(rows, table), guimap.root_finder(table)


def test_an_instance_carries_its_own_name_and_a_type_its_own_rule(tmp_path: pathlib.Path) -> None:
    found = tables(tmp_path)
    assert {'court_filter', 'finder_filter', 'ledger_filter'} <= found[2].keys()
    assert openers.goal_of('ledger_filter', found) == ('variable', 'filters', None)
    assert openers.goal_of('court_filter', found) == ('state', '[List.FiltersShown]', 'court_filter')


def test_a_toggle_reaches_only_the_filter_window_inside_its_own_window(tmp_path: pathlib.Path) -> None:
    routes = {r['target']: r['sources'] for r in openers.chain_routes({'court', 'finder', 'ledger'},
                                                                       tables(tmp_path))}
    assert routes == {'court_filter': ['court'], 'finder_filter': ['finder'], 'ledger_filter': ['ledger']}
