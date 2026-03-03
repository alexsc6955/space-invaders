"""
Space Invaders Scene
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Literal

from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.engine.components import Anim2D, Life
from mini_arcade_core.engine.entities import BaseEntity
from mini_arcade_core.spaces.geometry.bounds import Position2D, Size2D

# from mini_arcade_core.engine.entities.sprite import AnimSprite2D, Sprite2D


class EntityId(IntEnum):
    SHIP = 1
    UFO = 2
    ALIEN_START = 100
    ALIEN_END = 199
    BULLET_START = 200
    BULLET_END = 299
    MISSILE_START = 300
    MISSILE_END = 399
    SHELTER_START = 400
    SHELTER_END = 499


@dataclass
class Effect:
    position: Position2D
    size: Size2D
    texture: int  # single sprite (no anim)
    ttl: float = 0.12  # seconds
    alive: bool = True


class Ship(BaseEntity):
    """
    Ship entity
    """

    ship_explosion_frames: list[int] | None = None
    ship_explosion_fps: float = 14.0
    ship_explosion_time: float = 0.45
    exploding: bool = False
    explode_timer: float = 0.0

    @staticmethod
    def build(
        entity_id: EntityId,
        name: str,
        x: float,
        y: float,
        texture: int,
        ship_explosion_frames: list[int],
    ) -> Ship:
        """Build a new Ship entity."""
        ship: Ship = Ship.from_dict(
            {
                "id": entity_id,
                "name": name,
                "transform": {
                    "center": {"x": x, "y": y},
                    "size": {"width": 40.0, "height": 20.0},
                },
                "shape": {
                    "kind": "rect",
                },
                "collider": {
                    "kind": "rect",
                },
                "kinematic": {
                    "velocity": {"vx": 0.0, "vy": 0.0},
                    "acceleration": {"ax": 0.0, "ay": 0.0},
                    "max_speed": 300.0,
                },
                "sprite": {
                    "texture": texture,
                },
            }
        )
        ship.ship_explosion_frames = ship_explosion_frames
        return ship

    @staticmethod
    def start_explosion(ship: BaseEntity, frames: list[int]) -> None:
        if not frames or ship.anim is not None:
            return
        ship.anim = Anim2D(
            anim=Animation(
                frames=frames, fps=Ship.ship_explosion_fps, loop=False
            ),
            texture=frames[0],
        )
        ship.life = Life(ttl=Ship.ship_explosion_time, alive=True)


@dataclass
class Alien(BaseEntity):
    """
    Alien entity
    """

    exploding: bool = False
    explode_timer: float = 0.0
    row: int = 0
    col: int = 0
    fire_cd: float = 0.0

    @staticmethod
    def build(
        entity_id: EntityId,
        name: str,
        x: float,
        y: float,
        frames: list[int],
    ) -> Alien:
        """Build a new Alien entity."""
        alien = Alien.from_dict(
            {
                "id": entity_id,
                "name": name,
                "transform": {
                    "center": {"x": x, "y": y},
                    "size": {"width": 30.0, "height": 20.0},
                },
                "kinematic": {
                    "velocity": {"vx": 0.0, "vy": 0.0},
                    "acceleration": {"ax": 0.0, "ay": 0.0},
                    "max_speed": 50.0,
                },
                "shape": {
                    "kind": "rect",
                },
                "collider": {
                    "kind": "rect",
                },
                "sprite": {
                    "texture": frames[0] if frames else 0,
                },
                "anim": {
                    "frames": frames,
                    "fps": 5.0,
                    "loop": True,
                },
            }
        )
        alien.fire_cd = 2.0 + 3.0 * (entity_id - EntityId.ALIEN_START) / (
            EntityId.ALIEN_END - EntityId.ALIEN_START
        )
        alien.exploding = False
        alien.explode_timer = 0.0
        alien.col = (entity_id - EntityId.ALIEN_START) % 11
        alien.row = (entity_id - EntityId.ALIEN_START) // 11
        return alien


class Ufo(BaseEntity):
    """UFO bonus ship entity."""

    travel_dir: float = 1.0
    points: int = 100

    @staticmethod
    def build(
        entity_id: EntityId,
        x: float,
        y: float,
        texture: int,
        travel_dir: float,
    ) -> "Ufo":
        ufo: Ufo = Ufo.from_dict(
            {
                "id": entity_id,
                "name": "UFO",
                "transform": {
                    "center": {"x": x, "y": y},
                    "size": {"width": 48.0, "height": 22.0},
                },
                "shape": {
                    "kind": "rect",
                },
                "collider": {
                    "kind": "rect",
                },
                "kinematic": {
                    "velocity": {"vx": 0.0, "vy": 0.0},
                    "acceleration": {"ax": 0.0, "ay": 0.0},
                    "max_speed": 110.0,
                },
                "sprite": {
                    "texture": texture,
                },
                "life": {
                    "alive": True,
                },
            }
        )
        ufo.travel_dir = 1.0 if travel_dir >= 0 else -1.0
        ufo.points = 100
        return ufo


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


class Bullet(BaseEntity):
    """
    Bullet entity
    """

    owner: BulletOwner

    @staticmethod
    def build(
        entity_id: EntityId,
        name: str,
        x: float,
        y: float,
        owner: BulletOwner,
        texture: int | None = None,
    ) -> Bullet:
        """Build a new Bullet entity."""
        bullet: Bullet = Bullet.from_dict(
            {
                "id": entity_id,
                "name": name,
                "transform": {
                    "center": {"x": x, "y": y},
                    "size": {"width": 4.0, "height": 10.0},
                },
                "kinematic": {
                    "velocity": {"vx": 0.0, "vy": 0.0},
                    "acceleration": {"ax": 0.0, "ay": 0.0},
                    "max_speed": 400.0,
                },
                "sprite": {
                    "texture": texture if texture is not None else 0,
                },
                "life": {
                    "ttl": 5.0,  # seconds
                    "alive": True,
                },
            }
        )
        bullet.owner = owner
        return bullet


class Missile(BaseEntity):
    """
    Missile entity.
    """

    target_id: int | None = None  # target alien entity id
    speed: float = 420.0

    @staticmethod
    def build(
        entity_id: EntityId,
        name: str,
        x: float,
        y: float,
        texture: int | None = None,
    ) -> Missile:
        missile: Missile = Missile.from_dict(
            {
                "id": entity_id,
                "name": name,
                "transform": {
                    "center": {"x": x, "y": y},
                    "size": {"width": 14.0, "height": 22.0},
                },
                "shape": {
                    "kind": "rect",
                },
                "collider": {
                    "kind": "rect",
                },
                "kinematic": {
                    "velocity": {"vx": 0.0, "vy": -250.0},
                    "acceleration": {"ax": 0.0, "ay": 0.0},
                    "max_speed": 520.0,
                },
                "sprite": {
                    "texture": texture if texture is not None else 0,
                },
                "life": {
                    "ttl": 6.0,
                    "alive": True,
                },
            }
        )
        missile.target_id = None
        missile.speed = 420.0
        return missile


@dataclass
class Shelter(BaseEntity):

    damage: int = 0  # 0 = full, 1..9 damaged
    tex_full: int | None = None
    tex_damaged: list[int] = field(default_factory=list)  # len 9

    @staticmethod
    def build(
        entity_id: EntityId,
        name: str,
        x: float,
        y: float,
        tex_full: int,
        tex_damaged: list[int],
    ) -> Shelter:
        """Build a new Shelter entity."""
        shelter: Shelter = Shelter.from_dict(
            {
                "id": entity_id,
                "name": name,
                "transform": {
                    "center": {"x": x, "y": y},
                    "size": {"width": 60.0, "height": 40.0},
                },
                "shape": {
                    "kind": "rect",
                },
                "collider": {
                    "kind": "rect",
                },
                "sprite": {
                    "texture": tex_full,
                },
            }
        )
        shelter.tex_full = tex_full
        shelter.tex_damaged = tex_damaged
        return shelter
