"""R43: relief grade SQL catalog persist — bulk txn, prior by uid, heartbeat."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.persistReliefGrades import persist_relief_grades
from app.core.generationLogging import generation_world_log
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem
from app.db.database import Database
from app.db.models.reliefGradeInstance import ReliefGradeInstanceRow
from app.db.models.reliefGradeSystem import ReliefGradeSystemRow
from app.db.repositories.sqlite.reliefGradeRepository import SqliteReliefGradeRepository

_WORLD = "w-grade-persist"
_DDL = """
CREATE TABLE IF NOT EXISTS relief_grade_systems (
    grade_system_uid TEXT PRIMARY KEY,
    world_uid TEXT NOT NULL,
    grade_instance_uids TEXT NOT NULL,
    created_at TEXT NOT NULL,
    owner_uid TEXT,
    display_name TEXT
);
CREATE TABLE IF NOT EXISTS relief_grade_instances (
    grade_uid TEXT PRIMARY KEY,
    world_uid TEXT NOT NULL,
    kind TEXT NOT NULL,
    height_cells INTEGER NOT NULL,
    length_cells INTEGER NOT NULL,
    cell_refs TEXT NOT NULL,
    created_at TEXT NOT NULL,
    angle_deg REAL,
    facing TEXT,
    earthen_canal INTEGER NOT NULL DEFAULT 0,
    structure_refs TEXT,
    structure_canal TEXT,
    template_uid TEXT,
    owner_uid TEXT,
    site_id TEXT,
    grade_system_uid TEXT
);
"""


def _sheer(uid: str, cells: list[tuple[int, int]], *, world: str = _WORLD) -> ReliefGradeInstance:
    return ReliefGradeInstance(
        grade_uid=uid,
        world_uid=world,
        kind=ReliefSideKind.SHEER,
        height_cells=2,
        length_cells=1,
        cell_refs=cells,
    )


def _system(*uids: str, world: str = _WORLD) -> ReliefGradeSystem:
    return ReliefGradeSystem(
        grade_system_uid="sys-" + "-".join(uids),
        world_uid=world,
        grade_instance_uids=list(uids),
    )


class _TrackingRepo:
    def __init__(self) -> None:
        self.list_world_calls = 0
        self.list_uid_calls: list[list[str]] = []
        self.session_enters = 0
        self.upsert_instance_calls = 0
        self.bulk_instances: list[ReliefGradeInstanceRow] = []
        self.bulk_systems: list[ReliefGradeSystemRow] = []

    @asynccontextmanager
    async def persist_session(self):
        self.session_enters += 1
        yield

    async def upsert_instance(self, row: ReliefGradeInstanceRow) -> None:
        self.upsert_instance_calls += 1

    async def upsert_system(self, row: ReliefGradeSystemRow) -> None:
        return

    async def upsert_instances(self, rows) -> None:
        self.bulk_instances.extend(rows)

    async def upsert_systems(self, rows) -> None:
        self.bulk_systems.extend(rows)

    async def list_instances_by_uids(self, world_uid: str, uids) -> list[ReliefGradeInstanceRow]:
        self.list_uid_calls.append(list(uids))
        return []

    async def list_instances_for_world(self, world_uid: str) -> list[ReliefGradeInstanceRow]:
        self.list_world_calls += 1
        return []

    async def delete_instances_for_world(self, world_uid: str) -> None:
        return


class PersistReliefGradesCallerTest(IsolatedAsyncioTestCase):
    async def test_prior_uses_uids_not_full_world_list(self) -> None:
        repo = _TrackingRepo()
        instances = [_sheer(f"g-{i}", [(i, 0)]) for i in range(10)]
        n = await persist_relief_grades(
            repo,
            world_uid=_WORLD,
            instances=instances,
            replace_world=False,
        )
        self.assertEqual(n, 10)
        self.assertEqual(repo.list_world_calls, 0)
        self.assertEqual(len(repo.list_uid_calls), 1)
        self.assertEqual(repo.list_uid_calls[0], [f"g-{i}" for i in range(10)])
        self.assertEqual(repo.session_enters, 1)
        self.assertEqual(len(repo.bulk_instances), 10)
        self.assertEqual(repo.upsert_instance_calls, 0)

    async def test_empty_bag_skips_prior_read(self) -> None:
        repo = _TrackingRepo()
        n = await persist_relief_grades(
            repo,
            world_uid=_WORLD,
            instances=[],
            replace_world=False,
        )
        self.assertEqual(n, 0)
        self.assertEqual(repo.list_world_calls, 0)
        self.assertEqual(repo.list_uid_calls, [])
        self.assertEqual(repo.session_enters, 0)


class SqliteReliefGradePersistTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._db = Database(self._tmp.name)
        await self._db.connect()
        await self._db.conn.executescript(_DDL)
        await self._db.conn.commit()
        self._repo = SqliteReliefGradeRepository(self._db)
        self._counts = {"txn": 0, "commit": 0}
        self._install_commit_counter()

    async def asyncTearDown(self) -> None:
        await self._db.disconnect()
        os.unlink(self._tmp.name)

    def _install_commit_counter(self) -> None:
        conn = self._db.conn
        orig_commit = conn.commit
        orig_txn = self._db.transaction_on

        async def commit() -> None:
            self._counts["commit"] += 1
            await orig_commit()

        @asynccontextmanager
        async def transaction_on(conn_arg):
            self._counts["txn"] += 1
            async with orig_txn(conn_arg):
                yield conn_arg

        conn.commit = commit  # type: ignore[method-assign]
        self._db.transaction_on = transaction_on  # type: ignore[method-assign]

    async def test_bulk_persist_one_commit(self) -> None:
        instances = [_sheer(f"g-{i}", [(i, 0)]) for i in range(20)]
        systems = [_system("g-0", "g-1"), _system("g-2", "g-3")]
        self._counts["txn"] = 0
        self._counts["commit"] = 0
        n = await persist_relief_grades(
            self._repo,
            world_uid=_WORLD,
            instances=instances,
            systems=systems,
            replace_world=False,
        )
        self.assertEqual(n, 20)
        self.assertEqual(self._counts["txn"], 1)
        self.assertEqual(self._counts["commit"], 0)
        loaded = await self._repo.list_instances_for_world(_WORLD)
        self.assertEqual(len(loaded), 20)
        sys_rows = await self._db.conn.execute(
            "SELECT COUNT(*) FROM relief_grade_systems WHERE world_uid = ?",
            [_WORLD],
        )
        row = await sys_rows.fetchone()
        self.assertEqual(row[0], 2)

    async def test_per_row_upsert_commits_without_session(self) -> None:
        inst = _sheer("g-patch", [(0, 0)])
        from app.application.worldData.persistReliefGrades import instance_to_row

        self._counts["txn"] = 0
        self._counts["commit"] = 0
        await self._repo.upsert_instance(instance_to_row(inst, created_at="2026-01-01T00:00:00Z"))
        self.assertEqual(self._counts["commit"], 1)
        self.assertEqual(self._counts["txn"], 0)

    async def test_merge_prior_cell_refs(self) -> None:
        first = _sheer("g-shared", [(0, 0)])
        await persist_relief_grades(
            self._repo, world_uid=_WORLD, instances=[first], replace_world=False,
        )
        again = _sheer("g-shared", [(1, 0)])
        await persist_relief_grades(
            self._repo, world_uid=_WORLD, instances=[again], replace_world=False,
        )
        rows = await self._repo.list_instances_by_uids(_WORLD, ["g-shared"])
        self.assertEqual(len(rows), 1)
        refs = {(int(p[0]), int(p[1])) for p in rows[0].cell_refs}
        self.assertEqual(refs, {(0, 0), (1, 0)})

    async def test_persist_does_not_list_full_world(self) -> None:
        extra = _sheer("g-other", [(99, 99)])
        await persist_relief_grades(
            self._repo, world_uid=_WORLD, instances=[extra], replace_world=False,
        )
        world_lists = []
        orig = self._repo.list_instances_for_world

        async def spy(world_uid: str):
            world_lists.append(world_uid)
            return await orig(world_uid)

        self._repo.list_instances_for_world = spy  # type: ignore[method-assign]
        bag = [_sheer(f"g-new-{i}", [(i, 1)]) for i in range(10)]
        await persist_relief_grades(
            self._repo, world_uid=_WORLD, instances=bag, replace_world=False,
        )
        self.assertEqual(world_lists, [])
        loaded = await self._repo.list_instances_by_uids(
            _WORLD, [inst.grade_uid for inst in bag],
        )
        self.assertEqual(len(loaded), 10)

    async def test_heartbeat_in_detailed_generation_log(self) -> None:
        root = Path(tempfile.mkdtemp())
        logging.getLogger().setLevel(logging.DEBUG)
        pack_log = logging.getLogger("app.application.worldData.pack.bake.packBakeLog")
        pack_log.setLevel(logging.DEBUG)
        instances = [_sheer(f"g-{i}", [(i, 0)]) for i in range(3)]
        systems = [_system("g-0", "g-1")]
        with generation_world_log(_WORLD, mode="detailed", root=root) as run_path:
            await persist_relief_grades(
                self._repo,
                world_uid=_WORLD,
                instances=instances,
                systems=systems,
                replace_world=False,
            )
        latest = root / _WORLD / "bake-detailed-latest.log"
        self.assertTrue(latest.is_file())
        self.assertTrue(run_path.is_file())
        text = latest.read_text(encoding="utf-8")
        msgs = [
            json.loads(line)["msg"]
            for line in text.splitlines()
            if line.strip()
        ]
        self.assertTrue(any("relief_grades persist start" in m for m in msgs))
        self.assertTrue(any("relief_grades persist progress" in m for m in msgs))
        self.assertTrue(any("relief_grades persist done" in m for m in msgs))
        self.assertTrue(any("elapsed_ms=" in m for m in msgs))
        self.assertTrue(any("instances=3" in m for m in msgs))


if __name__ == "__main__":
    unittest.main()
