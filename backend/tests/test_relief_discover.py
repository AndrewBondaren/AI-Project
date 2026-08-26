"""Relief pipeline v2 discover — C39 / C41 / R42 unit geometry."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.discover.apron import (
    enclosed_one_cell_pit,
    is_q2_seed,
    is_side_seed,
    is_slope_corridor_cell,
    resolve_side_parent,
)
from app.application.worldData.generators.terrain.relief.discover.core import (
    DiscoverResult,
    discover_fronts,
)
from app.application.worldData.generators.terrain.relief.discover.fronts import FrontStage
from app.application.worldData.generators.terrain.relief.discover.millBuckets import (
    BucketRef,
    MillBuckets,
    Q2Kind,
    UNSET_SLOT,
)
from app.application.worldData.generators.terrain.relief.discover.millCorridor import (
    corridor_from_cells,
)
from app.application.worldData.generators.terrain.relief.discover.millSchedule import (
    is_q2_side_event,
)
from app.application.worldData.generators.terrain.relief.discover.rim import (
    iter_rect_z_cells,
    seed_rim,
)
from app.application.worldData.generators.terrain.relief.discover.plugins import (
    OpenLandPlugin,
    RoadShoulderPlugin,
    ShorePlugin,
    plugins_for_keys,
    shore_condition_at,
)
from app.application.worldData.generators.terrain.relief.discover.seam import SeamStage
from app.application.worldData.generators.terrain.relief.discover.types import (
    FOREIGN_MARK,
    Coord,
    ProposedTrace,
    ReliefVertices,
)
from app.application.worldData.generators.terrain.relief.sample.openLandTerrains import (
    open_land_terrain_keys,
)
from app.application.worldData.generators.terrain.relief.sample.ravineTerrain import (
    ravine_terrain_key,
)
from app.application.worldData.pack.refine.meterGradeSurface import (
    MeterGradeSurface,
    meter_grade_cell_blocked,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain, ReliefContext
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.relief.reliefGradeKnobs import DEFAULT_SLOPE_LENGTH_CELLS
from app.dataModel.terrain.relief.reliefTerrainEnvelope import ReliefOntologyEnvelopes
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks

_MASKS = WorldTerrainMasks.canonical_defaults()
_PLAINS = _MASKS.default_plains.system_terrain
_FOREST = _MASKS.default_forests.system_terrain
_ROAD = _MASKS.default_roads.system_terrain
_RAVINE = ravine_terrain_key()
_LAND = open_land_terrain_keys()
_ENVELOPE_L_FLOOR = (
    ReliefOntologyEnvelopes.canonical_defaults()
    .for_terrain(ReliefConditionTerrain.PLAINS)
    .length_from_min_cells()
)
_SHORE_SEA = ReliefConditionTerrain.SHORE_SEA.value
_BARRIERS = WorldTerrainRegistry.canonical_barrier_terrain_keys()


def _vertices_for(z: dict[Coord, int]) -> ReliefVertices:
    xs = [x for x, _y in z]
    ys = [y for _x, y in z]
    return ReliefVertices.for_bounds(
        origin_x=min(xs),
        origin_y=min(ys),
        width=max(xs) - min(xs) + 1,
        height=max(ys) - min(ys) + 1,
    )


def _surface(z: dict[Coord, int], terrain: str = _PLAINS) -> MeterGradeSurface:
    return MeterGradeSurface(
        surface_z=z,
        surface_terrain={xy: terrain for xy in z},
        hydrology=None,
        surface_facing=None,
    )


def _geom(result: DiscoverResult) -> tuple[ReliefVertices, tuple]:
    return result.vertices, result.fronts


def _run_discover(*args, **kwargs) -> tuple[ReliefVertices, tuple]:
    return _geom(discover_fronts(*args, **kwargs))


def _discover_result(z: dict[Coord, int]) -> DiscoverResult:
    xs = [x for x, _y in z]
    ys = [y for _x, y in z]
    surface = _surface(z)
    return discover_fronts(
        surface,
        origin_x=min(xs),
        origin_y=min(ys),
        width=max(xs) - min(xs) + 1,
        height=max(ys) - min(ys) + 1,
        plugins=(OpenLandPlugin(_LAND),),
        cell_blocked=lambda _xy: False,
    )


def _discover(z: dict[Coord, int]) -> tuple[ReliefVertices, tuple]:
    return _geom(_discover_result(z))


def _discover_ravine(
    z: dict[Coord, int],
    terrain: dict[Coord, str],
    *,
    cap_front=None,
    envelopes=None,
) -> tuple[ReliefVertices, tuple]:
    xs = [x for x, _y in z]
    ys = [y for _x, y in z]
    surface = MeterGradeSurface(
        surface_z=z,
        surface_terrain=terrain,
        hydrology=None,
        surface_facing=None,
    )
    return _geom(discover_fronts(
        surface,
        origin_x=min(xs),
        origin_y=min(ys),
        width=max(xs) - min(xs) + 1,
        height=max(ys) - min(ys) + 1,
        plugins=plugins_for_keys(
            land_keys=_LAND,
            road_key=_ROAD,
            ravine_key=_RAVINE,
            contexts=frozenset({ReliefContext.RAVINE, ReliefContext.OPEN_LAND}),
        ),
        cell_blocked=lambda _xy: False,
        cap_front=cap_front,
        envelopes=envelopes,
    ))


def _discover_shore(
    z: dict[Coord, int],
    terrain: dict[Coord, str],
    hydro: dict[Coord, MapCellHydrology] | None,
    *,
    cap_front=None,
    envelopes=None,
    cell_blocked=None,
) -> tuple[ReliefVertices, tuple]:
    xs = [x for x, _y in z]
    ys = [y for _x, y in z]
    surface = MeterGradeSurface(
        surface_z=z,
        surface_terrain=terrain,
        hydrology=hydro,
        surface_facing=None,
    )
    blocked = cell_blocked
    if blocked is None:
        blocked = lambda xy: meter_grade_cell_blocked(
            surface, xy, road_key=_ROAD, barrier_keys=_BARRIERS,
        )
    return _geom(discover_fronts(
        surface,
        origin_x=min(xs),
        origin_y=min(ys),
        width=max(xs) - min(xs) + 1,
        height=max(ys) - min(ys) + 1,
        plugins=plugins_for_keys(
            land_keys=_LAND,
            road_key=_ROAD,
            ravine_key=_RAVINE,
            contexts=frozenset({ReliefContext.SHORE, ReliefContext.OPEN_LAND}),
            envelopes=envelopes,
        ),
        cell_blocked=blocked,
        cap_front=cap_front,
        envelopes=envelopes,
    ))


class ReliefDiscoverTest(unittest.TestCase):
    def test_import_types_not_persist(self) -> None:
        from app.application.worldData.generators.terrain.relief.discover import (
            GradePaintSpec,
            ReliefVertices,
        )
        from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance

        self.assertFalse(hasattr(ReliefVertices, "model_fields"))
        self.assertFalse(hasattr(GradePaintSpec, "model_fields"))
        self.assertTrue(hasattr(ReliefGradeInstance, "model_fields"))

    def test_mill_stage_s_has_q_and_total(self) -> None:
        z = {
            (0, 1): 4, (1, 1): 4, (2, 1): 4,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        mill = _discover_result(z).mill
        payload = mill.as_dict()
        for key in (
            "q1_s",
            "q2_s",
            "mill_setup_s",
            "mill_sheer_s",
            "mill_seam_s",
            "mill_reconcile_s",
            "mill_s",
        ):
            self.assertIn(key, payload)
            self.assertGreaterEqual(payload[key], 0.0)
        self.assertNotIn("q3_s", payload)
        self.assertFalse(hasattr(mill, "q3_s"))
        self.assertGreaterEqual(mill.mill_s, mill.q_total_s)
        empty = discover_fronts(
            _surface({(0, 0): 1}),
            origin_x=0,
            origin_y=0,
            width=1,
            height=1,
            plugins=(),
            cell_blocked=lambda _xy: False,
        )
        self.assertEqual(empty.mill.mill_s, empty.mill.mill_setup_s)
        self.assertEqual(empty.mill.q1_s, 0.0)
        self.assertEqual(empty.fronts, ())
        self.assertEqual(empty.side_parent, {})

    def test_discover_fronts_one_walk_no_grid_drain(self) -> None:
        import inspect

        from app.application.worldData.generators.terrain.relief.discover.core import (
            discover_fronts as mill,
        )
        from app.application.worldData.generators.terrain.relief.discover.millSchedule import (
            run_mill_schedule,
        )
        from app.application.worldData.generators.terrain.relief.discover.rim import RimStage

        src = inspect.getsource(mill)
        self.assertIn("run_mill_schedule", src)
        self.assertIn("iter_rect_z_cells", src)
        self.assertNotIn("fill_leftover", src)
        self.assertNotIn("buckets_high_to_low", src)
        self.assertNotIn("def _drain", src)
        sched = inspect.getsource(run_mill_schedule)
        self.assertNotIn("fill_leftover", sched)
        self.assertNotIn("def _drain", sched)
        self.assertIn("max_leftover_z", sched)
        self.assertFalse(hasattr(RimStage, "buckets_high_to_low"))
        self.assertFalse(hasattr(RimStage, "fill_leftover"))

    def test_z_top_mills_q2_before_lower_leftover(self) -> None:
        """Q2 SHEER landing (not C39) mills before leftover C39 at a lower z."""
        z = {
            (0, 1): 8, (1, 1): 8, (2, 1): 8,
            (0, 0): 7, (1, 0): 7, (2, 0): 7,
            (3, 1): 6,
            (10, 2): 4, (10, 1): 2,
        }
        order: list[tuple[int, Coord]] = []

        class _OrderPlugin(OpenLandPlugin):
            def accept_flood(self, body, surface):
                ok = super().accept_flood(body, surface)
                if ok and body:
                    z_body = int(next(iter(body.values())))
                    order.append((z_body, min(body)))
                return ok

        surface = _surface(z)
        discover_fronts(
            surface,
            origin_x=0,
            origin_y=0,
            width=11,
            height=3,
            plugins=(_OrderPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
        )
        zs = [item[0] for item in order]
        self.assertGreaterEqual(len(zs), 3)
        self.assertEqual(zs[0], 8)
        self.assertIn(6, zs)
        self.assertIn(4, zs)
        self.assertLess(zs.index(6), zs.index(4))

    def test_mesa_8_connected_gy_901(self) -> None:
        """Diagonal 4 on 901 col4 is the same vertex as the plateau (R41)."""
        z = {
            (0, 901): 4, (1, 901): 4, (2, 901): 4, (3, 901): 2, (4, 901): 4,
            (0, 900): 4, (1, 900): 4, (2, 900): 4, (3, 900): 4, (4, 900): 3,
        }
        vertices, _fronts = _discover(z)
        fours = [xy for xy, h in z.items() if h == 4]
        slots = {vertices.at_grid[vertices.index(x, y)] for x, y in fours}
        self.assertEqual(slots, {1})
        self.assertIn((4, 901), vertices.members[0])
        self.assertIn((0, 901), vertices.members[0])
        self.assertNotIn((3, 901), vertices.members[0])

    def test_front_w_times_l_cardinal(self) -> None:
        z = {
            (0, 1): 4, (1, 1): 4, (2, 1): 4,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        _vertices, fronts = _discover(z)
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertTrue(south)
        front = max(south, key=lambda f: len(f.rim))
        self.assertEqual(len(front.rim), 3)
        self.assertEqual(front.outward, Facing.SOUTH)
        self.assertGreaterEqual(len(front.corridor), 3)

    def test_claimed_landing_skips_slope_walk(self) -> None:
        """Occupied (landing, Facing) is dropped before lockstep SLOPE."""
        z = {(0, 1): 4, (0, 0): 3}
        surface = _surface(z)
        vertices = ReliefVertices.for_bounds(
            origin_x=0, origin_y=0, width=1, height=2,
        )
        body = {(0, 1): 4}
        slot = vertices.add_vertex(body)
        self.assertTrue(vertices.claim_facings(((0, 0),), Facing.SOUTH))
        traces = FrontStage(surface, vertices, lambda _xy: False).propose(
            slot, body, OpenLandPlugin(_LAND),
        )
        self.assertEqual(traces, ())

    def test_steep_first_step_is_not_a_slope_walk(self) -> None:
        """First-step envelope class is SHEER → no long SLOPE ray."""
        z = {(0, 1): 4, (0, 0): 2}
        surface = _surface(z)
        vertices = ReliefVertices.for_bounds(
            origin_x=0, origin_y=0, width=1, height=2,
        )
        body = {(0, 1): 4}
        slot = vertices.add_vertex(body)
        stage = FrontStage(surface, vertices, lambda _xy: False)
        plugin = OpenLandPlugin(_LAND)
        self.assertEqual(stage.propose(slot, body, plugin), ())
        sheers = stage.propose_sheers(slot, body, plugin)
        self.assertEqual(len(sheers), 1)
        self.assertEqual(sheers[0].first_dz, 2)
        self.assertEqual(sheers[0].trace, ((0, 0),))

    def test_isolated_peak_shoots_eight_facings(self) -> None:
        """One rim cell may look all 8 ways; each Facing is one ray."""
        z = {
            (0, 2): 2, (1, 2): 2, (2, 2): 2,
            (0, 1): 2, (1, 1): 4, (2, 1): 2,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        _vertices, fronts = _discover(z)
        self.assertEqual({f.outward for f in fronts}, set(Facing))
        self.assertEqual(len(fronts), 8)
        occupied = {xy for f in fronts for xy in f.corridor}
        self.assertEqual(len(occupied), 8)
        self.assertNotIn((1, 1), occupied)

    def test_mesa_south_does_not_fire_diagonal_into_ortho(self) -> None:
        """SE from a west rim cell must not land on the neighbor's south cell."""
        z = {
            (0, 1): 4, (1, 1): 4, (2, 1): 4,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        _vertices, fronts = _discover(z)
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertEqual(len(south), 1)
        self.assertEqual(set(south[0].corridor), {(0, 0), (1, 0), (2, 0)})
        diagonal = [
            f for f in fronts
            if f.outward in (Facing.SOUTHEAST, Facing.SOUTHWEST)
        ]
        for front in diagonal:
            self.assertFalse(set(front.corridor) & {(0, 0), (1, 0), (2, 0)})

    def test_bowl_sides_keep_unique_cells(self) -> None:
        """A basin is not one slope: four sides stamp unique mid-edges; center is free."""
        z = {}
        for x in range(5):
            for y in range(5):
                interior = 1 <= x <= 3 and 1 <= y <= 3
                z[(x, y)] = 2 if interior else 4
        vertices, fronts = _discover(z)
        center = (2, 2)
        i = vertices.index(*center)
        self.assertIsNotNone(i)
        self.assertEqual(vertices.seam[i], 0)
        self.assertEqual(vertices.occ[i], 0)
        for front in fronts:
            self.assertNotIn(center, front.corridor)
        outwards = {f.outward for f in fronts}
        self.assertGreaterEqual(
            outwards & {Facing.NORTH, Facing.SOUTH, Facing.EAST, Facing.WEST},
            {Facing.NORTH, Facing.SOUTH, Facing.EAST, Facing.WEST},
        )
        occupied = {xy for f in fronts for xy in f.corridor}
        self.assertTrue({(2, 3), (2, 1), (1, 2), (3, 2)} <= occupied)
        for corner in ((1, 3), (3, 3), (1, 1), (3, 1)):
            ci = vertices.index(*corner)
            self.assertNotEqual(vertices.seam[ci], 0)
            self.assertEqual(vertices.occ[ci], 0)

    def test_one_by_one_hole_skips(self) -> None:
        z = {
            (0, 2): 4, (1, 2): 4, (2, 2): 4,
            (0, 1): 4, (1, 1): 2, (2, 1): 4,
            (0, 0): 4, (1, 0): 4, (2, 0): 4,
        }
        vertices, fronts = _discover(z)
        hole = (1, 1)
        i = vertices.index(*hole)
        self.assertNotEqual(vertices.seam[i], 0)
        self.assertEqual(fronts, ())
        self.assertEqual(vertices.occ[i], 0)
        self.assertEqual(vertices.at_grid[i], 0)

    def test_mixed_heights_share_pit_across_vertices(self) -> None:
        """6 / 4 / 3 may all shoot into 2; the pit is seam, not first-wins occ."""
        z = {
            (0, 2): 4, (1, 2): 6, (2, 2): 3,
            (0, 1): 4, (1, 1): 2, (2, 1): 3,
            (0, 0): 3, (1, 0): 4, (2, 0): 3,
        }
        vertices, fronts = _discover(z)
        pit = (1, 1)
        i = vertices.index(*pit)
        self.assertIsNotNone(i)
        self.assertNotEqual(vertices.seam[i], 0)
        self.assertEqual(vertices.occ[i], 0)
        for front in fronts:
            self.assertNotIn(pit, front.corridor)
        peak_slot = vertices.at_grid[vertices.index(1, 2)]
        self.assertNotEqual(peak_slot, 0)
        self.assertGreaterEqual(len(vertices.members), 2)

    def test_unit_dz_plains_stamps_slope_corridor(self) -> None:
        z = {(0, 0): 4, (1, 0): 3, (2, 0): 2}
        vertices, fronts = _discover(z)
        east = [f for f in fronts if f.outward is Facing.EAST]
        self.assertTrue(east)
        corridor = {xy for f in east for xy in f.corridor}
        self.assertTrue(corridor)
        for xy in corridor:
            i = vertices.index(*xy)
            self.assertNotEqual(vertices.occ[i], 0)
            self.assertEqual(vertices.at_grid[i], 0)
        self.assertNotEqual(vertices.at_grid[vertices.index(0, 0)], 0)

    def test_lower_terrace_seeds_when_upper_drop_is_sheer(self) -> None:
        """Plains |dz|=2 is sheer: the terrace is a vertex, not a slope corridor."""
        z = {
            (0, 2): 6, (1, 2): 6, (2, 2): 6,
            (0, 1): 4, (1, 1): 4, (2, 1): 4,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        vertices, fronts = _discover(z)
        mesa_slot = vertices.at_grid[vertices.index(1, 2)]
        terrace = {(0, 1), (1, 1), (2, 1)}
        for xy in terrace:
            i = vertices.index(*xy)
            slot = vertices.at_grid[i]
            self.assertNotEqual(slot, 0)
            self.assertNotEqual(slot, mesa_slot)
            self.assertEqual(vertices.occ[i], 0)
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertTrue(south)

    def test_uncovered_east_landing_is_q2_vertex_with_parent_sheer(self) -> None:
        """Mesa z=8; south |dz|=1 slope; east z=6 is Q2 landing, parent SHEER."""
        z = {
            (0, 1): 8, (1, 1): 8, (2, 1): 8,
            (0, 0): 7, (1, 0): 7, (2, 0): 7,
            (3, 1): 6,
        }
        vertices, fronts = _discover(z)
        landing = (3, 1)
        i = vertices.index(*landing)
        self.assertIsNotNone(i)
        landing_slot = vertices.at_grid[i]
        mesa_slot = vertices.at_grid[vertices.index(1, 1)]
        self.assertNotEqual(landing_slot, 0)
        self.assertNotEqual(landing_slot, mesa_slot)
        self.assertEqual(vertices.occ[i], 0)
        east = [
            f for f in fronts
            if f.outward is Facing.EAST and f.slot == mesa_slot
        ]
        self.assertTrue(east)
        self.assertIn(landing, east[0].corridor)
        self.assertEqual(east[0].first_dz, 2)

    def test_q2_same_z_side_of_slope_corridor_is_new_vertex(self) -> None:
        """|dz|=1 plains corridor; same-z cell south of occ, not 8-adj to the body."""
        z = {
            (0, 2): 4, (1, 2): 4, (2, 2): 4,
            (0, 1): 3, (1, 1): 3, (2, 1): 3,
            (1, 0): 3,
        }
        got = _discover_result(z)
        vertices = got.vertices
        side = (1, 0)
        i = vertices.index(*side)
        mesa_slot = vertices.at_grid[vertices.index(1, 2)]
        side_slot = vertices.at_grid[i]
        self.assertNotEqual(side_slot, 0)
        self.assertNotEqual(side_slot, mesa_slot)
        self.assertEqual(vertices.occ[i], 0)
        corridor = vertices.index(1, 1)
        self.assertNotEqual(vertices.occ[corridor], 0)
        self.assertEqual(got.side_parent.get(side_slot), mesa_slot)

    def test_q2_drains_disconnected_sides(self) -> None:
        """Two same-z sides of one corridor, not 8-linked through free cells, both Q2."""
        z = {
            (1, 2): 4, (2, 2): 4, (3, 2): 4,
            (1, 1): 3, (2, 1): 3, (3, 1): 3,
            (0, 0): 3, (4, 0): 3,
        }
        got = _discover_result(z)
        vertices = got.vertices
        mesa_slot = vertices.at_grid[vertices.index(2, 2)]
        west = vertices.at_grid[vertices.index(0, 0)]
        east = vertices.at_grid[vertices.index(4, 0)]
        self.assertNotEqual(west, 0)
        self.assertNotEqual(east, 0)
        self.assertNotEqual(west, mesa_slot)
        self.assertNotEqual(east, mesa_slot)
        self.assertNotEqual(west, east)
        self.assertEqual(got.side_parent.get(west), mesa_slot)
        self.assertEqual(got.side_parent.get(east), mesa_slot)
        surface = _surface(z)
        self.assertFalse(is_side_seed((0, 0), surface, vertices))
        self.assertFalse(is_side_seed((4, 0), surface, vertices))

    def test_q1_cell_is_not_side_predicate(self) -> None:
        """C39 leftover can be same-z of occ; scheduler still skips it as Q2 side."""
        z = {
            (1, 1): 4, (1, 0): 3, (2, 1): 4,
        }
        surface = _surface(z)
        vertices = _vertices_for(z)
        vertices.mark_occ((2, 1), 1)
        never = lambda _a, _b: False
        self.assertTrue(seed_rim((1, 1), surface, vertices))
        self.assertTrue(is_side_seed((1, 1), surface, vertices))
        self.assertFalse(
            is_q2_side_event(
                (1, 1), surface, vertices, parent_sheers=never, live=None,
            ),
        )

    def test_q2_landing_is_not_side_predicate(self) -> None:
        """SHEER landing against a body is Q2 landing, not a corridor side."""
        z = {
            (1, 1): 8, (2, 1): 6, (1, 0): 7,
        }
        surface = _surface(z)
        vertices = _vertices_for(z)
        vertices.add_vertex({(1, 1): 8})
        always = lambda _a, _b: True
        self.assertTrue(
            is_q2_seed((2, 1), surface, vertices, parent_sheers=always),
        )
        self.assertFalse(is_side_seed((2, 1), surface, vertices))
        self.assertFalse(
            is_q2_side_event(
                (2, 1), surface, vertices, parent_sheers=always, live=None,
            ),
        )

    def test_resolve_side_parent_min_dz_then_smaller_slot(self) -> None:
        z = {
            (0, 1): 8, (1, 1): 3, (2, 1): 5,
            (1, 0): 3,
        }
        surface = _surface(z)
        vertices = _vertices_for(z)
        high = vertices.add_vertex({(0, 1): 8})
        near = vertices.add_vertex({(2, 1): 5})
        vertices.mark_occ((1, 1), near)
        parent = resolve_side_parent((1, 0), surface, vertices)
        self.assertEqual(parent, near)
        self.assertNotEqual(parent, high)

    def test_resolve_side_parent_tie_smaller_slot(self) -> None:
        z = {
            (0, 1): 5, (1, 1): 3, (2, 1): 5,
            (1, 0): 3,
        }
        surface = _surface(z)
        vertices = _vertices_for(z)
        left = vertices.add_vertex({(0, 1): 5})
        right = vertices.add_vertex({(2, 1): 5})
        vertices.mark_occ((0, 0), 0)
        vertices.mark_occ((1, 1), left)
        parent = resolve_side_parent(
            (1, 0),
            surface,
            vertices,
            live=corridor_from_cells({(1, 1), (2, 0)}, {(2, 0): right}),
        )
        self.assertEqual(parent, left)
        self.assertLess(left, right)

    def test_resolve_side_parent_skips_foreign(self) -> None:
        z = {(1, 1): 3, (1, 0): 3}
        surface = _surface(z)
        vertices = _vertices_for(z)
        vertices.mark_foreign((1, 1))
        self.assertIsNone(resolve_side_parent((1, 0), surface, vertices))

    def test_side_predicate_sees_live_slope_corridor_when_occ_delayed(self) -> None:
        """C41 leaves |dz|=1 landings unmarked; Q2 side still reads committed SLOPE."""
        z = {
            (1, 2): 4, (1, 1): 3, (1, 0): 3,
        }
        surface = _surface(z)
        vertices = _vertices_for(z)
        vertices.add_vertex({(1, 2): 4})
        never = lambda _a, _b: False
        live = corridor_from_cells({(1, 1)})
        self.assertFalse(is_side_seed((1, 0), surface, vertices))
        self.assertTrue(is_side_seed((1, 0), surface, vertices, live=live))
        self.assertFalse(is_side_seed((1, 1), surface, vertices, live=live))
        self.assertTrue(
            is_q2_side_event(
                (1, 0), surface, vertices, parent_sheers=never, live=live,
            ),
        )

    def test_slope_corridor_cell_is_occ_or_live_trace(self) -> None:
        z = {(0, 0): 3, (1, 0): 3, (2, 0): 3}
        vertices = _vertices_for(z)
        vertices.mark_occ((0, 0), 1)
        vertices.mark_foreign((2, 0))
        self.assertTrue(is_slope_corridor_cell((0, 0), vertices))
        self.assertFalse(is_slope_corridor_cell((1, 0), vertices))
        self.assertFalse(is_slope_corridor_cell((2, 0), vertices))
        self.assertEqual(vertices.occ[vertices.index(2, 0)], FOREIGN_MARK)
        self.assertTrue(
            is_slope_corridor_cell(
                (1, 0), vertices, live=corridor_from_cells({(1, 0)}),
            ),
        )

    def test_one_by_one_pit_is_not_q2_or_side(self) -> None:
        z = {
            (0, 2): 4, (1, 2): 4, (2, 2): 4,
            (0, 1): 4, (1, 1): 2, (2, 1): 4,
            (0, 0): 4, (1, 0): 4, (2, 0): 4,
        }
        surface = _surface(z)
        vertices = _vertices_for(z)
        ring = {xy: 4 for xy in z if xy != (1, 1)}
        vertices.add_vertex(ring)
        hole = (1, 1)
        self.assertTrue(enclosed_one_cell_pit(hole, surface, vertices))
        never = lambda _a, _b: True
        self.assertFalse(is_q2_seed(hole, surface, vertices, parent_sheers=never))
        self.assertFalse(is_side_seed(hole, surface, vertices))
        vertices, fronts = _discover(z)
        i = vertices.index(*hole)
        self.assertNotEqual(vertices.seam[i], 0)
        self.assertEqual(fronts, ())
        self.assertEqual(vertices.at_grid[i], 0)

    def test_straight_road_two_ortho_fronts(self) -> None:
        """Pavement = one vertex; shoot both shoulders, not along the road."""
        z = {
            (0, 2): 2, (1, 2): 2, (2, 2): 2,
            (0, 1): 4, (1, 1): 4, (2, 1): 4,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        terrain = {(x, y): (_ROAD if y == 1 else _PLAINS) for x, y in z}
        surface = MeterGradeSurface(
            surface_z=z,
            surface_terrain=terrain,
            hydrology=None,
            surface_facing=None,
        )
        vertices, fronts = _run_discover(
            surface,
            origin_x=0,
            origin_y=0,
            width=3,
            height=3,
            plugins=(RoadShoulderPlugin(_ROAD),),
            cell_blocked=lambda _xy: False,
        )
        self.assertEqual(set(vertices.members[0]), {(0, 1), (1, 1), (2, 1)})
        north = [f for f in fronts if f.outward is Facing.NORTH]
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertEqual(len(north), 1)
        self.assertEqual(len(south), 1)
        self.assertEqual(len(north[0].rim), 3)
        self.assertEqual(len(south[0].rim), 3)
        along = [f for f in fronts if f.outward in (Facing.EAST, Facing.WEST)]
        self.assertEqual(along, [])

    def test_road_corner_does_not_double_inner_cell(self) -> None:
        """Inner corner is C41 seam — one cell, not two Instances."""
        z = {
            (0, 2): 2, (1, 2): 4, (2, 2): 4,
            (0, 1): 2, (1, 1): 4, (2, 1): 2,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        pavement = {(1, 2), (2, 2), (1, 1)}
        terrain = {xy: (_ROAD if xy in pavement else _PLAINS) for xy in z}
        surface = MeterGradeSurface(
            surface_z=z,
            surface_terrain=terrain,
            hydrology=None,
            surface_facing=None,
        )
        vertices, fronts = _run_discover(
            surface,
            origin_x=0,
            origin_y=0,
            width=3,
            height=3,
            plugins=(RoadShoulderPlugin(_ROAD),),
            cell_blocked=lambda _xy: False,
        )
        self.assertEqual(set(vertices.members[0]), pavement)
        inner = (2, 1)
        i = vertices.index(*inner)
        self.assertNotEqual(vertices.seam[i], 0)
        self.assertEqual(vertices.occ[i], 0)
        for front in fronts:
            self.assertNotIn(inner, front.corridor)

    def test_ravine_bank_does_not_swallow_mesa(self) -> None:
        """Ravine body is the bank; plateau interior stays open_land (R41-T-4)."""
        z = {
            (0, 3): 4, (1, 3): 4, (2, 3): 4, (3, 3): 4,
            (0, 2): 4, (1, 2): 4, (2, 2): 4, (3, 2): 4,
            (0, 1): 4, (1, 1): 4, (2, 1): 4, (3, 1): 2,
            (0, 0): 2, (1, 0): 2, (2, 0): 2, (3, 0): 2,
        }
        terrain = {xy: _PLAINS for xy in z}
        terrain[(3, 1)] = _RAVINE
        terrain[(2, 0)] = _RAVINE
        terrain[(3, 0)] = _RAVINE
        vertices, fronts = _discover_ravine(z, terrain)
        ravine_slots = {f.slot for f in fronts if f.context is ReliefContext.RAVINE}
        open_slots = {f.slot for f in fronts if f.context is ReliefContext.OPEN_LAND}
        self.assertTrue(ravine_slots)
        self.assertTrue(open_slots)
        interior = (1, 2)
        bank = (2, 1)
        ii = vertices.index(*interior)
        bi = vertices.index(*bank)
        self.assertIn(vertices.at_grid[ii], open_slots)
        self.assertNotIn(vertices.at_grid[ii], ravine_slots)
        self.assertIn(vertices.at_grid[bi], ravine_slots)
        self.assertNotIn(interior, vertices.members[vertices.at_grid[bi] - 1])

    def test_ravine_thick_inner_wall_seeds_after_bank_cap(self) -> None:
        """Mask terrace leftover after L_tpl=1 is a second ravine vertex, not the floor."""
        n = 9
        z: dict[Coord, int] = {}
        terrain: dict[Coord, str] = {}
        for x in range(n):
            for y in range(n):
                d = min(x, y, n - 1 - x, n - 1 - y)
                xy = (x, y)
                if d == 0:
                    z[xy] = 6
                    terrain[xy] = _PLAINS
                elif d == 1:
                    z[xy] = 4
                    terrain[xy] = _RAVINE
                elif d == 2:
                    z[xy] = 3
                    terrain[xy] = _RAVINE
                else:
                    z[xy] = 1
                    terrain[xy] = _RAVINE
        vertices, fronts = _discover_ravine(
            z, terrain, cap_front=lambda _ctx: 1,
        )
        ravine_slots = {f.slot for f in fronts if f.context is ReliefContext.RAVINE}
        self.assertGreaterEqual(len(ravine_slots), 2)
        bank = (0, 4)
        wall = (2, 4)
        floor = (4, 4)
        bi = vertices.index(*bank)
        wi = vertices.index(*wall)
        fi = vertices.index(*floor)
        self.assertIn(vertices.at_grid[bi], ravine_slots)
        self.assertIn(vertices.at_grid[wi], ravine_slots)
        self.assertNotEqual(vertices.at_grid[bi], vertices.at_grid[wi])
        self.assertEqual(vertices.at_grid[fi], 0)
        self.assertNotIn(floor, vertices.members[vertices.at_grid[wi] - 1])

    def test_ravine_floor_without_drop_does_not_seed(self) -> None:
        z: dict[Coord, int] = {}
        terrain: dict[Coord, str] = {}
        for x in range(5):
            for y in range(5):
                xy = (x, y)
                if x == 0 or x == 4 or y == 0 or y == 4:
                    z[xy] = 4
                    terrain[xy] = _PLAINS
                else:
                    z[xy] = 2
                    terrain[xy] = _RAVINE
        vertices, fronts = _discover_ravine(
            z, terrain, cap_front=lambda _ctx: 1,
        )
        floor = (2, 2)
        i = vertices.index(*floor)
        self.assertEqual(vertices.at_grid[i], 0)
        self.assertEqual(vertices.occ[i], 0)
        ravine_slots = {f.slot for f in fronts if f.context is ReliefContext.RAVINE}
        self.assertTrue(ravine_slots)
        for slot in ravine_slots:
            self.assertNotIn(floor, vertices.members[slot - 1])

    def test_ravine_unit_dz_stamps_bank(self) -> None:
        z = {
            (0, 1): 3, (1, 1): 3,
            (0, 0): 2, (1, 0): 2,
        }
        terrain = {(x, y): (_PLAINS if y == 1 else _RAVINE) for x, y in z}
        _vertices, fronts = _discover_ravine(z, terrain)
        south = [f for f in fronts if f.context is ReliefContext.RAVINE]
        self.assertTrue(south)
        covered = {xy for f in south for xy in f.corridor}
        self.assertTrue({(0, 0), (1, 0)} <= covered)

    def test_ravine_equal_z_floor_continues_from_envelope(self) -> None:
        z = {
            (0, 2): 4,
            (0, 1): 2,
            (0, 0): 2,
        }
        terrain = {
            (0, 2): _PLAINS,
            (0, 1): _RAVINE,
            (0, 0): _RAVINE,
        }
        _vertices, fronts = _discover_ravine(z, terrain)
        south = [f for f in fronts if f.context is ReliefContext.RAVINE]
        covered = {xy for f in south for xy in f.corridor}
        self.assertTrue({(0, 1), (0, 0)} <= covered)

    def test_ravine_grades_channel_bed_false_stops_equal_z(self) -> None:
        z = {
            (0, 2): 4,
            (0, 1): 2,
            (0, 0): 2,
        }
        terrain = {
            (0, 2): _PLAINS,
            (0, 1): _RAVINE,
            (0, 0): _RAVINE,
        }
        base = ReliefOntologyEnvelopes.canonical_defaults()
        envelopes = base.model_copy(
            update={
                "ravine": base.ravine.model_copy(
                    update={"grades_channel_bed": False},
                ),
            },
        )
        _vertices, fronts = _discover_ravine(z, terrain, envelopes=envelopes)
        south = [f for f in fronts if f.context is ReliefContext.RAVINE]
        covered = {xy for f in south for xy in f.corridor}
        self.assertIn((0, 1), covered)
        self.assertNotIn((0, 0), covered)

    def test_envelope_cap_does_not_swallow_inner_l(self) -> None:
        """Equal-z stop on open_land: long cap is not an all-seam inner L."""
        z = {}
        for x in range(4):
            for y in range(4):
                z[(x, y)] = 10 if x == 0 or y == 0 else 6
        long_cap, short_cap = _ENVELOPE_L_FLOOR, DEFAULT_SLOPE_LENGTH_CELLS
        _v20, fronts20 = _run_discover(
            _surface(z),
            origin_x=0,
            origin_y=0,
            width=4,
            height=4,
            plugins=(OpenLandPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
            cap_front=lambda _ctx: long_cap,
        )
        _v1, fronts1 = _run_discover(
            _surface(z),
            origin_x=0,
            origin_y=0,
            width=4,
            height=4,
            plugins=(OpenLandPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
            cap_front=lambda _ctx: short_cap,
        )
        for fronts in (fronts20, fronts1):
            outwards = {f.outward for f in fronts}
            self.assertGreaterEqual(len(fronts), 2)
            self.assertIn(Facing.NORTH, outwards)
            self.assertIn(Facing.EAST, outwards)

    def test_occupancy_cap_is_l_tpl_not_envelope_floor(self) -> None:
        from app.application.worldData.pack.refine.detailedGradeHalo import (
            grade_halo_cells,
            length_cap_for_context,
        )
        from app.dataModel.terrain.relief import ReliefTemplate

        tpl = ReliefTemplate.model_validate({
            "system_name": "open_step",
            "display_name": "Open",
            "context": ReliefContext.OPEN_LAND.value,
            "conditions": [{
                "terrain": ReliefConditionTerrain.PLAINS.value,
                "cases": [
                    {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                    {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0},
                ],
            }],
        })
        templates = {"open_step": tpl}
        self.assertEqual(
            length_cap_for_context(ReliefContext.OPEN_LAND, templates),
            DEFAULT_SLOPE_LENGTH_CELLS,
        )
        self.assertGreaterEqual(grade_halo_cells(templates), _ENVELOPE_L_FLOOR)

    def test_open_land_stops_on_basin_floor(self) -> None:
        """Flat floor after the drop is the depression, not this slope's L."""
        z = {
            (0, 3): 6,
            (0, 2): 4,
            (0, 1): 4,
            (0, 0): 4,
        }
        _vertices, fronts = _discover(z)
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertTrue(south)
        front = max(south, key=lambda f: f.path_length)
        self.assertEqual(front.corridor, ((0, 2),))
        self.assertEqual(front.path_length, 1)
        self.assertEqual(front.z_end, 4)

    def test_ravine_equal_z_continues_channel(self) -> None:
        """Ravine channel floor stays L (R41-T-5 for ravine / bed)."""
        z = {
            (0, 3): 6,
            (0, 2): 4,
            (0, 1): 4,
            (0, 0): 4,
        }
        terrain = {
            (0, 3): _PLAINS,
            (0, 2): _RAVINE,
            (0, 1): _RAVINE,
            (0, 0): _RAVINE,
        }
        _vertices, fronts = _discover_ravine(z, terrain)
        ravine = [f for f in fronts if f.context is ReliefContext.RAVINE]
        self.assertTrue(ravine)
        front = max(ravine, key=lambda f: f.path_length)
        self.assertEqual(front.corridor, ((0, 2), (0, 1), (0, 0)))
        self.assertEqual(front.path_length, 3)

    def test_walk_cap_uses_envelope_max_not_literal(self) -> None:
        """R41-T-11: lockstep bound is slope_length_max_cells, not _TRACE_CAP=64."""
        z = {(0, y): 2 + y for y in range(7)}
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains.model_copy(
            update={"slope_length_max_cells": 2},
        )
        envelopes = ReliefOntologyEnvelopes.canonical_defaults().model_copy(
            update={"plains": plains},
        )
        surface = _surface(z)
        _vertices, fronts = _run_discover(
            surface,
            origin_x=0,
            origin_y=0,
            width=1,
            height=7,
            plugins=(OpenLandPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
            envelopes=envelopes,
        )
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertTrue(south)
        self.assertEqual(max(f.path_length for f in south), 2)

    def test_descending_open_land_walks_until_heightmap_or_flat(self) -> None:
        """No envelope max: descending steps keep going; a flat floor still stops."""
        z = {(0, y): 2 + y for y in range(7)}
        _vertices, fronts = _discover(z)
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertTrue(south)
        self.assertEqual(max(f.path_length for f in south), 6)

    def test_unit_dz_policy_is_envelope_not_plugin(self) -> None:
        self.assertFalse(hasattr(OpenLandPlugin, "allows_unit_stamp"))
        self.assertFalse(hasattr(OpenLandPlugin(_LAND), "allows_unit_stamp"))
        from app.application.worldData.generators.terrain.relief.discover.plugins import (
            RavinePlugin,
        )
        self.assertFalse(hasattr(RavinePlugin, "allows_unit_stamp"))
        self.assertFalse(hasattr(ShorePlugin, "allows_unit_stamp"))
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        self.assertEqual(plains.stamp_min_abs_dz, 1)
        self.assertTrue(plains.stamps_first_step(1, ReliefContext.OPEN_LAND))
        self.assertTrue(plains.stamps_first_step(2, ReliefContext.OPEN_LAND))
        self.assertTrue(
            plains.stamps_first_step(1, ReliefContext.ROAD_SHOULDER),
        )

    def test_canonical_plains_stamps_unit_open_land(self) -> None:
        z = {(0, 0): 4, (1, 0): 3}
        _vertices, fronts = _run_discover(
            _surface(z),
            origin_x=0,
            origin_y=0,
            width=2,
            height=1,
            plugins=(OpenLandPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
        )
        east = [f for f in fronts if f.outward is Facing.EAST]
        self.assertTrue(east)
        self.assertIn((1, 0), east[0].corridor)

    def test_forest_stamp_min_still_skips_unit(self) -> None:
        z = {(0, 0): 4, (1, 0): 3}
        forest = {(0, 0): _FOREST, (1, 0): _FOREST}
        surface = MeterGradeSurface(
            surface_z=z,
            surface_terrain=forest,
            hydrology=None,
            surface_facing=None,
        )
        _vertices, fronts = _run_discover(
            surface,
            origin_x=0,
            origin_y=0,
            width=2,
            height=1,
            plugins=(OpenLandPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
        )
        self.assertEqual(fronts, ())

    def test_road_unit_dz_stamps_shoulder(self) -> None:
        z = {
            (0, 1): 3, (1, 1): 3,
            (0, 0): 2, (1, 0): 2,
        }
        terrain = {(x, y): (_ROAD if y == 1 else _PLAINS) for x, y in z}
        surface = MeterGradeSurface(
            surface_z=z,
            surface_terrain=terrain,
            hydrology=None,
            surface_facing=None,
        )
        _vertices, fronts = _run_discover(
            surface,
            origin_x=0,
            origin_y=0,
            width=2,
            height=2,
            plugins=(RoadShoulderPlugin(_ROAD),),
            cell_blocked=lambda _xy: False,
        )
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertTrue(south)
        covered = {xy for f in south for xy in f.corridor}
        self.assertTrue({(0, 0), (1, 0)} <= covered)

    def test_classify_span_is_corridor_after_seam(self) -> None:
        """h / L_ray from unique corridor, not the far cell of the full walk (R41-T-8)."""
        z = {
            (0, 2): 8,
            (1, 2): 6, (2, 2): 2,
            (2, 4): 8,
            (2, 3): 6,
        }
        surface = _surface(z)
        vertices = ReliefVertices.for_bounds(
            origin_x=0, origin_y=2, width=3, height=3,
        )
        fronts = SeamStage(vertices, surface).commit(
            (
                ProposedTrace(
                    slot=1,
                    z_body=8,
                    rim=((0, 2),),
                    facing=Facing.EAST,
                    first_dz=2,
                    trace=((1, 2), (2, 2)),
                    z_end=2,
                ),
                ProposedTrace(
                    slot=1,
                    z_body=8,
                    rim=((2, 4),),
                    facing=Facing.SOUTH,
                    first_dz=2,
                    trace=((2, 3), (2, 2)),
                    z_end=2,
                ),
            ),
            OpenLandPlugin(_LAND),
        )
        self.assertEqual(len(fronts), 2)
        for front in fronts:
            self.assertEqual(front.path_length, 1)
            self.assertEqual(front.z_end, 6)
            self.assertEqual(front.z_body - front.z_end, 2)
            self.assertNotIn((2, 2), front.corridor)

    def test_shore_river_grades_bed_without_inventing_cells(self) -> None:
        """River U15 bands are not cut — bank + river_bed, not painted shore_river."""
        z = {
            (0, 1): 4, (1, 1): 4,
            (0, 0): 2, (1, 0): 2,
        }
        terrain = {xy: _PLAINS for xy in z}
        hydro = {
            (0, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
            (1, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
        }
        vertices, fronts = _discover_shore(z, terrain, hydro)
        south = [f for f in fronts if f.context is ReliefContext.SHORE]
        self.assertTrue(south)
        covered = {xy for f in south for xy in f.corridor}
        self.assertTrue({(0, 0), (1, 0)} <= covered)
        self.assertEqual(terrain[(0, 1)], _PLAINS)
        self.assertEqual(terrain[(0, 0)], _PLAINS)
        self.assertNotEqual(
            shore_condition_at((0, 0), MeterGradeSurface(
                surface_z=z, surface_terrain=terrain, hydrology=hydro,
                surface_facing=None,
            )),
            None,
        )
        self.assertEqual(
            shore_condition_at((0, 0), MeterGradeSurface(
                surface_z=z, surface_terrain=terrain, hydrology=hydro,
                surface_facing=None,
            )),
            ReliefConditionTerrain.SHORE_RIVER,
        )
        bank = (0, 1)
        bi = vertices.index(*bank)
        self.assertNotEqual(vertices.at_grid[bi], 0)

    def test_shore_mountain_river_kind_still_grades_bed(self) -> None:
        z = {(0, 1): 5, (0, 0): 2}
        terrain = {xy: _PLAINS for xy in z}
        hydro = {
            (0, 0): MapCellHydrology(
                role=HydrologyCellRole.RIVER_BED,
                shore_kind=HydrologyShoreKind.MOUNTAIN_RIVER,
            ),
        }
        _vertices, fronts = _discover_shore(z, terrain, hydro)
        south = [f for f in fronts if f.context is ReliefContext.SHORE]
        self.assertTrue(south)
        self.assertIn((0, 0), south[0].corridor)

    def test_shore_equal_z_bed_continues_length(self) -> None:
        z = {(0, 3): 5, (0, 2): 2, (0, 1): 2, (0, 0): 2}
        terrain = {xy: _PLAINS for xy in z}
        hydro = {
            (0, 2): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
            (0, 1): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
            (0, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
        }
        _vertices, fronts = _discover_shore(z, terrain, hydro)
        south = [f for f in fronts if f.context is ReliefContext.SHORE]
        self.assertTrue(south)
        front = max(south, key=lambda f: f.path_length)
        self.assertEqual(front.corridor, ((0, 2), (0, 1), (0, 0)))

    def test_shore_bed_floor_without_drop_does_not_seed(self) -> None:
        z: dict[Coord, int] = {}
        terrain: dict[Coord, str] = {}
        hydro: dict[Coord, MapCellHydrology] = {}
        for x in range(5):
            for y in range(5):
                xy = (x, y)
                if x == 0 or x == 4 or y == 0 or y == 4:
                    z[xy] = 4
                    terrain[xy] = _PLAINS
                else:
                    z[xy] = 2
                    terrain[xy] = _PLAINS
                    hydro[xy] = MapCellHydrology(role=HydrologyCellRole.RIVER_BED)
        vertices, fronts = _discover_shore(
            z, terrain, hydro, cap_front=lambda _ctx: 1,
        )
        floor = (2, 2)
        i = vertices.index(*floor)
        self.assertEqual(vertices.at_grid[i], 0)
        shore_slots = {f.slot for f in fronts if f.context is ReliefContext.SHORE}
        self.assertTrue(shore_slots)
        for slot in shore_slots:
            self.assertNotIn(floor, vertices.members[slot - 1])

    def test_shore_bank_does_not_swallow_mesa(self) -> None:
        z = {
            (0, 3): 4, (1, 3): 4, (2, 3): 4, (3, 3): 4,
            (0, 2): 4, (1, 2): 4, (2, 2): 4, (3, 2): 4,
            (0, 1): 4, (1, 1): 4, (2, 1): 4, (3, 1): 2,
            (0, 0): 2, (1, 0): 2, (2, 0): 2, (3, 0): 2,
        }
        terrain = {xy: _PLAINS for xy in z}
        hydro = {
            (3, 1): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
            (2, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
            (3, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED),
        }
        vertices, fronts = _discover_shore(z, terrain, hydro)
        shore_slots = {f.slot for f in fronts if f.context is ReliefContext.SHORE}
        open_slots = {f.slot for f in fronts if f.context is ReliefContext.OPEN_LAND}
        self.assertTrue(shore_slots)
        self.assertTrue(open_slots)
        interior = (1, 2)
        bank = (2, 1)
        ii = vertices.index(*interior)
        bi = vertices.index(*bank)
        self.assertIn(vertices.at_grid[ii], open_slots)
        self.assertNotIn(vertices.at_grid[ii], shore_slots)
        self.assertIn(vertices.at_grid[bi], shore_slots)
        self.assertNotIn(interior, vertices.members[vertices.at_grid[bi] - 1])

    def test_shore_sea_shoots_strip_not_open_water(self) -> None:
        z = {(0, 2): 6, (0, 1): 4, (0, 0): 1}
        terrain = {
            (0, 2): _PLAINS,
            (0, 1): _SHORE_SEA,
            (0, 0): _PLAINS,
        }
        hydro = {
            (0, 1): MapCellHydrology.shore(HydrologyShoreKind.SEA),
            (0, 0): MapCellHydrology(role=HydrologyCellRole.COASTAL_SEA),
        }
        _vertices, fronts = _discover_shore(z, terrain, hydro)
        south = [f for f in fronts if f.context is ReliefContext.SHORE]
        self.assertTrue(south)
        covered = {xy for f in south for xy in f.corridor}
        self.assertIn((0, 1), covered)
        self.assertNotIn((0, 0), covered)

    def test_shore_lake_grades_open_water(self) -> None:
        z = {(0, 1): 4, (0, 0): 2}
        terrain = {xy: _PLAINS for xy in z}
        hydro = {(0, 0): MapCellHydrology(role=HydrologyCellRole.LAKE)}
        _vertices, fronts = _discover_shore(z, terrain, hydro)
        south = [f for f in fronts if f.context is ReliefContext.SHORE]
        self.assertTrue(south)
        self.assertIn((0, 0), south[0].corridor)

    def test_shore_flat_without_drop_does_not_seed(self) -> None:
        z = {(0, 1): 3, (0, 0): 3}
        terrain = {(0, 1): _PLAINS, (0, 0): _SHORE_SEA}
        hydro = {(0, 0): MapCellHydrology.shore(HydrologyShoreKind.SEA)}
        vertices, fronts = _discover_shore(z, terrain, hydro)
        shore_fronts = [f for f in fronts if f.context is ReliefContext.SHORE]
        self.assertFalse(shore_fronts)
        for xy in z:
            i = vertices.index(*xy)
            self.assertEqual(vertices.at_grid[i], 0)

    def test_grades_channel_bed_false_does_not_enter_bed(self) -> None:
        z = {(0, 1): 4, (0, 0): 2}
        terrain = {xy: _PLAINS for xy in z}
        hydro = {(0, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED)}
        base = ReliefOntologyEnvelopes.canonical_defaults()
        envelopes = base.model_copy(
            update={
                "shore_river": base.shore_river.model_copy(
                    update={"grades_channel_bed": False},
                ),
            },
        )
        _vertices, fronts = _discover_shore(z, terrain, hydro, envelopes=envelopes)
        covered = {xy for f in fronts if f.context is ReliefContext.SHORE for xy in f.corridor}
        self.assertNotIn((0, 0), covered)

    def test_sea_terrace_min_reads_envelope_not_literal(self) -> None:
        def _terrace(width: int, min_cells: int | None = None):
            z: dict[Coord, int] = {}
            terrain: dict[Coord, str] = {}
            hydro: dict[Coord, MapCellHydrology] = {}
            for x in range(width):
                z[(x, 3)] = 8
                terrain[(x, 3)] = _PLAINS
                z[(x, 2)] = 5
                terrain[(x, 2)] = _SHORE_SEA
                hydro[(x, 2)] = MapCellHydrology.shore(HydrologyShoreKind.SEA)
                z[(x, 1)] = 3
                terrain[(x, 1)] = _SHORE_SEA
                hydro[(x, 1)] = MapCellHydrology.shore(HydrologyShoreKind.SEA)
                z[(x, 0)] = 0
                terrain[(x, 0)] = _PLAINS
                hydro[(x, 0)] = MapCellHydrology(role=HydrologyCellRole.COASTAL_SEA)
            envelopes = None
            if min_cells is not None:
                base = ReliefOntologyEnvelopes.canonical_defaults()
                envelopes = base.model_copy(
                    update={
                        "shore_sea": base.shore_sea.model_copy(
                            update={"sheer_terrace_min_cells": min_cells},
                        ),
                    },
                )
            return _discover_shore(
                z, terrain, hydro,
                cap_front=lambda _ctx: 1,
                envelopes=envelopes,
            )

        # Bank |dz|=3 is skip (not slope/sheer), so the first terrace y=2 is leftover C39.
        vertices5, _ = _terrace(5)
        leftover = (2, 2)
        self.assertNotEqual(vertices5.at_grid[vertices5.index(*leftover)], 0)
        vertices3, _ = _terrace(3)
        self.assertEqual(vertices3.at_grid[vertices3.index(1, 2)], 0)
        vertices3_ok, _ = _terrace(3, min_cells=3)
        self.assertNotEqual(vertices3_ok.at_grid[vertices3_ok.index(1, 2)], 0)

    def test_shore_unit_dz_stamps_from_envelope(self) -> None:
        z = {(0, 1): 3, (0, 0): 2}
        terrain = {xy: _PLAINS for xy in z}
        hydro = {(0, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED)}
        _vertices, fronts = _discover_shore(z, terrain, hydro)
        south = [f for f in fronts if f.context is ReliefContext.SHORE]
        self.assertTrue(south)
        self.assertIn((0, 0), south[0].corridor)

    def test_plugins_for_keys_registers_shore_body(self) -> None:
        plugins = plugins_for_keys(
            land_keys=_LAND,
            road_key=_ROAD,
            ravine_key=_RAVINE,
            contexts=frozenset({ReliefContext.SHORE}),
        )
        self.assertEqual(len(plugins), 1)
        self.assertIsInstance(plugins[0], ShorePlugin)
        z = {(0, 1): 4, (0, 0): 2}
        terrain = {xy: _PLAINS for xy in z}
        hydro = {(0, 0): MapCellHydrology(role=HydrologyCellRole.RIVER_BED)}
        surface = MeterGradeSurface(
            surface_z=z, surface_terrain=terrain, hydrology=hydro,
            surface_facing=None,
        )
        self.assertTrue(plugins[0].claims((0, 1), surface))
        self.assertTrue(plugins[0].may_shoot((0, 1), (0, 0), surface))


class MillBucketsTest(unittest.TestCase):
    def test_insert_rejects_second_bucket(self) -> None:
        buckets = MillBuckets()
        leftover = BucketRef.leftover(4)
        self.assertTrue(buckets.insert(leftover, (0, 0)))
        self.assertFalse(
            buckets.insert(BucketRef.q2(4, 1), (0, 0), kind=Q2Kind.LANDING),
        )
        self.assertEqual(buckets.cell_to_bucket[(0, 0)], leftover)
        self.assertEqual(leftover.slot, UNSET_SLOT)

    def test_leftover_walk_is_on_rim_not_buckets(self) -> None:
        z = {(0, 0): 4, (1, 0): 3, (0, 1): 4}
        surface = _surface(z)
        vertices = _vertices_for(z)
        buckets = MillBuckets()
        cells = list(iter_rect_z_cells(surface, vertices))
        for xy, height in cells:
            self.assertTrue(buckets.insert(BucketRef.leftover(height), xy))
        for xy, height in cells:
            self.assertFalse(buckets.insert(BucketRef.leftover(height), xy))
        self.assertEqual(set(buckets.leftover_z(4)), {(0, 0), (0, 1)})
        self.assertEqual(set(buckets.leftover_z(3)), {(1, 0)})
        self.assertEqual(buckets.max_leftover_z(), 4)
        self.assertTrue(buckets.move(BucketRef.claimed(4, 1), (0, 0)))
        self.assertFalse(buckets.is_leftover((0, 0), 4))
        self.assertEqual(buckets.max_leftover_z(), 4)
        buckets.drop_leftover_z(4)
        self.assertEqual(buckets.max_leftover_z(), 3)


class GradePipelineTimingsTest(unittest.TestCase):
    def test_q_total_and_log_fields(self) -> None:
        from app.application.worldData.generators.terrain.relief.discover.timings import (
            GradePipelineTimings,
        )

        mill = GradePipelineTimings(q1_s=1.0, q2_s=2.0, mill_s=7.0)
        self.assertEqual(mill.q_total_s, 3.0)
        self.assertFalse(hasattr(mill, "q3_s"))
        self.assertFalse(hasattr(GradePipelineTimings, "from_mill"))
        summed = mill.added(GradePipelineTimings(q1_s=0.5, paint_s=1.25))
        self.assertEqual(summed.q1_s, 1.5)
        self.assertEqual(summed.q_total_s, 3.5)
        self.assertEqual(summed.paint_s, 1.25)
        payload = summed.as_dict()
        self.assertEqual(payload["q_total_s"], 3.5)
        self.assertNotIn("q3_s", payload)
        fields = summed.mill_log_fields()
        self.assertNotIn("grade_s", fields)
        self.assertNotIn("materialize_s", fields)
        self.assertIn("q1_s", fields)
        self.assertIn("paint_s", fields)
        self.assertNotIn("q3_s", fields)
        self.assertIn("q_total_s", GradePipelineTimings.wire_keys())


class ReliefDiscoverPolishTest(unittest.TestCase):
    def test_fronts_has_no_pick_and_no_trace_cap_literal(self) -> None:
        import inspect

        from app.application.worldData.generators.terrain.relief.discover import (
            fronts as fronts_mod,
        )

        src = inspect.getsource(fronts_mod)
        self.assertNotIn("pick_template", src)
        self.assertNotIn("templatePick", src)
        self.assertNotIn("_TRACE_CAP", src)
        self.assertIn("slope_walk_cap_cells", src)


if __name__ == "__main__":
    unittest.main()
