"""Production handler registry + isolated DB + HTTP: preview never writes."""
import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI, HTTPException

from app.api.deps import get_container
from app.api.routes.worlds import router
from app.application.importResult import ImportResult
from app.application.jsonValidation.types import ImportValidationError, ImportValidationReport
from app.core.container import Container
from app.db.database import Database


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


class ImportValidationPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Database(str(Path(tmp.name) / "policy.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.service = self.container.world_bundle_service()
        self.worlds = self.container.world_service()

    def fixture(self, name="world_template"):
        return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))

    async def test_preview_all_sections_cannot_reach_write_or_version_paths(self):
        fixture = self.fixture()
        original = copy.deepcopy(fixture)
        before = (self.db.conn.total_changes, self.db.bootstrap_conn.total_changes)
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.db, "transaction", side_effect=AssertionError("transaction")))
            for handler in self.service._handlers:
                stack.enter_context(patch.object(handler, "import_section", side_effect=AssertionError("write handler")))
            stack.enter_context(patch.object(self.worlds, "find_by_id", side_effect=AssertionError("version lookup")))
            stack.enter_context(patch.object(self.worlds, "next_version_number", side_effect=AssertionError("version allocation")))
            stack.enter_context(patch("app.application.worldData.worldBundleService.remap_bundle", side_effect=AssertionError("remap")))
            report = await self.service.import_bundle(fixture, validate_only=True)
        self.assertIsInstance(report, ImportValidationReport)
        self.assertTrue(report.valid, report.issues)
        self.assertEqual(before, (self.db.conn.total_changes, self.db.bootstrap_conn.total_changes))
        self.assertEqual(fixture, original)
        self.assertEqual(await self.worlds.get_all(), [])

    async def test_invalid_new_field_same_diagnostics_and_zero_writes(self):
        fixture = self.fixture("world_defaults_test")
        fixture["world"]["terrain_masks"] = {"default_forests": {"forest_min_rainfall": -1}}
        before = self.db.conn.total_changes
        report = await self.service.import_bundle(fixture, validate_only=True)
        self.assertFalse(report.valid)
        with self.assertRaises(ImportValidationError) as error:
            await self.service.import_bundle(fixture)
        self.assertEqual(tuple(error.exception.errors), report.issues)
        self.assertEqual(self.db.conn.total_changes, before)

    async def test_library_membership_checked_against_incoming_world(self):
        fixture = self.fixture("world_defaults_test")
        fixture["relief_templates"] = [{"system_name": "bad-ref", "display_name": "Bad",
            "context": "river", "structure_refs": ["missing-barrier"]}]
        report = await self.service.import_bundle(fixture, validate_only=True)
        self.assertFalse(report.valid)
        self.assertEqual(report.issues[0].path[:2], ("relief_templates", 0))
        self.assertEqual(await self.worlds.get_all(), [])

    async def test_library_schema_and_other_sections_aggregate(self):
        fixture = self.fixture("world_defaults_test")
        fixture["race_templates"] = [{"race_traits": "invalid"}]
        fixture["perk_templates"] = [None]
        fixture["states"] = [{}]
        report = await self.service.import_bundle(fixture, validate_only=True)
        self.assertFalse(report.valid)
        self.assertEqual({e.path[0] for e in report.issues}, {"states", "race_templates", "perk_templates"})

    async def test_infrastructure_failure_is_not_a_validation_report(self):
        fixture = self.fixture()
        handler = self.service._by_key["states"]
        with patch.object(handler, "validate_section", side_effect=OSError("infrastructure failure")):
            with self.assertRaises(OSError):
                await self.service.import_bundle(fixture, validate_only=True)
        self.assertEqual(await self.worlds.get_all(), [])

    async def test_preview_is_not_reservation_and_apply_revalidates(self):
        fixture = self.fixture("world_defaults_test")
        self.assertTrue((await self.service.import_bundle(fixture, validate_only=True)).valid)
        results, rolled_back = await self.service.import_bundle(fixture)
        self.assertFalse(rolled_back)
        self.assertEqual(results["world"].succeeded, 1)
        before = self.db.conn.total_changes
        self.assertTrue((await self.service.import_bundle(fixture, validate_only=True)).valid)
        self.assertEqual(self.db.conn.total_changes, before)
        changed = copy.deepcopy(fixture)
        changed["world"]["terrain_masks"] = {"default_forests": {"forest_min_rainfall": None}}
        with self.assertRaises(ImportValidationError):
            await self.service.import_bundle(changed)
        self.assertEqual(len(await self.worlds.get_all()), 1)
        _, rolled_back = await self.service.import_bundle(fixture)
        self.assertFalse(rolled_back)
        self.assertEqual(len(await self.worlds.get_all()), 2)

    async def test_ordinary_import_still_rolls_back_handler_failure(self):
        fixture = self.fixture()
        handler = self.service._by_key["states"]
        with patch.object(handler, "import_section", new=AsyncMock(return_value=ImportResult(total=1, succeeded=0, failed=1))):
            _, rolled_back = await self.service.import_bundle(fixture)
        self.assertTrue(rolled_back)
        self.assertEqual(await self.worlds.get_all(), [])

    async def test_world_patch_keeps_missing_nested_value_and_rejects_invalid(self):
        fixture = self.fixture("world_defaults_test")
        fixture["world"]["terrain_masks"] = {"default_forests": {"forest_min_rainfall": 60}}
        await self.service.import_bundle(fixture)
        uid = fixture["world"]["world_uid"]
        await self.worlds.update(uid, {"terrain_masks": {"default_forests": {"enabled": False}}})
        world = await self.worlds.get_by_id(uid)
        self.assertEqual(world.terrain_masks["default_forests"]["forest_min_rainfall"], 60)
        self.assertFalse(world.terrain_masks["default_forests"]["enabled"])
        with self.assertRaises(HTTPException) as error:
            await self.worlds.update(uid, {"terrain_masks": {"default_forests": {"forest_min_rainfall": -1}}})
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual((await self.worlds.get_by_id(uid)).terrain_masks, world.terrain_masks)

    async def test_union_patch_persists_star_changes_and_invalid_merge_never_writes(self):
        fixture = self.fixture("world_defaults_test")
        fixture["world"]["terrain_masks"] = {"default_mountains": {"default_form": {
            "form_type": "star", "rays": 5, "inner_ratio": 0.45}}}
        await self.service.import_bundle(fixture)
        uid = fixture["world"]["world_uid"]
        await self.worlds.update(uid, {"terrain_masks": {"default_mountains": {
            "default_form": {"rays": 7}}}})
        world = await self.worlds.get_by_id(uid)
        self.assertEqual(world.terrain_masks["default_mountains"]["default_form"],
                         {"form_type": "star", "rays": 7, "inner_ratio": 0.45})
        for change in ({"default_mountains": {"default_form": {"rays": 1}}},
                       {"default_forests": {"hills": {"shapes": None}}}):
            with self.assertRaises(HTTPException) as caught:
                await self.worlds.update(uid, {"terrain_masks": change})
            self.assertEqual(caught.exception.status_code, 422)
            self.assertEqual((await self.worlds.get_by_id(uid)).terrain_masks, world.terrain_masks)

    async def test_http_flag_default_false_true_and_invalid(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_container] = lambda: self.container
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            fixture = self.fixture("world_defaults_test")
            async def send(query=""):
                return await client.post(f"/worlds/import{query}", files={"file": ("world.json", json.dumps(fixture), "application/json")})
            response = await send("?validate_only=true")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"validate_only": True, "valid": True, "issues": []})
            self.assertEqual(await self.worlds.get_all(), [])
            fixture["world"]["terrain_masks"] = {"default_forests": {"forest_min_rainfall": -1}}
            response = await send("?validate_only=true")
            self.assertFalse(response.json()["valid"])
            self.assertEqual(response.json()["issues"][0]["code"], "greater_than_equal")
            self.assertEqual((await send()).status_code, 422)
            del fixture["world"]["terrain_masks"]
            self.assertEqual((await send("?validate_only=false")).status_code, 200)
            self.assertEqual((await send()).status_code, 200)
            self.assertEqual(len(await self.worlds.get_all()), 2)


if __name__ == "__main__":
    unittest.main()
