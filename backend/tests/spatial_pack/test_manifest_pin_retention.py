"""Two-connection lifetime probe with explicit test-only head and pin owners."""
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from app.application.artifacts.staging.artifactStaging import TypedArtifactStager
from app.application.worldData.generators.hydrology.encoding.packCodec import (
    decode_root, encode_root, encode_shard,
)
from app.application.worldData.generators.hydrology.encoding.packFormats import ROOT_FORMAT, SHARD_FORMAT
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest, encode_candidate_manifest
from app.application.worldData.pack.spatial.openWaterBlobReader import OpenWaterBlobReader
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.worldPack.meta.spatial.domainRoot import SpatialDatasetKind, SpatialDomainRootRef
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.dataModel.worldSnapshot.results.publication import CasDecision, PackActivationDisposition, PackActivationResult
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import STAMP, live_database
from tests.spatial_pack.test_storage_schema import records


class ManifestPinRetentionTests(IsolatedAsyncioTestCase):
    async def test_first_shard_read_after_head_change_and_gc(self):
        writer = await self.enterAsyncContext(live_database())
        observer = await self.enterAsyncContext(live_database(writer[0].path, seed=False))
        a, b = SqliteBlobFixture(writer), SqliteBlobFixture(observer)
        root, shard = records()
        world = root.source_ref.key.world_uid
        async with writer[0].transaction():
            await writer[0].conn.execute("INSERT INTO worlds(world_uid,name,created_at) VALUES (?,?,?)",
                                         (world, world, STAMP))
        for fixture in (a, b):
            for contract in (ROOT_FORMAT, SHARD_FORMAT):
                fixture.service._registry.register(contract, ContentAddressedBlobBackend(
                    Path(writer[0].path).parent / "artifacts", contract, fixture.leases))
        registry = a.service._registry
        commits, publications = writer[1:3]
        async with commits.transaction("init") as scope:
            initial = await publications.initialize(scope, world)

        # Sealed fixture artifacts stand in for distinct head/pin identities.
        anchors = await a.open("anchors")
        head = ArtifactRetentionHolder(artifact=await a.stager.stage(anchors, b"head"))
        pin = ArtifactRetentionHolder(artifact=await a.stager.stage(anchors, b"reader"))

        async def activate(operation, expected, previous_manifest=None):
            lease = await a.service.open_operation(operation, world, OperationKind.PACK_ACTIVATION, "a" * 64)
            children = ()
            roots = ()
            if previous_manifest is None:
                shard_ref = await TypedArtifactStager(SHARD_FORMAT, 1, registry, a.service).stage(
                    lease, encode_shard(shard))
                catalog = root.model_copy(update={"shards": (root.shards[0].model_copy(update={"artifact": shard_ref}),)})
                root_ref = await TypedArtifactStager(ROOT_FORMAT, 1, registry, a.service).stage(lease, encode_root(catalog))
                children = (root_ref, shard_ref)
                roots = (SpatialDomainRootRef(domain=SpatialDatasetKind.HYDROLOGY_OPEN_WATER, root=root_ref),)
            manifest = WorldPackManifest(world_uid=world, pack_version="2.0.0", spatial_roots=roots)
            ref = await a.stager.stage(lease, encode_candidate_manifest(manifest))
            refs = (ref, *children)
            await a.service.finish_preparation(lease, refs)
            await a.ledger.claim_publication(lease.kind, operation, world, "a" * 64, "b" * 64)
            active = expected.model_copy(update={"publication_id": operation, "pack_hash": ref.content_hash})
            async with commits.transaction(operation) as scope:
                self.assertIs(await publications.compare_append(scope, expected, active), CasDecision.APPLIED)
                async with a.catalog._scopes.bind(scope):
                    await a.holders.acquire(ref, head)
                    for child in children:
                        await a.holders.acquire(child, ArtifactRetentionHolder(artifact=ref))
                    if previous_manifest is not None:
                        await a.holders.release(previous_manifest, head)
                await a.holders.handoff(scope, lease, (), refs)
                await a.ledger.record_terminal(scope, PackActivationResult(operation_id=operation,
                    request_fingerprint="b" * 64, manifest=ref, disposition=PackActivationDisposition.ACTIVE,
                    publication=active))
            return active, refs

        active_a, (manifest_a, root_a, shard_a) = await activate("pack-a", initial)
        async with observer[1].transaction("pin-a") as scope:
            self.assertEqual(await observer[2].read(world, scope=scope.read_scope), active_a)
            async with b.catalog._scopes.bind(scope):
                await b.holders.acquire(manifest_a, pin)
        active_b, (manifest_b,) = await activate("pack-b", active_a, manifest_a)
        self.assertEqual(await observer[2].read(world), active_b)
        candidates = (manifest_a, root_a, shard_a, manifest_b)
        self.assertEqual(await b.holders.holders(manifest_a), (pin,))
        self.assertEqual((await b.service.collect("gc-pinned", candidates)).retained, candidates)
        owner = ArtifactRetentionHolder(artifact=manifest_a)
        async with b.catalog.guard(manifest_a):
            self.assertTrue(await b.holders.is_held(manifest_a, pin))
            restored = decode_manifest(await b.backend.read_verified(manifest_a, max_bytes=manifest_a.nbytes))
        reader = OpenWaterBlobReader(b.service._registry, b.catalog, b.holders)
        catalog = decode_root(await reader.read_root(restored.spatial_roots[0].root, owner), 1)
        self.assertEqual(await reader.read_shard(catalog.shards[0].artifact, owner), encode_shard(shard))

        async with observer[1].transaction("release-pin") as scope:
            async with b.catalog._scopes.bind(scope):
                await b.holders.release(manifest_a, pin)
                self.assertFalse(await b.holders.holders(manifest_a))
                for child in (root_a, shard_a):
                    await b.holders.release(child, owner)
        collected = await b.service.collect("gc-released", candidates)
        self.assertEqual(collected.deleted, (manifest_a, root_a, shard_a))
        self.assertEqual(collected.retained, (manifest_b,))
