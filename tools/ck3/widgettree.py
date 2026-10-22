"""The widget tree of the running game, as the channel walks it: every widget with its place, its
name and its text, and the class it is.

`derive` finds the field offsets this walk runs on, and `onscreen` says what of the tree is drawn
and where.
"""
import re
import sys

from tools.ck3 import channel, memory, vtablemap
from tools.nvda import speech

# One widget as the tree walk gives it: vtable, x and y relative to the parent, width, height,
# parent address, name, text. The tree maps the address of each widget to this.
Widget = tuple[int, float, float, float, float, int, str, str]
Nodes = dict[int, Widget]
# The classes whose text field is their own. On any other widget the same offset reads the
# neighbour, because text boxes come out of one pool back to back - so filter on class before
# believing a text.
TEXT_CLASSES = ('Textbox', 'Editbox')


def widgets(root: int) -> Nodes:
    """The whole tree with fields attached: address -> (vtable, x, y, width, height, parent, name, text).

    x and y are relative to the parent; use `onscreen.screen_pos` for the place on screen. The text
    is only valid on a text box - on other classes you are reading the neighbour from the same
    pool. So filter on vtable before believing the text.

    **The order of this dict is the engine's own child order, and it is the only copy of it.** The
    DLL walks each widget's child list in index order and this keeps the lines as they arrive, so
    the children of a parent come out in the order the game draws them - which is what decides
    which of two drawn widgets lies on top. Nothing else records it: the parent offset says who the
    parent is, never in which place. Rebuild children from this dict and do not sort them.
    """
    nodes: Nodes = {}
    missing: list[tuple[str, str]] = []
    for line in channel.ask(f'tree {root:x}', timeout=60).split('\n'):
        d = line.split('\t')
        if d[0] == 'w':
            nodes[int(d[1], 16)] = (int(d[2], 16), float(d[3]), float(d[4]), float(d[5]),
                                    float(d[6]), int(d[7], 16), d[8], d[9])
        elif d[0] == 'missing':
            missing.append((d[1], d[2]))
    missing = [(address, why) for address, why in missing if not _foreign_text(nodes, address, why)]
    # Whatever the walk lost it says on a `missing` line - a node or child list it could not read,
    # a child count nobody believes, a walk an exception broke off, a text cut short - so say so:
    # on 1.20.0.3 a walk that skipped such nodes in silence lost the decisions window and its 526
    # widgets. Spoken once per address, because the reader asks for the toast container every round
    # and a node that stays unreadable would otherwise be said every 400 ms.
    if missing:
        print(f"tree from {root:x}: {len(missing)} places lost: {'; '.join(f'{address} {why}{_lost_where(nodes, int(address, 16))}' for address, why in missing[:5])}", file=sys.stderr, flush=True)
        new = {address for address, _ in missing} - _MISSING_SAID
        if new:
            _MISSING_SAID.update(new)
            speech.failure('reading the game', 'part of the screen could not be read and is left out',
                           'so what you hear may be incomplete; report it with the game version')
    return nodes


# The addresses as the DLL writes them on a `missing` line, in hex text.
_MISSING_SAID: set[str] = set()
# Per game process, the vtables of `TEXT_CLASSES` where that process loaded them.
_TEXT_VTABLES: dict[int, set[int]] = {}


def _foreign_text(nodes: Nodes, address: str, why: str) -> bool:
    """Is this a text cut short on a widget whose class has no text of its own? The DLL reads the
    text field of every widget, and on another class that field holds something else: on
    22 October 2026 on Harold the two texts of 262148 characters cut short were on
    `construct_progressbar` and `building_progressbar`, and all 195 widgets of those names are a
    `ProgressBar`. Nothing believes such a text, so its loss is no loss. Asked only when a text is
    cut short, because finding the classes reads the exe."""
    if not why.startswith('text of'):
        return False
    pid = int(channel.ask('hello').split('\t')[1])
    if pid not in _TEXT_VTABLES:
        base = vtablemap.module_base(pid)
        _TEXT_VTABLES[pid] = {base + rva for name in TEXT_CLASSES for rva in memory.vtables_by_name(name)}
    return nodes[int(address, 16)][0] not in _TEXT_VTABLES[pid]


def _lost_where(nodes: Nodes, address: int) -> str:
    """The names from a lost widget up towards its window, so a loss says where it is: the texts cut
    short on 21 October 2026 could not be brought back that afternoon to see which they were."""
    names: list[str] = []
    while address in nodes and len(names) < 6:
        names.append(nodes[address][6] or '-')
        address = nodes[address][5]
    return f" ({' < '.join(names)})" if names else ''


_MARKUP = re.compile('[\x15\x16][^ !]*[ !]?')


def strip_markup(text: str) -> str:
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


def class_map(pid: int, addresses: dict[int, int]) -> dict[int, str | None]:
    """Address -> class name, through the vtable. `addresses` is a dict {address: vtable}, not a list."""
    base = vtablemap.module_base(pid)
    names = {base + rva: name for rva, name in memory.widget_vtables().items()}
    return {address: names.get(vtable) for address, vtable in addresses.items()}
