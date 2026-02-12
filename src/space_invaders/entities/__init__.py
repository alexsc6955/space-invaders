"""
Space Invaders Scene
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.spaces.d2.collision2d import RectCollider
from mini_arcade_core.spaces.d2.geometry2d import Position2D, Size2D
from mini_arcade_core.spaces.d2.physics2d import Velocity2D
from mini_arcade_core.spaces.physics.kinematics2d import Kinematic2D
from mini_arcade_core.engine.entities.sprite import AnimSprite2D, Sprite2D


@dataclass
class Effect:
    position: Position2D
    size: Size2D
    texture: int  # single sprite (no anim)
    ttl: float = 0.12  # seconds
    alive: bool = True


@dataclass
class Ship(Sprite2D):
    """
    Ship entity
    """

    body: Kinematic2D | None = None  # set after world init

    # new
    exploding: bool = False
    explode_timer: float = 0.0
    explode_anim: Animation | None = None
    base_texture: int | None = None  # remember original texture


@dataclass
class Alien:
    """
    Alien entity
    """

    position: Position2D
    size: Size2D
    velocity: Velocity2D
    speed: float = 25.0
    texture: int | None = None
    anim: Animation | None = None
    exploding: bool = False
    explode_timer: float = 0.0
    row: int = 0
    col: int = 0
    fire_cd: float = 0.0

    @property
    def collider(self) -> RectCollider:
        return RectCollider(self.position, self.size)


BulletOwner = Literal["ship", "alien"]


class ProjectileKind(str, Enum):
    A = "A"
    B = "B"
    C = "C"


@dataclass(frozen=True)
class ProjectileSpec:
    kind: ProjectileKind
    frames: tuple[int, int, int, int]  # 4 textures
    fps: float
    speed: float
    size: Size2D


@dataclass
class Bullet:
    """
    Bullet entity
    """

    position: Position2D
    size: Size2D
    velocity: Velocity2D
    owner: BulletOwner
    alive: bool = True
    texture: int | None = None
    anim: Animation | None = None

    @property
    def collider(self) -> RectCollider:
        return RectCollider(self.position, self.size)


@dataclass
class Missile:
    position: Position2D
    size: Size2D
    velocity: Velocity2D
    alive: bool = True
    target_id: int | None = None  # index into world.aliens (best-effort)
    speed: float = 420.0
    anim: Animation | None = None
    texture: int | None = None

    @property
    def collider(self) -> RectCollider:
        return RectCollider(self.position, self.size)


@dataclass
class Shelter:
    position: Position2D
    size: Size2D
    damage: int = 0  # 0 = full, 1..9 damaged
    alive: bool = True

    tex_full: int | None = None
    tex_damaged: list[int] = field(default_factory=list)  # len 9

    @property
    def collider(self) -> RectCollider:
        return RectCollider(self.position, self.size)

    @property
    def texture(self) -> int | None:
        if not self.alive:
            return None
        if self.damage <= 0:
            return self.tex_full
        idx = min(self.damage, 9) - 1
        if 0 <= idx < len(self.tex_damaged):
            return self.tex_damaged[idx]
        return self.tex_full
