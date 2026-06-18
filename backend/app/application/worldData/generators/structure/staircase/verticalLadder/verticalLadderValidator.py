"""
Vertical ladder validator.
ТЗ: docs/tz_staircase_generation.md §8
"""
import logging

from app.application.worldData.generators.structure.staircase.validator import StaircaseValidator

logger = logging.getLogger(__name__)


class VerticalLadderValidator(StaircaseValidator):

    def _check_stair_path(self, stair_cells, cells, conn_label) -> None:
        pass

    def _check_anchor_xy(
        self,
        fr_anchor:  tuple[int, int],
        to_anchor:  tuple[int, int],
        conn_label: str,
    ) -> None:
        if fr_anchor != to_anchor:
            logger.error(
                "vertical_ladder %s [инвариант XY]: fr_anchor=%s ≠ to_anchor=%s",
                conn_label, fr_anchor, to_anchor,
            )

    def _check_fr_footprint(
        self,
        ax:           int,
        ay:           int,
        fr_footprint: set[tuple[int, int]] | None,
        on_the_edge:  bool,
        conn_label:   str,
    ) -> None:
        if not on_the_edge and fr_footprint is not None and (ax, ay) not in fr_footprint:
            logger.error(
                "vertical_ladder %s [fr_anchor footprint]: (%d,%d) вне footprint нижней комнаты",
                conn_label, ax, ay,
            )

    def _check_ladder_cell(
        self,
        ax:         int,
        ay:         int,
        z_top:      int,
        cells:      dict,
        conn_label: str,
    ) -> None:
        z_cell = z_top - 1
        cell   = cells.get((ax, ay, z_cell))
        got    = cell.system_building_element if cell else "пусто"
        if got != "ladder":
            logger.error(
                "vertical_ladder %s [ячейка]: (%d,%d,z=%d) должна быть 'ladder', получено %r",
                conn_label, ax, ay, z_cell, got,
            )

    def _check_top_cell(
        self,
        ax:           int,
        ay:           int,
        z_top:        int,
        cells:        dict,
        to_footprint: set[tuple[int, int]] | None,
        conn_label:   str,
    ) -> None:
        above      = cells.get((ax, ay, z_top))
        above_elem = above.system_building_element if above else "пусто"
        if above_elem not in ("floor", "trapdoor"):
            logger.error(
                "vertical_ladder %s [выход]: (%d,%d,z=%d) должна быть 'floor' или 'trapdoor', "
                "получено %r",
                conn_label, ax, ay, z_top, above_elem,
            )
        elif to_footprint is not None and (ax, ay) not in to_footprint:
            logger.error(
                "vertical_ladder %s [to_anchor footprint]: (%d,%d) вне footprint верхней комнаты",
                conn_label, ax, ay,
            )

    def validate(
        self,
        fr_anchor:    tuple[int, int],
        to_anchor:    tuple[int, int],
        z_lo:         int,
        z_top:        int,
        cells:        dict,
        conn_label:   str,
        fr_footprint: set[tuple[int, int]] | None = None,
        to_footprint: set[tuple[int, int]] | None = None,
        on_the_edge:  bool = False,
        **kwargs,
    ) -> None:
        ax, ay = fr_anchor
        self._check_anchor_xy(fr_anchor, to_anchor, conn_label)
        self._check_fr_footprint(ax, ay, fr_footprint, on_the_edge, conn_label)
        self._check_ladder_cell(ax, ay, z_top, cells, conn_label)
        self._check_top_cell(ax, ay, z_top, cells, to_footprint, conn_label)


class ExternalVerticalLadderValidator(VerticalLadderValidator):

    def _check_fr_footprint(self, ax, ay, fr_footprint, on_the_edge, conn_label) -> None:
        pass  # якорь всегда снаружи fr

    def _check_top_cell(self, ax, ay, z_top, cells, to_footprint, conn_label) -> None:
        pass  # якорь снаружи здания — floor/trapdoor на z_top не ожидается
