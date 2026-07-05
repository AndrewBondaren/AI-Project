"""Declared river wire — modes + system topology, SCH-WORLD-HYDROLOGY."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.enums.riverSystemRole import RiverSystemRole
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint

MAX_RIVER_TURN_DEG = 45.0


class HydrologyMouth(BaseModel):
    """River mouth: geographic location or explicit waypoint."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: DefaultOnWire[str | None] = None
    x: DefaultOnWire[int | None] = None
    y: DefaultOnWire[int | None] = None
    z: DefaultOnWire[int | None] = None

    @model_validator(mode="after")
    def _location_or_coords(self) -> HydrologyMouth:
        has_loc = bool(self.location_uid)
        has_xy = self.x is not None and self.y is not None
        if has_loc == has_xy:
            if not has_loc:
                raise ValueError("mouth requires location_uid or x/y coordinates")
        return self


class DeclaredRiverSegment(BaseModel):
    """Manual polyline leg (declare_mode segments)."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    from_wp: HydrologyWaypoint = Field(alias="from")
    to_wp: HydrologyWaypoint = Field(alias="to")
    connection_type: StrictOnWire[str]
    width_cells: DefaultOnWire[int] = 1


class DeclaredRiver(BaseModel):
    """One named river declare entry."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: StrictOnWire[str]
    system_role: DefaultOnWire[RiverSystemRole] = RiverSystemRole.STEM
    parent_location_uid: DefaultOnWire[str | None] = None
    declare_mode: DefaultOnWire[RiverDeclareMode | None] = None
    source: DefaultOnWire[HydrologyWaypoint | None] = None
    mouth: DefaultOnWire[HydrologyMouth | None] = None
    route_location_uids: DefaultOnWire[list[str]] = Field(default_factory=list)
    segments: DefaultOnWire[list[DeclaredRiverSegment]] = Field(default_factory=list)

    @field_validator("system_role", mode="before")
    @classmethod
    def _coerce_role(cls, value: object) -> object:
        if value is None:
            return RiverSystemRole.STEM
        return value

    @model_validator(mode="after")
    def _role_mode_matrix(self) -> DeclaredRiver:
        role = self.system_role
        mode = self.declare_mode

        if role == RiverSystemRole.SYSTEM:
            if mode is not None:
                raise ValueError("system_role=system must not set declare_mode")
            if any(
                (
                    self.source,
                    self.mouth,
                    self.route_location_uids,
                    self.segments,
                ),
            ):
                raise ValueError("system_role=system must not carry geometry")
            return self

        if role == RiverSystemRole.TRIBUTARY and not self.parent_location_uid:
            raise ValueError("system_role=tributary requires parent_location_uid")

        if mode is None:
            raise ValueError(f"declare_mode required for system_role={role.value}")

        if mode == RiverDeclareMode.ENDPOINTS:
            if self.source is None or self.mouth is None:
                raise ValueError("declare_mode=endpoints requires source and mouth")
        elif mode == RiverDeclareMode.VIA_LOCATIONS:
            if len(self.route_location_uids) < 2:
                raise ValueError("declare_mode=via_locations requires ≥2 route_location_uids")
        elif mode == RiverDeclareMode.SEGMENTS:
            if not self.segments:
                raise ValueError("declare_mode=segments requires segments")
            _validate_segment_turns(self.segments)

        return self


def _segment_angle_deg(
    a: HydrologyWaypoint,
    b: HydrologyWaypoint,
    c: HydrologyWaypoint,
) -> float:
    v1 = (b.x - a.x, b.y - a.y)
    v2 = (c.x - b.x, c.y - b.y)
    len1 = math.hypot(v1[0], v1[1])
    len2 = math.hypot(v2[0], v2[1])
    if len1 == 0 or len2 == 0:
        return 0.0
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    cos_a = max(-1.0, min(1.0, dot / (len1 * len2)))
    return math.degrees(math.acos(cos_a))


def _validate_segment_turns(segments: list[DeclaredRiverSegment]) -> None:
    if len(segments) < 2:
        return
    points = [segments[0].from_wp] + [seg.to_wp for seg in segments]
    for i in range(1, len(points) - 1):
        turn = _segment_angle_deg(points[i - 1], points[i], points[i + 1])
        if turn > MAX_RIVER_TURN_DEG + 1e-6:
            raise ValueError(
                f"river segment turn {turn:.1f}° exceeds {MAX_RIVER_TURN_DEG}° at waypoint index {i}",
            )
