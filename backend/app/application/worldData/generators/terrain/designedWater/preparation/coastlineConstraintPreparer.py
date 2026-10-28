"""Turn an authored water-source line into captured terrain constraints."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.placement.adapters.coastlineShape import coastline_segments
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometryRequest
from app.dataModel.terrain.designedWater.geometry.waterDesignConstraints import WaterDesignConstraints
from app.dataModel.terrain.designedWater.strategyKind import WaterDesignIssueCode
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class CoastlineConstraintPreparer:
    """Geometry only: no policy, budget allocation, hydro presence or relief writes."""

    def prepare(self, request: AuthoredWaterGeometryRequest) -> WaterDesignConstraints:
        if not isinstance(request, AuthoredWaterGeometryRequest):
            raise TypeError("coastline constraints require a typed geometry request")
        request = AuthoredWaterGeometryRequest.model_validate(request, strict=True)
        if not isinstance(request.source, CoastlineWaterSource):
            raise ValueError("coastline constraints require a water-source line")
        # Reuse the existing owner for water-side selection, topology and caps.
        # The one computed claim is an allowed mask, not a generated water body.
        geometry = prepare_authored_water_geometry(request)
        from app.application.worldData.generators.hydrology.placement.projectDeclaredHydrology import project_water_source

        source = project_water_source(request.source.value, request.grid.fine_span)
        segments = coastline_segments(source)
        allowed = frozenset(cell for part in geometry.footprints for cell in part)
        required: set[Coord] = set()
        for cell in rasterize_segments(list(segments)):
            coast = request.topology.canonicalize(*cell)
            neighbors = frozenset(canonical for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx or dy) and (canonical := request.topology.canonicalize(cell[0] + dx, cell[1] + dy)) is not None)
            wet = neighbors & allowed
            if coast is None or not wet:
                raise PlanBuildFailure((FieldPathError(("coastline_constraints", request.source.value.location_uid),
                    f"authored coastline cell {cell} has no available water-side neighbor",
                    code=WaterDesignIssueCode.CONSTRAINT_CONFLICT.value),))
            required.update(wet)
        return WaterDesignConstraints(source=request.source, pre_hydrology_ref=request.pre_hydrology.ref,
            grid=request.grid, allowed_cells=allowed, required_cells=frozenset(required), notices=geometry.notices)
