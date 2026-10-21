"""Derives the field offsets of a widget object from the running game, through the channel.

Why this exists: without derivation the offsets are fixed numbers from one build, and everything
breaks at the next patch.

How it works, at two speeds:
  - deriving starts with a full memory scan, 21 seconds on a loaded game of 1.20 (measured 4 October
    2026). The result belongs to the exe, not to the session, so it goes to disk under a key made
    from that exe.
  - rechecking costs three to four seconds once a root of the tree is found, and finding one from
    seed widgets took 2.4 to 9.6 seconds on the same game (measured 4 October 2026, two starts).
    Both happen at every start. If the check fails, the stored derivation has expired and everything
    is derived again.

Every prediction below is one that can only come true for the right field. If a field cannot be
found, this file stops hard and names that field.
"""
import json
import math
import os
import pathlib
import struct
import sys
import time
from collections.abc import Iterable, Iterator
from typing import NotRequired, TypedDict

from tools import paths
from tools.ck3 import channel, guimap, memory, onscreen, vtablemap, widgettree
from tools.nvda import speech

STORED = os.path.join(paths.REPORTS, 'fields.json')
CHUNK = 0x420          # roomier than the largest widget object


class Fields(TypedDict):
    """A derivation, as `fields.json` keeps it: the build it holds for, the seven offsets the channel
    walks with, three counts from the scan and what the scan skipped, the two visibility offsets
    a state with a window to open adds, and the route to the tooltip root once it is asked for."""
    key: str
    parent: int
    children: int
    count: int
    position: int
    size: int
    name: int
    text: int
    objects: int
    unreadable: int
    roots: int
    flag: NotRequired[int]
    alpha: NotRequired[int]
    skipped: NotRequired[str]
    gui_global: NotRequired[int]     # from the exe base: a global holding the object with the layer roots
    root_slot: NotRequired[int]      # in that object: the root of the tree, the tooltip root right after


# What a search in the DLL left out, per kind: kind -> (regions, bytes).
Skips = dict[str, tuple[int, int]]
SKIP_WORDS = {'own stack': "the channel's own stack", 'uncached': 'memory without a cache'}


def build_key() -> str:
    """How you tell it is still the same build. If the exe changes, everything lapses."""
    st = os.stat(paths.require('EXE'))
    return f'{int(st.st_size)}-{int(st.st_mtime)}'


def scan(from_address: int, to_address: int) -> tuple[dict[int, int], Skips]:
    """Address -> vtable, and what the scan left out. Both come from the vtable comparison and do
    not depend on the field offsets we are looking for."""
    found: dict[int, int] = {}
    answer = channel.ask(f'scan {from_address:x} {to_address:x}' if to_address else 'scan', timeout=300)
    for line in answer.split('\n'):
        part = line.split('\t')
        if part[0] == 'w':
            found[int(part[1], 16)] = int(part[2], 16)
    return found, skips(answer)


def skips(answer: str) -> Skips:
    """What a scan or find left out. The DLL skips the stacks of its own threads, where copies of
    what it was handed sit, and write-combined or uncached memory, which the processor shares with
    the graphics card; it says so on a line per kind, with regions and bytes."""
    found: Skips = {}
    for line in answer.split('\n'):
        part = line.split('\t')
        if part[0] in SKIP_WORDS:
            found[part[0]] = (int(part[1]), int(part[2]))
    return found


def skipped(*searches: Skips) -> str:
    """What one or more searches left out, summed, as a clause; empty when nothing was.

    Every search that comes back empty carries this, or "not found" reads as "not there".
    """
    total: dict[str, list[int]] = {}
    for one in searches:
        for kind, (regions, size) in one.items():
            tally = total.setdefault(kind, [0, 0])
            tally[0] += regions
            tally[1] += size
    return '; '.join(f"skipped {regions} region{'' if regions == 1 else 's'} of {SKIP_WORDS[kind]}, "
                     + (f'{size >> 10} kB' if size < 2**20 else f'{size >> 20} MB')
                     for kind, (regions, size) in total.items())


def tree(root: int) -> dict[int, int]:
    found: dict[int, int] = {}
    for line in channel.ask(f'tree {root:x}', timeout=60).split('\n'):
        part = line.split('\t')
        if part[0] == 'w':
            found[int(part[1], 16)] = int(part[2], 16)
    return found


def chunks_of(addresses: Iterable[int]) -> tuple[dict[int, bytes], int]:
    """Raw bytes per object. Unreadable ones are skipped and counted, not hidden."""
    chunks: dict[int, bytes] = {}
    failed = 0
    for address in addresses:
        b = channel.read(address, CHUNK)
        if b is None:
            failed += 1
        else:
            chunks[address] = b
    return chunks, failed


def _pair(chunk: bytes, offset: int) -> tuple[float, float]:
    first, second = struct.unpack_from('<ff', chunk, offset)
    return first, second


def _parent_field(chunks: dict[int, bytes], addresses: set[int]) -> int:
    """Prediction: the parent field forms a forest. Every chain ends at a root and there are no
    cycles. A sibling or neighbour pointer points at a widget just as often but loops around, and
    drops out on that."""
    best: tuple[int, int] | None = None
    for offset in range(0, CHUNK - 8, 8):
        parent: dict[int, int] = {}
        for address, b in chunks.items():
            value = int.from_bytes(b[offset:offset + 8], 'little')
            parent[address] = value if value in addresses else 0
        if len(set(parent.values()) - {0}) < 2:
            continue
        ends = 0
        for address in parent:
            seen: set[int] = set()
            p, depth = address, 0
            while p and depth < 40:
                if p in seen:
                    break
                seen.add(p)
                p = parent.get(p, 0)
                depth += 1
            if p == 0:
                ends += 1
        if ends < 0.99 * len(parent):
            continue
        if best is None or ends > best[1]:
            best = (offset, ends)
    if best is None:
        raise SystemExit('deriving failed on field: parent (no field where nearly every '
                         'chain ends at a root)')
    return best[0]


def children_from_parents(chunks: dict[int, bytes], f_parent: int,
                          addresses: set[int]) -> dict[int, set[int]]:
    from_address: dict[int, set[int]] = {}
    for address, b in chunks.items():
        value = int.from_bytes(b[f_parent:f_parent + 8], 'little')
        if value in addresses:
            from_address.setdefault(value, set()).add(address)
    return from_address


def _count_field(chunks: dict[int, bytes], children_of: dict[int, set[int]]) -> int:
    """Prediction: a 32-bit number that equals the number of children for every parent.

    The requirement is overwhelming majority, not perfection. The interface moves while it is being
    read - the main menu animates - so one parent whose count changes midway is normal. Measured
    27 July 2026: +0x0FC explained 942 of 943 parents, the runner-up 861. A demand of 943 out of
    943 would fail such a result, and that is not strictness but brittleness.
    """
    tally: dict[int, int] = {}
    for offset in range(0, CHUNK - 4, 4):
        hit = sum(1 for parent, children in children_of.items()
                   if parent in chunks
                   and int.from_bytes(chunks[parent][offset:offset + 4], 'little') == len(children))
        if hit:
            tally[offset] = hit
    best = sorted(tally.items(), key=lambda p: -p[1])
    if not best:
        raise SystemExit('deriving failed on field: child count (not a single candidate)')
    offset, hit = best[0]
    runner_up = best[1][1] if len(best) > 1 else 0
    if hit < 0.95 * len(children_of):
        raise SystemExit(
            f'deriving failed on field: child count (best +0x{offset:03X} explains {int(hit)} of {len(children_of)}, '
            f'runner-up {int(runner_up)})')
    print(f'count: +0x{offset:03X} explains {int(hit)} of {len(children_of)} parents, runner-up {int(runner_up)}')
    return offset


def _child_field(chunks: dict[int, bytes], children_of: dict[int, set[int]]) -> int:
    """Prediction: a pointer to a block containing exactly the children that name this object as
    their parent. Equal, not overlapping."""
    samples: int = 20
    probe = [o for o in sorted(children_of, key=lambda k: -len(children_of[k]))
             if o in chunks][:samples]
    best: tuple[int | None, int] = (None, 0)
    for offset in range(0, CHUNK - 8, 8):
        ok = 0
        for parent in probe:
            children = children_of[parent]
            pointer = int.from_bytes(chunks[parent][offset:offset + 8], 'little')
            if pointer < 0x10000 or len(children) > 500:
                continue
            b = channel.read(pointer, len(children) * 8)
            if b is None:
                continue
            block = {int.from_bytes(b[i:i + 8], 'little') for i in range(0, len(b), 8)}
            if block == children:
                ok += 1
        if ok == len(probe):
            return offset
        if ok > best[1]:
            best = (offset, ok)
    if best[0] is not None and best[1] >= max(3, 0.8 * len(probe)):
        return best[0]
    raise SystemExit(f'deriving failed on field: child list (best explained {int(best[1])} of {len(probe)} parents)')


# The predictions a field is found by, and a stored derivation is checked against at every start,
# with one threshold each, so that deriving and rechecking cannot drift apart.
SPREAD = 100        # a position field holds at least this many places across the sample
FAMILIES = 0.9      # and spreads the children of at least this share of the families
GUI_NAMES = 0.6     # of at least twenty names, this share stands literally in the gui files


def _in_proportion(width: float, height: float, window_width: int, window_height: int) -> bool:
    """Does a root of this size span the whole gui space: the same scale on both axes against the
    drawing area, and a scale a game could be set to?"""
    if not (width >= 100.0 and height >= 100.0):
        return False
    scale_x, scale_y = window_width / width, window_height / height
    return abs(scale_x - scale_y) < 0.005 and 0.4 <= scale_x <= 2.5


def _gui_names(names: set[str], gui: str) -> int:
    """How many of these names stand in the gui files, or 0 when that is not most of at least
    twenty."""
    hit = sum(1 for n in names if n in gui)
    return hit if len(names) >= 20 and hit >= GUI_NAMES * len(names) else 0


def _position_like(chunks: dict[int, bytes], f_parent: int, offset: int) -> tuple[bool, int, float | None]:
    """(does it hold, distinct places, share of families spread) for a candidate position field."""
    distinct = _spread(chunks, offset)
    families = _siblings_spread(chunks, f_parent, offset) if distinct >= SPREAD else None
    return families is not None and families >= FAMILIES, distinct, families


def _size_field(chunks: dict[int, bytes], roots: list[int], window_width: int,
                window_height: int) -> int:
    """Prediction: a root widget spans the entire GUI space.

    That space is not the screen size. There is a GUI scale in between, and it is not reliably on
    disk - the game changes it itself as soon as the resolution changes. So it is not asked for but
    derived: at the right offset a root holds a pair of floats that yields the same scale on both
    axes relative to the window's drawing area. A field that is zero everywhere fails this, and a
    random pair almost never hits the window's ratio.
    """
    for offset in range(0, CHUNK - 8, 4):
        for root in roots:
            if root not in chunks:
                continue
            if _in_proportion(*_pair(chunks[root], offset), window_width, window_height):
                return offset
    raise SystemExit('deriving failed on field: size (no root in proportion with the '
                     f'drawing area of {int(window_width)}x{int(window_height)})')


def _spread(chunks: dict[int, bytes], offset: int) -> int:
    values: set[tuple[float, float]] = set()
    for b in chunks.values():
        x, y = _pair(b, offset)
        if not math.isnan(x) and not math.isnan(y) and abs(x) < 1e6 and abs(y) < 1e6:
            values.add((round(x, 1), round(y, 1)))
    return len(values)


def _siblings_spread(chunks: dict[int, bytes], f_parent: int, offset: int) -> float | None:
    """Do the children of one parent sit in different places?

    This is what separates the position field from a field that is almost always (0,0). "Every
    child fits inside its parent" is trivially true for a field holding zero, so on a loaded game
    the derivation picked +0x32C, which holds two distinct values over four hundred widgets, above
    the +0x118 that the recogniser confirms. Siblings are laid out beside each other, so in a real
    position field a family of four is not stacked in one spot. Measured 24 August 2026: +0x118
    spreads in nearly every family, +0x32C in none.
    """
    families: int = 40
    children_of: dict[int, list[int]] = {}
    for address, b in chunks.items():
        parent = int.from_bytes(b[f_parent:f_parent + 8], 'little')
        if parent in chunks:
            children_of.setdefault(parent, []).append(address)
    big = [c for c in children_of.values() if len(c) >= 4][:families]
    if not big:
        return None
    spread = 0
    for family in big:
        places = {_pair(chunks[a], offset) for a in family}
        if len(places) > 1:
            spread += 1
    return spread / float(len(big))


def _pos_field(chunks: dict[int, bytes], f_parent: int, f_size: int) -> int:
    """Prediction: a position field fits inside its parent, spreads its siblings, and carries as
    many different values as there are places on the screen.

    The first requirement alone decides almost nothing, and that is measured, not assumed. On a
    loaded game, 24 August 2026 over 3000 widgets: +0x118 fits 2352 of 2999 parent boxes, +0x120
    fits 2353, and +0x414 fits 2350. Three offsets within a tenth of a percent, so whichever way
    that comparison is scored it is deciding on noise - which is exactly how the old rule, taking
    the highest raw count, landed on a field holding two distinct values.

    What does separate them is how many different values they hold: 886 against 157 for +0x414. So
    the fit is a floor, not a score, and the choice is made on spread. The top candidates are
    printed, because the two that remain close are +0x118 and +0x120, and those are both
    position-like: when a window is unparked, both move from -60 to 0.
    """
    rows: list[tuple[int, int, int, int]] = []
    for offset in range(0, CHUNK - 8, 4):
        holds, distinct, _ = _position_like(chunks, f_parent, offset)
        if not holds:
            continue
        ok = pairs = 0
        for b in chunks.values():
            parent = int.from_bytes(b[f_parent:f_parent + 8], 'little')
            if parent not in chunks:
                continue
            kx, ky = _pair(b, offset)
            kb, kh = _pair(b, f_size)
            ob, oh = _pair(chunks[parent], f_size)
            if any(math.isnan(v) for v in (kx, ky, kb, kh, ob, oh)):
                continue
            pairs += 1
            if -2.0 <= kx and -2.0 <= ky and kx + kb <= ob + 2.0 and ky + kh <= oh + 2.0:
                ok += 1
        if pairs >= 20 and ok >= 0.7 * pairs:
            rows.append((distinct, offset, ok, pairs))
    if not rows:
        raise SystemExit('deriving failed on field: position (nothing both fits its parents and '
                         'spreads its siblings)')
    rows.sort(reverse=True)
    for distinct, offset, ok, pairs in rows[:3]:
        print(f'position candidate +0x{offset:03X}: {int(distinct)} distinct values, fits {int(ok)} of {int(pairs)} parent boxes')
    return rows[0][1]


def _cstring(chunk: bytes, offset: int) -> str | None:
    """MSVC layout of 32 bytes: sixteen bytes of buffer or pointer, then the length, then the
    capacity. If the capacity is 15, the text sits inside the object itself. A length past what
    one `read` may ask is no string of the game's, the way a derivation meets most candidates."""
    block = chunk[offset:offset + 32]
    length = int.from_bytes(block[16:24], 'little')
    capacity = int.from_bytes(block[24:32], 'little')
    if capacity < 15 or capacity > 0x100000 or length > capacity or length == 0 or length > 65536:
        return None
    if capacity == 15:
        if block[length] != 0 or any(c < 32 or c > 126 for c in block[:length]):
            return None
        return block[:length].decode('utf-8', 'replace')
    pointer = int.from_bytes(block[0:8], 'little')
    if pointer < 0x10000:
        return None
    b = channel.read(pointer, length)
    return None if b is None else b.decode('utf-8', 'replace')


def gui_text() -> str:
    """Every gui file the engine loads, as one text: what the name prediction looks names up in."""
    return ''.join(pathlib.Path(full).read_text(encoding='utf-8-sig', errors='replace')
                   for _, _, full in guimap.files())


def localization_text() -> str:
    """Every sentence the localization gives, as one text: what the text prediction looks in."""
    return '\n'.join(guimap.localization().values())


def _name_field(chunks: dict[int, bytes], gui: str) -> int:
    """Prediction: most names appear literally in the game's gui files. That is a primary source
    on disk and needs no eyesight."""
    best: tuple[int | None, int] = (None, 0)
    for offset in range(0, CHUNK - 32, 8):
        hit = _gui_names({t for t in (_cstring(b, offset) for b in chunks.values()) if t}, gui)
        if hit > best[1]:
            best = (offset, hit)
    if best[0] is None:
        raise SystemExit('deriving failed on field: name')
    return best[0]


def _text_field(chunks: dict[int, bytes], text_boxes: list[int], translation: str, f_name: int) -> int:
    """Prediction: most displayed texts appear in the localization files. Test on text boxes only -
    on another object you are reading the neighbour from the same pool here."""
    best: tuple[int | None, int] = (None, 0)
    for offset in range(0, CHUNK - 32, 8):
        if offset == f_name:
            continue
        texts = {widgettree.strip_markup(t)
                 for t in (_cstring(chunks[a], offset) for a in text_boxes if a in chunks) if t}
        texts = {t for t in texts if t}
        if len(texts) < 5:
            continue
        hit = sum(1 for t in texts if t in translation)
        if hit > best[1] and hit >= 0.5 * len(texts):
            best = (offset, hit)
    if best[0] is None:
        raise SystemExit('deriving failed on field: text')
    return best[0]


def window_classes_of(pid: int) -> set[int]:
    """Where the vtables of every class with Window in its name are loaded in this run."""
    module = vtablemap.module_base(pid)
    return {module + v for v in memory.vtables_by_name('Window')}


def derive_all(pid: int) -> tuple[Fields, set[int]]:
    """Derive every field from a full scan. Expensive, so once per build. The widgets the scan found
    come back with it, so the tree can be held against them."""
    addresses, skips_of_scan = scan(0, 0)
    left_out = skipped(skips_of_scan)
    if not addresses:
        raise SystemExit('the scan found no widget at all; is the game already showing a screen? '
                         f'It {left_out or "skipped nothing"}')
    chunks, failed = chunks_of(addresses)
    width, height = onscreen.window_size(pid)

    f_parent = _parent_field(chunks, set(addresses))
    children_of = children_from_parents(chunks, f_parent, set(addresses))
    f_count = _count_field(chunks, children_of)
    f_children = _child_field(chunks, children_of)
    roots = [a for a, b in chunks.items()
               if int.from_bytes(b[f_parent:f_parent + 8], 'little') not in addresses]
    f_size = _size_field(chunks, roots, width, height)
    f_position = _pos_field(chunks, f_parent, f_size)
    f_name = _name_field(chunks, gui_text())
    classes = widgettree.class_map(pid, addresses)
    text_boxes = [a for a, k in classes.items() if k == 'Textbox']
    f_text = _text_field(chunks, text_boxes, localization_text(), f_name)

    return ({'key': build_key(), 'parent': f_parent, 'children': f_children, 'count': f_count,
             'position': f_position, 'size': f_size, 'name': f_name, 'text': f_text,
             'objects': len(addresses), 'unreadable': failed, 'roots': len(roots), 'skipped': left_out},
            set(addresses))


def all_in_scan(nodes: Iterable[int], scanned: set[int], left_out: str) -> None:
    """Every widget of the tree has to be in the full scan, or the scan missed some.

    The scan skips the channel's own stacks and memory without a cache. Read from outside on two
    saves of 1.20 on 4 October 2026, that memory held no vtable of any class in the exe, and on a
    third every widget of the tree was in the scan; this is the test that keeps it so. The tree is
    walked by following pointers and skips nothing, so a widget in skipped memory shows up here, at
    every new derivation.
    """
    missing = set(nodes) - scanned
    if missing:
        raise SystemExit(f'{len(missing)} widgets of the tree are not in the full scan, which '
                         f'{left_out or "skipped nothing"}; if the game was not paused, pause it and '
                         'start again, and otherwise the scan skips memory the game now uses')


# The key that opens the subject (F1), the window it opens, and one that stays shut meanwhile.
KEY, SUBJECT, CONTROL = 112, 'character_window', 'council_window'


def _window_objects(pid: int, root: int) -> dict[str, int]:
    """Name -> the first window object of that name in the tree."""
    window_classes = window_classes_of(pid)
    named: dict[str, int] = {}
    for a, k in widgettree.widgets(root).items():
        if k[0] in window_classes and k[6]:
            named.setdefault(k[6], a)
    return named


def visibility_fields(fields: Fields, named: dict[str, int]) -> Fields:
    """Derive the two visibility offsets by toggling a window and watching what moves.

    Everything else here is derived from what one reading of memory looks like. These two cannot
    be: alpha and the window flag are ordinary numbers whose *meaning* only shows when the state
    changes. So change it - press a key that opens one window, and require:

      - on the subject, one byte-sized field goes to 0x00 and one float field goes to 1.0, and both
        return to their old value when the window closes again;
      - on a window that stays shut, neither moves.

    Measured 24 August 2026 on a loaded game: opening `character_window` with F1 moved six words -
    the flag at +0x0D0, alpha at +0x108, the two parked position fields at -60, one render word, and
    a counter that ticks on every window including the control. Only the flag and alpha satisfy the
    shape above, and the control moved on nothing else.

    The counter is why the control matters: without it a field that simply ticks would pass.
    """
    subject, control = SUBJECT, CONTROL

    def snapshot() -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        for name in (subject, control):
            chunk = channel.read(named[name], CHUNK)
            if chunk is None:
                raise SystemExit(f'deriving visibility failed: the {name} object can no longer be read')
            out[name] = chunk
        return out

    def toggle(before: dict[str, bytes], what: str) -> dict[str, bytes]:
        channel.ask(f'sendkey {KEY}')
        for _ in range(20):
            time.sleep(0.5)
            after = snapshot()
            if after[subject] != before[subject]:
                return after
        raise SystemExit(f'deriving visibility failed: {what} changed nothing in ten seconds')

    start = snapshot()
    opened = toggle(start, 'opening')
    closed = toggle(opened, 'closing')

    def moved(a: bytes, b: bytes, offset: int, size: int) -> bool:
        return a[offset:offset + size] != b[offset:offset + size]

    def alone_in_its_word(before: bytes, after: bytes, offset: int) -> bool:
        """A flag is a byte-sized field, so its word moves in that one byte and nowhere else.

        Without this the parked position fields qualify: they hold -60.0 and go to 0.0, and the two
        high bytes of that float both pass "went to zero and came back". Measured 24 August 2026:
        five candidates, of which four were bytes inside +0x118 and +0x120.
        """
        word = offset & ~3
        changed = [o for o in range(word, word + 4) if before[o] != after[o]]
        return changed == [offset]

    flag = [o for o in range(CHUNK)
            if start[subject][o] == closed[subject][o] != opened[subject][o] == 0
            and alone_in_its_word(start[subject], opened[subject], o)
            and not moved(start[control], opened[control], o, 1)]
    alpha = [o for o in range(0, CHUNK - 4, 4)
             if struct.unpack_from('<f', opened[subject], o)[0] == 1.0
             and struct.unpack_from('<f', start[subject], o)[0] == 0.0
             and start[subject][o:o + 4] == closed[subject][o:o + 4]
             and not moved(start[control], opened[control], o, 4)]
    if len(flag) != 1 or len(alpha) != 1:
        raise SystemExit(f"deriving visibility failed: {len(flag)} candidates for the flag {[f'0x{o:03X}' for o in flag[:6]]} and {len(alpha)} for "
                         f"alpha {[f'0x{o:03X}' for o in alpha[:6]]}; expected exactly one of each")
    print(f'flag: +0x{flag[0]:03X}, alpha: +0x{alpha[0]:03X} ({subject} toggled, {control} did not move)')
    out = fields.copy()
    out['flag'], out['alpha'] = flag[0], alpha[0]
    return out


def position_from_tree(pid: int, fields: Fields) -> tuple[Fields, int, dict[int, int]]:
    """Derive the position field a second time, from the live tree instead of the scan.

    The scan finds every widget-shaped object in the process; the tree holds the ones the game is
    actually drawing, and everything downstream uses the tree. Deriving from the wider population
    is what made this field come out differently per game state - measured 24 August 2026 on the
    same loaded game: from the scan +0x280, from the tree +0x118, and it is +0x118 that the
    recogniser confirms and that moves when a window is unparked.

    How wrong the scan answers are shows only against the tree: +0x280 carries 29 distinct values
    there and spreads a third of its families, against 886 and 0.97 for +0x118. Objects that hang
    off the tree apparently keep stale coordinates, and there are enough of them to outvote the
    live ones.

    This runs after the scan derivation, which is what makes the tree reachable in the first place:
    walking it needs the parent and children offsets. The root and the tree come back with it, so
    the start does not search for them a second time.
    """
    nodes: int = 1000
    configure_channel(fields)
    root, walked = quick_root(fields, pid)
    chunks, _ = chunks_of(list(walked)[:nodes])
    from_tree = _pos_field(chunks, fields['parent'], fields['size'])
    if from_tree != fields['position']:
        print('position: the scan said +0x{:03X}, the tree says +0x{:03X}; the tree decides'.format(fields['position'], from_tree))
    out = fields.copy()
    out['position'] = from_tree
    return out, root, walked


def store(fields: Fields) -> None:
    with open(STORED, 'w') as file:
        json.dump(fields, file, indent=1)


def stored() -> Fields | None:
    if not os.path.exists(STORED):
        return None
    with open(STORED) as file:
        fields: Fields = json.load(file)
    return fields if fields.get('key') == build_key() else None


TOOLTIP_ROOT = '_tooltip_root_'     # the engine's own name for the root that holds the tooltip of now


def tooltip_root(pid: int, fields: Fields, root: int) -> int:
    """The root outside the tree that holds the tooltip being shown, found without a scan.

    A tooltip's text never stands in the tree. It stands under `_tooltip_root_`, one of the roots
    only a full scan finds (21 seconds). But the engine keeps its layer roots side by side in one
    object - `_layer_`, the root of the tree, `_tooltip_root_`, `tools_layer` - and globals in the
    exe point at that object: ten of them on 1.20.1.1, with the root of the tree 0xd0 bytes in
    (measured 21 October 2026). So it is two reads from a global. Global and place are derived once
    per build from the root a start already has, and checked at every call against what they must
    lead to: the root of the tree, and a widget with the tooltip root's name beside it. A check
    that fails derives again. Which text under the tooltip root is the tooltip of now, `shown` says;
    the root keeps the text of its last tooltip.
    """
    base = vtablemap.module_base(pid)
    if 'gui_global' in fields and 'root_slot' in fields:
        found = _tooltip_through(base + fields['gui_global'], fields['root_slot'], root, fields['name'])
        if found is not None:
            return found
    fields['gui_global'], fields['root_slot'] = _tooltip_route(pid, root, base, fields['name'])
    store(fields)
    found = _tooltip_through(base + fields['gui_global'], fields['root_slot'], root, fields['name'])
    if found is None:
        raise SystemExit('the route to the tooltip root, just derived, does not lead to it')
    return found


def _named(address: int, f_name: int) -> str | None:
    b = channel.read(address, f_name + 32)
    return None if b is None else _cstring(b, f_name)


def _tooltip_through(global_address: int, slot: int, root: int, f_name: int) -> int | None:
    """The tooltip root along a stored route, or None when the route no longer leads there."""
    holder = channel.read(global_address, 8)
    if holder is None:
        return None
    pair = channel.read(int.from_bytes(holder, 'little') + slot, 16)
    if pair is None or int.from_bytes(pair[:8], 'little') != root:
        return None
    candidate = int.from_bytes(pair[8:], 'little')
    return candidate if _named(candidate, f_name) == TOOLTIP_ROOT else None


def _tooltip_route(pid: int, root: int, base: int, f_name: int) -> tuple[int, int]:
    """(global from the exe base, place of the root in the object it holds), derived.

    The place: of every pointer to the root of the tree, the one with a widget called
    `_tooltip_root_` right behind it - one on 1.20.1.1, among about twenty; that search took 6 to 12
    seconds and the whole derivation 24. The global: a value in the exe's writable pages, 9.8 MB
    read in a second, that points at most 4 kB before that place. Several
    globals point at the one object; the object most of them point at wins, and of its globals the
    lowest, so the choice is the same every time.
    """
    pattern = root.to_bytes(8, 'little')
    zeros = next(i for i, b in enumerate(pattern) if b)        # a search may not start on a zero byte
    answer = channel.ask(f'find {pattern[zeros:].hex()}', timeout=300)
    pointers = [int(line.split('\t')[1], 16) - zeros for line in answer.split('\n') if line.startswith('t\t')]
    slots = []
    for at in pointers:
        beside = channel.read(at + 8, 8)
        if beside is not None and _named(int.from_bytes(beside, 'little'), f_name) == TOOLTIP_ROOT:
            slots.append(at)
    if len(slots) != 1:
        raise SystemExit(f'{len(slots)} places hold the root of the tree beside a tooltip root, among '
                         f'{len(pointers)} pointers to it; the search {skipped(skips(answer)) or "skipped nothing"}')
    holders: dict[int, list[int]] = {}
    for start, data in _image_writable(pid, base):
        for at in range(0, len(data) - 7, 8):
            value = int.from_bytes(data[at:at + 8], 'little')
            if slots[0] - 0x1000 <= value <= slots[0]:
                holders.setdefault(value, []).append(start + at)
    if not holders:
        raise SystemExit('no global in the exe points at the object that lists the layer roots')
    holder = max(holders, key=lambda value: (len(holders[value]), value))
    return min(holders[holder]) - base, slots[0] - holder


def _image_writable(pid: int, base: int) -> Iterator[tuple[int, bytes]]:
    """The writable pages of the exe as the running game holds them: where its globals live."""
    import ctypes
    k32 = memory.kernel32
    handle = k32.OpenProcess(0x0410, False, pid)
    if not handle:
        raise SystemExit(f'cannot open the game process: {int(pid)}')
    info = memory.Region()
    address = base
    try:
        while k32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(info), ctypes.sizeof(info)):
            start = info.BaseAddress or address
            if info.AllocationBase != base:
                return
            if info.State == 0x1000 and info.Protect & 0x0C:        # committed, read-write or write-copy
                buffer = ctypes.create_string_buffer(info.RegionSize)
                got = ctypes.c_size_t()
                if not k32.ReadProcessMemory(handle, ctypes.c_void_p(start), buffer, info.RegionSize,
                                             ctypes.byref(got)):
                    raise SystemExit(f'cannot read the writable page of the exe at {start:x}')
                yield start, buffer.raw[:got.value]
            address = start + info.RegionSize
    finally:
        k32.CloseHandle(handle)


def to_root(address: int, f_parent: int) -> tuple[int, dict[int, int]]:
    """Up until the parent is no longer a widget. `tree` on a non-widget returns nothing, and that
    is the test right there."""
    p, nodes = address, tree(address)
    for _ in range(40):
        b = channel.read(p + f_parent, 8)
        if b is None:
            return p, nodes
        upper = int.from_bytes(b, 'little')
        if upper < 0x10000:
            return p, nodes
        top = tree(upper)
        if not top:
            return p, nodes
        p, nodes = upper, top
    raise SystemExit('the parent chain does not end; is the parent field still right?')


def quick_root(fields: Fields, pid: int) -> tuple[int, dict[int, int]]:
    """From seed widgets up to the roots, then return the largest tree.

    Two traps live here. A single hit is not a widget: there are loose places in memory that happen
    to hold a vtable value, and no tree hangs under them. And the first tree that looks big enough
    is not the right one: the game also has tooltip roots and leftovers of the loading screen, with
    dozens of nodes. Measured 27 July 2026: beside the interface of 2370 nodes stood a subtree of
    55. So take the largest, not the first.

    `ample` exists for speed: trying forty seeds is expensive, so it stops as soon as a tree of that
    order turns up. That early exit takes the first tree above the threshold rather than the
    largest, and that has proved safe: measured 29 July 2026 on a loaded game, 120 seeds came out at
    18 endpoints, of which the interface counted 98,915 widgets and the runner-up eleven. Four
    orders of magnitude sit between those two, so any threshold in between points at the same tree.
    Repeat that measurement if the engine ever grows a second large root.
    """
    samples: int = 40
    ample: int = 1500
    at_least: int = 500
    found: dict[int, dict[int, int]] = {}
    left_out: list[Skips] = []
    for group, skips_of_piece in seed_batches(pid):
        left_out.append(skips_of_piece)
        for address in group[:samples]:
            if address in found:
                continue
            root, nodes = to_root(address, fields['parent'])
            found[root] = nodes
            if len(nodes) >= ample:                 # this is the interface, searching further is pointless
                return root, nodes
        if found and max(len(k) for k in found.values()) >= at_least:
            root = max(found, key=lambda w: len(found[w]))
            return root, found[root]
    raise SystemExit('no widget tree of any significance found; is the game still running? '
                     f'The scan {skipped(*left_out) or "skipped nothing"}')


def _sample(nodes: Iterable[int], root: int) -> list[int]:
    """Spread across memory, so that one odd pool does not decide the outcome."""
    how_many: int = 200
    addresses = sorted(nodes)
    step = max(1, len(addresses) // how_many)
    choice = addresses[::step][:how_many]
    if root not in choice:
        choice.append(root)
    return choice


def _child_check(fields: Fields, root: int) -> tuple[int, int]:
    """From the root downwards: a parent's child list must contain exactly the widgets naming that
    parent as their parent. This tests the child field, the count and the parent field in one
    movement, and it need not cover the whole tree.

    **It reads only the two fields it tests, not a whole chunk.** Measured 4 October 2026 on the
    loaded Ghur game of 1.20: the root sat 816 bytes before the end of readable memory, a read of
    `CHUNK` from it failed, nothing was tested, and the start turned a good derivation down, said
    so to the player and derived the same offsets again for three minutes.
    """
    how_many: int = 20
    need = max(fields['children'] + 8, fields['count'] + 4)
    todo = [root]
    tested, misses = 0, 0
    while todo and tested < how_many:
        parent = todo.pop(0)
        b = channel.read(parent, need)
        if b is None:
            continue
        items = int.from_bytes(b[fields['children']:fields['children'] + 8], 'little')
        count = int.from_bytes(b[fields['count']:fields['count'] + 4], 'little')
        if not items or count == 0 or count > 500:
            continue
        block = channel.read(items, count * 8)
        if block is None:
            misses += 1
            continue
        children = [int.from_bytes(block[i:i + 8], 'little') for i in range(0, len(block), 8)]
        for child in children:
            back = channel.read(child + fields['parent'], 8)
            if back is None or int.from_bytes(back, 'little') != parent:
                misses += 1
        todo.extend(children)
        tested += 1
    return tested, misses


def verify(fields: Fields, root: int, nodes: dict[int, int], pid: int) -> list[str]:
    """Recheck the stored derivation against the game running right now, with predictions that are
    each verifiable without eyesight. What comes back is a list of defects; if it is empty, the
    stored derivation still holds.

    A sample is enough: this check has to establish whether the layout is still the same, not take
    inventory of the whole tree. Walking every node cost three seconds at every start and added
    nothing.
    """
    chunks, _ = chunks_of(_sample(nodes, root))
    window_width, window_height = onscreen.window_size(pid)
    defects: list[str] = []

    tested, misses = _child_check(fields, root)
    if tested < 5:
        defects.append('too few parents with children found to test against')
    elif misses:
        defects.append(f'child list and parent field contradict each other in {int(misses)} places')

    # The root is read for itself, with only the bytes this needs: in the sample it can fall out
    # unreadable, and this check then stood down without a word (4 October 2026, see _child_check).
    b, h = _pair(channel.read_known(root, fields['size'] + 8), fields['size'])
    if not _in_proportion(b, h, window_width, window_height):
        defects.append('the root is out of proportion with the drawing area '
                       f'({b:.0f}x{h:.0f} against window {int(window_width)}x{int(window_height)})')

    names = {t for t in (_cstring(b, fields['name']) for b in chunks.values()) if t}
    if not _gui_names(names, gui_text()):
        defects.append(f'fewer than {GUI_NAMES:.0%} of {len(names)} names appear in the gui files')

    defects.extend(_position_check(fields, nodes))
    defects.extend(_scale_check(fields, chunks, nodes))
    defects.extend(_visibility_check(fields, chunks, nodes, pid))
    return defects


def _position_check(fields: Fields, nodes: Iterable[int]) -> list[str]:
    """Is the stored position offset still a position?

    This check exists because its absence cost a whole afternoon: three times a derivation produced
    a different position offset and `verify` reported no defects, because it tested the child list,
    the proportions of the root and the names, and nothing at all about position. A wrong offset
    reads as a screen where everything sits at the same spot, which downstream looks like a game
    that has not drawn anything.

    Two requirements, both cheap and both measured against the wrong answers this actually produced:
    a position field carries as many different values as there are places on screen (886 against 29
    for +0x280 over a thousand widgets), and children of one parent are not stacked on one spot
    (0.97 of families against 0.33).
    """
    how_many: int = 800
    chunks, _ = chunks_of(list(nodes)[:how_many])
    if not chunks:
        return ['nothing could be read from the tree to check the position offset against']
    holds, distinct, families = _position_like(chunks, fields['parent'], fields['position'])
    if not holds:
        return [(f"position at +0x{fields['position']:03X} does not behave like one: {int(distinct)} distinct values, {'no' if families is None else f'{families:.2f}'} of families "
                 'spread their children')]
    return []


def _scale_check(fields: Fields, chunks: dict[int, bytes], nodes: dict[int, int]) -> list[str]:
    """Is `onscreen.OWN_SCALE` still the own scale, with the scale from above beside it?

    That offset is not derived, and this is what keeps it from going stale unseen. The scale from
    above is the product of the own scales of every ancestor (`onscreen.scales_for`), so for every
    widget of the sample whose parent is in the tree, the parent's own scale times the parent's
    scale from above is the widget's scale from above. A field holding anything else - a pointer, a
    count, a coordinate - breaks that at once. Not yet measured on a loaded game of 1.20.1.2.
    """
    parents = {a: int.from_bytes(b[fields['parent']:fields['parent'] + 8], 'little')
               for a, b in chunks.items()}
    parents = {a: p for a, p in parents.items() if p in nodes}
    scales = onscreen.scales_for(set(parents) | set(parents.values()))
    pairs = [(scales[a][1], scales[p][0] * scales[p][1]) for a, p in parents.items()
             if a in scales and p in scales]
    held = sum(1 for above, expected in pairs if abs(above - expected) < 1e-4)
    if len(pairs) < 20 or held < 0.99 * len(pairs):
        return [(f'the scale at +0x{onscreen.OWN_SCALE:03X} does not behave like one: the scale from '
                 f"above is the product of the parent's in {held} of {len(pairs)} widgets")]
    return []


def _visibility_check(fields: Fields, chunks: dict[int, bytes], nodes: dict[int, int],
                      pid: int) -> list[str]:
    """Cheap recheck of the two visibility offsets, without touching the game.

    Deriving them means opening and closing a window, which is not something to do at every start
    while somebody is playing. Rechecking them does not need that: alpha is a fraction on every
    widget, and the flag is a small bit pattern - but only on a window object. Measured 24 August
    2026: checking the flag on ordinary widgets fails immediately, because at that offset they hold
    something else entirely. A wrong offset lands on a pointer or a coordinate and fails both tests.
    If this fires, the full derivation runs, and that one does press the key.
    """
    if 'alpha' not in fields or 'flag' not in fields:
        return ['no visibility offsets in the stored derivation']
    # Publish the candidate before testing it: `flags_for` reads the offset from there, and this is
    # the one under test. If it turns out wrong, `fields_for` derives again and publishes that.
    onscreen.use_fields(fields.get('alpha'), fields.get('flag'))
    defects: list[str] = []
    alphas = [struct.unpack_from('<f', b, fields['alpha'])[0] for b in chunks.values()]
    if not alphas or any(a < 0.0 or a > 1.0 for a in alphas) or 1.0 not in alphas:
        defects.append('alpha at +0x{:03X} is not a fraction across the sample'.format(fields['alpha']))

    window_classes = window_classes_of(pid)
    windows = [a for a, vtable in nodes.items() if vtable in window_classes][:400]
    values = list(onscreen.flags_for(windows).values())
    if not values:
        defects.append('no window object could be read at +0x{:03X}'.format(fields['flag']))
    elif any(v & ~0x3F for v in values):
        defects.append('the window flag at +0x{:03X} carries bits it never carries ({})'.format(fields['flag'], sorted({f'0x{v:02X}' for v in values})[:6]))
    return defects


def fields_for(pid: int, recheck: bool = True) -> tuple[Fields, int, str]:
    """The path walked at every start: the derivation, the root of the tree, and what happened.

    If there is a derivation for this exe and it holds up against the running game, that is the
    one. Otherwise it is derived again and written out. Nothing is assumed: a stored derivation
    also has to prove itself every time - except with `recheck` off, for leaving a game from a
    menu, where the recheck turns a good derivation down and derives again for minutes.

    When this returns, the channel walks with these offsets and `onscreen` knows the drawing area
    and the two visibility offsets. The root comes back too: finding it again cost every caller a
    seed search of up to ten seconds.
    """
    vtablemap.configure(pid)          # vtables first, or no scan finds anything
    onscreen.use_screen(pid)          # and the drawing area, which every geometric answer needs
    fields = stored()
    if fields:
        configure_channel(fields)               # the walk below runs on these, not on defaults
        onscreen.use_fields(fields.get('alpha'), fields.get('flag'))
        root, nodes = quick_root(fields, pid)
        if not recheck:
            return fields, root, 'stored derivation, not rechecked'
        defects = verify(fields, root, nodes, pid)
        if not defects:
            return fields, root, 'stored derivation holds'
        reason = 'stored derivation fails: ' + '; '.join(defects)
        speech.failure('reading the game', 'the places it read this game at last time do not hold',
                       'it is working out the new places, which takes a few minutes')
    else:
        reason = 'no derivation for this version of the game'
    fields, scanned = derive_all(pid)
    fields, root, nodes = position_from_tree(pid, fields)
    all_in_scan(nodes, scanned, fields.get('skipped', ''))
    fields, note = _with_visibility(pid, fields, root)
    store(fields)
    configure_channel(fields)
    onscreen.use_fields(fields.get('alpha'), fields.get('flag'))
    left_out = f"; the scan {fields['skipped']}" if fields.get('skipped') else ''
    return fields, root, reason + ' - derived again' + note + left_out


def _with_visibility(pid: int, fields: Fields, root: int) -> tuple[Fields, str]:
    """Add the two visibility offsets where this game state has the windows to derive them with.

    They need a window that can be opened, and the main menu has none - its window objects are all
    dialogues nobody has opened. Deriving the other seven there is still useful, so the tree can be
    walked and read; what cannot be answered is what is visible, and `onscreen.use_fields` makes any
    attempt to ask say so instead of guessing. Anything else that goes wrong stops: this used to
    catch every failure along with the main menu's, so a loaded game could come out without
    visibility and only a clause in a reason most callers threw away.
    """
    named = _window_objects(pid, root)
    if SUBJECT not in named or CONTROL not in named:
        return fields, f'; visibility not derived: no {SUBJECT} in this tree, as on the main menu'
    return visibility_fields(fields, named), ''


def configure_channel(fields: Fields) -> None:
    """Hands the derived offsets to the DLL. The DLL knows nothing about CK3; all knowledge about
    it lives here. It walks nothing until this has been called."""
    channel.ask(f"set {fields['parent']:x} {fields['position']:x} {fields['size']:x} {fields['name']:x} "
                f"{fields['text']:x} {fields['children']:x} {fields['count']:x}")


def _start_block() -> None:
    fields, _, why = fields_for(int(sys.argv[1]))
    print(why)
    for name in ('parent', 'children', 'count', 'position', 'size', 'name', 'text',
                 'alpha', 'flag'):
        value = fields.get(name)
        print(f'{name!s:<9} +0x{value:03X}' if isinstance(value, int)
              else f'{name!s:<9} not derived in this game state')


def regions(pid: int) -> list[tuple[int, int]]:
    """The memory regions of the game, asked for from the outside.

    Needed because `scan` walks a window to the end before answering: a roomy window therefore
    costs the full scan time, even when the first hit lands immediately. With this list the scan
    can be aimed, up to the first hit.
    """
    import ctypes
    k32 = memory.kernel32
    handle = k32.OpenProcess(0x0410, False, pid)
    if not handle:
        raise SystemExit(f'cannot open the game process: {int(pid)}')
    items: list[tuple[int, int]] = []
    address = 0x10000
    info = memory.Region()
    while address < 0x7FFFFFFF0000:
        if not k32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(info),
                                  ctypes.sizeof(info)):
            break
        base = info.BaseAddress or address
        size = info.RegionSize
        if (info.State == 0x1000 and info.Type == 0x20000
                and info.Protect & 0x0C4 and not info.Protect & 0x100):
            items.append((base, size))
        address = base + size
    k32.CloseHandle(handle)
    return items


def seed_batches(pid: int) -> Iterator[tuple[list[int], Skips]]:
    """Per piece of memory the addresses found, and what the scan of that piece left out, until
    the caller finds a usable one.

    Scanning happens in chunks because `scan` walks a window to the end before answering: a roomy
    window costs the full scan time even when the first hit lands immediately.
    """
    chunk: int = 0x4000000
    stack: list[tuple[int, int]] = []
    total = 0
    for base, size in regions(pid):
        stack.append((base, size))
        total += size
        if total < chunk:
            continue
        found, left_out = scan(stack[0][0], stack[-1][0] + stack[-1][1])
        yield sorted(found), left_out
        stack, total = [], 0
    if stack:
        found, left_out = scan(stack[0][0], stack[-1][0] + stack[-1][1])
        yield sorted(found), left_out


if __name__ == '__main__':
    _start_block()
