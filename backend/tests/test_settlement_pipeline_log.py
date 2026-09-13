"""C11 / C23 wall timings — packBakeLog + SettlementPipelineTimings."""

from __future__ import annotations

import unittest

from app.application.worldData.generators.assemblers.settlementAssembler.timings import (
    SettlementAssembleTimings,
)
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_settlement_c11_done,
    log_pack_settlement_c11_start,
    log_pack_settlement_topology_done,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorOrchestrator import (
    MaterializeResult,
)
from app.application.worldData.settlementOutdoor.settlementPipelineTimings import (
    SettlementPipelineTimings,
    WallClock,
)


class SettlementPipelineTimingsTests(unittest.TestCase):
    def test_from_parts_copies_assemble_and_topology(self):
        assemble = SettlementAssembleTimings(
            cache_s=0.1, packing_s=1.5, area_s=2.25, generate_s=4.0,
        )
        topology = SettlementPipelineTimings(
            topo_slots_s=0.4, topo_streets_s=0.6, topology_s=1.2,
        )
        pipeline = SettlementPipelineTimings.from_parts(
            assemble=assemble,
            topology=topology,
            generate_s=4.1,
            sql_s=0.05,
            c11_s=8.0,
        )
        self.assertEqual(pipeline.assemble_packing_s, 1.5)
        self.assertEqual(pipeline.assemble_area_s, 2.25)
        self.assertEqual(pipeline.topo_streets_s, 0.6)
        self.assertEqual(pipeline.generate_s, 4.1)
        self.assertEqual(pipeline.sql_s, 0.05)
        d = pipeline.as_dict()
        self.assertIn("c11_s", d)
        self.assertNotIn("materialize_s", d)

    def test_wall_clock_laps(self):
        clock = WallClock()
        first = clock.lap()
        second = clock.lap()
        self.assertGreaterEqual(first, 0.0)
        self.assertGreaterEqual(second, 0.0)
        self.assertGreaterEqual(clock.total(), first + second)

    def test_materialize_result_omits_pipeline_when_absent(self):
        payload = MaterializeResult(location_uid="loc", status="published").to_dict()
        self.assertNotIn("c11_pipeline", payload)

    def test_materialize_result_includes_c11_pipeline(self):
        payload = MaterializeResult(
            location_uid="loc",
            status="published",
            pipeline_s=SettlementPipelineTimings(generate_s=1.25, c11_s=3.5),
        ).to_dict()
        self.assertEqual(payload["c11_pipeline"]["generate_s"], 1.25)
        self.assertEqual(payload["c11_pipeline"]["c11_s"], 3.5)


class SettlementPackBakeLogTests(unittest.TestCase):
    def test_c11_done_line_has_stage_keys(self):
        logger_name = "app.application.worldData.pack.bake.packBakeLog"
        with self.assertLogs(logger_name, level="INFO") as cm:
            log_pack_settlement_c11_start("w1", location_uid="loc-city")
            log_pack_settlement_c11_done(
                "w1",
                location_uid="loc-city",
                status="published",
                pipeline=SettlementPipelineTimings(
                    generate_s=1.5, sql_s=0.2, encode_s=0.3, c11_s=4.0,
                ),
                districts=3,
                buildings=12,
                encode_bytes=4096,
            )
        text = "\n".join(cm.output)
        self.assertIn("pack settlement c11 start", text)
        self.assertIn("pack settlement c11 done", text)
        self.assertIn("generate_s=1.50", text)
        self.assertIn("sql_s=0.20", text)
        self.assertIn("encode_s=0.30", text)
        self.assertIn("c11_s=4.00", text)
        self.assertIn("encode_bytes=4096", text)
        self.assertNotIn("materialize_s=", text)

    def test_topology_done_line_has_stage_keys(self):
        logger_name = "app.application.worldData.pack.bake.packBakeLog"
        with self.assertLogs(logger_name, level="INFO") as cm:
            log_pack_settlement_topology_done(
                "w1",
                location_uid="loc-city",
                status="planned",
                pipeline=SettlementPipelineTimings(
                    topo_slots_s=0.4, topo_streets_s=0.8, topology_s=1.5,
                ),
                districts=3,
                gates=2,
            )
        text = "\n".join(cm.output)
        self.assertIn("pack settlement topology done", text)
        self.assertIn("topo_streets_s=0.80", text)
        self.assertIn("topology_s=1.50", text)


if __name__ == "__main__":
    unittest.main()
