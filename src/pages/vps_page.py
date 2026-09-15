"""VPSPage — remote server SSH stats (if configured)."""
from .base import Page
from ..util.text import clip


class VPSPage(Page):
    name = "VPS"

    def render(self, gfx, d, st, oc, dl, ctx):
        vps = ctx.get("vps_snapshot", {})
        online = vps.get("online", False)
        host = vps.get("host", "?")
        if not online:
            if vps.get("fail_count", 0) >= 3:
                label = "VPS OFFLINE"
            else:
                label = "VPS CONNECT..."
            gfx.frame(d, "VPS", label)
            gfx.text(d, (3, 15), clip(host, 20), small=True)
            d.ellipse([148, 3, 155, 10], fill=255)
            d.ellipse([149, 4, 154, 9], fill=0)
            d.ellipse([150, 5, 153, 8], fill=255)
            retries = vps.get("fail_count", 0)
            gfx.text(d, (3, 25), f"retries {retries}", small=True)
            gfx.text(d, (3, 35), "SSH failed", small=True)
            return

        d.rectangle([148, 4, 155, 9], fill=255)
        gfx.frame(d, "VPS", vps.get("uptime", "?"))
        y = 13
        for label, pct in (("CPU", vps.get("cpu", 0)),
                           ("RAM", vps.get("ram", 0)),
                           ("DSK", vps.get("disk", 0))):
            gfx.text(d, (3, y), f"{label} {pct:5.1f}%", small=True)
            gfx.hbar(d, 62, y + 1, 95, 8, pct / 100.0)
            y += 10

        procs = vps.get("top_procs", [])
        if procs:
            for name, cpu_p in procs[:3]:
                n = clip(name, 14)
                gfx.text(d, (3, y), n, small=True)
                gfx.text(d, (90, y), f"{cpu_p:3.0f}%", small=True)
                y += 8
