"""Pass 1.4 relief object — basin floor by piecewise distance profile; absolute z write."""

import logging
from collections.abc import Sequence

from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinSpec import (
    BasinSpec,
)
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.distanceField import (
    distance_from_boundary,
)
from app.application.worldData.generators.terrain.reliefObjects.bathymetry.floorProfile import (
    BasinFloorEvaluator, floor_profile_z,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.basinKind import basin_kind_profile
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile, SampledFloorProfile

logger = logging.getLogger(__name__)


def apply_basin_z(heightmap: SurfaceHeightmap, specs: Sequence[BasinSpec],
                  topology: WorldTopology, *, reserved: frozenset[Coord],
                  coordinate_space: CoordinateSpace = CoordinateSpace.WORLD_SURFACE_GRID,
                  grid: SurfaceGridSettings | None = None) -> int:
    """Write basin floors onto ``heightmap.surface_z``; returns written cell count."""
    if not isinstance(coordinate_space, CoordinateSpace):
        raise TypeError("basin writer requires a typed coordinate space")
    if coordinate_space is CoordinateSpace.LOCATION_FINE_GRID:
        raise ValueError("basin writer requires world coordinates")
    written: dict[Coord, int] = {}
    for spec in sorted(specs, key=lambda s: s.source_uid):
        cells = spec.footprint - reserved
        if not cells:
            logger.debug("basin_z_skip_empty | uid=%s", spec.source_uid)
            continue
        if any(cell not in heightmap.surface_z for cell in cells):
            raise ValueError(f"basin footprint outside working heightmap: {spec.source_uid}")
        # Profiles are already accepted geometry. Only the legacy scalar path
        # derives a distance/bands floor; no path reselects cells or runs P2.
        payload = spec.floor_profile
        evaluator = (BasinFloorEvaluator(payload, topology=topology,
            coordinate_space=coordinate_space, grid=grid) if isinstance(payload, FieldFloorProfile) else None)
        samples: dict[Coord, int] = {}
        dist: dict[Coord, int] = {}
        if isinstance(payload, SampledFloorProfile):
            if payload.space != coordinate_space:
                raise ValueError("sampled floor space must match the working heightmap")
            samples = dict(payload.samples)
        elif payload is None:
            dist = distance_from_boundary(frozenset(cells), topology)
        profile = basin_kind_profile(spec.kind)
        for cell in cells:
            if evaluator is not None:
                z = evaluator.sample(cell)
            elif isinstance(payload, SampledFloorProfile):
                z = samples[cell]
            else:
                z = floor_profile_z(dist.get(cell, spec.bands.max + 1), level=spec.z_water_level,
                                    floor_z=spec.floor_z, bands=spec.bands, profile=profile)
            previous = written.get(cell)
            if previous is None or z < previous:
                written[cell] = z
    for cell, z in written.items():
        heightmap.surface_z[cell] = z
    return len(written)
