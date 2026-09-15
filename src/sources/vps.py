"""VPS monitor: polls a remote server via SSH for CPU, RAM, disk, uptime, and top processes."""
import json
import os
import subprocess
import threading
import time

from ..util.constants import VPS_CONFIG_FILE, CREATE_NO_WINDOW


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
        remote = (
            "cat /proc/loadavg; echo '---'; "
            "free -m | head -2; echo '---'; "
            "df -h / | tail -1; echo '---'; "
            "cat /proc/uptime; echo '---'; "
            "ps -eo %mem,%cpu,comm --sort=-%cpu | head -4"
        )
        try:
            r = subprocess.run(cmd + [remote], capture_output=True, timeout=self.timeout + 3,
                               creationflags=CREATE_NO_WINDOW)
            if r.returncode != 0:
                raise RuntimeError(f"ssh exit {r.returncode}")
            out = r.stdout.decode("utf-8", errors="replace")
            sections = out.split("---")
            now = time.time()

            cpu = 0.0
            if len(sections) > 0:
                parts = sections[0].strip().split()
                if len(parts) >= 1:
                    try:
                        load1 = float(parts[0])
                        cores = os.cpu_count() or 1
                        cpu = min(100.0, load1 * 100.0 / max(cores, 1))
                    except ValueError:
                        pass

            ram = 0.0
            if len(sections) > 1:
                for line in sections[1].strip().splitlines():
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 3:
                            try:
                                used = int(parts[2])
                                total = int(parts[1])
                                ram = (used / total * 100) if total else 0.0
                            except (ValueError, IndexError):
                                pass
                        break

            disk = 0.0
            if len(sections) > 2:
                parts = sections[2].strip().split()
                if len(parts) >= 5:
                    try:
                        disk = float(parts[4].rstrip("%"))
                    except ValueError:
                        pass

            uptime_str = ""
            if len(sections) > 3:
                parts = sections[3].strip().split()
                if parts:
                    try:
                        up_s = float(parts[0])
                        d = int(up_s) // 86400
                        h = (int(up_s) % 86400) // 3600
                        m = (int(up_s) % 3600) // 60
                        if d > 0:
                            uptime_str = f"{d}d{h}h"
                        elif h > 0:
                            uptime_str = f"{h}h{m:02d}m"
                        else:
                            uptime_str = f"{m}m"
                    except ValueError:
                        uptime_str = sections[3].strip()[:12]

            top_procs = []
            if len(sections) > 4:
                for line in sections[4].strip().splitlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            cpu_p = float(parts[0])
                            name = parts[2].split("/")[-1][:14]
                            top_procs.append((name, cpu_p))
                        except (ValueError, IndexError):
                            pass
                top_procs = top_procs[:3]

            with self._lock:
                self.online = True
                self.cpu = cpu
                self.ram = ram
                self.disk = disk
                self.uptime = uptime_str
                self.top_procs = top_procs
                self._fail_count = 0
                self._last_poll = now

        except Exception:
            with self._lock:
                self._fail_count += 1
                if self._fail_count >= self.max_retries:
                    self.online = False
                self._last_poll = time.time()

    def snapshot(self):
        with self._lock:
            return {
                "enabled": self.enabled, "online": self.online,
                "cpu": self.cpu, "ram": self.ram, "disk": self.disk,
                "uptime": self.uptime, "top_procs": list(self.top_procs),
                "host": self.host, "fail_count": self._fail_count,
            }
