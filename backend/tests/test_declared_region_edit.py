"""10c: production import/HTTP and atomic declaration/state writes."""

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from pydantic import TypeAdapter

from app.api.deps import get_container
from app.api.routes.worlds import router
from app.application.jsonValidation.resolve import ResolveMode
from app.application.jsonValidation.types import ImportValidationError
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.core.container import Container
from app.dataModel.terrainMasks.regions.edit import DeclaredRegionEdit
from app.db.database import Database
from app.db.repositories.sqlite.regionStateRepository import SqliteRegionStateRepository
from app.ids import region_uid


def spec(name="Wood", **changes):
    return {"entry_type": "forest", "name": name,
            "shape": {"kind": "ellipse", "cx": 10, "cy": 10, "rx": 5, "ry": 5}, **changes}


class DeclaredRegionEditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Database(str(Path(tmp.name) / "regions.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.worlds = self.container.world_service()
        self.repo = SqliteRegionStateRepository(self.db)
        self.bundle = json.loads((Path(__file__).resolve().parents[2] /
            "fixtures/world_landcover_default.json").read_text(encoding="utf-8"))
        self.bundle["world"]["terrain_masks"] = {"declared_regions": [spec()]}
        self.uid = self.bundle["world"]["world_uid"]
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_container] = lambda: self.container
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def import_world(self):
        results, rollback = await self.container.world_bundle_service().import_bundle(copy.deepcopy(self.bundle))
        self.assertFalse(rollback, results)
        worlds = await self.worlds.get_all()
        self.assertEqual(len(worlds), 1)
        self.uid = worlds[0].world_uid

    async def edit(self, op, name="Wood", region=None, **kwargs):
        data = {"op": op, "name": name}
        if region is not None:
            data["region"] = region
        return await self.worlds.edit_region(self.uid, TypeAdapter(DeclaredRegionEdit).validate_python(data), **kwargs)

    async def row(self, name="Wood"):
        return await self.repo.get(self.uid, region_uid(self.uid, name=name))

    async def test_import_missing_name_preview_and_runtime(self):
        self.bundle["world"]["terrain_masks"]["declared_regions"][0].pop("name")
        response = await self.client.post("/worlds/import?validate_only=true",
            files={"file": ("world.json", json.dumps(self.bundle), "application/json")})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["valid"])
        self.assertTrue(any("name" in issue["loc"] for issue in response.json()["issues"]))
        self.assertEqual([i["code"] for i in response.json()["issues"]], ["value_error"])
        self.assertEqual(await self.worlds.get_all(), [])
        with patch("app.application.jsonValidation.declaredRegions.declared_region_identity",
                   wraps=declared_region_identity) as identity, \
             self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as logs:
            await self.import_world()
        self.assertTrue(any("degraded_identity" in line for line in logs.output))
        contexts = [call.kwargs["ctx"] for call in identity.call_args_list]
        self.assertTrue(contexts)
        for ctx in contexts:
            self.assertIs(ctx.mode, ResolveMode.IMPORT)
            self.assertFalse(ctx.validate_only)
            self.assertEqual(ctx.path_prefix, ("terrain_masks", "declared_regions", 0))
            self.assertEqual(ctx.report.issues, [])
        rows = await self.repo.get_by_world(self.uid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].current_type, "forest")

    async def test_import_derives_world_uid_before_region_identity_check(self):
        self.bundle["world"].pop("world_uid")
        with patch("app.application.jsonValidation.declaredRegions.declared_region_identity",
                   wraps=declared_region_identity) as identity:
            await self.import_world()
        self.assertTrue(identity.call_args_list)
        self.assertTrue(all(call.args[0] for call in identity.call_args_list))
        self.assertIn(self.uid, [call.args[0] for call in identity.call_args_list])
        self.assertNotIn("world_uid", self.bundle["world"])

    async def test_collision_normalization_and_shape_same_rejection(self):
        for entries in ([spec(" Café "), spec("Cafe\u0301")],
                        [spec(shape={"kind": "ellipse", "cx": 0, "cy": 0, "rx": 0, "ry": 1})],
                        [spec("bad|name")]):
            self.bundle["world"]["terrain_masks"]["declared_regions"] = entries
            report = await self.container.world_bundle_service().import_bundle(copy.deepcopy(self.bundle), validate_only=True)
            self.assertFalse(report.valid)
            with self.assertRaises(ImportValidationError) as caught:
                await self.container.world_bundle_service().import_bundle(copy.deepcopy(self.bundle))
            self.assertEqual([(i.path, i.code) for i in report.issues],
                             [(i.path, i.code) for i in caught.exception.errors])
        self.assertEqual(await self.worlds.get_all(), [])

    async def test_resize_type_rename_remove_readd(self):
        await self.import_world()
        row = await self.row()
        await self.repo.upsert(replace(row, current_type="plains", pending_target="forest", progress=.5))
        resized = spec(shape={"kind": "ellipse", "cx": 10, "cy": 10, "rx": 8, "ry": 5})
        await self.edit("update", region=resized)
        row = await self.row()
        self.assertEqual((row.current_type, row.progress, row.pending_target), ("plains", 0, None))
        await self.edit("update", region=spec(entry_type="farmland"))
        row = await self.row()
        self.assertEqual(row.current_type, "farmland")
        self.assertEqual(row.history[-1]["cause"], "declared_edit")
        await self.edit("update", region=spec("New"))
        self.assertTrue((await self.row()).tombstone)
        self.assertFalse((await self.row("New")).tombstone)
        await self.edit("remove", name="New")
        self.assertTrue((await self.row("New")).tombstone)
        await self.edit("add", name="New", region=spec("New"))
        row = await self.row("New")
        self.assertEqual((row.current_type, row.history, row.progress, row.tombstone), ("forest", [], 0, False))

    async def test_http_preview_collision_and_atomic_rollback(self):
        await self.import_world()
        before = self.db.conn.total_changes
        with patch.object(self.db, "transaction", side_effect=AssertionError("preview transaction")):
            response = await self.client.post(f"/worlds/{self.uid}/regions?validate_only=true",
                json={"op": "update", "name": "Wood", "region": spec("Other")})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(self.db.conn.total_changes, before)
        with patch.object(self.worlds._region_editor, "reconcile", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                await self.edit("remove")
        self.assertFalse((await self.row()).tombstone)
        world = await self.worlds.get_by_id(self.uid)
        self.assertEqual(world.terrain_masks["declared_regions"][0]["name"], "Wood")
        response = await self.client.post(f"/worlds/{self.uid}/regions",
            json={"op": "remove", "name": " Wood "})
        self.assertEqual(response.status_code, 200)
        self.assertTrue((await self.row()).tombstone)

    async def test_full_world_update_reconciles_and_rejects_duplicates(self):
        await self.import_world()
        await self.worlds.update(self.uid, {"terrain_masks": {"declared_regions": []}})
        self.assertTrue((await self.row()).tombstone)
        with self.assertRaises(ImportValidationError):
            await self.worlds.update(self.uid, {"terrain_masks": {"declared_regions": [spec(), spec()]}})
        await self.worlds.update(self.uid, {"terrain_masks": {"declared_regions": [spec()]}})
        self.assertFalse((await self.row()).tombstone)

    async def test_remove_without_state_and_readd_after_cleanup(self):
        await self.import_world()
        async with self.db.transaction():
            await self.db.conn.execute("DELETE FROM region_states WHERE world_uid = ?", [self.uid])
        await self.edit("remove")
        self.assertTrue((await self.row()).tombstone)
        await self.repo.cleanup_orphans(self.uid)
        await self.edit("add", region=spec())
        self.assertFalse((await self.row()).tombstone)

    async def test_operation_errors_and_rename_collision_preview_apply(self):
        await self.import_world()
        await self.edit("add", name="Other", region=spec("Other"))
        for operation in ({"op": "add", "name": "Wood", "region": spec()},
                          {"op": "remove", "name": "missing"},
                          {"op": "update", "name": "Wood", "region": spec("Other")}):
            preview = await self.client.post(f"/worlds/{self.uid}/regions?validate_only=true", json=operation)
            applied = await self.client.post(f"/worlds/{self.uid}/regions", json=operation)
            self.assertEqual(preview.status_code, 200)
            self.assertFalse(preview.json()["valid"])
            self.assertEqual(applied.status_code, 422)
            self.assertEqual(preview.json()["issues"], applied.json()["detail"])
        self.assertFalse((await self.row()).tombstone)
