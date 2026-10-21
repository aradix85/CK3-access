"""Reads the game state from a save file - the answer key for searching in memory.

A save is a header followed by a zip holding one file: `gamestate`, tens of megabytes of plain
text in the familiar Paradox form. This is deliberately not a full parser: it finds a block, the
blocks of the characters and the player, which is what laying a save beside memory needs.
"""
import glob
import io
import os
import pathlib
import re
import zipfile

from tools import paths


def newest_readable_save() -> str:
    """The newest save that was stored as text.

    Needed because CK3 mixes two forms: a manual save is plain text, but an autosave is binary
    tokenised and therefore useless as an answer key. Measured 28 July 2026: `autosave_exit.ck3`
    contains not a single readable keyword.
    """
    folder = paths.require('SAVES')
    saves = sorted(glob.glob(os.path.join(folder, '*.ck3')), key=os.path.getmtime, reverse=True)
    for path in saves:
        state = _gamestate(pathlib.Path(path).read_bytes())
        if state is not None and is_text(state):
            return path
    raise SystemExit(f'not a single save in {folder} is stored as text')


def named(save: str) -> str:
    """A save by its path, or by any part of its file name in the save folder.

    Memory carries the state that was loaded, and held against another save every field disagrees
    at once, which reads exactly like a shifted field offset - so a part that fits two saves stops.
    """
    if os.path.isabs(save):
        return save
    matches = [p for p in glob.glob(os.path.join(paths.require('SAVES'), '*.ck3'))
               if save.lower() in os.path.basename(p).lower()]
    if len(matches) != 1:
        raise SystemExit(f'{len(matches)} saves carry {save!r} in their name, so it says nothing')
    return matches[0]


def is_text(content: str) -> bool:
    return 'living={' in content[:2000000] or 'meta_data={' in content[:200000]


def unpack(path: str) -> str:
    """The game state as text. The header before the zip differs in length per save, so it is
    searched for and not assumed."""
    state = _gamestate(pathlib.Path(path).read_bytes())
    if state is None:
        raise SystemExit(f'no zip in {os.path.basename(path)} - is this an ironman save?')
    return state


def _gamestate(raw: bytes) -> str | None:
    """The game state inside the bytes of a save, or None when they hold no zip."""
    start = raw.find(b'PK\x03\x04')
    if start < 0:
        return None
    with zipfile.ZipFile(io.BytesIO(raw[start:])) as zip:
        return zip.read('gamestate').decode('utf-8', 'replace')


def block(text: str, build_key: str, start_at: int = 0) -> str | None:
    """The content between the braces of `key={ ... }`, with braces counted so that nested
    blocks do not close it early."""
    pos = text.find(f'\n{build_key}={{', start_at)
    if pos < 0:
        pos = text.find(f'{build_key}={{', start_at)
        if pos < 0:
            return None
    i = text.index('{', pos) + 1
    depth, j = 1, i
    while depth and j < len(text):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
        j += 1
    return text[i:j - 1]


_CHARACTER = re.compile(r'\n(\d+)=\{\n\tfirst_name=')


def character_index(text: str) -> dict[int, int]:
    """Character number -> where its block starts, in one pass.

    Looking one character up costs a scan of the whole game state, and a calibration round asks
    for hundreds of them. Measured 28 August 2026 on the Nobatia save: 400 characters cost 8.4 s
    one at a time against 0.2 s through this index, returning the same block 400 out of 400 times.

    A number is not unique across kinds - 1515 is a dynasty house as well as a barony - so the
    pattern demands a character field right behind it. Within one kind it is unique: over the
    three saves not one number carries two character blocks.
    """
    return {int(m.group(1)): m.start() for m in _CHARACTER.finditer(text)}


def player(text: str) -> str:
    """The character number of the player."""
    m = re.search(r'currently_played_characters=\{\s*(\d+)', text)
    if not m:
        raise SystemExit('no played character in the game state')
    return m.group(1)


if __name__ == '__main__':
    path = newest_readable_save()
    print(f'save: {os.path.basename(path)}, player: {player(unpack(path))}')
