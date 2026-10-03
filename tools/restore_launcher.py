"""Restores launcher-settings.json to the original from before the injector.

Meant for one case: the game no longer starts. Run it with
`python -m tools.restore_launcher`; it says out loud whether it worked, and if you hear nothing at
all it did not run. Steam's own "verify integrity of game files" is the second net behind this one.

Importing it does nothing: on 3 October 2026 a round that imported every module to check the imports
ran the copy at import time, and put the 1.19 original over the launcher settings of 1.20.
"""
import hashlib
import os
import shutil

from tools import paths
from tools.nvda import speech

ORIGINAL = os.path.join(paths.PROJECT, 'launcher-settings.original.json')


def sha256(path: str) -> str:
    with open(path, 'rb') as file:
        return hashlib.sha256(file.read()).hexdigest()


def main() -> None:
    target = os.path.join(paths.require('GAME'), 'launcher', 'launcher-settings.json')
    shutil.copyfile(ORIGINAL, target)
    if sha256(ORIGINAL) == sha256(target):
        message = 'Launcher restored to the original. Start the game through Steam.'
    else:
        message = 'Restore failed. The files still differ.'
    speech.output(message)
    print(message)


if __name__ == '__main__':
    main()
