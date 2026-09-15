"""Text utilities: ASCII transliteration, clipping, formatting."""

import time

# ─── transliteration map for non-ASCII chars ──────────────────────
_TRANSLIT = {
    "·": "-", "•": "-", "—": "-", "–": "-", "…": "...", "°": "o",
    "á": "a", "à": "a", "ä": "a", "â": "a", "ã": "a",
    "é": "e", "è": "e", "ë": "e", "ê": "e",
    "í": "i", "ì": "i", "ï": "i", "î": "i",
    "ó": "o", "ò": "o", "ö": "o", "ô": "o", "õ": "o",
    "ú": "u", "ù": "u", "ü": "u", "û": "u",
    "ñ": "n", "ç": "c",
    "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N",
    "✓": "v", "✔": "v", "✗": "x", "✘": "x",
}


def ascii_text(text):
    """Replace non-ASCII chars with closest ASCII equivalent."""
    out = []
    for ch in str(text):
        if 32 <= ord(ch) <= 126:
            out.append(ch)
        else:
            out.append(_TRANSLIT.get(ch, "?"))
    return "".join(out).replace("\n", " ").replace("\r", " ")


def clip(text, n):
    """Truncate *text* to *n* chars, appending ~ if clipped."""
    t = ascii_text(text)
    return t if len(t) <= n else t[:n - 1] + "~"


def fmt_speed(mbps):
    """Format network speed in human-readable form."""
    if mbps >= 10:
        return f"{mbps:.0f}MB/s"
    if mbps >= 1:
        return f"{mbps:.1f}MB/s"
    return f"{mbps * 1024:.0f}KB/s"


def fmt_bytes(mb):
    """Format megabytes as KB/MB/GB."""
    if mb >= 1024:
        return f"{mb / 1024:.2f}GB"
    if mb >= 1:
        return f"{mb:.1f}MB"
    return f"{mb * 1024:.0f}KB"


def fmt_uptime(sec):
    """Format seconds as XhYYm."""
    return f"{int(sec) // 3600}h{(int(sec) % 3600) // 60:02d}m"


def age_str(ts):
    """Human-readable age from a timestamp: Xs, Xm, Xh."""
    d = int(time.time() - ts)
    if d < 60:
        return f"{d}s"
    if d < 3600:
        return f"{d // 60}m"
    return f"{d // 3600}h"
