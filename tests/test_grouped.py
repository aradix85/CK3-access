"""How a step tells rows with the same text apart by their heading (`openers.grouped`).

Every category of the interaction menu ends in an expander that says "2 more...", and only the one
under the wanted heading may be pressed: the step that took the first one expanded another
category, and the row it was after was then not in the tree (29 October 2026, Ghur played).
"""
from tools.ck3 import openers, pairing


def widget(address: int, parent: int, text: str | None = None) -> pairing.Harvested:
    return {'address': f'{address:x}', 'parent': f'{parent:x}', 'depth': 0, 'index': 0, 'class': None,
            'name': '', 'text': text, 'own_rect': [0, 0, 0, 0], 'screen_rect': [0, 0, 0, 0],
            'scale': [1, 1], 'alpha': 1.0, 'state': 0, 'clipped': False}


# The menu (1) holds a title (5) and three categories (2, 3, 4), each with its name and its rows,
# parents before children as the harvest writes them.
MENU: pairing.Record = {'tree': [
    widget(1, 0),
    widget(2, 1), widget(3, 1), widget(4, 1), widget(5, 1, 'Interactions'),
    widget(20, 2, 'Diplomacy'), widget(21, 2), widget(30, 3, 'Hostile'), widget(31, 3),
    widget(40, 4, 'Vassal'), widget(41, 4), widget(42, 4),
    widget(210, 21, '2 more...'), widget(310, 31, '2 more...'),
    widget(410, 41, 'Modify Vassal Contract'), widget(420, 42, '2 more...'),
]}
EXPANDERS = {21, 31, 42}


def test_the_expander_under_the_heading_is_the_one() -> None:
    assert [a for a in sorted(EXPANDERS) if openers.grouped(MENU, a, 'Vassal', EXPANDERS)] == [42]


def test_a_heading_above_several_of_them_tells_none_apart() -> None:
    assert not any(openers.grouped(MENU, a, 'Interactions', EXPANDERS) for a in EXPANDERS)
