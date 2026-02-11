"""
Space Invaders utils
"""

from __future__ import annotations

import sys
from pathlib import Path


def find_assets_root() -> Path:
    """Return the path to the `assets` directory.

    Works in:
    - dev: repo/assets (when running from source tree)
    - pip install: site-packages/assets
    - PyInstaller onefile: _MEIPASS/assets (if bundled with --add-data)

    :raises FileNotFoundError: If the assets directory cannot be found.
    """
    # 1) PyInstaller onefile support
    # pylint: disable=protected-access
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
        candidate = base / "assets"
        if candidate.is_dir():
            return candidate
    # pylint: enable=protected-access

    # 2) Dev / pip-installed: walk upwards and look for an `assets` folder
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "assets"
        if candidate.is_dir():
            return candidate

    raise FileNotFoundError("Could not locate 'assets' directory.")
