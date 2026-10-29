"""Exact binding seam only; this is not full production activation evidence."""

from dataclasses import replace
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
