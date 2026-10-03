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
from app.dataModel.locations.context.cascadeLevel import CascadeLevel
from app.dataModel.locations.context.cascadeParams import ECONOMIC_TIER
from app.dataModel.locations.context.cascadeSpec import (
    Cascade,
    CascadeChannel,
    ChannelKind,
    DefaultPolicy,
    cascade_channels,
    check_link,
    verify_cascade_contract,
)
from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.namedLocation.bundleNamedLocation import BundleNamedLocation
from app.dataModel.registryKey import RegistryKey
from app.dataModel.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.settlement.settlement.settlementSkeleton import SettlementSkeleton
from app.dataModel.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.structure.room.roomDef import RoomDef
from app.db.models.world import World


def registry(values):
    return WorldEconomyTierRegistry([
        EconomyTierEntry(system_tier=key, display_tier=key, base_value=value)
        for key, value in values
    ])


class LocationContextContractTests(unittest.TestCase):
    def test_canonical_level_order_and_rank(self):
        self.assertEqual([level.value for level in CascadeLevel],
                         ["world", "settlement", "district", "area", "building", "room"])
        self.assertEqual([level.rank for level in CascadeLevel], list(range(6)))
        self.assertIs(CascadeLevel("building"), CascadeLevel.BUILDING)

    def test_cascade_metadata_is_frozen_and_has_extension_slots(self):
        spec = Cascade("test_field", DefaultPolicy.NONE_IS_ERROR,
                       fold="test_fold", levels=(CascadeLevel.WORLD, CascadeLevel.AREA))
        self.assertEqual(spec.fold, "test_fold")
        self.assertEqual(spec.levels, (CascadeLevel.WORLD, CascadeLevel.AREA))
        with self.assertRaises(FrozenInstanceError):
            spec.field = "changed"
        tier_spec = LocationContext.model_fields["economic_tier"].metadata
        self.assertIs(tier_spec[0], ECONOMIC_TIER)
        self.assertIsNone(tier_spec[0].fold)
        self.assertIsNone(tier_spec[0].levels)

    def test_only_v1_fields_and_branded_tier(self):
        self.assertEqual(set(LocationContext.model_fields), {"level", "economic_tier", "provenance"})
        context = LocationContext(level=CascadeLevel.BUILDING, economic_tier="custom_tier",
                                  provenance={"economic_tier": (CascadeLevel.AREA, "economic_tier")})
        self.assertIsInstance(context.economic_tier, RegistryKey)
        self.assertEqual(context.provenance["economic_tier"], (CascadeLevel.AREA, "economic_tier"))
        with self.assertRaises(ValidationError):
            LocationContext(level=CascadeLevel.WORLD, wall_material="stone")
        with self.assertRaises(ValidationError):
            LocationContext(level=CascadeLevel.BUILDING, economic_tier="")
        with self.assertRaises(ValidationError):
            LocationContext(level="unknown")
        with self.assertRaises(ValidationError):
            LocationContext(level=CascadeLevel.BUILDING, provenance={"economic_tier": ("unknown", "authored")})

    def test_model_fields_are_frozen(self):
        context = LocationContext(level=CascadeLevel.BUILDING, economic_tier="custom")
        for name, value in (("level", CascadeLevel.ROOM), ("economic_tier", "changed"), ("provenance", {})):
            with self.subTest(field=name), self.assertRaises(ValidationError) as error:
                setattr(context, name, value)
            self.assertEqual(error.exception.errors()[0]["type"], "frozen_instance")

    def test_root_is_empty_and_does_not_resolve_or_log(self):
        world = World(world_uid="context-contract", name="Contract", created_at="2026-10-03")
        with patch.object(WorldEconomyTierRegistry, "resolve_default") as default:
            with self.assertNoLogs(level="WARNING"):
                first, second = LocationContext.root(world), LocationContext.root(world)
        default.assert_not_called()
        self.assertIs(first.level, CascadeLevel.WORLD)
        self.assertIsNone(first.economic_tier)
        self.assertEqual(first.provenance, {})
        self.assertIsNot(first.provenance, second.provenance)
        self.assertIs(first._world, world)
        self.assertEqual(first.model_dump(mode="json"),
                         {"level": "world", "economic_tier": None, "provenance": {}})

    def test_default_median_sorts_and_uses_upper_middle_with_warning(self):
        for entries, expected in (([("high", 90), ("low", 0), ("medium", 10)], "medium"),
                                  ([("high", 90), ("low", 0)], "high"),
                                  ([("only", 20)], "only")):
            with self.subTest(entries=entries):
                tiers = registry(entries)
                original = list(tiers.root)
                with self.assertLogs(WorldEconomyTierRegistry.__module__, level="WARNING") as logged:
                    tier = tiers.resolve_default(DefaultPolicy.REGISTRY_MEDIAN)
                self.assertEqual(tier, expected)
                self.assertIsInstance(tier, RegistryKey)
                self.assertEqual(len(logged.records), 1)
                self.assertIn(expected, logged.output[0])
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
        for model in (BundleNamedLocation, SettlementSkeleton,
                      DistrictTemplateEntry, PlotLayoutTemplate, RoomDef):
            for _name, channel in cascade_channels(model):
                self.assertIs(channel.param, ECONOMIC_TIER)

    def test_channels_cover_the_whole_chain_per_level(self):
        models = (RoomDef, BundleNamedLocation, PlotLayoutTemplate,
                  DistrictTemplateEntry, SettlementSkeleton)
        expected = {
            CascadeLevel.ROOM: {
                (RoomDef, "economic_tier"),
                (BundleNamedLocation, "system_economic_tier"),
            },
            CascadeLevel.BUILDING: {
                (BundleNamedLocation, "system_economic_tier")},
            CascadeLevel.AREA: {
                (PlotLayoutTemplate, "economic_tier"),
                (PlotLayoutTemplate, "economic_tier_band"),
                (PlotLayoutTemplate, "economic_tier_range"),
            },
            CascadeLevel.DISTRICT: {
                (BundleNamedLocation, "system_economic_tier"),
                (DistrictTemplateEntry, "economic_tier_range"),
            },
            CascadeLevel.SETTLEMENT: {
                (BundleNamedLocation, "system_economic_tier"),
                (SettlementSkeleton, "economic_tier"),
            },
            CascadeLevel.WORLD: set(),
        }
        for level, wanted in expected.items():
            found = {
                (model, field)
                for model in models
                for field, _channel in cascade_channels(
                    model, ECONOMIC_TIER, level)
            }
            self.assertEqual(found, wanted, level.value)

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
        check_link(CascadeLevel.BUILDING, nl)
        with self.assertRaises(TypeError):
            check_link(CascadeLevel.AREA, nl)
        with self.assertRaises(TypeError):
            check_link(CascadeLevel.WORLD, nl)

    def test_nullable_field_is_a_channel_not_absence(self):
        # A declared channel with a null value keeps cascading; a model
        # without the channel is what absence means.
        self.assertTrue(cascade_channels(PlotLayoutTemplate, ECONOMIC_TIER))
        self.assertEqual(
            cascade_channels(
                PlotLayoutTemplate, level=CascadeLevel.WORLD), ())

    def test_contract_detects_param_without_channels(self):
        class FakeContext(BaseModel):
            ghost: Annotated[
                str | None,
                Cascade(field="ghost", default=DefaultPolicy.NONE_IS_ERROR,
                        levels=(CascadeLevel.AREA,)),
            ] = None

        with self.assertRaisesRegex(ValueError, "no channel declares it"):
            verify_cascade_contract(FakeContext)

    def test_incompatible_channel_type_errors(self):
        class FakeSource(BaseModel):
            amount: Annotated[
                DefaultOnWire[int | None],
                CascadeChannel(ECONOMIC_TIER, CascadeLevel.DISTRICT),
            ] = None

        try:
            with self.assertRaisesRegex(ValueError, "incompatible"):
                verify_cascade_contract(LocationContext)
        finally:
            del FakeSource
            gc.collect()

    def test_contract_modules_have_no_application_or_db_imports(self):
        root = Path(__file__).resolve().parents[1] / "app" / "dataModel"
        paths = list((root / "locations" / "context").glob("*.py"))
        paths.append(root / "economy" / "economyTier" / "worldEconomyTierRegistry.py")
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            modules.extend(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
            with self.subTest(path=path.name):
                self.assertFalse(any(module and module.startswith(("app.application", "app.db")) for module in modules))
