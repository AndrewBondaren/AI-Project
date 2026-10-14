"""4d/L-5: production archive/writer integration against real SQLite."""
import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from test_library_packs_4b import _ServiceCase, _relief_body, _plot_body
from app.api.deps import get_container
from app.api.errorMapping import install_error_handlers
from app.api.routes.libraryPacks import router as packs_router
from app.api.routes.libraryArchives import router as archives_router
from app.api.routes.worlds import router as worlds_router
from app.application.importResult import ImportResult
from app.application.worldData.bundle.archive import read_archive
from app.application.worldData.libraryPacks.archiveSources import pack_to_wire
from app.application.worldData.libraryPacks.errors import LibraryPackPolicyRequiredError
from app.application.worldData.libraryPacks.writeContracts import LibraryWriteSelection, WriteStatus
from app.ids import LibraryKind, library_uid, remapped_library_uid


class LibraryPacks4dTests(_ServiceCase):
    async def _world(self, world_uid):
        return await self.container.world_service().create({"world_uid": world_uid, "name": world_uid,
                                                           "created_at": "2026-10-10"})

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bundle = self.container.world_bundle_service()
        app = FastAPI()
        install_error_handlers(app)
        app.include_router(archives_router)
        app.include_router(packs_router)
        app.include_router(worlds_router)
        app.dependency_overrides[get_container] = lambda: self.container
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def world_pack(self):
        await self._world("source")
        pack = await self.service.create_pack(system_name="world.source.custom", owner_world_uid="source")
        member = await self.service.create_member(pack.pack_uid, library_kind="relief_templates",
            local_uid="meadow", body=_relief_body("meadow"), world_uid="source")
        world = await self.worlds.get_by_id("source")
        world.library_pins = [{"library_kind": "relief_templates", "template_uid": member.template_uid}]
        await self.worlds.update(world)
        return pack, member

    async def test_world_copy_round_trip_pins_and_same_local_members(self):
        pack, member = await self.world_pack()
        duplicate = await self.service.copy_member(member.template_uid, pack.pack_uid, world_uid="source")
        source = await self.bundle.export("source")
        self.assertIn("library_packs", source)
        self.assertNotIn("relief_templates", source)
        path = Path(self.tmp.name) / "world.wpack"
        self.bundle.write_archive(source, path=path)
        contents = read_archive(path)
        self.assertEqual(len(contents.library_packs[0].manifest.members), 2)
        self.assertNotIn("library_packs", contents.sections)
        data = self.bundle.read_archive(path)
        results, rolled_back = await self.bundle.import_bundle(data)
        self.assertFalse(rolled_back, results)
        copied = next(w for w in await self.worlds.get_all() if w.world_uid != "source")
        owned = await self.packs.list_world_owned(copied.world_uid)
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0].source_pack_uid, pack.pack_uid)
        members = await self.members.list_by_pack(owned[0].pack_uid)
        self.assertEqual(len(members), 2)
        self.assertEqual({m.local_uid for m in members}, {"meadow"})
        mapping = {m.source_template_uid: m.template_uid for m in members}
        self.assertEqual(set(mapping), {member.template_uid, duplicate.member.template_uid})
        self.assertEqual(copied.library_pins[0]["template_uid"], mapping[member.template_uid])
        self.assertEqual(await self.bundle.export("source"), source)
        self.assertEqual(await self.packs.list_engine(), [])
        second = await self.bundle.export(copied.world_uid)
        _, failed = await self.bundle.import_bundle(second)
        self.assertFalse(failed)
        self.assertEqual(len(await self.worlds.get_all()), 3)

    async def test_cross_pack_structure_refs_and_dependencies(self):
        await self._world("source")
        structure_pack = await self.service.create_pack(system_name="world.source.structures", owner_world_uid="source")
        kind = LibraryKind.STRUCTURE_TEMPLATES
        uid = library_uid(kind, "house", pack_uid=structure_pack.pack_uid)
        root = Path(__file__).resolve().parents[2] / "structures_templates/base"
        body = json.loads(next(p for p in sorted(root.glob("*.json")) if p.name != "pack.manifest.json").read_text(encoding="utf-8"))
        body["system_name"] = uid
        await self.service.create_member(structure_pack.pack_uid, library_kind=kind,
            local_uid="house", body=body, world_uid="source")
        plots = await self.service.create_pack(system_name="world.source.plots", owner_world_uid="source",
            dependencies=(structure_pack.pack_uid,))
        plot = await self.service.create_member(plots.pack_uid, library_kind="plot_templates",
            local_uid="home", body=_plot_body("home", uid), world_uid="source")
        _, rolled_back = await self.bundle.import_bundle(await self.bundle.export("source"))
        self.assertFalse(rolled_back)
        copied = next(w for w in await self.worlds.get_all() if w.world_uid != "source")
        packs = {p.source_pack_uid: p for p in await self.packs.list_world_owned(copied.world_uid)}
        member_uid = remapped_library_uid(kind, target_pack_uid=packs[structure_pack.pack_uid].pack_uid, source_template_uid=uid)
        plot_uid = remapped_library_uid(LibraryKind.PLOT_TEMPLATES,
            target_pack_uid=packs[plots.pack_uid].pack_uid, source_template_uid=plot.template_uid)
        self.assertEqual((await self.service.read_member_body(plot_uid))["main_building"]["structure"], member_uid)
        self.assertEqual(await self.deps.required_uids(packs[plots.pack_uid].pack_uid), {packs[structure_pack.pack_uid].pack_uid})

    async def test_later_entity_failure_rolls_back_new_world_and_library(self):
        await self.world_pack()
        data = await self.bundle.export("source")
        before = await self.packs.list_all()
        handler = next(h for h in self.bundle._handlers if h.key == "states")
        with patch.object(handler, "import_section", return_value=ImportResult(1, 0, 1)):
            _, rollback = await self.bundle.import_bundle(data)
        self.assertTrue(rollback)
        self.assertEqual([w.world_uid for w in await self.worlds.get_all()], ["source"])
        self.assertEqual(await self.packs.list_all(), before)

    async def test_world_preview_continuation_and_source_stale_are_atomic(self):
        pack, _ = await self.world_pack()
        data = await self.bundle.export("source")
        writer = self.service._write_service
        original = writer._policy.decide

        def require_selection(snapshot, request, **kwargs):
            decision = original(snapshot, request, **kwargs)
            if request.preview_token is None and not request.decisions:
                return replace(decision, status=WriteStatus.POLICY_REQUIRED, actions=())
            return decision

        with patch.object(writer._policy, "decide", side_effect=require_selection):
            with self.assertRaises(LibraryPackPolicyRequiredError) as first:
                await self.bundle.import_bundle(data)
            self.assertEqual(len(await self.worlds.get_all()), 1)
            token = first.exception.outcome.preview_token
            revised = deepcopy(data)
            revised["world"]["name"] = "Changed source"
            with self.assertRaises(LibraryPackPolicyRequiredError) as stale:
                await self.bundle.import_bundle(revised, preview_token=token)
            self.assertTrue(stale.exception.outcome.stale)
            self.assertEqual(len(await self.worlds.get_all()), 1)
            _, failed = await self.bundle.import_bundle(data, preview_token=token)
            self.assertFalse(failed)
            self.assertEqual(len(await self.worlds.get_all()), 2)
        with self.assertRaisesRegex(Exception, "token"):
            await self.bundle.import_bundle(data, preview_token=token[:-4] + "aaaa")

    async def test_engine_archive_import_replace_copy_stale_and_no_world(self):
        pack, members = await self._relief_engine_pack()
        path = Path(self.tmp.name) / "library.wpack"
        await self.service.archives.write_engine_archive(pack.pack_uid, path=path)
        preview = await self.client.post("/library-packs/import", data={"path": str(path)})
        self.assertEqual(preview.status_code, 409, preview.text)
        payload = preview.json()
        applied = await self.client.post("/library-packs/import", data={"path": str(path),
            "preview_token": payload["preview_token"], "decisions": json.dumps([
                {"item_key": pack.pack_uid, "policy": "replace", "target_uid": pack.pack_uid}])})
        self.assertEqual(applied.status_code, 200, applied.text)
        again = await self.client.post("/library-packs/import", data={"path": str(path)})
        copied = await self.client.post("/library-packs/import", data={"path": str(path),
            "preview_token": again.json()["preview_token"], "decisions": json.dumps([
                {"item_key": pack.pack_uid, "policy": "copy", "copy_system_name": "engine.copy"}])})
        self.assertEqual(copied.status_code, 200, copied.text)
        stale = await self.client.post("/library-packs/import", data={"path": str(path),
            "preview_token": again.json()["preview_token"]})
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertTrue(stale.json()["stale"])
        self.assertEqual(await self.worlds.get_all(), [])

    async def test_lifecycle_http_scopes_and_member_negotiation(self):
        await self._world("w1")
        pack = await self.client.post("/worlds/w1/library-packs", json={"system_name": "world.w1.custom"})
        self.assertEqual(pack.status_code, 201, pack.text)
        uid = pack.json()["pack_uid"]
        payload = {"library_kind": "relief_templates", "local_uid": "meadow", "body": _relief_body("meadow")}
        first = await self.client.post(f"/worlds/w1/library-packs/{uid}/members", json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        member = first.json()["items"][0]["members"][0]
        conflict = await self.client.post(f"/worlds/w1/library-packs/{uid}/members", json=payload)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        payload.update(preview_token=conflict.json()["preview_token"],
                       decisions=[{"item_key": "0", "policy": "replace", "target_uid": member}])
        applied = await self.client.post(f"/worlds/w1/library-packs/{uid}/members", json=payload)
        self.assertEqual(applied.status_code, 200, applied.text)
        forbidden = await self.client.patch(f"/library-packs/{uid}", json={"display_name": "Bad"})
        self.assertEqual(forbidden.status_code, 403)
        published = await self.client.post(f"/worlds/w1/library-packs/{uid}/publish", json={})
        self.assertEqual(published.status_code, 200, published.text)
        repeated = await self.client.post("/worlds/w1/library-packs/instantiate",
            json={"source_pack_uid": published.json()["pack"]["pack_uid"]})
        self.assertEqual(repeated.status_code, 200, repeated.text)

    async def test_deferred_metadata_and_invalid_identity_do_not_write(self):
        await self.world_pack()
        data = await self.bundle.export("source")
        for mutation in ("defaults", "identity"):
            invalid = deepcopy(data)
            manifest = invalid["library_packs"][0]["manifest"]
            if mutation == "defaults":
                manifest["defaults"] = {"relief_templates": "meadow"}
            else:
                manifest["pack_uid"] = "forged"
            response = await self.client.post("/worlds/import", files={"file": ("world.json", json.dumps(invalid))})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(len(await self.worlds.get_all()), 1)
