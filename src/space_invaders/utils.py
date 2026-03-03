"""
Space Invaders utils
"""

from __future__ import annotations

from pathlib import Path

from mini_arcade_core.utils import find_assets_root as _find_assets_root


def find_assets_root() -> Path:
    """Return the path to the `assets` directory.

    Works in:
    - dev: repo/assets (when running from source tree)
    - pip install: site-packages/assets
    - PyInstaller onefile: _MEIPASS/assets (if bundled with --add-data)

    :raises FileNotFoundError: If the assets directory cannot be found.
    """
    return _find_assets_root(__file__)
