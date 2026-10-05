"""§6.8: an unavailable attachment host is ERROR; generation continues."""
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.generationLogging import generation_world_log
from app.application.worldData.generators.structure.layoutEngine import (
    _layout_mode_b, _spiral_search, _try_adjacent, _place_next_to_any,
)
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from tests.structureWire import room_wire
from tests.test_structure_orientation import simple_structure, test_world_building
from tests.test_u_shape_orientation_baseline import room

LAYOUT = "app.application.worldData.generators.structure.layoutEngine"


class HostNotPlacedTests(unittest.TestCase):
    def test_missing_and_unplaced_host_log_error_and_skip_attached_rooms(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                host = room("host", x=None, y=None)
                guest = room("guest", x=None, y=None)
                guest.attach_to = host.room_id
                placed = [] if missing else [host]
                with self.assertLogs(LAYOUT, level="WARNING") as captured:
                    _layout_mode_b([host, guest], placed, staircases=[],
                                   building_uid="test", world_uid="w")
                self.assertEqual(len(captured.records), 1)
                self.assertEqual(captured.records[0].levelno, logging.ERROR)
                self.assertIn("host='host' not placed", captured.records[0].getMessage())
                self.assertIn("skipping 1 attached room(s)", captured.records[0].getMessage())
                self.assertFalse(guest.placed)
                self.assertFalse(host.placed)
                self.assertEqual(placed, [] if missing else [host])

    def test_generate_finishes_and_error_reaches_transcript_when_host_cannot_fit(self):
        world, building = test_world_building()
        template = simple_structure()
        template.levels[0]["rooms"].extend([
            room_wire(room_id="host", required=False, count_range=[1, 1]),
            room_wire(room_id="guest", attach_to="host", attach_wall="both"),
        ])
        observed = {}

        def no_host_space(candidate, placed, origin):
            # Exercise the existing optional-room fit failure, keeping the entry room.
            if candidate.room_id == "host":
                return False
            return _spiral_search(candidate, placed, origin)

        def capture_mode_b(rooms, *args, **kwargs):
            _layout_mode_b(rooms, *args, **kwargs)
            observed.update({r.room_id: r.placed for r in rooms})

        def try_adjacent(candidate, *args):
            return False if candidate.room_id == "host" else _try_adjacent(candidate, *args)

        def place_next(candidate, *args):
            return False if candidate.room_id == "host" else _place_next_to_any(candidate, *args)

        with tempfile.TemporaryDirectory() as directory:
            with generation_world_log(world.world_uid, mode="test", root=directory) as path:
                with patch(LAYOUT + "._spiral_search", side_effect=no_host_space), \
                     patch(LAYOUT + "._try_adjacent", side_effect=try_adjacent), \
                     patch(LAYOUT + "._place_next_to_any", side_effect=place_next), \
                     patch(LAYOUT + "._layout_mode_b", side_effect=capture_mode_b):
                    result = StructureGeneratorService().generate_from_template(world, building, template)
            records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]
        self.assertTrue(result.cells)
        self.assertEqual(observed, dict(hall=True, host=False, guest=False))
        diagnostics = [r for r in records if "host='host' not placed" in r["msg"]]
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["level"], "ERROR")
        self.assertEqual(diagnostics[0]["logger"], LAYOUT)
