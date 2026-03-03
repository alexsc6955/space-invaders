"""
Space Invaders Scene Helpers
"""

from __future__ import annotations

from mini_arcade_core.spaces.geometry.bounds import Position2D, Size2D

from space_invaders.entities import (
    Alien,
    Effect,
    EntityId,
)
from space_invaders.scenes.space_invaders.models import (
    SpaceInvadersWorld,
)


def alloc_entity_id_in_range(
    world: SpaceInvadersWorld,
    start: EntityId,
    end: EntityId,
) -> int | None:
    """
    Allocate the first free entity id in [start, end].
    Returns None when the range is exhausted.
    """
    start_id = int(start)
    end_id = int(end)
    used_ids = {e.id for e in world.entities if start_id <= e.id <= end_id}
    for candidate in range(start_id, end_id + 1):
        if candidate not in used_ids:
            return candidate
    return None


def spawn_effect(
    world: SpaceInvadersWorld,
    texture: int | None,
    x: float,
    y: float,
    w: float,
    h: float,
    ttl: float = 0.12,
):
    if texture is None:
        return
    world.effects.append(
        Effect(
            position=Position2D(x, y),
            size=Size2D(w, h),
            texture=texture,
            ttl=ttl,
        )
    )


def is_round_locked(world: SpaceInvadersWorld) -> bool:
    """Returns True when gameplay should stop accepting new actions."""
    return bool(world.game_over or world.victory)


def alien_points(alien: Alien) -> int:
    """Classic-ish scoring tiers by alien row."""
    row = int(getattr(alien, "row", 0))
    if row <= 0:
        return 30
    if row <= 2:
        return 20
    return 10
    return 10
