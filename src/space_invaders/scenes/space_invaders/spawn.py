"""
Spawn policies for Space Invaders scene bootstrap.
"""

from __future__ import annotations

from dataclasses import dataclass

from mini_arcade_core.engine.entities import BaseEntity

from space_invaders.entities import Alien, Shelter
from space_invaders.scenes.space_invaders.models import SpaceInvadersWorld


@dataclass(frozen=True)
class AlienFormationSpec:  # pylint: disable=too-many-instance-attributes
    """Typed configuration for the opening alien formation."""

    cols: int = 12
    rows: int = 5
    start_x: float = 80.0
    start_y: float = 60.0
    gap_x: float = 48.0
    gap_y: float = 38.0
    row_frames: tuple[tuple[int, ...], ...] = ()
    fire_base: float = 2.0
    fire_span: float = 3.0


@dataclass(frozen=True)
class ShelterRowSpec:
    """Typed configuration for the opening shelter row."""

    shelter_count: int = 4
    bottom_offset: float = 150.0


def alien_formation_spec(
    raw_cfg: dict[str, object] | None,
    *,
    resolve_texture,
) -> AlienFormationSpec:
    """
    Normalize alien-grid config into a typed formation spec.
    """
    raw_cfg = raw_cfg or {}
    start = raw_cfg.get("start", {}) or {}
    spacing = raw_cfg.get("spacing", {}) or {}
    row_frame_paths = raw_cfg.get("row_frame_paths", []) or []
    row_frames = tuple(
        tuple(
            resolve_texture(str(path)) for path in paths if str(path).strip()
        )
        for paths in row_frame_paths
        if isinstance(paths, list)
    )
    fire_cd = raw_cfg.get("fire_cd", {}) or {}
    return AlienFormationSpec(
        cols=int(raw_cfg.get("cols", 12)),
        rows=int(raw_cfg.get("rows", 5)),
        start_x=float(start.get("x", 80.0)),
        start_y=float(start.get("y", 60.0)),
        gap_x=float(spacing.get("x", 48.0)),
        gap_y=float(spacing.get("y", 38.0)),
        row_frames=row_frames,
        fire_base=float(fire_cd.get("base", 2.0)),
        fire_span=float(fire_cd.get("span", 3.0)),
    )


def shelter_row_spec(raw_cfg: dict[str, object] | None) -> ShelterRowSpec:
    """
    Normalize shelter-row config into a typed spawn spec.
    """
    raw_cfg = raw_cfg or {}
    return ShelterRowSpec(
        shelter_count=int(raw_cfg.get("count", 4)),
        bottom_offset=float(raw_cfg.get("bottom_offset", 150.0)),
    )


def spawn_alien_formation(
    *,
    world: SpaceInvadersWorld,
    viewport: tuple[float, float],
    alien_template: dict[str, object],
    spec: AlienFormationSpec,
) -> list[BaseEntity]:
    """
    Build the opening alien formation from config data.
    """
    fire_denominator = max((spec.rows * spec.cols) - 1, 1)
    alien_domain_start = world.entity_id_domain("alien").start_id
    reserved_alien_ids: set[int] = set()
    spawned: list[BaseEntity] = []

    for row in range(spec.rows):
        if row >= len(spec.row_frames) or len(spec.row_frames[row]) < 2:
            continue
        frame_a = int(spec.row_frames[row][0])
        frame_b = int(spec.row_frames[row][1])
        for col in range(spec.cols):
            alien_id = world.allocate_entity_id_for(
                "alien",
                reserved_ids=reserved_alien_ids,
            )
            if alien_id is None:
                continue
            reserved_alien_ids.add(alien_id)
            spawned.append(
                Alien.build_from_template(
                    template=alien_template,
                    viewport=viewport,
                    entity_id=alien_id,
                    name=f"Alien {alien_id}",
                    row=row,
                    col=col,
                    fire_cd=spec.fire_base
                    + (
                        spec.fire_span
                        * (alien_id - alien_domain_start)
                        / fire_denominator
                    ),
                    overrides={
                        "transform": {
                            "position": {
                                "x": spec.start_x + col * spec.gap_x,
                                "y": spec.start_y + row * spec.gap_y,
                            }
                        },
                        "sprite": {"texture": frame_a},
                        "anim": {"frames": [frame_a, frame_b]},
                    },
                )
            )
    return spawned


def spawn_shelter_row(
    *,
    world: SpaceInvadersWorld,
    viewport: tuple[float, float],
    shelter_template: dict[str, object],
    spec: ShelterRowSpec,
) -> list[BaseEntity]:
    """
    Build the shelter row for a new round.
    """
    view_width, view_height = viewport
    shelter_w = float(
        (
            (shelter_template.get("transform", {}) or {}).get("size", {}) or {}
        ).get("width", 60.0)
    )
    gap = (view_width - spec.shelter_count * shelter_w) / float(
        spec.shelter_count + 1
    )
    base_y = view_height - spec.bottom_offset
    reserved_shelter_ids: set[int] = set()
    spawned: list[BaseEntity] = []

    for index in range(spec.shelter_count):
        shelter_id = world.allocate_entity_id_for(
            "shelter",
            reserved_ids=reserved_shelter_ids,
        )
        if shelter_id is None:
            continue
        reserved_shelter_ids.add(shelter_id)
        spawned.append(
            Shelter.build_from_template(
                template=shelter_template,
                viewport=viewport,
                entity_id=shelter_id,
                name=f"Shelter {shelter_id}",
                overrides={
                    "transform": {
                        "position": {
                            "x": gap + index * (shelter_w + gap),
                            "y": base_y,
                        }
                    },
                },
            )
        )
    return spawned


__all__ = [
    "AlienFormationSpec",
    "ShelterRowSpec",
    "alien_formation_spec",
    "spawn_alien_formation",
    "shelter_row_spec",
    "spawn_shelter_row",
]
