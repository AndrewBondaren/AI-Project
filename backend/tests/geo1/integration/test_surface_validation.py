"""G10-A typed pipeline admission and canonical replay, before activation."""

from enum import Enum, StrEnum
from dataclasses import is_dataclass
from typing import TypeAliasType, get_args, get_type_hints
from unittest import TestCase

from pydantic import BaseModel, ValidationError

from app.application.encoding.canonicalCodec import decode, encode
from app.application.worldData.planning.contracts.surfacePlanningView import GeoSurfacePlanningView
from app.application.worldData.planning.contracts.surfacePlanBundle import GeoSurfacePlanBundle
from app.application.worldData.planning.encoding.surfaceEnvelopeCodec import SurfaceEnvelopeCodec
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.sources.proceduralWaterSource import ProceduralWaterSource
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.integration.support.pipeline import view, bundle, rebuild, placement_plan
from tests.geo1.placement_policy.fixtures import coastline


class SurfaceContractTests(TestCase):
    def setUp(self):
        self.view = view()

    def test_complete_codec_type_closure_including_empty_variants(self):
        registered = {entry.python_type for entry in SURFACE_MANIFEST.entries}
        seen = set()

        def visit(kind):
            if isinstance(kind, Enum):
                kind = type(kind)
            if kind in seen:
                return
            seen.add(kind)
            if isinstance(kind, TypeAliasType):
                visit(kind.__value__)
            elif isinstance(kind, type) and kind not in (Enum, StrEnum) and (
                    issubclass(kind, (BaseModel, Enum)) or is_dataclass(kind)):
                self.assertIn(kind, registered, kind.__name__)
                if issubclass(kind, BaseModel):
                    for field in kind.model_fields.values():
                        visit(field.annotation)
                elif is_dataclass(kind):
                    for annotation in get_type_hints(kind).values():
                        visit(annotation)
            else:
                for arg in get_args(kind):
                    try:
                        hash(arg)
                    except TypeError:
                        continue
                    visit(arg)

        visit(GeoSurfacePlanningView)
        visit(GeoSurfacePlanBundle)

    def test_complete_view_bundle_and_each_phase_replay(self):
        plans = bundle(self.view)
        for value in (self.view, plans, *(
                getattr(plans, name) for name in type(plans).model_fields
                if isinstance(getattr(plans, name), PlanEnvelope))):
            with self.subTest(type=type(value).__name__):
                wire = encode(value, SURFACE_MANIFEST)
                restored = decode(wire, type(value), SURFACE_MANIFEST)
                self.assertEqual(restored, value)
                self.assertEqual(encode(restored, SURFACE_MANIFEST), wire)
                if isinstance(value, PlanEnvelope):
                    codec = SurfaceEnvelopeCodec(type(value), SURFACE_MANIFEST)
                    self.assertEqual(codec.decode(codec.encode(value)), value)

    def test_all_source_variants_survive_capture_codec(self):
        path = tuple(HydrologyWaypoint(x=x, y=y) for x, y in ((0, 0), (1, 0), (1, 1)))
        sources = (
            AuthoredBasinSource(value=DeclaredBasin(location_uid="basin", kind=BasinKind.SEA, floor_z=-5,
                footprint=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1))),
            AuthoredLakeSource(value=DeclaredLake(location_uid="lake", shoreline=path)),
            CoastlineWaterSource(value=DeclaredCoastline(location_uid="coast", kind=BasinKind.SEA, path=path)),
            ProceduralSource(value=ProceduralWaterSource(source_uid="auto", generation_region_uid="region",
                kind=BasinKind.OCEAN, liquid="water")))
        inputs = rebuild(self.view.water_placement, sources=sources)
        captured = rebuild(self.view, water_placement=inputs)
        self.assertEqual(decode(encode(captured, SURFACE_MANIFEST), type(captured), SURFACE_MANIFEST), captured)

    def test_nonempty_placement_outcomes_metadata_decisions_and_budget_replay(self):
        plan = placement_plan()
        restored = decode(encode(plan, SURFACE_MANIFEST), type(plan), SURFACE_MANIFEST)
        self.assertEqual(restored, plan)
        self.assertEqual(tuple(item.status for item in restored.outcomes), ("resolved", "disabled", "unresolved"))
        self.assertEqual(tuple(item.identity.source_uid for item in restored.outcomes), ("basin", "off", "missing"))

    def test_resolution_modes_are_coherent(self):
        for name in ("water_placement", "hydrology", "boundary_input", "coating_input"):
            with self.subTest(phase=name), self.assertRaisesRegex(ValidationError, "execution mode"):
                rebuild(self.view, **{name: rebuild(getattr(self.view, name), resolution_mode=ResolutionMode.VALIDATE_ONLY)})

    def test_every_spatial_phase_requires_the_captured_grid(self):
        grid = SurfaceGridSettings(fine_span=self.view.terrain_base.grid.fine_span + 1, light_side=2)
        for name in ("water_placement", "region_input", "relief", "hydrology", "river_relief",
                     "hydrology_final", "boundary_input", "surface_support"):
            with self.subTest(phase=name), self.assertRaisesRegex(ValidationError, "captured grid"):
                rebuild(self.view, **{name: rebuild(getattr(self.view, name), grid=grid)})

    def test_every_topology_phase_requires_the_captured_topology(self):
        original = self.view.water_placement.topology
        other = WorldTopology(mode="planar", bounds=original.bounds)
        if other == original:
            other = WorldTopology(mode="wrapped", bounds=original.bounds)
        for name in ("region_input", "hydrology", "river_relief", "hydrology_final", "boundary_input", "surface_support"):
            with self.subTest(phase=name), self.assertRaisesRegex(ValidationError, "captured topology"):
                rebuild(self.view, **{name: rebuild(getattr(self.view, name), topology=other)})

    def test_authored_bounds_presence_and_z_range_cannot_drift(self):
        with self.assertRaisesRegex(ValidationError, "world-bounds presence"):
            rebuild(self.view, region_input=rebuild(self.view.region_input, declared_world_bounds=None))
        water = self.view.water_placement
        with self.assertRaisesRegex(ValidationError, "world bounds"):
            rebuild(water, declared_world_bounds=WorldBounds(x_min=0, x_max=5, y_min=0, y_max=1))
        for name in ("water_placement", "relief", "hydrology", "river_relief"):
            with self.subTest(phase=name), self.assertRaisesRegex(ValidationError, "z range"):
                rebuild(self.view, **{name: rebuild(getattr(self.view, name), z_min=self.view.terrain_base.z_min - 1)})

    def test_admission_rejects_forged_mutable_and_invalid_legacy_instances(self):
        for name, change in (("water_placement", {"sources": []}), ("hydrology", {"anchors": []}),
                             ("water_placement", {"seas": self.view.water_placement.seas.model_copy(
                                 update={"placement_specificity": -1})})):
            with self.subTest(phase=name, change=change), self.assertRaises(ValidationError):
                rebuild(self.view, **{name: getattr(self.view, name).model_copy(update=change)})

    def test_duplicate_and_unknown_liquid_sources_are_rejected(self):
        source = ProceduralSource(value=ProceduralWaterSource(source_uid="auto", generation_region_uid="region",
            kind=BasinKind.OCEAN, liquid="water"))
        with self.assertRaisesRegex(ValidationError, "duplicate water source"):
            rebuild(self.view.water_placement, sources=(source, source))
        with self.assertRaisesRegex(ValidationError, "material membership"):
            rebuild(self.view.water_placement, sources=(source,), liquid_keys=frozenset())

    def test_boundary_cannot_share_identity_with_body_producer(self):
        source = coastline()
        boundary = coastline(True).model_copy(update={"location_uid": source.value.location_uid})
        with self.assertRaisesRegex(ValidationError, "body-producing source universe"):
            rebuild(self.view, water_placement=rebuild(self.view.water_placement, sources=(source,)),
                boundary_input=rebuild(self.view.boundary_input, sources=(boundary,)))

    def test_bundle_rejects_foreign_phase_versions_worlds_and_dependency_refs(self):
        plans = bundle(self.view)
        for key_update in ({"world_uid": "other"}, {"schema_version": 999}, {"contract_id": "wrong.phase"}):
            envelope = plans.water_placement
            forged = rebuild(envelope, ref=rebuild(envelope.ref, key=rebuild(envelope.ref.key, **key_update)))
            with self.subTest(change=key_update), self.assertRaisesRegex(ValidationError, "foreign world/scope/phase/version"):
                rebuild(plans, water_placement=forged)
        deps = plans.coating.dependencies
        forged = rebuild(deps[0], ref=rebuild(deps[0].ref, output_fingerprint=b"x" * 32))
        with self.assertRaisesRegex(ValidationError, "dependency refs"):
            rebuild(plans, coating=rebuild(plans.coating, dependencies=(forged, *deps[1:])))

    def test_bundle_preserves_route_mapping_in_final_fill(self):
        plans = bundle(self.view)
        mapping = SourceBodyMapping(entries=(SourceBodyMappingEntry(source_uid="dry-source", body_uids=()),))
        final = rebuild(plans.hydrology, payload=rebuild(plans.hydrology.payload, source_mapping=mapping))
        with self.assertRaisesRegex(ValidationError, "preserve route-stage"):
            rebuild(plans, hydrology=final)

    def test_geo_route_generation_sources_are_required_and_revalidated(self):
        from tests.geo1.integration.support.pipeline import fields
        inputs = self.view.hydrology
        for name in ("generation", "defaults"):
            values = fields(inputs)
            values.pop(name)
            with self.subTest(missing=name), self.assertRaises(ValidationError):
                type(inputs).model_validate(values)
        with self.assertRaises(ValidationError):
            rebuild(inputs, generation=inputs.generation.model_copy(update={"autoresolve": "true"}))
        with self.assertRaises(ValidationError):
            rebuild(inputs, defaults=inputs.defaults.model_copy(update={"water_fraction": 2.0}))

    def test_geo_route_root_sources_must_match_water_placement(self):
        for update in ({"generation": rebuild(self.view.hydrology.generation, autoresolve=True)},
                       {"defaults": rebuild(self.view.hydrology.defaults, water_fraction=0.25)}):
            with self.subTest(update=update), self.assertRaisesRegex(ValidationError, "generation and defaults"):
                rebuild(self.view, hydrology=rebuild(self.view.hydrology, **update))

    def test_route_generation_source_edits_change_artifact_and_source_revision(self):
        from app.application.worldData.planning.composition.planProviders import declared_binding
        from app.application.worldData.planning.composition.surfacePlanningCapture import _revision
        from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan
        from app.dataModel.planning.identity.planKey import WorldPlanScope
        from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding
        from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot as S
        inputs = self.view.hydrology
        handle = declared_binding(geo_surface_plan_binding(S.HYDROLOGY_ROUTES), type(inputs), GeoHydrologyRoutesPlan)
        deps = bundle(self.view).hydrology_routes.dependencies
        variants = (inputs,
            rebuild(inputs, generation=rebuild(inputs.generation, autoresolve=False)),
            rebuild(inputs, generation=rebuild(inputs.generation, autoresolve=True)),
            rebuild(inputs, defaults=rebuild(inputs.defaults, water_fraction=0.25)))
        self.assertEqual(len({handle.fingerprint_inputs("world", WorldPlanScope(), value, deps) for value in variants}), 4)
        self.assertEqual(len({_revision("world", (value,)) for value in variants}), 4)
        validation = rebuild(inputs, resolution_mode=ResolutionMode.VALIDATE_ONLY)
        self.assertEqual(_revision("world", (inputs,)), _revision("world", (validation,)))
        self.assertNotEqual(handle.fingerprint_inputs("world", WorldPlanScope(), inputs, deps),
            handle.fingerprint_inputs("world", WorldPlanScope(), validation, deps))


    def test_captured_category_sources_are_required_strict_and_revalidated_in_both_phases(self):
        from tests.geo1.integration.support.pipeline import fields
        for inputs in (self.view.water_placement, self.view.hydrology):
            for name in ("sea_generation", "ocean_generation", "lake_generation"):
                with self.subTest(phase=type(inputs).__name__, field=name):
                    values = fields(inputs)
                    values.pop(name)
                    with self.assertRaises(ValidationError):
                        type(inputs).model_validate(values)
                    for update in ({"autoresolve": "true"}, {"water_fraction": 2.0}, {"strategy": "unknown"}):
                        with self.assertRaises(ValidationError):
                            rebuild(inputs, **{name: getattr(inputs, name).model_copy(update=update)})

    def test_category_generation_must_match_across_phases(self):
        for name in ("sea_generation", "ocean_generation", "lake_generation"):
            for update in ({"autoresolve": True}, {"water_fraction": 0.2}):
                value = rebuild(getattr(self.view.hydrology, name), **update)
                with self.subTest(field=name, update=update):
                    with self.assertRaisesRegex(ValidationError, "captured category generation"):
                        rebuild(self.view, hydrology=rebuild(self.view.hydrology, **{name: value}))
                    matched = rebuild(self.view, hydrology=rebuild(self.view.hydrology, **{name: value}),
                        water_placement=rebuild(self.view.water_placement, **{name: value}))
                    restored = decode(encode(matched, SURFACE_MANIFEST), type(matched), SURFACE_MANIFEST)
                    self.assertEqual(restored, matched)

    def test_each_category_setting_changes_both_request_fingerprints_and_source_revision(self):
        from app.application.worldData.planning.composition.planProviders import declared_binding
        from app.application.worldData.planning.composition.surfacePlanningCapture import _revision
        from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan
        from app.dataModel.terrain.planning.waterPlacementPlan import GeoWaterPlacementPlan
        from app.dataModel.planning.identity.planKey import WorldPlanScope
        from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding
        from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot as S
        from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
        plans = bundle(self.view)
        for slot, inputs, payload_type in ((S.WATER_PLACEMENT, self.view.water_placement, GeoWaterPlacementPlan),
                (S.HYDROLOGY_ROUTES, self.view.hydrology, GeoHydrologyRoutesPlan)):
            handle = declared_binding(geo_surface_plan_binding(slot), type(inputs), payload_type)
            deps = getattr(plans, slot.value).dependencies
            variants = [inputs]
            for name in ("sea_generation", "ocean_generation", "lake_generation"):
                for update in ({"autoresolve": False}, {"autoresolve": True}, {"water_fraction": 0.2},
                        {"strategy": Strategy.AUTHORED_REGION}):
                    variants.append(rebuild(inputs, **{name: rebuild(getattr(inputs, name), **update)}))
            with self.subTest(slot=slot):
                self.assertEqual(len({handle.fingerprint_inputs("world", WorldPlanScope(), value, deps)
                    for value in variants}), len(variants))
                self.assertEqual(len({_revision("world", (value,)) for value in variants}), len(variants))

    def test_captured_categories_feed_common_inheritance_and_policy_after_replay(self):
        from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
        from app.application.policy.policyResolver import PolicyResolver
        from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode as Mode
        inputs = rebuild(self.view.hydrology, enabled=True,
            generation=rebuild(self.view.hydrology.generation, autoresolve=True),
            sea_generation=rebuild(self.view.hydrology.sea_generation, autoresolve=False),
            lake_generation=rebuild(self.view.hydrology.lake_generation, water_fraction=0.1))
        inputs = decode(encode(inputs, SURFACE_MANIFEST), type(inputs), SURFACE_MANIFEST)
        for name, expected, fraction in (("sea_generation", Mode.DECLARED_ONLY, 0.6),
                ("ocean_generation", Mode.AUTORESOLVE, 0.6), ("lake_generation", Mode.AUTORESOLVE, 0.1)):
            bound = bind_hydrology_generation_policy(enabled=inputs.enabled, generation=inputs.generation,
                defaults=inputs.defaults, category=getattr(inputs, name), root_path=("hydrology",),
                context_path=("classification", name))
            decision = PolicyResolver().resolve(bound.spec, bound.inputs, bound.facts, mode=inputs.resolution_mode)
            self.assertIs(decision.require_behavior(), expected)
            self.assertEqual(bound.context.water_fraction, fraction)
