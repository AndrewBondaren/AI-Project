"""Baseline placement records and terrain-owned basin specs in coarse surface space."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.placement.water import ResolvedWaterPlacement
from app.dataModel.placement.result import PlacementOutcomeV2, ResolvedPlacementV2
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterDesignDecision
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.terrain.designedWater.coverage.budget import WaterCoverageBudget
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.topology.worldTopology import WorldTopology


class WaterPlacementPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    coordinate_space: CoordinateSpace
    topology: WorldTopology
    records: tuple[ResolvedWaterPlacement, ...]
    basin_specs: tuple[BasinSpec, ...]

    @model_validator(mode="after")
    def consistent_sources(self) -> Self:
        if self.coordinate_space != CoordinateSpace.WORLD_SURFACE_GRID:
            raise ValueError("baseline water placement requires world_surface_grid")
        records = {record.source_uid: record for record in self.records}
        specs = {spec.source_uid: spec for spec in self.basin_specs}
        if len(records) != len(self.records) or len(specs) != len(self.basin_specs):
            raise ValueError("duplicate water placement source_uid")
        if records.keys() != specs.keys():
            raise ValueError("water records and basin specs require identical source_uid sets")
        for uid, record in records.items():
            spec = specs[uid]
            if (record.footprint_cells != spec.footprint or record.z_water_level != spec.z_water_level
                    or record.kind != spec.kind or record.liquid != spec.liquid):
                raise ValueError(f"water record/basin spec mismatch for {uid}")
        return self


class GeoWaterPlacementPlan(WaterPlacementPlan):
    """One spatial batch plus its source admission, metadata and budget evidence."""

    outcomes: tuple[PlacementOutcomeV2, ...]
    metadata: tuple[WaterSourceMetadata, ...]
    source_decisions: tuple[tuple[EntityUid, WaterDesignDecision], ...]
    budget: WaterCoverageBudget | None

    @model_validator(mode="after")
    def coherent_admission(self) -> Self:
        validate_immutable(self)
        decisions = dict(self.source_decisions)
        if len(decisions) != len(self.source_decisions):
            raise ValueError("duplicate source decision UID")
        if any(decision.state is PolicyState.READY and decision.behavior is None for decision in decisions.values()):
            raise ValueError("ready water admission requires a selected strategy")
        outcomes = {outcome.identity.source_uid: outcome for outcome in self.outcomes}
        if len(outcomes) != len(self.outcomes) or outcomes.keys() != decisions.keys():
            raise ValueError("each source decision requires exactly one placement outcome")
        accepted = {uid for uid, outcome in outcomes.items() if isinstance(outcome, ResolvedPlacementV2)}
        if accepted != {record.source_uid for record in self.records}:
            raise ValueError("accepted water records must match resolved outcomes")
        metadata = {item.source_uid: item for item in self.metadata}
        if (len(metadata) != len(self.metadata) or not accepted <= metadata.keys()
                or not metadata.keys() <= decisions.keys()):
            raise ValueError("accepted sources require unique metadata associated with source decisions")
        for uid in accepted:
            if decisions[uid].state is not PolicyState.READY:
                raise ValueError("resolved water requires ready source admission")
        return self
