"""POJO for `map_cells.hydrology` JSON — surface-top metadata (U19, TZ C2)."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole


class MapCellHydrology(BaseModel):
    """
    Wire shape persisted on map_cells.hydrology (nullable JSON column).

    Only surface-top cells per (gx, gy) — see docs/tz_terrain_hydrology.md § C2.
    """

    SCHEMA_ID: ClassVar[str] = "SCH-MAP-CELL-HYDROLOGY"

    model_config = ConfigDict(extra="ignore", frozen=True)

    liquid_candidate: DefaultOnWire[bool] = False
    role: DefaultOnWire[HydrologyCellRole | None] = None
    deepening_index: DefaultOnWire[int | None] = constrained_field(default=None, greater_equals=0)
    connection_edge_uid: DefaultOnWire[str | None] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_wire(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        role = HydrologyCellRole.from_wire(out.get("role"))
        if role == HydrologyCellRole.SHORE:
            out["liquid_candidate"] = False
        elif role is not None and role.is_open_water_role():
            out["liquid_candidate"] = True
        return out

    def is_liquid_candidate(self) -> bool:
        return bool(self.liquid_candidate)


def parse_cell_hydrology(raw: dict | None) -> MapCellHydrology | None:
    if raw is None or not isinstance(raw, dict) or not raw:
        return None
    return MapCellHydrology.model_validate(raw)


def dump_cell_hydrology(pojo: MapCellHydrology | None) -> dict | None:
    if pojo is None:
        return None
    data = pojo.model_dump(mode="json", exclude_none=True)
    return data if data else None


def cell_hydrology_liquid_candidate(raw: dict | None) -> bool:
    """Typed read path for MapCell.hydrology wire dict."""
    parsed = parse_cell_hydrology(raw)
    return parsed is not None and parsed.is_liquid_candidate()
