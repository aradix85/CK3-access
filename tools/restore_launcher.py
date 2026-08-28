"""Restores launcher-settings.json to the original from before the injector.

Meant for one case: the game no longer starts. Run it with
`python tools/restore_launcher.py`; it says out loud whether it worked, and if you hear nothing at
all it did not run. Steam's own "verify integrity of game files" is the second net behind this one.
"""
import hashlib, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nvda'))
import paths
import speech

ORIGINAL = os.path.join(paths.PROJECT, 'launcher-settings.original.json')
TARGET = os.path.join(paths.GAME, 'launcher', 'launcher-settings.json')


def sha256(path):
    with open(path, 'rb') as file:
        return hashlib.sha256(file.read()).hexdigest()


shutil.copyfile(ORIGINAL, TARGET)

if sha256(ORIGINAL) == sha256(TARGET):
    message, braille = 'Launcher restored to the original. Start the game through Steam.', 'restored'
else:
    message, braille = 'Restore failed. The files still differ.', 'failed'

speech.output(message, braille=braille)
print(message)
