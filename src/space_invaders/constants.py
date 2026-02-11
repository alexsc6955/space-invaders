"""
Constants for the game.
"""

from __future__ import annotations

from space_invaders.utils import find_assets_root

ASSETS_ROOT = find_assets_root()
ROOT = ASSETS_ROOT.parent

FPS = 60
WINDOW_SIZE = (800, 600)
