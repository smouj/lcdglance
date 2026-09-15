"""NetworkPage — up/down speed + sparkline from ring buffer."""
from .base import Page
from ..sources.system import NET_HIST


class NetworkPage(Page):
    name = "Network"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "NETWORK", f"tot {fmt_bytes(st.get('net_recv', 0))}")
        gfx.text(d, (3, 13), f"DN {fmt_speed(st.get('net_dn', 0))}", small=True)
        gfx.text(d, (3, 23), f"UP {fmt_speed(st.get('net_up', 0))}", small=True)
        gfx.text(d, (3, 33), f"sent {fmt_bytes(st.get('net_sent', 0))}", small=True)
        gfx.sparkline(d, 86, 14, 71, 28, NET_HIST)


from ..util.text import fmt_speed, fmt_bytes
