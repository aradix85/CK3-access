"""How `tools.ck3.hand.route_of` reads a hand route back out of a record, so the key round can walk it.

A step's target is never written in the route, only the window the next step is pressed in; a step
pressed in the same window as the next one only changed the window standing open, as a tab does.
"""
from tools.ck3 import hand


def test_a_recorded_route_comes_back_as_steps() -> None:
    route = ("hand: F1, CharacterWindow.SetTab('family') in character_window, right:DefaultOnCharacterRightClick "
             'in character_window, InteractionItem.OnClick@Vassal>2 more in character_interaction_menu_window, '
             'InteractionItem.OnClick@Grant Court Position in character_interaction_menu_window')
    assert hand.route_of(route, 'court_task_interaction_window') == ('character_window', 'F1', [
        ("CharacterWindow.SetTab('family')", ''),
        ('right:DefaultOnCharacterRightClick', 'character_interaction_menu_window'),
        ('InteractionItem.OnClick@Vassal>2 more', ''),
        ('InteractionItem.OnClick@Grant Court Position', 'court_task_interaction_window')])
    assert hand.route_of('hand: F1, marry_off_interaction in character_window', 'marriage_interaction_window') == (
        'character_window', 'F1', [('marry_off_interaction', 'marriage_interaction_window')])
    assert hand.route_of('hand: F1, hover:tutorial_highlight_main_character_button in character_window, '
                         "'memories' in character_window", 'memories_window') == ('character_window', 'F1', [
        ('hover:tutorial_highlight_main_character_button', ''), ("'memories'", 'memories_window')])
    assert hand.route_of('hand: button:button_x', 'x_window') == ('x_window', 'button:button_x', [])
    assert hand.route_of('hand: event:debug.1000', 'character_event') == ('character_event', 'event:debug.1000', [])


def test_a_route_the_tool_cannot_walk_again_is_refused() -> None:
    assert hand.route_of('hand: F9, Hunt, Plan Hunt, Confirm, the capital', 'activity_planner') is None
    assert hand.route_of('hand: button:button_migrate, the county tier and Sarysyn on the map clicked with '
                         'the real mouse', 'window_migration') is None
    assert hand.route_of('shortcut F1', 'character_window') is None
