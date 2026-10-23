"""PC-9A: exercise the real bindings and all eight phases through one service."""

from copy import deepcopy
from dataclasses import fields
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

    def test_no_extent_has_no_provider_calls(self):
        view = capture(world(world_bounds=None))
        with patch.object(self.c.service, "get_or_build") as builds:
            self.assertIsNone(self.c.prepare(view))
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
