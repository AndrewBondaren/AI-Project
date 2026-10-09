"""Closed set of det-id tags — project_data_storage_tz.md § DET-1.

``kind`` is never a free string: a new tag means a new enum member here,
reviewed like a contract change. Tag = domain, keys = identity parts.
"""

from enum import StrEnum


class UidKind(StrEnum):
    """Domain tag in the canonical uid/rng string."""

    # Entity identity — world_uid root (entity_uid / entity_rng)
    DISTRICT = "district"
    AREA = "area"
    BUILDING = "building"
    LEVEL = "level"
    ENTRY = "entry"
    PASSAGE = "passage"
    ROOM = "room"
    CITY_NODE = "city_node"
    CONN_NODE = "conn_node"
    TRANSITION = "transition"
    GRADE = "grade"
    GRADE_SYSTEM = "grade_system"

    # Bake reproducibility — world_seed root (seed_uid / seed_rng)
    JOB_TILE = "tile"
    JOB_CHUNK = "chunk"
    JOB_TILE_EDGE = "tile_edge"
    GRADE_FACE = "grade_face"
    GRADE_INTERIOR = "grade_interior"
    RELIEF_PICK = "relief_pick"
    KIND_ROLL = "kind_roll"
    TERRAIN = "terrain"

    # rng streams — world_uid root (entity_rng)
    CASCADE = "cascade"
    CELL = "cell"
    TOPOLOGY = "topology"
    BARRIER = "barrier"
    FRONTAGE = "frontage"
    STRUCTURE = "structure"
    STAIR = "stair"


class LibraryKind(StrEnum):
    """Global template-library namespaces — no world root (plan D8)."""

    BUILDING_TEMPLATES = "building_templates"
    RELIEF_TEMPLATES = "relief_templates"
    STRUCTURE_TEMPLATES = "structure_templates"
    PERK_TEMPLATES = "perk_templates"
    RACE_TEMPLATES = "race_templates"
    LIBRARY_PACKS = "library_packs"
