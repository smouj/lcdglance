"""TransitionEngine — smooth page transitions on a 160×43 mono LCD.

Supports:
  - slide: horizontal wipe left/right (3-4 frames)
  - wipe: vertical wipe down (3-4 frames)
  - dissolve: random noise fade (4-5 frames, slightly more expensive)

The engine blends two frame buffers to produce intermediate frames.
Transitions are brief (under 200ms at 24 FPS) and only triggered on
page changes — never between re-renders of the same page.
"""
import random
import time

from ..util.constants import W, H, BITMAP_SIZE


class TransitionEngine:
    """Manages page transition animations."""

    TYPES = ("slide", "wipe", "dissolve")
    FRAMES = {"slide": 4, "wipe": 4, "dissolve": 5}
    DURATION = 0.18  # total transition time in seconds

    def __init__(self):
        self.active = False
        self._type = "slide"
        self._start = 0.0
        self._frame_a = None  # bytes — old page
        self._frame_b = None  # bytes — new page
        self._noise = None    # pre-generated noise mask for dissolve

    def start(self, frame_a, frame_b, kind=None):
        """Begin a transition from *frame_a* to *frame_b*."""
        if frame_a is None or frame_b is None:
            return
        self.active = True
        self._type = kind or random.choice(self.TYPES)
        self._start = time.time()
        self._frame_a = frame_a
        self._frame_b = frame_b
        if self._type == "dissolve":
            self._noise = self._gen_noise()

    def render(self, now):
        """Return the blended frame bytes, or None if no transition is active."""
        if not self.active:
            return None
        elapsed = now - self._start
        total_frames = self.FRAMES.get(self._type, 4)
        progress = min(1.0, elapsed / self.DURATION)
        frame_idx = min(int(progress * total_frames), total_frames - 1)

        a = self._frame_a
        b = self._frame_b
        if a is None or b is None:
            self.active = False
            return None

        if self._type == "slide":
            result = self._blend_slide(a, b, frame_idx, total_frames)
        elif self._type == "wipe":
            result = self._blend_wipe(a, b, frame_idx, total_frames)
        else:
            result = self._blend_dissolve(a, b, frame_idx, total_frames)

        if frame_idx >= total_frames - 1:
            self.active = False

        return result

    def _blend_slide(self, a, b, frame, total):
        """Horizontal slide: old page slides out, new slides in."""
        offset = int((W * frame) / total)
        result = bytearray(BITMAP_SIZE)
        for y in range(H):
            row_start = y * W
            # New page fills from left
            if offset > 0:
                result[row_start:row_start + offset] = b[row_start:row_start + offset]
            # Old page shifts right
            remaining = W - offset
            if remaining > 0:
                result[row_start + offset:row_start + W] = a[row_start:row_start + remaining]
        return bytes(result)

    def _blend_wipe(self, a, b, frame, total):
        """Vertical wipe: new page reveals from top."""
        cutoff = int((H * (frame + 1)) / total)
        result = bytearray(a)
        row_size = W
        for y in range(min(cutoff, H)):
            src_start = y * W
            result[src_start:src_start + row_size] = b[src_start:src_start + row_size]
        return bytes(result)

    def _blend_dissolve(self, a, b, frame, total):
        """Noise dissolve: random pixels from the new page appear over the old."""
        if self._noise is None:
            self._noise = self._gen_noise()
        threshold = int(255 * (frame + 1) / total)
        result = bytearray(a)
        for i in range(BITMAP_SIZE):
            if self._noise[i] < threshold:
                result[i] = b[i]
        return bytes(result)

    @staticmethod
    def _gen_noise():
        """Pre-generate a random noise mask for dissolve transitions."""
        return bytes(random.randint(0, 255) for _ in range(BITMAP_SIZE))
