"""C24 district packing: anchor, C14 skip, frames, HTTP mapping."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock

from app.api.routes.locations import _http_from_outdoor
from app.application.worldData.pack.io.packBlobWire import (
    append_settlement_structure_district,
    encode_settlement_structure_frames,
    parse_settlement_structure_blob,
    settlement_structure_payload,
)
from app.application.worldData.pack.io.tileCodec import (
    PAYLOAD_KIND_SETTLEMENT_STRUCTURE,
    TileCodec,
)
from app.application.worldData.pack.io.worldPackPaths import WorldPackPaths
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.settlementOutdoor.settlementOutdoorContract import (
    SettlementOutdoorConflictError,
    SettlementOutdoorError,
    SettlementOutdoorNotFoundError,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorOrchestrator import (
    SettlementOutdoorOrchestrator,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    packing_queue,
    should_skip_materialize,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    DistrictAnchorError,
    resolve_district_uid,
    topology_census,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTypes import (
    district_type_entry,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.settlement.district.districtTopologySlot import DistrictTopologySlot
from app.dataModel.spatial.facing import Facing
from app.dataModel.worldPack.settlementStructureWire import (
    AreaSlotWire,
    AreaStructureWire,
    DistrictStructureWire,
    SettlementStructureWire,
)
from app.dataModel.worldPack.worldPackManifest import SettlementStructureEntry
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from pathlib import Path
from tempfile import TemporaryDirectory


def _volume() -> dict:
    return {"x0": 0, "y0": 0, "z0": 0, "x1": 10, "y1": 10, "z1": 0}


def _district_row(
    uid: str,
    *,
    origin_x: int,
    origin_y: int,
    width_fine: int = 16,
    depth_fine: int = 16,
    slot_index: int,
    template: str = "core",
) -> NamedLocation:
    freeze = DistrictTopologySlot(
        cell_x=slot_index,
        cell_y=0,
        origin_x=origin_x,
        origin_y=origin_y,
        width_fine=width_fine,
        depth_fine=depth_fine,
        ground_z=0,
        template_system_name=template,
        slot_index=slot_index,
    )
    return NamedLocation(
        location_uid=uid,
        world_uid="w1",
        display_name=uid,
        system_location_type=district_type_entry().system_type,
        created_at="2026-01-01T00:00:00",
        parent_location_uid="set-1",
        district_topology=freeze.model_dump(mode="json"),
    )


def _census() -> list[NamedLocation]:
    return [
        _district_row("d-a", origin_x=0, origin_y=0, slot_index=0),
        _district_row("d-b", origin_x=16, origin_y=0, slot_index=2),
    ]


def _settlement() -> NamedLocation:
    return NamedLocation(
        location_uid="set-1",
        world_uid="w1",
        display_name="Hold",
        system_location_type=WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT,
        system_location_subtype="city",
        system_city_size="medium",
        created_at="2026-01-01T00:00:00",
        map_x=2,
        map_y=2,
        map_z=0,
    )


class _SkipWriter:
    def __init__(self, *, published: bool, entry: SettlementStructureEntry | None):
        self._published = published
        self._entry = entry
        self.manifest = SimpleNamespace(
            settlement_structure_entry=lambda _uid: self._entry,
        )

    def has_published_settlement(self, _uid: str) -> bool:
        return self._published


def _entry(*, status: str, packed: list[str]) -> SettlementStructureEntry:
    return SettlementStructureEntry(
        location_uid="set-1",
        territory_volume=_volume(),
        structure_path="locations/l.set-1.settlement.zst",
        structure_status=status,
        packed_district_uids=packed,
    )


class C24AnchorTests(TestCase):

    def test_resolve_by_district_uid(self):
        census = _census()
        self.assertEqual(
            resolve_district_uid(census, district_uid="d-b"),
            "d-b",
        )

    def test_resolve_at_inside_rect(self):
        census = _census()
        self.assertEqual(
            resolve_district_uid(census, at_x=16, at_y=0),
            "d-b",
        )
        self.assertEqual(
            resolve_district_uid(census, at_x=0, at_y=0),
            "d-a",
        )

    def test_both_anchors_rejected(self):
        with self.assertRaises(DistrictAnchorError):
            resolve_district_uid(_census(), district_uid="d-a", at_x=0, at_y=0)

    def test_at_outside_rejected(self):
        with self.assertRaises(DistrictAnchorError):
            resolve_district_uid(_census(), at_x=100, at_y=100)

    def test_unknown_uid_rejected(self):
        with self.assertRaises(DistrictAnchorError):
            resolve_district_uid(_census(), district_uid="missing")

    def test_at_pair_required(self):
        with self.assertRaises(DistrictAnchorError):
            resolve_district_uid(_census(), at_x=0)

    def test_census_sorted_by_slot_index(self):
        rows = topology_census(_census())
        self.assertEqual([row.location_uid for row in rows], ["d-a", "d-b"])


class C14SkipTests(IsolatedAsyncioTestCase):

    async def test_c23_children_without_packed_do_not_skip(self):
        repo = MagicMock()
        skipped = await should_skip_materialize(
            _settlement(),
            _SkipWriter(published=False, entry=None),
            repo,
            children=_census(),
        )
        self.assertFalse(skipped)

    async def test_published_without_packed_list_does_not_skip(self):
        repo = MagicMock()
        skipped = await should_skip_materialize(
            _settlement(),
            _SkipWriter(published=True, entry=_entry(status="absent", packed=[])),
            repo,
            children=_census(),
        )
        self.assertFalse(skipped)

    async def test_complete_skips_settlement(self):
        repo = MagicMock()
        skipped = await should_skip_materialize(
            _settlement(),
            _SkipWriter(
                published=True,
                entry=_entry(status="complete", packed=["d-a", "d-b"]),
            ),
            repo,
            children=_census(),
        )
        self.assertTrue(skipped)

    async def test_packed_district_skips_that_uid(self):
        repo = MagicMock()
        writer = _SkipWriter(
            published=True,
            entry=_entry(status="partial", packed=["d-a"]),
        )
        self.assertTrue(
            await should_skip_materialize(
                _settlement(), writer, repo, district_uid="d-a", children=_census(),
            )
        )
        self.assertFalse(
            await should_skip_materialize(
                _settlement(), writer, repo, district_uid="d-b", children=_census(),
            )
        )

    async def test_authored_tavern_skips(self):
        building = WorldLocationTypeRegistry.canonical_engine().entry_for(
            WorldLocationTypeRegistry.SYSTEM_TYPE_BUILDING,
        )
        assert building is not None
        tavern = NamedLocation(
            location_uid="tavern-1",
            world_uid="w1",
            display_name="Inn",
            system_location_type=building.system_type,
            created_at="2026-01-01T00:00:00",
        )
        skipped = await should_skip_materialize(
            _settlement(),
            _SkipWriter(published=False, entry=None),
            MagicMock(),
            children=[tavern],
        )
        self.assertTrue(skipped)

    def test_packing_queue_is_census_minus_packed(self):
        queue = packing_queue(_census(), ["d-a"])
        self.assertEqual([row.location_uid for row in queue], ["d-b"])


class C24FrameTests(TestCase):

    def _wire(self, uid: str) -> SettlementStructureWire:
        return SettlementStructureWire(
            settlement_uid="set-1",
            districts=[
                DistrictStructureWire(
                    location_uid=uid,
                    areas=[
                        AreaStructureWire(
                            area_uid=f"a-{uid}",
                            slot=AreaSlotWire(
                                cells=[(0, 0)],
                                ground_z=0,
                                facing=Facing.NORTH,
                            ),
                        ),
                    ],
                ),
            ],
        )

    def test_append_does_not_recompress_first_payload(self):
        codec = TileCodec()
        first = encode_settlement_structure_frames(self._wire("d-a"), codec)
        second = append_settlement_structure_district(
            first, self._wire("d-b").districts[0], codec,
        )
        self.assertTrue(second.startswith(first))
        merged = parse_settlement_structure_blob(second, codec)
        self.assertEqual(merged.settlement_uid, "set-1")
        self.assertEqual(
            [d.location_uid for d in merged.districts],
            ["d-a", "d-b"],
        )

    def test_legacy_single_zstd_still_reads(self):
        codec = TileCodec()
        wire = self._wire("d-legacy")
        blob = codec.encode(
            PAYLOAD_KIND_SETTLEMENT_STRUCTURE,
            settlement_structure_payload(wire),
        )
        loaded = parse_settlement_structure_blob(blob, codec)
        self.assertEqual(loaded.settlement_uid, "set-1")
        self.assertEqual(loaded.districts[0].location_uid, "d-legacy")

    def test_writer_publish_records_packed_list(self):
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            writer = WorldPackWriter(paths)
            tmp_ref = writer.encode_settlement_structure_tmp("set-1", self._wire("d-a"))
            writer.publish_settlement_structure(
                tmp_ref,
                territory_volume=_volume(),
                packed_district_uids=["d-a"],
                structure_status="partial",
            )
            entry = writer.manifest.settlement_structure_entry("set-1")
            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(entry.packed_district_uids, ["d-a"])
            self.assertEqual(entry.structure_status, "partial")
            tmp_ref2 = writer.encode_settlement_structure_tmp("set-1", self._wire("d-b"))
            writer.publish_settlement_structure(
                tmp_ref2,
                territory_volume=_volume(),
                packed_district_uids=["d-a", "d-b"],
                structure_status="complete",
            )
            again = writer.manifest.settlement_structure_entry("set-1")
            assert again is not None
            self.assertEqual(again.packed_district_uids, ["d-a", "d-b"])
            self.assertEqual(again.structure_status, "complete")


class C24OrchestratorHttpTests(IsolatedAsyncioTestCase):

    def _orch(self, *, children: list[NamedLocation], paths: WorldPackPaths):
        world = World(world_uid="w1", name="t", created_at="2026-01-01T00:00:00")
        settlement = _settlement()
        facade = MagicMock()
        facade.has_pack_for.return_value = True
        loc_repo = MagicMock()
        loc_repo.get_by_id = AsyncMock(return_value=settlement)
        loc_repo.get_children = AsyncMock(return_value=children)
        world_repo = MagicMock()
        world_repo.get_by_id = AsyncMock(return_value=world)
        writer = WorldPackWriter(paths)
        return SettlementOutdoorOrchestrator(
            world_repo,
            loc_repo,
            MagicMock(),
            MagicMock(),
            writer_for=lambda _world: writer,
            facade_for=lambda _uid: facade,
            pack_context_for=MagicMock(),
            library=MagicMock(),
            node_repo=MagicMock(),
            edge_repo=MagicMock(),
        ), settlement

    async def test_empty_census_is_conflict(self):
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            paths.ensure_dirs()
            from app.dataModel.worldPack.locationsIndexWire import (
                LocationsIndexPin,
                LocationsIndexWire,
            )
            paths.locations_index_path().write_text(
                LocationsIndexWire(
                    locations=[LocationsIndexPin(location_uid="set-1", map_x=2, map_y=2)],
                ).model_dump_json(),
                encoding="utf-8",
            )
            orch, settlement = self._orch(children=[], paths=paths)
            with self.assertRaises(SettlementOutdoorConflictError):
                await orch.materialize("w1", settlement.location_uid)

    async def test_both_anchors_are_validation_error(self):
        with TemporaryDirectory() as tmp:
            paths = WorldPackPaths(Path(tmp), "w1")
            paths.ensure_dirs()
            from app.dataModel.worldPack.locationsIndexWire import (
                LocationsIndexPin,
                LocationsIndexWire,
            )
            paths.locations_index_path().write_text(
                LocationsIndexWire(
                    locations=[LocationsIndexPin(location_uid="set-1", map_x=2, map_y=2)],
                ).model_dump_json(),
                encoding="utf-8",
            )
            orch, settlement = self._orch(children=_census(), paths=paths)
            with self.assertRaises(SettlementOutdoorError) as ctx:
                await orch.materialize(
                    "w1",
                    settlement.location_uid,
                    district_uid="d-a",
                    at_x=0,
                    at_y=0,
                )
            self.assertNotIsInstance(ctx.exception, SettlementOutdoorConflictError)

    def test_http_maps_conflict_to_409(self):
        err = _http_from_outdoor(
            SettlementOutdoorConflictError("no C23 topology census"),
        )
        self.assertEqual(err.status_code, 409)

    def test_http_maps_anchor_to_422(self):
        err = _http_from_outdoor(SettlementOutdoorError("district_uid and at"))
        self.assertEqual(err.status_code, 422)

    def test_http_maps_not_found_to_404(self):
        err = _http_from_outdoor(SettlementOutdoorNotFoundError("missing"))
        self.assertEqual(err.status_code, 404)
