"""Wire `world.hydrology.declared_*` → generator runtime types."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.jsonValidation.worldRow import hydrology as read_hydrology, materials, terrain_scalars
from app.application.worldData.generators.hydrology.types import (
    CoastlineSpec,
    DeclaredRiverEdge,
    LakeSpec,
    RiverSystemIndex,
)
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.enums.riverSystemRole import RiverSystemRole
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass(frozen=True)
class LoadedDeclaredHydrology:
    coastline_specs: list[CoastlineSpec]
    lake_specs: list[LakeSpec]
    river_edges: list[DeclaredRiverEdge]
    river_intents: list[DeclaredRiver]
    river_system_index: RiverSystemIndex
    declared_basins: list[DeclaredBasin] = field(default_factory=list)

    @property
    def coastline_segments(self) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        return [seg for spec in self.coastline_specs for seg in spec.segments]


def _coerce_pojo(model_cls: type, value: object):
    if isinstance(value, model_cls):
        return value
    return model_cls.model_validate(value)


def _coerce_declared_coastlines(entries: list) -> list[DeclaredCoastline]:
    return [_coerce_pojo(DeclaredCoastline, entry) for entry in entries]


def _coerce_declared_lakes(entries: list) -> list[DeclaredLake]:
    return [_coerce_pojo(DeclaredLake, entry) for entry in entries]


def _coerce_declared_rivers(entries: list) -> list[DeclaredRiver]:
    return [_coerce_pojo(DeclaredRiver, entry) for entry in entries]


def build_river_system_index(rivers: list[DeclaredRiver]) -> RiverSystemIndex:
    by_uid = {river.location_uid: river for river in rivers}
    children: dict[str, list[str]] = {uid: [] for uid in by_uid}
    for river in rivers:
        parent_uid = river.parent_location_uid
        if parent_uid:
            children.setdefault(parent_uid, []).append(river.location_uid)
    topology_by_system_uid = {
        river.location_uid: river.river_system_topology.value
        for river in rivers
        if river.system_role == RiverSystemRole.SYSTEM and river.river_system_topology is not None
    }
    return RiverSystemIndex(
        by_location_uid=by_uid,
        topology_by_system_uid=topology_by_system_uid,
        children=children,
    )


def _waypoint_fine(wp: HydrologyWaypoint) -> tuple[int, int]:
    """World fine-grid cell (x, y); not a coarse map-cell index."""
    return int(wp.x), int(wp.y)


def _path_to_segments(
    points: list[HydrologyWaypoint],
    *,
    closed: bool = False,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    if len(points) < 2:
        return []
    fine_pts = [_waypoint_fine(p) for p in points]
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for i in range(len(fine_pts) - 1):
        segments.append((fine_pts[i], fine_pts[i + 1]))
    if closed and len(fine_pts) >= 3:
        segments.append((fine_pts[-1], fine_pts[0]))
    return segments


def _segments_from_declared_river(river: DeclaredRiver) -> list[DeclaredRiverEdge]:
    if river.declare_mode != RiverDeclareMode.SEGMENTS:
        return []
    edges: list[DeclaredRiverEdge] = []
    for index, seg in enumerate(river.segments):
        a = _waypoint_fine(seg.from_wp)
        b = _waypoint_fine(seg.to_wp)
        edges.append(DeclaredRiverEdge(
            edge_uid=f"dr-{river.location_uid}-{index}",
            segment=(a, b),
            connection_type=seg.connection_type,
            width_cells=int(seg.width_cells),
            location_uid=river.location_uid,
        ))
    return edges


def load_declared_hydrology(
    world: World,
    locations: list[NamedLocation],
) -> LoadedDeclaredHydrology:
    """Read POJO declare from world; segments mode → edges at import (A3 hybrid)."""
    pojo = read_hydrology(world)
    coastlines = [entry for entry in _coerce_declared_coastlines(list(pojo.declared_coastlines)) if entry.is_water_source]
    lakes = _coerce_declared_lakes(list(pojo.declared_lakes))
    rivers = _coerce_declared_rivers(list(pojo.declared_rivers))
    basins = [_coerce_pojo(DeclaredBasin, entry) for entry in pojo.declared_basins]
    if basins or coastlines or lakes:
        liquid_keys = materials(world).liquid_keys()
        for entry in [*basins, *coastlines, *lakes]:
            if entry.liquid not in liquid_keys:
                raise ValueError(f"water body {entry.location_uid}: liquid must reference a liquid material")
    if basins:
        scalars = terrain_scalars(world)
        z_min = scalars.resolved_z_min(scalars.z_min)
        for basin in basins:
            basin.validate_water_level(pojo.default_water_level)
            if basin.floor_z < z_min:
                raise ValueError(f"basin {basin.location_uid}: floor_z is below world z_min")

    return load_prepared_declared_hydrology(coastlines, lakes, rivers, basins)


def load_prepared_declared_hydrology(
    coastlines: list[DeclaredCoastline], lakes: list[DeclaredLake],
    rivers: list[DeclaredRiver], basins: list[DeclaredBasin],
) -> LoadedDeclaredHydrology:
    """Convert validated declarations with the same geometry order and identities."""
    coastline_specs: list[CoastlineSpec] = []
    for entry in coastlines:
        if not entry.is_water_source:
            continue
        segments = _path_to_segments(list(entry.path), closed=entry.closed)
        if not segments:
            continue
        coastline_specs.append(CoastlineSpec(segments=segments, location_uid=entry.location_uid))

    lake_specs: list[LakeSpec] = []
    for entry in lakes:
        segments = _path_to_segments(list(entry.shoreline), closed=True)
        if not segments:
            continue
        # Geometry-only compatibility for pack tile collection and L0 (HY-10).
        # Physical kind/level are resolved exclusively by the water pipeline.
        lake_specs.append(LakeSpec(shoreline_segments=segments, location_uid=entry.location_uid))

    river_edges: list[DeclaredRiverEdge] = []
    river_intents: list[DeclaredRiver] = []
    for river in rivers:
        if river.system_role == RiverSystemRole.SYSTEM:
            continue
        if river.declare_mode == RiverDeclareMode.SEGMENTS:
            river_edges.extend(_segments_from_declared_river(river))
        elif river.declare_mode in (RiverDeclareMode.ENDPOINTS, RiverDeclareMode.VIA_LOCATIONS):
            river_intents.append(river)

    return LoadedDeclaredHydrology(
        coastline_specs=coastline_specs,
        lake_specs=lake_specs,
        river_edges=river_edges,
        river_intents=river_intents,
        river_system_index=build_river_system_index(rivers),
        declared_basins=basins,
    )
