from enum import StrEnum


class SettlementPersistScope(StrEnum):
    OCCUPANCY            = "occupancy"
    MAP_CELLS_SURFACE    = "map_cells_surface"
    MAP_CELLS_GEOMETRY   = "map_cells_geometry"
    CONNECTIONS_CITY     = "connections_city"
    CONNECTIONS_DISTRICT = "connections_district"
    BUILDINGS            = "buildings"


OUTDOOR_SCOPES = frozenset({
    SettlementPersistScope.MAP_CELLS_SURFACE,
    SettlementPersistScope.MAP_CELLS_GEOMETRY,
    SettlementPersistScope.CONNECTIONS_CITY,
    SettlementPersistScope.CONNECTIONS_DISTRICT,
    SettlementPersistScope.BUILDINGS,
})
