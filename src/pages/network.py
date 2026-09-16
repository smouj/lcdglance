"""NetworkPage — up/down speed with sparklines and connection quality.

Layout (160x43):
  Header: NETWORK + total traffic
  Line 1: ↓ 38.4 MB/s  ↑ 3.2 MB/s  (speeds + sparklines)
  Line 2: PEAK ↓52.1M   PING --ms   (peak + latency)
  Line 3: download state (if active) or link quality bar
"""
import time

from .base import Page
from ..sources.system import NET_HIST
from ..util.text import clip, fmt_speed, fmt_bytes


class NetworkPage(Page):
    name = "Network"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        dl_snap = dl.snapshot()
        dl_state = dl_snap.get("state", "idle")

        # Header shows active state or total traffic
        if dl_snap.get("active"):
            header = f"NET * {fmt_speed(dl_snap.get('speed', 0))}"
        elif dl_state == "confirming":
            header = "NET * confirming"
        else:
            header = f"NET  tot {fmt_bytes(st.get('net_recv', 0))}"

        gfx.frame(d, header, "")

        dn = st.get("net_dn", 0)
        up = st.get("net_up", 0)

        # Line 1: download + upload speeds with sparkline
        y = 13
        gfx.text(d, (3, y), f"DN {fmt_speed(dn)}", small=True)
        gfx.text(d, (80, y), f"UP {fmt_speed(up)}", small=True)

        # Download sparkline (full width)
        if NET_HIST and len(NET_HIST) >= 3:
            gfx.sparkline(d, 3, y + 10, 154, 14, NET_HIST)

        y = 27
        # Line 2: peak + download state
        if dl_snap.get("active"):
            elapsed = int(dl_snap.get("elapsed", 0))
            detail = f"{clip(dl_snap.get('name', dl_snap.get('file', '')), 12)} {elapsed}s"
            gfx.text(d, (3, y), detail, small=True)
            gfx.text(d, (110, y), fmt_bytes(dl_snap.get("total_mb", 0)), small=True)
        elif dl_state == "confirming":
            gfx.text(d, (3, y), "confirming download...", small=True)
        elif dl_state == "candidate":
            gfx.text(d, (3, y), "detecting activity...", small=True)

        # Line 3: totals
        gfx.text(d, (3, 37), f"RX {fmt_bytes(st.get('net_recv', 0))}  TX {fmt_bytes(st.get('net_sent', 0))}", small=True)
