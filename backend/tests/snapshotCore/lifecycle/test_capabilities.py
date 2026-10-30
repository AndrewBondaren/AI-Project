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
                        SqliteOperationStore(commits, world, players, second[2]._access)
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
                        SqliteOperationStore(first[1], second[2], first[3], first[2]._access)
                    async with first[1].transaction("scope") as scope:
                        expected = await first[2].read("w1", scope=scope.read_scope)
                        with self.assertRaises(PublicationInfrastructureError):
                            await first[2].compare_append(scope.read_scope, expected, expected)
                        with self.assertRaises(PublicationInfrastructureError):
                            await second[2].read("w1", scope=scope.read_scope)
        run_async(check())
