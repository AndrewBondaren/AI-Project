"""LOC-T-3 settlement AABB occupancy — no import 422."""

from __future__ import annotations

import logging
import unittest
from unittest import IsolatedAsyncioTestCase

from fastapi import HTTPException

from app.application.jsonValidation.settlementVolumeSeparation import (
    log_settlement_volume_separation,
)
from app.application.worldData.namedLocationService import NamedLocationService
from app.application.worldData.pack.bake.locationsIndexBake import build_locations_index
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volumes_by_location,
)
from app.application.worldData.settlementMapOccupancy import (
    occupancy_locations,
    pick_occupants,
)
from app.dataModel.worldPack.territoryVolume import (
    TerritoryVolume,
    empty_inclusive,
    volumes_conflict,
)
from app.dataModel.worldPack.territoryVolumePolicy import TerritoryVolumePolicy
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _policy() -> TerritoryVolumePolicy:
    return TerritoryVolumePolicy.canonical_defaults()


def _world() -> World:
    return World(world_uid="w1", name="test", created_at="2026-01-01T00:00:00")


def _city(uid: str, *, size: str = "medium", map_x: int = 0, map_y: int = 0, map_z: int = 0) -> NamedLocation:
    return NamedLocation(
        location_uid=uid,
        world_uid="w1",
        display_name=uid,
        system_location_type="settlement",
        system_location_subtype="city",
        system_city_size=size,
        created_at="2026-01-01T00:00:00",
        map_x=map_x,
        map_y=map_y,
        map_z=map_z,
    )


def _box(**kwargs) -> TerritoryVolume:
    payload = {"x0": 0, "y0": 0, "z0": 0, "x1": 9, "y1": 9, "z1": 9}
    payload.update(kwargs)
    return TerritoryVolume(**payload)


def _city_row(uid: str, *, size: str = "medium", map_x: int = 0, map_y: int = 0) -> dict:
    return {
        "location_uid": uid,
        "display_name": uid,
        "system_location_type": "settlement",
        "system_location_subtype": "city",
        "system_city_size": size,
        "map_x": map_x,
        "map_y": map_y,
        "created_at": "2026-01-01T00:00:00",
    }


class _LocRepo:
    def __init__(self) -> None:
        self.rows: list[NamedLocation] = []

    async def upsert(self, loc: NamedLocation) -> None:
        self.rows = [row for row in self.rows if row.location_uid != loc.location_uid]
        self.rows.append(loc)

    async def create(self, loc: NamedLocation) -> None:
        await self.upsert(loc)

    async def update(self, loc: NamedLocation) -> None:
        await self.upsert(loc)

    async def get_by_world(self, world_uid: str) -> list[NamedLocation]:
        return list(self.rows)

    async def list_by_world_insert_order(self, world_uid: str) -> list[NamedLocation]:
        return list(self.rows)

    async def get_by_id(self, location_uid: str) -> NamedLocation | None:
        return next((row for row in self.rows if row.location_uid == location_uid), None)


class _WorldRepo:
    def __init__(self, world: World) -> None:
        self.world = world

    async def get_by_id(self, world_uid: str) -> World | None:
        if world_uid == self.world.world_uid:
            return self.world
        return None


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestEmptyInclusiveAndConflict(unittest.TestCase):
    def test_overlap_empty_is_zero(self) -> None:
        self.assertEqual(empty_inclusive(0, 10, 5, 15), 0)

    def test_abutting_xy_empty_is_zero(self) -> None:
        self.assertEqual(empty_inclusive(0, 9, 10, 19), 0)

    def test_one_cell_gap(self) -> None:
        self.assertEqual(empty_inclusive(0, 9, 11, 19), 1)

    def test_overlap_is_conflict(self) -> None:
        a = _box()
        b = _box(x0=5, x1=14)
        self.assertTrue(volumes_conflict(a, b, _policy()))

    def test_abutting_xy_is_conflict(self) -> None:
        a = _box()
        b = _box(x0=10, x1=19)
        self.assertTrue(volumes_conflict(a, b, _policy()))

    def test_empty_z_at_policy_min_is_ok(self) -> None:
        policy = _policy()
        a = _box(z0=0, z1=policy.settlement_z_above)
        z0_b = a.z1 + 1 + policy.min_settlement_separation_z
        b = _box(z0=z0_b, z1=z0_b + policy.settlement_z_above)
        self.assertFalse(volumes_conflict(a, b, policy))
        self.assertEqual(empty_inclusive(a.z0, a.z1, b.z0, b.z1), policy.min_settlement_separation_z)

    def test_overlap_conflicts_when_min_xy_is_zero(self) -> None:
        policy = TerritoryVolumePolicy(
            min_settlement_separation_xy=0,
            min_settlement_separation_z=0,
        )
        vol = _box()
        self.assertTrue(volumes_conflict(vol, vol, policy))

    def test_predicate_does_not_raise_http(self) -> None:
        try:
            volumes_conflict(_box(), _box(), _policy())
        except HTTPException as exc:
            self.fail(f"volumes_conflict raised HTTPException {exc.status_code}")


class TestPickOccupants(unittest.TestCase):
    def test_equal_medium_first_index_occupies(self) -> None:
        world = _world()
        first = _city("loc-a")
        second = _city("loc-b")
        picked = pick_occupants(world, [(0, first), (1, second)])
        self.assertEqual([loc.location_uid for loc in picked.occupants], ["loc-a"])
        self.assertEqual(len(picked.conflicts), 1)
        self.assertEqual(picked.conflicts[0].winner.location_uid, "loc-a")
        self.assertEqual(picked.conflicts[0].loser.location_uid, "loc-b")
        self.assertEqual(picked.conflicts[0].reason, "declaration_order")

    def test_large_second_beats_medium_first(self) -> None:
        world = _world()
        medium = _city("loc-medium", size="medium")
        large = _city("loc-large", size="large")
        picked = pick_occupants(world, [(0, medium), (1, large)])
        self.assertEqual([loc.location_uid for loc in picked.occupants], ["loc-large"])
        self.assertEqual(picked.conflicts[0].reason, "footprint")
        self.assertEqual(picked.conflicts[0].winner.location_uid, "loc-large")

    def test_separated_xy_both_occupy(self) -> None:
        world = _world()
        policy = _policy()
        first = _city("loc-a", map_x=0, map_y=0)
        gap = policy.min_settlement_separation_xy
        # first volume y1 = side-1; occupancy side is city×medium via generate helper
        picked_side = pick_occupants(world, [(0, first)])
        self.assertEqual(len(picked_side.occupants), 1)
        side = picked_side.occupants[0]
        vol = next(v for _, v in territory_volumes_by_location(world, [side]))
        second_y = vol.y1 + 1 + gap
        second = _city("loc-b", map_x=0, map_y=second_y)
        picked = pick_occupants(world, [(0, first), (1, second)])
        self.assertEqual(
            [loc.location_uid for loc in picked.occupants],
            ["loc-a", "loc-b"],
        )
        self.assertEqual(picked.conflicts, ())

    def test_uid_order_does_not_win_tie(self) -> None:
        world = _world()
        amber = _city("loc-city-amberport-002")
        iron = _city("loc-city-ironhold-002")
        picked = pick_occupants(world, [(0, iron), (1, amber)])
        self.assertEqual(picked.occupants[0].location_uid, "loc-city-ironhold-002")

    def test_pick_does_not_raise_http(self) -> None:
        world = _world()
        try:
            pick_occupants(world, [(0, _city("a")), (1, _city("b"))])
        except HTTPException as exc:
            self.fail(f"pick_occupants raised HTTPException {exc.status_code}")


class TestOccupancyCallers(unittest.TestCase):
    def test_occupancy_locations_keeps_loser_out_of_index(self) -> None:
        world = _world()
        iron = _city("loc-city-ironhold-002")
        amber = _city("loc-city-amberport-002")
        peak = NamedLocation(
            location_uid="loc-peak",
            world_uid="w1",
            display_name="Peak",
            system_location_type="geographic",
            created_at="2026-01-01T00:00:00",
            map_x=8,
            map_y=8,
        )
        rows = occupancy_locations(world, [iron, amber, peak])
        uids = [loc.location_uid for loc in rows]
        self.assertEqual(uids, ["loc-city-ironhold-002", "loc-peak"])
        index = build_locations_index([iron, amber, peak], world)
        self.assertEqual(
            [pin.location_uid for pin in index.locations],
            ["loc-city-ironhold-002", "loc-peak"],
        )

    def test_territory_volumes_omit_loser(self) -> None:
        world = _world()
        iron = _city("loc-city-ironhold-002")
        amber = _city("loc-city-amberport-002")
        pairs = territory_volumes_by_location(world, [iron, amber])
        self.assertEqual([uid for uid, _ in pairs], ["loc-city-ironhold-002"])


class TestSettlementVolumeLog(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger(
            "app.application.jsonValidation.settlementVolumeSeparation",
        )
        self.handler = _LogCapture()
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.ERROR)

    def tearDown(self) -> None:
        self.logger.removeHandler(self.handler)

    def test_error_carries_uid_size_z(self) -> None:
        policy = _policy()
        log_settlement_volume_separation(
            winner_uid="loc-city-ironhold-002",
            loser_uid="loc-city-amberport-002",
            winner_name="Айронхолд",
            loser_name="Амберпорт",
            winner_subtype="city",
            loser_subtype="city",
            winner_size="medium",
            loser_size="medium",
            winner_side_fine=2000,
            loser_side_fine=2000,
            winner_map_z=0,
            loser_map_z=0,
            winner_z0=0,
            winner_z1=policy.settlement_z_above,
            loser_z0=0,
            loser_z1=policy.settlement_z_above,
            empty_x=0,
            empty_y=0,
            empty_z=0,
            min_xy=policy.min_settlement_separation_xy,
            min_z=policy.min_settlement_separation_z,
            reason="declaration_order",
        )
        self.assertEqual(len(self.handler.records), 1)
        record = self.handler.records[0]
        self.assertEqual(record.levelno, logging.ERROR)
        self.assertIn("json_validation | settlement_volume_separation", record.getMessage())
        self.assertEqual(record.winner_uid, "loc-city-ironhold-002")
        self.assertEqual(record.loser_uid, "loc-city-amberport-002")
        self.assertEqual(record.winner_size, "medium")
        self.assertEqual(record.loser_size, "medium")
        self.assertEqual(record.winner_subtype, "city")
        self.assertEqual(record.winner_map_z, 0)
        self.assertEqual(record.loser_z0, 0)
        self.assertEqual(record.winner_z1, policy.settlement_z_above)
        self.assertEqual(record.min_z, policy.min_settlement_separation_z)


class TestNamedLocationServiceGate(IsolatedAsyncioTestCase):
    async def test_import_overlapping_persists_both_and_logs(self) -> None:
        repo = _LocRepo()
        world = _world()
        svc = NamedLocationService(repo=repo, world_repo=_WorldRepo(world))
        log = logging.getLogger("app.application.jsonValidation.settlementVolumeSeparation")
        handler = _LogCapture()
        log.addHandler(handler)
        log.setLevel(logging.ERROR)
        try:
            result = await svc.import_from_json(
                world.world_uid,
                [
                    _city_row("loc-city-ironhold-002"),
                    _city_row("loc-city-amberport-002"),
                ],
            )
        except HTTPException as exc:
            self.fail(f"import raised HTTPException {exc.status_code}")
        finally:
            log.removeHandler(handler)
        self.assertEqual(result.failed, 0)
        self.assertEqual(result.succeeded, 2)
        self.assertEqual({row.location_uid for row in repo.rows}, {
            "loc-city-ironhold-002",
            "loc-city-amberport-002",
        })
        self.assertEqual(len(handler.records), 1)
        record = handler.records[0]
        self.assertEqual(record.levelno, logging.ERROR)
        self.assertEqual(record.winner_uid, "loc-city-ironhold-002")
        self.assertEqual(record.loser_uid, "loc-city-amberport-002")
        self.assertEqual(record.winner_size, "medium")
        self.assertEqual(record.loser_map_z, 0)
        self.assertEqual(record.reason, "declaration_order")

    async def test_separated_import_has_no_error(self) -> None:
        repo = _LocRepo()
        world = _world()
        svc = NamedLocationService(repo=repo, world_repo=_WorldRepo(world))
        policy = _policy()
        first = _city("loc-a")
        vol = next(v for _, v in territory_volumes_by_location(world, [first]))
        second_y = vol.y1 + 1 + policy.min_settlement_separation_xy
        log = logging.getLogger("app.application.jsonValidation.settlementVolumeSeparation")
        handler = _LogCapture()
        log.addHandler(handler)
        log.setLevel(logging.ERROR)
        try:
            result = await svc.import_from_json(
                world.world_uid,
                [
                    _city_row("loc-a", map_x=0, map_y=0),
                    _city_row("loc-b", map_x=0, map_y=second_y),
                ],
            )
        finally:
            log.removeHandler(handler)
        self.assertEqual(result.succeeded, 2)
        self.assertEqual(handler.records, [])

    async def test_large_second_import_occupies_large(self) -> None:
        repo = _LocRepo()
        world = _world()
        svc = NamedLocationService(repo=repo, world_repo=_WorldRepo(world))
        log = logging.getLogger("app.application.jsonValidation.settlementVolumeSeparation")
        handler = _LogCapture()
        log.addHandler(handler)
        log.setLevel(logging.ERROR)
        try:
            await svc.import_from_json(
                world.world_uid,
                [
                    _city_row("loc-medium", size="medium"),
                    _city_row("loc-large", size="large"),
                ],
            )
        finally:
            log.removeHandler(handler)
        self.assertEqual(handler.records[0].winner_uid, "loc-large")
        self.assertEqual(handler.records[0].reason, "footprint")
        mapped = occupancy_locations(world, list(repo.rows))
        self.assertEqual([loc.location_uid for loc in mapped], ["loc-large"])


if __name__ == "__main__":
    unittest.main()
