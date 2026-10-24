"""What a chain step waits for, read off gui text written for the test, without the game.

On 22 October 2026 the filter windows had no chain route at all: a window declared as a type stood
in the map with an empty body, so its `visible` rule went unread, an instance's own name lost to
the name its type wrote first, and a condition that is a data function had no goal kind. Pressing
the button `filters` in the court window on Saru drew the court's own filter window.
"""
import pathlib

import pytest

from tools.ck3 import guimap, onscreen, openers, pairing

TYPES = ('types T {'
         ' type list_filter = window { name = "list_filter" visible = "[List.FiltersShown]" }'
         ' type ledger_filter = window { name = "ledger_filter" visible = "[GetVariableSystem.Exists(\'filters\')]" }'
         ' type filter_button = button { down = "[ List.FiltersShown ]" onclick = "[List.OnToggleFilters]" }'
         ' type sub_window = window { name = "sub_window" }'
         ' type editor = window { name = "editor"'
         ' visible = "[And( Not(VariableSystem.Exists(\'shot\')), VariableSystem.Exists(\'editor\') )]" } }')
WINDOWS = ('window = { name = "court" filter_button = {} list_filter = { name = "court_filter" } }'
           ' window = { name = "finder" filter_button = {} list_filter = { name = "finder_filter" } }'
           ' window = { name = "character"'
           ' widget = { datacontext = "[W.GetCourt]" filter_button = { name = "court_button" } }'
           ' widget = { datacontext = "[W.GetVassals]" filter_button = { name = "vassal_button" } }'
           ' list_filter = { name = "its_court_filter" datacontext = "[W.GetCourt]" }'
           ' list_filter = { name = "its_vassal_filter" datacontext = "[W.GetVassals]" } }'
           ' window = { name = "ledger" button = { onclick = "[GetVariableSystem.Toggle(\'filters\')]" } }'
           ' window = { name = "holder" sub_window = { visible = "[ Sub.IsVisible ]" }'
           ' button = { onclick = "[Sub.Close]" } button = { onclick = "[Sub.Toggle]" } }'
           ' window = { name = "matchmaker" widget = { datacontext = "[M.GetList]"'
           ' datacontext = "[List.Filtered]" filter_button = { name = "match_button" } }'
           ' list_filter = { name = "match_filter" datacontext = "[M.GetList]" } }')
# Two tabs without a key, and the filter button of the second list behind the second tab and behind
# a condition that no button declares - the shape of the subordinates in the character window.
TABBED = '''window = { name = "tabbed"
    button = { name = "tab_a" down = "[W.IsTabShown('a')]" onclick = "[W.SetTab('a')]" }
    button = { name = "tab_b" down = "[W.IsTabShown('b')]" onclick = "[W.SetTab('b')]" }
    widget = { visible = "[W.AreNoneExpanded]"
        widget = { visible = "[ W.IsTabShown('b') ]" datacontext = "[W.GetSubordinates]" filter_button = {} }
        list_filter = { name = "its_b_filter" datacontext = "[W.GetSubordinates]" } } }'''


def tables(tmp_path: pathlib.Path) -> guimap.Tables:
    full = tmp_path / 'gui_windows.gui'
    full.write_text(TYPES + ' ' + WINDOWS + ' ' + TABBED, encoding='utf-8')
    rows: list[guimap.Row] = [('game', 'gui/windows.gui', str(full))]
    table, local = guimap.type_table(rows)
    return table, local, guimap.windows(rows, table), guimap.root_finder(table)


def test_an_instance_carries_its_own_name_and_a_type_its_own_rule(tmp_path: pathlib.Path) -> None:
    found = tables(tmp_path)
    assert {'court_filter', 'finder_filter', 'ledger_filter'} <= found[2].keys()
    assert openers.goal_of('ledger_filter', found) == openers.Goal('variable', 'filters')
    assert openers.goal_of('editor', found) == openers.Goal('variable', 'editor')
    assert openers.goal_of('court_filter', found) == openers.Goal('state', '[List.FiltersShown]', 'court_filter')


def test_a_toggle_reaches_only_the_filter_window_inside_its_own_window(tmp_path: pathlib.Path) -> None:
    routes = {r['target']: r['sources'] for r in openers.chain_routes({'court', 'finder', 'ledger'},
                                                                       tables(tmp_path))}
    assert routes == {'court_filter': ['court'], 'finder_filter': ['finder'], 'ledger_filter': ['ledger']}


def test_the_data_context_picks_the_button_where_one_window_holds_two_lists(tmp_path: pathlib.Path) -> None:
    found = tables(tmp_path)
    goal = openers.goal_of('its_vassal_filter', found)
    assert goal.context == '[W.GetVassals]'
    tree = guimap.window('character', found[0], found[1], found[2])
    pressed = []
    stack: list[tuple[guimap.Node, tuple[str, ...]]] = [(tree, ())]
    while stack:
        node, context = stack.pop()
        context = context + guimap.contexts(node)
        stack.extend((child, context) for child in node['children'])
        if openers.fires_for(node, goal, context)[0]:
            pressed.append(guimap.attribute(node, 'name'))
    assert pressed == ['vassal_button']


def test_a_widget_passes_on_every_data_context_it_sets(tmp_path: pathlib.Path) -> None:
    """The candidate list of the marriage window sets the list and then a filter of it, and its
    filter window carries the list: only the first context reaches the button (24 October 2026)."""
    routes = {r['target']: r['sources'] for r in openers.chain_routes({'matchmaker'}, tables(tmp_path))}
    assert routes == {'match_filter': ['matchmaker']}


def test_a_hidden_trigger_is_shown_by_the_button_whose_down_hides_it(tmp_path: pathlib.Path) -> None:
    found = tables(tmp_path)
    goal = openers.goal_of('its_b_filter', found)
    assert openers.unhiding('tabbed', goal, found) == [openers.Goal('state', "[W.IsTabShown('b')]")]


def test_the_one_use_of_a_window_type_carries_its_condition(tmp_path: pathlib.Path) -> None:
    found = tables(tmp_path)
    assert openers.goal_of('sub_window', found) == openers.Goal('state', '[Sub.IsVisible]', 'sub_window')
    routes = {r['target']: r['sources'] for r in openers.chain_routes({'holder'}, found)}
    assert routes == {'sub_window': ['holder']}


def test_a_call_opens_the_state_its_object_is_asked_about() -> None:
    tenet, doctrine = '[ActivityPlanner.IsSelectingTenet]', '[ActivityPlanner.IsSelectingDoctrine]'
    call = '[ActivityPlanner.OpenSelectionForTenetIndex( (int32)0 )]'
    assert openers.opens_state(call, tenet) and not openers.opens_state(call, doctrine)
    assert openers.opens_state('[TenetWindow.Toggle]', '[TenetWindow.IsVisible]')
    assert not openers.opens_state('[TenetWindow.Close]', '[TenetWindow.IsVisible]')
    assert not openers.opens_state('[RiteWindow.Toggle]', '[TenetWindow.IsVisible]')
    by_hand = openers.Goal('call', 'OpenAppointWindow')
    assert openers.reaches('[CourtPositionType.OpenAppointWindow( CourtPositionsWindow.CourtOwner.Self )]', by_hand)
    assert not openers.reaches('[CourtPositionType.Close]', by_hand)


def test_a_row_is_told_from_its_siblings_by_what_it_shows() -> None:
    def widget(address: str, parent: str, text: str | None) -> pairing.Harvested:
        return {'address': address, 'parent': parent, 'depth': 1, 'index': 0, 'class': 'Textbox',
                'name': '', 'text': text, 'own_rect': [0.0, 0.0, 1.0, 1.0],
                'screen_rect': [0.0, 0.0, 1.0, 1.0], 'scale': [1.0, 1.0], 'alpha': 1.0, 'state': 0,
                'clipped': False}
    tree = [widget('a', '0', None), widget('c', '0', None), widget('b', 'a', 'Grand Wedding'),
            widget('d', 'c', None), widget('e', 'd', 'Ecumenical Council')]
    record: pairing.Record = {'tree': tree}
    assert openers.shows(record, 0xc, 'council') and not openers.shows(record, 0xa, 'council')


def test_a_click_lands_as_near_the_middle_as_it_can(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(onscreen, 'DRAWING_AREA', (1920, 1200))
    def button(address: str, rect: list[float]) -> openers.Clickable:
        widget: pairing.Harvested = {
            'address': address, 'parent': '0', 'depth': 1, 'index': 0, 'class': 'PushButton',
            'name': '', 'text': None, 'own_rect': rect, 'screen_rect': rect, 'scale': [1.0, 1.0],
            'alpha': 1.0, 'state': 0, 'clipped': False}
        return ((0,), rect[0], rect[1], rect[2], rect[3], widget)
    card = [100.0, 100.0, 168.0, 220.0]
    point = openers.reachable_point([button('a', card)], 0xa, card)
    assert point is not None and abs(point[0] - 184) <= 6 and abs(point[1] - 210) <= 6
    # A later button over the middle takes it there; the nearest point still the card's own wins.
    covered = openers.reachable_point([button('a', card), button('b', [150.0, 180.0, 68.0, 60.0])], 0xa, card)
    assert covered is not None and not (150 <= covered[0] < 218 and 180 <= covered[1] < 240)
    assert abs(covered[0] - 184) + abs(covered[1] - 210) < 60
    # The peace terms tabs of the war overview hang 7 points past the bottom (23 October 2026):
    # with the middle covered, the nearest point below the drawing area would win, and reach nothing.
    tab = [1059.0, 1157.0, 196.0, 50.0]
    low = openers.reachable_point([button('a', tab), button('b', [1100.0, 1160.0, 120.0, 40.0])], 0xa, tab)
    assert low is not None and low[1] < 1200
