"""Which number means which culture, faith, religion or trait - read from the running game.

The model gives a number where the game means a culture or a faith. Turning that number into a
key used to mean reading a save, and **that is wrong unless it is the very save the game loaded**.
Measured 29 August 2026 on a save written before the mods were installed and loaded into the
modded game: memory carries the numbering of that save, and against the numbering of another
state 2 of 237 faiths and 2 of 94 religions come out right. A reader that takes the newest save
therefore does not read a slightly wrong faith, it reads a random one, and nothing says so.

Reading it here removes the question, because these are the very objects the character records
point at. It also removes the need for a manual save to exist at all.

Three shapes, and the difference is real rather than cosmetic. Faiths, religions and rites are
game state: a `TPdxRefDatabase` whose slot number is the number, refilled from the save at every
load, with the key in the record. Cultures and titles are the same database, but their record
holds a pointer to the object that carries the key. Traits are definitions of the installation: a
`CTraitDatabase` holding an array of pointers, the same on every state, so a save written before
the mods simply has fewer of them.

**A number is only meaningful inside the state that is running.** A player can found a faith or a
culture, so the count grows while playing; never keep a numbering across a load, and take the
count from the database rather than from anywhere else.
"""
import re
import struct
import sys
from typing import TypeVar

from tools import terminal
from tools.ck3 import anchor, database, derive, mapdata, model

# Where the key sits in a record of one database: `record`, `key`, and `array` or `pointer`.
Layout = dict[str, int]
K = TypeVar('K')

# The class of each database, and which of the three shapes it has.
CLASSES = {
    # Since 1.20 a culture record holds no key, only the names a player sees, and a pointer to its
    # template, which carries the key the save calls culture_template.
    'culture': ('.?AV?$TPdxRefDatabase@VCCulture@@$07@@', 'indirect'),
    'faith': ('.?AV?$TPdxRefDatabase@VCFaith@@$07@@', 'blocks'),
    'religion': ('.?AV?$TPdxRefDatabase@VCReligion@@$07@@', 'blocks'),
    # Since 1.20 a character carries a rite and the faith follows from it.
    'rite': ('.?AV?$TPdxRefDatabase@VCRite@@$07@@', 'blocks'),
    'trait': ('.?AVCTraitDatabase@@', 'array'),
    'title': ('.?AV?$TPdxRefDatabase@VCLandedTitle@@$07@@', 'indirect'),
}
CHUNK = 65536
STRING = 32
SAMPLE = 32


def _key_test(known: set[str]) -> re.Pattern[str]:
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

    **Plus digits and the underscore, because the game names what it founds itself.** On 1.20 a
    faith founds rites while it grows, and the game calls them `dynamic_rite_151`: no rite key on
    disk has a digit, so the fifth rejection threw away a perfect reading of the rites (measured
    21 October 2026 on the played Ghur, 1.20.1.1).
    """
    letters = ''.join(sorted(set(''.join(known)) | set('0123456789_')))
    return re.compile(f'^[A-Za-z][{re.escape(letters)}]+$')


def on_disk(kind: str) -> set[str]:
    """Every key of this database as the files give it, mods merged in the engine's own order.

    Titles come from `mapdata.titles` rather than `database.entries`, because `landed_titles`
    nests five levels deep and a title is told from the other keys inside a block by its tier
    letter. That walk lives in one place; repeating the rule here would give two answers to the
    question of what a title key is.
    """
    if kind == 'title':
        return set(mapdata.titles())
    return {key for key, _, _ in database.entries(kind)}


def _is_array_database(address: int) -> bool:
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


def _array_at(head: bytes, at: int) -> tuple[int, int] | None:
    """(address, count) of the pointer array sitting at this offset, or None."""
    where, count = struct.unpack_from('<QI', head, at)
    if not model.POINTER[0] <= where < model.POINTER[1] or not 0 < count < 10000:
        return None
    return where, count


def _members(found: tuple[int, int], how_many: int = 8) -> list[int] | None:
    """The first few entries of that array, or None when they are not pointers at all."""
    where, count = found
    raw = derive.read(where, min(count, how_many) * 8)
    if not raw:
        return None
    entries = [struct.unpack_from('<Q', raw, i * 8)[0] for i in range(len(raw) // 8)]
    return entries if all(model.POINTER[0] <= one < model.POINTER[1] for one in entries) else None


def _object(pid: int, kind: str) -> tuple[int, str]:
    name, shape = CLASSES[kind]
    valid = _is_array_database if shape == 'array' else anchor.is_ref_database
    return anchor.object_of(pid, name, valid), shape


def _places(pid: int, kind: str, layout: Layout) -> dict[int, int]:
    """Per number the address where its key sits. The count comes from the database itself.

    Three shapes end here. An array of definitions hands out its members directly. A block
    database lays its records end to end and carries the key inside one. A title record carries
    no key but a pointer to the object that does, so that one costs a read round before the
    addresses are even known.
    """
    address, shape = _object(pid, kind)
    if shape == 'array':
        head = derive.read_known(address, 256)
        found = _array_at(head, layout['array'])
        if found is None:
            raise SystemExit(f"the {kind} database no longer holds its array at +{layout['array']}")
        where, count = found
        raw = derive.read_known(where, count * 8)
        return {n: struct.unpack_from('<Q', raw, n * 8)[0] + layout['key'] for n in range(count)}
    starts, count = model.block_table(address)
    records = {n: starts[n // model.BLOCK] + (n % model.BLOCK) * layout['record'] for n in range(count)}
    if shape == 'blocks':
        return {n: at + layout['key'] for n, at in records.items()}
    spots = {n: at + layout['pointer'] for n, at in records.items()}
    held = model.readmany(sorted(spots.values()), 8)
    out: dict[int, int] = {}
    for number, at in spots.items():
        chunk = held.get(at)
        if chunk and len(chunk) == 8:
            target = struct.unpack('<Q', chunk)[0]
            if model.POINTER[0] <= target < model.POINTER[1]:
                out[number] = target + layout['key']
    return out


def _read(pid: int, kind: str, layout: Layout) -> tuple[int, dict[int, str]]:
    places = _places(pid, kind, layout)
    chunks = model.readmany(sorted(places.values()), STRING)
    found = model.names_of({n: chunks[a] for n, a in places.items() if a in chunks}, 0)
    return len(places), found


def _holds(kind: str, count: int, found: dict[int, str]) -> bool:
    """Does this reading prove itself? Every number has a well-formed key, and the great
    majority are keys the files carry. Not all of them: a player can found a faith or a culture,
    and those carry a key no file has - which is exactly why the numbering is read here."""
    known = on_disk(kind)
    shaped = _key_test(known)
    if len(found) != count or any(not shaped.match(text) for text in found.values()):
        return False
    return sum(1 for text in found.values() if text in known) >= 0.9 * count


def keys(pid: int, kind: str) -> dict[int, str]:
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
        raise SystemExit(f'the layout just derived for {kind} does not read {int(count)} keys')
    return found


def _key_at(chunk: bytes, at: int, shaped: re.Pattern[str]) -> bool:
    """Is there a key here at all - short enough to sit in place, or behind a pointer?"""
    text = model.string_at(chunk, at)
    if text is not None:
        return bool(shaped.match(text))
    return model.long_string_at(chunk, at) is not None


def _strides(spots: list[int], how_many: int) -> list[int]:
    """The distances that turn up most often between two marks in a row, commonest first."""
    counts: dict[int, int] = {}
    for i, first in enumerate(spots):
        for second in spots[i + 1:i + 40]:
            counts[second - first] = counts.get(second - first, 0) + 1
    if not counts:
        raise SystemExit('no key at all in this block')
    return sorted(counts, key=lambda distance: (-counts[distance], distance))[:how_many]


def _step(spots: list[int]) -> int:
    """The record length: the distance that turns up most often between two keys in a row."""
    return _strides(spots, 1)[0]


def _own_number_strides(block: bytes, rows: int) -> list[int]:
    """Record lengths at which a record's own slot number comes back, shortest first.

    A record of a ref database carries its own number - a character at +24 with a generation in the
    high byte (`model.py`), a culture at +16. Spacing between pointers is no measure when a record
    holds repeating inner structures: in a culture record the commonest pointer distance is 104,
    and its 1848 bytes were not among the twenty commonest (measured 21 October 2026, 1.20.1.1).
    Each length found here still has to read keys the files carry before it counts.
    """
    words = len(block) // 4
    value = [v & 0xFFFFFF for v in struct.unpack_from(f'<{words}I', block)]
    twos = {i for i, v in enumerate(value) if v == 2}
    found: set[int] = set()
    for one in (i for i, v in enumerate(value) if v == 1):
        for stride in range(2, min(words - one, 4096), 2):         # whole words, records 8-aligned
            start = one - stride
            if one + stride not in twos or start < 0:
                continue
            seen = min(rows, (words - start) // stride)
            if seen >= 4 and all(value[start + n * stride] == n for n in range(seen)):
                found.add(stride * 4)
    if not found:
        raise SystemExit('no record in this block carries its own number')
    return sorted(found)


def _winner(scores: dict[K, int], what: str) -> K:
    """The one candidate the files agree with. A tie is a failure rather than a coin toss."""
    ranked = sorted(scores.items(), key=lambda pair: -pair[1])
    if not ranked:
        raise SystemExit(f'no {what} agrees with the files on disk')
    if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
        raise SystemExit(f'two candidates for the {what} score alike')
    return ranked[0][0]


def _agrees(chunks: dict[int, bytes], at: int, known: set[str]) -> int | None:
    """How many of these records show a key the files carry at this offset, or None if too few do.

    Following the pointer matters here: most religion keys are longer than fifteen characters, so
    counting only what fits inside a record scored the right field 16 out of 49 and threw it away.
    """
    texts = model.names_of(chunks, at)
    if not texts:
        return None
    hits = sum(1 for text in texts.values() if text in known)
    return hits if hits >= 0.9 * len(texts) else None


def _derive_blocks(address: int, known: set[str]) -> Layout:
    """Record length from the spacing of the keys, and which field is the key from the files.

    Spacing alone does not decide the field: a culture record carries a second key-shaped string
    272 bytes before its own, and on being well formed the two are indistinguishable. What tells
    them apart is the set of keys the files carry - one field matches it whole, the other partly.
    """
    starts, filled = model.block_table(address)
    block = derive.read_known(starts[0], CHUNK)
    # The spacing of keys the files carry, not of anything shaped like a key: on 1.20 a religion,
    # faith or rite record also holds strings that only look like one, and the commonest distance
    # between all of them was not the record (measured 2 October 2026 on a state begun in 1.20).
    texts = model.names_of({at: block[at:at + STRING] for at in range(0, len(block) - STRING, 8)}, 0)
    spots = sorted(at for at, text in texts.items() if text in known)
    record = _step(spots)
    # A block holds a thousand slots and a state fills far fewer, so only the filled ones count.
    # Religion has 424 bytes to a record: 154 of them fit in the chunk and 49 are filled, and
    # taking the empty ones for misses rejected a reading that was perfectly good.
    rows = min(filled, len(block) // record)
    chunks = {n: block[n * record:(n + 1) * record] for n in range(rows)}
    scores: dict[int, int] = {}
    for at in sorted({spot % record for spot in spots}):
        hits = _agrees(chunks, at, known)
        if hits:
            scores[at] = hits
    return {'record': record, 'key': _winner(scores, 'key field')}


def _derive_array(address: int, known: set[str]) -> Layout:
    """Which slot holds the array of definitions, and where the key sits inside one.

    Every slot is scored and the best one wins. Taking the first slot whose entries yield keys is
    not enough: the object carries more than one array over the same things, and the first is not
    the one whose order is the numbering.
    """
    head = derive.read_known(address, 256)
    shaped = _key_test(known)
    scores: dict[tuple[int, int], int] = {}
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


def _pointers_at(block: bytes, at: int, rows: int, record: int) -> dict[int, int] | None:
    """The value at this offset in every one of the first `rows` records, if all are pointers.

    All of them, not most: an offset that is a pointer in nine records out of ten is a field that
    sometimes holds one, and following it would read whatever happens to sit at a stray address.
    """
    out: dict[int, int] = {}
    for n in range(rows):
        value = struct.unpack_from('<Q', block, n * record + at)[0]
        if not model.POINTER[0] <= value < model.POINTER[1]:
            return None
        out[n] = value
    return out


def _derive_indirect(address: int, known: set[str]) -> Layout:
    """A block database whose record holds no key but a pointer to the object that carries one.

    The record length comes from the record's own number, which comes back once per record
    (`_own_number_strides`). Which length, which pointer, and where the key sits behind it, is
    settled by the files on disk: the combination that reads the most keys they carry.

    **The offset is kept relative to the pointer's value and not to the object it belongs to.**
    Measured 1 September 2026: a title record points eight bytes past the start of its object,
    and the key sits at +0x20 in that object, so the number stored here is 24. Folding the eight
    in means nothing has to remember it, and nothing here has to know what the object is.
    """
    starts, filled = model.block_table(address)
    block = derive.read_known(starts[0], CHUNK)
    spots = [at for at in range(0, len(block) - 8, 8)
             if model.POINTER[0] <= struct.unpack_from('<Q', block, at)[0] < model.POINTER[1]]
    shaped = _key_test(known)
    readings: dict[tuple[int, int, int], dict[int, str]] = {}
    for record in _own_number_strides(block, min(filled, SAMPLE)):
        rows = min(filled, len(block) // record, SAMPLE)
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
                texts = model.names_of(by_slot, inside)
                if texts and _agrees(by_slot, inside, known):
                    readings[(record, at, inside)] = texts
    if not readings:
        raise SystemExit('no pointer in a record of this database leads to a key on disk')
    return dict(zip(('record', 'pointer', 'key'), _one_reading(readings), strict=True))


def _one_reading(readings: dict[tuple[int, int, int], dict[int, str]]) -> tuple[int, int, int]:
    """Of the (record, pointer, key) that read keys the files carry, the one that reads the most.

    A longer record reads fewer rows, so a multiple of the true one loses on its own. Two pointers
    can tie, and a tie is a failure unless both read exactly the same keys: a culture record holds
    two ways to its template (measured 21 October 2026), and then the key nearest to where its
    pointer points is read, so the choice is the same every time.
    """
    best = max(len(texts) for texts in readings.values())
    tied = sorted((key for key, texts in readings.items() if len(texts) == best), key=lambda k: (k[2], k[1], k[0]))
    first = readings[tied[0]]
    if any(readings[other] != first for other in tied[1:]):
        raise SystemExit(f'{len(tied)} pointers lead to keys equally well and read different ones')
    return tied[0]


def _stored(kind: str) -> Layout | None:
    stored = anchor.load_model()
    if stored.get('key') != derive.build_key():
        return None
    return stored.get('databases', {}).get(kind)


def derive_layout(pid: int, kind: str) -> Layout:
    """Where the key sits in a record of this database, kept under the key of this exe."""
    address, shape = _object(pid, kind)
    known = on_disk(kind)
    if shape == 'blocks':
        layout = _derive_blocks(address, known)
    elif shape == 'indirect':
        layout = _derive_indirect(address, known)
    else:
        layout = _derive_array(address, known)
    stored = anchor.load_model()
    stored['key'] = derive.build_key()
    stored.setdefault('databases', {})[kind] = layout
    anchor.store_model(stored)
    return layout


def main(pid: int) -> None:
    for kind in CLASSES:
        found = keys(pid, kind)
        known = on_disk(kind)
        print(f'{kind!s:<9} {len(found):4d} numbers in the running game, {int(sum(1 for t in found.values() if t in known)):4d} of them keys the files carry, {len(known):4d} on disk')
        print('          {}'.format(', '.join(f'{int(n)}={found[n]}' for n in sorted(found)[:6])))


if __name__ == '__main__':
    terminal.utf8()
    main(int(sys.argv[1]))
