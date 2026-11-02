from app.db.repositories.sqlite.snapshotCore.operations.terminalCodec import StoredTerminalCodec
from app.db.repositories.sqlite.snapshotCore.operations.publicationEvidence import SqlitePublicationEvidence
from app.db.repositories.sqlite.artifacts.operationArtifacts import SqliteOperationArtifacts
"""Real task/database/lifetime/read-only capability checks, without domain handlers."""

import asyncio
import ast
from pathlib import Path
import unittest
from app.application.publication.errors import PublicationInfrastructureError
from app.db.repositories.sqlite.snapshotCore.commitScope import SqlitePublicationCommitStore
from app.db.repositories.sqlite.snapshotCore.publications.worldPublicationStore import SqliteWorldPublicationStore
from app.db.repositories.sqlite.snapshotCore.publications.playerPublicationStore import SqlitePlayerPublicationStore
from app.db.repositories.sqlite.snapshotCore.history.snapshotHistoryStore import SqliteSnapshotHistoryStore
from app.db.repositories.sqlite.shared.access.scopedAccess import ScopedSqliteAccess
from app.db.repositories.sqlite.shared.capabilities.scopeRegistry import SqliteScopeRegistry
from app.db.repositories.sqlite.shared.transactions.transactionDriver import SqliteTransactionDriver
from app.db.repositories.sqlite.shared.capabilities.scopeBinding import SqliteCommitScopeBinding
from app.db.repositories.sqlite.snapshotCore.operations.operationStore import SqliteOperationStore
from tests.snapshotCore.support.fixtures import run_async, live_database, live_started
from app.db.repositories.sqlite.artifacts.access.artifactScope import SqliteArtifactScope
from app.db.models.snapshotCore.operationRows import PublicationOperationRow
from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind, ArtifactFormatRegistry
from app.dataModel.registryKey import RegistryKey
from unittest.mock import patch


class CommitCapabilityTests(unittest.TestCase):
    def test_explicit_di_shares_registry_and_rejects_cross_database_bindings(self):
        async def check():
            async with live_database() as first:
                async with live_database(first[0].path, seed=False) as second:
                    db, commits, world, players, history, operations = first
                    for adapter in (world, players, history, operations):
                        self.assertIs(adapter._access, world._access)
                        self.assertIs(adapter._registry, commits.registry)
                        self.assertIs(adapter._access.registry, commits.registry)
                    with self.assertRaises(ValueError):
                        SqlitePublicationCommitStore(db, second[1].registry, SqliteTransactionDriver())
                    for factory in (SqliteWorldPublicationStore, SqlitePlayerPublicationStore, SqliteSnapshotHistoryStore):
                        with self.assertRaises(ValueError):
                            factory(commits, second[2]._access)
                    with self.assertRaises(ValueError):
                        SqliteOperationStore(commits, second[2]._access, StoredTerminalCodec(),
                            operations._evidence, operations._artifacts)
                    # A second registry for the same Database is also a different authority.
                    with self.assertRaises(ValueError):
                        SqliteWorldPublicationStore(commits, ScopedSqliteAccess(SqliteScopeRegistry(db)))
        run_async(check())

    def test_driver_commands_require_an_owned_uow(self):
        async def check():
            async with live_database() as bundle:
                db, commits, *_ = bundle
                for command in (commits.driver.commit, commits.driver.rollback, commits.driver.close):
                    with self.assertRaises(PublicationInfrastructureError):
                        await command(db.main_conn)
                with self.assertRaises(PublicationInfrastructureError):
                    await commits.driver.begin(db.main_conn, write=True)
        run_async(check())

    def test_shared_import_direction_has_no_concrete_store_or_composition_dependency(self):
        root = Path(__file__).resolve().parents[3] / "app/db/repositories/sqlite/shared"
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    modules = (node.module or "",)
                elif isinstance(node, ast.Import):
                    modules = tuple(alias.name for alias in node.names)
                else:
                    continue
                for module in modules:
                    with self.subTest(path=path, module=module):
                        self.assertFalse(module.startswith((
                            "app.db.repositories.sqlite.snapshotCore",
                            "app.db.repositories.sqlite.artifacts", "app.core",
                        )))

    def test_scope_is_task_bound_expires_and_cannot_be_forged_or_nested(self):
        async def check():
            async with live_database() as bundle:
                db, commits, world, players, history, operations = bundle
                await live_started(bundle)
                async with commits.transaction("scope") as scope:
                    read = scope.read_scope
                    self.assertFalse(hasattr(scope, "connection"))
                    self.assertFalse(hasattr(scope, "commit"))
                    self.assertFalse(hasattr(scope, "__dict__"))
                    with self.assertRaises(PublicationInfrastructureError):
                        await asyncio.create_task(world.read("w1", scope=read))
                    with self.assertRaises(PublicationInfrastructureError):
                        await asyncio.create_task(commits.driver.commit(db.main_conn))
                    with self.assertRaises(PublicationInfrastructureError):
                        async with commits.transaction("nested"):
                            pass
                    with self.assertRaises(PublicationInfrastructureError):
                        SqliteCommitScopeBinding(commits.registry).assert_active()
                with self.assertRaises(PublicationInfrastructureError):
                    await world.read("w1", scope=read)
        run_async(check())

    def test_read_scope_cannot_write_and_foreign_database_scope_is_rejected(self):
        async def check():
            async with live_database() as first:
                await live_started(first)
                async with live_database(first[0].path, seed=False) as second:
                    with self.assertRaises(ValueError):
                        SqlitePublicationEvidence(first[1], second[2], first[3], first[2]._access)
                    async with first[1].transaction("scope") as scope:
                        expected = await first[2].read("w1", scope=scope.read_scope)
                        with self.assertRaises(PublicationInfrastructureError):
                            await first[2].compare_append(scope.read_scope, expected, expected)
                        with self.assertRaises(PublicationInfrastructureError):
                            await second[2].read("w1", scope=scope.read_scope)
        run_async(check())


class ArtifactScopeCapabilityTests(unittest.TestCase):
    def ref(self):
        return ArtifactRef(kind=ArtifactKind.BLOB,
            format_key=RegistryKey[ArtifactFormatRegistry]("test.blob"), format_version=1,
            content_hash="a" * 64, nbytes=0)

    def helper(self, bundle):
        return SqliteArtifactScope(bundle[1], bundle[2]._access)

    async def insert_operation(self, helper, scope, name):
        await helper.access.insert(scope, PublicationOperationRow(name, "w1", "snapshot_apply", "a" * 64))

    def test_guard_joins_reads_and_writes_without_creating_a_domain_operation(self):
        async def check():
            async with live_database() as bundle:
                helper = self.helper(bundle)
                self.assertIs(helper.commits, bundle[1])
                self.assertIs(helper.access, bundle[2]._access)
                async with helper.guard(self.ref()):
                    async with helper.transaction("actual-operation") as scope:
                        technical_id = helper.commits.registry.operation_id(scope)
                        self.assertNotEqual(technical_id, "actual-operation")
                        await self.insert_operation(helper, scope, "actual-operation")
                        async with helper.transaction("joined") as joined:
                            self.assertIs(joined, scope)
                        async with helper.read_scope() as read:
                            row = await helper.access.one(read, "SELECT count(*) AS n FROM publication_operations")
                            self.assertEqual(row["n"], 1)
                            with self.assertRaises(PublicationInfrastructureError):
                                await self.insert_operation(helper, read, "forbidden")
                async with helper.read_scope() as read:
                    self.assertIsNone(await helper.access.one(read,
                        "SELECT * FROM publication_operations WHERE operation_id=?", (technical_id,)))
                with self.assertRaises(PublicationInfrastructureError):
                    scope.assert_active()
                with self.assertRaises(PublicationInfrastructureError):
                    read.assert_active()
        run_async(check())

    def test_explicit_handoff_bind_borrows_scope_and_parent_owns_rollback(self):
        async def check():
            async with live_database() as bundle:
                helper = self.helper(bundle)
                with self.assertRaisesRegex(RuntimeError, "parent rollback"):
                    async with bundle[1].transaction("publication") as scope:
                        async with helper.bind(scope):
                            async with helper.transaction("publication") as joined:
                                self.assertIs(joined, scope)
                                self.assertEqual(helper.commits.registry.operation_id(joined), "publication")
                                await self.insert_operation(helper, joined, "publication")
                        # Exiting bind neither commits nor revokes the borrowed capability.
                        scope.assert_active()
                        with self.assertRaises(PublicationInfrastructureError):
                            async with helper.read_scope():
                                pass
                        async with helper.bind(scope):
                            async with helper.read_scope() as read:
                                self.assertIsNotNone(await helper.access.one(read,
                                    "SELECT * FROM publication_operations WHERE operation_id='publication'"))
                        raise RuntimeError("parent rollback")
                async with helper.read_scope() as read:
                    self.assertIsNone(await helper.access.one(read,
                        "SELECT * FROM publication_operations WHERE operation_id='publication'"))
                with self.assertRaises(PublicationInfrastructureError):
                    async with helper.bind(scope):
                        pass
        run_async(check())

    def test_foreign_forged_read_only_and_mismatched_registry_are_rejected(self):
        async def check():
            async with live_database() as first:
                async with live_database(first[0].path, seed=False) as second:
                    helper = self.helper(first)
                    with self.assertRaises(ValueError):
                        SqliteArtifactScope(first[1], second[2]._access)
                    with self.assertRaises(ValueError):
                        SqliteArtifactScope(first[1], ScopedSqliteAccess(SqliteScopeRegistry(first[0])))
                    async with second[1].transaction("foreign") as foreign:
                        with self.assertRaises(PublicationInfrastructureError):
                            async with helper.bind(foreign):
                                pass
                    with self.assertRaises(PublicationInfrastructureError):
                        async with helper.bind(SqliteCommitScopeBinding(first[1].registry)):
                            pass
                    async with first[1].transaction("read-only") as scope:
                        with self.assertRaises(PublicationInfrastructureError):
                            async with helper.bind(scope.read_scope):
                                pass
                    async with helper.read_scope():
                        async with helper.read_scope() as read:
                            read.assert_active()
                        with self.assertRaises(PublicationInfrastructureError):
                            async with helper.transaction("cannot-upgrade"):
                                pass
        run_async(check())

    def test_ambient_and_non_reentrant_scopes_are_rejected(self):
        async def check():
            async with live_database() as bundle:
                helper = self.helper(bundle)
                async with bundle[1].transaction("ambient") as ambient:
                    for context in (helper.guard(self.ref()), helper.transaction("nested"), helper.read_scope()):
                        with self.assertRaises(PublicationInfrastructureError):
                            async with context:
                                pass
                    async with helper.bind(ambient):
                        for context in (helper.guard(self.ref()), helper.bind(ambient)):
                            with self.assertRaises(PublicationInfrastructureError):
                                async with context:
                                    pass
                async with helper.guard(self.ref()):
                    async with helper.transaction("joined") as scope:
                        for context in (helper.guard(self.ref()), helper.bind(scope)):
                            with self.assertRaises(PublicationInfrastructureError):
                                async with context:
                                    pass
                # A raw Database UOW is also ambient, not an implicit join candidate.
                async with bundle[0].transaction():
                    with self.assertRaises(PublicationInfrastructureError):
                        async with helper.guard(self.ref()):
                            pass
        run_async(check())

    def test_inherited_child_binding_is_rejected_both_live_and_expired(self):
        async def check():
            async with live_database() as bundle:
                helper = self.helper(bundle)
                released = asyncio.Event()
                async def rejected():
                    for context in (helper.transaction("child"), helper.read_scope(), helper.guard(self.ref())):
                        with self.assertRaises(PublicationInfrastructureError):
                            async with context:
                                pass
                async def after_exit():
                    await released.wait()
                    await rejected()
                async with helper.guard(self.ref()):
                    await asyncio.create_task(rejected())
                    expired_child = asyncio.create_task(after_exit())
                    async with helper.transaction("parent") as scope:
                        async def bind_child():
                            with self.assertRaises(PublicationInfrastructureError):
                                async with helper.bind(scope):
                                    pass
                        await asyncio.create_task(bind_child())
                released.set()
                await expired_child
                async with helper.transaction("fresh") as scope:
                    scope.assert_active()
        run_async(check())

    def test_guard_rollback_and_cancellation_restore_binding(self):
        async def check():
            async with live_database() as bundle:
                helper = self.helper(bundle)
                for failure in (RuntimeError("rollback"), asyncio.CancelledError()):
                    with self.assertRaises(type(failure)):
                        async with helper.guard(self.ref()):
                            async with helper.transaction("rolled-back") as scope:
                                await self.insert_operation(helper, scope, "rolled-back")
                            raise failure
                    async with helper.read_scope() as read:
                        self.assertIsNone(await helper.access.one(read,
                            "SELECT * FROM publication_operations WHERE operation_id='rolled-back'"))
                invalid = self.ref().model_copy(update={"nbytes": -1})
                with self.assertRaises(ValueError):
                    async with helper.guard(invalid):
                        self.fail("invalid descriptor entered guard")
                async with helper.transaction("fresh") as scope:
                    scope.assert_active()
        run_async(check())

    def test_independent_connection_cannot_write_until_guard_exits(self):
        async def check():
            async with live_database() as first:
                async with live_database(first[0].path, seed=False) as second:
                    helper, other = self.helper(first), self.helper(second)
                    attempting, acquired = asyncio.Event(), asyncio.Event()
                    original = second[1].driver.begin
                    async def begin(conn, *, write):
                        attempting.set()
                        await original(conn, write=write)
                    async def contender():
                        async with other.transaction("second") as scope:
                            acquired.set()
                            await self.insert_operation(other, scope, "second")
                    with patch.object(second[1].driver, "begin", begin):
                        async with helper.guard(self.ref()):
                            pending = asyncio.create_task(contender())
                            await asyncio.wait_for(attempting.wait(), 2)
                            # SQLite worker has received BEGIN IMMEDIATE on another connection.
                            await asyncio.sleep(0.05)
                            self.assertFalse(acquired.is_set())
                        await asyncio.wait_for(pending, 3)
                    self.assertTrue(acquired.is_set())
                    async with helper.read_scope() as read:
                        self.assertIsNotNone(await helper.access.one(read,
                            "SELECT * FROM publication_operations WHERE operation_id='second'"))
        run_async(check())
