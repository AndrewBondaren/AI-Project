"""Relief pipeline v2 discover — C39 / C41 / R42 unit geometry."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.terrain.relief.discover.core import (
    discover_fronts,
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


def _surface(z: dict[Coord, int], terrain: str = _PLAINS) -> MeterGradeSurface:
    return MeterGradeSurface(
        surface_z=z,
        surface_terrain={xy: terrain for xy in z},
        hydrology=None,
        surface_facing=None,
    )


def _discover(z: dict[Coord, int]) -> tuple[ReliefVertices, tuple]:
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


def _discover_ravine(
    z: dict[Coord, int],
    terrain: dict[Coord, str],
    *,
    cap_front=None,
) -> tuple[ReliefVertices, tuple]:
    xs = [x for x, _y in z]
    ys = [y for _x, y in z]
    surface = MeterGradeSurface(
        surface_z=z,
        surface_terrain=terrain,
        hydrology=None,
        surface_facing=None,
    )
    return discover_fronts(
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
    )


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
    return discover_fronts(
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
    )


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

    def test_bowl_seam_not_first_come(self) -> None:
        z = {}
        for x in range(5):
            for y in range(5):
                interior = 1 <= x <= 3 and 1 <= y <= 3
                z[(x, y)] = 2 if interior else 4
        vertices, fronts = _discover(z)
        center = (2, 2)
        i = vertices.index(*center)
        self.assertIsNotNone(i)
        self.assertNotEqual(vertices.seam[i], 0)
        self.assertEqual(vertices.occ[i], 0)
        for front in fronts:
            self.assertNotIn(center, front.corridor)

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

    def test_unit_dz_plains_does_not_stamp_occ(self) -> None:
        z = {(0, 0): 4, (1, 0): 3, (2, 0): 2}
        vertices, fronts = _discover(z)
        self.assertEqual(fronts, ())
        for xy in z:
            i = vertices.index(*xy)
            self.assertEqual(vertices.occ[i], 0)
            self.assertEqual(vertices.seam[i], 0)

    def test_lower_terrace_does_not_seed_under_occ(self) -> None:
        z = {
            (0, 2): 6, (1, 2): 6, (2, 2): 6,
            (0, 1): 4, (1, 1): 4, (2, 1): 4,
            (0, 0): 2, (1, 0): 2, (2, 0): 2,
        }
        vertices, fronts = _discover(z)
        south = [f for f in fronts if f.outward is Facing.SOUTH]
        self.assertTrue(south)
        covered = {xy for f in south for xy in f.corridor}
        self.assertTrue(covered)
        terrace = {(0, 1), (1, 1), (2, 1)}
        self.assertTrue(terrace & covered)
        for xy in terrace & covered:
            i = vertices.index(*xy)
            self.assertNotEqual(vertices.occ[i], 0)
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
        vertices, fronts = discover_fronts(
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
        vertices, fronts = discover_fronts(
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

    def test_envelope_sized_cap_seams_l_corner(self) -> None:
        """Occupancy cap is L_tpl; envelope floor as k makes the inner L all-seam."""
        z = {}
        for x in range(4):
            for y in range(4):
                z[(x, y)] = 10 if x == 0 or y == 0 else 6
        long_cap, short_cap = _ENVELOPE_L_FLOOR, DEFAULT_SLOPE_LENGTH_CELLS
        _v20, fronts20 = discover_fronts(
            _surface(z),
            origin_x=0,
            origin_y=0,
            width=4,
            height=4,
            plugins=(OpenLandPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
            cap_front=lambda _ctx: long_cap,
        )
        _v1, fronts1 = discover_fronts(
            _surface(z),
            origin_x=0,
            origin_y=0,
            width=4,
            height=4,
            plugins=(OpenLandPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
            cap_front=lambda _ctx: short_cap,
        )
        self.assertEqual(fronts20, ())
        outwards = {f.outward for f in fronts1}
        self.assertGreaterEqual(len(fronts1), 2)
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

    def test_equal_z_continues_ray_length(self) -> None:
        """Flat floor after the drop is L, not a stop (R41-T-5)."""
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
        self.assertEqual(front.corridor, ((0, 2), (0, 1), (0, 0)))
        self.assertEqual(front.path_length, 3)
        self.assertEqual(front.z_end, 4)

    def test_unit_dz_policy_is_envelope_not_plugin(self) -> None:
        self.assertFalse(hasattr(OpenLandPlugin, "allows_unit_stamp"))
        self.assertFalse(hasattr(OpenLandPlugin(_LAND), "allows_unit_stamp"))
        from app.application.worldData.generators.terrain.relief.discover.plugins import (
            RavinePlugin,
        )
        self.assertFalse(hasattr(RavinePlugin, "allows_unit_stamp"))
        self.assertFalse(hasattr(ShorePlugin, "allows_unit_stamp"))
        plains = ReliefOntologyEnvelopes.canonical_defaults().plains
        self.assertEqual(plains.stamp_min_abs_dz, 2)
        self.assertFalse(plains.stamps_first_step(1, ReliefContext.OPEN_LAND))
        self.assertTrue(plains.stamps_first_step(2, ReliefContext.OPEN_LAND))
        self.assertTrue(
            plains.stamps_first_step(1, ReliefContext.ROAD_SHOULDER),
        )

    def test_envelope_stamp_min_one_allows_unit_open_land(self) -> None:
        """Override proves skip is POJO policy; canonical plains stays 2."""
        z = {(0, 0): 4, (1, 0): 3}
        base = ReliefOntologyEnvelopes.canonical_defaults()
        envelopes = base.model_copy(
            update={"plains": base.plains.model_copy(update={"stamp_min_abs_dz": 1})},
        )
        xs = [x for x, _y in z]
        ys = [y for _x, y in z]
        _vertices, fronts = discover_fronts(
            _surface(z),
            origin_x=min(xs),
            origin_y=min(ys),
            width=max(xs) - min(xs) + 1,
            height=max(ys) - min(ys) + 1,
            plugins=(OpenLandPlugin(_LAND),),
            cell_blocked=lambda _xy: False,
            envelopes=envelopes,
        )
        east = [f for f in fronts if f.outward is Facing.EAST]
        self.assertTrue(east)
        self.assertIn((1, 0), east[0].corridor)

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
        _vertices, fronts = discover_fronts(
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

        vertices5, _ = _terrace(5)
        leftover = (2, 1)
        self.assertNotEqual(vertices5.at_grid[vertices5.index(*leftover)], 0)
        vertices3, _ = _terrace(3)
        self.assertEqual(vertices3.at_grid[vertices3.index(1, 1)], 0)
        vertices3_ok, _ = _terrace(3, min_cells=3)
        self.assertNotEqual(vertices3_ok.at_grid[vertices3_ok.index(1, 1)], 0)

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


if __name__ == "__main__":
    unittest.main()
