"""Design geometry transport; contains no placement header, decision or outcome."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSourceKind
from app.dataModel.placement.common import OriginalArea
from app.dataModel.placement.prepared import PlacementCandidate
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.relief.bathymetry.floorProfile import BasinFloorProfile, FieldFloorProfile, SampledFloorProfile
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable


class WaterDesignPreparation(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    metadata: WaterSourceMetadata
    pre_hydrology_ref: PlanRef
    coordinate_space: CoordinateSpace
    grid: SurfaceGridSettings
    candidates: Annotated[tuple[PlacementCandidate, ...], Field(min_length=1)]
    original_area: OriginalArea
    floor_z: Annotated[FineZ, Field(strict=True)]
    floor_profile: BasinFloorProfile | None
    notices: tuple[FieldPathError, ...]

    @model_validator(mode="after")
    def valid_geometry_result(self) -> Self:
        if self.coordinate_space is CoordinateSpace.LOCATION_FINE_GRID:
            raise ValueError("water geometry requires world coordinates")
        if self.floor_z >= self.metadata.level:
            raise ValueError("water floor must be below its level")
        if len({c.candidate_uid for c in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate water geometry candidate UID")
        cells = frozenset(cell for candidate in self.candidates for cell in candidate.footprint.cells)
        if self.original_area != float(len(cells)):
            raise ValueError("original_area must match discrete geometry in its coordinate space")
        profile = self.floor_profile
        if self.metadata.source_kind is WaterDesignSourceKind.PROCEDURAL and not isinstance(profile, FieldFloorProfile):
            raise ValueError("procedural geometry must retain its field floor profile")
        if isinstance(profile, FieldFloorProfile):
            if profile.level != self.metadata.level or self.floor_z != max(profile.z_min, profile.level - profile.depth):
                raise ValueError("field floor must preserve water level and lower bound")
        elif isinstance(profile, SampledFloorProfile):
            if profile.space != self.coordinate_space or frozenset(c for c, _ in profile.samples) != cells:
                raise ValueError("sampled profile must cover geometry in the same space")
            if self.floor_z != min(z for _, z in profile.samples) or any(z >= self.metadata.level for _, z in profile.samples):
                raise ValueError("sampled profile must preserve floor bounds")
        validate_immutable(self)
        return self
