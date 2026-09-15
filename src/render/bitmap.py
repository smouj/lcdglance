"""Bitmap conversion between PIL images and the Logitech mono buffer format.

The G510 mono LCD uses ONE BYTE PER PIXEL (160×43 = 6880 bytes).
Never use img.convert("1") — Pillow applies Floyd-Steinberg dithering by
default, turning crisp text into speckled noise. Threshold with a LUT instead.
"""
from ..util.constants import W, H, BITMAP_SIZE, BIN_THRESHOLD, INVERT

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_MONO_LUT = None


def lut():
    """256-entry lookup table for binarisation (computed once)."""
    global _MONO_LUT
    if _MONO_LUT is None:
        if INVERT:
            _MONO_LUT = [0 if i >= BIN_THRESHOLD else 255 for i in range(256)]
        else:
            _MONO_LUT = [255 if i >= BIN_THRESHOLD else 0 for i in range(256)]
    return _MONO_LUT


def to_mono_bytes(img):
    """Convert a PIL image to the 6880-byte mono buffer for LogiLcdMonoSetBackground."""
    return img.convert("L").point(lut()).tobytes()


def mono_to_image(data):
    """Round-trip: mono buffer back to a PIL image (for preview/sheet generation)."""
    if not HAS_PIL:
        return None
    img = Image.new("L", (W, H), 0)
    px = img.load()
    i = 0
    for y in range(H):
        for x in range(W):
            if data[i]:
                px[x, y] = 255
            i += 1
    return img
