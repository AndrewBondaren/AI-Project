"""Bind the operation snapshot to ready domain observations; no source reads."""

from collections.abc import Mapping

from app.application.worldData.generators.terrain.landcover.types import (
    LandcoverInputs,
    StateSnapshotEntry,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.regions.inputs.landcoverInputs import (
    prepare_landcover_inputs as _compose_landcover_inputs,
)


def read_region_state_snapshot(ctx: LightGridBakeContext) -> Mapping[str, StateSnapshotEntry]:
    """The async bake/refine owner has already read the entity repository."""
    return ctx.region_state_snapshot


def prepare_landcover_inputs(ctx: LightGridBakeContext) -> LandcoverInputs:
    return _compose_landcover_inputs(ctx.require_working(), read_region_state_snapshot(ctx))
