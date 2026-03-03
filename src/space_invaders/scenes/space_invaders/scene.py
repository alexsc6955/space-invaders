"""
Space Invaders Scene
"""

from __future__ import annotations

from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.scenes.autoreg import (  # pyright: ignore[reportMissingImports]
    register_scene,
)
from mini_arcade_core.scenes.sim_scene import (  # pyright: ignore[reportMissingImports]
    SimScene,
)
from mini_arcade_core.spaces.geometry.bounds import Size2D

from space_invaders.constants import ASSETS_ROOT
from space_invaders.entities import (
    Alien,
    EntityId,
    ProjectileKind,
    ProjectileSpec,
    Shelter,
    Ship,
)
from space_invaders.scenes.space_invaders.models import (
    SpaceInvadersTickContext,
    SpaceInvadersWorld,
)
from space_invaders.scenes.space_invaders.systems import (
    AlienAnimationSystem,
    AlienFireSystem,
    AlienSystem,
    BulletAlienCollisionSystem,
    BulletAnimationSystem,
    BulletBulletCollisionSystem,
    BulletCullSystem,
    BulletMissileCollisionSystem,
    BulletMoveSystem,
    BulletShelterCollisionSystem,
    BulletShieldCollisionSystem,
    BulletShipCollisionSystem,
    BulletSpawnSystem,
    EffectsSystem,
    ExplosionSystem,
    MissileAlienCollisionSystem,
    MissileCullSystem,
    MissileHomingSystem,
    MissileSpawnSystem,
    MissileTargetSystem,
    OmegaRayDamageSystem,
    OmegaRaySystem,
    RoundStateSystem,
    ShieldSystem,
    ShipSystem,
    SpaceInvadersHotkeysSystem,
    SpaceInvadersInputSystem,
    SpaceInvadersPauseSystem,
    SpaceInvadersRenderSystem,
    build_space_invaders_capture_hotkeys_system,
    UfoCollisionSystem,
    UfoSystem,
)


@register_scene("space_invaders")
class SpaceInvadersScene(
    SimScene[SpaceInvadersTickContext, SpaceInvadersWorld]
):
    """
    Minimal scene: opens a window, clears screen, handles quit/ESC.
    """

    world: SpaceInvadersWorld
    _tex_cache: dict[str, int]
    tick_context_type = SpaceInvadersTickContext

    def on_enter(self):
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
        ship = Ship.build(
            EntityId.SHIP,
            "Player Ship",
            vw / 2,
            vh - 50,
            texture=self._load_texture(f"{ASSETS_ROOT}/sprites/player.png"),
            ship_explosion_frames=ship_explosion_frames,
        )
        ship.exploding = False
        ship.explode_timer = 0.0

        self.world = SpaceInvadersWorld(
            viewport=(vw, vh),
            entities=[
                ship,
            ],
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
            explosion_texture=self._tex(
                f"{ASSETS_ROOT}/sprites/invaderExplosion.png"
            ),
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
            ufo_texture=self._tex(f"{ASSETS_ROOT}/sprites/ufo.png"),
            ufo_spawn_timer=5.0,
        )

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

        i = EntityId.ALIEN_START.value
        for r in range(rows):
            f1, f2 = row_frames[r]
            for c in range(cols):
                x = start_x + c * (alien_w + gap_x)
                y = start_y + r * (alien_h + gap_y)
                start_id = i
                alien = Alien.build(
                    entity_id=start_id,
                    name=f"Alien {start_id}",
                    x=x,
                    y=y,
                    frames=[f1, f2],
                )
                alien.row = r
                alien.col = c
                alien.fire_cd = 0.0
                alien.exploding = False
                alien.explode_timer = 0.0
                self.world.entities.append(alien)
                i += 1

        shelter_full = self._tex(f"{ASSETS_ROOT}/sprites/shelter_full.png")
        shelter_dmg = [
            self._tex(f"{ASSETS_ROOT}/sprites/shelterDamaged_{i}.png")
            for i in range(1, 10)
        ]

        shelter_w = 60
        gap = (vw - 4 * shelter_w) / 5
        base_y = vh - 150
        xs = [gap + i * (shelter_w + gap) for i in range(4)]
        for x in xs:
            start_id = EntityId.SHELTER_START.value + len(
                self.world.get_entities_by_id_range(
                    EntityId.SHELTER_START, EntityId.SHELTER_END
                )
            )
            self.world.entities.append(
                Shelter.build(
                    entity_id=start_id,
                    name=f"Shelter {start_id}",
                    x=x,
                    y=base_y,
                    tex_full=shelter_full,
                    tex_damaged=shelter_dmg,
                )
            )

        self.systems.extend(
            [
                SpaceInvadersInputSystem(),
                SpaceInvadersPauseSystem(),
                SpaceInvadersHotkeysSystem(),
                build_space_invaders_capture_hotkeys_system(
                    self.context.services
                ),
                ShieldSystem(),
                MissileTargetSystem(),
                ShipSystem(),
                UfoSystem(),
                OmegaRaySystem(),
                MissileSpawnSystem(),
                BulletSpawnSystem(),
                BulletMissileCollisionSystem(),
                BulletBulletCollisionSystem(),
                AlienSystem(),
                AlienAnimationSystem(),
                AlienFireSystem(),
                BulletMoveSystem(),
                BulletAnimationSystem(),
                MissileHomingSystem(),
                MissileAlienCollisionSystem(),
                UfoCollisionSystem(),
                BulletAlienCollisionSystem(),
                BulletShelterCollisionSystem(),
                BulletShieldCollisionSystem(),
                BulletShipCollisionSystem(),
                OmegaRayDamageSystem(),
                ExplosionSystem(),
                MissileCullSystem(),
                BulletCullSystem(),
                RoundStateSystem(),
                EffectsSystem(),
                SpaceInvadersRenderSystem(),
            ]
        )

    def _tex(self, path: str) -> int:
        if not hasattr(self, "_tex_cache"):
            self._tex_cache = {}
        if path not in self._tex_cache:
            self._tex_cache[path] = self._load_texture(path)
        return self._tex_cache[path]
