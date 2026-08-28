"""Calibration - does what we read out of the game match what the save says?

The answer key is the newest manual save; autosaves are binary and drop out. Every source is held
against it separately and reported separately, because the value is in knowing which source is
broken: if a field offset shifts after a patch, only the game model fails and the rest stands.

Usage:
    python tools\\ck3\\calibrate.py <pid> [<number of characters>] [<step>] [<save>]

The save argument is any part of a save file name, and it is what you reach for when the game has
something other than the newest save loaded. Recognition is tested against the widget tree, the
game model against the save. Take a step large
enough to cross several blocks; within one block you are not testing the block arithmetic.
The field offsets live in `reports\\model.json` and belong to be derived there, not typed in here.
"""
import glob
import os
import sys

import derive
import anchor
import savegame

PROJECT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL = os.path.join(PROJECT, 'reports', 'model.json')
sys.path.insert(0, os.path.join(PROJECT, 'tools'))  # boxreader and windowgrab sit one folder up


def answer_key(save=None):
    """The unpacked save that serves as the answer key, with its path.

    Defaults to the newest readable save. Name the save - any part of the file name will do - when
    the game has a different one loaded. Memory carries the state that was loaded, and held against
    another save every field disagrees at once, which reads exactly like a shifted field offset.
    """
    if save is None:
        path = savegame.newest_readable_save()
    else:
        matches = [p for p in glob.glob(os.path.join(savegame.SAVE_DIR, '*.ck3'))
                   if save.lower() in os.path.basename(p).lower()]
        if len(matches) != 1:
            raise SystemExit('%d saves carry %r in their name, so it says nothing' % (len(matches), save))
        path = matches[0]
    return path, savegame.unpack(path)


def test_model(key_sheet, pid, numbers):
    """Reads characters through the anchor and puts every field beside the save.

    Unknown numbers are counted, not scored as errors: an empty slot is normal, and a character
    the save does not know is not a shifted field offset. Walk across several blocks, or you are
    not testing the block arithmetic.

    The database object is fetched once and handed down. Letting `anchor.character` find it again
    per character is what made this round unusable: measured 28 August 2026, twenty characters cost
    0.08 s with the object passed in and five cost 9.9 s without, because looking the database up
    is 1.9 s on its own. Reading a character is 4 ms; everything else was the lookup.
    """
    counters = {}
    index = savegame.character_index(key_sheet)
    db = anchor.database(pid)
    unknown, empty, misses = 0, 0, []
    for number in numbers:
        pos, from_memory = anchor.character(pid, number, db)
        if from_memory['number'] != number:
            empty += 1
            continue
        values = savegame.numbers(_character_block(key_sheet, index, number))
        if not values:
            unknown += 1
            continue
        for field in from_memory:
            if field not in values:
                continue
            ok, total = counters.get(field, (0, 0))
            matches = from_memory[field] == values[field]
            counters[field] = (ok + (1 if matches else 0), total + 1)
            if not matches and len(misses) < 5:
                misses.append('%s at %d: memory %d, save %d'
                           % (field, number, from_memory[field], values[field]))
    return counters, unknown, empty, misses


def _character_block(key_sheet, index, number):
    """The block of a character, and not that of a title with the same number.

    The index carries that distinction - see `savegame.character_index` - and it is what keeps a
    round of hundreds of characters affordable.
    """
    if number not in index:
        return None
    return savegame.block(key_sheet, str(number), index[number] - 1)


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


def main(pid, count=400, step=97, save=None):
    path, key_sheet = answer_key(save)
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

    blocks, places = anchor.size(pid)
    numbers = list(range(1, places, step))[:count]
    counters, unknown, empty, misses = test_model(key_sheet, pid, numbers)
    print('game model: %d characters across %d blocks' % (len(numbers), blocks))
    for field, (g, t) in sorted(counters.items()):
        print('   %-14s %d of %d' % (field, g, t))
    print('   %d empty slots, %d numbers the save did not know' % (empty, unknown))
    for line in misses:
        print('   %s' % line)
    # The verdict, because that is the whole point after a patch: which field moved?
    shifted = ['%s (%d wrong)' % (f, t - g) for f, (g, t) in sorted(counters.items()) if g < t]
    print('   %s' % ('fields that disagree with the save: ' + ', '.join(shifted) if shifted
                     else 'every field agrees with the save'))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    given = sys.argv[1:]
    named = given.pop() if given and not given[-1].isdigit() else None
    main(int(given[0]), *[int(a) for a in given[1:]], save=named)
