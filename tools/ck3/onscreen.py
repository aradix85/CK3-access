"""What of the widget tree is on screen, and where: the state byte and alpha that decide whether a
widget is drawn, the frame of a list that clips it, the drawing area, and the scales and anchors
that turn a place in the tree into a point on the screen.

The two visibility offsets and the drawing area belong to a run: `derive.fields_for` publishes them
through `use_fields` and `use_screen`, and every question here stops loudly until it has.
"""
import pathlib
import struct
from collections.abc import Iterable

from tools import windowgrab
from tools.ck3 import channel, guimap, widgettree

# Per widget: its own scale, and the scale that reaches it from above.
Scales = dict[int, tuple[float, float]]
# Per window name: does the centring correction apply in x, and in y.
Anchors = dict[str, tuple[bool, bool]]


def window_size(pid: int) -> tuple[int, int]:
    """The drawing area of the game window, live from Windows.

    Not from `pdx_settings.txt`: that file is only written on exit and therefore does not know the
    GUI scale of this moment.
    """
    hwnd, _, _ = windowgrab.window_of(pid)
    return windowgrab.client_size(hwnd)


ALPHA: int | None = None
WINDOW_FLAG: int | None = None
DRAWING_AREA: tuple[int, int] | None = None


def use_screen(pid: int) -> tuple[int, int]:
    """Publish the drawing area of this run, because it is not a property of the build.

    Asked once and remembered: it is fixed while the game runs - the size is set in
    `pdx_settings.txt` while the game is shut - and `on_screen` asks for it per widget, one of
    them 225 times in a single round. Like the two offsets above it starts as None and stays
    loud when unset: a guessed screen size rejects perfectly good widgets with the words "off
    screen", which reads exactly like a measurement and is not one. That is what 1600x900
    written into `openers.on_screen` did once the drawing area became 1920x1200.
    """
    global DRAWING_AREA
    DRAWING_AREA = window_size(pid)
    return DRAWING_AREA


def drawing_area() -> tuple[int, int]:
    if DRAWING_AREA is None:
        raise SystemExit('the drawing area is not known yet: call use_screen(pid) first, or '
                         'derive.fields_for(pid), which does it')
    return DRAWING_AREA


def use_fields(alpha: int | None, flag: int | None) -> None:
    """Publish the two visibility offsets for this build, as the derivation holds them.

    `flags_for` and `is_visible` need an offset but are called per widget, so passing the field
    dictionary down every call site would be noise. They read these two instead, and
    `derive.fields_for` sets them. They start as None on purpose: a wrong offset here reads as
    "nothing is visible", which is indistinguishable from a game that has not drawn anything yet,
    so the failure has to be loud and immediate rather than a plausible empty list.
    """
    global ALPHA, WINDOW_FLAG
    ALPHA, WINDOW_FLAG = alpha, flag


def _visibility_offset(which: str) -> int:
    value = ALPHA if which == 'alpha' else WINDOW_FLAG
    if value is None:
        raise SystemExit(f'the {which} offset is not known yet: call derive.fields_for(pid) first, '
                         'which derives it or reads it back from the stored derivation')
    return value


SWITCHED_OFF = 0x02     # `enabled` false on this widget or an ancestor
HIDDEN = 0x08           # a `visible` condition that does not hold, on this widget
PASSES_CLICKS = 0x20    # `alwaystransparent`, or the class default for icons and layouts


def flags_for(addresses: Iterable[int]) -> dict[int, int]:
    """The state byte of many objects. It is a bit pattern, and only `HIDDEN` decides what is drawn.

    **Measured 3 October 2026 on 1.20.0.3, over all 294 named window objects and the gui files, on
    two states with the same outcome;** the harvest of 1.19.0.6 shows the same pattern. The counts
    below are from the first.
    0x08 hides, on any widget, and 0x10 never occurs without it. 0x20 is not about being drawn: it
    is the game letting the mouse through - 3052 of 3052 widgets with `alwaystransparent = yes`
    carry it, 4393 of 4398 with `no` do not, and without the line it follows the class (icons and
    layouts pass clicks, buttons and windows catch them). The root, every layer and the activity
    planner carry it while drawn, which is why "zero is a drawn window" failed on them. 0x04 is
    `enabled = no` on the widget itself (407 of 407), and 0x02 goes with it and is inherited by
    everything below: 549 widgets where it starts all carry 0x04, the 140 that inherit it none.
    0x01 never occurs; 0x40 sits on scroll areas, edit boxes and zoom areas and is not read here.
    """
    return channel.field_for(addresses, _visibility_offset('flag'))


def alphas_for(addresses: Iterable[int]) -> dict[int, float]:
    """The alpha of many objects, the way `flags_for` reads the state byte. One that cannot be read
    is missing from the answer."""
    return {address: struct.unpack('<f', value.to_bytes(4, 'little'))[0]
            for address, value in channel.field_for(addresses, _visibility_offset('alpha'), 4).items()}


def shown(nodes: widgettree.Nodes, addresses: Iterable[int]) -> dict[int, int]:
    """Of `addresses`, the ones nothing hides, each with its own state byte.

    Hidden means 0x08 on the widget or on any ancestor; a byte that cannot be read is an object
    that went away between the walk and this question, and counts as not shown. This is the one
    place that says whether a window is drawn. Alpha, clipping and the drawing area are separate
    questions (`is_visible`, `is_clipped`, `drawing_area`).
    """
    chains: dict[int, list[int]] = {}
    for address in addresses:
        chain: list[int] = []
        node = address
        while node in nodes:
            chain.append(node)
            node = nodes[node][5]
        chains[address] = chain
    flags = flags_for({a for chain in chains.values() for a in chain})
    return {address: flags[address] for address, chain in chains.items()
            if all(a in flags and not flags[a] & HIDDEN for a in chain)}


OWN_SCALE = 0x110


def scales_for(addresses: Iterable[int]) -> Scales:
    """Per widget (own scale, scale from above). The two sit next to each other, so one read round.

    Measured 23 August 2026 across all 2437 nodes of the main menu: +0x114 is exactly the product
    of the own scales of every ancestor, no exceptions. So the engine already works that out for
    us and the parent chain does not need multiplying.
    """
    out: Scales = {}
    for address, value in channel.readmany((a + OWN_SCALE for a in addresses), 8).items():
        own, above = struct.unpack('<ff', value)
        out[address - OWN_SCALE] = (own, above)
    return out


def _scale_of(scales: Scales, address: int) -> tuple[float, float]:
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
        raise KeyError(f'no scale for {address:x}: ask scales_for for the whole tree, not only the widgets '
                       'you are placing - screen_pos needs every parent as well')
    return pair


def screen_pos(nodes: widgettree.Nodes, address: int, scales: Scales) -> tuple[float, float]:
    """The place on screen: the own position plus that of every parent, with the scale applied.

    Five of the 515 gui files scale a full-screen container. The arithmetic, measured 30 July and
    23 August 2026: add up the position of every node times the scale that applies at that point
    (+0x114), and for each scaled container above it add `size x (1 - own scale) / 2`. That is the
    difference between shrinking around the centre and shrinking around the edge - and so it only
    applies on an axis where the container hangs centred. Which axes those are comes from disk, via
    `scale_anchors`; a scaled container it does not know is corrected on both axes, which is a
    choice and not a measurement.

    `scales` comes from `scales_for`; pass it in rather than fetching it per widget, because that
    makes it one channel question per four hundred nodes instead of one per node.

    What remains after this is alignment and not geometry: the recognised word sits centred or left
    in its box, and which of the two differs per widget, so compare per widget on left or on centre
    and not blindly on left edges. Measured that way: main menu 24 words, median 0.5 points; pause
    menu 11 words, median 0.5 points.
    """
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


def _anchor_for(nodes: widgettree.Nodes, address: int, anchors: Anchors) -> tuple[bool, bool]:
    """From a scaled container up to the window it hangs in."""
    p, steps = address, 0
    while p in nodes and steps < 24:
        name = nodes[p][6]
        if name in anchors:
            return anchors[name]
        p, steps = nodes[p][5], steps + 1
    return True, True


_ANCHORS: Anchors | None = None


def _scaled(entries: list[guimap.Entry], named: str | None, anchors: Anchors) -> None:
    """Every block that scales itself to fit, under its own name or the nearest name above it,
    with the anchor it hangs on itself - not one a child a few lines further down carries."""
    for entry in entries:
        body = entry['body']
        if not body:
            continue
        own = next((e['value'] for e in body if e['key'] == 'name' and e['value']), named)
        if own and any(e['key'] == 'scale' and 'ScaleToFitElement' in (e['value'] or '') for e in body):
            parts = set(next((e['value'] or '' for e in body if e['key'] == 'parentanchor'), '').split('|'))
            anchors[own] = ('center' in parts or 'hcenter' in parts, 'center' in parts or 'vcenter' in parts)
        _scaled(body, own, anchors)


def scale_anchors() -> Anchors:
    """Per scaled container, by its own name or the nearest name above it: does the centring
    correction apply in x, and in y? Read from the gui files, through `guimap`.

    No table of our own: the anchoring sits as `parentanchor` in the block that carries the `scale`
    line, and that is the source that changes along with the game. Measured 23 August 2026 across
    all gui files: five files really scale. The main menu and the bookmarks hang on `center` and
    therefore correct on both axes; `ingame_pausemenu` hangs on `left|vcenter` and corrects only in
    y; the ruler designer on `hcenter` and `bottom|hcenter` respectively, so only in x. In
    `fullscreen_event.gui` the scale line is commented out, so the event window does not scale -
    that is the hard requirement and it falls outside this. Read per block on 21 October 2026, the
    barbershop scales three containers, and only its portrait hangs on `center`: the line reader
    before it took the anchor of a child eight lines down for the whole window.
    """
    global _ANCHORS
    if _ANCHORS is not None:
        return _ANCHORS
    anchors: Anchors = {}
    for _, _, full in guimap.files():
        text = pathlib.Path(full).read_text(encoding='utf-8-sig', errors='replace')
        if 'ScaleToFitElement' not in text:
            continue
        _scaled(guimap.parse(text), None, anchors)
    _ANCHORS = anchors
    return anchors


def screen_size(nodes: widgettree.Nodes, address: int, scales: Scales) -> tuple[float, float]:
    """The size as it is drawn: the own size times the own scale times the scale from above."""
    _, _, _, width, height, _, _, _ = nodes[address]
    own, combined = _scale_of(scales, address)
    return width * own * combined, height * own * combined


def is_visible(nodes: widgettree.Nodes, address: int) -> bool:
    """Alpha is a property of the whole parent chain: if one ancestor sits at 0 you see nothing,
    while the child itself keeps reporting 1.0. An ancestor that can no longer be read went away
    after the walk, and counts as not shown, as in `shown`."""
    while address in nodes:
        alpha = channel.read(address + _visibility_offset('alpha'), 4)
        if alpha is None or struct.unpack('<f', alpha)[0] == 0.0:
            return False
        address = nodes[address][5]
    return True


def is_clipped(nodes: widgettree.Nodes, address: int, scales: Scales, classes: dict[int, str | None]) -> bool:
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
