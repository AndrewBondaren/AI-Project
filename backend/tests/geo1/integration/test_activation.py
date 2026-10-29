"""Exact binding seam only; this is not full production activation evidence."""

from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from pydantic import ValidationError

from app.application.encoding.canonicalCodec import encode, decode
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanContractFailure
from app.application.worldData.planning.composition.planProviders import declared_binding
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, GeoHydrologyPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.policy.policyDecision import PolicyReason, ValueSelectionDecision
from app.dataModel.policy.policyEnums import PolicyOperation, PolicyState, PolicyDisableReason
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.surfacePlanning.surfacePlanBindings import PC_SURFACE_BINDINGS, GEO_SURFACE_BINDINGS, surface_plan_binding, geo_surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot as S
from tests.geo1.integration.support.fixtures import Seam, FrozenUpstream, seal

from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometry
from app.application.worldData.generators.hydrology.boundaries.boundaryPlanner import CoastlineBoundaryPlanner
from app.application.worldData.generators.hydrology.policy.hydrologyPolicyFacts import collect_hydrology_policy_facts
from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
from app.application.worldData.placement.adapters.coastline.attachedCoastline import AttachedCoastlinePreparer
from app.application.planning.providers.planRegistry import PlanRegistry
from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import (
    HydrologyPolicySnapshot, HydrologyPlacementGateInputs, HydrologyPlacementBehaviorInputs,
)
from app.dataModel.hydrology.seas import HydrologySeasPolicy
from app.dataModel.policy.policyBindings import PolicySupportFact
from app.dataModel.policy.policyEnums import PolicySupportState
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind
from tests.geo1.boundaries.fixtures import make
from tests.geo1.integration.support.pipeline import fields, view, bundle


class BindingSeamTests(TestCase):
    def setUp(self):
        self.seam = Seam()
        self.addCleanup(self.seam.service.shutdown)

    def test_all_geo_dependencies_match_the_declared_family(self):
        bindings = {binding.slot.value: binding for binding in GEO_SURFACE_BINDINGS}
        self.assertEqual(len(bindings), 12)
        for binding in GEO_SURFACE_BINDINGS:
            for dependency in binding.dependency_contracts():
                self.assertEqual(dependency.contract_id, bindings[dependency.slot].metadata.id)
        self.assertEqual(len(PC_SURFACE_BINDINGS), 8)
        self.assertIs(geo_surface_plan_binding(S.CLIMATE_BASE), surface_plan_binding(S.CLIMATE_BASE))
        self.assertIs(geo_surface_plan_binding(S.TERRAIN_BASE), surface_plan_binding(S.TERRAIN_BASE))
        self.assertEqual(geo_surface_plan_binding(S.CLIMATE_LOCAL).metadata.schema_version, 2)
        with self.assertRaises(ValueError):
            replace(geo_surface_plan_binding(S.CLIMATE_LOCAL), declared_dependencies=())

    def test_real_registered_local_support_and_coating_build(self):
        final = self.seam.final()
        before = encode(final, SURFACE_MANIFEST)
        result = self.seam.run(final)
        self.assertEqual(len(result["surface_support"].payload.facts), 1)
        self.assertEqual(result["coating"].payload.cells[0].target.material, "sand")
        self.assertEqual(encode(final, SURFACE_MANIFEST), before)
        for name in ("climate_local", "surface_support", "coating"):
            ref = next(dep.ref for dep in result[name].dependencies if dep.slot == "hydrology")
            self.assertEqual(ref, final.ref)

    def test_pc_final_is_rejected_at_the_geo_boundary(self):
        seam = self.seam
        pc = declared_binding(surface_plan_binding(S.HYDROLOGY), HydrologyFinalInput, HydrologyPlan)
        seam.registry.register(pc, FrozenUpstream())
        envelope = seal(pc, HydrologyPlan(**seam.common_hydro))
        with self.assertRaises((PlanContractFailure, ValueError)):
            PlanDependencyReader(seam.registry).with_plan("hydrology", seam.handles["hydrology"], envelope)
        reader = PlanDependencyReader(seam.registry).with_plan("hydrology", pc, envelope)
        with self.assertRaises(PlanContractFailure):
            reader.require("hydrology", seam.handles["hydrology"])
        dependency = PlanDependency(slot="hydrology", ref=envelope.ref)
        declared = next(d for d in seam.handles["climate_local"].dependency_contracts if d.slot == "hydrology")
        self.assertFalse(declared.accepts(dependency))

    def test_geo_final_codec_closure_and_metadata_independence(self):
        decision = ValueSelectionDecision[HydrologyExecutionMode, WaterPolicyReason](operation=PolicyOperation.VALUE_SELECTION, state=PolicyState.READY,
            effective_priority=None, behavior=HydrologyExecutionMode.DECLARED_ONLY,
            reasons=(PolicyReason[WaterPolicyReason](domain_reason=WaterPolicyReason.DECLARED_ONLY,
                common_reason=PolicyDisableReason.DOMAIN_RULE),), waiting_supports=(), provenance=(), issues=())
        first = self.seam.final(source="one")
        second = self.seam.final(source="two", decisions=((WaterGenerationCategory.OCEAN, decision),))
        for envelope in (first, second):
            wire = encode(envelope, SURFACE_MANIFEST)
            restored = decode(wire, PlanEnvelope[GeoHydrologyPlan], SURFACE_MANIFEST)
            self.assertEqual(restored, envelope)
        a, b = self.seam.run(first), self.seam.run(second)
        self.assertEqual(a["climate_local"].payload, b["climate_local"].payload)
        self.assertEqual(a["coating"].payload, b["coating"].payload)
        self.assertEqual(a["surface_support"].payload.facts[0].substrate,
                         b["surface_support"].payload.facts[0].substrate)
        self.assertNotEqual(a["surface_support"].payload.facts[0].support_input_fingerprint,
                            b["surface_support"].payload.facts[0].support_input_fingerprint)

    def test_mapping_cannot_claim_a_nonexistent_final_body(self):
        with self.assertRaisesRegex(ValidationError, "final physical water bodies"):
            GeoHydrologyPlan(**self.seam.common_hydro, source_mapping=SourceBodyMapping(entries=(
                SourceBodyMappingEntry(source_uid="source", body_uids=("union-or-missing-body",)),)),
                classification_decisions=())


class BoundaryBindingTests(TestCase):
    def setUp(self):
        self.case = make()
        self.handle = declared_binding(geo_surface_plan_binding(S.HYDROLOGY), HydrologyFinalInput, GeoHydrologyPlan)
        payload = GeoHydrologyPlan(**fields(self.case.snapshot.hydrology.payload),
            source_mapping=self.case.snapshot.source_mapping, classification_decisions=())
        # Frozen upstream refs are fixture evidence, not upstream generation.
        frozen = bundle(view())
        self.final = seal(self.handle, payload, tuple(
            (dep.slot, SimpleNamespace(ref=dep.ref)) for dep in frozen.hydrology.dependencies))
        self.snapshot = BoundaryWaterSnapshot[GeoHydrologyPlan](**(fields(self.case.snapshot) | dict(
            hydrology=self.final, mapping_hydrology_ref=self.final.ref, placement_ref=frozen.water_placement.ref)))

    def policy_snapshot(self):
        return HydrologyPolicySnapshot[GeoHydrologyPlan](world_uid="world", hydrology=self.final,
            source_mapping=self.final.payload.source_mapping, mapping_hydrology_ref=self.final.ref,
            supports=(PolicySupportFact(uid="water-source", state=PolicySupportState.ACCEPTED),))

    def test_geo_final_declares_the_exact_water_ref_boundary_requires(self):
        water = geo_surface_plan_binding(S.WATER_PLACEMENT)
        final = geo_surface_plan_binding(S.HYDROLOGY)
        self.assertEqual(set(final.upstream), {S.RELIEF, S.HYDROLOGY_ROUTES, S.RIVER_RELIEF, S.WATER_PLACEMENT})
        declaration = next(dep for dep in final.dependency_contracts() if dep.slot == S.WATER_PLACEMENT.value)
        self.assertEqual(declaration.contract_id, water.metadata.id)
        self.assertEqual(declaration.schema_version, water.metadata.schema_version)
        self.assertNotIn(S.WATER_PLACEMENT, surface_plan_binding(S.HYDROLOGY).upstream)

    def test_real_geo_handle_is_preserved_through_boundary_geometry_and_p2(self):
        registry = PlanRegistry()
        registry.register(self.handle, FrozenUpstream())
        reader = PlanDependencyReader(registry).with_plan("hydrology", self.handle, self.final)
        self.assertEqual(reader.require("hydrology", self.handle), self.snapshot.hydrology)
        self.assertIs(type(self.snapshot.hydrology.payload), GeoHydrologyPlan)
        expected = BoundaryGeometry().prepare(self.case.source, self.case.snapshot)
        self.assertEqual(BoundaryGeometry().prepare(self.case.source, self.snapshot), replace(expected,
            boundary=expected.boundary.model_copy(update={"hydrology_ref": self.final.ref})))
        prepared = AttachedCoastlinePreparer().prepare_boundary(self.case.source, self.snapshot, self.case.admission)
        self.assertEqual(prepared.boundary.hydrology_ref, self.final.ref)
        plan = CoastlineBoundaryPlanner().prepare(self.case.input, self.snapshot,
            (self.case.admission,), snapshot_uid="same-final-water")
        self.assertEqual(len(plan.boundaries), 1)
        self.assertEqual(plan.boundaries[0].hydrology_ref, self.final.ref)
        self.assertEqual(plan.outcomes[0].identity.source_uid, self.case.source.location_uid)

    def test_policy_fact_collection_and_binding_keep_the_geo_envelope(self):
        snapshot = self.policy_snapshot()
        observed = collect_hydrology_policy_facts(self.case.source, snapshot)
        self.assertTrue(observed.target_has_water.value)
        binding = bind_hydrology_placement_policy(self.case.source, HydrologySeasPolicy(placement_specificity=3),
            HydrologyPlacementGateInputs(world_enabled=True, category_enabled=True),
            HydrologyPlacementBehaviorInputs(strategy=DesignedWaterStrategyKind.AUTHORED_REGION), snapshot,
            source_path=("boundaries", 0), category_path=("seas",))
        decision = PolicyResolver().resolve(binding.spec, binding.inputs, binding.facts, mode=self.case.input.resolution_mode)
        self.assertIs(decision.state, PolicyState.READY)
        self.assertEqual(snapshot.hydrology, self.final)

    def test_pc_geo_snapshot_substitution_is_rejected(self):
        for owner, value in ((BoundaryWaterSnapshot, self.snapshot),
                             (BoundaryWaterSnapshot[GeoHydrologyPlan], self.case.snapshot),
                             (HydrologyPolicySnapshot, self.policy_snapshot())):
            with self.subTest(owner=owner), self.assertRaises(ValidationError):
                owner.model_validate(fields(value), strict=True)

    def test_wrong_direct_water_ref_is_rejected_even_with_same_final_payload(self):
        other = self.snapshot.placement_ref.model_copy(update={"output_fingerprint": b"x" * 32})
        wrong_phase = next(dep.ref for dep in self.final.dependencies if dep.slot == S.RELIEF.value)
        for ref in (other, wrong_phase):
            with self.subTest(ref=ref), self.assertRaisesRegex(ValidationError, "exact hydrology dependency"):
                BoundaryWaterSnapshot[GeoHydrologyPlan].model_validate(fields(self.snapshot) | {"placement_ref": ref})

    def test_geo_bundle_rejects_final_without_direct_water_provenance(self):
        plans = bundle(view())
        final = plans.hydrology.model_copy(update={"dependencies": tuple(
            dep for dep in plans.hydrology.dependencies if dep.slot != S.WATER_PLACEMENT.value)})
        with self.assertRaisesRegex(ValidationError, "dependency refs"):
            type(plans).model_validate(fields(plans) | {"hydrology": final})


class SourceMappingProducerTests(TestCase):
    @staticmethod
    def spec(uid, cells, *, level=0):
        from app.dataModel.hydrology.bands import HydrologyBands
        from app.dataModel.hydrology.enums.basinKind import BasinKind
        from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
        return BasinSpec(source_uid=uid, kind=BasinKind.LAKE, liquid="water", footprint=frozenset(cells),
            z_water_level=level, floor_z=level-5, bands=HydrologyBands(min=1, max=2))

    def fill(self, wet, specs, *, auto=False, mode=None):
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
        from app.dataModel.hydrology.worldHydrology import WorldHydrology
        from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
        from tests.hydrology_fixtures import flat_heightmap, hydro_topology
        heightmap = flat_heightmap(0, 5, 0, 3, z=10)
        heightmap.surface_z.update(wet)
        before = dict(heightmap.surface_z)
        result = assemble_water_bodies(heightmap, specs, hydro_topology(heightmap, mode or WorldTopologyMode.PLANAR),
            WorldHydrology(default_seas={"min_water_cells": 1}, default_lakes={"min_water_cells": 1}),
            change_uid="same-fill", auto_seas=auto, auto_lakes=auto, ctx=ResolveContext(collect_only=True))
        self.assertEqual(heightmap.surface_z, before)
        bodies = {body.water_body_uid for body in result.materialized.bodies}
        self.assertTrue(all(set(entry.body_uids) <= bodies for entry in result.materialized.source_mapping.entries))
        return result

    @staticmethod
    def mapped(result):
        return {entry.source_uid: entry.body_uids for entry in result.materialized.source_mapping.entries}

    def test_supplied_source_and_accepted_dry_source_are_explicit(self):
        specs = (self.spec("wet", ((2, 2),)), self.spec("dry", ((4, 2),)))
        result = self.fill({(2, 2): -2}, specs)
        self.assertEqual(self.mapped(result), {"dry": (), "wet": ("wet",)})

    def test_dry_shore_does_not_count_as_water_for_the_source(self):
        from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
        specs = (self.spec("wet", ((2, 2),)), self.spec("shore", ((3, 2),)))
        result = self.fill({(2, 2): -2, (3, 2): 0}, specs)
        shore = result.materialized.by_cell[(3, 2)]
        self.assertIs(shore.role, HydrologyCellRole.SHORE)
        self.assertEqual(shore.water_body_uid, "wet")
        self.assertEqual(self.mapped(result)["shore"], ())

    def test_tied_sources_use_actual_cell_ownership_instead_of_equal_uids(self):
        cells = ((2, 2), (3, 2))
        result = self.fill(dict.fromkeys(cells, -2), (self.spec("a", cells), self.spec("b", cells)))
        actual = tuple(sorted({result.materialized.by_cell[cell].water_body_uid for cell in cells}))
        self.assertEqual(self.mapped(result), {"a": actual, "b": actual})
        self.assertIn("b", {body.water_body_uid for body in result.materialized.bodies})
        self.assertNotEqual(self.mapped(result)["b"], ("b",))

    def test_one_source_footprint_can_map_to_multiple_final_bodies(self):
        left, right = (1, 2), (4, 2)
        result = self.fill({left: -2, right: -2}, (
            self.spec("a-left", (left,)), self.spec("b-right", (right,)), self.spec("z-probe", (left, right))))
        self.assertEqual(self.mapped(result)["z-probe"], ("a-left", "b-right"))

    def test_merge_mapping_contains_physical_bodies_and_never_system_uids(self):
        result = self.fill({(2, 2): -2, (3, 2): -2}, (
            self.spec("a", ((2, 2),)), self.spec("b", ((3, 2),))))
        self.assertTrue(result.physical_unions)
        systems = {union.water_system_uid for union in result.physical_unions}
        self.assertTrue(all(not systems.intersection(entry.body_uids) for entry in result.materialized.source_mapping.entries))
        for source, cell in (("a", (2, 2)), ("b", (3, 2))):
            self.assertEqual(self.mapped(result)[source], (result.materialized.by_cell[cell].water_body_uid,))

    def test_spill_mapping_uses_final_wet_body_after_the_level_changes(self):
        result = self.fill({(2, 2): 0, (2, 1): 3, (2, 0): 3}, (self.spec("spill", ((2, 2),), level=6),))
        cell = result.materialized.by_cell[(2, 2)]
        self.assertEqual(cell.z_water_level, 3)
        self.assertEqual(self.mapped(result)["spill"], (cell.water_body_uid,))

    def test_natural_discovery_does_not_create_placement_mapping_entries(self):
        result = self.fill({(2, 2): -2}, (), auto=True)
        self.assertTrue(result.materialized.bodies)
        self.assertEqual(result.materialized.source_mapping.entries, ())
        result = self.fill({(2, 2): -1}, (self.spec("probe", ((2, 2),), level=-2),), auto=True)
        actual = result.materialized.by_cell[(2, 2)].water_body_uid
        self.assertEqual(self.mapped(result), {"probe": (actual,)})
        self.assertNotEqual(actual, "probe")
        self.assertIn(actual, result.materialized.uid_remap.values())

    def test_source_mapping_replays_across_order_and_topology(self):
        from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
        for mode, cells in ((Mode.PLANAR, ((2, 2), (3, 2))), (Mode.WRAPPED, ((0, 1), (5, 1))),
                            (Mode.SPHERE, ((0, 0), (3, 0)))):
            specs = (self.spec("a", (cells[0],)), self.spec("b", (cells[1],)))
            first = self.fill(dict.fromkeys(cells, -2), specs, mode=mode)
            second = self.fill(dict.fromkeys(cells, -2), tuple(reversed(specs)), mode=mode)
            with self.subTest(mode=mode):
                self.assertEqual(first.materialized.source_mapping, second.materialized.source_mapping)
                self.assertEqual(first.materialized.by_cell, second.materialized.by_cell)

    def test_failed_terrain_resolution_does_not_claim_accepted_sources_are_dry(self):
        from app.application.jsonValidation.resolve import ResolveContext
        from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
        from app.dataModel.hydrology.worldHydrology import WorldHydrology
        from tests.hydrology_fixtures import flat_heightmap, hydro_topology
        heightmap = flat_heightmap(0, 5, 0, 3, z=10)
        topology = hydro_topology(heightmap)
        del heightmap.surface_z[(2, 2)]
        ctx = ResolveContext(collect_only=True)
        result = assemble_water_bodies(heightmap, (self.spec("accepted", ((1, 2),)),), topology,
            WorldHydrology(), change_uid="invalid-surface", auto_seas=False, auto_lakes=False, ctx=ctx)
        self.assertTrue(ctx.errors)
        self.assertEqual(result.materialized.source_mapping.entries, ())
