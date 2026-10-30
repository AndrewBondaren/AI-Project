"""Cache invalidation follows exact GEO dependencies across the consumption seam."""

from unittest import TestCase
from unittest.mock import patch
from types import SimpleNamespace

from tests.geo1.integration.support.fixtures import Seam

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.service.cacheService import CacheService
from app.application.planning.providers.planRegistry import PlanRegistry, PlanDependencyReader
from app.application.planning.service.planningService import PlanningService, PlanBuildFailure
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import HydrologyFactsAssembler
from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import GeoHydrologyFinalPlanProvider
from app.application.worldData.planning.composition.planProviders import declared_binding
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
from app.dataModel.policy.policyDecision import ValueSelectionDecision, PolicyReason
from app.dataModel.policy.policyEnums import PolicyOperation, PolicyState, PolicyDisableReason
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot as S
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import GeoWaterPlacementPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
from tests.geo1.integration.support.fixtures import FrozenUpstream, Wait, seal
from tests.geo1.integration.support.pipeline import view, bundle, ReliefSeam


class SeamRevisionTests(TestCase):
    def setUp(self):
        self.seam = Seam()
        self.addCleanup(self.seam.service.shutdown)

    def test_warm_cache_skips_all_three_builds_and_final_edit_invalidates(self):
        first = self.seam.run(self.seam.final(source="before"))
        with patch.object(self.seam.registry, "build", wraps=self.seam.registry.build) as builds:
            self.assertEqual(self.seam.run(self.seam.final(source="before")), first)
            builds.assert_not_called()
            second = self.seam.run(self.seam.final(source="after"))
            self.assertEqual(builds.call_count, 3)
        for name in ("climate_local", "surface_support", "coating"):
            self.assertNotEqual(first[name].ref.key, second[name].ref.key)
        for name in ("climate_base", "terrain_base"):
            self.assertEqual(first[name].ref, second[name].ref)

    def test_new_service_replays_the_same_refs(self):
        expected = self.seam.run(self.seam.final())
        other = Seam()
        self.addCleanup(other.service.shutdown)
        self.assertEqual(expected, other.run(other.final()))


class GeoFinalProviderTests(TestCase):
    def setUp(self):
        self.inputs = view()
        plans = bundle(self.inputs)
        self.upstream = {name: getattr(plans, name) for name in (
            "relief", "hydrology_routes", "river_relief", "water_placement")}
        self.registry, self.handles = PlanRegistry(), {}
        for slot, input_type, output_type in (
                (S.RELIEF, ReliefPlanInput, ReliefPlan),
                (S.HYDROLOGY_ROUTES, GeoHydrologyPlanInput, GeoHydrologyRoutesPlan),
                (S.RIVER_RELIEF, RiverReliefInput, RiverReliefPlan),
                (S.WATER_PLACEMENT, GeoWaterPlacementInput, GeoWaterPlacementPlan)):
            handle = declared_binding(geo_surface_plan_binding(slot), input_type, output_type)
            self.handles[slot.value] = handle
            self.registry.register(handle, FrozenUpstream())
        self.final = declared_binding(geo_surface_plan_binding(S.HYDROLOGY), HydrologyFinalInput, GeoHydrologyPlan)
        self.assembler = HydrologyFactsAssembler()
        self.registry.register(self.final, GeoHydrologyFinalPlanProvider(**self.handles, assembler=self.assembler))
        policy = CachePolicy(max_retained_bytes=10000000, max_entry_bytes=5000000)
        self.service = PlanningService(self.registry, CacheService(MemoryCache(policy), policy),
            PlanningExecutionPolicy(max_workers=2, max_pending_builds=8))
        self.addCleanup(self.service.shutdown)

    def build(self, upstream=None):
        available = self.upstream if upstream is None else upstream
        reader, deps = PlanDependencyReader(self.registry), []
        for declaration in self.final.dependency_contracts:
            name = declaration.slot
            envelope = available[name]
            reader = reader.with_plan(name, self.handles[name], envelope)
            deps.append(PlanDependency(slot=name, ref=envelope.ref))
        dependencies = tuple(deps)
        meta, scope = self.final.metadata, WorldPlanScope()
        inputs = self.inputs.hydrology_final
        request = PlanRequest[HydrologyFinalInput](key=PlanKey(world_uid="world", scope=scope,
            contract_id=meta.id, schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=self.final.fingerprint_inputs("world", scope, inputs, dependencies)),
            inputs=inputs, dependencies=dependencies)
        return self.service.get_or_build(self.final, request, reader, wait=Wait())

    def test_geo_final_reuses_domain_facts_once_and_retains_direct_water_ref(self):
        with patch.object(self.assembler, "assemble", wraps=self.assembler.assemble) as assemble:
            first = self.build()
            self.assertEqual(self.build(), first)
            assemble.assert_called_once()
        routes = self.upstream["hydrology_routes"].payload
        self.assertEqual(first.payload.source_mapping, routes.source_mapping)
        self.assertEqual(first.payload.classification_decisions, routes.classification_decisions)
        self.assertEqual(next(dep.ref for dep in first.dependencies if dep.slot == S.WATER_PLACEMENT.value),
            self.upstream["water_placement"].ref)

    def test_mismatched_upstream_provenance_is_rejected_before_domain_facts(self):
        for name, slot in (("hydrology_routes", S.WATER_PLACEMENT), ("relief", S.WATER_PLACEMENT),
                           ("river_relief", S.HYDROLOGY_ROUTES)):
            envelope = self.upstream[name]
            deps = tuple((dep.slot, SimpleNamespace(ref=dep.ref.model_copy(
                update={"output_fingerprint": b"x" * 32}) if dep.slot == slot.value else dep.ref))
                for dep in envelope.dependencies)
            invalid = seal(self.handles[name], envelope.payload, deps)
            available = self.upstream | {name: invalid}
            # Keep the rest of the chain coherent so the failed edge is isolated.
            for dependent in ("hydrology_routes", "river_relief"):
                if dependent == name:
                    continue
                previous = available[dependent]
                actual = tuple((dep.slot, SimpleNamespace(ref=available[dep.slot].ref
                    if dep.slot in available else dep.ref)) for dep in previous.dependencies)
                available[dependent] = seal(self.handles[dependent], previous.payload, actual)
            with self.subTest(phase=name), patch.object(self.assembler, "assemble") as assemble:
                with self.assertRaises(PlanBuildFailure):
                    self.build(available)
                assemble.assert_not_called()

    def test_changed_water_provenance_cannot_hit_a_cached_final(self):
        first = self.build()
        water = self.upstream["water_placement"]
        changed = water.model_copy(update={"ref": water.ref.model_copy(update={"key": water.ref.key.model_copy(
            update={"input_fingerprint": b"x" * 32})})})
        with self.assertRaises(PlanBuildFailure):
            self.build(self.upstream | {"water_placement": changed})
        self.assertEqual(self.build(), first)

    def test_final_carries_route_classification_without_resolving_it_again(self):
        before = self.build()
        decision = ValueSelectionDecision[HydrologyExecutionMode, WaterPolicyReason](
            operation=PolicyOperation.VALUE_SELECTION, state=PolicyState.DISABLED,
            effective_priority=None, behavior=HydrologyExecutionMode.DISABLED,
            reasons=(PolicyReason[WaterPolicyReason](domain_reason=None, common_reason=PolicyDisableReason.ENABLED_FALSE),),
            waiting_supports=(), provenance=(), issues=())
        routes = self.upstream["hydrology_routes"]
        classified = routes.payload.model_copy(update={"classification_decisions": ((WaterGenerationCategory.OCEAN, decision),)})
        routes = seal(self.handles["hydrology_routes"], classified, tuple(
            (dep.slot, SimpleNamespace(ref=dep.ref)) for dep in routes.dependencies))
        river = self.upstream["river_relief"]
        river = seal(self.handles["river_relief"], river.payload, tuple(
            (dep.slot, SimpleNamespace(ref=routes.ref if dep.slot == "hydrology_routes" else dep.ref))
            for dep in river.dependencies))
        after = self.build(self.upstream | {"hydrology_routes": routes, "river_relief": river})
        self.assertEqual(after.payload.classification_decisions, classified.classification_decisions)
        self.assertEqual(after.payload.source_mapping, classified.source_mapping)
        self.assertEqual(after.payload.model_copy(update={"classification_decisions": ()}), before.payload)


class GeoReliefProviderTests(TestCase):
    def setUp(self):
        from tests.planning.providers.test_domain_providers import RiverReliefProviderTests
        self.pc = RiverReliefProviderTests()
        self.pc.setUp()
        self.addCleanup(self.pc.doCleanups)
        self.seam = ReliefSeam(self.pc)
        self.addCleanup(self.seam.service.shutdown)

    def relief(self, upstream=None):
        return self.seam.build("relief", self.seam.inputs,
            self.seam.upstream if upstream is None else upstream)

    def routes(self):
        coarse = self.pc.RouteFixture.route()
        fine = self.pc.RouteFixture.route(fine=True)
        return self.pc.RouteFixture.routes(coarse_routes=(coarse,), fine_routes=(fine,),
            fine_base_surface_z=(((0, 0), 5), ((1, 0), 9), ((2, 0), 7)))

    def river(self, payload, *, mapping=None, decisions=()):
        from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
        relief = self.relief()
        routes = self.seam.seal("hydrology_routes", GeoHydrologyRoutesPlan(base=payload,
            source_mapping=mapping if mapping is not None else SourceBodyMapping(entries=()),
            classification_decisions=decisions),
            (("relief", relief), ("water_placement", self.seam.upstream["water_placement"])))
        return self.seam.build("river_relief", self.pc.river_inputs,
            {"relief": relief, "hydrology_routes": routes})

    def test_geo_pre_river_relief_matches_pc_mountain_basin_and_light_geometry(self):
        from app.application.encoding.canonicalCodec import encode
        from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
        before = {name: encode(envelope, SURFACE_MANIFEST) for name, envelope in self.seam.upstream.items()}
        result = self.relief()
        self.assertEqual(result.payload, self.seam.expected)
        self.assertTrue(result.payload.mountain_layout.entries)
        self.assertTrue(result.payload.light.mountain_cells)
        self.assertEqual({name: encode(envelope, SURFACE_MANIFEST) for name, envelope in self.seam.upstream.items()}, before)

    def test_geo_coarse_and_fine_riverbeds_match_pc_and_preserve_receivers(self):
        base = self.routes()
        expected = self.pc.river(base).payload
        result = self.river(base)
        self.assertEqual(result.payload, expected)
        self.assertTrue(result.payload.coarse_beds)
        self.assertTrue(result.payload.fine_beds)
        receiver = base.coarse_routes[0].receiver_cell
        self.assertEqual(dict(result.payload.surface_z)[receiver], dict(self.seam.expected.surface_z)[receiver])
        fine_receiver = base.fine_routes[0].receiver_cell
        self.assertEqual(dict(result.payload.fine_surface_z)[fine_receiver], dict(base.fine_base_surface_z)[fine_receiver])

    def test_relief_warm_cache_and_clear_preserve_refs_without_reselection(self):
        from app.application.worldData.generators.terrain.relief.planning import reliefPlanProvider as module
        with patch.object(module, "_mountain_layout", wraps=module._mountain_layout) as layout:
            first = self.relief()
            self.assertEqual(self.relief(), first)
            self.assertEqual(layout.call_count, 1)
            self.seam.backend.clear()
            self.assertEqual(self.relief(), first)
            self.assertEqual(layout.call_count, 2)

    def test_river_does_not_repeat_pre_river_geometry_and_replays_its_cache(self):
        from app.application.worldData.generators.terrain.relief.planning import reliefPlanProvider as module
        self.relief()
        with patch.object(module, "_mountain_layout", side_effect=AssertionError("mountain selection repeated")), \
                patch.object(module, "apply_basin_z", side_effect=AssertionError("basin carve repeated")):
            first = self.river(self.routes())
            self.assertEqual(self.river(self.routes()), first)
        codec = self.seam.handles["river_relief"].cache_binding.codec
        self.assertEqual(codec.decode(codec.encode(first)), first)

    def test_geo_only_route_metadata_changes_refs_without_changing_terrain(self):
        from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
        decision = ValueSelectionDecision[HydrologyExecutionMode, WaterPolicyReason](
            operation=PolicyOperation.VALUE_SELECTION, state=PolicyState.READY, effective_priority=None,
            behavior=HydrologyExecutionMode.DECLARED_ONLY, reasons=(), waiting_supports=(), provenance=(), issues=())
        first = self.river(self.routes())
        second = self.river(self.routes(), mapping=SourceBodyMapping(entries=(
            SourceBodyMappingEntry(source_uid="dry-source", body_uids=()),)),
            decisions=((WaterGenerationCategory.OCEAN, decision),))
        self.assertEqual(first.payload, second.payload)
        self.assertNotEqual(first.ref, second.ref)

    def test_mismatched_relief_and_river_refs_fail_before_terrain_computation(self):
        from app.application.worldData.generators.terrain.relief.planning import reliefPlanProvider as module
        water = self.seam.upstream["water_placement"]
        wrong = self.seam.seal("water_placement", water.payload, (("terrain_base", SimpleNamespace(
            ref=self.seam.upstream["terrain_base"].ref.model_copy(update={"output_fingerprint": b"x"*32}))),))
        with patch.object(module, "_plan_relief") as compute:
            with self.assertRaises(PlanBuildFailure):
                self.relief(self.seam.upstream | {"water_placement": wrong})
            compute.assert_not_called()
        relief = self.relief()
        from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
        routes = self.seam.seal("hydrology_routes", GeoHydrologyRoutesPlan(base=self.routes(),
            source_mapping=SourceBodyMapping(entries=()), classification_decisions=()),
            (("relief", SimpleNamespace(ref=relief.ref.model_copy(update={"output_fingerprint": b"x"*32}))),
             ("water_placement", water)))
        with patch.object(module, "_plan_river_relief") as compute:
            with self.assertRaises(PlanBuildFailure):
                self.seam.build("river_relief", self.pc.river_inputs, {"relief": relief, "hydrology_routes": routes})
            compute.assert_not_called()

    def test_pc_water_cannot_enter_the_geo_relief_handle(self):
        from app.application.planning.service.planningService import PlanContractFailure
        with self.assertRaises((ValueError, PlanContractFailure)):
            self.relief(self.seam.upstream | {"water_placement": self.pc.water.get()})

    def test_pc_routes_cannot_enter_the_geo_river_handle(self):
        from app.application.planning.service.planningService import PlanContractFailure
        relief = self.relief()
        routes = seal(self.pc.routes_binding, self.routes(), (("relief", relief),), world_uid=self.seam.world_uid)
        with self.assertRaises((ValueError, PlanContractFailure)):
            self.seam.build("river_relief", self.pc.river_inputs, {"relief": relief, "hydrology_routes": routes})

    def test_real_geo_relief_river_and_final_providers_share_the_same_refs(self):
        from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
        from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
        relief = self.relief()
        route = self.pc.RouteFixture.route()
        base = self.pc.RouteFixture.routes(coarse_open_water=((route.receiver_cell,
            MapCellHydrology(liquid_candidate=True, water_body_uid="lake")),))
        routes = self.seam.seal("hydrology_routes", GeoHydrologyRoutesPlan(base=base,
            source_mapping=SourceBodyMapping(entries=()), classification_decisions=()),
            (("relief", relief), ("water_placement", self.seam.upstream["water_placement"])))
        available = self.seam.upstream | {"relief": relief, "hydrology_routes": routes}
        river = self.seam.build("river_relief", self.pc.river_inputs, available)
        final = declared_binding(geo_surface_plan_binding(S.HYDROLOGY), HydrologyFinalInput, GeoHydrologyPlan)
        self.seam.handles["hydrology"] = final
        self.seam.registry.register(final, GeoHydrologyFinalPlanProvider(self.seam.handles["relief"],
            self.seam.handles["hydrology_routes"], self.seam.handles["river_relief"],
            self.seam.handles["water_placement"], HydrologyFactsAssembler()))
        inputs = HydrologyFinalInput(enabled=True, grid=self.seam.inputs.grid,
            topology=self.seam.upstream["water_placement"].payload.topology)
        available |= {"river_relief": river}
        result = self.seam.build("hydrology", inputs, available)
        self.assertEqual(result.payload.coarse_surface_z, river.payload.surface_z)
        self.assertEqual(dict(result.payload.coarse_hydro)[route.receiver_cell].water_body_uid, "lake")
        self.assertEqual(result.payload.source_mapping, routes.payload.source_mapping)
        self.assertEqual(self.seam.build("hydrology", inputs, available), result)


class GeoRoutesProviderTests(TestCase):
    def setUp(self):
        from tests.geo1.integration.test_activation import GeoRouteAssemblyTests
        from app.application.policy.policyResolver import PolicyResolver
        from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import GeoHydrologyRoutesPlanProvider
        from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import GeoRiverReliefPlanProvider
        self.domain = GeoRouteAssemblyTests()
        self.domain.setUp()
        self.addCleanup(self.domain.doCleanups)
        self.registry, self.handles = PlanRegistry(), {}
        for slot, input_type, output_type in ((S.RELIEF, ReliefPlanInput, ReliefPlan),
                (S.WATER_PLACEMENT, GeoWaterPlacementInput, GeoWaterPlacementPlan),
                (S.HYDROLOGY_ROUTES, GeoHydrologyPlanInput, GeoHydrologyRoutesPlan),
                (S.RIVER_RELIEF, RiverReliefInput, RiverReliefPlan),
                (S.HYDROLOGY, HydrologyFinalInput, GeoHydrologyPlan)):
            self.handles[slot.value] = declared_binding(geo_surface_plan_binding(slot), input_type, output_type)
        h = self.handles
        self.policy, self.assembler = PolicyResolver(), self.domain.owner
        self.registry.register(h["water_placement"], FrozenUpstream())
        self.registry.register(h["relief"], FrozenUpstream())
        self.registry.register(h["hydrology_routes"], GeoHydrologyRoutesPlanProvider(
            h["relief"], h["water_placement"], self.assembler, self.policy))
        self.registry.register(h["river_relief"], GeoRiverReliefPlanProvider(h["relief"], h["hydrology_routes"]))
        self.registry.register(h["hydrology"], GeoHydrologyFinalPlanProvider(h["relief"], h["hydrology_routes"],
            h["river_relief"], h["water_placement"], HydrologyFactsAssembler()))
        water = self.seal("water_placement", self.domain.placement)
        self.upstream = {"water_placement": water,
            "relief": self.seal("relief", self.domain.pc.before.payload, (("water_placement", water),))}
        policy = CachePolicy(max_retained_bytes=10000000, max_entry_bytes=5000000)
        self.service = PlanningService(self.registry, CacheService(MemoryCache(policy), policy),
            PlanningExecutionPolicy(max_workers=2, max_pending_builds=8))
        self.addCleanup(self.service.shutdown)

    def seal(self, name, payload, upstream=()):
        return seal(self.handles[name], payload, upstream, world_uid="climate-world")

    def build(self, inputs=None, *, name="hydrology_routes", available=None):
        inputs = self.domain.inputs if inputs is None else inputs
        available = self.upstream if available is None else available
        handle, reader, deps = self.handles[name], PlanDependencyReader(self.registry), []
        for declaration in handle.dependency_contracts:
            slot = declaration.slot
            envelope = available[slot]
            reader = reader.with_plan(slot, self.handles[slot], envelope)
            deps.append(PlanDependency(slot=slot, ref=envelope.ref))
        dependencies = tuple(deps)
        meta, scope = handle.metadata, WorldPlanScope()
        request = PlanRequest[type(inputs)](key=PlanKey(world_uid="climate-world", scope=scope,
            contract_id=meta.id, schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=handle.fingerprint_inputs("climate-world", scope, inputs, dependencies)),
            inputs=inputs, dependencies=dependencies)
        return self.service.get_or_build(handle, request, reader, wait=Wait())

    def test_real_provider_runs_common_policy_and_assembly_once_then_uses_cache(self):
        with patch.object(self.policy, "resolve", wraps=self.policy.resolve) as policy, \
                patch.object(self.assembler, "assemble_geo", wraps=self.assembler.assemble_geo) as assemble, \
                patch("app.application.jsonValidation.worldRow.hydrology", side_effect=AssertionError("live World read")):
            result = self.build()
            self.assertEqual(self.build(), result)
            self.assertEqual(policy.call_count, 3)
            assemble.assert_called_once()
        self.assertEqual(result.payload.base, self.domain.pc.routes().payload)
        self.assertTrue(result.payload.base.coarse_routes and result.payload.base.fine_routes)
        self.assertEqual(result.payload.classification_decisions, self.domain.decisions)
        self.assertEqual(result.payload.source_mapping, self.domain.assemble().payload.source_mapping)
        codec = self.handles["hydrology_routes"].cache_binding.codec
        self.assertEqual(codec.decode(codec.encode(result)), result)

    def test_captured_category_overrides_and_inheritance_drive_policy(self):
        from tests.geo1.integration.support.pipeline import rebuild
        inputs = rebuild(self.domain.inputs, generation=rebuild(self.domain.inputs.generation, autoresolve=True),
            sea_generation=rebuild(self.domain.inputs.sea_generation, autoresolve=False),
            lake_generation=rebuild(self.domain.inputs.lake_generation, autoresolve=False))
        result = self.build(inputs)
        decisions = dict(result.payload.classification_decisions)
        self.assertIs(decisions[WaterGenerationCategory.SEA].require_behavior(), HydrologyExecutionMode.DECLARED_ONLY)
        self.assertIs(decisions[WaterGenerationCategory.LAKE].require_behavior(), HydrologyExecutionMode.DECLARED_ONLY)
        self.assertIs(decisions[WaterGenerationCategory.OCEAN].require_behavior(), HydrologyExecutionMode.AUTORESOLVE)
        self.assertTrue(all(d.provenance for d in decisions.values()))

    def test_category_edit_changes_key_without_hidden_policy_cache(self):
        from tests.geo1.integration.support.pipeline import rebuild
        first = self.build()
        inputs = rebuild(self.domain.inputs,
            sea_generation=rebuild(self.domain.inputs.sea_generation, water_fraction=0.25))
        with patch.object(self.policy, "resolve", wraps=self.policy.resolve) as policy:
            second = self.build(inputs)
            self.assertEqual(self.build(inputs), second)
            self.assertEqual(policy.call_count, 3)
        self.assertNotEqual(first.ref.key, second.ref.key)
        self.assertEqual(first.payload, second.payload)

    def test_wrong_relief_water_provenance_fails_before_policy_or_fill(self):
        water = self.upstream["water_placement"]
        wrong = self.seal("relief", self.upstream["relief"].payload, (("water_placement", SimpleNamespace(
            ref=water.ref.model_copy(update={"output_fingerprint": b"x"*32}))),))
        with patch.object(self.policy, "resolve") as policy, patch.object(self.assembler, "assemble_geo") as assemble:
            with self.assertRaises(PlanBuildFailure):
                self.build(available=self.upstream | {"relief": wrong})
            policy.assert_not_called()
            assemble.assert_not_called()

    def test_water_dependency_edit_invalidates_the_coherent_route_chain(self):
        from tests.geo1.integration.support.pipeline import rebuild
        first = self.build()
        water = self.upstream["water_placement"]
        uid, decision = water.payload.source_decisions[0]
        changed = rebuild(water.payload, source_decisions=((uid, rebuild(decision,
            effective_priority=decision.effective_priority+1)), *water.payload.source_decisions[1:]))
        water = self.seal("water_placement", changed)
        relief = self.seal("relief", self.upstream["relief"].payload, (("water_placement", water),))
        second = self.build(available={"water_placement": water, "relief": relief})
        self.assertNotEqual(first.ref.key, second.ref.key)
        self.assertEqual(first.payload, second.payload)

    def test_real_routes_river_relief_and_final_preserve_one_policy_result(self):
        with patch.object(self.policy, "resolve", wraps=self.policy.resolve) as policy:
            routes = self.build()
            available = self.upstream | {"hydrology_routes": routes}
            river = self.build(self.domain.pc.river_inputs, name="river_relief", available=available)
            available |= {"river_relief": river}
            final = self.build(self.domain.pc.final_inputs, name="hydrology", available=available)
            self.assertEqual(policy.call_count, 3)
        self.assertEqual(final.payload.coarse_surface_z, river.payload.surface_z)
        self.assertEqual(final.payload.source_mapping, routes.payload.source_mapping)
        self.assertEqual(final.payload.classification_decisions, routes.payload.classification_decisions)
        self.assertTrue(final.payload.sparse_fine_hydro)
        self.assertEqual(self.build(self.domain.pc.final_inputs, name="hydrology", available=available), final)

    def test_disabled_root_yields_common_disabled_decisions_and_no_fill(self):
        from tests.geo1.integration.support.pipeline import rebuild
        with patch.object(self.assembler._water, "_materialize", side_effect=AssertionError("disabled fill")):
            result = self.build(rebuild(self.domain.inputs, enabled=False))
        self.assertTrue(all(decision.state is PolicyState.DISABLED
            for _, decision in result.payload.classification_decisions))
        self.assertFalse(result.payload.base.water_bodies or result.payload.base.coarse_routes
            or result.payload.base.fine_routes or result.payload.source_mapping.entries)


class TerrainRegionProviderTests(TestCase):
    def setUp(self):
        from app.application.worldData.generators.terrain.regions.regionExtent import TerrainRegionPlanProvider
        from app.dataModel.terrain.regions.regionPlanningInput import TerrainRegionPlanningInput
        from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
        from tests.geo1.regions.test_extent import inputs, WORLD
        self.inputs, self.world_uid = inputs(fine_span=2), WORLD.world_uid
        self.handle = declared_binding(geo_surface_plan_binding(S.TERRAIN_REGIONS), TerrainRegionPlanningInput, TerrainRegionPlan)
        self.registry, self.provider = PlanRegistry(), TerrainRegionPlanProvider()
        self.registry.register(self.handle, self.provider)
        policy = CachePolicy(max_retained_bytes=10000000, max_entry_bytes=5000000)
        self.service = PlanningService(self.registry, CacheService(MemoryCache(policy), policy),
            PlanningExecutionPolicy(max_workers=2, max_pending_builds=8))
        self.addCleanup(self.service.shutdown)

    def request(self, inputs=None):
        inputs = self.inputs if inputs is None else inputs
        meta, scope = self.handle.metadata, WorldPlanScope()
        return PlanRequest[type(inputs)](key=PlanKey(world_uid=self.world_uid, scope=scope,
            contract_id=meta.id, schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=self.handle.fingerprint_inputs(self.world_uid, scope, inputs, ())),
            inputs=inputs, dependencies=())

    def build(self, inputs=None):
        return self.service.get_or_build(self.handle, self.request(inputs),
            PlanDependencyReader(self.registry), wait=Wait())

    def test_real_region_kernel_cache_and_codec_preserve_supplied_identity(self):
        from app.application.worldData.generators.terrain.regions import regionExtent as module
        from tests.geo1.regions.test_extent import WORLD
        expected = module.prepare_terrain_regions(WORLD, inputs=self.inputs)
        with patch.object(module, "prepare_terrain_regions", wraps=module.prepare_terrain_regions) as kernel:
            first = self.build()
            self.assertEqual(self.build(), first)
            kernel.assert_called_once()
        self.assertEqual(first.payload, expected)
        self.assertEqual(first.payload.snapshot.snapshot_uid, self.inputs.snapshot_uid)
        self.assertEqual(first.payload.snapshot.world_region.region_uid, self.inputs.world_region_uid)
        self.assertEqual(first.payload.snapshot.world_region.generation_area_fine2, 48)
        self.assertEqual(self.handle.cache_binding.codec.decode(self.handle.cache_binding.codec.encode(first)), first)
        self.assertEqual(first.dependencies, ())
        self.assertEqual(first.diagnostics, ())

    def test_identity_and_geometry_edits_invalidate_request_and_source_revision(self):
        from tests.geo1.integration.support.pipeline import rebuild
        from app.application.worldData.planning.composition.surfacePlanningCapture import _revision
        from app.dataModel.spatial.regionShape import BboxShape
        from app.dataModel.terrain.regions.regionPlanningInput import RegionGeometryInput
        variants = (self.inputs, rebuild(self.inputs, snapshot_uid="next-snapshot"),
            rebuild(self.inputs, world_region_uid="next-world-region"),
            rebuild(self.inputs, regions=(RegionGeometryInput(region_uid="authored",
                geometry=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1)),)))
        plans = tuple(self.build(value) for value in variants)
        self.assertEqual(len({plan.ref.key for plan in plans}), len(plans))
        self.assertEqual(len({_revision(self.world_uid, (value,)) for value in variants}), len(variants))
        self.assertEqual(plans[1].payload.snapshot.snapshot_uid, "next-snapshot")
        self.assertEqual(plans[2].payload.snapshot.world_region.region_uid, "next-world-region")
        self.assertIsNotNone(plans[3].payload.snapshot.region_for("authored"))

    def test_missing_declared_bounds_never_produces_world_extent_from_topology(self):
        from tests.geo1.integration.support.pipeline import rebuild
        from app.dataModel.spatial.regionShape import BboxShape
        from app.dataModel.terrain.regions.regionPlanningInput import RegionGeometryInput
        inputs = rebuild(self.inputs, declared_world_bounds=None,
            regions=(RegionGeometryInput(region_uid="authored", geometry=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1)),))
        plan = self.build(inputs).payload
        self.assertIsNone(plan.snapshot.world_region)
        self.assertEqual(tuple(coverage.region_uid for coverage in plan.coverages), ("authored",))
        self.assertEqual(plan.snapshot.snapshot_uid, inputs.snapshot_uid)

    def test_topology_normalization_replays_without_an_extra_geometry_path(self):
        from tests.geo1.regions.test_extent import inputs, WORLD
        from app.application.worldData.generators.terrain.regions.regionExtent import prepare_terrain_regions
        from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
        for mode in WorldTopologyMode:
            value = inputs(mode=mode, fine_span=2)
            with self.subTest(mode=mode):
                actual = self.build(value)
                self.assertEqual(actual.payload, prepare_terrain_regions(WORLD, inputs=value))
                self.assertEqual(self.build(value), actual)
                area = sum(span.x1-span.x0 for coverage in actual.payload.coverages for span in coverage.spans)
                self.assertEqual(area, actual.payload.snapshot.world_region.generation_area_fine2)

    def test_foreign_claim_owner_is_not_hidden_by_the_provider(self):
        from tests.geo1.regions.test_extent import inputs, claim_ref
        from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
        from app.dataModel.terrain.regions.regionPlanningInput import RegionGeometryInput
        value = inputs(RegionGeometryInput(region_uid="claim", geometry=RegionCoverage(region_uid="claim", spans=()),
            owner_ref=claim_ref("other-world")))
        with self.assertRaises(PlanBuildFailure) as error:
            self.build(value)
        self.assertEqual(error.exception.issues[0].code, "TERRAIN_REGION_IDENTITY_MISMATCH")

    def test_shutdown_is_checked_before_and_after_the_region_kernel(self):
        from unittest.mock import Mock
        from app.application.planning.service.planningService import PlanWaitCancelled
        from app.application.worldData.generators.terrain.regions import regionExtent as module
        for side_effect, calls in (([PlanWaitCancelled()], 0), ([None, PlanWaitCancelled()], 1)):
            control = Mock()
            control.raise_if_shutdown.side_effect = side_effect
            with self.subTest(calls=calls), patch.object(module, "prepare_terrain_regions",
                    wraps=module.prepare_terrain_regions) as kernel:
                with self.assertRaises(PlanWaitCancelled):
                    self.provider.build(self.request(), PlanDependencyReader(self.registry), control)
                self.assertEqual(kernel.call_count, calls)
