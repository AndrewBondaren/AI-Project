"""Remaining E6 consumers: no error inheritance, registry row skip or hidden repairs."""
import unittest
from dataclasses import replace
from random import Random
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from app.application.cascade import locationScope
from app.application.jsonValidation import resolve as resolve_module
from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.jsonValidation.sourceValidation import validate_source
from app.application.cascade.locationScope import (
    area_context, building_context, district_context, settlement_context, empty_location_chain)
from app.application.worldData.locations.namedLocationService import NamedLocationService
from app.application.worldData.generators.utils.materialResolver import resolve_material
from app.application.worldData.generators.utils.economicTierBands import materialize_band
from app.application.worldData.generators.utils.tierRegistry import tier_rank
from app.application.templateLibrary.structureTemplateLibraryService import StructureTemplateLibraryService
from app.application.templateLibrary.reliefTemplateLibraryService import ReliefTemplateLibraryService
from app.application.templateLibrary.loadReliefTemplatesForWorld import load_relief_templates_for_world
from app.application.templateLibrary.templateContracts import (
    ReliefTemplateSnapshot,
    TemplateEntry,
)
from app.dataModel.terrain.relief import ReliefTemplate, reliefTemplate
from app.application.worldData.relief.parseObjectReliefPickPolicy import parse_object_relief_pick_policy
from app.application.worldData.registries.raceService import RaceService, _to_race
from app.application.worldData.registries.worldPerkService import WorldPerkService, _to_perk
from app.application.imports.helpers import import_list
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.structure.building import structureTemplate
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.settlement.settlement.settlementPayload import SettlementPayload
from app.dataModel.locations.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from tests.test_cascade_context_baseline import fixture


class SourceConsumerTests(unittest.TestCase):
    def test_location_wire_policy_has_identical_facts_and_one_log(self):
        world, location, _ = fixture()
        for value, field in (("unknown", "system_economic_tier"),
                             ("unknown", "parent_wall_material"),
                             ("unknown", "parent_floor_material")):
            facts = []
            for preview in (False, True):
                ctx = ResolveContext.for_import(validate_only=preview)
                with patch(resolve_module.__name__ + ".logger") as log:
                    with self.assertRaises(UnresolvedModelError) as caught:
                        NamedLocationService._from_wire({"location_uid": "source", "display_name": "Source",
                            "system_location_type": "building", field: value},
                            world_uid=world.world_uid, world=world, ctx=ctx)
                facts.append(caught.exception.issues)
                self.assertEqual(log.warning.call_count, 0 if preview else 1)
            self.assertEqual(facts[0], facts[1])
            self.assertEqual(facts[0][0].path, (field,))

    def test_invalid_authored_source_never_reaches_extend(self):
        world, location, _ = fixture()
        parent = empty_location_chain(world, ScopeLevel.AREA)
        before = parent.model_dump()
        for field in ("system_economic_tier", "parent_wall_material", "parent_floor_material"):
            invalid = replace(location, **{field: "unknown"})
            with patch(locationScope.__name__ + ".extend") as extend:
                with self.assertRaises(UnresolvedModelError):
                    building_context(world, parent, invalid)
                extend.assert_not_called()
        self.assertEqual(parent.model_dump(), before)

    def test_settlement_payload_material_is_validated_before_extend(self):
        world, location, _ = fixture()
        settlement = replace(location, system_location_type="settlement",
                             location_payload={"dominant_material": "unknown"})
        with patch(locationScope.__name__ + ".extend") as extend:
            with self.assertRaises(UnresolvedModelError):
                settlement_context(world, settlement)
            extend.assert_not_called()

    def test_plot_lower_priority_range_and_band_are_not_silently_ignored(self):
        world, _, _ = fixture()
        parent = empty_location_chain(world, ScopeLevel.DISTRICT)
        for extra in ({"economic_tier_range": {"min": "unknown", "max": "t9"}},
                      {"economic_tier_range": {"min": "t9", "max": "t1"}},
                      {"economic_tier_band": "unknown"}):
            plot = PlotLayoutTemplate(system_name="plot", display_name="Plot", economic_tier="t2", **extra)
            with patch(locationScope.__name__ + ".extend") as extend:
                with self.assertRaises(UnresolvedModelError):
                    area_context(world, parent, plot, area_uid="plot")
                extend.assert_not_called()

    def test_district_range_and_unavailable_registry_reject(self):
        world, _, _ = fixture()
        source = DistrictTemplateEntry(system_name="test", display_name="Test", district_type="residential",
                                       economic_tier_range={"min": "t1", "max": "unknown"})
        parent = empty_location_chain(world, ScopeLevel.SETTLEMENT)
        with self.assertRaises(UnresolvedModelError):
            district_context(world, parent, source, district_uid="district")
        plot = PlotLayoutTemplate(system_name="plot", display_name="Plot", economic_tier="t2")
        for registry in (None, False, [{"system_tier": "t2"}]):
            world.economic_tier_registry = registry
            with self.assertRaises(UnresolvedModelError) as caught:
                validate_source(world, plot, ctx=ResolveContext(validate_only=True))
            self.assertEqual(caught.exception.issues[0].code, "REF_W_UNAVAILABLE")

    def test_material_error_is_not_default_and_does_not_consume_rng(self):
        world, _, _ = fixture()
        rng = Random(17)
        state = rng.getstate()
        for use, tier, default in (("wall", "unknown", "stone"),
                                   ("missing_use", "t2", "missing_default")):
            with self.assertRaises(UnresolvedModelError):
                resolve_material(world, use, tier, rng, default)
            self.assertEqual(rng.getstate(), state)
        world.material_registry[0]["economic_tier"] = "unknown"
        with self.assertRaises(UnresolvedModelError):
            resolve_material(world, "wall", "t2", rng, "stone")

    def test_direct_band_and_rank_do_not_hide_invalid_keys(self):
        world, _, _ = fixture()
        with self.assertRaises(UnresolvedModelError):
            materialize_band(world, "unknown", Random(1))
        with self.assertRaises(UnresolvedModelError):
            tier_rank([], "unknown")
        self.assertEqual(tier_rank([], None), 0)

    def test_opening_defaults_are_declared_and_do_not_draw_rng(self):
        world, _, _ = fixture()
        world.material_registry = []
        rng = Random(17)
        state = rng.getstate()
        for key in ("window_glass", "porthole_glass", "vent_mesh"):
            self.assertEqual(resolve_material(world, key, "t2", rng, key), key)
            self.assertEqual(rng.getstate(), state)
        self.assertEqual(resolve_material(world, "road", "t2", rng, "dirt_road"), "dirt_road")
        self.assertEqual(rng.getstate(), state)
        # A partial canonical row is a declared overlay, not an invalid row.
        world.material_registry = [{"system_material": "stone", "hardness": 4}]
        source = NamedLocationService._from_wire({"location_uid": "overlay", "display_name": "Overlay",
            "system_location_type": "building", "parent_wall_material": "stone"},
            world_uid=world.world_uid, world=world)
        self.assertEqual(source.parent_wall_material, "stone")
        world.material_registry[0]["hardness"] = "invalid"
        with self.assertRaises(UnresolvedModelError):
            NamedLocationService._from_wire({"location_uid": "overlay", "display_name": "Overlay",
                "system_location_type": "building", "parent_wall_material": "stone"},
                world_uid=world.world_uid, world=world)

    def test_preflight_retains_errors_from_independent_consumer_context(self):
        from app.application.jsonValidation.bundle.preflight import validate_rows
        from app.application.jsonValidation.resolve import reject_unresolved
        from app.application.jsonValidation.types import FieldPathError
        def prepare(row):
            reject_unresolved(ResolveContext(validate_only=True),
                              [FieldPathError(("field",), "invalid", code="TEST")])
        ctx = ResolveContext(validate_only=True)
        with self.assertRaises(UnresolvedModelError):
            validate_rows([{}], prepare, ctx=ctx)
        self.assertEqual(len(ctx.errors), 1)

    def test_object_relief_policy_only_none_means_absent(self):
        self.assertIsNone(parse_object_relief_pick_policy(None))
        for invalid in (False, 0, "bad", []):
            with self.subTest(invalid=invalid), self.assertRaises(UnresolvedModelError):
                parse_object_relief_pick_policy(invalid)


class LibraryConsumerTests(unittest.IsolatedAsyncioTestCase):
    async def test_infrastructure_failure_is_not_converted_to_data_error(self):
        for service_cls, model_path in (
            (StructureTemplateLibraryService, structureTemplate.__name__ + ".StructureTemplate.model_validate"),
            (ReliefTemplateLibraryService, reliefTemplate.__name__ + ".ReliefTemplate.model_validate")):
            repo = SimpleNamespace(upsert=AsyncMock())
            service = service_cls(repo)
            with patch(model_path, side_effect=OSError("infrastructure")):
                with self.assertRaises(OSError):
                    await service.upsert_from_dict({})
            repo.upsert.assert_not_called()
        with self.assertRaises(OSError):
            await import_list([{}], lambda raw: raw, AsyncMock(side_effect=OSError("database")))

    async def test_relief_preload_uses_membership_snapshot_not_registry(self):
        """B5: the loader's membership snapshot is the only source — a
        prepared member body arrives keyed by its member uid."""
        world, _, _ = fixture()
        uid = str(uuid4())
        entry = TemplateEntry(template_uid=uid, pack_uid=str(uuid4()),
            body=ReliefTemplate.model_validate({"system_name": "g", "display_name": "G",
                                                "context": "open_land"}))
        loader = SimpleNamespace(load_relief=AsyncMock(return_value=ReliefTemplateSnapshot(
            world_uid=world.world_uid, templates={uid: entry})))
        self.assertEqual(await load_relief_templates_for_world(loader, world), {uid: entry.body})
        empty = SimpleNamespace(load_relief=AsyncMock(return_value=ReliefTemplateSnapshot(
            world_uid=world.world_uid)))
        self.assertEqual(await load_relief_templates_for_world(empty, world), {})

    async def test_race_and_perk_update_validate_before_write(self):
        world, _, _ = fixture()
        worlds = SimpleNamespace(get_by_id=AsyncMock(return_value=world))
        for cls, convert, column in ((RaceService, _to_race, "race_template_registry"),
                                     (WorldPerkService, _to_perk, "perk_template_registry")):
            row = convert({})
            setattr(world, column, [{"system_template_uid": row.template_uid, "display_template_name": row.display_name}])
            repo = SimpleNamespace(get_by_id=AsyncMock(return_value=row), update=AsyncMock())
            with self.assertRaises(UnresolvedModelError):
                await cls(repo, worlds).update(world.world_uid, row.template_uid, {"display_name": ""})
            repo.update.assert_not_called()
            self.assertNotEqual(row.display_name, "")
