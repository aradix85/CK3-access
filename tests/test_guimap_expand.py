"""How `guimap` expands a window, on gui text written for the test, without the game.

Measured 21 October 2026 on 1.20.1.2, all silent until then: a `local_template` of cooltip.gui that
three windows in other files pull in, the windows declared as a type built twice over, and two
windows whose expansion repeats itself without end.
"""
import pathlib

import pytest

from tools.ck3 import guimap


def window(tmp_path: pathlib.Path, name: str, files: dict[str, str]) -> guimap.Node:
    rows: list[guimap.Row] = []
    for virtual, text in files.items():
        full = tmp_path / virtual.replace('/', '_')
        full.write_text(text, encoding='utf-8')
        rows.append(('game', virtual, str(full)))
    table, local = guimap.type_table(rows)
    return guimap.window(name, table, local, guimap.windows(rows, table))


def names(node: guimap.Node) -> list[str]:
    own = guimap.attribute(node, 'name')
    return ([own] if own else []) + [name for child in node['children'] for name in names(child)]


def test_a_local_template_is_looked_up_where_it_is_used(tmp_path: pathlib.Path) -> None:
    tree = window(tmp_path, 'w', {
        'gui/shared.gui': 'local_template part { textbox = { name = "from_part" } }\n'
                          'types Shared { type shared_box = container { using = part } }',
        'gui/window.gui': 'window = { name = "w" shared_box = {} }'})
    assert names(tree) == ['w', 'from_part']


def test_a_using_no_table_knows_stops(tmp_path: pathlib.Path) -> None:
    with pytest.raises(guimap.GuiError, match='using = nowhere'):
        window(tmp_path, 'w', {'gui/window.gui': 'window = { name = "w" using = nowhere }'})


def test_a_window_declared_as_a_type_is_built_once(tmp_path: pathlib.Path) -> None:
    tree = window(tmp_path, 'typed', {
        'gui/window.gui': 'types W { type my_window = window { name = "typed" '
                          'textbox = { name = "once" } } }'})
    assert names(tree) == ['typed', 'once']


def test_a_repeat_with_the_same_slots_ends_and_a_nesting_with_its_own_does_not(
        tmp_path: pathlib.Path) -> None:
    types = ('types T { type panel = container { block "content" {} } '
             'type loop = container { name = "loop" block "more" {} } }')
    nested = window(tmp_path, 'nested', {'gui/window.gui': types + (
        ' window = { name = "nested" panel = { name = "outer" blockoverride "content" {'
        ' panel = { name = "inner" blockoverride "content" { textbox = { name = "leaf" } } } } } }')})
    assert names(nested) == ['nested', 'outer', 'inner', 'leaf']
    endless = window(tmp_path, 'endless', {'gui/window.gui': types + (
        ' window = { name = "endless" loop = { blockoverride "more" { loop = {} } } }')})
    assert names(endless) == ['endless', 'loop', 'loop']
