"""
Bootstrap helpers for Space Invaders scene setup.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from mini_arcade_core.engine.animation import Animation
from mini_arcade_core.scenes.bootstrap import resolve_named_templates
from mini_arcade_core.spaces.geometry.bounds import Size2D

from space_invaders.constants import ASSETS_ROOT
from space_invaders.entities import (
    EntityId,
    ProjectileKind,
    ProjectileSpec,
    Ship,
)
from space_invaders.scenes.space_invaders.models import SpaceInvadersWorld
from space_invaders.scenes.space_invaders.spawn import (
    alien_formation_spec,
    shelter_row_spec,
    spawn_alien_formation,
    spawn_shelter_row,
)


@dataclass(frozen=True)
class SpaceInvadersAssetBundle:  # pylint: disable=too-many-instance-attributes
    """Resolved textures, animations, and templates needed to boot a round."""

    templates: dict[str, dict[str, Any]]
    projectile_specs: dict[ProjectileKind, ProjectileSpec]
    omega_charge_anim: Animation
    omega_beam_anim: Animation
    omega_beam_large_anim: Animation
    shield_anim: Animation
    ship_explosion_frames: list[int]
    player_proj_explosion: int
    enemy_proj_explosion: int
    invader_explosion_texture: int
    target_texture: int


def resolve_space_invaders_template(
    load_texture,
    raw_template: dict[str, Any],
) -> dict[str, Any]:
    """
    Resolve texture-bearing template fields into runtime textures.
    """
    template = deepcopy(raw_template)

    sprite_path = template.pop("sprite_path", None)
    if isinstance(sprite_path, str) and sprite_path.strip():
        template["sprite"] = {
            **(template.get("sprite", {}) or {}),
            "texture": load_texture(sprite_path),
        }

    sprite_full_path = template.pop("sprite_full_path", None)
    if isinstance(sprite_full_path, str) and sprite_full_path.strip():
        tex_full = load_texture(sprite_full_path)
        template["tex_full"] = tex_full
        template["sprite"] = {
            **(template.get("sprite", {}) or {}),
            "texture": tex_full,
        }

    damaged_paths = template.pop("sprite_damaged_paths", None)
    if isinstance(damaged_paths, list):
        template["tex_damaged"] = [
            load_texture(str(path))
            for path in damaged_paths
            if str(path).strip()
        ]

    frame_paths = template.pop("frame_paths", None)
    if isinstance(frame_paths, list):
        template["frames"] = [
            load_texture(str(path))
            for path in frame_paths
            if str(path).strip()
        ]

    explosion_paths = template.pop("ship_explosion_frame_paths", None)
    if isinstance(explosion_paths, list):
        template["ship_explosion_frames"] = [
            load_texture(str(path))
            for path in explosion_paths
            if str(path).strip()
        ]

    return template


def build_projectile_specs(
    load_texture,
    entities_cfg: dict[str, Any],
) -> dict[ProjectileKind, ProjectileSpec]:
    """
    Build runtime projectile specs from config data.
    """
    raw_specs = entities_cfg.get("projectile_specs", {}) or {}
    if not isinstance(raw_specs, dict):
        return {}

    specs: dict[ProjectileKind, ProjectileSpec] = {}
    for key, spec_data in raw_specs.items():
        try:
            kind = ProjectileKind[str(key).strip().upper()]
        except KeyError:
            continue
        if not isinstance(spec_data, dict):
            continue
        frame_paths = spec_data.get("frame_paths", []) or []
        frames = tuple(
            load_texture(str(path))
            for path in frame_paths
            if str(path).strip()
        )
        size = spec_data.get("size", {}) or {}
        specs[kind] = ProjectileSpec(
            kind,
            frames=tuple(frames[:4]),
            fps=float(spec_data.get("fps", 15.0)),
            speed=float(spec_data.get("speed", 300.0)),
            size=Size2D(
                float(size.get("width", 6.0)),
                float(size.get("height", 14.0)),
            ),
        )
    return specs


def load_space_invaders_assets(
    *,
    load_texture,
    entities_cfg: dict[str, Any],
) -> SpaceInvadersAssetBundle:
    """
    Load resolved templates plus animation/sprite assets used by the scene.
    """
    templates = resolve_named_templates(
        entities_cfg.get("templates", {}) or {},
        resolver=lambda template: resolve_space_invaders_template(
            load_texture,
            template,
        ),
    )

    omega_charge = [
        load_texture(f"{ASSETS_ROOT}/sprites/RayCharge_1.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/RayCharge_2.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/RayCharge_3.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/RayCharge_4.png"),
    ]
    omega_ray = [
        load_texture(f"{ASSETS_ROOT}/sprites/OmegaRay_1.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/OmegaRay_2.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/OmegaRay_3.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/OmegaRay_4.png"),
    ]
    omega_ray_large = [
        load_texture(f"{ASSETS_ROOT}/sprites/OmegaRay_Large_1.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/OmegaRay_Large_2.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/OmegaRay_Large_3.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/OmegaRay_Large_4.png"),
    ]
    shield_frames = [
        load_texture(f"{ASSETS_ROOT}/sprites/Shield_0000_1.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/Shield_0001_2.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/Shield_0002_3.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/Shield_0003_4.png"),
    ]
    ship_explosion_frames = [
        load_texture(f"{ASSETS_ROOT}/sprites/playerExplosionA.png"),
        load_texture(f"{ASSETS_ROOT}/sprites/playerExplosionB.png"),
    ]

    return SpaceInvadersAssetBundle(
        templates=templates,
        projectile_specs=build_projectile_specs(load_texture, entities_cfg),
        omega_charge_anim=Animation(frames=omega_charge, fps=12.0),
        omega_beam_anim=Animation(frames=omega_ray, fps=18.0),
        omega_beam_large_anim=Animation(frames=omega_ray_large, fps=18.0),
        shield_anim=Animation(frames=shield_frames, fps=18.0, loop=True),
        ship_explosion_frames=ship_explosion_frames,
        player_proj_explosion=load_texture(
            f"{ASSETS_ROOT}/sprites/playerProjectileExplosion.png"
        ),
        enemy_proj_explosion=load_texture(
            f"{ASSETS_ROOT}/sprites/enemyProjectileExplosion.png"
        ),
        invader_explosion_texture=load_texture(
            f"{ASSETS_ROOT}/sprites/invaderExplosion.png"
        ),
        target_texture=load_texture(f"{ASSETS_ROOT}/sprites/targetMark.png"),
    )


def build_space_invaders_world(  # pylint: disable=too-many-locals
    *,
    viewport: tuple[float, float],
    entities_cfg: dict[str, Any],
    load_texture,
) -> SpaceInvadersWorld:
    """
    Build the initial Space Invaders world and opening formation.
    """
    assets = load_space_invaders_assets(
        load_texture=load_texture,
        entities_cfg=entities_cfg,
    )
    templates = assets.templates
    projectile_specs = assets.projectile_specs
    bullet_template = templates.get("bullet", {})
    missile_template = templates.get("missile", {})
    ship_template = templates.get("ship", {})
    alien_template = templates.get("alien", {})
    shelter_template = templates.get("shelter", {})
    ufo_template = templates.get("ufo", {})
    formation_spec = alien_formation_spec(
        entities_cfg.get("alien_grid", {}) or {},
        resolve_texture=load_texture,
    )
    shelter_spec = shelter_row_spec(entities_cfg.get("shelters", {}) or {})

    if ship_template:
        ship_template = deepcopy(ship_template)
        ship_template["ship_explosion_frames"] = (
            ship_template.get("ship_explosion_frames")
            or assets.ship_explosion_frames
        )
    ship = Ship.build_from_template(
        template=ship_template,
        viewport=viewport,
        entity_id=int(EntityId.SHIP),
        name=str(ship_template.get("name", "Player Ship")),
    )
    ship.exploding = False
    ship.explode_timer = 0.0

    world = SpaceInvadersWorld(
        viewport=viewport,
        entities=[ship],
        entity_templates=templates,
        alien_formation_spec=formation_spec,
        shelter_row_spec=shelter_spec,
        bullet_texture=int(
            ((bullet_template.get("sprite", {}) or {}).get("texture", 0)) or 0
        ),
        projectile_specs=projectile_specs,
        explosion_texture=assets.invader_explosion_texture,
        omega_charge_anim=assets.omega_charge_anim,
        omega_beam_anim=assets.omega_beam_anim,
        omega_beam_large_anim=assets.omega_beam_large_anim,
        missile_anim=Animation(
            frames=list(missile_template.get("frames", []) or []),
            fps=float(
                ((missile_template.get("anim", {}) or {}).get("fps", 18.0))
            ),
            loop=bool(
                ((missile_template.get("anim", {}) or {}).get("loop", True))
            ),
        ),
        target_texture=assets.target_texture,
        fx_player_proj_tex=assets.player_proj_explosion,
        fx_enemy_proj_tex=assets.enemy_proj_explosion,
        fx_ttl=0.12,
        shield_anim=assets.shield_anim,
        ufo_texture=int(
            ((ufo_template.get("sprite", {}) or {}).get("texture", 0)) or 0
        ),
        ufo_spawn_timer=float(ufo_template.get("spawn_timer", 5.0)),
        ufo_spawn_min=float(ufo_template.get("spawn_min", 12.0)),
        ufo_spawn_max=float(ufo_template.get("spawn_max", 20.0)),
        ufo_speed=float(
            ((ufo_template.get("kinematic", {}) or {}).get("max_speed", 95.0))
        ),
        ufo_points=int(ufo_template.get("points", 100)),
    )

    world.entities.extend(
        spawn_alien_formation(
            world=world,
            viewport=viewport,
            alien_template=alien_template,
            spec=formation_spec,
        )
    )
    world.entities.extend(
        spawn_shelter_row(
            world=world,
            viewport=viewport,
            shelter_template=shelter_template,
            spec=shelter_spec,
        )
    )
    return world


__all__ = [
    "SpaceInvadersAssetBundle",
    "build_space_invaders_world",
    "build_projectile_specs",
    "load_space_invaders_assets",
    "resolve_space_invaders_template",
]
