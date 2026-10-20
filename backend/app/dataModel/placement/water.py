"""Resolved water record, without basin specs, bathymetry or implicit defaults."""

from pydantic import StrictInt

from app.dataModel.annotationPolicy import StrictEnumOnWire, StrictOnWire
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.placement.common import FineCell, PlacementModel
from app.dataModel.placement.result import ResolvedPlacement


class ResolvedWaterPlacement(PlacementModel):
    placement: StrictOnWire[ResolvedPlacement]
    z_water_level: StrictOnWire[StrictInt]
    kind: StrictEnumOnWire[BasinKind]
    liquid: StrictOnWire[MaterialKey]

    @property
    def source_uid(self) -> str:
        return self.placement.identity.source_uid

    @property
    def footprint_cells(self) -> frozenset[FineCell]:
        return self.placement.footprint.cells
