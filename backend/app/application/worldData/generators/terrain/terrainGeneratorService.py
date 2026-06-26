import hashlib
from typing import Optional

from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    settlement_grid_rect,
)
from app.application.worldData.generators.coordinates import (
    cell_size_m,
    meters_to_grid_x,
    meters_to_grid_y,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


# Location types that act as surface anchors (get "urban" cells)
_CITY_TYPES = frozenset({"city", "town", "village", "camp"})

# Location types that define terrain zones
_ZONE_TYPES = frozenset({"region", "kingdom", "empire", "duchy"})

# climate_zone → base z-elevation
_CLIMATE_TO_Z: dict[str, int] = {
    "arctic": 4, "tundra": 3, "subarctic": 3, "subpolar": 2,
    "cold": 2, "cold_temperate": 1,
    "temperate": 0, "continental": 0,
    "arid": 0, "mediterranean": 0,
    "subtropical": -1, "coastal": -1, "maritime": -1, "tropical": -1,
}

# climate_zone → base temperature at z=0 (°C)
_CLIMATE_BASE_TEMP: dict[str, int] = {
    "arctic": -35, "tundra": -20, "subarctic": -15, "subpolar": -10,
    "cold": -5, "cold_temperate": 0,
    "temperate": 10, "continental": 8,
    "arid": 20, "mediterranean": 15,
    "subtropical": 22, "coastal": 14, "maritime": 12, "tropical": 28,
}


def _z_to_terrain(z: int, terrain_set: set[str]) -> str:
    if z >= 2:
        candidates = ["tundra", "plains"]
    elif z == 1:
        candidates = ["forest", "plains"]
    elif z == 0:
        candidates = ["plains"]
    else:
        candidates = ["liquid_body", "plains"]
    for t in candidates:
        if t in terrain_set:
            return t
    return next(iter(terrain_set), "plains")


def _cell_z_noise(world_seed: int, x: int, y: int, base_z: int, amplitude: int = 1) -> int:
    """Deterministic per-cell z noise. Same world + same (x,y) → same result."""
    h = (world_seed ^ (x * 73856093) ^ (y * 19349663)) & 0xFFFFFFFF
    noise = (h % (2 * amplitude + 1)) - amplitude
    return base_z + noise


def _dist_sq(x1: int, y1: int, x2: int, y2: int) -> int:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2


class TerrainGeneratorService:
    """
    Pure utility — no repositories, no async.
    Deterministic: same world_uid + same locations → same map_cells output.

    Importable by both worldData services (eager init) and engine nodes (lazy/repair).
    """

    def generate_surface(
        self,
        world: World,
        locations: list[NamedLocation],
        padding: int = 2,
        skip_location_uids: frozenset[str] = frozenset(),
    ) -> list[MapCell]:
        """
        Step 1 eager init: generate one surface cell per (x, y) in bounding box.

        City anchors expand into footprints based on city_size_registry radius.
        Surrounding grid is filled with climate-based terrain via nearest-city Voronoi.

        skip_location_uids: cities whose cells already exist in DB — their footprint is
        skipped (explicit fixture shape is preserved) but they stay in Voronoi for climate.
        """
        if not locations:
            return []

        world_seed   = int(hashlib.md5(world.world_uid.encode()).hexdigest()[:8], 16)
        terrain_reg  = world.terrain_registry or []
        terrain_set  = {t["system_terrain"] for t in terrain_reg if "system_terrain" in t}
        lapse_rate   = world.elevation_lapse_rate or 7.0
        z_min       = world.z_min if world.z_min is not None else -3
        z_max       = world.z_max if world.z_max is not None else 4

        uid_map: dict[str, NamedLocation] = {l.location_uid: l for l in locations}
        cell_m = cell_size_m(world)

        # Anchor locations: have physical map coords and are not mobile
        anchors = [
            l for l in locations
            if l.map_x is not None and l.map_y is not None
            and l.map_z is not None and not l.is_mobile
        ]
        if not anchors:
            return []

        # City anchors + Voronoi centers in world surface grid indices (not meter anchor).
        city_list = [l for l in anchors if l.system_location_type in _CITY_TYPES]
        city_centers: dict[tuple[int, int], NamedLocation] = {
            (
                meters_to_grid_x(city.map_x, cell_m),
                meters_to_grid_y(city.map_y, cell_m),
            ): city
            for city in city_list
        }

        # Zone for each city: walk up tree to first zone-type ancestor
        city_zones: dict[str, NamedLocation] = {}
        for city in city_list:
            zone = self._find_zone(city, uid_map)
            if zone:
                city_zones[city.location_uid] = zone

        # Expand each city into a footprint (same grid rect as settlement occupancy).
        # all_footprints: every city (including skipped) — used for stable bounding box.
        # city_footprint: only non-skipped cities — used for urban cell assignment.
        # cell (gx, gy) → owning city; first-claimed wins on overlap.
        all_footprints:  dict[tuple[int, int], NamedLocation] = {}
        city_footprint:  dict[tuple[int, int], NamedLocation] = {}
        for city in city_list:
            rect = settlement_grid_rect(world, city)
            for gy in range(rect.gy0, rect.gy1):
                for gx in range(rect.gx0, rect.gx1):
                    pos = (gx, gy)
                    if pos not in all_footprints:
                        all_footprints[pos] = city
                    if city.location_uid not in skip_location_uids:
                        if pos not in city_footprint:
                            city_footprint[pos] = city

        # Grid bounds: always driven by ALL footprints so the grid is stable
        # regardless of which cities are already in the DB (skip_location_uids).
        if all_footprints:
            x_min = min(p[0] for p in all_footprints) - padding
            x_max = max(p[0] for p in all_footprints) + padding
            y_min = min(p[1] for p in all_footprints) - padding
            y_max = max(p[1] for p in all_footprints) + padding
        else:
            x_min = min(meters_to_grid_x(l.map_x, cell_m) for l in anchors) - padding
            x_max = max(meters_to_grid_x(l.map_x, cell_m) for l in anchors) + padding
            y_min = min(meters_to_grid_y(l.map_y, cell_m) for l in anchors) - padding
            y_max = max(meters_to_grid_y(l.map_y, cell_m) for l in anchors) + padding

        cells: list[MapCell] = []
        for y in range(y_min, y_max + 1):
            for x in range(x_min, x_max + 1):
                pos = (x, y)

                if pos in city_footprint:
                    city    = city_footprint[pos]
                    z       = city.map_z
                    terrain = "urban" if "urban" in terrain_set else _z_to_terrain(0, terrain_set)
                    loc_uid = city.location_uid
                    climate = self._city_climate(city, city_zones, world)
                elif pos in all_footprints:
                    # Skipped city footprint — explicit cells already in DB, don't touch.
                    continue
                else:
                    nearest = self._nearest_city(x, y, city_centers)
                    climate = self._city_climate(nearest, city_zones, world) if nearest else (
                        world.default_climate_zone or "temperate"
                    )
                    base_z  = _CLIMATE_TO_Z.get(climate, 0)
                    raw_z   = _cell_z_noise(world_seed, x, y, base_z)
                    z       = max(z_min, min(z_max, raw_z))
                    terrain = _z_to_terrain(z, terrain_set)
                    zone    = city_zones.get(nearest.location_uid) if nearest else None
                    loc_uid = zone.location_uid if zone else (nearest.location_uid if nearest else None)

                base_temp = _CLIMATE_BASE_TEMP.get(climate, 5)
                cells.append(MapCell(
                    world_uid=world.world_uid,
                    x=x,
                    y=y,
                    z=z,
                    system_terrain=terrain,
                    temperature_base=round(base_temp - z * lapse_rate),
                    location_uid=loc_uid,
                ))

        # Additional anchor cells for non-surface locations (mines, underground cities, etc.)
        # These are at different z than surface, so added without overwriting surface cells
        for anchor in anchors:
            if anchor.system_location_type in _CITY_TYPES:
                continue  # already handled above
            climate   = self._resolve_climate(anchor, uid_map, world)
            base_temp = _CLIMATE_BASE_TEMP.get(climate, 5)
            cells.append(MapCell(
                world_uid=world.world_uid,
                x=anchor.map_x,
                y=anchor.map_y,
                z=anchor.map_z,
                system_terrain=_z_to_terrain(anchor.map_z, terrain_set),
                temperature_base=round(base_temp - anchor.map_z * lapse_rate),
                location_uid=anchor.location_uid,
            ))

        return cells

    def generate_minimal(self, world: World, location: NamedLocation) -> list[MapCell]:
        """
        Broken location repair: create a single anchor cell for a location
        that has no map_cells. Used in engine nodes during active sessions.
        """
        terrain_reg = world.terrain_registry or []
        terrain_set = {t["system_terrain"] for t in terrain_reg if "system_terrain" in t}
        lapse_rate  = world.elevation_lapse_rate or 7.0

        x = location.map_x if location.map_x is not None else 0
        y = location.map_y if location.map_y is not None else 0
        z = location.map_z if location.map_z is not None else 0

        terrain   = "urban" if location.system_location_type in _CITY_TYPES and "urban" in terrain_set \
                    else _z_to_terrain(z, terrain_set)
        base_temp = _CLIMATE_BASE_TEMP.get(location.system_climate_zone or "temperate", 5)

        return [MapCell(
            world_uid=world.world_uid,
            x=x, y=y, z=z,
            system_terrain=terrain,
            temperature_base=round(base_temp - z * lapse_rate),
            location_uid=location.location_uid,
        )]

    # ------------------------------------------------------------------

    def _find_zone(
        self,
        location: NamedLocation,
        uid_map: dict[str, NamedLocation],
    ) -> Optional[NamedLocation]:
        current = uid_map.get(location.parent_location_uid)
        while current:
            if current.system_location_type in _ZONE_TYPES:
                return current
            current = uid_map.get(current.parent_location_uid)
        return None

    def _resolve_climate(
        self,
        location: NamedLocation,
        uid_map: dict[str, NamedLocation],
        world: World,
    ) -> str:
        current: Optional[NamedLocation] = location
        while current:
            if current.system_climate_zone:
                return current.system_climate_zone
            current = uid_map.get(current.parent_location_uid)
        return world.default_climate_zone or "temperate"

    def _city_climate(
        self,
        city: Optional[NamedLocation],
        city_zones: dict[str, NamedLocation],
        world: World,
    ) -> str:
        if city is None:
            return world.default_climate_zone or "temperate"
        zone = city_zones.get(city.location_uid)
        if zone and zone.system_climate_zone:
            return zone.system_climate_zone
        if city.system_climate_zone:
            return city.system_climate_zone
        return world.default_climate_zone or "temperate"

    def _nearest_city(
        self,
        x: int,
        y: int,
        city_centers: dict[tuple[int, int], NamedLocation],
    ) -> Optional[NamedLocation]:
        best      = None
        best_dist = float("inf")
        for (cx, cy), loc in city_centers.items():
            d = _dist_sq(x, y, cx, cy)
            if d < best_dist:
                best_dist = d
                best      = loc
        return best
