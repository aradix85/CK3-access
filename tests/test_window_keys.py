"""What the key round inside a window may press, decided off disk before any key goes in.

A key fires every widget of the window that declares it, under whatever binding name. On
22 October 2026 the gui files showed Alt+1 to Alt+3 as sub-tabs that in the activity window and
every event window also choose an event option, and the round had pressed them there.
"""
from tools.ck3 import windowmap

BOUND = {'sub_tab_1': 'alt+1', 'sub_tab_2': 'alt+2', 'sub_tab_3': 'alt+3', 'sub_tab_4': 'alt+4',
         'close_window': 'ESCAPE', 'close_tooltips': 'ESCAPE', 'go_back': 'B', 'go_back_3': 'mb4'}
SUB_TABS = "[Concatenate('sub_tab_', IntToString(PdxGuiWidget.GetIndexInDataModel))]"


def row(binding: str, calls: list[str]) -> windowmap.Binding:
    return {'binding': binding, 'keys': BOUND.get(binding), 'calls': calls,
            'view_only': bool(calls) and all(windowmap.VIEW_ONLY.match(c) for c in calls)}


def pressed(rows: list[windowmap.Binding]) -> list[str]:
    return [binding for binding, _, _ in windowmap.presses_for(rows, BOUND)]


def test_a_sub_tab_that_also_chooses_an_event_option_is_not_pressed() -> None:
    rows = [row(SUB_TABS, ['GetVariableSystem.Set', 'PdxGuiFoldOut.Unfold']),
            row(SUB_TABS, ['EventOption.Select', 'GetVariableSystem.Clear'])]
    assert pressed(rows) == []


def test_without_the_acting_widget_the_first_three_sub_tabs_are_pressed() -> None:
    assert pressed([row(SUB_TABS, ['GetVariableSystem.Set'])]) == ['sub_tab_1', 'sub_tab_2', 'sub_tab_3']


def test_the_same_key_under_another_name_blocks_it() -> None:
    rows = [row('close_window', ['ActivityWindow.Close']), row('close_tooltips', ['EventOption.Select'])]
    assert pressed(rows) == []


def test_in_place_the_keys_that_shut_the_window_go_last() -> None:
    """A window the clock brought up cannot be opened again, so what shuts it goes last: the message
    popup carries Escape, Enter and Alt+C, and the last two confirm it (read 7 November 2026)."""
    presses = [('close_window', 'ESCAPE', False), ('confirm', 'RETURN', False), ('tab_1', 'ctrl+1', False),
               ('confirm_2', 'alt+c', False), ('tab_2', 'ctrl+2', False)]
    assert [b for b, _, _ in windowmap.shutting_last(presses)] == ['tab_1', 'tab_2', 'confirm', 'confirm_2',
                                                                   'close_window']


def test_the_first_tab_goes_in_again_after_the_last_one() -> None:
    """A window remembers its tab: after a round that ended on the second tab of the dynastic cycle,
    the routes to its eras and catalysts found no button on the first (measured 9 November 2026)."""
    tab_1, tab_2, sub = ('tab_1', 'ctrl+1', False), ('tab_2', 'ctrl+2', False), ('sub_tab_1', 'alt+1', False)
    shut = ('close_window', 'ESCAPE', False)
    assert windowmap.steps_for([tab_2, tab_1, sub, shut]) == [
        (tab_2, None), (sub, 'tab_2'), (tab_1, None), (sub, 'tab_1'), (shut, None)]
    assert windowmap.steps_for([tab_1, tab_2, sub, shut]) == [
        (tab_1, None), (sub, 'tab_1'), (tab_2, None), (sub, 'tab_2'), (tab_1, None), (shut, None)]
    assert windowmap.steps_for([sub, shut]) == [(shut, None), (sub, None)]


def test_a_widget_without_an_onclick_blocks_nothing_and_a_mouse_button_is_no_key() -> None:
    rows = [row('go_back', ['OpenFromViewHistory']), row('go_back', []), row('go_back_3', ['OpenFromViewHistory'])]
    assert pressed(rows) == ['go_back']


def test_closing_the_tooltips_only_changes_the_view_and_a_key_goes_in_once() -> None:
    rows = [row('close_window', ['ActivityWindow.Close']), row('close_tooltips', ['CloseAllTooltips'])]
    assert pressed(rows) == ['close_window']
