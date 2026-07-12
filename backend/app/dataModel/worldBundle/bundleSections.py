"""World JSON bundle section keys — WP-24 import levels.

Single source of truth for skeleton/registry allowlists. Consumers:
``importLevels``, ``WorldBundleService``, ``bundleRemapService``.
"""

from __future__ import annotations

from typing import ClassVar, Literal

ImportLevel = Literal["registry", "skeleton"]


class BundleSection:
    """Canonical top-level keys of a world import/export JSON bundle."""

    WORLD: ClassVar[str] = "world"
    RACES: ClassVar[str] = "races"
    PERKS: ClassVar[str] = "perks"
    STATES: ClassVar[str] = "states"
    LOCATIONS: ClassVar[str] = "locations"
    CONNECTION_NODES: ClassVar[str] = "connection_nodes"
    CONNECTION_EDGES: ClassVar[str] = "connection_edges"
    # Rejected on skeleton/registry import (pack path) — not in allowlists below.
    MAP_CELLS: ClassVar[str] = "map_cells"

    REGISTRY: ClassVar[frozenset[str]] = frozenset({WORLD})
    SKELETON: ClassVar[frozenset[str]] = frozenset({
        WORLD,
        RACES,
        PERKS,
        STATES,
        LOCATIONS,
        CONNECTION_NODES,
        CONNECTION_EDGES,
    })

    @classmethod
    def for_level(cls, level: ImportLevel) -> frozenset[str]:
        if level == "registry":
            return cls.REGISTRY
        return cls.SKELETON
