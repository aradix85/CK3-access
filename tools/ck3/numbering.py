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
import mapdata
import model

PROJECT = os.path.dirname(os.path.dirname(HERE))
MODEL = os.path.join(PROJECT, 'reports', 'model.json')

# The class of each database, and which of the three shapes it has.
CLASSES = {
    'culture': ('.?AV?$TPdxRefDatabase@VCCulture@@$07@@', 'blocks'),
    'faith': ('.?AV?$TPdxRefDatabase@VCFaith@@$07@@', 'blocks'),
    'religion': ('.?AV?$TPdxRefDatabase@VCReligion@@$07@@', 'blocks'),
    'trait': ('.?AVCTraitDatabase@@', 'array'),
    'title': ('.?AV?$TPdxRefDatabase@VCLandedTitle@@$07@@', 'indirect'),
}
# Inside the header of a TPdxRefDatabase. These three are not derived, so every read proves them
# again: the keys that come out have to be the keys the files on disk carry.
HEAD = {'table': 8, 'blocks': 16, 'count': 60}
# **The field at +40 is not the block size, measured 1 September 2026.** It reads 1024 for
# cultures, faiths and religions - the size they really use - and it read as the block size here
# until titles came along, where it says 32768 while the database works in blocks of 1024, and
# characters, where it says 131072. Three databases where the two coincided is a coincidence and
# not a counting rule. `anchor.py` has carried 1024 by hand all along and that turns out to be
# right; taking it from the header would have indexed the character database at 131072 and read
# every field behind it quietly wrong.
BLOCK = 1024
CHUNK = 65536
STRING = 32
SAMPLE = 32
POINTER = (0x10000000000, 0x800000000000)


def _key_test(known):
    """What a key of this database may look like, taken from the files rather than imagined.

    **Written by hand this was wrong four times, and every time it looked like a moved offset.**
    Three lower-case letters turned down `yi`, culture 49. Lower case only turned down
    `RICE_hafsa`, which is how RICE names its traits. No hyphen turned down 379 titles -
    `d_al-qays`, `k_galicia-volhynia`, `b_starodub-on-the-klyazma`. No apostrophe turned down
    `b_mansa'l-kharaz` and `b_ka'abir`. Each of those readings was perfect and each was thrown
    away by the judge rather than by the reading.

    So the character set is the one the files use for this database, and a rejection now means
    the game holds a key no file could have written. It stays a real test: the offsets that lose
    here read struct padding and pointer halves, which carry bytes no key does.
    """
    letters = ''.join(sorted(set(''.join(known))))
    return re.compile('^[A-Za-z][%s]+$' % re.escape(letters))


def on_disk(kind):
    """Every key of this database as the files give it, mods merged in the engine's own order.

    Titles come from `mapdata.titles` rather than `database.entries`, because `landed_titles`
    nests five levels deep and a title is told from the other keys inside a block by its tier
    letter. That walk lives in one place; repeating the rule here would give two answers to the
    question of what a title key is.
    """
    if kind == 'title':
        return set(mapdata.titles())
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
    valid = _is_array_database if shape == 'array' else anchor.is_ref_database
    return anchor.object_of(pid, name, valid), shape


def _places(pid, kind, layout):
    """Per number the address where its key sits. The count comes from the database itself.

    Three shapes end here. An array of definitions hands out its members directly. A block
    database lays its records end to end and carries the key inside one. A title record carries
    no key but a pointer to the object that does, so that one costs a read round before the
    addresses are even known.
    """
    address, shape = _object(pid, kind)
    if shape == 'array':
        head = derive.read(address, 256)
        where, count = _array_at(head, layout['array'])
        raw = derive.read(where, count * 8)
        return {n: struct.unpack_from('<Q', raw, n * 8)[0] + layout['key'] for n in range(count)}
    head = derive.read(address, 64)
    table, blocks = struct.unpack_from('<QI', head, HEAD['table'])
    count = struct.unpack_from('<I', head, HEAD['count'])[0]
    starts = struct.unpack('<%dQ' % blocks, derive.read(table, blocks * 8))
    records = {n: starts[n // BLOCK] + (n % BLOCK) * layout['record'] for n in range(count)}
    if shape == 'blocks':
        return {n: at + layout['key'] for n, at in records.items()}
    spots = {n: at + layout['pointer'] for n, at in records.items()}
    raw = model.readmany(sorted(spots.values()), 8)
    out = {}
    for number, at in spots.items():
        chunk = raw.get(at)
        if chunk and len(chunk) == 8:
            target = struct.unpack('<Q', chunk)[0]
            if POINTER[0] <= target < POINTER[1]:
                out[number] = target + layout['key']
    return out


def _read(pid, kind, layout):
    places = _places(pid, kind, layout)
    chunks = model.readmany(sorted(places.values()), STRING)
    found = model.names_of({n: chunks[a] for n, a in places.items() if a in chunks}, 0)
    return len(places), found


def _holds(kind, count, found):
    """Does this reading prove itself? Every number has a well-formed key, and the great
    majority are keys the files carry. Not all of them: a player can found a faith or a culture,
    and those carry a key no file has - which is exactly why the numbering is read here."""
    known = on_disk(kind)
    shaped = _key_test(known)
    if len(found) != count or any(not shaped.match(text) for text in found.values()):
        return False
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


def _key_at(chunk, at, shaped):
    """Is there a key here at all - short enough to sit in place, or behind a pointer?"""
    text = model.string_at(chunk, at)
    if text is not None:
        return bool(shaped.match(text))
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
    shaped = _key_test(known)
    spots = [at for at in range(0, len(block) - STRING, 8) if _key_at(block, at, shaped)]
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
    shaped = _key_test(known)
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
                              for spot in range(0, 512 - STRING, 8) if _key_at(one, spot, shaped)}):
            hits = _agrees(chunks, inside, known)
            if hits:
                scores[(at, inside)] = hits
    if not scores:
        raise SystemExit('no array of definitions in this database')
    at, inside = _winner(scores, 'array of definitions')
    return {'array': at, 'key': inside}


def _pointers_at(block, at, rows, record):
    """The value at this offset in every one of the first `rows` records, if all are pointers.

    All of them, not most: an offset that is a pointer in nine records out of ten is a field that
    sometimes holds one, and following it would read whatever happens to sit at a stray address.
    """
    out = {}
    for n in range(rows):
        value = struct.unpack_from('<Q', block, n * record + at)[0]
        if not POINTER[0] <= value < POINTER[1]:
            return None
        out[n] = value
    return out


def _derive_indirect(address, known):
    """A block database whose record holds no key but a pointer to the object that carries one.

    The record length comes from the spacing of the pointers, the same way the block shape takes
    it from the spacing of the keys: every record has the same layout, so the distance that turns
    up most often between two pointer-shaped values is the record. Which of the pointers is the
    one, and where the key sits behind it, is settled by the files on disk - exactly one pair
    yields keys the files carry.

    **The offset is kept relative to the pointer's value and not to the object it belongs to.**
    Measured 1 September 2026: a title record points eight bytes past the start of its object,
    and the key sits at +0x20 in that object, so the number stored here is 24. Folding the eight
    in means nothing has to remember it, and nothing here has to know what the object is.
    """
    head = derive.read(address, 64)
    table = struct.unpack_from('<Q', head, HEAD['table'])[0]
    filled = struct.unpack_from('<I', head, HEAD['count'])[0]
    first = struct.unpack('<Q', derive.read(table, 8))[0]
    block = derive.read(first, CHUNK)
    spots = [at for at in range(0, len(block) - 8, 8)
             if POINTER[0] <= struct.unpack_from('<Q', block, at)[0] < POINTER[1]]
    record = _step(spots)
    rows = min(filled, len(block) // record, SAMPLE)
    shaped = _key_test(known)
    scores = {}
    for at in sorted({spot % record for spot in spots}):
        targets = _pointers_at(block, at, rows, record)
        if not targets:
            continue
        chunks = model.readmany(sorted(set(targets.values())), 512)
        by_slot = {n: chunks[where] for n, where in targets.items() if where in chunks}
        if len(by_slot) < rows:
            continue
        for inside in sorted({spot for one in by_slot.values()
                              for spot in range(0, 512 - STRING, 8) if _key_at(one, spot, shaped)}):
            hits = _agrees(by_slot, inside, known)
            if hits:
                scores[(at, inside)] = hits
    if not scores:
        raise SystemExit('no pointer in a record of this database leads to a key on disk')
    at, inside = _winner(scores, 'pointer to the key')
    return {'record': record, 'pointer': at, 'key': inside}


def _stored(kind):
    stored = json.load(open(MODEL, encoding='utf-8'))
    if stored.get('key') != derive.build_key():
        return None
    return stored.get('databases', {}).get(kind)


def derive_layout(pid, kind):
    """Where the key sits in a record of this database, kept under the key of this exe."""
    address, shape = _object(pid, kind)
    known = on_disk(kind)
    if shape == 'blocks':
        layout = _derive_blocks(address, known)
    elif shape == 'indirect':
        layout = _derive_indirect(address, known)
    else:
        layout = _derive_array(address, known)
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
