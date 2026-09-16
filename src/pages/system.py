"""SystemPage — CPU / RAM / disk with temps, usage, and sparklines.

Layout (160x43):
  Header: SYSTEM + uptime + clock
  Line 1: CPU 42% █████░░░░░  54C
  Line 2: RAM 68% ███████░░░  21.7/32G
  Line 3: DSK 71% ███████░░░  682G free
  Line 4: LOAD sparkline ▁▂▃▂▄▆█▅▃▂▁▂▃▂
"""
from .base import Page
from ..util.text import clip, fmt_uptime, fmt_bytes


def _best_temp(temps, default="--"):
    """Pick the best temperature reading (prefer 'Core' or first CPU temp)."""
    if not temps:
        return default
    for label, value in temps:
        low = label.lower()
        if "core" in low or "cpu" in low or "package" in low:
            return f"{value:.0f}C"
    return f"{temps[0][1]:.0f}C"


class SystemPage(Page):
    name = "System"

    def render(self, gfx, d, st, oc, dl, ctx):
        gfx.frame(d, "SYSTEM", fmt_uptime(st.get("uptime", 0)))
        y = 13
        hist_bufs = ctx.get("hist_bufs", {})
        temps = st.get("temps", [])

        # CPU line: percentage + bar + temp
        cpu_pct = st.get("cpu", 0)
        cpu_temp = _best_temp(temps)
        gfx.text(d, (3, y), f"CPU {cpu_pct:3.0f}%", small=True)
        gfx.hbar(d, 50, y + 1, 60, 8, cpu_pct / 100.0)
        buf = hist_bufs.get("cpu")
        if buf and len(buf) >= 3:
            gfx.sparkline(d, 50, y + 1, 60, 8, buf)
        gfx.text(d, (115, y), cpu_temp, small=True)
        y += 10

        # RAM line: percentage + bar + used/total
        ram_pct = st.get("mem", 0)
        ram_used = st.get("mem_used", 0)
        ram_total = st.get("mem_total", 0)
        ram_detail = f"{fmt_bytes(ram_used)}/{fmt_bytes(ram_total)}" if ram_total else ""
        gfx.text(d, (3, y), f"RAM {ram_pct:3.0f}%", small=True)
        gfx.hbar(d, 50, y + 1, 60, 8, ram_pct / 100.0)
        buf = hist_bufs.get("ram")
        if buf and len(buf) >= 3:
            gfx.sparkline(d, 50, y + 1, 60, 8, buf)
        gfx.text(d, (115, y), clip(ram_detail, 16), small=True)
        y += 10

        # Disk line: percentage + bar + free space
        disk_pct = st.get("disk", 0)
        disk_free = fmt_bytes(st.get("disk_total", 0) - st.get("disk_used", 0))
        gfx.text(d, (3, y), f"DSK {disk_pct:3.0f}%", small=True)
        gfx.hbar(d, 50, y + 1, 60, 8, disk_pct / 100.0)
        buf = hist_bufs.get("disk")
        if buf and len(buf) >= 3:
            gfx.sparkline(d, 50, y + 1, 60, 8, buf)
        gfx.text(d, (115, y), f"{disk_free} free", small=True)
        y += 10

        # Load sparkline
        buf = hist_bufs.get("cpu")
        if buf and len(buf) >= 3:
            gfx.text(d, (3, y), "LOAD", small=True)
            gfx.sparkline(d, 30, y + 1, 125, 8, buf)
