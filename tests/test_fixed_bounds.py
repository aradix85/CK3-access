"""The fixed bounds a patch can pass without a word, kept out, checked without a game.

**What this is guarding.** On 1.21.0.3 two fixed read sizes broke what the derivation itself would
have found: every widget was read to 0x420 bytes where a text box had grown past that, and 0x400
bytes were read behind a pointer in a character record where a field now lay at +0x408
(21 November 2026). Each rule below replaced such a number on 23 November 2026: a size is measured,
a walk is as long as what it walks, and what stays written down - the head of a database, the slots
of a block - stops with a sentence that names it.
"""
import struct

import numpy
import pytest

from tools.ck3 import anchor, channel, derive, mapdata, model, widgettree

VTABLE, F_PARENT = 0x7FF700001000, 0xE8
DB, TABLE, FIRST, SECOND = 0x20100000000, 0x20100001000, 0x20100100000, 0x20100300000
SHAPE: anchor.Model = {'number_field_in_record': 24, 'number_mask': 0xFFFFFF}


def use(monkeypatch: pytest.MonkeyPatch, laid_out: dict[int, bytes]) -> None:
    """The game's memory as a dictionary of where bytes start."""
    def read(address: int, count: int) -> bytes | None:
        for start, data in laid_out.items():
            if start <= address and address + count <= start + len(data):
                return data[address - start:address - start + count]
        return None
    monkeypatch.setattr(channel, 'read', read)


def test_a_chain_of_parents_ends_however_deep_and_a_circle_does_not() -> None:
    deep = {n: n - 1 for n in range(1, 101)}                   # a hundred under one another
    circle = {200: 201, 201: 202, 202: 200, 203: 200}           # three in a circle, one running into it
    assert derive._ending_at_a_root(deep | circle) == 100


def test_the_climb_to_the_root_is_as_long_as_the_tree_is_deep(monkeypatch: pytest.MonkeyPatch) -> None:
    top, step = 0x20000, 0x100

    def read(address: int, _count: int) -> bytes | None:
        widget, field = address & ~0xFF, address & 0xFF
        if not top <= widget < top + 60 * step:
            return None
        return (VTABLE if field == 0 else widget - step if widget > top else 0).to_bytes(8, 'little')

    monkeypatch.setattr(channel, 'read', read)
    monkeypatch.setattr(derive, 'tree', lambda root: {root: VTABLE})
    assert derive.to_root(top + 59 * step, F_PARENT, {VTABLE}) == (top, {top: VTABLE})


def test_a_parent_chain_that_comes_back_on_itself_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    one, other = 0x20000, 0x20100

    def read(address: int, _count: int) -> bytes:
        widget, field = address & ~0xFF, address & 0xFF
        return (VTABLE if field == 0 else other if widget == one else one).to_bytes(8, 'little')

    monkeypatch.setattr(channel, 'read', read)
    with pytest.raises(SystemExit, match='comes back on itself'):
        derive.to_root(one, F_PARENT, {VTABLE})


def test_objects_come_back_in_the_order_asked_and_the_unreadable_are_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    """`readmany` answers in order of address; the position proof takes the first families it meets."""
    monkeypatch.setattr(channel, 'readmany',
                        lambda addresses, size: {a: bytes(size) for a in sorted(addresses) if a != 5})
    chunks, failed = derive.chunks_of([9, 5, 3, 7], 4)
    assert (list(chunks), failed) == ([9, 3, 7], 1)


def test_the_size_of_an_object_is_the_commonest_distance_between_neighbours() -> None:
    pool = [0x1000 + n * 0x3C0 for n in range(10)] + [0x90000]
    assert derive.object_size(pool) == (0x3C0, 0.9)
    assert derive.object_size([0x1000]) == (0, 0.0)


def test_a_field_of_every_widget_lies_within_the_smallest_class(monkeypatch: pytest.MonkeyPatch) -> None:
    icons = {0x100000 + n * 0x3C0: 1 for n in range(120)}
    buttons = {0x900000 + n * 0x910: 2 for n in range(120)}
    few = {0x5000 + n * 0x100: 3 for n in range(20)}            # smaller, and too few to count
    monkeypatch.setattr(widgettree, 'class_map',
                        lambda _pid, objects: {address: str(kind) for address, kind in objects.items()})
    assert derive._base_size(1, icons | buttons | few) == 0x3C0
    with pytest.raises(SystemExit, match='cannot be measured'):
        derive._base_size(1, few)


def widget(parent: int, own: float, above: float) -> bytes:
    """A widget of 0x40 bytes: its parent, a pair that holds 1.0 twice, and its two scales."""
    data = bytearray(0x40)
    struct.pack_into('<Q', data, 0, parent)
    struct.pack_into('<ff', data, 0x10, 1.0, 1.0)
    struct.pack_into('<ff', data, 0x20, own, above)
    return bytes(data)


def test_the_scale_is_the_pair_a_scaled_parent_proves() -> None:
    plain = {1: widget(0, 1.0, 1.0)} | {n: widget(1, 1.0, 1.0) for n in range(10, 60)}
    scaled = plain | {2: widget(1, 0.8, 1.0), 3: widget(2, 1.0, 0.8)}
    assert derive._scale_field(scaled, 0) == 0x20
    with pytest.raises(SystemExit, match='nothing is scaled'):
        derive._scale_field(plain, 0)                           # two pairs hold 1.0 twice: no telling


def head(blocks: int, filled: int) -> bytes:
    data = bytearray(64)
    struct.pack_into('<Q', data, anchor.HEAD['table'], TABLE)
    struct.pack_into('<I', data, anchor.HEAD['blocks'], blocks)
    struct.pack_into('<I', data, anchor.HEAD['count'], filled)
    return bytes(data)


def records(stride: int, first: int) -> bytes:
    """The start of a block: records that carry their own number, a generation in the top byte."""
    data = bytearray(channel.READ_MOST)
    for slot in range(len(data) // stride):
        struct.pack_into('<I', data, slot * stride + SHAPE['number_field_in_record'], (3 << 24) | (first + slot))
    return bytes(data)


def test_a_head_that_does_not_read_as_one_stops_and_names_what_it_assumed(monkeypatch: pytest.MonkeyPatch) -> None:
    table = struct.pack('<2Q', FIRST, SECOND)
    use(monkeypatch, {DB: head(2, 1500), TABLE: table})
    assert model.block_table(DB) == ((FIRST, SECOND), 1500)
    for broken in ({DB: head(2, 5000), TABLE: table},                           # more than two blocks hold
                   {DB: head(2, 1500), TABLE: struct.pack('<2Q', FIRST, 7)},    # a block that is no pointer
                   {DB: head(0, 0), TABLE: table},
                   {DB: head(2, 1500)}):                                        # a table that cannot be read
        use(monkeypatch, broken)
        with pytest.raises(SystemExit, match='anchor.HEAD.*1024 slots.*heap pointer'):
            model.block_table(DB)


def test_a_record_longer_than_any_seen_is_still_measured(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, {FIRST: records(1400, 0)})                 # 472 bytes on 1.21; 1200 was the most tried
    assert model._record_length(FIRST, SHAPE) == 1400
    use(monkeypatch, {FIRST: bytes(channel.READ_MOST)})
    with pytest.raises(SystemExit, match=r'no record length up to 4094 bytes.*\+24'):
        model._record_length(FIRST, SHAPE)


def test_the_second_block_proves_the_slots_of_a_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anchor, 'load_model', lambda: dict(SHAPE))
    monkeypatch.setattr(anchor, 'database', lambda _pid: DB)
    laid_out = {DB: head(2, 1500), TABLE: struct.pack('<2Q', FIRST, SECOND),
                FIRST: records(472, 0), SECOND: records(472, model.BLOCK)}
    use(monkeypatch, laid_out)
    assert model._layout(1)[0]['record_length'] == 472
    use(monkeypatch, laid_out | {SECOND: records(472, 512)})
    with pytest.raises(SystemExit, match='no longer holds 1024 slots'):
        model._layout(1)


def test_two_provinces_touch_whatever_their_numbers() -> None:
    """20000 stood in the packing as the most a province number could be; 1.21 has 13474."""
    numbers = numpy.array([[1, 1, 25000], [30000, 30000, 25000]], dtype=numpy.int32)
    assert mapdata.touching(numbers) == {(1, 25000), (1, 30000), (25000, 30000)}
