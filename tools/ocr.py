"""Reads the text on screen, with positions attached.

Runs on the `rapidocr` package (3.9.2), OpenVINO engine. Two routes: `read_image` for a whole
screen and `read_box` for a box whose position the widget tree already knows.

The setup is fixed and measured, 28 July 2026, and the alternatives are closed questions.
Detection PP-OCRv5 `ch mobile`, recognition PP-OCRv6 `tiny`, line orientation classification off. A
full screen of 1600x900 costs 0.98 s; a known box 6 ms. Heavier models were tested and lost:
`medium` is twelve times slower and does not read one letter better, and the server models are both
worse and ten times slower.

If you want it faster per box, recognition moves to the NPU: measured 29 July 2026 over 22 boxes,
1.86 ms via `tools\\boxreader.py` against 6.02 ms here, with the same result on every box. That
route needs a fixed input shape and deliberately does not live in this file.
"""
import ctypes

import numpy
from PIL import Image, ImageGrab
from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion, RapidOCR

ctypes.windll.user32.SetProcessDPIAware()

# Why these two models, briefly: the recognition model decides which characters can come out
# at all. PP-OCRv4 does not know the r-hacek of `Premyslid` and turns it into `premyslid`; v5
# and v6 do know it. Within v6, `tiny` is as accurate as `small` and `medium` and much faster.
_CHOICE = {
    'Det.engine_type': EngineType.OPENVINO,
    'Det.lang_type': LangDet.CH,
    'Det.model_type': ModelType.MOBILE,
    'Det.ocr_version': OCRVersion.PPOCRV5,
    'Rec.engine_type': EngineType.OPENVINO,
    'Rec.lang_type': LangRec.CH,
    'Rec.model_type': ModelType.TINY,
    'Rec.ocr_version': OCRVersion.PPOCRV6,
    'Global.use_cls': False,
}

_instance = None


def _engine():
    """The engine is only built on first use; loading costs about a second."""
    global _instance
    if _instance is None:
        _instance = RapidOCR(params=_CHOICE)
    return _instance


def warm_up():
    """Pay the startup cost at a moment when nobody is waiting.

    Note: `use_det` and `use_rec` stick to the engine once you pass them in. A warm-up round
    without the detection step therefore switched it off for everything that came after, and then
    `read_image` returns zero lines with no error at all. That is why the flags are spelled out on
    every call.
    """
    probe = numpy.array(Image.new('RGB', (96, 32), (255, 255, 255)))
    _engine()(probe, use_det=False, use_cls=False, use_rec=True)
    _engine()(probe, use_det=True, use_cls=False, use_rec=True)


def _box(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))


def read_image(screenshot):
    """Returns a list of (x, y, width, height, text) in the points of this image."""
    result = _engine()(numpy.array(screenshot.convert('RGB')),
                          use_det=True, use_cls=False, use_rec=True)
    if getattr(result, 'boxes', None) is None:
        return []
    lines = [(*_box(crop), text.strip())
              for crop, text in zip(result.boxes, result.txts)]
    lines.sort(key=lambda r: (r[1], r[0]))
    return lines


def read_box(screenshot, x, y, width, height, margin=2):
    """Reads one box whose position is already known from the widget tree.

    Detection goes off here: it exists to find text, and we already know where it is. On a small
    crop it also gets confused - measured 28 July 2026, `Load Game` became `Game peo` when the full
    pipeline was let loose on a scrap.

    On the margin: over fifteen boxes with known ground truth, 0 through 6 points all gave fifteen
    correct, and only at 10 did it collapse. So the margin is not critical - except where a
    neighbouring element sits close. At `Settings` on the main menu a gear icon touches the word:
    with margin 2 it reads `Settings`, with 6 `Sttins` and with 12 `stiting`. Hence small.
    """
    part = screenshot.convert('RGB').crop((max(0, x - margin), max(0, y - margin),
                                      x + width + margin, y + height + margin))
    result = _engine()(numpy.array(part), use_det=False, use_cls=False, use_rec=True)
    if not getattr(result, 'txts', None):
        return ''
    return result.txts[0].strip()


def read_screen(box=None):
    """Returns a list of (x, y, width, height, text) in screen points.

    This grabs the whole screen and therefore the foreground window. For the game,
    `tools\\windowgrab.py` plus `read_image` is the better route: it does not need the foreground.
    """
    screenshot = ImageGrab.grab(bbox=box)
    shift_x, shift_y = (box[0], box[1]) if box else (0, 0)
    return [(x + shift_x, y + shift_y, b, h, text)
            for x, y, b, h, text in read_image(screenshot)]


if __name__ == '__main__':
    for x, y, b, h, text in read_screen():
        print('%5d,%5d  %3dx%-3d  %s' % (x, y, b, h, text))
