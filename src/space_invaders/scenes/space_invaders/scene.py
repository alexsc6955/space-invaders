"""
Space Invaders Scene
"""

from __future__ import annotations

from dataclasses import replace

from mini_arcade_core.scenes.autoreg import (  # pyright: ignore[reportMissingImports]
    register_scene,
)
from mini_arcade_core.scenes.bootstrap import (
    scene_entities_config,
    scene_viewport,
)
from mini_arcade_core.scenes.game_scene import (  # pyright: ignore[reportMissingImports]
    GameScene,
    GameSceneSystemsConfig,
)

from space_invaders.scenes.commands import PauseSpaceInvadersCommand
from space_invaders.scenes.space_invaders.bootstrap import (
    build_space_invaders_world,
    resolve_space_invaders_template,
)
from space_invaders.scenes.space_invaders.models import (
    SpaceInvadersIntent,
    SpaceInvadersTickContext,
    SpaceInvadersWorld,
)
from space_invaders.scenes.space_invaders.pipeline import (
    build_space_invaders_systems,
)
from space_invaders.scenes.space_invaders.systems import ShipKillSwitchSystem
from space_invaders.scenes.space_invaders.systems.render import (
    SpaceInvadersRenderSystem,
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
    )


@register_scene("space_invaders")
class SpaceInvadersScene(
    GameScene[SpaceInvadersTickContext, SpaceInvadersWorld]
):
    """
    Minimal scene: opens a window, clears screen, handles quit/ESC.
    """

    world: SpaceInvadersWorld
    _tex_cache: dict[str, int]
    tick_context_type = SpaceInvadersTickContext
    capture_config = replace(
        GameScene.capture_config,
        replay_game_id="space_invaders",
    )
    systems_config = GameSceneSystemsConfig(
        controls_scene_key="space_invaders",
        intent_factory=_build_space_invaders_intent,
        input_system_name="space_invaders_input",
        pause_command_factory=lambda _ctx: PauseSpaceInvadersCommand(),
        extra_system_factories=(lambda _runtime: ShipKillSwitchSystem(),),
        render_system_factory=lambda _runtime: SpaceInvadersRenderSystem(),
    )

    def _resolve_template(
        self, raw_template: dict[str, object]
    ) -> dict[str, object]:
        return resolve_space_invaders_template(self._tex, raw_template)

    def debug_overlay_lines(self) -> list[str]:
        ship = self.world.ship()
        alive_aliens = len(self.world.aliens())
        lines = [
            f"score: {self.world.score}",
            f"lives: {self.world.lives}",
            f"aliens: {alive_aliens}",
            f"bullets: {len(self.world.bullets)}",
            f"missiles: {len(self.world.missiles)}",
            f"shield: {self.world.shield_active} cd={self.world.shield_cd_timer:.2f}",
            f"omega: {self.world.omega_active} cd={self.world.omega_cd_timer:.2f}",
            (
                "missile_targeting: "
                f"{self.world.missile_targeting} idx={self.world.missile_target_idx}"
            ),
        ]
        if ship is not None:
            lines.append(
                "ship_pos: "
                f"({ship.transform.center.x:.1f}, {ship.transform.center.y:.1f})"
            )
        return lines

    def on_enter(self):
        viewport = scene_viewport(self)
        entities_cfg = scene_entities_config(
            self,
            error_message=(
                "Missing gameplay.scenes.space_invaders.entities config"
            ),
        )
        self.world = build_space_invaders_world(
            viewport=viewport,
            entities_cfg=entities_cfg,
            load_texture=self._tex,
        )

        self.systems.extend(build_space_invaders_systems())

    def _tex(self, path: str) -> int:
        if not hasattr(self, "_tex_cache"):
            self._tex_cache = {}
        if path not in self._tex_cache:
            self._tex_cache[path] = self._load_texture(path)
        return self._tex_cache[path]
