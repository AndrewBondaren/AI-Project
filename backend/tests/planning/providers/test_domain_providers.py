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


class ReliefProviderFixture:
    def setUp(self):
        from unittest.mock import Mock
        from app.application.encoding.canonicalCodec import encode, decode
        from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import ReliefPlanProvider
        from app.dataModel.planning.contracts.planDependency import PlanDependencyContract
        from app.dataModel.planning.identity.planKey import PlanSlot
        from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, MountainAnchorInput, TerrainMergeEntry
        from app.dataModel.terrain.relief.planning.reliefPlan import (MountainTemplateInput, MountainLayout,
            LightReliefPlan, LightMountainCell, LightRavineCell, ReliefPlan)
        from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy, ObjectReliefPickPolicy
        from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe
        from app.dataModel.terrain.relief.specs import ReliefSideSpec
        from app.dataModel.terrain.relief.enums import ReliefContext, ReliefPickMode, ReliefSideKind
        from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy, RavinesCategoryPolicy
        from app.dataModel.terrainMasks.mountain.specs import (MountainSpec, MountainRangeSpec, MountainFormBySides,
            StarForm, PeakForm, PlateauForm, MountainRangeSides, MountainSaddleSpec)
        from app.dataModel.terrainMasks.mountain.enums import MountainKind, MountainRangeStyle
        from app.dataModel.spatial.grid.coordinateTypes import LightCellRef
        from app.dataModel.spatial.facing import Facing

        self.water = WaterPlacementProviderTests()
        self.water.setUp()
        self.addCleanup(self.water.doCleanups)
        self.h = self.water.h
        self.Input, self.Plan, self.Peak, self.Range = ReliefPlanInput, ReliefPlan, MountainSpec, MountainRangeSpec
        self.Template, self.Recipe, self.Pick, self.Anchor = MountainTemplateInput, MountainSideRecipe, ReliefContextPickPolicy, MountainAnchorInput
        self.Context = ReliefContext
        self.inputs = ReliefPlanInput(seed=17, masks_enabled=True,
            mountains=MountainsCategoryPolicy(autoresolve=False, default_radius_m=12),
            ravines=RavinesCategoryPolicy(autoresolve=True), declared_mountains=(), anchors=(),
            grid=self.water.inputs.grid, z_min=-100, z_max=100, mountain_templates=(),
            mountain_pick=ReliefContextPickPolicy(), terrain_merge=tuple(TerrainMergeEntry(key=key, merge_rank=rank)
                for key, rank in (("mountain", 30), ("plains", 10), ("ravine", 20))))
        records = (ReliefPlanInput, MountainAnchorInput, TerrainMergeEntry, MountainTemplateInput, MountainLayout,
            LightReliefPlan, LightMountainCell, LightRavineCell, ReliefPlan, PlanEnvelope[ReliefPlan],
            MountainsCategoryPolicy, RavinesCategoryPolicy, ReliefContextPickPolicy, ObjectReliefPickPolicy,
            MountainSideRecipe, ReliefSideSpec, MountainSpec, MountainRangeSpec, MountainFormBySides,
            StarForm, PeakForm, PlateauForm, MountainRangeSides, MountainSaddleSpec, LightCellRef)
        enums = (ReliefContext, ReliefPickMode, ReliefSideKind, MountainKind, MountainRangeStyle, Facing)
        self.manifest = CanonicalSchemaManifest(entries=self.water.manifest.entries + tuple(
            RegisteredTypeEntry(type_id=index, python_type=owner, kind=CanonicalTypeKind.RECORD)
            for index, owner in enumerate(records, 200)) + tuple(
            RegisteredTypeEntry(type_id=index, python_type=owner, kind=CanonicalTypeKind.ENUM)
            for index, owner in enumerate(enums, 250)))
        manifest = self.manifest
        metadata = PlanContractMetadata(id=f"surface.pc.{SurfacePlanSlot.RELIEF.value}", schema_version=1, algorithm_version=1)

        class ReliefCodec:
            def validate(self, value):
                return TypeAdapter(PlanEnvelope[ReliefPlan]).validate_python(value, strict=True)
            def encode(self, value):
                return encode(value, manifest)
            def decode(self, encoded):
                return decode(encoded, PlanEnvelope[ReliefPlan], manifest)
            def retained_bytes(self, value):
                return retained_entry_bytes(value)

        def fingerprint(world, scope, inputs, deps):
            return input_fingerprint(metadata, world, scope, inputs, deps, manifest)

        self.handles = ((SurfacePlanSlot.CLIMATE_BASE, self.water.terrain.climate.binding),
                        (SurfacePlanSlot.TERRAIN_BASE, self.water.terrain.binding),
                        (SurfacePlanSlot.WATER_PLACEMENT, self.water.binding))
        declarations = tuple(PlanDependencyContract(slot=PlanSlot(slot.value), contract_id=handle.metadata.id,
            schema_version=handle.metadata.schema_version, algorithm_version=handle.metadata.algorithm_version)
            for slot, handle in self.handles)
        self.binding = RegisteredPlanContract(metadata, TypeAdapter(ReliefPlanInput).validate_python,
            fingerprint, declarations, CacheBinding(CacheContract[PlanEnvelope[ReliefPlan]](
                id=f"surface.envelope.pc.{SurfacePlanSlot.RELIEF.value}", schema_version=1), ReliefCodec()), manifest)
        self.provider = Mock(wraps=ReliefPlanProvider(*(handle for _, handle in self.handles)))
        self.h.registry.register(self.binding, self.provider)

    def peak(self, **update):
        return self.Peak.model_validate(dict(origin_x_m=5, origin_y_m=-5, radius_m=12,
            form=dict(form_type="by_sides", side_count=4),
            sides=[dict(kind="slope")] * 4) | update)

    def get(self, inputs=None, climate=None, terrain=None, water=None):
        from app.dataModel.planning.identity.planKey import PlanSlot
        inputs = self.inputs if inputs is None else inputs
        climate = self.water.terrain.climate.get() if climate is None else climate
        terrain = self.water.terrain.get(climate=climate) if terrain is None else terrain
        water = self.water.get(terrain=terrain) if water is None else water
        envelopes = (climate, terrain, water)
        deps = tuple(PlanDependency(slot=PlanSlot(slot.value), ref=envelope.ref)
            for (slot, _), envelope in zip(self.handles, envelopes))
        reader = self.h.empty
        for (slot, handle), envelope in zip(self.handles, envelopes):
            reader = reader.with_plan(PlanSlot(slot.value), handle, envelope)
        meta = self.binding.metadata
        key = PlanKey(world_uid="climate-world", scope=WorldPlanScope(), contract_id=meta.id,
            schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=self.binding.fingerprint_inputs("climate-world", WorldPlanScope(), inputs, deps))
        return self.h.service.get_or_build(self.binding,
            PlanRequest[self.Input](key=key, inputs=inputs, dependencies=deps), reader, wait=Wait(10))


class ReliefProviderTests(ReliefProviderFixture, unittest.TestCase):
    def test_coarse_matches_legacy_with_mountain_reservation_ravine_and_basin(self):
        from app.ids import seed_int
        from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
        from app.application.worldData.generators.terrain.reliefObjects import apply_relief_objects_z
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap
        from tests.hydrology_fixtures import hydro_world
        climate, terrain, water = self.water.terrain.climate.get(), self.water.terrain.get(), self.water.get()
        peak = self.peak()
        inputs = self.inputs.model_copy(update={"declared_mountains": (peak,)})
        result = self.get(inputs).payload
        world = hydro_world(world_uid="climate-world", fine_cells_per_map_cell=10,
            world_map_cells_per_tile=2, z_min=-100, z_max=100, default_climate_zone="temperate",
            terrain_masks=dict(default_mountains=inputs.mountains.model_dump(mode="json"),
                default_ravines=inputs.ravines.model_dump(mode="json"), declared_mountains=[peak.model_dump(mode="json")]))
        hm = SurfaceHeightmap(world_uid="climate-world", bbox=terrain.payload.bbox,
            surface_z={(coord.gx, coord.gy): z for coord, z in terrain.payload.surface_z})
        before = dict(hm.surface_z)
        apply_relief_objects_z(world, [], hm, pole_field=ClimatePoleField(climate.payload.poles, climate.payload.bbox),
            light_side=2, basin_specs=water.payload.basin_specs, topology=water.payload.topology)
        self.assertEqual({(c.gx, c.gy): z for c, z in result.surface_z}, hm.surface_z)
        self.assertEqual({(c.gx, c.gy): z for c, z in terrain.payload.surface_z}, before)
        self.assertTrue(any(hm.surface_z[cell] > before[cell] for cell in water.payload.basin_specs[0].footprint))
        self.assertEqual(result.mountain_layout.entries, (peak,))
        self.assertEqual(len(result.light.base_surface_z), len(before) * 4)

    def test_full_light_base_matches_existing_relief_contributor(self):
        from app.application.worldData.pack.bake.lightGrid.contributors.relief import ReliefContributor
        from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
        from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
        from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
        from app.ids import seed_int
        from types import SimpleNamespace
        from tests.hydrology_fixtures import hydro_world
        world = hydro_world(world_uid="climate-world", z_min=-100, z_max=100, default_climate_zone="temperate")
        terrain, climate = self.water.terrain.get(), self.water.terrain.climate.get()
        coarse = {(c.gx, c.gy): z for c, z in terrain.payload.surface_z}
        compose = LightGridCompose(LightGridScale.from_tile(10, 2))
        context = SimpleNamespace(world=world, pole_field=ClimatePoleField(climate.payload.poles, climate.payload.bbox),
            surface_planning=SimpleNamespace(coarse_relief_z=coarse), tiles=list(coarse))
        ReliefContributor().apply(compose, context)
        result = self.get(self.inputs.model_copy(update={"seed": seed_int(world)})).payload.light
        for cell, z in result.base_surface_z:
            self.assertEqual(z, compose.get(cell.gx, cell.gy, cell.tx, cell.ty).surface_z)

    def test_disabled_masks_and_categories_keep_water_and_full_base_without_effects(self):
        inputs = self.inputs.model_copy(update={"masks_enabled": False, "declared_mountains": (self.peak(),)})
        result = self.get(inputs).payload
        self.assertEqual(result.mountain_layout.entries, ())
        self.assertEqual((result.light.mountain_cells, result.light.ravine_cells), ((), ()))
        water = self.water.get().payload
        surface = {(c.gx, c.gy): z for c, z in result.surface_z}
        self.assertTrue(all(surface[cell] < spec.z_water_level for spec in water.basin_specs for cell in spec.footprint))

    def test_same_layout_selected_once_and_hit_rebuild_have_equal_refs(self):
        from unittest.mock import patch
        from app.application.worldData.generators.terrain.mountains.collect import collect_prepared_mountain_entries_for_coarse
        path = "app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider.collect_prepared_mountain_entries_for_coarse"
        inputs = self.inputs.model_copy(update={"declared_mountains": (self.peak(),)})
        with patch(path, wraps=collect_prepared_mountain_entries_for_coarse) as collect:
            first = self.get(inputs)
            self.assertEqual(self.get(inputs), first)
            self.assertEqual(collect.call_count, 1)
            self.h.backend.clear()
            self.assertEqual(self.get(inputs), first)
            self.assertEqual(collect.call_count, 2)
        local = dict(first.payload.light.base_surface_z)
        for tile in ((0, 0), (0, -1)):
            selected = [cell for cell, _ in self.get(inputs).payload.light.base_surface_z
                        if (cell.gx, cell.gy) == tile]
            self.assertEqual(len(selected), 4)
            self.assertTrue(all(cell in local for cell in selected))
        local.clear()
        self.assertEqual(len(first.payload.light.base_surface_z), 252)
        other = Harness(policy=PlanningExecutionPolicy(max_workers=1, max_pending_builds=2))
        self.addCleanup(other.service.shutdown)
        for (_, handle), provider in zip(self.handles, (self.water.terrain.climate.provider,
                                                       self.water.terrain.provider, self.water.provider)):
            other.registry.register(handle, provider)
        other.registry.register(self.binding, self.provider)
        previous, self.h = self.h, other
        try:
            self.assertEqual(self.get(inputs), first)
        finally:
            self.h = previous

    def test_input_policy_seed_merge_and_upstream_edits_invalidate(self):
        first = self.get()
        for update in ({"seed": 18}, {"terrain_merge": tuple(entry.model_copy(update={"merge_rank": 99})
                       for entry in self.inputs.terrain_merge)},
                       {"ravines": self.inputs.ravines.model_copy(update={"drop_z": 3})}):
            self.assertNotEqual(self.get(self.inputs.model_copy(update=update)).ref.key, first.ref.key)
        terrain = self.water.terrain.get(self.water.terrain.inputs.model_copy(update={"seed": 18}))
        self.assertNotEqual(self.get(terrain=terrain).ref.key, first.ref.key)
        self.assertEqual(self.get(), first)

    def test_mixed_upstream_refs_are_rejected_without_replanning(self):
        from app.application.planning.service.planningService import PlanBuildFailure
        old = self.water.terrain.get()
        climate = self.water.terrain.climate.get(self.water.terrain.climate.inputs.model_copy(update={"seed": 18}))
        with self.assertRaises(PlanBuildFailure):
            self.get(climate=climate, terrain=old)

    def test_ravines_use_full_extent_without_wrapped_edge_neighbors(self):
        from app.dataModel.spatial.grid.coordinateTypes import FineZ, LightCellRef
        grid = self.water.terrain.Grid(fine_span=10, light_side=1)
        inputs = self.water.terrain.inputs.model_copy(update={"grid": grid})
        original = self.water.terrain.provider.build._mock_wraps

        def base_surface(request, reader, control):
            result = original(request, reader, control)
            surface = tuple((cell, FineZ(-5 if (cell.gx, cell.gy) in ((0, 0), (-2, -3)) else 0))
                            for cell, _ in result.payload.surface_z)
            return PlanBuildResult[self.water.terrain.Plan](payload=result.payload.model_copy(
                update={"surface_z": surface}), diagnostics=())

        self.water.terrain.provider.build.side_effect = base_surface
        terrain = self.water.terrain.get(inputs)
        topology = self.water.topology.model_copy(update={"mode": self.water.topology.mode.__class__.WRAPPED})
        water = self.water.get(self.water.inputs.model_copy(update={"enabled": False, "grid": grid,
            "topology": topology}), terrain=terrain)
        policy = self.inputs.ravines.model_copy(update={"min_neighbors": 8})
        relief_input = self.inputs.model_copy(update={"grid": grid, "ravines": policy})
        result = self.get(relief_input, terrain=terrain, water=water).payload
        coarse = {(cell.gx, cell.gy): z for cell, z in result.surface_z}
        self.assertEqual(coarse[(0, 0)], -6)
        self.assertEqual(coarse[(-2, -3)], -5)
        base = dict(result.light.base_surface_z)
        ravines = {effect.cell: effect.surface_z for effect in result.light.ravine_cells}
        center, edge = LightCellRef(0, 0, 0, 0), LightCellRef(-2, -3, 0, 0)
        self.assertEqual(ravines[center], base[center] - 1)
        self.assertNotIn(edge, ravines)


class ReliefTemplateProviderTests(ReliefProviderFixture, unittest.TestCase):
    def test_missing_template_is_error_and_independent_declared_peak_keeps_its_effect(self):
        missing = self.peak(sides=[], location_uid="needs-template")
        declared = self.peak(origin_x_m=25, sides=[dict(kind="sheer")] * 4, location_uid="declared")
        inputs = self.inputs.model_copy(update={"declared_mountains": (missing, declared)})
        with self.assertNoLogs("app.application.jsonValidation.resolve", level="DEBUG"):
            first = self.get(inputs)
            self.assertEqual(self.get(inputs), first)
        self.assertEqual(first.payload.mountain_layout.entries, (declared,))
        diagnostic, = first.diagnostics
        self.assertEqual((diagnostic.issue.code, diagnostic.disposition),
                         ("DOMAIN_NO_CANDIDATE", PlanDiagnosticDisposition.ERROR))
        self.assertEqual(missing.sides, ())
        self.h.backend.clear()
        with self.assertNoLogs("app.application.jsonValidation.resolve", level="DEBUG"):
            self.assertEqual(self.get(inputs), first)

    def test_template_recipe_edit_and_none_recipe_on_real_member(self):
        peak = self.peak(sides=[])
        template = self.Template(template_uid="template-a", context=self.Context.MOUNTAIN,
            side_recipe=self.Recipe(default_side_kind="slope"))
        inputs = self.inputs.model_copy(update={"declared_mountains": (peak,), "mountain_templates": (template,)})
        first = self.get(inputs)
        self.assertEqual([side.kind.value for side in first.payload.mountain_layout.entries[0].sides], ["slope"] * 4)
        edited = template.model_copy(update={"side_recipe": self.Recipe(default_side_kind="sheer")})
        second = self.get(inputs.model_copy(update={"mountain_templates": (edited,)}))
        self.assertNotEqual(second.ref.key, first.ref.key)
        self.assertNotEqual(second.payload.light.mountain_cells, first.payload.light.mountain_cells)
        empty_recipe = template.model_copy(update={"side_recipe": None})
        mode_d = self.get(inputs.model_copy(update={"mountain_templates": (empty_recipe,)}))
        self.assertEqual(len(mode_d.payload.mountain_layout.entries[0].sides), 4)
        self.assertEqual(mode_d.diagnostics, ())

    def test_range_peaks_spine_sides_saddles_and_codec_round_trip(self):
        from app.application.encoding.canonicalCodec import encode, decode
        range_spec = self.Range.model_validate(dict(spine=[[5, -5], [25, -5]], width_m=12,
            peaks=[self.peak(sides=[]).model_dump(), self.peak(origin_x_m=25, sides=[]).model_dump()],
            peak_spacings_m=[20], saddles=[dict(peak_a_index=0, peak_b_index=1, rise_fraction=0.7)],
            sides=dict(left=dict(kind="sheer"), right=dict(kind="slope")), location_uid="range"))
        template = self.Template(template_uid="template-a", context=self.Context.MOUNTAIN,
            side_recipe=self.Recipe(side_kinds=["slope", "sheer"]))
        inputs = self.inputs.model_copy(update={"declared_mountains": (range_spec,), "mountain_templates": (template,)})
        first = self.get(inputs)
        stamped, = first.payload.mountain_layout.entries
        for field in ("spine", "sides", "saddles", "peak_spacings_m", "location_uid"):
            self.assertEqual(getattr(stamped, field), getattr(range_spec, field))
        self.assertTrue(all(len(peak.sides) == 4 for peak in stamped.peaks))
        codec = self.binding.cache_binding.codec
        self.assertEqual(codec.decode(codec.encode(first)), first)
        self.assertEqual(decode(encode(inputs, self.manifest), self.Input, self.manifest), inputs)
        self.assertTrue(first.payload.light.mountain_cells)

    def test_auto_selection_anchor_precedence_and_terrain_color_do_not_reselect(self):
        anchor = self.Anchor(location_uid="anchor", position=(5, -5))
        policy = self.inputs.mountains.model_copy(update={"autoresolve": True, "threshold": 0.0, "ridge_cell_m": 10})
        declared = self.peak(location_uid="anchor")
        inputs = self.inputs.model_copy(update={"mountains": policy, "anchors": (anchor,), "declared_mountains": (declared,)})
        first = self.get(inputs)
        self.assertEqual(first.payload.mountain_layout.entries[0], declared)
        color = tuple(entry.model_copy(update={"merge_rank": -50}) for entry in inputs.terrain_merge)
        second = self.get(inputs.model_copy(update={"terrain_merge": color}))
        self.assertEqual(second.payload.mountain_layout, first.payload.mountain_layout)
        self.assertEqual(second.payload.light.mountain_cells, first.payload.light.mountain_cells)

    def test_frozen_autoselection_uses_row_major_terrain_order(self):
        from unittest.mock import patch
        from app.application.worldData.generators.terrain.mountains.collect import collect_prepared_mountain_entries_for_coarse
        policy = self.inputs.mountains.model_copy(update={"autoresolve": True, "threshold": 0.0, "ridge_cell_m": 10})
        keys = [(x, y) for y in range(-3, 6) for x in range(-2, 5)]
        supplied = []

        def collect(**kwargs):
            cells = tuple(kwargs["heightmap_keys"])
            supplied.extend(cells)
            return collect_prepared_mountain_entries_for_coarse(**(kwargs | {"heightmap_keys": cells}))

        path = "app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider.collect_prepared_mountain_entries_for_coarse"
        with patch(path, side_effect=collect):
            result = self.get(self.inputs.model_copy(update={"mountains": policy}))
        self.assertEqual(supplied, keys)
        self.assertTrue(result.payload.mountain_layout.entries)

    def test_object_template_policy_overrides_resolved_world_policy(self):
        peak = self.peak(sides=[], relief_pick_policy={"mountain": {
            "mode": "fixed", "default_template_uid": "b"}})
        templates = tuple(self.Template(template_uid=uid, context=self.Context.MOUNTAIN,
            side_recipe=self.Recipe(default_side_kind=kind)) for uid, kind in (("a", "slope"), ("b", "sheer")))
        inputs = self.inputs.model_copy(update={"declared_mountains": (peak,), "mountain_templates": templates,
            "mountain_pick": self.Pick(mode="fixed", default_template_uid="a")})
        result = self.get(inputs)
        self.assertEqual([side.kind.value for side in result.payload.mountain_layout.entries[0].sides], ["sheer"] * 4)
        self.assertEqual(result.diagnostics, ())


class RiverReliefProviderTests(ReliefProviderFixture, unittest.TestCase):
    def setUp(self):
        from app.application.encoding.canonicalCodec import encode, decode
        from app.application.planning.service.planFingerprints import output_fingerprint
        from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import RiverReliefPlanProvider
        from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput
        from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan, RiverBedRecord
        from app.dataModel.hydrology.planning.hydrologyPlan import (HydrologyRoutesPlan, RiverRoute,
            RiverPathSegment, DeclaredWaterPaint)
        from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
        from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
        from app.dataModel.hydrology.waterBody import WaterBody
        from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
        from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
        from app.dataModel.planning.contracts.planDependency import PlanDependencyContract
        from app.dataModel.planning.identity.planKey import PlanSlot
        from app.dataModel.spatial.grid.coordinateTypes import FineXY, SurfaceGridCoord
        from tests.planning.contracts.test_domain_payloads import HydrologyPlanningPayloadTests
        super().setUp()
        self.before = self.get()
        self.RouteFixture = HydrologyPlanningPayloadTests()
        self.Kind, self.RiverInput, self.RiverPlan = HydrologyConnectionType, RiverReliefInput, RiverReliefPlan
        extra = (RiverReliefInput, RiverReliefPlan, RiverBedRecord[SurfaceGridCoord], RiverBedRecord[FineXY],
            HydrologyRoutesPlan, RiverRoute[SurfaceGridCoord], RiverRoute[FineXY],
            RiverPathSegment[SurfaceGridCoord], RiverPathSegment[FineXY], DeclaredWaterPaint,
            RiverDrainageLink, WaterBody, MapCellHydrology, PlanEnvelope[RiverReliefPlan], PlanEnvelope[HydrologyRoutesPlan])
        self.river_manifest = CanonicalSchemaManifest(entries=self.manifest.entries + tuple(
            RegisteredTypeEntry(type_id=index, python_type=owner, kind=CanonicalTypeKind.RECORD)
            for index, owner in enumerate(extra, 300)) + (RegisteredTypeEntry(type_id=350,
                python_type=HydrologyConnectionType, kind=CanonicalTypeKind.ENUM),))
        manifest = self.river_manifest

        def binding(slot, input_type, payload_type, declarations):
            meta = PlanContractMetadata(id=f"surface.pc.{slot.value}", schema_version=1, algorithm_version=1)
            envelope_type = PlanEnvelope[payload_type]

            class Codec:
                def validate(self, value):
                    return TypeAdapter(envelope_type).validate_python(value, strict=True)
                def encode(self, value):
                    return encode(value, manifest)
                def decode(self, encoded):
                    return decode(encoded, envelope_type, manifest)
                def retained_bytes(self, value):
                    return retained_entry_bytes(value)

            def fingerprint(world, scope, inputs, deps):
                return input_fingerprint(meta, world, scope, inputs, deps, manifest)
            return RegisteredPlanContract(meta, TypeAdapter(input_type).validate_python, fingerprint, declarations,
                CacheBinding(CacheContract[envelope_type](id=f"surface.envelope.pc.{slot.value}", schema_version=1), Codec()), manifest)

        def declaration(slot, handle):
            meta = handle.metadata
            return PlanDependencyContract(slot=PlanSlot(slot.value), contract_id=meta.id,
                schema_version=meta.schema_version, algorithm_version=meta.algorithm_version)

        self.routes_binding = binding(SurfacePlanSlot.HYDROLOGY_ROUTES, HydrologyPlanInput, HydrologyRoutesPlan,
            (declaration(SurfacePlanSlot.RELIEF, self.binding),))
        # PC-8 owns route production. Tests supply a validated, signed dependency envelope.
        self.h.registry.register(self.routes_binding, Provider(lambda *args: self.fail("route provider invoked")))
        self.river_binding = binding(SurfacePlanSlot.RIVER_RELIEF, RiverReliefInput, RiverReliefPlan,
            (declaration(SurfacePlanSlot.HYDROLOGY_ROUTES, self.routes_binding), declaration(SurfacePlanSlot.RELIEF, self.binding)))
        self.h.registry.register(self.river_binding, RiverReliefPlanProvider(self.binding, self.routes_binding))
        self.river_inputs = RiverReliefInput(z_min=-100, z_max=100, grid=self.inputs.grid,
            topology=self.water.topology, channel_depths=((self.Kind.MOUNTAIN_RIVER, 5), (self.Kind.RIVER, 2)))

    def river(self, payload, inputs=None):
        from app.application.planning.service.planFingerprints import output_fingerprint
        from app.dataModel.planning.identity.planKey import PlanSlot, InputFingerprint
        inputs = self.river_inputs if inputs is None else inputs
        meta = self.routes_binding.metadata
        route_deps = (PlanDependency(slot=PlanSlot(SurfacePlanSlot.RELIEF.value), ref=self.before.ref),)
        # The route producer is not part of PC-7; its opaque source-key digest is a fixture.
        key = PlanKey(world_uid="climate-world", scope=WorldPlanScope(), contract_id=meta.id,
            schema_version=meta.schema_version, algorithm_version=meta.algorithm_version, input_fingerprint=InputFingerprint(bytes(32)))
        envelope = PlanEnvelope[type(payload)](ref=PlanRef(key=key, output_fingerprint=output_fingerprint(
            payload, route_deps, (), self.river_manifest)), dependencies=route_deps, payload=payload, diagnostics=())
        reader = self.h.empty.with_plan(PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value), self.routes_binding, envelope)
        reader = reader.with_plan(PlanSlot(SurfacePlanSlot.RELIEF.value), self.binding, self.before)
        deps = (PlanDependency(slot=PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value), ref=envelope.ref), *route_deps)
        meta = self.river_binding.metadata
        request = PlanRequest[self.RiverInput](key=PlanKey(world_uid="climate-world", scope=WorldPlanScope(),
            contract_id=meta.id, schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=self.river_binding.fingerprint_inputs("climate-world", WorldPlanScope(), inputs, deps)),
            inputs=inputs, dependencies=deps)
        return self.h.service.get_or_build(self.river_binding, request, reader, wait=Wait(10))

    def test_overlap_carves_once_from_original_base_and_keeps_receiver(self):
        route = self.RouteFixture.route(uid="a")
        other = self.RouteFixture.route(uid="b")
        other = other.model_copy(update={"segments": tuple(segment.model_copy(update={
            "connection_type": self.Kind.MOUNTAIN_RIVER}) for segment in other.segments),
            "drainage": other.drainage.model_copy(update={"river_type": self.Kind.MOUNTAIN_RIVER})})
        routes = self.RouteFixture.routes(coarse_routes=(route, other))
        first = self.river(routes)
        before, after = dict(self.before.payload.surface_z), dict(first.payload.surface_z)
        start, receiver = route.segments[0].path
        self.assertEqual(after[start], before[start] - 5)
        self.assertEqual(after[receiver], before[receiver])
        self.assertEqual({bed.river_uid for bed in first.payload.coarse_beds}, {"a", "b"})
        self.assertTrue(all(dict(bed.bed_z)[start] == after[start] for bed in first.payload.coarse_beds))
        reordered = self.river(routes.model_copy(update={"coarse_routes": (other, route)}))
        self.assertEqual(reordered.payload.surface_z, first.payload.surface_z)
        self.assertEqual(self.river(routes), first)
        self.h.backend.clear()
        self.assertEqual(self.river(routes), first)

    def test_fine_keeps_receiver_and_all_unchanged_sampled_cells(self):
        from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, FineZ
        route = self.RouteFixture.route(fine=True)
        base = tuple(((FineX(x), FineY(0)), FineZ(z)) for x, z in ((0, 5), (1, 9), (2, 7)))
        routes = self.RouteFixture.routes(coarse_routes=(), fine_routes=(route,), fine_base_surface_z=base)
        first = self.river(routes)
        self.assertEqual([z for _, z in first.payload.fine_surface_z], [3, 9, 7])
        self.assertEqual(first.payload.surface_z, self.before.payload.surface_z)
        self.assertEqual(routes.fine_base_surface_z, base)
        codec = self.river_binding.cache_binding.codec
        self.assertEqual(codec.decode(codec.encode(first)), first)

    def test_empty_routes_do_not_repeat_relief_and_missing_heights_fail(self):
        from unittest.mock import patch
        from app.application.planning.service.planningService import PlanBuildFailure
        from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord, GridX, GridY
        routes = self.RouteFixture.routes(coarse_routes=())
        path = "app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider._mountain_layout"
        with patch(path, side_effect=AssertionError("mountains replanned")):
            empty = self.river(routes)
        self.assertEqual(empty.payload.surface_z, self.before.payload.surface_z)
        self.assertEqual((empty.payload.coarse_beds, empty.payload.fine_beds), ((), ()))
        route = self.RouteFixture.route()
        segment = route.segments[0].model_copy(update={"path": (SurfaceGridCoord(GridX(999), GridY(0)), route.receiver_cell)})
        invalid = self.RouteFixture.routes(coarse_routes=(route.model_copy(update={"segments": (segment,)}),))
        with self.assertRaises(PlanBuildFailure):
            self.river(invalid)

    def test_profile_symbol_identity_and_z_min_clamp(self):
        from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_spec as old
        from app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedZ import river_bed_spec
        self.assertIs(old, river_bed_spec)
        route = self.RouteFixture.route()
        start = route.segments[0].path[0]
        pre = dict(self.before.payload.surface_z)[start]
        inputs = self.river_inputs.model_copy(update={"z_min": pre - 1})
        first = self.river(self.RouteFixture.routes(), inputs)
        self.assertEqual(dict(first.payload.surface_z)[start], pre - 1)


if __name__ == "__main__":
    unittest.main()


class HydrologyProviderTests(ReliefProviderFixture, unittest.TestCase):
    def setUp(self):
        from unittest.mock import Mock
        from app.application.encoding.canonicalCodec import encode, decode
        from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import (
            HydrologyRoutesPlanProvider, HydrologyFinalPlanProvider)
        from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import RiverReliefPlanProvider
        from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput, HydrologyFinalInput, HydrologyAnchorInput
        from app.dataModel.hydrology.planning.hydrologyPlan import (HydrologyRoutesPlan, HydrologyPlan,
            RiverRoute, RiverPathSegment, DeclaredWaterPaint, LakePaint, CoastlinePaint, SegmentRiverPaint, IntentRiverPaint)
        from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput
        from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan, RiverBedRecord
        from app.dataModel.hydrology.declaredRiver import DeclaredRiver, DeclaredRiverSegment, HydrologyMouth
        from app.dataModel.hydrology.rivers import HydrologyRiversPolicy, RiverTypeClassify
        from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
        from app.dataModel.hydrology.waterBody import WaterBody
        from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
        from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
        from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
        from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
        from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
        from app.dataModel.hydrology.enums.waterSystemKind import WaterSystemKind
        from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
        from app.dataModel.hydrology.enums.riverSystemRole import RiverSystemRole
        from app.dataModel.hydrology.enums.riverSystemTopology import RiverSystemTopology
        from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope, HYDROLOGY_BOOTSTRAP_SCOPES
        from app.dataModel.planning.contracts.planDependency import PlanDependencyContract
        from app.dataModel.planning.identity.planKey import PlanSlot
        from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord, FineXY
        super().setUp()
        self.HInput, self.FInput, self.RInput = HydrologyPlanInput, HydrologyFinalInput, RiverReliefInput
        self.HPlan, self.FPlan, self.RPlan = HydrologyRoutesPlan, HydrologyPlan, RiverReliefPlan
        self.Declare, self.Anchor, self.Kind = DeclaredRiver, HydrologyAnchorInput, HydrologyConnectionType
        self.water_inputs = self.water.inputs.model_copy(update={
            "seas": self.water.inputs.seas.model_copy(update={"min_water_cells": 1,
                "autoresolve_coastal_sea": False, "autoresolve_open_ocean": False}),
            "lakes": self.water.inputs.lakes.model_copy(update={"min_water_cells": 1, "autoresolve": False})})
        self.water_envelope = self.water.get(inputs=self.water_inputs)
        self.before = self.get(water=self.water_envelope)
        self.before = self.signed(self.before, self.before.payload.model_copy(update={"surface_z": tuple(
            (cell, (-2 if cell.gy == 0 and cell.gx in (1, 2) else 8 - (cell.gx + 2) * 2
                    if cell.gy == 0 and cell.gx <= 0 else 10)) for cell, _ in self.before.payload.surface_z)}), self.manifest)
        self.hydro_inputs = HydrologyPlanInput(enabled=True, seed=17, resolution_mode=self.water.Mode.RUNTIME,
            scopes=HYDROLOGY_BOOTSTRAP_SCOPES, default_water_level=0,
            seas=self.water_inputs.seas, lakes=self.water_inputs.lakes,
            rivers=HydrologyRiversPolicy(autoresolve=False, max_path_cells=64, mouth_search_radius_fine=0),
            declared_rivers=(self.segment(),), coastlines=(), declared_lakes=(), anchors=(),
            topology=self.water.topology, grid=self.inputs.grid, z_min=-100, z_max=100,
            liquid_keys=frozenset(("water",)), change_uid="change")
        records = (HydrologyPlanInput, HydrologyFinalInput, HydrologyAnchorInput,
            HydrologyRoutesPlan, HydrologyPlan, RiverReliefInput, RiverReliefPlan,
            RiverBedRecord[SurfaceGridCoord], RiverBedRecord[FineXY],
            RiverRoute[SurfaceGridCoord], RiverRoute[FineXY], RiverPathSegment[SurfaceGridCoord], RiverPathSegment[FineXY],
            DeclaredWaterPaint, LakePaint, CoastlinePaint, SegmentRiverPaint, IntentRiverPaint,
            DeclaredRiver, DeclaredRiverSegment, HydrologyMouth, HydrologyRiversPolicy, RiverTypeClassify,
            MapCellHydrology, WaterBody, PhysicalWaterUnion, RiverDrainageLink,
            PlanEnvelope[HydrologyRoutesPlan], PlanEnvelope[HydrologyPlan], PlanEnvelope[RiverReliefPlan])
        enums = (HydrologyCellRole, HydrologyShoreKind, HydrologyConnectionType,
            WaterSystemKind, RiverDeclareMode, RiverSystemRole, RiverSystemTopology, HydrologyScope)
        self.hydro_manifest = CanonicalSchemaManifest(entries=self.manifest.entries + tuple(
            RegisteredTypeEntry(type_id=i, python_type=t, kind=CanonicalTypeKind.RECORD) for i, t in enumerate(records, 400))
            + tuple(RegisteredTypeEntry(type_id=i, python_type=t, kind=CanonicalTypeKind.ENUM) for i, t in enumerate(enums, 450)))
        manifest = self.hydro_manifest

        def binding(slot, input_type, payload_type, handles):
            meta = PlanContractMetadata(id=f"surface.pc.{slot.value}", schema_version=1, algorithm_version=1)
            envelope_type = PlanEnvelope[payload_type]
            class Codec:
                def validate(self, value): return TypeAdapter(envelope_type).validate_python(value, strict=True)
                def encode(self, value): return encode(value, manifest)
                def decode(self, value): return decode(value, envelope_type, manifest)
                def retained_bytes(self, value): return retained_entry_bytes(value)
            declarations = tuple(PlanDependencyContract(slot=PlanSlot(s.value), contract_id=h.metadata.id,
                schema_version=h.metadata.schema_version, algorithm_version=h.metadata.algorithm_version) for s, h in handles)
            return RegisteredPlanContract(meta, TypeAdapter(input_type).validate_python,
                lambda w, s, i, d: input_fingerprint(meta, w, s, i, d, manifest), declarations,
                CacheBinding(CacheContract[envelope_type](id="cache." + meta.id, schema_version=1), Codec()), manifest)
        self.route_handles = ((SurfacePlanSlot.RELIEF, self.binding), (SurfacePlanSlot.WATER_PLACEMENT, self.water.binding))
        self.routes_binding = binding(SurfacePlanSlot.HYDROLOGY_ROUTES, HydrologyPlanInput, HydrologyRoutesPlan, self.route_handles)
        self.river_handles = ((SurfacePlanSlot.RELIEF, self.binding), (SurfacePlanSlot.HYDROLOGY_ROUTES, self.routes_binding))
        self.river_binding = binding(SurfacePlanSlot.RIVER_RELIEF, RiverReliefInput, RiverReliefPlan, self.river_handles)
        self.final_handles = (*self.river_handles, (SurfacePlanSlot.RIVER_RELIEF, self.river_binding))
        self.final_binding = binding(SurfacePlanSlot.HYDROLOGY, HydrologyFinalInput, HydrologyPlan, self.final_handles)
        self.route_provider = Mock(wraps=HydrologyRoutesPlanProvider(self.binding, self.water.binding))
        self.final_provider = Mock(wraps=HydrologyFinalPlanProvider(self.binding, self.routes_binding, self.river_binding))
        self.h.registry.register(self.routes_binding, self.route_provider)
        self.river_provider = RiverReliefPlanProvider(self.binding, self.routes_binding)
        self.h.registry.register(self.river_binding, self.river_provider)
        self.h.registry.register(self.final_binding, self.final_provider)
        self.river_inputs = RiverReliefInput(z_min=-100, z_max=100, grid=self.inputs.grid, topology=self.water.topology,
            channel_depths=tuple((kind, self.hydro_inputs.rivers.channel_depth_for(kind)) for kind in (
                HydrologyConnectionType.MOUNTAIN_RIVER, HydrologyConnectionType.RIVER)))
        self.final_inputs = HydrologyFinalInput(enabled=True, grid=self.inputs.grid, topology=self.water.topology)

    def segment(self, uid="river", start=(-20, 0), end=(10, 0), kind="river"):
        from app.dataModel.hydrology.declaredRiver import DeclaredRiver
        return DeclaredRiver.model_validate(dict(location_uid=uid, declare_mode="segments", segments=[
            {"from": dict(x=start[0], y=start[1]), "to": dict(x=end[0], y=end[1]),
             "connection_type": kind, "width_cells": 2}]))

    def signed(self, envelope, payload, manifest, dependencies=None):
        from app.application.planning.service.planFingerprints import output_fingerprint
        deps = envelope.dependencies if dependencies is None else dependencies
        return PlanEnvelope[type(payload)](ref=PlanRef(key=envelope.ref.key, output_fingerprint=output_fingerprint(
            payload, deps, envelope.diagnostics, manifest)), dependencies=deps, payload=payload, diagnostics=envelope.diagnostics)

    def execute(self, binding, inputs, handles, envelopes):
        from app.dataModel.planning.identity.planKey import PlanSlot
        deps = tuple(sorted((PlanDependency(slot=PlanSlot(slot.value), ref=env.ref) for (slot, _), env in zip(handles, envelopes)), key=lambda dep: dep.slot))
        reader = self.h.empty
        for (slot, handle), env in zip(handles, envelopes):
            reader = reader.with_plan(PlanSlot(slot.value), handle, env)
        meta = binding.metadata
        req = PlanRequest[type(inputs)](key=PlanKey(world_uid="climate-world", scope=WorldPlanScope(), contract_id=meta.id,
            schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=binding.fingerprint_inputs("climate-world", WorldPlanScope(), inputs, deps)), inputs=inputs, dependencies=deps)
        return self.h.service.get_or_build(binding, req, reader, wait=Wait(20))

    def routes(self, inputs=None, before=None, water=None):
        return self.execute(self.routes_binding, inputs or self.hydro_inputs, self.route_handles,
            (before or self.before, water or self.water_envelope))

    def finish(self, routes=None, river=None, before=None, inputs=None):
        before = before or self.before
        routes = routes or self.routes(before=before)
        river = river or self.execute(self.river_binding, self.river_inputs, self.river_handles, (before, routes))
        return self.execute(self.final_binding, inputs or self.final_inputs, self.final_handles, (before, routes, river))

    def test_routes_final_match_legacy_without_recarve_or_world_reads(self):
        from unittest.mock import patch
        from app.application.worldData.generators.hydrology.hydrologyGeneratorService import HydrologyGeneratorService
        from app.application.worldData.generators.hydrology.shore.fineHydrologyIndex import apply_declared_fine_river_carves
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap
        from app.dataModel.topology.fineTopology import fine_topology
        from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
        from tests.hydrology_fixtures import hydro_world
        source = {(cell.gx, cell.gy): z for cell, z in self.before.payload.surface_z}
        hm = SurfaceHeightmap("climate-world", self.water.terrain.inputs.bbox, dict(source))
        w = hydro_world(world_uid="climate-world", fine_cells_per_map_cell=10, z_min=-100, hydrology=dict(
            default_water_level=0, default_seas=self.hydro_inputs.seas.model_dump(), default_lakes=self.hydro_inputs.lakes.model_dump(),
            default_rivers=self.hydro_inputs.rivers.model_dump(), declared_rivers=[self.segment().model_dump()]))
        legacy = HydrologyGeneratorService().apply(w, [], hm, basin_specs=self.water_envelope.payload.basin_specs,
            topology=self.water.topology, change_uid="change")
        fine, z = apply_declared_fine_river_carves(w, [], source, topology=fine_topology(self.water.topology, 10),
            base_space=CoordinateSpace.WORLD_SURFACE_GRID, coarse_hydro=legacy.cell_index.by_cell, water_bodies=legacy.water_bodies)
        with patch("app.application.jsonValidation.worldRow.hydrology", side_effect=AssertionError("live World lookup")), patch(
            "app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedZ.river_bed_spec", side_effect=AssertionError("route profile")):
            routes = self.routes()
        with patch("app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider.assemble_water_bodies",
                   side_effect=AssertionError("final water discovery")):
            final = self.finish(routes)
        self.assertTrue(routes.payload.coarse_routes)
        self.assertTrue(routes.payload.fine_routes)
        self.assertEqual(dict(final.payload.coarse_surface_z), {cell: hm.surface_z[(cell.gx, cell.gy)] for cell, _ in final.payload.coarse_surface_z})
        self.assertEqual({(c.gx, c.gy): v for c, v in final.payload.coarse_hydro}, legacy.cell_index.by_cell)
        self.assertEqual(dict(final.payload.sparse_fine_hydro), fine)
        self.assertEqual(dict(final.payload.fine_z_overrides), z)
        self.assertEqual(final.payload.water_bodies, legacy.water_bodies)
        self.assertEqual(final.payload.physical_unions, legacy.physical_unions)
        self.assertEqual({(c.gx, c.gy): z for c, z in self.before.payload.surface_z}, source)

    def test_cache_clear_rebuild_restart_and_codec_equality(self):
        first, routes = self.finish(), self.routes()
        self.assertEqual(self.finish(), first)
        self.assertEqual(self.route_provider.build.call_count, 1)
        self.assertEqual(self.final_provider.build.call_count, 1)
        self.h.backend.clear()
        self.assertEqual(self.finish(), first)
        for binding, env in ((self.routes_binding, routes), (self.final_binding, first)):
            codec = binding.cache_binding.codec
            self.assertEqual(codec.decode(codec.encode(env)), env)
        original = self.h
        self.h = Harness(policy=PlanningExecutionPolicy(max_workers=1, max_pending_builds=2))
        self.addCleanup(self.h.service.shutdown)
        for binding, provider in ((self.binding, self.provider), (self.water.binding, self.water.provider),
            (self.routes_binding, self.route_provider), (self.river_binding, self.river_provider),
            (self.final_binding, self.final_provider)):
            self.h.registry.register(binding, provider)
        self.assertEqual(self.finish(), first)

    def test_routing_failure_is_partial_and_runtime_fallback_is_frozen(self):
        from app.dataModel.validation.enums.resolutionMode import ResolutionMode
        bad = self.segment(uid="bad", start=(-20, 10), end=(40, 10))
        inputs = self.hydro_inputs.model_copy(update={"declared_rivers": (bad,)})
        runtime = self.routes(inputs)
        self.assertTrue(any(d.disposition is PlanDiagnosticDisposition.FALLBACK for d in runtime.diagnostics))
        preview = self.routes(inputs.model_copy(update={"resolution_mode": ResolutionMode.VALIDATE_ONLY}))
        self.assertFalse(preview.payload.coarse_routes)
        self.assertTrue(preview.payload.water_bodies)
        self.assertTrue(all(d.disposition is PlanDiagnosticDisposition.ERROR for d in preview.diagnostics))
        invalid = self.routes(self.hydro_inputs.model_copy(update={"declared_rivers": (self.segment(uid="bad", kind="road"), self.segment(uid="not-river", kind="coastline"), self.segment())}))
        self.assertEqual([route.river_uid for route in invalid.payload.coarse_routes], ["river"])
        self.assertTrue(any(d.issue.code == "RIVER_INVALID_CONNECTION_TYPE" for d in invalid.diagnostics))

    def test_empty_disabled_and_scoped_water_keep_terrain(self):
        from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope
        for inputs in (self.hydro_inputs.model_copy(update={"enabled": False}),
                       self.hydro_inputs.model_copy(update={"scopes": frozenset()})):
            routes = self.routes(inputs)
            self.assertFalse(routes.payload.coarse_routes or routes.payload.fine_routes or routes.payload.water_bodies)
            final = self.finish(routes, inputs=self.final_inputs.model_copy(update={"enabled": inputs.enabled}))
            self.assertEqual(final.payload.coarse_surface_z, self.before.payload.surface_z)
            self.assertFalse(final.payload.coarse_hydro)
        no_rivers = self.routes(self.hydro_inputs.model_copy(update={"scopes": frozenset((HydrologyScope.OPEN_OCEAN,))}))
        self.assertTrue(no_rivers.payload.water_bodies)
        self.assertFalse(no_rivers.payload.coarse_routes)

    def test_edit_invalidates_dependencies_and_bad_bed_mapping_fails(self):
        from app.application.planning.service.planningService import PlanBuildFailure
        first = self.routes()
        changed = self.signed(self.before, self.before.payload.model_copy(update={"surface_z": tuple(
            (cell, z + 1 if cell.gx == -2 else z) for cell, z in self.before.payload.surface_z)}), self.manifest)
        second = self.routes(before=changed)
        self.assertNotEqual(first.ref, second.ref)
        self.assertNotEqual(self.finish(first).ref, self.finish(second, before=changed).ref)
        with self.assertRaises(PlanBuildFailure): self.finish(first, before=changed)
        river = self.execute(self.river_binding, self.river_inputs, self.river_handles, (self.before, first))
        bad = self.signed(river, river.payload.model_copy(update={"coarse_beds": ()}), self.hydro_manifest)
        with self.assertRaises(PlanBuildFailure): self.finish(first, bad)
        self.assertFalse(self.finish(first).diagnostics)

    def test_declared_paint_preserves_fine_geometry_order_width_and_missing_anchors(self):
        from app.dataModel.hydrology.declaredLake import DeclaredLake
        from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
        point = lambda x, y: dict(x=x, y=y)
        intent = self.Declare.model_validate(dict(location_uid="intent", declare_mode="via_locations",
            route_location_uids=["a", "missing", "b"]))
        inputs = self.hydro_inputs.model_copy(update={"declared_rivers": (self.segment(), intent),
            "anchors": (self.Anchor(location_uid="a", position=(-20, 0), z=None, subtype=None),
                        self.Anchor(location_uid="b", position=(10, 0), z=None, subtype=None)),
            "declared_lakes": (DeclaredLake.model_validate(dict(location_uid="lake", shoreline=[point(0, 0), point(10, 0), point(10, 10)])),),
            "coastlines": (DeclaredCoastline.model_validate(dict(location_uid="coast", kind="sea", path=[point(0, 0), point(10, 0)])),)})
        result = self.routes(inputs)
        paint = result.payload.declared_paint
        self.assertEqual(paint.segments[0].segment, ((-20, 0), (10, 0)))
        self.assertEqual(paint.segments[0].width_fine, 2)
        self.assertEqual(paint.lakes[0].shoreline_segments[-1], ((10, 10), (0, 0)))
        self.assertFalse(paint.intents)
        self.assertTrue(any(d.issue.code == "RIVER_MISSING_PAINT_GEOMETRY" for d in result.diagnostics))


    def test_procedural_baseline_keeps_seed_identity_and_geometry(self):
        from app.application.worldData.generators.hydrology.riverNetworkAssembler import assemble_rivers
        from app.application.worldData.generators.hydrology.types import HydrologyMasterInput, LoadedConnectionGraph
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap
        from tests.hydrology_fixtures import hydro_world
        inputs = self.hydro_inputs.model_copy(update={"declared_rivers": (),
            "rivers": self.hydro_inputs.rivers.model_copy(update={"autoresolve": True})})
        hm = SurfaceHeightmap("climate-world", self.water.terrain.inputs.bbox,
            {(cell.gx, cell.gy): z for cell, z in self.before.payload.surface_z})
        w = hydro_world(world_uid="climate-world", seed=inputs.seed, fine_cells_per_map_cell=10, z_min=-100,
            hydrology=dict(default_rivers=inputs.rivers.model_dump()))
        from app.ids import seed_int
        inputs = inputs.model_copy(update={"seed": seed_int(w)})
        routes = self.routes(inputs)
        self.assertTrue(routes.payload.coarse_routes)
        occupied = {(cell.gx, cell.gy): v for cell, v in routes.payload.coarse_open_water}
        master = HydrologyMasterInput(world_uid="climate-world", hydrology_enabled=True, scopes=inputs.scopes,
            connection_graph=LoadedConnectionGraph([], []))
        legacy = assemble_rivers(w, hm, master, occupied=occupied, topology=inputs.topology,
            water_bodies=routes.payload.water_bodies)
        expected = [(segment.edge_uid, tuple(segment.polyline_cells)) for segment in legacy.segments]
        self.assertEqual([(segment.edge_uid, tuple((cell.gx, cell.gy) for cell in segment.path))
            for route in routes.payload.coarse_routes for segment in route.segments], expected)
        first = self.finish(routes)
        self.assertEqual({(cell.gx, cell.gy): z for cell, z in first.payload.coarse_surface_z}, hm.surface_z)
        self.h.backend.clear()
        self.assertEqual(self.routes(inputs), routes)

    def test_endpoint_and_via_anchors_preserve_identity_and_wire_width(self):
        from app.dataModel.validation.enums.resolutionMode import ResolutionMode
        for via in (False, True):
            data = dict(location_uid="intent", declare_mode="via_locations", route_location_uids=["start", "mouth"]) if via else dict(
                location_uid="intent", declare_mode="endpoints", source=dict(x=-20, y=0), mouth=dict(location_uid="mouth"))
            intent = self.Declare.model_validate(data)
            inputs = self.hydro_inputs.model_copy(update={"declared_rivers": (intent,),
                "resolution_mode": ResolutionMode.VALIDATE_ONLY,
                "anchors": (self.Anchor(location_uid="start", position=(-20, 0), z=None, subtype=None),
                            self.Anchor(location_uid="mouth", position=(10, 0), z=None, subtype=None))})
            routes = self.routes(inputs)
            self.assertEqual([r.river_uid for r in routes.payload.coarse_routes], ["intent"])
            self.assertEqual([r.river_uid for r in routes.payload.fine_routes], ["intent"])
            self.assertEqual(routes.payload.coarse_routes[0].drainage.receiver_uid, "basin")
            self.assertEqual(routes.payload.declared_paint.intents[0].path, ((-20, 0), (10, 0)))
            self.assertEqual(routes.payload.declared_paint.intents[0].width_wire, 1)
            self.finish(routes)

    def test_confluence_is_rooted_and_receiver_bed_is_written_by_parent_once(self):
        parent = self.segment(uid="parent")
        child = self.Declare.model_validate(dict(location_uid="child", system_role="tributary", parent_location_uid="parent",
            declare_mode="segments", segments=[{"from": dict(x=-20, y=20), "to": dict(x=-20, y=0), "connection_type": "river"}]))
        # The vertical approach is flat and never uphill at the parent junction.
        before = self.signed(self.before, self.before.payload.model_copy(update={"surface_z": tuple(
            (cell, 10 if cell.gx == -2 and cell.gy > 0 else z) for cell, z in self.before.payload.surface_z)}), self.manifest)
        routes = self.routes(self.hydro_inputs.model_copy(update={"declared_rivers": (child, parent)}), before)
        self.assertEqual([r.river_uid for r in routes.payload.coarse_routes], ["parent", "child"])
        self.assertEqual(routes.payload.coarse_routes[1].drainage.receiver_uid, "parent")
        final = self.finish(routes, before=before)
        receiver = routes.payload.coarse_routes[1].receiver_cell
        self.assertEqual(dict(final.payload.coarse_surface_z)[receiver], dict(before.payload.surface_z)[receiver] - 3)

    def test_physical_union_and_water_diagnostics_survive_cache(self):
        # Disjoint authored footprints meet through the existing physical fill.
        from app.dataModel.spatial.regionShape import BboxShape
        water_inputs = self.water_inputs.model_copy(update={"basins": (
            self.water_inputs.basins[0].model_copy(update={"footprint": BboxShape(x_min=0, x_max=10, y_min=0, y_max=10)}),
            self.water_inputs.basins[0].model_copy(update={"location_uid": "other",
                "footprint": BboxShape(x_min=20, x_max=30, y_min=0, y_max=10)}))})
        water = self.water.get(inputs=water_inputs)
        deps = tuple(PlanDependency(slot=dep.slot, ref=water.ref if dep.slot == SurfacePlanSlot.WATER_PLACEMENT.value else dep.ref)
                     for dep in self.before.dependencies)
        before = self.signed(self.before, self.before.payload, self.manifest, deps)
        routes = self.routes(before=before, water=water)
        self.assertEqual({b.water_body_uid for b in routes.payload.water_bodies}, {"basin", "other"})
        self.assertTrue(routes.payload.physical_unions)
        final = self.finish(routes, before=before)
        self.assertEqual(final.payload.physical_unions, routes.payload.physical_unions)
        self.h.backend.clear()
        self.assertEqual(self.routes(before=before, water=water), routes)

    def test_final_rejects_incoherent_water_and_receiver_mapping(self):
        from app.application.planning.service.planningService import PlanBuildFailure
        water = self.water.get(inputs=self.water_inputs.model_copy(update={"enabled": False}))
        with self.assertRaises(PlanBuildFailure): self.routes(water=water)
        routes = self.routes()
        bad_payload = routes.payload.model_copy(update={"coarse_open_water": ()})
        bad_routes = self.signed(routes, bad_payload, self.hydro_manifest)
        with self.assertRaises(PlanBuildFailure): self.finish(bad_routes)

    def test_final_never_routes_profiles_discovers_or_writes(self):
        from unittest.mock import patch
        routes = self.routes()
        river = self.execute(self.river_binding, self.river_inputs, self.river_handles, (self.before, routes))
        path = "app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider."
        with patch(path + "prepared_declared_river_requests", side_effect=AssertionError("reroute")), patch(
            path + "assemble_water_bodies", side_effect=AssertionError("refill")), patch(
            "app.application.worldData.generators.terrain.reliefObjects.riverBed.riverBedZ.apply_river_bed_z",
            side_effect=AssertionError("recarve")):
            self.finish(routes, river)
