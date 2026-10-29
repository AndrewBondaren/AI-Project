"""PC-9A: exercise the real bindings and all eight phases through one service."""

from copy import deepcopy
from dataclasses import fields, replace
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.service.cacheService import CacheService
from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.providers.planRegistry import PlanRegistry
from app.application.planning.service.planningService import PlanningService
from app.application.worldData.planning.composition.planProviders import register_world_plan_providers
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.db.models.world import World


class Wait:
    def raise_if_cancelled(self):
        pass

    def remaining_seconds(self):
        return 30.0


def world(**overrides):
    values = dict(world_uid="surface-world", name="surface", created_at="",
        world_bounds=dict(x_min=0, x_max=2, y_min=0, y_max=2), world_map_cells_per_tile=2,
        hydrology={"enabled": False}, terrain_masks={"enabled": False})
    values.update(overrides)
    return World(**values)


def capture(source, *, locations=(), mode=ResolutionMode.RUNTIME, templates=(), ctx=None):
    return SurfacePlanningCapture().capture(source, locations, mode=mode,
        mountain_templates=templates, resolve_ctx=ctx or ResolveContext(
            collect_only=True, validate_only=mode is ResolutionMode.VALIDATE_ONLY))


class Composition:
    def __init__(self, workers=2):
        policy = CachePolicy(max_retained_bytes=10000000, max_entry_bytes=5000000)
        self.backend = MemoryCache(policy)
        self.registry = PlanRegistry()
        self.handles = register_world_plan_providers(self.registry)
        self.service = PlanningService(self.registry, CacheService(self.backend, policy),
            PlanningExecutionPolicy(max_workers=workers, max_pending_builds=8))
        self.assembler = SurfacePlanningAssembler(self.service, self.registry, self.handles)

    def prepare(self, view):
        return self.assembler.prepare(view, wait=Wait())


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.c = Composition()
        self.addCleanup(self.c.service.shutdown)
        self.view = capture(world())

    def test_real_container_surface_lifetime_and_shutdown(self):
        from concurrent.futures import ThreadPoolExecutor
        from app.core.appSettings import app_settings
        from app.core.container import Container
        from tests.cache.test_admission import configured
        from app.application.cancellation.requestPlanWait import RequestPlanWait
        with patch.object(app_settings, "planning", configured()):
            container = Container(None, None)
            self.addCleanup(container.shutdown_planning)
            with ThreadPoolExecutor(max_workers=4) as pool:
                assemblers = list(pool.map(lambda _: container.surface_planning(), range(12)))
            self.assertTrue(all(item is assemblers[0] for item in assemblers))
            self.assertIs(container.surface_planning_capture(), container.surface_planning_capture())
            self.assertIs(container.source_publication_guard(), container.source_publication_guard())
            bundle = assemblers[0].prepare(self.view, wait=RequestPlanWait.unbounded())
            self.assertEqual(bundle, self.c.prepare(self.view))
            container.shutdown_planning()
            from app.application.planning.service.planningService import PlanWaitCancelled
            with self.assertRaises(PlanWaitCancelled):
                assemblers[0].prepare(self.view, wait=RequestPlanWait.unbounded())

    def test_production_domains_share_backend_and_rebuild_after_clear_restart_and_edit(self):
        from app.core.appSettings import app_settings
        from app.core.container import Container
        from app.dataModel.planning.policy.planningRuntimeSettings import PlanningRuntimeSettings
        from app.dataModel.surfacePlanning.surfacePlanBindings import PC_SURFACE_BINDINGS

        source = world()
        outputs = []
        for workers in (1, 4):
            resources = PlanningRuntimeSettings(
                cache=CachePolicy(max_retained_bytes=10000000, max_entry_bytes=5000000),
                execution=PlanningExecutionPolicy(max_workers=workers, max_pending_builds=8))
            with self.subTest(workers=workers), patch.object(app_settings, "planning", resources):
                container = Container(None, None)
                self.addCleanup(container.shutdown_planning)
                entry = container.surface_planning_entry()
                backend = container.planning_memory_cache()
                registry = container.plan_registry()
                with patch.object(backend, "put", wraps=backend.put) as puts:
                    first, _ = entry.require_plan_inputs(source, [], wait=Wait())
                self.assertEqual({str(call.args[0].key.contract.id) for call in puts.call_args_list},
                    {str(binding.cache_id) for binding in PC_SURFACE_BINDINGS})
                self.assertEqual(puts.call_count, 8)
                self.assertGreater(backend.retained_bytes, 0)
                with patch.object(registry, "build", wraps=registry.build) as builds:
                    hit, _ = entry.require_plan_inputs(source, [], wait=Wait())
                builds.assert_not_called()
                self.assertEqual(first, hit)
                # No invalidation: authoritative input revision must select new keys.
                edited_source = replace(source, hydrology={"enabled": False,
                    "default_rivers": {"channel_depth_cells": 7}})
                with patch.object(registry, "build", wraps=registry.build) as builds:
                    edited, _ = entry.require_plan_inputs(edited_source, [], wait=Wait())
                self.assertEqual([str(call.args[0].metadata.id) for call in builds.call_args_list],
                    ["surface.pc." + slot for slot in
                        ("hydrology_routes", "river_relief", "hydrology", "climate_local")])
                self.assertNotEqual(first.view_revision, edited.view_revision)
                backend.clear()
                self.assertEqual(backend.retained_bytes, 0)
                rebuilt, _ = entry.require_plan_inputs(source, [], wait=Wait())
                self.assertEqual(first, rebuilt)
                outputs.append(first)
                container.shutdown_planning()
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[0], outputs[1])

    def test_entry_requires_wait_and_retains_no_extent_semantics(self):
        source = world(world_bounds=None)
        entry = SurfacePlanningEntry(self.c.assembler, SurfacePlanningCapture())
        with self.assertRaises(TypeError):
            entry.require_plan_inputs(source, [])
        view = capture(source)
        with patch.object(self.c.registry, "build", wraps=self.c.registry.build) as builds:
            self.assertIsNone(entry.prepare_captured(view, world=source, wait=Wait(),
                resolve_ctx=ResolveContext(collect_only=True)))
            with self.assertRaisesRegex(ValueError, "unavailable"):
                entry.require_plan_inputs(source, [], wait=Wait())
        builds.assert_not_called()

    def test_entry_diagnostics_are_replayed_once_on_hit_and_miss(self):
        from app.application.jsonValidation.resolve import UnresolvedModelError
        source = world(default_climate_zone="custom")
        entry = SurfacePlanningEntry(self.c.assembler, SurfacePlanningCapture())
        first, second = ResolveContext(collect_only=True), ResolveContext(collect_only=True)
        entry.require_plan_inputs(source, [], resolve_ctx=first, wait=Wait())
        with patch.object(self.c.registry, "build", wraps=self.c.registry.build) as builds:
            entry.require_plan_inputs(source, [], resolve_ctx=second, wait=Wait())
        builds.assert_not_called()
        self.assertTrue(first.errors)
        self.assertEqual(first.errors, second.errors)
        self.assertEqual(len(first.errors), len(set(first.errors)))
        with self.assertRaises(UnresolvedModelError):
            entry.require_plan_inputs(source, [], resolve_ctx=ResolveContext(validate_only=True), wait=Wait())

    def test_eight_real_registrations_and_explicit_phase_order(self):
        with patch.object(self.c.registry, "build", wraps=self.c.registry.build) as builds:
            bundle = self.c.prepare(self.view)
        expected = [slot.value for slot in (SurfacePlanSlot.CLIMATE_BASE, SurfacePlanSlot.TERRAIN_BASE,
            SurfacePlanSlot.WATER_PLACEMENT, SurfacePlanSlot.RELIEF, SurfacePlanSlot.HYDROLOGY_ROUTES,
            SurfacePlanSlot.RIVER_RELIEF, SurfacePlanSlot.HYDROLOGY, SurfacePlanSlot.CLIMATE_LOCAL)]
        self.assertEqual([call.args[0].metadata.id for call in builds.call_args_list],
            ["surface.pc." + name for name in expected])
        self.assertEqual(len(fields(self.c.handles)), 8)
        self.assertEqual(bundle.hydrology.payload.coarse_surface_z, bundle.river_relief.payload.surface_z)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            register_world_plan_providers(self.c.registry)

    def test_hit_returns_same_bundle_without_rebuilding(self):
        first = self.c.prepare(self.view)
        with patch.object(self.c.registry, "build", wraps=self.c.registry.build) as builds:
            second = self.c.prepare(self.view)
        self.assertEqual(first, second)
        builds.assert_not_called()

    def test_declaration_version_and_id_edits_reach_wiring_and_bundle_together(self):
        from app.dataModel.surfacePlanning import surfacePlanBindings as declarations
        from app.dataModel.planning.identity.planKey import AlgorithmVersion
        from app.dataModel.registryKey import RegistryKey
        from app.dataModel.planning.contracts.planContract import PlanContractRegistry
        old = self.c.prepare(self.view)
        records = tuple(replace(item, metadata=item.metadata.model_copy(update={
            "id": RegistryKey[PlanContractRegistry]("surface.test.climate_base"),
            "algorithm_version": AlgorithmVersion(2)}))
            if item.slot is SurfacePlanSlot.CLIMATE_BASE else item for item in declarations.PC_SURFACE_BINDINGS)
        with patch.object(declarations, "PC_SURFACE_BINDINGS", records):
            changed = Composition()
            try:
                bundle = changed.prepare(self.view)
                self.assertEqual(bundle.climate_base.ref.key.algorithm_version, 2)
                self.assertEqual(bundle.climate_base.ref.key.contract_id, "surface.test.climate_base")
                self.assertEqual(changed.handles.terrain_base.dependency_contracts[0].algorithm_version, 2)
                with self.assertRaisesRegex(ValueError, "phase/version"):
                    SurfacePlanBundle.model_validate(old)
            finally:
                changed.service.shutdown()

    def test_graph_edit_is_consumed_by_binding_and_bundle_validator(self):
        from app.dataModel.surfacePlanning import surfacePlanBindings as declarations
        records = tuple(replace(item, upstream=()) if item.slot is SurfacePlanSlot.CLIMATE_LOCAL else item
            for item in declarations.PC_SURFACE_BINDINGS)
        original = self.c.prepare(self.view)
        edited = original.model_copy(update={"climate_local": original.climate_local.model_copy(update={"dependencies": ()})})
        with patch.object(declarations, "PC_SURFACE_BINDINGS", records):
            changed = Composition()
            try:
                self.assertEqual(changed.handles.climate_local.dependency_contracts, ())
                self.assertEqual(SurfacePlanBundle.model_validate(edited).climate_local.dependencies, ())
                with self.assertRaisesRegex(ValueError, "incoherent"):
                    SurfacePlanBundle.model_validate(original)
            finally:
                changed.service.shutdown()

    def test_g9_schema2_revision_and_all_ref_vectors_are_stable(self):
        # G9 schema2 baseline. Climate/terrain vectors remain unchanged;
        # water schema invalidates dependent refs. The earlier capture vector
        # already predates source changes, independently of the version bump.
        self.assertEqual(self.view.revision.hex(), "d6417ff3e790c5719f177098e6be783cc8c8e1f882ba47d621c0e6163065191b")
        expected = (
            ("2736f4721825436d4d5a71afb945c11a3d5ec38b9c584e3c83447ca55206bfda", "cc69edceb54a048ed0dc8d9d23ce91c50c6cbc479eb482db4b544b9e5d897b56"),
            ("ec3a2ce38373b90dec09f218afeec38850c61fea6837723b5e8b9361e9da68ae", "2e7db55f89e7216f563e52c6de0afcfc90968385439f7a625966aeb3dbbedfc3"),
            ("feed1f959a66e9357304ede8ad2094ef81988e4b4b6dc255fa4f823f718bc7c7", "9955b899ff7c63f5c45d83d0366e20bc8baf776950ba5a4a4036defff1d91f98"),
            ("5339912b9a092b0f19355f5510f2c6ddd1aeaf207771f6468738a8ea30937713", "5f68ab60cb413762cf26286e2c920bbea3a20a77e1c17f656549d01b9fafe62e"),
            ("44dea72065ae06bd9b42a4cec411dc02f107dbf15f2762477baf0b9c08c7e55d", "5ef9b42acd67ab80316e99c12791a3d334589e65972787a6c00d8f718d613b1d"),
            ("d757fa93b3729f824230b97c6bdae02c80e532b0f43a3048bcc2be24ee5302d5", "ee6364af02c53a700c8f71010fb64c6909902883f92afe0a70f4708ccc7ed23a"),
            ("6692b5d795ba6912e38676793830a6614921108a50a99ef45d46546e2fe4f2ee", "c44632b829b682fd2d753805b31e7d9529ff1d850e1f3ef5c18de5e6ea99b32f"),
            ("1d61f81c97abbd0e825a7997f7131f9f71b6a7052b9729337ab3ff3b61f77c8a", "885982c153c4154b2eddb8c4ff75c6c9ea488a3853a8bbd2ba92c5f9eb0acd08"),
        )
        bundle = self.c.prepare(self.view)
        actual = tuple((ref.key.input_fingerprint.hex(), ref.output_fingerprint.hex())
            for field in fields(self.c.handles) for ref in (getattr(bundle, field.name).ref,))
        self.assertEqual(actual, expected)

    def test_no_extent_has_no_provider_calls(self):
        view = capture(world(world_bounds=None))
        with patch.object(self.c.service, "get_or_build") as builds:
            self.assertIsNone(self.c.prepare(view))
        builds.assert_not_called()

    def test_constructed_or_copied_invalid_view_is_revalidated_before_any_build(self):
        changed_grid = self.view.hydrology_final.grid.model_copy(update={"fine_span": 123})
        changed_final = self.view.hydrology_final.model_copy(update={"grid": changed_grid})
        invalid = self.view.model_copy(update={"hydrology_final": changed_final})
        with patch.object(self.c.registry, "build", wraps=self.c.registry.build) as builds:
            with self.assertRaises(ValidationError):
                self.c.prepare(invalid)
        builds.assert_not_called()

    def test_removed_legacy_entry_modules_have_no_compatibility_shims(self):
        from pathlib import Path
        app = Path(__file__).resolve().parents[3] / "app"
        for path in ("application/worldData/generators/terrain/passes/surfaceTerrainContext.py",
                     "application/worldData/planning/legacy/surfaceTerrainContext.py"):
            self.assertFalse((app / path).exists(), path)

    def test_working_views_cannot_change_cached_payload_or_other_requests(self):
        bundle = self.c.prepare(self.view)
        saved = deepcopy(bundle)
        first = working_fixture(world(), bundle)
        second = working_fixture(world(), bundle)
        for mapping in (first.hydrology.coarse_hydro, first.hydrology.sparse_fine_hydro,
                        first.hydrology.fine_z_overrides, first.terrain.relief_z,
                        first.hydrology.coarse_surface_z):
            with self.assertRaises(TypeError):
                mapping[(0, 0)] = 7
        self.assertEqual(bundle, saved)
        self.assertEqual(second.hydrology.coarse_surface_z, first.hydrology.coarse_surface_z)
        self.assertEqual(second.terrain.relief_z,
            {(cell.gx, cell.gy): z for cell, z in bundle.terrain_base.payload.surface_z})

    def test_typed_no_hydrology_baseline(self):
        source = world()
        bundle, working = SurfacePlanningEntry(self.c.assembler, SurfacePlanningCapture()).require_plan_inputs(
            source, [], wait=Wait())
        self.assertEqual(working.hydrology.coarse_surface_z,
            {(cell.gx, cell.gy): z for cell, z in bundle.hydrology.payload.coarse_surface_z})
        self.assertEqual(working.hydrology.coarse_hydro, {})

    def test_bundle_rejects_mixed_world_phase_and_exact_ref(self):
        bundle = self.c.prepare(self.view)
        other = self.c.prepare(capture(world(world_uid="other")))
        for update in ({"world_uid": "other"}, {"hydrology": other.hydrology},
                       {"hydrology": bundle.hydrology_routes}):
            with self.subTest(update=tuple(update)), self.assertRaises(ValidationError):
                SurfacePlanBundle.model_validate(bundle.model_copy(update=update))
        changed = self.c.prepare(capture(world(climate_pole_preset="ice")))
        with self.assertRaisesRegex(ValueError, "incoherent"):
            SurfacePlanBundle.model_validate(bundle.model_copy(update={"climate_base": changed.climate_base}))

    def test_codecs_round_trip_every_envelope_and_reject_corruption(self):
        bundle = self.c.prepare(self.view)
        for field in fields(self.c.handles):
            binding = getattr(self.c.handles, field.name)
            codec = binding.cache_binding.codec
            envelope = getattr(bundle, field.name)
            encoded = codec.encode(envelope)
            self.assertEqual(codec.decode(encoded), envelope)
            with self.assertRaises(ValueError):
                codec.decode(encoded + b"x")

    def test_declared_basin_full_chain_and_old_new_geometry(self):
        source = world(z_min=-100, hydrology={"enabled": True,
            "default_lakes": {"autoresolve": False},
            "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
            "declared_basins": [{"location_uid": "basin", "kind": "ocean", "floor_z": -10,
                "footprint": {"kind": "bbox", "x_min": 0, "x_max": 3000, "y_min": 0, "y_max": 3000}}]})
        bundle = self.c.prepare(capture(source))
        self.assertTrue(bundle.water_placement.payload.basin_specs)
        self.assertTrue(bundle.hydrology.payload.water_bodies)
        self.assertTrue(bundle.hydrology.payload.coarse_hydro)
        working = working_fixture(source, bundle)
        self.assertEqual(working.hydrology.coarse_surface_z,
            {(cell.gx, cell.gy): z for cell, z in bundle.hydrology.payload.coarse_surface_z})
        for cell, role in bundle.hydrology.payload.coarse_hydro:
            self.assertEqual(role, working.hydrology.coarse_hydro[(cell.gx, cell.gy)])

    def test_accepted_river_crosses_route_bed_final_chain_in_both_spaces(self):
        source = world(world_bounds=dict(x_min=0, x_max=3, y_min=0, y_max=2),
            world_topology_mode="planar", z_min=-100, z_max=1, hydrology={"enabled": True,
                "default_seas": {"autoresolve_coastal_sea": False, "autoresolve_open_ocean": False},
                "default_lakes": {"autoresolve": False},
                "default_rivers": {"autoresolve": False, "mouth_search_radius_fine": 0},
                "declared_basins": [{"location_uid": "basin", "kind": "ocean", "floor_z": -10,
                    "footprint": {"kind": "bbox", "x_min": 0, "x_max": 10, "y_min": 0, "y_max": 20}}],
                "declared_rivers": [{"location_uid": "river", "declare_mode": "segments", "segments": [
                    {"from": {"x": 35, "y": 5}, "to": {"x": 5, "y": 5},
                     "connection_type": "river", "width_cells": 2}]}]})
        source.map_settings = {"global_cell_size_m": 10}
        view = capture(source)
        bundle = self.c.prepare(view)
        self.assertTrue(bundle.hydrology_routes.payload.coarse_routes)
        self.assertTrue(bundle.hydrology_routes.payload.fine_routes)
        self.assertTrue(bundle.river_relief.payload.coarse_beds)
        self.assertTrue(bundle.river_relief.payload.fine_beds)
        self.assertTrue(bundle.hydrology.payload.fine_z_overrides)
        for name in ("hydrology_routes", "river_relief", "hydrology"):
            codec = getattr(self.c.handles, name).cache_binding.codec
            envelope = getattr(bundle, name)
            self.assertEqual(codec.decode(codec.encode(envelope)), envelope)
        self.assertEqual(bundle, self.c.prepare(view))


class WorkingFieldsTests(unittest.TestCase):
    """PC-11.2a: request lifetime, concurrent profile access, readonly projections."""

    def setUp(self):
        from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
        self.c = Composition()
        self.addCleanup(self.c.service.shutdown)
        self.source = world()
        self.view = capture(self.source)
        self.entry = SurfacePlanningEntry(self.c.assembler, SurfacePlanningCapture())

    def prepared(self):
        return self.entry.prepare_captured(self.view, world=self.source,
            wait=Wait(), resolve_ctx=ResolveContext(collect_only=True))

    def test_request_factories_once_and_cache_hit_gets_new_views(self):
        from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
        from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
        from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
        with patch.object(ClimateWorkingFields, "from_plans", wraps=ClimateWorkingFields.from_plans) as climate, \
             patch.object(TerrainWorkingFields, "from_plan", wraps=TerrainWorkingFields.from_plan) as terrain, \
             patch.object(HydrologyWorkingFields, "from_plan", wraps=HydrologyWorkingFields.from_plan) as hydro:
            bundle, working = self.prepared()
            for x, y in ((0, 0), (1, 0), (2, 2)):
                self.assertIs(working.hydrology.fine_z_for_tile(x, y),
                              working.hydrology.fine_z_for_tile(x, y))
            self.assertEqual((climate.call_count, terrain.call_count, hydro.call_count), (1, 1, 1))
        with patch.object(self.c.registry, "build", side_effect=AssertionError("HIT rebuilt")):
            cached, other = self.prepared()
        self.assertEqual(bundle, cached)
        for name in ("climate", "terrain", "hydrology"):
            self.assertIsNot(getattr(working, name), getattr(other, name))
        self.assertIsNot(working.climate._lock, other.climate._lock)
        self.assertEqual(working.terrain.relief_z,
                         {(cell.gx, cell.gy): z for cell, z in bundle.terrain_base.payload.surface_z})
        self.assertEqual(working.hydrology.coarse_surface_z,
                         {(cell.gx, cell.gy): z for cell, z in bundle.hydrology.payload.coarse_surface_z})
        from dataclasses import FrozenInstanceError
        with self.assertRaises(FrozenInstanceError):
            working.climate = other.climate
        with self.assertRaises(TypeError):
            working.terrain.relief_z[(0, 0)] = 100
        with self.assertRaises(TypeError):
            working.hydrology.coarse_surface_z[(0, 0)] = 100

    def test_profile_memo_concurrent_frozen_hit_failure_retry_and_request_isolation(self):
        from concurrent.futures import ThreadPoolExecutor
        from time import sleep
        from unittest.mock import Mock
        from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
        from app.dataModel.climate.enums.climateZone import ClimateZone
        from app.dataModel.registryKey import RegistryKey
        from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
        bundle, _ = self.prepared()
        key = RegistryKey[WorldClimateZoneRegistry]("request-custom")
        first, second = ClimateZone.TEMPERATE.to_profile(), ClimateZone.ARCTIC.to_profile()

        def resolve(zone):
            self.assertEqual(zone, key)
            sleep(.01)
            return first

        resolver = Mock(side_effect=resolve)
        working = ClimateWorkingFields.from_plans(bundle.climate_base.payload,
            bundle.climate_local.payload, resolver)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(working.profile_for_key, [key] * 32))
        self.assertTrue(all(value is first for value in results))
        resolver.assert_called_once_with(key)
        default_key = bundle.climate_base.payload.default_zone
        with ThreadPoolExecutor(max_workers=8) as pool:
            frozen = list(pool.map(working.profile_for_key, [default_key] * 32))
        self.assertTrue(all(value is frozen[0] for value in frozen))
        resolver.assert_called_once()
        retry_resolver = Mock(side_effect=[RuntimeError("failed lookup"), second])
        retry = ClimateWorkingFields.from_plans(bundle.climate_base.payload,
            bundle.climate_local.payload, retry_resolver)
        with self.assertRaisesRegex(RuntimeError, "failed lookup"):
            retry.profile_for_key(key)
        self.assertIs(retry.profile_for_key(key), second)
        self.assertIs(retry.profile_for_key(key), second)
        self.assertEqual(retry_resolver.call_count, 2)
        self.assertIs(working.profile_for_key(key), first)
        different = RegistryKey[WorldClimateZoneRegistry]("another-custom")
        other_resolver = Mock(return_value=second)
        other = ClimateWorkingFields.from_plans(bundle.climate_base.payload,
            bundle.climate_local.payload, other_resolver)
        self.assertIs(other.profile_for_key(different), second)
        other_resolver.assert_called_once_with(different)

    def test_prepared_pole_sampler_matches_live_adapter_and_frozen_sampler(self):
        from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
        bundle, working = self.prepared()
        with patch("app.application.worldData.generators.climate.registry.profile_for",
                   side_effect=AssertionError("frozen pole sampled live registry")):
            for x, y in ((0, 0), (1, 1), (-1, 2), (5, -2)):
                expected = ClimatePlanSampler.sample(bundle.climate_base.payload, x, y)
                self.assertEqual(working.climate.sample_pole(x, y), expected)
                self.assertEqual(working.climate.sample_pole(x, y),
                                 working.climate.pole_field.sample(self.source, x, y))

    def test_hydrology_tile_index_negative_boundaries_and_readonly_empty_maps(self):
        from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
        from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
        from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
        from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
        bundle, _ = self.prepared()
        points = ((-9, -1), (-8, -1), (-1, -1), (0, 0), (7, 0), (8, 0))
        water = MapCellHydrology(role=HydrologyCellRole.LAKE)
        plan = bundle.hydrology.payload.model_copy(update={
            "fine_z_overrides": tuple((point, index) for index, point in enumerate(points)),
            "sparse_fine_hydro": tuple((point, water) for point in points)})
        fields = HydrologyWorkingFields.from_plan(plan, SurfaceGridSettings(fine_span=8, light_side=2))
        with patch("app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields._tile_index",
                   side_effect=AssertionError("tile lookup rebuilt index")):
            for gx, gy in ((-2, -1), (-1, -1), (0, 0), (1, 0), (4, 4)):
                expected = {point: index for index, point in enumerate(points)
                            if (point[0] // 8, point[1] // 8) == (gx, gy)}
                self.assertEqual(fields.fine_z_for_tile(gx, gy), expected)
                self.assertEqual(set(fields.fine_hydro_for_tile(gx, gy)), set(expected))
                with self.assertRaises(TypeError):
                    fields.fine_z_for_tile(gx, gy)[(100, 100)] = 7
                with self.assertRaises(TypeError):
                    fields.fine_hydro_for_tile(gx, gy)[(100, 100)] = water
        self.assertEqual(plan.fine_z_overrides, tuple((point, index) for index, point in enumerate(points)))

    def test_no_extent_probe_and_foreign_world_do_not_project(self):
        from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningViewKind
        from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
        view = capture(world(world_bounds=None))
        with patch.object(self.c.assembler, "prepare", wraps=self.c.assembler.prepare) as prepare, \
             patch.object(ClimateWorkingFields, "from_plans", side_effect=AssertionError("unexpected projection")):
            self.assertEqual(self.entry.extent_status(view), SurfacePlanningViewKind.NO_EXTENT)
            prepare.assert_not_called()
            self.assertIsNone(self.entry.prepare_captured(view, world=self.source,
                wait=Wait(), resolve_ctx=ResolveContext(collect_only=True)))
            prepare.assert_called_once()
            with self.assertRaisesRegex(ValueError, "another world"):
                self.entry.prepare_captured(self.view, world=world(world_uid="foreign-world"),
                    wait=Wait(), resolve_ctx=ResolveContext(collect_only=True))
            prepare.assert_called_once()


if __name__ == "__main__":
    unittest.main()


def planning_kwargs(test):
    """One planning lifetime per regression test; no process-global service."""
    composition = getattr(test, "_surface_composition", None)
    if composition is None:
        composition = Composition()
        test._surface_composition = composition
        test.addCleanup(composition.service.shutdown)
    from app.application.cancellation.requestPlanWait import RequestPlanWait
    return dict(planning=composition.assembler, capture=SurfacePlanningCapture(),
        wait=RequestPlanWait.unbounded())


def working_fixture(source, bundle):
    """Explicit request inputs for direct consumer tests; no process cache."""
    from functools import partial
    from app.application.worldData.generators.climate.materialize.climateWorkingFields import ClimateWorkingFields
    from app.application.worldData.generators.hydrology.materialize.hydrologyWorkingFields import HydrologyWorkingFields
    from app.application.worldData.generators.terrain.materialize.terrainWorkingFields import TerrainWorkingFields
    from app.application.worldData.generators.climate.registry import profile_for
    from app.application.worldData.generators.coordinates import map_cell_fine_span
    from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
    from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
    from app.dataModel.worldPack.wire.worldMapCellsPerTile import resolve_world_map_side
    from app.application.worldData.regions.inputs.landcoverInputs import LandcoverObservations
    grid = SurfaceGridSettings(fine_span=map_cell_fine_span(source),
                               light_side=resolve_world_map_side(source.world_map_cells_per_tile))
    climate = ClimateWorkingFields.from_plans(bundle.climate_base.payload, bundle.climate_local.payload,
        partial(profile_for, source))
    terrain = TerrainWorkingFields.from_plan(bundle.terrain_base.payload)
    hydrology = HydrologyWorkingFields.from_plan(bundle.hydrology.payload, grid)
    return SurfaceWorkingMaps(climate, terrain, hydrology,
        LandcoverObservations.from_views(bundle.water_placement.payload.topology, grid,
            climate, terrain, hydrology))
