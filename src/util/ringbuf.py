"""Thread-safe ring buffer for sparkline and metric history."""
import threading


class RingBuffer:
    """Fixed-size append-only buffer with time-based sampling.

    Usage::

        cpu_hist = RingBuffer(maxlen=120, interval=1.0)
        # in the loop:
        cpu_hist.tick(time.time(), cpu_percent)
        # in a page render:
        values = cpu_hist.values
    """

    def __init__(self, maxlen=120, interval=1.0):
        self.maxlen = maxlen
        self.interval = interval
        self.data = []
        self._last = 0.0
        self._lock = threading.Lock()

    def tick(self, now, value):
        """Append *value* if enough time has elapsed since the last sample."""
        if now - self._last < self.interval:
            return
        with self._lock:
            self.data.append(value)
            if len(self.data) > self.maxlen:
                del self.data[0]
            self._last = now

    def force(self, value):
        """Append a value regardless of interval (for immediate seeding)."""
        with self._lock:
            self.data.append(value)
            if len(self.data) > self.maxlen:
                del self.data[0]
            self._last = 0.0  # next tick will record too

    @property
    def values(self):
        with self._lock:
            return list(self.data)

    @property
    def last(self):
        with self._lock:
            return self.data[-1] if self.data else None

    def clear(self):
        with self._lock:
            self.data.clear()

    def __len__(self):
        with self._lock:
            return len(self.data)
