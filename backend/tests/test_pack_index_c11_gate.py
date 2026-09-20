"""Pack locations_index gate before C11 / location L2 — LOC-T-3 occupancy SoT."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock

from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_detailed_bake_skip_not_in_index,
    log_pack_settlement_skip_not_in_index,
)
from app.application.worldData.pack.bake.packDetailedBakeOrchestrator import (
    PackDetailedBakeOrchestrator,
)
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.read.locationsIndexRead import (
    load_locations_index,
    location_uid_in_pack_index,
    location_uids_in_pack_index,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    MaterializeResult,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorOrchestrator import (
    SettlementOutdoorOrchestrator,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.worldPack.detailedBakeScope import DetailedBakeRequest
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _world() -> World:
    return World(world_uid="w1", name="test", created_at="2026-01-01T00:00:00")


def _city(uid: str, *, map_x: int = 2, map_y: int = 2) -> NamedLocation:
    return NamedLocation(
        location_uid=uid,
        world_uid="w1",
        display_name=uid,
        system_location_type=WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT,
        system_location_subtype="city",
        system_city_size="medium",
        created_at="2026-01-01T00:00:00",
        map_x=map_x,
        map_y=map_y,
        map_z=0,
    )


def _write_index(paths: WorldPackPaths, *uids: str) -> None:
    paths.ensure_dirs()
    pins = [
        LocationsIndexPin(location_uid=uid, map_x=2, map_y=2)
        for uid in uids
    ]
    paths.locations_index_path().write_text(
        LocationsIndexWire(locations=pins).model_dump_json(),
        encoding="utf-8",
    )


class LocationsIndexReadTests(TestCase):
    def test_missing_file_is_empty(self):
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            self.assertIsNone(load_locations_index(paths))
            self.assertEqual(location_uids_in_pack_index(paths), frozenset())
            self.assertFalse(location_uid_in_pack_index(paths, "loc-city-ironhold-002"))

    def test_pin_present_loser_absent(self):
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            _write_index(paths, "loc-city-ironhold-002")
            self.assertTrue(location_uid_in_pack_index(paths, "loc-city-ironhold-002"))
            self.assertFalse(location_uid_in_pack_index(paths, "loc-city-amberport-002"))
            self.assertEqual(
                location_uids_in_pack_index(paths),
                frozenset({"loc-city-ironhold-002"}),
            )


class PackIndexSkipLogLevelTests(TestCase):
    def test_skip_logs_are_error(self):
        logger = "app.application.worldData.pack.bake.packBakeLog"
        with self.assertLogs(logger, level="ERROR") as captured:
            log_pack_detailed_bake_skip_not_in_index(
                "w1", location_uid="loc-city-amberport-002",
            )
            log_pack_settlement_skip_not_in_index(
                "w1", location_uid="loc-city-amberport-002",
            )
        text = "\n".join(captured.output)
        self.assertIn("ERROR", text)
        self.assertIn("not_in_locations_index", text)
        self.assertIn("occupancy", text)
        self.assertNotIn("INFO:", text)


def _outdoor(
    *,
    world: World,
    settlement: NamedLocation,
    paths: WorldPackPaths,
    children: list[NamedLocation] | None = None,
) -> SettlementOutdoorOrchestrator:
    facade = MagicMock()
    facade.has_pack_for.return_value = True
    writer = MagicMock()
    writer.paths = paths
    loc_repo = MagicMock()
    loc_repo.get_by_id = AsyncMock(return_value=settlement)
    loc_repo.get_children = AsyncMock(return_value=list(children or []))
    loc_repo.list_by_world_insert_order = AsyncMock(return_value=[settlement])
    world_repo = MagicMock()
    world_repo.get_by_id = AsyncMock(return_value=world)
    generator = MagicMock()
    generator.generate_layout = MagicMock(
        side_effect=AssertionError("C11 generate must not run"),
    )
    return SettlementOutdoorOrchestrator(
        world_repo,
        loc_repo,
        MagicMock(),
        generator,
        writer_for=lambda _world: writer,
        facade_for=lambda _uid: facade,
        pack_context_for=MagicMock(),
        library=MagicMock(),
        node_repo=MagicMock(),
        edge_repo=MagicMock(),
    )


class C11PackIndexGateTests(IsolatedAsyncioTestCase):
    async def test_materialize_skips_uid_not_in_index(self):
        world = _world()
        amber = _city("loc-city-amberport-002", map_y=6)
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            _write_index(paths, "loc-city-ironhold-002")
            orch = _outdoor(world=world, settlement=amber, paths=paths)
            result = await orch.materialize("w1", amber.location_uid)
            self.assertEqual(result.status, "skipped")
            orch._locations.get_children.assert_not_called()
            orch._generator.generate_layout.assert_not_called()

    async def test_materialize_pin_passes_index_gate(self):
        world = _world()
        iron = _city("loc-city-ironhold-002")
        authored = NamedLocation(
            location_uid="loc-hand",
            world_uid="w1",
            display_name="hand",
            system_location_type="landmark",
            created_at="2026-01-01T00:00:00",
        )
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            _write_index(paths, iron.location_uid)
            orch = _outdoor(
                world=world, settlement=iron, paths=paths, children=[authored],
            )
            result = await orch.materialize("w1", iron.location_uid)
            self.assertEqual(result.status, "skipped")
            orch._locations.get_children.assert_awaited()
            orch._generator.generate_layout.assert_not_called()

    async def test_batch_only_index_uids(self):
        world = _world()
        iron = _city("loc-city-ironhold-002")
        amber = _city("loc-city-amberport-002", map_y=6)
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            _write_index(paths, iron.location_uid)
            orch = _outdoor(world=world, settlement=iron, paths=paths)
            orch._locations.list_by_world_insert_order = AsyncMock(
                return_value=[iron, amber],
            )
            seen: list[str] = []

            async def _capture(_world_uid: str, uid: str, *, skip_if_initialized: bool = True):
                seen.append(uid)
                return MaterializeResult(location_uid=uid, status="skipped")

            orch.materialize = _capture  # type: ignore[method-assign]
            batch = await orch.materialize_all("w1")
            self.assertEqual(seen, [iron.location_uid])
            self.assertEqual(len(batch.results), 1)


class LocationL2PackIndexGateTests(IsolatedAsyncioTestCase):
    async def test_location_not_in_index_skips_refine(self):
        amber = _city("loc-city-amberport-002", map_y=6)
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            _write_index(paths, "loc-city-ironhold-002")
            writer = MagicMock()
            writer.paths = paths
            orch = PackDetailedBakeOrchestrator(MagicMock())
            orch._refine_tiles = AsyncMock(
                side_effect=AssertionError("L2 refine must not run"),
            )
            result = await orch._bake_location_scope(
                _world(),
                [amber],
                writer,
                MagicMock(),
                MagicMock(),
                DetailedBakeRequest(
                    scope="location",
                    location_uid=amber.location_uid,
                ),
                relief_templates={},
            )
            self.assertEqual(result.tiles_refined, 0)
            self.assertEqual(result.wilderness_chunks, 0)
            self.assertEqual(result.location_uid, amber.location_uid)
            orch._refine_tiles.assert_not_called()

    async def test_location_in_index_calls_refine(self):
        iron = _city("loc-city-ironhold-002")
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            _write_index(paths, iron.location_uid)
            writer = MagicMock()
            writer.paths = paths
            orch = PackDetailedBakeOrchestrator(MagicMock())
            orch._refine_tiles = AsyncMock(
                side_effect=AssertionError("stop after gate"),
            )
            with self.assertRaisesRegex(AssertionError, "stop after gate"):
                await orch._bake_location_scope(
                    _world(),
                    [iron],
                    writer,
                    MagicMock(),
                    MagicMock(),
                    DetailedBakeRequest(
                        scope="location",
                        location_uid=iron.location_uid,
                    ),
                    relief_templates={},
                )
            orch._refine_tiles.assert_awaited()
