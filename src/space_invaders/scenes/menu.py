"""
Main menu scene for Space Invaders.
"""

from __future__ import annotations

from mini_arcade_core.engine.commands import QuitCommand
from mini_arcade_core.scenes.autoreg import register_scene
from mini_arcade_core.ui.menu import BaseMenuScene, MenuItem, MenuStyle

from space_invaders.scenes.commands import StartSpaceInvadersCommand


@register_scene("space_invaders_menu")
class SpaceInvadersMenuScene(BaseMenuScene):
    """Main menu scene for Space Invaders."""

    @property
    def menu_title(self) -> str | None:
        return "SPACE INVADERS"

    def menu_style(self) -> MenuStyle:
        return MenuStyle(
            background_color=(12, 12, 16, 255),
            panel_color=(24, 24, 32, 240),
            button_enabled=True,
            button_fill=(16, 16, 24, 255),
            button_border=(90, 120, 120, 255),
            button_selected_border=(120, 255, 160, 255),
            normal=(220, 220, 220, 255),
            selected=(255, 255, 255, 255),
            hint="ENTER start  ESC quit",
            hint_color=(170, 170, 170, 255),
        )

    def menu_items(self):
        return [
            MenuItem("start", "START GAME", StartSpaceInvadersCommand),
            MenuItem("quit", "QUIT", QuitCommand),
        ]
