"""Captures the screen or a crop of it, small enough to read back.

What is visible here must never carry a claim that ends up in the product - the widget tree and
the files on disk are what count for that. This exists to find what is on screen but NOT in the
tree: icons, colour, placement, and windows that swallow clicks.
"""
import ctypes
import os
import sys

from PIL import ImageGrab

ctypes.windll.user32.SetProcessDPIAware()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
os.makedirs(paths.WORK, exist_ok=True)
DEFAULT = os.path.join(paths.WORK, 'beeld.jpg')


def capture(path=DEFAULT, box=None, scale=0.5, quality=60):
    """box is (left, top, right, bottom) in screen points, or None for the whole screen."""
    screenshot = ImageGrab.grab(bbox=box)
    if scale != 1.0:
        screenshot = screenshot.resize((int(screenshot.width * scale), int(screenshot.height * scale)))
    screenshot = screenshot.convert('RGB')
    screenshot.save(path, 'JPEG', quality=quality)
    return path, screenshot.size


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    crop_box = tuple(int(w) for w in sys.argv[2:6]) if len(sys.argv) >= 6 else None
    path, extent = capture(target, crop_box)
    import os
    print('%s  %dx%d  %.0f kB' % (path, extent[0], extent[1], os.path.getsize(path) / 1024))


def diff(box=None, pause=0.4):
    """Captures the same crop twice and counts how many pixels changed.

    Counting is more useful than looking: it answers 'did anything happen' without anyone having
    to look at the screen. Move the mouse outside the box, or you are measuring the cursor.
    """
    import time
    first = ImageGrab.grab(bbox=box).convert('RGB')
    time.sleep(pause)
    second = ImageGrab.grab(bbox=box).convert('RGB')
    if first.size != second.size:
        raise ValueError('the two captures are not the same size')
    a, b = first.load(), second.load()
    changed = 0
    for y in range(first.height):
        for x in range(first.width):
            if a[x, y] != b[x, y]:
                changed += 1
    total = first.width * first.height
    return changed, total
