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
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler, to_legacy_context
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import SurfaceTerrainContext
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

    def test_stable_revision_and_all_ref_vectors_survive_boundary_refactor(self):
        # Captured before the review refactor: module moves and field metadata
        # must preserve the existing canonical protocol, not silently flush cache keys.
        self.assertEqual(self.view.revision.hex(), "941978fd04c928948688581205aa70994d8f8e3664309f8237b5fbe903239a74")
        expected = (
            ("2736f4721825436d4d5a71afb945c11a3d5ec38b9c584e3c83447ca55206bfda", "cc69edceb54a048ed0dc8d9d23ce91c50c6cbc479eb482db4b544b9e5d897b56"),
            ("ec3a2ce38373b90dec09f218afeec38850c61fea6837723b5e8b9361e9da68ae", "2e7db55f89e7216f563e52c6de0afcfc90968385439f7a625966aeb3dbbedfc3"),
            ("40fe4e14d54833a3b5a6c1e1b2d3edc9ff3b0abec79e76e46526cd18d61f0a06", "9955b899ff7c63f5c45d83d0366e20bc8baf776950ba5a4a4036defff1d91f98"),
            ("daaf5e8f0220f444fcdad645fa5059f46eb1c322865ee14a619a5f72db346ae8", "6384630059a8e4421cc4666db5df6b6aba72139ff3e63ed91ea4a08dd2ff72ef"),
            ("ff195f6f5a9718d3ecf382a2259e5688d32e72b4ff191f2f3a8e31cd6d00d4f1", "b6dd7fc700459983782f425273fc0ff37fa28405d403f94cfde6c51abd338fee"),
            ("63e1c98f05c7d74324bc024c9c3dd99e2562f5f54c289ede2d1c02504f47790b", "7aa08c792103739f7412e8edf98c0e0910a7afbefafe217a90d1ef3d1cd91900"),
            ("475e525e49541f26351c53e4ab14c56c164b4f1ebe9808de9345cf238457c23a", "9a645e15fc8f589c5ed10001f552dc163210a5eb36d8e6bfef8f8b912e7cc58e"),
            ("8e0fa4e0b33e098a12ca1efec42aae390b2554465486a7b758f22394226d3737", "3a2412011c3c3998abb74ee5e66182bb5d7ca9eb4c99dddc37c585646a50e333"))
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

    def test_legacy_public_type_identity_and_eight_fields(self):
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import SurfaceTerrainContext as Old
        self.assertIs(Old, SurfaceTerrainContext)
        self.assertEqual(len(fields(Old)), 8)

    def test_legacy_copies_cannot_change_cached_payload_or_other_views(self):
        bundle = self.c.prepare(self.view)
        first, second = to_legacy_context(bundle), to_legacy_context(bundle)
        saved = deepcopy(second)
        for field in ("coarse_hydro", "sparse_fine_hydro", "fine_z_overrides", "coarse_relief_z", "coarse_surface_z"):
            getattr(first, field).clear()
        first.coarse_hm.surface_z.clear()
        self.assertEqual(second, saved)
        self.assertEqual(to_legacy_context(self.c.prepare(self.view)), saved)
        self.assertIsNot(second.coarse_hm.surface_z, second.coarse_surface_z)
        self.assertEqual(second.coarse_relief_z,
            {(cell.gx, cell.gy): z for cell, z in bundle.terrain_base.payload.surface_z})

    def test_legacy_no_hydrology_baseline(self):
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import prepare_surface_terrain_context
        source = world()
        self.assertEqual(to_legacy_context(self.c.prepare(capture(source))), prepare_surface_terrain_context(source, []))

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
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import prepare_surface_terrain_context
        legacy = prepare_surface_terrain_context(source, [])
        self.assertEqual(to_legacy_context(bundle).coarse_surface_z, legacy.coarse_surface_z)
        for cell, role in bundle.hydrology.payload.coarse_hydro:
            self.assertEqual(role, legacy.coarse_hydro[(cell.gx, cell.gy)])

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


if __name__ == "__main__":
    unittest.main()
