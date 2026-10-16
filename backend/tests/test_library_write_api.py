"""Regression coverage for existing HTTP writes using real SQLite and DI."""
import json
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from test_library_packs_4b import _ServiceCase, _relief_body
import test_library_write_service as service_fixture
import test_library_packs_b3 as fs_fixture
from app.api.deps import get_container
from app.api.errorMapping import install_error_handlers
from app.api.routes.reliefTemplates import router as relief_router
from app.api.routes.structureTemplates import router as structure_router
from app.application.templateLibrary.packs.write.writeContracts import LibraryWriteSelection
from app.application.templateLibrary.packs.errors import LibraryPackValidationError, LibraryPackConflictError
from app.application.templateLibrary.packs.write.writeResults import PolicyRequired
from app.ids import LibraryKind, library_uid


class LibraryWriteApiTests(_ServiceCase):
    fs_pack = service_fixture.LibraryWriteServiceTests.fs_pack

    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self._world("w1")
        app = FastAPI()
        install_error_handlers(app)
        app.include_router(relief_router)
        app.include_router(structure_router)
        app.dependency_overrides[get_container] = lambda: self.container
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_create_requires_pack_and_can_negotiate_replace(self):
        body = _relief_body("meadow")
        missing = await self.client.post("/relief-templates", json=body)
        self.assertEqual(missing.status_code, 422, missing.text)
        pack = await self.service.create_pack(system_name="http.relief")
        params = {"pack_uid": pack.pack_uid}
        first = await self.client.post("/relief-templates", params=params, json=body)
        self.assertEqual(first.status_code, 201, first.text)
        uid = first.json()["template_uid"]
        changed = {**body, "display_name": "Revised"}
        preview = await self.client.post("/relief-templates", params=params, json=changed)
        self.assertEqual(preview.status_code, 409, preview.text)
        self.assertEqual(preview.json()["status"], "policy_required")
        params.update(preview_token=preview.json()["preview_token"], decisions=json.dumps([
            {"item_key": "0", "policy": "replace", "target_uid": uid}]))
        applied = await self.client.post("/relief-templates", params=params, json=changed)
        self.assertEqual(applied.status_code, 201, applied.text)
        self.assertEqual(applied.json()["display_name"], "Revised")

    async def test_world_import_preview_replace_and_stale(self):
        body = _relief_body("meadow")
        url = "/worlds/w1/relief-templates/import"
        first = await self.client.post(url, json=body)
        self.assertEqual(first.status_code, 200, first.text)
        uid = first.json()["uids"][0]
        preview = await self.client.post(url, json=body)
        self.assertEqual(preview.status_code, 409, preview.text)
        params = {"preview_token": preview.json()["preview_token"], "decisions": json.dumps([
            {"item_key": "0", "policy": "replace", "target_uid": uid}])}
        changed = {**body, "display_name": "Changed"}
        stale = await self.client.post(url, params=params, json=changed)
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertTrue(stale.json()["stale"])
        self.assertEqual((await self.relief_rows.get_by_uid(uid)).display_name, "Meadow")
        params["preview_token"] = stale.json()["preview_token"]
        applied = await self.client.post(url, params=params, json=changed)
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertEqual(applied.json()["uids"], [uid])

    async def test_fs_import_negotiation(self):
        root, path, manifest = self.fs_pack()
        with patch("app.application.templateLibrary.reliefTemplateLibraryService.resolve_relief_domain_root", return_value=root):
            data = {"path": str(path)}
            first = await self.client.post("/relief-templates/import", data=data)
            self.assertEqual(first.status_code, 200, first.text)
            preview = await self.client.post("/relief-templates/import", data=data)
            self.assertEqual(preview.status_code, 409, preview.text)
            data.update(preview_token=preview.json()["preview_token"], decisions=json.dumps([
                {"item_key": "fs", "policy": "replace", "target_uid": manifest["pack_uid"]}]))
            applied = await self.client.post("/relief-templates/import", data=data)
            self.assertEqual(applied.status_code, 200, applied.text)
            preview = await self.client.post("/relief-templates/import", data={"path": str(path)})
            copied = await self.client.post("/relief-templates/import", data={"path": str(path),
                "preview_token": preview.json()["preview_token"], "decisions": json.dumps([
                    {"item_key": "fs", "policy": "copy", "copy_system_name": "http.fs.copy"}])})
            self.assertEqual(copied.status_code, 200, copied.text)
            self.assertNotEqual(first.json()["uids"], copied.json()["uids"])

    async def test_publish_can_continue_after_default_publication(self):
        source, _ = await self._relief_engine_pack()
        instance = await self.service.instantiate_pack(source.pack_uid, world_uid="w1")
        await self.service.copy_pack(instance.pack.pack_uid)
        preview = await self.service.copy_pack(instance.pack.pack_uid, system_name="another.copy")
        self.assertIsInstance(preview, PolicyRequired)
        applied = await self.service.copy_pack(instance.pack.pack_uid, system_name="another.copy",
            preview_token=preview.preview_token)
        self.assertEqual(applied.pack.system_name, "another.copy")

    async def test_structure_creation_and_owner_gate(self):
        pack = await self.service.create_pack(system_name="http.structures")
        uid = library_uid(LibraryKind.STRUCTURE_TEMPLATES, "house", pack_uid=pack.pack_uid)
        response = await self.client.post("/structure-templates",
            params={"pack_uid": pack.pack_uid, "local_uid": "house"},
            json={"system_name": uid, "display_name": "House"})
        self.assertEqual(response.status_code, 201, response.text)
        params = {"pack_uid": pack.pack_uid, "local_uid": "house"}
        body = {"system_name": uid, "display_name": "House"}
        preview = await self.client.post("/structure-templates", params=params, json=body)
        self.assertEqual(preview.status_code, 409, preview.text)
        params.update(preview_token=preview.json()["preview_token"],
            decisions=json.dumps([{"item_key": "0", "policy": "copy"}]))
        copied = await self.client.post("/structure-templates", params=params, json=body)
        self.assertEqual(copied.status_code, 201, copied.text)
        self.assertNotEqual(copied.json()["template_uid"], uid)
        copied_uid = copied.json()["template_uid"]
        changed = {"system_name": copied_uid, "display_name": "Edited copy"}
        preview = await self.client.post("/structure-templates",
            params={"pack_uid": pack.pack_uid, "local_uid": "house"}, json=changed)
        self.assertEqual(preview.status_code, 409, preview.text)
        params.update(preview_token=preview.json()["preview_token"], decisions=json.dumps([
            {"item_key": "0", "policy": "replace", "target_uid": copied_uid}]))
        edited = await self.client.post("/structure-templates", params=params, json=changed)
        self.assertEqual(edited.status_code, 201, edited.text)
        self.assertEqual(edited.json()["template_uid"], copied_uid)
        self.assertEqual((await self.structure_rows.get_by_uid(uid)).display_name, "House")
        owned = await self.service.create_pack(system_name="owned.relief", owner_world_uid="w1")
        forbidden = await self.client.post("/relief-templates", params={"pack_uid": owned.pack_uid},
            json=_relief_body("meadow"))
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

    async def test_upload_batch_copy_and_incomplete_selection_are_atomic(self):
        pack = await self.service.create_pack(system_name="http.batch")
        url = "/relief-templates/import"
        bodies = [_relief_body("meadow"), _relief_body("shore")]
        files = {"file": ("bodies.json", json.dumps(bodies), "application/json")}
        first = await self.client.post(url, data={"pack_uid": pack.pack_uid}, files=files)
        self.assertEqual(first.status_code, 200, first.text)
        before = await self.members.list_by_pack(pack.pack_uid)
        preview = await self.client.post(url, data={"pack_uid": pack.pack_uid}, files=files)
        self.assertEqual(preview.status_code, 409, preview.text)
        data = {"pack_uid": pack.pack_uid, "preview_token": preview.json()["preview_token"],
                "decisions": json.dumps([{"item_key": "0", "policy": "copy"}])}
        partial = await self.client.post(url, data=data, files=files)
        self.assertEqual(partial.status_code, 409, partial.text)
        self.assertEqual(await self.members.list_by_pack(pack.pack_uid), before)
        data["decisions"] = json.dumps([{"item_key": str(i), "policy": "copy"} for i in range(2)])
        applied = await self.client.post(url, data=data, files=files)
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertTrue(set(first.json()["uids"]).isdisjoint(applied.json()["uids"]))
        self.assertEqual(len(await self.members.list_by_pack(pack.pack_uid)), 4)

    async def test_structure_fs_preview_and_replace(self):
        root = Path(self.tmp.name) / "structures_templates"
        manifest = fs_fixture._manifest_dict("user", kind=LibraryKind.STRUCTURE_TEMPLATES)
        member = manifest["members"][0]
        path = fs_fixture._write_pack(root, "user", manifest=manifest, bodies={member["local_uid"]:
            {"system_name": member["template_uid"], "display_name": "House"}})
        with patch("app.application.templateLibrary.structureTemplateLibraryService.resolve_structures_domain_root", return_value=root):
            url = "/structure-templates/import"
            body = {"path": str(path)}
            first = await self.client.post(url, json=body)
            self.assertEqual(first.status_code, 200, first.text)
            preview = await self.client.post(url, json=body)
            self.assertEqual(preview.status_code, 409, preview.text)
            self.assertNotIn("outline", json.dumps(preview.json()))
            self.assertNotIn("worlds", preview.json()["preview"][0])
            body.update(preview_token=preview.json()["preview_token"], decisions=[
                {"item_key": "fs", "policy": "replace", "target_uid": manifest["pack_uid"]}])
            applied = await self.client.post(url, json=body)
            self.assertEqual(applied.status_code, 200, applied.text)

    async def test_invalid_negotiation_and_default_pack_rejected(self):
        pack = await self.service.create_pack(system_name="http.invalid")
        for selection in ("invalid json", json.dumps([{"item_key": "wrong", "policy": "copy"}])):
            response = await self.client.post("/relief-templates",
                params={"pack_uid": pack.pack_uid, "decisions": selection}, json=_relief_body("meadow"))
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(await self.members.list_by_pack(pack.pack_uid), [])
        missing = await self.client.post("/relief-templates/import", data={"path": "missing-pack"})
        self.assertEqual(missing.status_code, 422, missing.text)
        root = Path(__file__).resolve().parents[2] / "structures_templates"
        default = await self.service.import_fs_pack(LibraryKind.STRUCTURE_TEMPLATES, root / "base", domain_root=root)
        member = (await self.members.list_by_pack(default.pack.pack_uid))[0]
        row = await self.structure_rows.get_by_uid(member.template_uid)
        response = await self.client.post("/structure-templates",
            params={"pack_uid": default.pack.pack_uid, "local_uid": member.local_uid}, json=row.data)
        self.assertEqual(response.status_code, 403, response.text)

    async def test_publish_rejects_replace_conflicting_name_and_stale(self):
        source, _ = await self._relief_engine_pack()
        instance = await self.service.instantiate_pack(source.pack_uid, world_uid="w1")
        published = await self.service.copy_pack(instance.pack.pack_uid)
        replace = LibraryWriteSelection(item_key="pack", policy="replace", target_uid=published.pack.pack_uid)
        with self.assertRaises(LibraryPackValidationError):
            await self.service.copy_pack(instance.pack.pack_uid, decisions=(replace,))
        copy = LibraryWriteSelection(item_key="pack", policy="copy", copy_system_name="another.copy")
        with self.assertRaises(LibraryPackValidationError):
            await self.service.copy_pack(instance.pack.pack_uid, system_name="different", decisions=(copy,))
        preview = await self.service.copy_pack(instance.pack.pack_uid, system_name="another.copy")
        member = instance.members[0]
        await self.service.update_member_body(member.template_uid, _relief_body("meadow", display_name="Revised"), world_uid="w1")
        stale = await self.service.copy_pack(instance.pack.pack_uid, decisions=(copy,), preview_token=preview.preview_token)
        self.assertIsInstance(stale, PolicyRequired)
        self.assertTrue(stale.stale)
        self.assertIsNone(await self.packs.get_by_system_name("another.copy"))
        with self.assertRaises(LibraryPackConflictError):
            await self.service.copy_pack(instance.pack.pack_uid, system_name=published.pack.system_name,
                preview_token=stale.preview_token)

    async def test_world_pack_instantiation_can_negotiate(self):
        source, members = await self._relief_engine_pack()
        url = "/worlds/w1/relief-templates/import"
        params = {"template_uid": members[0].template_uid}
        first = await self.client.post(url, params=params)
        self.assertEqual(first.status_code, 200, first.text)
        preview = await self.client.post(url, params=params)
        self.assertEqual(preview.status_code, 409, preview.text)
        params.update(preview_token=preview.json()["preview_token"], decisions=json.dumps([
            {"item_key": "pack", "policy": "replace", "target_uid": first.json()["pack_uid"]}]))
        applied = await self.client.post(url, params=params)
        self.assertEqual(applied.status_code, 200, applied.text)

        preview = await self.client.post(url, params={"template_uid": members[0].template_uid})
        self.assertEqual(preview.status_code, 409, preview.text)
        instance_uid = first.json()["pack_uid"]
        before_members = await self.members.list_by_pack(instance_uid)
        before_bodies = {m.template_uid: await self.service.read_member_body(m.template_uid)
                         for m in before_members}
        await self.service.update_member_body(members[0].template_uid,
            _relief_body(members[0].local_uid, display_name="Changed after preview"))
        params["preview_token"] = preview.json()["preview_token"]
        stale = await self.client.post(url, params=params)
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertTrue(stale.json()["stale"])
        self.assertEqual(await self.members.list_by_pack(instance_uid), before_members)
        self.assertEqual({m.template_uid: await self.service.read_member_body(m.template_uid)
                          for m in before_members}, before_bodies)

    async def test_bundle_policy_conflict_rolls_back_world_and_members(self):
        from app.application.worldBundle.entity.sections import WorldSectionHandler
        from app.application.worldBundle.worldBundleService import WorldBundleService
        from app.application.templateLibrary.packs.errors import (
            LibraryPackPolicyRequiredError, require_no_policy)
        from app.api.routes.worlds import router as worlds_router
        from app.application.imports.result import ImportResult

        container = self.container
        body = _relief_body("meadow")
        class SeedLibraries:
            key = "relief_templates"
            def validate_section(self, world, data, *, ctx):
                container.relief_world_import_service().prepare_body(world, data[0], ctx=ctx)
            async def import_section(self, uid, data):
                outcome = await container.relief_world_import_service().import_outlines_into_world(uid, data)
                require_no_policy(outcome)
                return ImportResult(total=1, succeeded=1, failed=0)

        # The second library handler sees the writes of an earlier handler
        # in the same outer UOW; the conflict must unwind the complete import.
        service = WorldBundleService(self.db, container.world_service(),
            [WorldSectionHandler(container.world_service()), SeedLibraries(), SeedLibraries()])
        fixture = json.loads((Path(__file__).resolve().parents[2] / "fixtures/world_defaults_test.json").read_text(encoding="utf-8"))
        data = {"world": fixture["world"], "relief_templates": [body]}
        uid = data["world"]["world_uid"]
        with self.assertRaises(LibraryPackPolicyRequiredError):
            await service.import_bundle(data)
        self.assertIsNone(await self.worlds.get_by_id(uid))
        self.assertEqual(await self.packs.list_all(), [])
        self.assertEqual(await self.relief_rows.list_all(), [])
        # Exercise the production HTTP boundary too: it catches the domain
        # exception only after the service has rolled back its transaction.
        app = FastAPI()
        install_error_handlers(app)
        app.include_router(worlds_router)
        app.dependency_overrides[get_container] = lambda: container
        with patch.object(container, "world_bundle_service", return_value=service):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/worlds/import", files={"file": ("world.json", json.dumps(data), "application/json")})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()["status"], "policy_required")
        self.assertIsNone(await self.worlds.get_by_id(uid))
        self.assertEqual(await self.packs.list_all(), [])

    async def test_bundle_later_entity_failure_rolls_back_library_apply(self):
        from app.application.worldBundle.entity.sections import WorldSectionHandler
        from app.application.worldBundle.worldBundleService import WorldBundleService
        from app.application.imports.result import ImportResult
        from app.application.templateLibrary.packs.errors import require_no_policy
        container = self.container
        class SeedLibraries:
            key = "relief_templates"
            def validate_section(self, world, data, *, ctx):
                container.relief_world_import_service().prepare_body(world, data[0], ctx=ctx)
            async def import_section(self, uid, data):
                outcome = await container.relief_world_import_service().import_outlines_into_world(uid, data)
                require_no_policy(outcome)
                return ImportResult(total=1, succeeded=1, failed=0)
        class FailingEntity:
            key = "states"
            def validate_section(self, world, data, *, ctx):
                pass
            async def import_section(self, uid, data):
                return ImportResult(total=1, succeeded=0, failed=1)
        service = WorldBundleService(self.db, container.world_service(),
            [WorldSectionHandler(container.world_service()), SeedLibraries(), FailingEntity()])
        fixture = json.loads((Path(__file__).resolve().parents[2] / "fixtures/world_defaults_test.json").read_text(encoding="utf-8"))
        data = {"world": fixture["world"], "relief_templates": [_relief_body("meadow")], "states": []}
        results, rolled_back = await service.import_bundle(data)
        self.assertTrue(rolled_back)
        self.assertEqual(results["relief_templates"].succeeded, 1)
        self.assertIsNone(await self.worlds.get_by_id(data["world"]["world_uid"]))
        self.assertEqual(await self.packs.list_all(), [])
        self.assertEqual(await self.relief_rows.list_all(), [])
