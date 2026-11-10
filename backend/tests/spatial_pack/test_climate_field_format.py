from pathlib import Path
from dataclasses import asdict, replace
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from app.application.artifacts.contracts.blobRead import ReadableBlobBackend
from app.application.artifacts.staging.artifactStaging import TypedArtifactStager
from app.application.worldData.pack.encoding.climateFieldFormat import CLIMATE_FIELD_FORMAT
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest
from app.application.worldData.pack.encoding.preparedManifest import finish_pack_preparation
from app.application.worldData.pack.io.packBlobWire import climate_field_payload
from app.application.worldData.pack.io.tileCodec import PAYLOAD_KIND_CLIMATE, PAYLOAD_KIND_WORLD_MAP, TileCodec
from app.core.container.packs import PacksWiring
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest, TileManifestEntry
from app.dataModel.worldPack.read.pinnedManifest import ManifestPinRead, ManifestStorageRead
from app.dataModel.worldSnapshot.results.publication import CasDecision, PackActivationDisposition, PackActivationResult
from app.db.repositories.sqlite.worldPack.climateRetention import retain_climate_members
from app.dataModel.worldPack.wire.climateFieldWire import ClimateFieldWire, ClimateSampleWire
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database
from tests.spatial_pack.test_execution_pins import ExecutionPinFixture


class ClimateFieldFormatTests(IsolatedAsyncioTestCase):
    async def test_existing_wire_stages_and_reopens(self):
        directory = Path(self.enterContext(TemporaryDirectory()))
        db = str(directory / "pack.db")
        codec = TileCodec()
        artifacts = []
        async with live_database(db) as bundle:
            fixture = SqliteBlobFixture(bundle)
            registry = fixture.service._registry
            PacksWiring.register_climate_field_format(registry, directory / "artifacts", fixture.leases)
            stager = TypedArtifactStager(CLIMATE_FIELD_FORMAT, 1, registry, fixture.service)
            lease = await fixture.open("climate")
            for status in ("coarse", "fine"):
                field = ClimateFieldWire(climate_status=status, width=1, height=1,
                                         samples=[ClimateSampleWire(rainfall=3)])
                blob = codec.encode(PAYLOAD_KIND_CLIMATE, climate_field_payload(field))
                ref = await stager.stage(lease, blob)
                self.assertEqual(ref.content_hash, codec.content_hash(blob))
                artifacts.append((ref, blob))
            with self.assertRaises(ValueError):
                await stager.stage(lease, codec.encode(PAYLOAD_KIND_WORLD_MAP, climate_field_payload(field)))
            with self.assertRaises(ValueError):
                await stager.stage(lease, codec.encode(PAYLOAD_KIND_CLIMATE, {}))
            await fixture.service.finish_preparation(lease, tuple(ref for ref, _ in artifacts))

        async with live_database(db, seed=False) as bundle:
            fixture = SqliteBlobFixture(bundle)
            registry = fixture.service._registry
            PacksWiring.register_climate_field_format(registry, directory / "artifacts", fixture.leases)
            for ref, expected in artifacts:
                await registry.verify(ref)
                backend = registry.resolve(CLIMATE_FIELD_FORMAT)
                assert isinstance(backend, ReadableBlobBackend)
                blob = await backend.read_verified(ref, max_bytes=ref.nbytes)
                self.assertEqual(registry.decode(CLIMATE_FIELD_FORMAT, blob, ref.format_version), expected)


class PinnedClimateRetentionTests(ExecutionPinFixture):
    async def test_pinned_climate_survives_replacement_restart_and_gc(self):
        f = self.fixture
        registry = f.service._registry
        PacksWiring.register_climate_field_format(registry, self.path.parent / "artifacts", f.leases)
        stager = TypedArtifactStager(CLIMATE_FIELD_FORMAT, 1, registry, f.service)
        # A sealed fixture anchor represents the publication head in this storage probe.
        head_holder = ArtifactRetentionHolder(artifact=self.manifest)

        async def publish_fields(operation, rainfall, previous=None):
            lease = await f.open(operation)
            blobs = {}
            for status in ("coarse", "fine"):
                field = ClimateFieldWire(climate_status=status, width=1, height=1,
                                         samples=[ClimateSampleWire(rainfall=rainfall)])
                blob = TileCodec().encode(PAYLOAD_KIND_CLIMATE, climate_field_payload(field))
                blobs[await stager.stage(lease, blob)] = blob
            coarse, fine = blobs
            manifest = WorldPackManifest(world_uid="w1", pack_version="2.0.0", spatial_roots=(),
                climate_coarse_ref=coarse, tiles=[TileManifestEntry(gx=0, gy=0, climate_status="fine",
                                                                    climate_fine_ref=fine)])
            ref = await finish_pack_preparation(lease, manifest, (), f.stager, f.service)
            await f.ledger.claim_publication(lease.kind, operation, lease.world_uid, "a"*64, "b"*64)
            head = self.head.model_copy(update={"publication_id": operation, "pack_hash": ref.content_hash})
            if previous is not None:
                with self.assertRaisesRegex(RuntimeError, "abort publication"):
                    async with self.bundle[1].transaction(operation) as scope:
                        self.assertIs(await self.bundle[2].compare_append(scope, self.head, head), CasDecision.APPLIED)
                        await retain_climate_members(scope, f.holders, lease, ref, manifest)
                        raise RuntimeError("abort publication")
                self.assertEqual(await self.bundle[2].read("w1"), self.head)
                for member in manifest.climate_artifacts():
                    self.assertFalse(await f.holders.is_held(member, ArtifactRetentionHolder(artifact=ref)))
            async with self.bundle[1].transaction(operation) as scope:
                self.assertIs(await self.bundle[2].compare_append(scope, self.head, head), CasDecision.APPLIED)
                await retain_climate_members(scope, f.holders, lease, ref, manifest)
                async with f.catalog._scopes.bind(scope):
                    await f.holders.acquire(ref, head_holder)
                    if previous is not None:
                        await f.holders.release(previous, head_holder)
                await f.holders.handoff(scope, lease, (), (ref, *manifest.climate_artifacts()))
                await f.ledger.record_terminal(scope, PackActivationResult(operation_id=operation,
                    request_fingerprint="b"*64, manifest=ref, disposition=PackActivationDisposition.ACTIVE,
                    publication=head))
            self.head = head
            return ref, blobs

        ref_a, fields_a = await publish_fields("climate-a", 1)
        intent = replace(self.intent, logical_read_key="climate", pin_id="pin-climate-a")
        self.assertEqual(await self.pins.acquire(intent), ref_a)
        ref_b, fields_b = await publish_fields("climate-b", 2, ref_a)
        self.assertTrue(fields_a.keys().isdisjoint(fields_b))
        await self.reopen()
        cold = self.fixture
        registry = cold.service._registry
        PacksWiring.register_climate_field_format(registry, self.path.parent / "artifacts", cold.leases)
        self.assertEqual((await self.bundle[2].read("w1")).pack_hash, ref_b.content_hash)
        candidates = (ref_a, *fields_a)
        self.assertEqual((await cold.service.collect("gc-climate", candidates)).retained, candidates)
        pin = ManifestPinRead(**asdict(intent), max_bytes=ref_a.nbytes)
        address = await self.manifest_reader.resolve(pin)
        result = await self.manifest_reader.read_verified(ManifestStorageRead(pin=pin, address=address))
        self.assertEqual(result.ref, ref_a)
        manifest = decode_manifest(result.payload)
        self.assertEqual(manifest.climate_artifacts(), tuple(fields_a))
        backend = registry.resolve(CLIMATE_FIELD_FORMAT)
        assert isinstance(backend, ReadableBlobBackend)
        for child in manifest.climate_artifacts():
            async with cold.catalog.guard(child):
                self.assertEqual(await cold.holders.holders(child), (ArtifactRetentionHolder(artifact=ref_a),))
                self.assertEqual(await backend.read_verified(child, max_bytes=child.nbytes), fields_a[child])
