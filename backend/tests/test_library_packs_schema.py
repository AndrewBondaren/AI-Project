"""Library pack catalog — plan library-packs-model.md step B-2 (TZ §3, §6).

Runs against a real temp SQLite migrated by ``0001_initial.sql`` — no
copied DDL: schema validation, same names across packs, single owner,
FK/cascade, concurrent attach, rollback/retry, source_file preservation.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest
from unittest import IsolatedAsyncioTestCase

from app.application.canonicalLibrary import (
    CanonicalEntry,
    CanonicalSnapshot,
    SqlCanonicalPersistence,
)
from app.ids import LibraryKind, library_uid
from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
from app.db.database import Database
from app.db.models.buildingTemplate import BuildingTemplateRow
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.db.models.structureTemplate import StructureTemplateRow
from app.db.models.world import World
from app.db.repositories.sqlite.libraryPackDependencyRepository import (
    SqliteLibraryPackDependencyRepository,
)
from app.db.repositories.sqlite.libraryPackMemberRepository import (
    SqliteLibraryPackMemberRepository,
)
from app.db.repositories.sqlite.libraryPackRepository import (
    SqliteLibraryPackRepository,
)
from app.db.repositories.sqlite.reliefTemplateRepository import (
    SqliteReliefTemplateRepository,
)
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository

_STRUCT = LibraryKind.STRUCTURE_TEMPLATES
_PACKS = LibraryKind.LIBRARY_PACKS


def _pack(system_name: str, *, owner: str | None = None,
          source: str | None = None) -> LibraryPackRow:
    return LibraryPackRow(
        pack_uid=library_uid(_PACKS, system_name),
        system_name=system_name,
        pack_name=system_name.rsplit(".", 1)[-1],
        display_name=system_name,
        owner_world_uid=owner,
        source_pack_uid=source,
    )


def _member(pack: LibraryPackRow, local_uid: str, *,
            kind: LibraryKind = _STRUCT,
            source_template_uid: str | None = None) -> LibraryPackMemberRow:
    return LibraryPackMemberRow(
        template_uid=library_uid(kind, local_uid, pack_uid=pack.pack_uid),
        pack_uid=pack.pack_uid,
        library_kind=kind.value,
        local_uid=local_uid,
        source_template_uid=source_template_uid,
    )


class LibraryPackSchemaTests(IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = Database(self._tmp.name)
        await self.db.connect()
        await self.db.apply_migrations()
        for uid in ("world-a", "world-b"):
            await self.db.conn.execute(
                "INSERT INTO worlds(world_uid, name, created_at) VALUES (?, ?, ?)",
                (uid, uid, "2026-10-09"),
            )
        await self.db.conn.commit()
        self.packs = SqliteLibraryPackRepository(self.db)
        self.members = SqliteLibraryPackMemberRepository(self.db)
        self.deps = SqliteLibraryPackDependencyRepository(self.db)

    async def asyncTearDown(self) -> None:
        await self.db.disconnect()
        os.unlink(self._tmp.name)

    # ----------------------------------------------------------- schema

    async def test_schema_validation(self):
        await self.db.validate_schema([
            World, BuildingTemplateRow, ReliefTemplateRow, StructureTemplateRow,
            LibraryPackRow, LibraryPackMemberRow, LibraryPackDependencyRow,
        ])

    async def test_world_library_pins_column_roundtrip(self):
        repo = SqliteWorldRepository(self.db)
        world = World(
            world_uid="world-pins", name="pins", created_at="2026-10-09",
            library_pins=[
                LibraryPinEntry(
                    library_kind=LibraryKind.RELIEF_TEMPLATES,
                    local_uid="smoke_003",
                ).model_dump(mode="json"),
                LibraryPinEntry(
                    library_kind=LibraryKind.STRUCTURE_TEMPLATES,
                    local_uid="inn_small",
                ).model_dump(mode="json"),
            ],
        )
        await repo.create(world)
        stored = await repo.get_by_id("world-pins")
        self.assertEqual(stored.library_pins, world.library_pins)
        empty = await repo.get_by_id("world-a")
        self.assertEqual(empty.library_pins, [])

    async def test_system_name_no_longer_globally_unique(self):
        for i in ("one", "two"):
            await self.db.conn.execute(
                "INSERT INTO building_templates "
                "(template_uid, system_name, display_name, structure_type, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"bt-{i}", "shared_name", i, "house", "{}"),
            )
            await self.db.conn.execute(
                "INSERT INTO relief_templates "
                "(template_uid, system_name, display_name, context, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"rt-{i}", "shared_name", i, "any", "{}"),
            )
        await self.db.conn.commit()
        for table in ("building_templates", "relief_templates"):
            async with self.db.conn.execute(f"PRAGMA index_list({table})") as cur:
                indexes = await cur.fetchall()
            unique_indexes = [
                idx for idx in indexes
                if idx[2] and "system_name" in {
                    c[1] for c in await self._index_columns(table, idx[1])
                }
            ]
            self.assertEqual(unique_indexes, [], f"{table} still has UNIQUE index on system_name")

    async def _index_columns(self, table: str, index_name: str):
        async with self.db.conn.execute(f"PRAGMA index_info({index_name})") as cur:
            return [(row[0], row[2]) for row in await cur.fetchall()]

    # ----------------------------------------------------------- ownership / uniqueness

    async def test_same_local_uid_in_different_packs_allowed(self):
        pack_a, pack_b = _pack("engine.a"), _pack("engine.b")
        await self.packs.insert_missing([pack_a, pack_b])
        count = await self.members.insert_missing([
            _member(pack_a, "shared"), _member(pack_b, "shared"),
        ])
        self.assertEqual(count, 2)
        self.assertIsNotNone(
            await self.members.find_by_local_uid(pack_a.pack_uid, _STRUCT.value, "shared"),
        )
        self.assertIsNotNone(
            await self.members.find_by_local_uid(pack_b.pack_uid, _STRUCT.value, "shared"),
        )

    async def test_same_local_uid_within_one_pack_rejected(self):
        pack = _pack("engine.dup")
        await self.packs.insert(pack)
        await self.members.insert(_member(pack, "dup"))
        with self.assertRaises(sqlite3.IntegrityError):
            await self.members.insert(
                LibraryPackMemberRow(
                    template_uid="other-uid",
                    pack_uid=pack.pack_uid,
                    library_kind=_STRUCT.value,
                    local_uid="dup",
                ),
            )

    async def test_member_single_owner_by_pk(self):
        pack_a, pack_b = _pack("engine.a2"), _pack("engine.b2")
        await self.packs.insert_missing([pack_a, pack_b])
        member = _member(pack_a, "m")
        await self.members.insert(member)
        # Another pack cannot claim the same template_uid as its membership.
        with self.assertRaises(sqlite3.IntegrityError):
            await self.members.insert(
                LibraryPackMemberRow(
                    template_uid=member.template_uid,
                    pack_uid=pack_b.pack_uid,
                    library_kind=_STRUCT.value,
                    local_uid="m-copy",
                ),
            )
        self.assertEqual((await self.members.get_by_uid(member.template_uid)).pack_uid,
                         pack_a.pack_uid)

    async def test_pack_system_name_globally_unique(self):
        await self.packs.insert(_pack("engine.unique"))
        with self.assertRaises(sqlite3.IntegrityError):
            await self.packs.insert(
                LibraryPackRow(
                    pack_uid="different-uid",
                    system_name="engine.unique",
                    pack_name="unique",
                    display_name="x",
                ),
            )

    # ----------------------------------------------------------- FK / provenance

    async def test_fk_violations(self):
        ghost_member = LibraryPackMemberRow(
            template_uid="ghost", pack_uid="no-such-pack",
            library_kind=_STRUCT.value, local_uid="g",
        )
        with self.assertRaises(sqlite3.IntegrityError):
            await self.members.insert(ghost_member)
        with self.assertRaises(sqlite3.IntegrityError):
            await self.deps.insert(LibraryPackDependencyRow("no-such-pack", "req"))
        with self.assertRaises(sqlite3.IntegrityError):
            await self.packs.insert(
                LibraryPackRow(
                    pack_uid="bad-owner", system_name="engine.bad",
                    pack_name="bad", display_name="bad",
                    owner_world_uid="no-such-world",
                ),
            )

    async def test_dangling_required_and_source_uids_allowed(self):
        pack = _pack("engine.deps", source="deleted-source-pack")
        await self.packs.insert(pack)
        await self.deps.insert(LibraryPackDependencyRow(pack.pack_uid, "not-yet-imported"))
        member = _member(pack, "m", source_template_uid="deleted-member")
        await self.members.insert(member)
        self.assertEqual(await self.deps.required_uids(pack.pack_uid), {"not-yet-imported"})
        self.assertEqual(
            (await self.packs.get_by_uid(pack.pack_uid)).source_pack_uid,
            "deleted-source-pack",
        )
        self.assertEqual(
            (await self.members.get_by_uid(member.template_uid)).source_template_uid,
            "deleted-member",
        )

    async def test_source_pack_delete_leaves_dangling_provenance(self):
        source = _pack("engine.source")
        instance = _pack("world.instance", owner="world-a", source=source.pack_uid)
        await self.packs.insert_missing([source, instance])
        await self.packs.delete(source.pack_uid)
        stored = await self.packs.get_by_uid(instance.pack_uid)
        # "source deleted" stays computable: stored uid survives, lookup resolves to None.
        self.assertEqual(stored.source_pack_uid, source.pack_uid)
        self.assertIsNone(await self.packs.get_by_uid(stored.source_pack_uid))

    async def test_world_owned_cascade(self):
        engine_pack = _pack("engine.stays")
        world_pack = _pack("world.owned", owner="world-a")
        await self.packs.insert_missing([engine_pack, world_pack])
        member = _member(world_pack, "m")
        await self.members.insert(member)
        await self.deps.insert(LibraryPackDependencyRow(world_pack.pack_uid, engine_pack.pack_uid))
        await self.db.conn.execute("DELETE FROM worlds WHERE world_uid = ?", ("world-a",))
        await self.db.conn.commit()
        self.assertIsNone(await self.packs.get_by_uid(world_pack.pack_uid))
        self.assertIsNone(await self.members.get_by_uid(member.template_uid))
        self.assertEqual(await self.deps.list_for_pack(world_pack.pack_uid), [])
        self.assertIsNotNone(await self.packs.get_by_uid(engine_pack.pack_uid))
        self.assertEqual(await self.packs.list_world_owned("world-a"), [])

    async def test_list_by_owner_and_engine_scopes(self):
        packs = [_pack("engine.e1"), _pack("engine.e2"),
                 _pack("world.w1", owner="world-a"), _pack("world.w2", owner="world-b")]
        await self.packs.insert_missing(packs)
        self.assertEqual(
            {p.system_name for p in await self.packs.list_engine()},
            {"engine.e1", "engine.e2"},
        )
        self.assertEqual(
            {p.system_name for p in await self.packs.list_world_owned("world-a")},
            {"world.w1"},
        )

    # ----------------------------------------------------------- insert-missing contract

    async def test_insert_missing_never_replaces_membership(self):
        pack_a, pack_b = _pack("engine.keep"), _pack("engine.keep2")
        await self.packs.insert_missing([pack_a, pack_b])
        member = _member(pack_a, "m")
        await self.members.insert(member)
        rebind = LibraryPackMemberRow(
            template_uid=member.template_uid, pack_uid=pack_b.pack_uid,
            library_kind=_STRUCT.value, local_uid="m-elsewhere",
        )
        added = await self.members.insert_missing([rebind, _member(pack_b, "new")])
        self.assertEqual(added, 1)
        stored = await self.members.get_by_uid(member.template_uid)
        self.assertEqual(stored.pack_uid, pack_a.pack_uid)
        self.assertEqual(stored.local_uid, "m")

    async def test_insert_missing_local_uid_conflict_rolls_back_batch(self):
        pack = _pack("engine.conflict")
        await self.packs.insert(pack)
        await self.members.insert(_member(pack, "taken"))
        good, clashing = (
            _member(pack, "fresh"),
            LibraryPackMemberRow(
                template_uid="clash-uid", pack_uid=pack.pack_uid,
                library_kind=_STRUCT.value, local_uid="taken",
            ),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            await self.members.insert_missing([good, clashing])
        # Rollback: the valid member of the failed batch is not persisted.
        self.assertIsNone(await self.members.get_by_uid(good.template_uid))
        added = await self.members.insert_missing([good])
        self.assertEqual(added, 1)

    async def test_concurrent_insert_missing(self):
        pack_a, pack_b = _pack("engine.c1"), _pack("engine.c2")
        await self.packs.insert_missing([pack_a, pack_b])
        shared = _member(pack_a, "shared-uid-member")
        # Cross-connection attach: the writer serializes at the DB level
        # (WAL + busy timeout); ON CONFLICT DO NOTHING covers the overlap.
        db2 = Database(self._tmp.name)
        await db2.connect()
        try:
            members2 = SqliteLibraryPackMemberRepository(db2)
            counts = await asyncio.gather(
                self.members.insert_missing([shared, _member(pack_a, "a-only")]),
                members2.insert_missing([shared, _member(pack_b, "b-only")]),
            )
        finally:
            await db2.disconnect()
        self.assertEqual(sorted(counts), [1, 2])
        self.assertEqual(len(await self.members.list_by_packs(
            [pack_a.pack_uid, pack_b.pack_uid])), 3)
        self.assertEqual(
            (await self.members.get_by_uid(shared.template_uid)).pack_uid, pack_a.pack_uid,
        )

    async def test_existing_uids_is_the_completeness_primitive(self):
        pack = _pack("engine.full")
        await self.packs.insert(pack)
        member = _member(pack, "only")
        await self.members.insert(member)
        declared = {member.template_uid, "missing-uid"}
        existing = await self.members.existing_uids(sorted(declared))
        self.assertEqual(existing, {member.template_uid})
        self.assertEqual(declared - existing, {"missing-uid"})

    # ----------------------------------------------------------- transactions

    async def test_insert_missing_participates_in_caller_transaction(self):
        pack = _pack("engine.txn")
        await self.packs.insert(pack)
        with self.assertRaises(RuntimeError):
            async with self.db.transaction_on(self.db.main_conn):
                await self.members.insert_missing([_member(pack, "inside")])
                raise RuntimeError("caller abort")
        self.assertIsNone(await self.members.get_by_uid(
            library_uid(_STRUCT, "inside", pack_uid=pack.pack_uid)))

    async def test_body_and_member_share_one_transaction(self):
        pack = _pack("engine.atomic")
        await self.packs.insert(pack)
        member = _member(pack, "atomic-m")
        body = StructureTemplateRow(
            template_uid=member.template_uid, display_name="body", data={},
        )
        with self.assertRaises(RuntimeError):
            async with self.db.transaction_on(self.db.main_conn):
                await self.db.conn.execute(
                    "INSERT INTO structure_templates "
                    "(template_uid, display_name, version, data) VALUES (?, ?, ?, ?)",
                    (body.template_uid, body.display_name, body.version, "{}"),
                )
                await self.members.insert(member)
                raise RuntimeError("abort after both writes")
        # Neither body nor membership survived the rollback.
        self.assertIsNone(await self.members.get_by_uid(member.template_uid))
        async with self.db.conn.execute(
            "SELECT 1 FROM structure_templates WHERE template_uid = ?",
            (member.template_uid,),
        ) as cur:
            self.assertIsNone(await cur.fetchone())

    async def test_source_file_preserved_by_fill_missing(self):
        pack = _pack("engine.src")
        await self.packs.insert(pack)
        member = _member(pack, "m", source_template_uid=None)
        await self.db.conn.execute(
            "INSERT INTO structure_templates "
            "(template_uid, display_name, version, data, source_file) "
            "VALUES (?, ?, ?, ?, ?)",
            (member.template_uid, "user copy", "9.9", "{}", "user/custom.json"),
        )
        await self.db.conn.commit()
        persistence = SqlCanonicalPersistence(model=StructureTemplateRow)
        snapshot = CanonicalSnapshot(entries=(
            CanonicalEntry(
                uid=member.template_uid,
                body=StructureTemplateRow(
                    template_uid=member.template_uid, display_name="canonical",
                    data={}, source_file="engine.src/m.json",
                ),
            ),
        ))
        result = await persistence.insert_missing(snapshot, self.db)
        self.assertEqual(result.existing, (member.template_uid,))
        async with self.db.conn.execute(
            "SELECT display_name, source_file FROM structure_templates WHERE template_uid = ?",
            (member.template_uid,),
        ) as cur:
            row = await cur.fetchone()
        self.assertEqual((row["display_name"], row["source_file"]),
                         ("user copy", "user/custom.json"))

    # ----------------------------------------------------------- lookup primitives

    async def test_find_instance_and_list_for_world(self):
        source = _pack("engine.src2")
        inst_a = _pack("world.inst", owner="world-a", source=source.pack_uid)
        authored = _pack("world.authored", owner="world-a")
        other_world = _pack("world.other", owner="world-b")
        await self.packs.insert_missing([source, inst_a, authored, other_world])
        members = [
            _member(inst_a, "inst-m", source_template_uid="src-member"),
            _member(authored, "auth-m"),
            _member(other_world, "other-m"),
        ]
        await self.members.insert_missing(members)
        found = await self.packs.find_instance("world-a", source.pack_uid)
        self.assertEqual(found.pack_uid, inst_a.pack_uid)
        self.assertIsNone(await self.packs.find_instance("world-b", source.pack_uid))
        world_members = await self.members.list_for_world("world-a")
        self.assertEqual({m.local_uid for m in world_members}, {"inst-m", "auth-m"})

    async def test_dependencies_primitives(self):
        pack, required = _pack("engine.d"), _pack("engine.req")
        await self.packs.insert_missing([pack, required])
        dep = LibraryPackDependencyRow(pack.pack_uid, required.pack_uid)
        self.assertEqual(await self.deps.insert_missing([dep]), 1)
        self.assertEqual(await self.deps.insert_missing([dep]), 0)
        self.assertEqual(await self.deps.required_uids(pack.pack_uid), {required.pack_uid})
        self.assertEqual(len(await self.deps.list_for_packs([pack.pack_uid])), 1)
        self.assertEqual(
            [d.pack_uid for d in await self.deps.list_dependents(required.pack_uid)],
            [pack.pack_uid],
        )
        self.assertEqual(await self.deps.delete_for_pack(pack.pack_uid), 1)
        self.assertEqual(await self.deps.list_for_pack(pack.pack_uid), [])
        self.assertEqual(await self.deps.list_dependents(required.pack_uid), [])

    async def test_update_metadata_never_rewrites_identity(self):
        pack = _pack("engine.meta", source="src-keep")
        await self.packs.insert(pack)
        mutated = LibraryPackRow(
            pack_uid=pack.pack_uid, system_name="forged", pack_name="renamed",
            display_name="Renamed", version="2.0",
            owner_world_uid="world-a", source_pack_uid="forged",
        )
        await self.packs.update_metadata(mutated)
        stored = await self.packs.get_by_uid(pack.pack_uid)
        self.assertEqual(
            (stored.pack_name, stored.display_name, stored.version),
            ("renamed", "Renamed", "2.0"),
        )
        self.assertEqual(stored.system_name, "engine.meta")
        self.assertIsNone(stored.owner_world_uid)
        self.assertEqual(stored.source_pack_uid, "src-keep")

    async def test_save_and_upsert_are_not_mutation_paths(self):
        pack = _pack("engine.immut")
        await self.packs.insert(pack)
        member = _member(pack, "m")
        dep = LibraryPackDependencyRow(pack.pack_uid, "req")
        with self.assertRaises(NotImplementedError):
            await self.members.save(member)
        with self.assertRaises(NotImplementedError):
            await self.members.upsert(member)
        with self.assertRaises(NotImplementedError):
            await self.deps.save(dep)
        with self.assertRaises(NotImplementedError):
            await self.deps.upsert(dep)
        with self.assertRaises(NotImplementedError):
            await self.packs.upsert(pack)

    async def test_pack_save_degrades_to_metadata_update(self):
        pack = _pack("engine.savex", source="src-keep")
        await self.packs.insert(pack)
        forged = LibraryPackRow(
            pack_uid=pack.pack_uid, system_name="forged", pack_name="via-save",
            display_name="Via Save", version="3.0",
            owner_world_uid="world-a", source_pack_uid="forged",
        )
        # BaseRepository.save is reachable on the concrete class; identity
        # and provenance are excluded by __update_exclude__ — only mutable
        # metadata lands, same contract as update_metadata.
        await self.packs.save(forged)
        stored = await self.packs.get_by_uid(pack.pack_uid)
        self.assertEqual(
            (stored.pack_name, stored.display_name, stored.version),
            ("via-save", "Via Save", "3.0"),
        )
        self.assertEqual(stored.system_name, "engine.savex")
        self.assertIsNone(stored.owner_world_uid)
        self.assertEqual(stored.source_pack_uid, "src-keep")

    async def test_relief_get_by_system_name_ambiguous_is_error(self):
        repo = SqliteReliefTemplateRepository(self.db)
        for uid in ("r-1", "r-2"):
            await repo.upsert(ReliefTemplateRow(
                template_uid=uid, system_name="same", display_name=uid,
                context="any", data={},
            ))
        with self.assertRaises(RuntimeError):
            await repo.get_by_system_name("same")
        self.assertIsNone(await repo.get_by_system_name("missing"))
        await repo.upsert(ReliefTemplateRow(
            template_uid="r-3", system_name="unique", display_name="u",
            context="any", data={},
        ))
        self.assertEqual((await repo.get_by_system_name("unique")).template_uid, "r-3")


if __name__ == "__main__":
    unittest.main()
