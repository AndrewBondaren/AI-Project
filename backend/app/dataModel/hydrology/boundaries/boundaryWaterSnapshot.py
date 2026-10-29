"""Explicit final fine samples and accepted supports, captured after water fill."""

from typing import Generic, Literal, Self
from typing_extensions import TypeVar

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.result import PlacementOutcomeV2, ResolvedPlacementV2
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.immutableValue import validate_immutable


class FineBoundaryWaterCell(BaseModel, frozen=True):
    """None is observed dry; an absent sample is unknown, never implicit dry."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    cell: FineXY
    body_uid: EntityUid | None


H = TypeVar("H", bound=HydrologyPlan, default=HydrologyPlan)


class BoundaryWaterSnapshot(BaseModel, Generic[H], frozen=True):
    """The producer supplies accepted supports in fine space; consumers never guess."""

    model_config = FineBoundaryWaterCell.model_config

    hydrology: PlanEnvelope[H]
    source_mapping: SourceBodyMapping
    mapping_hydrology_ref: PlanRef
    placement_ref: PlanRef
    coordinate_space: Literal[CoordinateSpace.WORLD_FINE_GRID]
    water_outcomes: tuple[PlacementOutcomeV2, ...]
    fine_cells: tuple[FineBoundaryWaterCell, ...]
    grid: SurfaceGridSettings
    topology: WorldTopology

    @property
    def accepted(self) -> tuple[ResolvedPlacementV2, ...]:
        return tuple(outcome for outcome in self.water_outcomes if isinstance(outcome, ResolvedPlacementV2))

    @field_validator("topology", mode="before")
    @classmethod
    def normalized_topology(cls, value: object) -> object:
        return WorldTopology.model_validate(value.model_dump(warnings=False), strict=True) if isinstance(value, WorldTopology) else value

    @model_validator(mode="after")
    def same_revision(self) -> Self:
        validate_immutable(self)
        ref = self.hydrology.ref
        if self.mapping_hydrology_ref != ref:
            raise ValueError("mapping must bind to this hydrology revision")
        if self.placement_ref.key.world_uid != ref.key.world_uid or not any(
                dependency.slot == SurfacePlanSlot.WATER_PLACEMENT.value and dependency.ref == self.placement_ref
                for dependency in self.hydrology.dependencies):
            raise ValueError("accepted placement ref must be an exact hydrology dependency in the same world")
        box, bounds = self.hydrology.payload.coarse_surface_z, self.topology.bounds
        if len(box) != bounds.width * bounds.height or any(not bounds.contains(cell.gx, cell.gy) for cell, _ in box):
            raise ValueError("boundary snapshot requires the matching full coarse topology")
        sources = tuple(target.identity.source_uid for target in self.water_outcomes)
        regions = tuple(target.identity.region_uid for target in self.water_outcomes)
        if len(set(sources)) != len(sources) or len(set(regions)) != len(regions):
            raise ValueError("ambiguous accepted source/region identity")
        if any(target.identity.world_uid != ref.key.world_uid for target in self.water_outcomes):
            raise ValueError("accepted support world mismatch")
        topology = fine_topology(self.topology, self.grid.fine_span)
        if any(topology.canonicalize(*cell) != cell for target in self.accepted for cell in target.footprint.cells):
            raise ValueError("accepted supports require canonical fine coordinates")
        keys = tuple((sample.cell[1], sample.cell[0]) for sample in self.fine_cells)
        if keys != tuple(sorted(set(keys))) or any(topology.canonicalize(*sample.cell) != sample.cell for sample in self.fine_cells):
            raise ValueError("fine samples require sorted unique canonical coordinates")
        bodies = {body.water_body_uid for body in self.hydrology.payload.water_bodies}
        if any(sample.body_uid is not None and sample.body_uid not in bodies for sample in self.fine_cells):
            raise ValueError("fine sample must refer to a final physical body")
        if any(entry.source_uid not in {target.identity.source_uid for target in self.accepted} or not set(entry.body_uids) <= bodies for entry in self.source_mapping.entries):
            raise ValueError("mapping requires accepted source identities and final physical body UIDs")
        return self
