"""PC-9 keeps generic planning neutral and publication at operation boundaries."""

import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.planning.consumers.test_wiring import Composition, capture, world


APP = Path(__file__).resolve().parents[3] / "app"


class BoundaryTests(unittest.TestCase):
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
        module = APP / "application/worldData/pack/refine/fine/fineChunkPersist.py"
        tree = ast.parse(module.read_text(encoding="utf-8"))
        calls = [node.func.attr for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        self.assertNotIn("save_manifest", calls)
        self.assertNotIn("maybe_checkpoint_manifest", calls)
        self.assertIn("recalc_manifest_counters", calls)
        for relative in ("pack/refine/fine/fineChunkRunner.py", "pack/refine/chunks/chunkRefineWorker.py",
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

    def test_compatibility_entry_contains_no_domain_planning(self):
        source = (APP / "application/worldData/generators/terrain/passes/surfaceTerrainContext.py").read_text(encoding="utf-8")
        self.assertIn("SurfacePlanningAssembler", source)
        self.assertIn("prepare_captured_context", source)
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


class L2BoundaryTests(unittest.TestCase):
    def test_refine_transits_have_no_legacy_context_or_planning_entry(self):
        root = APP / "application/worldData"
        paths = ("pack/bake/detailed/packDetailedBakeOrchestrator.py", "pack/bake/detailed/detailedBakeRefine.py",
            "pack/refine/fine/fineChunkRunner.py", "pack/refine/fine/fineTilePrep.py",
            "pack/refine/fine/fineTileContext.py", "pack/refine/fine/fineChunkCompute.py",
            "pack/refine/fine/fineTerrainRefineOrchestrator.py", "pack/refine/entry/entryRefineOrchestrator.py",
            "pack/refine/chunks/chunkRefineWorker.py", "generators/terrain/landcover/finePaint.py",
            "pack/climate/climatePackBakeOrchestrator.py", "materialize/terrain/terrainBatchOrchestrator.py")
        for path in paths:
            text = (root / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("SurfaceTerrainContext", text)
                self.assertNotIn("to_legacy_context", text)
                self.assertNotIn("prepare_captured", text)
                self.assertNotIn("surface_ctx", text)
                if "fineChunkCompute" not in path:
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
