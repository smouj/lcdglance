"""System stats collector with tiered caching.

psutil.process_iter() costs ~300 ms, so the two parts of the stats
are cached separately: cheap counters refresh every second, the
process scan only every few seconds via an async thread.
"""
import threading
import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from ..util.constants import SKIP_PROCS
from ..util.ringbuf import RingBuffer

# ─── network history ──────────────────────────────────────────────
_net = {"sent": 0.0, "recv": 0.0, "t": 0.0, "up": 0.0, "dn": 0.0}

# Ring buffers for sparkline history (separate from the module-level NET_HIST
# that existed in v7 for backward compat with preview.py)
NET_HIST_BUF = RingBuffer(maxlen=120, interval=1.0)
CPU_HIST_BUF = RingBuffer(maxlen=120, interval=1.0)
RAM_HIST_BUF = RingBuffer(maxlen=120, interval=1.0)
DISK_HIST_BUF = RingBuffer(maxlen=120, interval=5.0)

# Legacy flat list for preview.py compat
NET_HIST = []

# ─── tiered caching ────────────────────────────────────────────────
STATS_TTL = 1.0
TOP_TTL = 3.0
_base_cache = {"t": 0.0, "data": {}}
_top_cache = {"t": 0.0, "data": [], "busy": False}


def _collect_base(st):
    """Collect cheap counters: CPU, RAM, disk, network, temps, uptime."""
    st["cpu"] = psutil.cpu_percent(interval=None)
    f = psutil.cpu_freq()
    st["cpu_freq"] = f.current if f else 0
    m = psutil.virtual_memory()
    st["mem"] = m.percent
    st["mem_used"] = m.used / (1024 ** 3)
    st["mem_total"] = m.total / (1024 ** 3)
    d = psutil.disk_usage("C:\\")
    st["disk"] = d.percent
    st["disk_used"] = d.used / (1024 ** 3)
    st["disk_total"] = d.total / (1024 ** 3)
    n = psutil.net_io_counters()
    now = time.time()
    sent = n.bytes_sent / (1024 ** 2)
    recv = n.bytes_recv / (1024 ** 2)
    dt = now - _net["t"]
    if dt > 0 and _net["t"] > 0:
        _net["up"] = (sent - _net["sent"]) / dt
        _net["dn"] = (recv - _net["recv"]) / dt
    _net.update(sent=sent, recv=recv, t=now)
    st["net_up"], st["net_dn"] = _net["up"], _net["dn"]
    st["net_sent"], st["net_recv"] = sent, recv
    # Feed ring buffers
    NET_HIST_BUF.tick(now, _net["dn"] * 1024)
    CPU_HIST_BUF.tick(now, st["cpu"])
    RAM_HIST_BUF.tick(now, st["mem"])
    DISK_HIST_BUF.tick(now, st["disk"])
    # Legacy compat
    NET_HIST.append(_net["dn"] * 1024)
    if len(NET_HIST) > 60:
        del NET_HIST[:-60]
    try:
        temps = psutil.sensors_temperatures()
        tl = []
        if temps:
            for name, entries in temps.items():
                for e in entries:
                    if e.current is not None:
                        tl.append((e.label or name, e.current))
        st["temps"] = tl
    except Exception:
        st["temps"] = []
    st["procs"] = len(psutil.pids())
    st["uptime"] = time.time() - psutil.boot_time()
    return st


def _collect_top():
    """Collect top-3 processes by CPU (expensive, runs on a thread)."""
    procs = []
    for p in psutil.process_iter(["name", "cpu_percent", "memory_percent"]):
        try:
            i = p.info
            nm = (i.get("name") or "").strip()
            if nm.lower() in SKIP_PROCS or i["cpu_percent"] is None:
                continue
            procs.append(i)
        except Exception:
            continue
    procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
    return procs[:3]


def _refresh_top_async():
    if _top_cache["busy"]:
        return
    _top_cache["busy"] = True

    def work():
        try:
            _top_cache["data"] = _collect_top()
            _top_cache["t"] = time.time()
        except Exception:
            pass
        finally:
            _top_cache["busy"] = False

    threading.Thread(target=work, daemon=True).start()


def get_system_stats():
    """Return a dict of current system stats (cached, thread-safe)."""
    if not HAS_PSUTIL:
        return {}
    now = time.time()
    st = _base_cache["data"]
    try:
        if not st or now - _base_cache["t"] >= STATS_TTL:
            st = _collect_base(st)
            _base_cache.update(t=now, data=st)
        if now - _top_cache["t"] >= TOP_TTL:
            _refresh_top_async()
        st["top"] = _top_cache["data"]
    except Exception:
        pass
    return st
