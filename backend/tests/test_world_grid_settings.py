"""G-1: one strict size contract across facade, direct import and scoped writes."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import httpx
from fastapi import FastAPI
from pydantic import ValidationError

from test_library_packs_4b import _ServiceCase
from app.api.deps import get_container
from app.api.errorMapping import install_error_handlers
from app.api.routes.worlds import router
from app.application.jsonValidation import grid_settings
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldColumnResolve import resolve_world_column
from app.application.jsonValidation.worldSlices import slice_for_pojo
from app.application.worldData.registries.worldColumnWrite import apply_world_column
from app.application.worldData.registries.worldService import WorldService
from app.dataModel.worldPack.wire.mapCellSize import FINE_CELLS_PER_MAP_CELL_DEFAULT
from app.dataModel.worldPack.meta.worldGridSettings import (
    WorldGridSettings, grid_settings_wire_from_mapping, validate_world_row_grid_columns,
)
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository


KEY = "fine_cells_per_map_cell"
INVALID = (True, False, None, 1000.0, 1000.5, "1000", -1000, 0, 999, 1500)
VALID = (1000, 2000, 3000)
WIRE = {"world_uid": "w1", "name": "World", "created_at": "2026-10-16"}


class GridSettingsTests(unittest.TestCase):
    def assert_issue(self, error):
        issue = error.errors[0]
        self.assertEqual(issue.path, (KEY,))
        self.assertEqual(issue.schema_id, WorldGridSettings.SCHEMA_ID)
        self.assertTrue(issue.code)

    def test_same_valid_values_across_pojo_facade_direct_import_and_scoped(self):
        for value in VALID:
            with self.subTest(value=value):
                self.assertEqual(WorldGridSettings(**{KEY: value}).fine_cells_per_map_cell, value)
                for partial in (False, True):
                    self.assertEqual(normalize_world({KEY: value}, partial=partial)[KEY], value)
                self.assertEqual(WorldService.prepare_import({**WIRE, KEY: value}).fine_cells_per_map_cell, value)
                self.assertEqual(resolve_world_column(KEY, value, ResolveContext()), {KEY: value})

    def test_same_invalid_values_preserve_diagnostics_and_never_mutate(self):
        for value in INVALID:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    WorldGridSettings(**{KEY: value})
                for partial in (False, True):
                    with self.assertRaises(ImportValidationError) as caught:
                        normalize_world({KEY: value}, partial=partial)
                    self.assert_issue(caught.exception)
                wire = {**WIRE, KEY: value}
                before_wire = deepcopy(wire)
                with self.assertRaises(ImportValidationError) as caught:
                    WorldService.prepare_import(wire)
                self.assert_issue(caught.exception)
                self.assertEqual(wire, before_wire)
                world = World(**WIRE)
                before = deepcopy(world)
                with self.assertRaises(ImportValidationError) as caught:
                    apply_world_column(world, KEY, value, ResolveContext())
                self.assert_issue(caught.exception)
                self.assertEqual(world, before)

    def test_default_missing_patch_and_explicit_null_projection(self):
        self.assertEqual(WorldGridSettings.canonical_defaults().fine_cells_per_map_cell,
                         FINE_CELLS_PER_MAP_CELL_DEFAULT)
        self.assertEqual(World(**WIRE).fine_cells_per_map_cell, FINE_CELLS_PER_MAP_CELL_DEFAULT)
        self.assertEqual(normalize_world({})[KEY], FINE_CELLS_PER_MAP_CELL_DEFAULT)
        self.assertNotIn(KEY, normalize_world({}, partial=True))
        self.assertEqual(WorldService.prepare_import(WIRE).fine_cells_per_map_cell,
                         FINE_CELLS_PER_MAP_CELL_DEFAULT)
        self.assertEqual(grid_settings_wire_from_mapping({KEY: None}), {KEY: None})
        self.assertEqual(grid_settings(SimpleNamespace()).fine_cells_per_map_cell,
                         FINE_CELLS_PER_MAP_CELL_DEFAULT)

    def test_removed_map_cell_size_key_is_rejected(self):
        for partial in (False, True):
            with self.assertRaises(ImportValidationError):
                normalize_world({"map_cell_size_m": 2000}, partial=partial)
            with self.assertRaises(ImportValidationError):
                normalize_world({KEY: 3000, "map_cell_size_m": None}, partial=partial)
        with self.assertRaises(ImportValidationError):
            resolve_world_column("map_cell_size_m", 2000, ResolveContext())

    def test_scoped_change_isolated_and_reports_only_actual_invalidation(self):
        world = World(**WIRE, material_registry=[42], g=-1)
        before = deepcopy(world)
        self.assertEqual(apply_world_column(world, KEY, 1000, ResolveContext()), frozenset())
        self.assertEqual(apply_world_column(world, KEY, 2000, ResolveContext()), frozenset({"map_cells"}))
        before.fine_cells_per_map_cell = 2000
        self.assertEqual(world, before)
        self.assertEqual(apply_world_column(world, KEY, 2000, ResolveContext()), frozenset())

    def test_startup_guard_and_runtime_accessor_use_registered_contract(self):
        validate_world_row_grid_columns(World)
        with self.assertRaises(RuntimeError):
            validate_world_row_grid_columns(type("MissingGrid", (), {"__dataclass_fields__": {}}))
        self.assertTrue(slice_for_pojo(WorldGridSettings).facade)
        self.assertEqual(grid_settings(World(**WIRE, fine_cells_per_map_cell=2000)).fine_cells_per_map_cell, 2000)


class GridSettingsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_import_and_master_update_reject_before_save(self):
        repo = AsyncMock(spec=IWorldRepository)
        service = WorldService(repo)
        repo.get_by_id.return_value = World(**WIRE)
        for value in INVALID:
            for operation in ("create", "import_from_json", "update"):
                with self.subTest(value=value, operation=operation):
                    with self.assertRaises(ImportValidationError):
                        if operation == "update":
                            await service.update("w1", {KEY: value})
                        else:
                            await getattr(service, operation)({**WIRE, KEY: value})
        repo.create.assert_not_awaited()
        repo.upsert.assert_not_awaited()
        repo.update.assert_not_awaited()

    async def test_create_import_and_master_update_accept_same_values(self):
        for value in VALID:
            with self.subTest(value=value):
                repo = AsyncMock(spec=IWorldRepository)
                repo.get_by_id.return_value = World(**WIRE)
                service = WorldService(repo)
                self.assertEqual((await service.create({**WIRE, KEY: value})).fine_cells_per_map_cell, value)
                self.assertEqual((await service.import_from_json({**WIRE, KEY: value})).succeeded, 1)
                result = await service.update("w1", {KEY: value, "force": True})
                self.assertEqual(result.world.fine_cells_per_map_cell, value)
                self.assertEqual(result.map_cells_invalidated, value != 1000)


class GridSettingsBoundaryTests(_ServiceCase):
    async def test_bundle_preview_and_apply_reject_size_without_writes(self):
        bundle = self.container.world_bundle_service()
        for value in INVALID:
            with self.subTest(value=value):
                data = {"world": {**WIRE, KEY: value}}
                before = (self.db.conn.total_changes, self.db.bootstrap_conn.total_changes)
                report = await bundle.import_bundle(data, validate_only=True)
                self.assertFalse(report.valid)
                self.assertEqual(report.issues[0].path, (KEY,))
                self.assertEqual(report.issues[0].schema_id, WorldGridSettings.SCHEMA_ID)
                with self.assertRaises(ImportValidationError) as caught:
                    await bundle.import_bundle(data)
                self.assertEqual(tuple(caught.exception.errors), report.issues)
                self.assertEqual((self.db.conn.total_changes, self.db.bootstrap_conn.total_changes), before)
        self.assertEqual(await self.worlds.get_all(), [])

    async def test_bundle_copy_import_preserves_valid_size(self):
        results, rolled_back = await self.container.world_bundle_service().import_bundle(
            {"world": {**WIRE, KEY: 2000}})
        self.assertFalse(rolled_back, results)
        worlds = await self.worlds.get_all()
        self.assertEqual(len(worlds), 1)
        self.assertEqual(worlds[0].fine_cells_per_map_cell, 2000)

    async def test_http_size_errors_and_master_force_contract(self):
        app = FastAPI()
        install_error_handlers(app)
        app.include_router(router)
        app.dependency_overrides[get_container] = lambda: self.container
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/worlds", json={**WIRE, KEY: None})
            self.assertEqual(response.status_code, 422)
            issue = response.json()["detail"][0]
            self.assertEqual(issue["loc"], [KEY])
            self.assertEqual(issue["schema_id"], WorldGridSettings.SCHEMA_ID)
            self.assertEqual(issue["code"], "int_type")
            self.assertEqual(await self.worlds.get_all(), [])
            self.assertEqual((await client.post("/worlds", json=WIRE)).status_code, 201)
            response = await client.put("/worlds/w1", json={KEY: 2000})
            self.assertTrue(response.json()["requires_force"])
            self.assertEqual((await self.worlds.get_by_id("w1")).fine_cells_per_map_cell, 1000)
            response = await client.put("/worlds/w1", json={KEY: 2000, "force": True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual((await self.worlds.get_by_id("w1")).fine_cells_per_map_cell, 2000)
