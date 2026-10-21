"""Reads the text on screen, with positions attached.

Runs on the `rapidocr` package (3.9.2), OpenVINO engine: `read_image` for a whole screen or a
window. A box whose position the widget tree already knows is read on the NPU, `tools\\boxreader.py`.

The setup is fixed and measured, 28 July 2026, and the alternatives are closed questions.
Detection PP-OCRv5 `ch mobile`, recognition PP-OCRv6 `tiny`, line orientation classification off. A
full screen of 1600x900 costs 0.98 s. Heavier models were tested and lost:
`medium` is twelve times slower and does not read one letter better, and the server models are both
worse and ten times slower.

A known box is read with recognition alone: measured 29 July 2026 over 22 boxes, 1.86 ms on the NPU
against 6.02 ms on the CPU, with the same result on every box. That route needs a fixed input shape
and deliberately does not live in this file.
"""
import ctypes
from collections.abc import Sequence

import numpy
from PIL import Image, ImageGrab
from rapidocr import EngineType, LangDet, LangRec, ModelType, OCRVersion, RapidOCR
from rapidocr.utils.output import RapidOCROutput

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

_instance: RapidOCR | None = None
# One line of text: x, y, width, height in the points of its image, and what it says.
Line = tuple[int, int, int, int, str]


def _engine() -> RapidOCR:
    """The engine is only built on first use; loading costs about a second."""
    global _instance
    if _instance is None:
        _instance = RapidOCR(params=_CHOICE)
    return _instance


def _box(points: Sequence[Sequence[float]]) -> tuple[int, int, int, int]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))


def read_image(screenshot: Image.Image) -> list[Line]:
    """Returns a list of (x, y, width, height, text) in the points of this image."""
    result = _engine()(numpy.array(screenshot.convert('RGB')),
                          use_det=True, use_cls=False, use_rec=True)
    # Detection with recognition always answers in this form, empty boxes when nothing is found
    # (measured 3 October 2026, rapidocr 3.9.2); anything else is a rapidocr that changed.
    if not isinstance(result, RapidOCROutput):
        raise TypeError(f'rapidocr answered detection plus recognition with {type(result).__name__}')
    if result.boxes is None or result.txts is None:
        return []
    lines = [(*_box(crop), text.strip())
              for crop, text in zip(result.boxes, result.txts, strict=True)]
    lines.sort(key=lambda r: (r[1], r[0]))
    return lines


def read_screen() -> list[Line]:
    """Returns a list of (x, y, width, height, text) in screen points.

    This grabs the whole screen and therefore the foreground window. For the game,
    `tools\\windowgrab.py` plus `read_image` is the better route: it does not need the foreground.
    DPI aware first, so the screen comes in physical pixels.
    """
    ctypes.windll.user32.SetProcessDPIAware()
    return read_image(ImageGrab.grab())


if __name__ == '__main__':
    for x, y, b, h, text in read_screen():
        print(f'{int(x):5d},{int(y):5d}  {int(b):3d}x{int(h):<3d}  {text}')
