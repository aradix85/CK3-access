"""The guard at every new derivation: every widget of the tree has to be in the full scan.

The scan skips the channel's own stacks and memory without a cache. If a patch ever puts widgets
there, the tree - walked by following pointers, skipping nothing - still holds them and the scan does
not, and the derivation has to stop and say so rather than carry on with a scan that missed some.
"""
import pytest

from tools.ck3 import derive


def test_a_tree_inside_the_scan_passes():
    derive.all_in_scan([1, 2, 3], {1, 2, 3, 4}, 'skipped 1 region of memory without a cache, 4 kB')


def test_a_widget_outside_the_scan_stops_and_says_what_was_skipped():
    with pytest.raises(SystemExit) as stop:
        derive.all_in_scan([1, 2, 5], {1, 2, 3}, 'skipped 1 region of memory without a cache, 4 kB')
    said = str(stop.value)
    assert said.startswith('1 widgets of the tree are not in the full scan')
    assert 'skipped 1 region of memory without a cache, 4 kB' in said


def test_nothing_skipped_is_said_too():
    with pytest.raises(SystemExit, match='which skipped nothing'):
        derive.all_in_scan([9], set(), '')
