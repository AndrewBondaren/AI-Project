"""S3 engine tests — tz_cascade_context §4; no production wiring."""

import gc
import unittest
from random import Random
from unittest.mock import Mock

from pydantic import BaseModel

from app.application.worldData.context.cascadeLink import EmptyLink, Link
from app.application.worldData.context.contextResolver import extend
from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import (
    WorldEconomyTierRegistry,
)
from app.dataModel.locations.context.cascadeParams import ECONOMIC_TIER
from app.dataModel.cascade.cascadeSpec import ScopeAxis
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.namedLocation.bundleNamedLocation import (
    BundleNamedLocation,
)
from app.dataModel.locations.settlement.district.districtTemplateEntry import (
    DistrictTemplateEntry,
)
from app.dataModel.locations.settlement.settlement.settlementSkeleton import (
    SettlementSkeleton,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
)
from app.dataModel.locations.structure.room.roomDef import RoomDef
from app.db.models.world import World


def _world():
    tiers = WorldEconomyTierRegistry([
        EconomyTierEntry(system_tier=f"t{i}", display_tier=f"Tier {i}",
                         base_value=i * 10)
        for i in range(10)
    ])
    return World(
        world_uid="ctx-world", name="Ctx", created_at="2026-10-03",
        economic_tier_registry=tiers.model_dump(mode="json"),
    )


def _nl(tier=None, uid="nl", location_type="building", size=None,
        density=None):
    return BundleNamedLocation(
        location_uid=uid, display_name=uid,
        system_location_type=location_type, system_economic_tier=tier,
        system_city_size=size, settlement_density=density,
    )


def _room(tier=None):
    return RoomDef(
        room_id="r1", display_name="Room", room_type="hall",
        is_public=True, is_forbidden=False, required=True,
        size={"width_range": [5, 5], "depth_range": [5, 5]},
        economic_tier=tier,
    )


def _skeleton(tier=None, size=None, density=None):
    return SettlementSkeleton(
        economic_tier=tier, system_city_size=size,
        settlement_density=density,
    )


def _dte(tier_range=None, density=None):
    bounds = (
        None if tier_range is None
        else {"min": tier_range[0], "max": tier_range[1]}
    )
    return DistrictTemplateEntry(
        system_name="d1", display_name="District",
        district_type="residential", economic_tier_range=bounds,
        density=density,
    )


def _plot(tier=None, band=None, tier_range=None):
    bounds = (
        None if tier_range is None
        else {"min": tier_range[0], "max": tier_range[1]}
    )
    return PlotLayoutTemplate(
        system_name="p1", display_name="Plot",
        economic_tier=tier, economic_tier_band=band,
        economic_tier_range=bounds,
    )


def _chain_to_building(ctx, **stamps):
    """settlement → district → area → building with null stamps."""
    ctx = extend(ctx, Link(ScopeLevel.SETTLEMENT,
                           _nl(stamps.get("city"), "city", "settlement")),
                 Link(ScopeLevel.SETTLEMENT, _skeleton()))
    ctx = extend(ctx, Link(ScopeLevel.DISTRICT, _nl(uid="district")),
                 Link(ScopeLevel.DISTRICT, _dte()))
    ctx = extend(ctx, Link(ScopeLevel.AREA, _plot()))
    return extend(ctx, Link(ScopeLevel.BUILDING, _nl(stamps.get("building"))))


class ExtendSequenceTests(unittest.TestCase):
    def test_repeated_level_fails(self):
        ctx = extend(LocationContext.root(_world()),
                     Link(ScopeLevel.SETTLEMENT, _nl(uid="c")))
        with self.assertRaisesRegex(ValueError, "strictly below"):
            extend(ctx, Link(ScopeLevel.SETTLEMENT, _nl(uid="c2")))

    def test_skipped_level_fails(self):
        with self.assertRaisesRegex(ValueError, "skips a level"):
            extend(LocationContext.root(_world()),
                   Link(ScopeLevel.DISTRICT, _nl(uid="d")))

    def test_level_above_context_fails(self):
        ctx = _chain_to_building(LocationContext.root(_world()))
        with self.assertRaisesRegex(ValueError, "strictly below"):
            extend(ctx, Link(ScopeLevel.SETTLEMENT, _nl(uid="c")))

    def test_mixed_levels_in_one_extend_fails(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            extend(LocationContext.root(_world()),
                   Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
                   Link(ScopeLevel.DISTRICT, _nl(uid="d")))

    def test_foreign_axis_fails(self):
        class FactionScope(ScopeAxis):
            FACTION = "faction"
            CHAPTER = "chapter"

        with self.assertRaisesRegex(ValueError, "axis"):
            extend(LocationContext.root(_world()),
                   Link(FactionScope.CHAPTER, _nl(uid="x")))

    def test_object_without_channel_fails(self):
        class PlainPojo(BaseModel):
            note: str = "x"

        with self.assertRaisesRegex(TypeError, "no cascade channel"):
            extend(LocationContext.root(_world()),
                   Link(ScopeLevel.SETTLEMENT, PlainPojo()))

    def test_object_at_wrong_level_fails(self):
        with self.assertRaisesRegex(TypeError, "no cascade channel"):
            extend(LocationContext.root(_world()),
                   Link(ScopeLevel.SETTLEMENT, _room("t9")))


class ExtendResolutionTests(unittest.TestCase):
    def test_root_does_not_resolve_or_materialize(self):
        ctx = LocationContext.root(_world())
        self.assertIsNone(ctx.economic_tier)
        self.assertEqual(ctx.provenance, {})
        self.assertIs(ctx.level, ScopeLevel.WORLD)

    def test_room_explicit_beats_everything(self):
        ctx = _chain_to_building(LocationContext.root(_world()),
                                 city="t1", building="t8")
        ctx = extend(ctx, Link(ScopeLevel.ROOM, _room("t9")),
                     rng=Random(0))
        self.assertEqual(ctx.economic_tier, "t9")
        self.assertEqual(
            ctx.provenance["economic_tier"],
            (ScopeLevel.ROOM, "RoomDef.economic_tier"),
        )

    def test_null_authored_continues_inheritance(self):
        ctx = _chain_to_building(LocationContext.root(_world()),
                                 building="t8")
        ctx = extend(ctx, Link(ScopeLevel.ROOM, _room()), rng=Random(0))
        self.assertEqual(ctx.economic_tier, "t8")
        self.assertEqual(
            ctx.provenance["economic_tier"],
            (ScopeLevel.BUILDING,
             "BundleNamedLocation.system_economic_tier"),
        )

    def test_empty_link_does_not_block_inheritance(self):
        world = _world()
        ctx = extend(
            LocationContext.root(world),
            Link(ScopeLevel.SETTLEMENT, _nl("t1", "c", "settlement")),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(ctx, EmptyLink(ScopeLevel.AREA))
        ctx = extend(ctx, Link(ScopeLevel.BUILDING, _nl()))
        ctx = extend(ctx, Link(ScopeLevel.ROOM, _room()), rng=Random(0))
        self.assertEqual(ctx.economic_tier, "t1")
        self.assertEqual(
            ctx.provenance["economic_tier"],
            (ScopeLevel.SETTLEMENT,
             "BundleNamedLocation.system_economic_tier"),
        )

    def test_upper_anchor_propagates_through_null_levels(self):
        ctx = _chain_to_building(LocationContext.root(_world()),
                                 city="t2")
        ctx = extend(ctx, Link(ScopeLevel.ROOM, _room()), rng=Random(0))
        self.assertEqual(ctx.economic_tier, "t2")

    def test_skeleton_feeds_settlement_level_below_nl(self):
        # Both settlement link objects feed the level; the NL stamp is
        # declared above the skeleton in the chain.
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
            Link(ScopeLevel.SETTLEMENT, _skeleton("t0")),
        )
        self.assertEqual(ctx.economic_tier, "t0")
        ctx2 = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl("t5", "c")),
            Link(ScopeLevel.SETTLEMENT, _skeleton("t0")),
        )
        self.assertEqual(ctx2.economic_tier, "t5")

    def test_city_size_nl_beats_skeleton_and_inherits_down(self):
        # M7: CITY_SIZE resolves only at the settlement scope — the
        # authored NL node sits above the skeleton node; deeper scopes
        # inherit the value unchanged.
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c", size="large")),
            Link(ScopeLevel.SETTLEMENT, _skeleton(size="small")),
        )
        self.assertEqual(ctx.system_city_size, "large")
        self.assertEqual(
            ctx.provenance["system_city_size"],
            (ScopeLevel.SETTLEMENT,
             "BundleNamedLocation.system_city_size"),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(ctx, Link(ScopeLevel.AREA, _plot()))
        ctx = extend(ctx, Link(ScopeLevel.BUILDING, _nl()))
        self.assertEqual(ctx.system_city_size, "large")

    def test_city_size_skeleton_feeds_and_default_is_canonical(self):
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
            Link(ScopeLevel.SETTLEMENT, _skeleton(size="small")),
        )
        self.assertEqual(ctx.system_city_size, "small")
        self.assertEqual(
            ctx.provenance["system_city_size"],
            (ScopeLevel.SETTLEMENT, "SettlementSkeleton.system_city_size"),
        )
        with self.assertLogs(level="WARNING") as captured:
            empty = extend(
                LocationContext.root(_world()),
                EmptyLink(ScopeLevel.SETTLEMENT),
            )
        # The tier default warns; the canonical size default is silent.
        self.assertFalse(
            [r for r in captured.records
             if "city_size" in r.getMessage()],
        )
        self.assertEqual(empty.system_city_size, "medium")
        self.assertEqual(
            empty.provenance["system_city_size"],
            (ScopeLevel.WORLD, "default:canonical_default"),
        )

    def test_density_nl_beats_skeleton_and_inherits_down(self):
        # M8: NL authored density sits above the skeleton node at the
        # settlement scope; deeper scopes inherit unchanged.
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT,
                 _nl(uid="c", density="dense")),
            Link(ScopeLevel.SETTLEMENT, _skeleton(density="sparse")),
        )
        self.assertEqual(ctx.settlement_density, "dense")
        self.assertEqual(
            ctx.provenance["settlement_density"],
            (ScopeLevel.SETTLEMENT,
             "BundleNamedLocation.settlement_density"),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(ctx, Link(ScopeLevel.AREA, _plot()))
        self.assertEqual(ctx.settlement_density, "dense")

    def test_density_district_template_overrides_settlement(self):
        # M8 district-first: an authored district template density is
        # the chain top — it beats the settlement value; a template
        # without density leaves the inherited value standing.
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT,
                 _nl(uid="c", density="sparse")),
            Link(ScopeLevel.SETTLEMENT, _skeleton(density="medium")),
        )
        self.assertEqual(ctx.settlement_density, "sparse")
        district = extend(
            ctx, Link(ScopeLevel.DISTRICT, _dte(density="dense")),
        )
        self.assertEqual(district.settlement_density, "dense")
        self.assertEqual(
            district.provenance["settlement_density"],
            (ScopeLevel.DISTRICT, "DistrictTemplateEntry.density"),
        )
        plain = extend(ctx, Link(ScopeLevel.DISTRICT, _dte()))
        self.assertEqual(plain.settlement_density, "sparse")

    def test_density_skeleton_feeds_and_default_is_canonical(self):
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
            Link(ScopeLevel.SETTLEMENT, _skeleton(density="sparse")),
        )
        self.assertEqual(ctx.settlement_density, "sparse")
        self.assertEqual(
            ctx.provenance["settlement_density"],
            (ScopeLevel.SETTLEMENT,
             "SettlementSkeleton.settlement_density"),
        )
        with self.assertLogs(level="WARNING") as captured:
            empty = extend(
                LocationContext.root(_world()),
                EmptyLink(ScopeLevel.SETTLEMENT),
            )
        # The tier default warns; the canonical density default is silent.
        self.assertFalse(
            [r for r in captured.records
             if "density" in r.getMessage()],
        )
        self.assertEqual(empty.settlement_density, "medium")
        self.assertEqual(
            empty.provenance["settlement_density"],
            (ScopeLevel.WORLD, "default:canonical_default"),
        )

    def test_area_tier_beats_band_and_range(self):
        ctx = _chain_to_building(LocationContext.root(_world()))
        area_ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        area_ctx = extend(area_ctx, EmptyLink(ScopeLevel.DISTRICT))
        area_ctx = extend(
            area_ctx,
            Link(ScopeLevel.AREA,
                 _plot(tier="t7", band="common", tier_range=("t1", "t3"))),
            rng=Random(0),
        )
        self.assertEqual(area_ctx.economic_tier, "t7")

    def test_district_nl_stamp_beats_dte_range(self):
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        ctx = extend(
            ctx,
            Link(ScopeLevel.DISTRICT, _nl("t6", "d")),
            Link(ScopeLevel.DISTRICT, _dte(("t1", "t3"))),
            rng=Random(0),
        )
        self.assertEqual(ctx.economic_tier, "t6")

    def test_range_materializes_nearest_to_anchor(self):
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl("t1", "c", "settlement")),
        )
        ctx = extend(
            ctx, Link(ScopeLevel.DISTRICT, _dte(("t2", "t8"))),
        )
        # Anchor "t1" is below the range — the pick clamps to "t2".
        self.assertEqual(ctx.economic_tier, "t2")
        self.assertEqual(
            ctx.provenance["economic_tier"],
            (ScopeLevel.DISTRICT,
             "DistrictTemplateEntry.economic_tier_range"),
        )

    def test_band_materializes_once_with_caller_rng(self):
        rng = Mock(wraps=Random(7))
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(
            ctx, Link(ScopeLevel.AREA, _plot(band="common")), rng=rng,
        )
        # No authored anchor above (settlement NL is null): the rng is
        # consumed exactly once, at the materialize point.
        self.assertIn(ctx.economic_tier, {"t1", "t2", "t3"})
        calls = [m for m in rng.method_calls if m[0] == "choice"]
        self.assertEqual(len(calls), 1)

    def test_band_anchored_pick_is_deterministic(self):
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl("t9", "c", "settlement")),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(
            ctx, Link(ScopeLevel.AREA, _plot(band="common")),
            rng=Random(0),
        )
        # Anchor t9 → nearest common-band tier is t3 — no rng consumed.
        self.assertEqual(ctx.economic_tier, "t3")

    def test_materialize_does_not_reroll_at_deeper_scope(self):
        rng = Mock(wraps=Random(11))
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(
            ctx, Link(ScopeLevel.AREA, _plot(band="rich")), rng=rng,
        )
        value_at_area = ctx.economic_tier
        ctx = extend(
            ctx, Link(ScopeLevel.BUILDING, _nl()), rng=Mock(wraps=Random(99)),
        )
        # The building scope inherits the materialized value — the area
        # band is never re-rolled.
        self.assertEqual(ctx.economic_tier, value_at_area)
        self.assertEqual(ctx.economic_tier, "t9")

    def test_materialize_without_rng_is_a_caller_bug(self):
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        with self.assertRaisesRegex(ValueError, "requires rng"):
            extend(ctx, Link(ScopeLevel.AREA, _plot(band="common")))

    def test_empty_chain_uses_registry_median_with_warning(self):
        ctx = _chain_to_building(LocationContext.root(_world()))
        ctx = extend(ctx, Link(ScopeLevel.ROOM, _room()), rng=Random(0))
        # Where the default was applied: at the first scope boundary.
        self.assertEqual(ctx.economic_tier, "t5")

    def test_median_warns_once_at_first_empty_scope(self):
        module = ("app.dataModel.economy.economyTier"
                  ".worldEconomyTierRegistry")
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        with self.assertLogs(module, level="WARNING") as captured:
            extend(LocationContext.root(_world()),
                   Link(ScopeLevel.SETTLEMENT, _nl(uid="c")))
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(ctx.economic_tier, "t5")

    def test_provenance_records_default_source(self):
        ctx = extend(
            LocationContext.root(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        self.assertEqual(
            ctx.provenance["economic_tier"],
            (ScopeLevel.WORLD, "default:registry_median"),
        )


if __name__ == "__main__":
    unittest.main()
