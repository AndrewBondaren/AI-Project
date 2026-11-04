"""P2W integration probe. Manifest bytes use the fixture BLOB registration."""
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest, encode_candidate_manifest
from app.dataModel.artifacts.lifecycle.holders import OperationHolder
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.dataModel.worldSnapshot.results.publication import CasDecision, PackActivationDisposition, PackActivationResult
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database


class ManifestActivationRollbackTests(IsolatedAsyncioTestCase):
    async def test_refused_handoff_rolls_back_applied_cas(self):
        writer = await self.enterAsyncContext(live_database())
        observer = await self.enterAsyncContext(live_database(writer[0].path, seed=False))
        staging, cold = SqliteBlobFixture(writer), SqliteBlobFixture(observer)
        _, commits, publications, *_ = writer
        async with commits.transaction("bootstrap") as scope:
            initial = await publications.initialize(scope, "w1")

        async def prepare(operation, cells, expected):
            candidate = WorldPackManifest(world_uid="w1", pack_version="2.0.0", spatial_roots=(),
                                          world_map_cells=cells)
            data = encode_candidate_manifest(candidate)
            lease = await staging.open(operation)
            ref = await staging.stager.stage(lease, data)
            await staging.service.finish_preparation(lease, (ref,))
            await staging.ledger.claim_publication(lease.kind, operation, "w1", "a" * 64, "b" * 64)
            publication = expected.model_copy(update={"publication_id": operation, "pack_hash": ref.content_hash})
            return lease, ref, publication, data

        lease_a, ref_a, active, bytes_a = await prepare("pack-a", 1, initial)
        async with commits.transaction("pack-a") as scope:
            self.assertIs(await publications.compare_append(scope, initial, active), CasDecision.APPLIED)
            await staging.ledger.record_terminal(scope, PackActivationResult(
                operation_id="pack-a", request_fingerprint="b" * 64, manifest=ref_a,
                disposition=PackActivationDisposition.ACTIVE, publication=active))

        lease_b, ref_b, candidate, _ = await prepare("pack-b", 2, active)
        with self.assertRaisesRegex(ValueError, "no published/retention owner"):
            async with commits.transaction("pack-b") as scope:
                self.assertIs(await publications.compare_append(scope, active, candidate), CasDecision.APPLIED)
                await staging.holders.handoff(scope, lease_b, (), (ref_b,))

        self.assertEqual(await observer[2].read("w1"), active)
        self.assertIsNone((await observer[-1].read("pack-b")).terminal)
        self.assertTrue(await cold.holders.is_held(ref_b, OperationHolder(lease=lease_b)))
        recovered = (await cold.service.recover("pack-a")).terminal
        assert isinstance(recovered, PackActivationResult)
        self.assertEqual(recovered.manifest.content_hash, active.pack_hash)
        async with cold.catalog.guard(recovered.manifest):
            self.assertTrue(await cold.holders.is_held(recovered.manifest, OperationHolder(lease=lease_a)))
            data = await cold.backend.read_verified(recovered.manifest, max_bytes=len(bytes_a))
        self.assertEqual(data, bytes_a)
        self.assertEqual(decode_manifest(data).world_map_cells, 1)
