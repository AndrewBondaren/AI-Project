"""Stable surface TLV registrations for app.dataModel.spatial."""

from app.dataModel.encoding.schemaManifest import CanonicalTypeKind
from app.dataModel.spatial.facing import Facing
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import LightCellRef, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.regionShape import (
    AnchorRadiusShape,
    BboxShape,
    CorridorShape,
    EdgeNoise,
    EllipseShape,
    PolygonShape,
    RegionShapeKind,
)


BINDINGS: tuple[tuple[int, type, CanonicalTypeKind], ...] = (
    (2, GridBBox, CanonicalTypeKind.RECORD),
    (26, SurfaceGridSettings, CanonicalTypeKind.RECORD),
    (34, BboxShape, CanonicalTypeKind.RECORD),
    (35, EdgeNoise, CanonicalTypeKind.RECORD),
    (36, RegionShapeKind, CanonicalTypeKind.ENUM),
    (37, EllipseShape, CanonicalTypeKind.RECORD),
    (38, PolygonShape, CanonicalTypeKind.RECORD),
    (39, AnchorRadiusShape, CanonicalTypeKind.RECORD),
    (40, CorridorShape, CanonicalTypeKind.RECORD),
    (110, Facing, CanonicalTypeKind.ENUM),
    (116, SurfaceGridCoord, CanonicalTypeKind.RECORD),
    (119, CoordinateSpace, CanonicalTypeKind.ENUM),
    (141, LightCellRef, CanonicalTypeKind.RECORD),
)
