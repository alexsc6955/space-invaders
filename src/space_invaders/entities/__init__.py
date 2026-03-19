"""Entity definitions for the Space Invaders game."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Literal

from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.engine.components import Anim2D, Life
from mini_arcade_core.engine.entities import BaseEntity
from mini_arcade_core.scenes.entity_blueprints import build_entity_payload
from mini_arcade_core.spaces.geometry.bounds import Position2D, Size2D

# from mini_arcade_core.engine.entities.sprite import AnimSprite2D, Sprite2D


class EntityId(IntEnum):
    """Reserved entity-id ranges for world-managed entity types."""

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


def _payload_from_template(
    template: dict[str, Any],
    *,
    viewport: tuple[float, float],
    entity_id: int,
    name: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_entity_payload(
        template,
        viewport=viewport,
        overrides={
            "id": int(entity_id),
            "name": name,
            **(overrides or {}),
        },
    )


@dataclass
class Effect:
    """Transient sprite-only effect tracked outside the entity list."""

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
    # pylint: disable=too-many-arguments,too-many-positional-arguments
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
                "tags": ["ship", "player"],
            }
        )
        ship.ship_explosion_frames = ship_explosion_frames
        ship.tags = tuple(dict.fromkeys((*ship.tags, "ship", "player")))
        return ship

    @staticmethod
    def build_from_template(
        *,
        template: dict[str, Any],
        viewport: tuple[float, float],
        entity_id: int,
        name: str,
        overrides: dict[str, Any] | None = None,
    ) -> "Ship":
        """Build a ship instance from a resolved entity template."""
        payload = _payload_from_template(
            template,
            viewport=viewport,
            entity_id=entity_id,
            name=name,
            overrides=overrides,
        )
        ship: Ship = Ship.from_dict(payload)
        ship.ship_explosion_frames = list(
            payload.get("ship_explosion_frames", []) or []
        )
        ship.exploding = False
        ship.explode_timer = 0.0
        ship.tags = tuple(dict.fromkeys((*ship.tags, "ship", "player")))
        return ship

    @staticmethod
    def start_explosion(ship: BaseEntity, frames: list[int]) -> None:
        """Attach the one-shot ship explosion animation and lifetime."""
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
                "tags": ["alien"],
            }
        )
        alien.fire_cd = 2.0 + 3.0 * (entity_id - EntityId.ALIEN_START) / (
            EntityId.ALIEN_END - EntityId.ALIEN_START
        )
        alien.exploding = False
        alien.explode_timer = 0.0
        alien.col = (entity_id - EntityId.ALIEN_START) % 11
        alien.row = (entity_id - EntityId.ALIEN_START) // 11
        alien.tags = tuple(dict.fromkeys((*alien.tags, "alien")))
        return alien

    @staticmethod
    # pylint: disable=too-many-arguments
    def build_from_template(
        *,
        template: dict[str, Any],
        viewport: tuple[float, float],
        entity_id: int,
        name: str,
        row: int,
        col: int,
        fire_cd: float = 0.0,
        overrides: dict[str, Any] | None = None,
    ) -> "Alien":
        """Build an alien with row/column metadata from a template."""
        payload = _payload_from_template(
            template,
            viewport=viewport,
            entity_id=entity_id,
            name=name,
            overrides=overrides,
        )
        alien: Alien = Alien.from_dict(payload)
        alien.fire_cd = float(fire_cd)
        alien.exploding = False
        alien.explode_timer = 0.0
        alien.row = int(row)
        alien.col = int(col)
        alien.tags = tuple(dict.fromkeys((*alien.tags, "alien")))
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
        """Build a UFO entity with its travel direction preset."""
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
                "tags": ["ufo"],
            }
        )
        ufo.travel_dir = 1.0 if travel_dir >= 0 else -1.0
        ufo.points = 100
        ufo.tags = tuple(dict.fromkeys((*ufo.tags, "ufo")))
        return ufo

    @staticmethod
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def build_from_template(
        *,
        template: dict[str, Any],
        viewport: tuple[float, float],
        entity_id: int,
        name: str,
        travel_dir: float,
        points: int,
        overrides: dict[str, Any] | None = None,
    ) -> "Ufo":
        """Build a configured UFO entity from a template payload."""
        payload = _payload_from_template(
            template,
            viewport=viewport,
            entity_id=entity_id,
            name=name,
            overrides=overrides,
        )
        ufo: Ufo = Ufo.from_dict(payload)
        ufo.travel_dir = 1.0 if travel_dir >= 0 else -1.0
        ufo.points = int(points)
        ufo.tags = tuple(dict.fromkeys((*ufo.tags, "ufo")))
        return ufo


BulletOwner = Literal["ship", "alien"]


class ProjectileKind(str, Enum):
    """Projectile animation families used by alien bullet rows."""

    A = "A"
    B = "B"
    C = "C"


@dataclass(frozen=True)
class ProjectileSpec:
    """Resolved runtime data for one projectile kind."""

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
    # pylint: disable=too-many-arguments,too-many-positional-arguments
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
                "tags": ["bullet", f"{owner}_bullet"],
            }
        )
        bullet.owner = owner
        bullet.tags = tuple(
            dict.fromkeys((*bullet.tags, "bullet", f"{owner}_bullet"))
        )
        return bullet

    @staticmethod
    # pylint: disable=too-many-arguments
    def build_from_template(
        *,
        template: dict[str, Any],
        viewport: tuple[float, float],
        entity_id: int,
        name: str,
        owner: BulletOwner,
        overrides: dict[str, Any] | None = None,
    ) -> "Bullet":
        """Build a bullet and preserve owner-specific tagging metadata."""
        payload = _payload_from_template(
            template,
            viewport=viewport,
            entity_id=entity_id,
            name=name,
            overrides=overrides,
        )
        bullet: Bullet = Bullet.from_dict(payload)
        bullet.owner = owner
        bullet.tags = tuple(
            dict.fromkeys((*bullet.tags, "bullet", f"{owner}_bullet"))
        )
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
        """Build a missile entity with default homing parameters."""
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
                "tags": ["missile"],
            }
        )
        missile.target_id = None
        missile.speed = 420.0
        missile.tags = tuple(dict.fromkeys((*missile.tags, "missile")))
        return missile

    @staticmethod
    def build_from_template(
        *,
        template: dict[str, Any],
        viewport: tuple[float, float],
        entity_id: int,
        name: str,
        overrides: dict[str, Any] | None = None,
    ) -> "Missile":
        """Build a missile entity from a resolved template payload."""
        payload = _payload_from_template(
            template,
            viewport=viewport,
            entity_id=entity_id,
            name=name,
            overrides=overrides,
        )
        missile: Missile = Missile.from_dict(payload)
        missile.target_id = None
        missile.speed = float(payload.get("speed", 420.0))
        missile.tags = tuple(dict.fromkeys((*missile.tags, "missile")))
        return missile


@dataclass
class Shelter(BaseEntity):
    """Player shelter entity with staged damage textures."""

    damage: int = 0  # 0 = full, 1..9 damaged
    tex_full: int | None = None
    tex_damaged: list[int] = field(default_factory=list)  # len 9

    @staticmethod
    # pylint: disable=too-many-arguments,too-many-positional-arguments
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
                "tags": ["shelter"],
            }
        )
        shelter.tex_full = tex_full
        shelter.tex_damaged = tex_damaged
        shelter.tags = tuple(dict.fromkeys((*shelter.tags, "shelter")))
        return shelter

    @staticmethod
    def build_from_template(
        *,
        template: dict[str, Any],
        viewport: tuple[float, float],
        entity_id: int,
        name: str,
        overrides: dict[str, Any] | None = None,
    ) -> "Shelter":
        """Build a shelter and cache its pristine and damaged textures."""
        payload = _payload_from_template(
            template,
            viewport=viewport,
            entity_id=entity_id,
            name=name,
            overrides=overrides,
        )
        shelter: Shelter = Shelter.from_dict(payload)
        shelter.tex_full = payload.get("tex_full")
        shelter.tex_damaged = list(payload.get("tex_damaged", []) or [])
        shelter.tags = tuple(dict.fromkeys((*shelter.tags, "shelter")))
        return shelter
