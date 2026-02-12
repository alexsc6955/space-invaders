"""
Space Invaders Scene
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from mini_arcade_core.backend import Backend
from mini_arcade_core.backend.keys import Key
from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.engine.commands import ToggleVideoRecordCommand
from mini_arcade_core.engine.components import TTL, Alive, Animated, Renderable
from mini_arcade_core.engine.entities.sprite import AnimSprite2D, Sprite2D
from mini_arcade_core.runtime.context import RuntimeContext
from mini_arcade_core.scenes.autoreg import (  # pyright: ignore[reportMissingImports]
    register_scene,
)
from mini_arcade_core.scenes.sim_scene import (  # pyright: ignore[reportMissingImports]
    BaseIntent,
    BaseTickContext,
    BaseWorld,
    Drawable,
    DrawCall,
    SimScene,
)
from mini_arcade_core.scenes.systems.builtins import (
    BaseInputSystem,
    BaseRenderSystem,
)
from mini_arcade_core.scenes.systems.system_pipeline import SystemPipeline
from mini_arcade_core.spaces.d2.collision2d import RectCollider
from mini_arcade_core.spaces.d2.geometry2d import Position2D, Size2D
from mini_arcade_core.spaces.d2.physics2d import Velocity2D
from mini_arcade_core.spaces.geometry.transform import Transform2D
from mini_arcade_core.spaces.math.vec2 import Vec2
from mini_arcade_core.spaces.physics.kinematics2d import Kinematic2D
from mini_arcade_core.utils import logger

from space_invaders.constants import ASSETS_ROOT


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


@dataclass
class SpaceInvadersWorld(BaseWorld):
    """
    Space Invaders World
    """

    viewport: tuple[float, float]
    ship: Ship
    aliens: list[Alien] = field(default_factory=list)
    aliens_direction: float = 1.0  # 1 for right, -1 for left
    bullets: list[Bullet] = field(default_factory=list)
    ship_fire_cooldown: float = 0.20
    ship_fire_timer: float = 0.0
    explosion_texture: int | None = None
    bullet_texture: int | None = None
    projectile_specs: dict[ProjectileKind, ProjectileSpec] = field(
        default_factory=dict
    )
    alien_fire_timer: float = 1.0  # start with a delay
    alien_fire_cooldown_min: float = 0.8  # slower
    alien_fire_cooldown_max: float = 1.6
    max_alien_bullets: int = 2

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
    missiles: list[Missile] = field(default_factory=list)

    target_texture: int | None = None
    target_scale: float = 1.35

    shelters: list[Shelter] = field(default_factory=list)

    effects: list[Effect] = field(default_factory=list)

    # projectile impact VFX (single sprites)
    fx_player_proj_tex: int | None = None
    fx_enemy_proj_tex: int | None = None
    fx_ttl: float = 0.12

    # shield
    shield_active: bool = False
    shield_timer: float = 0.0
    shield_duration: float = 1.0
    shield_cd_timer: float = 0.0
    shield_cooldown: float = 2.0
    shield_anim: Animation | None = None
    shield_scale: float = 1.35

    # ship explosion frames (non-loop)
    ship_explosion_frames: list[int] = field(default_factory=list)
    ship_explosion_fps: float = 14.0
    ship_explosion_time: float = 0.0


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

    toggle_video_recording: bool = False


@dataclass
class SpaceInvadersTickContext(
    BaseTickContext[SpaceInvadersWorld, SpaceInvadersIntent]
):
    """
    Space Invaders Tick Context
    """


@dataclass
class SpaceInvadersInputSystem(BaseInputSystem):
    """
    Process input and update intent.
    """

    name: str = "space_invaders_input"

    def step(self, ctx: SpaceInvadersTickContext):
        """Process input and update intent."""
        key_down = ctx.input_frame.keys_down
        key_pressed = ctx.input_frame.keys_pressed
        move_ship_left = 1.0 if Key.LEFT in key_down else 0.0
        move_ship_right = 1.0 if Key.RIGHT in key_down else 0.0
        fire_bullet = Key.SPACE in key_pressed
        fire_omega_ray = Key.O in key_pressed

        toggle_missile_target = Key.T in key_pressed
        missile_target_left = Key.A in key_pressed  # or Key.LEFT if you want
        missile_target_right = Key.D in key_pressed
        missile_launch = Key.M in key_pressed
        missile_target_up = Key.W in key_pressed
        missile_target_down = Key.S in key_pressed
        shield_toggle = Key.C in key_pressed

        toggle_video_recording = Key.R in key_pressed

        ctx.intent = SpaceInvadersIntent(
            move_ship_left=move_ship_left,
            move_ship_right=move_ship_right,
            fire_bullet=fire_bullet,
            fire_omega_ray=fire_omega_ray,
            toggle_missile_target=toggle_missile_target,
            missile_target_left=missile_target_left,
            missile_target_right=missile_target_right,
            missile_launch=missile_launch,
            missile_target_up=missile_target_up,
            missile_target_down=missile_target_down,
            shield_toggle=shield_toggle,
            toggle_video_recording=toggle_video_recording,
        )


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

        if ctx.intent.toggle_video_recording:
            ctx.commands.push(ToggleVideoRecordCommand())


@dataclass
class ShieldSystem:
    name: str = "space_invaders_shield"
    order: int = 22  # after input, before collisions

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        it = ctx.intent
        if it is None:
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

        # tick cooldown
        if w.missile_cd_timer > 0:
            w.missile_cd_timer = max(0.0, w.missile_cd_timer - ctx.dt)

        alive = [a for a in w.aliens if not a.exploding]
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
        cur_row, cur_col = cur.row, cur.col

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

        vw, _ = ctx.world.viewport
        ship = ctx.world.ship

        move_x = ctx.intent.move_ship_right - ctx.intent.move_ship_left
        ship.body.velocity.x = move_x * ship.body.speed
        ship.body.velocity.y = 0.0

        # move first
        ship.body.step(ctx.dt)

        # clamp using UPDATED position
        x, y = ship.body.position.to_tuple()
        x = max(0.0, min(vw - ship.body.size.width, x))

        # set position (your setter keeps center in sync)
        ship.body.position = Vec2(x, y)


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

        if not w.missile_targeting:
            return
        if w.missile_cd_timer > 0:
            return

        alive = [a for a in w.aliens if not a.exploding]
        if not alive:
            return
        if w.missile_target_idx is None:
            return

        target = alive[w.missile_target_idx]

        # spawn from ship top-center
        ship = w.ship
        sx, sy = ship.position.to_tuple()
        sw, _ = ship.size.to_tuple()

        mx = sx + sw / 2 - self.missile_size.width / 2
        my = sy - self.missile_size.height

        w.missiles.append(
            Missile(
                position=Position2D(mx, my),
                size=self.missile_size,
                velocity=Velocity2D(0.0, -250.0),  # initial kick upward
                target_id=id(target),  # stable reference (not list index)
                speed=520.0,
                anim=w.missile_anim,
            )
        )

        w.missile_cd_timer = w.missile_cooldown
        w.missile_targeting = False
        # optionally exit targeting after launch
        # w.missile_targeting = False


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
        vw, _ = ctx.world.viewport
        aliens = ctx.world.aliens
        if not aliens:
            return

        dir_x = ctx.world.aliens_direction

        # 1) set vx for all aliens
        for a in aliens:
            a.velocity.vx = dir_x * a.speed
            a.velocity.vy = 0.0

        # 2) predict if we hit a wall this tick
        hit_wall = False
        for a in aliens:
            x, y = a.position.to_tuple()
            next_x, _ = a.velocity.advance(x, y, ctx.dt)
            if next_x <= 0.0 or (next_x + a.size.width) >= vw:
                hit_wall = True
                break

        # 3) apply movement
        if hit_wall:
            # reverse direction and drop down
            ctx.world.aliens_direction *= -1.0
            for a in aliens:
                x, y = a.position.to_tuple()
                a.position = Position2D(x, y + self.drop_step)
        else:
            # normal horizontal move
            for a in aliens:
                x, y = a.position.to_tuple()
                x, _ = a.velocity.advance(x, y, ctx.dt)
                a.position = Position2D(x, y)


@dataclass
class AlienAnimationSystem:
    name: str = "space_invaders_alien_anim"
    order: int = 28

    def step(self, ctx: SpaceInvadersTickContext):
        for a in ctx.world.aliens:
            if a.anim:
                a.anim.update(ctx.dt)
                a.texture = a.anim.current_frame


@dataclass
class AlienFireSystem:
    name: str = "space_invaders_alien_fire"
    order: int = 32  # after AlienSystem movement is fine

    min_cooldown: float = 0.25
    max_cooldown: float = 1.10

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.aliens:
            return

        for a in w.aliens:
            if a.fire_cd > 0.0:
                a.fire_cd = max(0.0, a.fire_cd - ctx.dt)

        # tick timer
        w.alien_fire_timer -= ctx.dt
        if w.alien_fire_timer > 0:
            return

        # gate: limit how many alien bullets can exist
        active_alien_bullets = sum(
            1 for b in w.bullets if b.alive and b.owner == "alien"
        )
        if active_alien_bullets >= w.max_alien_bullets:
            # try again soon, but don't spam checks every frame
            w.alien_fire_timer = 0.15
            return

        # reset to a random next fire time
        w.alien_fire_timer = random.uniform(
            w.alien_fire_cooldown_min, w.alien_fire_cooldown_max
        )

        # choose shooters = bottom-most alien per column (not exploding)
        shooters = self._bottom_most_by_column(w.aliens)
        if not shooters:
            return

        shooter = random.choice(shooters)

        kind = self._projectile_kind_for_row(
            shooter.row, total_rows=self._infer_rows(w.aliens)
        )
        if kind is None:
            return

        spec = w.projectile_specs.get(kind)
        if spec is None:
            return

        sx, sy = shooter.position.to_tuple()
        sw, sh = shooter.size.to_tuple()

        # spawn at bottom-center of alien
        bx = sx + (sw / 2) - (spec.size.width / 2)
        by = sy + sh

        w.bullets.append(
            Bullet(
                position=Position2D(bx, by),
                size=spec.size,
                velocity=Velocity2D(0.0, spec.speed),  # downwards
                owner="alien",
                anim=Animation(frames=list(spec.frames), fps=spec.fps),
                texture=None,
            )
        )
        shooter.fire_cd = random.uniform(0.8, 2.0)
        logger.debug(
            f"Alien at row {shooter.row} col {shooter.col} fired a {kind} projectile."
        )

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

        for b in w.bullets:
            if not b.alive or b.owner != "ship":
                continue

            for m in w.missiles:
                if not m.alive:
                    continue

                if b.collider.intersects(m.collider):
                    b.alive = False
                    m.alive = False

                    bx, by = b.position.to_tuple()
                    spawn_effect(
                        w,
                        w.fx_enemy_proj_tex,
                        bx - 8,
                        by - 8,
                        24,
                        24,
                        ttl=w.fx_ttl,
                    )
                    break


@dataclass
class BulletSpawnSystem:
    """
    Spawn bullets from ship intent (SPACE).
    Uses a simple cooldown timer.
    """

    name: str = "space_invaders_bullet_spawn"
    order: int = 25

    bullet_w: int = 4
    bullet_h: int = 10
    bullet_speed: float = 520.0

    def step(self, ctx: SpaceInvadersTickContext):
        if ctx.intent is None:
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

        ship = ctx.world.ship
        sx, sy = ship.body.position.to_tuple()

        # bullet spawn position = top-center of ship
        bx = sx + (ship.body.size.width / 2) - (self.bullet_w / 2)
        by = sy - self.bullet_h

        ctx.world.bullets.append(
            Bullet(
                position=Position2D(bx, by),
                size=Size2D(self.bullet_w, self.bullet_h),
                velocity=Velocity2D(0.0, -self.bullet_speed),
                owner="ship",
                texture=ctx.world.bullet_texture,
            )
        )

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
        ship = w.ship
        sx, sy = ship.position.to_tuple()
        sw, sh = ship.size.to_tuple()

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
            if not b.alive:
                continue
            x, y = b.position.to_tuple()
            x, y = b.velocity.advance(x, y, ctx.dt)
            b.position = Position2D(x, y)


@dataclass
class BulletAnimationSystem:
    name: str = "space_invaders_bullet_anim"
    order: int = 38

    def step(self, ctx: SpaceInvadersTickContext):
        for b in ctx.world.bullets:
            if not b.alive:
                continue
            if b.anim:
                b.anim.update(ctx.dt)
                b.texture = b.anim.current_frame


@dataclass
class BulletAlienCollisionSystem:
    """Kills aliens hit by ship bullets and removes the bullet."""

    name: str = "space_invaders_bullet_alien_collision"
    order: int = 45
    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        bullets = ctx.world.bullets
        aliens = ctx.world.aliens
        if not bullets or not aliens:
            return

        for b in bullets:
            if not b.alive or b.owner != "ship":
                continue

            for a in aliens:
                if a.exploding:
                    continue  # already dying

                if b.collider.intersects(a.collider):
                    b.alive = False
                    a.exploding = True
                    a.explode_timer = self.explosion_time
                    break


@dataclass
class BulletShelterCollisionSystem:
    name: str = "space_invaders_bullet_shelter_collision"
    order: int = 43  # before alien collisions (45) is fine
    max_damage: int = 9
    destroy_on_max: bool = False  # set True if you want it to disappear at 9

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.bullets or not w.shelters:
            return

        for b in w.bullets:
            if not b.alive or b.owner != "alien":
                continue

            for s in w.shelters:
                if not s.alive:
                    continue

                if b.collider.intersects(s.collider):
                    b.alive = False

                    bx, by = b.position.to_tuple()
                    spawn_effect(
                        w,
                        w.fx_enemy_proj_tex,
                        bx - 8,
                        by - 8,
                        24,
                        24,
                        ttl=w.fx_ttl,
                    )

                    if s.damage < self.max_damage:
                        s.damage += 1
                    if self.destroy_on_max and s.damage >= self.max_damage:
                        s.alive = False
                    break


@dataclass
class BulletShieldCollisionSystem:
    name: str = "space_invaders_bullet_shield_collision"
    order: int = 44  # after shelter collision, before ship hit

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.shield_active or not w.bullets:
            return

        ship = w.ship
        sx, sy = ship.position.to_tuple()
        sw, sh = ship.size.to_tuple()

        scale = float(getattr(w, "shield_scale", 1.35))
        shield_w = sw * scale
        shield_h = sh * scale
        shield_x = sx + sw / 2 - shield_w / 2
        shield_y = sy + sh / 2 - shield_h / 2

        shield_collider = RectCollider(
            Position2D(shield_x, shield_y),
            Size2D(shield_w, shield_h),
        )

        for b in w.bullets:
            if not b.alive or b.owner != "alien":
                continue
            if shield_collider.intersects(b.collider):
                b.alive = False
                bx, by = b.position.to_tuple()
                spawn_effect(
                    w,
                    w.fx_enemy_proj_tex,
                    bx - 8,
                    by - 8,
                    24,
                    24,
                    ttl=w.fx_ttl,
                )


@dataclass
class BulletShipCollisionSystem:
    name: str = "space_invaders_bullet_ship_collision"
    order: int = 45  # after shield collision

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        ship = w.ship
        if ship.exploding or not w.bullets:
            return
        if w.shield_active:
            return  # shield handles it

        ship_collider = RectCollider(ship.body.position, ship.body.size)

        for b in w.bullets:
            if not b.alive or b.owner != "alien":
                continue

            if ship_collider.intersects(b.collider):
                b.alive = False

                ship.exploding = True
                ship.explode_timer = w.ship_explosion_time
                ship.base_texture = ship.texture
                ship.texture = None  # render explosion instead
                ship.explode_anim = Animation(
                    frames=list(w.ship_explosion_frames),
                    fps=w.ship_explosion_fps,
                    loop=False,
                )
                break


@dataclass
class ShipExplosionSystem:
    name: str = "space_invaders_ship_explosion"
    order: int = 46

    def step(self, ctx: SpaceInvadersTickContext):
        ship = ctx.world.ship
        if not ship.exploding:
            return

        ship.explode_timer = max(0.0, ship.explode_timer - ctx.dt)
        if ship.explode_anim:
            ship.explode_anim.update(ctx.dt)

        if ship.explode_timer <= 0:
            ship.exploding = False
            # restore ship
            ship.texture = ship.base_texture
            ship.explode_anim = None


@dataclass
class MissileHomingSystem:
    name: str = "space_invaders_missile_homing"
    order: int = 40

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missiles:
            return

        # map current alive aliens by id()
        alive_by_id = {id(a): a for a in w.aliens if not a.exploding}

        for m in w.missiles:
            if not m.alive:
                continue

            # animate
            if m.anim:
                m.anim.update(ctx.dt)
                m.texture = m.anim.current_frame

            target = alive_by_id.get(m.target_id) if m.target_id else None

            if target is not None:
                tx, ty = target.position.to_tuple()
                tw, th = target.size.to_tuple()
                target_cx = tx + tw / 2
                target_cy = ty + th / 2

                mx, my = m.position.to_tuple()
                mcx = mx + m.size.width / 2
                mcy = my + m.size.height / 2

                dx = target_cx - mcx
                dy = target_cy - mcy
                dist2 = dx * dx + dy * dy

                if dist2 > 0.0001:
                    dist = dist2**0.5
                    vx = (dx / dist) * m.speed
                    vy = (dy / dist) * m.speed
                    m.velocity.vx = vx
                    m.velocity.vy = vy

            # move
            x, y = m.position.to_tuple()
            x, y = m.velocity.advance(x, y, ctx.dt)
            m.position = Position2D(x, y)


@dataclass
class MissileAlienCollisionSystem:
    name: str = "space_invaders_missile_alien_collision"
    order: int = 45  # same zone as other collisions
    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missiles or not w.aliens:
            return

        # alive aliens by id (skip exploding)
        alive_by_id = {id(a): a for a in w.aliens if not a.exploding}

        for m in w.missiles:
            if not m.alive:
                continue
            if m.target_id is None:
                continue

            target = alive_by_id.get(m.target_id)
            if target is None:
                # target died (by bullets/omega), so missile should fizzle
                m.alive = False
                continue

            # ONLY test collision vs that target
            if m.collider.intersects(target.collider):
                m.alive = False
                target.exploding = True
                target.explode_timer = self.explosion_time


@dataclass
class MissileCullSystem:
    name: str = "space_invaders_missile_cull"
    order: int = 47

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missiles:
            return
        vw, vh = w.viewport

        alive: list[Missile] = []
        for m in w.missiles:
            if not m.alive:
                continue
            x, y = m.position.to_tuple()
            if (
                (y > vh)
                or (y + m.size.height < 0)
                or (x > vw)
                or (x + m.size.width < 0)
            ):
                continue
            alive.append(m)
        w.missiles = alive


@dataclass
class OmegaRayDamageSystem:
    name: str = "space_invaders_omega_damage"
    order: int = 44  # before ExplosionSystem (46) is perfect

    explosion_time: float = 0.20

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.omega_active or w.omega_x is None:
            return
        if not w.aliens:
            return

        # Beam rect: from top of screen to top of ship
        ship = w.ship
        _, sy = ship.position.to_tuple()

        beam_x = float(w.omega_x)
        beam_w = float(w.omega_width)
        beam_h = float(max(0, int(sy)))  # 0..ship_top

        if beam_h <= 0:
            return

        beam_rect = RectCollider(
            Position2D(beam_x, 0.0),
            Size2D(beam_w, beam_h),
        )

        # Kill all aliens intersecting the beam
        for a in w.aliens:
            if a.exploding:
                continue
            if beam_rect.intersects(a.collider):
                a.exploding = True
                a.explode_timer = self.explosion_time


@dataclass
class ExplosionSystem:
    name: str = "space_invaders_explosions"
    order: int = 46  # after collision

    def step(self, ctx: SpaceInvadersTickContext):
        if not ctx.world.aliens:
            return

        alive_aliens: list[Alien] = []
        for a in ctx.world.aliens:
            if a.exploding:
                a.explode_timer -= ctx.dt
                if a.explode_timer > 0:
                    alive_aliens.append(a)
                # else: drop it (explosion finished)
            else:
                alive_aliens.append(a)

        ctx.world.aliens = alive_aliens


@dataclass
class BulletCullSystem:
    """Removes bullets that are dead or out of viewport."""

    name: str = "space_invaders_bullet_cull"
    order: int = 36

    def step(self, ctx: SpaceInvadersTickContext):
        vw, vh = ctx.world.viewport

        alive: list[Bullet] = []
        for b in ctx.world.bullets:
            if not b.alive:
                continue
            x, y = b.position.to_tuple()
            if (
                (y + b.size.height) < 0
                or y > vh
                or (x + b.size.width) < 0
                or x > vw
            ):
                continue
            alive.append(b)

        ctx.world.bullets = alive


@dataclass
class BulletBulletCollisionSystem:
    name: str = "space_invaders_bullet_bullet_collision"
    order: int = 42

    def step(self, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.bullets:
            return

        ship_bullets = [b for b in w.bullets if b.alive and b.owner == "ship"]
        alien_bullets = [
            b for b in w.bullets if b.alive and b.owner == "alien"
        ]
        if not ship_bullets or not alien_bullets:
            return

        for sb in ship_bullets:
            if not sb.alive:
                continue
            for ab in alien_bullets:
                if not ab.alive:
                    continue

                if sb.collider.intersects(ab.collider):
                    sb.alive = False
                    ab.alive = False

                    x, y = sb.position.to_tuple()
                    spawn_effect(
                        w,
                        w.fx_enemy_proj_tex,
                        x - 8,
                        y - 8,
                        24,
                        24,
                        ttl=w.fx_ttl,
                    )
                    break


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


class DrawShip(Drawable):
    """
    Drawable Ship
    """

    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        ship = ctx.world.ship
        bx, by = ship.body.position.to_tuple()
        bw, bh = ship.body.size.to_tuple()

        if ship.exploding and ship.explode_anim:
            tex = ship.explode_anim.current_frame
            backend.render.draw_texture(
                tex, int(bx), int(by), int(bw), int(bh)
            )
            return

        if ship.texture is not None and ship.visible:
            backend.render.draw_texture(
                ship.texture, int(bx), int(by), int(bw), int(bh)
            )
        else:
            backend.render.draw_rect(
                int(bx), int(by), int(bw), int(bh), color=(255, 255, 255)
            )


class DrawShield(Drawable):
    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        w = ctx.world
        ship = w.ship
        if not w.shield_active or not w.shield_anim:
            return
        if ship.exploding:
            return

        sx, sy = ship.position.to_tuple()
        sw, sh = ship.size.to_tuple()

        scale = float(getattr(w, "shield_scale", 1.35))
        tw = int(sw * scale)
        th = int(sh * scale)

        cx = sx + sw / 2.0
        cy = sy + sh / 2.0
        tx = int(cx - tw / 2.0)
        ty = int(cy - th / 2.0)

        backend.render.draw_texture(
            w.shield_anim.current_frame, tx, ty, tw, th
        )


class DrawAliens(Drawable):
    """
    Drawable Aliens
    """

    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        for a in ctx.world.aliens:
            x, y = a.position.to_tuple()
            w, h = a.size.to_tuple()

            explosion_texture = ctx.world.explosion_texture
            if a.exploding and explosion_texture is not None:
                backend.render.draw_texture(
                    explosion_texture, int(x), int(y), int(w), int(h)
                )
                continue

            if a.texture is not None:
                backend.render.draw_texture(
                    a.texture, int(x), int(y), int(w), int(h)
                )
            else:
                backend.render.draw_rect(
                    int(x), int(y), int(w), int(h), color=(255, 255, 255)
                )


class DrawBullets(Drawable):
    """
    Drawable Bullets
    """

    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        for b in ctx.world.bullets:
            x, y = b.position.to_tuple()
            w, h = b.size.to_tuple()
            if b.texture is not None:
                backend.render.draw_texture(
                    b.texture, int(x), int(y), int(w), int(h)
                )
            else:
                backend.render.draw_rect(
                    int(x), int(y), int(w), int(h), color=(255, 255, 255)
                )


class DrawOmegaRay(Drawable):
    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if w.omega_x is None:
            return

        ship = w.ship
        sx, sy = ship.position.to_tuple()
        sw, sh = ship.size.to_tuple()

        beam_w = int(w.omega_width)
        beam_x = int(w.omega_x)

        # where the beam "ends" (top of ship)
        origin_y = int(sy)  # ship top

        # charging: show charge just above ship
        if w.omega_charge_timer > 0 and w.omega_charge_anim:
            tex = w.omega_charge_anim.current_frame
            backend.render.draw_texture(tex, beam_x, origin_y - 24, beam_w, 24)
            return

        # firing
        if not w.omega_active:
            return
        if not w.omega_beam_anim or not w.omega_beam_large_anim:
            return

        thin_tex = w.omega_beam_anim.current_frame
        large_tex = w.omega_beam_large_anim.current_frame

        # Beam should cover from TOP (0) down to ship top (origin_y)
        beam_h = max(0, origin_y)
        backend.render.draw_texture_tiled_y(
            thin_tex, beam_x, 0, beam_w, beam_h
        )

        # fat chunk near the bottom (close to ship), like your reference image
        base_h = min(int(w.omega_large_height), beam_h)
        base_y = max(0, origin_y - base_h)
        backend.render.draw_texture(large_tex, beam_x, base_y, beam_w, base_h)


class DrawMissileTarget(Drawable):
    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        w = ctx.world
        if not w.missile_targeting:
            return

        alive = [a for a in w.aliens if not a.exploding]
        if not alive or w.missile_target_idx is None:
            return

        target_tex = w.target_texture
        if target_tex is None:
            return

        a = alive[w.missile_target_idx]
        x, y = a.position.to_tuple()
        aw, ah = a.size.to_tuple()

        scale = float(getattr(w, "target_scale", 1.35))
        tw = int(aw * scale)
        th = int(ah * scale)

        cx = x + aw / 2.0
        cy = y + ah / 2.0

        tx = int(cx - tw / 2.0)
        ty = int(cy - th / 2.0)

        backend.render.draw_texture(target_tex, tx, ty, tw, th)


class DrawMissiles(Drawable):
    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        for m in ctx.world.missiles:
            x, y = m.position.to_tuple()
            w, h = m.size.to_tuple()
            if m.texture is not None:
                backend.render.draw_texture(
                    int(m.texture), int(x), int(y), int(w), int(h)
                )
            else:
                backend.render.draw_rect(
                    int(x), int(y), int(w), int(h), color=(255, 255, 255)
                )


class DrawShelters(Drawable):
    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        for s in ctx.world.shelters:
            if not s.alive:
                continue
            x, y = s.position.to_tuple()
            w, h = s.size.to_tuple()
            tex = s.texture
            if tex is not None:
                backend.render.draw_texture(
                    tex, int(x), int(y), int(w), int(h)
                )
            else:
                backend.render.draw_rect(
                    int(x), int(y), int(w), int(h), color=(0, 255, 0)
                )


class DrawEffects(Drawable):
    def draw(self, backend: Backend, ctx: SpaceInvadersTickContext):
        for e in ctx.world.effects:
            x, y = e.position.to_tuple()
            w, h = e.size.to_tuple()
            backend.render.draw_texture(
                e.texture, int(x), int(y), int(w), int(h)
            )


@dataclass
class SpaceInvadersRenderSystem(BaseRenderSystem):
    """
    Render the Space Invaders world.
    """

    name: str = "space_invaders_render"
    order: int = 100

    def step(self, ctx: SpaceInvadersTickContext):
        """Render the Space Invaders world."""

        ctx.draw_ops = [
            DrawCall(DrawShip(), ctx=ctx),
            DrawCall(DrawShield(), ctx=ctx),
            DrawCall(DrawAliens(), ctx=ctx),
            DrawCall(DrawShelters(), ctx=ctx),
            DrawCall(DrawOmegaRay(), ctx=ctx),
            DrawCall(DrawMissileTarget(), ctx=ctx),
            DrawCall(DrawMissiles(), ctx=ctx),
            DrawCall(DrawBullets(), ctx=ctx),
            DrawCall(DrawEffects(), ctx=ctx),
        ]
        super().step(ctx)


@register_scene("space_invaders")
class SpaceInvadersScene(SimScene[SpaceInvadersTickContext]):
    """
    Minimal scene: opens a window, clears screen, handles quit/ESC.
    """

    world: SpaceInvadersWorld
    _tex_cache: dict[str, int]
    tick_context_type = SpaceInvadersTickContext

    def on_enter(self):
        # Add cheats
        # Justification: window typer is protocol, mypy can't infer correctly
        # pylint: disable=assignment-from-no-return
        vw, vh = self.context.services.window.get_virtual_size()
        # pylint: enable=assignment-from-no-return
        proj_a = (
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileA_1.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileA_2.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileA_3.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileA_4.png"),
        )
        proj_b = (
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileB_1.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileB_2.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileB_3.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileB_4.png"),
        )
        proj_c = (
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileC_1.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileC_2.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileC_3.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/ProjectileC_4.png"),
        )
        missile = (
            self._tex(f"{ASSETS_ROOT}/sprites/missile_1.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/missile_2.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/missile_3.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/missile_4.png"),
        )

        omega_charge = (
            self._tex(f"{ASSETS_ROOT}/sprites/RayCharge_1.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/RayCharge_2.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/RayCharge_3.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/RayCharge_4.png"),
        )
        omega_ray = (
            self._tex(f"{ASSETS_ROOT}/sprites/OmegaRay_1.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/OmegaRay_2.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/OmegaRay_3.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/OmegaRay_4.png"),
        )
        omega_ray_large = (
            self._tex(f"{ASSETS_ROOT}/sprites/OmegaRay_Large_1.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/OmegaRay_Large_2.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/OmegaRay_Large_3.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/OmegaRay_Large_4.png"),
        )

        ship_w = 40

        player_proj_explosion = self._tex(
            f"{ASSETS_ROOT}/sprites/playerProjectileExplosion.png"
        )
        enemy_proj_explosion = self._tex(
            f"{ASSETS_ROOT}/sprites/enemyProjectileExplosion.png"
        )

        shield_frames = [
            self._tex(f"{ASSETS_ROOT}/sprites/Shield_0000_1.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/Shield_0001_2.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/Shield_0002_3.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/Shield_0003_4.png"),
        ]

        # ship explosion frames (A and B interleaved)
        ship_explosion_frames = [
            self._tex(f"{ASSETS_ROOT}/sprites/playerExplosionA.png"),
            self._tex(f"{ASSETS_ROOT}/sprites/playerExplosionB.png"),
        ]

        self.world = SpaceInvadersWorld(
            viewport=(vw, vh),
            ship=Ship(
                body=Kinematic2D(
                    transform=Transform2D(
                        center=Vec2(x=vw / 2 - ship_w / 2, y=vh - 50),
                        size=Size2D(width=ship_w, height=20),
                    ),
                    velocity=Vec2(x=0.0, y=0.0),
                    speed=300.0,
                ),
                texture=self._load_texture(
                    f"{ASSETS_ROOT}/sprites/player.png"
                ),
            ),
            explosion_texture=self._load_texture(
                f"{ASSETS_ROOT}/sprites/invaderExplosion.png"
            ),
            bullet_texture=self._load_texture(
                f"{ASSETS_ROOT}/sprites/Projectile_Player.png"
            ),
            projectile_specs={
                ProjectileKind.A: ProjectileSpec(
                    ProjectileKind.A,
                    proj_a,
                    fps=15.0,
                    speed=400.0,
                    size=Size2D(6, 14),
                ),
                ProjectileKind.B: ProjectileSpec(
                    ProjectileKind.B,
                    proj_b,
                    fps=15.0,
                    speed=350.0,
                    size=Size2D(6, 14),
                ),
                ProjectileKind.C: ProjectileSpec(
                    ProjectileKind.C,
                    proj_c,
                    fps=15.0,
                    speed=300.0,
                    size=Size2D(6, 14),
                ),
            },
            omega_charge_anim=Animation(frames=list(omega_charge), fps=12.0),
            omega_beam_anim=Animation(frames=list(omega_ray), fps=18.0),
            omega_beam_large_anim=Animation(
                frames=list(omega_ray_large), fps=18.0
            ),
            missile_anim=Animation(frames=list(missile), fps=18.0),
            target_texture=self._load_texture(
                f"{ASSETS_ROOT}/sprites/targetMark.png"
            ),
            fx_player_proj_tex=player_proj_explosion,
            fx_enemy_proj_tex=enemy_proj_explosion,
            fx_ttl=0.12,
            shield_anim=Animation(frames=shield_frames, fps=18.0, loop=True),
            ship_explosion_frames=ship_explosion_frames,
            ship_explosion_time=0.45,
        )
        # also store base texture for ship
        self.world.ship.base_texture = self.world.ship.texture

        alien_w, alien_h = 38, 28
        gap_x, gap_y = 18, 18
        cols, rows = 12, 5
        start_x, start_y = 80, 60

        row_frames = [
            (
                self._tex(f"{ASSETS_ROOT}/sprites/invaderS1.png"),
                self._tex(f"{ASSETS_ROOT}/sprites/invaderS2.png"),
            ),  # row 0
            (
                self._tex(f"{ASSETS_ROOT}/sprites/invaderM1.png"),
                self._tex(f"{ASSETS_ROOT}/sprites/invaderM2.png"),
            ),  # row 1
            (
                self._tex(f"{ASSETS_ROOT}/sprites/invaderM1.png"),
                self._tex(f"{ASSETS_ROOT}/sprites/invaderM2.png"),
            ),  # row 2
            (
                self._tex(f"{ASSETS_ROOT}/sprites/invaderL1.png"),
                self._tex(f"{ASSETS_ROOT}/sprites/invaderL2.png"),
            ),  # row 3
            (
                self._tex(f"{ASSETS_ROOT}/sprites/invaderL1.png"),
                self._tex(f"{ASSETS_ROOT}/sprites/invaderL2.png"),
            ),  # row 4
        ]

        for r in range(rows):
            f1, f2 = row_frames[r]
            for c in range(cols):
                x = start_x + c * (alien_w + gap_x)
                y = start_y + r * (alien_h + gap_y)
                self.world.aliens.append(
                    Alien(
                        position=Position2D(x=x, y=y),
                        size=Size2D(width=alien_w, height=alien_h),
                        velocity=Velocity2D(vx=0.0, vy=0.0),
                        speed=10.0,
                        row=r,
                        col=c,
                        anim=Animation(
                            frames=[
                                f1,
                                f2,
                            ],
                            fps=5.0,
                        ),
                    )
                )

        shelter_full = self._tex(f"{ASSETS_ROOT}/sprites/shelter_full.png")
        shelter_dmg = [
            self._tex(f"{ASSETS_ROOT}/sprites/shelterDamaged_{i}.png")
            for i in range(1, 10)
        ]

        shelter_w, shelter_h = 60, 40
        gap = (vw - 4 * shelter_w) / 5
        base_y = vh - 150
        xs = [gap + i * (shelter_w + gap) for i in range(4)]
        for x in xs:
            self.world.shelters.append(
                Shelter(
                    position=Position2D(float(x), float(base_y)),
                    size=Size2D(shelter_w, shelter_h),
                    tex_full=shelter_full,
                    tex_damaged=shelter_dmg,
                )
            )

        self.systems.extend(
            [
                SpaceInvadersInputSystem(),
                # SpaceInvadersHotkeysSystem(),
                # ShieldSystem(),
                # MissileTargetSystem(),
                ShipSystem(),
                # OmegaRaySystem(),
                # MissileSpawnSystem(),
                # BulletSpawnSystem(),
                # BulletMissileCollisionSystem(),
                # BulletBulletCollisionSystem(),
                # AlienSystem(),
                # AlienAnimationSystem(),
                # AlienFireSystem(),
                # BulletMoveSystem(),
                # BulletAnimationSystem(),
                # MissileHomingSystem(),
                # MissileAlienCollisionSystem(),
                # BulletAlienCollisionSystem(),
                # BulletShelterCollisionSystem(),
                # BulletShieldCollisionSystem(),
                # BulletShipCollisionSystem(),
                # ShipExplosionSystem(),
                # OmegaRayDamageSystem(),
                # ExplosionSystem(),
                # MissileCullSystem(),
                # BulletCullSystem(),
                # EffectsSystem(),
                SpaceInvadersRenderSystem(),
            ]
        )

    def _get_tick_context(self, input_frame, dt) -> SpaceInvadersTickContext:
        return SpaceInvadersTickContext(
            input_frame=input_frame,
            dt=dt,
            world=self.world,
            commands=self.context.command_queue,
        )

    def _tex(self, path: str) -> int:
        if not hasattr(self, "_tex_cache"):
            self._tex_cache = {}
        if path not in self._tex_cache:
            self._tex_cache[path] = self._load_texture(path)
        return self._tex_cache[path]
