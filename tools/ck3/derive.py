"""Derives the field offsets of a widget object from the running game, through the channel.

Why this exists: without derivation the offsets are fixed numbers from one build, and everything
breaks at the next patch.

How it works, at two speeds:
  - deriving costs a full memory scan, measured at 132 seconds. The result belongs to the exe, not
    to the session, so it goes to disk under a key made from that exe.
  - rechecking costs two seconds. That happens at every start. If the check fails, the stored
    derivation has expired and everything is derived again.

Every prediction below is one that can only come true for the right field. If a field cannot be
found, this file stops hard and names that field.
"""
import glob
import json
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vtablemap
import memory
import channel
import windowgrab

EXE = memory.EXE
INSTALL = memory.INSTALL
PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORED = os.path.join(PROJECT, 'reports', 'fields.json')
CHUNK = 0x420          # roomier than the largest widget object


def window_size(pid):
    """The drawing area of the game window, live from Windows.

    Not from `pdx_settings.txt`: that file is only written on exit and therefore does not know the
    GUI scale of this moment.
    """
    hwnd, _, _ = windowgrab.window_of(pid)
    return windowgrab.client_size(hwnd)


def build_key():
    """How you tell it is still the same build. If the exe changes, everything lapses."""
    st = os.stat(EXE)
    return '%d-%d' % (st.st_size, int(st.st_mtime))


def read(address, count):
    line = channel.ask('read %x %d' % (address, count), timeout=20,
                        errors_ok=True).split('\n')[0].strip()
    return None if line.startswith('error') else bytes.fromhex(line)


def scan(from_address, to_address):
    """Address -> vtable. Both come from the vtable comparison and do not depend on the field
    offsets we are looking for."""
    found = {}
    answer = channel.ask('scan %x %x' % (from_address, to_address) if to_address else 'scan', timeout=300)
    for line in answer.split('\n'):
        part = line.split('\t')
        if part[0] == 'w':
            found[int(part[1], 16)] = int(part[2], 16)
    return found


def tree(root):
    found = {}
    for line in channel.ask('tree %x' % root, timeout=60).split('\n'):
        part = line.split('\t')
        if part[0] == 'w':
            found[int(part[1], 16)] = int(part[2], 16)
    return found


ALPHA = None
WINDOW_FLAG = None


def use_fields(fields):
    """Publish the two visibility offsets for this build.

    `flags_for` and `is_visible` need an offset but are called per widget, so passing the field
    dictionary down every call site would be noise. They read these two instead, and `fields_for`
    sets them. They start as None on purpose: a wrong offset here reads as "nothing is visible",
    which is indistinguishable from a game that has not drawn anything yet, so the failure has to
    be loud and immediate rather than a plausible empty list.
    """
    global ALPHA, WINDOW_FLAG
    ALPHA, WINDOW_FLAG = fields.get('alpha'), fields.get('flag')


def _visibility_offset(which):
    value = ALPHA if which == 'alpha' else WINDOW_FLAG
    if value is None:
        raise SystemExit('the %s offset is not known yet: call fields_for(pid) first, which '
                         'derives it or reads it back from the stored derivation' % which)
    return value


def flags_for(addresses):
    """The window flag of many objects in as few channel questions as possible.

    The DLL refuses a command that fills its 8192-byte buffer - it answers `error: command too
    long`, measured 29 July 2026. Hence at most 400 addresses per question.
    """
    flag = _visibility_offset('flag')
    out, items = {}, sorted(addresses)
    for start in range(0, len(items), 400):
        part = items[start:start + 400]
        ask = 'readmany 1 ' + ' '.join('%x' % (a + flag) for a in part)
        for line in channel.ask(ask, timeout=120).split('\n'):
            d = line.split('\t')
            if d[0] == 'l' and len(d) > 2 and d[2] != 'unreadable':
                out[int(d[1], 16) - flag] = int(d[2], 16)
    return out


def widgets(root):
    """The whole tree with fields attached: address -> (vtable, x, y, width, height, parent, name, text).

    x and y are relative to the parent; use `screen_pos` for the place on screen. The text is only
    valid on a text box - on other classes you are reading the neighbour from the same pool. So
    filter on vtable before believing the text.

    **The order of this dict is the engine's own child order, and it is the only copy of it.** The
    DLL walks each widget's child list in index order and this keeps the lines as they arrive, so
    the children of a parent come out in the order the game draws them - which is what decides
    which of two drawn widgets lies on top. Nothing else records it: the parent offset says who the
    parent is, never in which place. Rebuild children from this dict and do not sort them.
    """
    nodes = {}
    for line in channel.ask('tree %x' % root, timeout=60).split('\n'):
        d = line.split('\t')
        if d[0] == 'w':
            nodes[int(d[1], 16)] = (int(d[2], 16), float(d[3]), float(d[4]), float(d[5]),
                                    float(d[6]), int(d[7], 16), d[8], d[9])
    return nodes


OWN_SCALE = 0x110
PARENT_SCALE = 0x114


def scales_for(addresses):
    """Per widget (own scale, scale from above). The two sit next to each other, so one read round.

    Measured 23 August 2026 across all 2437 nodes of the main menu: +0x114 is exactly the product
    of the own scales of every ancestor, no exceptions. So the engine already works that out for
    us and the parent chain does not need multiplying.
    """
    out, items = {}, sorted(addresses)
    for start in range(0, len(items), 400):
        part = items[start:start + 400]
        ask = 'readmany 8 ' + ' '.join('%x' % (a + OWN_SCALE) for a in part)
        for line in channel.ask(ask, timeout=120).split('\n'):
            d = line.split('\t')
            if d[0] == 'l' and len(d) > 2 and d[2] != 'unreadable':
                out[int(d[1], 16) - OWN_SCALE] = struct.unpack('<ff', bytes.fromhex(d[2])[:8])
    return out


def _scale_of(scales, address):
    """The scale pair of one node, or a hard stop.

    A missing ancestor used to count as scale 1.0. That is silent and wrong: `screen_pos` walks the
    parent chain, so asking `scales_for` for the text boxes alone leaves every container above them
    at 1.0, the position of a scaled container is added unscaled, and its centring correction never
    fires. Measured 24 August 2026 on the main menu: the frames of the six buttons under the 0.83
    container came out 110 points too far left, the recogniser read half a word, and the score
    looked like a recognition problem. Nothing reported anything. So: ask `scales_for` for the whole
    tree, and if a node is missing, say so here rather than three layers on.
    """
    pair = scales.get(address)
    if pair is None:
        raise KeyError('no scale for %x: ask scales_for for the whole tree, not only the widgets '
                       'you are placing - screen_pos needs every parent as well' % address)
    return pair


def screen_pos(nodes, address, scales, anchors=None):
    """The place on screen: the own position plus that of every parent, with the scale applied.

    Five of the 515 gui files scale a full-screen container. The arithmetic, measured 30 July and
    23 August 2026: add up the position of every node times the scale that applies at that point
    (+0x114), and for each scaled container above it add `size x (1 - own scale) / 2`. That is the
    difference between shrinking around the centre and shrinking around the edge - and so it only
    applies on an axis where the container hangs centred. Which axes those are comes from disk, via
    `scale_anchors`; if a window is missing there, both axes are corrected, which is right for four
    of the five files.

    `scales` comes from `scales_for`; pass it in rather than fetching it per widget, because that
    makes it one channel question per four hundred nodes instead of one per node.

    What remains after this is alignment and not geometry: the recognised word sits centred or left
    in its box, and which of the two differs per widget, so compare per widget on left or on centre
    and not blindly on left edges. Measured that way: main menu 24 words, median 0.5 points; pause
    menu 11 words, median 0.5 points.
    """
    if anchors is None:
        anchors = scale_anchors()
    x = y = 0.0
    first = True
    while address in nodes:
        _, dx, dy, width, height, parent, _, _ = nodes[address]
        own, combined = _scale_of(scales, address)
        x += dx * combined
        y += dy * combined
        if not first and abs(own - 1.0) > 0.0001:
            in_x, in_y = _anchor_for(nodes, address, anchors)
            if in_x:
                x += width * (1.0 - own) / 2.0 * combined
            if in_y:
                y += height * (1.0 - own) / 2.0 * combined
        first = False
        address = parent
    return x, y


def _anchor_for(nodes, address, anchors):
    """From a scaled container up to the window it hangs in."""
    p, steps = address, 0
    while p in nodes and steps < 24:
        name = nodes[p][6]
        if name in anchors:
            return anchors[name]
        p, steps = nodes[p][5], steps + 1
    return True, True


_ANCHORS = None


def scale_anchors():
    """Per window: does the centring correction apply in x, and in y? Read from the gui files.

    No table of our own: the anchoring sits as `parentanchor` next to the `scale` line in the gui
    file itself, and that is the source that changes along with the game. Measured 23 August 2026
    across all gui files: five files really scale. The main menu, the bookmarks and the barbershop
    hang on `center` and therefore correct on both axes; `ingame_pausemenu` hangs on `left|vcenter`
    and corrects only in y; the ruler designer on `hcenter` and `bottom|hcenter` respectively, so
    only in x. In `fullscreen_event.gui` the scale line is commented out, so the event window does
    not scale - that is the hard requirement and it falls outside this.
    """
    global _ANCHORS
    if _ANCHORS is not None:
        return _ANCHORS
    anchors = {}
    for pattern in (os.path.join(INSTALL, 'game', 'gui', '**', '*.gui'),
                    os.path.join(INSTALL, 'clausewitz', 'gui', '**', '*.gui'),
                    os.path.join(INSTALL, 'jomini', '**', '*.gui')):
        for path in glob.glob(pattern, recursive=True):
            lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
            for i, line in enumerate(lines):
                if 'ScaleToFitElement' not in line or line.lstrip().startswith('#'):
                    continue
                anchor = ''
                for j in range(max(0, i - 8), min(len(lines), i + 9)):
                    if 'parentanchor' in lines[j]:
                        anchor = lines[j].split('=', 1)[1].strip()
                        break
                window = ''
                for j in range(i, -1, -1):
                    if lines[j].strip().startswith('name =') and window == '':
                        window = lines[j].split('=', 1)[1].strip().strip('"')
                    if lines[j].startswith('window = {'):
                        break
                    if lines[j].strip().startswith('name ='):
                        window = lines[j].split('=', 1)[1].strip().strip('"')
                if window:
                    parts = {s.strip() for s in anchor.split('|')}
                    anchors[window] = ('center' in parts or 'hcenter' in parts,
                                       'center' in parts or 'vcenter' in parts)
    _ANCHORS = anchors
    return anchors


def screen_size(nodes, address, scales):
    """The size as it is drawn: the own size times the own scale times the scale from above."""
    _, _, _, width, height, _, _, _ = nodes[address]
    own, combined = _scale_of(scales, address)
    return width * own * combined, height * own * combined


def is_visible(nodes, address):
    """Alpha is a property of the whole parent chain: if one ancestor sits at 0 you see nothing,
    while the child itself keeps reporting 1.0."""
    while address in nodes:
        if struct.unpack('<f', read(address + _visibility_offset('alpha'), 4))[0] == 0.0:
            return False
        address = nodes[address][5]
    return True



def is_clipped(nodes, address, scales, classes):
    """Is this widget scrolled out of view inside a list?

    A third mechanism next to the window flag and alpha, and it had to be measured because the
    other two say nothing about it. Measured 24 August 2026 on the decisions view, a list longer
    than its frame: seven rows sat below the box of their scroll area, down to y 2286 against a
    frame ending at 855, and every one of them carried alpha 1.0. So alpha does not clip, and a
    reader that trusts it reads out rows nobody can see.

    What does decide it is geometry: the nearest ScrollArea above a widget has a box, and a row
    outside that box is not on screen. `classes` is the class map, because the scroll area is
    recognised by its class and not by its name.
    """
    x, y = screen_pos(nodes, address, scales)
    width, height = screen_size(nodes, address, scales)
    p, steps = nodes[address][5], 0
    while p in nodes and steps < 30:
        if 'Scroll' in (classes.get(p) or ''):
            ax, ay = screen_pos(nodes, p, scales)
            aw, ah = screen_size(nodes, p, scales)
            if aw > 1 and ah > 1:
                return not (ax - 1 <= x and ay - 1 <= y
                            and x + width <= ax + aw + 1 and y + height <= ay + ah + 1)
        p, steps = nodes[p][5], steps + 1
    return False


def chunks_of(addresses):
    """Raw bytes per object. Unreadable ones are skipped and counted, not hidden."""
    chunks, failed = {}, 0
    for address in addresses:
        b = read(address, CHUNK)
        if b is None:
            failed += 1
        else:
            chunks[address] = b
    return chunks, failed


def _pair(chunk, offset):
    return struct.unpack_from('<ff', chunk, offset)


def _parent_field(chunks, addresses):
    """Prediction: the parent field forms a forest. Every chain ends at a root and there are no
    cycles. A sibling or neighbour pointer points at a widget just as often but loops around, and
    drops out on that."""
    best = None
    for offset in range(0, CHUNK - 8, 8):
        parent = {}
        for address, b in chunks.items():
            value = int.from_bytes(b[offset:offset + 8], 'little')
            parent[address] = value if value in addresses else 0
        if len(set(parent.values()) - {0}) < 2:
            continue
        ends = 0
        for address in parent:
            seen, p, depth = set(), address, 0
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


def children_from_parents(chunks, f_parent, addresses):
    from_address = {}
    for address, b in chunks.items():
        value = int.from_bytes(b[f_parent:f_parent + 8], 'little')
        if value in addresses:
            from_address.setdefault(value, set()).add(address)
    return from_address


def _count_field(chunks, children_of):
    """Prediction: a 32-bit number that equals the number of children for every parent.

    The requirement is overwhelming majority, not perfection. The interface moves while it is being
    read - the main menu animates - so one parent whose count changes midway is normal. Measured
    27 July 2026: +0x0FC explained 942 of 943 parents, the runner-up 861. A demand of 943 out of
    943 would fail such a result, and that is not strictness but brittleness.
    """
    tally = {}
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
            'deriving failed on field: child count (best +0x%03X explains %d of %d, '
            'runner-up %d)' % (offset, hit, len(children_of), runner_up))
    print('count: +0x%03X explains %d of %d parents, runner-up %d'
          % (offset, hit, len(children_of), runner_up))
    return offset


def _child_field(chunks, children_of, samples=20):
    """Prediction: a pointer to a block containing exactly the children that name this object as
    their parent. Equal, not overlapping."""
    probe = [o for o in sorted(children_of, key=lambda k: -len(children_of[k]))
             if o in chunks][:samples]
    best = (None, 0)
    for offset in range(0, CHUNK - 8, 8):
        ok = 0
        for parent in probe:
            children = children_of[parent]
            pointer = int.from_bytes(chunks[parent][offset:offset + 8], 'little')
            if pointer < 0x10000 or len(children) > 500:
                continue
            b = read(pointer, len(children) * 8)
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
    raise SystemExit('deriving failed on field: child list (best explained %d of %d parents)'
                     % (best[1], len(probe)))


def _size_field(chunks, roots, window_width, window_height):
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
            width, height = _pair(chunks[root], offset)
            if width < 100.0 or height < 100.0:
                continue
            scale_x = window_width / width
            scale_y = window_height / height
            if abs(scale_x - scale_y) < 0.005 and 0.4 <= scale_x <= 2.5:
                return offset
    raise SystemExit('deriving failed on field: size (no root in proportion with the '
                     'drawing area of %dx%d)' % (window_width, window_height))


def _spread(chunks, offset):
    values = set()
    for b in chunks.values():
        x, y = _pair(b, offset)
        if x == x and y == y and abs(x) < 1e6 and abs(y) < 1e6:
            values.add((round(x, 1), round(y, 1)))
    return len(values)


def _siblings_spread(chunks, f_parent, offset, families=40):
    """Do the children of one parent sit in different places?

    This is what separates the position field from a field that is almost always (0,0). "Every
    child fits inside its parent" is trivially true for a field holding zero, so on a loaded game
    the derivation picked +0x32C, which holds two distinct values over four hundred widgets, above
    the +0x118 that the recogniser confirms. Siblings are laid out beside each other, so in a real
    position field a family of four is not stacked in one spot. Measured 24 August 2026: +0x118
    spreads in nearly every family, +0x32C in none.
    """
    children_of = {}
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


def _pos_field(chunks, f_parent, f_size, addresses, spread_required=100):
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
    rows = []
    for offset in range(0, CHUNK - 8, 4):
        distinct = _spread(chunks, offset)
        if distinct < spread_required:
            continue
        families = _siblings_spread(chunks, f_parent, offset)
        if families is None or families < 0.9:
            continue
        ok = pairs = 0
        for address, b in chunks.items():
            parent = int.from_bytes(b[f_parent:f_parent + 8], 'little')
            if parent not in chunks:
                continue
            kx, ky = _pair(b, offset)
            kb, kh = _pair(b, f_size)
            ob, oh = _pair(chunks[parent], f_size)
            if not all(v == v for v in (kx, ky, kb, kh, ob, oh)):
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
        print('position candidate +0x%03X: %d distinct values, fits %d of %d parent boxes'
              % (offset, distinct, ok, pairs))
    return rows[0][1]


def _cstring(chunk, offset):
    """MSVC layout of 32 bytes: sixteen bytes of buffer or pointer, then the length, then the
    capacity. If the capacity is 15, the text sits inside the object itself."""
    block = chunk[offset:offset + 32]
    length = int.from_bytes(block[16:24], 'little')
    capacity = int.from_bytes(block[24:32], 'little')
    if capacity < 15 or capacity > 0x100000 or length > capacity or length == 0:
        return None
    if capacity == 15:
        if block[length] != 0 or any(c < 32 or c > 126 for c in block[:length]):
            return None
        return block[:length].decode('utf-8', 'replace')
    pointer = int.from_bytes(block[0:8], 'little')
    if pointer < 0x10000:
        return None
    b = read(pointer, length)
    return None if b is None else b.decode('utf-8', 'replace')


def _file_chunk(pattern, text_encoding='utf-8'):
    return ''.join(open(p, encoding=text_encoding, errors='ignore').read()
                   for p in glob.glob(pattern, recursive=True))


def gui_text():
    return (_file_chunk(os.path.join(INSTALL, 'game', 'gui', '**', '*.gui')) +
            _file_chunk(os.path.join(INSTALL, 'clausewitz', 'gui', '**', '*.gui')))


def localization_text():
    return _file_chunk(os.path.join(INSTALL, 'game', 'localization', 'english',
                                      '**', '*.yml'), 'utf-8-sig')


def _name_field(chunks, gui):
    """Prediction: most names appear literally in the game's gui files. That is a primary source
    on disk and needs no eyesight."""
    best = (None, 0)
    for offset in range(0, CHUNK - 32, 8):
        names = {t for t in (_cstring(b, offset) for b in chunks.values()) if t}
        if len(names) < 20:
            continue
        hit = sum(1 for n in names if n in gui)
        if hit > best[1] and hit >= 0.6 * len(names):
            best = (offset, hit)
    if best[0] is None:
        raise SystemExit('deriving failed on field: name')
    return best[0]


import re

_MARKUP = re.compile('[\x15\x16][^ !]*[ !]?')


def strip_markup(text):
    """Strips the game's markup codes; those do not appear in the localization files.

    Two bytes open a code: 0x15 for colour, tooltips and links, and 0x16 for an icon. Both end at
    a space or an exclamation mark, and the pattern has to stop there instead of running on to the
    next space. Measured 25 August 2026 over the 1466 texts in the harvest: running on eats the
    separator between two codes standing back to back, which glued words together in 117 of them
    (`SucceededIntent`) and swallowed a colon that is on screen (`Aspiration` for `Aspiration:`).
    Both were written down as quirks of the game and were ours. Judged three ways: 179 texts found
    literally in the localization against 175, 883 text boxes confirmed by the recogniser against
    871, and no change at all on the 1296 texts that carry no two codes in a row.

    An icon carries meaning - `warning_icon` heads the 53 texts that hold one - but here it is
    markup like any other. The raw text keeps it for the presentation layer to turn into a word.
    """
    return re.sub(' {2,}', ' ', _MARKUP.sub('', text)).strip()


def _text_field(chunks, text_boxes, translation, f_name):
    """Prediction: most displayed texts appear in the localization files. Test on text boxes only -
    on another object you are reading the neighbour from the same pool here."""
    best = (None, 0)
    for offset in range(0, CHUNK - 32, 8):
        if offset == f_name:
            continue
        texts = {strip_markup(t) for t in (_cstring(chunks[a], offset) for a in text_boxes
                                     if a in chunks) if t}
        texts = {t for t in texts if t}
        if len(texts) < 5:
            continue
        hit = sum(1 for t in texts if t in translation)
        if hit > best[1] and hit >= 0.5 * len(texts):
            best = (offset, hit)
    if best[0] is None:
        raise SystemExit('deriving failed on field: text')
    return best[0]


def class_map(pid, addresses):
    """Address -> class name, through the vtable. `addresses` is a dict {address: vtable}, not a list."""
    base = vtablemap.module_base(pid)
    names = {base + rva: name for rva, name in memory.widget_vtables().items()}
    return {address: names.get(vtable) for address, vtable in addresses.items()}


def derive_all(pid):
    """Derive every field from a full scan. Expensive, so once per build."""
    addresses = scan(0, 0)
    if not addresses:
        raise SystemExit('the scan found no widget at all; is the game already showing a screen?')
    chunks, failed = chunks_of(addresses)
    width, height = window_size(pid)

    f_parent = _parent_field(chunks, set(addresses))
    children_of = children_from_parents(chunks, f_parent, set(addresses))
    f_count = _count_field(chunks, children_of)
    f_children = _child_field(chunks, children_of)
    roots = [a for a, b in chunks.items()
               if int.from_bytes(b[f_parent:f_parent + 8], 'little') not in addresses]
    f_size = _size_field(chunks, roots, width, height)
    f_position = _pos_field(chunks, f_parent, f_size, set(addresses))
    f_name = _name_field(chunks, gui_text())
    classes = class_map(pid, addresses)
    text_boxes = [a for a, k in classes.items() if k == 'Textbox']
    f_text = _text_field(chunks, text_boxes, localization_text(), f_name)

    return dict(key=build_key(), parent=f_parent, children=f_children, count=f_count,
                position=f_position, size=f_size, name=f_name, text=f_text,
                objects=len(addresses), unreadable=failed, roots=len(roots))


def visibility_fields(pid, fields, root, key=112, subject='character_window',
                      control='council_window'):
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
    module = vtablemap.module_base(pid)
    window_classes = {module + v for v in (memory.vtables_by_name('Window') or [])}
    nodes = widgets(root)
    named = {}
    for a, k in nodes.items():
        if k[0] in window_classes and k[6]:
            named.setdefault(k[6], a)
    for name in (subject, control):
        if name not in named:
            raise SystemExit('deriving visibility failed: no window object called %s in this tree; '
                             'this derivation needs a loaded game, not the main menu' % name)

    def snapshot():
        return {name: read(named[name], CHUNK) for name in (subject, control)}

    def toggle(before, what):
        channel.ask('sendkey %d' % key)
        for _ in range(20):
            time.sleep(0.5)
            after = snapshot()
            if after[subject] != before[subject]:
                return after
        raise SystemExit('deriving visibility failed: %s changed nothing in ten seconds' % what)

    start = snapshot()
    opened = toggle(start, 'opening')
    closed = toggle(opened, 'closing')

    def moved(a, b, offset, size):
        return a[offset:offset + size] != b[offset:offset + size]

    def alone_in_its_word(before, after, offset):
        """A flag is a byte-sized field, so its word moves in that one byte and nowhere else.

        Without this the parked position fields qualify: they hold -60.0 and go to 0.0, and the two
        high bytes of that float both pass "went to zero and came back". Measured 24 August 2026:
        five candidates, of which four were bytes inside +0x118 and +0x120.
        """
        word = offset & ~3
        changed = [o for o in range(word, word + 4) if before[o] != after[o]]
        return changed == [offset]

    flag = [o for o in range(0, CHUNK)
            if start[subject][o] == closed[subject][o] != opened[subject][o] == 0
            and alone_in_its_word(start[subject], opened[subject], o)
            and not moved(start[control], opened[control], o, 1)]
    alpha = [o for o in range(0, CHUNK - 4, 4)
             if struct.unpack_from('<f', opened[subject], o)[0] == 1.0
             and struct.unpack_from('<f', start[subject], o)[0] == 0.0
             and start[subject][o:o + 4] == closed[subject][o:o + 4]
             and not moved(start[control], opened[control], o, 4)]
    if len(flag) != 1 or len(alpha) != 1:
        raise SystemExit('deriving visibility failed: %d candidates for the flag %s and %d for '
                         'alpha %s; expected exactly one of each'
                         % (len(flag), ['0x%03X' % o for o in flag[:6]],
                            len(alpha), ['0x%03X' % o for o in alpha[:6]]))
    print('flag: +0x%03X, alpha: +0x%03X (%s toggled, %s did not move)'
          % (flag[0], alpha[0], subject, control))
    return dict(fields, flag=flag[0], alpha=alpha[0])


def position_from_tree(pid, fields, nodes=1000):
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
    walking it needs the parent and children offsets.
    """
    configure_channel(fields)
    root, walked = quick_root(fields, pid)
    chunks, _ = chunks_of(list(walked)[:nodes])
    from_tree = _pos_field(chunks, fields['parent'], fields['size'], set(chunks))
    if from_tree != fields['position']:
        print('position: the scan said +0x%03X, the tree says +0x%03X; the tree decides'
              % (fields['position'], from_tree))
    return dict(fields, position=from_tree)


def store(fields):
    os.makedirs(os.path.dirname(STORED), exist_ok=True)
    with open(STORED, 'w') as file:
        json.dump(fields, file, indent=1)


def stored():
    if not os.path.exists(STORED):
        return None
    with open(STORED) as file:
        fields = json.load(file)
    return fields if fields.get('key') == build_key() else None


def to_root(address, f_parent):
    """Up until the parent is no longer a widget. `tree` on a non-widget returns nothing, and that
    is the test right there."""
    p, nodes = address, tree(address)
    for _ in range(40):
        b = read(p + f_parent, 8)
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


def quick_root(fields, pid, at_least=500, ample=1500, samples=40):
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
    found = {}
    for group in seed_batches(pid):
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
    raise SystemExit('no widget tree of any significance found; is the game still running?')


def _sample(nodes, root, how_many=200):
    """Spread across memory, so that one odd pool does not decide the outcome."""
    addresses = sorted(nodes)
    step = max(1, len(addresses) // how_many)
    choice = addresses[::step][:how_many]
    if root not in choice:
        choice.append(root)
    return choice


def _child_check(fields, root, how_many=20):
    """From the root downwards: a parent's child list must contain exactly the widgets naming that
    parent as their parent. This tests the child field, the count and the parent field in one
    movement, and it need not cover the whole tree.
    """
    todo, tested, misses = [root], 0, 0
    while todo and tested < how_many:
        parent = todo.pop(0)
        b = read(parent, CHUNK)
        if b is None:
            continue
        items = int.from_bytes(b[fields['children']:fields['children'] + 8], 'little')
        count = int.from_bytes(b[fields['count']:fields['count'] + 4], 'little')
        if not items or count == 0 or count > 500:
            continue
        block = read(items, count * 8)
        if block is None:
            misses += 1
            continue
        children = [int.from_bytes(block[i:i + 8], 'little') for i in range(0, len(block), 8)]
        for child in children:
            back = read(child + fields['parent'], 8)
            if back is None or int.from_bytes(back, 'little') != parent:
                misses += 1
        todo.extend(children)
        tested += 1
    return tested, misses


def verify(fields, root, nodes, pid):
    """Recheck the stored derivation against the game running right now. Three predictions, all
    three verifiable without eyesight. What comes back is a list of defects; if it is empty, the
    stored derivation still holds.

    A sample is enough: this check has to establish whether the layout is still the same, not take
    inventory of the whole tree. Walking every node cost three seconds at every start and added
    nothing.
    """
    chunks, _ = chunks_of(_sample(nodes, root))
    window_width, window_height = window_size(pid)
    defects = []

    tested, misses = _child_check(fields, root)
    if tested < 5:
        defects.append('too few parents with children found to test against')
    elif misses:
        defects.append('child list and parent field contradict each other in %d places' % misses)

    if root in chunks:
        b, h = _pair(chunks[root], fields['size'])
        scale_x = window_width / b if b else 0.0
        scale_y = window_height / h if h else 0.0
        if not scale_x or abs(scale_x - scale_y) > 0.005:
            defects.append('the root is out of proportion with the drawing area '
                               '(%.0fx%.0f against window %dx%d)'
                               % (b, h, window_width, window_height))

    gui = gui_text()
    names = {t for t in (_cstring(b, fields['name']) for b in chunks.values()) if t}
    hit = sum(1 for n in names if n in gui)
    if not names or hit < 0.6 * len(names):
        defects.append('names do not appear in the gui files (%d of %d)'
                           % (hit, len(names)))

    defects.extend(_position_check(fields, nodes))
    defects.extend(_visibility_check(fields, chunks, nodes, pid))
    return defects


def _position_check(fields, nodes, how_many=800):
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
    if 'position' not in fields:
        return ['no position offset in the stored derivation']
    chunks, _ = chunks_of(list(nodes)[:how_many])
    if not chunks:
        return ['nothing could be read from the tree to check the position offset against']
    distinct = _spread(chunks, fields['position'])
    families = _siblings_spread(chunks, fields['parent'], fields['position'])
    if distinct < 100 or families is None or families < 0.9:
        return ['position at +0x%03X does not behave like one: %d distinct values, %s of families '
                'spread their children' % (fields['position'], distinct,
                                           'no' if families is None else '%.2f' % families)]
    return []


def _visibility_check(fields, chunks, nodes, pid):
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
    use_fields(fields)
    defects = []
    alphas = [struct.unpack_from('<f', b, fields['alpha'])[0] for b in chunks.values()]
    if not alphas or any(a < 0.0 or a > 1.0 for a in alphas) or 1.0 not in alphas:
        defects.append('alpha at +0x%03X is not a fraction across the sample' % fields['alpha'])

    module = vtablemap.module_base(pid)
    window_classes = {module + v for v in (memory.vtables_by_name('Window') or [])}
    # `verify` is handed the map from `tree`, which is address -> vtable; `widgets` hands over the
    # full record instead. Take the vtable from either rather than demanding one of the two.
    windows = [a for a, k in nodes.items()
               if (k[0] if isinstance(k, tuple) else k) in window_classes][:400]
    values = list(flags_for(windows).values()) if windows else []
    if not values:
        defects.append('no window object could be read at +0x%03X' % fields['flag'])
    elif any(v & ~0x3F for v in values):
        defects.append('the window flag at +0x%03X carries bits it never carries (%s)'
                       % (fields['flag'], sorted({'0x%02X' % v for v in values})[:6]))
    return defects


def fields_for(pid):
    """The path walked at every start.

    If there is a derivation for this exe and it holds up against the running game, that is the
    one. Otherwise it is derived again and written out. Nothing is assumed: a stored derivation
    also has to prove itself every time.
    """
    vtablemap.configure(pid)          # vtables first, or no scan finds anything
    fields = stored()
    if fields:
        root, nodes = quick_root(fields, pid)
        defects = verify(fields, root, nodes, pid)
        if not defects:
            use_fields(fields)
            return fields, 'stored derivation holds'
        reason = 'stored derivation fails: ' + '; '.join(defects)
    else:
        reason = 'no derivation for this version of the game'
    fields = derive_all(pid)
    fields = position_from_tree(pid, fields)
    root, _ = quick_root(fields, pid)
    fields, note = _with_visibility(pid, fields, root)
    store(fields)
    use_fields(fields)
    return fields, reason + ' - derived again' + note


def _with_visibility(pid, fields, root):
    """Add the two visibility offsets if this game state allows deriving them.

    They need a window that can be opened, and the main menu has none - its window objects are all
    dialogues nobody has opened. Deriving the other seven there is still useful, so the tree can be
    walked and read; what cannot be answered is what is visible, and `use_fields` makes any attempt
    to ask say so instead of guessing.
    """
    try:
        return visibility_fields(pid, fields, root), ''
    except SystemExit as why:
        return fields, '; visibility not derived (%s)' % why


def configure_channel(fields):
    """Hands the derived offsets to the DLL. The DLL knows nothing about CK3; all knowledge about
    it lives here."""
    channel.ask('set %x %x %x %x %x' % (fields['parent'], fields['position'],
                                         fields['size'], fields['name'], fields['text']))
    channel.ask('childfield %x %x' % (fields['children'], fields['count']))


def _start_block():
    fields, why = fields_for(int(sys.argv[1]))
    print(why)
    for name in ('parent', 'children', 'count', 'position', 'size', 'name', 'text',
                 'alpha', 'flag'):
        print('%-9s +0x%03X' % (name, fields[name]) if name in fields
              else '%-9s not derived in this game state' % name)


def regions(pid):
    """The memory regions of the game, asked for from the outside.

    Needed because `scan` walks a window to the end before answering: a roomy window therefore
    costs the full scan time, even when the first hit lands immediately. With this list the scan
    can be aimed, up to the first hit.
    """
    import ctypes
    k32 = memory._k32
    handle = k32.OpenProcess(0x0410, False, pid)
    if not handle:
        raise SystemExit('cannot open the game process: %d' % pid)
    items = []
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


def seed_batches(pid, chunk=0x4000000):
    """Per piece of memory the addresses found, until the caller finds a usable one.

    Scanning happens in chunks because `scan` walks a window to the end before answering: a roomy
    window costs the full scan time even when the first hit lands immediately.
    """
    stack, total = [], 0
    for base, size in regions(pid):
        stack.append((base, size))
        total += size
        if total < chunk:
            continue
        found = scan(stack[0][0], stack[-1][0] + stack[-1][1])
        if found:
            yield sorted(found)
        stack, total = [], 0
    if stack:
        found = scan(stack[0][0], stack[-1][0] + stack[-1][1])
        if found:
            yield sorted(found)


if __name__ == '__main__':
    _start_block()
