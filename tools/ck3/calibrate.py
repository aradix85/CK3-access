"""Calibration - does what we read out of the game match what the save says?

The answer key is the newest manual save; autosaves are binary and drop out. Every source is held
against it separately and reported separately, because the value is in knowing which source is
broken: if a field offset shifts after a patch, only the game model fails and the rest stands.

Usage:
    python tools\\ck3\\calibrate.py <pid> [<number of characters>] [<save>]

The save argument is any part of a save file name, and it is what you reach for when the game has
something other than the newest save loaded. Recognition is tested against the widget tree, the
game model against the save, and the characters are taken spread across the whole database so that
the block arithmetic is tested rather than one block.

**Seven fields need a save written from the state now loaded**, not the file that state was loaded
from: the game recomputes the levies around loading. They are reported apart, so that a
disagreement there reads as a stale answer key rather than as a moved field.
The field offsets live in `reports\\model.json` and are derived by `model.py`, not typed in.
"""
import glob
import os
import sys

import derive
import model
import savegame

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.path.join(PROJECT, 'reports', 'model.json')
sys.path.insert(0, os.path.join(PROJECT, 'tools'))  # boxreader and windowgrab sit one folder up


def save_named(save=None):
    """The path of the save that serves as the answer key.

    Defaults to the newest readable save. Name the save - any part of the file name will do - when
    the game has a different one loaded. Memory carries the state that was loaded, and held against
    another save every field disagrees at once, which reads exactly like a shifted field offset.

    **For the seven fields the game recomputes around loading this is not enough**, and that was
    measured on two states on 29 August 2026: the file the state was loaded from disagrees with
    memory for a third of all characters. Those need a save written from the state now loaded.
    """
    if save is None:
        return savegame.newest_readable_save()
    matches = [p for p in glob.glob(os.path.join(savegame.SAVE_DIR, '*.ck3'))
               if save.lower() in os.path.basename(p).lower()]
    if len(matches) != 1:
        raise SystemExit('%d saves carry %r in their name, so it says nothing' % (len(matches), save))
    return matches[0]


def text_boxes(nodes):
    """The addresses of the text boxes, found through the vtable that touches the localization files.

    The text field exists on every object but only makes sense on a text box; on the rest you read
    the neighbour from the same pool - shader names and fragments of shader code. Which vtable it
    is differs per build, so it is determined here and not written down.
    """
    translation = derive.localization_text()
    hit = {}
    for vtable, x, y, width, height, parent, name, text in nodes.values():
        clean = derive.strip_markup(text)
        if len(clean) > 3 and clean in translation:
            hit[vtable] = hit.get(vtable, 0) + 1
    if not hit:
        raise SystemExit('not a single widget text appears in the localization files')
    best = max(hit, key=hit.get)
    return [a for a, w in nodes.items() if w[0] == best and w[7].strip()]


def _flat(text):
    """For comparison: widget text glues markup fragments together without a space."""
    return ''.join(text.split()).lower()


def test_ocr(pid, nodes, addresses):
    """Reads every text box actually on screen and puts it beside the widget text.

    Alpha is not enough to know whether a box is showing: the game builds all windows up front and
    leaves about 28 of them at alpha 1.0 without drawing them, and a window lying over another
    leaves the alpha of what is underneath untouched. Without a second witness this test therefore
    scores the pixels of the wrong window as a reading error - measured 29 July 2026: 23 of 63
    boxes were covered that way.

    So the full pipeline gets a vote: it reads the whole screen once, and a box only counts if a
    line overlaps it carrying the same text. That is a different engine with its own detection, and
    therefore an independent witness. Rejected boxes are reported, not hidden.
    """
    import ocr
    import boxreader
    import windowgrab
    screenshot, box_width, high = windowgrab.grab(pid)
    lines = ocr.read_image(screenshot)

    ok, total, covered, misses = 0, 0, 0, []
    scales = derive.scales_for(list(nodes))
    for address in addresses:
        vtable, dx, dy, width, height, parent, name, text = nodes[address]
        if width < 4 or height < 4 or not derive.is_visible(nodes, address):
            continue
        x, y = derive.screen_pos(nodes, address, scales)
        width, height = derive.screen_size(nodes, address, scales)
        x, y, b, h = int(x), int(y), int(width), int(height)
        truth = derive.strip_markup(text)
        witness = [r for r in lines
                   if not (x + b < r[0] or r[0] + r[2] < x or y + h < r[1] or r[1] + r[3] < y)
                   and _flat(truth) in _flat(r[4])]
        if not witness:
            covered += 1
            continue
        read_text, confidence = boxreader.read_box_conf(screenshot, x, y, b, h)
        total += 1
        if _flat(read_text) == _flat(truth):
            ok += 1
        elif len(misses) < 5:
            misses.append('%r read as %r (confidence %.2f)' % (truth, read_text, confidence))
    return ok, total, covered, misses


def main(pid, count=400, save=None):
    path = save_named(save)
    print('answer key: %s' % os.path.basename(path))

    fields = derive.fields_for(pid)[0]
    derive.configure_channel(fields)
    root = derive.quick_root(fields, pid)[0]
    nodes = derive.widgets(root)
    print('widget tree: %d nodes' % len(nodes))

    ok, total, covered, misses = test_ocr(pid, nodes, text_boxes(nodes))
    print('recognition against widget tree: %d of %d confirmed boxes '
          '(%d rejected: covered or not drawn)' % (ok, total, covered))
    for line in misses:
        print('   %s' % line)

    counters, read, wrong, misses, places = model.compare(pid, path, count)
    blocks = places // 1024
    print('game model: %d characters read across %d blocks, %d slots reused or unreadable'
          % (read, blocks, wrong))
    for field, (g, t) in sorted(counters.items()):
        print('   %-24s %d of %d%s' % (field, g, t,
                                       '   recomputed on load' if field in model.RECOMPUTED_ON_LOAD
                                       else ''))
    for line in misses:
        print('   %s' % line)
    # The verdict, because that is the whole point after a patch: which field moved? A field that
    # is recomputed around loading is called out separately - there the likely fault is the answer
    # key rather than the offset, and saying so is what stops the next session hunting a ghost.
    shifted = ['%s (%d wrong)' % (f, t - g) for f, (g, t) in sorted(counters.items())
               if g < t and f not in model.RECOMPUTED_ON_LOAD]
    stale = ['%s (%d wrong)' % (f, t - g) for f, (g, t) in sorted(counters.items())
             if g < t and f in model.RECOMPUTED_ON_LOAD]
    print('   %s' % ('fields that disagree with the save: ' + ', '.join(shifted) if shifted
                     else 'every field that survives a load agrees with the save'))
    if stale:
        print('   these are recomputed around loading, so this points at the answer key rather '
              'than at a moved field: %s' % ', '.join(stale))
        print('   write a save from the state now loaded and hand that one in instead')
    defects = model.check(pid)
    print('   the derivation itself %s'
          % ('holds against the running game' if not defects else 'has defects: '
             + '; '.join(defects)))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    given = sys.argv[1:]
    named = given.pop() if given and not given[-1].isdigit() else None
    main(int(given[0]), *[int(a) for a in given[1:]], save=named)
