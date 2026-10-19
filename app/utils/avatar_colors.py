import secrets
from typing import Optional

VIBRANT_AVATAR_COLORS = [
    "Teal",
    "Blue",
    "Purple",
    "Orange",
    "Green",
    "Amber",
    "Rose",
    "Cyan",
    "Indigo",
    "Emerald",
    "Pink",
    "Violet",
]

def pick_random_avatar_color() -> str:
    """Randomly selects a vibrant avatar color for new users."""
    return secrets.choice(VIBRANT_AVATAR_COLORS)

def resolve_vibrant_avatar_color(current_color: Optional[str], seed: str = "") -> str:
    """
    Returns current_color if it's already a valid vibrant color.
    If it's Gray, Slate, Zinc, Stone, or None, returns a vibrant color based on seed or random choice.
    """
    if current_color and current_color not in ["Gray", "Slate", "Zinc", "Stone"]:
        return current_color
    if seed:
        idx = (hash(seed) & 0x7FFFFFFF) % len(VIBRANT_AVATAR_COLORS)
        return VIBRANT_AVATAR_COLORS[idx]
    return pick_random_avatar_color()
