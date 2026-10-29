from unittest import TestCase

from app.application.encoding.canonicalCodec import encode, decode
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.application.worldData.generators.terrain.relief.surfaceCoatingSupport import CoatingPlanProvider
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceSupportPlan
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.coating.fixtures import prepared, coating_input, envelope, binding, key
from tests.geo1.coating.test_policy import fact


class CoatingTransportTests(TestCase):
    def test_both_providers_build_through_registered_readonly_dependencies(self):
        from app.application.planning.providers.planRegistry import PlanRegistry, PlanDependencyReader
        from app.application.worldData.generators.terrain.relief.surfaceCoatingSupport import SurfaceCoatingSupportProvider
        from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import CoatingPlan, SURFACE_SUPPORT_SLOT
        from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput, CoatingPlanInput
        from app.dataModel.planning.contracts.planDependency import PlanDependency
        from app.dataModel.planning.contracts.planRequest import PlanRequest
        from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
        from app.dataModel.planning.identity.planRef import PlanRef
        from app.application.planning.service.planFingerprints import output_fingerprint
        class NeverBuild:
            def build(self, *args):
                raise AssertionError("captured dependencies must not be regenerated")
        class Control:
            def raise_if_shutdown(self):
                pass
        request, deps = prepared()
        registry = PlanRegistry()
        reader = PlanDependencyReader(registry)
        handles = {}
        for name in deps.__dataclass_fields__:
            upstream = getattr(deps, name)
            handle = binding(name, type(upstream.payload), type(upstream.payload))
            registry.register(handle, NeverBuild())
            reader = reader.with_plan(name, handle, upstream)
            handles[name] = handle
        support_handle = binding("surface_support", SurfaceSupportInput, SurfaceSupportPlan)
        provider = SurfaceCoatingSupportProvider(**handles)
        registry.register(support_handle, provider)
        result = registry.build(support_handle, request, reader, Control())
        self.assertEqual(len(result.payload.facts), 1)
        support_envelope = PlanEnvelope[SurfaceSupportPlan](ref=PlanRef(
            key=request.key, output_fingerprint=output_fingerprint(result.payload, request.dependencies, (), SURFACE_MANIFEST)),
            dependencies=request.dependencies, payload=result.payload, diagnostics=())
        coat_handle = binding("coating", CoatingPlanInput, CoatingPlan)
        coat_provider = CoatingPlanProvider(support_handle, handles["hydrology"], fine_span=2)
        registry.register(coat_handle, coat_provider)
        reader = PlanDependencyReader(registry).with_plan(SURFACE_SUPPORT_SLOT, support_handle, support_envelope)
        reader = reader.with_plan("hydrology", handles["hydrology"], deps.hydrology)
        coat_request = PlanRequest[CoatingPlanInput](key=key("coating"), inputs=coating_input(), dependencies=(
            PlanDependency(slot="hydrology", ref=deps.hydrology.ref),
            PlanDependency(slot=SURFACE_SUPPORT_SLOT, ref=support_envelope.ref)))
        coat = registry.build(coat_handle, coat_request, reader, Control())
        self.assertEqual(coat.payload.cells[0].target.material, "sand")

    def test_full_production_manifest_closure(self):
        _, deps = prepared()
        for facts in (fact(), fact(substrate=None)):
            support = SurfaceSupportPlan(facts=(facts,))
            for mode in ResolutionMode:
                inputs = coating_input(mode)
                plan = CoatingPlanProvider.plan(inputs, support, deps.hydrology.payload, fine_span=2).payload
                for value in (inputs, support, plan, envelope("surface_support", support), envelope("coating", plan)):
                    with self.subTest(value=type(value), mode=mode):
                        wire = encode(value, SURFACE_MANIFEST)
                        restored = decode(wire, type(value), SURFACE_MANIFEST)
                        self.assertEqual(value, restored)
                        self.assertEqual(wire, encode(restored, SURFACE_MANIFEST))
