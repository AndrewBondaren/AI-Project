"""ENUM-E wire values — docs/tz_json_validation.md JV-0/JV-2."""

from __future__ import annotations

from enum import StrEnum


from app.dataModel.materials.enums.materialCategory import MaterialCategory  # noqa: E402 — wire re-export


class CellStateCategory(StrEnum):
    INTERACTIVE = "interactive"
    ENVIRONMENTAL = "environmental"


class BorderCategory(StrEnum):
    LIQUID = "liquid"
    NULL = "null"


class NodeCategory(StrEnum):
    FACTION_CONTEXT = "faction_context"
    PROFESSION_DETAIL = "profession_detail"
    SECRET = "secret"
    PSYCHOLOGICAL_PROFILE = "psychological_profile"
    SOCIAL_CONNECTIONS = "social_connections"
    PERSONAL_HISTORY = "personal_history"


class ConnectionNodeType(StrEnum):
    INTERSECTION = "intersection"
    SETTLEMENT_GATE = "settlement_gate"
    PORTAL = "portal"
    BUILDING_ENTRANCE = "building_entrance"
    LOCATION_HUB = "location_hub"
    WAYPOINT = "waypoint"


class GraphLevel(StrEnum):
    WORLD = "world"
    CITY = "city"
    DISTRICT = "district"
    AREA = "area"


class HydrologyConnectionType(StrEnum):
    LAKE_SHORELINE = "lake_shoreline"
    COASTLINE = "coastline"
    RIVER = "river"
    MOUNTAIN_RIVER = "mountain_river"


class BridgeSubtype(StrEnum):
    PEDESTRIAN = "pedestrian"
    TRANSPORT = "transport"
    VIADUCT = "viaduct"


class SidewalkSide(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class PortalType(StrEnum):
    COORDINATE = "coordinate"
    GRAPH = "graph"


class GapPolicy(StrEnum):
    CLIP = "clip"
    FILL = "fill"
    RANDOM = "random"


class BuildingContext(StrEnum):
    INDOOR = "indoor"
    UNDERGROUND = "underground"
    NAUTICAL = "nautical"


from app.dataModel.structure.enums.staircaseType import StaircaseType  # noqa: E402 — wire re-export
from app.dataModel.structure.enums.passageType import PassageType  # noqa: E402 — wire re-export


class StreetLayout(StrEnum):
    GRID = "grid"
    ORGANIC = "organic"
    RADIAL = "radial"
    CUL_DE_SAC = "cul_de_sac"
    COURTYARD = "courtyard"


class MeasurementSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class StatConflictMode(StrEnum):
    SOFT = "soft"
    MIGRATE = "migrate"


from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode  # noqa: E402 — wire re-export
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset  # noqa: E402 — wire re-export


class SeasonKey(StrEnum):
    WINTER = "winter"
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"


class SystemGender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    ASEXUAL = "asexual"
    BOTH = "both"


from app.dataModel.settlement.enums.districtDensity import DistrictDensity  # noqa: E402 — wire re-export
