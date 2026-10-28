"""G5: immutable source geometry boundary, before metadata and without placement."""

from math import isfinite
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterAnchorInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.immutableValue import validate_immutable

type AuthoredWaterSource = Annotated[AuthoredBasinSource | AuthoredLakeSource | CoastlineWaterSource, Field(discriminator="kind")]


class AuthoredWaterGeometryRequest(BaseModel, frozen=True):
    """G8 supplies captured source/terrain/anchors/limits after READY admission.

    This is the request for one geometry calculation before metadata exists.
    Source/anchors use world fine coordinates; the terrain envelope is coarse.
    No defaults, cascade, admission decision or live World is resolved here.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    source: AuthoredWaterSource
    pre_hydrology: PlanEnvelope[TerrainPlan]
    topology: WorldTopology
    grid: SurfaceGridSettings
    seed_root: EntityUid
    anchors: tuple[WaterAnchorInput, ...]
    seas: HydrologySeasPolicy
    z_min: Annotated[FineZ, Field(strict=True)]

    @field_validator("topology", "seas", mode="before")
    @classmethod
    def revalidate_legacy_records(cls, value: object) -> object:
        if isinstance(value, HydrologySeasPolicy):
            return HydrologySeasPolicy.model_validate(value.model_dump(warnings=False), strict=True)
        if isinstance(value, WorldTopology):
            return WorldTopology.model_validate(value.model_dump(warnings=False), strict=True)
        return value

    @model_validator(mode="after")
    def coherent_geometry_inputs(self) -> Self:
        bounds, box = self.topology.bounds, self.pre_hydrology.payload.bbox
        if (box.x_min, box.x_max, box.y_min, box.y_max) != (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max):
            raise ValueError("authored geometry requires a complete coarse terrain snapshot")
        if any(z < self.z_min for _, z in self.pre_hydrology.payload.surface_z):
            raise ValueError("terrain surface lies below world z_min")
        world_uid = self.pre_hydrology.ref.key.world_uid
        if any(d.ref.key.world_uid != world_uid for d in self.pre_hydrology.dependencies):
            raise ValueError("terrain dependencies belong to another world")
        if len({a.source_uid for a in self.anchors}) != len(self.anchors):
            raise ValueError("duplicate authored anchor identity")
        # Only geometry limits are consumed; admission/autoresolve remain upstream.
        for limit in (self.seas.max_area_fraction, self.seas.max_extent_x_fraction, self.seas.max_extent_y_fraction):
            if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not isfinite(limit) or not 0 < limit <= 1:
                raise ValueError("coastline geometry limits require finite fractions in (0,1]")
        validate_immutable(self)
        return self


class AuthoredWaterGeometry(BaseModel, frozen=True):
    """One computed geometry, reused by metadata, strategy and G4-C.

    Producer: water adapter geometry helper. G8 reads rim_level to build lake
    metadata, then binds this same result to AuthoredWaterDesignInput.geometry.
    Ref/space/z_min describe the source terrain; this is neither a second
    placement transport nor an accepted placement, and owns no floor writes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    source_uid: EntityUid
    pre_hydrology_ref: PlanRef
    coordinate_space: CoordinateSpace
    footprints: Annotated[tuple[frozenset[Coord], ...], Field(min_length=1)]
    rim_level: Annotated[FineZ, Field(strict=True)] | None
    z_min: Annotated[FineZ, Field(strict=True)]
    notices: tuple[FieldPathError, ...]

    @model_validator(mode="after")
    def world_geometry(self) -> Self:
        if self.coordinate_space is CoordinateSpace.LOCATION_FINE_GRID or any(not part for part in self.footprints):
            raise ValueError("authored geometry requires nonempty world-space footprints")
        validate_immutable(self)
        return self
