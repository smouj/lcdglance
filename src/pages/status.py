"""StatusPage — B3 scouter: power level + CPU temp + gateway + active agents."""
from .base import Page
from ..util.text import clip, age_str


class StatusPage(Page):
    """B3 scouter: power level + CPU temp + gateway + active agents.

    Shows for 5 seconds then returns to the current page (B3 timeout).
    """
    name = "Status"

    def render(self, gfx, d, st, oc, dl, ctx):
        s = oc.snapshot()
        gfx.frame(d, "SCOUTER", f"PL {ctx.get('load', 0):,}")
        y = 13
        for label, pct in (("CPU", st.get("cpu", 0)),
                           ("RAM", st.get("mem", 0)),
                           ("DSK", st.get("disk", 0))):
            gfx.text(d, (3, y), f"{label} {pct:5.1f}%", small=True)
            gfx.hbar(d, 62, y + 1, 70, 8, pct / 100.0)
            y += 10

        temps = st.get("temps", [])
        temp_str = ""
        if temps:
            for name, val in temps:
                low = name.lower()
                if "core" in low or "cpu" in low or "package" in low or "tctl" in low:
                    temp_str = f" {val:.0f}" + chr(176) + "C"
                    break
            if not temp_str:
                temp_str = f" {temps[0][1]:.0f}" + chr(176) + "C"
        gfx.text(d, (135, 13), clip(temp_str, 8), small=True)

        gw_status = "GW UP" if s.get("online") else "GW DOWN"
        if s.get("online"):
            d.ellipse([148, y + 2, 154, y + 8], fill=255)
        else:
            d.ellipse([148, y + 2, 154, y + 8], outline=255)

        agents_count = sum((s.get("active_agents") or {}).values())
        agent_str = f"AG{agents_count}" if agents_count else "AG0"
        gw_str = f"{gw_status} {agent_str}"
        gfx.text(d, (3, y), clip(gw_str, 20), small=True)
        y += 10

        if s.get("codex_active"):
            codex = "CODEX active"
        elif s.get("codex_mtime"):
            codex = f"CODEX {age_str(s['codex_mtime'])} ago"
        else:
            codex = "CODEX n/a"
        gfx.text(d, (3, y), clip(codex, 25), small=True)
