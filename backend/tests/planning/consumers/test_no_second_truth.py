"""PC-9 keeps generic planning neutral and publication at operation boundaries."""

import ast
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.planning.consumers.test_wiring import Composition, capture, world


APP = Path(__file__).resolve().parents[3] / "app"


class BoundaryTests(unittest.TestCase):
    def test_preparing_metadata_never_materializes_any_lod_on_miss_hit_or_edit(self):
        from dataclasses import replace
        from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry
        from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture
        from tests.planning.consumers.test_wiring import Wait

        c = Composition()
        self.addCleanup(c.service.shutdown)
        entry = SurfacePlanningEntry(c.assembler, SurfacePlanningCapture())
        source = world()
        with ExitStack() as stack:
            for target in (
                "pack.bake.l0.worldMapBakeOrchestrator.WorldMapBakeOrchestrator.bake_tiles",
                "materialize.terrain.terrainBatchOrchestrator.TerrainBatchOrchestrator.build_tile_surface_state",
                "pack.refine.fine.chunk.fineChunkRunner.FineChunkRunner.refine_rects",
                "pack.io.worldPackWriter.WorldPackWriter.write_world_map_tile",
                "pack.io.worldPackWriter.WorldPackWriter.write_wilderness_chunk",
                "pack.io.worldPackWriter.WorldPackWriter.save_manifest",
            ):
                stack.enter_context(patch("app.application.worldData." + target,
                    side_effect=AssertionError("metadata preparation materialized: " + target)))
            first, first_working = entry.require_plan_inputs(source, [], wait=Wait())
            hit, hit_working = entry.require_plan_inputs(source, [], wait=Wait())
            edited, _ = entry.require_plan_inputs(replace(source, z_max=60), [], wait=Wait())
        self.assertEqual(first, hit)
        self.assertIsNot(first_working, hit_working)
        self.assertNotEqual(first.view_revision, edited.view_revision)

    def test_snapshot_todo_belongs_to_outline_read_boundary_and_runner_has_no_state_io(self):
        root = APP / "application/worldData"
        outline = (root / "pack/read/wildernessRegionReadService.py").read_text(encoding="utf-8")
        self.assertLess(outline.index("TODO(snapshot)"), outline.index("if self.get_snapshot"))
        self.assertIn("world-state-crud-transition.md, section 7", outline)
        entry = (root / "pack/refine/entry/entryRefineOrchestrator.py").read_text(encoding="utf-8")
        self.assertNotIn("TODO(snapshot)", entry)
        runner = ast.parse((root / "pack/refine/fine/chunk/fineChunkRunner.py").read_text(encoding="utf-8"))
        for node in ast.walk(runner):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn("repositories", node.module or "")
                self.assertNotIn("regionStateSnapshot", node.module or "")
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else "")
                self.assertNotIn(name, {"load_region_state_snapshot", "get_by_world", "get_many",
                    "require_plan_inputs", "capture_view", "prepare_captured"})

    def test_surface_observations_have_one_typed_channel_and_no_production_legacy_symbols(self):
        from dataclasses import fields
        from app.application.worldData.regions.factConsumers.context import FactConsumerContext
        from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
        self.assertEqual([field.name for field in fields(FactConsumerContext)],
                         ["cells", "climate", "terrain", "hydrology"])
        self.assertNotIn("surface_planning", {field.name for field in fields(LightGridBakeContext)})
        banned = {"SurfaceTerrainContext", "to_legacy_context", "prepare_captured_context",
                  "prepare_surface_terrain_context", "require_surface_terrain_context",
                  "prepare_landcover_inputs_legacy"}
        for path in (APP / "application/worldData").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self.assertNotIn(node.name, banned, str(path))
                elif isinstance(node, ast.Name):
                    self.assertNotIn(node.id, banned, str(path))
                elif isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, banned | {"surface_planning"}, str(path))
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn("surfaceTerrainContext", node.module or "", str(path))

    def test_landcover_collection_raster_fine_and_outline_have_no_transitive_pack_dependency(self):
        from collections import deque

        def module_path(name):
            path = APP.parent.joinpath(*name.split("."))
            if path.with_suffix(".py").is_file():
                return path.with_suffix(".py")
            if (path / "__init__.py").is_file():
                return path / "__init__.py"
            return None

        dependencies = {}

        def imports(name):
            if name in dependencies:
                return dependencies[name]
            path = module_path(name)
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            parts = name.split(".")
            found = {".".join(parts[:i]) for i in range(1, len(parts))}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        package = name if path.name == "__init__.py" else name.rsplit(".", 1)[0]
                        parts = package.split(".")
                        prefix = ".".join(parts[:len(parts) - node.level + 1])
                        owner = ".".join(part for part in (prefix, node.module) if part)
                    else:
                        owner = node.module or ""
                    found.add(owner)
                    found.update(owner + "." + alias.name for alias in node.names)
            dependencies[name] = {item for item in found if item.startswith("app.") and module_path(item)}
            return dependencies[name]

        roots = ["app.application.worldData.generators.terrain.landcover." + name
                 for name in ("types", "materializer", "collect", "finePaint")]
        roots += ["app.application.worldData." + name for name in (
            "masks.collection.defaultCollect", "masks.regionRasterContext", "masks.regionRasterizer",
            "regions.coverageBackground", "regions.inputs.landcoverInputs", "regions.factConsumers",
            "render.regions.regionOutline")]
        for root in roots:
            seen, queue = set(), deque([(root,)])
            while queue:
                chain = queue.popleft()
                name = chain[-1]
                if name in seen:
                    continue
                seen.add(name)
                self.assertFalse(name.startswith("app.application.worldData.pack"), " -> ".join(chain))
                queue.extend(chain + (dependency,) for dependency in imports(name) if dependency not in seen)

    def test_frozen_view_has_no_generator_imports(self):
        module = APP / "application/worldData/planning/contracts/surfacePlanningView.py"
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn("generators", node.module or "")

    def test_local_climate_import_is_top_level_and_pole_kernel_has_one_owner(self):
        from app.application.worldData.generators.climate import poleResolve
        from app.application.worldData.generators.climate.planning import basePoleLayout, climatePlanProvider
        for name in ("autoresolve_base_poles", "manual_base_pole"):
            self.assertIs(getattr(poleResolve, name), getattr(basePoleLayout, name))
            self.assertIs(getattr(climatePlanProvider, name), getattr(basePoleLayout, name))
        module = APP / "application/worldData/generators/climate/planning/climatePlanProvider.py"
        tree = ast.parse(module.read_text(encoding="utf-8"))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            and node.module == "app.application.worldData.generators.climate.localFieldFromCoarse"]
        self.assertEqual(len(imports), 1)
        self.assertIn(imports[0], tree.body)

    def test_lower_refine_persist_never_publishes_or_checkpoints(self):
        module = APP / "application/worldData/pack/refine/fine/chunk/fineChunkPersist.py"
        tree = ast.parse(module.read_text(encoding="utf-8"))
        calls = [node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        self.assertNotIn("save_manifest", calls)
        self.assertNotIn("maybe_checkpoint_manifest", calls)
        self.assertIn("recalc_manifest_counters", calls)
        for relative in ("pack/refine/fine/chunk/fineChunkRunner.py", "pack/refine/chunks/chunkRefineWorker.py",
                         "pack/refine/entry/entryRefineOrchestrator.py", "pack/bake/detailed/packDetailedBakeOrchestrator.py"):
            source = (APP / "application/worldData" / relative).read_text(encoding="utf-8")
            self.assertNotIn("save_manifest(", source, relative)
            self.assertNotIn("publish_manifest", source, relative)

    def test_standalone_entry_route_publishes_after_optional_background_work(self):
        tree = ast.parse((APP / "api/routes/map.py").read_text(encoding="utf-8"))
        for entry in (node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)):
            work = [node for node in ast.walk(entry) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == "refine_from_entry"]
            if not work:
                continue
            for statement in ast.walk(entry):
                if isinstance(statement, ast.If) and isinstance(statement.test, ast.Name) and statement.test.id == "schedule_bg":
                    nested = [node for node in ast.walk(statement) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == "finalize_pack_on_world"]
                    self.assertEqual(nested, [], "entry publication must also happen when schedule_bg is false")
            finalize = [node for node in ast.walk(entry) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "finalize_pack_on_world"]
            self.assertEqual(len(finalize), 1)
            self.assertIn("db_path", {keyword.arg for keyword in finalize[0].keywords})

    def test_generic_planning_and_cache_import_no_world_domains(self):
        for root in (APP / "application" / "planning", APP / "application" / "cache"):
            for module in root.rglob("*.py"):
                tree = ast.parse(module.read_text(encoding="utf-8-sig"))
                for node in ast.walk(tree):
                    names = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                        [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                    for name in names:
                        self.assertFalse(any(part in name for part in ("worldData", "hydrology", "climate", "terrain", "surfacePlanning")),
                            (str(module), name))

    def test_capture_calls_no_planning_or_cache_and_does_not_mutate_source(self):
        with patch("app.application.planning.service.planningService.PlanningService.get_or_build",
                   side_effect=AssertionError("capture must not plan")), patch(
                   "app.application.worldData.generators.climate.planning.climatePlanProvider.build_climate_base",
                   side_effect=AssertionError("capture must not construct poles")):
            self.assertIsNotNone(capture(world()))

    def test_providers_and_assembler_run_after_live_source_is_discarded(self):
        c = Composition()
        self.addCleanup(c.service.shutdown)
        view = capture(world())
        with patch("app.application.jsonValidation.worldRow.hydrology", side_effect=AssertionError("live read")), patch(
                   "app.application.jsonValidation.worldRow.climate_scalars", side_effect=AssertionError("live read")):
            bundle = c.prepare(view)
        self.assertIsNotNone(bundle)

    def test_typed_entry_delegates_preparation_and_keeps_one_report_boundary(self):
        source = (APP / "application/worldData/planning/composition/surfacePlanningEntry.py").read_text(encoding="utf-8")
        self.assertIn("prepare_captured_bundle", source)
        for obsolete in ("run_surface_pass_coarse", "run_pole_resolve_pass", "hydrology_generator",
                         "apply_relief_objects_z", "apply_declared_fine_river_carves"):
            self.assertNotIn(obsolete, source)

    def test_surface_boundary_imports_only_public_apis_from_other_owners(self):
        root = APP / "application/worldData/planning"
        for module in root.rglob("*.py"):
            tree = ast.parse(module.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse(any(alias.name.startswith("_") for alias in node.names),
                        (str(module), node.module))

    def test_contracts_and_wiring_do_not_declare_dependency_metadata(self):
        root = APP / "application/worldData/planning"
        for relative in ("composition/planProviders.py", "contracts/surfacePlanBundle.py"):
            source = (root / relative).read_text(encoding="utf-8-sig")
            self.assertNotIn("surface.pc.", source)
            self.assertNotIn("SchemaVersion(1)", source)
            self.assertNotIn("AlgorithmVersion(1)", source)


if __name__ == "__main__":
    unittest.main()


class GameplayReadBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_then_existing_layers_then_merge_without_planning_or_writes(self):
        from tempfile import TemporaryDirectory
        from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
        from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
        from app.application.worldData.pack.read.packReadServices import build_pack_read_services
        from app.application.worldData.mapCells.patchStoreService import PatchStoreService
        from app.application.worldData.mapCells.mapCellQueryFacade import MapCellQueryFacade
        from app.dataModel.worldPack import FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun, WorldMapCellWire
        from app.dataModel.worldPack.wire.mergeMapCells import CellContribution
        from app.dataModel.worldPack.bake.layerPriority import MapLayerKind

        source = world(fine_cells_per_map_cell=2, terrain_chunk_columns=1)
        with TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "read.db")
            writer = WorldPackWriter(WorldPackPaths.from_db_parent(db_path, source.world_uid))
            writer.write_world_map_tile(0, 0,
                [WorldMapCellWire(tx=x, ty=0, surface_z=0, system_terrain="plains") for x in range(2)],
                cells_per_side=2)
            writer.write_wilderness_chunk(0, 0, FineTerrainChunkWire(cx=0, cy=0, chunk_columns=1,
                columns=[FineTerrainColumnWire(lx=0, ly=0,
                    runs=[FineTerrainZRun(z0=0, z1=0, system_terrain="forest")])]), refine_role="scene")
            writer.save_manifest()
            services = build_pack_read_services(source.world_uid, PatchStoreService(), db_path=db_path)
            reader = services.context.reader_for(source)
            before = {path: path.read_bytes() for path in writer.paths.root.rglob("*") if path.is_file()}
            events = []

            def record(label, fn):
                def call(*args, **kwargs):
                    events.append(label)
                    return fn(*args, **kwargs)
                return call

            with ExitStack() as stack:
                stack.enter_context(patch.object(MapCellQueryFacade, "_chunk_refine_role",
                    side_effect=record("metadata", MapCellQueryFacade._chunk_refine_role)))
                stack.enter_context(patch.object(reader, "chunk_exists", side_effect=record("exists", reader.chunk_exists)))
                stack.enter_context(patch.object(reader, "read_wilderness_chunk",
                    side_effect=record("fine", reader.read_wilderness_chunk)))
                stack.enter_context(patch.object(services.gameplay, "merge_layer_batches",
                    wraps=services.gameplay.merge_layer_batches))
                for target in (
                    "planning.composition.surfacePlanningEntry.SurfacePlanningEntry.require_plan_inputs",
                    "planning.composition.surfacePlanningCapture.SurfacePlanningCapture.capture",
                    "pack.refine.fine.chunk.fineChunkRunner.FineChunkRunner.refine_rects",
                    "pack.io.worldPackWriter.WorldPackWriter.write_wilderness_chunk",
                    "pack.io.worldPackWriter.WorldPackWriter.write_world_map_tile",
                    "pack.io.worldPackWriter.WorldPackWriter.save_manifest",
                ):
                    stack.enter_context(patch("app.application.worldData." + target,
                        side_effect=AssertionError("read invoked write/planning: " + target)))
                views = await services.gameplay.get_cells(source, {(0, 0, 0): None, (1, 0, 0): None})
                self.assertEqual(events, ["metadata", "exists", "fine", "metadata", "exists"])
                self.assertEqual([view.system_terrain for view in views], ["forest", "plains"])
                self.assertEqual([view.source_layer for view in views], [MapLayerKind.PLAYER_SCENE, MapLayerKind.WORLD_MAP])
                services.gameplay.merge_layer_batches.assert_awaited_once()
                patched = await services.gameplay.get_cell(source, 0, 0, 0,
                    patch=CellContribution(x=0, y=0, z=0, system_terrain="swamp"))
                self.assertEqual(patched.system_terrain, "swamp")
                self.assertEqual(patched.source_layer, MapLayerKind.PATCH)
            self.assertEqual(before, {path: path.read_bytes() for path in writer.paths.root.rglob("*") if path.is_file()})


class L2BoundaryTests(unittest.TestCase):
    def test_refine_transits_have_no_legacy_context_or_planning_entry(self):
        root = APP / "application/worldData"
        paths = ("pack/bake/detailed/packDetailedBakeOrchestrator.py", "pack/bake/detailed/detailedBakeRefine.py",
            "pack/refine/fine/chunk/fineChunkRunner.py", "pack/refine/fine/prep/fineTilePrep.py",
            "pack/refine/fine/prep/fineTileContext.py", "pack/refine/fine/chunk/fineChunkCompute.py",
            "pack/refine/fine/fineScenePathRefine.py", "pack/refine/fine/fineRectDrain.py",
            "pack/refine/entry/entryRefineOrchestrator.py",
            "pack/refine/chunks/chunkRefineWorker.py", "generators/terrain/landcover/finePaint.py",
            "pack/climate/climatePackBakeOrchestrator.py", "materialize/terrain/terrainBatchOrchestrator.py")
        for path in paths:
            text = (root / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("SurfaceTerrainContext", text)
                self.assertNotIn("to_legacy_context", text)
                self.assertNotIn("prepare_captured", text)
                self.assertNotIn("surface_ctx", text)
                if "landcover/finePaint" in path:
                    self.assertIn("LandcoverCollectContext", text)
                    self.assertIn("LandcoverInputs", text)
                    self.assertNotIn("SurfacePlanBundle", text)
                elif "fineChunkCompute" not in path:
                    self.assertIn("SurfacePlanBundle", text)
        route = (APP / "api/routes/map.py").read_text(encoding="utf-8")
        self.assertEqual(route.count("require_plan_inputs("), 3)
        for call in ast.walk(ast.parse(route)):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr in {
                    "refine_from_entry", "schedule_chunk_refine", "refine_queued_chunk", "drain_persisted"}:
                keywords = {keyword.arg for keyword in call.keywords}
                self.assertIn("working", keywords)
                self.assertIn("region_state_snapshot", keywords)
        self.assertNotIn("require_surface_terrain_context", route)

    def test_terrain_batch_has_single_l2_zone(self):
        import inspect
        module = APP / "application/worldData/materialize/terrain/terrainBatchOrchestrator.py"
        text = module.read_text(encoding="utf-8")
        for removed in ("map_cells", "MapCellService", "save_z_slice", "generate_z_slice",
                "plan_bootstrap_tiles", "prepare_surface_terrain_context", "run_pole_resolve_pass",
                "SurfacePlanningEntry", "SurfacePlanningAssembler", "SurfacePlanningCapture",
                "planning.composition", "ImportResult", "PlanWaitControl"):
            self.assertNotIn(removed, text)
        from app.application.worldData.materialize.terrain.terrainBatchOrchestrator import TerrainBatchOrchestrator
        params = list(inspect.signature(TerrainBatchOrchestrator.__init__).parameters)
        self.assertEqual(params, ["self", "generator"])
