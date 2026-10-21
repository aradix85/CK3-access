"""Loading a script only defines; the work starts under its main guard.

On 3 October 2026 a check that only loaded each script put the launcher file of 1.19 back. Each case
below is one shape `tools\\check.py` must let through or report, written to a file of its own.
"""
import pathlib

from tools import check

DEFINES = '''"""A module."""
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sys

NAME = os.path.join('a', 'b')


def main() -> None:
    print('work')


if __name__ == '__main__':
    main()
'''


def found(tmp_path: pathlib.Path, source: str) -> list[str]:
    path = tmp_path / 'script.py'
    path.write_text(source, encoding='utf-8')
    return check.loading_work([str(path)])


def test_a_module_that_only_defines_passes(tmp_path: pathlib.Path) -> None:
    assert found(tmp_path, DEFINES) == []


def test_work_at_the_top_level_is_reported(tmp_path: pathlib.Path) -> None:
    for work in ("print('loaded')", 'for x in range(2):\n    pass', 'try:\n    import os\nexcept ImportError:\n    pass',
                 "with open('x') as f:\n    pass"):
        assert len(found(tmp_path, DEFINES + work + '\n')) == 1, work


def test_every_script_of_the_project_only_defines() -> None:
    assert check.loading_work(check.scripts()) == []
