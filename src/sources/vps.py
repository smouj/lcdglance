"""VPS monitor: polls a remote server via SSH for CPU, RAM, disk, uptime, and top processes."""
import json
import os
import subprocess
import threading
import time

from ..util.constants import VPS_CONFIG_FILE, CREATE_NO_WINDOW
from ..supervisor import ConnectionSupervisor


# ─── remote probe ───────────────────────────────────────────────────
# The section order is a contract with parse_remote_output(): every index
# below is positional, and reading the wrong one is silent (RAM stuck at
# 0 %, uptime showing the disk line).
REMOTE_PROBE = (
    "cat /proc/loadavg; echo '---'; "      # 0
    "nproc; echo '---'; "                  # 1
    "free -m | head -2; echo '---'; "      # 2
    "df -h / | tail -1; echo '---'; "      # 3
    "cat /proc/uptime; echo '---'; "       # 4
    "ps -eo %cpu,%mem,comm --sort=-%cpu | head -4"   # 5
)


def parse_remote_output(out, fallback_cores=None):
    """Parse REMOTE_PROBE output into a metrics dict.

    Sections: 0 loadavg | 1 nproc | 2 free -m | 3 df -h | 4 /proc/uptime | 5 ps
    """
    sections = out.split("---")

    def sec(i):
        return sections[i] if len(sections) > i else ""

    # 0 — load average
    load1 = 0.0
    parts = sec(0).strip().split()
    if parts:
        try:
            load1 = float(parts[0])
        except ValueError:
            load1 = 0.0

    # 1 — remote core count, then CPU % from load1 / cores
    cores = max(1, fallback_cores or os.cpu_count() or 1)
    try:
        cores = max(1, int(sec(1).strip()))
    except ValueError:
        pass
    cpu = min(100.0, load1 * 100.0 / max(cores, 1))

    # 2 — free -m: "Mem:  total  used  free ..."
    ram = 0.0
    for line in sec(2).strip().splitlines():
        if line.startswith("Mem:"):
            f = line.split()
            if len(f) >= 3:
                try:
                    total, used = int(f[1]), int(f[2])
                    ram = (used / total * 100) if total else 0.0
                except (ValueError, IndexError):
                    pass
            break

    # 3 — df -h / : Use% is the 5th field
    disk = 0.0
    f = sec(3).strip().split()
    if len(f) >= 5:
        try:
            disk = float(f[4].rstrip("%"))
        except ValueError:
            pass

    # 4 — /proc/uptime
    uptime_str = ""
    f = sec(4).strip().split()
    if f:
        try:
            up_s = float(f[0])
            d = int(up_s) // 86400
            h = (int(up_s) % 86400) // 3600
            mnt = (int(up_s) % 3600) // 60
            if d > 0:
                uptime_str = f"{d}d{h}h"
            elif h > 0:
                uptime_str = f"{h}h{mnt:02d}m"
            else:
                uptime_str = f"{mnt}m"
        except ValueError:
            uptime_str = sec(4).strip()[:12]

    # 5 — ps, skipping the header row
    top_procs = []
    for line in sec(5).strip().splitlines()[1:]:
        f = line.strip().split()
        if len(f) >= 3:
            try:
                top_procs.append((f[2].split("/")[-1][:14], float(f[0])))
            except (ValueError, IndexError):
                pass

    return {"cpu": cpu, "ram": ram, "disk": disk, "uptime": uptime_str,
            "cores": cores, "load1": load1, "top_procs": top_procs[:3]}


class VPSMonitor:
    """Polls a remote VPS via SSH for CPU, RAM, disk, uptime and top processes.

    Runs on its own thread with configurable poll interval. If SSH fails
    max_retries times in a row it enters OFFLINE mode and retries less frequently.
    When host is empty the monitor is disabled entirely and the VPS page is hidden.
    """

    def __init__(self):
        cfg = self._load_config()
        self.host = cfg.get("host", "")
        self.user = cfg.get("user", "root")
        self.key_path = cfg.get("key_path", "")
        self.poll_interval = cfg.get("poll_interval", 30)
        self.timeout = cfg.get("timeout", 5)
        self.max_retries = cfg.get("max_retries", 3)
        self.retry_interval = cfg.get("retry_interval", 60)
        self.enabled = bool(self.host)
        self._lock = threading.Lock()
        self.sup = ConnectionSupervisor("vps", stale_threshold=2, offline_threshold=3)
        self.online = False
        self.cpu = 0.0
        self.ram = 0.0
        self.disk = 0.0
        self.uptime = ""
        self.top_procs = []
        self._fail_count = 0
        self._last_poll = 0.0

    @staticmethod
    def _load_config():
        try:
            with open(VPS_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _ssh_cmd(self):
        cmd = ["ssh", "-o", f"ConnectTimeout={self.timeout}",
               "-o", "StrictHostKeyChecking=no",
               "-o", "BatchMode=yes",
               "-o", f"ServerAliveInterval={self.timeout}"]
        if self.key_path:
            cmd += ["-i", self.key_path]
        cmd.append(f"{self.user}@{self.host}")
        return cmd

    def poll(self):
        if not self.enabled:
            return
        if self._fail_count >= self.max_retries:
            now = time.time()
            if now - self._last_poll < self.retry_interval:
                return
        cmd = self._ssh_cmd()
        start = time.monotonic()
        try:
            r = subprocess.run(cmd + [REMOTE_PROBE], capture_output=True,
                               timeout=self.timeout + 3,
                               creationflags=CREATE_NO_WINDOW)
            if r.returncode != 0:
                raise RuntimeError(f"ssh exit {r.returncode}")
            out = r.stdout.decode("utf-8", errors="replace")
            now = time.time()
            elapsed = time.monotonic() - start
            m = parse_remote_output(out, fallback_cores=os.cpu_count())

            with self._lock:
                self.sup.mark_online(latency=elapsed)
                self.online = self.sup.is_online
                self.cpu = m["cpu"]
                self.ram = m["ram"]
                self.disk = m["disk"]
                self.uptime = m["uptime"]
                self.top_procs = m["top_procs"]
                self._fail_count = 0
                self._last_poll = now

        except Exception as exc:
            with self._lock:
                self.sup.mark_failure(str(exc)[:120])
                self._fail_count += 1
                if self._fail_count >= self.max_retries:
                    self.online = False
                self._last_poll = time.time()

    def health(self):
        """Return supervisor snapshot for diagnostics."""
        return self.sup.snapshot()

    def snapshot(self):
        with self._lock:
            base = {
                "enabled": self.enabled, "online": self.online,
                "cpu": self.cpu, "ram": self.ram, "disk": self.disk,
                "uptime": self.uptime, "top_procs": list(self.top_procs),
                "host": self.host, "fail_count": self._fail_count,
            }
            base.update(self.sup.snapshot())
            return base
