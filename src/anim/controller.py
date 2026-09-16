"""AnimationController — state machine for mascot and page animations.

Tracks the current animation state (idle, blinking, working, etc.),
advances frame counters, and exposes the target FPS for the main loop.

States have priorities so that high-priority events (alerts, downloads)
interrupt lower-priority ones (idle, working). A state expires after its
duration, and the controller falls back to the next-highest-priority
state in the queue.
"""
import time
from enum import IntEnum


class AnimState(IntEnum):
    """Animation states ordered by visual priority."""
    IDLE       = 0
    IDLE_BLINK = 1
    IDLE_LOOK  = 2
    WORKING   = 10
    THINKING  = 11
    SUCCESS   = 12
    FAILURE   = 20
    ALERT     = 21
    DOWNLOAD  = 30
    OFFLINE   = 31
    SLEEP     = 32
    WAKE      = 33
    TRANSITION = 40


# Duration in seconds for transient states (0 = persists until replaced)
STATE_DURATION = {
    AnimState.IDLE_BLINK: 0.12,
    AnimState.IDLE_LOOK:  2.5,
    AnimState.SUCCESS:    4.0,
    AnimState.FAILURE:    5.0,
    AnimState.WAKE:       1.5,
    AnimState.TRANSITION: 0.3,
}

# Target FPS per state
STATE_FPS = {
    AnimState.IDLE:       4,
    AnimState.IDLE_BLINK: 8,
    AnimState.IDLE_LOOK:  4,
    AnimState.WORKING:    8,
    AnimState.THINKING:  10,
    AnimState.SUCCESS:    8,
    AnimState.FAILURE:    12,
    AnimState.ALERT:     12,
    AnimState.DOWNLOAD:  12,
    AnimState.OFFLINE:    2,
    AnimState.SLEEP:      1,
    AnimState.WAKE:       8,
    AnimState.TRANSITION: 24,
}


class AnimationController:
    """State machine that drives mascot expressions and page animation rates."""

    def __init__(self):
        self.state = AnimState.IDLE
        self.frame = 0
        self.until = 0.0          # when current transient state expires
        self._blink_next = time.time() + 3.0
        self._blink_until = 0.0
        self._look = 0
        self._look_next = time.time() + 4.0
        self._look_at = time.time()
        self._queue = []          # [(priority, AnimState, duration)]

    def push(self, state, duration=None):
        """Push a transient state. duration overrides STATE_DURATION."""
        dur = duration if duration is not None else STATE_DURATION.get(state, 0)
        priority = int(state)
        # Remove any existing entry for this state
        self._queue = [(p, s, d) for p, s, d in self._queue if s != state]
        self._queue.append((priority, state, dur))
        self._queue.sort(key=lambda x: -x[0])  # highest priority first

    def tick(self, now):
        """Advance the state machine by one tick. Returns current AnimState."""
        # Check if current state expired
        if self.until > 0 and now > self.until:
            self.until = 0.0
            # Remove the expired state from the queue
            self._queue = [(p, s, d) for p, s, d in self._queue if s != self.state]
            # Fall back to highest-priority remaining, or IDLE
            if self._queue:
                _, state, dur = self._queue[0]
                self.state = state
                self.until = now + dur if dur > 0 else 0.0
            else:
                self.state = AnimState.IDLE

        # Blink scheduling (always runs, for mascot rendering)
        if now > self._blink_next:
            self._blink_until = now + 0.12
            self._blink_next = now + 2.2 + (hash(int(now)) % 30) / 10.0

        # Look scheduling
        if now > self._look_next:
            self._look = (-2, 0, 2)[hash(int(now)) % 3]
            self._look_next = now + 2.5 + (hash(int(now * 7)) % 25) / 10.0
            self._look_at = now

        self.frame += 1
        return self.state

    @property
    def fps(self):
        """Target frames per second for the current state."""
        return STATE_FPS.get(self.state, 4)

    @property
    def blinking(self):
        return time.time() < self._blink_until

    @property
    def bob(self):
        """Vertical bob offset for mascot animation."""
        return int(round(1.4 * (2.3 ** (1 / 2) * math.sin(time.time() * 2.3)))) if self.state != AnimState.SLEEP else 0

    def reset(self):
        """Reset to idle state."""
        self.state = AnimState.IDLE
        self.frame = 0
        self.until = 0.0
        self._queue.clear()


# Needed for bob property
import math
