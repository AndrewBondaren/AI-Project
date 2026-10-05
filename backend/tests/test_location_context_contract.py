"""S2 contract tests — tz_cascade_context §3, §5; no production wiring."""

import ast
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Annotated
from unittest.mock import patch

import gc

from pydantic import BaseModel, ValidationError

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
    cascade_channels,
    check_link,
)
from app.dataModel.cascade.cascadeSpec import (
    Cascade,
    CascadeChannel,
    CascadeLink,
    ChannelKind,
    DefaultPolicy,
    ScopeAxis,
)
from app.dataModel.cascade.cascadeVerify import (
    verify_cascade_contract,
)
from app.dataModel.locations.context.locationContext import LocationContext
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
                for model in (BundleNamedLocation, SettlementSkeleton)
                for field, _ in cascade_channels(model, CITY_SIZE)
            },
            {
                (BundleNamedLocation, "system_city_size"),
                (SettlementSkeleton, "system_city_size"),
            },
        )
        density = {
            level: {
                (model, field)
                for model in (BundleNamedLocation, SettlementSkeleton,
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
                (BundleNamedLocation, "settlement_density"),
                (SettlementSkeleton, "settlement_density"),
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
        # M10: `dominant_material` — settlement-only authored pair
        # (NL node beats the skeleton node); the fold is declared on
        # the param, not as a channel.
        self.assertEqual(
            {
                (model, field)
                for model in (BundleNamedLocation, SettlementSkeleton)
                for field, _ in cascade_channels(model, DOMINANT_MATERIAL)
            },
            {
                (BundleNamedLocation, "dominant_material"),
                (SettlementSkeleton, "dominant_material"),
            },
        )
        self.assertEqual(DOMINANT_MATERIAL.fold, "dominant_material")
        self.assertEqual(DOMINANT_MATERIAL.levels, (ScopeLevel.SETTLEMENT,))

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
                        SettlementSkeleton, "economic_tier",
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
