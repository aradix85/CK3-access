"""The interaction menu read by its tree: a row's category, and one row told apart by its heading.

Every category of the menu ends in an expander that says "2 more...", and only the one under the
wanted heading may be pressed: the step that took the first one expanded another category, and the
row it was after was then not in the tree (29 October 2026, Ghur played). Sorting rows by height put
them under the wrong category once a category above them was expanded.
"""
from tools.ck3 import interactions, openers, pairing


def widget(address: int, parent: int, text: str | None = None, name: str = '') -> pairing.Harvested:
    return {'address': f'{address:x}', 'parent': f'{parent:x}', 'depth': 0, 'index': 0, 'class': None,
            'name': name, 'text': text, 'own_rect': [0, 0, 0, 0], 'screen_rect': [0, 0, 0, 0],
            'scale': [1, 1], 'alpha': 1.0, 'state': 0, 'clipped': False}


# The menu (1) holds a title (5), three categories (2, 3, 4), each with its name and its rows, and
# the flyout an expander opens beside them (6), parents before children as the harvest writes them.
MENU: pairing.Record = {'tree': [
    widget(1, 0),
    widget(2, 1), widget(3, 1), widget(4, 1), widget(5, 1, 'Interactions'), widget(6, 1),
    widget(20, 2, 'Diplomacy', 'category_name'), widget(21, 2), widget(30, 3, 'Hostile', 'category_name'),
    widget(31, 3), widget(40, 4, 'Vassal', 'category_name'), widget(41, 4), widget(42, 4), widget(60, 6),
    widget(210, 21, '2 more...'), widget(310, 31, '2 more...'),
    widget(410, 41, 'Modify Vassal Contract'), widget(420, 42, '2 more...'),
    widget(600, 60, 'Grant Court Position'),
]}
EXPANDERS = {21, 31, 42}


def test_the_expander_under_the_heading_is_the_one() -> None:
    assert [a for a in sorted(EXPANDERS) if openers.grouped(MENU, a, 'Vassal', EXPANDERS)] == [42]


def test_a_heading_above_several_of_them_tells_none_apart() -> None:
    assert not any(openers.grouped(MENU, a, 'Interactions', EXPANDERS) for a in EXPANDERS)


def test_a_row_belongs_to_the_category_in_its_own_group() -> None:
    assert [interactions.category_of(MENU, a) for a in (21, 31, 41, 42)] == \
        ['Diplomacy', 'Hostile', 'Vassal', 'Vassal']


def test_a_row_of_the_flyout_belongs_to_no_group() -> None:
    assert interactions.category_of(MENU, 60) is None
