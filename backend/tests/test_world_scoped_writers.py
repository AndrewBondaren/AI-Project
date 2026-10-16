"""W2-3: internal registry writes isolate validation and preserve world data."""

from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from test_library_packs_4b import _ServiceCase
from app.application.jsonValidation.resolve import resolve_model
from app.application.jsonValidation.types import ImportValidationError
from app.application.worldData.errors import WorldDataNotFoundError
from app.application.worldData.raceService import RaceService
from app.application.worldData.worldPerkService import WorldPerkService
from app.application.templateLibrary.reliefWorldImportService import ReliefWorldImportService
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository


class ScopedWriterTests(unittest.IsolatedAsyncioTestCase):
    def world_repo(self):
        world = World("w1", "World", "2026-10-16", material_registry=[42], g=-1)
        repo = AsyncMock(spec=IWorldRepository)
        repo.get_by_id.return_value = world
        return world, repo

    def binders(self):
        for service_type, key in ((RaceService, "race_template_registry"),
                                  (WorldPerkService, "perk_template_registry")):
            world, repo = self.world_repo()
            yield service_type(AsyncMock(), repo), key, world, repo

    async def test_bind_duplicate_and_unbind_preserve_invalid_neighbors(self):
        for service, key, world, repo in self.binders():
            with self.subTest(column=key):
                before = deepcopy(world)
                template = SimpleNamespace(template_uid="template-1", display_name="Template")
                await service._ensure_registry("w1", template)
                rows = getattr(world, key)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["system_template_uid"], "template-1")
                self.assertEqual(rows[0]["display_template_name"], "Template")
                self.assertTrue(rows[0]["imported_at"])
                repo.update.assert_awaited_once_with(world)
                before.__dict__[key] = deepcopy(rows)
                self.assertEqual(world, before)
                await service._ensure_registry("w1", template)
                self.assertEqual(repo.update.await_count, 1)
                await service._unbind_registry("w1", "template-1")
                self.assertEqual(getattr(world, key), [])
                self.assertEqual(repo.update.await_count, 2)
                before.__dict__[key] = []
                self.assertEqual(world, before)

    async def test_invalid_registry_keeps_index_and_never_saves_or_drops_rows(self):
        for service, key, world, repo in self.binders():
            for operation in ("_ensure_registry", "_unbind_registry"):
                with self.subTest(column=key, operation=operation):
                    setattr(world, key, [{"system_template_uid": "valid"}, {"system_template_uid": None}])
                    before = deepcopy(world)
                    arg = (SimpleNamespace(template_uid="new", display_name="New")
                           if operation == "_ensure_registry" else "valid")
                    with self.assertRaises(ImportValidationError) as caught:
                        await getattr(service, operation)("w1", arg)
                    issue = caught.exception.errors[0]
                    self.assertEqual(issue.path, (key, 1, "system_template_uid"))
                    self.assertTrue(issue.schema_id)
                    self.assertTrue(issue.code)
                    self.assertEqual(world, before)
                    repo.update.assert_not_awaited()

    async def test_missing_world_preserves_domain_error(self):
        for service, key, world, repo in self.binders():
            with self.subTest(column=key):
                repo.get_by_id.return_value = None
                with self.assertRaisesRegex(WorldDataNotFoundError, "World 'missing' not found"):
                    await service.get_all("missing")
                repo.update.assert_not_awaited()

    def relief(self):
        world, repo = self.world_repo()
        world.terrain_registry = []
        service = ReliefWorldImportService(repo, AsyncMock(), catalog=SimpleNamespace())
        outline = resolve_model(ReliefTemplate, {
            "system_name": "forest", "display_name": "Forest", "context": "open_land",
            "conditions": [{"terrain": "forest", "cases": [
                {"policy": "slope_down", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                {"policy": "slope_up", "delta_z": 1, "slope_weight": 1.0, "sheer_weight": 0.0},
                {"policy": "slope_none", "delta_z": 0, "slope_weight": 1.0, "sheer_weight": 0.0}]}],
        })
        return service, outline, world, repo

    async def test_relief_sync_is_scoped_and_second_sync_does_not_save(self):
        service, outline, world, repo = self.relief()
        before = deepcopy(world)
        await service._sync_terrain_from_outline("w1", outline, "template-1")
        self.assertIn("forest", {row["system_terrain"] for row in world.terrain_registry})
        repo.update.assert_awaited_once_with(world)
        before.terrain_registry = deepcopy(world.terrain_registry)
        self.assertEqual(world, before)
        await service._sync_terrain_from_outline("w1", outline, "template-1")
        self.assertEqual(repo.update.await_count, 1)

    async def test_relief_invalid_target_does_not_mutate_loaded_world(self):
        service, outline, world, repo = self.relief()
        world.terrain_registry = [42]
        before = deepcopy(world)
        with self.assertRaises(ImportValidationError) as caught:
            await service._sync_terrain_from_outline("w1", outline, "template-1")
        self.assertEqual(caught.exception.errors[0].path[:2], ("terrain_registry", 0))
        self.assertEqual(world, before)
        repo.update.assert_not_awaited()


class ScopedWriterSqlTests(_ServiceCase):
    async def test_container_wires_repository_backed_bind_and_unbind(self):
        world = await self._world("w1")
        world.material_registry = [42]
        await self.worlds.update(world)
        for service, key in ((self.container.race_service(), "race_template_registry"),
                             (self.container.perk_service(), "perk_template_registry")):
            with self.subTest(column=key):
                row = await service.create("w1", {"display_name": "Scoped template"})
                saved = await self.worlds.get_by_id("w1")
                self.assertEqual(saved.material_registry, [42])
                self.assertEqual(getattr(saved, key)[0]["system_template_uid"], row.template_uid)
                await service.delete("w1", row.template_uid)
                saved = await self.worlds.get_by_id("w1")
                self.assertEqual(getattr(saved, key), [])
                self.assertEqual(saved.material_registry, [42])
