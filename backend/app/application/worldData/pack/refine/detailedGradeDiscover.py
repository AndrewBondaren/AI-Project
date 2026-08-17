"""Worker facade: discover fronts + L2 paint — R41 schedule A.

Catalog ``face_key`` is identity, not a seed graph. No pre-pool occupancy.
Pick runs after discover (R41-T-3). Apply takes ``DiscoveredFront`` (R41-T-2).
Classify ``path_length`` / ``dz`` come from the C41 corridor (R41-T-8).
"""

from __future__ import annotations

from collections import defaultdict

from app.application.jsonValidation import (
    relief_pick_policy,
    relief_template_registry,
    terrain_masks,
)
from app.application.worldData.generators.terrain.relief.discover.core import (
    discover_fronts,
)
from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    GRID_OUTWARD_DELTA,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    plugins_for_keys,
    shore_condition_at,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    DiscoveredFront,
    FrontGeometry,
    GradePaintSpec,
)
from app.application.worldData.generators.terrain.relief.geom.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.geom.outward import relief_dz
from app.application.worldData.generators.terrain.relief.log.log import relief_debug
from app.application.worldData.generators.terrain.relief.pick.gradeConstrained import (
    grade_constrained,
)
from app.application.worldData.generators.terrain.relief.pick.templatePick import (
    pick_template,
    resolve_picked_template,
)
from app.application.worldData.generators.terrain.relief.sample.openLandTerrains import (
    open_land_terrain_keys,
)
from app.application.worldData.generators.terrain.relief.sample.ravineTerrain import (
    ravine_terrain_key,
)
from app.application.worldData.generators.terrain.relief.sample.terrainMap import (
    map_system_terrain,
)
from app.application.worldData.generators.terrain.relief.volume.gradeInstanceFactory import (
    make_grade_uid,
)
from app.application.worldData.pack.refine.columnBounds import (
    ColumnBounds,
    expand_rect,
    rect_contains,
)
from app.application.worldData.pack.refine.detailedGradeCatalog import TileFaceCatalog
from app.application.worldData.pack.refine.detailedGradeHalo import length_cap_for_context
from app.application.worldData.pack.refine.detailedGradeMaterialize import (
    inherit_segment_uid,
)
from app.application.worldData.pack.refine.detailedGradePaint import apply_grade_paint_spec
from app.application.worldData.pack.refine.detailedGradeResult import DetailedGradeResult
from app.application.worldData.pack.refine.meterGradeSurface import (
    MeterGradeSurface,
    apply_grade_uids,
    meter_grade_cell_blocked,
)
from app.application.worldData.terrainBatchOrchestrator import TileSurfaceState
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.worldPack.packJobUid import FaceGridAxis
from app.db.models.world import World


def _axis_for_outward(outward: Facing) -> FaceGridAxis | None:
    dx, dy = GRID_OUTWARD_DELTA[outward]
    if dx != 0 and dy == 0:
        return FaceGridAxis.V
    if dy != 0 and dx == 0:
        return FaceGridAxis.H
    return None


def _terrain_of(
    surface: MeterGradeSurface,
    front: FrontGeometry,
) -> tuple[str, str]:
    raw = (
        surface.terrain_at(front.corridor[0])
        if front.corridor
        else None
    ) or surface.terrain_at(front.rim[0]) or ""
    seed = front.corridor[0] if front.corridor else front.rim[0]
    mapped = map_system_terrain(raw)
    if mapped is not None and mapped.is_shore_class():
        return mapped.value, raw
    shore = shore_condition_at(seed, surface)
    if shore is not None and (
        mapped is None
        or surface.hydro_role_at(seed) is not None
    ):
        return shore.value, raw
    key = mapped.value if mapped is not None else raw
    return key, raw


def _site_id(front: FrontGeometry) -> str:
    return (
        f"{front.context.value}|{front.rim[0][0]},{front.rim[0][1]}"
        f"|{front.outward.value}"
    )


def _uid_for_front(
    front: FrontGeometry,
    *,
    world_uid: str,
    site_id: str,
    catalog: TileFaceCatalog | None,
    existing: dict[Coord, str],
    interior_seq: dict[tuple[int, int], int],
) -> str:
    inherited = inherit_segment_uid(front.corridor[:1] or front.rim, existing)
    if inherited:
        return inherited
    if catalog is not None and front.corridor:
        faces = catalog.faces_for_cells(front.corridor)
        if faces:
            uid = catalog.uid_for_faces(
                faces, axis=_axis_for_outward(front.outward),
            )
            if uid:
                return uid
        cx, cy = catalog.chunk_of(*min(front.corridor))
        k = interior_seq[(cx, cy)]
        interior_seq[(cx, cy)] = k + 1
        return catalog.interior_uid(cx, cy, k)
    return make_grade_uid(
        world_uid=world_uid, site_id=site_id, seed=min(front.rim),
    )


def discover_and_paint(
    world: World,
    surface_state: TileSurfaceState,
    rect: ColumnBounds,
    *,
    halo: int,
    catalog: TileFaceCatalog | None,
    templates: dict[str, ReliefTemplate],
    existing_uids: dict[Coord, str] | None = None,
) -> DetailedGradeResult:
    """Discover vertices/fronts on the ready heightmap, then one L2 write-set."""
    if not templates:
        return DetailedGradeResult.empty()

    grid = MeterGradeSurface.from_tile_surface_state(
        surface_state, alias_heights=True,
    )
    known = dict(existing_uids or {})
    if known:
        apply_grade_uids(grid, known)

    contexts = frozenset(tpl.context for tpl in templates.values())
    masks = terrain_masks(world)
    road_key = str(masks.default_roads.system_terrain)
    plugins = plugins_for_keys(
        land_keys=open_land_terrain_keys(world),
        road_key=road_key,
        ravine_key=ravine_terrain_key(world),
        contexts=contexts,
    )
    barrier_keys = WorldTerrainRegistry.canonical_barrier_terrain_keys()

    def cell_blocked(xy: Coord) -> bool:
        return meter_grade_cell_blocked(
            grid, xy, road_key=road_key, barrier_keys=barrier_keys,
        )

    def cap_front(context: ReliefContext) -> int | None:
        return length_cap_for_context(context, templates)

    grid_rect = expand_rect(rect, max(0, int(halo)))
    _vertices, fronts = discover_fronts(
        grid,
        origin_x=grid_rect.x_min,
        origin_y=grid_rect.y_min,
        width=grid_rect.x_max - grid_rect.x_min + 1,
        height=grid_rect.y_max - grid_rect.y_min + 1,
        plugins=plugins,
        cell_blocked=cell_blocked,
        existing_uids=known,
        cap_front=cap_front,
    )

    world_seed = bake_seed(world)
    registry = relief_template_registry(world)
    policy = relief_pick_policy(world)
    pick_seq = 0
    acc = DetailedGradeResult.empty()
    interior_seq: dict[tuple[int, int], int] = defaultdict(int)
    for front in fronts:
        owned = tuple(
            xy for xy in front.corridor
            if rect_contains(rect, xy[0], xy[1])
        )
        if not owned:
            continue
        terrain_key, system_terrain = _terrain_of(grid, front)
        site_id = _site_id(front)
        path_length = int(front.path_length)
        if path_length < 1:
            relief_debug(
                "grade_front_skip",
                why="no_path_length",
                site_id=site_id,
            )
            continue
        pick = pick_template(
            context=front.context,
            registry=registry,
            world_policy=policy,
            world_seed=world_seed,
            site_id=site_id,
            occurrence_seq=pick_seq,
        )
        pick_seq += 1
        template = resolve_picked_template(pick, templates)
        if template is None:
            relief_debug(
                "grade_front_skip",
                why="no_template",
                site_id=site_id,
                context=front.context.value,
            )
            continue
        dz = relief_dz(front.z_body, front.z_end)
        decision = grade_constrained(
            template=template,
            template_uid=pick.template_uid or template.system_name,
            terrain_key=terrain_key,
            dz=dz,
            world_seed=world_seed,
            site_id=site_id,
            path_length=path_length,
        )
        if decision.skipped or decision.kind is None or int(decision.h) < 1:
            relief_debug(
                "grade_front_skip",
                why="constrained",
                site_id=site_id,
                skipped=decision.skipped,
            )
            continue
        uid = _uid_for_front(
            front,
            world_uid=world.world_uid,
            site_id=site_id,
            catalog=catalog,
            existing=known,
            interior_seq=interior_seq,
        )
        painted = DiscoveredFront(
            spec=GradePaintSpec(
                grade_uid=uid,
                outward=front.outward,
                front_w=len(front.rim),
                anchor_top=min(front.rim),
                anchor_bottom=front.anchor_bottom,
                decision=decision,
                corridor=front.corridor,
            ),
            context=front.context,
            site_id=site_id,
            slot=front.slot,
            template_uid=pick.template_uid,
            rim=front.rim,
            terrain_key=terrain_key,
            system_terrain=system_terrain or terrain_key,
            dz=dz,
        )
        part = apply_grade_paint_spec(painted, world=world, surface=grid)
        clipped = part.clipped_to_rect(rect)
        acc = acc.merged_with(clipped)
        apply_grade_uids(grid, clipped.surface_grade_uid)
        known.update(clipped.surface_grade_uid)
    return acc
