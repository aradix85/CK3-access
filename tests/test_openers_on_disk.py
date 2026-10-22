"""Which widgets open a window, read from gui text the way `guimap` parses it, without the game.

Until 21 October 2026 `openers` counted braces line by line beside `guimap`, and it missed the
legends button because its name is written without quotes. Each case here is a shape that occurs
in the game's own files.
"""
from tools.ck3 import guimap, openers

WINDOWS = {'my_realm_window'}

MAIN_TAB = '''widget_hud_main_tab = {
    name = "tab_my_realm"
    blockoverride "maintab_button" {
        onclick = "[ToggleGameView('my_realm')]"
        shortcut = "my_realm_window"
    }
}'''
UNQUOTED = '''type create_legend_round_button = button_round {
    name = legends_button
    onclick = "[ToggleGameViewData( 'legend_creation', LegendSeed.Self )]"
}'''
UNDER = '''widget = {
    name = "holder"
    button = { onclick = "[OpenGameViewData('ledger')]" }
}'''


def rows(text: str) -> tuple[dict[str, openers.Button], dict[str, openers.Button]]:
    found: dict[str, openers.Button] = {}
    beneath: dict[str, openers.Button] = {}
    openers._settle({'key': None, 'arg': None, 'value': None, 'body': guimap.parse(text)},
                    'test.gui', WINDOWS, found, beneath)
    return found, beneath


def test_a_blockoverride_hands_its_call_to_the_named_widget() -> None:
    found, _ = rows(MAIN_TAB)
    assert found['tab_my_realm']['target'] == 'my_realm'


def test_a_name_without_quotes_is_a_name() -> None:
    found, _ = rows(UNQUOTED)
    assert found['legends_button']['target'] == 'legend_creation'


def test_a_nameless_button_is_answered_for_by_its_parent() -> None:
    found, beneath = rows(UNDER)
    assert not found and beneath['holder']['target'] == 'ledger' and beneath['holder']['under']


def test_every_onclick_fires_not_only_the_last() -> None:
    """Measured 21 October 2026: a click and a shortcut fire every onclick of a block, in order.
    The ledger's own shortcut button opens the ledger first and folds the menu after it."""
    first, second = "[ToggleGameView('ledger')]", "[GetVariableSystem.Clear( 'extra_buttons_expand' )]"
    source: guimap.Node = {'type': 'button_normal', 'children': [],
                           'attrs': [('name', 'ledger_shortcut'), ('onclick', first), ('onclick', second)]}
    assert openers.fires_for(source, openers.Goal('view', 'ledger'), ()) == ([first], [f'onclick: {second}'])
