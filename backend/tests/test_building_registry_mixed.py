"""D9: ``worlds.building_template_registry`` — heterogeneous column.

tz_building_generator §5.2, plan ``.cursor/plans/building-registry-mixed-column.md``.
The column stores two row kinds discriminated by ``system_template_uid``:
uid pointers (``BuildingTemplateRegistryEntry``) and embedded plot
layouts (``PlotLayoutTemplate`` world overrides).

RED until step 3: the declared ``WorldBuildingTemplateRegistry`` POJO is
pointer-only, so public write paths reject mixed columns — ``worlds.update``
422s on ANY field of such a world, ``import_from_json`` fails, and
``_ensure_registry`` cannot read the column to append a pointer.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from fastapi import HTTPException

from app.application.jsonValidation.worldRow import world_building_layout_overrides
from app.core.container import Container
from app.db.database import Database
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

_POINTER = {
    "system_template_uid": "11111111-2222-3333-4444-555555555555",
    "display_template_name": "Library Tavern",
    "imported_at": "2026-06-03T00:00:00Z",
}
_LAYOUT = {
    "system_name": "plot_override_x",
    "display_name": "Plot Override X",
    "plot_type": "dwelling",
}
_GARBAGE = {"garbage": True}
_HYBRID = {
    "system_template_uid": "66666666-7777-8888-9999-000000000000",
    "display_template_name": "Hybrid Row",
    "system_name": "hybrid_layout_keys",
    "display_name": "Hybrid Layout Keys",
    "plot_type": "dwelling",
}


def _world_fixture() -> dict:
    return json.loads(
        (FIXTURES / "world_defaults_test.json").read_text(encoding="utf-8")
    )["world"]


class MixedColumnServiceTests(IsolatedAsyncioTestCase):
    """Public write paths over a real migrated world row."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(str(Path(self.tmp.name) / "mixed.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.worlds = self.container.world_service()
        self.world_repo = SqliteWorldRepository(self.db)
        self.buildings = self.container.building_template_library_service()

    async def _world_with_registry(self, rows: list[dict]) -> str:
        """World written through the service, then the column planted via the
        repository — the same direct-write path pack adapters/interim packing
        use to produce heterogeneous rows today."""
        world = _world_fixture()
        result = await self.worlds.import_from_json(world)
        self.assertEqual(result.failed, 0, result.errors)
        row = await self.worlds.get_by_id(world["world_uid"])
        row.building_template_registry = list(rows)
        await self.world_repo.update(row)
        return world["world_uid"]

    def _kinds(self, world) -> list[str]:
        return [
            "pointer" if "system_template_uid" in row else "layout"
            for row in world.building_template_registry
        ]

    async def test_update_preserves_mixed_registry(self):
        """Unrelated-field update must not reject or lose layout rows."""
        uid = await self._world_with_registry([_POINTER, _LAYOUT])
        await self.worlds.update(uid, {"name": "Renamed"})
        world = await self.worlds.get_by_id(uid)
        self.assertEqual(world.name, "Renamed")
        self.assertEqual(self._kinds(world), ["pointer", "layout"])
        self.assertEqual(
            world.building_template_registry[1]["system_name"],
            _LAYOUT["system_name"],
        )

    async def test_import_from_json_accepts_mixed_registry(self):
        world = _world_fixture()
        world["building_template_registry"] = [_POINTER, _LAYOUT]
        result = await self.worlds.import_from_json(world)
        self.assertEqual(result.failed, 0, result.errors)
        stored = await self.worlds.get_by_id(world["world_uid"])
        self.assertEqual(self._kinds(stored), ["pointer", "layout"])

    async def test_import_bodies_appends_pointer_keeping_layout_rows(self):
        """``_ensure_registry`` reads the whole column; layout rows are not
        pointer entries and must survive the append (replace-semantics patch)."""
        uid = await self._world_with_registry([_LAYOUT])
        result = await self.buildings.import_bodies_into_world(
            uid, [{"system_name": "bt_new", "display_name": "BT New"}]
        )
        self.assertEqual(result.failed, 0, result.errors)
        world = await self.worlds.get_by_id(uid)
        kinds = self._kinds(world)
        self.assertEqual(kinds.count("layout"), 1)
        self.assertEqual(kinds.count("pointer"), 1)
        self.assertEqual(kinds[0], "layout")


class MixedColumnOverridesTests(unittest.TestCase):
    """Row-kind semantics — guards that hold before and after the union."""

    def test_layout_overrides_read_only_layout_rows(self):
        world = SimpleNamespace(
            world_uid="w1",
            building_template_registry=[_POINTER, _LAYOUT],
        )
        layouts = world_building_layout_overrides(world)
        self.assertEqual(
            [str(layout.system_name) for layout in layouts],
            [_LAYOUT["system_name"]],
        )

    def test_pointer_only_world_has_no_overrides(self):
        world = SimpleNamespace(
            world_uid="w1", building_template_registry=[_POINTER]
        )
        self.assertEqual(world_building_layout_overrides(world), [])

    def test_hybrid_row_counts_as_pointer(self):
        """Both keys → pointer (same rule as worldRow / pack remap)."""
        world = SimpleNamespace(
            world_uid="w1", building_template_registry=[_HYBRID]
        )
        self.assertEqual(world_building_layout_overrides(world), [])


class MixedColumnRejectTests(IsolatedAsyncioTestCase):
    """A row of neither kind is a validation error, never a silent drop."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(str(Path(self.tmp.name) / "reject.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.worlds = self.container.world_service()

    async def test_garbage_row_rejected_with_index(self):
        world = _world_fixture()
        world["building_template_registry"] = [_POINTER, _GARBAGE]
        # Domain-error contract after worlddata-http-decoupling; HTTPException
        # while the CRUD adapter still maps in-service.
        with self.assertRaises(HTTPException) as caught:
            await self.worlds.import_from_json(world)
        detail = str(caught.exception.detail)
        self.assertIn("building_template_registry", detail)
        self.assertIn("1", detail)  # row index in the error path


if __name__ == "__main__":
    unittest.main()
