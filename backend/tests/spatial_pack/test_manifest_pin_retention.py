"""Two-connection lifetime probe with explicit test-only head and pin owners."""
import asyncio
import threading
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
        await self.exercise_versions(shared=False, pin_first=True)

    async def test_pin_wins_race_and_shared_shard_survives_last_release(self):
        await self.exercise_versions(shared=True, pin_first=True)

    async def test_activation_wins_race_and_pin_resolves_new_head(self):
        await self.exercise_versions(shared=True, pin_first=False)

    async def exercise_versions(self, *, shared, pin_first):
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

        async def prepare(operation, expected, previous_manifest=None):
            lease = await a.service.open_operation(operation, world, OperationKind.PACK_ACTIVATION, "a" * 64)
            children = ()
            roots = ()
            if previous_manifest is None or shared:
                shard_ref = await TypedArtifactStager(SHARD_FORMAT, 1, registry, a.service).stage(
                    lease, encode_shard(shard))
                catalog = root.model_copy(update={"shards": (root.shards[0].model_copy(update={"artifact": shard_ref}),)})
                root_ref = await TypedArtifactStager(ROOT_FORMAT, 1, registry, a.service).stage(lease, encode_root(catalog))
                children = (root_ref, shard_ref)
                roots = (SpatialDomainRootRef(domain=SpatialDatasetKind.HYDROLOGY_OPEN_WATER, root=root_ref),)
            manifest = WorldPackManifest(world_uid=world, pack_version="2.0.0", spatial_roots=roots, world_map_cells=int(previous_manifest is not None))
            ref = await a.stager.stage(lease, encode_candidate_manifest(manifest))
            refs = (ref, *children)
            await a.service.finish_preparation(lease, refs)
            await a.ledger.claim_publication(lease.kind, operation, world, "a" * 64, "b" * 64)
            active = expected.model_copy(update={"publication_id": operation, "pack_hash": ref.content_hash})
            return active, refs, lease

        async def activate(prepared, expected, previous_manifest=None, during_commit=None):
            active, refs, lease = prepared
            ref, *children = refs
            operation = lease.operation_id
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
                if during_commit:
                    await during_commit()

        prepared_a = await prepare("pack-a", initial)
        active_a, (manifest_a, root_a, shard_a), _ = prepared_a
        await activate(prepared_a, initial)
        prepared_b = await prepare("pack-b", active_a, manifest_a)
        active_b, refs_b, _ = prepared_b
        manifest_b = refs_b[0]
        if shared:
            self.assertEqual(refs_b[1:], (root_a, shard_a))
        refs_by_hash = {ref.content_hash: ref for ref in (manifest_a, manifest_b)}
        second_pin = ArtifactRetentionHolder(artifact=await a.stager.stage(anchors, b"reader-2"))

        async def pin_active(identity, during_pin=None):
            async with observer[1].transaction("pin-active") as scope:
                observed = await observer[2].read(world, scope=scope.read_scope)
                ref = refs_by_hash[observed.pack_hash]
                if during_pin:
                    await during_pin()
                async with b.catalog._scopes.bind(scope):
                    await b.holders.acquire(ref, identity)
                return ref

        self.assertEqual(await pin_active(pin), manifest_a)
        attempted = threading.Event()
        competing_db = writer[0] if pin_first else observer[0]
        await competing_db.conn.set_trace_callback(
            lambda sql: attempted.set() if sql == "BEGIN IMMEDIATE" else None)
        async with asyncio.TaskGroup() as tasks:
            async def start_contender():
                nonlocal contender
                action = activate(prepared_b, active_a, manifest_a) if pin_first else pin_active(second_pin)
                contender = tasks.create_task(action)
                self.assertTrue(await asyncio.to_thread(attempted.wait, 5))
                self.assertFalse(contender.done())

            contender = None
            if pin_first:
                self.assertEqual(await pin_active(second_pin, start_contender), manifest_a)
            else:
                await activate(prepared_b, active_a, manifest_a, start_contender)
        await competing_db.conn.set_trace_callback(None)
        if not pin_first:
            self.assertEqual(contender.result(), manifest_b)
        self.assertEqual(await observer[2].read(world), active_b)
        candidates = (manifest_a, root_a, shard_a, manifest_b)
        if pin_first:
            self.assertCountEqual(await b.holders.holders(manifest_a), (pin, second_pin))
            await b.holders.release(manifest_a, pin)
            pin = second_pin
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
        if shared:
            self.assertEqual(collected.deleted, (manifest_a,))
            self.assertEqual(collected.retained, (root_a, shard_a, manifest_b))
            owner_b = ArtifactRetentionHolder(artifact=manifest_b)
            async with b.catalog.guard(manifest_b):
                holder = head if pin_first else second_pin
                self.assertTrue(await b.holders.is_held(manifest_b, holder))
                current = decode_manifest(await b.backend.read_verified(manifest_b, max_bytes=manifest_b.nbytes))
            catalog_b = decode_root(await reader.read_root(current.spatial_roots[0].root, owner_b), 1)
            self.assertEqual(await reader.read_shard(catalog_b.shards[0].artifact, owner_b), encode_shard(shard))
            return
        self.assertEqual(collected.deleted, (manifest_a, root_a, shard_a))
        self.assertEqual(collected.retained, (manifest_b,))
