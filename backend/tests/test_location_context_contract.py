"""S2 contract tests — tz_cascade_context §3, §5; no production wiring."""

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Annotated
from unittest.mock import patch

import gc

from pydantic import BaseModel, ValidationError, computed_field, create_model

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.economy.economyTier.economyTierEntry import EconomyTierEntry
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import WorldEconomyTierRegistry
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import (
    CITY_SIZE,
    DOMINANT_MATERIAL,
    ECONOMIC_TIER,
    FLOOR_MATERIAL,
    SETTLEMENT_DENSITY,
    WALL_MATERIAL,
)
from app.dataModel.locations.settlement.enums.districtDensity import (
    DistrictDensity,
)
from app.dataModel.cascade.cascadeGraph import (
    bind_field,
    cascade_channels,
    check_link,
    ordered_chain,
)
from app.dataModel.cascade.cascadeSpec import (
    Cascade,
    CascadeChannel,
    CascadeDefault,
    CascadeLink,
    FieldRef,
    ChannelKind,
    DefaultPolicy,
    ScopeAxis,
)
from app.dataModel.cascade.cascadeVerify import (
    verify_cascade_contract,
)
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.locations.namedLocation.bundleNamedLocation import BundleNamedLocation
from app.dataModel.registryKey import RegistryKey
from app.dataModel.locations.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.locations.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.room.roomDef import RoomDef
from app.db.models.world import World


def registry(values):
    return WorldEconomyTierRegistry([
        EconomyTierEntry(system_tier=key, display_tier=key, base_value=value)
        for key, value in values
    ])


class LinkedListAxis(ScopeAxis):
    ROOT = "root"
    TAIL = "tail"
    HEAD = "head"
    MIDDLE = "middle"


class FieldRefContractTests(unittest.TestCase):
    def test_binding_is_independent_of_selector_identity(self):
        class Source(BaseModel):
            signal: str = "value"

        first = FieldRef(lambda: Source, lambda pojo: pojo.signal)
        second = FieldRef(lambda: Source, lambda pojo: pojo.signal)
        self.assertEqual(bind_field(first), bind_field(second))
        self.assertEqual(bind_field(first).field, "signal")

    def test_self_supplier_is_not_evaluated_before_class_exists(self):
        ref = FieldRef(lambda: Source, lambda pojo: pojo.signal)

        class Source(BaseModel):
            signal: str = "value"

        self.assertIs(bind_field(ref).model, Source)

    def test_selector_must_return_one_direct_attribute(self):
        class Source(BaseModel):
            signal: str = "value"

        def two_fields(pojo):
            pojo.signal
            return pojo.signal

        for selector in (
            lambda pojo: pojo.signal.nested,
            lambda pojo: pojo.signal + "suffix",
            lambda pojo: pojo.signal or "fallback",
            lambda pojo: "literal",
            lambda pojo: pojo,
            two_fields,
        ):
            with self.subTest(selector=selector):
                with self.assertRaisesRegex(ValueError, "one direct attribute"):
                    bind_field(FieldRef(lambda: Source, selector))

    def test_computed_field_is_only_allowed_for_default_binding(self):
        class Source(BaseModel):
            @computed_field
            @property
            def signal(self) -> str:
                raise AssertionError("binding must not execute computed fields")

        ref = FieldRef(lambda: Source, lambda pojo: pojo.signal)
        with self.assertRaisesRegex(ValueError, "no such field"):
            bind_field(ref)
        self.assertEqual(bind_field(ref, computed=True).field, "signal")

    def test_non_pojo_attributes_are_rejected(self):
        class Source(BaseModel):
            signal: str = "value"

            def helper(self):
                return self.signal

        for selector in (lambda pojo: pojo.helper, lambda pojo: pojo.model_fields):
            with self.assertRaisesRegex(ValueError, "no such field"):
                bind_field(FieldRef(lambda: Source, selector))

    def test_legacy_constructor_signatures_are_removed(self):
        with self.assertRaises(TypeError):
            CascadeLink(BaseModel, "signal", LinkedListAxis.HEAD)
        with self.assertRaises(TypeError):
            CascadeDefault(BaseModel, "signal")

    def test_source_selectors_are_not_hidden_in_annotated_metadata(self):
        root = Path(__file__).resolve().parents[1] / "app" / "dataModel"
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "FieldRef" not in text:
                continue
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Subscript)
                        and isinstance(node.value, ast.Name)
                        and node.value.id == "Annotated"):
                    with self.subTest(path=path.name, line=node.lineno):
                        self.assertFalse(any(
                            isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Name)
                            and child.func.id == "FieldRef"
                            for child in ast.walk(node)
                        ))


class LinkedListContractTests(unittest.TestCase):
    def _fixture(self, edges, *, fields=None, levels=None, field_types=None,
                 above_edges=None):
        """Arbitrary source fields, deliberately unlike location POJOs.

        Field and enum declaration orders both differ from the links.
        No production registry or source enumeration is changed.
        """
        fields = fields or {
            "tail": LinkedListAxis.TAIL,
            "middle": LinkedListAxis.MIDDLE,
            "signal": LinkedListAxis.HEAD,
        }
        # Each fixture has its own parameter identity. A distinct axis
        # also prevents typing.Annotated's equality cache from reusing
        # metadata from an earlier fixture's structurally equal Cascade.
        axis = ScopeAxis("SignalAxis", {
            member.name: member.value for member in LinkedListAxis
        })
        def local_level(level):
            return axis[level.name] if type(level) is LinkedListAxis else level

        fields = {name: local_level(level) for name, level in fields.items()}
        param = Cascade(
            field="signal", default=DefaultPolicy.NONE_IS_ERROR,
            axis=axis,
            levels=(tuple(local_level(level) for level in levels)
                    if levels else tuple(fields.values())),
        )
        # Synthetic fields are generated from test data, unlike production selectors.
        def ref(name):
            return FieldRef(lambda: source, lambda pojo: getattr(pojo, name))

        declarations = {}
        for name, level in fields.items():
            target = edges.get(name)
            upper = (above_edges or {}).get(name)
            channel = CascadeChannel(
                param, level,
                above=(
                    CascadeLink(ref(upper), fields.get(upper, level))
                    if upper else None
                ),
                below=(
                    CascadeLink(ref(target), fields.get(target, level))
                    if target else None
                ),
            )
            field_type = (field_types or {}).get(name, str)
            declarations[name] = (Annotated[field_type | None, channel], None)
        source = create_model("SignalSource", **declarations)
        context = create_model(
            "SignalContext", signal=(Annotated[str | None, param], None),
        )
        return param, source, context

    def _assert_broken(self, edges, pattern, **kwargs):
        param, source, context = self._fixture(edges, **kwargs)
        with patch(
            "app.dataModel.cascade.cascadeVerify._source_models",
            return_value={source},
        ), patch(
            "app.dataModel.cascade.cascadeGraph._source_models",
            return_value={source},
        ):
            with self.assertRaisesRegex(ValueError, pattern):
                verify_cascade_contract(context)
            with self.assertRaisesRegex(ValueError, pattern):
                ordered_chain(param)

    def test_declared_links_override_enum_and_field_order(self):
        param, source, context = self._fixture(
            {"signal": "middle", "middle": "tail"},
        )
        with patch(
            "app.dataModel.cascade.cascadeVerify._source_models",
            return_value={source},
        ), patch(
            "app.dataModel.cascade.cascadeGraph._source_models",
            return_value={source},
        ):
            verify_cascade_contract(context)
            chain = ordered_chain(param)
        self.assertEqual([node.field for _, node, _ in chain],
                         ["signal", "middle", "tail"])
        self.assertEqual([node.level for _, node, _ in chain],
                         [param.axis.HEAD, param.axis.MIDDLE, param.axis.TAIL])
        self.assertTrue(all(owner is source for owner, _, _ in chain))

    def test_links_across_arbitrary_source_models(self):
        param = Cascade(
            field="signal", default=DefaultPolicy.NONE_IS_ERROR,
            axis=LinkedListAxis,
            levels=(LinkedListAxis.TAIL, LinkedListAxis.MIDDLE),
        )
        tail = create_model("TemplateSignal", signal=(Annotated[
            str | None, CascadeChannel(param, LinkedListAxis.TAIL),
        ], None))
        head = create_model("StampedSignal", signal=(Annotated[
            str | None, CascadeChannel(
                param, LinkedListAxis.MIDDLE,
                below=CascadeLink(FieldRef(lambda: tail, lambda pojo: pojo.signal), LinkedListAxis.TAIL),
            ),
        ], None))
        context = create_model("SignalContext", signal=(Annotated[
            str | None, param,
        ], None))
        with patch(
            "app.dataModel.cascade.cascadeVerify._source_models",
            return_value={tail, head},
        ), patch(
            "app.dataModel.cascade.cascadeGraph._source_models",
            return_value={tail, head},
        ):
            verify_cascade_contract(context)
            self.assertEqual([owner for owner, _, _ in ordered_chain(param)],
                             [head, tail])

    def test_reverse_declarations_resolve_to_the_same_nodes(self):
        param, source, context = self._fixture(
            {"signal": "middle", "middle": "tail"},
            above_edges={"middle": "signal", "tail": "middle"},
        )
        with patch("app.dataModel.cascade.cascadeVerify._source_models",
                   return_value={source}), patch(
                       "app.dataModel.cascade.cascadeGraph._source_models",
                       return_value={source}):
            verify_cascade_contract(context)
            self.assertEqual([node.field for _, node, _ in ordered_chain(param)],
                             ["signal", "middle", "tail"])

    def test_cycle_has_no_valid_ends(self):
        self._assert_broken(
            {"signal": "middle", "middle": "tail", "tail": "signal"},
            "top.*bottom",
        )

    def test_chain_ending_in_cycle_is_rejected(self):
        self._assert_broken(
            {"signal": "middle", "middle": "tail", "tail": "middle"},
            "two above neighbours",
        )

    def test_merging_branches_are_rejected(self):
        self._assert_broken(
            {"signal": "tail", "middle": "tail"},
            "two above neighbours",
        )

    def test_splitting_branches_are_rejected(self):
        self._assert_broken(
            {"signal": "middle"}, "two below neighbours",
            above_edges={"tail": "signal"},
        )

    def test_detached_cycle_is_not_a_chain(self):
        self._assert_broken(
            {"middle": "tail", "tail": "middle"},
            "unreachable nodes",
        )

    def test_disconnected_node_is_rejected(self):
        self._assert_broken({"signal": "middle"}, "top.*bottom")

    def test_link_to_missing_field_is_rejected(self):
        self._assert_broken({"signal": "missing"}, "no such field")

    def test_incompatible_value_ends_are_rejected(self):
        self._assert_broken(
            {"signal": "middle", "middle": "tail"},
            "different types", field_types={"tail": int},
        )

    def test_required_level_coverage_is_still_verified(self):
        _, source, context = self._fixture(
            {"signal": "middle"},
            fields={"signal": LinkedListAxis.HEAD,
                    "middle": LinkedListAxis.MIDDLE},
            levels=(LinkedListAxis.HEAD, LinkedListAxis.MIDDLE,
                    LinkedListAxis.TAIL),
        )
        with patch(
            "app.dataModel.cascade.cascadeVerify._source_models",
            return_value={source},
        ):
            with self.assertRaisesRegex(ValueError, "levels without channel"):
                verify_cascade_contract(context)

    def test_foreign_axis_is_still_rejected(self):
        _, source, context = self._fixture(
            {"signal": "middle", "middle": "tail"},
            fields={"signal": LinkedListAxis.HEAD,
                    "middle": LinkedListAxis.MIDDLE,
                    "tail": ScopeLevel.ROOM},
        )
        with patch(
            "app.dataModel.cascade.cascadeVerify._source_models",
            return_value={source},
        ):
            with self.assertRaisesRegex(ValueError, "foreign axis"):
                verify_cascade_contract(context)


class DefaultSourceContractTests(unittest.TestCase):
    def _verify(self, defaults, field="signal", policy=DefaultPolicy.CANONICAL_DEFAULT):
        axis = ScopeAxis("DefaultAxis", {"SOURCE": "source"})
        param = Cascade("signal", policy, axis=axis,
                        default_source=(CascadeDefault(FieldRef(lambda: defaults, lambda pojo: getattr(pojo, field)))
                                        if defaults is not None else None))
        source = create_model("DefaultChannel", signal=(Annotated[
            str | None, CascadeChannel(param, axis.SOURCE),
        ], None))
        context = create_model("DefaultContext", signal=(Annotated[
            str | None, param,
        ], None))
        with patch("app.dataModel.cascade.cascadeVerify._source_models",
                   return_value={source}):
            verify_cascade_contract(context)

    def test_ordinary_and_computed_pojo_fields_are_supported(self):
        class ComputedDefaults(BaseModel):
            @computed_field
            @property
            def signal(self) -> str:
                return "computed"

        self._verify(create_model("PlainDefaults", signal=(str, "plain")))
        self._verify(ComputedDefaults)

    def test_missing_default_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires default_source"):
            self._verify(None)

    def test_non_pojo_default_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "POJO model"):
            self._verify(str)

    def test_missing_default_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no such field 'missing'"):
            self._verify(create_model("PlainDefaults", signal=(str, "plain")),
                         field="missing")

    def test_incompatible_default_field_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "type incompatible"):
            self._verify(create_model("WrongDefaults", signal=(int, 1)))

    def test_error_policy_forbids_a_default_source(self):
        with self.assertRaisesRegex(ValueError, "NONE_IS_ERROR forbids"):
            self._verify(create_model("PlainDefaults", signal=(str, "plain")),
                         policy=DefaultPolicy.NONE_IS_ERROR)


class LocationContextContractTests(unittest.TestCase):
    def test_canonical_level_order_and_rank(self):
        self.assertEqual([level.value for level in ScopeLevel],
                         ["world", "settlement", "district", "area", "building", "room"])
        self.assertEqual([level.rank for level in ScopeLevel], list(range(6)))
        self.assertIs(ScopeLevel("building"), ScopeLevel.BUILDING)

    def test_cascade_metadata_is_frozen_and_has_extension_slots(self):
        spec = Cascade("test_field", DefaultPolicy.NONE_IS_ERROR,
                       axis=ScopeLevel,
                       fold="test_fold", levels=(ScopeLevel.WORLD, ScopeLevel.AREA))
        self.assertEqual(spec.fold, "test_fold")
        self.assertEqual(spec.levels, (ScopeLevel.WORLD, ScopeLevel.AREA))
        with self.assertRaises(FrozenInstanceError):
            spec.field = "changed"
        tier_spec = LocationContext.model_fields["economic_tier"].metadata
        self.assertIs(tier_spec[0], ECONOMIC_TIER)
        self.assertIsNone(tier_spec[0].fold)
        self.assertIsNone(tier_spec[0].levels)

    def test_only_v1_fields_and_branded_tier(self):
        self.assertEqual(set(LocationContext.model_fields),
                         {"level", "economic_tier", "system_city_size",
                          "settlement_density", "wall_material",
                          "floor_material", "dominant_material",
                          "provenance"})
        context = LocationContext(level=ScopeLevel.BUILDING, economic_tier="custom_tier",
                                  system_city_size="custom_size",
                                  settlement_density="dense",
                                  wall_material="stone", floor_material="wood",
                                  dominant_material="granite",
                                  provenance={"economic_tier": (ScopeLevel.AREA, "economic_tier")})
        self.assertIsInstance(context.economic_tier, RegistryKey)
        self.assertIsInstance(context.system_city_size, RegistryKey)
        self.assertIsInstance(context.settlement_density, DistrictDensity)
        self.assertIsInstance(context.wall_material, RegistryKey)
        self.assertIsInstance(context.floor_material, RegistryKey)
        self.assertIsInstance(context.dominant_material, RegistryKey)
        self.assertEqual(context.provenance["economic_tier"], (ScopeLevel.AREA, "economic_tier"))
        with self.assertRaises(ValidationError):
            LocationContext(level=ScopeLevel.WORLD, unknown_param="stone")
        with self.assertRaises(ValidationError):
            LocationContext(level=ScopeLevel.BUILDING, economic_tier="")
        with self.assertRaises(ValidationError):
            LocationContext(level="unknown")
        with self.assertRaises(ValidationError):
            LocationContext(level=ScopeLevel.BUILDING, provenance={"economic_tier": ("unknown", "authored")})

    def test_model_fields_are_frozen(self):
        context = LocationContext(level=ScopeLevel.BUILDING, economic_tier="custom")
        for name, value in (("level", ScopeLevel.ROOM), ("economic_tier", "changed"), ("provenance", {})):
            with self.subTest(field=name), self.assertRaises(ValidationError) as error:
                setattr(context, name, value)
            self.assertEqual(error.exception.errors()[0]["type"], "frozen_instance")

    def test_root_is_empty_and_does_not_resolve_or_log(self):
        world = World(world_uid="context-contract", name="Contract", created_at="2026-10-03")
        with patch.object(WorldEconomyTierRegistry, "resolve_default") as default:
            with self.assertNoLogs(level="WARNING"):
                first, second = LocationContext.root(world), LocationContext.root(world)
        default.assert_not_called()
        self.assertIs(first.level, ScopeLevel.WORLD)
        self.assertIsNone(first.economic_tier)
        self.assertEqual(first.provenance, {})
        self.assertIsNot(first.provenance, second.provenance)
        self.assertIs(first._world, world)
        self.assertEqual(first.model_dump(mode="json"),
                         {"level": "world", "economic_tier": None,
                          "system_city_size": None,
                          "settlement_density": None,
                          "wall_material": None, "floor_material": None,
                          "dominant_material": None,
                          "provenance": {}})

    def test_default_median_sorts_and_uses_upper_middle_silently(self):
        # The POJO policy returns the median without logging — the
        # cascade engine emits the warning (cascade/cascadeLog).
        for entries, expected in (([("high", 90), ("low", 0), ("medium", 10)], "medium"),
                                  ([("high", 90), ("low", 0)], "high"),
                                  ([("only", 20)], "only")):
            with self.subTest(entries=entries):
                tiers = registry(entries)
                original = list(tiers.root)
                with self.assertNoLogs(level="WARNING"):
                    tier = tiers.resolve_default(DefaultPolicy.REGISTRY_MEDIAN)
                self.assertEqual(tier, expected)
                self.assertIsInstance(tier, RegistryKey)
                self.assertEqual(tiers.root, original)

    def test_missing_registry_or_unsupported_policy_is_an_error(self):
        with self.assertNoLogs(level="WARNING"):
            with self.assertRaisesRegex(ValueError, "empty registry"):
                registry([]).resolve_default(DefaultPolicy.REGISTRY_MEDIAN)
            with self.assertRaisesRegex(ValueError, "no value"):
                registry([("custom", 10)]).resolve_default(DefaultPolicy.NONE_IS_ERROR)
            with self.assertRaisesRegex(ValueError, "unsupported default policy"):
                registry([("custom", 10)]).resolve_default(DefaultPolicy.CANONICAL_DEFAULT)

    # --- S2a: linked list of fields — identity param, typed edges ---

    def test_param_identity_binds_context_and_channels(self):
        declared = [
            meta
            for info in LocationContext.model_fields.values()
            for meta in info.metadata
            if isinstance(meta, Cascade)
        ]
        for model in (BundleNamedLocation, SettlementSkeleton,
                      DistrictTemplateEntry, PlotLayoutTemplate, RoomDef):
            for _name, channel in cascade_channels(model):
                self.assertTrue(
                    any(channel.param is param for param in declared),
                    f"{model.__name__}.{_name}: channel param not "
                    "declared on LocationContext",
                )

    def test_channels_cover_the_whole_chain_per_level(self):
        models = (RoomDef, BundleNamedLocation, PlotLayoutTemplate,
                  DistrictTemplateEntry, SettlementSkeleton)
        expected = {
            ScopeLevel.ROOM: {
                (RoomDef, "economic_tier"),
                (BundleNamedLocation, "system_economic_tier"),
            },
            ScopeLevel.BUILDING: {
                (BundleNamedLocation, "system_economic_tier")},
            ScopeLevel.AREA: {
                (PlotLayoutTemplate, "economic_tier"),
                (PlotLayoutTemplate, "economic_tier_band"),
                (PlotLayoutTemplate, "economic_tier_range"),
            },
            ScopeLevel.DISTRICT: {
                (BundleNamedLocation, "system_economic_tier"),
                (DistrictTemplateEntry, "economic_tier_range"),
            },
            ScopeLevel.SETTLEMENT: {
                (BundleNamedLocation, "system_economic_tier"),
                (SettlementSkeleton, "economic_tier"),
            },
            ScopeLevel.WORLD: set(),
        }
        for level, wanted in expected.items():
            found = {
                (model, field)
                for model in models
                for field, _channel in cascade_channels(
                    model, ECONOMIC_TIER, level)
            }
            self.assertEqual(found, wanted, level.value)

    def test_scoped_params_cover_their_declared_levels(self):
        # CITY_SIZE — settlement-only; SETTLEMENT_DENSITY — the
        # district-first pair (cascade-migration M7/M8).
        self.assertEqual(
            {
                (model, field)
                for model in (BundleNamedLocation, SettlementSkeleton, SettlementPayload)
                for field, _ in cascade_channels(model, CITY_SIZE)
            },
            {
                (SettlementPayload, "system_city_size"),
            },
        )
        density = {
            level: {
                (model, field)
                for model in (BundleNamedLocation, SettlementSkeleton, SettlementPayload,
                              DistrictTemplateEntry)
                for field, _ in cascade_channels(
                    model, SETTLEMENT_DENSITY, level)
            }
            for level in ScopeLevel
        }
        self.assertEqual(
            density[ScopeLevel.DISTRICT],
            {(DistrictTemplateEntry, "density")},
        )
        self.assertEqual(
            density[ScopeLevel.SETTLEMENT],
            {
                (SettlementPayload, "settlement_density"),
            },
        )
        # M9: `parent_*_material` — the same NL field is the channel
        # node at every non-world scope (room is the top).
        for param, field in (
            (WALL_MATERIAL, "parent_wall_material"),
            (FLOOR_MATERIAL, "parent_floor_material"),
        ):
            found = {
                level: {
                    (model, name)
                    for model in (BundleNamedLocation,)
                    for name, _ in cascade_channels(model, param, level)
                }
                for level in ScopeLevel
            }
            for level in (
                ScopeLevel.SETTLEMENT, ScopeLevel.DISTRICT,
                ScopeLevel.AREA, ScopeLevel.BUILDING, ScopeLevel.ROOM,
            ):
                self.assertEqual(
                    found[level], {(BundleNamedLocation, field)},
                    (param.field, level.value),
                )
        # P4: `dominant_material` — one authored payload node;
        # the fold is declared on
        # the param, not as a channel.
        self.assertEqual(
            {
                (model, field)
                for model in (BundleNamedLocation, SettlementSkeleton, SettlementPayload)
                for field, _ in cascade_channels(model, DOMINANT_MATERIAL)
            },
            {
                (SettlementPayload, "dominant_material"),
            },
        )
        self.assertEqual(DOMINANT_MATERIAL.fold, "dominant_material")
        self.assertEqual(DOMINANT_MATERIAL.levels, (ScopeLevel.SETTLEMENT,))

    def test_payload_chains_have_no_nl_or_skeleton_duplicates(self):
        for param, field in ((CITY_SIZE, "system_city_size"),
                             (DOMINANT_MATERIAL, "dominant_material")):
            with self.subTest(param=field):
                self.assertEqual([(owner, node.field) for owner, node, _ in ordered_chain(param)],
                                 [(SettlementPayload, field)])
                self.assertNotIn(field, BundleNamedLocation.model_fields)
                self.assertEqual(cascade_channels(SettlementSkeleton, param), ())
        self.assertEqual([(owner, node.field) for owner, node, _ in ordered_chain(SETTLEMENT_DENSITY)],
                         [(DistrictTemplateEntry, "density"), (SettlementPayload, "settlement_density")])
        self.assertNotIn("settlement_density", BundleNamedLocation.model_fields)

    def test_channel_kinds_are_declared(self):
        kinds = {
            field: channel.kind
            for field, channel in cascade_channels(
                PlotLayoutTemplate, ECONOMIC_TIER)
        }
        self.assertEqual(kinds, {
            "economic_tier": ChannelKind.VALUE,
            "economic_tier_band": ChannelKind.BAND,
            "economic_tier_range": ChannelKind.RANGE,
        })
        [(field, dte_channel)] = cascade_channels(
            DistrictTemplateEntry, ECONOMIC_TIER)
        self.assertEqual(field, "economic_tier_range")
        self.assertIs(dte_channel.kind, ChannelKind.RANGE)

    def test_verify_cascade_contract_passes_on_real_models(self):
        verify_cascade_contract(LocationContext)

    def test_wrong_object_type_for_level_errors(self):
        nl = BundleNamedLocation(
            location_uid="x", display_name="x", system_location_type="building",
        )
        check_link(ScopeLevel.BUILDING, nl)
        # The NL declares material channels at every non-world scope
        # (M9) — a model with a narrower chain is what absence means.
        room = RoomDef(
            room_id="r1", display_name="Room", room_type="hall",
            is_public=True, is_forbidden=False, required=True,
            size={"width_range": [5, 5], "depth_range": [5, 5]},
        )
        check_link(ScopeLevel.ROOM, room)
        with self.assertRaises(TypeError):
            check_link(ScopeLevel.BUILDING, room)
        with self.assertRaises(TypeError):
            check_link(ScopeLevel.WORLD, nl)

    def test_nullable_field_is_a_channel_not_absence(self):
        # A declared channel with a null value keeps cascading; a model
        # without the channel is what absence means.
        self.assertTrue(cascade_channels(PlotLayoutTemplate, ECONOMIC_TIER))
        self.assertEqual(
            cascade_channels(
                PlotLayoutTemplate, level=ScopeLevel.WORLD), ())

    def test_contract_detects_param_without_channels(self):
        class FakeContext(BaseModel):
            ghost: Annotated[
                str | None,
                Cascade(field="ghost", default=DefaultPolicy.NONE_IS_ERROR,
                        axis=ScopeLevel, levels=(ScopeLevel.AREA,)),
            ] = None

        with self.assertRaisesRegex(ValueError, "no channel declares it"):
            verify_cascade_contract(FakeContext)

    def test_channel_on_foreign_axis_errors(self):
        class OtherAxis(ScopeAxis):
            ROOT = "root"
            CHILD = "child"

        class FakeSource(BaseModel):
            name: Annotated[
                DefaultOnWire[str | None],
                CascadeChannel(ECONOMIC_TIER, OtherAxis.CHILD),
            ] = None

        try:
            with self.assertRaisesRegex(ValueError, "foreign axis"):
                verify_cascade_contract(LocationContext)
        finally:
            del FakeSource
            gc.collect()

    def test_incompatible_channel_type_errors(self):
        class FakeSource(BaseModel):
            amount: Annotated[
                DefaultOnWire[int | None],
                CascadeChannel(ECONOMIC_TIER, ScopeLevel.DISTRICT),
            ] = None

        try:
            with self.assertRaisesRegex(ValueError, "incompatible"):
                verify_cascade_contract(LocationContext)
        finally:
            del FakeSource
            gc.collect()

    def test_value_edge_ends_with_different_types_error(self):
        # `str` and `RegistryKey` both pass the kind check, but the
        # chain bottom carries `EconomyTierKey` — a VALUE edge requires
        # one base type (tz_cascade_context §2).
        class FakeSource(BaseModel):
            tier: Annotated[
                DefaultOnWire[str | None],
                CascadeChannel(
                    ECONOMIC_TIER, ScopeLevel.SETTLEMENT,
                    above=CascadeLink(
                        FieldRef(lambda: SettlementSkeleton, lambda pojo: pojo.economic_tier),
                        ScopeLevel.SETTLEMENT),
                ),
            ] = None

        try:
            with self.assertRaisesRegex(ValueError, "different types"):
                verify_cascade_contract(LocationContext)
        finally:
            del FakeSource
            gc.collect()

    def test_contract_modules_have_no_application_or_db_imports(self):
        root = Path(__file__).resolve().parents[1] / "app" / "dataModel"
        paths = list((root / "locations" / "context").glob("*.py"))
        paths.extend((root / "cascade").glob("*.py"))
        paths.append(root / "economy" / "economyTier" / "worldEconomyTierRegistry.py")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            modules.extend(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
            with self.subTest(path=path.name):
                self.assertFalse(any(module and module.startswith(("app.application", "app.db")) for module in modules))
