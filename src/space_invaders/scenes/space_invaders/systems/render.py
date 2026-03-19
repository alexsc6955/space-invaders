"""
Rendering system for Space Invaders scene.
"""

from __future__ import annotations

from dataclasses import dataclass

from mini_arcade_core.engine.entities import BaseEntity
from mini_arcade_core.scenes.systems.builtins import (
    ConfiguredQueuedRenderSystem,
    EntityRenderRule,
    RenderOverlay,
)
from mini_arcade_core.scenes.systems.phases import SystemPhase

from space_invaders.scenes.space_invaders.draw_ops import (
    DrawEffects,
    DrawMissileTarget,
    DrawOmegaRay,
    DrawRegionTint,
    DrawShieldOverlay,
)
from space_invaders.scenes.space_invaders.models import (
    SpaceInvadersTickContext,
)


def _is_alien_entity(entity: BaseEntity) -> bool:
    tags = tuple(
        str(tag).strip().lower() for tag in getattr(entity, "tags", ())
    )
    if "alien" in tags:
        return True
    return (
        getattr(entity, "row", None) is not None
        and getattr(entity, "col", None) is not None
    )


def _is_alien_explosion(
    ctx: SpaceInvadersTickContext, entity: BaseEntity
) -> bool:
    return bool(
        _is_alien_entity(entity)
        and getattr(entity, "exploding", False)
        and ctx.world.explosion_texture is not None
    )


def _emit_alien_explosion(
    ctx: SpaceInvadersTickContext, rq: object, entity: BaseEntity
) -> None:
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


def _emit_hud(ctx: SpaceInvadersTickContext, rq: object) -> None:
    w = ctx.world
    vw, vh = w.viewport
    aliens_left = len(w.aliens())

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


@dataclass
class SpaceInvadersRenderSystem(
    ConfiguredQueuedRenderSystem[SpaceInvadersTickContext]
):
    """Declarative render composition for Space Invaders."""

    name: str = "min_render"
    phase: int = SystemPhase.RENDERING
    order: int = 100
    overlays: tuple[RenderOverlay[SpaceInvadersTickContext], ...] = (
        RenderOverlay.from_drawable(DrawRegionTint(), layer="effects", z=90),
        RenderOverlay.from_drawable(
            DrawShieldOverlay(), layer="lighting", z=30
        ),
        RenderOverlay.from_drawable(DrawOmegaRay(), layer="effects", z=40),
        RenderOverlay.from_drawable(
            DrawMissileTarget(), layer="effects", z=50
        ),
        RenderOverlay.from_drawable(DrawEffects(), layer="effects", z=60),
        RenderOverlay(emit=_emit_hud),
    )
    entity_rules: tuple[EntityRenderRule[SpaceInvadersTickContext], ...] = (
        EntityRenderRule(
            matches=_is_alien_explosion,
            emit=_emit_alien_explosion,
        ),
    )
