"""Unit: RELIEF-T-7 domain root reject; T-14 schedule hole → SLOPE."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.application.worldData.generators.terrain.relief.pick.gradePass import grade_from_template
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
    resolve_relief_domain_root,
)
from app.dataModel.terrain.relief import ReliefTemplate
from app.dataModel.terrain.relief.enums import ReliefSideKind


class ReliefDebtFollowupTest(unittest.IsolatedAsyncioTestCase):
    async def test_import_path_rejects_outside_domain_root(self) -> None:
        repo = MagicMock()
        svc = ReliefTemplateLibraryService(repo=repo)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "relief_templates"
            root.mkdir()
            outsider = Path(tmp) / "other" / "x.json"
            outsider.parent.mkdir()
            outsider.write_text("{}", encoding="utf-8")
            with self.assertRaises(ReliefValidationError) as ctx:
                await svc.import_path(outsider, domain_root=root)
            self.assertIn("outside relief domain root", str(ctx.exception))

    def test_resolve_domain_root_default_cwd(self) -> None:
        root = resolve_relief_domain_root()
        self.assertEqual(root.name, "relief_templates")

    def test_schedule_hole_safe_slope(self) -> None:
        """Mode B with gap between bands → SLOPE fallback (RELIEF-T-14)."""
        tpl = ReliefTemplate.model_validate({
            "system_name": "gappy",
            "display_name": "Gappy",
            "context": "road_shoulder",
            "conditions": [{
                "terrain": "plains",
                "cases": [
                    {
                        "policy": "slope_down",
                        "bands": [
                            {
                                "delta_z_min": 1,
                                "delta_z_max": 1,
                                "slope_weight": 1.0,
                                "sheer_weight": 0.0,
                            },
                            {
                                "delta_z_min": 5,
                                "delta_z_max": None,
                                "slope_weight": 0.0,
                                "sheer_weight": 1.0,
                            },
                        ],
                    },
                    {
                        "policy": "slope_up",
                        "bands": [
                            {
                                "delta_z_min": 1,
                                "delta_z_max": None,
                                "slope_weight": 1.0,
                                "sheer_weight": 0.0,
                            },
                        ],
                    },
                    {"policy": "slope_none", "bands": []},
                ],
            }],
        })
        decision = grade_from_template(
            template=tpl,
            template_uid="uid",
            terrain_key="plains",
            dz=3,
            world_seed="s",
            site_id="site",
        )
        self.assertFalse(decision.skipped)
        self.assertEqual(decision.kind, ReliefSideKind.SLOPE)
        self.assertEqual(decision.reason, "schedule_hole_safe_slope")


if __name__ == "__main__":
    unittest.main()
