"""Mascot source data: build the three sources (PC, OpenClaw, Codex) and pick the active one."""
import time

from ..util.constants import MASCOT_COLOR, ACTIVE_COLOR, MASCOT_NAME
from ..util.text import age_str


def build_sources(st, oc, dl):
    """The three things the panel watches: the PC, OpenClaw and Codex."""
    s = oc.snapshot()
    agents = s.get("active_agents") or {}
    now = time.time()
    codex_age = (now - s["codex_mtime"]) if s.get("codex_mtime") else None
    return [
        {
            "key": "pc", "label": "PC", "online": True,
            "busy": st.get("cpu", 0) > 55,
            "detail": f"cpu {st.get('cpu', 0):.0f}% ram {st.get('mem', 0):.0f}%",
        },
        {
            "key": "openclaw", "label": "CLAW",
            "online": bool(s.get("online")),
            "busy": bool(agents) or s.get("running", 0) > 0,
            "detail": f"run {sum(agents.values()) or s.get('running', 0)} "
                      f"ok {s.get('ok', 0)}",
        },
        {
            "key": "codex", "label": "CODEX",
            "online": bool(s.get("codex_seen")),
            "busy": bool(s.get("codex_active")),
            "detail": (f"{age_str(s['codex_mtime'])} ago" if codex_age is not None
                       else "not found"),
        },
    ]


def pick_active(sources):
    """The source to feature: whichever agent is busy, else OpenClaw, else the PC."""
    for s in sources:
        if s["key"] != "pc" and s["busy"]:
            return s
    for s in sources:
        if s["key"] == "openclaw" and s["online"]:
            return s
    return sources[0]


def mood_for(st, oc, dl, src):
    """Expression for the featured mascot."""
    # Check for alerts first
    s = oc.snapshot()
    if (st.get("cpu", 0) > 95) or (st.get("mem", 0) > 95):
        return "alarm"
    ev = s.get("last_event")
    if ev and (time.time() - ev["ts"] < 8):
        return "happy" if ev["kind"] == "ok" else "alarm"
    if dl.active:
        return "focus"
    if src and src.get("busy"):
        return "watch"
    cpu, mem = st.get("cpu", 0), st.get("mem", 0)
    if cpu > 90 or mem > 90 or st.get("disk", 0) > 95:
        return "worried"
    return "idle"


def load_index(st, oc, dl):
    """A single 'load index' derived from real machine and agent activity."""
    s = oc.snapshot()
    pl = 1000.0
    pl += (st.get("cpu", 0) or 0) * 42
    pl += (st.get("mem", 0) or 0) * 26
    pl += (st.get("disk", 0) or 0) * 6
    pl += min((st.get("net_dn", 0) or 0) * 3, 2000)
    pl += sum((s.get("active_agents") or {}).values()) * 4500
    if dl.active:
        pl += min((dl.snapshot().get("speed") or 0) * 2500, 6000)
    return int(pl)


def is_busy(st, oc, dl, src):
    """True when the machine or the agents are busy enough to warrant a highlight."""
    s = oc.snapshot()
    return bool(
        (src and src.get("busy"))
        or dl.active
        or (st.get("cpu", 0) or 0) > 70
        or sum((s.get("active_agents") or {}).values()) > 0
    )
