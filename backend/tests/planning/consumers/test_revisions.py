"""Capture/source revisions and precise per-artifact dependency closure."""

from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.worldData.planning.guards.sourceRevision import require_current_source, SurfacePlanningStale
from app.application.worldData.planning.contracts.surfacePlanningView import ReadySurfacePlanningView
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.db.models.namedLocation import NamedLocation
from tests.planning.consumers.test_wiring import Composition, world, capture


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.c = Composition()
        self.addCleanup(self.c.service.shutdown)
        self.source = world()

    def rebuilds(self, initial, changed):
        self.c.prepare(initial)
        with patch.object(self.c.registry, "build", wraps=self.c.registry.build) as builds:
            result = self.c.prepare(changed)
        return result, [str(call.args[0].metadata.id) for call in builds.call_args_list]

    def test_ui_labels_ticks_and_timestamps_do_not_change_source_or_keys(self):
        first = capture(self.source)
        changed = capture(replace(self.source, name="renamed", current_tick=99, created_at="changed"))
        require_current_source(first, changed)
        _, builds = self.rebuilds(first, changed)
        self.assertEqual(builds, [])

    def test_execution_mode_changes_keys_but_not_authoritative_revision(self):
        first = capture(self.source)
        changed = capture(self.source, mode=ResolutionMode.VALIDATE_ONLY)
        self.assertEqual(first.revision, changed.revision)
        require_current_source(first, changed)
        result, builds = self.rebuilds(first, changed)
        self.assertEqual(builds, ["surface.pc." + slot for slot in (
            "water_placement", "relief", "hydrology_routes", "river_relief", "hydrology", "climate_local")])
        self.assertEqual(result.hydrology.payload, self.c.prepare(first).hydrology.payload)

    def test_river_depth_replans_exact_downstream_closure(self):
        first = capture(self.source)
        changed = capture(replace(self.source, hydrology={"enabled": False,
            "default_rivers": {"channel_depth_cells": 7}}))
        self.assertNotEqual(first.revision, changed.revision)
        _, builds = self.rebuilds(first, changed)
        self.assertEqual(builds, ["surface.pc." + slot for slot in (
            "hydrology_routes", "river_relief", "hydrology", "climate_local")])

    def test_template_edit_replans_relief_and_downstream_only(self):
        from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
        from app.dataModel.terrain.relief.enums import ReliefContext
        first = capture(self.source)
        changed = capture(self.source, templates=(MountainTemplateInput(
            template_uid="member", context=ReliefContext.MOUNTAIN, side_recipe=None),))
        _, builds = self.rebuilds(first, changed)
        self.assertNotEqual(first.revision, changed.revision)
        self.assertEqual(builds, ["surface.pc." + slot for slot in (
            "relief", "hydrology_routes", "river_relief", "hydrology", "climate_local")])

    def test_stale_guard_rejects_changed_projection_and_foreign_world(self):
        first = capture(self.source)
        for changed in (capture(replace(self.source, z_min=-200)), capture(replace(self.source, world_uid="other"))):
            with self.subTest(revision=changed.revision.hex()), self.assertRaises(SurfacePlanningStale) as error:
                require_current_source(first, changed)
            self.assertEqual(error.exception.expected, first.revision)
            self.assertEqual(error.exception.actual, changed.revision)

    def test_capture_is_frozen_and_has_no_source_mutation(self):
        original = deepcopy(self.source)
        view = capture(self.source)
        self.assertEqual(self.source, original)
        with self.assertRaises(ValidationError):
            view.world_uid = "mutated"
        with self.assertRaises(ValidationError):
            view.terrain_base.seed = 1
        self.source.hydrology["enabled"] = True
        self.assertFalse(view.hydrology.enabled)

    def test_manual_pole_order_is_preserved_but_hydro_anchor_order_is_canonical(self):
        def pole(uid, zone, x):
            return NamedLocation(location_uid=uid, world_uid=self.source.world_uid, display_name=uid, created_at="",
                system_location_type="climate_pole", system_climate_zone=zone, map_x=x, map_y=0)
        first, second = pole("b", "arctic", 0), pole("a", "desert", 1000)
        before = capture(self.source, locations=(first, second))
        after = capture(self.source, locations=(second, first))
        self.assertEqual(tuple(p.location_uid for p in before.climate_base.manual_poles), ("b", "a"))
        self.assertEqual(before.hydrology.anchors, after.hydrology.anchors)
        self.assertNotEqual(before.revision, after.revision)
        self.assertEqual(before.water_placement.anchors, ())

    def test_coordinate_overrides_and_bounds_are_resolved_without_generation(self):
        source = replace(self.source, world_map_cells_per_tile=4)
        source.map_settings = {"global_cell_size_m": 2000}
        view = capture(source)
        self.assertEqual(view.terrain_base.grid.fine_span, 2000)
        self.assertEqual(view.terrain_base.grid.light_side, 4)
        self.assertEqual(view.hydrology.topology, view.water_placement.topology)

    def test_capture_diagnostics_are_request_local_and_replayed_on_cache_hit(self):
        source = replace(self.source, default_climate_zone="custom")
        first_ctx, second_ctx = ResolveContext(collect_only=True), ResolveContext(collect_only=True)
        first, second = capture(source, ctx=first_ctx), capture(source, ctx=second_ctx)
        self.assertEqual(first_ctx.errors, second_ctx.errors)
        self.assertTrue(first_ctx.errors)
        bundle, builds = self.rebuilds(first, second)
        self.assertEqual(builds, [])
        self.assertEqual(bundle.view_revision, first.revision)
        self.assertFalse(any(issue.issue.code == "unknown_climate" for issue in bundle.climate_base.diagnostics))

    def test_capture_preserves_producer_dispositions_without_classifying_ctx_errors(self):
        from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
        from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
        baseline = capture(self.source)
        facts = tuple(PlanDiagnostic(issue=FieldPathError(("climate_zone_registry",), disposition.value),
            disposition=disposition) for disposition in PlanDiagnosticDisposition)
        with patch("app.application.worldData.planning.composition.surfacePlanningCapture.resolve_base_profiles",
                   return_value=(baseline.climate_base.profiles, facts)):
            changed = capture(self.source)
        self.assertEqual(changed.capture_diagnostics, facts)
        self.assertEqual(changed.revision, baseline.revision)

    def test_execution_policy_marker_applies_without_type_or_field_name_special_cases(self):
        from typing import Annotated
        from pydantic import BaseModel, ConfigDict
        from app.dataModel.planning.identity.sourceFieldRole import SourceFieldRole
        from app.application.worldData.planning.composition.surfacePlanningCapture import _revision

        class Source(BaseModel):
            model_config = ConfigDict(frozen=True)
            content: int
            different_policy_name: Annotated[int, SourceFieldRole.EXECUTION_POLICY]

        before, after = Source(content=1, different_policy_name=2), Source(content=1, different_policy_name=3)
        self.assertEqual(_revision("world", (before,)), _revision("world", (after,)))
        self.assertNotEqual(_revision("world", (before,)), _revision("world", (Source(content=2, different_policy_name=2),)))

    def test_climate_owner_resolves_custom_values_and_fallback_diagnostic(self):
        from app.application.worldData.generators.climate.registry import resolve_base_profiles, profile_for
        from app.application.jsonValidation.worldRow import climate_zones
        from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnosticDisposition
        from app.dataModel.registryKey import RegistryKey
        from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
        source = replace(self.source, default_climate_zone="desert",
            climate_zone_registry=[{"system_climate": "desert", "base_temperature": 123}])
        view = capture(source)
        ctx = ResolveContext(collect_only=True)
        profiles, diagnostics = resolve_base_profiles(RegistryKey[WorldClimateZoneRegistry]("unknown"), (),
            view.climate_base.preset, climate_zones(source), ctx)
        self.assertEqual(diagnostics[0].disposition, PlanDiagnosticDisposition.FALLBACK)
        self.assertEqual(tuple(ctx.errors), tuple(d.issue for d in diagnostics))
        self.assertEqual(next(p.values.base_temperature for p in view.climate_base.profiles if p.key == "desert"),
            profile_for(source, "desert").base_temperature)
        self.assertIn("unknown", {profile.key for profile in profiles})

    def test_invalid_authored_source_reports_and_never_uses_synthetic_defaults(self):
        ctx = ResolveContext(collect_only=True)
        with self.assertRaises(UnresolvedModelError):
            capture(replace(self.source, hydrology={"enabled": None}), ctx=ctx)
        self.assertTrue(ctx.errors)

    def test_mismatched_capture_policy_and_mixed_grid_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "mode"):
            capture(self.source, mode=ResolutionMode.VALIDATE_ONLY, ctx=ResolveContext())
        view = capture(self.source)
        malformed = view.model_copy(update={"hydrology_final": view.hydrology_final.model_copy(update={
            "grid": view.terrain_base.grid.model_copy(update={"fine_span": 123})})})
        with self.assertRaisesRegex(ValueError, "captured grid"):
            ReadySurfacePlanningView.model_validate(malformed)

    def test_new_composition_worker_count_and_eviction_preserve_all_outputs(self):
        view = capture(self.source)
        first = self.c.prepare(view)
        other = Composition(workers=1)
        self.addCleanup(other.service.shutdown)
        self.assertEqual(first, other.prepare(view))
        self.c.backend.clear()
        self.assertEqual(first, self.c.prepare(view))


if __name__ == "__main__":
    unittest.main()
