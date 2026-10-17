"""Topology scalar: POJO/row/wire sync and isolated initial-schema validation."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldColumnResolve import resolve_world_column
from app.application.jsonValidation.worldRow import terrain_scalars
from app.dataModel.terrain.worldTerrainScalars import WorldTerrainScalars, validate_world_row_terrain_columns
from app.dataModel.worldPack.wire.worldTopologyMode import WorldTopologyMode
from app.db.database import Database
from app.db.models.world import World


class WorldTopologyScalarTests(unittest.TestCase):
    def setUp(self):
        self.key = "world_topology_mode"
        self.default = WorldTerrainScalars.canonical_defaults().world_topology_mode
        self.world = World(world_uid="world-topology", name="Topology", created_at="2026-10-17")

    def test_missing_wire_and_runtime_row_default_to_wrapped(self):
        self.assertIs(self.default, WorldTopologyMode.WRAPPED)
        self.assertEqual(normalize_world({})[self.key], self.default.value)
        self.assertEqual(self.world.world_topology_mode, self.default.value)
        self.assertIs(terrain_scalars(SimpleNamespace()).world_topology_mode, self.default)
        validate_world_row_terrain_columns(World)

    def test_all_modes_round_trip_through_existing_world_slice(self):
        for mode in WorldTopologyMode:
            with self.subTest(mode=mode):
                result = resolve_world_column(self.key, mode.value, ResolveContext.for_import(validate_only=True))
                self.assertEqual(result, {self.key: mode.value})
                self.world.world_topology_mode = result[self.key]
                self.assertIs(terrain_scalars(self.world).world_topology_mode, mode)

    def test_supplied_invalid_mode_never_defaults(self):
        for value in (None, "unknown", 0, True):
            with self.subTest(value=value), self.assertRaises(ImportValidationError) as caught:
                normalize_world({self.key: value})
            self.assertTrue(any(issue.path[-1] == self.key for issue in caught.exception.errors))


class WorldTopologySchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_initial_schema_matches_model_and_uses_pojo_default(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Database(str(Path(directory) / "topology.sqlite"))
            await db.connect()
            try:
                await db.apply_migrations()
                await db.validate_schema([World])
                validate_world_row_terrain_columns(World)
                key = "world_topology_mode"
                default = WorldTerrainScalars.canonical_defaults().world_topology_mode.value
                async with db.conn.execute("PRAGMA table_info(worlds)") as cursor:
                    columns = {row["name"]: row for row in await cursor.fetchall()}
                self.assertEqual(columns[key]["notnull"], 1)
                self.assertEqual(columns[key]["dflt_value"], repr(default))
                await db.conn.execute(
                    "INSERT INTO worlds (world_uid, name, created_at) VALUES (?, ?, ?)",
                    ("world-sql-default", "SQL default", "2026-10-17"),
                )
                async with db.conn.execute("SELECT world_topology_mode FROM worlds") as cursor:
                    row = await cursor.fetchone()
                self.assertEqual(row[key], default)
            finally:
                await db.disconnect()


if __name__ == "__main__":
    unittest.main()
