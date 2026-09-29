"""Debug route contract without starting a server or using a database."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from app.api.routes.debug import debug_generate_structure_rotations, _LogCapture
from app.application.worldData.debugStructureRotations import generate_rotations, RotationProbe
from app.application.worldData.generators.structure.errors import GenerationError
from app.dataModel.spatial.facing import Facing
from tests.test_structure_orientation import simple_structure, test_world_building


class DebugStructureRotationsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.structure = simple_structure()
        self.world, self.building = test_world_building()
        self.plot = {
            "system_name": "00000000-0000-4000-8000-000000000004",
            "display_name": "Plot",
            "main_building": {"structure": str(self.structure.system_name)},
        }
        self.plots = SimpleNamespace(find_by_uid=AsyncMock(return_value=SimpleNamespace(data=self.plot)))
        self.worlds = SimpleNamespace(get_by_id=AsyncMock(return_value=self.world))
        self.container = SimpleNamespace(
            building_template_library_service=lambda: self.plots,
            world_service=lambda: self.worlds,
            structure_template_library_service=lambda: SimpleNamespace(list_all=AsyncMock(return_value=[])),
        )

    async def call_route(self, **kwargs):
        with patch("app.api.routes.debug.JsonResolver.resolve", AsyncMock(return_value=self.plot)), patch(
            "app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults.assemble_structure_catalog",
            return_value=Mock(resolve=Mock(return_value=self.structure)),
        ):
            return await debug_generate_structure_rotations(
                self.world.world_uid, file=None, path=None, container=self.container, **kwargs,
            )

    async def test_json_and_plot_uid_return_four_equivalent_grids(self):
        for kwargs in ({}, {"plot_uid": self.plot["system_name"]}):
            response = await self.call_route(**kwargs)
            data = json.loads(response.body)
            self.assertEqual(set(data["rotations"]), {"north", "east", "south", "west"})
            for side, result in data["rotations"].items():
                self.assertEqual(result["status"], "ok")
                self.assertTrue(result["grids"])
                self.assertTrue(data["equivalence"][side]["matches"])
                self.assertIn("width", result["rooms"][0])
        self.plots.find_by_uid.assert_awaited_once_with(self.plot["system_name"])

    async def test_missing_references_and_empty_plot(self):
        self.plots.find_by_uid.return_value = None
        with self.assertRaises(HTTPException) as error:
            await self.call_route(plot_uid="missing")
        self.assertEqual(error.exception.status_code, 404)
        self.worlds.get_by_id.return_value = None
        with self.assertRaises(HTTPException) as error:
            await self.call_route()
        self.assertEqual(error.exception.status_code, 404)
        self.worlds.get_by_id.return_value = self.world
        self.structure = None
        with self.assertRaises(HTTPException) as error:
            await self.call_route()
        self.assertEqual(error.exception.status_code, 422)
        self.plot.pop("main_building")
        with self.assertRaises(HTTPException) as error:
            await self.call_route()
        self.assertEqual(error.exception.status_code, 422)

    def test_error_on_one_side_does_not_hide_other_sides(self):
        generate = RotationProbe.generate_from_template

        def selective_failure(probe, *args, **kwargs):
            if kwargs.get("facing") == Facing.NORTH:
                raise GenerationError("north fixture failure")
            return generate(probe, *args, **kwargs)

        with patch.object(RotationProbe, "generate_from_template", selective_failure):
            data = generate_rotations(self.world, self.building, self.structure, None, _LogCapture)
        self.assertEqual(data["rotations"]["north"]["status"], "error")
        self.assertIsNone(data["equivalence"]["north"]["matches"])
        for side in ("east", "south", "west"):
            self.assertEqual(data["rotations"][side]["status"], "ok")
            self.assertTrue(data["equivalence"][side]["matches"])
