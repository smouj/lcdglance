"""Download detector: shows the Download view only for genuine sustained downloads.

A file must keep growing inside a real download folder AND the network must
carry traffic, repeatedly, for several seconds. Browser caches and %TEMP% are
excluded so streaming video never triggers it.
"""
import os
import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from ..util.constants import (
    DL_DIRS, DL_HINTS, DL_MIN_GROWTH_MB, DL_MIN_NET_MB,
    DL_MIN_STREAK, DL_MIN_TOTAL_MB, DL_QUIET_STOP,
)


class DownloadDetector:
    def __init__(self):
        self.active = False
        self.name = ""
        self.speed = 0.0
        self.peak = 0.0
        self.total_mb = 0.0
        self.file = ""
        self.file_mb = 0.0
        self.started = 0.0
        self._last_rx = 0.0
        self._last_bytes = {}
        self._files = {}
        self._streak = 0
        self._quiet = 0
        self._name_t = 0.0
        self._name_cached = ""

    def _downloader_name(self):
        if not HAS_PSUTIL:
            return ""
        now = time.time()
        if now - self._name_t < 5.0:
            return self._name_cached
        best, best_rate = "", 0.0
        for p in psutil.process_iter(["pid", "name"]):
            try:
                nm = (p.info["name"] or "").lower()
                if not any(h in nm for h in DL_HINTS):
                    continue
                wr = p.io_counters().write_bytes
                prev = self._last_bytes.get(p.info["pid"])
                self._last_bytes[p.info["pid"]] = wr
                if prev is not None:
                    rate = (wr - prev) / (1024 ** 2)
                    if rate > best_rate:
                        best, best_rate = p.info["name"], rate
            except Exception:
                continue
        self._name_t = now
        self._name_cached = best
        return best

    def _fastest_growing(self):
        best = None
        for d in DL_DIRS:
            if not d or not os.path.isdir(d):
                continue
            try:
                for e in os.scandir(d):
                    if not e.is_file(follow_symlinks=False):
                        continue
                    try:
                        stt = e.stat()
                    except Exception:
                        continue
                    if time.time() - stt.st_mtime > 90:
                        continue
                    prev = self._files.get(e.path)
                    self._files[e.path] = stt.st_size
                    if prev is not None and stt.st_size > prev:
                        delta = (stt.st_size - prev) / (1024 ** 2)
                        if best is None or delta > best[2]:
                            best = (e.name, stt.st_size / (1024 ** 2), delta)
            except Exception:
                continue
        return best

    def poll(self, st):
        if not HAS_PSUTIL:
            return
        now = time.time()
        rx = st.get("net_recv", 0.0)
        rx_rate = (rx - self._last_rx) if self._last_rx else 0.0
        self._last_rx = rx

        if rx_rate < DL_MIN_NET_MB and not self.active:
            self._streak = 0
            self.total_mb = 0.0
            return

        found = self._fastest_growing()
        qualifies = (found is not None
                     and found[2] >= DL_MIN_GROWTH_MB
                     and rx_rate >= DL_MIN_NET_MB)

        if qualifies:
            self._quiet = 0
            self._streak += 1
            self.speed = rx_rate
            self.total_mb += found[2]
            self.file, self.file_mb = found[0], found[1]
            self.peak = max(self.peak, self.speed)
            if not self.active and self._streak >= DL_MIN_STREAK \
                    and self.total_mb >= DL_MIN_TOTAL_MB:
                self.active = True
                self.started = now
            if self.active:
                self.name = self._downloader_name() or self.name or found[0]
        else:
            self._streak = 0
            if self.active:
                self._quiet += 1
                if self._quiet > DL_QUIET_STOP:
                    self.active = False
                    self._quiet = 0
                    self.speed = 0.0
                    self.total_mb = 0.0
            else:
                self.total_mb = 0.0

    def snapshot(self):
        return {
            "active": self.active, "name": self.name,
            "speed": self.speed, "peak": self.peak,
            "total_mb": self.total_mb, "file": self.file,
            "file_mb": self.file_mb,
            "elapsed": (time.time() - self.started) if self.started else 0.0,
        }
