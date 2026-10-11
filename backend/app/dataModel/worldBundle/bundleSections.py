"""World JSON bundle section keys — WP-24 / tz_world_bundle.md.

Single source of truth for skeleton/registry allowlists. Consumers:
``importLevels``, ``WorldBundleService``, ``bundleRemapService``.
"""

from __future__ import annotations

from types import MappingProxyType
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


class BundleArchiveLayout:
    """Transport paths, separate from section keys (TZ library packs §4.2).

    Library and baked-pack files are subtrees, not JSON bundle sections.
    Their member layouts are supplied by C-5/C-6; these roots do not allow
    arbitrary files to bypass the archive reader's allowlist.
    """

    MANIFEST: ClassVar[str] = "bundle.manifest.json"
    SKELETON_PREFIX: ClassVar[str] = "skeleton/"
    LIBRARY_PREFIX: ClassVar[str] = "library/"
    PACK_PREFIX: ClassVar[str] = "pack/"


# Explicit wire mapping: adding a section requires choosing its archive path.
SECTION_PATHS = MappingProxyType({
    BundleSection.WORLD: "skeleton/world.json",
    BundleSection.STATES: "skeleton/states.json",
    BundleSection.LOCATIONS: "skeleton/locations.json",
    BundleSection.CONNECTION_NODES: "skeleton/connection_nodes.json",
    BundleSection.CONNECTION_EDGES: "skeleton/connection_edges.json",
    BundleSection.RELIEF_TEMPLATES: "skeleton/relief_templates.json",
    BundleSection.BUILDING_TEMPLATES: "skeleton/building_templates.json",
    BundleSection.RACE_TEMPLATES: "skeleton/race_templates.json",
    BundleSection.PERK_TEMPLATES: "skeleton/perk_templates.json",
})
PATH_SECTIONS = MappingProxyType({path: key for key, path in SECTION_PATHS.items()})

assert set(SECTION_PATHS) == BundleSection.SKELETON
assert len(PATH_SECTIONS) == len(SECTION_PATHS)
