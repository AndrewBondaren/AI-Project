"""Application inputs/results for HY-12's common placement adapter."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import TypeAdapter

from app.application.jsonValidation.types import FieldPathError
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.relief.bathymetry.floorProfile import BasinFloorProfile, FieldFloorProfile, SampledFloorProfile
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


class WaterGeometryView(Protocol):
    """Geometry reads only these fields; placement/admission state stays outside."""

    @property
    def topology(self) -> WorldTopology: ...
    @property
    def surface_z(self) -> Mapping[Coord, int]: ...
    @property
    def anchors(self) -> Mapping[str, Coord]: ...


@dataclass(frozen=True)
class AuthoredGeometryView:
    """Local working view of a validated G5 request, never a cached transport."""

    topology: WorldTopology
    surface_z: Mapping[Coord, int]
    anchors: Mapping[str, Coord]


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
    """One resolved metadata source; the accepted design owns the floor payload."""

    source: WaterSourceMetadata
    prepared: PreparedPlacement
    floor_z: FineZ
    floor_profile: BasinFloorProfile | None

    def __post_init__(self) -> None:
        if not isinstance(self.source, WaterSourceMetadata) or not isinstance(self.prepared, PreparedPlacement):
            raise TypeError("water entries require typed metadata and prepared placement")
        object.__setattr__(self, "source", WaterSourceMetadata.model_validate(self.source, strict=True))
        object.__setattr__(self, "prepared", PreparedPlacement.model_validate(self.prepared, strict=True))
        if self.source.source_uid != self.prepared.intent.identity.source_uid:
            raise ValueError("water metadata and prepared placement must identify the same source")
        if type(self.floor_z) is not int or self.floor_z >= self.source.level:
            raise ValueError("water floor must be a strict integer below the resolved level")
        if self.floor_profile is not None:
            if not isinstance(self.floor_profile, (FieldFloorProfile, SampledFloorProfile)):
                raise TypeError("water entries require a typed floor profile")
            object.__setattr__(self, "floor_profile", TypeAdapter(BasinFloorProfile).validate_python(self.floor_profile, strict=True))
        if isinstance(self.floor_profile, FieldFloorProfile):
            profile = self.floor_profile
            if (profile.level != self.source.level or profile.depth != self.source.default_depth
                    or self.floor_z != max(profile.z_min, profile.level - profile.depth)):
                raise ValueError("water field floor must match the captured metadata and bound")


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
