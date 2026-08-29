"""The anchor into the game model: from the exe to a database of the game state, without searching.

The chain. A character is a `CCharacter` and the storage is `TPdxRefDatabase<CCharacter, 8>`. That
object has a vtable, so the class can be found by name in the exe. A global variable in the exe
points at the object; it sits at a fixed place within a build. From there:

    global -> database -> block table -> block -> record

**The same chain reaches the other databases of the game state** - cultures, faiths, religions -
because they are the same template with another type in it, and it reaches `CTraitDatabase`, which
is a different shape. `object_of` therefore takes the class name and a test for what makes an
address believable; `numbering.py` supplies both. Nothing here knows what sits inside a record.

This module stops at the database. **Walking the block table and reading a record is `model.py`**,
which also derives what sits where inside one; keeping both here would mean two places knowing the
same layout. The numbers are slot numbers without any shift: low numbers are filled with the dead
and with historical characters, the living sit above 32768.

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
CLASS = '.?AV?$TPdxRefDatabase@VCCharacter@@$07@@'
PER_BLOCK = 1024


def _model():
    return json.load(open(MODEL, encoding='utf-8'))


def _store(model):
    json.dump(model, open(MODEL, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


def vtables(pid, name=CLASS):
    """Every vtable address of the class carrying exactly this RTTI name.

    More than one is normal - multiple inheritance gives a class a vtable per base, and
    `CTraitDatabase` has two. None means the name is wrong rather than the class missing, so
    it stops instead of searching memory for something that cannot be there.
    """
    found = [rva for rva, written in memory.vtables_by_name(name).items() if written == name]
    if not found:
        raise SystemExit('no vtable named %s in the exe' % name)
    return [vtablemap.module_base(pid) + rva for rva in sorted(found)]


def is_ref_database(address):
    """Does this address carry a believable TPdxRefDatabase? A table, and counts that are not
    absurd. The stack copies fall away here by themselves: they have an empty table."""
    b = derive.read(address, 24)
    if b is None:
        return False
    table, count, capacity = struct.unpack_from('<QII', b, 8)
    return bool(table) and 0 < count <= capacity <= 100000


def find_objects(pid, name=CLASS, valid=is_ref_database):
    """Every believable object of this class, in the order memory gives them.

    Search on bytes 1 through 7 of the address: the first byte of an address in this range is
    zero, and a search starting with a zero byte cannot skip ahead and grinds to a halt.

    A class with two vtables has two sub-objects at two addresses, and only one of them is the
    object a global points at - `CTraitDatabase` is such a class. Returning the first believable
    one therefore is not enough; the caller decides which of them it can use.
    """
    found = []
    for vt in vtables(pid, name):
        pattern = struct.pack('<Q', vt)[1:].hex()
        answer = channel.ask('find ' + pattern, timeout=600)
        for line in answer.split('\n'):
            if not line.startswith('t\t'):
                continue
            address = int(line.split('\t')[1], 16) - 1
            head = derive.read(address, 8)
            if head is None or struct.unpack('<Q', head)[0] != vt:
                continue
            if valid(address) and address not in found:
                found.append(address)
    if not found:
        raise SystemExit('no object of %s found in memory' % name)
    return found


def derive_global(pid, name=CLASS, valid=is_ref_database, tries=4):
    """The offset of the global variable pointing at one of those objects.

    Search for pointers holding the value of the object and keep the hit that falls inside the
    module itself: that is a global, and its offset is fixed within a build.

    **Search on bytes 1 through 7 here too, not on all eight.** One address in 256 ends in a zero
    byte, and a search that starts on one cannot skip ahead; it crawls through eleven gigabytes.
    Measured 29 August 2026 on the religion database, which sat at ...100 and had not answered
    after twenty minutes. The hit then sits one byte past the pointer, so the eight bytes are read
    back to prove it really holds the address.
    """
    base = vtablemap.module_base(pid)
    for address in find_objects(pid, name, valid)[:tries]:
        answer = channel.ask('find ' + struct.pack('<Q', address)[1:].hex(), timeout=900)
        for line in answer.split('\n'):
            if not line.startswith('t\t'):
                continue
            where = int(line.split('\t')[1], 16) - 1
            if not base <= where < base + 0x6000000:
                continue
            held = derive.read(where, 8)
            if held is not None and struct.unpack('<Q', held)[0] == address:
                return where - base, address
    raise SystemExit('no global pointing at %s; only heap and stack copies' % name)


def object_of(pid, name=CLASS, valid=is_ref_database):
    """The object, from the stored offset or else derived again.

    Every database of the game state is reached this way: the character store, but also the
    cultures, faiths and religions that `numbering.py` reads. They differ only in their class
    name and in what makes an address believable, so both are arguments.
    """
    model = _model()
    base = vtablemap.module_base(pid)
    known = model.get('globals', {}) if model.get('key') == derive.build_key() else {}
    rva = known.get(name)
    if rva:
        b = derive.read(base + rva, 8)
        if b is not None:
            address = struct.unpack('<Q', b)[0]
            if valid(address):
                return address
    rva, address = derive_global(pid, name, valid)
    model['key'] = derive.build_key()
    model.setdefault('globals', {})[name] = rva
    _store(model)
    return address


def database(pid):
    """The character database."""
    return object_of(pid)


def size(pid, db=None):
    """How many blocks, and therefore how many character slots, this game state has."""
    header = derive.read(db or database(pid), 24)
    blocks = struct.unpack_from('<I', header, 16)[0]
    return blocks, blocks * PER_BLOCK


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    pid = int(sys.argv[1])
    db = database(pid)
    blocks, slots = size(pid, db)
    print('database at %x, %d blocks, %d character slots' % (db, blocks, slots))
    # Reading a character is `model.py`: this module's job ends at the database. Imported here
    # rather than at the top, because model imports this one.
    import model
    for number in [int(a) for a in sys.argv[2:]] or [32769]:
        print('%d -> %s' % (number, model.character(pid, number)))
