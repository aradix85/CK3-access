"""Captures the screen or a crop of it, small enough to read back.

What is visible here must never carry a claim that ends up in the product - the widget tree and
the files on disk are what count for that. This exists to find what is on screen but NOT in the
tree: icons, colour, placement, and windows that swallow clicks.
"""
import ctypes
import os
import sys

import numpy
from PIL import ImageGrab

from tools import paths

ctypes.windll.user32.SetProcessDPIAware()
os.makedirs(paths.WORK, exist_ok=True)
DEFAULT = os.path.join(paths.WORK, 'beeld.jpg')
# (left, top, right, bottom) in screen points.
Box = tuple[int, int, int, int]


def capture(path: str = DEFAULT, box: Box | None = None, scale: float = 0.5,
            quality: int = 60) -> tuple[str, tuple[int, int]]:
    """box is (left, top, right, bottom) in screen points, or None for the whole screen."""
    screenshot = ImageGrab.grab(bbox=box)
    if scale != 1.0:
        screenshot = screenshot.resize((int(screenshot.width * scale), int(screenshot.height * scale)))
    screenshot = screenshot.convert('RGB')
    screenshot.save(path, 'JPEG', quality=quality)
    return path, screenshot.size


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    crop_box = ((int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
                if len(sys.argv) >= 6 else None)
    path, extent = capture(target, crop_box)
    print(f'{path}  {int(extent[0])}x{int(extent[1])}  {os.path.getsize(path) / 1024:.0f} kB')


def diff(box: Box | None = None, pause: float = 0.4) -> tuple[int, int]:
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
    # A pixel counts once, however many of its three channels moved.
    changed = int(numpy.count_nonzero((numpy.asarray(first) != numpy.asarray(second)).any(axis=2)))
    total = first.width * first.height
    return changed, total
