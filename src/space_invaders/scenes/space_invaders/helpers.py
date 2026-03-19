# pylint: disable=too-many-arguments,too-many-positional-arguments

"""
Space Invaders Scene Helpers
"""

from __future__ import annotations

from mini_arcade_core.spaces.geometry.bounds import Position2D, Size2D

from space_invaders.entities import Alien, Effect
from space_invaders.scenes.space_invaders.models import SpaceInvadersWorld


def spawn_effect(
    world: SpaceInvadersWorld,
    texture: int | None,
    x: float,
    y: float,
    w: float,
    h: float,
    ttl: float = 0.12,
):
    """Append a transient overlay effect when a valid texture is available."""
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


def is_entity_alive(entity: object) -> bool:
    """Resolve alive state from ``life.alive`` or a plain ``alive`` flag."""
    life = getattr(entity, "life", None)
    if life is not None:
        return bool(getattr(life, "alive", True))
    return bool(getattr(entity, "alive", True))


def mark_entity_dead(entity: object) -> None:
    """Mark an entity dead when it exposes a life component or alive flag."""
    life = getattr(entity, "life", None)
    if life is not None:
        setattr(life, "alive", False)
        return
    if hasattr(entity, "alive"):
        setattr(entity, "alive", False)


def alien_points(alien: Alien) -> int:
    """Classic-ish scoring tiers by alien row."""
    row = int(getattr(alien, "row", 0))
    if row <= 0:
        return 30
    if row <= 2:
        return 20
    return 10
