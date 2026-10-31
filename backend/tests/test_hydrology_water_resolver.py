"""HY-12/4 physical spill, inheritance, final extent and bootstrap identity."""

import unittest

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import BasinSpec
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.waterSystemKind import WaterSystemKind
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.ids.waterSystemIdentity import water_system_uid
from tests.hydrology_fixtures import flat_heightmap, hydro_topology


def spec(uid, cells, level, *, kind=BasinKind.LAKE):
    return BasinSpec(uid, kind, "water", frozenset(cells), level, -10,
                     HydrologyBands(min=1, max=2))


def row_map(row):
    hm = flat_heightmap(0, len(row) - 1, 0, 2, z=99)
    hm.surface_z.update({(x, 1): z for x, z in enumerate(row)})
    return hm


def assemble(hm, specs, *, mode=WorldTopologyMode.PLANAR, change="change-a", auto=False,
             policy=None):
    return assemble_water_bodies(hm, specs, hydro_topology(hm, mode), policy or WorldHydrology(),
                                  change_uid=change, auto_seas=auto, auto_lakes=auto,
                                  ctx=ResolveContext(validate_only=True))


class WaterResolverTests(unittest.TestCase):
    def test_merge_recomputes_outer_spill_and_materializes_lower_level(self):
        hm = row_map([99, 0, 0, 2, 0, 0, 8, -2, 99])
        hm.surface_z[(2, 0)] = 10  # would be wet at requested 20, dry at final 8
        a, b = spec("A", [(1, 1), (2, 1)], 20), spec("B", [(4, 1), (5, 1)], 5)
        before = dict(hm.surface_z)
        result = assemble(hm, [a, b])
        bodies = {body.water_body_uid: body for body in result.materialized.bodies}
        self.assertEqual(set(bodies), {"A", "B"})
        self.assertEqual({body.z_water_level for body in bodies.values()}, {8})
        self.assertEqual(len(result.physical_unions), 1)
        union = result.physical_unions[0]
        self.assertEqual(union.member_uids, ("A", "B"))
        self.assertTrue(all(body.parent_system_uid == union.water_system_uid for body in bodies.values()))
        cells = dict(result.materialized.cells)
        self.assertEqual(cells[(6, 1)].role, HydrologyCellRole.SHORE)
        self.assertFalse(cells[(6, 1)].liquid_candidate)
        self.assertNotIn((7, 1), cells)  # lower outside region across the dry spillway
        self.assertFalse(cells[(2, 0)].liquid_candidate)
        self.assertEqual(hm.surface_z, before)

    def test_nested_union_cascades_to_all_children_and_keeps_uids(self):
        hm = row_map([99, 0, 0, 2, 0, 0, 4, 0, 0, 8, -2, 99])
        specs = [spec("A", [(1, 1)], 20), spec("B", [(4, 1)], 5), spec("C", [(7, 1)], 6)]
        result = assemble(hm, specs)
        self.assertEqual({body.water_body_uid for body in result.materialized.bodies}, {"A", "B", "C"})
        self.assertEqual(len(result.physical_unions), 2)
        first, second = result.physical_unions
        self.assertEqual(first.parent_system_uid, second.water_system_uid)
        self.assertEqual({body.z_water_level for body in result.materialized.bodies}, {8})
        self.assertEqual({union.z_water_level for union in result.physical_unions}, {8})
        self.assertEqual(first.member_uids, ("A", "B"))
        self.assertEqual(second.member_uids, ("A", "B", "C"))

    def test_dead_end_bench_does_not_cap_level(self):
        hm = row_map([99, 0, 0, 3, 4, 99])
        result = assemble(hm, [spec("lake", [(1, 1)], 5)])
        self.assertEqual(result.materialized.bodies[0].z_water_level, 5)
        self.assertTrue(dict(result.materialized.cells)[(4, 1)].liquid_candidate)

    def test_flat_sill_processed_atomically(self):
        hm = row_map([99, 0, 0, 3, 3, 3, -2, 99])
        result = assemble(hm, [spec("lake", [(1, 1)], 10)])
        self.assertEqual(result.materialized.bodies[0].z_water_level, 3)
        self.assertEqual(dict(result.materialized.cells)[(3, 1)].role, HydrologyCellRole.SHORE)
        self.assertNotIn((6, 1), dict(result.materialized.cells))

    def test_dry_sill_at_equal_level_does_not_merge(self):
        hm = row_map([99, 0, 0, 5, 0, 0, 99])
        result = assemble(hm, [spec("A", [(1, 1)], 5), spec("B", [(4, 1)], 5)])
        self.assertEqual(result.physical_unions, ())
        self.assertEqual(len(result.materialized.bodies), 2)

    def test_planar_ocean_edge_holds_default_but_lake_drains(self):
        hm = row_map([-10, -10, -10, 99])
        ocean = assemble(hm, [spec("ocean", [(1, 1)], 0, kind=BasinKind.OCEAN)])
        self.assertEqual(ocean.materialized.bodies[0].z_water_level, 0)
        self.assertTrue(dict(ocean.materialized.cells)[(0, 1)].liquid_candidate)
        lake = assemble(hm, [spec("lake", [(1, 1)], 0)])
        self.assertEqual(lake.materialized.bodies, ())

    def test_puddle_does_not_create_body_or_water_roles(self):
        hm = row_map([99, 0, 99])
        result = assemble(hm, [spec("tiny", [(1, 1)], 5)])
        self.assertEqual(result.materialized.bodies, ())
        self.assertEqual(dict(result.materialized.cells), {})

    def test_natural_only_high_flat_world_does_not_synthesize_ocean(self):
        hm = flat_heightmap(0, 5, 0, 3, z=10)
        self.assertEqual(dict(assemble(hm, [], auto=True).materialized.cells), {})

    def test_natural_water_seam_has_one_positional_body(self):
        hm = flat_heightmap(0, 5, 0, 3, z=10)
        hm.surface_z.update({(0, 1): -2, (5, 1): -1, (0, 2): -3})
        result = assemble(hm, [], mode=WorldTopologyMode.WRAPPED, auto=True)
        self.assertEqual(len(result.materialized.bodies), 1)
        self.assertEqual(result.materialized.bodies[0].kind, BasinKind.OCEAN)
        self.assertEqual(result.physical_unions, ())

    def test_retry_permutation_and_refill_operation_identity(self):
        hm = row_map([99, 0, 0, 2, 0, 0, 99])
        specs = [spec("A", [(1, 1)], 5), spec("B", [(4, 1)], 5)]
        first = assemble(hm, specs)
        retry = assemble(hm, list(reversed(specs)))
        self.assertEqual(first, retry)
        before = dict(hm.surface_z)
        hm.surface_z.update({cell: 5 for cell in hm.surface_z})
        self.assertEqual(assemble(hm, specs, change="drought").materialized.bodies, ())
        hm.surface_z.update(before)
        restored = assemble(hm, specs, change="refill")
        self.assertEqual({body.water_body_uid for body in first.materialized.bodies},
                          {body.water_body_uid for body in restored.materialized.bodies})
        self.assertNotEqual(first.physical_unions[0].water_system_uid,
                             restored.physical_unions[0].water_system_uid)

    def test_system_kind_is_part_of_shared_identity(self):
        physical = water_system_uid("world", "change", ["A", "B"], WaterSystemKind.PHYSICAL_MERGE)
        self.assertEqual(physical, water_system_uid("world", "change", ["B", "A"],
                                                   WaterSystemKind.PHYSICAL_MERGE))
        self.assertNotEqual(physical, water_system_uid("world", "change", ["A", "B"],
                                                      WaterSystemKind.CONNECTED))

    def test_coincident_declares_keep_both_identities(self):
        hm = row_map([99, 0, 0, 99])
        result = assemble(hm, [spec("A", [(1, 1)], 5), spec("B", [(1, 1)], 5)])
        self.assertEqual({body.water_body_uid for body in result.materialized.bodies}, {"A", "B"})
        self.assertEqual(result.physical_unions[0].member_uids, ("A", "B"))

    def test_reserved_mountain_island_stays_dry_at_its_original_height(self):
        hm = flat_heightmap(0, 5, 0, 5, z=-2)
        hm.surface_z[(2, 2)] = 50
        before = dict(hm.surface_z)
        result = assemble(hm, [spec("ocean", set(hm.surface_z), 0, kind=BasinKind.OCEAN)],
                          mode=WorldTopologyMode.WRAPPED)
        self.assertEqual(dict(result.materialized.cells)[(2, 2)].role, HydrologyCellRole.SHORE)
        self.assertEqual(hm.surface_z, before)

    def test_partial_snapshot_reports_unresolved_instead_of_inventing_rim(self):
        hm = flat_heightmap(0, 5, 0, 3, z=-2)
        del hm.surface_z[(2, 2)]
        result = assemble(hm, [], auto=True)
        self.assertEqual(dict(result.materialized.cells), {})
        self.assertEqual(result.physical_unions, ())

    def test_physical_water_and_shore_cross_sphere_fold(self):
        hm = flat_heightmap(0, 5, 0, 3, z=10)
        hm.surface_z.update({(0, 0): -1, (3, 0): -2})
        result = assemble(hm, [spec("fold-lake", [(0, 0), (3, 0)], 0)],
                          mode=WorldTopologyMode.SPHERE)
        cells = dict(result.materialized.cells)
        self.assertTrue(cells[(0, 0)].liquid_candidate)
        self.assertTrue(cells[(3, 0)].liquid_candidate)
        self.assertEqual(cells[(0, 1)].role, HydrologyCellRole.SHORE)
        self.assertEqual(len(result.materialized.bodies), 1)

    def test_exterior_reservoir_survives_later_merge_with_higher_lake(self):
        hm = row_map([-5, -5, 5, 5, 99])
        # The natural ocean reaches the boundary before the higher source is
        # encountered. That boundary condition must survive subsequent unions.
        result = assemble(hm, [spec("high-lake", [(3, 1)], 20)], auto=True)
        self.assertTrue(result.materialized.bodies)
        self.assertNotIn("high-lake", {body.water_body_uid for body in result.materialized.bodies})
        self.assertTrue(all(body.z_water_level == 0 for body in result.materialized.bodies))
        self.assertEqual(dict(result.materialized.cells)[(2, 1)].role, HydrologyCellRole.SHORE)
        self.assertFalse(dict(result.materialized.cells)[(2, 1)].liquid_candidate)

    def test_auto_anchor_remap_keeps_shared_parent_identity_consistent(self):
        hm = row_map([99, -1, -5, 2, 0, 0, 99])
        result = assemble(hm, [spec("B", [(4, 1)], 5)],
                          auto=True, mode=WorldTopologyMode.WRAPPED)
        self.assertEqual(len(result.physical_unions), 1)
        union = result.physical_unions[0]
        self.assertEqual(union.water_system_uid, water_system_uid(
            hm.world_uid, "change-a", union.member_uids, WaterSystemKind.PHYSICAL_MERGE))
        self.assertEqual(set(union.member_uids), {body.water_body_uid for body in result.materialized.bodies})
        self.assertTrue(all(body.parent_system_uid == union.water_system_uid
                            for body in result.materialized.bodies))

    def test_spill_keeps_disconnected_low_pockets_of_declared_footprint(self):
        hm = row_map([99, -2, 8, 0, 0, 10, 5, 5, 99])
        result = assemble(hm, [spec("lake", [(x, 1) for x in range(3, 8)], 20)])
        self.assertEqual(result.materialized.bodies[0].z_water_level, 8)
        self.assertEqual(result.materialized.bodies[0].declared_level, 8)
        self.assertTrue(dict(result.materialized.cells)[(3, 1)].liquid_candidate)
        self.assertTrue(dict(result.materialized.cells)[(7, 1)].liquid_candidate)
        self.assertEqual(dict(result.materialized.cells)[(5, 1)].role, HydrologyCellRole.SHORE)
        self.assertEqual({entry.water_body_uid for entry in dict(result.materialized.cells).values()}, {"lake"})


if __name__ == "__main__":
    unittest.main()
