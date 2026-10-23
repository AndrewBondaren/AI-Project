"""Canonical protocol vectors and reusable non-domain provider fixtures."""

from dataclasses import dataclass
from threading import Event, Lock
from time import monotonic
import unittest

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.encoding.canonicalCodec import CanonicalCodec
from app.application.planning.service.planFingerprints import input_fingerprint
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, RegisteredTypeEntry, CanonicalTypeKind
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.service.cacheService import CacheService, retained_entry_bytes
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader, PlanRegistry
from app.application.planning.service.planningService import PlanningService, PlanWaitCancelled
from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.planning.contracts.planContract import PlanContractMetadata
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import PlanKey, RegionPlanScope, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
from app.dataModel.cache.policy.cachePolicy import CachePolicy
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot


class Data(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    value: int = Field(ge=0)


MANIFEST = CanonicalSchemaManifest(entries=tuple(RegisteredTypeEntry(type_id=identity, python_type=owner, kind=kind)
    for identity, owner, kind in (
        (1, Data, CanonicalTypeKind.RECORD), (2, PlanKey, CanonicalTypeKind.RECORD),
        (3, PlanRef, CanonicalTypeKind.RECORD), (4, WorldPlanScope, CanonicalTypeKind.RECORD),
        (5, RegionPlanScope, CanonicalTypeKind.RECORD), (6, type(WorldPlanScope().kind), CanonicalTypeKind.ENUM),
        (7, PlanDependency, CanonicalTypeKind.RECORD), (8, PlanDiagnostic, CanonicalTypeKind.RECORD),
        (9, PlanDiagnosticDisposition, CanonicalTypeKind.ENUM), (10, FieldPathError, CanonicalTypeKind.RECORD))))
CANONICAL = CanonicalCodec(MANIFEST)


class EnvelopeCodec:
    def validate(self, value: object) -> PlanEnvelope[Data]:
        return TypeAdapter(PlanEnvelope[Data]).validate_python(value, strict=True)

    def encode(self, value: PlanEnvelope[Data]) -> bytes:
        raise AssertionError("RAM planning does not serialize an envelope")

    def decode(self, encoded: bytes) -> PlanEnvelope[Data]:
        raise AssertionError("RAM planning does not deserialize an envelope")

    def retained_bytes(self, value: PlanEnvelope[Data]) -> int:
        return retained_entry_bytes(value)


def contract(name="test.base", *, declarations=()):
    metadata = PlanContractMetadata(id=name, schema_version=1, algorithm_version=1)

    def fingerprint(world_uid, scope, inputs, dependencies):
        return input_fingerprint(metadata, world_uid, scope, inputs, dependencies, MANIFEST)

    return RegisteredPlanContract(metadata, TypeAdapter(Data).validate_python, fingerprint,
        declarations, CacheBinding(CacheContract[PlanEnvelope[Data]](id="cache." + name, schema_version=1),
                                  EnvelopeCodec()), MANIFEST)


def request(binding, value=2, *, world="world", scope=None, deps=()):
    inputs = Data(value=value)
    scope = WorldPlanScope() if scope is None else scope
    metadata = binding.metadata
    return PlanRequest[Data](key=PlanKey(world_uid=world, scope=scope, contract_id=metadata.id,
        schema_version=metadata.schema_version, algorithm_version=metadata.algorithm_version,
        input_fingerprint=binding.fingerprint_inputs(world, scope, inputs, deps)),
        inputs=inputs, dependencies=deps)


class Wait:
    def __init__(self, seconds=None):
        self.cancelled = Event()
        self.deadline = None if seconds is None else monotonic() + seconds

    def raise_if_cancelled(self):
        if self.cancelled.is_set():
            raise PlanWaitCancelled()

    def remaining_seconds(self):
        return None if self.deadline is None else self.deadline - monotonic()


class Provider:
    def __init__(self, fn=None):
        self.count = 0
        self.fn = fn
        self.lock = Lock()

    def build(self, request, dependencies, control):
        with self.lock:
            self.count += 1
        if self.fn:
            return self.fn(request, dependencies, control)
        return PlanBuildResult[Data](payload=Data(value=request.inputs.value * 2), diagnostics=())


class Harness:
    def __init__(self, *, policy=None, cache_policy=None):
        self.registry = PlanRegistry()
        self.policy = cache_policy or CachePolicy(max_retained_bytes=1000000, max_entry_bytes=500000)
        self.backend = MemoryCache(self.policy)
        self.cache = CacheService(self.backend, self.policy)
        self.service = PlanningService(self.registry, self.cache,
            policy or PlanningExecutionPolicy(max_workers=2, max_pending_builds=4))
        self.empty = PlanDependencyReader(self.registry)

    def register(self, binding=None, provider=None):
        binding, provider = binding or contract(), provider or Provider()
        self.registry.register(binding, provider)
        return binding, provider

    def get(self, binding, *, value=2, dependencies=None, wait=None, req=None):
        return self.service.get_or_build(binding, req or request(binding, value),
            dependencies or self.empty, wait=wait or Wait(5))


class CanonicalTests(unittest.TestCase):
    def test_exact_primitive_tlv_vectors_and_no_bool_int_collision(self):
        def tlv(tag, payload):
            return bytes([tag]) + len(payload).to_bytes(8, "big") + payload
        for value, expected in ((None, tlv(0, b"")), (True, tlv(1, b"\x01")),
                                (0, tlv(2, b"\x00\x00")), (-256, tlv(2, b"\x01\x01\x00")),
                                ("я", tlv(4, "я".encode())), (b"x", tlv(5, b"x"))):
            self.assertEqual(CANONICAL.encode(value), expected)
        self.assertNotEqual(CANONICAL.encode(True), CANONICAL.encode(1))
        self.assertEqual(CANONICAL.encode(-0.0), CANONICAL.encode(0.0))

    def test_sets_sorted_sequences_ordered_and_manifest_ids_stable(self):
        self.assertEqual(CANONICAL.encode(frozenset((3, 1))), CANONICAL.encode(frozenset((1, 3))))
        self.assertNotEqual(CANONICAL.encode((3, 1)), CANONICAL.encode((1, 3)))
        model = Data(value=1)
        self.assertEqual(CANONICAL.encode(model), CanonicalCodec(CANONICAL.manifest).encode(model))
        renamed = CanonicalCodec(CanonicalSchemaManifest(entries=tuple(item.model_copy(update={"type_id": 99})
            if item.python_type is Data else item for item in MANIFEST.entries)))
        self.assertNotEqual(CANONICAL.encode(model), renamed.encode(model))

    def test_unknown_types_mutability_nonfinite_and_incomplete_records_rejected(self):
        @dataclass(frozen=True)
        class Unknown:
            value: int
        for invalid in ([], {}, set(), float("inf"), float("nan"), Unknown(1),
                        Data.model_construct(), Data(value=1).model_copy(update={"extra": 1})):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                CANONICAL.encode(invalid)
        with self.assertRaises(ValueError):
            CanonicalSchemaManifest(entries=(RegisteredTypeEntry(type_id=1, python_type=Data, kind=CanonicalTypeKind.RECORD),
                RegisteredTypeEntry(type_id=1, python_type=PlanKey, kind=CanonicalTypeKind.RECORD)))

    def test_enum_tag_is_distinct_from_wire_string(self):
        self.assertNotEqual(CANONICAL.encode(WorldPlanScope().kind), CANONICAL.encode("world"))


class ClimateBaseProviderTests(unittest.TestCase):
    def setUp(self):
        from app.application.worldData.generators.climate.planning.climatePlanProvider import ClimateBasePlanProvider
        from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND, ClimatePoleBlendDefaults
        from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
        from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
        from app.dataModel.climate.enums.climateZone import ClimateZone, ClimateZoneProfileData
        from app.dataModel.climate.enums.poleKind import PoleKind
        from app.dataModel.climate.enums.poleSource import PoleSource
        from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ResolvedClimateProfile
        from app.dataModel.climate.planning.climatePoints import ClimatePolePoint
        from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput, ManualPoleInput
        from app.dataModel.spatial.grid.gridBBox import GridBBox
        from app.application.encoding.canonicalCodec import encode, decode
        from app.application.planning.service.planFingerprints import cache_item_key

        self.Input, self.Plan, self.Manual = ClimateBaseInput, ClimateBasePlan, ManualPoleInput
        self.Mode, self.Preset, self.Kind = ClimatePoleMode, ClimatePolePreset, PoleKind
        self.blend, self.BBox = CLIMATE_POLE_BLEND, GridBBox
        extra = ((20, ClimateBaseInput), (21, ManualPoleInput), (22, ClimateBasePlan),
                 (23, ResolvedClimateProfile), (24, ClimatePolePoint), (25, GridBBox),
                 (26, ClimatePoleBlendDefaults), (27, ClimateZoneProfileData),
                 (28, PlanEnvelope[ClimateBasePlan]))
        enums = ((30, ClimatePoleMode), (31, ClimatePolePreset), (32, PoleKind), (33, PoleSource))
        self.manifest = CanonicalSchemaManifest(entries=MANIFEST.entries + tuple(
            RegisteredTypeEntry(type_id=identity, python_type=owner, kind=CanonicalTypeKind.RECORD)
            for identity, owner in extra) + tuple(
            RegisteredTypeEntry(type_id=identity, python_type=owner, kind=CanonicalTypeKind.ENUM)
            for identity, owner in enums))
        self.profiles = tuple(ResolvedClimateProfile(key=zone.system_climate, values=zone.value.engine)
                              for zone in ClimateZone.engine_members())
        self.inputs = ClimateBaseInput(seed=17, bbox=GridBBox(-2, 4, -3, 5), fine_span=10,
            mode=ClimatePoleMode.AUTORESOLVE, preset=ClimatePolePreset.BINARY,
            peak_min=-40, peak_max=50, default_zone="temperate", manual_poles=(), profiles=self.profiles, blend=self.blend)
        metadata = PlanContractMetadata(id=f"surface.pc.{SurfacePlanSlot.CLIMATE_BASE.value}", schema_version=1, algorithm_version=1)
        manifest = self.manifest
        plan_type = PlanEnvelope[ClimateBasePlan]

        class ClimateCodec:
            def validate(self, value):
                return TypeAdapter(plan_type).validate_python(value, strict=True)
            def encode(self, value):
                return encode(value, manifest)
            def decode(self, encoded):
                return decode(encoded, plan_type, manifest)
            def retained_bytes(self, value):
                return retained_entry_bytes(value)

        def fingerprint(world, scope, inputs, deps):
            return input_fingerprint(metadata, world, scope, inputs, deps, manifest)

        self.binding = RegisteredPlanContract(metadata, TypeAdapter(ClimateBaseInput).validate_python,
            fingerprint, (), CacheBinding(CacheContract[plan_type](id=f"surface.envelope.pc.{SurfacePlanSlot.CLIMATE_BASE.value}", schema_version=1),
                                         ClimateCodec()), manifest)
        self.h = Harness()
        self.addCleanup(self.h.service.shutdown)
        self.provider = ClimateBasePlanProvider()
        self.h.registry.register(self.binding, self.provider)

    def get(self, inputs=None):
        inputs = inputs if inputs is not None else self.inputs
        metadata = self.binding.metadata
        key = PlanKey(world_uid="climate-world", scope=WorldPlanScope(), contract_id=metadata.id,
            schema_version=metadata.schema_version, algorithm_version=metadata.algorithm_version,
            input_fingerprint=self.binding.fingerprint_inputs("climate-world", WorldPlanScope(), inputs, ()))
        req = PlanRequest[self.Input](key=key, inputs=inputs, dependencies=())
        return self.h.service.get_or_build(self.binding, req, self.h.empty, wait=Wait(5))

    def test_binary_and_single_preset_layout_goldens_and_no_bbox_bootstrap(self):
        base = self.get().payload
        self.assertEqual([(pole.gx, pole.gy, pole.base_temperature) for pole in base.poles], [(1, -3, -22), (1, 5, 32)])
        single = self.get(self.inputs.model_copy(update={"preset": self.Preset.ICE})).payload
        self.assertEqual([(pole.gx, pole.gy) for pole in single.poles], [(2, 1)])
        no_extent = self.get(self.inputs.model_copy(update={"bbox": None})).payload
        self.assertIsNone(no_extent.bbox)
        self.assertEqual([(pole.gx, pole.gy) for pole in no_extent.poles], [(0, 0), (0, 1)])

    def test_first_manual_wins_with_negative_floor_coordinates_and_diagnostics(self):
        manual = self.Manual(location_uid="manual", position=(-1, -11), kind=self.Kind.COLD, zone="arctic")
        extra = self.Manual(location_uid="ignored", position=(100, 100), kind=self.Kind.HOT, zone="tropical")
        plan = self.get(self.inputs.model_copy(update={"manual_poles": (manual, extra)}))
        self.assertEqual([(pole.gx, pole.gy, pole.location_uid) for pole in plan.payload.poles], [(-1, -2, "manual")])
        self.assertEqual(tuple(issue.issue.code for issue in plan.diagnostics), ("multiple_poles",))
        self.assertEqual(plan.diagnostics[0].issue.path, ("manual_poles",))
        missing = manual.model_copy(update={"zone": None})
        fallback = self.get(self.inputs.model_copy(update={"manual_poles": (missing, extra)}))
        self.assertEqual(len(fallback.payload.poles), 2)
        self.assertTrue(all(pole.location_uid is None for pole in fallback.payload.poles))
        self.assertEqual(tuple(issue.issue.code for issue in fallback.diagnostics), ("multiple_poles", "pole_no_zone"))
        self.assertEqual(fallback.diagnostics[1].issue.path, ("manual_poles", 0, "zone"))

    def test_manual_empty_fallback_has_same_diagnostics_on_hit_and_clear(self):
        inputs = self.inputs.model_copy(update={"mode": self.Mode.MANUAL})
        first = self.get(inputs)
        self.assertEqual(first.payload.poles, ())
        self.assertEqual(first.diagnostics[0].issue.code, "manual_mode_no_pole")
        self.assertEqual(first.diagnostics[0].issue.path, ("manual_poles",))
        self.assertEqual(self.get(inputs), first)
        self.h.backend.clear()
        self.assertEqual(self.get(inputs), first)

    def test_input_edits_invalidate_while_hydrology_and_anchors_are_not_base_inputs(self):
        from unittest.mock import patch
        first = self.get()
        with patch.object(self.provider, "build", side_effect=AssertionError("base must HIT")):
            unrelated_hydrology = {(0, 0): 123}
            unrelated_anchors = [(1, 2)]
            unrelated_hydrology[(0, 0)] = -5
            unrelated_anchors.append((4, 5))
            self.assertEqual(self.get(), first)
        for change in ({"seed": 18}, {"fine_span": 20}, {"peak_max": 60},
                       {"bbox": self.BBox(-3, 4, -3, 5)}, {"preset": self.Preset.ICE}):
            self.assertNotEqual(self.get(self.inputs.model_copy(update=change)).ref, first.ref)
        profiles = tuple(profile.model_copy(update={"values": type(profile.values)(
            base_temperature=profile.values.base_temperature + 1,
            typical_elevation_z=profile.values.typical_elevation_z,
            base_rainfall=profile.values.base_rainfall, temperature_variance=profile.values.temperature_variance,
            rainfall_variance=profile.values.rainfall_variance)}) for profile in self.inputs.profiles)
        self.assertNotEqual(self.get(self.inputs.model_copy(update={"profiles": profiles})).ref, first.ref)

    def test_frozen_sampler_goldens_and_no_world_lookups(self):
        from dataclasses import replace
        from unittest.mock import patch
        from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
        from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
        manual = self.Manual(location_uid="cold", position=(0, 0), kind=self.Kind.COLD, zone="arctic")
        plan = self.get(self.inputs.model_copy(update={"manual_poles": (manual,), "bbox": self.BBox(-10, 10, -10, 10)})).payload
        cold = replace(plan.poles[0], base_temperature=-20)
        plan = plan.model_copy(update={"poles": (cold,)})
        with patch("app.application.worldData.generators.climate.registry.profile_for", side_effect=AssertionError("no live World")):
            near = ClimatePlanSampler.sample(plan, GridX(0), GridY(0))
            far = ClimatePlanSampler.sample(plan, GridX(10), GridY(10))
            middle = ClimatePlanSampler.sample(plan, GridX(5), GridY(5))
        self.assertEqual((near.system_climate_zone, near.base_temperature_override, near.typical_elevation_z), ("arctic", -20, 4))
        self.assertEqual((far.system_climate_zone, far.base_temperature_override, far.typical_elevation_z), ("temperate", 12, 0))
        self.assertEqual((middle.system_climate_zone, middle.base_temperature_override, middle.typical_elevation_z), ("temperate", -4, 2))

    def test_envelope_codec_round_trip_including_rich_preset_wire_value(self):
        from app.application.encoding.canonicalCodec import encode, decode
        encoded = encode(self.inputs, self.manifest)
        self.assertEqual(decode(encoded, self.Input, self.manifest), self.inputs)
        envelope = self.get()
        codec = self.binding.cache_binding.codec
        self.assertEqual(codec.decode(codec.encode(envelope)), envelope)

    def test_legacy_unknown_key_alias_fallback_is_preserved(self):
        from types import SimpleNamespace
        from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
        world = SimpleNamespace(world_uid="unknown-climate", default_climate_zone="unknown", climate_zone_registry=None)
        sample = ClimatePoleField(()).sample(world, 0, 0)
        self.assertEqual(sample.system_climate_zone, "temperate")

    def test_multi_pole_blend_tie_order_and_no_poles_sampler_goldens(self):
        from dataclasses import replace
        from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
        from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
        plan = self.get().payload
        cold, hot = plan.poles
        cold = replace(cold, gx=GridX(-10), gy=GridY(0), base_temperature=-20)
        hot = replace(hot, gx=GridX(10), gy=GridY(0), base_temperature=40)
        plan = plan.model_copy(update={"poles": (cold, hot)})
        close = ClimatePlanSampler.sample(plan, GridX(-10), GridY(0))
        middle = ClimatePlanSampler.sample(plan, GridX(0), GridY(0))
        reversed_middle = ClimatePlanSampler.sample(plan.model_copy(update={"poles": (hot, cold)}), GridX(0), GridY(0))
        self.assertEqual((close.system_climate_zone, close.base_temperature_override), ("arctic", -19))
        self.assertEqual((middle.system_climate_zone, middle.base_temperature_override), ("arctic", 10))
        self.assertEqual((reversed_middle.system_climate_zone, reversed_middle.base_temperature_override), ("tropical", 10))
        empty = ClimatePlanSampler.sample(plan.model_copy(update={"poles": ()}), GridX(0), GridY(0))
        self.assertEqual((empty.system_climate_zone, empty.typical_elevation_z, empty.base_temperature_override), ("temperate", 0, None))

    def test_sampler_uses_captured_blend_and_no_bbox_retains_pole_temperature(self):
        from dataclasses import replace
        from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
        from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
        manual = self.Manual(location_uid="cold", position=(0, 0), kind=self.Kind.COLD, zone="arctic")
        plan = self.get(self.inputs.model_copy(update={"manual_poles": (manual,), "bbox": None})).payload
        sample = ClimatePlanSampler.sample(plan, GridX(1000), GridY(1000))
        self.assertEqual((sample.system_climate_zone, sample.base_temperature_override), ("arctic", -22))
        finite = plan.model_copy(update={"bbox": self.BBox(-10, 10, -10, 10)})
        wider = finite.model_copy(update={"blend": replace(finite.blend, single_pole_fade_diagonal_factor=2.0)})
        self.assertNotEqual(ClimatePlanSampler.sample(finite, GridX(10), GridY(10)),
                            ClimatePlanSampler.sample(wider, GridX(10), GridY(10)))

    def test_custom_registry_climate_key_is_not_restricted_to_builtin_enum(self):
        from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
        from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
        custom = self.profiles[0].model_copy(update={"key": "alien"})
        manual = self.Manual(location_uid="custom", position=(0, 0), kind=self.Kind.NEUTRAL, zone="alien")
        plan = self.get(self.inputs.model_copy(update={"profiles": (*self.profiles, custom),
            "default_zone": "alien", "manual_poles": (manual,), "bbox": None})).payload
        self.assertEqual(ClimatePlanSampler.sample(plan, GridX(0), GridY(0)).system_climate_zone, "alien")


class TerrainBaseProviderTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import Mock
        from app.application.worldData.generators.terrain.planning.terrainPlanProvider import TerrainPlanProvider
        from app.application.encoding.canonicalCodec import encode, decode
        from app.dataModel.planning.contracts.planDependency import PlanDependencyContract
        from app.dataModel.planning.identity.planKey import PlanSlot
        from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
        from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
        from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
        from app.dataModel.terrain.planning.terrainPlan import TerrainPlan

        self.climate = ClimateBaseProviderTests()
        self.climate.setUp()
        self.addCleanup(self.climate.doCleanups)
        self.h = self.climate.h
        self.Input, self.Plan, self.Grid = TerrainBaseInput, TerrainPlan, SurfaceGridSettings
        self.slot = PlanSlot(SurfacePlanSlot.CLIMATE_BASE.value)
        self.inputs = TerrainBaseInput(seed=17, bbox=self.climate.inputs.bbox, z_min=-5, z_max=5,
                                      grid=SurfaceGridSettings(fine_span=10, light_side=2))
        self.manifest = CanonicalSchemaManifest(entries=self.climate.manifest.entries + tuple(
            RegisteredTypeEntry(type_id=identity, python_type=owner, kind=CanonicalTypeKind.RECORD)
            for identity, owner in ((40, TerrainBaseInput), (41, TerrainPlan), (42, SurfaceGridSettings),
                                    (43, SurfaceGridCoord), (44, PlanEnvelope[TerrainPlan]))))
        metadata = PlanContractMetadata(id=f"surface.pc.{SurfacePlanSlot.TERRAIN_BASE.value}", schema_version=1, algorithm_version=1)
        manifest = self.manifest

        class TerrainCodec:
            def validate(self, value):
                return TypeAdapter(PlanEnvelope[TerrainPlan]).validate_python(value, strict=True)
            def encode(self, value):
                return encode(value, manifest)
            def decode(self, encoded):
                return decode(encoded, PlanEnvelope[TerrainPlan], manifest)
            def retained_bytes(self, value):
                return retained_entry_bytes(value)

        def fingerprint(world, scope, inputs, deps):
            return input_fingerprint(metadata, world, scope, inputs, deps, manifest)

        climate_meta = self.climate.binding.metadata
        declaration = PlanDependencyContract(slot=self.slot, contract_id=climate_meta.id,
            schema_version=climate_meta.schema_version, algorithm_version=climate_meta.algorithm_version)
        self.binding = RegisteredPlanContract(metadata, TypeAdapter(TerrainBaseInput).validate_python,
            fingerprint, (declaration,), CacheBinding(CacheContract[PlanEnvelope[TerrainPlan]](
                id=f"surface.envelope.pc.{SurfacePlanSlot.TERRAIN_BASE.value}", schema_version=1), TerrainCodec()), manifest)
        self.provider = Mock(wraps=TerrainPlanProvider(self.climate.binding))
        self.h.registry.register(self.binding, self.provider)

    def get(self, inputs=None, climate=None, reader=None):
        inputs = self.inputs if inputs is None else inputs
        climate = self.climate.get() if climate is None else climate
        deps = (PlanDependency(slot=self.slot, ref=climate.ref),)
        metadata = self.binding.metadata
        key = PlanKey(world_uid="climate-world", scope=WorldPlanScope(), contract_id=metadata.id,
            schema_version=metadata.schema_version, algorithm_version=metadata.algorithm_version,
            input_fingerprint=self.binding.fingerprint_inputs("climate-world", WorldPlanScope(), inputs, deps))
        request = PlanRequest[self.Input](key=key, inputs=inputs, dependencies=deps)
        reader = self.h.empty.with_plan(self.slot, self.climate.binding, climate) if reader is None else reader
        return self.h.service.get_or_build(self.binding, request, reader, wait=Wait(5))

    def test_heights_match_legacy_surface_pass_across_topology_modes(self):
        from app.db.models.world import World
        from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
        from app.ids import seed_int
        from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
        from app.application.worldData.generators.terrain.passes.surfacePass import run_surface_pass_coarse
        from app.dataModel.topology.worldTopology import WorldTopologyMode
        climate = self.climate.get()
        box = self.inputs.bbox
        for mode in WorldTopologyMode:
            with self.subTest(mode=mode):
                world = World(world_uid="climate-world", name="baseline", created_at="2026-10-23",
                    z_min=self.inputs.z_min, z_max=self.inputs.z_max, default_climate_zone="temperate",
                    climate_zone_registry=WorldClimateZoneRegistry.canonical_engine().model_dump(mode="json"),
                    world_topology_mode=mode.value, world_bounds=dict(x_min=box.x_min, x_max=box.x_max,
                                                                   y_min=box.y_min, y_max=box.y_max))
                legacy = run_surface_pass_coarse(world, [], ClimatePoleField(climate.payload.poles, box))
                plan = self.get(self.inputs.model_copy(update={"seed": seed_int(world)})).payload
                self.assertEqual({(coord.gx, coord.gy): z for coord, z in plan.surface_z}, legacy.surface_z)
                self.assertEqual(plan.bbox, legacy.bbox)
        # Topology does not enter the frozen base-height projection or the baseline noise kernel.
        self.assertEqual(self.provider.build.call_count, 1)

    def test_clamps_at_both_bounds_and_covers_negative_coordinates(self):
        for level in (-2, 3):
            with self.subTest(level=level):
                plan = self.get(self.inputs.model_copy(update={"z_min": level, "z_max": level})).payload
                self.assertEqual({z for _, z in plan.surface_z}, {level})
                coords = [(coord.gy, coord.gx) for coord, _ in plan.surface_z]
                self.assertEqual(coords, sorted(coords))
                self.assertEqual(coords[0], (-3, -2))
                self.assertEqual(coords[-1], (5, 4))
                self.assertEqual(len(coords), 63)

    def test_hit_clear_and_fresh_service_have_identical_refs_and_diagnostics(self):
        from app.application.planning.service.planFingerprints import cache_item_key
        from app.dataModel.cache.identity.cacheKey import CacheKey
        first = self.get()
        self.assertEqual(self.get(), first)
        self.assertEqual(self.provider.build.call_count, 1)
        self.h.cache.evict(self.binding.cache_binding, CacheKey(contract=self.binding.cache_binding.contract,
            item_key=cache_item_key(first.ref.key, self.manifest)))
        self.assertEqual(self.get(), first)
        self.assertEqual(self.provider.build.call_count, 2)
        other = Harness(policy=PlanningExecutionPolicy(max_workers=1, max_pending_builds=2))
        self.addCleanup(other.service.shutdown)
        other.registry.register(self.climate.binding, self.climate.provider)
        other.registry.register(self.binding, self.provider)
        previous = self.h
        self.h = other
        try:
            self.assertEqual(self.get(), first)
        finally:
            self.h = previous

    def test_effective_seed_extent_scale_and_z_edits_invalidate(self):
        first = self.get()
        for update in ({"seed": 18}, {"bbox": self.climate.BBox(-3, 4, -3, 5)},
                       {"z_min": -1}, {"z_max": 1},
                       {"grid": self.Grid(fine_span=20, light_side=2)},
                       {"grid": self.Grid(fine_span=10, light_side=4)}):
            with self.subTest(update=update):
                edited = self.get(self.inputs.model_copy(update=update))
                self.assertNotEqual(edited.ref.key, first.ref.key)
        self.assertEqual(self.provider.build.call_count, 7)

    def test_dependency_edit_rebuilds_terrain_without_rebuilding_climate(self):
        from dataclasses import replace
        from unittest.mock import patch
        first = self.get()
        profiles = tuple(profile.model_copy(update={"values": replace(profile.values,
            typical_elevation_z=4)}) for profile in self.climate.profiles)
        climate = self.climate.get(self.climate.inputs.model_copy(update={"profiles": profiles}))
        with patch.object(type(self.climate.provider), "build", side_effect=AssertionError("climate rebuild")):
            changed = self.get(climate=climate)
            self.assertEqual(self.get(climate=climate), changed)
        self.assertNotEqual(changed.ref.key, first.ref.key)
        self.assertNotEqual(changed.payload, first.payload)
        self.assertEqual(changed.dependencies, (PlanDependency(slot=self.slot, ref=climate.ref),))
        self.assertEqual(self.provider.build.call_count, 2)

    def test_partial_delivery_and_independent_buffers_preserve_full_world_plan(self):
        first = self.get()
        full = dict(first.payload.surface_z)
        for xs, ys in ((range(-2, 1), range(-3, 1)), (range(1, 5), range(1, 6))):
            delivered = {coord: z for coord, z in self.get().payload.surface_z
                         if coord.gx in xs and coord.gy in ys}
            self.assertEqual(delivered, {coord: z for coord, z in full.items()
                                        if coord.gx in xs and coord.gy in ys})
            delivered.clear()
        full.clear()
        self.assertEqual(self.get(), first)
        self.assertEqual(len(first.payload.surface_z), 63)
        self.assertEqual(self.provider.build.call_count, 1)

    def test_missing_or_stale_dependency_rejected_before_cached_hit(self):
        from app.application.planning.service.planningService import PlanContractFailure
        first = self.get()
        with self.assertRaises(PlanContractFailure):
            self.get(reader=self.h.empty)
        old = self.climate.get()
        changed = self.climate.get(self.climate.inputs.model_copy(update={"seed": 18}))
        reader = self.h.empty.with_plan(self.slot, self.climate.binding, old)
        with self.assertRaises(PlanContractFailure):
            self.get(climate=changed, reader=reader)
        self.assertEqual(self.get(), first)
        self.assertEqual(self.provider.build.call_count, 1)

    def test_payload_and_envelope_round_trip(self):
        from app.application.encoding.canonicalCodec import encode, decode
        first = self.get()
        self.assertEqual(decode(encode(self.inputs, self.manifest), self.Input, self.manifest), self.inputs)
        codec = self.binding.cache_binding.codec
        self.assertEqual(codec.decode(codec.encode(first)), first)


class WaterPlacementProviderTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import Mock
        from app.application.encoding.canonicalCodec import encode, decode
        from app.application.worldData.generators.terrain.planning.waterPlacementPlanProvider import WaterPlacementPlanProvider
        from app.dataModel.planning.contracts.planDependency import PlanDependencyContract
        from app.dataModel.planning.identity.planKey import PlanSlot
        from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput, WaterAnchorInput
        from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
        from app.dataModel.hydrology.worldHydrology import WorldHydrology
        from app.dataModel.hydrology.bands import HydrologyBands
        from app.dataModel.hydrology.seas import HydrologySeasPolicy
        from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
        from app.dataModel.hydrology.shore import HydrologyShoreDefaults
        from app.dataModel.hydrology.declaredBasin import DeclaredBasin
        from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
        from app.dataModel.hydrology.declaredLake import DeclaredLake
        from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
        from app.dataModel.hydrology.enums.basinKind import BasinKind
        from app.dataModel.hydrology.enums.waterSide import WaterSide
        from app.dataModel.spatial.regionShape import (BboxShape, PolygonShape, EllipseShape,
            AnchorRadiusShape, CorridorShape, EdgeNoise, RegionShapeKind)
        from app.dataModel.placement import (PlacementIdentity, PlacementIntent, PlacementCandidate,
            PlacementFootprint, PreparedPlacement, CoastlinePlacementFact, ResolvedPlacement,
            ResolvedWaterPlacement, PlacementMode, AbsoluteMovement, WaterPresence)
        from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
        from app.dataModel.topology.worldTopology import WorldTopology, WorldTopologyMode
        from app.dataModel.topology.worldBounds import WorldBounds
        from app.dataModel.locations.enums.geographicSubtype import GeographicSubtype
        from app.dataModel.validation.enums.resolutionMode import ResolutionMode
        from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace

        self.terrain = TerrainBaseProviderTests()
        self.terrain.setUp()
        self.addCleanup(self.terrain.doCleanups)
        self.h = self.terrain.h
        self.Input, self.Plan, self.Basin, self.Coast, self.Lake = (
            WaterPlacementInput, WaterPlacementPlan, DeclaredBasin, DeclaredCoastline, DeclaredLake)
        self.Mode, self.Topology, self.Bounds = ResolutionMode, WorldTopology, WorldBounds
        self.slot = PlanSlot(SurfacePlanSlot.TERRAIN_BASE.value)
        box = self.terrain.inputs.bbox
        self.topology = WorldTopology(mode="planar", bounds=WorldBounds(x_min=box.x_min, x_max=box.x_max,
                                                                       y_min=box.y_min, y_max=box.y_max))
        defaults = WorldHydrology.canonical_empty()
        self.inputs = WaterPlacementInput(enabled=True, resolution_mode=ResolutionMode.RUNTIME,
            default_water_level=0, seas=defaults.default_seas, lakes=defaults.default_lakes,
            basins=(DeclaredBasin.model_validate(dict(location_uid="basin", kind="ocean", floor_z=-10,
                footprint=dict(kind="bbox", x_min=0, x_max=20, y_min=-20, y_max=0))),),
            coastlines=(), declared_lakes=(), anchors=(), topology=self.topology,
            grid=self.terrain.inputs.grid, z_min=-100, z_max=100, liquid_keys=frozenset(("water", "lava")))
        records = (WaterPlacementInput, WaterAnchorInput, WaterPlacementPlan, PlanEnvelope[WaterPlacementPlan],
            WorldTopology, WorldBounds, HydrologySeasPolicy, HydrologyLakesPolicy, HydrologyShoreDefaults,
            HydrologyBands, DeclaredBasin, DeclaredCoastline, DeclaredLake, HydrologyWaypoint,
            BboxShape, PolygonShape, EllipseShape, AnchorRadiusShape, CorridorShape, EdgeNoise,
            PlacementIdentity, PlacementIntent, PlacementCandidate, PlacementFootprint, PreparedPlacement,
            CoastlinePlacementFact, ResolvedPlacement, ResolvedWaterPlacement, BasinSpec)
        enums = (BasinKind, WaterSide, RegionShapeKind, WorldTopologyMode, GeographicSubtype,
                 ResolutionMode, CoordinateSpace, PlacementMode, AbsoluteMovement, WaterPresence)
        self.manifest = CanonicalSchemaManifest(entries=self.terrain.manifest.entries + tuple(
            RegisteredTypeEntry(type_id=index, python_type=owner, kind=CanonicalTypeKind.RECORD)
            for index, owner in enumerate(records, 50)) + tuple(
            RegisteredTypeEntry(type_id=index, python_type=owner, kind=CanonicalTypeKind.ENUM)
            for index, owner in enumerate(enums, 100)))
        manifest = self.manifest
        metadata = PlanContractMetadata(id=f"surface.pc.{SurfacePlanSlot.WATER_PLACEMENT.value}", schema_version=1, algorithm_version=1)

        class WaterCodec:
            def validate(self, value):
                return TypeAdapter(PlanEnvelope[WaterPlacementPlan]).validate_python(value, strict=True)
            def encode(self, value):
                return encode(value, manifest)
            def decode(self, encoded):
                return decode(encoded, PlanEnvelope[WaterPlacementPlan], manifest)
            def retained_bytes(self, value):
                return retained_entry_bytes(value)

        def fingerprint(world, scope, inputs, deps):
            return input_fingerprint(metadata, world, scope, inputs, deps, manifest)

        terrain_meta = self.terrain.binding.metadata
        self.binding = RegisteredPlanContract(metadata, TypeAdapter(WaterPlacementInput).validate_python,
            fingerprint, (PlanDependencyContract(slot=self.slot, contract_id=terrain_meta.id,
                schema_version=terrain_meta.schema_version, algorithm_version=terrain_meta.algorithm_version),),
            CacheBinding(CacheContract[PlanEnvelope[WaterPlacementPlan]](
                id=f"surface.envelope.pc.{SurfacePlanSlot.WATER_PLACEMENT.value}", schema_version=1), WaterCodec()), manifest)
        self.provider = Mock(wraps=WaterPlacementPlanProvider(self.terrain.binding))
        self.h.registry.register(self.binding, self.provider)

    def get(self, inputs=None, terrain=None, reader=None):
        inputs = self.inputs if inputs is None else inputs
        terrain = self.terrain.get() if terrain is None else terrain
        deps = (PlanDependency(slot=self.slot, ref=terrain.ref),)
        meta = self.binding.metadata
        key = PlanKey(world_uid="climate-world", scope=WorldPlanScope(), contract_id=meta.id,
            schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=self.binding.fingerprint_inputs("climate-world", WorldPlanScope(), inputs, deps))
        request = PlanRequest[self.Input](key=key, inputs=inputs, dependencies=deps)
        reader = self.h.empty.with_plan(self.slot, self.terrain.binding, terrain) if reader is None else reader
        return self.h.service.get_or_build(self.binding, request, reader, wait=Wait(5))

    def test_basin_legacy_equivalence_and_revision_through_shared_kernel(self):
        from unittest.mock import patch
        from app.application.worldData.generators.hydrology.placement.waterPlacementPass import (
            run_water_placement_pass, run_prepared_water_placement, legacy_surface_revision)
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap
        from tests.hydrology_fixtures import hydro_world
        terrain = self.terrain.get()
        hm = SurfaceHeightmap(world_uid="climate-world", bbox=terrain.payload.bbox,
            surface_z={(coord.gx, coord.gy): z for coord, z in terrain.payload.surface_z})
        world = hydro_world(world_uid="climate-world", fine_cells_per_map_cell=10,
            hydrology=dict(enabled=True, declared_basins=[self.inputs.basins[0].model_dump(mode="json")]), z_min=-100)
        before = dict(hm.surface_z)
        legacy = run_water_placement_pass(world, [], hm)
        path = "app.application.worldData.generators.terrain.planning.waterPlacementPlanProvider.run_prepared_water_placement"
        with patch(path, wraps=run_prepared_water_placement) as kernel:
            current = self.get(terrain=terrain)
        context = kernel.call_args.args[1]
        self.assertEqual(context.snapshot_revision, terrain.ref.output_fingerprint)
        self.assertEqual(legacy.preparation.snapshot_revision, legacy.batch_result.snapshot_revision)
        self.assertEqual(legacy.preparation.snapshot_revision, legacy_surface_revision(hm))
        self.assertEqual(current.payload.records, legacy.records)
        self.assertEqual(current.payload.basin_specs, legacy.basin_specs)
        self.assertEqual(hm.surface_z, before)
        self.assertEqual(current.payload.records[0].footprint_cells,
                         frozenset((x, y) for x in range(3) for y in range(-2, 1)))

    def test_disabled_and_empty_inputs_return_typed_empty_plan_without_resolve(self):
        from unittest.mock import patch
        path = "app.application.worldData.generators.terrain.planning.waterPlacementPlanProvider.run_prepared_water_placement"
        with patch(path, side_effect=AssertionError("empty water resolved")):
            for update in ({"enabled": False}, {"basins": ()}):
                result = self.get(self.inputs.model_copy(update=update))
                self.assertEqual((result.payload.records, result.payload.basin_specs, result.diagnostics), ((), (), ()))

    def test_hit_and_rebuild_preserve_diagnostics_without_logging(self):
        from app.application.planning.service.planFingerprints import cache_item_key
        from app.dataModel.cache.identity.cacheKey import CacheKey
        coast = self.Coast.model_validate(dict(location_uid="basin", kind="sea", closed=False,
            path=[dict(x=0, y=-20), dict(x=0, y=0)]))
        inputs = self.inputs.model_copy(update={"coastlines": (coast,)})
        with self.assertNoLogs("app.application.jsonValidation.resolve", level="DEBUG"):
            first = self.get(inputs)
            self.assertEqual(self.get(inputs), first)
            self.h.cache.evict(self.binding.cache_binding, CacheKey(contract=self.binding.cache_binding.contract,
                item_key=cache_item_key(first.ref.key, self.manifest)))
            self.assertEqual(self.get(inputs), first)
        self.assertIn("WATER_PLACEMENT_MERGED_SOURCES", {d.issue.code for d in first.diagnostics})
        self.assertTrue(all(d.disposition == PlanDiagnosticDisposition.FALLBACK for d in first.diagnostics))
        self.assertEqual(self.provider.build.call_count, 2)

    def test_collapsed_geometry_is_explicit_error_with_independent_basin_preserved(self):
        tiny = self.Basin.model_validate(dict(location_uid="tiny", kind="ocean", floor_z=-10,
            footprint=dict(kind="polygon", vertices=[[0, 0], [1, 0], [1, 1]])))
        inputs = self.inputs.model_copy(update={"basins": (*self.inputs.basins, tiny)})
        for mode in (self.Mode.RUNTIME, self.Mode.VALIDATE_ONLY):
            with self.subTest(mode=mode), self.assertNoLogs("app.application.jsonValidation.resolve", level="DEBUG"):
                result = self.get(inputs.model_copy(update={"resolution_mode": mode}))
                self.assertEqual(tuple(r.source_uid for r in result.payload.records), ("basin",))
                diagnostic, = result.diagnostics
                self.assertEqual(diagnostic.disposition, PlanDiagnosticDisposition.ERROR)
                self.assertEqual(diagnostic.issue.path, ("hydrology", "declared_basins", 1))

    def test_terrain_edit_invalidates_and_revision_mismatch_rejected_before_hit(self):
        from app.application.planning.service.planningService import PlanContractFailure
        first = self.get()
        old = self.terrain.get()
        edited = self.terrain.get(self.terrain.inputs.model_copy(update={"seed": 18}))
        second = self.get(terrain=edited)
        self.assertNotEqual(first.ref.key, second.ref.key)
        self.assertEqual(first.payload, second.payload)
        reader = self.h.empty.with_plan(self.slot, self.terrain.binding, old)
        with self.assertRaises(PlanContractFailure):
            self.get(terrain=edited, reader=reader)
        with self.assertRaises(PlanContractFailure):
            self.get(reader=self.h.empty)

    def test_input_edits_invalidate_and_cached_geometry_cannot_be_mutated(self):
        from pydantic import ValidationError
        first = self.get()
        for update in ({"default_water_level": 1},
                       {"seas": self.inputs.seas.model_copy(update={"placement_specificity": 2})},
                       {"grid": self.terrain.Grid(fine_span=20, light_side=2)}):
            with self.subTest(update=update):
                self.assertNotEqual(self.get(self.inputs.model_copy(update=update)).ref.key, first.ref.key)
        record, = first.payload.records
        shape = record.placement.prepared.intent.shape
        with self.assertRaises(ValidationError):
            shape.x_min = -999
        with self.assertRaises(AttributeError):
            record.footprint_cells.add((999, 999))
        cells = set(record.footprint_cells)
        cells.clear()
        self.assertEqual(self.get(), first)
        self.assertEqual(len(record.footprint_cells), 9)

    def test_input_envelope_codec_round_trip_and_lake_projection(self):
        from app.application.encoding.canonicalCodec import encode, decode
        lake = self.Lake.model_validate(dict(location_uid="lake", shoreline=[
            dict(x=0, y=-20), dict(x=20, y=-20), dict(x=20, y=0), dict(x=0, y=0)]))
        inputs = self.inputs.model_copy(update={"basins": (), "declared_lakes": (lake,)})
        first = self.get(inputs)
        record, = first.payload.records
        self.assertEqual(record.kind.value, "lake")
        self.assertEqual(record.footprint_cells, frozenset(((1, -1),)))
        self.assertEqual(decode(encode(inputs, self.manifest), self.Input, self.manifest), inputs)
        codec = self.binding.cache_binding.codec
        self.assertEqual(codec.decode(codec.encode(first)), first)

    def test_topology_seam_projection_preserves_baseline_geometry(self):
        from app.dataModel.spatial.grid.gridBBox import GridBBox
        terrain = self.terrain.get(self.terrain.inputs.model_copy(update={"bbox": GridBBox(-2, 5, -3, 5)}))
        basin = self.Basin.model_validate(dict(location_uid="seam", kind="ocean", floor_z=-10,
            footprint=dict(kind="bbox", x_min=40, x_max=70, y_min=-10, y_max=0)))
        for mode in ("wrapped", "sphere"):
            topology = self.Topology(mode=mode, bounds=self.Bounds(x_min=-2, x_max=5, y_min=-3, y_max=5))
            result = self.get(self.inputs.model_copy(update={"topology": topology, "basins": (basin,)}), terrain=terrain)
            self.assertEqual(result.payload.records[0].footprint_cells,
                frozenset((x, y) for x in (4, 5, -2, -1) for y in (-1, 0)))

    def test_incoherent_extent_or_z_range_fails_without_cached_empty_plan(self):
        from app.application.planning.service.planningService import PlanBuildFailure
        invalid_topology = self.Topology(mode="planar",
            bounds=self.Bounds(x_min=-2, x_max=5, y_min=-3, y_max=5))
        for update in ({"topology": invalid_topology}, {"z_max": 0}):
            with self.subTest(update=update), self.assertRaises(PlanBuildFailure):
                self.get(self.inputs.model_copy(update=update))


if __name__ == "__main__":
    unittest.main()
