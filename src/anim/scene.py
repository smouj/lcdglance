"""SceneDirector — manages page selection, overrides, and auto-focus.

Decides which page to show based on:
  1. Manual page selection (B1/B2 buttons)
  2. Auto-focus overrides (downloads, agent events)
  3. B3 scouter overlay
  4. B4 flash overlay

The SceneDirector tracks the scene stack, expiration timers, and
transition requests. The main loop queries it each tick for the
current page and overlay state.
"""
import time


class SceneDirector:
    """Orchestrates which page the LCD shows and for how long."""

    def __init__(self, pages, mascot_page, dl_page, status_page):
        self.pages = pages
        self.mascot_page = mascot_page
        self.dl_page = dl_page
        self.status_page = status_page
        self.page_index = 0
        self.status_until = 0.0
        self.flash_until = 0.0
        self._override = None       # {"page": obj, "until": ts, "kind": str}
        self._dl_was_active = False
        self._ev_seen = 0.0

    @property
    def current_page(self):
        """Return the Page object that should be rendered now."""
        now = time.time()
        if now < self.flash_until:
            return self.pages[self.page_index]
        if now < self.status_until:
            return self.status_page
        if self._override and self._override["page"]:
            if now <= self._override["until"]:
                return self._override["page"]
            self._override = None
        return self.pages[self.page_index]

    @property
    def page_index_out(self):
        """Return the logical page index (for dot indicator)."""
        return self.page_index

    @property
    def is_animated(self):
        """Whether the current page needs animation-rate updates."""
        now = time.time()
        page = self.current_page
        return (page is self.mascot_page
                or page is self.dl_page
                or now < self.flash_until
                or now < self.status_until)

    def next_page(self):
        self.page_index = (self.page_index + 1) % len(self.pages)

    def prev_page(self):
        self.page_index = (self.page_index - 1) % len(self.pages)

    def show_status(self, duration=5.0):
        """B3: show the scouter overlay for *duration* seconds."""
        self.status_until = time.time() + duration

    def flash(self, duration=0.7):
        """B4: flash the screen white for *duration* seconds."""
        self.flash_until = time.time() + duration

    def update(self, now, oc, dl):
        """Process auto-focus events: downloads and agent completions."""
        s = oc.snapshot()
        ev = s.get("last_event")

        # Agent finished → jump to mascot reacting
        if ev and ev["ts"] != self._ev_seen:
            self._ev_seen = ev["ts"]
            self._override = {"page": self.mascot_page, "until": now + 8.0,
                              "kind": "event"}

        # Download active → show download page
        if dl.active:
            self._dl_was_active = True
            self._override = {"page": self.dl_page, "until": now + 1.5,
                              "kind": "download"}
        elif self._dl_was_active:
            self._dl_was_active = False
            if self._override and self._override["kind"] == "download":
                self._override = {"page": self.mascot_page, "until": now + 4.0,
                                  "kind": "event"}

        # Expire overrides
        if self._override and now > self._override["until"]:
            self._override = None

    @property
    def override_kind(self):
        ov = self._override
        return ov["kind"] if ov else None
