"""ENUM-E wire values — docs/tz_json_validation.md JV-0/JV-2."""

from __future__ import annotations

from enum import StrEnum


class MaterialCategory(StrEnum):
    SOLID = "solid"
    LIQUID = "liquid"
    GAS = "gas"


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


class StaircaseType(StrEnum):
    LADDER = "ladder"
    SPIRAL_SMALL = "spiral_small"
    SPIRAL_STANDARD = "spiral_standard"
    STANDARD = "standard"
    STRAIGHT = "straight"
    U_SHAPE = "u_shape"


class StreetLayout(StrEnum):
    GRID = "grid"
    ORGANIC = "organic"
    RADIAL = "radial"
    CUL_DE_SAC = "cul_de_sac"
    COURTYARD = "courtyard"


class DistrictDensity(StrEnum):
    SPARSE = "sparse"
    MEDIUM = "medium"
    DENSE = "dense"


class MeasurementSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class StatConflictMode(StrEnum):
    SOFT = "soft"
    MIGRATE = "migrate"


class ClimatePoleMode(StrEnum):
    MANUAL = "manual"
    AUTORESOLVE = "autoresolve"


class ClimatePolePreset(StrEnum):
    ICE = "ice"
    DESERT = "desert"
    BINARY = "binary"


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
