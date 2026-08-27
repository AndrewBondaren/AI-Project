"""Golden 8-slot packs from generate SoT § Карты-эталоны.

Glyphs here are consume dump (tz_terrain_relief_consume § 3×3), not writer
input. Writer is ``pack_cell_slots``. Locked R44 maps are a different file.
"""

from __future__ import annotations

import re
import unittest

from app.application.worldData.pack.refine.gradeCellSlots import pack_cell_slots
from app.dataModel.terrain.relief.gradeLeftoverPair import (
    leftover_pair_is_sheer,
    leftover_pair_theta,
)
from app.dataModel.terrain.relief.gradeSlot import (
    GRADE_SLOT_COUNT,
    GradeCouple,
    GradeOctant,
    GradeSeam,
    GradeSheer,
    neighbor_cell,
)

# consume § Debug ASCII — код → глиф; порядок краёв NW N NE W E SW S SE.
_GLYPH_TO_CODE = {
    "↖": int(GradeOctant.NORTHWEST),
    "↑": int(GradeOctant.NORTH),
    "↗": int(GradeOctant.NORTHEAST),
    "←": int(GradeOctant.WEST),
    "→": int(GradeOctant.EAST),
    "↙": int(GradeOctant.SOUTHWEST),
    "↓": int(GradeOctant.SOUTH),
    "↘": int(GradeOctant.SOUTHEAST),
    ".": int(GradeSeam.SEAM),
    "┃": int(GradeSheer.SHEER),
    "+": int(GradeCouple.COUPLE),
}

_LABEL = re.compile(r"\((\d+),(\d+)\)=(\d+)")

# Leftover L=1 |Δz| — не knobs шаблона ``delta_z``. 1/2 = эталоны ТЗ; 5 = последний Octant; 6/10 = SHEER.
_PAIR_DZ = (1, 2, 5, 6, 10)

# docs/tz_terrain_relief.md § Яма 4 вокруг 2
_PIT_4_AROUND_2 = """
(0,2)=4          (1,2)=4          (2,2)=4

.  .  .          .  .  .          .  .  .
.  4  +          +  4  +          +  4  .
.  +  ↘          +  ↓  +          ↙  +  .


(0,1)=4          (1,1)=2          (2,1)=4

.  +  +          ↘  ↓  ↙          +  +  .
.  4  →          →  2  ←          ←  4  .
.  +  +          ↗  ↑  ↖          +  +  .


(0,0)=4          (1,0)=4          (2,0)=4

.  +  ↗          +  ↑  +          ↖  +  .
.  4  +          +  4  +          +  4  .
.  .  .          .  .  .          .  .  .
"""

# docs/tz_terrain_relief.md § Пул 3×3: склон 4|3|2 на восток
_POOL_EAST_4_3_2 = """
(0,2)=4          (1,2)=3          (2,2)=2

.  .  .          .  .  .          .  .  .
.  4  →          →  3  →          →  2  .
.  +  ↘          ↗  +  ↘          ↗  +  .


(0,1)=4          (1,1)=3          (2,1)=2

.  +  ↗          ↘  +  ↗          ↘  +  .
.  4  →          →  3  →          →  2  .
.  +  ↘          ↗  +  ↘          ↗  +  .


(0,0)=4          (1,0)=3          (2,0)=2

.  +  ↗          ↘  +  ↗          ↘  +  .
.  4  →          →  3  →          →  2  .
.  .  .          .  .  .          .  .  .
"""


def _tokens_nine(row: str) -> list[str]:
    parts = [p for p in re.split(r"\s{2,}", row.strip()) if p]
    if len(parts) != 9:
        raise AssertionError(f"expected 9 glyphs, got {parts!r} from {row!r}")
    return parts


def _slots_from_glyphs(nw_n_ne: list[str], w_z_e: list[str], sw_s_se: list[str]) -> tuple[int, ...]:
    glyphs = (
        nw_n_ne[0],
        nw_n_ne[1],
        nw_n_ne[2],
        w_z_e[0],
        w_z_e[2],
        sw_s_se[0],
        sw_s_se[1],
        sw_s_se[2],
    )
    return tuple(_GLYPH_TO_CODE[g] for g in glyphs)


def parse_tz_dump_map(text: str) -> tuple[dict[tuple[int, int], int], dict[tuple[int, int], tuple[int, ...]]]:
    """Labels + 3×3 dump glyphs → heightmap and expected slots[8]."""
    lines = [ln.rstrip() for ln in text.strip().splitlines()]
    z: dict[tuple[int, int], int] = {}
    expected: dict[tuple[int, int], tuple[int, ...]] = {}
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        labels = _LABEL.findall(lines[i])
        if not labels:
            i += 1
            continue
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        top = _tokens_nine(lines[i])
        mid = _tokens_nine(lines[i + 1])
        bot = _tokens_nine(lines[i + 2])
        i += 3
        for col, (xs, ys, zs) in enumerate(labels):
            xy = (int(xs), int(ys))
            z[xy] = int(zs)
            a, b = col * 3, col * 3 + 3
            expected[xy] = _slots_from_glyphs(top[a:b], mid[a:b], bot[a:b])
    return z, expected


def _packed(z: dict[tuple[int, int], int]) -> dict[tuple[int, int], tuple[int, ...]]:
    return {cell.cell: cell.slots for cell in pack_cell_slots(z)}


def _octant_to_sheer(slots: tuple[int, ...]) -> tuple[int, ...]:
    sheer = int(GradeSheer.SHEER)
    return tuple(sheer if 0 <= code <= int(GradeOctant.SOUTHEAST) else code for code in slots)


def _slots_for_pair_dz(
    expected: dict[tuple[int, int], tuple[int, ...]],
    dz: int,
) -> dict[tuple[int, int], tuple[int, ...]]:
    if not leftover_pair_is_sheer(abs(dz)):
        return expected
    return {xy: _octant_to_sheer(slots) for xy, slots in expected.items()}


def _pit_z(dz: int) -> dict[tuple[int, int], int]:
    return {
        (x, y): (0 if (x, y) == (1, 1) else dz)
        for x in range(3)
        for y in range(3)
    }


def _pool_east_z(dz: int) -> dict[tuple[int, int], int]:
    return {(x, y): (2 - x) * dz for x in range(3) for y in range(3)}


def _cascade_south_z(dz: int) -> dict[tuple[int, int], int]:
    return {(x, y): y * dz for x in range(3) for y in range(3)}


class TestPackTzEtalons(unittest.TestCase):
    def _assert_map(self, text: str) -> dict[tuple[int, int], int]:
        z, expected = parse_tz_dump_map(text)
        got = _packed(z)
        self.assertEqual(set(got), set(expected))
        for xy, slots in expected.items():
            self.assertEqual(got[xy], slots, msg=f"cell {xy}")
        self._assert_pair_ends(z, got)
        return z

    def _assert_pair_ends(
        self,
        z: dict[tuple[int, int], int],
        slots: dict[tuple[int, int], tuple[int, ...]],
    ) -> None:
        for xy, codes in slots.items():
            self.assertEqual(len(codes), GRADE_SLOT_COUNT)
            for position, code in enumerate(codes):
                nb = neighbor_cell(xy, position)
                if nb not in z:
                    self.assertEqual(code, int(GradeSeam.SEAM), msg=f"{xy} pos {position}")
                    continue
                back = int(GradeOctant(position).opposite())
                self.assertEqual(code, slots[nb][back], msg=f"{xy}↔{nb}")

    def test_pit_four_around_two_all_nine_cells(self) -> None:
        z = self._assert_map(_PIT_4_AROUND_2)
        self.assertEqual(z[(1, 1)], 2)
        self.assertEqual(len(z), 9)
        # consume § Тело sidecar — яма (0,1)=4
        self.assertEqual(
            _packed(z)[(0, 1)],
            (8, 10, 10, 8, 4, 8, 10, 10),
        )
        floor = _packed(z)[(1, 1)]
        self.assertEqual(floor[4], int(GradeOctant.WEST))
        self.assertEqual(floor[3], int(GradeOctant.EAST))
        self.assertNotIn(int(GradeSheer.SHEER), floor)
        self.assertAlmostEqual(leftover_pair_theta(2), 63.43, places=1)

    def test_pit_four_around_three_same_directions(self) -> None:
        # generate: |dz|=1 (4 вокруг 3) — те же направления, θ=45°.
        text = _PIT_4_AROUND_2.replace("(1,1)=2", "(1,1)=3").replace("→  2  ←", "→  3  ←")
        z = self._assert_map(text)
        self.assertEqual(z[(1, 1)], 3)
        _, pit2 = parse_tz_dump_map(_PIT_4_AROUND_2)
        self.assertEqual(_packed(z), pit2)
        self.assertAlmostEqual(leftover_pair_theta(1), 45.0, places=1)

    def test_pool_east_four_three_two_all_nine_cells(self) -> None:
        z = self._assert_map(_POOL_EAST_4_3_2)
        packed = _packed(z)
        east = int(GradeOctant.EAST)
        # (0,2) EAST → приходит в (1,2) WEST тем же →
        self.assertEqual(packed[(0, 2)][4], east)
        self.assertEqual(packed[(1, 2)][3], east)
        # диагональ ↘ с (0,2) — в (1,1)
        self.assertEqual(packed[(0, 2)][7], int(GradeOctant.SOUTHEAST))
        self.assertEqual(packed[(1, 1)][0], int(GradeOctant.SOUTHEAST))
        # ↗ с верхней кромки в пул не существует (нет y=3) — шов
        self.assertEqual(packed[(0, 2)][2], int(GradeSeam.SEAM))
        self.assertEqual(packed[(1, 2)][1], int(GradeSeam.SEAM))

    def test_cascade_south_same_pair_rules_as_east_pool(self) -> None:
        # generate § Каскад вниз: pack как пул, ось SOUTH.
        z = {(x, y): 2 + y for x in range(3) for y in range(3)}
        packed = _packed(z)
        south = int(GradeOctant.SOUTH)
        couple = int(GradeCouple.COUPLE)
        seam = int(GradeSeam.SEAM)
        self.assertEqual(len(packed), 9)
        self._assert_pair_ends(z, packed)
        self.assertEqual(packed[(0, 2)][6], south)
        self.assertEqual(packed[(0, 1)][1], south)
        self.assertEqual(packed[(1, 2)][4], couple)
        self.assertEqual(packed[(2, 2)][4], seam)
        self.assertEqual(packed[(0, 2)][1], seam)
        self.assertEqual(packed[(0, 0)][6], seam)
        self.assertEqual(packed[(0, 2)][7], int(GradeOctant.SOUTHEAST))
        self.assertEqual(packed[(1, 1)][0], int(GradeOctant.SOUTHEAST))

    def test_mixed_heights_north_up_grid(self) -> None:
        # Север вверх, как эталоны ТЗ:
        # 10  2   6     y=2
        # 10  4   5     y=1
        # 11  1  -2     y=0
        seam, couple, sheer = int(GradeSeam.SEAM), int(GradeCouple.COUPLE), int(GradeSheer.SHEER)
        nw, n, w, e, sw, s = (
            int(GradeOctant.NORTHWEST),
            int(GradeOctant.NORTH),
            int(GradeOctant.WEST),
            int(GradeOctant.EAST),
            int(GradeOctant.SOUTHWEST),
            int(GradeOctant.SOUTH),
        )
        z = {
            (0, 2): 10, (1, 2): 2, (2, 2): 6,
            (0, 1): 10, (1, 1): 4, (2, 1): 5,
            (0, 0): 11, (1, 0): 1, (2, 0): -2,
        }
        expected = {
            (0, 2): (seam, seam, seam, seam, sheer, seam, couple, sheer),
            (1, 2): (seam, seam, seam, sheer, w, sheer, n, nw),
            (2, 2): (seam, seam, seam, w, seam, sw, s, seam),
            (0, 1): (seam, couple, sheer, seam, sheer, seam, n, sheer),
            (1, 1): (sheer, n, sw, sheer, w, sheer, s, sheer),
            (2, 1): (nw, s, seam, w, seam, sw, sheer, seam),
            (0, 0): (seam, n, sheer, seam, sheer, seam, seam, seam),
            (1, 0): (sheer, s, sw, sheer, e, seam, seam, seam),
            (2, 0): (sheer, sheer, seam, e, seam, seam, seam, seam),
        }
        packed = _packed(z)
        self.assertEqual(packed, expected)
        self._assert_pair_ends(z, packed)
        self.assertEqual(packed[(0, 2)][6], couple)
        self.assertEqual(packed[(0, 1)][1], couple)
        self.assertEqual(packed[(0, 2)][4], sheer)
        self.assertEqual(packed[(1, 2)][3], sheer)
        self.assertEqual(packed[(2, 1)][1], s)
        self.assertEqual(packed[(2, 2)][6], s)
        self.assertEqual(packed[(1, 0)][4], e)
        self.assertEqual(packed[(2, 0)][3], e)

    def test_pit_pool_cascade_for_each_pair_dz(self) -> None:
        _, pit_slots = parse_tz_dump_map(_PIT_4_AROUND_2)
        _, pool_slots = parse_tz_dump_map(_POOL_EAST_4_3_2)
        south = int(GradeOctant.SOUTH)
        southeast = int(GradeOctant.SOUTHEAST)
        couple = int(GradeCouple.COUPLE)
        seam = int(GradeSeam.SEAM)
        sheer = int(GradeSheer.SHEER)
        for dz in _PAIR_DZ:
            want_pit = _slots_for_pair_dz(pit_slots, dz)
            got_pit = _packed(_pit_z(dz))
            self.assertEqual(got_pit, want_pit, msg=f"pit dz={dz}")
            self._assert_pair_ends(_pit_z(dz), got_pit)

            want_pool = _slots_for_pair_dz(pool_slots, dz)
            got_pool = _packed(_pool_east_z(dz))
            self.assertEqual(got_pool, want_pool, msg=f"pool dz={dz}")
            self._assert_pair_ends(_pool_east_z(dz), got_pool)
            flow_e = sheer if leftover_pair_is_sheer(dz) else int(GradeOctant.EAST)
            self.assertEqual(got_pool[(0, 2)][4], flow_e, msg=f"pool dz={dz}")
            self.assertEqual(got_pool[(1, 2)][3], flow_e, msg=f"pool dz={dz}")

            z_south = _cascade_south_z(dz)
            got_south = _packed(z_south)
            self._assert_pair_ends(z_south, got_south)
            flow_s = sheer if leftover_pair_is_sheer(dz) else south
            flow_se = sheer if leftover_pair_is_sheer(dz) else southeast
            self.assertEqual(got_south[(0, 2)][6], flow_s, msg=f"cascade dz={dz}")
            self.assertEqual(got_south[(0, 1)][1], flow_s, msg=f"cascade dz={dz}")
            self.assertEqual(got_south[(1, 2)][4], couple, msg=f"cascade dz={dz}")
            self.assertEqual(got_south[(2, 2)][4], seam, msg=f"cascade dz={dz}")
            self.assertEqual(got_south[(0, 2)][7], flow_se, msg=f"cascade dz={dz}")
            self.assertEqual(got_south[(1, 1)][0], flow_se, msg=f"cascade dz={dz}")


class TestPackTzAngleStep(unittest.TestCase):
    def test_l1_pair_kind_for_each_dz(self) -> None:
        east = int(GradeOctant.EAST)
        sheer = int(GradeSheer.SHEER)
        for dz in _PAIR_DZ:
            packed = _packed({(0, 0): dz, (1, 0): 0})
            want = sheer if leftover_pair_is_sheer(dz) else east
            self.assertEqual(packed[(0, 0)][4], want, msg=f"dz={dz}")
            self.assertEqual(packed[(1, 0)][3], want, msg=f"dz={dz}")


if __name__ == "__main__":
    unittest.main()
