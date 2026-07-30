"""World JSON bundle section keys — WP-24 / tz_world_bundle.md.

Single source of truth for skeleton/registry allowlists. Consumers:
``importLevels``, ``WorldBundleService``, ``bundleRemapService``.
"""

from __future__ import annotations

from typing import ClassVar, Literal

ImportLevel = Literal["registry", "skeleton"]


class BundleSection:
    """Canonical top-level keys of a world import/export JSON bundle."""

    WORLD: ClassVar[str] = "world"
    STATES: ClassVar[str] = "states"
    LOCATIONS: ClassVar[str] = "locations"
    CONNECTION_NODES: ClassVar[str] = "connection_nodes"
    CONNECTION_EDGES: ClassVar[str] = "connection_edges"
    RELIEF_TEMPLATES: ClassVar[str] = "relief_templates"
    BUILDING_TEMPLATES: ClassVar[str] = "building_templates"
    RACE_TEMPLATES: ClassVar[str] = "race_templates"
    PERK_TEMPLATES: ClassVar[str] = "perk_templates"
    # Rejected on skeleton/registry import (pack path) — not in allowlists below.
    MAP_CELLS: ClassVar[str] = "map_cells"

    # Removed from wire (breaking): "races", "perks" → *_templates (Q1).

    REGISTRY: ClassVar[frozenset[str]] = frozenset({WORLD})
    SKELETON: ClassVar[frozenset[str]] = frozenset({
        WORLD,
        STATES,
        LOCATIONS,
        CONNECTION_NODES,
        CONNECTION_EDGES,
        RELIEF_TEMPLATES,
        BUILDING_TEMPLATES,
        RACE_TEMPLATES,
        PERK_TEMPLATES,
    })

    @classmethod
    def for_level(cls, level: ImportLevel) -> frozenset[str]:
        if level == "registry":
            return cls.REGISTRY
        return cls.SKELETON
