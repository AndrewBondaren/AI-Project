"""P4 application CRUD through DI and real temporary SQLite storage."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.application.jsonValidation.worldRow import transition_types
from app.core.container import Container
from app.dataModel.locations.transitions.transition import Transition
from app.db.database import Database
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class TransitionCrudTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "crud.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        await self.db.conn.execute("INSERT INTO worlds(world_uid,name,created_at) VALUES ('w','W','2026-10-06')")
        await self.db.conn.execute(
            "INSERT INTO named_locations(location_uid,world_uid,system_location_type,display_name,created_at) "
            "VALUES ('house','w','building','House','2026-10-06')")
        await self.db.conn.commit()
        self.container = Container(None, self.db)
        self.world = World("w", "W", "2026-10-06")
        self.locations = {"house": NamedLocation("house", "w", "House", "building", "2026-10-06")}
        self.service = self.scoped(self.world)

    def scoped(self, world):
        return self.container.transition_service(world, levels={}, locations=self.locations, nodes={})

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    def transition(self, uid="t", **wire):
        return Transition.model_validate({
            "transition_uid": uid, "world_uid": "w", "system_transition_type": "main_entrance",
            "source": {}, "destination": {},
            "destination_side": {"owner_location_uid": "house"}, **wire,
        })

    async def test_crud_and_state_flags_are_data(self):
        original = self.transition(is_active=False, destination_side={
            "owner_location_uid": "house", "is_discovered": False, "is_accessible": False})
        self.assertEqual(await self.service.create(original), original)
        self.assertEqual(await self.service.read("t"), original)
        updated = await self.service.update("t", {"destination_side": {"entry_difficulty_override": 100}})
        self.assertFalse(updated.is_active)
        self.assertFalse(updated.destination_side.is_discovered)
        self.assertFalse(updated.destination_side.is_accessible)
        self.assertEqual(updated.destination_side.entry_difficulty_override, 100)
        self.assertEqual(await self.service.entries_of("w", "house"), [updated])
        self.assertTrue(await self.service.delete("t"))
        self.assertIsNone(await self.service.read("t"))
        self.assertFalse(await self.service.delete("t"))
        async with self.db.conn.execute("SELECT count(*) FROM transition_sides") as cursor:
            self.assertEqual((await cursor.fetchone())[0], 0)

    async def test_invalid_patches_and_references_leave_aggregate_unchanged(self):
        original = await self.service.create(self.transition())
        for patch in (
            {"destination_side": {"entry_difficulty_override": -1}},
            {"source_side": {"guard_level_override": 101}},
            {"destination_side": {"owner_location_uid": "missing"}},
            {"source": {"node_uid": "missing"}},
            {"destination": {"space": "level", "level_uid": "missing", "x": 0, "y": 0, "z": 0}},
            {"system_transition_type": "portal"},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                await self.service.update("t", patch)
            self.assertEqual(await self.service.read("t"), original)
        invalid = original.model_copy(update={"world_uid": "other"})
        with self.assertRaises(ValueError):
            await self.service.create(invalid)

    async def test_sql_failure_and_caller_transaction_rollback(self):
        original = await self.service.create(self.transition())
        await self.db.conn.execute(
            "CREATE TRIGGER fail_side BEFORE UPDATE ON transition_sides "
            "WHEN NEW.side='destination' BEGIN SELECT RAISE(ABORT, 'failure'); END")
        await self.db.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            await self.service.update("t", {"display_name": "Changed"})
        self.assertEqual(await self.service.read("t"), original)
        with self.assertRaisesRegex(RuntimeError, "caller"):
            async with self.db.transaction():
                await self.service.create(self.transition("rollback"))
                raise RuntimeError("caller")
        self.assertIsNone(await self.service.read("rollback"))

    async def test_entries_use_custom_behavior_and_destination_owner(self):
        custom_world = World("w", "W", "2026-10-06", transition_type_registry=[
            {"system_type": "secret", "display_name": "Secret", "behaves_as": "hidden_entrance"},
            {"system_type": "internal", "display_name": "Internal", "behaves_as": "door"},
        ])
        service = self.scoped(custom_world)
        def custom(uid, key, **wire):
            return Transition.model_validate({
                **self.transition(uid).model_dump(mode="json"), "system_transition_type": key, **wire,
            }, context={"transition_type_registry": transition_types(custom_world)})
        secret = await service.create(custom("secret", "secret"))
        await service.create(custom("door", "internal"))
        await service.create(custom("source_only", "secret", source_side={"owner_location_uid": "house"}, destination_side={}))
        self.assertEqual(await service.entries_of("w", "house"), [secret])
        # Fresh DI scopes cannot leak custom keys into the canonical world snapshot.
        with self.assertRaises(ValueError):
            await self.service.create(secret.model_copy(update={"transition_uid": "canonical"}))
        with self.assertRaises(ValueError):
            await service.entries_of("other", "house")

    async def test_level_and_node_queries_delegate_and_missing_update(self):
        await self.service.create(self.transition())
        self.assertEqual(await self.service.for_level("w", "missing"), [])
        self.assertEqual(await self.service.for_node("w", "missing"), [])
        with self.assertRaises(KeyError):
            await self.service.update("missing", {"display_name": "Changed"})
