"""World, intent, and tick-context models for Space Invaders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.engine.entities import BaseEntity
from mini_arcade_core.scenes.sim_scene import (  # pyright: ignore[reportMissingImports]
    BaseIntent,
    BaseTickContext,
    BaseWorld,
    EntityIdDomain,
)

from space_invaders.entities import (
    Effect,
    EntityId,
    ProjectileKind,
    ProjectileSpec,
)

if TYPE_CHECKING:
    from space_invaders.scenes.space_invaders.spawn import (
        AlienFormationSpec,
        ShelterRowSpec,
    )


@dataclass
class SpaceInvadersWorld(
    BaseWorld
):  # pylint: disable=too-many-instance-attributes
    """
    Space Invaders World
    """

    entity_id_domains = {
        "ship": EntityIdDomain(
            start_id=int(EntityId.SHIP), end_id=int(EntityId.SHIP)
        ),
        "ufo": EntityIdDomain(
            start_id=int(EntityId.UFO), end_id=int(EntityId.UFO)
        ),
        "alien": EntityIdDomain(
            start_id=int(EntityId.ALIEN_START), end_id=int(EntityId.ALIEN_END)
        ),
        "bullet": EntityIdDomain(
            start_id=int(EntityId.BULLET_START),
            end_id=int(EntityId.BULLET_END),
        ),
        "missile": EntityIdDomain(
            start_id=int(EntityId.MISSILE_START),
            end_id=int(EntityId.MISSILE_END),
        ),
        "shelter": EntityIdDomain(
            start_id=int(EntityId.SHELTER_START),
            end_id=int(EntityId.SHELTER_END),
        ),
    }
    viewport: tuple[float, float]
    bullet_texture: int | None = None
    entity_templates: dict[str, dict[str, Any]] = field(default_factory=dict)
    alien_formation_spec: AlienFormationSpec | None = None
    shelter_row_spec: ShelterRowSpec | None = None
    bullets: list[int] = field(default_factory=list)
    ship_fire_timer: float = 0.0
    ship_fire_cooldown: float = 0.20
    aliens_direction: float = 1.0  # 1 for right, -1 for left
    alien_fire_timer: float = 1.0  # start with a delay
    max_alien_bullets: int = 2
    alien_fire_cooldown_min: float = 0.8  # slower
    alien_fire_cooldown_max: float = 1.6
    projectile_specs: dict[ProjectileKind, ProjectileSpec] = field(
        default_factory=dict
    )
    explosion_texture: int | None = None

    omega_active: bool = False
    omega_timer: float = 0.0
    omega_charge_timer: float = 0.0
    omega_x: float | None = None  # beam X (left) in pixels
    omega_cooldown: float = 2.5
    omega_cd_timer: float = 0.0

    omega_charge_anim: Animation | None = None
    omega_beam_anim: Animation | None = None
    omega_beam_large_anim: Animation | None = None

    omega_width: int = 36  # scaled beam width
    omega_large_height: int = 180  # base chunk size

    missile_targeting: bool = False
    missile_target_idx: int | None = None  # index in alive aliens list
    missile_cooldown: float = 1.5
    missile_cd_timer: float = 0.0

    missile_anim: Animation | None = None
    missiles: list[int] = field(default_factory=list)

    target_texture: int | None = None
    target_scale: float = 1.35

    ufo_texture: int | None = None
    ufo_spawn_timer: float = 6.0
    ufo_spawn_min: float = 12.0
    ufo_spawn_max: float = 20.0
    ufo_speed: float = 95.0
    ufo_points: int = 100

    effects: list[Effect] = field(default_factory=list)
    fx_player_proj_tex: int | None = None
    fx_enemy_proj_tex: int | None = None
    fx_ttl: float = 0.12

    score: int = 0
    lives: int = 3
    game_over: bool = False
    victory: bool = False

    # shield
    shield_active: bool = False
    shield_timer: float = 0.0
    shield_duration: float = 1.0
    shield_cd_timer: float = 0.0
    shield_cooldown: float = 2.0
    shield_anim: Animation | None = None
    shield_scale: float = 1.35

    def ship(self) -> BaseEntity | None:
        """Return the player ship entity, if one is currently present."""
        ship = self.find_entity(tag="ship")
        if ship is not None:
            return ship
        entities = self.get_entities_in_domain("ship")
        return entities[0] if entities else None

    def ufo(self) -> BaseEntity | None:
        """Return the active UFO bonus ship, if present."""
        ufo = self.find_entity(tag="ufo")
        if ufo is not None:
            return ufo
        entities = self.get_entities_in_domain("ufo")
        return entities[0] if entities else None

    def aliens(self) -> list[BaseEntity]:
        """Return all alien entities in tag-first, domain-second order."""
        aliens = self.get_entities_by_tag("alien")
        if aliens:
            return aliens
        return self.get_entities_in_domain("alien")

    def shelters(self) -> list[BaseEntity]:
        """Return all shelter entities in tag-first, domain-second order."""
        shelters = self.get_entities_by_tag("shelter")
        if shelters:
            return shelters
        return self.get_entities_in_domain("shelter")

    def bullet_entities(self) -> list[BaseEntity]:
        """Return all bullet entities in tag-first, domain-second order."""
        bullets = self.get_entities_by_tag("bullet")
        if bullets:
            return bullets
        return self.get_entities_in_domain("bullet")

    def missile_entities(self) -> list[BaseEntity]:
        """Return all missile entities in tag-first, domain-second order."""
        missiles = self.get_entities_by_tag("missile")
        if missiles:
            return missiles
        return self.get_entities_in_domain("missile")


@dataclass
class SpaceInvadersIntent(
    BaseIntent
):  # pylint: disable=too-many-instance-attributes
    """
    Space Invaders Intent
    """

    move_ship_left: float
    move_ship_right: float
    fire_bullet: bool = False
    fire_omega_ray: bool = False

    toggle_missile_target: bool = False
    missile_target_left: bool = False
    missile_target_right: bool = False
    missile_launch: bool = False
    missile_target_up: bool = False
    missile_target_down: bool = False

    shield_toggle: bool = False
    pause: bool = False

    ship_kill_switch: bool = False  # for testing, kills player instantly


@dataclass
class SpaceInvadersTickContext(
    BaseTickContext[SpaceInvadersWorld, SpaceInvadersIntent]
):
    """
    Space Invaders Tick Context
    """
