"""PC-9A stays dormant and cannot turn the generic engine into a world planner."""

import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.planning.consumers.test_wiring import Composition, capture, world


APP = Path(__file__).resolve().parents[3] / "app"


class BoundaryTests(unittest.TestCase):
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

    def test_production_callers_have_no_new_active_composition_path_yet(self):
        # The only production change before PC-9 is the context type re-export.
        source = (APP / "application/worldData/generators/terrain/passes/surfaceTerrainContext.py").read_text()
        self.assertNotIn("SurfacePlanningAssembler", source)
        self.assertIn("def prepare_surface_terrain_context", source)
        self.assertIn("run_surface_pass_coarse", source)

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
