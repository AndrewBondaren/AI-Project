"""Resolve source transport values once, before design and placement."""

from pydantic import TypeAdapter

from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.hydrology.sources.waterDesignSource import (
    AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource, WaterDesignSource,
)
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.spatial.grid.coordinateTypes import FineZ

_SOURCE = TypeAdapter(WaterDesignSource)
_LEVEL = TypeAdapter(FineZ)


class WaterSourceMetadataFactory:
    """Hydrology owns level/bands/depth; geometry supplies only the ready lake rim."""

    def build(self, source: WaterDesignSource, *, default_water_level: FineZ,
              seas: HydrologySeasPolicy, lakes: HydrologyLakesPolicy,
              rim_level: FineZ | None, source_path: tuple[str | int, ...]) -> WaterSourceMetadata:
        if not isinstance(source, (AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource)):
            raise TypeError("metadata requires a typed water design source")
        if not isinstance(seas, HydrologySeasPolicy) or not isinstance(lakes, HydrologyLakesPolicy):
            raise TypeError("metadata requires typed sea and lake policies")
        source = _SOURCE.validate_python(source, strict=True)
        level = _LEVEL.validate_python(default_water_level, strict=True)
        if isinstance(source, AuthoredLakeSource):
            if rim_level is None:
                raise ValueError("authored lake metadata requires the computed rim level")
            level = _LEVEL.validate_python(rim_level, strict=True)
            kind, uid = BasinKind.LAKE, source.value.location_uid
        else:
            if rim_level is not None:
                raise ValueError("only authored lake metadata consumes a rim level")
            kind = source.value.kind
            if isinstance(source, ProceduralSource):
                uid = source.value.source_uid
                if source.value.z_water_level is not None:
                    level = source.value.z_water_level
            else:
                uid = source.value.location_uid
                if isinstance(source, AuthoredBasinSource) and source.value.z_water_level is not None:
                    level = FineZ(source.value.z_water_level)
        category = lakes if kind is BasinKind.LAKE else seas
        bands = source.value.rim if isinstance(source, AuthoredBasinSource) and source.value.rim is not None else category.bands
        return WaterSourceMetadata(source_uid=uid, source_kind=source.kind, body_kind=kind,
            liquid=source.value.liquid, level=level, bands=bands, default_depth=category.basin_depth,
            source_path=source_path)
