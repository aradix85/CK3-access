"""Reads one known box on the NPU. Two to three times faster than the same route on the CPU.

When to use this: when the widget tree already knows where a box is and you read many of them in a
row. `tools\\ocr.py` does the same in about 4 ms; this route does an ordinary box in 2.1 ms. For a
single box that difference is nothing, for a whole window full of boxes it adds up.

The same model as `ocr.py` - PP-OCRv6 `tiny` - so that the two routes cannot drift apart. The
difference is in the execution: the NPU only accepts models with a fixed input shape. The model is
therefore converted to OpenVINO's intermediate form and compiled per width bucket; that happens by
itself and is kept on disk.

Why width buckets and not one fixed width, measured 29 July 2026: a box is scaled to height 48, and
`Rally Points` at 512x21 then becomes 1170 points wide. Squeeze that into 320 and it reads `al is`;
into 640, `Rally oints`; at 1280 it reads correctly. One fixed width of 320 therefore cost exactly
the wide box, and those are not rare - an event line is wide. The cost scales with the width: 2.12
ms at 320, 4.05 at 640, 5.14 at 1280, so the narrowest bucket that fits is the right one. Compiling
costs 0.7 s per new bucket and lands in the model cache afterwards.

Do not quantise for the NPU: measured, int8 costs three errors over 35 boxes there and buys almost
no time. On the CPU int8 is worth it (35 ms down to 7 ms).
"""
import os

import numpy
import openvino
from PIL import Image

HEIGHT = 48
BOX = 320  # the width runs in multiples of this

_HERE = os.path.dirname(os.path.abspath(__file__))
_OWN = os.path.join(_HERE, 'ocr_modellen')
_IR = os.path.join(_OWN, 'v6_tiny_rec.xml')
_CHARS = os.path.join(_OWN, 'v6_tiny_rec_tekens.txt')
_CACHE = os.path.join(_OWN, 'ov_cache')

_core = None
_device = 'NPU'
_requests = {}
_list = None


def _source_model():
    """The onnx file that rapidocr fetched itself."""
    import rapidocr
    path = os.path.join(os.path.dirname(rapidocr.__file__), 'models', 'PP-OCRv6_rec_tiny.onnx')
    if not os.path.exists(path):
        raise FileNotFoundError(
            'PP-OCRv6_rec_tiny.onnx is not there yet. Run ocr.warm_up() first; '
            'rapidocr will fetch the model then.')
    return path


def _decode():
    """One-off: convert the onnx and pull out the character list.

    The width stays free here; it is only fixed at compile time, because every width bucket has its
    own compiled model.
    """
    import onnx
    source = _source_model()
    chars = None
    for attribute in onnx.load(source).metadata_props:
        if attribute.key == 'character':
            chars = attribute.value
    if chars is None:
        raise ValueError('no character list in the metadata of %s' % source)
    with open(_CHARS, 'w', encoding='utf-8') as file:
        file.write(chars)
    openvino.save_model(openvino.convert_model(source), _IR)


def _charset(output_width):
    """The list must be exactly as long as the model has channels, or everything shifts."""
    raw = open(_CHARS, encoding='utf-8').read().split('\n')
    for candidate in (raw, ['blank'] + raw, ['blank'] + raw + [' ']):
        if len(candidate) == output_width:
            return candidate
    raise ValueError('character list of %d does not fit %d model channels'
                     % (len(raw), output_width))


def _request_for(width):
    """The compiled model for this width bucket; compiling happens once per bucket."""
    global _list
    if width not in _requests:
        model = _core.read_model(_IR)
        model.reshape({model.inputs[0]: openvino.PartialShape([1, 3, HEIGHT, width])})
        compiled = _core.compile_model(model, _device)
        _requests[width] = compiled.create_infer_request()
        _list = _charset(compiled.output(0).shape[-1])
    return _requests[width]


def warm_up(device='NPU'):
    """Compiling costs a few seconds; after that it sits in the model cache."""
    global _core, _device, _requests
    if not (os.path.exists(_IR) and os.path.exists(_CHARS)):
        _decode()
    _core = openvino.Core()
    os.makedirs(_CACHE, exist_ok=True)
    _core.set_property({'CACHE_DIR': _CACHE})
    _device = device
    _requests = {}
    _request_for(BOX)


def _preprocess(cut, width):
    """The way PaddleOCR does it: scale to height 48, then pad after normalising.

    Padding before normalising makes the padding black instead of neutral, and then it reads
    nonsense - that cost 11 of 13 boxes before anyone noticed.
    """
    scale = HEIGHT / cut.height
    box_width = max(1, min(width, int(numpy.ceil(cut.width * scale))))
    arr = numpy.asarray(cut.resize((box_width, HEIGHT), Image.BILINEAR), dtype=numpy.float32) / 255.0
    arr = ((arr - 0.5) / 0.5).transpose(2, 0, 1)
    canvas = numpy.zeros((3, HEIGHT, width), dtype=numpy.float32)
    canvas[:, :, :box_width] = arr
    return canvas[None]


def read_box_conf(screenshot, x, y, width, height, margin=0):
    """Returns (text, confidence) of one box.

    The confidence is the mean of the highest probability per accepted character. It comes free
    from the same output and separates "hard to read" from "this is really there": a box that
    yields the pixels of another window reads itself wrong with high confidence, while a hard box
    comes out below 0.7. Use it as a filter, not as truth.

    `margin` is 0 and that is measured, 29 July 2026, over 40 boxes that the screen reader
    confirmed independently: 36 correct at margin 0, 34 at 2, 4 and 6, 27 at 8, 21 at 10. A margin
    pulls in the neighbouring character - at margin 6 a `6` was read as `16`. The widget rectangle
    is the text frame; nothing needs to be added.
    """
    if _core is None:
        warm_up()
    cut = screenshot.convert('RGB').crop((max(0, x - margin), max(0, y - margin),
                                      x + width + margin, y + height + margin))
    scaled = cut.width * HEIGHT / cut.height
    box = BOX * int(numpy.ceil(scaled / BOX))
    output = list(_request_for(box).infer([_preprocess(cut, box)]).values())[0]
    best = output[0].argmax(axis=-1)
    scores = output[0].max(axis=-1)
    text, confidences, previous = [], [], -1
    for i, score in zip(best, scores):
        if i != previous and i != 0:
            text.append(_list[i])
            confidences.append(float(score))
        previous = i
    confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return ''.join(text).strip(), confidence


def read_box(screenshot, x, y, width, height, margin=0):
    """Text only. Same call as `ocr.read_box`."""
    return read_box_conf(screenshot, x, y, width, height, margin)[0]
