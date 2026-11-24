"""The comparison of two harvest records says what a patch did to a window, without a game."""
from tools.ck3 import compare


def record(exe: str, names: list[str], route: str = 'shortcut F2') -> dict[str, object]:
    return {'window': 'my_realm_window', 'opened': True, 'exe': exe, 'route': route,
            'tree': [{'name': name} for name in names]}


def test_a_window_the_patch_left_alone_is_the_same() -> None:
    """Rows and nameless widgets do not count: a list is as long as the state makes it."""
    old = record('1.20', ['header', 'row', 'row', ''])
    new = record('1.21', ['header', 'row', 'row', 'row', 'row', ''])
    assert compare.verdict(old, new) == ('same', 'the same 2 names')


def test_a_rebuilt_window_names_what_came_and_went() -> None:
    old = record('1.20', ['header', 'holdings', 'close'])
    new = record('1.21', ['header', 'districts', 'build_queue'])
    assert compare.verdict(old, new) == (
        'changed', '2 names new (build_queue, districts), 2 gone (close, holdings), 1 kept')


def test_a_key_that_moved_is_said() -> None:
    old = record('1.20', ['header'], 'shortcut F5')
    new = record('1.21', ['header'], 'shortcut F6')
    assert compare.verdict(old, new) == ('same', 'the same 1 names; opened by shortcut F6, was shortcut F5')


def test_nothing_is_claimed_before_the_window_was_opened_again() -> None:
    old = record('1.20', ['header'])
    assert compare.verdict(old, None)[0] == 'waiting'
    assert compare.verdict(old, record('1.20', ['other']))[0] == 'waiting'


def test_a_route_that_no_longer_opens_it_is_lost() -> None:
    old = record('1.20', ['header'])
    refused = {'window': 'my_realm_window', 'opened': False, 'exe': '1.21', 'reason': 'did not open in 3 tries'}
    assert compare.verdict(old, refused) == ('lost', 'the route no longer opens it: did not open in 3 tries')
