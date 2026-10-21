"""The numbering's derivation rules, checked on bytes laid out by hand, without a game.

**What this is guarding.** On 1.20 three rules each threw away a reading that was right
(21 October 2026): the record length was taken from the spacing of pointers, which in a culture
record repeat every 104 bytes; the key test refused digits, so the rites the game founds itself
(`dynamic_rite_151`) failed it; and two pointers that both lead to the same key were a tie.
"""
import struct

import pytest

from tools.ck3 import numbering


def block_of(record: int, rows: int, own_at: int) -> bytes:
    """Records of `record` bytes, each with its own number at `own_at`, and a decoy inside: small
    numbers 1, 2, 3 every 104 bytes, the way repeating inner structures look."""
    out = bytearray(record * rows)
    for n in range(rows):
        struct.pack_into('<I', out, n * record + own_at, n)
        for k, at in enumerate(range(200, record - 8, 104)):
            struct.pack_into('<I', out, n * record + at, k % 3 + 1)
    return bytes(out)


def test_the_record_length_comes_from_the_record_s_own_number() -> None:
    assert 1848 in numbering._own_number_strides(block_of(1848, 35, 16), 32)


def test_a_block_without_own_numbers_says_so() -> None:
    with pytest.raises(SystemExit, match='own number'):
        numbering._own_number_strides(bytes(8192), 32)


def test_a_key_the_game_founds_itself_is_well_formed() -> None:
    shaped = numbering._key_test({'roman_rite', 'mozarabic_church', 'syriac_dyophysite'})     # no digit
    assert shaped.match('dynamic_rite_151')
    assert not shaped.match('roman rite')


def test_two_pointers_to_the_same_keys_are_no_tie() -> None:
    same = {0: 'akan', 1: 'kru'}
    assert numbering._one_reading({(1848, 32, 304): same, (1848, 40, 24): dict(same)}) == (1848, 40, 24)


def test_two_pointers_to_different_keys_are_a_tie() -> None:
    with pytest.raises(SystemExit, match='read different ones'):
        numbering._one_reading({(1848, 32, 304): {0: 'akan'}, (1848, 40, 24): {0: 'kru'}})


def test_a_multiple_of_the_record_reads_fewer_rows_and_loses() -> None:
    readings = {(1848, 40, 24): {n: f'k{n}' for n in range(32)}, (3696, 40, 24): {n: f'k{n}' for n in range(17)}}
    assert numbering._one_reading(readings) == (1848, 40, 24)
