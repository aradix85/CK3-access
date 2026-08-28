"""Reads the game state from a save file - the answer key for searching in memory.

A save is a header followed by a zip holding one file: `gamestate`, tens of megabytes of plain
text in the familiar Paradox form. This is deliberately not a full parser. What searching in
memory needs is one question: give me object X and all its numbers. Building more than that is
work nobody asked for.

Usage:
    text = unpack()                         # or unpack(path) for another save
    values = numbers(block(text, '32769'))
    -> {'culture': 235, 'faith': 23, 'skill.0': 5, 'alive_data.gold.value': 552, ...}
"""
import glob
import io
import os
import re
import zipfile

SAVE_DIR = os.path.expanduser(
    r'~\Documents\Paradox Interactive\Crusader Kings III\save games')


def newest_save():
    saves = glob.glob(os.path.join(SAVE_DIR, '*.ck3'))
    if not saves:
        raise SystemExit('no save found in %s' % SAVE_DIR)
    return max(saves, key=os.path.getmtime)


def newest_readable_save():
    """The newest save that was stored as text.

    Needed because CK3 mixes two forms: a manual save is plain text, but an autosave is binary
    tokenised and therefore useless as an answer key. Measured 28 July 2026: `autosave_exit.ck3`
    contains not a single readable keyword.
    """
    saves = sorted(glob.glob(os.path.join(SAVE_DIR, '*.ck3')),
                   key=os.path.getmtime, reverse=True)
    for path in saves:
        try:
            if is_text(unpack(path)):
                return path
        except SystemExit:
            continue
    raise SystemExit('not a single save in %s is stored as text' % SAVE_DIR)


def is_text(content):
    return 'living={' in content[:2000000] or 'meta_data={' in content[:200000]


def unpack(path=None):
    """The game state as text. The header before the zip differs in length per save, so it is
    searched for and not assumed."""
    path = path or newest_save()
    raw = open(path, 'rb').read()
    start = raw.find(b'PK\x03\x04')
    if start < 0:
        raise SystemExit('no zip in %s - is this an ironman save?' % os.path.basename(path))
    with zipfile.ZipFile(io.BytesIO(raw[start:])) as zip:
        name = 'gamestate' if 'gamestate' in zip.namelist() else zip.namelist()[0]
        return zip.read(name).decode('utf-8', 'replace')


def block(text, build_key, start_at=0):
    """The content between the braces of `key={ ... }`, with braces counted so that nested
    blocks do not close it early."""
    pos = text.find('\n%s={' % build_key, start_at)
    if pos < 0:
        pos = text.find('%s={' % build_key, start_at)
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


def character_index(text):
    """Character number -> where its block starts, in one pass.

    Looking one character up costs a scan of the whole game state, and a calibration round asks
    for hundreds of them. Measured 28 August 2026 on the Nobatia save: 400 characters cost 8.4 s
    one at a time against 0.2 s through this index, returning the same block 400 out of 400 times.

    A number is not unique across kinds - 1515 is a dynasty house as well as a barony - so the
    pattern demands a character field right behind it. Within one kind it is unique: over the
    three saves not one number carries two character blocks.
    """
    return {int(m.group(1)): m.start() for m in _CHARACTER.finditer(text)}


_MAPPING = re.compile(r'([a-z_][a-z_0-9]*)=([^\s{}"]+|\{[^{}]*\})', re.I)


def numbers(content, prefix='', depth=0):
    """Every whole number in a block, with its path as the name. Whole numbers only, because that
    is what can be found back in memory as a separate field; decimals and text cannot."""
    out = {}
    if content is None or depth > 4:
        return out
    for name, value in _MAPPING.findall(content):
        path = prefix + name
        value = value.strip()
        if value.startswith('{'):
            parts = value[1:-1].split()
            for n, part in enumerate(parts):
                if re.fullmatch(r'-?\d+', part):
                    out['%s.%d' % (path, n)] = int(part)
        elif re.fullmatch(r'-?\d+', value):
            out[path] = int(value)
    # nested blocks separately, because the regexp above only catches flat assignments
    for m in re.finditer(r'\n\t*([a-z_][a-z_0-9]*)=\{', content, re.I):
        name = m.group(1)
        part = block(content, name, m.start())
        if part is not None and len(part) < 20000:
            out.update(numbers(part, prefix + name + '.', depth + 1))
    return out


def player(text):
    """The character number of the player."""
    m = re.search(r'currently_played_characters=\{\s*(\d+)', text)
    if not m:
        raise SystemExit('no played character in the game state')
    return m.group(1)


if __name__ == '__main__':
    path = newest_readable_save()
    print('save: %s' % os.path.basename(path))
    text = unpack(path)
    number = player(text)
    values = numbers(block(text, number))
    print('player: %s, %d numbers in his record' % (number, len(values)))
    for name in sorted(values)[:40]:
        print('   %-40s %d' % (name, values[name]))
