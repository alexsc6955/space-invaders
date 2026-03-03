"""
Scene-level commands for Space Invaders.
"""

from __future__ import annotations

from mini_arcade_core.engine.commands import Command, CommandContext
from mini_arcade_core.engine.scenes.models import ScenePolicy


class StartSpaceInvadersCommand(Command):
    """Change from menu to gameplay."""

    def execute(self, context: CommandContext):
        context.managers.scenes.change("space_invaders")


class PauseSpaceInvadersCommand(Command):
    """Push pause overlay and block gameplay updates/input below it."""

    def execute(self, context: CommandContext):
        scene_id = "space_invaders_pause"
        if context.managers.scenes.has_scene(scene_id):
            return
        context.managers.scenes.push(
            scene_id,
            as_overlay=True,
            policy=ScenePolicy(
                blocks_update=True,
                blocks_input=True,
                is_opaque=False,
                receives_input=True,
            ),
        )


class ResumeSpaceInvadersCommand(Command):
    """Resume from pause overlay."""

    def execute(self, context: CommandContext):
        context.managers.scenes.remove_scene("space_invaders_pause")


class BackToMenuCommand(Command):
    """Return to game menu."""

    def execute(self, context: CommandContext):
        context.managers.scenes.change("space_invaders_menu")


class RestartSpaceInvadersCommand(Command):
    """Restart gameplay from a fresh scene instance."""

    def execute(self, context: CommandContext):
        context.managers.scenes.change("space_invaders")
