"""Finds, per widget class, where the displayed text sits inside the object.

The reason: +0x390 is right for `Textbox` on the main menu, but in a loaded game it yields four
texts while twenty lines are on screen. So the text field is not one place for all classes.

The method is the same as for the other fields, with the text recogniser as truth instead of the
gui files: take a line demonstrably on screen, find the widgets covering that spot, and search
their bytes for the place where that text sits as a C++ string. What remains is one offset per
class, with a count attached.

Runs standalone and writes to a file: this does not belong in a conversation.
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import derive
import channel
import ocr
import windowgrab

CHUNK = 0x420


def normalize(text):
    """The recogniser does not read perfectly. Compare in lower case without odd characters."""
    return re.sub(r'[^a-z0-9]', '', text.lower())


def capture(pid, root):
    """Image and tree back to back, or you are comparing two different moments.

    The image comes from the game window itself, so the foreground is not needed. The recogniser
    gives window points and the tree gives widget space; since windowed mode those two are no
    longer equal, so the lines are converted with root size divided by window size.
    """
    channel.ask('mouse 5 5 0')                    # cursor into a corner, otherwise a tooltip is showing
    time.sleep(2.0)
    screenshot, window_width, window_height = windowgrab.grab(pid)
    ruw = ocr.read_image(screenshot)

    full, vtb = {}, {}
    for line in channel.ask('tree %x' % root, timeout=60).split('\n'):
        d = line.split('\t')
        if d[0] == 'w' and len(d) >= 9:
            a = int(d[1], 16)
            full[a] = dict(x=float(d[3]), y=float(d[4]), b=float(d[5]), h=float(d[6]),
                          parent=int(d[7], 16), name=d[8])
            vtb[a] = int(d[2], 16)

    fx = full[root]['b'] / window_width
    fy = full[root]['h'] / window_height
    lines = [(x * fx, y * fy, b * fx, h * fy, text) for x, y, b, h, text in ruw]
    return lines, full, vtb


def screen_boxes(full):
    """Screen position per widget, summed along the parent chain within the same tree."""
    out = {}
    for a in full:
        x = y = 0.0
        p, depth = a, 0
        while p in full and depth < 25:
            x += full[p]['x']
            y += full[p]['y']
            p = full[p]['parent']
            depth += 1
        out[a] = (x, y, full[a]['b'], full[a]['h'])
    return out


def candidates(boxes, ox, oy, ob, oh, largest=400.0):
    """Widgets covering the spot of a screen line, smallest first.

    Smallest first because a large panel covers every line and says nothing; the widget carrying
    the text is small and fits tightly around it.
    """
    cx, cy = ox + ob / 2.0, oy + oh / 2.0
    hit = [(b * h, a) for a, (x, y, b, h) in boxes.items()
            if b <= largest and h <= 200 and x - 6 <= cx <= x + b + 6 and y - 6 <= cy <= y + h + 6]
    hit.sort()
    return [a for _, a in hit]


def text_offsets(address, needle):
    """Offsets in this object where `needle` sits as a C++ string.

    Walks every aligned position and uses the same parsing as the field derivation, so both text
    inside the object itself and text behind a pointer.
    """
    chunk = derive.read(address, CHUNK)
    if chunk is None:
        return []
    target = normalize(needle)
    if len(target) < 3:
        return []
    found = []
    for offset in range(0, CHUNK - 32, 8):
        text = derive._cstring(chunk, offset)
        if not text:
            continue
        strip_markup = normalize(derive.strip_markup(text))
        if strip_markup and (target in strip_markup or strip_markup in target):
            found.append(offset)
    return found


def search(pid, root, output):
    ocr, full, vtb = capture(pid, root)
    class_of = derive.class_map(pid, vtb)
    boxes = screen_boxes(full)

    per_class = defaultdict(Counter)
    no_hit = []
    for ox, oy, ob, oh, text in ocr:
        if len(normalize(text)) < 3:
            continue
        hit = False
        for a in candidates(boxes, ox, oy, ob, oh)[:6]:
            for offset in text_offsets(a, text):
                per_class[class_of.get(a) or '?'][offset] += 1
                hit = True
        if not hit:
            no_hit.append((ox, oy, text))

    report = {
        'screen_lines': len(ocr),
        'nodes': len(full),
        'per_class': {k: v.most_common(4) for k, v in per_class.items()},
        'without_hit': no_hit[:20],
    }
    with open(output, 'w', encoding='utf-8') as file:
        json.dump(report, file, indent=1, ensure_ascii=False)
    return report


if __name__ == '__main__':
    v = search(int(sys.argv[1]), int(sys.argv[2], 16), sys.argv[3])
    print('screen lines %d, nodes %d' % (v['screen_lines'], v['nodes']))
    for cls, positions in sorted(v['per_class'].items(), key=lambda p: -sum(n for _, n in p[1])):
        print('%-16s %s' % (cls, ', '.join('+0x%03X (%dx)' % (p, n) for p, n in positions)))
    print('screen lines without any hit: %d' % len(v['without_hit']))
