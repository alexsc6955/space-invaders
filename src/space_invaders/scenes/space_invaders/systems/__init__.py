"""
Space Invaders Scene Systems
"""

# pylint: disable=duplicate-code,missing-function-docstring,too-many-arguments
# pylint: disable=too-many-branches,too-many-instance-attributes,too-many-lines
# pylint: disable=too-many-locals,too-many-positional-arguments
# pylint: disable=too-many-return-statements,too-many-statements

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Iterable

from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.engine.components import Anim2D
from mini_arcade_core.engine.entities import BaseEntity
from mini_arcade_core.scenes.systems import SystemBundle
from mini_arcade_core.scenes.systems.builtins import (
    AxisIntentBinding,
    IntentAxisVelocitySystem,
    KinematicMotionSystem,
    MotionBinding,
    ProjectileBoundaryBinding,
    ProjectileBoundarySystem,
    ProjectileCleanupBinding,
    ProjectileCleanupSystem,
    SpawnBinding,
    SpawnSystem,
    ViewportConstraintBinding,
    ViewportConstraintSystem,
)
from mini_arcade_core.scenes.systems.phases import SystemPhase
from mini_arcade_core.spaces.collision.intersections import (
    intersects_entities,
    rect_rect,
)
from mini_arcade_core.spaces.geometry.bounds import Size2D
from mini_arcade_core.spaces.math.vec2 import Vec2
from mini_arcade_core.utils import logger

from space_invaders.entities import (
    Alien,
    Bullet,
    Effect,
    EntityId,
    Missile,
    ProjectileKind,
    Shelter,
    Ship,
    Ufo,
)
from space_invaders.scenes.space_invaders.helpers import (
    alien_points,
    is_entity_alive,
    is_round_locked,
    mark_entity_dead,
    spawn_effect,
)
from space_invaders.scenes.space_invaders.models import (
    SpaceInvadersTickContext,
)
from space_invaders.scenes.space_invaders.systems.render import (
    SpaceInvadersRenderSystem,
)

__all__ = [
    "ShipKillSwitchSystem",
    "ShipExplosionLifecycleSystem",
    "ShieldSystem",
    "MissileTargetSystem",
    "ShipMovementBundle",
    "ShipSystem",
    "UfoSystem",
    "OmegaRaySystem",
    "MissileSpawnSystem",
    "BulletSpawnSystem",
    "BulletMissileCollisionSystem",
    "BulletBulletCollisionSystem",
    "BulletCleanupSystem",
    "AlienSystem",
    "AlienAnimationSystem",
    "AlienFireSystem",
    "BulletMotionBundle",
    "BulletMoveSystem",
    "BulletAnimationSystem",
    "MissileHomingSystem",
    "MissileAlienCollisionSystem",
    "UfoCollisionSystem",
    "BulletAlienCollisionSystem",
    "BulletShelterCollisionSystem",
    "BulletShieldCollisionSystem",
    "BulletShipCollisionSystem",
    "OmegaRayDamageSystem",
    "ExplosionSystem",
    "MissileCleanupSystem",
    "MissileCullSystem",
    "BulletCullSystem",
    "RoundStateSystem",
    "EffectsSystem",
    "SpaceInvadersRenderSystem",
]


def _active_ship(ctx: SpaceInvadersTickContext) -> Ship | None:
    ship: Ship | None = ctx.world.ship()
    if ship is None:
        return None
    if getattr(ship, "exploding", False) or ship.anim is not None:
        return None
    return ship


def _bullet_entities(ctx: SpaceInvadersTickContext) -> tuple[Bullet, ...]:
    return tuple(
        bullet for bullet in ctx.world.bullet_entities() if bullet is not None
    )


def _missile_entities(ctx: SpaceInvadersTickContext) -> tuple[Missile, ...]:
    return tuple(
        missile
        for missile in ctx.world.missile_entities()
        if missile is not None
    )


def _aliens(ctx: SpaceInvadersTickContext) -> tuple[Alien, ...]:
    return tuple(alien for alien in ctx.world.aliens() if alien is not None)


def _alive_bullets(
    ctx: SpaceInvadersTickContext,
    *,
    owner: str | None = None,
) -> tuple[Bullet, ...]:
    return tuple(
        bullet
        for bullet in _bullet_entities(ctx)
        if is_entity_alive(bullet)
        and (owner is None or getattr(bullet, "owner", None) == owner)
    )


def _alive_missiles(ctx: SpaceInvadersTickContext) -> tuple[Missile, ...]:
    return tuple(
        missile
        for missile in _missile_entities(ctx)
        if is_entity_alive(missile)
    )


def _pairwise_collisions(
    *,
    sources: Iterable[BaseEntity],
    targets: Iterable[BaseEntity],
    on_collision: Callable[[BaseEntity, BaseEntity], None],
    source_filter: Callable[[BaseEntity], bool] | None = None,
    target_filter: Callable[[BaseEntity], bool] | None = None,
    collides: Callable[[BaseEntity, BaseEntity], bool] = intersects_entities,
    stop_after_source_hit: bool = True,
) -> None:
    """
    Iterate source/target pairs and invoke ``on_collision`` for each hit.
    """
    source_filter = source_filter or (lambda _entity: True)
    target_filter = target_filter or (lambda _entity: True)
    target_list = list(targets)

    for source in sources:
        if not is_entity_alive(source) or not source_filter(source):
            continue

        for target in target_list:
            if not is_entity_alive(source):
                break
            if not is_entity_alive(target) or not target_filter(target):
                continue
            if not collides(source, target):
                continue

            on_collision(source, target)
            if stop_after_source_hit:
                break


@dataclass
class ShipKillSwitchSystem:
    """Applies one-shot debug/test input to the player ship."""

    name: str = "space_invaders_ship_kill_switch"
    phase: int = SystemPhase.CONTROL
    order: int = 13  # after pause (12) or right after input (10/11)

    def step(self, ctx: SpaceInvadersTickContext) -> None:
        if ctx.intent is None:
            return

        ship: Ship | None = ctx.world.ship()
        if ship is None or not ctx.intent.ship_kill_switch:
            return
        ship.exploding = True
        Ship.start_explosion(ship, ship.ship_explosion_frames)


@dataclass
class ShipExplosionLifecycleSystem:
    """Ticks ship explosion animation and clears transient death state."""

    name: str = "space_invaders_ship_explosion_lifecycle"
    phase: int = SystemPhase.PRESENTATION
    order: int = 16

    def step(self, ctx: SpaceInvadersTickContext) -> None:
        ship: Ship | None = ctx.world.ship()
        if ship is None:
            return
        if ship.anim:
            ship.anim.step(ctx.dt)
        if ship.life:
            ship.life.step(ctx.dt)
            if not ship.life.alive:
                ship.anim = None
                ship.life = None
                ship.exploding = False


@dataclass
class ShieldSystem:
    """Manage shield activation, cooldown, and presentation timing."""

    name: str = "space_invaders_shield"
    phase: int = SystemPhase.CONTROL
    order: int = 22  # after input, before collisions

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        it = ctx.intent
        if it is None:
            return
        if is_round_locked(w):
            return

        # cooldown tick
        if w.shield_cd_timer > 0:
            w.shield_cd_timer = max(0.0, w.shield_cd_timer - ctx.dt)

        # active tick
        if w.shield_active:
            w.shield_timer = max(0.0, w.shield_timer - ctx.dt)
            if w.shield_anim:
                w.shield_anim.update(ctx.dt)
            if w.shield_timer <= 0:
                w.shield_active = False

        # trigger
        if (
            it.shield_toggle
            and (not w.shield_active)
            and w.shield_cd_timer <= 0
        ):
            w.shield_active = True
            w.shield_timer = w.shield_duration
            w.shield_cd_timer = w.shield_cooldown
            if w.shield_anim:
                w.shield_anim.time = 0.0
                w.shield_anim.index = 0


@dataclass
class MissileTargetSystem:
    """Toggle and move the missile lock-on cursor across living aliens."""

    name: str = "space_invaders_missile_target"
    phase: int = SystemPhase.CONTROL
    order: int = (
        21  # after input, before ship move if you want to gate movement
    )

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        it = ctx.intent
        if it is None:
            return
        if is_round_locked(w):
            return

        # tick cooldown
        if w.missile_cd_timer > 0:
            w.missile_cd_timer = max(0.0, w.missile_cd_timer - ctx.dt)

        aliens = w.aliens()
        alive = [a for a in aliens if not getattr(a, "exploding", False)]
        if not alive:
            w.missile_targeting = False
            w.missile_target_idx = None
            return

        # toggle targeting mode
        if it.toggle_missile_target:
            w.missile_targeting = not w.missile_targeting
            if w.missile_targeting:
                # ensure idx valid when entering targeting
                if (
                    w.missile_target_idx is None
                    or w.missile_target_idx >= len(alive)
                ):
                    w.missile_target_idx = 0
            return

        if not w.missile_targeting:
            return

        # keep idx valid
        if w.missile_target_idx is None:
            w.missile_target_idx = 0
        w.missile_target_idx = max(
            0, min(len(alive) - 1, w.missile_target_idx)
        )

        cur = alive[w.missile_target_idx]
        cur_row = int(getattr(cur, "row", 0))
        cur_col = int(getattr(cur, "col", 0))

        def find_in_dir(drow: int, dcol: int) -> int | None:
            candidates: list[tuple[int, int]] = []  # (score, idx)
            for idx, a in enumerate(alive):
                if a is cur:
                    continue

                dr = a.row - cur_row
                dc = a.col - cur_col

                # respect direction
                if drow != 0:
                    if dr == 0 or (dr > 0) != (drow > 0):
                        continue
                if dcol != 0:
                    if dc == 0 or (dc > 0) != (dcol > 0):
                        continue

                same_axis = (dcol != 0 and a.row == cur_row) or (
                    drow != 0 and a.col == cur_col
                )
                manhattan = abs(dr) + abs(dc)
                score = manhattan + (0 if same_axis else 1000)
                candidates.append((score, idx))

            if not candidates:
                return None
            candidates.sort(key=lambda t: t[0])
            return candidates[0][1]

        if it.missile_target_left:
            nxt = find_in_dir(0, -1)
            if nxt is not None:
                w.missile_target_idx = nxt
        elif it.missile_target_right:
            nxt = find_in_dir(0, +1)
            if nxt is not None:
                w.missile_target_idx = nxt
        elif it.missile_target_up:
            nxt = find_in_dir(-1, 0)
            if nxt is not None:
                w.missile_target_idx = nxt
        elif it.missile_target_down:
            nxt = find_in_dir(+1, 0)
            if nxt is not None:
                w.missile_target_idx = nxt


@dataclass
class ShipMovementBundle(SystemBundle[SpaceInvadersTickContext]):
    """
    Bundle of processors that apply ship intent, motion, and clamping.
    """

    _velocity: IntentAxisVelocitySystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )
    _motion: KinematicMotionSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )
    _constraints: ViewportConstraintSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        def _enabled(ctx: SpaceInvadersTickContext) -> bool:
            return (ctx.intent is not None) and (
                not is_round_locked(ctx.world)
            )

        self._velocity = IntentAxisVelocitySystem(
            enabled_when=_enabled,
            bindings=(
                AxisIntentBinding(
                    entity_getter=_active_ship,
                    value_getter=lambda ctx: float(ctx.intent.move_ship_right)
                    - float(ctx.intent.move_ship_left),
                    axis="x",
                    zero_other_axis=True,
                ),
            ),
        )
        self._motion = KinematicMotionSystem(
            enabled_when=_enabled,
            bindings=(
                MotionBinding(
                    entities_getter=lambda ctx: tuple(
                        ship
                        for ship in (_active_ship(ctx),)
                        if ship is not None
                    ),
                ),
            ),
        )
        self._constraints = ViewportConstraintSystem(
            enabled_when=_enabled,
            bindings=(
                ViewportConstraintBinding(
                    entities_getter=lambda ctx: tuple(
                        ship
                        for ship in (_active_ship(ctx),)
                        if ship is not None
                    ),
                    policy="clamp",
                    axes=("x",),
                ),
            ),
        )

    def iter_systems(self) -> Iterable[object]:
        return (self._velocity, self._motion, self._constraints)


@dataclass
class UfoSystem:
    """Spawn and move the periodic UFO bonus ship."""

    name: str = "space_invaders_ufo"
    phase: int = SystemPhase.SIMULATION
    order: int = 24
    _spawn: SpawnSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._spawn = SpawnSystem(
            name=self.name,
            phase=self.phase,
            order=self.order,
            bindings=(
                SpawnBinding(
                    should_spawn=self._should_spawn,
                    spawn=self._spawn_ufo,
                    on_spawned=self._after_spawn,
                ),
            ),
        )

    @staticmethod
    def _should_spawn(ctx: SpaceInvadersTickContext) -> bool:
        w = ctx.world
        return bool(
            w.ufo() is None
            and w.ufo_spawn_timer <= 0
            and w.ufo_texture is not None
        )

    def _spawn_ufo(self, ctx: SpaceInvadersTickContext) -> Ufo | None:
        w = ctx.world
        vw, _ = w.viewport
        ufo_template = w.entity_templates.get("ufo", {})
        ufo_size = (ufo_template.get("transform", {}) or {}).get(
            "size", {}
        ) or {}
        ufo_width = float(ufo_size.get("width", 48.0))
        spawn_y = float(ufo_template.get("spawn_y", 36.0))
        direction = random.choice((-1.0, 1.0))
        x = -ufo_width if direction > 0 else vw + ufo_width
        ufo = Ufo.build_from_template(
            template=ufo_template,
            viewport=w.viewport,
            entity_id=int(EntityId.UFO),
            name=str(ufo_template.get("name", "UFO")),
            travel_dir=direction,
            points=int(ufo_template.get("points", w.ufo_points)),
            overrides={
                "transform": {"position": {"x": x, "y": spawn_y}},
            },
        )
        if ufo.kinematic is not None:
            ufo.kinematic.max_speed = float(w.ufo_speed)
            ufo.kinematic.velocity.x = direction * float(w.ufo_speed)
        return ufo

    @staticmethod
    def _after_spawn(
        ctx: SpaceInvadersTickContext,
        _spawned: tuple[BaseEntity, ...],
    ) -> None:
        ctx.world.ufo_spawn_timer = random.uniform(
            ctx.world.ufo_spawn_min,
            ctx.world.ufo_spawn_max,
        )

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        vw, _ = w.viewport
        ufo: Ufo | None = w.ufo()
        ufo_template = w.entity_templates.get("ufo", {})
        spawn_margin = float(ufo_template.get("spawn_margin", 64.0))

        if is_round_locked(w):
            if ufo is not None:
                w.remove_entities_by_ids({int(EntityId.UFO)})
            return

        if ufo is None:
            w.ufo_spawn_timer = max(0.0, float(w.ufo_spawn_timer) - ctx.dt)
            self._spawn.step(ctx)
            return

        if ufo.kinematic is None:
            return
        ufo.kinematic.velocity.x = float(ufo.travel_dir) * float(w.ufo_speed)
        ufo.kinematic.velocity.y = 0.0
        ufo.kinematic.step(ufo.transform, ctx.dt)

        ux = float(ufo.transform.center.x)
        uw = float(ufo.transform.size.width)
        if (ux + uw) < -spawn_margin or ux > (vw + spawn_margin):
            w.remove_entities_by_ids({int(EntityId.UFO)})
            w.ufo_spawn_timer = random.uniform(
                w.ufo_spawn_min, w.ufo_spawn_max
            )


@dataclass
class MissileSpawnSystem:
    """Spawn homing missiles from the ship toward the selected alien."""

    name: str = "space_invaders_missile_spawn"
    phase: int = SystemPhase.CONTROL
    order: int = 26  # after ship system is fine

    missile_size: Size2D = Size2D(14, 22)
    _spawn: SpawnSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._spawn = SpawnSystem(
            name=self.name,
            phase=self.phase,
            order=self.order,
            bindings=(
                SpawnBinding(
                    should_spawn=self._should_spawn,
                    spawn=self._spawn_missile,
                    on_spawned=self._after_spawn,
                ),
            ),
        )

    @staticmethod
    def _should_spawn(ctx: SpaceInvadersTickContext) -> bool:
        w = ctx.world
        it = ctx.intent
        if it is None or not it.missile_launch:
            return False
        if is_round_locked(w):
            return False
        if not w.missile_targeting or w.missile_cd_timer > 0:
            return False

        ship = w.ship()
        if ship is None:
            return False
        if getattr(ship, "exploding", False) or ship.anim is not None:
            return False

        aliens = [a for a in w.aliens() if not getattr(a, "exploding", False)]
        return bool(
            aliens
            and w.missile_target_idx is not None
            and 0 <= w.missile_target_idx < len(aliens)
        )

    def _spawn_missile(self, ctx: SpaceInvadersTickContext) -> Missile | None:
        w = ctx.world
        aliens = [a for a in w.aliens() if not getattr(a, "exploding", False)]
        if w.missile_target_idx is None or w.missile_target_idx >= len(aliens):
            return None

        target = aliens[w.missile_target_idx]
        missile_template = w.entity_templates.get("missile", {})
        missile_size = (missile_template.get("transform", {}) or {}).get(
            "size", {}
        ) or {}
        missile_w = float(missile_size.get("width", self.missile_size.width))
        missile_h = float(missile_size.get("height", self.missile_size.height))

        ship: Ship | None = w.ship()
        if ship is None:
            return None
        sx, sy = ship.transform.center.to_tuple()
        sw, _ = ship.transform.size.to_tuple()

        mx = sx + sw / 2 - missile_w / 2
        my = sy - missile_h

        missile_id = w.allocate_entity_id_for("missile")
        if missile_id is None:
            return None

        missile_tex = (
            w.missile_anim.current_frame
            if w.missile_anim and len(w.missile_anim.frames) > 0
            else None
        )
        missile = Missile.build_from_template(
            template=missile_template,
            viewport=w.viewport,
            entity_id=missile_id,
            name=str(missile_template.get("name", "Missile")),
            overrides={
                "transform": {"position": {"x": mx, "y": my}},
                "sprite": {
                    "texture": (
                        missile_tex
                        if missile_tex is not None
                        else (
                            (missile_template.get("sprite", {}) or {}).get(
                                "texture", 0
                            )
                        )
                    )
                },
            },
        )
        missile.target_id = target.id
        missile.rotation_deg = 0.0

        if w.missile_anim:
            missile.anim = Anim2D(
                anim=Animation(
                    frames=list(w.missile_anim.frames),
                    fps=w.missile_anim.fps,
                    loop=w.missile_anim.loop,
                ),
                texture=missile_tex,
            )
            if missile.sprite and missile.anim.texture is not None:
                missile.sprite.texture = missile.anim.texture

        return missile

    @staticmethod
    def _after_spawn(
        ctx: SpaceInvadersTickContext,
        spawned: tuple[BaseEntity, ...],
    ) -> None:
        ctx.world.missiles.extend(int(entity.id) for entity in spawned)
        ctx.world.missile_cd_timer = ctx.world.missile_cooldown
        ctx.world.missile_targeting = False

    def step(self, ctx: SpaceInvadersTickContext):
        self._spawn.step(ctx)


@dataclass
class AlienSystem:
    """
    Move aliens as a formation:
    - Move horizontally
    - If any hits wall -> reverse direction and drop down
    """

    name: str = "space_invaders_aliens"
    phase: int = SystemPhase.SIMULATION
    order: int = 30

    drop_step: float = 18.0

    def step(self, ctx: SpaceInvadersTickContext):
        if is_round_locked(ctx.world):
            return
        vw, _ = ctx.world.viewport
        aliens = ctx.world.aliens()
        if not aliens:
            return

        dir_x = ctx.world.aliens_direction

        # Predict wall contact without mutating transforms.
        hit_wall = False
        for a in aliens:
            if a.kinematic is None:
                continue
            x = a.transform.center.x
            next_x = x + (dir_x * a.kinematic.max_speed * ctx.dt)
            if next_x < 0.0 or (next_x + a.transform.size.width) > vw:
                hit_wall = True
                break

        if hit_wall:
            # Reverse formation direction and drop one row.
            ctx.world.aliens_direction *= -1.0
            for a in aliens:
                if a.kinematic is None:
                    continue
                a.kinematic.velocity.x = 0.0
                a.kinematic.velocity.y = 0.0
                a.transform.center.y += self.drop_step
            return

        # Normal horizontal move.
        for a in aliens:
            if a.kinematic is None:
                continue
            a.kinematic.velocity.x = dir_x * a.kinematic.max_speed
            a.kinematic.velocity.y = 0.0
            a.kinematic.step(a.transform, ctx.dt)
            # Keep formation inside viewport bounds.
            a.transform.center.x = max(
                0.0, min(vw - a.transform.size.width, a.transform.center.x)
            )


@dataclass
class AlienAnimationSystem:
    """Advance alien sprite animations during presentation."""

    name: str = "space_invaders_alien_anim"
    phase: int = SystemPhase.PRESENTATION
    order: int = 28

    def step(self, ctx: SpaceInvadersTickContext):
        for alien in _aliens(ctx):
            if alien.anim:
                alien.anim.step(ctx.dt)


@dataclass
class AlienFireSystem:
    """Choose alien shooters and spawn enemy projectiles on a timer."""

    name: str = "space_invaders_alien_fire"
    phase: int = SystemPhase.SIMULATION
    order: int = 32  # after AlienSystem movement is fine

    min_cooldown: float = 0.25
    max_cooldown: float = 1.10
    _spawn: SpawnSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )
    _pending_shooter_id: int | None = field(
        init=False,
        default=None,
        repr=False,
    )
    _pending_kind: ProjectileKind | None = field(
        init=False,
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._spawn = SpawnSystem(
            name=self.name,
            phase=self.phase,
            order=self.order,
            bindings=(
                SpawnBinding(
                    should_spawn=self._should_spawn,
                    spawn=self._spawn_bullet,
                    on_spawned=self._after_spawn,
                ),
            ),
        )

    def step(self, ctx: SpaceInvadersTickContext):
        if is_round_locked(ctx.world):
            self._clear_pending()
            return
        aliens = ctx.world.aliens()
        if not aliens:
            self._clear_pending()
            return

        for a in aliens:
            if a.fire_cd > 0.0:
                a.fire_cd = max(0.0, a.fire_cd - ctx.dt)

        # tick timer
        ctx.world.alien_fire_timer -= ctx.dt
        if ctx.world.alien_fire_timer > 0:
            return

        if self._active_alien_bullet_count(ctx) >= ctx.world.max_alien_bullets:
            # try again soon, but don't spam checks every frame
            ctx.world.alien_fire_timer = 0.15
            self._clear_pending()
            return

        ctx.world.alien_fire_timer = random.uniform(
            ctx.world.alien_fire_cooldown_min,
            ctx.world.alien_fire_cooldown_max,
        )
        self._spawn.step(ctx)

    def _active_alien_bullet_count(
        self,
        ctx: SpaceInvadersTickContext,
    ) -> int:
        vw, vh = ctx.world.viewport
        active_alien_bullets = 0
        for bullet in _alive_bullets(ctx, owner="alien"):
            x, y = bullet.transform.center.to_tuple()
            bw, bh = bullet.transform.size.to_tuple()
            if (y + bh) < 0 or y > vh or (x + bw) < 0 or x > vw:
                continue
            active_alien_bullets += 1
        return active_alien_bullets

    def _should_spawn(self, ctx: SpaceInvadersTickContext) -> bool:
        aliens = ctx.world.aliens()
        shooters = self._bottom_most_by_column(aliens)
        if not shooters:
            self._clear_pending()
            return False

        shooter = random.choice(shooters)
        kind = self._projectile_kind_for_row(
            shooter.row,
            total_rows=self._infer_rows(aliens),
        )
        if kind is None or ctx.world.projectile_specs.get(kind) is None:
            self._clear_pending()
            return False

        self._pending_shooter_id = int(shooter.id)
        self._pending_kind = kind
        return True

    def _spawn_bullet(
        self,
        ctx: SpaceInvadersTickContext,
    ) -> Bullet | None:
        if self._pending_shooter_id is None or self._pending_kind is None:
            return None

        shooter = ctx.world.get_entity_by_id(self._pending_shooter_id)
        spec = ctx.world.projectile_specs.get(self._pending_kind)
        if shooter is None or spec is None:
            self._clear_pending()
            return None
        if (
            getattr(shooter, "exploding", False)
            or float(getattr(shooter, "fire_cd", 0.0)) > 0.0
        ):
            self._clear_pending()
            return None

        sx, sy = shooter.transform.center.to_tuple()
        sw, sh = shooter.transform.size.to_tuple()
        bullet_id = ctx.world.allocate_entity_id_for("bullet")
        if bullet_id is None:
            self._clear_pending()
            return None

        bullet = Bullet.build_from_template(
            template=ctx.world.entity_templates.get("bullet", {}),
            viewport=ctx.world.viewport,
            entity_id=bullet_id,
            name="AlienBullet",
            owner="alien",
            overrides={
                "transform": {
                    "position": {
                        "x": sx + (sw / 2) - (spec.size.width / 2),
                        "y": sy + sh,
                    },
                    "size": {
                        "width": spec.size.width,
                        "height": spec.size.height,
                    },
                },
                "sprite": {"texture": spec.frames[0]},
                "kinematic": {
                    "velocity": {"vx": 0.0, "vy": spec.speed},
                    "max_speed": spec.speed,
                },
                "anim": {
                    "frames": list(spec.frames),
                    "fps": spec.fps,
                    "loop": True,
                },
            },
        )
        return bullet

    def _after_spawn(
        self,
        ctx: SpaceInvadersTickContext,
        spawned: tuple[BaseEntity, ...],
    ) -> None:
        ctx.world.bullets.extend(int(entity.id) for entity in spawned)

        shooter: Alien | None = None
        if self._pending_shooter_id is not None:
            shooter = ctx.world.get_entity_by_id(self._pending_shooter_id)
        if shooter is not None:
            shooter.fire_cd = random.uniform(0.8, 2.0)
            logger.critical(
                "Alien %s fired a bullet of kind %s from row %s, col %s",
                shooter.id,
                self._pending_kind,
                getattr(shooter, "row", "?"),
                getattr(shooter, "col", "?"),
            )
        self._clear_pending()

    def _clear_pending(self) -> None:
        self._pending_shooter_id = None
        self._pending_kind = None

    def _bottom_most_by_column(self, aliens: list[Alien]) -> list[Alien]:
        best: dict[int, Alien] = {}
        for a in aliens:
            if a.exploding:
                continue
            if a.fire_cd > 0.0:
                continue

            cur = best.get(a.col)
            if cur is None or a.row > cur.row:
                best[a.col] = a
        return list(best.values())

    def _infer_rows(self, aliens: list[Alien]) -> int:
        # rows count = max row index + 1
        return (max(a.row for a in aliens) + 1) if aliens else 0

    def _projectile_kind_for_row(
        self, row: int, total_rows: int
    ) -> ProjectileKind | None:
        if total_rows <= 0:
            return None

        # bottom 2 rows -> A
        if row >= total_rows - 2:
            return ProjectileKind.A

        # middle 2 rows -> B (only if exist)
        if total_rows >= 4 and row in (total_rows - 4, total_rows - 3):
            return ProjectileKind.B

        # top row -> C
        if row == 0:
            return ProjectileKind.C

        # fallback for “extra rows” if you add more later
        return ProjectileKind.B


@dataclass
class BulletMissileCollisionSystem:
    """Destroy opposing bullets and missiles when they intersect."""

    name: str = "space_invaders_bullet_missile_collision"
    phase: int = SystemPhase.SIMULATION
    order: int = 41  # before missile/alien collisions

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.bullets or not w.missiles:
            return

        def _on_collision(bullet: BaseEntity, missile: BaseEntity) -> None:
            mark_entity_dead(bullet)
            mark_entity_dead(missile)

            bx, by = bullet.transform.center.to_tuple()
            spawn_effect(
                w,
                getattr(w, "fx_enemy_proj_tex", None),
                bx - 8,
                by - 8,
                24,
                24,
                ttl=float(getattr(w, "fx_ttl", 0.12)),
            )

        _pairwise_collisions(
            sources=_alive_bullets(ctx, owner="ship"),
            targets=_alive_missiles(ctx),
            on_collision=_on_collision,
        )

        # Dedicated cleanup systems compact tracked ids and remove dead entities.


@dataclass
class BulletSpawnSystem:
    """
    Spawn bullets from ship intent (SPACE).
    Uses a simple cooldown timer.
    """

    name: str = "space_invaders_bullet_spawn"
    phase: int = SystemPhase.CONTROL
    order: int = 25
    _spawn: SpawnSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._spawn = SpawnSystem(
            name=self.name,
            phase=self.phase,
            order=self.order,
            bindings=(
                SpawnBinding(
                    should_spawn=self._should_spawn,
                    spawn=self._spawn_bullet,
                    on_spawned=self._after_spawn,
                ),
            ),
        )

    @staticmethod
    def _should_spawn(ctx: SpaceInvadersTickContext) -> bool:
        if ctx.intent is None:
            return False
        if is_round_locked(ctx.world):
            return False
        if not ctx.intent.fire_bullet:
            return False
        if ctx.world.ship_fire_timer > 0:
            return False
        ship = ctx.world.ship()
        if ship is None:
            return False
        return not getattr(ship, "exploding", False) and ship.anim is None

    @staticmethod
    def _spawn_bullet(
        ctx: SpaceInvadersTickContext,
    ) -> Bullet | None:
        bullet_template = ctx.world.entity_templates.get("bullet", {})
        ship = ctx.world.ship()
        if ship is None:
            return None
        sx, sy = ship.transform.center.to_tuple()

        id_start = ctx.world.allocate_entity_id_for("bullet")
        if id_start is None:
            return None

        bullet = Bullet.build_from_template(
            template=bullet_template,
            viewport=ctx.world.viewport,
            entity_id=id_start,
            name=str(bullet_template.get("name", "Bullet")),
            owner="ship",
            overrides={
                "transform": {"position": {"x": sx, "y": sy}},
                "sprite": {"texture": ctx.world.bullet_texture},
            },
        )
        bw = bullet.transform.size.width
        bh = bullet.transform.size.height
        bullet.transform.center = Vec2(
            sx + (ship.transform.size.width / 2) - (bw / 2), sy - bh
        )
        bullet.kinematic.velocity.y = -abs(bullet.kinematic.max_speed)
        return bullet

    @staticmethod
    def _after_spawn(
        ctx: SpaceInvadersTickContext,
        spawned: tuple[BaseEntity, ...],
    ) -> None:
        ctx.world.bullets.extend(int(entity.id) for entity in spawned)
        ctx.world.ship_fire_timer = ctx.world.ship_fire_cooldown

    def step(self, ctx: SpaceInvadersTickContext):
        if ctx.intent is None:
            return
        if is_round_locked(ctx.world):
            return

        # tick cooldown timer
        if ctx.world.ship_fire_timer > 0:
            ctx.world.ship_fire_timer = max(
                0.0, ctx.world.ship_fire_timer - ctx.dt
            )

        self._spawn.step(ctx)


@dataclass
class OmegaRaySystem:
    """Charge and fire the player omega beam attack."""

    name: str = "space_invaders_omega_ray"
    phase: int = SystemPhase.CONTROL
    order: int = 33

    charge_time: float = 0.8
    fire_time: float = 1.2

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if is_round_locked(w):
            w.omega_active = False
            w.omega_timer = 0.0
            w.omega_charge_timer = 0.0
            w.omega_x = None
            return

        # update anims always
        if w.omega_charge_anim:
            w.omega_charge_anim.update(ctx.dt)
        if w.omega_beam_anim:
            w.omega_beam_anim.update(ctx.dt)
        if w.omega_beam_large_anim:
            w.omega_beam_large_anim.update(ctx.dt)

        # tick cooldown
        if w.omega_cd_timer > 0:
            w.omega_cd_timer = max(0.0, w.omega_cd_timer - ctx.dt)

        # active beam
        if w.omega_active:
            w.omega_timer -= ctx.dt
            if w.omega_timer <= 0:
                w.omega_active = False
                w.omega_x = None
                w.omega_cd_timer = w.omega_cooldown
            return

        # charging
        if w.omega_charge_timer > 0:
            w.omega_charge_timer -= ctx.dt
            if w.omega_charge_timer <= 0:
                w.omega_active = True
                w.omega_timer = self.fire_time
            return

        # start charge on O press
        if ctx.intent is None or not ctx.intent.fire_omega_ray:
            return

        if w.omega_cd_timer > 0:
            return  # still cooling down

        # lock beam x from ship center
        ship: Ship | None = w.ship()
        if ship is None:
            return
        if getattr(ship, "exploding", False) or ship.anim is not None:
            return
        sx, _ = ship.transform.center.to_tuple()
        sw, _ = ship.transform.size.to_tuple()

        beam_w = float(w.omega_width)
        beam_x = (sx + sw / 2.0) - (beam_w / 2.0)

        w.omega_x = beam_x
        w.omega_charge_timer = self.charge_time


@dataclass
class BulletMotionBundle(SystemBundle[SpaceInvadersTickContext]):
    """Bundle of processors that integrate bullet motion."""

    _motion: KinematicMotionSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._motion = KinematicMotionSystem(
            bindings=(
                MotionBinding(
                    entities_getter=_bullet_entities,
                    predicate=lambda _ctx, bullet: (
                        bullet.life is None or bullet.life.alive
                    ),
                ),
            ),
        )

    def iter_systems(self) -> Iterable[object]:
        return (self._motion,)


ShipSystem = ShipMovementBundle
BulletMoveSystem = BulletMotionBundle


@dataclass
class BulletAnimationSystem:
    """Advance projectile animations and mirror the current texture."""

    name: str = "space_invaders_bullet_anim"
    phase: int = SystemPhase.PRESENTATION
    order: int = 38

    def step(self, ctx: SpaceInvadersTickContext):
        bullets = ctx.world.bullet_entities()
        for b in bullets:
            if not b.life.alive:
                continue
            if b.anim:
                b.anim.step(ctx.dt)
                b.sprite.texture = b.anim.texture


@dataclass
class BulletAlienCollisionSystem:
    """Kills aliens hit by ship bullets and removes the bullet."""

    name: str = "space_invaders_bullet_alien_collision"
    phase: int = SystemPhase.SIMULATION
    order: int = 45
    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        aliens = ctx.world.aliens()
        if not ctx.world.bullets or not aliens:
            return

        def _on_collision(bullet: BaseEntity, alien: BaseEntity) -> None:
            mark_entity_dead(bullet)
            setattr(alien, "exploding", True)
            setattr(alien, "explode_timer", self.explosion_time)
            ctx.world.score += alien_points(alien)

        _pairwise_collisions(
            sources=_alive_bullets(ctx, owner="ship"),
            targets=aliens,
            target_filter=lambda alien: not getattr(alien, "exploding", False),
            on_collision=_on_collision,
        )


@dataclass
class BulletShelterCollisionSystem:
    """Apply shelter damage and bullet cleanup on projectile impact."""

    name: str = "space_invaders_bullet_shelter_collision"
    phase: int = SystemPhase.SIMULATION
    order: int = 43  # before alien collisions (45) is fine
    max_damage: int = 9
    destroy_on_max: bool = False  # set True if you want it to disappear at 9

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.bullets:
            return

        shelters = w.shelters()
        if not shelters:
            return

        dead_shelter_ids: set[int] = set()

        def _on_collision(bullet: BaseEntity, shelter: BaseEntity) -> None:
            owner = getattr(bullet, "owner", None)
            if owner not in ("alien", "ship"):
                return

            mark_entity_dead(bullet)

            bx, by = bullet.transform.center.to_tuple()
            fx_tex = (
                getattr(w, "fx_player_proj_tex", None)
                if owner == "ship"
                else getattr(w, "fx_enemy_proj_tex", None)
            )
            spawn_effect(
                w,
                fx_tex,
                bx - 8,
                by - 8,
                24,
                24,
                ttl=float(getattr(w, "fx_ttl", 0.12)),
            )

            damage = int(getattr(shelter, "damage", 0))
            if damage < self.max_damage:
                damage += 1
            shelter.damage = damage

            tex_damaged = getattr(shelter, "tex_damaged", []) or []
            if shelter.sprite is not None:
                if damage > 0 and tex_damaged:
                    idx = min(damage, len(tex_damaged)) - 1
                    shelter.sprite.texture = tex_damaged[idx]
                elif getattr(shelter, "tex_full", None) is not None:
                    shelter.sprite.texture = shelter.tex_full

            if self.destroy_on_max and damage >= self.max_damage:
                dead_shelter_ids.add(shelter.id)

        _pairwise_collisions(
            sources=_alive_bullets(ctx),
            targets=shelters,
            target_filter=lambda shelter: shelter.id not in dead_shelter_ids,
            on_collision=_on_collision,
        )

        if dead_shelter_ids:
            w.remove_entities_by_ids(dead_shelter_ids)


@dataclass
class BulletShieldCollisionSystem:
    """Consume enemy bullets that intersect the active player shield."""

    name: str = "space_invaders_bullet_shield_collision"
    phase: int = SystemPhase.SIMULATION
    order: int = 44  # after shelter collision, before ship hit

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.shield_active or not w.bullets:
            return
        if is_round_locked(w):
            return

        ship: Ship | None = w.ship()
        if ship is None:
            return
        if getattr(ship, "exploding", False) or ship.anim is not None:
            return
        sx, sy = ship.transform.center.to_tuple()
        sw, sh = ship.transform.size.to_tuple()

        scale = float(getattr(w, "shield_scale", 1.35))
        shield_w = sw * scale
        shield_h = sh * scale
        shield_x = sx + sw / 2 - shield_w / 2
        shield_y = sy + sh / 2 - shield_h / 2

        for bullet in _alive_bullets(ctx, owner="alien"):
            bx, by = bullet.transform.center.to_tuple()
            bw, bh = bullet.transform.size.to_tuple()
            if not rect_rect(
                ax=shield_x,
                ay=shield_y,
                aw=shield_w,
                ah=shield_h,
                bx=bx,
                by=by,
                bw=bw,
                bh=bh,
                inclusive=True,
            ):
                continue
            mark_entity_dead(bullet)
            spawn_effect(
                w,
                getattr(w, "fx_enemy_proj_tex", None),
                bx - 8,
                by - 8,
                24,
                24,
                ttl=float(getattr(w, "fx_ttl", 0.12)),
            )


@dataclass
class BulletShipCollisionSystem:
    """Handle enemy bullet hits on the player ship when unshielded."""

    name: str = "space_invaders_bullet_ship_collision"
    phase: int = SystemPhase.SIMULATION
    order: int = 45  # after shield collision

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if is_round_locked(w):
            return
        ship: Ship | None = w.ship()
        if ship is None or not w.bullets:
            return
        if getattr(ship, "exploding", False) or ship.anim is not None:
            return
        if getattr(w, "shield_active", False):
            return  # shield handles it

        def _on_collision(_bullet: BaseEntity, _ship: BaseEntity) -> None:
            mark_entity_dead(_bullet)
            ship.exploding = True
            w.lives = max(0, int(w.lives) - 1)
            if w.lives <= 0:
                w.game_over = True
                w.missile_targeting = False
            Ship.start_explosion(ship, ship.ship_explosion_frames)

        _pairwise_collisions(
            sources=_alive_bullets(ctx, owner="alien"),
            targets=(ship,),
            on_collision=_on_collision,
            stop_after_source_hit=True,
        )


@dataclass
class MissileHomingSystem:
    """Steer live missiles toward their assigned alien targets."""

    name: str = "space_invaders_missile_homing"
    phase: int = SystemPhase.SIMULATION
    order: int = 40

    def step(self, ctx: SpaceInvadersTickContext):
        # TODO: Move seek/steering into a built-in target-follow motion system.
        w = ctx.world
        if not w.missiles:
            return

        aliens = w.aliens()
        alive_by_id: dict[int, Alien] = {
            a.id: a for a in aliens if not getattr(a, "exploding", False)
        }

        for m in _alive_missiles(ctx):
            if m.life is None or not m.life.alive:
                continue

            # animate
            if m.anim:
                m.anim.step(ctx.dt)
                if m.sprite and m.anim.texture is not None:
                    m.sprite.texture = m.anim.texture

            target_id = getattr(m, "target_id", None)
            target = alive_by_id.get(target_id) if target_id else None

            if target is not None:
                tx, ty = target.transform.center.to_tuple()
                tw, th = target.transform.size.to_tuple()
                target_cx = tx + tw / 2
                target_cy = ty + th / 2

                mx, my = m.transform.center.to_tuple()
                mcx = mx + m.transform.size.width / 2
                mcy = my + m.transform.size.height / 2

                dx = target_cx - mcx
                dy = target_cy - mcy
                dist2 = dx * dx + dy * dy

                if dist2 > 0.0001:
                    dist = dist2**0.5
                    speed = float(getattr(m, "speed", 420.0))
                    vx = (dx / dist) * speed
                    vy = (dy / dist) * speed
                    if m.kinematic:
                        m.kinematic.velocity.x = vx
                        m.kinematic.velocity.y = vy
                    # Keep heading available for render backends that support rotation.
                    m.rotation_deg = math.degrees(math.atan2(vy, vx)) + 90.0
            elif m.life is not None:
                mark_entity_dead(m)
                continue

            if m.kinematic:
                m.kinematic.step(m.transform, ctx.dt)


@dataclass
class MissileAlienCollisionSystem:
    """Resolve missile impacts against their targeted aliens."""

    name: str = "space_invaders_missile_alien_collision"
    phase: int = SystemPhase.SIMULATION
    order: int = 45  # same zone as other collisions
    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missiles:
            return

        aliens = w.aliens()
        # alive aliens by id (skip exploding)
        alive_by_id: dict[int, Alien] = {
            a.id: a for a in aliens if not getattr(a, "exploding", False)
        }

        for missile in _alive_missiles(ctx):
            target_id = getattr(missile, "target_id", None)
            if target_id is None:
                continue

            target = alive_by_id.get(target_id)
            if target is None:
                mark_entity_dead(missile)
                continue

            if not intersects_entities(missile, target):
                continue
            mark_entity_dead(missile)
            target.exploding = True
            target.explode_timer = self.explosion_time
            w.score += alien_points(target)


@dataclass
class UfoCollisionSystem:
    """Handle collisions between UFO and ship projectiles."""

    name: str = "space_invaders_ufo_collision"
    phase: int = SystemPhase.SIMULATION
    order: int = 45

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        ufo: Ufo | None = w.ufo()
        if ufo is None:
            return
        if ufo.life is not None and not ufo.life.alive:
            return

        hit = False

        for bullet in _alive_bullets(ctx, owner="ship"):
            if not intersects_entities(bullet, ufo):
                continue
            mark_entity_dead(bullet)
            hit = True
            break

        if not hit:
            for missile in _alive_missiles(ctx):
                if not intersects_entities(missile, ufo):
                    continue
                mark_entity_dead(missile)
                hit = True
                break

        if not hit:
            return

        w.score += int(getattr(ufo, "points", w.ufo_points))
        ux, uy = ufo.transform.center.to_tuple()
        uw, uh = ufo.transform.size.to_tuple()
        spawn_effect(
            w,
            getattr(w, "explosion_texture", None),
            ux + (uw * 0.5) - 12,
            uy + (uh * 0.5) - 12,
            24,
            24,
            ttl=float(getattr(w, "fx_ttl", 0.12)),
        )

        w.remove_entities_by_ids({int(EntityId.UFO)})

        w.ufo_spawn_timer = random.uniform(w.ufo_spawn_min, w.ufo_spawn_max)


@dataclass
class MissileCullSystem:
    """Cull missiles that leave the viewport and mark them dead."""

    name: str = "space_invaders_missile_cull"
    phase: int = SystemPhase.SIMULATION
    order: int = 47
    _constraints: ProjectileBoundarySystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._constraints = ProjectileBoundarySystem(
            name=self.name,
            phase=self.phase,
            order=self.order,
            bindings=(
                ProjectileBoundaryBinding(
                    entities_getter=_missile_entities,
                    on_cull=lambda _ctx, missile: (
                        setattr(missile.life, "alive", False)
                        if missile.life is not None
                        else None
                    ),
                ),
            ),
        )

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missiles:
            return
        self._constraints.step(ctx)


@dataclass
class MissileCleanupSystem:
    """Compacts tracked missile ids and removes dead missile entities."""

    name: str = "space_invaders_missile_cleanup"
    phase: int = SystemPhase.SIMULATION
    order: int = 48
    _cleanup: ProjectileCleanupSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._cleanup = ProjectileCleanupSystem(
            name=self.name,
            phase=self.phase,
            order=self.order,
            bindings=(
                ProjectileCleanupBinding(
                    entities_getter=_missile_entities,
                    keep_entity=is_entity_alive,
                    tracked_ids_attr="missiles",
                    tracked_domain_name="missile",
                ),
            ),
        )

    def step(self, ctx: SpaceInvadersTickContext) -> None:
        if not ctx.world.missiles:
            return
        self._cleanup.step(ctx)


@dataclass
class OmegaRayDamageSystem:
    """Apply omega beam damage to aliens and the UFO."""

    name: str = "space_invaders_omega_damage"
    phase: int = SystemPhase.SIMULATION
    order: int = 44  # before ExplosionSystem (46) is perfect

    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.omega_active or w.omega_x is None:
            return
        aliens = w.aliens()
        if not aliens:
            return

        # Beam rect: from top of screen to top of ship
        ship: Ship | None = w.ship()
        if ship is None:
            return
        _, sy = ship.transform.center.to_tuple()

        beam_x = float(w.omega_x)
        beam_w = float(w.omega_width)
        beam_h = float(max(0.0, sy))  # 0..ship_top

        if beam_h <= 0:
            return

        # Kill all aliens intersecting the beam
        for a in aliens:
            if getattr(a, "exploding", False):
                continue
            ax, ay = a.transform.center.to_tuple()
            aw, ah = a.transform.size.to_tuple()
            if rect_rect(
                ax=beam_x,
                ay=0.0,
                aw=beam_w,
                ah=beam_h,
                bx=ax,
                by=ay,
                bw=aw,
                bh=ah,
                inclusive=True,
            ):
                a.exploding = True
                a.explode_timer = self.explosion_time
                w.score += alien_points(a)

        ufo: Ufo | None = w.ufo()
        if ufo is None:
            return
        ux, uy = ufo.transform.center.to_tuple()
        uw, uh = ufo.transform.size.to_tuple()
        if rect_rect(
            ax=beam_x,
            ay=0.0,
            aw=beam_w,
            ah=beam_h,
            bx=ux,
            by=uy,
            bw=uw,
            bh=uh,
            inclusive=True,
        ):
            w.score += int(getattr(ufo, "points", w.ufo_points))
            w.remove_entities_by_ids({int(EntityId.UFO)})
            w.ufo_spawn_timer = random.uniform(
                w.ufo_spawn_min, w.ufo_spawn_max
            )


@dataclass
class ExplosionSystem:
    """Expire alien explosion timers and remove finished explosions."""

    name: str = "space_invaders_explosions"
    phase: int = SystemPhase.SIMULATION
    order: int = 46  # after collision

    def step(self, ctx: SpaceInvadersTickContext):
        aliens = ctx.world.aliens()
        if not aliens:
            return

        dead_alien_ids: set[int] = set()
        for a in aliens:
            if not getattr(a, "exploding", False):
                continue
            a.explode_timer = max(0.0, a.explode_timer - ctx.dt)
            if a.explode_timer <= 0.0:
                dead_alien_ids.add(a.id)

        if dead_alien_ids:
            ctx.world.remove_entities_by_ids(dead_alien_ids)


@dataclass
class BulletCullSystem:
    """Removes bullets that are dead or out of viewport."""

    name: str = "space_invaders_bullet_cull"
    phase: int = SystemPhase.SIMULATION
    order: int = 36
    _constraints: ProjectileBoundarySystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._constraints = ProjectileBoundarySystem(
            name=self.name,
            phase=self.phase,
            order=self.order,
            bindings=(
                ProjectileBoundaryBinding(
                    entities_getter=_bullet_entities,
                    on_cull=lambda _ctx, bullet: (
                        setattr(bullet.life, "alive", False)
                        if bullet.life is not None
                        else None
                    ),
                ),
            ),
        )

    def step(self, ctx: SpaceInvadersTickContext):
        self._constraints.step(ctx)


@dataclass
class BulletCleanupSystem:
    """Compacts tracked bullet ids and removes dead bullet entities."""

    name: str = "space_invaders_bullet_cleanup"
    phase: int = SystemPhase.SIMULATION
    order: int = 46
    _cleanup: ProjectileCleanupSystem[SpaceInvadersTickContext] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self._cleanup = ProjectileCleanupSystem(
            name=self.name,
            phase=self.phase,
            order=self.order,
            bindings=(
                ProjectileCleanupBinding(
                    entities_getter=_bullet_entities,
                    keep_entity=is_entity_alive,
                    tracked_ids_attr="bullets",
                    tracked_domain_name="bullet",
                ),
            ),
        )

    def step(self, ctx: SpaceInvadersTickContext) -> None:
        if not ctx.world.bullets:
            return
        self._cleanup.step(ctx)


@dataclass
class BulletBulletCollisionSystem:
    """Destroy colliding player and alien bullets."""

    name: str = "space_invaders_bullet_bullet_collision"
    phase: int = SystemPhase.SIMULATION
    order: int = 42

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.bullets:
            return
        if is_round_locked(w):
            return

        ship_bullets = list(_alive_bullets(ctx, owner="ship"))
        alien_bullets = list(_alive_bullets(ctx, owner="alien"))
        if not ship_bullets or not alien_bullets:
            return

        def _on_collision(
            ship_bullet: BaseEntity, alien_bullet: BaseEntity
        ) -> None:
            mark_entity_dead(ship_bullet)
            mark_entity_dead(alien_bullet)
            x, y = ship_bullet.transform.center.to_tuple()
            spawn_effect(
                w,
                getattr(w, "fx_enemy_proj_tex", None),
                x - 8,
                y - 8,
                24,
                24,
                ttl=float(getattr(w, "fx_ttl", 0.12)),
            )

        _pairwise_collisions(
            sources=ship_bullets,
            targets=alien_bullets,
            on_collision=_on_collision,
        )


@dataclass
class EffectsSystem:
    """Tick transient non-entity effects and discard expired entries."""

    name: str = "space_invaders_effects"
    phase: int = SystemPhase.PRESENTATION
    order: int = 90  # before render

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.effects:
            return

        alive: list[Effect] = []
        for e in w.effects:
            if not e.alive:
                continue
            e.ttl -= ctx.dt
            if e.ttl > 0:
                alive.append(e)

        w.effects = alive


@dataclass
class RoundStateSystem:
    """Detect victory or defeat conditions for the current round."""

    name: str = "space_invaders_round_state"
    phase: int = SystemPhase.SIMULATION
    order: int = 88

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if w.game_over:
            return
        if w.victory:
            return
        aliens = w.aliens()
        if not aliens:
            w.victory = True
            w.missile_targeting = False
            return

        _, vh = w.viewport
        ship: Ship | None = w.ship()
        ship_hit = False
        alien_reached_bottom = False

        for alien in aliens:
            _, ay = alien.transform.center.to_tuple()
            _, ah = alien.transform.size.to_tuple()
            if ay + ah >= vh:
                alien_reached_bottom = True
                break
            if ship is not None and intersects_entities(alien, ship):
                ship_hit = True
                break

        if alien_reached_bottom or ship_hit:
            w.game_over = True
            w.missile_targeting = False
