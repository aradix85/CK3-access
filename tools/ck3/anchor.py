"""The anchor into the game model: from the exe to a character, without searching.

The chain. A character is a `CCharacter` and the storage is `TPdxRefDatabase<CCharacter, 8>`. That
object has a vtable, so the class can be found by name in the exe. A global variable in the exe
points at the object; it sits at a fixed place within a build. From there:

    global -> database -> block table -> block -> record

Character N lives in block `N // 1024`, record `N % 1024`, and the record starts 24 bytes before
the field carrying its number. The numbers are slot numbers without any shift: low numbers are
filled with the dead and with historical characters, the living sit above 32768.

Why this still works after a patch. None of it is written down. The vtable comes from the exe, the
offset of the global is derived and stored under a key made from that same exe, and at every start
it is recomputed: if the object's vtable checks out and the block counts are sane, it is still
good; if that check fails, it is derived again. That is the same setup as `derive.py` uses for the
widget fields, and for the same reason.

Deriving costs about two and a half minutes, rechecking a fraction of a second.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import derive
import vtablemap
import memory
import channel

PROJECT = os.path.dirname(os.path.dirname(HERE))
MODEL = os.path.join(PROJECT, 'reports', 'model.json')
CLASS = 'TPdxRefDatabase@VCCharacter@@'
PER_BLOCK = 1024


def _model():
    return json.load(open(MODEL, encoding='utf-8'))


def _store(model):
    json.dump(model, open(MODEL, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


def vtable(pid):
    """The address of the character database's vtable in the running game."""
    candidates = memory.vtables_by_name(CLASS)
    exact = [rva for rva, name in candidates.items() if name.startswith('.?AV?$' + CLASS)]
    if len(exact) != 1:
        raise SystemExit('expected one vtable for %s, found %d' % (CLASS, len(exact)))
    return vtablemap.module_base(pid) + exact[0]


def _valid(address, vt):
    """Does this address carry a believable database? Four bytes of vtable, a table, and counts
    that are not absurd. The stack copies of the vtable fall away here by themselves: they have
    an empty table."""
    b = derive.read(address, 24)
    if b is None or struct.unpack_from('<Q', b, 0)[0] != vt:
        return None
    table = struct.unpack_from('<Q', b, 8)[0]
    count = struct.unpack_from('<I', b, 16)[0]
    capacity = struct.unpack_from('<I', b, 20)[0]
    if not table or count == 0 or count > capacity or capacity > 100000:
        return None
    return table, count, capacity


def find_database(pid):
    """Find the database by searching memory for its vtable.

    Search on bytes 1 through 7 of the address: the first byte of an address in this range is
    zero, and a search starting with a zero byte cannot skip ahead and grinds to a halt.
    """
    vt = vtable(pid)
    pattern = struct.pack('<Q', vt)[1:].hex()
    answer = channel.ask('find ' + pattern, timeout=600)
    for line in answer.split('\n'):
        if not line.startswith('t\t'):
            continue
        address = int(line.split('\t')[1], 16) - 1
        if _valid(address, vt):
            return address
    raise SystemExit('no database found with this vtable')


def derive_global(pid):
    """The offset of the global variable pointing at the database.

    Search for pointers holding the value of the database object and keep the hit that falls
    inside the module itself: that is a global, and its offset is fixed within a build.
    """
    db = find_database(pid)
    base = vtablemap.module_base(pid)
    answer = channel.ask('find ' + struct.pack('<Q', db).hex(), timeout=900)
    in_module = [int(r.split('\t')[1], 16) for r in answer.split('\n')
                     if r.startswith('t\t') and base <= int(r.split('\t')[1], 16) < base + 0x6000000]
    if not in_module:
        raise SystemExit('no global pointing at the database; only heap and stack copies')
    return in_module[0] - base, db


def database(pid):
    """The database object, from the stored offset or else derived again."""
    model = _model()
    base = vtablemap.module_base(pid)
    vt = vtable(pid)
    rva = model.get('global_rva') if model.get('key') == derive.build_key() else None
    if rva:
        b = derive.read(base + rva, 8)
        if b is not None:
            address = struct.unpack('<Q', b)[0]
            if _valid(address, vt):
                return address
    rva, address = derive_global(pid)
    model['key'] = derive.build_key()
    model['global_rva'] = rva
    _store(model)
    return address


def character(pid, number, db=None):
    """The fields of character N, computed rather than searched for.

    A number outside the blocks is a caller's mistake and not an edge case: the number of blocks
    is in the database and can be asked for with `size`.
    """
    model = _model()
    db = db or database(pid)
    header = derive.read(db, 24)
    table = struct.unpack_from('<Q', header, 8)[0]
    blocks = struct.unpack_from('<I', header, 16)[0]
    if number // PER_BLOCK >= blocks:
        raise ValueError('character %d falls outside the %d blocks (at most %d)'
                         % (number, blocks, blocks * PER_BLOCK - 1))
    block = struct.unpack('<Q', derive.read(table + (number // PER_BLOCK) * 8, 8))[0]
    pos = block + (number % PER_BLOCK) * model['record_length'] + model['number_field_in_record']
    raw = derive.read(pos, max(model['fields'].values()) + 8)
    if raw is None:
        raise ValueError('record of character %d unreadable at %x' % (number, pos))
    values = {name: struct.unpack_from('<i', raw, offset)[0]
               for name, offset in model['fields'].items()}
    handle = struct.unpack_from('<I', raw, 0)[0]
    values['number'] = handle & model['number_mask']
    values['generation'] = handle >> 24
    return pos, values


def size(pid, db=None):
    """How many blocks, and therefore how many character slots, this game state has."""
    header = derive.read(db or database(pid), 24)
    blocks = struct.unpack_from('<I', header, 16)[0]
    return blocks, blocks * PER_BLOCK


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    pid = int(sys.argv[1])
    db = database(pid)
    print('database at %x' % db)
    for number in [int(a) for a in sys.argv[2:]] or [32769]:
        pos, values = character(pid, number, db)
        print('%d at %x -> %s' % (number, pos, values))
