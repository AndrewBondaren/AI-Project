"""Test adapters to the retained HY-6 geometry API, with no paint/carve path."""

from app.application.worldData.generators.hydrology.shore.waterSideFootprint import (
    CoastlineWaterSide, compute_land_centroid, water_side_footprint,
)


def flood_water_side(hm, coast, segments, *, topology, bounded=True):
    geometry = CoastlineWaterSide(coast, segments, compute_land_centroid(hm, topology=topology),
                                  topology=topology)
    return water_side_footprint(geometry, bounded=bounded, passable=hm.surface_z.__contains__)


def flood_water_side_unbounded(hm, coast, segments, *, topology):
    return flood_water_side(hm, coast, segments, topology=topology, bounded=False)


def _land_shore_cells(coast, segments, hm, centroid, *, topology):
    return CoastlineWaterSide(coast, segments, centroid, topology=topology).land_shore(hm.surface_z.__contains__)


def water_side_seeds(coast, segments, hm, centroid, *, topology):
    return CoastlineWaterSide(coast, segments, centroid, topology=topology).seeds(hm.surface_z.__contains__)


def apply_test_river(hm, segment, *, depth_step, z_min, occupied=None):
    """Test the profile → relief → roles contract explicitly."""
    from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_spec, river_bed_roles
    from app.application.worldData.generators.terrain.reliefObjects.riverBed import apply_river_bed_z
    spec = river_bed_spec(hm, segment, depth_step=depth_step, occupied=occupied or {}, z_min=z_min)
    apply_river_bed_z(hm, (spec,))
    return river_bed_roles(segment, spec)
