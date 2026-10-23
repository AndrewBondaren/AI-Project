"""Baseline placement records and terrain-owned basin specs in coarse surface space."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.placement.water import ResolvedWaterPlacement
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
