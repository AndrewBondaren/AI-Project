"""W2-4: pure world preparation and strict prepared persistence in caller UOW."""

from copy import deepcopy
from unittest.mock import patch

from test_library_packs_4b import _ServiceCase, _RELIEF
import test_library_write_plan as plan_fixture
from app.application.jsonValidation.types import ImportValidationError
from app.application.worldData.libraryPacks.errors import LibraryPackConflictError
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteRequest
from app.application.worldData.libraryPacks.writeRetentionPlanner import WriteRetentionPlanner
from app.application.worldData.worldColumnWrite import invalidated_world_tables


class LibraryWorldColumnWriteTests(_ServiceCase):
    item = plan_fixture.LibraryWritePlanTests.item
    imported = plan_fixture.LibraryWritePlanTests.imported

    async def asyncSetUp(self):
        await super().asyncSetUp()
        world = await self._world("w1")
        world.terrain_registry = []
        world.material_registry = [42]
        await self.worlds.update(world)
        self.writer = self.container.library_write_service()
        self.raw = self.imported(body={
            "system_name": "meadow", "display_name": "Meadow", "context": "open_land",
            "conditions": [{"terrain": "forest", "cases": [
                {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0}]}],
        })
        self.request = LibraryWriteRequest(items=(self.item("raw", imported=True),))

    async def prepare(self):
        return await self.writer.prepare(self.request, imports={"raw": self.raw})

    async def trace(self):
        statements = []
        await self.db.main_conn.set_trace_callback(statements.append)
        self.addAsyncCleanup(self.db.main_conn.set_trace_callback, None)
        return statements

    def writes(self, statements):
        return [sql for sql in statements if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    async def test_prepared_values_survive_apply_without_resolve_or_neighbor_repair(self):
        async with self.db.transaction():
            trace = await self.trace()
            plan = await self.prepare()
            self.assertEqual(self.writes(trace), [])
            self.assertEqual(len(plan.worlds), 1)
            write = plan.worlds[0]
            self.assertEqual({change.path[0] for change in write.changes}, {"terrain_registry"})
            self.assertEqual(invalidated_world_tables(
                {"terrain_registry": write.before.terrain_registry},
                {"terrain_registry": write.after.terrain_registry}), frozenset())
            current = await self.worlds.get_by_id("w1")
            current.name = "Changed after prepare"
            await self.worlds.update(current)
            trace.clear()
            with patch("app.application.jsonValidation.worldColumnResolve.resolve_world_column",
                       side_effect=AssertionError("executor must not resolve")), \
                 patch("app.application.jsonValidation.resolve.resolve_model",
                       side_effect=AssertionError("executor must not normalize")):
                await self.writer.apply_prepared(plan)
            saved = await self.worlds.get_by_id("w1")
            self.assertEqual(saved.terrain_registry, write.after.terrain_registry)
            self.assertEqual(saved.material_registry, [42])
            self.assertEqual(saved.name, "Changed after prepare")
            world_updates = [sql for sql in trace if sql.lstrip().upper().startswith('UPDATE "WORLDS"')
                             or sql.lstrip().upper().startswith("UPDATE WORLDS")]
            self.assertEqual(len(world_updates), 1)

    async def test_invalid_final_column_rejects_before_any_sql_writes(self):
        world = await self.worlds.get_by_id("w1")
        world.terrain_registry = [42]
        await self.worlds.update(world)
        trace = await self.trace()
        with self.assertRaises(ImportValidationError) as caught:
            await self.writer.execute(self.request, imports={"raw": self.raw})
        self.assertEqual(caught.exception.errors[0].path[:2], ("terrain_registry", 0))
        self.assertEqual(self.writes(trace), [])
        self.assertIsNone(await self.packs.get_by_uid(self.raw.pack.pack_uid))
        self.assertEqual((await self.worlds.get_by_id("w1")).terrain_registry, [42])

    async def test_stale_authored_column_rejects_before_body_or_catalog_writes(self):
        async with self.db.transaction():
            plan = await self.prepare()
            current = await self.worlds.get_by_id("w1")
            current.terrain_registry = [{"system_terrain": "plains"}]
            await self.worlds.update(current)
            trace = await self.trace()
            with self.assertRaises(LibraryPackConflictError):
                await self.writer.apply_prepared(plan)
            self.assertEqual(self.writes(trace), [])
            self.assertIsNone(await self.packs.get_by_uid(self.raw.pack.pack_uid))

    async def test_deleted_world_is_conflict_before_any_writes(self):
        async with self.db.transaction():
            plan = await self.prepare()
            await self.worlds.delete("w1")
            trace = await self.trace()
            with self.assertRaises(LibraryPackConflictError):
                await self.writer.apply_prepared(plan)
            self.assertEqual(self.writes(trace), [])

    async def test_world_and_library_writes_roll_back_with_caller(self):
        before = await self.worlds.get_by_id("w1")
        with self.assertRaisesRegex(ValueError, "caller failed"):
            async with self.db.transaction():
                plan = await self.prepare()
                await self.writer.apply_prepared(plan)
                self.assertNotEqual((await self.worlds.get_by_id("w1")).terrain_registry, before.terrain_registry)
                raise ValueError("caller failed")
        self.assertEqual(await self.worlds.get_by_id("w1"), before)
        self.assertIsNone(await self.packs.get_by_uid(self.raw.pack.pack_uid))
        self.assertIsNone(await self.relief_rows.get_by_uid(self.raw.members[0].member.template_uid))

    async def test_projection_rejects_non_facade_columns_and_validates_pins(self):
        world = await self.worlds.get_by_id("w1")
        before = deepcopy(world)
        adapter = self.service._scope.adapters[_RELIEF]
        def projection(column, raw):
            def prepare(current, uid_map, members):
                result = deepcopy(current)
                setattr(result, column, raw)
                return result
            return prepare
        planner = WriteRetentionPlanner({_RELIEF: adapter})
        with patch.object(adapter, "prepare_world_refs", side_effect=projection("terrain_pack_hash", "hash")):
            with self.assertRaises(ImportValidationError) as caught:
                planner._world(world, (), {})
            self.assertEqual(caught.exception.errors[0].code, "NOT_WRITABLE_WORLD_COLUMN")
        with patch.object(adapter, "prepare_world_refs", side_effect=projection("library_pins", [
                {"library_kind": _RELIEF.value, "template_uid": "member", "extra": "ignored"}])):
            projected = planner._world(world, (), {})
            self.assertEqual(projected.library_pins, [{"library_kind": _RELIEF.value, "template_uid": "member"}])
        with patch.object(adapter, "prepare_world_refs", side_effect=projection("library_pins", [
                {"library_kind": _RELIEF.value, "template_uid": "valid"},
                {"library_kind": _RELIEF.value, "template_uid": None}])):
            with self.assertRaises(ImportValidationError) as caught:
                planner._world(world, (), {})
            self.assertEqual(caught.exception.errors[0].path, ("library_pins", 1, "template_uid"))
        self.assertEqual(world, before)
