"""OpenClaw monitor: polls WSL lcd-probe for agent/task status and alerts."""
import json
import subprocess
import threading
import time

from ..util.constants import (
    WSL_CMD, CREATE_NO_WINDOW, TERMINAL_OK, TERMINAL_BAD, RUNTIME_TAG, SEEN_FILE,
)
from ..supervisor import ConnectionSupervisor


class OpenClawMonitor:
    def __init__(self):
        self._lock = threading.Lock()
        self._poll_lock = threading.Lock()   # prevents concurrent polls
        self.sup = ConnectionSupervisor("oc", stale_threshold=1, offline_threshold=2)
        self.online = False
        self.running = self.ok = self.fail = self.total = 0
        self.last_task = ""
        self.last_task_status = ""
        self.last_poll_ok = 0.0
        self.alerts = []
        self.last_event = None
        self._seen = set()
        self._baselined = False
        self.active_agents = {}
        self.codex_seen = False
        self.codex_active = False
        self.codex_mtime = 0.0
        self.codex_last = ""
        # Model in use + quota (from the lcd-probe M|/U| lines)
        self.model = ""
        self.usage_provider = ""
        self.usage_balance = ""
        self.usage_window_label = ""
        self.usage_window_pct = ""
        self._load_seen()

    def _load_seen(self):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                self._seen = set(json.load(f).get("seen", []))
        except Exception:
            self._seen = set()

    def _save_seen(self):
        try:
            with open(SEEN_FILE, "w", encoding="utf-8") as f:
                json.dump({"seen": list(self._seen)[-500:]}, f)
        except Exception:
            pass

    def poll(self):
        """Read the compact lcd-probe lines and raise alerts for finished work.

        Protected by _poll_lock to prevent concurrent runs. Validates returncode
        before marking online. Uses a 30-second timeout (down from 180).
        """
        if not self._poll_lock.acquire(blocking=False):
            return   # another poll is already running
        try:
            self._poll_inner()
        finally:
            self._poll_lock.release()

    def _poll_inner(self):
        start = time.monotonic()
        try:
            r = subprocess.run(WSL_CMD, capture_output=True, timeout=30,
                               creationflags=CREATE_NO_WINDOW)
            elapsed = time.monotonic() - start
            if r.returncode != 0:
                err = r.stderr.decode("utf-8", errors="replace")[:120] if r.stderr else f"exit {r.returncode}"
                self.sup.mark_failure(err)
                with self._lock:
                    self.online = False
                return
            out = r.stdout.decode("utf-8", errors="replace")
            if not out.strip():
                # The probe process answered but produced no data: the link is
                # broken, not healthy. Previously this marked STALE and then
                # the same poll fell through to mark_online() at the bottom,
                # so the two halves of the state disagreed. Fail here, let the
                # supervisor (the single source of truth) decide the state.
                self.sup.mark_failure("empty output")
                with self._lock:
                    self.online = self.sup.is_online
                return
            now = time.time()
            new_alerts, new_events = [], []
            ok = fail = total = 0
            last_task = last_status = ""
            newest = -1
            active_agents = {}
            codex_mtime = 0.0
            codex_last = ""
            model = ""
            u_prov = u_bal = u_wlab = u_wpct = ""

            for line in out.splitlines():
                line = line.strip()
                if line.startswith("N|"):
                    try:
                        total = int(line[2:] or 0)
                    except ValueError:
                        pass
                elif line.startswith("R|"):
                    p = line.split("|", 2)
                    if len(p) >= 3:
                        a = p[2] or "?"
                        active_agents[a] = active_agents.get(a, 0) + 1
                elif line.startswith("T|"):
                    p = line.split("|", 6)
                    if len(p) < 7:
                        continue
                    _, tid, rt, st, agent, ended, label = p
                    if st in TERMINAL_OK:
                        ok += 1
                    elif st in TERMINAL_BAD:
                        fail += 1
                    try:
                        ended_i = int(ended or 0)
                    except ValueError:
                        ended_i = 0
                    if ended_i > newest:
                        newest, last_task, last_status = ended_i, label, st
                    fresh = bool(tid) and tid not in self._seen
                    if tid:
                        self._seen.add(tid)
                    if fresh and self._baselined:
                        good = st in TERMINAL_OK
                        kind = "ok" if good else "fail"
                        tag = RUNTIME_TAG.get(rt, (rt or "task").upper())
                        text = f"{tag} {'OK' if good else st.upper()}: {label}"
                        new_alerts.append((now, kind, text))
                        if rt == "subagent" or not good:
                            new_events.append((now, kind, text))
                elif line.startswith("M|"):
                    model = line[2:].strip()
                elif line.startswith("U|"):
                    p = line.split("|", 4)
                    u_prov = p[1].strip() if len(p) > 1 else ""
                    u_bal = p[2].strip() if len(p) > 2 else ""
                    u_wlab = p[3].strip() if len(p) > 3 else ""
                    u_wpct = p[4].strip() if len(p) > 4 else ""
                elif line.startswith("C2|"):
                    p = line.split("|", 2)
                    try:
                        codex_mtime = max(codex_mtime, float(p[1] or 0))
                    except (ValueError, IndexError):
                        pass
                    if len(p) >= 3:
                        codex_last = p[2]
                elif line.startswith("C|"):
                    try:
                        codex_mtime = max(codex_mtime, float(line[2:] or 0))
                    except ValueError:
                        pass

            self._save_seen()

            with self._lock:
                self.sup.mark_online(latency=elapsed)
                self.online = self.sup.is_online
                self.running = sum(active_agents.values())
                self.ok, self.fail, self.total = ok, fail, total
                self.last_task, self.last_task_status = last_task, last_status
                self.last_poll_ok = now
                self.active_agents = active_agents
                self.codex_seen = codex_mtime > 0
                self.codex_mtime = codex_mtime
                self.codex_last = codex_last
                self.codex_active = bool(codex_mtime) and (now - codex_mtime) < 180
                self.model = model
                self.usage_provider = u_prov
                self.usage_balance = u_bal
                self.usage_window_label = u_wlab
                self.usage_window_pct = u_wpct
                if not self._baselined:
                    self._baselined = True
                    self.alerts.append((now, "info", "OpenClaw link up"))
                for ts, kind, text in new_alerts:
                    self.alerts.append((ts, kind, text))
                for ts, kind, text in new_events:
                    self.last_event = {"ts": ts, "kind": kind, "label": text}
                if len(self.alerts) > 40:
                    self.alerts = self.alerts[-40:]
        except Exception as exc:
            with self._lock:
                self.sup.mark_failure(str(exc)[:120])
                self.online = self.sup.is_online

    def health(self):
        """Return supervisor snapshot for diagnostics."""
        return self.sup.snapshot()

    def snapshot(self):
        with self._lock:
            base = {
                "online": self.online, "running": self.running,
                "ok": self.ok, "fail": self.fail, "total": self.total,
                "last_task": self.last_task,
                "last_task_status": self.last_task_status,
                "last_poll_ok": self.last_poll_ok,
                "last_event": dict(self.last_event) if self.last_event else None,
                "alerts": list(self.alerts),
                "active_agents": dict(self.active_agents),
                "codex_seen": self.codex_seen,
                "codex_active": self.codex_active,
                "codex_mtime": self.codex_mtime,
                "codex_last": self.codex_last,
                "model": self.model,
                "usage_provider": self.usage_provider,
                "usage_balance": self.usage_balance,
                "usage_window_label": self.usage_window_label,
                "usage_window_pct": self.usage_window_pct,
            }
            base.update(self.sup.snapshot())
            return base
