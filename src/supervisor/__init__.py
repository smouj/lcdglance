"""Connection supervisor — ONLINE → STALE → OFFLINE with auto-reconnect and backoff.

Every monitored component (LCD, RGB, OpenClaw, VPS) gets a ConnectionSupervisor
that tracks its health state and triggers reconnection attempts with exponential
backoff. No more silent deaths or instant offline flips from a single timeout.
"""
from .core import ConnectionSupervisor

__all__ = ["ConnectionSupervisor"]
