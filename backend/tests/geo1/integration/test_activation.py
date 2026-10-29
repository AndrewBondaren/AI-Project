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
