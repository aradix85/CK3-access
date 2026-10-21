"""Restores launcher-settings.json to the original from before the injector.

Meant for one case: the game no longer starts. Run it with
`python -m tools.restore_launcher`; it says out loud that it worked, and if you hear nothing at all
it did not. Steam's own "verify integrity of game files" is the second net behind this one.

Importing it does nothing: on 3 October 2026 a round that imported every module to check the imports
ran the copy at import time, and put the 1.19 original over the launcher settings of 1.20.
"""
import os
import shutil

from tools import paths
from tools.nvda import speech

ORIGINAL = os.path.join(paths.PROJECT, 'launcher-settings.original.json')


def main() -> None:
    shutil.copyfile(ORIGINAL, os.path.join(paths.require('GAME'), 'launcher', 'launcher-settings.json'))
    message = 'Launcher restored to the original. Start the game through Steam.'
    speech.output(message)
    print(message)


if __name__ == '__main__':
    main()
