"""Kill LGS built-in LCD applets that steal the panel from us."""
import subprocess

from ..util.constants import CREATE_NO_WINDOW


def kill_lcd_applets():
    """Terminate known LGS LCD applets that take over the display."""
    for name in ("LCDMedia.exe", "LCDClock.exe", "LCDPop3.exe", "LCDRSS.exe",
                 "LCDYouTube.exe", "LCDCountdown.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", name],
                           capture_output=True, timeout=3,
                           creationflags=CREATE_NO_WINDOW)
        except Exception:
            pass
