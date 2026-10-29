"""Piecewise basin floor profile by boundary distance (HY-12 step 3a)."""

from decimal import Decimal

from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.application.worldData.generators.terrain.designedWater.fields.continentalFieldComposer import ContinentalFieldComposer
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKindProfile
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe, PlateRecipe, PlateNoiseRecipe
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import Coord, WorldTopology


class BasinFloorEvaluator:
    """Evaluate a fixed accepted field; no spatial selection or height writes."""

    def __init__(self, profile: FieldFloorProfile, *, topology: WorldTopology,
                 coordinate_space: CoordinateSpace, grid: SurfaceGridSettings | None) -> None:
        if not isinstance(profile, FieldFloorProfile) or not isinstance(topology, WorldTopology):
            raise TypeError("floor evaluation requires typed profile and topology")
        self.profile = FieldFloorProfile.model_validate(profile, strict=True)
        topology = WorldTopology.model_validate(topology, strict=True)
        if coordinate_space is CoordinateSpace.WORLD_SURFACE_GRID:
            if not isinstance(grid, SurfaceGridSettings):
                raise TypeError("coarse field floor requires the captured grid")
            grid = SurfaceGridSettings.model_validate(grid, strict=True)
            expected = fine_topology(topology, grid.fine_span)
            self.span = grid.fine_span
        elif coordinate_space is CoordinateSpace.WORLD_FINE_GRID:
            expected = topology
            self.span = 1
        else:
            raise ValueError("field floor requires an explicit world coordinate space")
        if self.profile.recipe.topology != expected:
            raise ValueError("field floor recipe topology does not match the working frame")
        self.topology = topology
        recipe = self.profile.recipe
        # The plate layout is derived once per fixed recipe, never per cell.
        if isinstance(recipe, PlateNoiseRecipe):
            self.layout = PlateFieldGenerator().layout(recipe.plate_recipe)
        elif isinstance(recipe, PlateRecipe):
            self.layout = PlateFieldGenerator().layout(recipe)
        else:
            self.layout = None

    def sample(self, cell: Coord) -> FineZ:
        if (type(cell) is not tuple or len(cell) != 2 or any(type(v) is not int for v in cell)
                or self.topology.canonicalize(*cell) != cell):
            raise ValueError("floor sample requires a canonical working cell")
        x, y = (cell[0] + .5) * self.span, (cell[1] + .5) * self.span
        recipe = self.profile.recipe
        if isinstance(recipe, NoiseRecipe):
            value = NoiseFieldGenerator().sample(recipe, x=x, y=y)
        elif isinstance(recipe, PlateRecipe):
            if self.layout is None:
                raise ValueError("plate floor requires its captured layout")
            value = PlateFieldGenerator().sample(self.layout, x=x, y=y)
        else:
            if self.layout is None:
                raise ValueError("composed floor requires its captured plate layout")
            value = ContinentalFieldComposer().sample(recipe, self.layout, x=x, y=y)
        # Signed water wetness = -continental field. Exact half-up rounding
        # controls absolute depth; placement score quantization stays elsewhere.
        numerator, denominator = Decimal(str(value)).as_integer_ratio()
        depth = max(1, (self.profile.depth * (denominator - numerator) + denominator) // (2 * denominator))
        return FineZ(max(self.profile.z_min, self.profile.level - depth))


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def floor_profile_z(d: int, *, level: int, floor_z: int, bands: HydrologyBands,
                    profile: BasinKindProfile) -> int:
    top = level - 1
    depth = top - floor_z
    assert depth >= 0, "floor_z must be below z_water_level"
    d_shelf, d_slope = bands.min, bands.max
    fraction = profile.shelf_depth_fraction
    if fraction is None:
        z = floor_z + round(depth * (1 - min(d, d_slope) / d_slope))
    else:
        z_shelf = top - round(depth * fraction)
        if d <= d_shelf:
            z = _lerp(top, z_shelf, d / d_shelf)
        elif d <= d_slope:
            z = floor_z if d_slope == d_shelf else _lerp(
                z_shelf, floor_z, (d - d_shelf) / (d_slope - d_shelf))
        else:
            z = floor_z
    return min(top, max(floor_z, z))
