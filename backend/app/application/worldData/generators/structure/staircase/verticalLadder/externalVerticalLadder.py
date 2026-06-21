"""
External vertical ladder — лестница снаружи здания.
Наследует VerticalLadderBuilder, всегда on_the_edge=True, near_wall=True.
ТЗ: docs/tz_staircase_generation.md §8.1
"""
from __future__ import annotations

from app.application.worldData.generators.structure.staircase.surfaceCorridor import (
    SurfaceCorridorBuilder,
)
from app.application.worldData.generators.structure.staircase.undergroundTunnel import (
    UndergroundTunnelBuilder,
)
from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadder import (
    VerticalLadderBuilder,
)
from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadderValidator import (
    ExternalVerticalLadderValidator,
)


class ExternalVerticalLadderBuilder(VerticalLadderBuilder):
    _validator = ExternalVerticalLadderValidator()

    def build(self):
        entry = dict(self.sc_entry or {})
        entry["on_the_edge"] = True
        entry["near_wall"]   = True
        self.sc_entry = entry

        fr_anchor, to_anchor = super().build()

        if self.z_lo < 0:
            UndergroundTunnelBuilder(
                cells=self.cells,
                world_uid=self.world_uid,
                building_uid=self.building_uid,
                mat=self.mat,
                z_lo=self.z_lo,
                z_top=self.z_top,
                conn_label=self.conn_label,
                passage_height=self.passage_height,
            ).build(fr_anchor, set(self.fr.get_footprint()))

        # Если якорь не смежен с верхней комнатой — якорь за пределами здания,
        # нужен surface corridor вместо edge_ladder_passage
        to_fp = set(self.to.get_footprint())
        anchor_adjacent = any(
            (to_anchor[0] + dx, to_anchor[1] + dy) in to_fp
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
        if not anchor_adjacent and to_anchor not in to_fp:
            sc_id = (self.sc_entry or {}).get("staircase_id", "?")
            passage = SurfaceCorridorBuilder(
                cells=self.cells,
                world_uid=self.world_uid,
                building_uid=self.building_uid,
                mat=self.mat,
                z_top=self.z_top,
                conn_label=self.conn_label,
                passage_height=self.passage_height,
            ).build(to_anchor, self.to, self.to_level, sc_id=sc_id)
            if passage:
                self.extra_passages.append(passage)
            self.skip_edge_ladder = True

        return fr_anchor, to_anchor
