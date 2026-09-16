"""ConnectionSupervisor — ONLINE → STALE → OFFLINE with auto-reconnect and backoff.

Each monitored component (LCD, RGB, OpenClaw, VPS) gets its own supervisor
that tracks health state and triggers reconnection attempts with exponential
backoff. No more silent deaths or instant offline flips from a single timeout.

State machine:
    CONNECTING → ONLINE → STALE → OFFLINE → (backoff) → CONNECTING

A single transient failure moves ONLINE → STALE. Two consecutive failures
move STALE → OFFLINE. From OFFLINE, reconnection is attempted with
exponential backoff (1, 2, 4, 8, 15, 30 s). A single success from any
state snaps back to ONLINE.
"""
import time

# ─── states ──────────────────────────────────────────────────────────
CONNECTING = "connecting"
ONLINE     = "online"
STALE      = "stale"
OFFLINE    = "offline"

ALL_STATES = (CONNECTING, ONLINE, STALE, OFFLINE)

# ─── backoff schedule (seconds) ─────────────────────────────────────
_BACKOFF = [1, 2, 4, 8, 15, 30]


class ConnectionSupervisor:
    """Health tracker for one monitored component.

    Usage:
        sup = ConnectionSupervisor("lcd")
        sup.mark_connecting()
        # ... try to connect ...
        if connected:
            sup.mark_online()
        else:
            sup.mark_failure()

        # In the main loop:
        if sup.should_reconnect(now):
            sup.mark_connecting()
            # ... try to connect again ...
    """

    def __init__(self, name, stale_threshold=1, offline_threshold=2):
        """Args:
            name: component label for diagnostics ("lcd", "rgb", "oc", "vps")
            stale_threshold: failures before ONLINE → STALE
            offline_threshold: consecutive failures before STALE → OFFLINE
        """
        self.name = name
        self.state = OFFLINE
        self._fail_count = 0
        self._stale_threshold = stale_threshold
        self._offline_threshold = offline_threshold
        self._backoff_idx = 0
        self._last_ok = 0.0
        self._last_attempt = 0.0
        self._state_changed_at = 0.0
        self._latency = 0.0
        self._diagnostics = {}   # free-form dict for diagnostics page

    # ─── state transitions ──────────────────────────────────────────
    def mark_connecting(self):
        """We are about to attempt a connection."""
        self.state = CONNECTING
        self._state_changed_at = time.time()

    def mark_online(self, latency=0.0):
        """Connection succeeded — snap to ONLINE from any state."""
        now = time.time()
        self.state = ONLINE
        self._fail_count = 0
        self._backoff_idx = 0
        self._last_ok = now
        self._latency = latency
        self._state_changed_at = now
        self._diagnostics["last_ok"] = now

    def mark_failure(self, detail=""):
        """Connection failed or health check failed.

        ONLINE → STALE after stale_threshold failures.
        STALE → OFFLINE after offline_threshold consecutive failures.
        CONNECTING → OFFLINE immediately (we just tried and failed).
        """
        self._fail_count += 1
        if self.state == CONNECTING:
            self.state = OFFLINE
        elif self.state == ONLINE:
            if self._fail_count >= self._stale_threshold:
                self.state = STALE
                self._state_changed_at = time.time()
        elif self.state == STALE:
            if self._fail_count >= self._offline_threshold:
                self.state = OFFLINE
                self._state_changed_at = time.time()
        if detail:
            self._diagnostics["last_error"] = detail
            self._diagnostics["last_error_ts"] = time.time()

    def mark_stale(self, detail=""):
        """Externally force STALE (e.g. partial data from OpenClaw)."""
        if self.state == ONLINE:
            self.state = STALE
            self._state_changed_at = time.time()
            self._fail_count = 1
        if detail:
            self._diagnostics["last_warn"] = detail
            self._diagnostics["last_warn_ts"] = time.time()

    # ─── queries ─────────────────────────────────────────────────────
    @property
    def is_online(self):
        return self.state == ONLINE

    @property
    def is_stale(self):
        return self.state == STALE

    @property
    def is_offline(self):
        return self.state == OFFLINE

    @property
    def is_connected(self):
        """True if the component is usable (ONLINE or STALE)."""
        return self.state in (ONLINE, STALE)

    @property
    def fail_count(self):
        return self._fail_count

    @property
    def last_ok_age(self):
        """Seconds since last successful connection."""
        if self._last_ok == 0:
            return -1
        return time.time() - self._last_ok

    @property
    def latency(self):
        return self._latency

    def should_reconnect(self, now=None):
        """True if enough backoff time has elapsed to attempt reconnection."""
        if self.state != OFFLINE:
            return False
        now = now or time.time()
        delay = _BACKOFF[min(self._backoff_idx, len(_BACKOFF) - 1)]
        return now - self._last_attempt >= delay

    def next_backoff(self):
        """Advance the backoff counter (call after a failed reconnect attempt)."""
        self._backoff_idx = min(self._backoff_idx + 1, len(_BACKOFF) - 1)
        self._last_attempt = time.time()

    def reset_backoff(self):
        """Reset backoff after a successful connection."""
        self._backoff_idx = 0

    def age_str(self):
        """Human-readable age since last state change."""
        d = time.time() - self._state_changed_at
        if d < 60:
            return f"{int(d)}s"
        if d < 3600:
            return f"{int(d // 60)}m"
        return f"{int(d // 3600)}h"

    def snapshot(self):
        """Return a dict for diagnostics / page rendering."""
        return {
            "name": self.name,
            "state": self.state,
            "fail_count": self._fail_count,
            "last_ok_age": self.last_ok_age,
            "latency": self._latency,
            "state_age": self.age_str(),
            "backoff": _BACKOFF[min(self._backoff_idx, len(_BACKOFF) - 1)],
            **self._diagnostics,
        }
