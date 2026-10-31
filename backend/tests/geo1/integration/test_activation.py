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
        shore = dict(result.materialized.cells)[(3, 2)]
        self.assertIs(shore.role, HydrologyCellRole.SHORE)
        self.assertEqual(shore.water_body_uid, "wet")
        self.assertEqual(self.mapped(result)["shore"], ())

    def test_tied_sources_use_actual_cell_ownership_instead_of_equal_uids(self):
        cells = ((2, 2), (3, 2))
        result = self.fill(dict.fromkeys(cells, -2), (self.spec("a", cells), self.spec("b", cells)))
        actual = tuple(sorted({dict(result.materialized.cells)[cell].water_body_uid for cell in cells}))
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
            self.assertEqual(self.mapped(result)[source], (dict(result.materialized.cells)[cell].water_body_uid,))

    def test_spill_mapping_uses_final_wet_body_after_the_level_changes(self):
        result = self.fill({(2, 2): 0, (2, 1): 3, (2, 0): 3}, (self.spec("spill", ((2, 2),), level=6),))
        cell = dict(result.materialized.cells)[(2, 2)]
        self.assertEqual(cell.z_water_level, 3)
        self.assertEqual(self.mapped(result)["spill"], (cell.water_body_uid,))

    def test_natural_discovery_does_not_create_placement_mapping_entries(self):
        result = self.fill({(2, 2): -2}, (), auto=True)
        self.assertTrue(result.materialized.bodies)
        self.assertEqual(result.materialized.source_mapping.entries, ())

        result = self.fill({(2, 2): -1}, (self.spec("probe", ((2, 2),), level=-2),), auto=True)
        actual = dict(result.materialized.cells)[(2, 2)].water_body_uid
        self.assertEqual(self.mapped(result), {"probe": (actual,)})
        self.assertNotEqual(actual, "probe")
        self.assertIn(actual, dict(result.materialized.uid_aliases).values())

    def test_source_mapping_replays_across_order_and_topology(self):
        from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
        for mode, cells in ((Mode.PLANAR, ((2, 2), (3, 2))), (Mode.WRAPPED, ((0, 1), (5, 1))),
                            (Mode.SPHERE, ((0, 0), (3, 0)))):
            specs = (self.spec("a", (cells[0],)), self.spec("b", (cells[1],)))
            first = self.fill(dict.fromkeys(cells, -2), specs, mode=mode)
            second = self.fill(dict.fromkeys(cells, -2), tuple(reversed(specs)), mode=mode)
            with self.subTest(mode=mode):
                self.assertEqual(first.materialized.source_mapping, second.materialized.source_mapping)
                self.assertEqual(dict(first.materialized.cells), dict(second.materialized.cells))

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


class RouteWaterTransportTests(TestCase):
    def setUp(self):
        from tests.planning.providers.test_domain_providers import WaterAndPaintOwnerTests
        self.fixture = WaterAndPaintOwnerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_open_water_stage_preserves_the_materializers_actual_mapping(self):
        from unittest.mock import patch
        from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
        produced = []
        def capture(*args, **kwargs):
            water = assemble_water_bodies(*args, **kwargs)
            produced.append(water.materialized.source_mapping)
            return water
        with patch("app.application.worldData.generators.hydrology.water.planning.waterBodyJob.assemble_water_bodies",
                   side_effect=capture) as materialize:
            result = self.fixture.water()
        materialize.assert_called_once()
        self.assertTrue(produced[0].entries)
        self.assertEqual(result.payload.source_mapping, produced[0])

    def test_disabled_open_water_carries_explicit_empty_mapping_without_fill(self):
        from unittest.mock import patch
        inputs = self.fixture.fixture.hydro_inputs.model_copy(update={"enabled": False})
        with patch("app.application.worldData.generators.hydrology.water.planning.waterBodyJob.assemble_water_bodies") as fill:
            result = self.fixture.water(inputs=inputs)
            fill.assert_not_called()
        self.assertEqual(result.payload.source_mapping.entries, ())

    def test_open_water_rejects_missing_mapping_and_foreign_body_uids(self):
        value = self.fixture.water().payload
        values = fields(value)
        values.pop("source_mapping")
        with self.assertRaises(ValidationError):
            type(value).model_validate(values)
        invalid = SourceBodyMapping(entries=(SourceBodyMappingEntry(source_uid="accepted", body_uids=("missing-body",)),))
        with self.assertRaisesRegex(ValidationError, "final physical body UIDs"):
            type(value).model_validate(fields(value) | {"source_mapping": invalid})


class GeoWaterDecisionConsumerTests(TestCase):
    def setUp(self):
        from unittest.mock import Mock
        from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
        from tests.geo1.integration.support.pipeline import placement_plan, view, rebuild
        self.placement = placement_plan()
        self.inputs = rebuild(view().hydrology, topology=self.placement.topology)
        bounds = self.inputs.topology.bounds
        footprint = self.placement.basin_specs[0].footprint
        from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY, FineZ, SurfaceGridCoord
        self.surface = tuple((SurfaceGridCoord(GridX(x), GridY(y)), FineZ(-2 if (x, y) in footprint else 10))
            for y in range(bounds.y_min, bounds.y_max+1) for x in range(bounds.x_min, bounds.x_max+1))
        self.owner, self.control = WaterBodyPlanner(), Mock()

    def decisions(self, *, enabled=True, autoresolve=False):
        from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
        from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings, CategoryWaterGenerationSettings
        values = []
        for category in sorted(WaterGenerationCategory, key=lambda c: c.value):
            binding = bind_hydrology_generation_policy(enabled=enabled,
                generation=WorldWaterGenerationSettings(autoresolve=autoresolve), defaults=self.inputs.defaults,
                category=getattr(self.inputs, category.value+"_generation"), root_path=("hydrology",),
                context_path=("classification", category.value))
            values.append((category, PolicyResolver().resolve(binding.spec, binding.inputs, binding.facts,
                mode=self.inputs.resolution_mode)))
        return tuple(values)

    def fill(self, *, inputs=None, surface=None, placement=None, decisions=None):
        return self.owner.plan_geo(world_uid="world", inputs=inputs if inputs is not None else self.inputs,
            surface_z=surface if surface is not None else self.surface,
            placement=placement if placement is not None else self.placement,
            classification_decisions=decisions if decisions is not None else self.decisions(), control=self.control)

    def test_accepted_specs_use_one_existing_kernel_and_keep_actual_mapping(self):
        from unittest.mock import patch
        from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
        module = "app.application.worldData.generators.hydrology.water.planning.waterBodyJob"
        before = tuple(self.surface)
        with patch(module+".assemble_water_bodies", wraps=assemble_water_bodies) as kernel, \
                patch(module + ".WaterBodyJob._select_specs", side_effect=AssertionError("legacy selection")):
            result = self.fill()
        kernel.assert_called_once()
        self.assertEqual(kernel.call_args.args[1], self.placement.basin_specs)
        self.assertFalse(kernel.call_args.kwargs["auto_seas"])
        self.assertFalse(kernel.call_args.kwargs["auto_lakes"])
        self.assertEqual(self.surface, before)
        self.assertTrue(result.payload.water_bodies)
        self.assertEqual(tuple(entry.source_uid for entry in result.payload.source_mapping.entries), ("basin",))
        by_cell = {(cell.gx, cell.gy): value for cell, value in result.payload.coarse_open_water}
        self.assertEqual(result.payload.source_mapping.entries[0].body_uids,
            tuple(sorted({by_cell[cell].water_body_uid for cell in self.placement.basin_specs[0].footprint
                if cell in by_cell and by_cell[cell].liquid_candidate})))

    def test_ready_decisions_do_not_re_read_legacy_enabled_or_autoresolve_gates(self):
        from tests.geo1.integration.support.pipeline import rebuild
        original = self.fill()
        inputs = rebuild(self.inputs, enabled=False, scopes=frozenset(),
            seas=self.inputs.seas.model_copy(update={"enabled": False,
                "autoresolve_coastal_sea": False, "autoresolve_open_ocean": False}),
            lakes=self.inputs.lakes.model_copy(update={"enabled": False, "autoresolve": False}))
        self.assertEqual(self.fill(inputs=inputs), original)

    def test_disabled_decisions_stop_before_kernel_without_claiming_dry_sources(self):
        from unittest.mock import patch
        with patch("app.application.worldData.generators.hydrology.water.planning.waterBodyJob.assemble_water_bodies") as kernel:
            result = self.fill(decisions=self.decisions(enabled=False))
        kernel.assert_not_called()
        self.assertEqual(result.payload.source_mapping.entries, ())
        self.assertFalse(result.payload.coarse_open_water or result.payload.water_bodies or result.diagnostics)

    def test_dry_accepted_source_stays_explicit_in_actual_mapping(self):
        result = self.fill(surface=tuple((cell, 10) for cell, _ in self.surface))
        self.assertEqual(result.payload.source_mapping.entries,
            (SourceBodyMappingEntry(source_uid="basin", body_uids=()),))
        self.assertFalse(result.payload.water_bodies)

    def test_sea_autoresolve_never_discovers_a_second_designed_body(self):
        from tests.geo1.integration.support.pipeline import rebuild
        empty = rebuild(self.placement, records=(), basin_specs=(), outcomes=(), metadata=(), source_decisions=())
        # Entirely submerged flat terrain cannot hold a natural lake. The PC sea
        # discovery would create an ocean here; the GEO consumer must not.
        result = self.fill(placement=empty, surface=tuple((cell, -2) for cell, _ in self.surface),
            decisions=self.decisions(autoresolve=True))
        self.assertFalse(result.payload.water_bodies or result.payload.coarse_open_water)
        self.assertNotIn("WATER_NO_OCEAN_DEPRESSION", tuple(d.issue.code for d in result.diagnostics))

    def test_natural_lake_classification_follows_decision_and_allowed_kinds(self):
        from app.dataModel.hydrology.enums.basinKind import BasinKind
        from tests.geo1.integration.support.pipeline import rebuild
        empty = rebuild(self.placement, records=(), basin_specs=(), outcomes=(), metadata=(), source_decisions=())
        surface = tuple((cell, -2 if (cell.gx, cell.gy) in {(3, 3), (4, 3)} else 10)
                        for cell, _ in self.surface)
        self.assertFalse(self.fill(placement=empty, surface=surface).payload.water_bodies)
        auto = self.fill(placement=empty, surface=surface, decisions=self.decisions(autoresolve=True))
        self.assertTrue(auto.payload.water_bodies)
        self.assertTrue(all(body.kind is BasinKind.LAKE for body in auto.payload.water_bodies))
        self.assertEqual(auto.payload.source_mapping.entries, ())
        inputs = rebuild(self.inputs, allowed_body_kinds=frozenset({BasinKind.OCEAN}))
        self.assertFalse(self.fill(inputs=inputs, placement=empty, surface=surface,
            decisions=self.decisions(autoresolve=True)).payload.water_bodies)

    def test_missing_duplicate_unordered_and_unresolved_decisions_fail_before_fill(self):
        from unittest.mock import patch
        from app.application.planning.service.planningService import PlanBuildFailure
        from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
        ready = self.decisions()
        unresolved = ready[0][1].model_copy(update={"state": PolicyState.UNRESOLVED,
            "behavior": None, "issues": (FieldPathError(path=("generation",), message="unresolved"),)})
        forged = ready[0][1].model_copy(update={"behavior": "autoresolve"})
        for values in ((), ready[:-1], ready+ready[:1], tuple(reversed(ready)),
                ((ready[0][0], unresolved), *ready[1:]), ((ready[0][0], forged), *ready[1:])):
            with self.subTest(values=values), patch(
                    "app.application.worldData.generators.hydrology.water.planning.waterBodyJob.assemble_water_bodies") as kernel:
                with self.assertRaises(PlanBuildFailure):
                    self.fill(decisions=values)
                kernel.assert_not_called()

    def test_missing_heights_topology_or_admission_provenance_fails_before_fill(self):
        from unittest.mock import patch
        from app.application.planning.service.planningService import PlanBuildFailure
        wrong = self.placement.model_copy(update={"source_decisions": ()})
        for updates in ({"surface": self.surface[:-1]}, {"placement": wrong},
                {"inputs": self.inputs.model_copy(update={"topology": self.inputs.topology.model_copy(update={"mode": "wrapped"})})}):
            with self.subTest(updates=updates), patch(
                    "app.application.worldData.generators.hydrology.water.planning.waterBodyJob.assemble_water_bodies") as kernel:
                with self.assertRaises(PlanBuildFailure):
                    self.fill(**updates)
                kernel.assert_not_called()


class GeoRouteAssemblyTests(TestCase):
    def setUp(self):
        from unittest.mock import Mock
        from tests.planning.providers.test_domain_providers import HydrologyProviderTests
        from tests.geo1.integration.support.pipeline import fields, geo_placement
        from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
        from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings, CategoryWaterGenerationSettings
        from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
        from app.dataModel.hydrology.enums.basinKind import BasinKind
        self.pc = HydrologyProviderTests()
        self.pc.setUp()
        self.addCleanup(self.pc.doCleanups)
        self.inputs = GeoHydrologyPlanInput(**fields(self.pc.hydro_inputs),
            generation=WorldWaterGenerationSettings(), defaults=WaterGenerationDefaults(),
            sea_generation=CategoryWaterGenerationSettings(), ocean_generation=CategoryWaterGenerationSettings(),
            lake_generation=CategoryWaterGenerationSettings(),
            allowed_body_kinds=frozenset(BasinKind))
        # GEO requires positive admission. Resolve that fixture explicitly through
        # the existing placement owner while retaining the same accepted geometry.
        positive = self.pc.water_inputs.model_copy(update={"seas":
            self.pc.water_inputs.seas.model_copy(update={"placement_specificity": 2})})
        self.placement = geo_placement(self.pc.water.get(inputs=positive).payload)
        self.owner, self.control = self.pc.routes_assembler, Mock()
        self.decisions = self.generation_decisions()

    def generation_decisions(self, enabled=True):
        from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
        from app.dataModel.hydrology.generation.waterGenerationSettings import CategoryWaterGenerationSettings
        values = []
        for category in sorted(WaterGenerationCategory, key=lambda c: c.value):
            binding = bind_hydrology_generation_policy(enabled=enabled,
                generation=self.inputs.generation, defaults=self.inputs.defaults,
                category=getattr(self.inputs, category.value+"_generation"), root_path=("hydrology",),
                context_path=("classification", category.value))
            values.append((category, PolicyResolver().resolve(binding.spec, binding.inputs, binding.facts,
                mode=self.inputs.resolution_mode)))
        return tuple(values)

    def assemble(self, **updates):
        return self.owner.assemble_geo(**(dict(world_uid="climate-world", inputs=self.inputs,
            relief=self.pc.before.payload, placement=self.placement,
            classification_decisions=self.decisions, control=self.control) | updates))

    def test_real_coarse_and_fine_routes_equal_pc_without_height_changes(self):
        original = self.pc.before.payload
        result = self.assemble()
        self.assertEqual(result.payload.base, self.pc.routes().payload)
        self.assertTrue(result.payload.base.coarse_routes)
        self.assertTrue(result.payload.base.fine_routes)
        self.assertTrue(result.payload.source_mapping.entries)
        self.assertEqual(result.payload.classification_decisions, self.decisions)
        self.assertEqual(self.pc.before.payload, original)
        self.assertEqual(self.assemble(), result)
        self.assertEqual(decode(encode(result.payload, SURFACE_MANIFEST), type(result.payload), SURFACE_MANIFEST), result.payload)

    def spies(self):
        from contextlib import ExitStack
        from unittest.mock import Mock, patch
        stack = ExitStack()
        self.addCleanup(stack.close)
        calls = Mock()
        for name, stage, method in (("water", self.owner._water, "plan_geo"),
                ("coarse", self.owner._coarse, "plan"), ("fine", self.owner._fine, "plan"),
                ("paint", self.owner._paint, "project")):
            spy = stack.enter_context(patch.object(stage, method, wraps=getattr(stage, method)))
            calls.attach_mock(spy, name)
        return calls

    def test_stage_order_and_exact_geo_inputs_reach_existing_river_owners(self):
        calls = self.spies()
        result = self.assemble()
        self.assertEqual([call[0] for call in calls.mock_calls], ["water", "coarse", "fine", "paint"])
        for name in ("water", "coarse", "fine"):
            self.assertIs(getattr(calls, name).call_args.kwargs["inputs"], self.inputs)
            self.assertIs(getattr(calls, name).call_args.kwargs["surface_z"], self.pc.before.payload.surface_z)
        self.assertIs(calls.water.call_args.kwargs["classification_decisions"], self.decisions)
        self.assertEqual(result.payload.source_mapping, self.owner._water.plan_geo(
            world_uid="climate-world", inputs=self.inputs, surface_z=self.pc.before.payload.surface_z,
            placement=self.placement, classification_decisions=self.decisions, control=self.control).payload.source_mapping)

    def test_diagnostic_dispositions_and_order_are_preserved(self):
        from unittest.mock import Mock, patch
        from contextlib import ExitStack
        from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
        from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
        diagnostics = tuple(PlanDiagnostic(issue=FieldPathError(("stage", str(i)), "producer fact", code="SAME_CODE"),
            disposition=kind) for i, kind in enumerate((PlanDiagnosticDisposition.ERROR,
                PlanDiagnosticDisposition.FALLBACK, PlanDiagnosticDisposition.NOTICE)))
        with ExitStack() as stack:
            for stage, method, added in ((self.owner._water, "plan_geo", (diagnostics[0],)),
                    (self.owner._coarse, "plan", (diagnostics[1],)), (self.owner._fine, "plan", (diagnostics[2],)),
                    (self.owner._paint, "project", (diagnostics[0],))):
                original = getattr(stage, method)
                def wrap(*args, _original=original, _added=added, **kwargs):
                    return _original(*args, **kwargs).model_copy(update={"diagnostics": _added})
                stack.enter_context(patch.object(stage, method, side_effect=wrap))
            self.assertEqual(self.assemble().diagnostics, diagnostics)

    def test_stage_failure_stops_all_later_operations(self):
        from unittest.mock import patch
        for name, stage, method in (("water", self.owner._water, "plan_geo"),
                ("coarse", self.owner._coarse, "plan"), ("fine", self.owner._fine, "plan")):
            with self.subTest(name=name), patch.object(stage, method, side_effect=ValueError("phase failed")), \
                    patch.object(self.owner._paint, "project") as paint:
                with self.assertRaisesRegex(ValueError, "phase failed"):
                    self.assemble()
                paint.assert_not_called()

    def test_shutdown_after_water_stops_before_routing(self):
        from unittest.mock import Mock, patch
        from app.application.planning.service.planningService import PlanWaitCancelled
        water = self.owner._water.plan_geo(world_uid="climate-world", inputs=self.inputs,
            surface_z=self.pc.before.payload.surface_z, placement=self.placement,
            classification_decisions=self.decisions, control=self.control)
        control = Mock()
        control.raise_if_shutdown.side_effect = [None, PlanWaitCancelled()]
        with patch.object(self.owner._water, "plan_geo", return_value=water), \
                patch.object(self.owner._coarse, "plan") as coarse, patch.object(self.owner._paint, "project") as paint:
            with self.assertRaises(PlanWaitCancelled):
                self.assemble(control=control)
            coarse.assert_not_called()
            paint.assert_not_called()

    def test_invalid_decisions_stop_before_river_planning(self):
        from unittest.mock import patch
        from app.application.planning.service.planningService import PlanBuildFailure
        with patch.object(self.owner._coarse, "plan") as coarse, patch.object(self.owner._fine, "plan") as fine:
            with self.assertRaises(PlanBuildFailure):
                self.assemble(classification_decisions=())
            coarse.assert_not_called()
            fine.assert_not_called()

    def test_disabled_root_keeps_baseline_river_and_paint_semantics(self):
        from tests.geo1.integration.support.pipeline import rebuild
        result = self.assemble(inputs=rebuild(self.inputs, enabled=False),
            classification_decisions=self.generation_decisions(enabled=False))
        self.assertFalse(result.payload.base.water_bodies or result.payload.base.coarse_routes
            or result.payload.base.fine_routes or result.payload.source_mapping.entries)
        expected = self.owner._paint.project(rivers=self.inputs.declared_rivers,
            coastlines=self.inputs.coastlines, lakes=self.inputs.declared_lakes, anchors=self.inputs.anchors)
        self.assertEqual(result.payload.base.declared_paint, expected.payload)
