"""Step 4: exercise the real cache composition, configuration and eviction."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.dataModel.worldPack.meta.manifestCacheContract import MANIFEST_BYTES_CONTRACT
from app.application.cache.service.cacheService import CacheFailure
from app.application.worldData.pack.encoding.manifestCacheKey import manifest_cache_key
from app.application.worldData.planning.composition.planProviders import register_world_plan_providers, world_plan_contracts
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.core.appSettings import AppSettings, app_settings
from app.core.configManager import ConfigManager
from app.core.container import Container
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheError import CacheIssueCode
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheMiss
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.climate.planning.climatePlan import ClimateLocalPlan
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.worldPack.bake.worldPackCacheSettings import WorldPackCacheSettings
from app.dataModel.surfacePlanning.surfacePlanBindings import PC_SURFACE_BINDINGS, surface_plan_binding
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from tests.cache.test_admission import configured


def manifest_entry(i):
    key = CacheKey[bytes](contract=MANIFEST_BYTES_CONTRACT, item_key=i.to_bytes(32))
    return CacheEntry[bytes](key=key, value=i.to_bytes(4))


def plan_entry(i):
    declaration = surface_plan_binding(SurfacePlanSlot.CLIMATE_LOCAL)
    plan_key = PlanKey(world_uid="w1", scope=WorldPlanScope(), contract_id=declaration.metadata.id,
                       schema_version=declaration.metadata.schema_version, algorithm_version=1,
                       input_fingerprint=i.to_bytes(32))
    envelope = PlanEnvelope[ClimateLocalPlan](ref=PlanRef(key=plan_key, output_fingerprint=bytes(32)),
                                              dependencies=(), payload=ClimateLocalPlan(anchors=()), diagnostics=())
    key = CacheKey[PlanEnvelope[ClimateLocalPlan]].model_validate({
        "contract": {"id": declaration.cache_id, "schema_version": declaration.cache_schema_version},
        "item_key": i.to_bytes(32),
    })
    return CacheEntry(key=key, value=envelope)


class ContainerCacheTests(TestCase):
    def setUp(self):
        self.pack = WorldPackCacheSettings.model_validate({
            "manifest_cache": {"max_entry_bytes": 8000, "max_retained_bytes": 8500}})

    def test_config_roundtrip(self):
        with TemporaryDirectory() as directory:
            manager = ConfigManager(Path(directory) / "config.toml")
            self.assertNotIn("world_pack", manager.load())
            manager.save(AppSettings(world_pack=self.pack))
            self.assertIn("[world_pack.manifest_cache]", manager.path.read_text(encoding="utf8"))
            self.assertEqual(manager.load()["world_pack"], self.pack)
            for body in ("[world_pack]", "[world_pack.manifest_cache]\nmax_entry_bytes = 5\nmax_retained_bytes = 2"):
                manager.path.write_text(body, encoding="utf8")
                with self.assertRaises(ValidationError):
                    manager.load()

    def test_lazy_factories(self):
        with patch.object(app_settings, "world_pack", None), patch.object(app_settings, "planning", configured()):
            container = Container(None, None)
            with self.assertRaisesRegex(ValueError, "world_pack.manifest_cache"):
                container.pack_manifest_cache_service()
            with patch.object(app_settings, "world_pack", self.pack):
                for factory in (container.planning_v2_cache_service, container.pack_manifest_cache_service):
                    with ThreadPoolExecutor(8) as pool:
                        services = list(pool.map(lambda _: factory(), range(30)))
                    self.assertTrue(all(service is services[0] for service in services))
                self.assertIsNot(container.planning_v2_cache_service(), container.pack_manifest_cache_service())
                self.assertIsNot(container.pack_manifest_cache_service(), Container(None, None).pack_manifest_cache_service())

    def test_registry_boundaries(self):
        with patch.object(app_settings, "world_pack", self.pack), patch.object(app_settings, "planning", configured()):
            container = Container(None, None)
            plans = container.planning_v2_cache_service()
            pack = container.pack_manifest_cache_service()
            for declared in PC_SURFACE_BINDINGS:
                key = CacheKey.model_validate({
                    "contract": {"id": declared.cache_id, "schema_version": declared.cache_schema_version},
                    "item_key": bytes(32),
                })
                self.assertIsInstance(plans.get(key), CacheMiss)
                with self.assertRaises(CacheFailure) as caught:
                    pack.get(key)
                self.assertEqual(caught.exception.error.issues[0].code, CacheIssueCode.UNKNOWN_NAMESPACE)
            with self.assertRaises(CacheFailure) as caught:
                plans.get(manifest_entry(0).key)
            self.assertEqual(caught.exception.error.issues[0].code, CacheIssueCode.UNKNOWN_NAMESPACE)

    def test_first_registry_or_facade_access_registers_once(self):
        target = "app.core.container.worldData.register_world_plan_providers"
        for first in ("registry", "facade", "concurrent"):
            with self.subTest(first=first), patch.object(app_settings, "planning", configured()), patch(
                    target, wraps=register_world_plan_providers) as register:
                container = Container(None, None)
                self.addCleanup(container.shutdown_planning)
                if first == "registry":
                    container.plan_registry().check(container._planning_contracts().climate_base)
                elif first == "facade":
                    container.surface_planning()
                barrier = Barrier(2)

                def access_registry():
                    barrier.wait(timeout=5)
                    return container.plan_registry()

                with ThreadPoolExecutor(2) as pool:
                    registry_job = pool.submit(access_registry)
                    barrier.wait(timeout=5)
                    facade = container.surface_planning()
                    registry = registry_job.result(timeout=5)
                register.assert_called_once()
                self.assertIs(registry, container.plan_registry())
                self.assertIs(facade, container.surface_planning())
                registry.check(container._planning_contracts().climate_local)

    def test_partial_provider_registration_can_retry(self):
        container = Container(None, None)

        def fail_after_registration(registry, contracts):
            register_world_plan_providers(registry, contracts)
            raise RuntimeError("registration interrupted")

        with patch("app.core.container.worldData.register_world_plan_providers", fail_after_registration):
            with self.assertRaisesRegex(RuntimeError, "registration interrupted"):
                container.plan_registry()
        container.plan_registry().check(container._planning_contracts().climate_base)

    def test_cache_composition_does_not_register_or_invoke_domain_providers(self):
        with (patch.object(app_settings, "world_pack", self.pack),
              patch.object(app_settings, "planning", configured()),
              patch("app.core.container.worldData.register_world_plan_providers",
                    side_effect=AssertionError("Cache must not construct domain providers"))):
            container = Container(None, None)
            plans = container.planning_v2_cache_service()
            climate = plan_entry(1).value
            contract = world_plan_contracts().climate_local
            key = contract.cache_key(climate.ref.key)
            self.assertIsInstance(plans.get(key), CacheMiss)
            self.assertEqual(plans.create(CacheEntry(key=key, value=climate)).outcome, CacheAdmission.STORED)
            self.assertEqual(plans.get(key).entry.value, climate)
            with self.assertRaises(ValueError):
                world_plan_contracts().climate_base.cache_key(climate.ref.key)

            ref = ArtifactRef(kind=ArtifactKind.BLOB, format_key="test.manifest", format_version=1,
                              content_hash=sha256(b"data").hexdigest(), nbytes=4)
            manifest_key = manifest_cache_key(ref)
            pack = container.pack_manifest_cache_service()
            self.assertEqual(pack.create(CacheEntry(key=manifest_key, value=b"data")).outcome, CacheAdmission.STORED)
            restored = ArtifactRef.model_validate_json(ref.model_dump_json())
            self.assertEqual(pack.get(manifest_cache_key(restored)).entry.value, b"data")
            for change in ({"format_key": "test.other"}, {"format_version": 2}, {"nbytes": 5}):
                self.assertIsInstance(pack.get(manifest_cache_key(ref.model_copy(update=change))), CacheMiss)

    def test_eviction_is_isolated_in_both_directions(self):
        with patch.object(app_settings, "world_pack", self.pack), patch.object(app_settings, "planning", configured()):
            container = Container(None, None)
            plans = container.planning_v2_cache_service()
            pack = container.pack_manifest_cache_service()
            for writer, peer, make, other in ((pack, plans, manifest_entry, plan_entry),
                                               (plans, pack, plan_entry, manifest_entry)):
                with self.subTest(writer=make.__name__):
                    protected = other(99)
                    self.assertEqual(peer.create(protected).outcome, CacheAdmission.STORED)
                    before = peer._backend.retained_bytes
                    first = make(0)
                    self.assertEqual(writer.create(first).outcome, CacheAdmission.STORED)
                    for i in range(1, 64):
                        self.assertEqual(writer.create(make(i)).outcome, CacheAdmission.STORED)
                    self.assertIsInstance(writer.get(first.key), CacheMiss)
                    self.assertEqual(peer._backend.retained_bytes, before)
                    self.assertIsInstance(peer.get(protected.key), CacheHit)
