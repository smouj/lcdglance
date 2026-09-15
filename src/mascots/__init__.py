"""Mascot rendering: procedural (primary), opt-in sprites, interactions."""
from .mascot import MascotRenderer       # noqa: F401
from .sources import build_sources, pick_active, mood_for, load_index, is_busy  # noqa: F401
from .sprites import SpriteSet, create_default_sprites  # noqa: F401
from .interactions import find_interaction, INTERACTIONS  # noqa: F401
