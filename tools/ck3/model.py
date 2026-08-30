r"""The character record laid out: which offset carries what, derived rather than written down.

There are two kinds of field and they need different treatment. A **scalar** sits in the record
itself - culture, faith, the dynasty house, the name. An **indirect** field sits in a block the
record points at: money in one, everything about levies and holdings in another. Both are derived
here against a save, and both are checked at every start without one.

**The answer key has to be a save written from the loaded state, not the save the state was loaded
from.** Measured 29 August 2026 on two states, one modded from 1067 and one vanilla from 867: the
seven levy fields are recomputed around loading and do not survive the round trip, so against the
file the game was started from they disagree for a third of all characters while every other field
agrees. Handing this routine the wrong save therefore produces a shifted-looking offset that is not
shifted, which is the most expensive kind of wrong answer this project can produce.

**Checking at start needs no save, and that is the point.** A stored derivation has to prove
itself against the running game every time, the way `derive.py` does it for the widget fields. The
predictions are structural: the handle in the record has to be the slot it was read from, the name
has to be a well formed string, every pointer has to lead somewhere readable, and the levy numbers
have to stand in the relations that hold by definition - a current strength cannot exceed a
maximum. Each of those can fail on a shifted offset, which is what makes them worth running.

Usage:
    python tools\ck3\model.py <pid>                 check the stored derivation
    python tools\ck3\model.py <pid> <save>          derive again against that save
    python tools\ck3\model.py <pid> --player <save> derive where the player is kept
"""
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import anchor
import channel
import derive
import paths
import savegame
import vtablemap

MODEL = os.path.join(paths.PROJECT, 'reports', 'model.json')
FIXED = 100000
STRING_IN_PLACE = 15

# The fields looked for, with where the save keeps them. `alive` and `landed` name the block of
# the character's save entry; the memory side is what this module derives.
WANTED = [
    ('culture', 'record', None),
    ('faith', 'record', None),
    ('dynasty_house', 'record', None),
    ('gold', 'alive', ('gold', 'value')),
    ('piety', 'alive', ('piety', 'currency')),
    ('prestige', 'alive', ('prestige', 'currency')),
    ('current_strength', 'landed', None),
    ('strength', 'landed', None),
    ('strength_for_liege', 'landed', None),
    ('strength_without_hires', 'landed', None),
    ('levy', 'landed', None),
    ('power', 'landed', None),
    ('max_power', 'landed', None),
    ('balance', 'landed', None),
    ('liege_tax', 'landed', None),
    ('dread', 'landed', None),
    ('domain_limit', 'landed', None),
]

# Relations that hold by definition, used to check the derivation without a save. Skipped for a
# character whose block is empty, because an unlanded one carries zeros and proves nothing.
RELATIONS = [
    ('current_strength', '<=', 'strength'),
    ('strength_without_hires', '<=', 'strength'),
    ('levy', '<=', 'current_strength'),
    ('power', '<=', 'max_power'),
]


def to_fixed(text):
    """A decimal from the save as the whole number the game keeps: the point moved five places.

    Through the digits and not through a float, because float arithmetic turns 36.06569 into
    3606568.9999 and the comparison then fails for a value that is perfectly right.
    """
    sign = -1 if text.startswith('-') else 1
    whole, _, fraction = text.lstrip('-+').partition('.')
    return sign * int(whole + (fraction + '00000')[:5])


def forms(text):
    """Every byte form this value could be kept in, named. Six of them, and naming them is the
    point: a negative result means nothing unless it says what was looked for."""
    out = {}
    if '.' not in text:
        whole = int(text)
        if -2 ** 31 <= whole < 2 ** 31:
            out[struct.pack('<i', whole)] = 'int32'
        out[struct.pack('<q', whole)] = 'int64'
    fixed = to_fixed(text)
    if -2 ** 31 <= fixed < 2 ** 31:
        out.setdefault(struct.pack('<i', fixed), 'fixed32')
    out.setdefault(struct.pack('<q', fixed), 'fixed64')
    out.setdefault(struct.pack('<f', float(text)), 'float32')
    out.setdefault(struct.pack('<d', float(text)), 'float64')
    return out


def value_of(chunk, offset, form):
    if form == 'int32':
        return struct.unpack_from('<i', chunk, offset)[0]
    if form in ('int64', 'fixed64'):
        return struct.unpack_from('<q', chunk, offset)[0]
    if form == 'fixed32':
        return struct.unpack_from('<i', chunk, offset)[0]
    if form == 'float32':
        return struct.unpack_from('<f', chunk, offset)[0]
    return struct.unpack_from('<d', chunk, offset)[0]


def stored():
    model = json.load(open(MODEL, encoding='utf-8'))
    return model if model.get('key') == derive.build_key() else None


def _store(model):
    json.dump(model, open(MODEL, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


def readmany(addresses, count):
    """Raw bytes per address, in questions whose answer stays under 32 kB.

    The command takes at most about 400 addresses; the answer has a limit too, and it is not
    written down anywhere. A round asking for hundreds of kilobytes at a time is the one thing
    suspected of taking the game down on 28 August 2026, so the answer is bounded here as well.
    Both bounds have to hold at once: asking for 32 bytes each would otherwise put over a
    thousand addresses in one command and the DLL refuses the command rather than trimming it.
    """
    out = {}
    per_question = max(1, min(400, 32768 // count))
    for start in range(0, len(addresses), per_question):
        part = addresses[start:start + per_question]
        answer = channel.ask('readmany %d %s' % (count, ' '.join('%x' % a for a in part)),
                             timeout=180)
        for line in answer.split('\n'):
            piece = line.split('\t')
            if piece[0] == 'l' and len(piece) > 2 and piece[2] != 'unreadable':
                out[int(piece[1], 16)] = bytes.fromhex(piece[2])
    return out


def _layout(pid):
    """Where every record starts, from the block table in one read."""
    model = json.load(open(MODEL, encoding='utf-8'))
    db = anchor.database(pid)
    header = derive.read(db, 24)
    table = struct.unpack_from('<Q', header, 8)[0]
    blocks = struct.unpack_from('<I', header, 16)[0]
    starts = struct.unpack('<%dQ' % blocks, derive.read(table, blocks * 8))
    return model, starts, blocks


def _record_address(starts, model, slot):
    per = model['block_size']
    return starts[slot // per] + (slot % per) * model['record_length'] \
        + model['number_field_in_record']


def records_for(pid, handles):
    """The bytes of each character's record, keyed by handle, with the wrong ones left out.

    A handle carries a generation in its top byte, so a slot can hold a different character than
    the one asked for. Checking that the record says what the caller asked for is the whole
    difference between reading a character and reading whoever took over its place.
    """
    model, starts, blocks = _layout(pid)
    mask = model['number_mask']
    length = model['record_length'] - model['number_field_in_record']
    where = {h: _record_address(starts, model, h & mask)
             for h in handles if (h & mask) // model['block_size'] < blocks}
    raw = readmany(sorted(where.values()), length)
    good = {}
    for handle, address in where.items():
        chunk = raw.get(address)
        if chunk and struct.unpack_from('<I', chunk, 0)[0] == handle:
            good[handle] = chunk
    return good, len(where) - len(good)


def answer_key(save_path, handles=None):
    """What the save says about every landed character, as the text the save writes.

    Kept as text on purpose: `power` is a whole number for one character and 34891.956 for the
    next, so deciding the byte form here would throw half the key away.
    """
    import re
    text = savegame.unpack(save_path)
    index = savegame.character_index(text)
    rows = {}
    for number in (handles if handles is not None else sorted(index)):
        if number not in index:
            continue
        start = index[number]
        body = text[start:text.find('\n}\n', start)]
        if 'current_strength=' not in body:
            continue
        sections = {'record': body,
                    'alive': savegame.block(body, 'alive_data') or '',
                    'landed': savegame.block(body, 'landed_data') or ''}
        row = {'name': body.split('first_name="', 1)[1].split('"', 1)[0]}
        for field, where, path in WANTED:
            section = sections[where]
            key = field
            if path:
                section, key = savegame.block(section, path[0]) or '', path[1]
            found = re.search(r'\b%s=(-?[\d.]+)' % key, section)
            row[field] = found.group(1) if found else None
        rows[number] = row
    return rows


def string_at(chunk, offset):
    """An MSVC string laid out in place: characters, then length, then capacity.

    Over fifteen characters the letters move behind a pointer and only that pointer is in the
    record, so this returns None and `long_string_at` says where to read. Measured 29 August 2026
    on four hundred characters of the Ghur state: 60 of them, so a reader that stops here is
    missing one name in seven.
    """
    if offset + 32 > len(chunk):
        return None
    length = struct.unpack_from('<Q', chunk, offset + 16)[0]
    capacity = struct.unpack_from('<Q', chunk, offset + 24)[0]
    if capacity != STRING_IN_PLACE or length > STRING_IN_PLACE:
        return None
    return chunk[offset:offset + length].decode('utf-8', 'replace')


def long_string_at(chunk, offset):
    """(address, length) of a string too long to sit in the record, or None."""
    if offset + 32 > len(chunk):
        return None
    length = struct.unpack_from('<Q', chunk, offset + 16)[0]
    capacity = struct.unpack_from('<Q', chunk, offset + 24)[0]
    if capacity <= STRING_IN_PLACE or not 0 < length <= capacity < 4096:
        return None
    address = struct.unpack_from('<Q', chunk, offset)[0]
    if not 0x10000000000 <= address < 0x800000000000:
        return None
    return address, length


def names_of(records, offset):
    """The name of every record, following the pointer for the long ones in one bulk read."""
    out, waiting = {}, {}
    for handle, chunk in records.items():
        text = string_at(chunk, offset)
        if text is not None:
            out[handle] = text
            continue
        far = long_string_at(chunk, offset)
        if far:
            waiting[handle] = far
    if waiting:
        longest = max(length for _, length in waiting.values())
        fetched = readmany(sorted({address for address, _ in waiting.values()}), longest)
        for handle, (address, length) in waiting.items():
            raw = fetched.get(address)
            if raw is not None:
                out[handle] = raw[:length].decode('utf-8', 'replace')
    return out


def _best(counts, asked):
    """The place that holds for at least nineteen in twenty, and its form.

    Where a value fits both a four and an eight byte form the wider one is kept: a negative amount
    of gold sign-extends into the upper half, measured 28 August 2026, so the field really is
    eight bytes and the narrow match is the low half of it.
    """
    order = {'int32': 0, 'fixed64': 1, 'int64': 2, 'fixed32': 3, 'float64': 4, 'float32': 5}
    good = [(place, form, hits) for (place, form), hits in counts.items()
            if asked and hits >= 0.95 * asked]
    if not good:
        return None
    good.sort(key=lambda row: (-row[2], order.get(row[1], 9), row[0]))
    return good[0]


def derive_all(pid, rows, block_bytes=1024):
    """Every offset, found by laying the save beside the memory of the running game.

    A place counts only when it works for nineteen out of twenty characters rather than for one.
    That is what separates a field from a number that happened to sit somewhere once, and it is
    the reason this takes eighty characters instead of the player.
    """
    good, wrong = records_for(pid, list(rows))
    if len(good) < 20:
        raise SystemExit('only %d of %d records could be read and matched; too few to derive on'
                         % (len(good), len(rows)))
    length = len(next(iter(good.values())))

    name_counts, name_asked = {}, 0
    for handle, chunk in good.items():
        wanted = rows[handle]['name']
        if not wanted.isalpha():
            continue
        name_asked += 1
        for offset in range(0, length - 32, 8):
            if string_at(chunk, offset) == wanted:
                name_counts[(offset, 'string')] = name_counts.get((offset, 'string'), 0) + 1
    name = _best(name_counts, name_asked)
    if not name:
        raise SystemExit('no offset carries the name of nineteen in twenty characters')

    patterns, asked = {}, {}
    for handle, chunk in good.items():
        table = {}
        for field, _, _ in WANTED:
            text = rows[handle].get(field)
            if text is None:
                continue
            asked[field] = asked.get(field, 0) + 1
            for pattern, form in forms(text).items():
                table.setdefault(pattern, []).append((field, form))
        patterns[handle] = table

    scalar = {}
    for handle, chunk in good.items():
        for offset in range(0, length - 8):
            for width in (4, 8):
                for field, form in patterns[handle].get(chunk[offset:offset + width], ()):
                    scalar[(field, offset, form)] = scalar.get((field, offset, form), 0) + 1

    pointers = None
    for chunk in good.values():
        here = {offset for offset in range(0, length - 8, 8)
                if 0x10000000000 <= struct.unpack_from('<Q', chunk, offset)[0] < 0x800000000000}
        pointers = here if pointers is None else (pointers & here)

    indirect = {}
    for pointer_offset in sorted(pointers):
        targets = {h: struct.unpack_from('<Q', c, pointer_offset)[0] for h, c in good.items()}
        chunks = readmany(sorted(set(targets.values())), block_bytes)
        for handle in good:
            chunk = chunks.get(targets[handle])
            if chunk is None:
                continue
            for offset in range(0, len(chunk) - 8):
                for width in (4, 8):
                    for field, form in patterns[handle].get(chunk[offset:offset + width], ()):
                        spot = (field, pointer_offset, offset, form)
                        indirect[spot] = indirect.get(spot, 0) + 1
    return good, wrong, name, asked, scalar, indirect


def build(pid, rows, block_bytes=1024, against=None):
    """Derive and fold the result into the model, keeping the offsets relative to the handle
    field - the base `reports\\claims.json` and `check.py` already count against."""
    good, wrong, name, asked, scalar, indirect = derive_all(pid, rows, block_bytes)
    model = json.load(open(MODEL, encoding='utf-8'))
    fields, places, evidence = {}, {}, {}

    for field, _, _ in WANTED:
        direct = {(offset, form): hits for (f, offset, form), hits in scalar.items() if f == field}
        chosen = _best(direct, asked.get(field, 0))
        if chosen:
            fields[field] = chosen[0]
            evidence[field] = '%d of %d in the record' % (chosen[2], asked[field])
            continue
        through = {}
        for (f, pointer, offset, form), hits in indirect.items():
            if f == field:
                through[((pointer, offset), form)] = hits
        chosen = _best(through, asked.get(field, 0))
        if not chosen:
            evidence[field] = 'nowhere, in none of the six forms (%d characters carry it)' \
                % asked.get(field, 0)
            continue
        (pointer, offset), form, hits = chosen
        places[field] = {'pointer': pointer, 'offset': offset, 'form': form}
        evidence[field] = '%d of %d through the pointer at +0x%03x' % (hits, asked[field], pointer)

    model['key'] = derive.build_key()
    model['name'] = {'offset': name[0], 'form': 'string'}
    model['fields'] = fields
    model['indirect'] = places
    model['evidence'] = evidence
    # Which save it was derived against belongs in the file. A save carries the state that wrote
    # it, so an offset table without its provenance is a number nobody can put back in context.
    model['derived_on'] = '%s, %d characters, %d records unreadable or reused, against %s' \
        % (time.strftime('%Y-%m-%d'), len(good), wrong, against or 'an unnamed save')
    _store(model)
    return model


def sample_slots(pid, wanted=200):
    """Slots spread over the whole database, with what their record says about itself.

    Spread rather than the first few: the low numbers are the dead and the historical, and a check
    that only ever looks at those proves nothing about the ones a player meets.
    """
    model, starts, blocks = _layout(pid)
    slots = blocks * model['block_size']
    step = max(1, slots // wanted)
    picked = list(range(0, slots, step))[:wanted]
    length = model['record_length'] - model['number_field_in_record']
    where = {slot: _record_address(starts, model, slot) for slot in picked}
    raw = readmany(sorted(where.values()), length)
    out = {}
    for slot, address in where.items():
        chunk = raw.get(address)
        if chunk:
            out[slot] = chunk
    return model, out


def check(pid, wanted=400):
    """Does the stored derivation still hold against the game running right now?

    Four predictions, each able to fail on a shifted offset, and none of them needing a save.
    """
    defects = []
    model, records = sample_slots(pid, wanted)
    if not records:
        return ['no record could be read at all; is a game loaded?']

    mask = model['number_mask']
    own = sum(1 for slot, chunk in records.items()
              if struct.unpack_from('<I', chunk, 0)[0] & mask == slot)
    if own < 0.9 * len(records):
        defects.append('only %d of %d records carry the slot they were read from, so the record '
                       'length or the handle offset has moved' % (own, len(records)))

    if 'name' in model:
        readable = 0
        for text in names_of(records, model['name']['offset']).values():
            if text and len(text) >= 2 and text.isprintable():
                readable += 1
        if readable < 0.5 * len(records):
            defects.append('only %d of %d records hold a readable name at +0x%03x'
                           % (readable, len(records), model['name']['offset']))

    places = model.get('indirect', {})
    targets, per_pointer = {}, {}
    for field, place in places.items():
        per_pointer.setdefault(place['pointer'], []).append(field)
    for pointer in per_pointer:
        here = {}
        for slot, chunk in records.items():
            value = struct.unpack_from('<Q', chunk, pointer)[0]
            if 0x10000000000 <= value < 0x800000000000:
                here[slot] = value
        # A missing pointer is not a defect. Measured 29 August 2026 over 200 slots spread across
        # the whole database: 51 carry no money block and 171 no landed block, because most
        # characters are neither alive nor a ruler. What would be a defect is too few to check on.
        if len(here) < 20:
            defects.append('only %d of %d records carry the pointer at +0x%03x, too few to '
                           'check it against' % (len(here), len(records), pointer))
        targets[pointer] = (here, readmany(sorted(set(here.values())), 0x400))

    live = {}
    for slot in records:
        values = {}
        for field, place in places.items():
            here, chunks = targets[place['pointer']]
            chunk = chunks.get(here.get(slot))
            if chunk is not None and place['offset'] + 8 <= len(chunk):
                values[field] = value_of(chunk, place['offset'], place['form'])
        live[slot] = values

    for left, how, right in RELATIONS:
        if left not in places or right not in places:
            continue
        held = broken = 0
        for values in live.values():
            if left not in values or right not in values or values[right] <= 0:
                continue
            if values[left] <= values[right]:
                held += 1
            else:
                broken += 1
        if held + broken >= 20 and held < 0.95 * (held + broken):
            defects.append('%s %s %s fails for %d of the %d characters where it applies'
                           % (left, how, right, broken, held + broken))

    # A shifted offset usually lands on an identifier or half a pointer, and those are enormous.
    # The band is wide on purpose: it is here to catch nonsense, not to judge a rich duke.
    for field, place in places.items():
        limit = 10 ** 11 if place['form'].startswith('fixed') else 10 ** 7
        seen = [values[field] for values in live.values() if field in values]
        wild = [value for value in seen if abs(value) > limit]
        if len(seen) >= 20 and len(wild) > 0.05 * len(seen):
            defects.append('%s is outside any believable range for %d of the %d characters that '
                           'carry it' % (field, len(wild), len(seen)))
    return defects


def character(pid, handle, records=None):
    """Every field of one character: the scalars from the record, the rest through the pointers."""
    model = json.load(open(MODEL, encoding='utf-8'))
    good = records or records_for(pid, [handle])[0]
    if handle not in good:
        raise ValueError('character %d is not in the database, or the slot was reused' % handle)
    chunk = good[handle]
    values = {'number': struct.unpack_from('<I', chunk, 0)[0] & model['number_mask'],
              'generation': struct.unpack_from('<I', chunk, 0)[0] >> 24}
    if 'name' in model:
        values['name'] = names_of({handle: chunk}, model['name']['offset']).get(handle)
    for field, offset in model['fields'].items():
        values[field] = struct.unpack_from('<i', chunk, offset)[0]
    for pointer in {p['pointer'] for p in model.get('indirect', {}).values()}:
        address = struct.unpack_from('<Q', chunk, pointer)[0]
        block = derive.read(address, 0x400)
        for field, place in model.get('indirect', {}).items():
            if place['pointer'] == pointer and block is not None:
                values[field] = value_of(block, place['offset'], place['form'])
    return values


MODULE_SPAN = 0x6000000


def derive_player(pid, number):
    """Where the module keeps the handle of the character being played, derived against a save.

    The game does not keep a pointer to the player's record: searching all of memory for the
    address of that record gave exactly one hit, on the heap, with no class around it. What it
    keeps is the handle, the way it refers to a character everywhere else, and it keeps it inside
    the module, where a place is fixed within a build.

    Measured 30 August 2026 on the administrative state: six places in the module held 50149, the
    number the save writes down for its player. All six followed a mod event that moved the player
    to another character, and all six followed a load of another state. So they are kept as six
    witnesses rather than narrowed down to one: four bytes is a weak pattern, and a disagreement
    between them is worth hearing about instead of being resolved by picking a favourite.

    **Search on all four bytes.** The seven-byte search `anchor.derive_global` has to use for
    addresses would be wrong here for another reason: records sit next to each other, so a pattern
    that leaves out the low byte matches every neighbour in the block, and the DLL stops reporting
    at two hundred hits long before the real one appears.
    """
    base = vtablemap.module_base(pid)
    pattern = struct.pack('<I', number).hex()
    if pattern[:2] == '00':
        raise SystemExit('character %d begins with a zero byte, so it cannot lead a search; '
                         'derive against a state whose player has another number' % number)
    answer = channel.ask('findin %x %x %s' % (base, base + MODULE_SPAN, pattern), timeout=900)
    spots = [int(line.split('\t')[1], 16) - base
             for line in answer.split('\n') if line.startswith('t\t')]
    if not spots:
        raise SystemExit('no place in the module holds %d; either this is not the player of the '
                         'state that is loaded, or the game keeps him somewhere else now' % number)
    model = json.load(open(MODEL, encoding='utf-8'))
    model['key'] = derive.build_key()
    model['player_spots'] = ['%x' % spot for spot in sorted(spots)]
    model['player_derived_on'] = time.strftime('%Y-%m-%d %H:%M') + ' against character %d' % number
    _store(model)
    return sorted(spots)


def player(pid):
    """The handle of the character being played, and the name that goes with it.

    Every stored place has to say the same thing and the answer has to be a character the database
    knows, because a stop condition that quietly returns nonsense is worse than none: a state that
    has been moved to another character looks perfectly normal from the tree - the date is right,
    the windows are there - and everything measured after it is about somebody else.
    """
    model = stored()
    if model is None or not model.get('player_spots'):
        raise SystemExit('there is no derivation of where the player is kept for this build; '
                         'run `python tools\\ck3\\model.py <pid> --player <save>` on the state '
                         'that save belongs to')
    base = vtablemap.module_base(pid)
    spots = [base + int(spot, 16) for spot in model['player_spots']]
    raw = readmany(spots, 4)
    missing = [s for s in spots if s not in raw]
    if missing:
        raise SystemExit('%d of the %d places the player is kept in cannot be read'
                         % (len(missing), len(spots)))
    values = {struct.unpack('<I', raw[s])[0] for s in spots}
    if len(values) > 1:
        raise SystemExit('the %d places that hold the player disagree: %s. One of them is not the '
                         'player after all, so the derivation has to be done again'
                         % (len(spots), ', '.join(str(v) for v in sorted(values))))
    handle = values.pop()
    good, _ = records_for(pid, [handle])
    if handle not in good:
        raise SystemExit('the player reads as %d, and the character database has no such '
                         'character; the derivation no longer holds' % handle)
    name = names_of(good, stored()['name']['offset']).get(handle)
    return handle, name


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__.strip().splitlines()[-2].strip())
    pid = int(sys.argv[1])
    vtablemap.configure(pid)
    derive.configure_channel(derive.stored())

    if len(sys.argv) > 3 and sys.argv[2] == '--player':
        path = sys.argv[3]
        if not os.path.isabs(path):
            path = os.path.join(savegame.SAVE_DIR, path)
        number = savegame.player(savegame.unpack(path))
        spots = derive_player(pid, int(number))
        print('%s says its player is %s; %d places in the module hold it: %s'
              % (os.path.basename(path), number, len(spots),
                 ', '.join('+%x' % spot for spot in spots)))
        handle, name = player(pid)
        print('reading it back gives %d, %s' % (handle, name))
        return

    if len(sys.argv) > 2:
        path = sys.argv[2]
        if not os.path.isabs(path):
            path = os.path.join(savegame.SAVE_DIR, path)
        print('deriving against %s' % os.path.basename(path))
        rows = answer_key(path)
        spread = sorted(rows)[::max(1, len(rows) // 80)][:80]
        model = build(pid, {h: rows[h] for h in spread}, against=os.path.basename(path))
        print('%s\n' % model['derived_on'])
        print('name at +0x%03x' % model['name']['offset'])
        for field, _, _ in WANTED:
            if field in model['fields']:
                print('   %-24s record +0x%03x            %s'
                      % (field, model['fields'][field], model['evidence'][field]))
            elif field in model['indirect']:
                place = model['indirect'][field]
                print('   %-24s record +0x%03x -> +0x%03x %-8s %s'
                      % (field, place['pointer'], place['offset'], place['form'],
                         model['evidence'][field]))
            else:
                print('   %-24s %s' % (field, model['evidence'][field]))
        print('')

    if stored() is None:
        raise SystemExit('there is no derivation for this build; give a save to derive against')
    defects = check(pid)
    for defect in defects:
        print('DEFECT: %s' % defect)
    print('the stored derivation %s' % ('has %d defects' % len(defects) if defects
                                        else 'holds against the running game'))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    main()


# Recomputed around loading, so the file the game was started from disagrees with memory for them.
# Measured 29 August 2026 on two states: against the save loaded from, the seven below disagree
# for a third of all characters while every other field agrees to the unit; against a save written
# from the loaded state, all of them agree for all characters.
RECOMPUTED_ON_LOAD = ('current_strength', 'strength', 'strength_for_liege',
                      'strength_without_hires', 'levy', 'power', 'max_power')


def compare(pid, save_path, count=400):
    """Every derived field of many characters, laid beside the save. The regression test.

    Returns per field how often memory and save agree, split into the fields that survive a load
    and the seven that do not - because a disagreement in the second group says the answer key is
    the wrong file, and a disagreement in the first says a field has moved.
    """
    model, starts, blocks = _layout(pid)
    slots = blocks * model['block_size']
    rows = answer_key(save_path)
    handles = [h for h in sorted(rows)][::max(1, len(rows) // count)][:count] or list(rows)
    good, wrong = records_for(pid, handles)
    pointers = {p['pointer'] for p in model.get('indirect', {}).values()}
    blocks_read = {}
    for pointer in pointers:
        targets = {h: struct.unpack_from('<Q', c, pointer)[0] for h, c in good.items()}
        blocks_read[pointer] = (targets, readmany(sorted(set(targets.values())), 0x400))

    counters, misses = {}, []
    names = names_of(good, model['name']['offset']) if 'name' in model else {}
    for handle, chunk in good.items():
        live = {}
        if handle in names:
            live['name'] = names[handle]
        for field, offset in model['fields'].items():
            live[field] = struct.unpack_from('<i', chunk, offset)[0]
        for field, place in model.get('indirect', {}).items():
            targets, chunks = blocks_read[place['pointer']]
            block = chunks.get(targets.get(handle))
            if block is not None:
                live[field] = value_of(block, place['offset'], place['form'])
        for field, text in rows[handle].items():
            if text is None or field not in live or live[field] is None:
                continue
            form = model.get('indirect', {}).get(field, {}).get('form', 'int32')
            if field == 'name':
                # No conversion is needed here, and that was measured rather than assumed on
                # 29 August 2026: the record holds exactly the form the save writes, `SU_rI_` and
                # not `Sūrī`, for all 73 substituted names among four hundred characters. Turning
                # that key into the name a player hears is the presentation layer's job.
                agrees = live[field] == text
            elif form.startswith('fixed'):
                agrees = live[field] == to_fixed(text)
            elif '.' in text:
                continue
            else:
                agrees = live[field] == int(text)
            ok, total = counters.get(field, (0, 0))
            counters[field] = (ok + (1 if agrees else 0), total + 1)
            if not agrees and len(misses) < 5:
                misses.append('%s of character %d: memory %s, save %s'
                              % (field, handle, live[field], text))
    return counters, len(good), wrong, misses, slots
