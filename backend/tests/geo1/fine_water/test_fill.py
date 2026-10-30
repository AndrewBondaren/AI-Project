from copy import replace
from unittest import TestCase

from app.application.encoding.canonicalCodec import encode, decode
from app.application.planning.service.planningService import PlanBuildFailure
from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.terrain.planning.preWater.terrainBasePlanner import PreWaterTerrainPlanner
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.relief.bathymetry.floorProfile import SampledFloorProfile
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.fineTopology import fine_topology
from tests.geo1.coating.fixtures import envelope
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.terrain_base.fixtures import inputs, Control


def source(*, cells=None, mountain=False, hills=True, elevation=10):
    values = list(inputs(mountain=mountain, hills=hills))
    terrain = values[-1]
    values[-1] = envelope("terrain_base", replace(terrain.payload,
        surface_z=tuple((cell, elevation) for cell, _ in terrain.payload.surface_z)), terrain.dependencies)
    window = PreWaterTerrainPlanner().prepare_window("world", *values,
        cells=cells or coverage(0, 32, 0, 32), control=Control())
    return window, window.payload.protected_cells, fine_topology(values[2].topology, values[0].grid.fine_span)


def basin(uid, cells, space=CoordinateSpace.WORLD_FINE_GRID):
    return BasinSpec(source_uid=uid, kind=BasinKind.LAKE, liquid="water", footprint=frozenset(cells),
        z_water_level=0, floor_z=-5, bands=HydrologyBands(min=1, max=2),
        floor_profile=SampledFloorProfile(space=space,
            samples=tuple((cell, -5) for cell in sorted(cells, key=lambda c: (c[1], c[0])))))


def fill(window, topology, specs=(), expected=None):
    return WaterBodyPlanner().fill_fine(window, expected_surface=expected or window.ref,
        topology=topology, specs=specs, policy=WorldHydrology(),
        change_uid="fine-operation", control=Control())


class FineWaterTests(TestCase):
    def test_real_window_carve_fill_preserves_geometry_and_frozen_source(self):
        window, protected, topology = source(mountain=True)
        without_hills, _, _ = source(mountain=True, hills=False)
        self.assertTrue(any(z > dict(without_hills.payload.surface_z)[cell] for cell, z in window.payload.surface_z))
        before = encode(window, SURFACE_MANIFEST)
        cells = {(x, y) for y in range(1, 15) for x in range(1, 15)}
        spec = basin("accepted", cells)
        scratch, water, diagnostics = fill(window, topology, (spec,))
        wet = {cell for cell, value in water.materialized.by_cell.items() if value.liquid_candidate}
        self.assertEqual(wet, cells - protected)
        self.assertEqual({cell: scratch.surface_z[cell] for cell in protected},
                         {cell: z for cell, z in window.payload.surface_z if cell in protected})
        self.assertEqual(encode(window, SURFACE_MANIFEST), before)
        self.assertEqual({body.water_body_uid for body in water.materialized.bodies}, {"accepted"})
        self.assertEqual(water.materialized.source_mapping.entries[0].body_uids, ("accepted",))
        restored = decode(before, PlanEnvelope[FineSurfaceWindow], SURFACE_MANIFEST)
        replay = fill(restored, topology, (spec,))
        self.assertEqual(replay, (scratch, water, diagnostics))

    def test_touching_sources_use_one_physical_merge_and_mapping_owner(self):
        window, protected, topology = source()
        a = basin("a", {(x, y) for y in range(2, 8) for x in range(2, 8)})
        b = basin("b", {(x, y) for y in range(2, 8) for x in range(8, 14)})
        _, water, _ = fill(window, topology, (b, a))
        self.assertTrue(any(set(union.member_uids) == {"a", "b"} for union in water.physical_unions))
        self.assertEqual({entry.source_uid for entry in water.materialized.source_mapping.entries}, {"a", "b"})
        self.assertEqual(fill(window, topology, (a, b))[1], water)

    def test_revision_and_output_proof_are_required(self):
        window, protected, topology = source()
        previous, _, _ = source(hills=False)
        with self.assertRaisesRegex(ValueError, "revision"):
            fill(window, topology, expected=previous.ref)
        changed = replace(window.payload, surface_z=tuple((cell, z + 1) for cell, z in window.payload.surface_z))
        with self.assertRaisesRegex(ValueError, "revision"):
            fill(replace(window, payload=changed), protected, topology)

    def test_partial_world_evidence_is_rejected_without_implicit_dry(self):
        window, protected, topology = source(cells=coverage(0, 4, 0, 4))
        before = encode(window, SURFACE_MANIFEST)
        with self.assertRaises(PlanBuildFailure):
            fill(window, topology, (basin("partial", {(1, 1)}),))
        self.assertEqual(encode(window, SURFACE_MANIFEST), before)

    def test_coarse_floor_and_foreign_protection_are_rejected(self):
        window, protected, topology = source()
        with self.assertRaisesRegex(ValueError, "frame"):
            fill(window, topology, (basin("coarse", {(1, 1)}, CoordinateSpace.WORLD_SURFACE_GRID),))
        with self.assertRaisesRegex(ValueError, "topology"):
            fill(window, replace(topology, mode=type(topology.mode).WRAPPED))
        with self.assertRaisesRegex(ValueError, "protection"):
            FineSurfaceWindow(coverage=window.payload.coverage, surface_z=window.payload.surface_z,
                topology=topology, protected_cells=frozenset({(-1, 0)}))

    def test_empty_accepted_sources_do_not_reenable_implicit_water(self):
        window, protected, topology = source(elevation=-10)
        _, water, _ = fill(window, topology)
        self.assertEqual(water.materialized.by_cell, {})
        self.assertEqual(water.materialized.bodies, ())

    def test_window_completeness_order_and_recipe_identity(self):
        window, _, _ = source(cells=coverage(0, 4, 0, 4))
        for rows in (window.payload.surface_z[:-1], tuple(reversed(window.payload.surface_z)),
                     (window.payload.surface_z[0],) + window.payload.surface_z):
            with self.assertRaises(ValueError):
                FineSurfaceWindow(coverage=window.payload.coverage, surface_z=rows,
                    topology=window.payload.topology, protected_cells=window.payload.protected_cells)
        replay, _, _ = source(cells=coverage(0, 4, 0, 4))
        self.assertEqual(window, replay)
        changed, _, _ = source(cells=coverage(0, 4, 0, 4), hills=False)
        self.assertNotEqual(window.ref.key.input_fingerprint, changed.ref.key.input_fingerprint)
