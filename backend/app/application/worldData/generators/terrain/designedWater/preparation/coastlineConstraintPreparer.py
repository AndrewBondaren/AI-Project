"""Turn an authored water-source line into captured terrain constraints."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.placement.adapters.coastlineShape import coastline_segments
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.application.worldData.placement.adapters.waterGeometry.nativeGeometry import prepare_native_water_geometry
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometryRequest, LegacyAuthoredWaterGeometryRequest
from app.dataModel.terrain.designedWater.geometry.waterDesignConstraints import FineWaterDesignConstraints, WaterDesignConstraints
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class CoastlineConstraintPreparer:
    """Geometry only: no policy, budget allocation, hydro presence or relief writes."""

    # GEO-LEGACY-21: Replace the coarse authored request with fine W.
    def prepare(self, request: LegacyAuthoredWaterGeometryRequest) -> WaterDesignConstraints:
        if not isinstance(request, LegacyAuthoredWaterGeometryRequest):
            raise TypeError("coastline constraints require a typed geometry request")
        request = LegacyAuthoredWaterGeometryRequest.model_validate(request, strict=True)
        if not isinstance(request.source, CoastlineWaterSource):
            raise ValueError("coastline constraints require a water-source line")
        # Reuse the existing owner for water-side selection, topology and caps.
        # The one computed claim is an allowed mask, not a generated water body.
        geometry = prepare_authored_water_geometry(request)
        from app.application.worldData.generators.hydrology.placement.projectDeclaredHydrology import project_water_source

        source = project_water_source(request.source.value, request.grid.fine_span)
        allowed = frozenset(cell for part in geometry.footprints for cell in part)
        return WaterDesignConstraints(source=request.source, pre_hydrology_ref=request.pre_hydrology.ref,
            grid=request.grid, allowed_cells=allowed, required_cells=self._strip(source, request.topology, allowed),
            notices=geometry.notices)

    def prepare_native(self, request: AuthoredWaterGeometryRequest) -> FineWaterDesignConstraints:
        if not isinstance(request, AuthoredWaterGeometryRequest):
            raise TypeError("native coastline constraints require a typed fine request")
        request = AuthoredWaterGeometryRequest.model_validate(request, strict=True)
        if not isinstance(request.source, CoastlineWaterSource):
            raise ValueError("coastline constraints require a water-source line")
        geometry = prepare_native_water_geometry(request)
        allowed = frozenset(cell for part in geometry.footprints for cell in part)
        required = self._strip(request.source.value, request.pre_hydrology.payload.topology, allowed)
        return FineWaterDesignConstraints(source=request.source, pre_hydrology_ref=geometry.pre_hydrology_ref,
            coordinate_space=CoordinateSpace.WORLD_FINE_GRID, grid=request.grid, notices=geometry.notices,
            allowed_cells=frozenset((FineX(x), FineY(y)) for x, y in allowed),
            required_cells=frozenset((FineX(x), FineY(y)) for x, y in required))

    @staticmethod
    def _strip(source: DeclaredCoastline, topology: WorldTopology, allowed: frozenset[Coord]) -> frozenset[Coord]:
        required: set[Coord] = set()
        for cell in rasterize_segments(list(coastline_segments(source))):
            coast = topology.canonicalize(*cell)
            neighbors = frozenset(canonical for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx or dy) and (canonical := topology.canonicalize(cell[0] + dx, cell[1] + dy)) is not None)
            wet = neighbors & allowed
            if coast is None or not wet:
                raise PlanBuildFailure((FieldPathError(("coastline_constraints", source.location_uid),
                    f"authored coastline cell {cell} has no available water-side neighbor",
                    code=WaterDesignIssueCode.CONSTRAINT_CONFLICT.value),))
            required.update(wet)
        return frozenset(required)
