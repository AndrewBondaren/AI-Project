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
        metadata = PlanContractMetadata(id="surface.pc.climate_base", schema_version=1, algorithm_version=1)
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
            fingerprint, (), CacheBinding(CacheContract[plan_type](id="surface.envelope.pc.climate_base", schema_version=1),
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


if __name__ == "__main__":
    unittest.main()
