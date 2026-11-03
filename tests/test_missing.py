"""How `tools.ck3.missing` sorts a window without a player record, read off its gui file alone.

The groups decide what work a window asks for, so a rule that puts an event among the windows
nothing opens sends the next session looking for a button that does not exist.
"""
import json

from tools.ck3 import harvest, missing, openers


def test_the_first_group_that_fits_wins() -> None:
    chained = {'great_project', 'debug_chained'}
    assert missing.group_of('watch_window', 'gui/debug/window_watch.gui', chained) == 'developer'
    assert missing.group_of('debug_chained', 'gui/window_x.gui', chained) == 'developer'
    assert missing.group_of('texture_node_window', 'gui/node_editor/node_editor.gui', set()) == 'developer'
    assert missing.group_of('chat_window', 'gui/social/chat_window_base.gui', set()) == 'multiplayer'
    assert missing.group_of('mainmenu_mp_game_setup', 'gui/frontend_mp_game_setup.gui', set()) == 'multiplayer'
    assert missing.group_of('religion_window', 'gui/window_faith.gui', {'religion_window'}) == 'decided'
    assert missing.group_of('letter_event', 'gui/event_windows/letter_event.gui', set()) == 'event'
    assert missing.group_of('declare_war_window', 'gui/interaction_declare_war.gui', set()) == 'interaction'
    assert missing.group_of('great_project', 'gui/window_great_project.gui', chained) == 'chain'
    assert missing.group_of('army_window', 'gui/window_army.gui', chained) == 'no window route on disk'


def test_a_window_says_where_it_stands() -> None:
    console = {'opened': True, 'route': 'GUI.CreateWidget gui/window_army.gui'}
    assert not harvest.player_route(console)
    assert harvest.player_route({'opened': True, 'route': 'chain PushButton in decisions_view'})
    assert not harvest.player_route({'opened': False, 'reason': 'did not open in 1 try'})
    assert missing.state_of('army_window', console, set(), {}) == 'console record'
    assert missing.state_of('houses_list', {'opened': False, 'reason': 'did not open in 1 try'}, set(),
                            {}) == 'did not open: did not open in 1 try'
    assert missing.state_of('layer_window', None, {'layer_window'}, {}) == 'drawn always, so in every capture'
    assert missing.state_of('node_window', None, set(), {'reason': 'a type definition'}) == 'not tried: a type definition'


def test_a_view_is_reached_once_its_windows_have_player_records() -> None:
    # Records as the harvest keeps them on disk; only the fields the rule reads.
    records: dict[str, harvest.Record | harvest.Refused] = json.loads(json.dumps({
        'faith_window': {'window': 'faith_window', 'opened': True, 'route': 'shortcut alt+R', 'views': ['faith']},
        'holy_site_window': {'window': 'holy_site_window', 'opened': True,
                             'route': 'chain PushButton in faith_window', 'views': ['holy_site']},
        'diarchy_window': {'window': 'diarchy_window', 'opened': True,
                           'route': 'click open_future_diarchy_tutorial_uses_this', 'views': []},
        'inventory_view': {'window': 'inventory_view', 'opened': True,
                           'route': 'GUI.CreateWidget gui/window_inventory.gui', 'views': []},
        'kill_list': {'window': 'kill_list', 'opened': False, 'reason': 'did not open in 1 try'},
    }))
    buttons: list[openers.Button] = [
        {'via': 'onclick', 'target': 'diarchy', 'widget': 'w', 'file': 'f', 'opens': ['diarchy_window']},
        # Its window has only a console record, so a round still has to bring it up along the view.
        {'via': 'onclick', 'target': 'inventory', 'widget': 'w', 'file': 'f', 'opens': ['inventory_view']},
        # A button that refused, and one that opens by its shortcut and names a window, not a view.
        {'via': 'onclick', 'target': 'memories', 'widget': 'w', 'file': 'f', 'opens': None},
        {'via': 'shortcut', 'target': 'court_window', 'widget': 'w', 'file': 'f', 'opens': ['court_window']},
    ]
    assert harvest.reached_views(records, buttons) == {
        'faith': ['faith_window'], 'holy_site': ['holy_site_window'], 'diarchy': ['diarchy_window']}
