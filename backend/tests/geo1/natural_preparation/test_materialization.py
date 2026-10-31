from copy import replace
from unittest import TestCase
from unittest.mock import patch

from app.application.encoding.canonicalCodec import encode
from app.application.worldData.generators.terrain.planning.preWater.terrainBasePlanner import PreWaterTerrainPlanner
from app.application.worldData.generators.terrain.planning.preWater.terrainBaseJob import PreWaterTerrainJob
from app.application.worldData.generators.terrain.planning.preWater.prepared import materialization as window_job
from app.application.worldData.generators.terrain.hills import hillLayout, hillRaster
from app.application.worldData.generators.terrain.hills import hillSelection, hillPlacement
from app.application.worldData.generators.terrain.hills.hillPlacement import place_hills
from app.application.worldData.generators.terrain.hills.hillSelection import prepare_hills
from app.application.worldData.generators.terrain.landcover.planning.preWaterHillHosts import PreWaterHillHostJob
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.hillShape import HillShape
from app.dataModel.terrain.hills.acceptedHill import AcceptedHill, HillLayout
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.worldBounds import WorldBounds
from tests.geo1.coating.fixtures import envelope
from tests.geo1.hill_hosts.test_hosts import coverage
from tests.geo1.terrain_base.fixtures import prepare, Control
from tests.geo1.natural_preparation.fixtures import values
from tests import test_open_land_hills as hill_fixture
from app.dataModel.terrainMasks.regions import PlainSpec
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.regions.regionState import RegionState
from app.application.worldData.masks.regionIdentity import declared_region_identity


class MaterializationTests(TestCase):
    def ready(self, v=None):
        v = v or values()
        return PreWaterTerrainPlanner().prepare_revision("world", *v, control=Control()).payload

    def test_disjoint_negative_windows_and_all_topologies_equal_full_reference(self):
        for mode in WorldTopologyMode:
            for resample in ("nearest", "bilinear"):
                with self.subTest(mode=mode, resample=resample):
                    v = values()
                    box = GridBBox(-1, 0, -1, 0)
                    v[0] = replace(v[0], bbox=box)
                    v[2] = replace(v[2], topology=replace(v[2].topology, mode=mode,
                        bounds=WorldBounds(x_min=-1, x_max=0, y_min=-1, y_max=0)),
                        refine_policy=replace(v[2].refine_policy, resample=resample))
                    terrain = v[4]
                    v[4] = envelope("terrain_base", replace(terrain.payload, bbox=box,
                        surface_z=tuple((SurfaceGridCoord(c.gx-1, c.gy-1), z) for c, z in terrain.payload.surface_z)),
                        terrain.dependencies)
                    ready = self.ready(v)
                    full, protected = prepare(v, coverage(-16, 16, -16, 16))
                    parts = (coverage(-16, -12, -16, -12), coverage(-3, 3, -1, 2), coverage(12, 16, 12, 16))
                    union = RegionCoverage(region_uid="world", spans=tuple(sorted(
                        (s for p in parts for s in p.spans), key=lambda s: (s.y, s.x0))))
                    observed = PreWaterTerrainPlanner().materialize(ready, cells=union, control=Control())
                    expected = {(x, s.y): full.surface_z[x, s.y] for s in union.spans for x in range(s.x0, s.x1)}
                    self.assertEqual(dict(observed.surface_z), expected)
                    self.assertEqual(observed.protected_cells, protected.intersection(expected))

    def test_two_points_do_not_prepare_select_hosts_or_rasterize_full_features(self):
        ready = self.ready()
        before = encode(ready, SURFACE_MANIFEST)
        tile = next(t for t in ready.tiles if t.hills is not None)
        leaf = tile.hills
        while leaf.hill is None:
            leaf = leaf.left
        x, y = leaf.hill.origin
        requested = RegionCoverage(region_uid="world", spans=tuple(sorted(
            (*coverage(x, x+1, y, y+1).spans, *coverage(31, 32, 31, 32).spans), key=lambda s: (s.y, s.x0))))
        visited = []
        original = window_job.refine_light_surface
        def bounded(*args, **kwargs):
            local = tuple(kwargs["local_cells"])
            visited.extend(local)
            observed = original(*args, **(kwargs | {"local_cells": local}))
            self.assertEqual(len(observed), len(local))
            return observed
        with patch.object(PreWaterTerrainJob, "__init__", side_effect=AssertionError("re-preparation")), \
             patch.object(PreWaterHillHostJob, "project_tile", side_effect=AssertionError("hosts")), \
             patch.object(hillSelection, "selected_hills", side_effect=AssertionError("selection")), \
             patch.object(hillPlacement, "selected_hills", side_effect=AssertionError("selection")), \
             patch.object(hillRaster, "raster_hill", side_effect=AssertionError("full raster")), \
             patch.object(window_job, "refine_light_surface", side_effect=bounded), \
             patch.object(hillRaster, "_terrace", wraps=hillRaster._terrace) as raster:
            result = PreWaterTerrainPlanner().materialize(ready, cells=requested, control=Control())
        self.assertEqual(len(result.surface_z), 2)
        self.assertEqual(len(visited), 2)
        self.assertGreater(raster.call_count, 0)
        self.assertLessEqual(raster.call_count, 4)
        self.assertEqual(encode(ready, SURFACE_MANIFEST), before)

    def test_clipped_raster_preserves_every_shape_axis_and_small_radius(self):
        host = {(x, y) for y in range(-9, 10) for x in range(-9, 10)}
        for shape in HillShape:
            for axis in (0, 1):
                for radius in (1, 5):
                    hill = AcceptedHill(origin=(0, 0), shape=shape, axis=axis, radius=radius, height=4)
                    full = hillRaster.raster_hill(hill.origin, radius=radius, height=4,
                        host_cells=host, shape=shape, axis=axis)
                    for bounds in (GridBBox(-2, 3, -1, 2), GridBBox(2, 3, -1, 2)):
                        observed = hillRaster.raster_hill_window(hill, bounds)
                        self.assertEqual(observed, {c: z for c, z in full.items()
                            if bounds.x_min <= c[0] <= bounds.x_max and bounds.y_min <= c[1] <= bounds.y_max})

    def test_prepared_hills_preserve_full_selection_where_halo_reselection_fails(self):
        fixture = hill_fixture.TestPlaceHills()
        fixture.setUp()
        policy = HillPolicy(min_spacing=6, radius=2, height=3, shapes=(HillShape.CIRCLE,))
        registry = fixture._registry(policy, policy)
        full = {(x, y): 0 for y in range(96) for x in range(96)}
        terrain = dict.fromkeys(full, fixture.plains)
        accepted = prepare_hills(GridBBox(0, 95, 0, 95), terrain, (), registry=registry, seed=4)
        layout = hillLayout.build_hill_layout(accepted)
        x, y = accepted[0].origin
        with patch.object(hillLayout, "hills_for_window", wraps=hillLayout.hills_for_window) as query:
            hits = list(hillLayout.hills_for_window(layout, GridBBox(x, x, y, y)))
        self.assertEqual(hits, [accepted[0]])
        self.assertLess(query.call_count, len(accepted)//2)
        place_hills(full, terrain, (), terrain_registry=registry, seed=4, z_min=0, z_max=40)
        local = {(x, y): 0 for y in range(24, 72) for x in range(24, 72)}
        place_hills(local, dict.fromkeys(local, fixture.plains), (), terrain_registry=registry, seed=4, z_min=0, z_max=40)
        observed = {(x, y): 0 for y in range(36, 60) for x in range(36, 60)}
        hillLayout.materialize_hills(observed, layout, GridBBox(36, 59, 36, 59), z_min=0, z_max=40)
        self.assertEqual(observed, {c: full[c] for c in observed})
        self.assertTrue(any(local[c] != full[c] for c in observed))

    def test_overlapping_hills_merge_against_the_same_original_base(self):
        v = values(shape=HillShape.DOUBLE_OVAL, mountain=False)
        v[2] = replace(v[2], terrain_entries=tuple(replace(e, hills=replace(e.hills,
            radius=5, height=6, min_spacing=2)) if e.hills else e for e in v[2].terrain_entries))
        observed = PreWaterTerrainPlanner().materialize(self.ready(v), cells=coverage(0, 32, 0, 32), control=Control())
        self.assertEqual(dict(observed.surface_z), prepare(v)[0].surface_z)

    def test_captured_region_states_control_hosts_identically_to_full_reference(self):
        v = values(mountain=False)
        spec = PlainSpec(name="hosts", shape=BboxShape(x_min=0, x_max=15, y_min=0, y_max=15))
        state = RegionState(region_uid=declared_region_identity("world", spec).region_uid, current_type="farmland")
        outputs = []
        for tombstone in (False, True):
            v[2] = replace(v[2], declared_regions=(spec,), region_states=(replace(state, tombstone=tombstone),))
            ready = self.ready(v)
            observed = PreWaterTerrainPlanner().materialize(ready, cells=coverage(0, 32, 0, 32), control=Control())
            self.assertEqual(dict(observed.surface_z), prepare(v)[0].surface_z)
            outputs.append(observed.surface_z)
        self.assertNotEqual(*outputs)

    def test_ravine_exclusions_are_prepared_once_and_preserved(self):
        v = values(mountain=False)
        grid = SurfaceGridSettings(fine_span=16, light_side=1)
        v[0] = replace(v[0], grid=grid)
        v[1] = replace(v[1], grid=grid, ravines=replace(v[1].ravines, enabled=True, autoresolve=True, min_neighbors=1))
        v[2] = replace(v[2], grid=grid)
        terrain = v[4]
        v[4] = envelope("terrain_base", replace(terrain.payload, surface_z=tuple(
            (c, -10 if c.gx == 0 and c.gy == 0 else 10) for c, _ in terrain.payload.surface_z)), terrain.dependencies)
        ready = self.ready(v)
        self.assertTrue(ready.light.ravine_cells)
        self.assertIsNone(ready.tiles[0].hills)
        observed = PreWaterTerrainPlanner().materialize(ready, cells=coverage(0, 32, 0, 32), control=Control())
        self.assertEqual(dict(observed.surface_z), prepare(v)[0].surface_z)

    def test_scope_cancellation_and_spatial_index_guards(self):
        ready = self.ready()
        planner = PreWaterTerrainPlanner()
        for cells in (coverage(-1, 1), RegionCoverage(region_uid="world", spans=())):
            with self.assertRaises(ValueError):
                planner.materialize(ready, cells=cells, control=Control())
        class Stop:
            def raise_if_shutdown(self):
                raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):
            planner.materialize(ready, cells=coverage(), control=Stop())
        hill = AcceptedHill(origin=(2, 2), radius=2, height=3, shape=HillShape.CIRCLE, axis=0)
        with self.assertRaisesRegex(ValueError, "bounds"):
            HillLayout(bounds=GridBBox(0, 1, 0, 1), hill=hill, left=None, right=None)
