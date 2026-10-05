"""P1: additive schema, POJO↔SQL roundtrip and database constraints on temp DB."""

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.database import Database
from app.db.mapper import from_row, model_columns, to_row
from app.db.models.transition import TransitionRow
from app.db.models.transitionSide import TransitionSideRow
from app.db.models.transitionProjection import (
    from_transition_rows, to_transition_rows, validate_transition_row_projection,
)
from app.db.models.world import World


class TransitionSchemaTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "transitions.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        self.registry = WorldTransitionTypeRegistry.canonical_engine()
        await self.db.conn.execute(
            "INSERT INTO worlds(world_uid, name, created_at) VALUES ('world', 'World', '2026-10-06')",
        )
        for uid in ("building", "host"):
            await self.db.conn.execute(
                "INSERT INTO named_locations(location_uid, world_uid, system_location_type, display_name, created_at) "
                "VALUES (?, 'world', 'building', ?, '2026-10-06')", (uid, uid),
            )
        await self.db.conn.execute(
            "INSERT INTO location_levels(level_uid, location_uid, z, display_name) "
            "VALUES ('level', 'building', 28, 'Floor')",
        )
        await self.db.conn.execute(
            "INSERT INTO connection_nodes(node_uid, world_uid, x, y, z, node_type, graph_level) "
            "VALUES ('node', 'world', 123, -45, 28, 'building_entrance', 'area')",
        )
        await self.db.conn.commit()

    async def asyncTearDown(self) -> None:
        await self.db.disconnect()
        self.tmp.cleanup()

    def aggregate(self, *, symbolic: bool = False, system_type: str = "main_entrance",
                  registry=None, **wire) -> Transition:
        registry = registry or self.registry
        key = registry.require(system_type)
        a = TransitionEndpoint() if symbolic else TransitionEndpoint(
            x=123, y=-45, z=28, host_location_uid="host", node_uid="node",
        )
        b = TransitionEndpoint(space="level", level_uid="level", x=124, y=-45, z=28)
        return Transition.model_validate({
            "transition_uid": transition_uid("world", key, a, b),
            "world_uid": "world", "system_transition_type": key,
            "a": a, "b": b,
            "side_b": {"owner_location_uid": "building", "entry_difficulty_override": 0},
            **wire,
        }, context={"transition_type_registry": registry})

    async def insert(self, row) -> None:
        columns, values = to_row(row)
        await self.db.conn.execute(
            f"INSERT INTO {row.__table__} ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})", values,
        )

    async def stored_aggregate(self, aggregate, *, registry=None):
        rows = to_transition_rows(aggregate)
        await self.insert(rows.transition)
        for side in rows.sides:
            await self.insert(side)
        async with self.db.conn.execute(
            "SELECT * FROM transitions WHERE transition_uid=?", (aggregate.transition_uid,),
        ) as cursor:
            row = from_row(TransitionRow, await cursor.fetchone())
        async with self.db.conn.execute(
            "SELECT * FROM transition_sides WHERE transition_uid=? ORDER BY side DESC",
            (aggregate.transition_uid,),
        ) as cursor:
            sides = [from_row(TransitionSideRow, item) for item in await cursor.fetchall()]
        return from_transition_rows(row, sides, registry=registry or self.registry)

    async def test_validate_schema_and_exact_model_columns(self) -> None:
        await self.db.validate_schema([World, TransitionRow, TransitionSideRow])
        for model in (World, TransitionRow, TransitionSideRow):
            async with self.db.conn.execute(f"PRAGMA table_info({model.__table__})") as cursor:
                rows = await cursor.fetchall()
            self.assertEqual({row["name"] for row in rows}, model_columns(model))
        self.assertIn("transition_type_registry", model_columns(World))

    async def test_projection_gate_rejects_unmapped_pojo_field(self) -> None:
        with patch.object(Transition, "model_fields", {**Transition.model_fields, "new_field": object()}):
            with self.assertRaisesRegex(RuntimeError, "new_field"):
                validate_transition_row_projection()

    async def test_roundtrip_preserves_geometry_sides_params_and_uid(self) -> None:
        aggregate = self.aggregate(
            system_type="staircase", type_params={"staircase_type": "spiral"},
            access_mechanic=["key", "lockpick"], origin="authored", is_active=False,
            display_name="Лестница", glossary_ref="stairs", tag_refs=["stone"],
            side_a={"is_accessible": False, "is_discovered": False,
                    "guard_level_override": 100, "display_name": "Улица"},
        )
        self.assertEqual(aggregate, await self.stored_aggregate(aggregate))
        async with self.db.conn.execute("PRAGMA foreign_key_check") as cursor:
            self.assertEqual(await cursor.fetchall(), [])

    async def test_symbolic_surface_and_empty_json_survive_sql(self) -> None:
        aggregate = self.aggregate(symbolic=True)
        restored = await self.stored_aggregate(aggregate)
        self.assertEqual(aggregate, restored)
        self.assertIsNone(restored.a.geometry)
        self.assertIsNone(restored.a.host_location_uid)
        self.assertIsNone(restored.side_a.owner_location_uid)
        async with self.db.conn.execute("SELECT a_x, a_y, a_z, access_mechanic, type_params, tag_refs FROM transitions") as cursor:
            row = await cursor.fetchone()
        self.assertEqual(tuple(row), (None, None, None, "[]", "{}", "[]"))

    async def test_custom_type_hydrates_with_caller_registry(self) -> None:
        registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "royal_entry", "display_name": "Вход", "behaves_as": "main_entrance"},
        ])
        aggregate = self.aggregate(system_type="royal_entry", registry=registry)
        self.assertEqual(aggregate, await self.stored_aggregate(aggregate, registry=registry))

    async def test_sql_rejects_partial_or_invalid_geometry_and_space(self) -> None:
        row = to_transition_rows(self.aggregate(symbolic=True)).transition
        for change in ({"a_x": 1}, {"a_x": 1, "a_y": 2},
                       {"a_x": 1.5, "a_y": 2, "a_z": 3},
                       {"a_space": "unknown"}, {"a_level_uid": "level"},
                       {"a_space": "level", "a_level_uid": "level"},
                       {"b_level_uid": None}, {"b_x": None}):
            with self.subTest(change=change), self.assertRaises(sqlite3.IntegrityError):
                await self.insert(replace(row, **change))

    async def test_sql_bool_origin_and_json_checks(self) -> None:
        row = to_transition_rows(self.aggregate()).transition
        columns, values = to_row(row)
        for field, invalid in (("is_active", 2), ("is_bidirectional", -1),
                               ("origin", "import"), ("system_transition_type", ""),
                               ("access_mechanic", "{}"), ("type_params", "[]"),
                               ("tag_refs", "invalid-json")):
            mutated = list(values)
            mutated[columns.index(field)] = invalid
            with self.subTest(field=field), self.assertRaises(sqlite3.IntegrityError):
                await self.db.conn.execute(
                    f"INSERT INTO transitions ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' for _ in columns)})", mutated,
                )

    async def test_foreign_keys_cover_world_levels_hosts_nodes_and_owners(self) -> None:
        rows = to_transition_rows(self.aggregate())
        for field in ("world_uid", "a_level_uid", "b_level_uid", "a_host_location_uid",
                      "b_host_location_uid", "a_node_uid", "b_node_uid"):
            change = {field: "missing"}
            if field == "a_level_uid":
                change["a_space"] = "level"
            with self.subTest(field=field), self.assertRaises(sqlite3.IntegrityError):
                await self.insert(replace(rows.transition, **change))
        await self.insert(rows.transition)
        with self.assertRaises(sqlite3.IntegrityError):
            await self.insert(replace(rows.sides[0], owner_location_uid="missing"))
        with self.assertRaises(sqlite3.IntegrityError):
            await self.insert(replace(rows.sides[0], transition_uid="missing"))

    async def test_composite_side_pk_ranges_flags_and_cascade(self) -> None:
        rows = to_transition_rows(self.aggregate())
        await self.insert(rows.transition)
        for change in ({"side": "c"}, {"entry_difficulty_override": -1},
                       {"entry_difficulty_override": 101}, {"guard_level_override": 1.5}):
            with self.subTest(change=change), self.assertRaises(sqlite3.IntegrityError):
                await self.insert(replace(rows.sides[0], **change))
        for field in ("is_discovered", "is_accessible"):
            columns, values = to_row(rows.sides[0])
            values[columns.index(field)] = 2
            with self.assertRaises(sqlite3.IntegrityError):
                await self.db.conn.execute(
                    f"INSERT INTO transition_sides ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' for _ in columns)})", values,
                )
        for side in rows.sides:
            await self.insert(side)
        with self.assertRaises(sqlite3.IntegrityError):
            await self.insert(rows.sides[0])
        await self.db.conn.execute("DELETE FROM transitions WHERE transition_uid=?", (rows.transition.transition_uid,))
        async with self.db.conn.execute("SELECT count(*) FROM transition_sides") as cursor:
            self.assertEqual((await cursor.fetchone())[0], 0)

    async def test_projection_rejects_incomplete_duplicate_or_mismatched_sides(self) -> None:
        rows = to_transition_rows(self.aggregate())
        for sides in ([], [rows.sides[0]], [rows.sides[0], rows.sides[0]],
                      [rows.sides[0], replace(rows.sides[1], transition_uid="other")],
                      [rows.sides[0], replace(rows.sides[1], side="unknown")]):
            with self.subTest(sides=sides), self.assertRaises(ValueError):
                from_transition_rows(rows.transition, sides, registry=self.registry)

    async def test_indexes_and_legacy_schema_remain(self) -> None:
        async with self.db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = {row[0] for row in await cursor.fetchall()}
        self.assertTrue({"transitions", "transition_sides", "location_passages", "location_entry_points"} <= tables)
        async with self.db.conn.execute("PRAGMA table_info(connection_nodes)") as cursor:
            columns = {row["name"] for row in await cursor.fetchall()}
        self.assertTrue({"portal_type", "portal_destinations", "portal_bidirectional"} <= columns)
        async with self.db.conn.execute("PRAGMA index_list(transitions)") as cursor:
            names = {row["name"] for row in await cursor.fetchall()}
        self.assertTrue({"idx_transitions_a_level", "idx_transitions_b_level",
                         "idx_transitions_a_node", "idx_transitions_b_node"} <= names)
        async with self.db.conn.execute("PRAGMA index_info(idx_transition_sides_owner)") as cursor:
            self.assertEqual([row["name"] for row in await cursor.fetchall()],
                             ["owner_location_uid", "side", "transition_uid"])


if __name__ == "__main__":
    unittest.main()
