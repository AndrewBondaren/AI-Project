"""Persisted district slot freeze — C23 topology, not import bundle."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.settlement.enums.districtEntryRole import DistrictEntryRole
from app.dataModel.spatial.facing import Facing


class DistrictTopologyEntry(BaseModel):
    """One district-boundary entry persisted with topology (through_road / entry_point)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    node_uid: StrictOnWire[str]
    x: StrictOnWire[int]
    y: StrictOnWire[int]
    z: StrictOnWire[int]
    role: StrictOnWire[DistrictEntryRole]
    facing: StrictOnWire[Facing]
    connection_type: StrictOnWire[str]
    paired_exit_uid: DefaultOnWire[str | None] = None


class DistrictTopologySlot(BaseModel):
    """Geometry + template key on generated district NL (`named_locations.district_topology`)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    cell_x: StrictOnWire[int]
    cell_y: StrictOnWire[int]
    origin_x: StrictOnWire[int]
    origin_y: StrictOnWire[int]
    width_m: StrictOnWire[int]
    depth_m: StrictOnWire[int]
    ground_z: StrictOnWire[int]
    template_system_name: StrictOnWire[str]
    slot_index: StrictOnWire[int]
    entries: DefaultOnWire[tuple[DistrictTopologyEntry, ...]] = ()
