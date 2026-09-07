"""detailed_bake C11 hook — surface facade consumer after L2."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.worldData.pack.bake.packBakeResult import PackBakeResult
from app.application.worldData.pack.bake.packDetailedBakeOrchestrator import (
    PackDetailedBakeResult,
)
from app.application.worldData.persistResult import PersistResult
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    SettlementOutdoorExtractError,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorOrchestrator import (
    MaterializeResult,
    SettlementOutdoorError,
)
from app.application.worldData.worldSurfaceMaterializationOrchestrator import (
    WorldSurfaceMaterializationOrchestrator,
)
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.worldPack.detailedBakeScope import DetailedBakeRequest
from app.db.models.namedLocation import NamedLocation


def _city(**kwargs) -> NamedLocation:
    payload = {
        "location_uid": "loc-city",
        "world_uid": "w1",
        "display_name": "Hold",
        "system_location_type": WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT,
        "created_at": "2026-01-01T00:00:00",
        "system_city_size": "town",
    }
    payload.update(kwargs)
    return NamedLocation(**payload)


def _l2(*, scope="location", location_uid="loc-city", failed=0) -> PackDetailedBakeResult:
    return PackDetailedBakeResult(
        scope=scope,
        terrain=PersistResult.from_counts(1, 1, failed=failed),
        location_uid=location_uid if scope == "location" else None,
    )


def _orch(*, outdoor=None, bake_result=None):
    detailed = MagicMock()
    detailed.bake = AsyncMock(return_value=bake_result or _l2())
    return WorldSurfaceMaterializationOrchestrator(
        MagicMock(),
        detailed=detailed,
        outdoor=outdoor,
    )


class PackBakeResultSettlementTests(TestCase):
    def test_to_dict_omits_settlement_when_absent(self):
        result = PackBakeResult(mode="detailed", detailed=_l2())
        payload = result.to_dict()
        self.assertNotIn("settlement", payload)
        self.assertFalse(result.is_partial())

    def test_to_dict_includes_settlement_and_partial_on_error(self):
        result = PackBakeResult(
            mode="detailed",
            detailed=_l2(),
            settlement=MaterializeResult(
                location_uid="loc-city",
                status="error",
                error="boom",
            ),
        )
        payload = result.to_dict()
        self.assertEqual(payload["settlement"]["status"], "error")
        self.assertEqual(payload["settlement"]["error"], "boom")
        self.assertTrue(result.is_partial())

    def test_published_is_not_partial(self):
        result = PackBakeResult(
            mode="detailed",
            detailed=_l2(),
            settlement=MaterializeResult(location_uid="loc-city", status="published"),
        )
        self.assertFalse(result.is_partial())


class DetailedBakeC11HookTests(IsolatedAsyncioTestCase):
    @patch(
        "app.application.worldData.worldSurfaceMaterializationOrchestrator"
        ".require_surface_terrain_context",
    )
    async def test_city_location_calls_materialize_with_skip(self, _ctx):
        outdoor = MagicMock()
        published = MaterializeResult(location_uid="loc-city", status="published")
        outdoor.materialize = AsyncMock(return_value=published)
        orch = _orch(outdoor=outdoor)
        city = _city()
        request = DetailedBakeRequest(scope="location", location_uid=city.location_uid)

        detailed, settlement = await orch.materialize_pack_detailed(
            SimpleNamespace(world_uid="w1"),
            [city],
            MagicMock(),
            MagicMock(),
            request,
        )

        self.assertEqual(detailed.location_uid, "loc-city")
        self.assertEqual(settlement, published)
        outdoor.materialize.assert_awaited_once_with(
            "w1",
            "loc-city",
            skip_if_initialized=True,
        )

    @patch(
        "app.application.worldData.worldSurfaceMaterializationOrchestrator"
        ".require_surface_terrain_context",
    )
    async def test_wilderness_does_not_call_c11(self, _ctx):
        outdoor = MagicMock()
        outdoor.materialize = AsyncMock()
        orch = _orch(
            outdoor=outdoor,
            bake_result=_l2(scope="wilderness", location_uid=None),
        )
        request = DetailedBakeRequest(scope="wilderness", tile_gx=0, tile_gy=0)

        _, settlement = await orch.materialize_pack_detailed(
            SimpleNamespace(world_uid="w1"),
            [_city()],
            MagicMock(),
            MagicMock(),
            request,
        )

        self.assertIsNone(settlement)
        outdoor.materialize.assert_not_called()

    @patch(
        "app.application.worldData.worldSurfaceMaterializationOrchestrator"
        ".require_surface_terrain_context",
    )
    async def test_non_city_location_does_not_call_c11(self, _ctx):
        outdoor = MagicMock()
        outdoor.materialize = AsyncMock()
        pin = NamedLocation(
            location_uid="loc-cave",
            world_uid="w1",
            display_name="Cave",
            system_location_type="landmark",
            created_at="2026-01-01T00:00:00",
        )
        orch = _orch(
            outdoor=outdoor,
            bake_result=_l2(location_uid="loc-cave"),
        )
        request = DetailedBakeRequest(scope="location", location_uid="loc-cave")

        _, settlement = await orch.materialize_pack_detailed(
            SimpleNamespace(world_uid="w1"),
            [pin],
            MagicMock(),
            MagicMock(),
            request,
        )

        self.assertIsNone(settlement)
        outdoor.materialize.assert_not_called()

    @patch(
        "app.application.worldData.worldSurfaceMaterializationOrchestrator"
        ".require_surface_terrain_context",
    )
    async def test_district_uid_does_not_call_c11(self, _ctx):
        outdoor = MagicMock()
        outdoor.materialize = AsyncMock()
        district = NamedLocation(
            location_uid="loc-dist",
            world_uid="w1",
            display_name="Ward",
            system_location_type=WorldLocationTypeRegistry.SYSTEM_TYPE_DISTRICT,
            created_at="2026-01-01T00:00:00",
        )
        orch = _orch(
            outdoor=outdoor,
            bake_result=_l2(location_uid="loc-dist"),
        )
        request = DetailedBakeRequest(scope="location", location_uid="loc-dist")

        _, settlement = await orch.materialize_pack_detailed(
            SimpleNamespace(world_uid="w1"),
            [district],
            MagicMock(),
            MagicMock(),
            request,
        )

        self.assertIsNone(settlement)
        outdoor.materialize.assert_not_called()

    @patch(
        "app.application.worldData.worldSurfaceMaterializationOrchestrator"
        ".require_surface_terrain_context",
    )
    async def test_outdoor_none_skips_c11(self, _ctx):
        orch = _orch(outdoor=None)
        request = DetailedBakeRequest(scope="location", location_uid="loc-city")

        _, settlement = await orch.materialize_pack_detailed(
            SimpleNamespace(world_uid="w1"),
            [_city()],
            MagicMock(),
            MagicMock(),
            request,
        )

        self.assertIsNone(settlement)

    @patch(
        "app.application.worldData.worldSurfaceMaterializationOrchestrator"
        ".require_surface_terrain_context",
    )
    async def test_c11_error_keeps_l2_and_records_settlement(self, _ctx):
        outdoor = MagicMock()
        outdoor.materialize = AsyncMock(side_effect=SettlementOutdoorError("no pack"))
        l2 = _l2()
        orch = _orch(outdoor=outdoor, bake_result=l2)
        request = DetailedBakeRequest(scope="location", location_uid="loc-city")

        detailed, settlement = await orch.materialize_pack_detailed(
            SimpleNamespace(world_uid="w1"),
            [_city()],
            MagicMock(),
            MagicMock(),
            request,
        )

        self.assertIs(detailed, l2)
        self.assertEqual(settlement.status, "error")
        self.assertEqual(settlement.error, "no pack")

    @patch(
        "app.application.worldData.worldSurfaceMaterializationOrchestrator"
        ".require_surface_terrain_context",
    )
    async def test_extract_error_is_settlement_error_not_raise(self, _ctx):
        outdoor = MagicMock()
        outdoor.materialize = AsyncMock(
            side_effect=SettlementOutdoorExtractError("bad layout"),
        )
        orch = _orch(outdoor=outdoor)
        request = DetailedBakeRequest(scope="location", location_uid="loc-city")

        _, settlement = await orch.materialize_pack_detailed(
            SimpleNamespace(world_uid="w1"),
            [_city()],
            MagicMock(),
            MagicMock(),
            request,
        )

        self.assertEqual(settlement.status, "error")
        self.assertIn("bad layout", settlement.error)

    @patch(
        "app.application.worldData.worldSurfaceMaterializationOrchestrator"
        ".require_surface_terrain_context",
    )
    async def test_bake_pack_attaches_settlement(self, _ctx):
        outdoor = MagicMock()
        published = MaterializeResult(
            location_uid="loc-city",
            status="published",
            buildings=3,
        )
        outdoor.materialize = AsyncMock(return_value=published)
        orch = _orch(outdoor=outdoor)
        city = _city()

        result = await orch.bake_pack(
            "w1",
            SimpleNamespace(world_uid="w1"),
            [city],
            MagicMock(),
            MagicMock(),
            mode="detailed",
            detailed_request=DetailedBakeRequest(
                scope="location",
                location_uid=city.location_uid,
            ),
        )

        self.assertEqual(result.settlement, published)
        self.assertEqual(result.to_dict()["settlement"]["buildings"], 3)
        self.assertFalse(result.is_partial())
        outdoor.materialize.assert_awaited_once_with(
            "w1",
            "loc-city",
            skip_if_initialized=True,
        )
