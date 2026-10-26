"""Application inputs/results for HY-12's common placement adapter."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.application.jsonValidation.types import FieldPathError
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.placement import (
    PlacementDependency, PlacementOverlap, PlacementSeparation, PreparedPlacement,
)
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.dataModel.planning.identity.planKey import OutputFingerprint


class WaterPreparationCode(StrEnum):
    SNAPSHOT = "WATER_PLACEMENT_SNAPSHOT"
    GEOMETRY = "WATER_PLACEMENT_GEOMETRY"
    FLOOR = "WATER_PLACEMENT_FLOOR"
    CAP_REACHED = "WATER_PLACEMENT_CAP_REACHED"
    KIND_MISMATCH = "WATER_PLACEMENT_KIND_MISMATCH"
    DEGENERATE_RING = "WATER_PLACEMENT_DEGENERATE_RING"
    MERGED_SOURCES = "WATER_PLACEMENT_MERGED_SOURCES"


class WaterGeometryError(ValueError):
    """An invalid source cannot supply a geometric placement candidate."""


@dataclass(frozen=True)
class WaterPlacementContext:
    world_uid: str
    snapshot_uid: str
    snapshot_revision: OutputFingerprint
    topology: WorldTopology
    surface_z: Mapping[Coord, int]
    z_min: int
    anchors: Mapping[str, Coord]
    location_subtypes: Mapping[str, GeographicSubtype]
    auto_specificity: Mapping[str, int | None]
    dependencies: Mapping[str, tuple[PlacementDependency, ...]]
    permitted_overlaps: Mapping[str, tuple[PlacementOverlap, ...]]
    separations: Mapping[str, tuple[PlacementSeparation, ...]]


@dataclass(frozen=True)
class PreparedWaterEntry:
    source: DeclaredBasin | DeclaredCoastline | DeclaredLake
    prepared: PreparedPlacement
    z_water_level: int
    floor_z: int
    kind: BasinKind
    liquid: MaterialKey


@dataclass(frozen=True)
class WaterPreparationFailure:
    source_uid: str
    issue: FieldPathError


@dataclass(frozen=True)
class WaterPlacementPreparation:
    world_uid: str
    snapshot_uid: str
    snapshot_revision: OutputFingerprint
    entries: tuple[PreparedWaterEntry, ...]
    failures: tuple[WaterPreparationFailure, ...]
    notices: tuple[FieldPathError, ...]

    @property
    def objects(self) -> tuple[PreparedPlacement, ...]:
        return tuple(entry.prepared for entry in self.entries)
