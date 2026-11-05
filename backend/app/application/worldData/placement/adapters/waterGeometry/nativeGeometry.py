"""Rasterize authored water in the coordinate frame of its observed terrain."""

from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.placement.adapters.coastlineShape import coastline_cells
from app.application.worldData.placement.adapters.lakeShape import lake_cells, lake_level
from app.application.worldData.placement.adapters.waterShape import shape_cells
from app.application.worldData.placement.adapters.waterTypes import AuthoredGeometryView
from app.dataModel.placement.waterPreparationCode import WaterPreparationCode
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import (
    AuthoredWaterGeometry, AuthoredWaterGeometryRequest, LegacyAuthoredWaterGeometryRequest,
)
from app.dataModel.placement.coastlineCapNotice import CoastlineCapNotice
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


# GEO-LEGACY-17: Remove legacy request union arm and surface-frame branch.
def rasterize_authored_geometry(request: AuthoredWaterGeometryRequest | LegacyAuthoredWaterGeometryRequest,
        source: DeclaredBasin | DeclaredLake | DeclaredCoastline, view: AuthoredGeometryView) -> AuthoredWaterGeometry:
    uid = source.location_uid
    notices = []
    rim = None
    if isinstance(source, DeclaredBasin):
        cells, _ = shape_cells(source.footprint, uid, view, seed_root=request.seed_root)
    elif isinstance(source, DeclaredCoastline):
        cells, capped = coastline_cells(source, view, request.seas, seed_root=request.seed_root)
        if capped:
            notices.append(CoastlineCapNotice(source_uid=uid))
    else:
        cells, degenerate = lake_cells(source, view, seed_root=request.seed_root)
        rim = FineZ(lake_level(cells, view))
        if degenerate:
            notices.append(FieldPathError(("authored_geometry", uid), "degenerate lake ring uses its contour",
                code=WaterPreparationCode.DEGENERATE_RING.value))
    space = (CoordinateSpace.WORLD_FINE_GRID if isinstance(request, AuthoredWaterGeometryRequest)
             else CoordinateSpace.WORLD_SURFACE_GRID)
    return AuthoredWaterGeometry(source_uid=uid, pre_hydrology_ref=request.pre_hydrology.ref,
        coordinate_space=space, footprints=(cells,), rim_level=rim, z_min=request.z_min, notices=tuple(notices))


def prepare_native_water_geometry(request: AuthoredWaterGeometryRequest) -> AuthoredWaterGeometry:
    """Consume the fine W admitted by the caller; source and anchors are already fine."""
    if not isinstance(request, AuthoredWaterGeometryRequest):
        raise TypeError("native authored geometry requires a typed fine request")
    try:
        request = AuthoredWaterGeometryRequest.model_validate(request, strict=True)
    except ValueError as error:
        raise PlanBuildFailure((FieldPathError(("authored_geometry",), str(error),
            code=WaterPreparationCode.SNAPSHOT.value),)) from error
    view = AuthoredGeometryView(topology=request.topology, surface_z=dict(request.pre_hydrology.payload.surface_z),
        anchors={anchor.source_uid: anchor.position for anchor in request.anchors})
    try:
        return rasterize_authored_geometry(request, request.source.value, view)
    except ValueError as error:
        raise PlanBuildFailure((FieldPathError(("authored_geometry", request.source.value.location_uid), str(error),
            code=WaterPreparationCode.GEOMETRY.value),)) from error
