"""E2E: TZ etalon heightmaps → L2 persist → pack dump render.

Same grids as ``test_pack_tz_slot_maps``. Mill/discover is not this path —
etalons are pack on a given ``z_height_map``. Persist is ``FineChunkPersist``
(wilderness chunk + ``SCH-GRADE-CELL-SLOTS``); dump is ``PackMapGridRender``.
"""

from __future__ import annotations

import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.refine.detailedGradeCatalog import catalog_for_surface
from app.application.worldData.pack.refine.fineChunkPersist import FineChunkPersist
from app.application.worldData.pack.refine.fineTileContext import (
    ChunkComputeResult,
    FineTileContext,
)
from app.application.worldData.pack.refine.gradeCellSlots import pack_cell_slots
from app.application.worldData.pack.read.packReadServices import build_pack_read_services
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.patchStoreService import PatchStoreService
from app.application.worldData.render.packMapGridRender import PackMapGridRender
from app.application.worldData.render.renderPayloads import LEVEL_SURFACE_GRADE, LEVEL_SURFACE_Z
from app.db.models.mapCell import MapCell
from app.db.models.world import World

from tests.test_pack_tz_slot_maps import (
    _PAIR_DZ,
    _PIT_4_AROUND_2,
    _POOL_EAST_4_3_2,
    _cascade_south_z,
    _pit_z,
    _pool_east_z,
    _slots_for_pair_dz,
    _slots_from_glyphs,
    parse_tz_dump_map,
)

_CHUNK = 32
_MID_ROW = re.compile(r"^ *(\d+) \|")


def _packed(z: dict[tuple[int, int], int]) -> dict[tuple[int, int], tuple[int, ...]]:
    return {cell.cell: cell.slots for cell in pack_cell_slots(z)}


def _world(uid: str) -> World:
    return World(world_uid=uid, name="slot-e2e", created_at="2026-08-28")


def _fields(line: str) -> list[str]:
    """Fixed-width dump cells after the y-gutter, before the trailing ``|``."""
    if "|" not in line:
        return []
    body = line.split("|", 1)[1]
    if body.endswith("|"):
        body = body[:-1]
    body = body.rstrip("\n")
    parts = body.split(" ")
    return [p[-3:] for p in parts if len(p) >= 3]


def slots_from_surface_grade_dump(
    ascii_grid: str,
) -> dict[tuple[int, int], tuple[int, ...]]:
    """Edge glyphs from consume 3×3 dump → ``slots[8]``. Center is terrain, not z."""
    lines = ascii_grid.splitlines()
    out: dict[tuple[int, int], tuple[int, ...]] = {}
    for i, line in enumerate(lines):
        hit = _MID_ROW.match(line)
        if hit is None or i == 0 or i + 1 >= len(lines):
            continue
        y = int(hit.group(1))
        top = _fields(lines[i - 1])
        mid = _fields(line)
        bot = _fields(lines[i + 1])
        if not (len(top) == len(mid) == len(bot)):
            raise AssertionError(
                f"dump band width mismatch y={y}: {len(top)}/{len(mid)}/{len(bot)}\n{ascii_grid}",
            )
        xs = _x_axis(lines, n_cells=len(mid))
        for col, x in enumerate(xs):
            glyphs_top = list(top[col])
            glyphs_mid = list(mid[col])
            glyphs_bot = list(bot[col])
            out[(x, y)] = _slots_from_glyphs(glyphs_top, glyphs_mid, glyphs_bot)
    return out


def _x_axis(lines: list[str], *, n_cells: int) -> list[int]:
    """``grid gx: 0..2`` from dump header — dump walks x0..x1 left to right."""
    for line in lines:
        hit = re.search(r"grid gx: (-?\d+)\.\.(-?\d+)", line)
        if hit is not None:
            x0, x1 = int(hit.group(1)), int(hit.group(2))
            xs = list(range(x0, x1 + 1))
            if len(xs) != n_cells:
                raise AssertionError(f"gx {x0}..{x1} vs {n_cells} dump cells")
            return xs
    return list(range(n_cells))


# tests.test_pack_tz_slot_maps has cascade as a local z dict, not a dump string.
_CASCADE_SOUTH_Z = {(x, y): 2 + y for x in range(3) for y in range(3)}

_MIXED_Z = {
    (0, 2): 10, (1, 2): 2, (2, 2): 6,
    (0, 1): 10, (1, 1): 4, (2, 1): 5,
    (0, 0): 11, (1, 0): 1, (2, 0): -2,
}


class TestPackTzSlotL2RenderE2e(unittest.TestCase):
    def _persist_and_render(
        self,
        z_map: dict[tuple[int, int], int],
        *,
        uid: str,
    ):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = str(Path(tmp.name) / "game.db")
        world = _world(uid)
        paths = WorldPackPaths.from_db_parent(db_path, uid)
        writer = WorldPackWriter(paths)
        bbox = ColumnRect(0, _CHUNK - 1, 0, _CHUNK - 1)
        ctx = FineTileContext(
            world=world,
            locations=[],
            surface_ctx=MagicMock(),
            tile_gx=0,
            tile_gy=0,
            meter_bbox=bbox,
            chunk_size=_CHUNK,
            surface_state=MagicMock(),
            templates={},
            grade_halo=0,
            existing_uids={},
            catalog=catalog_for_surface(
                world, bbox, tile_gx=0, tile_gy=0, chunk_size=_CHUNK,
            ),
            workers=1,
            refine_role="scene",
            phase_name="e2e",
            world_uid=uid,
            chunks_total=1,
            location_pairs=[],
            volumes=[],
        )
        persist = FineChunkPersist(ctx, writer)
        cells = [
            MapCell(
                world_uid=uid, x=x, y=y, z=z_h,
                system_terrain="plains",
            )
            for (x, y), z_h in z_map.items()
        ]
        persist.persist_rect(
            ChunkComputeResult(
                chunk_idx=1,
                rect=bbox,
                cells=cells,
                chunk_t0=time.perf_counter(),
                chunk_grades=(),
            ),
        )
        pack = persist.finish()
        services = build_pack_read_services(uid, PatchStoreService(), db_path=db_path)
        payload = PackMapGridRender(services.render).render_wilderness_tile_grid(
            world, 0, 0,
            include_z_slices=False,
            include_column_diagnostics=False,
        )
        source = services.render.try_wilderness_tile(world, 0, 0)
        self.assertIsNotNone(source)
        sidecar = {cell.cell: cell.slots for cell in source.slots}
        return pack, payload, sidecar

    def _assert_l2_dump(
        self,
        z_map: dict[tuple[int, int], int],
        expected: dict[tuple[int, int], tuple[int, ...]],
        *,
        uid: str,
    ) -> None:
        pack, payload, sidecar = self._persist_and_render(z_map, uid=uid)
        self.assertEqual(pack.meter_surface_z, z_map)
        self.assertEqual(payload.read_mode, "wilderness_tile_l2")
        self.assertEqual(payload.column_count, len(z_map))
        self.assertEqual(sidecar, expected)
        self.assertEqual(_packed(z_map), expected)
        grade = payload.levels.get(LEVEL_SURFACE_GRADE, "")
        self.assertTrue(grade.strip(), msg="surface_grade dump empty")
        dumped = slots_from_surface_grade_dump(grade)
        self.assertEqual(set(dumped), set(expected))
        for xy, slots in expected.items():
            self.assertEqual(dumped[xy], slots, msg=f"dump cell {xy}\n{grade}")
        height = payload.levels.get(LEVEL_SURFACE_Z, "")
        self.assertTrue(height.strip())
        for z_h in set(z_map.values()):
            self.assertRegex(
                height,
                rf"(^|[\s|]){re.escape(str(z_h))}([\s|]|$)",
                msg=f"surface_z dump missing {z_h}\n{height}",
            )

    def test_pit_four_around_two(self) -> None:
        z, expected = parse_tz_dump_map(_PIT_4_AROUND_2)
        self._assert_l2_dump(z, expected, uid="w-e2e-pit")

    def test_pool_east_four_three_two(self) -> None:
        z, expected = parse_tz_dump_map(_POOL_EAST_4_3_2)
        self._assert_l2_dump(z, expected, uid="w-e2e-pool")

    def test_cascade_south(self) -> None:
        z = _CASCADE_SOUTH_Z
        self._assert_l2_dump(z, _packed(z), uid="w-e2e-cascade")

    def test_mixed_heights(self) -> None:
        self._assert_l2_dump(_MIXED_Z, _packed(_MIXED_Z), uid="w-e2e-mixed")

    def test_pit_pool_cascade_each_pair_dz(self) -> None:
        _, pit_slots = parse_tz_dump_map(_PIT_4_AROUND_2)
        _, pool_slots = parse_tz_dump_map(_POOL_EAST_4_3_2)
        for dz in _PAIR_DZ:
            pit_z = _pit_z(dz)
            self._assert_l2_dump(
                pit_z,
                _slots_for_pair_dz(pit_slots, dz),
                uid=f"w-e2e-pit-{dz}",
            )
            pool_z = _pool_east_z(dz)
            self._assert_l2_dump(
                pool_z,
                _slots_for_pair_dz(pool_slots, dz),
                uid=f"w-e2e-pool-{dz}",
            )
            south_z = _cascade_south_z(dz)
            self._assert_l2_dump(south_z, _packed(south_z), uid=f"w-e2e-cas-{dz}")


if __name__ == "__main__":
    unittest.main()
