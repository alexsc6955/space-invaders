"""
Space Invaders Scene Systems
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from mini_arcade_core.backend.keys import Key
from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.engine.components import Anim2D
from mini_arcade_core.runtime.services import RuntimeServices
from mini_arcade_core.scenes.sim_scene import DrawCall
from mini_arcade_core.scenes.systems.builtins import (
    ActionIntentSystem,
    ActionMap,
    AxisActionBinding,
    BaseQueuedRenderSystem,
    CaptureHotkeysConfig,
    CaptureHotkeysSystem,
    DigitalActionBinding,
)
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
from space_invaders.scenes.commands import PauseSpaceInvadersCommand
from space_invaders.scenes.space_invaders.helpers import (
    alien_points,
    alloc_entity_id_in_range,
    is_round_locked,
    spawn_effect,
)
from space_invaders.scenes.space_invaders.draw_ops import (
    DrawEffects,
    DrawMissileTarget,
    DrawOmegaRay,
    DrawRegionTint,
    DrawShieldOverlay,
)
from space_invaders.scenes.space_invaders.models import (
    SpaceInvadersIntent,
    SpaceInvadersTickContext,
)


SPACE_INVADERS_ACTIONS = ActionMap(
    bindings={
        "move_ship_x": AxisActionBinding(
            positive_keys=(Key.RIGHT,),
            negative_keys=(Key.LEFT,),
        ),
        "fire_bullet": DigitalActionBinding(keys=(Key.SPACE,)),
        "fire_omega_ray": DigitalActionBinding(keys=(Key.O,)),
        "toggle_missile_target": DigitalActionBinding(keys=(Key.T,)),
        "missile_target_left": DigitalActionBinding(keys=(Key.A,)),
        "missile_target_right": DigitalActionBinding(keys=(Key.D,)),
        "missile_target_up": DigitalActionBinding(keys=(Key.W,)),
        "missile_target_down": DigitalActionBinding(keys=(Key.S,)),
        "missile_launch": DigitalActionBinding(keys=(Key.M,)),
        "shield_toggle": DigitalActionBinding(keys=(Key.C,)),
        "ship_kill_switch": DigitalActionBinding(keys=(Key.K,)),
        "pause": DigitalActionBinding(keys=(Key.ESCAPE,)),
        "capture_toggle_video": DigitalActionBinding(keys=(Key.R,)),
    }
)


def _build_space_invaders_intent(
    actions,
    _ctx: SpaceInvadersTickContext,
) -> SpaceInvadersIntent:
    move = actions.value("move_ship_x")
    return SpaceInvadersIntent(
        move_ship_left=max(0.0, -move),
        move_ship_right=max(0.0, move),
        fire_bullet=actions.pressed("fire_bullet"),
        fire_omega_ray=actions.pressed("fire_omega_ray"),
        toggle_missile_target=actions.pressed("toggle_missile_target"),
        missile_target_left=actions.pressed("missile_target_left"),
        missile_target_right=actions.pressed("missile_target_right"),
        missile_target_up=actions.pressed("missile_target_up"),
        missile_target_down=actions.pressed("missile_target_down"),
        missile_launch=actions.pressed("missile_launch"),
        shield_toggle=actions.pressed("shield_toggle"),
        pause=actions.pressed("pause"),
        ship_kill_switch=actions.pressed("ship_kill_switch"),
        toggle_video_recording=actions.pressed("capture_toggle_video"),
    )


class SpaceInvadersInputSystem(
    ActionIntentSystem[SpaceInvadersTickContext, SpaceInvadersIntent]
):
    """
    Process input and update intent.
    """

    def __init__(self):
        super().__init__(
            action_map=SPACE_INVADERS_ACTIONS,
            intent_factory=_build_space_invaders_intent,
            name="space_invaders_input",
        )


@dataclass
class SpaceInvadersPauseSystem:
    """Push pause scene when ESC is pressed."""

    name: str = "space_invaders_pause"
    order: int = 12

    def step(self, ctx: SpaceInvadersTickContext):
        if ctx.intent is None or not ctx.intent.pause:
            return
        ctx.commands.push(PauseSpaceInvadersCommand())


@dataclass
class SpaceInvadersHotkeysSystem:
    """Handles one-shot hotkeys (trail toggle, screenshot, etc.)."""

    name: str = "space_invaders_hotkeys"
    order: int = 13  # after pause (12) or right after input (10/11)

    def step(
        self, ctx: SpaceInvadersTickContext
    ):  # pylint: disable=too-many-branches
        """Execute hotkey commands based on intent."""
        if ctx.intent is None:
            return

        # TODO: Move this to a debug or misc system if it grows,
        # or if we add more hotkeys. For now it's fine here.
        ship: Ship = ctx.world.get_entity_by_id(EntityId.SHIP)
        if ctx.intent.ship_kill_switch:
            ship.exploding = True
            Ship.start_explosion(ship, ship.ship_explosion_frames)

        if ship.anim:
            ship.anim.step(ctx.dt)
        if ship.life:
            ship.life.step(ctx.dt)
            if not ship.life.alive:
                ship.anim = None
                ship.life = None
                ship.exploding = False


def build_space_invaders_capture_hotkeys_system(
    services: RuntimeServices,
) -> CaptureHotkeysSystem:
    """
    Shared capture bindings for Space Invaders.
    """
    return CaptureHotkeysSystem(
        services=services,
        action_map=SPACE_INVADERS_ACTIONS,
        cfg=CaptureHotkeysConfig(
            screenshot_label=None,
            replay_file=None,
            action_toggle_video="capture_toggle_video",
        ),
    )


@dataclass
class ShieldSystem:
    name: str = "space_invaders_shield"
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
    name: str = "space_invaders_missile_target"
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

        aliens: list[Alien] = w.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
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
class ShipSystem:
    """
    Move ship based on intent.
    """

    name: str = "space_invaders_ship"
    order: int = 20

    def step(self, ctx: SpaceInvadersTickContext):
        """Move ship based on intent."""

        if ctx.intent is None:
            return
        if is_round_locked(ctx.world):
            return

        vw, _ = ctx.world.viewport
        ship = ctx.world.get_entity_by_id(EntityId.SHIP)
        if ship is None:
            return
        if getattr(ship, "exploding", False) or ship.anim is not None:
            return

        move_x = ctx.intent.move_ship_right - ctx.intent.move_ship_left
        ship.kinematic.velocity.x = move_x * ship.kinematic.max_speed
        ship.kinematic.velocity.y = 0.0

        # move first
        ship.kinematic.step(ship.transform, ctx.dt)

        # clamp using UPDATED position
        x, y = ship.transform.center.to_tuple()
        x = max(0.0, min(vw - ship.transform.size.width, x))

        # set position (your setter keeps center in sync)
        ship.transform.center = Vec2(x, y)


@dataclass
class UfoSystem:
    """Spawn and move the periodic UFO bonus ship."""

    name: str = "space_invaders_ufo"
    order: int = 24

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        vw, _ = w.viewport
        ufo: Ufo | None = w.get_entity_by_id(EntityId.UFO)

        if is_round_locked(w):
            if ufo is not None:
                w.entities = [e for e in w.entities if e.id != EntityId.UFO]
            return

        if ufo is None:
            w.ufo_spawn_timer = max(0.0, float(w.ufo_spawn_timer) - ctx.dt)
            if w.ufo_spawn_timer > 0 or w.ufo_texture is None:
                return

            direction = random.choice((-1.0, 1.0))
            width = 48.0
            x = -width if direction > 0 else vw + width
            y = 36.0
            ufo = Ufo.build(
                EntityId.UFO,
                x=x,
                y=y,
                texture=w.ufo_texture,
                travel_dir=direction,
            )
            ufo.points = int(w.ufo_points)
            if ufo.kinematic is not None:
                ufo.kinematic.max_speed = float(w.ufo_speed)
                ufo.kinematic.velocity.x = direction * float(w.ufo_speed)
            w.entities.append(ufo)
            w.ufo_spawn_timer = random.uniform(w.ufo_spawn_min, w.ufo_spawn_max)
            return

        if ufo.kinematic is None:
            return
        ufo.kinematic.velocity.x = float(ufo.travel_dir) * float(w.ufo_speed)
        ufo.kinematic.velocity.y = 0.0
        ufo.kinematic.step(ufo.transform, ctx.dt)

        ux = float(ufo.transform.center.x)
        uw = float(ufo.transform.size.width)
        if (ux + uw) < -64.0 or ux > (vw + 64.0):
            w.entities = [e for e in w.entities if e.id != EntityId.UFO]
            w.ufo_spawn_timer = random.uniform(w.ufo_spawn_min, w.ufo_spawn_max)


@dataclass
class MissileSpawnSystem:
    name: str = "space_invaders_missile_spawn"
    order: int = 26  # after ship system is fine

    missile_size: Size2D = Size2D(14, 22)

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        it = ctx.intent
        if it is None or not it.missile_launch:
            return
        if is_round_locked(w):
            return

        if not w.missile_targeting:
            return
        if w.missile_cd_timer > 0:
            return

        aliens: list[Alien] = w.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
        alive = [a for a in aliens if not getattr(a, "exploding", False)]
        if not alive:
            return
        if w.missile_target_idx is None:
            return

        target = alive[w.missile_target_idx]

        # spawn from ship top-center
        ship: Ship | None = w.get_entity_by_id(EntityId.SHIP)
        if ship is None:
            return
        if getattr(ship, "exploding", False) or ship.anim is not None:
            return
        sx, sy = ship.transform.center.to_tuple()
        sw, _ = ship.transform.size.to_tuple()

        mx = sx + sw / 2 - self.missile_size.width / 2
        my = sy - self.missile_size.height

        missile_id = alloc_entity_id_in_range(
            w, EntityId.MISSILE_START, EntityId.MISSILE_END
        )
        if missile_id is None:
            return

        missile_tex = (
            w.missile_anim.current_frame
            if w.missile_anim and len(w.missile_anim.frames) > 0
            else None
        )
        missile = Missile.build(
            entity_id=missile_id,
            name="Missile",
            x=mx,
            y=my,
            texture=missile_tex,
        )
        missile.transform.size = Size2D(
            self.missile_size.width, self.missile_size.height
        )
        missile.target_id = target.id
        missile.speed = 520.0
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

        w.entities.append(missile)
        w.missiles.append(missile.id)

        w.missile_cd_timer = w.missile_cooldown
        w.missile_targeting = False


@dataclass
class AlienSystem:
    """
    Move aliens as a formation:
    - Move horizontally
    - If any hits wall -> reverse direction and drop down
    """

    name: str = "space_invaders_aliens"
    order: int = 30

    drop_step: float = 18.0

    def step(self, ctx: SpaceInvadersTickContext):
        if is_round_locked(ctx.world):
            return
        vw, _ = ctx.world.viewport
        aliens = ctx.world.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
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
    name: str = "space_invaders_alien_anim"
    order: int = 28

    def step(self, ctx: SpaceInvadersTickContext):
        for e in ctx.world.entities:
            if EntityId.ALIEN_START <= e.id <= EntityId.ALIEN_END and e.anim:
                e.anim.step(ctx.dt)


@dataclass
class AlienFireSystem:
    name: str = "space_invaders_alien_fire"
    order: int = 32  # after AlienSystem movement is fine

    min_cooldown: float = 0.25
    max_cooldown: float = 1.10

    def step(self, ctx: SpaceInvadersTickContext):
        if is_round_locked(ctx.world):
            return
        aliens: list[Alien] = ctx.world.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
        if not aliens:
            return

        for a in aliens:
            if a.fire_cd > 0.0:
                a.fire_cd = max(0.0, a.fire_cd - ctx.dt)

        # tick timer
        ctx.world.alien_fire_timer -= ctx.dt
        if ctx.world.alien_fire_timer > 0:
            return

        # gate: limit how many active on-screen alien bullets can exist
        vw, vh = ctx.world.viewport
        active_alien_bullets = 0
        for bullet_id in ctx.world.bullets:
            b = ctx.world.get_entity_by_id(bullet_id)
            if b is None or b.owner != "alien":
                continue
            if b.life and not b.life.alive:
                continue
            x, y = b.transform.center.to_tuple()
            bw, bh = b.transform.size.to_tuple()
            if (y + bh) < 0 or y > vh or (x + bw) < 0 or x > vw:
                continue
            active_alien_bullets += 1
        if active_alien_bullets >= ctx.world.max_alien_bullets:
            # try again soon, but don't spam checks every frame
            ctx.world.alien_fire_timer = 0.15
            return

        # reset to a random next fire time
        ctx.world.alien_fire_timer = random.uniform(
            ctx.world.alien_fire_cooldown_min,
            ctx.world.alien_fire_cooldown_max,
        )

        # choose shooters = bottom-most alien per column (not exploding)
        shooters = self._bottom_most_by_column(aliens)
        if not shooters:
            return

        shooter = random.choice(shooters)

        kind = self._projectile_kind_for_row(
            shooter.row, total_rows=self._infer_rows(aliens)
        )
        if kind is None:
            return

        spec = ctx.world.projectile_specs.get(kind)
        if spec is None:
            return

        sx, sy = shooter.transform.center.to_tuple()
        sw, sh = shooter.transform.size.to_tuple()

        # spawn at bottom-center of alien
        bx = sx + (sw / 2) - (spec.size.width / 2)
        by = sy + sh

        start_id = alloc_entity_id_in_range(
            ctx.world, EntityId.BULLET_START, EntityId.BULLET_END
        )
        if start_id is None:
            return
        bullet = Bullet.build(
            start_id,
            "AlienBullet",
            x=bx,
            y=by,
            owner="alien",
            texture=spec.frames[0],
        )
        bullet.transform.size = Size2D(spec.size.width, spec.size.height)
        bullet.kinematic.velocity.y = spec.speed
        bullet.anim = Anim2D(
            anim=Animation(frames=list(spec.frames), fps=spec.fps, loop=True),
            texture=spec.frames[0],
        )
        ctx.world.entities.append(bullet)
        ctx.world.bullets.append(start_id)
        logger.critical(
            f"Alien {shooter.id} fired a bullet of kind {kind} from row {shooter.row}, col {shooter.col}"
        )
        shooter.fire_cd = random.uniform(0.8, 2.0)

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
    name: str = "space_invaders_bullet_missile_collision"
    order: int = 41  # before missile/alien collisions

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.bullets or not w.missiles:
            return

        dead_bullet_ids: set[int] = set()
        dead_missile_ids: set[int] = set()

        for bullet_id in w.bullets:
            b = w.get_entity_by_id(bullet_id)
            if b is None or b.life is None or not b.life.alive:
                continue
            if getattr(b, "owner", None) != "ship":
                continue

            for missile_id in w.missiles:
                m = w.get_entity_by_id(missile_id)
                if m is None or m.life is None or not m.life.alive:
                    continue

                if intersects_entities(b, m):
                    b.life.alive = False
                    m.life.alive = False
                    dead_bullet_ids.add(b.id)
                    dead_missile_ids.add(m.id)

                    bx, by = b.transform.center.to_tuple()
                    spawn_effect(
                        w,
                        getattr(w, "fx_enemy_proj_tex", None),
                        bx - 8,
                        by - 8,
                        24,
                        24,
                        ttl=float(getattr(w, "fx_ttl", 0.12)),
                    )
                    break

        if dead_bullet_ids:
            w.bullets = [
                bid for bid in w.bullets if bid not in dead_bullet_ids
            ]
        if dead_missile_ids:
            w.missiles = [
                mid for mid in w.missiles if mid not in dead_missile_ids
            ]
        if dead_bullet_ids or dead_missile_ids:
            dead_ids = dead_bullet_ids | dead_missile_ids
            w.entities = [e for e in w.entities if e.id not in dead_ids]


@dataclass
class BulletSpawnSystem:
    """
    Spawn bullets from ship intent (SPACE).
    Uses a simple cooldown timer.
    """

    name: str = "space_invaders_bullet_spawn"
    order: int = 25

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

        if not ctx.intent.fire_bullet:
            return

        # still cooling down
        if ctx.world.ship_fire_timer > 0:
            return

        ship = ctx.world.get_entity_by_id(EntityId.SHIP)
        if ship is None:
            return
        if getattr(ship, "exploding", False) or ship.anim is not None:
            return
        sx, sy = ship.transform.center.to_tuple()

        id_start = alloc_entity_id_in_range(
            ctx.world, EntityId.BULLET_START, EntityId.BULLET_END
        )
        if id_start is None:
            return

        bullet = Bullet.build(
            id_start,
            "Bullet",
            x=sx,
            y=sy,
            owner="ship",
            texture=ctx.world.bullet_texture,
        )
        bw = bullet.transform.size.width
        bh = bullet.transform.size.height
        bullet.transform.center = Vec2(
            sx + (ship.transform.size.width / 2) - (bw / 2), sy - bh
        )
        bullet.kinematic.velocity.y = -bullet.kinematic.max_speed  # upwards
        ctx.world.entities.append(bullet)
        ctx.world.bullets.append(bullet.id)

        # reset cooldown
        ctx.world.ship_fire_timer = ctx.world.ship_fire_cooldown


@dataclass
class OmegaRaySystem:
    name: str = "space_invaders_omega_ray"
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
        ship: Ship | None = w.get_entity_by_id(EntityId.SHIP)
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
class BulletMoveSystem:
    """Moves all bullets using Velocity2D.advance."""

    name: str = "space_invaders_bullet_move"
    order: int = 35

    def step(self, ctx: SpaceInvadersTickContext):
        if not ctx.world.bullets:
            return

        for b in ctx.world.bullets:
            bullet = ctx.world.get_entity_by_id(b)
            if bullet is None:
                continue
            if bullet.life is not None and not bullet.life.alive:
                continue
            bullet.kinematic.step(bullet.transform, ctx.dt)


@dataclass
class BulletAnimationSystem:
    name: str = "space_invaders_bullet_anim"
    order: int = 38

    def step(self, ctx: SpaceInvadersTickContext):
        bullets: list[Bullet] = ctx.world.get_entities_by_id_range(
            EntityId.BULLET_START, EntityId.BULLET_END
        )
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
    order: int = 45
    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        bullets: list[Bullet] = ctx.world.get_entities_by_id_range(
            EntityId.BULLET_START, EntityId.BULLET_END
        )
        aliens: list[Alien] = ctx.world.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
        if not bullets or not aliens:
            return

        dead_bullet_ids: set[int] = set()

        for b in bullets:
            if b.life is None or not b.life.alive:
                continue
            if getattr(b, "owner", None) != "ship":
                continue

            for a in aliens:
                if getattr(a, "exploding", False):
                    continue  # already dying

                if intersects_entities(b, a):
                    b.life.alive = False
                    dead_bullet_ids.add(b.id)
                    a.exploding = True
                    a.explode_timer = self.explosion_time
                    ctx.world.score += alien_points(a)
                    break

        if dead_bullet_ids:
            ctx.world.bullets = [
                bid for bid in ctx.world.bullets if bid not in dead_bullet_ids
            ]
            ctx.world.entities = [
                e for e in ctx.world.entities if e.id not in dead_bullet_ids
            ]


@dataclass
class BulletShelterCollisionSystem:
    name: str = "space_invaders_bullet_shelter_collision"
    order: int = 43  # before alien collisions (45) is fine
    max_damage: int = 9
    destroy_on_max: bool = False  # set True if you want it to disappear at 9

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.bullets:
            return

        shelters: list[Shelter] = w.get_entities_by_id_range(
            EntityId.SHELTER_START, EntityId.SHELTER_END
        )
        if not shelters:
            return

        dead_bullet_ids: set[int] = set()
        dead_shelter_ids: set[int] = set()

        for bullet_id in w.bullets:
            b = w.get_entity_by_id(bullet_id)
            if b is None:
                continue
            if b.life is None or not b.life.alive:
                continue
            owner = getattr(b, "owner", None)
            if owner not in ("alien", "ship"):
                continue

            for s in shelters:
                if s.id in dead_shelter_ids:
                    continue

                if intersects_entities(b, s):
                    b.life.alive = False
                    dead_bullet_ids.add(b.id)

                    bx, by = b.transform.center.to_tuple()
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

                    damage = int(getattr(s, "damage", 0))
                    if damage < self.max_damage:
                        damage += 1
                    s.damage = damage

                    tex_damaged = getattr(s, "tex_damaged", []) or []
                    if s.sprite is not None:
                        if damage > 0 and tex_damaged:
                            idx = min(damage, len(tex_damaged)) - 1
                            s.sprite.texture = tex_damaged[idx]
                        elif getattr(s, "tex_full", None) is not None:
                            s.sprite.texture = s.tex_full

                    if self.destroy_on_max and damage >= self.max_damage:
                        dead_shelter_ids.add(s.id)
                    break

        if dead_bullet_ids:
            w.bullets = [
                bid for bid in w.bullets if bid not in dead_bullet_ids
            ]
            w.entities = [e for e in w.entities if e.id not in dead_bullet_ids]

        if dead_shelter_ids:
            w.entities = [
                e for e in w.entities if e.id not in dead_shelter_ids
            ]


@dataclass
class BulletShieldCollisionSystem:
    name: str = "space_invaders_bullet_shield_collision"
    order: int = 44  # after shelter collision, before ship hit

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.shield_active or not w.bullets:
            return
        if is_round_locked(w):
            return

        ship: Ship | None = w.get_entity_by_id(EntityId.SHIP)
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

        dead_bullet_ids: set[int] = set()

        for bullet_id in w.bullets:
            b = w.get_entity_by_id(bullet_id)
            if b is None:
                continue
            if b.life is None or not b.life.alive:
                continue
            if getattr(b, "owner", None) != "alien":
                continue
            bx, by = b.transform.center.to_tuple()
            bw, bh = b.transform.size.to_tuple()
            if rect_rect(
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
                b.life.alive = False
                dead_bullet_ids.add(b.id)
                spawn_effect(
                    w,
                    getattr(w, "fx_enemy_proj_tex", None),
                    bx - 8,
                    by - 8,
                    24,
                    24,
                    ttl=float(getattr(w, "fx_ttl", 0.12)),
                )

        if dead_bullet_ids:
            w.bullets = [
                bid for bid in w.bullets if bid not in dead_bullet_ids
            ]
            w.entities = [e for e in w.entities if e.id not in dead_bullet_ids]


@dataclass
class BulletShipCollisionSystem:
    name: str = "space_invaders_bullet_ship_collision"
    order: int = 45  # after shield collision

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if is_round_locked(w):
            return
        ship: Ship | None = w.get_entity_by_id(EntityId.SHIP)
        if ship is None or not w.bullets:
            return
        if getattr(ship, "exploding", False) or ship.anim is not None:
            return
        if getattr(w, "shield_active", False):
            return  # shield handles it

        dead_bullet_ids: set[int] = set()

        for bullet_id in w.bullets:
            b = w.get_entity_by_id(bullet_id)
            if b is None:
                continue
            if b.life is None or not b.life.alive:
                continue
            if getattr(b, "owner", None) != "alien":
                continue

            if intersects_entities(ship, b):
                b.life.alive = False
                dead_bullet_ids.add(b.id)
                ship.exploding = True
                w.lives = max(0, int(w.lives) - 1)
                if w.lives <= 0:
                    w.game_over = True
                    w.missile_targeting = False
                Ship.start_explosion(ship, ship.ship_explosion_frames)
                break

        if dead_bullet_ids:
            w.bullets = [
                bid for bid in w.bullets if bid not in dead_bullet_ids
            ]
            w.entities = [e for e in w.entities if e.id not in dead_bullet_ids]


@dataclass
class MissileHomingSystem:
    name: str = "space_invaders_missile_homing"
    order: int = 40

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missiles:
            return

        aliens: list[Alien] = w.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
        alive_by_id: dict[int, Alien] = {
            a.id: a for a in aliens if not getattr(a, "exploding", False)
        }

        for missile_id in w.missiles:
            m = w.get_entity_by_id(missile_id)
            if m is None or m.life is None or not m.life.alive:
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
                m.life.alive = False
                continue

            if m.kinematic:
                m.kinematic.step(m.transform, ctx.dt)


@dataclass
class MissileAlienCollisionSystem:
    name: str = "space_invaders_missile_alien_collision"
    order: int = 45  # same zone as other collisions
    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missiles:
            return

        aliens: list[Alien] = w.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
        # alive aliens by id (skip exploding)
        alive_by_id: dict[int, Alien] = {
            a.id: a for a in aliens if not getattr(a, "exploding", False)
        }

        dead_missile_ids: set[int] = set()

        for missile_id in w.missiles:
            m = w.get_entity_by_id(missile_id)
            if m is None or m.life is None or not m.life.alive:
                continue
            target_id = getattr(m, "target_id", None)
            if target_id is None:
                continue

            target = alive_by_id.get(target_id)
            if target is None:
                # target died (by bullets/omega), so missile should fizzle
                m.life.alive = False
                dead_missile_ids.add(m.id)
                continue

            # ONLY test collision vs that target
            if intersects_entities(m, target):
                m.life.alive = False
                dead_missile_ids.add(m.id)
                target.exploding = True
                target.explode_timer = self.explosion_time
                w.score += alien_points(target)

        if dead_missile_ids:
            w.missiles = [
                mid for mid in w.missiles if mid not in dead_missile_ids
            ]
            w.entities = [
                e for e in w.entities if e.id not in dead_missile_ids
            ]


@dataclass
class UfoCollisionSystem:
    """Handle collisions between UFO and ship projectiles."""

    name: str = "space_invaders_ufo_collision"
    order: int = 45

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        ufo: Ufo | None = w.get_entity_by_id(EntityId.UFO)
        if ufo is None:
            return
        if ufo.life is not None and not ufo.life.alive:
            return

        dead_bullet_ids: set[int] = set()
        dead_missile_ids: set[int] = set()
        hit = False

        for bullet_id in w.bullets:
            b = w.get_entity_by_id(bullet_id)
            if b is None or b.life is None or not b.life.alive:
                continue
            if getattr(b, "owner", None) != "ship":
                continue
            if not intersects_entities(b, ufo):
                continue
            b.life.alive = False
            dead_bullet_ids.add(b.id)
            hit = True
            break

        if not hit:
            for missile_id in w.missiles:
                m = w.get_entity_by_id(missile_id)
                if m is None or m.life is None or not m.life.alive:
                    continue
                if not intersects_entities(m, ufo):
                    continue
                m.life.alive = False
                dead_missile_ids.add(m.id)
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

        remove_ids = {EntityId.UFO, *dead_bullet_ids, *dead_missile_ids}
        w.entities = [e for e in w.entities if e.id not in remove_ids]

        if dead_bullet_ids:
            w.bullets = [bid for bid in w.bullets if bid not in dead_bullet_ids]
        if dead_missile_ids:
            w.missiles = [
                mid for mid in w.missiles if mid not in dead_missile_ids
            ]

        w.ufo_spawn_timer = random.uniform(w.ufo_spawn_min, w.ufo_spawn_max)


@dataclass
class MissileCullSystem:
    name: str = "space_invaders_missile_cull"
    order: int = 47

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missiles:
            return
        vw, vh = w.viewport

        alive_ids: list[int] = []
        alive_id_set: set[int] = set()
        for missile_id in w.missiles:
            if missile_id in alive_id_set:
                continue
            m = w.get_entity_by_id(missile_id)
            if m is None or m.life is None or not m.life.alive:
                continue
            x, y = m.transform.center.to_tuple()
            if (
                (y > vh)
                or (y + m.transform.size.height < 0)
                or (x > vw)
                or (x + m.transform.size.width < 0)
            ):
                continue
            alive_ids.append(missile_id)
            alive_id_set.add(missile_id)
        w.missiles = alive_ids
        missile_start = int(EntityId.MISSILE_START)
        missile_end = int(EntityId.MISSILE_END)
        w.entities = [
            e
            for e in w.entities
            if not (
                missile_start <= e.id <= missile_end
                and e.id not in alive_id_set
            )
        ]


@dataclass
class OmegaRayDamageSystem:
    name: str = "space_invaders_omega_damage"
    order: int = 44  # before ExplosionSystem (46) is perfect

    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.omega_active or w.omega_x is None:
            return
        aliens: list[Alien] = w.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
        if not aliens:
            return

        # Beam rect: from top of screen to top of ship
        ship: Ship | None = w.get_entity_by_id(EntityId.SHIP)
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

        ufo: Ufo | None = w.get_entity_by_id(EntityId.UFO)
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
            w.entities = [e for e in w.entities if e.id != EntityId.UFO]
            w.ufo_spawn_timer = random.uniform(w.ufo_spawn_min, w.ufo_spawn_max)


@dataclass
class ExplosionSystem:
    name: str = "space_invaders_explosions"
    order: int = 46  # after collision

    def step(self, ctx: SpaceInvadersTickContext):
        aliens: list[Alien] = ctx.world.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
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
            ctx.world.entities = [
                e for e in ctx.world.entities if e.id not in dead_alien_ids
            ]


@dataclass
class BulletCullSystem:
    """Removes bullets that are dead or out of viewport."""

    name: str = "space_invaders_bullet_cull"
    order: int = 36

    def step(self, ctx: SpaceInvadersTickContext):
        vw, vh = ctx.world.viewport
        alive_ids: list[int] = []
        alive_id_set: set[int] = set()
        for bullet_id in ctx.world.bullets:
            if bullet_id in alive_id_set:
                continue
            b = ctx.world.get_entity_by_id(bullet_id)
            if b is None:
                continue
            if b.life is not None and not b.life.alive:
                continue
            x, y = b.transform.center.to_tuple()
            bw, bh = b.transform.size.to_tuple()
            if (y + bh) < 0 or y > vh or (x + bw) < 0 or x > vw:
                continue
            alive_ids.append(bullet_id)
            alive_id_set.add(bullet_id)

        ctx.world.bullets = alive_ids
        bullet_start = int(EntityId.BULLET_START)
        bullet_end = int(EntityId.BULLET_END)
        ctx.world.entities = [
            e
            for e in ctx.world.entities
            if not (
                bullet_start <= e.id <= bullet_end and e.id not in alive_id_set
            )
        ]


@dataclass
class BulletBulletCollisionSystem:
    name: str = "space_invaders_bullet_bullet_collision"
    order: int = 42

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.bullets:
            return
        if is_round_locked(w):
            return

        ship_bullets: list[Bullet] = []
        alien_bullets: list[Bullet] = []
        for bullet_id in w.bullets:
            b = w.get_entity_by_id(bullet_id)
            if b is None:
                continue
            if b.life is None or not b.life.alive:
                continue
            owner = getattr(b, "owner", None)
            if owner == "ship":
                ship_bullets.append(b)
            elif owner == "alien":
                alien_bullets.append(b)
        if not ship_bullets or not alien_bullets:
            return

        dead_bullet_ids: set[int] = set()
        for sb in ship_bullets:
            if sb.id in dead_bullet_ids:
                continue
            for ab in alien_bullets:
                if ab.id in dead_bullet_ids:
                    continue
                if intersects_entities(sb, ab):
                    sb.life.alive = False
                    ab.life.alive = False
                    dead_bullet_ids.add(sb.id)
                    dead_bullet_ids.add(ab.id)
                    x, y = sb.transform.center.to_tuple()
                    spawn_effect(
                        w,
                        getattr(w, "fx_enemy_proj_tex", None),
                        x - 8,
                        y - 8,
                        24,
                        24,
                        ttl=float(getattr(w, "fx_ttl", 0.12)),
                    )
                    break

        if dead_bullet_ids:
            w.bullets = [
                bid for bid in w.bullets if bid not in dead_bullet_ids
            ]
            w.entities = [e for e in w.entities if e.id not in dead_bullet_ids]


@dataclass
class EffectsSystem:
    name: str = "space_invaders_effects"
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
    name: str = "space_invaders_round_state"
    order: int = 88

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if w.game_over:
            return
        if w.victory:
            return
        aliens = w.get_entities_by_id_range(
            EntityId.ALIEN_START, EntityId.ALIEN_END
        )
        if not aliens:
            w.victory = True
            w.missile_targeting = False


@dataclass
class SpaceInvadersRenderSystem(
    BaseQueuedRenderSystem[SpaceInvadersTickContext]
):
    """Build layered render queue ops for pipeline passes."""

    name: str = "min_render"
    order: int = 100

    def emit(self, ctx: SpaceInvadersTickContext, rq):
        super().emit(ctx, rq)
        rq.custom(
            op=DrawCall(drawable=DrawRegionTint(), ctx=ctx),
            layer="effects",
            z=90,
        )
        rq.custom(
            op=DrawCall(drawable=DrawShieldOverlay(), ctx=ctx),
            layer="lighting",
            z=30,
        )
        rq.custom(
            op=DrawCall(drawable=DrawOmegaRay(), ctx=ctx),
            layer="effects",
            z=40,
        )
        rq.custom(
            op=DrawCall(drawable=DrawMissileTarget(), ctx=ctx),
            layer="effects",
            z=50,
        )
        rq.custom(
            op=DrawCall(drawable=DrawEffects(), ctx=ctx),
            layer="effects",
            z=60,
        )
        self._emit_hud(ctx, rq)

    def emit_entity(self, ctx: SpaceInvadersTickContext, rq, entity) -> None:
        # Alien explosion override while timer is active.
        if (
            EntityId.ALIEN_START <= entity.id <= EntityId.ALIEN_END
            and getattr(entity, "exploding", False)
            and ctx.world.explosion_texture is not None
        ):
            t = entity.transform
            rq.texture(
                tex_id=ctx.world.explosion_texture,
                x=t.center.x,
                y=t.center.y,
                w=t.size.width,
                h=t.size.height,
                layer="world",
                z=entity.z_index,
            )
            return

        super().emit_entity(ctx, rq, entity)

    @staticmethod
    def _emit_hud(ctx: SpaceInvadersTickContext, rq) -> None:
        w = ctx.world
        vw, vh = w.viewport
        aliens_left = len(
            w.get_entities_by_id_range(EntityId.ALIEN_START, EntityId.ALIEN_END)
        )

        rq.text(
            x=12,
            y=12,
            text=f"SCORE {int(w.score):05d}",
            color=(255, 255, 255, 255),
            align="left",
            layer="ui",
            z=5,
        )
        rq.text(
            x=vw - 12,
            y=12,
            text=f"LIVES {int(w.lives)}",
            color=(255, 255, 255, 255),
            align="right",
            layer="ui",
            z=5,
        )
        rq.text(
            x=vw * 0.5,
            y=12,
            text=f"ALIENS {aliens_left}",
            color=(160, 200, 255, 255),
            align="center",
            layer="ui",
            z=5,
        )

        if w.game_over:
            rq.text(
                x=vw * 0.5,
                y=vh * 0.5,
                text="GAME OVER",
                color=(255, 80, 80, 255),
                align="center",
                layer="ui",
                z=10,
            )
        elif w.victory:
            rq.text(
                x=vw * 0.5,
                y=vh * 0.5,
                text="YOU WIN",
                color=(80, 255, 140, 255),
                align="center",
                layer="ui",
                z=10,
            )
