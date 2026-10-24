"""How `tools.ck3.missing` sorts a window without a player record, read off its gui file alone.

The groups decide what work a window asks for, so a rule that puts an event among the windows
nothing opens sends the next session looking for a button that does not exist.
"""
from tools.ck3 import missing


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
    assert not missing.player_route(console)
    assert missing.player_route({'opened': True, 'route': 'chain PushButton in decisions_view'})
    assert not missing.player_route({'opened': False, 'reason': 'did not open in 1 try'})
    assert missing.state_of('army_window', console, set(), {}) == 'console record'
    assert missing.state_of('houses_list', {'opened': False, 'reason': 'did not open in 1 try'}, set(),
                            {}) == 'did not open: did not open in 1 try'
    assert missing.state_of('layer_window', None, {'layer_window'}, {}) == 'drawn always, so in every capture'
    assert missing.state_of('node_window', None, set(), {'reason': 'a type definition'}) == 'not tried: a type definition'
