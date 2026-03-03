"""
Minimal main application for Space Invaders using mini-arcade-core and pygame backend.
"""

from __future__ import annotations

from pathlib import Path

from mini_arcade_core import (  # pyright: ignore[reportMissingImports]
    GameConfig,
    SceneRegistry,
    run_game,
)
from mini_arcade_core.utils import logger

# Justification: in editable installs, this module is provided by the package.
# pylint: disable=no-name-in-module
# from mini_arcade_pygame_backend import (  # pyright: ignore[reportMissingImports]
#     PygameBackend,
#     PygameBackendSettings,
# )
from mini_arcade_native_backend import (  # pyright: ignore[reportMissingImports]
    NativeBackend,
    NativeBackendSettings,
)

from space_invaders.constants import FPS, WINDOW_SIZE

# pylint: enable=no-name-in-module


def _default_system_font() -> str | None:
    """
    Return a readable system font path for the native backend.
    """
    candidates = [
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def run():
    """
    Main entry point for Space Invaders.

    - Auto-discovers scenes from the `space_invaders.scenes` package.
    - Sets up the game window with specified dimensions and background color.
    - Runs the game with the initial scene set to "space_invaders_menu".
    """
    scene_registry = SceneRegistry(_factories={}).discover(
        "space_invaders.scenes", "mini_arcade_core.scenes"
    )

    w_width, w_height = WINDOW_SIZE

    # NOTE: The reason we´re changing this to be a dictionary is to
    # add yaml-based and/or cli arguments-based configuration in the future.
    settings_data = {
        "window": {
            "width": w_width,
            "height": w_height,
            "title": "Space Invaders (Pygame + mini-arcade-core)",
            "high_dpi": False,
            "resizable": True,
        },
        "renderer": {"background_color": (30, 30, 30)},
        "audio": {
            "enable": False,
        },
    }
    font_path = _default_system_font()
    if font_path is not None:
        settings_data["fonts"] = [
            {"name": "default", "path": font_path, "size": 24}
        ]
    else:
        logger.warning(
            "No system font found; UI text may not render on native backend."
        )
    backend_settings = NativeBackendSettings.from_dict(settings_data)
    backend = NativeBackend(settings=backend_settings)

    game_config = GameConfig(
        initial_scene="space_invaders_menu",
        fps=FPS,
        backend=backend,
        virtual_resolution=WINDOW_SIZE,
    )
    logger.info("Starting Space Invaders...")
    logger.info(backend_settings.to_dict())
    run_game(game_config=game_config, scene_registry=scene_registry)


if __name__ == "__main__":
    run()
