"""
Space Invaders Scene Models
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.scenes.sim_scene import (  # pyright: ignore[reportMissingImports]
    BaseIntent,
    BaseTickContext,
    BaseWorld,
)

from space_invaders.entities import (
    Effect,
    ProjectileKind,
    ProjectileSpec,
)


@dataclass
class SpaceInvadersWorld(BaseWorld):
    """
    Space Invaders World
    """

    viewport: tuple[float, float]
    bullet_texture: int | None = None
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


@dataclass
class SpaceInvadersIntent(BaseIntent):
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
