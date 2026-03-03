"""
Pause overlay scene for Space Invaders.
"""

from __future__ import annotations

from mini_arcade_core.scenes.autoreg import register_scene
from mini_arcade_core.ui.menu import BaseMenuScene, MenuItem, MenuStyle

from space_invaders.scenes.commands import (
    BackToMenuCommand,
    RestartSpaceInvadersCommand,
    ResumeSpaceInvadersCommand,
)


@register_scene("space_invaders_pause")
class SpaceInvadersPauseScene(BaseMenuScene):
    """Pause overlay scene."""

    @property
    def menu_title(self) -> str | None:
        return "PAUSED"

    def menu_style(self) -> MenuStyle:
        return MenuStyle(
            overlay_color=(0, 0, 0, 190),
            panel_color=(20, 20, 30, 235),
            button_enabled=True,
            button_fill=(12, 12, 20, 255),
            button_border=(90, 90, 120, 255),
            button_selected_border=(120, 255, 160, 255),
            normal=(225, 225, 225, 255),
            selected=(255, 255, 255, 255),
            hint="ENTER select  ESC resume",
            hint_color=(180, 180, 180, 255),
        )

    def menu_items(self):
        return [
            MenuItem("continue", "CONTINUE", ResumeSpaceInvadersCommand),
            MenuItem("restart", "RESTART", RestartSpaceInvadersCommand),
            MenuItem("menu", "MAIN MENU", BackToMenuCommand),
        ]

    def quit_command(self):
        return ResumeSpaceInvadersCommand()
