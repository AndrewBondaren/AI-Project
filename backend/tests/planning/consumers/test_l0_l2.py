"""PC-10/PC-11: frozen L0/L2 consumers, cache equality and production refine."""

from tests.planning.consumers.test_wiring import working_fixture
from app.application.jsonValidation import terrain_system_keys
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.planning.consumers.test_wiring import Composition, Wait, capture, world
from app.application.worldData.planning.composition.surfacePlanningAssembler import to_legacy_context
from app.application.worldData.planning.composition.surfacePlanningEntry import surface_world_topology
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.application.worldData.pack.bake.lightGrid.bake import compose_light_grid
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.lightGrid.contributors.relief import ReliefContributor
from app.application.worldData.pack.bake.lightGrid.contributors.climate import ClimateContributor
from app.application.worldData.pack.bake.lightGrid.contributors.mountain import MountainContributor
from app.application.worldData.pack.bake.lightGrid.contributors.ravine import RavineContributor
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.hydro import HydroContributor
from app.application.worldData.pack.bake.l0.worldMapBakeOrchestrator import WorldMapBakeOrchestrator
from app.dataModel.worldPack.wire.locationsIndexWire import LocationsIndexWire
from app.dataModel.worldPack.wire.hydrologyMaskWire import WorldMapHydrologyRole


PIPELINE = (ReliefContributor(), ClimateContributor(), MountainContributor(), RavineContributor(), HydroContributor())


def mountain_source():
    return world(z_min=-10, z_max=40, world_topology_mode="planar", world_map_cells_per_tile=4,
        terrain_masks={"enabled": True, "default_mountains": {"autoresolve": False},
            "default_ravines": {"autoresolve": True, "min_drop_z": 1, "min_neighbors": 3},
            "declared_mountains": [{"entry_type": "mountain", "origin_x_m": 1000, "origin_y_m": 1000, "radius_m": 1500,
                "form": {"form_type": "by_sides", "side_count": 4}, "sides": [{"kind": "slope"}] * 4}]})


def context(source, bundle, tiles=None):
    scale = LightGridScale.from_tile(1000, source.world_map_cells_per_tile)
    return LightGridBakeContext(world=source, locations=[], locations_index=LocationsIndexWire(locations=[]),
        tiles=tiles if tiles is not None else [(c.gx, c.gy) for c, _ in bundle.terrain_base.payload.surface_z],
        scale=scale, terrain_system_keys=terrain_system_keys(source), surface_bundle=bundle, surface_planning=to_legacy_context(bundle, working=working_fixture(source, bundle)), working=working_fixture(source, bundle),
        topology=surface_world_topology(source, []),
        grid=SurfaceGridSettings(fine_span=scale.tile_macro, light_side=scale.side))


def bind_frozen_context(test, ctx):
    """Migrate old compose fixtures at the caller boundary, never in production."""
    from dataclasses import fields
    from app.db.models.world import World
    from app.application.worldData.planning.composition.surfacePlanningCapture import mountain_template_inputs
    values = {field.name: getattr(ctx.world, field.name) for field in fields(World)
        if hasattr(ctx.world, field.name)}
    values.setdefault("name", "L0 fixture")
    values.setdefault("created_at", "")
    values["world_map_cells_per_tile"] = ctx.scale.side
    if not values.get("world_bounds"):
        values["world_bounds"] = dict(x_min=min(x for x, _ in ctx.tiles), x_max=max(x for x, _ in ctx.tiles),
            y_min=min(y for _, y in ctx.tiles), y_max=max(y for _, y in ctx.tiles))
    ctx.world = World(**values)
    ctx.world.map_settings = {"global_cell_size_m": ctx.scale.tile_macro}
    ctx.topology = surface_world_topology(ctx.world, ctx.locations)
    ctx.grid = SurfaceGridSettings(fine_span=ctx.scale.tile_macro, light_side=ctx.scale.side)
    composition = Composition()
    test.addCleanup(composition.service.shutdown)
    ctx.surface_bundle = composition.prepare(capture(ctx.world, locations=ctx.locations,
        templates=mountain_template_inputs(ctx.relief_templates_by_uid)))
    ctx.surface_planning = to_legacy_context(ctx.surface_bundle, working=working_fixture(world(), ctx.surface_bundle))
    ctx.working = working_fixture(ctx.world, ctx.surface_bundle)
    return ctx


class L0Tests(unittest.TestCase):
    def setUp(self):
        self.c = Composition()
        self.addCleanup(self.c.service.shutdown)

    def test_frozen_relief_absolute_z_and_partial_tiles_are_equal(self):
        source = mountain_source()
        bundle = self.c.prepare(capture(source))
        self.assertTrue(bundle.relief.payload.light.mountain_cells)
        self.assertTrue(bundle.relief.payload.light.ravine_cells)
        full = compose_light_grid(context(source, bundle), contributors=PIPELINE)
        for tile in context(source, bundle).tiles:
            partial = compose_light_grid(context(source, bundle, [tile]), contributors=PIPELINE)
            self.assertEqual(partial.to_wire_tile(*tile), full.to_wire_tile(*tile))
        for effect in bundle.relief.payload.light.ravine_cells:
            ref = effect.cell
            self.assertEqual(full.get(ref.gx, ref.gy, ref.tx, ref.ty).surface_z, effect.surface_z)

    def test_no_live_detection_selection_or_template_stamp_and_no_instance_state(self):
        source = mountain_source()
        bundle = self.c.prepare(capture(source))
        original = deepcopy(bundle)
        expected = compose_light_grid(context(source, bundle), contributors=PIPELINE)
        source.terrain_masks = {"enabled": False}
        source.hydrology = {"enabled": True}
        with ExitStack() as stack:
            for target in ("app.application.worldData.generators.climate.climatePoleField.ClimatePoleField.sample",
                "app.application.worldData.generators.terrain.mountains.collect.collect_prepared_mountain_entries_for_coarse",
                "app.application.worldData.generators.terrain.mountains.reliefSidesStamp.stamp_entries_from_relief",
                "app.application.worldData.generators.terrain.reliefObjects.depressionDetect.detect_depression_cells",
                "app.application.worldData.generators.hydrology.load.loadDeclaredHydrology.load_declared_hydrology"):
                stack.enter_context(patch(target, side_effect=AssertionError(target)))
            actual = compose_light_grid(context(source, bundle), contributors=PIPELINE)
        self.assertEqual(bundle, original)
        for tile in context(source, bundle).tiles:
            self.assertEqual(actual.to_wire_tile(*tile), expected.to_wire_tile(*tile))
        materializer = PIPELINE[2]._materializer
        self.assertEqual(materializer.collect(context(source, bundle)), bundle.relief.payload.mountain_layout.entries)
        self.assertEqual(vars(materializer), {})

    def test_height_does_not_depend_on_successful_terrain_paint(self):
        source = mountain_source()
        bundle = self.c.prepare(capture(source))
        ctx = context(source, bundle)
        compose = LightGridCompose(ctx.scale)
        ReliefContributor().apply(compose, ctx)
        for ref, _ in bundle.relief.payload.light.base_surface_z:
            compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty).hydrology_role = WorldMapHydrologyRole.RIVER
        MountainContributor().apply(compose, ctx)
        for effect in bundle.relief.payload.light.mountain_cells:
            ref = effect.cell
            cell = compose.get(ref.gx, ref.gy, ref.tx, ref.ty)
            self.assertIsNone(cell.system_terrain)
            self.assertEqual(cell.surface_z, effect.surface_z)
        RavineContributor().apply(compose, ctx)
        for effect in bundle.relief.payload.light.ravine_cells:
            ref = effect.cell
            self.assertEqual(compose.get(ref.gx, ref.gy, ref.tx, ref.ty).surface_z, effect.surface_z)

    def test_hit_clear_restart_and_edit_without_eager_materialize(self):
        source = mountain_source()
        view = capture(source)
        first = self.c.prepare(view)
        with patch.object(self.c.registry, "build", wraps=self.c.registry.build) as builds:
            hit = self.c.prepare(view)
        builds.assert_not_called()
        self.c.backend.clear()
        rebuilt = self.c.prepare(view)
        fresh = Composition(workers=1)
        self.addCleanup(fresh.service.shutdown)
        restarted = fresh.prepare(view)
        ctx = context(source, first)
        expected = compose_light_grid(ctx, contributors=PIPELINE)
        for bundle in (hit, rebuilt, restarted):
            actual = compose_light_grid(context(source, bundle), contributors=PIPELINE)
            for tile in ctx.tiles:
                self.assertEqual(actual.to_wire_tile(*tile), expected.to_wire_tile(*tile))
        with patch("app.application.worldData.pack.bake.lightGrid.bake.compose_light_grid",
                   side_effect=AssertionError("eager materialize")):
            changed = capture(replace(source, z_max=60))
            self.c.prepare(changed)
        self.assertNotEqual(changed.revision, view.revision)

    def test_real_default_compose_and_writer_light_full_partial_delivery(self):
        source = mountain_source()
        bundle = self.c.prepare(capture(source))
        ctx = context(source, bundle)
        writer = Mock()
        writer.write_world_map_tile.return_value = "content-hash"
        for mode in ("light", "full"):
            count = WorldMapBakeOrchestrator().bake_tiles(source, [], writer, ctx.tiles,
                surface_bundle=bundle, region_state_snapshot={}, wait=Wait(),
                bake_mode=mode, working=working_fixture(source, bundle))
            self.assertEqual(count, len(ctx.tiles) * ctx.scale.side ** 2)
        self.assertEqual(writer.write_world_map_tile.call_count, 2 * len(ctx.tiles))
        expected = compose_light_grid(ctx).to_wire_tile(0, 0)
        cells, _ = WorldMapBakeOrchestrator().bake_tile(source, 0, 0,
            writer, wait=Wait(), surface_bundle=bundle, region_state_snapshot={},
            working=working_fixture(source, bundle))
        self.assertEqual(cells, expected)

    def test_missing_foreign_bundle_and_wrong_scale_fail_before_writes(self):
        source = mountain_source()
        bundle = self.c.prepare(capture(source))
        ctx = context(source, bundle)
        ctx.surface_bundle = None
        with self.assertRaisesRegex(ValueError, "frozen"):
            ReliefContributor().apply(LightGridCompose(ctx.scale), ctx)
        ctx.surface_bundle = bundle
        ctx.world = replace(source, world_uid="foreign")
        with self.assertRaisesRegex(ValueError, "another world"):
            ctx.require_surface_bundle()
        ctx.world = source
        ctx.scale = LightGridScale.from_tile(1000, 2)
        with self.assertRaisesRegex(ValueError, "scale"):
            ctx.require_surface_bundle()

    def test_declared_hydro_partial_matches_full_and_preserves_river_inside_sea(self):
        from app.db.models.namedLocation import NamedLocation
        source = world(z_min=-100, world_map_cells_per_tile=4, hydrology={"enabled": True,
            "default_lakes": {"autoresolve": False, "min_water_cells": 1},
            "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
            "default_rivers": {"autoresolve": False},
            "declared_basins": [{"location_uid": "basin", "kind": "ocean", "floor_z": -10,
                "footprint": {"kind": "bbox", "x_min": 0, "x_max": 3000, "y_min": 0, "y_max": 3000}}],
            "declared_lakes": [{"location_uid": "lake", "shoreline": [
                {"x": 1000, "y": 1000}, {"x": 2000, "y": 1000},
                {"x": 2000, "y": 2000}, {"x": 1000, "y": 2000}]}],
            "declared_coastlines": [{"location_uid": "coast", "kind": "sea", "path": [
                {"x": 0, "y": 2500}, {"x": 2500, "y": 2500}]}],
            "declared_rivers": [
                {"location_uid": "segment", "declare_mode": "segments", "segments": [
                    {"from": {"x": 0, "y": 500}, "to": {"x": 2500, "y": 500},
                     "connection_type": "river", "width_cells": 700}]},
                {"location_uid": "intent", "declare_mode": "via_locations", "route_location_uids": ["a", "b"]}]})
        locations = [NamedLocation(location_uid=uid, world_uid=source.world_uid, display_name=uid,
            created_at="", system_location_type="geographic", map_x=x, map_y=1500) for uid, x in (("a", 0), ("b", 2500))]
        bundle = self.c.prepare(capture(source, locations=locations))
        paint = bundle.hydrology.payload.declared_paint
        self.assertEqual(len(paint.segments), 1)
        self.assertEqual(paint.intents[0].path, ((0, 1500), (2500, 1500)))
        self.assertTrue(paint.lakes and paint.coastlines)
        self.assertTrue(bundle.hydrology.payload.coarse_hydro)
        full = compose_light_grid(context(source, bundle), contributors=PIPELINE)
        for tile in context(source, bundle).tiles:
            partial = compose_light_grid(context(source, bundle, [tile]), contributors=PIPELINE)
            self.assertEqual(full.to_wire_tile(*tile), partial.to_wire_tile(*tile))
        self.assertEqual(full.get(0, 0, 0, 2).hydrology_role, WorldMapHydrologyRole.RIVER)
        self.assertEqual(full.get(0, 0, 0, 2).hydrology_width, 15)
        self.assertEqual(full.get(0, 1, 0, 2).hydrology_width, paint.intents[0].width_wire)
        # Intent path has no dilation; the adjacent light row is coarse sea.
        self.assertEqual(full.get(0, 1, 0, 3).hydrology_role, WorldMapHydrologyRole.SEA)
        final_z = {(c.gx, c.gy): z for c, z in bundle.hydrology.payload.coarse_surface_z}
        self.assertEqual(full.get(0, 1, 0, 3).surface_z, final_z[(0, 1)])

    def test_standalone_l0_uses_injected_planning_on_miss_and_hit(self):
        from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
        source = mountain_source()
        writer = Mock()
        writer.write_world_map_tile.return_value = "hash"
        orchestrator = WorldMapBakeOrchestrator()
        bundle = frozen_surface_fixture(source)
        orchestrator.bake_tiles(source, [], writer, [(0, 0)], wait=Wait(), surface_bundle=bundle,
            region_state_snapshot={}, working=working_fixture(source, bundle))
        first = writer.write_world_map_tile.call_args.args[2]
        cells, _ = orchestrator.bake_tile(source, 0, 0, writer, wait=Wait(),
            surface_bundle=bundle, region_state_snapshot={},
            working=working_fixture(source, frozen_surface_fixture(source)))
        self.assertEqual(cells, first)


def frozen_surface_fixture(source, parent=None, *, bbox=None):
    """Real frozen bundle for old parent/column fixtures; no production adapter."""
    from dataclasses import fields
    from app.db.models.world import World
    values = {field.name: vars(source)[field.name] for field in fields(World)
              if field.name in vars(source)}
    values.setdefault("hydrology", {"enabled": False})
    values.setdefault("terrain_masks", {"enabled": False})
    values.setdefault("name", "L2 fixture")
    values.setdefault("created_at", "")
    if parent is not None:
        values["world_map_cells_per_tile"] = parent.side
        values["world_bounds"] = dict(x_min=parent.gx, x_max=parent.gx,
                                    y_min=parent.gy, y_max=parent.gy)
    if bbox is not None:
        values["world_bounds"] = dict(x_min=bbox.x_min, x_max=bbox.x_max,
                                    y_min=bbox.y_min, y_max=bbox.y_max)
    frozen_world = World(**values)
    if parent is not None:
        frozen_world.map_settings = {"global_cell_size_m": parent.tile_macro}
    composition = Composition()
    try:
        return composition.prepare(capture(frozen_world))
    finally:
        composition.service.shutdown()


class L2Tests(unittest.TestCase):
    def setUp(self):
        from app.application.worldData.materialize.terrain.terrainBatchOrchestrator import TerrainBatchOrchestrator
        self.c = Composition()
        self.addCleanup(self.c.service.shutdown)
        self.source = world(world_bounds=dict(x_min=0, x_max=2, y_min=0, y_max=2),
                            z_min=-20, z_max=40)
        self.source.map_settings = {"global_cell_size_m": 8}
        self.terrain = TerrainBatchOrchestrator()

    def parents(self, bundle):
        from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile
        ctx = LightGridBakeContext(world=self.source, locations=[], locations_index=LocationsIndexWire(),
            tiles=[(c.gx, c.gy) for c, _ in bundle.terrain_base.payload.surface_z],
            scale=LightGridScale.from_tile(8, 2), surface_bundle=bundle, working=working_fixture(self.source, bundle),
            topology=surface_world_topology(self.source, []),
            grid=SurfaceGridSettings(fine_span=8, light_side=2))
        compose = compose_light_grid(ctx, contributors=PIPELINE)
        return {tile: ParentLightTile.from_cells(world_uid=self.source.world_uid, gx=tile[0], gy=tile[1],
            side=2, tile_macro=8, cells=compose.to_wire_tile(*tile)) for tile in ctx.tiles}

    def states(self, bundle, parents, tiles=None):
        working = working_fixture(self.source, bundle)
        return {tile: self.terrain.build_tile_surface_state(self.source, [], bundle, *tile,
            parent_light=parents[tile], region_state_snapshot={}, working=working) for tile in (tiles if tiles is not None else parents)}

    def test_l2_cache_hit_clear_restart_and_reverse_tiles_are_equal(self):
        view = capture(self.source)
        first = self.c.prepare(view)
        parents = self.parents(first)
        expected = self.states(first, parents)
        with patch.object(self.c.registry, "build", side_effect=AssertionError("HIT rebuilt")):
            hit = self.c.prepare(view)
        self.c.backend.clear()
        rebuilt = self.c.prepare(view)
        fresh = Composition(workers=1)
        self.addCleanup(fresh.service.shutdown)
        restarted = fresh.prepare(view)
        for bundle in (hit, rebuilt, restarted):
            self.assertEqual(self.states(bundle, parents, list(reversed(parents))), expected)
        self.assertEqual(first, hit)

    def test_l2_uses_persisted_parent_and_does_not_replan_or_mutate_payloads(self):
        from dataclasses import replace
        bundle = self.c.prepare(capture(self.source))
        before = deepcopy(bundle)
        parents = self.parents(bundle)
        parent = parents[(0, 0)]
        # A persisted edit changes the fine base; coarse relief is not rebuilt instead.
        changed = parent.model_copy(update={"cells": {xy: cell.model_copy(update={"surface_z": 9})
                                                      for xy, cell in parent.cells.items()}})
        with patch.object(self.c.assembler, "prepare", side_effect=AssertionError("second planning")), patch(
                "app.application.worldData.planning.composition.surfacePlanningAssembler.to_legacy_context",
                side_effect=AssertionError("legacy view")):
            state = self.terrain.build_tile_surface_state(self.source, [], bundle, 0, 0, parent_light=changed, region_state_snapshot={}, working=working_fixture(self.source, bundle))
        self.assertTrue(all(8 <= z <= 10 for z in state.heightmap.surface_z.values()))
        self.assertEqual(bundle, before)
        with self.assertRaisesRegex(ValueError, "another world"):
            self.terrain.build_tile_surface_state(replace(self.source, world_uid="foreign"), [], bundle,
                                                  0, 0, parent_light=parent, region_state_snapshot={}, working=working_fixture(replace(self.source, world_uid="foreign"), bundle))

    def test_landcover_facts_use_typed_terrain_base_final_hydro_and_local_anchors(self):
        from app.application.worldData.pack.bake.lightGrid.contributors.landcover.inputs import prepare_landcover_inputs
        from app.application.worldData.regions.factConsumers import collect_facts
        from app.application.worldData.regions.factConsumers.context import FactConsumerContext
        from app.application.worldData.generators.climate.registry import profile_for
        source = mountain_source()
        bundle = self.c.prepare(capture(source))
        self.assertNotEqual(bundle.terrain_base.payload.surface_z, bundle.relief.payload.surface_z)
        legacy = to_legacy_context(bundle, working=working_fixture(source, bundle))
        profiles = {str(a.system_climate_zone): profile_for(source, a.system_climate_zone)
                    for a in legacy.local_field.anchors}
        ctx = LightGridBakeContext(world=source, locations=[], locations_index=LocationsIndexWire(),
            tiles=[(0, 0)], scale=LightGridScale.from_tile(1000, 4), surface_bundle=bundle, working=working_fixture(source, bundle),
            topology=surface_world_topology(source, []),
            grid=SurfaceGridSettings(fine_span=1000, light_side=4))
        inputs = prepare_landcover_inputs(ctx)
        for coord, _ in bundle.terrain_base.payload.surface_z:
            expected = collect_facts(FactConsumerContext(legacy, ((coord.gx, coord.gy),), profiles))
            self.assertEqual(inputs.facts_at((coord.gx * 1000, coord.gy * 1000)), expected)

    def test_hydro_full_sampled_overrides_clamp_and_hard_corridor(self):
        from app.application.worldData.generators.terrain.passes.parentLightUpsample import upsample_from_parent_light
        from app.application.worldData.generators.hydrology.shore.parentLightHydroCorridor import merge_hydro_hard_corridor
        from app.dataModel.worldPack.bake.parentLightRefinePolicy import ParentLightRefinePolicy
        self.source.hydrology = {"enabled": True,
            "default_rivers": {"autoresolve": False}, "default_lakes": {"autoresolve": False, "min_water_cells": 1},
            "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
            "declared_basins": [{"location_uid": "receiver", "kind": "lake", "floor_z": -10,
                "footprint": {"kind": "bbox", "x_min": 16, "x_max": 23, "y_min": 8, "y_max": 15}}],
            "declared_rivers": [{"location_uid": "river", "declare_mode": "segments", "segments": [
                {"from": {"x": 0, "y": 8}, "to": {"x": 23, "y": 8},
                 "connection_type": "river", "width_cells": 2}]}]}
        bundle = self.c.prepare(capture(self.source))
        hydro = bundle.hydrology.payload
        self.assertTrue(hydro.fine_z_overrides, "must cover sampled surface, not just river beds")
        self.assertTrue(hydro.sparse_fine_hydro)
        parents = self.parents(bundle)
        policy = ParentLightRefinePolicy(detail_noise_amplitude=0)
        overrides = dict(hydro.fine_z_overrides)
        for tile, parent in parents.items():
            state = self.terrain.build_tile_surface_state(self.source, [], bundle, *tile,
                parent_light=parent, refine_policy=policy, region_state_snapshot={}, working=working_fixture(self.source, bundle))
            base = upsample_from_parent_light(parent, self.source, policy=policy)
            for xy, z in state.heightmap.surface_z.items():
                target = overrides.get(xy, base[xy])
                self.assertEqual(z, max(base[xy] - policy.z_band, min(base[xy] + policy.z_band, target)))
            self.assertEqual(state.hydrology or {}, merge_hydro_hard_corridor(parent, dict(hydro.sparse_fine_hydro)))


class L2ProductionTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_default_profile_uses_frozen_fallback_without_alias_reresolve(self):
        """Accepted PC-11.2b delta: missing key cannot adopt a live alias override."""
        from app.application.worldData.pack.climate.climateCoarseBake import build_climate_coarse_wire
        source = world(default_climate_zone="missing-profile", climate_pole_mode="manual",
            climate_zone_registry=[{"system_climate": "temperate", "base_temperature": 42}])
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        bundle = composition.prepare(capture(source))
        working = working_fixture(source, bundle)
        legacy = to_legacy_context(bundle, working=working)
        live = build_climate_coarse_wire(source, legacy.pole_field, legacy.coarse_hm.bbox,
            local_field=legacy.local_field, coarse_surface_z=legacy.coarse_surface_z)
        frozen = build_climate_coarse_wire(source, legacy.pole_field, legacy.coarse_hm.bbox,
            local_field=legacy.local_field, coarse_surface_z=legacy.coarse_surface_z, working=working.climate)
        self.assertEqual(live.samples[0].temperature_base, 42)
        self.assertEqual(frozen.samples[0].temperature_base, 12)
        self.assertEqual(frozen.samples[0].rainfall, live.samples[0].rainfall)

    async def test_request_views_reused_by_l0_l2_and_serial_parallel_climate(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
        from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
        from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
        from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
        from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
        from app.application.worldData.materialize.terrain.terrainBatchOrchestrator import TerrainBatchOrchestrator
        from app.application.worldData.materialize.surface.materializationContext import MaterializationContext
        from app.application.worldData.pack.climate.climatePackBakeOrchestrator import ClimatePackBakeOrchestrator
        from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
        from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
        from app.application.worldData.pack.io.worldPackReader import WorldPackReader
        from app.application.worldData.pack.read.parentLightLoad import require_parent_light
        from app.application.worldData.regions.inputs.landcoverInputs import LandcoverObservations
        source = world(world_bounds=dict(x_min=0, x_max=2, y_min=0, y_max=0), fine_cells_per_map_cell=2,
            terrain_masks={"enabled": True, "default_landcover": {"autoresolve": False, "seed_spacing": 8}})
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        view = capture(source)
        entry = SurfacePlanningEntry(composition.assembler, SurfacePlanningCapture())
        with patch.object(ClimateWorkingFields, "from_plans", wraps=ClimateWorkingFields.from_plans) as climate_factory, \
             patch.object(TerrainWorkingFields, "from_plan", wraps=TerrainWorkingFields.from_plan) as terrain_factory, \
             patch.object(HydrologyWorkingFields, "from_plan", wraps=HydrologyWorkingFields.from_plan) as hydro_factory, \
             patch.object(LandcoverObservations, "from_views", wraps=LandcoverObservations.from_views) as facts_factory, \
             patch("app.application.worldData.planning.composition.surfacePlanningEntry.world_bounds_from_world",
                   side_effect=AssertionError("materialization resolved world topology again")):
            bundle, working = entry.prepare_captured(view, world=source, wait=Wait(), resolve_ctx=ResolveContext())
            with TemporaryDirectory() as tmp:
                writer = WorldPackWriter(WorldPackPaths.from_db_parent(str(Path(tmp) / "test.db"), source.world_uid))
                tiles = [(0, 0), (1, 0), (2, 0)]
                WorldMapBakeOrchestrator().bake_tiles(source, [], writer, tiles,
                    surface_bundle=bundle, region_state_snapshot={},
                    working=working, wait=Wait())
                terrain = TerrainBatchOrchestrator()
                climate = ClimatePackBakeOrchestrator()
                for gx, gy in reversed(tiles):
                    parent = require_parent_light(source.world_uid, gx, gy, reader=WorldPackReader(writer.paths),
                        cache=writer.parent_light_cache, tile_macro=2)
                    terrain.build_tile_surface_state(source, [], bundle, gx, gy, parent_light=parent, region_state_snapshot={}, working=working)
                    wires = []
                    for workers in (1, 4):
                        output = Mock()
                        with patch("app.application.worldData.generators.climate.climatePoleField.ClimatePoleField.sample",
                                   side_effect=AssertionError("pack used live pole adapter")), patch(
                                   "app.application.worldData.generators.climate.tierResolve.profile_for",
                                   side_effect=AssertionError("tier bypassed prepared accessor")), patch(
                                   "app.application.worldData.generators.climate.climateGeneratorService.profile_for",
                                   side_effect=AssertionError("weather bypassed prepared accessor")):
                            await climate.bake_fine_tile(source, bundle, output,
                                MaterializationContext(4, parallel_workers_override=workers), gx, gy,
                                parent_light=parent, working=working)
                        wires.append(output.write_climate_tile.call_args.args[2])
                    self.assertEqual(wires[0], wires[1])
            self.assertEqual((climate_factory.call_count, terrain_factory.call_count, hydro_factory.call_count), (1, 1, 1))
            self.assertEqual(facts_factory.call_count, 1)
            self.assertIs(working.landcover.topology, view.water_placement.topology)
            self.assertIs(working.landcover.grid, view.terrain_base.grid)
            self.assertIs(working.landcover.context.climate, working.climate)
            self.assertIs(working.landcover.context.terrain, working.terrain)
            self.assertIs(working.landcover.context.hydrology, working.hydrology)

    def test_landcover_observations_are_fresh_per_request_and_bind_current_snapshot(self):
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
        from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
        from app.application.worldData.regions.inputs.landcoverInputs import prepare_landcover_inputs
        from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
        source = world()
        composition = Composition()
        self.addCleanup(composition.service.shutdown)
        entry = SurfacePlanningEntry(composition.assembler, SurfacePlanningCapture())
        view = capture(source)
        _, first = entry.prepare_captured(view, world=source, wait=Wait(), resolve_ctx=ResolveContext())
        _, second = entry.prepare_captured(view, world=source, wait=Wait(), resolve_ctx=ResolveContext())
        self.assertIsNot(first.landcover, second.landcover)
        self.assertIsNot(first.landcover.context, second.landcover.context)
        old_snapshot = {"region": StateSnapshotEntry("forest")}
        new_snapshot = {"region": StateSnapshotEntry("plains", tombstone=True)}
        old_inputs = prepare_landcover_inputs(first, old_snapshot)
        new_inputs = prepare_landcover_inputs(first, new_snapshot)
        self.assertIs(old_inputs.state_snapshot, old_snapshot)
        self.assertIs(new_inputs.state_snapshot, new_snapshot)
        self.assertIs(old_inputs.facts_at.__self__, first.landcover)
        self.assertIs(new_inputs.facts_at.__self__, first.landcover)

    async def test_detailed_entry_and_queue_reuse_bundle_and_persist_identical_columns(self):
        import tempfile
        from pathlib import Path
        from app.application.worldData.materialize.surface.materializationContext import MaterializationContext
        from app.application.worldData.materialize.terrain.terrainBatchOrchestrator import TerrainBatchOrchestrator
        from app.application.worldData.generators.terrain.types import ColumnRect
        from app.application.worldData.pack.bake.detailed.detailedBakeRefine import refine_detailed_tiles
        from app.application.worldData.pack.bake.detailed.detailedBakeScope import DetailedScopePlan
        from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
        from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
        from app.application.worldData.pack.refine.fine.chunk.fineChunkRunner import FineChunkRunner
        from app.application.worldData.pack.refine.fine.fineScenePathRefine import FineScenePathRefine
        from app.application.worldData.pack.refine.fine.fineRectDrain import FineRectDrain
        from app.application.worldData.pack.refine.entry.entryRefineOrchestrator import EntryRefineOrchestrator
        from app.application.worldData.pack.refine.chunks.chunkRefineQueue import ChunkRefineQueue
        from app.application.worldData.pack.refine.chunks.chunkRefineWorker import ChunkRefineWorker
        source = world(world_bounds=dict(x_min=0, x_max=0, y_min=0, y_max=0), z_min=-2, z_max=10, terrain_chunk_columns=2, fine_cells_per_map_cell=2)
        source.map_settings = {"global_cell_size_m": 2}
        c = Composition()
        self.addCleanup(c.service.shutdown)
        bundle = c.prepare(capture(source))
        working = working_fixture(source, bundle)
        terrain = TerrainBatchOrchestrator()
        runner = FineChunkRunner(terrain)
        scene_path = FineScenePathRefine(terrain, runner=runner)
        refiner = FineRectDrain(terrain, runner=runner)
        entry = EntryRefineOrchestrator(scene_path, refiner)
        rect = ColumnRect(0, 1, 0, 1)
        plan = DetailedScopePlan([(0, 0)], lambda gx, gy: [rect], [], "background", None, None)
        mat = MaterializationContext(1)
        with tempfile.TemporaryDirectory() as tmp:
            paths = WorldPackPaths.from_db_parent(str(Path(tmp) / "test.db"), source.world_uid)
            writer = WorldPackWriter(paths)
            WorldMapBakeOrchestrator().bake_tiles(source, [], writer, [(0, 0)],
                surface_bundle=bundle, wait=Wait(), region_state_snapshot={}, working=working)
            with patch.object(c.assembler, "prepare", side_effect=AssertionError("second planning")), patch(
                    "app.application.worldData.planning.composition.surfacePlanningCapture.SurfacePlanningCapture.capture",
                    side_effect=AssertionError("second capture")), patch(
                    "app.application.worldData.planning.composition.surfacePlanningAssembler.to_legacy_context",
                    side_effect=AssertionError("legacy L2 view")):
                detailed = await refine_detailed_tiles(runner, source, [], writer, mat, bundle, plan, region_state_snapshot={}, working=working)
                # Compare the decoded wire: the writer may choose a codec filename per layout.
                from app.application.worldData.pack.io.worldPackReader import WorldPackReader
                reader = WorldPackReader(paths)
                expected = reader.read_wilderness_chunk(0, 0, 0, 0)
                self.assertTrue(expected.columns)
                # Cold writer forces parent decode from the baked blob.
                cold = WorldPackWriter(paths)
                result = await refiner.refine_queued_chunk(source, [], cold, mat, bundle, 0, 0, 0, 0, region_state_snapshot={}, working=working)
                self.assertEqual(result.fine_surface_z, detailed.fine_surface_z)
                self.assertEqual(reader.read_wilderness_chunk(0, 0, 0, 0), expected)
                await entry.refine_from_entry(source.world_uid, source, [], cold, mat, bundle,
                    kind="session_start", anchor_x=0, anchor_y=0,
                    region_state_snapshot={}, working=working)
                self.assertEqual(reader.read_wilderness_chunk(0, 0, 0, 0), expected)
                queue = ChunkRefineQueue()
                queue.enqueue_chunk(0, 0, 0, 0, anchor_x=0, anchor_y=0, chunk_columns=2, tile_macro=2)
                worker = ChunkRefineWorker(refiner)
                self.assertEqual(await worker.drain_queue(source.world_uid, source, [], cold, mat, bundle, queue, region_state_snapshot={}, working=working), (1, 0))
                self.assertEqual(reader.read_wilderness_chunk(0, 0, 0, 0), expected)
                from types import SimpleNamespace
                from unittest.mock import AsyncMock
                jobs = Mock()
                jobs.pop_next_pending = AsyncMock(return_value=SimpleNamespace(
                    gx=0, gy=0, cx=0, cy=0, job_uid="persisted-job"))
                jobs.mark_complete = AsyncMock()
                persisted = ChunkRefineWorker(refiner, job_repo=jobs)
                self.assertEqual(await persisted.drain_persisted(source.world_uid, source, [], cold,
                    mat, bundle, region_state_snapshot={}, max_jobs=1, working=working), 1)
                jobs.mark_complete.assert_awaited_once_with("persisted-job")
                self.assertEqual(reader.read_wilderness_chunk(0, 0, 0, 0), expected)


    async def test_climate_bundle_preserves_coarse_and_fine_wire_baseline(self):
        from app.application.worldData.materialize.surface.materializationContext import MaterializationContext
        from app.application.worldData.pack.climate.climatePackBakeOrchestrator import ClimatePackBakeOrchestrator
        from app.application.worldData.pack.climate.climateCoarseBake import build_climate_coarse_wire, build_climate_tile_wire, sample_climate_tile_ty_rows
        from app.dataModel.worldPack.wire.parentLightTile import ParentLightTile
        from app.dataModel.worldPack.wire.worldMapCellWire import WorldMapCellWire
        source = world(world_bounds=dict(x_min=0, x_max=2, y_min=0, y_max=0), fine_cells_per_map_cell=2)
        c = Composition()
        self.addCleanup(c.service.shutdown)
        bundle = c.prepare(capture(source))
        legacy = to_legacy_context(bundle, working=working_fixture(source, bundle))
        parent = ParentLightTile.from_cells(world_uid=source.world_uid, gx=0, gy=0, side=2, tile_macro=2,
            cells=[WorldMapCellWire(tx=x, ty=y, surface_z=x+y) for x in range(2) for y in range(2)])
        expected_coarse = build_climate_coarse_wire(source, legacy.pole_field, legacy.coarse_hm.bbox,
            local_field=legacy.local_field, coarse_surface_z=legacy.coarse_surface_z)
        expected_fine = build_climate_tile_wire(source, legacy.pole_field, 0, 0,
            local_field=legacy.local_field, coarse_surface_z=legacy.coarse_surface_z,
            fine_z_overrides=legacy.fine_z_overrides, parent_light=parent)
        writer = Mock()
        writer.write_climate_coarse.return_value = "hash"
        climate = ClimatePackBakeOrchestrator()
        with patch("app.application.worldData.planning.composition.surfacePlanningAssembler.to_legacy_context",
                   side_effect=AssertionError("legacy climate view")), patch(
                   "app.application.worldData.pack.climate.climatePackBakeOrchestrator.sample_climate_tile_ty_rows",
                   wraps=sample_climate_tile_ty_rows) as sample_rows:
            await climate.bake_coarse(source, bundle, writer, MaterializationContext(1), working=working_fixture(source, bundle))
            await climate.bake_fine_tile(source, bundle, writer, MaterializationContext(1), 0, 0, parent_light=parent, working=working_fixture(source, bundle))
        self.assertEqual(writer.write_climate_coarse.call_args.args[0], expected_coarse)
        self.assertEqual(writer.write_climate_tile.call_args.args[2], expected_fine)
        self.assertEqual(set(sample_rows.call_args.kwargs["coarse_surface_z"]), {(0, 0)})
