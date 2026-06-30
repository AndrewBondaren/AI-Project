"""JSON validation types — docs/tz_json_validation.md § Архитектура."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from app.application.worldData.jsonValidation.index.seedRegistryIndex import SeedRegistryIndex
from app.application.worldData.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex


class ValidationKind(StrEnum):
    BUNDLE = "bundle"
    SECTION = "section"
    CRUD_PATCH = "crud_patch"
    SEED = "seed"
    CHARACTER = "character"
    BUILDING_TEMPLATE = "building_template"
    DISTRICT_TEMPLATE = "district_template"
    BARRIER_TEMPLATE = "barrier_template"


class SectionKey(StrEnum):
    WORLD = "world"
    RACES = "races"
    LOCATIONS = "locations"
    CONNECTION_NODES = "connection_nodes"
    CONNECTION_EDGES = "connection_edges"
    MAP_CELLS = "map_cells"
    PERKS = "perks"
    STATES = "states"


def active_section_keys(bundle: dict[str, Any]) -> frozenset[SectionKey]:
    out: set[SectionKey] = set()
    for key in SectionKey:
        if key.value in bundle:
            out.add(key)
    return frozenset(out)


@dataclass(frozen=True)
class ValidationRequest:
    kind: ValidationKind
    payload: dict[str, Any] | list[Any]
    section: SectionKey | None = None
    world_uid: str | None = None
    seed_snapshot: dict[str, list[dict]] | None = None


@dataclass
class ValidationIssue:
    schema_id: str
    path: str
    code: str
    message: str
    severity: Literal["error", "warn"] = "error"


@dataclass
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    normalized: dict[str, Any] | list[Any] | None = None


@dataclass
class ValidationContext:
    request: ValidationRequest
    bundle: dict[str, Any] | None = None
    world_uid: str | None = None
    active_sections: frozenset[SectionKey] = frozenset()
    normalized: dict[str, Any] | list[Any] | None = None
    index: WorldRegistryIndex | None = None
    seed_index: SeedRegistryIndex | None = None
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)
