"""
Minimal main application for Space Invaders using mini-arcade-core and pygame backend.
"""

from __future__ import annotations

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

from space_invaders.constants import ASSETS_ROOT, FPS, WINDOW_SIZE

# pylint: enable=no-name-in-module


def run():
    """
    Main entry point for Space Invaders.

    - Auto-discovers scenes from the `space_invaders.scenes` package.
    - Configures the pygame backend with the Space Invaders font.
    - Sets up the game window with specified dimensions and background color.
    - Runs the game with the initial scene set to "menu".
    """
    scene_registry = SceneRegistry(_factories={}).discover(
        "space_invaders.scenes", "mini_arcade_core.scenes"
    )

    font_path = ASSETS_ROOT / "fonts" / "pixel_arial_11" / "PIXEAB__.TTF"

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
        "fonts": [{"name": "default", "path": str(font_path), "size": 24}],
        "audio": {
            "enable": False,
        },
    }
    backend_settings = NativeBackendSettings.from_dict(settings_data)
    backend = NativeBackend(settings=backend_settings)

    game_config = GameConfig(
        initial_scene="space_invaders",
        fps=FPS,
        backend=backend,
    )
    logger.info("Starting Space Invaders...")
    logger.info(backend_settings.to_dict())
    run_game(game_config=game_config, scene_registry=scene_registry)


if __name__ == "__main__":
    run()
