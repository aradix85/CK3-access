"""Which number means which culture, faith, religion or trait - read from the running game.

The model gives a number where the game means a culture or a faith. Turning that number into a
key used to mean reading a save, and **that is wrong unless it is the very save the game loaded**.
Measured 29 August 2026 on a save written before the mods were installed and loaded into the
modded game: memory carries the numbering of that save, and against the numbering of another
state 2 of 237 faiths and 2 of 94 religions come out right. A reader that takes the newest save
therefore does not read a slightly wrong faith, it reads a random one, and nothing says so.

Reading it here removes the question, because these are the very objects the character records
point at. It also removes the need for a manual save to exist at all.

Two shapes, and the difference is real rather than cosmetic. Cultures, faiths and religions are
game state: a `TPdxRefDatabase` whose slot number is the number, refilled from the save at every
load. Traits are definitions of the installation: a `CTraitDatabase` holding an array of pointers,
the same on every state, so a save written before the mods simply has fewer of them.

**A number is only meaningful inside the state that is running.** A player can found a faith or a
culture, so the count grows while playing; never keep a numbering across a load, and take the
count from the database rather than from anywhere else.
"""
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import anchor
import database
import derive
import model

PROJECT = os.path.dirname(os.path.dirname(HERE))
MODEL = os.path.join(PROJECT, 'reports', 'model.json')
# A key is an identifier, and both ends of that are wider than they look: two letters is enough,
# because culture 49 is `yi`, and capitals occur, because RICE names its traits `RICE_hafsa`.
# Asking for three lower-case letters rejected two perfectly good readings, and a rejected reading
# looks exactly like a moved offset.
KEY = re.compile(r'^[A-Za-z][A-Za-z0-9_]+$')

# The class of each database, and which of the two shapes it has.
CLASSES = {
    'culture': ('.?AV?$TPdxRefDatabase@VCCulture@@$07@@', 'blocks'),
    'faith': ('.?AV?$TPdxRefDatabase@VCFaith@@$07@@', 'blocks'),
    'religion': ('.?AV?$TPdxRefDatabase@VCReligion@@$07@@', 'blocks'),
    'trait': ('.?AVCTraitDatabase@@', 'array'),
}
# Inside the header of a TPdxRefDatabase. These four are not derived, so every read proves them
# again: the keys that come out have to be the keys the files on disk carry.
HEAD = {'table': 8, 'blocks': 16, 'block_size': 40, 'count': 60}
CHUNK = 65536
STRING = 32
SAMPLE = 32
POINTER = (0x10000000000, 0x800000000000)


def on_disk(kind):
    """Every key of this database as the files give it, mods merged in the engine's own order."""
    return {key for key, _, _ in database.entries(kind)}


def _is_array_database(address):
    """A CTraitDatabase holds an array of pointers with its length beside it.

    Demanding only a pointer and a plausible length is too little: a copy on the stack passes
    that, and no global points at a copy, so the derivation walked away empty. The array has to
    hold addresses that are addresses.
    """
    head = derive.read(address, 256)
    if head is None:
        return False
    return any(_members(found) for found in
               (_array_at(head, at) for at in range(0, 224, 8)) if found)


def _array_at(head, at):
    """(address, count) of the pointer array sitting at this offset, or None."""
    where, count = struct.unpack_from('<QI', head, at)
    if not POINTER[0] <= where < POINTER[1] or not 0 < count < 10000:
        return None
    return where, count


def _members(found, how_many=8):
    """The first few entries of that array, or None when they are not pointers at all."""
    where, count = found
    raw = derive.read(where, min(count, how_many) * 8)
    if not raw:
        return None
    entries = [struct.unpack_from('<Q', raw, i * 8)[0] for i in range(len(raw) // 8)]
    return entries if all(POINTER[0] <= one < POINTER[1] for one in entries) else None


def _object(pid, kind):
    name, shape = CLASSES[kind]
    valid = anchor.is_ref_database if shape == 'blocks' else _is_array_database
    return anchor.object_of(pid, name, valid), shape


def _places(pid, kind, layout):
    """Per number the address where its key sits. The count comes from the database itself."""
    address, shape = _object(pid, kind)
    if shape == 'array':
        head = derive.read(address, 256)
        where, count = _array_at(head, layout['array'])
        raw = derive.read(where, count * 8)
        return {n: struct.unpack_from('<Q', raw, n * 8)[0] + layout['key'] for n in range(count)}
    head = derive.read(address, 64)
    table, blocks = struct.unpack_from('<QI', head, HEAD['table'])
    size = struct.unpack_from('<I', head, HEAD['block_size'])[0]
    count = struct.unpack_from('<I', head, HEAD['count'])[0]
    starts = struct.unpack('<%dQ' % blocks, derive.read(table, blocks * 8))
    return {n: starts[n // size] + (n % size) * layout['record'] + layout['key']
            for n in range(count)}


def _read(pid, kind, layout):
    places = _places(pid, kind, layout)
    chunks = model.readmany(sorted(places.values()), STRING)
    found = model.names_of({n: chunks[a] for n, a in places.items() if a in chunks}, 0)
    return len(places), found


def _holds(kind, count, found):
    """Does this reading prove itself? Every number has a well-formed key, and the great
    majority are keys the files carry. Not all of them: a player can found a faith or a culture,
    and those carry a key no file has - which is exactly why the numbering is read here."""
    if len(found) != count or any(not KEY.match(text) for text in found.values()):
        return False
    known = on_disk(kind)
    return sum(1 for text in found.values() if text in known) >= 0.9 * count


def keys(pid, kind):
    """Number -> key, from the running game. Disk is used to prove the reading, never to make it.

    The stored layout has to hold up every time; if it does not, it is derived again, which is
    the same setup `derive.py` uses for the widget fields.
    """
    layout = _stored(kind)
    if layout:
        count, found = _read(pid, kind, layout)
        if _holds(kind, count, found):
            return found
    layout = derive_layout(pid, kind)
    count, found = _read(pid, kind, layout)
    if not _holds(kind, count, found):
        raise SystemExit('the layout just derived for %s does not read %d keys' % (kind, count))
    return found


def _key_at(chunk, at):
    """Is there a key here at all - short enough to sit in place, or behind a pointer?"""
    text = model.string_at(chunk, at)
    if text is not None:
        return bool(KEY.match(text))
    return model.long_string_at(chunk, at) is not None


def _step(spots):
    """The record length: the distance that turns up most often between two keys in a row."""
    counts = {}
    for i, first in enumerate(spots):
        for second in spots[i + 1:i + 40]:
            counts[second - first] = counts.get(second - first, 0) + 1
    if not counts:
        raise SystemExit('no key at all in this block')
    return max(counts, key=counts.get)


def _winner(scores, what):
    """The one candidate the files agree with. A tie is a failure rather than a coin toss."""
    ranked = sorted(scores.items(), key=lambda pair: -pair[1])
    if not ranked:
        raise SystemExit('no %s agrees with the files on disk' % what)
    if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
        raise SystemExit('two candidates for the %s score alike' % what)
    return ranked[0][0]


def _agrees(chunks, at, known):
    """How many of these records show a key the files carry at this offset, or None if too few do.

    Following the pointer matters here: most religion keys are longer than fifteen characters, so
    counting only what fits inside a record scored the right field 16 out of 49 and threw it away.
    """
    texts = model.names_of(chunks, at)
    if not texts:
        return None
    hits = sum(1 for text in texts.values() if text in known)
    return hits if hits >= 0.9 * len(texts) else None


def _derive_blocks(address, known):
    """Record length from the spacing of the keys, and which field is the key from the files.

    Spacing alone does not decide the field: a culture record carries a second key-shaped string
    272 bytes before its own, and on being well formed the two are indistinguishable. What tells
    them apart is the set of keys the files carry - one field matches it whole, the other partly.
    """
    head = derive.read(address, 64)
    table = struct.unpack_from('<Q', head, HEAD['table'])[0]
    filled = struct.unpack_from('<I', head, HEAD['count'])[0]
    first = struct.unpack('<Q', derive.read(table, 8))[0]
    block = derive.read(first, CHUNK)
    spots = [at for at in range(0, len(block) - STRING, 8) if _key_at(block, at)]
    record = _step(spots)
    # A block holds a thousand slots and a state fills far fewer, so only the filled ones count.
    # Religion has 424 bytes to a record: 154 of them fit in the chunk and 49 are filled, and
    # taking the empty ones for misses rejected a reading that was perfectly good.
    rows = min(filled, len(block) // record)
    chunks = {n: block[n * record:(n + 1) * record] for n in range(rows)}
    scores = {}
    for at in sorted({spot % record for spot in spots}):
        hits = _agrees(chunks, at, known)
        if hits:
            scores[at] = hits
    return {'record': record, 'key': _winner(scores, 'key field')}


def _derive_array(address, known):
    """Which slot holds the array of definitions, and where the key sits inside one.

    Every slot is scored and the best one wins. Taking the first slot whose entries yield keys is
    not enough: the object carries more than one array over the same things, and the first is not
    the one whose order is the numbering.
    """
    head = derive.read(address, 256)
    scores = {}
    for at in range(0, 224, 8):
        found = _array_at(head, at)
        entries = _members(found, SAMPLE) if found else None
        if not entries:
            continue
        chunks = model.readmany(entries, 512)
        if len(chunks) < len(entries):
            continue
        for inside in sorted({spot for one in chunks.values()
                              for spot in range(0, 512 - STRING, 8) if _key_at(one, spot)}):
            hits = _agrees(chunks, inside, known)
            if hits:
                scores[(at, inside)] = hits
    if not scores:
        raise SystemExit('no array of definitions in this database')
    at, inside = _winner(scores, 'array of definitions')
    return {'array': at, 'key': inside}


def _stored(kind):
    stored = json.load(open(MODEL, encoding='utf-8'))
    if stored.get('key') != derive.build_key():
        return None
    return stored.get('databases', {}).get(kind)


def derive_layout(pid, kind):
    """Where the key sits in a record of this database, kept under the key of this exe."""
    address, shape = _object(pid, kind)
    known = on_disk(kind)
    layout = _derive_blocks(address, known) if shape == 'blocks' else _derive_array(address, known)
    stored = json.load(open(MODEL, encoding='utf-8'))
    stored['key'] = derive.build_key()
    stored.setdefault('databases', {})[kind] = layout
    json.dump(stored, open(MODEL, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    return layout


def main(pid):
    for kind in CLASSES:
        found = keys(pid, kind)
        known = on_disk(kind)
        print('%-9s %4d numbers in the running game, %4d of them keys the files carry, %4d on disk'
              % (kind, len(found), sum(1 for t in found.values() if t in known), len(known)))
        print('          %s' % ', '.join('%d=%s' % (n, found[n]) for n in sorted(found)[:6]))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main(int(sys.argv[1]))
