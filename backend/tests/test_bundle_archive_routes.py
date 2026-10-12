"""C-4 HTTP transport against the production bundle service and temporary SQL."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from app.api.deps import get_container
from app.api.routes.worlds import router
from app.application.worldData.bundle.archive import BundleArchiveError, read_archive, write_archive
from app.core.container import Container
from app.dataModel.worldBundle.bundleManifest import BundleKind, BundleLibraryPackSource, BundleManifest
from app.dataModel.worldBundle.libraryArchive import LibraryArchiveManifest, LibraryArchivePack
from app.db.database import Database


class BundleArchiveRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = Database(str(self.root / "worlds.sqlite"))
        await self.db.connect()
        self.addAsyncCleanup(self.db.disconnect)
        await self.db.apply_migrations()
        self.container = Container(None, self.db)
        self.service = self.container.world_bundle_service()
        self.worlds = self.container.world_service()
        fixture = Path(__file__).resolve().parents[2] / "fixtures/world_test.json"
        self.bundle = json.loads(fixture.read_text(encoding="utf-8"))
        self.uid = self.bundle["world"]["world_uid"]
        self.archive = self.root / "input.wpack"
        self.service.write_archive(self.bundle, path=self.archive)
        self.json_path = self.root / "input.json"
        self.json_path.write_text(json.dumps(self.bundle), encoding="utf-8")
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_container] = lambda: self.container
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def send(self, path, *, upload, query=""):
        if upload:
            # Deliberately unrelated suffix/MIME: detection must use bytes.
            return await self.client.post(
                f"/worlds/import{query}",
                files={"file": ("input.bin", path.read_bytes(), "application/octet-stream")},
            )
        return await self.client.post(f"/worlds/import{query}", data={"path": str(path)})

    async def test_formats_and_sources_validate_without_writes(self):
        for path in (self.archive, self.json_path):
            for upload in (True, False):
                with self.subTest(format=path.suffix, upload=upload):
                    response = await self.send(path, upload=upload, query="?validate_only=true")
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json(), {"validate_only": True, "valid": True, "issues": []})
                    self.assertEqual(await self.worlds.get_all(), [])

    async def test_formats_and_sources_import_with_existing_copy_behavior(self):
        for path in (self.archive, self.json_path):
            for upload in (True, False):
                response = await self.send(path, upload=upload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertNotIn("rolled_back", response.json())
        worlds = await self.worlds.get_all()
        self.assertEqual(len(worlds), 4)
        self.assertEqual(len({w.world_uid for w in worlds}), 4)
        self.assertIn(self.uid, {w.world_uid for w in worlds})

    async def test_download_preview_levels_and_round_trip(self):
        await self.service.import_bundle(self.bundle)
        expected = await self.service.export(self.uid)
        for level in ("registry", "skeleton"):
            preview = await self.client.get(f"/worlds/{self.uid}/export?level={level}")
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.headers["content-type"], "application/json")
            self.assertNotIn("content-disposition", preview.headers)
            response = await self.client.get(f"/worlds/{self.uid}/export?level={level}&download=true")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "application/zip")
            self.assertIn(f'world_{self.uid}.wpack', response.headers["content-disposition"])
            self.assertTrue(response.content.startswith(b"PK\x03\x04"))
            downloaded = self.root / f"{level}.wpack"
            downloaded.write_bytes(response.content)
            contents = read_archive(downloaded)
            self.assertEqual(contents.sections, preview.json())
            self.assertEqual(contents.manifest.source.world_uid, self.uid)
            self.assertEqual(set(contents.sections), {"world"} if level == "registry" else set(expected))
            result = await self.send(downloaded, upload=True, query=f"?level={level}")
            self.assertEqual(result.status_code, 200, result.text)
        copies = [w for w in await self.worlds.get_all() if w.world_uid != self.uid]
        # Registry copy has no child sections; the final copy is skeleton.
        skeleton = next(w for w in copies if w.name.endswith(" v2"))
        exported = await self.service.export(skeleton.world_uid)
        self.assertEqual(set(exported), set(expected))
        for key, uid_field in (("states", "state_uid"), ("locations", "location_uid")):
            self.assertEqual(len(exported[key]), len(expected[key]))
            self.assertTrue(exported[key])
            self.assertTrue({row[uid_field] for row in exported[key]}.isdisjoint(
                row[uid_field] for row in expected[key]))
            self.assertEqual(
                [row.get("name") for row in exported[key]],
                [row.get("name") for row in expected[key]],
            )
        for key in ("relief_templates", "building_templates", "race_templates", "perk_templates"):
            self.assertEqual(exported[key], expected[key])

    async def test_archive_errors_and_wrong_kind_are_422_without_writes(self):
        broken = self.root / "broken.wpack"
        broken.write_bytes(b"PK\x03\x04broken")
        manifest = BundleManifest(
            kind=BundleKind.LIBRARY_PACK, format_version=1, sections={},
            source=BundleLibraryPackSource(
                kind=BundleKind.LIBRARY_PACK, pack_uid="pack-test", exporter="test",
                exported_at="2026-10-12T00:00:00Z",
            ),
        )
        foreign = self.root / "library.wpack"
        pack = LibraryArchivePack(LibraryArchiveManifest.model_validate({
            "pack_uid": "pack-test", "system_name": "test", "pack_name": "test",
            "display_name": "Test", "members": [{
                "library_kind": "relief_templates", "local_uid": "hill", "template_uid": "hill-uid",
            }],
        }), {"hill-uid": {"system_name": "hill"}})
        write_archive({}, manifest, path=foreign, library_packs=[pack])
        for path in (broken, foreign):
            for upload in (True, False):
                response = await self.send(path, upload=upload)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(await self.worlds.get_all(), [])

    async def test_source_errors_and_non_object_json(self):
        response = await self.client.post("/worlds/import")
        self.assertEqual(response.status_code, 400)
        response = await self.client.post(
            "/worlds/import", data={"path": str(self.archive)}, files={"file": ("x", b"{}")},
        )
        self.assertEqual(response.status_code, 400)
        response = await self.client.post("/worlds/import", data={"path": str(self.root / "missing")})
        self.assertEqual(response.status_code, 404)
        response = await self.client.post("/worlds/import", data={"path": str(self.root)})
        self.assertEqual(response.status_code, 400)
        for payload in (b"[]", b"invalid json"):
            response = await self.client.post("/worlds/import", files={"file": ("x", payload)})
            self.assertEqual(response.status_code, 422)

    async def test_library_transport_is_not_silently_discarded_before_4d(self):
        pack = LibraryArchivePack(LibraryArchiveManifest.model_validate({
            "pack_uid": "pack-test", "system_name": "test", "pack_name": "test",
            "display_name": "Test", "members": [{
                "library_kind": "relief_templates", "local_uid": "hill", "template_uid": "hill-uid",
            }],
        }), {"hill-uid": {"system_name": "hill"}})
        manifest = read_archive(self.archive).manifest
        packed = self.root / "with-libraries.wpack"
        write_archive(self.bundle, manifest, path=packed, library_packs=[pack])
        for upload in (True, False):
            response = await self.send(packed, upload=upload, query="?validate_only=true")
            self.assertEqual(response.status_code, 422, response.text)
            self.assertIn("4d", response.json()["detail"])
            self.assertEqual(await self.worlds.get_all(), [])

    async def test_upload_temporary_cleanup_on_success_and_decode_failure(self):
        paths = []
        original = self.service.read_archive

        def capture(path):
            paths.append(path)
            self.assertTrue(path.is_file())
            return original(path)

        with patch("app.application.worldData.worldBundleService.WorldBundleService.read_archive", side_effect=capture):
            response = await self.send(self.archive, upload=True, query="?validate_only=true")
            self.assertEqual(response.status_code, 200, response.text)
            broken = self.root / "broken.wpack"
            broken.write_bytes(b"PK\x03\x04broken")
            response = await self.send(broken, upload=True)
            self.assertEqual(response.status_code, 422)
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertFalse(path.parent.exists())
        self.assertTrue(self.archive.exists())

    async def test_export_temporary_cleanup_after_response_and_writer_failure(self):
        await self.service.import_bundle(self.bundle)
        paths = []
        original = self.service.write_archive

        def capture(sections, *, path):
            paths.append(path)
            return original(sections, path=path)

        target = "app.application.worldData.worldBundleService.WorldBundleService.write_archive"
        with patch(target, side_effect=capture):
            response = await self.client.get(f"/worlds/{self.uid}/export?download=true")
            self.assertEqual(response.status_code, 200, response.text)

        def fail(sections, *, path):
            paths.append(path)
            path.write_bytes(b"partial")
            raise BundleArchiveError("writer failure")

        with patch(target, side_effect=fail):
            with self.assertRaises(BundleArchiveError):
                await self.client.get(f"/worlds/{self.uid}/export?download=true")
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertFalse(path.parent.exists())
