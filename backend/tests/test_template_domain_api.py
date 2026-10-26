"""A7 HTTP: target kinds, negotiated archives and legacy converter diagnostics."""
import json

import httpx
from fastapi import FastAPI

from test_library_packs_4b import _ServiceCase
from template_domain_transport_fixture import create_graph, S, B, P
from app.api.deps import get_container
from app.api.errorMapping import install_error_handlers
from app.api.routes.libraryPacks import router as packs_router
from app.api.routes.libraryArchives import router as archives_router
from app.api.routes.worlds import router as worlds_router


class TemplateDomainApiTests(_ServiceCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        app = FastAPI()
        install_error_handlers(app)
        for router in (packs_router, archives_router, worlds_router):
            app.include_router(router)
        app.dependency_overrides[get_container] = lambda: self.container
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def _world(self, world_uid):
        return await self.container.world_service().create({"world_uid": world_uid, "name": world_uid,
                                                           "created_at": "2026-10-14"})

    async def post_world(self, data, *, validate=False):
        return await self.client.post("/worlds/import", params={"validate_only": str(validate).lower()},
            files={"file": ("world.json", json.dumps(data), "application/json")})

    async def test_authored_target_kinds_share_member_api_and_preview_stale_replace(self):
        pack = await self.service.create_pack(system_name="http.target")
        url = f"/library-packs/{pack.pack_uid}/members"
        response = await self.client.post(url, json={"library_kind": S.value, "local_uid": "geometry",
                                                   "body": {"display_name": "Geometry"}})
        self.assertEqual(response.status_code, 200, response.text)
        structure = response.json()["items"][0]["members"][0]
        for kind, body in ((B, {"structure": structure}), (P, {"main_building": {"structure": structure}})):
            payload = {"library_kind": kind.value, "local_uid": "same", "body": {"display_name": "Original", **body}}
            first = await self.client.post(url, json=payload)
            self.assertEqual(first.status_code, 200, first.text)
            uid = first.json()["items"][0]["members"][0]
            preview = await self.client.post(url, json=payload)
            self.assertEqual(preview.status_code, 409, preview.text)
            payload.update(preview_token=preview.json()["preview_token"],
                decisions=[{"item_key": "0", "policy": "replace", "target_uid": uid}])
            payload["body"]["display_name"] = "Changed"
            trace = []
            await self.db.main_conn.set_trace_callback(trace.append)
            try:
                stale = await self.client.post(url, json=payload)
            finally:
                await self.db.main_conn.set_trace_callback(None)
            self.assertEqual(stale.status_code, 409, stale.text)
            self.assertTrue(stale.json()["stale"])
            self.assertFalse(any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in trace))
            payload["preview_token"] = stale.json()["preview_token"]
            applied = await self.client.post(url, json=payload)
            self.assertEqual(applied.status_code, 200, applied.text)
            self.assertEqual(applied.json()["items"][0]["members"], [uid])
            read = await self.client.get(f"/library-members/{uid}")
            self.assertEqual(read.json()["body"]["display_name"], "Changed")

    async def test_engine_archive_http_copy_needs_no_world_and_remaps_all_kinds(self):
        pack, _, structure, building, plot, duplicate = await create_graph(self)
        exported = await self.client.get(f"/library-packs/{pack.pack_uid}/export")
        self.assertEqual(exported.status_code, 200, exported.text if exported.status_code != 200 else "")
        preview = await self.client.post("/library-packs/import", files={"file": ("graph.wpack", exported.content)})
        self.assertEqual(preview.status_code, 409, preview.text)
        applied = await self.client.post("/library-packs/import", files={"file": ("graph.wpack", exported.content)},
            data={"preview_token": preview.json()["preview_token"], "decisions": json.dumps([
                {"item_key": pack.pack_uid, "policy": "copy", "copy_system_name": "http.copy"}])})
        self.assertEqual(applied.status_code, 200, applied.text)
        item = applied.json()["items"][0]
        mapping = item["uid_map"]
        self.assertEqual(len(mapping), 4)
        self.assertEqual((await self.service.read_member_body(mapping[building.template_uid]))["structure"], mapping[structure.template_uid])
        self.assertEqual((await self.service.read_member_body(mapping[plot.template_uid]))["secondary_buildings"][0]["structure"], mapping[structure.template_uid])
        self.assertIsNone((await self.packs.get_by_uid(item["pack_uid"])).owner_world_uid)
        self.assertFalse(await self.worlds.get_all())

    async def test_world_http_roundtrip_keeps_graph_world_owned_and_duplicate_local_names(self):
        await self._world("source")
        await create_graph(self, owner="source", separate=True)
        data = await self.container.world_bundle_service().export("source")
        response = await self.post_world(data)
        self.assertEqual(response.status_code, 200, response.text)
        copied = next(w for w in await self.worlds.get_all() if w.world_uid != "source")
        packs = await self.packs.list_world_owned(copied.world_uid)
        members = await self.members.list_by_packs([p.pack_uid for p in packs])
        self.assertEqual(len(members), 4)
        self.assertEqual({m.local_uid for m in members}, {"same"})
        self.assertFalse(await self.packs.list_engine())

    async def test_engine_archive_import_into_empty_library_preserves_member_uids(self):
        pack, _, structure, building, plot, duplicate = await create_graph(self)
        exported = await self.client.get(f"/library-packs/{pack.pack_uid}/export")
        await self.service.delete_pack(pack.pack_uid)
        self.assertFalse(await self.packs.list_all())
        response = await self.client.post("/library-packs/import",
            files={"file": ("graph.wpack", exported.content)})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(set(response.json()["items"][0]["members"]),
                         {m.template_uid for m in (structure, building, plot, duplicate)})
        self.assertFalse(await self.worlds.get_all())

    async def test_valid_modern_graph_validate_only_performs_no_sql(self):
        await self._world("source")
        await create_graph(self, owner="source", separate=True)
        data = await self.container.world_bundle_service().export("source")
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            response = await self.post_world(data, validate=True)
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(trace, [])

    async def test_wrong_kind_local_identity_and_legacy_shape_are_422_without_bodies(self):
        pack = await self.service.create_pack(system_name="http.invalid")
        url = f"/library-packs/{pack.pack_uid}/members"
        for payload in (
            {"library_kind": "unknown", "local_uid": "x", "body": {}},
            {"library_kind": P.value, "local_uid": "x", "body": {"system_name": "other", "display_name": "Other"}},
            {"library_kind": B.value, "local_uid": "x", "body": {"display_name": "Plot", "main_building": None}}):
            result = await self.client.post(url, json=payload)
            self.assertEqual(result.status_code, 422, result.text)
        self.assertFalse(await self.members.list_by_pack(pack.pack_uid))

    async def test_flat_body_section_is_rejected_without_creating_world(self):
        data = {"world": {"world_uid": "legacy", "name": "Legacy", "created_at": "2026-10-14"},
                "building_templates": [{"system_name": "house", "display_name": "House"}]}
        validation = await self.post_world(data, validate=True)
        self.assertEqual(validation.status_code, 200, validation.text)
        self.assertFalse(validation.json()["valid"])
        response = await self.post_world(data)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertTrue(any(i["loc"] == ["library_packs"] for i in response.json()["detail"]))
        self.assertFalse(await self.worlds.get_all())
        self.assertFalse(await self.packs.list_all())

    async def test_empty_flat_plot_section_is_rejected_without_creating_library(self):
        data = {"world": {"world_uid": "empty", "name": "Empty", "created_at": "2026-10-14"},
                "plot_templates": []}
        response = await self.post_world(data)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertFalse(await self.worlds.get_all())
        self.assertFalse(await self.packs.list_all())
