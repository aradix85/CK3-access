"""The route to the tooltip root, checked without a game.

**What this is guarding.** The route is two reads from a global, stored per build. It may only be
believed while it leads to the root of the tree with a widget called `_tooltip_root_` beside it;
anything else has to derive it again, never hand back whatever lies at the old place. Memory is a
dictionary here, laid out the way the game laid it out on 21 October 2026.
"""
import pytest

from tools.ck3 import channel, derive, vtablemap

BASE, HOLDER, ROOT, TIP, OTHER = 0x7FF700000000, 0x25A6F1B27B0, 0x25A6F22AD30, 0x25A6F1B2C90, 0x25A7425F460
GLOBAL, SLOT, F_NAME = 0x5C7E3E8, 0xD0, 0x1B8


def name_block(name: str) -> bytes:
    """A name the way MSVC keeps a short string in the object: buffer, length, capacity 15."""
    return name.encode().ljust(16, b'\0') + len(name).to_bytes(8, 'little') + (15).to_bytes(8, 'little')


def memory(beside: int) -> dict[int, bytes]:
    return {BASE + GLOBAL: HOLDER.to_bytes(8, 'little'),
            HOLDER + SLOT: ROOT.to_bytes(8, 'little') + beside.to_bytes(8, 'little'),
            TIP: bytes(F_NAME) + name_block('_tooltip_root_'),
            OTHER: bytes(F_NAME) + name_block('_root_')}


def fields() -> derive.Fields:
    return {'key': 'build', 'parent': 0xE8, 'children': 0xF0, 'count': 0xFC, 'position': 0x118,
            'size': 0x128, 'name': F_NAME, 'text': 0x390, 'objects': 0, 'unreadable': 0, 'roots': 0,
            'gui_global': GLOBAL, 'root_slot': SLOT}


@pytest.fixture
def game(monkeypatch: pytest.MonkeyPatch) -> list[derive.Fields]:
    """A running game in a dictionary; what gets stored lands in the list it returns."""
    stored: list[derive.Fields] = []
    monkeypatch.setattr(vtablemap, 'module_base', lambda _pid: BASE)
    monkeypatch.setattr(derive, 'store', lambda found: stored.append(found.copy()))
    return stored


def use(monkeypatch: pytest.MonkeyPatch, laid_out: dict[int, bytes]) -> None:
    def read(address: int, count: int) -> bytes | None:
        for start, data in laid_out.items():
            if start <= address and address + count <= start + len(data):
                return data[address - start:address - start + count]
        return None
    monkeypatch.setattr(channel, 'read', read)


def test_a_route_that_still_holds_is_used_without_deriving(
        monkeypatch: pytest.MonkeyPatch, game: list[derive.Fields]) -> None:
    use(monkeypatch, memory(beside=TIP))

    def no_derivation(*_: int) -> tuple[int, int]:
        raise AssertionError('derived although the stored route still holds')

    monkeypatch.setattr(derive, '_tooltip_route', no_derivation)
    assert derive.tooltip_root(1, fields(), ROOT) == TIP
    assert game == []


def test_a_route_to_another_widget_is_derived_again(
        monkeypatch: pytest.MonkeyPatch, game: list[derive.Fields]) -> None:
    laid_out = memory(beside=OTHER)                  # the old place now holds a widget of another name
    laid_out[HOLDER + 0x40 + SLOT] = ROOT.to_bytes(8, 'little') + TIP.to_bytes(8, 'little')
    laid_out[BASE + GLOBAL + 0x10] = (HOLDER + 0x40).to_bytes(8, 'little')
    use(monkeypatch, laid_out)
    monkeypatch.setattr(derive, '_tooltip_route', lambda _pid, _root, _base, _name: (GLOBAL + 0x10, SLOT))

    assert derive.tooltip_root(1, fields(), ROOT) == TIP
    assert [(f['gui_global'], f['root_slot']) for f in game] == [(GLOBAL + 0x10, SLOT)]


def test_a_route_that_misses_the_root_of_the_tree_is_not_believed(
        monkeypatch: pytest.MonkeyPatch, game: list[derive.Fields]) -> None:
    use(monkeypatch, memory(beside=TIP))
    assert derive._tooltip_through(BASE + GLOBAL, SLOT, ROOT + 8, F_NAME) is None
    assert derive._tooltip_through(BASE + GLOBAL, SLOT + 8, ROOT, F_NAME) is None
    assert game == []
