"""Typed river routing facts; no geometry, placement or persistence policy."""

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, model_validator
from app.dataModel.hydrology.declaredRiver import HydrologyMouth
from app.dataModel.hydrology.riverDrainageLink import RiverReceiverKind
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.topology.worldTopology import Coord


class RiverRoutingCode(StrEnum):
    REDIRECTED = "RIVER_REDIRECTED"
    NO_WATER_BODIES = "RIVER_NO_WATER_BODIES"
    NO_REACHABLE_WATER = "RIVER_NO_REACHABLE_WATER"
    TARGET_UNREACHABLE = "RIVER_TARGET_UNREACHABLE"
    INVALID_SOURCE = "RIVER_INVALID_SOURCE"
    INVALID_CONNECTION_TYPE = "RIVER_INVALID_CONNECTION_TYPE"


class RiverRoutingFailure(StrEnum):
    INVALID_CONNECTION_TYPE = "invalid_connection_type"
    DRAINAGE_CYCLE = "drainage_cycle"
    MISSING_GEOMETRY = "missing_geometry"
    MISSING_ANCHOR = "missing_anchor"
    MISSING_TERRAIN = "missing_terrain"
    DISCONNECTED_PATH = "disconnected_path"
    UPHILL = "uphill"
    TURN_LIMIT = "turn_limit"
    BLOCKED = "blocked_river_bed"
    DRY_MOUTH = "dry_mouth"
    WRONG_BODY = "wrong_receiving_body"
    PATH_LIMIT = "path_budget_exceeded"
    SOURCE_IN_WATER = "source_already_in_water"
    RECEIVER_METADATA = "receiver_identity_or_kind_unavailable"


class RiverRouteDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    world_uid: str
    object_uid: str
    object_type: HydrologyConnectionType | None
    rejected_connection_type: str | None = None
    requested_receiver_uid: str | None = None
    fallback_reason: RiverRoutingFailure | None = None
    requested_mouth: HydrologyMouth | None
    code: RiverRoutingCode
    reason: RiverRoutingFailure
    source_cell: Coord | None = None
    failure_cell: Coord | None = None
    receiver_uid: str | None = None
    receiver_kind: RiverReceiverKind | None = None
    receiver_cell: Coord | None = None
    receiver_level: int | None = None

    @model_validator(mode="after")
    def redirected_receiver_is_complete(self):
        if self.code is RiverRoutingCode.REDIRECTED and (
                not self.receiver_uid or self.receiver_kind is None or self.receiver_cell is None):
            raise ValueError("river redirection requires receiver UID, kind and cell")
        if self.code is RiverRoutingCode.INVALID_CONNECTION_TYPE:
            if self.object_type is not None or self.rejected_connection_type is None:
                raise ValueError("invalid type requires original rejected value, without a substituted type")
        elif self.object_type is None:
            raise ValueError("routing diagnostic requires a valid object type")
        return self
