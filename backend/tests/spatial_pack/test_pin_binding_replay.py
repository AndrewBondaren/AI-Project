"""Storage experiment: the probe table and sealed pin tokens are fixture-only."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.pack.encoding.packManifestCodec import encode_candidate_manifest
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.dataModel.worldSnapshot.results.publication import CasDecision, PackActivationDisposition, PackActivationResult
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database


async def activate(bundle, fixture, operation, cells):
    lease = await fixture.open(operation)
    data = encode_candidate_manifest(WorldPackManifest(world_uid="w1", pack_version="2.0.0",
                                                       spatial_roots=(), world_map_cells=cells))
    ref = await fixture.stager.stage(lease, data)
    await fixture.service.finish_preparation(lease, (ref,))
    await fixture.ledger.claim_publication(lease.kind, operation, "w1", "a" * 64, "b" * 64)
    async with bundle[1].transaction(operation) as scope:
        expected = await bundle[2].read("w1", scope=scope.read_scope)
        active = expected.model_copy(update={"publication_id": operation, "pack_hash": ref.content_hash})
        assert await bundle[2].compare_append(scope, expected, active) is CasDecision.APPLIED
        await fixture.ledger.record_terminal(scope, PackActivationResult(operation_id=operation,
            request_fingerprint="b" * 64, manifest=ref, disposition=PackActivationDisposition.ACTIVE,
            publication=active))


async def acquire(bundle, fixture, pin, owner, *, rollback=False, check_owner=None):
    db, commits, publications = bundle[:3]
    async with commits.transaction("acquire") as scope:
        if check_owner is not None:
            await check_owner()
        access = fixture.catalog._scopes.access
        binding = await access.one(scope, "SELECT * FROM probe_pins WHERE pin=?", (pin,))
        if binding is not None:
            if binding["owner"] != owner or binding["closed"]:
                raise ValueError("foreign or closed pin")
            publication_id = binding["publication_id"]
        else:
            publication_id = (await publications.read("w1", scope=scope.read_scope)).publication_id
            await db.conn.execute("INSERT INTO probe_pins VALUES (?,?,?,0)", (pin, owner, publication_id))

        async def lookup(digest):
            row = await access.one(scope, """SELECT artifact_id FROM artifact_catalog
                WHERE kind='blob' AND format_key='test.blob' AND format_version=1 AND content_hash=?""", (digest,))
            return await fixture.catalog._by_id(scope, row["artifact_id"])

        publication = await access.one(scope, "SELECT pack_hash FROM world_publications WHERE publication_id=?",
                                       (publication_id,))
        manifest = await lookup(publication["pack_hash"])
        token = await lookup(sha256(pin.encode()).hexdigest())
        holder = ArtifactRetentionHolder(artifact=token)
        async with fixture.catalog._scopes.bind(scope):
            if binding is None:
                await fixture.holders.acquire(manifest, holder)
            elif not await fixture.holders.is_held(manifest, holder):
                raise ValueError("binding has lost its hold")
        if rollback:
            raise RuntimeError("interrupt before commit")
        return publication_id, manifest, holder


class PinBindingReplayTests(IsolatedAsyncioTestCase):
    async def test_commit_and_rollback_are_distinguishable_after_reopen(self):
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "world.sqlite")
            async with live_database(path) as first:
                fixture = SqliteBlobFixture(first)
                async with first[0].transaction():
                    await first[0].conn.execute("""CREATE TABLE probe_pins(
                        pin TEXT PRIMARY KEY, owner TEXT NOT NULL, publication_id TEXT, closed INTEGER NOT NULL)""")
                async with first[1].transaction("init") as scope:
                    await first[2].initialize(scope, "w1")
                anchors = await fixture.open("anchors")
                for pin in ("committed", "aborted"):
                    await fixture.stager.stage(anchors, pin.encode())
                await activate(first, fixture, "A", 1)
                await acquire(first, fixture, "committed", "task")  # Discard successful reply.
                with self.assertRaisesRegex(RuntimeError, "interrupt before commit"):
                    await acquire(first, fixture, "aborted", "task", rollback=True)

            async with live_database(path, seed=False) as second:
                fixture = SqliteBlobFixture(second)
                await activate(second, fixture, "B", 2)
                with self.assertRaisesRegex(ValueError, "foreign or closed"):
                    await acquire(second, fixture, "committed", "other-task")
                publication, ref, holder = await acquire(second, fixture, "committed", "task")
                self.assertEqual(publication, "A")
                self.assertEqual((await acquire(second, fixture, "aborted", "task"))[0], "B")
                async with second[1].transaction("release") as scope:
                    async with fixture.catalog._scopes.bind(scope):
                        await fixture.holders.release(ref, holder)
                        await second[0].conn.execute("UPDATE probe_pins SET closed=1 WHERE pin=?", ("committed",))
                self.assertFalse(await fixture.holders.is_held(ref, holder))

            async with live_database(path, seed=False) as third:
                with self.assertRaisesRegex(ValueError, "foreign or closed"):
                    await acquire(third, SqliteBlobFixture(third), "committed", "task")
