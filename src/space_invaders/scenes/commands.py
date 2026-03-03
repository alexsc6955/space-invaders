"""
Scene-level commands for Space Invaders.
"""

from __future__ import annotations

from mini_arcade_core.engine.commands import (
    ChangeSceneCommand,
    Command,
    CommandContext,
    PushSceneIfMissingCommand,
    RemoveSceneCommand,
)
from mini_arcade_core.engine.scenes.models import ScenePolicy


class StartSpaceInvadersCommand(Command):
    """Change from menu to gameplay."""

    def execute(self, context: CommandContext):
        ChangeSceneCommand("space_invaders").execute(context)


class PauseSpaceInvadersCommand(Command):
    """Push pause overlay and block gameplay updates/input below it."""

    def execute(self, context: CommandContext):
        PushSceneIfMissingCommand(
            "space_invaders_pause",
            as_overlay=True,
            policy=ScenePolicy(
                blocks_update=True,
                blocks_input=True,
                is_opaque=False,
                receives_input=True,
            ),
        ).execute(context)


class ResumeSpaceInvadersCommand(Command):
    """Resume from pause overlay."""

    def execute(self, context: CommandContext):
        RemoveSceneCommand("space_invaders_pause").execute(context)


class BackToMenuCommand(Command):
    """Return to game menu."""

    def execute(self, context: CommandContext):
        ChangeSceneCommand("space_invaders_menu").execute(context)


class RestartSpaceInvadersCommand(Command):
    """Restart gameplay from a fresh scene instance."""

    def execute(self, context: CommandContext):
        ChangeSceneCommand("space_invaders").execute(context)
