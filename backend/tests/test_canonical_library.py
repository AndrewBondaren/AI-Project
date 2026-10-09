"""Canonical-defaults engine — plan canonical-defaults-engine.md step 2.

World scope: wire-overlay merge before validation. Global scope:
fill-missing over a persistence double on a real temp SQLite (real
insert-missing / conflict / rollback, no mocks).
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest
from dataclasses import dataclass
from unittest import IsolatedAsyncioTestCase

from app.application.canonicalLibrary import (
    CanonicalAttachPolicy,
    CanonicalAttachResult,
    CanonicalCachePolicy,
    CanonicalContractError,
    CanonicalEntry,
    CanonicalLibrarySpec,
    CanonicalScope,
    CanonicalSnapshot,
    CanonicalSourceError,
    CanonicalSpecError,
    SourceCacheMode,
    SqlCanonicalPersistence,
    canonical_merge,
    ensure_canonical,
)
from app.application.worldData.ids import LibraryKind, library_uid
from app.db.database import Database

_CANONICAL_ROWS = (
    {"system_x": "alpha", "display_name": "Alpha", "flag": True, "count": 5, "tags": ["a"]},
    {"system_x": "beta", "display_name": "Beta", "flag": False, "count": 0, "tags": []},
)


def _world_spec() -> CanonicalLibrarySpec:
    return CanonicalLibrarySpec(
        name="test.registry",
        scope=CanonicalScope.WORLD,
        attach_policy=CanonicalAttachPolicy.WORLD_WIRE_OVERLAY,
        identity_field="system_x",
        world_canonical_rows=lambda: [dict(row) for row in _CANONICAL_ROWS],
    )


class CanonicalMergeTests(unittest.TestCase):
    def test_absent_and_empty_registry_materialize_canonical(self):
        spec = _world_spec()
        for raw in (None, []):
            with self.subTest(raw=raw):
                self.assertEqual(canonical_merge(spec, raw), list(_CANONICAL_ROWS))

    def test_partial_registry_inherits_and_keeps_explicit_falsy(self):
        raw = [{"system_x": "alpha", "flag": False, "count": 0, "tags": []}]
        merged = canonical_merge(_world_spec(), raw)
        self.assertEqual(merged[0], {
            "system_x": "alpha",
            "display_name": "Alpha",  # inherited from canonical
            "flag": False,            # explicit false — a value, not absence
            "count": 0,
            "tags": [],
        })
        self.assertEqual(merged[1], _CANONICAL_ROWS[1])

    def test_n_plus_one_key_stays_unmerged_in_place(self):
        raw = [{"system_x": "gamma", "display_name": "Gamma"}]
        merged = canonical_merge(_world_spec(), raw)
        self.assertEqual(merged[0], raw[0])
        self.assertEqual(merged[1:], list(_CANONICAL_ROWS))

    def test_explicit_fields_win_over_canonical(self):
        raw = [{"system_x": "beta", "display_name": "Renamed", "flag": True}]
        merged = canonical_merge(_world_spec(), raw)
        self.assertEqual(merged[0]["display_name"], "Renamed")
        self.assertIs(merged[0]["flag"], True)
        self.assertEqual(merged[0]["count"], 0)

    def test_row_order_and_invalid_shapes_pass_through(self):
        raw = ["junk", {"other": 1}, {"system_x": "beta"}]
        merged = canonical_merge(_world_spec(), raw)
        self.assertEqual(merged[0], "junk")
        self.assertEqual(merged[1], {"other": 1})
        self.assertEqual(merged[2], _CANONICAL_ROWS[1])
        self.assertEqual(merged[3], _CANONICAL_ROWS[0])

    def test_non_list_raw_returned_unchanged_for_resolver(self):
        raw = {"system_x": "alpha"}
        self.assertIs(canonical_merge(_world_spec(), raw), raw)

    def test_merge_rejects_global_scope(self):
        spec = _global_spec(_StaticSource(CanonicalSnapshot()))
        with self.assertRaises(CanonicalSpecError):
            canonical_merge(spec, None)

    def test_spec_rejects_incoherent_declarations(self):
        with self.assertRaises(CanonicalSpecError):
            CanonicalLibrarySpec(
                name="bad",
                scope=CanonicalScope.WORLD,
                attach_policy=CanonicalAttachPolicy.GLOBAL_FILL_MISSING,
                identity_field="k",
                world_canonical_rows=list,
            )
        with self.assertRaises(CanonicalSpecError):
            CanonicalLibrarySpec(
                name="bad2",
                scope=CanonicalScope.WORLD,
                attach_policy=CanonicalAttachPolicy.WORLD_WIRE_OVERLAY,
                world_canonical_rows=list,  # identity_field missing
            )


# ---------------------------------------------------------------------------
# Global scope — persistence double over a real temp SQLite
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE canonical_test_templates (
    template_uid TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    source_file TEXT
);
"""

_PACK_UID = library_uid(LibraryKind.LIBRARY_PACKS, "engine.test.base")
_UID_ALPHA = library_uid(LibraryKind.STRUCTURE_TEMPLATES, "alpha", pack_uid=_PACK_UID)
_UID_BETA = library_uid(LibraryKind.STRUCTURE_TEMPLATES, "beta", pack_uid=_PACK_UID)
_UID_GAMMA = library_uid(LibraryKind.STRUCTURE_TEMPLATES, "gamma", pack_uid=_PACK_UID)


@dataclass
class TestTemplateRow:
    __table__ = "canonical_test_templates"
    __pk__ = "template_uid"

    template_uid: str
    body: str
    source_file: str | None = None


def _entry(uid: str, body: str) -> CanonicalEntry:
    return CanonicalEntry(
        uid=uid,
        body=TestTemplateRow(uid, body, f"engine.test.base/{body}.json"),
    )


def _snapshot(*uids: str, fingerprint: str | None = "v1") -> CanonicalSnapshot:
    return CanonicalSnapshot(
        entries=tuple(_entry(uid, f"body-{uid[:8]}") for uid in uids),
        fingerprint=fingerprint,
    )


class _StaticSource:
    def __init__(self, snapshot: CanonicalSnapshot | Exception) -> None:
        self._snapshot = snapshot
        self.calls = 0

    async def load(self, context) -> CanonicalSnapshot:
        self.calls += 1
        if isinstance(self._snapshot, Exception):
            raise self._snapshot
        return self._snapshot


def _global_spec(source, *, cache: CanonicalCachePolicy | None = None) -> CanonicalLibrarySpec:
    return CanonicalLibrarySpec(
        name="test.library",
        scope=CanonicalScope.GLOBAL,
        attach_policy=CanonicalAttachPolicy.GLOBAL_FILL_MISSING,
        cache=cache or CanonicalCachePolicy(),
        global_source=source,
        global_persistence=SqlCanonicalPersistence(model=TestTemplateRow),
    )


class EnsureCanonicalTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._db = Database(self._tmp.name)
        await self._db.connect()
        await self._db.main_conn.executescript(_DDL)
        await self._db.main_conn.commit()

    async def asyncTearDown(self) -> None:
        await self._db.disconnect()
        os.unlink(self._tmp.name)

    async def _rows(self) -> dict[str, tuple]:
        async with self._db.main_conn.execute(
            "SELECT template_uid, body, source_file FROM canonical_test_templates ORDER BY template_uid",
        ) as cur:
            return {row[0]: (row[1], row[2]) for row in await cur.fetchall()}

    async def _seed(self, *rows: TestTemplateRow) -> None:
        conn = self._db.main_conn
        for row in rows:
            await conn.execute(
                "INSERT INTO canonical_test_templates (template_uid, body, source_file) "
                "VALUES (?, ?, ?)",
                (row.template_uid, row.body, row.source_file),
            )
        await conn.commit()

    async def test_fill_missing_on_empty_library(self):
        # Non-empty table ≠ complete: a foreign row must not stop attach.
        await self._seed(TestTemplateRow("user-row", "user body", "user/x.json"))
        source = _StaticSource(_snapshot(_UID_ALPHA, _UID_BETA))
        result = await ensure_canonical(_global_spec(source), self._db)
        self.assertEqual(result.added, (_UID_ALPHA, _UID_BETA))
        self.assertEqual(result.existing, ())
        rows = await self._rows()
        self.assertEqual(set(rows), {_UID_ALPHA, _UID_BETA, "user-row"})
        self.assertEqual(rows[_UID_ALPHA][1], "engine.test.base/body-%s.json" % _UID_ALPHA[:8])
        self.assertEqual(rows["user-row"], ("user body", "user/x.json"))

    async def test_user_override_of_canonical_uid_is_preserved(self):
        await self._seed(TestTemplateRow(_UID_ALPHA, "USER OVERRIDE", "user/alpha.json"))
        result = await ensure_canonical(
            _global_spec(_StaticSource(_snapshot(_UID_ALPHA, _UID_BETA))), self._db,
        )
        self.assertEqual(result.added, (_UID_BETA,))
        self.assertEqual(result.existing, (_UID_ALPHA,))
        rows = await self._rows()
        self.assertEqual(rows[_UID_ALPHA], ("USER OVERRIDE", "user/alpha.json"))

    async def test_deleted_canonical_uid_is_restored(self):
        spec = _global_spec(_StaticSource(_snapshot(_UID_ALPHA, _UID_BETA, _UID_GAMMA)))
        await ensure_canonical(spec, self._db)
        await self._db.main_conn.execute(
            "DELETE FROM canonical_test_templates WHERE template_uid = ?", (_UID_BETA,),
        )
        await self._db.main_conn.commit()
        result = await ensure_canonical(spec, self._db)
        self.assertEqual(result.added, (_UID_BETA,))
        self.assertEqual(result.existing, (_UID_ALPHA, _UID_GAMMA))
        self.assertEqual(set(await self._rows()), {_UID_ALPHA, _UID_BETA, _UID_GAMMA})

    async def test_concurrent_attach_is_safe(self):
        await self._seed(TestTemplateRow(_UID_ALPHA, "USER OVERRIDE", "user/a.json"))
        spec = _global_spec(_StaticSource(_snapshot(_UID_ALPHA, _UID_BETA, _UID_GAMMA)))
        results = await asyncio.gather(
            ensure_canonical(spec, self._db),
            ensure_canonical(spec, self._db),
        )
        rows = await self._rows()
        self.assertEqual(set(rows), {_UID_ALPHA, _UID_BETA, _UID_GAMMA})
        self.assertEqual(rows[_UID_ALPHA], ("USER OVERRIDE", "user/a.json"))
        for result in results:
            self.assertEqual(set(result.added) | set(result.existing),
                             {_UID_ALPHA, _UID_BETA, _UID_GAMMA})

    async def test_source_error_writes_nothing_and_retry_works(self):
        spec = _global_spec(_StaticSource(ValueError("broken source")))
        with self.assertRaises(ValueError):
            await ensure_canonical(spec, self._db)
        self.assertEqual(await self._rows(), {})
        spec2 = _global_spec(_StaticSource(_snapshot(_UID_ALPHA)))
        result = await ensure_canonical(spec2, self._db)
        self.assertEqual(result.added, (_UID_ALPHA,))

    async def test_insert_error_rolls_back_and_retry_works(self):
        bad = CanonicalEntry(uid=_UID_GAMMA, body=TestTemplateRow(_UID_GAMMA, None))
        snapshot = CanonicalSnapshot(
            entries=(_entry(_UID_ALPHA, "x"), _entry(_UID_BETA, "y"), bad),
            fingerprint="v1",
        )
        spec = _global_spec(_StaticSource(snapshot))
        with self.assertRaises(sqlite3.IntegrityError):
            await ensure_canonical(spec, self._db)
        # Rollback: rows inserted before the failing one are gone.
        self.assertEqual(await self._rows(), {})
        result = await ensure_canonical(
            _global_spec(_StaticSource(_snapshot(_UID_ALPHA, _UID_BETA, _UID_GAMMA))),
            self._db,
        )
        self.assertEqual(result.added, (_UID_ALPHA, _UID_BETA, _UID_GAMMA))

    async def test_duplicate_canonical_uid_rejected_before_write(self):
        snapshot = CanonicalSnapshot(entries=(_entry(_UID_ALPHA, "x"), _entry(_UID_ALPHA, "y")))
        with self.assertRaises(CanonicalSourceError):
            await ensure_canonical(_global_spec(_StaticSource(snapshot)), self._db)
        self.assertEqual(await self._rows(), {})

    async def test_fingerprint_cache_mode_requires_fingerprint(self):
        spec = _global_spec(
            _StaticSource(_snapshot(_UID_ALPHA, fingerprint=None)),
            cache=CanonicalCachePolicy(source=SourceCacheMode.FINGERPRINT),
        )
        with self.assertRaises(CanonicalSourceError):
            await ensure_canonical(spec, self._db)
        self.assertEqual(await self._rows(), {})

    async def test_empty_source_is_noop(self):
        result = await ensure_canonical(
            _global_spec(_StaticSource(CanonicalSnapshot(entries=()))), self._db,
        )
        self.assertEqual(result.added, ())
        self.assertEqual(result.existing, ())
        self.assertEqual(await self._rows(), {})

    async def test_attach_participates_in_caller_transaction(self):
        spec = _global_spec(_StaticSource(_snapshot(_UID_ALPHA)))
        with self.assertRaises(RuntimeError):
            async with self._db.transaction_on(self._db.main_conn):
                await ensure_canonical(spec, self._db)
                raise RuntimeError("abort caller work")
        # No hidden commit: attach rows rolled back with the caller txn.
        self.assertEqual(await self._rows(), {})

    async def test_persistence_must_partition_declared_uids(self):
        class BadPersistence:
            async def insert_missing(self, snapshot, context):
                return CanonicalAttachResult(added=(), existing=("foreign",))

        spec = CanonicalLibrarySpec(
            name="test.badpersist",
            scope=CanonicalScope.GLOBAL,
            attach_policy=CanonicalAttachPolicy.GLOBAL_FILL_MISSING,
            global_source=_StaticSource(_snapshot(_UID_ALPHA)),
            global_persistence=BadPersistence(),
        )
        with self.assertRaises(CanonicalContractError):
            await ensure_canonical(spec, self._db)

    async def test_ensure_rejects_world_scope(self):
        with self.assertRaises(CanonicalSpecError):
            await ensure_canonical(_world_spec(), self._db)


if __name__ == "__main__":
    unittest.main()
