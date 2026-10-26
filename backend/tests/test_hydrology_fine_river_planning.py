"""Review-debt step 4: resolved water before fine planning and explicit writer output."""

import json
import unittest
from unittest.mock import patch

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.coordinates.space import CoordinateSpace as Space
from app.application.worldData.generators.hydrology.shore import fineHydrologyIndex as module
from app.application.worldData.generators.terrain.reliefObjects.riverBed import apply_river_bed_z
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, DeclaredRiverSegment, HydrologyMouth
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint as Point
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.fineTopology import fine_topology
from tests.hydrology_fixtures import flat_heightmap, heightmap_from_z, hydro_topology, hydro_world, named_location


def river(uid, start, end):
    return DeclaredRiver(location_uid=uid, declare_mode="segments", segments=[DeclaredRiverSegment(
        from_wp=Point(x=start[0], y=start[1]), to_wp=Point(x=end[0], y=end[1]), connection_type="river")])


def world(rivers, *, span=1, **policy):
    return hydro_world(fine_cells_per_map_cell=span, z_min=-20, hydrology=WorldHydrology(
        declared_rivers=rivers, default_rivers=HydrologyRiversPolicy(autoresolve=False, **policy)
    ).model_dump(mode="json"))


def water(uid):
    return MapCellHydrology(role=Role.LAKE, water_body_uid=uid, z_water_level=0)


class FineRiverPlanningTests(unittest.TestCase):
    def test_fine_intent_sees_water_before_mouth_snap(self):
        w = world([DeclaredRiver(location_uid="r", declare_mode="endpoints",
            source=Point(x=0, y=0), mouth=HydrologyMouth(x=3, y=0))], span=7)
        base = {(x, 0): 20 for x in range(7)}
        base[(5, 0)] = -2
        original = dict(base)
        ctx = ResolveContext(validate_only=True)
        roles, z = module.apply_declared_fine_river_carves(w, [], base, fine_hydro={(5, 0): water("lake")},
            topology=hydro_topology(heightmap_from_z(base)), ctx=ctx)
        self.assertFalse(ctx.errors)
        self.assertEqual(set(roles), {(x, 0) for x in range(5)})
        self.assertEqual(z[(4, 0)], 17)
        self.assertEqual(z[(5, 0)], -2)
        self.assertEqual(base, original)

    def test_coarse_snap_resamples_and_classifies_real_terrain(self):
        w = world([DeclaredRiver(location_uid="r", declare_mode="endpoints",
            source=Point(x=0, y=0), mouth=HydrologyMouth(x=5, y=0))], span=3)
        base = {(0, 0): 60, (1, 0): 20, (2, 0): -2}
        ctx = ResolveContext(validate_only=True)
        roles, z = module.apply_declared_fine_river_carves(w, [], base,
            topology=fine_topology(hydro_topology(heightmap_from_z(base)), 3),
            base_space=Space.WORLD_SURFACE_GRID, coarse_hydro={(2, 0): water("lake")}, ctx=ctx)
        self.assertFalse(ctx.errors)
        self.assertEqual(set(roles), {(x, 0) for x in range(6)})
        self.assertEqual(z[(0, 0)], 56)  # source terrain selects mountain depth round(3*1.5)
        self.assertEqual(z[(5, 0)], 16)
        self.assertEqual(z[(6, 0)], -2)
        self.assertNotIn((0, 1), z)  # search samples are not overrides

    def test_writer_replacing_its_dict_is_returned_in_both_spaces(self):
        for space in (Space.WORLD_FINE_GRID, Space.WORLD_SURFACE_GRID):
            with self.subTest(space=space):
                w = world([river("r", (0, 0), (3, 0))])
                base = {(x, 0): 20 for x in range(4)}
                base[(3, 0)] = -2
                written = []

                def writer(hm, specs):
                    object.__setattr__(hm, "surface_z", dict(hm.surface_z))
                    apply_river_bed_z(hm, specs)
                    written.append(hm.surface_z)

                kw = {"fine_hydro" if space is Space.WORLD_FINE_GRID else "coarse_hydro": {(3, 0): water("lake")}}
                with patch.object(module, "apply_river_bed_z", side_effect=writer) as apply:
                    _, z = module.apply_declared_fine_river_carves(w, [], base,
                        topology=hydro_topology(heightmap_from_z(base)), base_space=space, **kw)
                self.assertIs(z, written[0])
                self.assertEqual(z[(1, 0)], 17)
                self.assertEqual(base[(1, 0)], 20)
                apply.assert_called_once()

    def test_runtime_fallback_uses_fine_diagnostic_coordinates_for_coarse_input(self):
        for space, span in ((Space.WORLD_FINE_GRID, 1), (Space.WORLD_SURFACE_GRID, 3)):
            with self.subTest(space=space):
                hm = flat_heightmap(0, 6, 0, 4, z=50)
                hm.surface_z.update({(1, 3): 20, (1, 2): 10, (1, 1): -2, (5, 3): -2})
                source, target = (span, 3 * span), (5 * span, 3 * span)
                w = world([DeclaredRiver(location_uid="redirect", declare_mode="endpoints",
                    source=Point(x=source[0], y=source[1]), mouth=HydrologyMouth(location_uid="authored"))], span=span)
                index = {(1, 1): water("alternate"), (5, 3): water("authored")}
                kw = {"fine_hydro" if space is Space.WORLD_FINE_GRID else "coarse_hydro": index}
                with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logged:
                    roles, z = module.apply_declared_fine_river_carves(w, [named_location("authored", *target)],
                        hm.surface_z, base_space=space, topology=fine_topology(hydro_topology(hm), span), **kw)
                diagnostic = json.loads(logged.records[0].getMessage().rsplit(" | ", 1)[1])
                self.assertEqual(diagnostic["code"], "RIVER_REDIRECTED")
                self.assertEqual(diagnostic["receiver_uid"], "alternate")
                self.assertEqual(diagnostic["source_cell"], list(source))
                self.assertEqual(diagnostic["object_uid"], "redirect")
                self.assertTrue(roles)
                self.assertTrue(all(entry.water_body_uid == "redirect" for entry in roles.values()))
                self.assertNotIn(tuple(diagnostic["receiver_cell"]), roles)
                self.assertEqual(z[tuple(diagnostic["receiver_cell"])], -2)

    def test_preview_and_import_do_not_redirect_or_mutate_inputs(self):
        for ctx in (ResolveContext(validate_only=True), ResolveContext.for_import()):
            hm = flat_heightmap(0, 6, 0, 4, z=50)
            hm.surface_z.update({(1, 3): 20, (1, 2): 10, (1, 1): -2, (5, 3): -2})
            original = dict(hm.surface_z)
            roles, z = module.apply_declared_fine_river_carves(world([river("r", (1, 3), (5, 3))]), [],
                hm.surface_z, topology=hydro_topology(hm), fine_hydro={(1, 1): water("alt"), (5, 3): water("target")}, ctx=ctx)
            self.assertEqual(roles, {})
            self.assertEqual(ctx.errors[0].code, "RIVER_TARGET_UNREACHABLE")
            self.assertEqual((z, hm.surface_z), (original, original))

    def test_dry_route_is_explicit_and_has_no_partial_bed(self):
        hm = flat_heightmap(0, 4, 0, 0, z=10)
        ctx = ResolveContext(validate_only=True)
        roles, z = module.apply_declared_fine_river_carves(world([river("dry", (0, 0), (4, 0))]), [],
            hm.surface_z, topology=hydro_topology(hm), ctx=ctx)
        self.assertEqual(roles, {})
        self.assertEqual(z, hm.surface_z)
        self.assertEqual(ctx.errors[0].code, "RIVER_NO_WATER_BODIES")

    def test_coarse_refinement_does_not_block_itself(self):
        w = world([river("r", (0, 0), (5, 0))], span=2)
        base = {(0, 0): 20, (1, 0): 10, (2, 0): -2}
        index = {(0, 0): MapCellHydrology(role=Role.RIVER_BED, water_body_uid="r"), (2, 0): water("lake")}
        original = dict(index)
        roles, z = module.apply_declared_fine_river_carves(w, [], base,
            topology=fine_topology(hydro_topology(heightmap_from_z(base)), 2),
            base_space=Space.WORLD_SURFACE_GRID, coarse_hydro=index)
        self.assertEqual(set(roles), {(x, 0) for x in range(4)})
        self.assertEqual(z[(0, 0)], 17)
        self.assertEqual(index, original)

    def test_failed_object_does_not_prevent_independent_river(self):
        hm = flat_heightmap(0, 6, 0, 2, z=20)
        hm.surface_z[(6, 2)] = -2
        w = world([river("invalid", (-1, 0), (6, 2)), river("valid", (0, 2), (6, 2))])
        ctx = ResolveContext(validate_only=True)
        roles, _ = module.apply_declared_fine_river_carves(w, [], hm.surface_z,
            topology=hydro_topology(hm), fine_hydro={(6, 2): water("lake")}, ctx=ctx)
        self.assertEqual({entry.water_body_uid for entry in roles.values()}, {"valid"})
        self.assertEqual(ctx.errors[0].code, "RIVER_INVALID_SOURCE")

    def test_wrapped_fallback_uses_sampled_seam(self):
        hm = flat_heightmap(0, 7, 0, 2, z=50)
        hm.surface_z.update({(6, 1): 20, (7, 1): 10, (0, 1): -2})
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING"):
            roles, z = module.apply_declared_fine_river_carves(world([river("wrap", (6, 1), (4, 1))]), [],
                hm.surface_z, topology=hydro_topology(hm, Mode.WRAPPED), fine_hydro={(0, 1): water("lake")})
        self.assertEqual(set(roles), {(6, 1), (7, 1)})
        self.assertEqual(z[(0, 1)], -2)

    def test_sparse_coarse_input_does_not_export_the_search_window(self):
        w = world([river("long", (0, 0), (1000, 0))], span=1000,
                  mouth_search_radius_fine=5, max_path_cells=8)
        base = {(0, 0): 20, (1, 0): -2}
        roles, z = module.apply_declared_fine_river_carves(w, [], base,
            topology=fine_topology(hydro_topology(heightmap_from_z(base)), 1000),
            base_space=Space.WORLD_SURFACE_GRID, coarse_hydro={(1, 0): water("far")},
            ctx=ResolveContext(validate_only=True))
        self.assertEqual(roles, {})
        self.assertEqual(len(z), 1001)
        self.assertTrue(all(y == 0 for _, y in z))

    def test_coarse_sampling_fallback_crosses_wrapped_seam_and_sphere_pole(self):
        cases = (
            (Mode.WRAPPED, (12, 2), (8, 2), {(6, 1): 20, (7, 1): 10, (0, 1): -2}, (0, 1)),
            (Mode.SPHERE, (2, 0), (4, 4), {(1, 0): 20, (5, 0): 10, (5, 1): -2}, (5, 1)),
        )
        for mode, source, target, floors, receiver in cases:
            with self.subTest(mode=mode):
                hm = flat_heightmap(0, 7, 0, 3, z=50)
                hm.surface_z.update(floors)
                w = world([river("seam", source, target)], span=2,
                          max_path_cells=12, mouth_search_radius_fine=0)
                with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logs:
                    roles, z = module.apply_declared_fine_river_carves(w, [], hm.surface_z,
                        topology=fine_topology(hydro_topology(hm, mode), 2), base_space=Space.WORLD_SURFACE_GRID,
                        coarse_hydro={receiver: water("lake")})
                diagnostic = json.loads(logs.records[0].getMessage().rsplit(" | ", 1)[1])
                self.assertEqual(diagnostic["code"], "RIVER_REDIRECTED")
                self.assertEqual(diagnostic["receiver_uid"], "lake")
                self.assertEqual(z[tuple(diagnostic["receiver_cell"])], -2)
                self.assertIn(source, roles)

    def test_water_outside_search_window_is_known_but_unreachable(self):
        w = world([river("far", (0, 0), (10, 0))], span=1000,
                  mouth_search_radius_fine=0, max_path_cells=8)
        base = {(0, 0): 10, (1, 0): 50, (2, 0): -2}
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logs:
            roles, _ = module.apply_declared_fine_river_carves(w, [], base,
                topology=fine_topology(hydro_topology(heightmap_from_z(base)), 1000),
                base_space=Space.WORLD_SURFACE_GRID, coarse_hydro={(2, 0): water("far-lake")})
        diagnostic = json.loads(logs.records[0].getMessage().rsplit(" | ", 1)[1])
        self.assertEqual(diagnostic["code"], "RIVER_NO_REACHABLE_WATER")
        self.assertEqual(roles, {})


if __name__ == "__main__":
    unittest.main()
