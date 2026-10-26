"""Scoped pack finalization, actual-root caches and atomic manifest publication."""

from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from test_library_packs_4b import _ServiceCase
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldColumnResolve import resolve_world_column
from app.application.worldData.errors import WorldDataNotFoundError, WorldDataValidationError
from app.application.worldData.pack.bake.finalize import packBakeFinalize
from app.application.worldData.pack.bake.finalize.packBakeFinalize import finalize_pack_on_world
from app.application.worldData.pack.bake.finalize.packBakePublisher import PackBakePublisher
from app.application.worldData.pack.io import packManifestStore
from app.application.worldData.pack.io.packManifestStore import PackManifestStore
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.core.appSettings import app_settings
from app.dataModel.worldPack.wire.worldMapCellsPerTile import WorldMapCellsPerTilePolicy
from app.dataModel.worldPack.meta.worldMapResolutionSettings import (
    WorldMapResolutionSettings, validate_world_row_map_resolution_columns,
)
from app.dataModel.worldPack.meta.worldPackMetadata import WorldPackMetadata, validate_world_row_pack_metadata_columns
from app.db.models.world import World
from app.db.repositories.iWorldRepository import IWorldRepository


class PackPublisherConfigurationTests(unittest.TestCase):
    def test_incomplete_publication_dependencies_fail_at_construction(self):
        dependencies = dict(db=MagicMock(), world_repository=MagicMock(), publication_guard=MagicMock())
        for missing in dependencies:
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, "pack publication requires"):
                PackBakePublisher(**(dependencies | {missing: None}))


class PackWorldWireTests(unittest.TestCase):
    def test_l0_override_keeps_existing_int_conversion_and_runtime_clamp(self):
        policy = WorldMapCellsPerTilePolicy.canonical_defaults()
        for raw in (None, 32, 64, 0, -3, True, False, 32.75, "64"):
            with self.subTest(raw=raw):
                expected = None if raw is None else int(raw)
                wire = {"world_map_cells_per_tile": raw}
                model = WorldMapResolutionSettings.model_validate(wire)
                self.assertEqual(model.world_map_cells_per_tile, expected)
                self.assertEqual(resolve_world_column("world_map_cells_per_tile", raw, ResolveContext()),
                                 {"world_map_cells_per_tile": expected})
                self.assertEqual(normalize_world(wire)["world_map_cells_per_tile"], expected)
                self.assertEqual(policy.resolve_side(model.world_map_cells_per_tile),
                                 32 if expected is None else max(1, expected))

    def test_nullable_metadata_missing_patch_and_independent_columns(self):
        self.assertEqual(WorldPackMetadata.canonical_defaults().model_dump(),
                         {"terrain_pack_path": None, "terrain_pack_hash": None})
        self.assertIsNone(WorldMapResolutionSettings.canonical_defaults().world_map_cells_per_tile)
        self.assertNotIn("terrain_pack_path", normalize_world({}, partial=True))
        self.assertEqual(resolve_world_column("terrain_pack_path", None, ResolveContext()),
                         {"terrain_pack_path": None})
        validate_world_row_map_resolution_columns(World)
        validate_world_row_pack_metadata_columns(World)
        for key, raw in (("terrain_pack_hash", 42), ("terrain_pack_path", {}),
                         ("world_map_cells_per_tile", "invalid")):
            with self.subTest(key=key), self.assertRaises(ImportValidationError) as caught:
                resolve_world_column(key, raw, ResolveContext())
            self.assertEqual(caught.exception.errors[0].path, (key,))
            self.assertTrue(caught.exception.errors[0].schema_id)


class PackFinalizeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db_path = str(self.root / "game.db")
        self.world = World("w1", "Original", "2026-10-16")
        self.current = deepcopy(self.world)
        self.current.name = "Edited during bake"
        self.current.material_registry = [42]
        self.current.terrain_pack_version = "untouched"
        self.repo = AsyncMock(spec=IWorldRepository)
        self.repo.get_by_id.side_effect = lambda uid: deepcopy(self.current)
        self.writer = WorldPackWriter(WorldPackPaths.from_db_parent(self.db_path, "w1"))
        self.context = PackReadContext("w1", db_path=self.db_path)

    async def finalize(self):
        return await finalize_pack_on_world(self.repo, self.world, self.writer,
                                            db_path=self.db_path, read_context=self.context)

    def prime_cache(self, root):
        key = str(root.resolve())
        reader = SimpleNamespace(invalidate_manifest=MagicMock())
        self.context._readers[key] = reader
        self.context._climate_cache[key] = None
        self.context._climate_tile_cache[(key, 0, 0)] = None
        return reader

    async def test_finalization_is_scoped_fresh_one_save_and_idempotent_hash(self):
        before = deepcopy(self.current)
        reader = self.prime_cache(self.writer.paths.root)
        with patch.object(self.writer, "recalc_manifest_counters",
                          wraps=self.writer.recalc_manifest_counters) as recalc:
            updated = await self.finalize()
        recalc.assert_called_once()
        self.repo.update.assert_awaited_once_with(updated)
        self.assertEqual(updated.name, "Edited during bake")
        self.assertEqual(updated.material_registry, [42])
        self.assertEqual(updated.terrain_pack_version, "untouched")
        self.assertEqual(updated.fine_cells_per_map_cell, before.fine_cells_per_map_cell)
        self.assertEqual(updated.world_map_cells_per_tile, 32)
        self.assertEqual(updated.terrain_pack_path, "worlds/w1/pack")
        manifest = PackManifestStore().load(self.writer.paths.manifest_path())
        self.assertEqual(updated.terrain_pack_hash, manifest.content_hash)
        self.assertEqual(self.current, before)
        reader.invalidate_manifest.assert_called_once()
        self.assertEqual(self.context._climate_cache, {})
        self.assertEqual(self.context._climate_tile_cache, {})
        self.current = updated
        self.assertEqual((await self.finalize()).terrain_pack_hash, manifest.content_hash)

    async def test_explicit_manifest_side_is_persisted(self):
        self.writer.manifest.world_map_cells_per_tile = 64
        updated = await self.finalize()
        self.assertEqual(updated.world_map_cells_per_tile, 64)

    async def test_existing_custom_reference_is_preserved(self):
        self.current.terrain_pack_path = "custom/w1"
        self.writer = WorldPackWriter(WorldPackPaths.for_world(self.current, self.db_path))
        updated = await self.finalize()
        self.assertEqual(updated.terrain_pack_path, "custom/w1")
        self.assertEqual(WorldPackPaths.for_world(updated, self.db_path).root, self.writer.paths.root)

    async def test_new_custom_root_roundtrips_and_invalidates_both_roots(self):
        old_root = self.writer.paths.root
        old_reader = self.prime_cache(old_root)
        self.writer = WorldPackWriter(WorldPackPaths.from_pack_root(self.root / "custom", "w1"))
        new_reader = self.prime_cache(self.writer.paths.root)
        updated = await self.finalize()
        self.assertEqual(WorldPackPaths.for_world(updated, self.db_path).root, self.writer.paths.root)
        old_reader.invalidate_manifest.assert_called_once()
        new_reader.invalidate_manifest.assert_called_once()
        self.assertEqual(self.context._climate_cache, {})
        self.assertEqual(self.context._climate_tile_cache, {})

    async def test_configured_worlds_root_keeps_portable_reference(self):
        with patch.object(app_settings, "world_pack_root", str(self.root / "packs")):
            self.writer = WorldPackWriter(WorldPackPaths.from_db_parent(self.db_path, "w1"))
            updated = await self.finalize()
            self.assertEqual(updated.terrain_pack_path, "packs/w1/pack")
            self.assertEqual(WorldPackPaths.for_world(updated, self.db_path).root, self.writer.paths.root)

    async def test_sql_failure_keeps_readable_manifest_clears_caches_and_never_logs_success(self):
        reader = self.prime_cache(self.writer.paths.root)
        self.repo.update.side_effect = OSError("SQL failed")
        with patch(packBakeFinalize.__name__ + ".log_pack_finalize") as log:
            with self.assertRaisesRegex(OSError, "SQL failed"):
                await self.finalize()
            log.assert_not_called()
        self.assertTrue(PackManifestStore().load(self.writer.paths.manifest_path()).content_hash)
        reader.invalidate_manifest.assert_called_once()
        self.assertEqual(self.context._climate_cache, {})
        self.assertIsNone(self.current.terrain_pack_path)

    async def test_file_replace_failure_preserves_old_manifest_and_never_saves_world(self):
        self.writer.save_manifest()
        before = self.writer.paths.manifest_path().read_bytes()
        self.writer.manifest.bake_mode = "full"
        with patch(packManifestStore.__name__ + ".os.replace",
                   side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                await self.finalize()
        self.assertEqual(self.writer.paths.manifest_path().read_bytes(), before)
        self.assertEqual(PackManifestStore().load(self.writer.paths.manifest_path()).bake_mode, "light")
        self.assertEqual(list(self.writer.paths.root.glob("manifest.json.*.tmp")), [])
        self.repo.update.assert_not_awaited()

    async def test_invalid_authored_side_fails_before_manifest_publication(self):
        self.writer.manifest.world_map_cells_per_tile = "invalid"
        with self.assertRaises(ImportValidationError):
            await self.finalize()
        self.assertFalse(self.writer.paths.manifest_path().exists())
        self.repo.update.assert_not_awaited()

    async def test_invalid_authored_metadata_never_saves_world_and_still_invalidates(self):
        reader = self.prime_cache(self.writer.paths.root)
        with patch.object(self.writer, "pack_storage_path", return_value=42):
            with self.assertRaises(ImportValidationError) as caught:
                await self.finalize()
        self.assertEqual(caught.exception.errors[0].path, ("terrain_pack_path",))
        self.repo.update.assert_not_awaited()
        reader.invalidate_manifest.assert_called_once()

    async def test_identity_mismatch_and_missing_world_have_no_file_side_effects(self):
        for target in (self.writer.paths, self.writer.manifest):
            with self.subTest(target=type(target).__name__):
                target.world_uid = "other"
                with self.assertRaises(WorldDataValidationError):
                    await self.finalize()
                target.world_uid = "w1"
        self.repo.get_by_id.side_effect = None
        self.repo.get_by_id.return_value = None
        with self.assertRaises(WorldDataNotFoundError):
            await self.finalize()
        self.assertFalse(self.writer.paths.manifest_path().exists())
        self.repo.update.assert_not_awaited()


class PackFinalizeSqlTests(_ServiceCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from tests.cache.test_admission import configured
        settings = patch.object(app_settings, "planning", configured())
        settings.start()
        self.addCleanup(settings.stop)
        self.addCleanup(self.container.shutdown_planning)

    async def test_container_repository_wiring_and_caller_rollback(self):
        world = await self._world("w1")
        orchestrator = self.container.pack_materialization_orchestrator()
        publisher = self.container.pack_bake_publisher()
        self.assertIs(orchestrator._publisher, publisher)
        self.assertIs(publisher._world_repository, self.container.world_repository())
        self.assertIs(publisher._db, self.db)
        self.assertIs(orchestrator._entry, self.container.entry_refine_orchestrator())
        self.assertIs(orchestrator._climate, self.container.entry_refine_orchestrator().climate_bake)
        surface = self.container.surface_materialization_orchestrator()
        self.assertIs(surface._pack, orchestrator)
        self.assertIs(surface._relief_loader, self.container.template_snapshot_loader())
        self.assertIs(surface._detailed._relief_loader, surface._relief_loader)
        self.assertIs(surface._detailed._relief_grade_repo, self.container.relief_grade_repository())
        writer = WorldPackWriter(WorldPackPaths.from_db_parent(self.db.path, "w1"))
        with self.assertRaisesRegex(ValueError, "caller failed"):
            async with self.db.transaction():
                await finalize_pack_on_world(self.worlds, world, writer, db_path=self.db.path)
                self.assertIsNotNone((await self.worlds.get_by_id("w1")).terrain_pack_hash)
                raise ValueError("caller failed")
        self.assertIsNone((await self.worlds.get_by_id("w1")).terrain_pack_hash)
        self.assertTrue(writer.paths.manifest_path().is_file())
