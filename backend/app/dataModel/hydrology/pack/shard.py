"""One observed 64 by 64 open-water tile."""
from typing import Self

from pydantic import StrictInt, model_validator

from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.encoding.decodeLimits import CollectionLimit, RecordLimits
from app.dataModel.hydrology.pack.profile import TILE_CELLS, TILE_SIDE
from app.dataModel.hydrology.pack.root import _PackRecord, require_source_ref
from app.dataModel.hydrology.query.source import WaterMembershipRun
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateTypes import FineXY
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow, SurfaceSamples
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.topology.worldTopology import Coord


COVERAGE_LIMITS = RecordLimits(RegionCoverage, (
    CollectionLimit(tuple[CoverageSpan, ...],
                    ref=FieldRef(lambda: RegionCoverage, lambda coverage: coverage.spans),
                    minimum=1, maximum=TILE_CELLS),
))
BED_LIMITS = RecordLimits(FineSurfaceWindow, (
    CollectionLimit(SurfaceSamples,
                    ref=FieldRef(lambda: FineSurfaceWindow, lambda bed: bed.surface_z),
                    minimum=1, maximum=TILE_CELLS),
    CollectionLimit(frozenset[Coord],
                    ref=FieldRef(lambda: FineSurfaceWindow, lambda bed: bed.protected_cells),
                    maximum=TILE_CELLS),
))


class HydrologyPackShard(_PackRecord):
    source_ref: PlanRef
    tx: StrictInt
    ty: StrictInt
    bed: FineSurfaceWindow
    wet_runs: tuple[WaterMembershipRun, ...]
    shore_rows: tuple[tuple[FineXY, MapCellHydrology], ...]

    @model_validator(mode="after")
    def _tile(self) -> Self:
        require_source_ref(self.source_ref)
        spans = self.bed.coverage.spans
        for record, limits in ((self.bed.coverage, COVERAGE_LIMITS), (self.bed, BED_LIMITS)):
            for rule in limits.collections:
                if not rule.admits(len(rule.ref.select(record))):
                    raise ValueError(f"invalid shard collection: {rule.bound.field}")
        for row in spans:
            if (row.y // TILE_SIDE != self.ty or row.x0 // TILE_SIDE != self.tx
                    or (row.x1 - 1) // TILE_SIDE != self.tx):
                raise ValueError("coverage outside shard tile")
        observed = dict(self.bed.surface_z)
        wet = set()
        previous = None
        for run in self.wet_runs:
            if previous is not None and (run.y < previous.y or run.y == previous.y and (
                    run.x0 < previous.x1 or run.x0 == previous.x1 and run.body_uid == previous.body_uid)):
                raise ValueError("noncanonical wet runs")
            if run.x0 // TILE_SIDE != self.tx or (run.x1 - 1) // TILE_SIDE != self.tx or run.y // TILE_SIDE != self.ty:
                raise ValueError("wet run outside shard tile")
            for x in range(run.x0, run.x1):
                if (x, run.y) not in observed:
                    raise ValueError("wet run outside observation")
                wet.add((x, run.y))
            previous = run
        shore_order = tuple((y, x) for (x, y), _ in self.shore_rows)
        if shore_order != tuple(sorted(set(shore_order))):
            raise ValueError("noncanonical shore rows")
        for cell, fact in self.shore_rows:
            if cell not in observed or cell in wet or fact.role is not HydrologyCellRole.SHORE or fact.liquid_candidate is not False:
                raise ValueError("invalid observed shore")
        return self


HydrologyPackShard.collection_limits = (
    CollectionLimit(tuple[WaterMembershipRun, ...],
                    ref=FieldRef(lambda: HydrologyPackShard, lambda shard: shard.wet_runs),
                    maximum=TILE_CELLS),
    CollectionLimit(tuple[tuple[FineXY, MapCellHydrology], ...],
                    ref=FieldRef(lambda: HydrologyPackShard, lambda shard: shard.shore_rows),
                    maximum=TILE_CELLS),
)
