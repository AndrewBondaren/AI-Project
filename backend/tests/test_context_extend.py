"""S3 engine tests — tz_cascade_context §4; no production wiring."""

import gc
import unittest
from random import Random
from unittest.mock import Mock, patch
from typing import Annotated

from pydantic import BaseModel, create_model

from app.application.worldData.context.cascadeLink import EmptyLink, Link
from app.application.worldData.context.contextResolver import extend, scope_sequence
from app.application.worldData.context.runtimeChain import bind_chain
from app.application.worldData.context.locationScope import empty_location_chain, root_context
from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import (
    WorldEconomyTierRegistry,
)
from app.dataModel.locations.context.cascadeParams import ECONOMIC_TIER
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.cascade.cascadeSpec import (
    Cascade, CascadeChannel, CascadeDefault, CascadeLink, FieldRef, DefaultPolicy, ScopeAxis,
)
from app.dataModel.cascade.cascadeGraph import ordered_scopes
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
from app.dataModel.materials.enums.materialCategory import MaterialCategory
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
from app.db.models.world import World


def _world(with_materials=False):
    tiers = WorldEconomyTierRegistry([
        EconomyTierEntry(system_tier=f"t{i}", display_tier=f"Tier {i}",
                         base_value=i * 10)
        for i in range(10)
    ])
    materials = None
    if with_materials:
        materials = WorldMaterialRegistry([
            MaterialRegistryEntry(
                system_material=f"{use}_{entry.system_tier}",
                display_name=f"{use} {entry.system_tier}",
                material_category=MaterialCategory.SOLID,
                tags=["construction"], use_type=[use],
                economic_tier=entry.system_tier,
            )
            for entry in tiers.root for use in ("wall", "floor")
        ])
    return World(
        world_uid="ctx-world", name="Ctx", created_at="2026-10-03",
        economic_tier_registry=tiers.model_dump(mode="json"),
        material_registry=(
            materials.model_dump(mode="json") if materials else None
        ),
    )


def _nl(tier=None, uid="nl", location_type="building", size=None,
        density=None, wall=None, floor=None, dominant=None):
    return BundleNamedLocation(
        location_uid=uid, display_name=uid,
        system_location_type=location_type, system_economic_tier=tier,
        system_city_size=size, settlement_density=density,
        parent_wall_material=wall, parent_floor_material=floor,
        dominant_material=dominant,
    )


def _room(tier=None):
    return RoomDef(
        room_id="r1", display_name="Room", room_type="hall",
        is_public=True, is_forbidden=False, required=True,
        size={"width_range": [5, 5], "depth_range": [5, 5]},
        economic_tier=tier,
    )


def _skeleton(tier=None, size=None, density=None, dominant=None):
    return SettlementSkeleton(
        economic_tier=tier, system_city_size=size,
        settlement_density=density, dominant_material=dominant,
    )


def _payload(size=None, density=None, dominant=None):
    return SettlementPayload(system_city_size=size, settlement_density=density,
                             dominant_material=dominant)


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
        ctx = extend(root_context(_world()),
                     Link(ScopeLevel.SETTLEMENT, _nl(uid="c")))
        with self.assertRaisesRegex(ValueError, "strictly below"):
            extend(ctx, Link(ScopeLevel.SETTLEMENT, _nl(uid="c2")))

    def test_skipped_level_fails(self):
        with self.assertRaisesRegex(ValueError, "skips a level"):
            extend(root_context(_world()),
                   Link(ScopeLevel.DISTRICT, _nl(uid="d")))

    def test_level_above_context_fails(self):
        ctx = _chain_to_building(root_context(_world()))
        with self.assertRaisesRegex(ValueError, "strictly below"):
            extend(ctx, Link(ScopeLevel.SETTLEMENT, _nl(uid="c")))

    def test_mixed_levels_in_one_extend_fails(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            extend(root_context(_world()),
                   Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
                   Link(ScopeLevel.DISTRICT, _nl(uid="d")))

    def test_foreign_axis_fails(self):
        class FactionScope(ScopeAxis):
            FACTION = "faction"
            CHAPTER = "chapter"

        with self.assertRaisesRegex(ValueError, "axis"):
            extend(root_context(_world()),
                   Link(FactionScope.CHAPTER, _nl(uid="x")))

    def test_object_without_channel_fails(self):
        class PlainPojo(BaseModel):
            note: str = "x"

        with self.assertRaisesRegex(TypeError, "no cascade channel"):
            extend(root_context(_world()),
                   Link(ScopeLevel.SETTLEMENT, PlainPojo()))

    def test_object_at_wrong_level_fails(self):
        with self.assertRaisesRegex(TypeError, "no cascade channel"):
            extend(root_context(_world()),
                   Link(ScopeLevel.SETTLEMENT, _room("t9")))


class RuntimeLinkedListTests(unittest.TestCase):
    def _fixture(self):
        # No reliance on the locations enum, field names or model table.
        axis = ScopeAxis("SignalScope", {
            "LEAF": "leaf", "FIRST": "first", "ROOT": "root",
            "MIDDLE": "middle",
        })
        defaults = create_model("SignalDefaults", signal=(str, "fallback"))
        param = Cascade(
            field="signal", default=DefaultPolicy.CANONICAL_DEFAULT,
            axis=axis, default_source=CascadeDefault(FieldRef(lambda: defaults, lambda pojo: pojo.signal)),
            levels=(axis.FIRST, axis.MIDDLE, axis.LEAF),
        )
        source = create_model("SignalSource", signal=(Annotated[
            str | None,
            CascadeChannel(param, axis.LEAF,
                           below=CascadeLink(FieldRef(lambda: source, lambda pojo: pojo.signal), axis.MIDDLE)),
            CascadeChannel(param, axis.MIDDLE,
                           below=CascadeLink(FieldRef(lambda: source, lambda pojo: pojo.signal), axis.FIRST)),
            CascadeChannel(param, axis.FIRST),
        ], None))
        # Override inherited parameter fields with plain fields, then add
        # a new metadata-bound parameter to the context.
        plain = {
            name: (str | None, None)
            for name, info in LocationContext.model_fields.items()
            if any(isinstance(meta, Cascade) for meta in info.metadata)
        }
        context = create_model(
            "SignalContext", __base__=LocationContext, **plain,
            level=(axis, ...),
            signal=(Annotated[str | None, param], None),
        )
        root = context(level=axis.ROOT)
        root._default_sources = (defaults(),)
        return axis, param, source, root

    def test_new_parameter_and_reordered_enum_use_declared_links(self):
        axis, _, source, root = self._fixture()
        ctx = extend(root, Link(axis.FIRST, source(signal="first")))
        self.assertEqual(scope_sequence(ctx),
                         (axis.ROOT, axis.FIRST, axis.MIDDLE, axis.LEAF))
        ctx = extend(ctx, EmptyLink(axis.MIDDLE))
        leaf = extend(ctx, Link(axis.LEAF, source(signal="leaf")))
        self.assertEqual(leaf.signal, "leaf")
        self.assertEqual(leaf.provenance["signal"],
                         (axis.LEAF, "SignalSource.signal"))
        self.assertEqual(ctx.signal, "first")
        self.assertEqual(root._links, {})
        self.assertEqual(root._node_results, {})

    def test_terminal_default_reads_supplied_pojo_value(self):
        axis, _, _, root = self._fixture()
        defaults = type(root._default_sources[0])
        root._default_sources = (defaults(signal="caller-default"),)
        first = extend(root, EmptyLink(axis.FIRST))
        leaf = extend(extend(first, EmptyLink(axis.MIDDLE)), EmptyLink(axis.LEAF))
        self.assertEqual(leaf.signal, "caller-default")
        self.assertEqual(leaf.provenance["signal"],
                         (axis.ROOT, "default:canonical_default"))

    def test_missing_and_ambiguous_default_objects_are_rejected(self):
        for count in (0, 2):
            axis, _, _, root = self._fixture()
            root._default_sources = root._default_sources * count
            with self.subTest(count=count), self.assertRaisesRegex(
                ValueError, f"got {count}",
            ):
                extend(root, EmptyLink(axis.FIRST))

    def test_none_terminal_default_is_rejected(self):
        axis, _, _, root = self._fixture()
        defaults = type(root._default_sources[0])
        root._default_sources = (defaults.model_construct(signal=None),)
        with self.assertRaisesRegex(ValueError, "returned None"):
            extend(root, EmptyLink(axis.FIRST))

    def test_authored_chain_does_not_require_terminal_default(self):
        axis, _, source, root = self._fixture()
        root._default_sources = ()
        first = extend(root, Link(axis.FIRST, source(signal="authored")))
        self.assertEqual(extend(first, EmptyLink(axis.MIDDLE)).signal, "authored")

    def test_location_default_median_is_lazy(self):
        world = _world()
        with patch.object(WorldEconomyTierRegistry, "resolve_default") as median:
            root = root_context(world)
            ctx = extend(root, Link(ScopeLevel.SETTLEMENT, _nl("t7")))
            self.assertEqual(ctx.economic_tier, "t7")
            median.assert_not_called()

    def test_location_default_median_is_read_once(self):
        world = _world()
        original = WorldEconomyTierRegistry.resolve_default
        calls = []

        def resolve(registry, policy):
            calls.append(policy)
            return original(registry, policy)

        with patch.object(WorldEconomyTierRegistry, "resolve_default", resolve):
            root = root_context(world)
            self.assertEqual(calls, [])
            with self.assertLogs(level="WARNING"):
                first = extend(root, EmptyLink(ScopeLevel.SETTLEMENT))
            with self.assertNoLogs(level="WARNING"):
                district = extend(first, EmptyLink(ScopeLevel.DISTRICT))
            self.assertEqual(district.economic_tier, first.economic_tier)
            self.assertEqual(calls, [DefaultPolicy.REGISTRY_MEDIAN])

    def test_incomplete_prefix_cannot_skip_declared_boundary(self):
        axis, _, source, root = self._fixture()
        first = extend(root, Link(axis.FIRST, source(signal="first")))
        with self.assertRaisesRegex(ValueError, "skips a level"):
            extend(first, EmptyLink(axis.LEAF))

    def test_iterator_keeps_all_declared_nodes_including_empty_ones(self):
        axis, param, source, _ = self._fixture()
        parent = source(signal="first")
        chain = list(bind_chain(param, {axis.FIRST: (parent,)}))
        self.assertEqual([bound.node.level for bound in chain],
                         [axis.LEAF, axis.MIDDLE, axis.FIRST])
        self.assertEqual([bound.obj for bound in chain], [None, None, parent])

    def test_none_and_pojo_default_values_feed_the_chain(self):
        axis, _, source, root = self._fixture()
        first = extend(root, Link(axis.FIRST, source(signal="first")))
        middle = extend(first, Link(axis.MIDDLE, source()))
        self.assertEqual(middle.signal, "first")
        self.assertEqual(middle.provenance["signal"],
                         (axis.FIRST, "SignalSource.signal"))
        # Values obtained from model defaults are read like template values.
        source.model_fields["signal"].default = "pojo-default"
        source.model_rebuild(force=True)
        leaf = extend(middle, Link(axis.LEAF, source()))
        self.assertEqual(leaf.signal, "pojo-default")

    def test_ancestor_nodes_are_snapshots(self):
        axis, _, source, root = self._fixture()
        parent = source(signal="original")
        first = extend(root, Link(axis.FIRST, parent))
        parent.signal = "mutated-after-resolution"
        middle = extend(first, EmptyLink(axis.MIDDLE))
        self.assertEqual(middle.signal, "original")
        self.assertEqual(middle.provenance["signal"],
                         (axis.FIRST, "SignalSource.signal"))

    def test_child_contexts_have_independent_node_results(self):
        axis, _, source, root = self._fixture()
        first = extend(root, Link(axis.FIRST, source(signal="first")))
        left = extend(first, Link(axis.MIDDLE, source(signal="left")))
        right = extend(first, Link(axis.MIDDLE, source(signal="right")))
        self.assertEqual((first.signal, left.signal, right.signal),
                         ("first", "left", "right"))
        self.assertEqual(extend(left, EmptyLink(axis.LEAF)).signal, "left")
        self.assertEqual(extend(right, EmptyLink(axis.LEAF)).signal, "right")

    def test_multiple_objects_for_same_channel_are_ambiguous(self):
        axis, _, source, root = self._fixture()
        with self.assertRaisesRegex(ValueError, "ambiguous source objects"):
            extend(root, Link(axis.FIRST, source(signal="one")),
                   Link(axis.FIRST, source(signal="two")))
        self.assertEqual(root._node_results, {})

    def test_ambiguous_scope_order_does_not_use_enum_as_tie_breaker(self):
        class AdditionalAxis(ScopeAxis):
            ROOT = "root"
            FIRST = "first"
            OTHER = "other"

        # Test the declaration mechanism directly: unrelated field chains
        # do not establish which scope follows the shared root.
        left_param = Cascade(
            "left", DefaultPolicy.NONE_IS_ERROR, AdditionalAxis,
            levels=(AdditionalAxis.FIRST,),
        )
        right_param = Cascade(
            "right", DefaultPolicy.NONE_IS_ERROR, AdditionalAxis,
            levels=(AdditionalAxis.OTHER,),
        )
        sources = create_model(
            "IndependentSources",
            left=(Annotated[str | None,
                            CascadeChannel(left_param, AdditionalAxis.FIRST)], None),
            right=(Annotated[str | None,
                             CascadeChannel(right_param, AdditionalAxis.OTHER)], None),
        )
        with patch("app.dataModel.cascade.cascadeGraph._source_models",
                   return_value={sources}):
            with self.assertRaisesRegex(ValueError, "ambiguous or cyclic"):
                ordered_scopes((left_param, right_param), AdditionalAxis.ROOT)

    def test_empty_chain_to_root_stays_unresolved(self):
        root = empty_location_chain(_world(), ScopeLevel.WORLD)
        self.assertIs(root.level, ScopeLevel.WORLD)
        self.assertEqual(root.provenance, {})
        self.assertEqual(root._node_results, {})

    def test_materialize_is_called_once_per_new_scope_node(self):
        from app.application.worldData.context import contextResolver

        resolver = Mock(wraps=contextResolver._MATERIALIZE["economic_tier"])
        with patch.dict(contextResolver._MATERIALIZE,
                        {"economic_tier": resolver}):
            settlement = extend(
                root_context(_world()), EmptyLink(ScopeLevel.SETTLEMENT),
            )
            district = extend(
                settlement, Link(ScopeLevel.DISTRICT, _dte(("t2", "t5"))),
                rng=Random(17),
            )
            area = extend(district, Link(ScopeLevel.AREA, _plot(band="common")))
            self.assertEqual(resolver.call_count, 2)
            building = extend(area, EmptyLink(ScopeLevel.BUILDING))
            room = extend(building, Link(ScopeLevel.ROOM, _room()))
            self.assertEqual(resolver.call_count, 2)
        self.assertEqual(room.economic_tier, area.economic_tier)
        self.assertEqual(room.provenance["economic_tier"],
                         area.provenance["economic_tier"])


class ExtendResolutionTests(unittest.TestCase):
    def test_root_does_not_resolve_or_materialize(self):
        ctx = root_context(_world())
        self.assertIsNone(ctx.economic_tier)
        self.assertEqual(ctx.provenance, {})
        self.assertIs(ctx.level, ScopeLevel.WORLD)

    def test_room_explicit_beats_everything(self):
        ctx = _chain_to_building(root_context(_world()),
                                 city="t1", building="t8")
        ctx = extend(ctx, Link(ScopeLevel.ROOM, _room("t9")),
                     rng=Random(0))
        self.assertEqual(ctx.economic_tier, "t9")
        self.assertEqual(
            ctx.provenance["economic_tier"],
            (ScopeLevel.ROOM, "RoomDef.economic_tier"),
        )

    def test_null_authored_continues_inheritance(self):
        ctx = _chain_to_building(root_context(_world()),
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
            root_context(world),
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
        ctx = _chain_to_building(root_context(_world()),
                                 city="t2")
        ctx = extend(ctx, Link(ScopeLevel.ROOM, _room()), rng=Random(0))
        self.assertEqual(ctx.economic_tier, "t2")

    def test_skeleton_feeds_settlement_level_below_nl(self):
        # Both settlement link objects feed the level; the NL stamp is
        # declared above the skeleton in the chain.
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
            Link(ScopeLevel.SETTLEMENT, _skeleton("t0")),
        )
        self.assertEqual(ctx.economic_tier, "t0")
        ctx2 = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl("t5", "c")),
            Link(ScopeLevel.SETTLEMENT, _skeleton("t0")),
        )
        self.assertEqual(ctx2.economic_tier, "t5")

    def test_city_size_payload_beats_legacy_skeleton_and_inherits_down(self):
        # P4: only the payload declares this channel; legacy skeleton
        # values cannot override it. Deeper scopes inherit unchanged.
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c", size="large")),
            Link(ScopeLevel.SETTLEMENT, _payload(size="large")),
            Link(ScopeLevel.SETTLEMENT, _skeleton(size="small")),
        )
        self.assertEqual(ctx.system_city_size, "large")
        self.assertEqual(
            ctx.provenance["system_city_size"],
            (ScopeLevel.SETTLEMENT,
             "SettlementPayload.system_city_size"),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(ctx, Link(ScopeLevel.AREA, _plot()))
        ctx = extend(ctx, Link(ScopeLevel.BUILDING, _nl()))
        self.assertEqual(ctx.system_city_size, "large")

    def test_city_size_payload_feeds_and_default_is_canonical(self):
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
            Link(ScopeLevel.SETTLEMENT, _payload(size="small")),
        )
        self.assertEqual(ctx.system_city_size, "small")
        self.assertEqual(
            ctx.provenance["system_city_size"],
            (ScopeLevel.SETTLEMENT, "SettlementPayload.system_city_size"),
        )
        with self.assertLogs(level="WARNING") as captured:
            empty = extend(
                root_context(_world()),
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

    def test_density_payload_beats_legacy_skeleton_and_inherits_down(self):
        # P4: payload density is the settlement source; legacy skeleton
        # values are plain fields. Deeper scopes inherit unchanged.
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT,
                 _nl(uid="c", density="dense")),
            Link(ScopeLevel.SETTLEMENT, _payload(density="dense")),
            Link(ScopeLevel.SETTLEMENT, _skeleton(density="sparse")),
        )
        self.assertEqual(ctx.settlement_density, "dense")
        self.assertEqual(
            ctx.provenance["settlement_density"],
            (ScopeLevel.SETTLEMENT,
             "SettlementPayload.settlement_density"),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(ctx, Link(ScopeLevel.AREA, _plot()))
        self.assertEqual(ctx.settlement_density, "dense")

    def test_density_district_template_overrides_settlement(self):
        # M8 district-first: an authored district template density is
        # the chain top — it beats the settlement value; a template
        # without density leaves the inherited value standing.
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT,
                 _nl(uid="c", density="sparse")),
            Link(ScopeLevel.SETTLEMENT, _payload(density="sparse")),
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

    def test_density_payload_feeds_and_default_is_canonical(self):
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
            Link(ScopeLevel.SETTLEMENT, _payload(density="sparse")),
        )
        self.assertEqual(ctx.settlement_density, "sparse")
        self.assertEqual(
            ctx.provenance["settlement_density"],
            (ScopeLevel.SETTLEMENT,
             "SettlementPayload.settlement_density"),
        )
        with self.assertLogs(level="WARNING") as captured:
            empty = extend(
                root_context(_world()),
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

    def test_wall_material_inherits_and_deeper_authored_wins(self):
        # M9: settlement NL authored material inherits down; a deeper
        # authored node (building NL, then room NL) overrides it.
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT,
                 _nl(uid="c", location_type="settlement", wall="granite")),
        )
        self.assertEqual(ctx.wall_material, "granite")
        district = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        district = extend(district, EmptyLink(ScopeLevel.AREA))
        plain = extend(district, Link(ScopeLevel.BUILDING, _nl()))
        self.assertEqual(plain.wall_material, "granite")
        self.assertEqual(
            plain.provenance["wall_material"],
            (ScopeLevel.SETTLEMENT,
             "BundleNamedLocation.parent_wall_material"),
        )
        building = extend(
            district, Link(ScopeLevel.BUILDING, _nl(wall="oak")),
        )
        self.assertEqual(building.wall_material, "oak")
        room = extend(
            building, Link(ScopeLevel.ROOM, _nl(wall="marble")),
        )
        self.assertEqual(room.wall_material, "marble")
        self.assertEqual(
            room.provenance["wall_material"],
            (ScopeLevel.ROOM,
             "BundleNamedLocation.parent_wall_material"),
        )

    def test_floor_material_inherits_and_deeper_authored_wins(self):
        # M9: same chain for `parent_floor_material` — wall and floor
        # resolve independently.
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT,
                 _nl(uid="c", location_type="settlement",
                     wall="granite", floor="basalt")),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(ctx, EmptyLink(ScopeLevel.AREA))
        ctx = extend(
            ctx,
            Link(ScopeLevel.BUILDING, _nl(floor="oak_floor")),
        )
        self.assertEqual(ctx.wall_material, "granite")
        self.assertEqual(ctx.floor_material, "oak_floor")
        self.assertEqual(
            ctx.provenance["floor_material"],
            (ScopeLevel.BUILDING,
             "BundleNamedLocation.parent_floor_material"),
        )

    def test_material_defaults_are_canonical_and_silent(self):
        # M9: no authored node anywhere → the dataModel canonical
        # construction defaults — no cascade `default_applied` warning
        # for the parent_* params (the tier median warning is a
        # separate parameter's default; the M10 dominant-material fold
        # may legitimately warn from the registry pick itself).
        with self.assertLogs(level="WARNING") as captured:
            ctx = extend(
                root_context(_world()),
                EmptyLink(ScopeLevel.SETTLEMENT),
            )
        self.assertFalse(
            [r for r in captured.records
             if "parent_wall_material" in r.getMessage()
             or "parent_floor_material" in r.getMessage()],
        )
        self.assertEqual(ctx.wall_material, "stone")
        self.assertEqual(ctx.floor_material, "wood")
        self.assertEqual(
            ctx.provenance["wall_material"],
            (ScopeLevel.WORLD, "default:canonical_default"),
        )
        self.assertEqual(
            ctx.provenance["floor_material"],
            (ScopeLevel.WORLD, "default:canonical_default"),
        )
        # The provisional default does not re-resolve: a deeper authored
        # node still overrides it.
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(ctx, EmptyLink(ScopeLevel.AREA))
        ctx = extend(
            ctx, Link(ScopeLevel.BUILDING, _nl(wall="iron")),
        )
        self.assertEqual(ctx.wall_material, "iron")
        self.assertEqual(ctx.floor_material, "wood")

    def test_dominant_material_payload_beats_legacy_skeleton_and_inherits(self):
        # P4: the payload is the only authored channel. Legacy skeleton
        # values are plain fields; deeper scopes inherit unchanged.
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT,
                 _nl(uid="c", dominant="marble")),
            Link(ScopeLevel.SETTLEMENT, _payload(dominant="marble")),
            Link(ScopeLevel.SETTLEMENT, _skeleton(dominant="granite")),
        )
        self.assertEqual(ctx.dominant_material, "marble")
        self.assertEqual(
            ctx.provenance["dominant_material"],
            (ScopeLevel.SETTLEMENT,
             "SettlementPayload.dominant_material"),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        ctx = extend(ctx, EmptyLink(ScopeLevel.AREA))
        ctx = extend(ctx, Link(ScopeLevel.BUILDING, _nl()))
        self.assertEqual(ctx.dominant_material, "marble")

    def test_dominant_material_payload_feeds(self):
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
            Link(ScopeLevel.SETTLEMENT, _payload(dominant="granite")),
        )
        self.assertEqual(ctx.dominant_material, "granite")
        self.assertEqual(
            ctx.provenance["dominant_material"],
            (ScopeLevel.SETTLEMENT,
             "SettlementPayload.dominant_material"),
        )

    def test_dominant_material_fold_picks_by_resolved_tier(self):
        # M10 — first `Cascade.fold`: with no authored node the fold
        # picks a registry wall material for the tier resolved at this
        # same scope (provenance records the fold, not a default).
        ctx = extend(
            root_context(_world(with_materials=True)),
            Link(ScopeLevel.SETTLEMENT,
                 _nl("t4", "c", "settlement")),
        )
        self.assertEqual(ctx.dominant_material, "wall_t4")
        self.assertEqual(
            ctx.provenance["dominant_material"],
            (ScopeLevel.SETTLEMENT, "fold:dominant_material"),
        )
        # The same chain resolves identically — the fold rng stream is
        # seeded per scope, never shared with tier materialize.
        again = extend(
            root_context(_world(with_materials=True)),
            Link(ScopeLevel.SETTLEMENT,
                 _nl("t4", "c", "settlement")),
        )
        self.assertEqual(again.dominant_material, "wall_t4")

    def test_dominant_material_authored_beats_fold(self):
        ctx = extend(
            root_context(_world(with_materials=True)),
            Link(ScopeLevel.SETTLEMENT,
                 _nl("t4", "c", "settlement", dominant="marble")),
            Link(ScopeLevel.SETTLEMENT, _payload(dominant="marble")),
        )
        self.assertEqual(ctx.dominant_material, "marble")
        self.assertEqual(
            ctx.provenance["dominant_material"],
            (ScopeLevel.SETTLEMENT,
             "SettlementPayload.dominant_material"),
        )

    def test_dominant_material_fold_falls_back_to_canonical(self):
        # No authored and no registry pick (empty material registry) —
        # resolve_material's own fallback lands on the canonical
        # construction default through the fold.
        ctx = extend(
            root_context(_world()),
            EmptyLink(ScopeLevel.SETTLEMENT),
        )
        self.assertEqual(ctx.dominant_material, "stone")
        self.assertEqual(
            ctx.provenance["dominant_material"],
            (ScopeLevel.SETTLEMENT, "fold:dominant_material"),
        )

    def test_area_tier_beats_band_and_range(self):
        ctx = _chain_to_building(root_context(_world()))
        area_ctx = extend(
            root_context(_world()),
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
            root_context(_world()),
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
            root_context(_world()),
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
            root_context(_world()),
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
            root_context(_world()),
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
            root_context(_world()),
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
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        ctx = extend(ctx, EmptyLink(ScopeLevel.DISTRICT))
        with self.assertRaisesRegex(ValueError, "requires rng"):
            extend(ctx, Link(ScopeLevel.AREA, _plot(band="common")))

    def test_empty_chain_uses_registry_median_with_warning(self):
        ctx = _chain_to_building(root_context(_world()))
        ctx = extend(ctx, Link(ScopeLevel.ROOM, _room()), rng=Random(0))
        # Where the default was applied: at the first scope boundary.
        self.assertEqual(ctx.economic_tier, "t5")

    def test_median_warns_once_at_first_empty_scope(self):
        module = "app.application.worldData.context.cascadeLog"
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        with self.assertLogs(module, level="WARNING") as captured:
            extend(root_context(_world()),
                   Link(ScopeLevel.SETTLEMENT, _nl(uid="c")))
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(ctx.economic_tier, "t5")

    def test_provenance_records_default_source(self):
        ctx = extend(
            root_context(_world()),
            Link(ScopeLevel.SETTLEMENT, _nl(uid="c")),
        )
        self.assertEqual(
            ctx.provenance["economic_tier"],
            (ScopeLevel.WORLD, "default:registry_median"),
        )


if __name__ == "__main__":
    unittest.main()
