from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from app.application.artifacts.staging.artifactStaging import TypedArtifactStager
from app.application.worldData.pack.encoding.manifestFormat import MANIFEST_STORAGE_VERSION
from app.application.worldData.pack.encoding.packManifestCodec import encode_candidate_manifest
from app.core.container.packs import PacksWiring
from app.core.appSettings import app_settings
from app.core.container import Container
from app.dataModel.worldPack.bake.worldPackCacheSettings import WorldPackCacheSettings
from app.application.worldData.pack.encoding.manifestFormat import MANIFEST_FORMAT_KEY
from app.dataModel.worldPack.wire.climateFieldWire import CLIMATE_FIELD_FORMAT_KEY
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database


class ManifestFormatTests(IsolatedAsyncioTestCase):
    async def test_container_initializes_configured_storage_once(self):
        bundle = await self.enterAsyncContext(live_database())
        container = Container(None, bundle[0])
        config = WorldPackCacheSettings.model_validate({
            "manifest_cache": {"max_entry_bytes": 100, "max_retained_bytes": 200},
        })
        with patch.object(app_settings, "world_pack", config):
            container.initialize_pack_storage()
            self.assertIsNone(container._pack_formats)
        with patch.object(app_settings, "world_pack", config.model_copy(update={"manifest_max_bytes": 4096})):
            container.initialize_pack_storage()
            registry = container._pack_formats
            self.assertEqual(registry.metadata(MANIFEST_FORMAT_KEY).supported_versions, {1})
            self.assertEqual(registry.metadata(CLIMATE_FIELD_FORMAT_KEY).supported_versions, {1})
            container.initialize_pack_storage()
            self.assertIs(container._pack_formats, registry)

    async def test_exact_budget_and_refusals_before_storage_io(self):
        model = WorldPackManifest(world_uid="w1", pack_version="2.0.0", spatial_roots=())
        data = encode_candidate_manifest(model)
        directory = Path(self.enterContext(TemporaryDirectory()))
        bundle = await self.enterAsyncContext(live_database(str(directory / "pack.db")))
        f = SqliteBlobFixture(bundle)
        registry = f.service._registry
        backend = PacksWiring.register_manifest_format(registry, directory / "artifacts", f.leases,
                                                      max_bytes=len(data))
        stager = TypedArtifactStager(backend.contract, MANIFEST_STORAGE_VERSION, registry, f.service)
        lease = await f.open("manifest")
        ref = await stager.stage(lease, data)
        self.assertEqual(await backend.read_verified(ref, max_bytes=len(data)), data)
        with patch.object(f.service, "reserve", side_effect=AssertionError("unexpected reservation")):
            for invalid in (data + b" ", b'{"world_uid":"w1"}', b'{'):
                with self.subTest(data=invalid[:10]), self.assertRaises(ValueError):
                    await stager.stage(lease, invalid)
        with patch.object(backend, "_io", side_effect=AssertionError("unexpected physical IO")):
            with self.assertRaises(ValueError):
                await backend.read_verified(ref, max_bytes=len(data)-1)
            with self.assertRaises(ValueError):
                await backend.read_verified(ref.model_copy(update={"nbytes": len(data)+1}), max_bytes=len(data)+100)
