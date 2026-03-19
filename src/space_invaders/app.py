"""
Main application entrypoint for Space Invaders.
"""

from __future__ import annotations

import json

from mini_arcade.modules.backend_loader import BackendLoader
from mini_arcade.modules.settings import Settings
from mini_arcade_core import run_game
from mini_arcade_core.utils import logger


def run():
    """
    Load settings profile and launch Space Invaders.
    """
    settings = Settings.for_game("space-invaders", required=True)
    backend_cfg = settings.backend_defaults(resolve_paths=True)
    backend = BackendLoader.load_backend(backend_cfg)

    engine_cfg = settings.engine_config_defaults()
    scene_cfg = settings.scene_defaults()
    gameplay_cfg = settings.gameplay_defaults()

    logger.debug(
        json.dumps(
            {
                "engine_config": engine_cfg,
                "scene_config": scene_cfg,
                "gameplay_config": gameplay_cfg,
                "backend_config": backend_cfg,
            },
            indent=4,
        )
    )
    logger.info("Starting Space Invaders...")
    run_game(
        engine_config=engine_cfg,
        scene_config=scene_cfg,
        backend=backend,
        gameplay_config=gameplay_cfg,
    )


if __name__ == "__main__":
    run()
