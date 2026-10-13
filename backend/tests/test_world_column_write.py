"""W2-1: scoped writes preserve intent, isolate validation and never persist."""

import copy
import unittest
from dataclasses import fields, replace
from typing import ClassVar
from unittest.mock import patch

from pydantic import BaseModel, Field, field_validator, model_validator

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldColumnResolve import resolve_world_column
from app.application.jsonValidation.worldSlices import (
    WORLD_SLICE_BY_KEY, WorldSlice, slice_for_world_key,
)
from app.application.worldData.worldColumnWrite import (
    COLUMN_INVALIDATES, apply_world_column, invalidated_world_tables,
)
from app.application.worldData.worldService import WorldService
from app.dataModel.annotationPolicy import DefaultWhenMissing, IgnoreOnWire
from app.dataModel.climate.worldClimateScalars import SeasonTempOffsets
from app.db.models.world import World


class Bounds(BaseModel):
    SCHEMA_ID: ClassVar[str] = "TEST-BOUNDS"
    lower: DefaultWhenMissing[int] = 0
    upper: DefaultWhenMissing[int] = 10

    @model_validator(mode="after")
    def ordered(self):
        if self.lower > self.upper:
            raise ValueError("lower exceeds upper")
        return self


class WorldColumnWriteTests(unittest.TestCase):
    def ctx(self, **kwargs):
        return replace(ResolveContext.for_import(validate_only=True), **kwargs)

    def world(self):
        return World("w1", "World", "2026-10-12", g=2.0, z_min=-700)

    def test_scalar_preserves_neighbors_even_invalid_independent_fields(self):
        world = self.world()
        world.g = -1
        world.material_registry = [42]
        before = copy.deepcopy(world)
        self.assertEqual(apply_world_column(world, "terrain_chunk_columns", 64, self.ctx()), frozenset())
        before.terrain_chunk_columns = 64
        self.assertEqual(world, before)

    def test_scalar_null_contract_and_no_mutation_on_failure(self):
        world = self.world()
        before = copy.deepcopy(world)
        for raw in (None, -1):
            with self.assertRaises(ImportValidationError) as error:
                apply_world_column(world, "g", raw, self.ctx())
            self.assertEqual(error.exception.errors[0].path, ("g",))
            self.assertEqual(error.exception.errors[0].schema_id, "SCH-WORLD-TERRAIN-SCALARS")
            self.assertEqual(world, before)
        apply_world_column(world, "z_min", None, self.ctx())
        self.assertIsNone(world.z_min)

    def test_atomic_nested_scalar_fills_defaults_and_dumps_json(self):
        world = self.world()
        world.season_temp_offsets = {"winter": -20, "summer": 9}
        apply_world_column(world, "season_temp_offsets", {"summer": 3}, self.ctx(partial=True))
        self.assertEqual(world.season_temp_offsets,
                         SeasonTempOffsets(summer=3).model_dump(mode="json"))

    def test_false_zero_and_empty_are_not_missing(self):
        for key, raw in (("closed_planet_grid", False), ("map_subsurface_depth", 0),
                         ("season_temp_offsets", {})):
            result = resolve_world_column(key, raw, self.ctx())
            self.assertEqual(set(result), {key})
            if key != "season_temp_offsets":
                self.assertEqual(result[key], raw)

    def test_legacy_adapter_matches_import(self):
        raw = {"grain": {"display_name": "Grain", "crop_kind": "grain"}}
        # Adapter injects identity before the shared registry resolver.
        scoped = resolve_world_column("crops_registry", raw, self.ctx())
        self.assertEqual(scoped["crops_registry"],
                         normalize_world({"crops_registry": raw}, partial=True)["crops_registry"])

    def test_invalid_registry_is_atomic_and_preserves_all_error_paths(self):
        world = self.world()
        before = copy.deepcopy(world)
        ctx = self.ctx(path_prefix=("operation",))
        with self.assertRaises(ImportValidationError) as error:
            apply_world_column(world, "relief_template_registry", [42, False], ctx)
        self.assertEqual([e.path for e in error.exception.errors],
                         [("operation", "relief_template_registry", 0),
                          ("operation", "relief_template_registry", 1)])
        self.assertEqual(ctx.errors, error.exception.errors)
        self.assertEqual(world, before)

    def test_non_facade_and_unknown_keys_rejected(self):
        for key in ("name", "fine_cells_per_map_cell", "missing"):
            with self.assertRaises(ImportValidationError):
                resolve_world_column(key, 1000, self.ctx())
        world_slice = replace(slice_for_world_key("g"), facade=False)
        with patch.dict(WORLD_SLICE_BY_KEY, {"g": world_slice}):
            with self.assertRaises(ImportValidationError):
                resolve_world_column("g", 2.0, self.ctx())

    def test_blob_is_atomic_and_does_not_merge_saved_fields(self):
        world = self.world()
        world.hydrology = {"enabled": False, "materialize_named_locations": True}
        apply_world_column(world, "hydrology", {"enabled": False}, self.ctx(partial=True))
        self.assertFalse(world.hydrology["enabled"])
        self.assertFalse(world.hydrology["materialize_named_locations"])

    def test_blob_null_rejected_by_both_import_and_scoped(self):
        for key in ("hydrology", "terrain_masks", "relief_pick_policy"):
            with self.subTest(key=key):
                facts = []
                for resolve in (lambda: resolve_world_column(key, None, self.ctx()),
                                lambda: normalize_world({key: None}, partial=True)):
                    with self.assertRaises(ImportValidationError) as error:
                        resolve()
                    facts.append(error.exception.errors[0].path)
                self.assertEqual(facts[0], facts[1])

    def test_registry_null_uses_shared_root_contract_after_adapter(self):
        for key in ("climate_zone_registry", "lore_registry", "relief_template_registry"):
            scoped = resolve_world_column(key, None, self.ctx())
            self.assertEqual(scoped[key], normalize_world({key: None}, partial=True)[key])
            self.assertIsNotNone(scoped[key])

    def test_invariant_checks_existing_values_but_returns_only_authored_column(self):
        world_slice = WorldSlice(Bounds.SCHEMA_ID, Bounds, "multi_column", ("lower", "upper"),
                                 wire_from_mapping=lambda source: dict(source), facade=True)
        with patch.dict(WORLD_SLICE_BY_KEY, {"lower": world_slice}):
            existing = {"lower": 1, "upper": 3}
            self.assertEqual(resolve_world_column("lower", 2, self.ctx(), existing=existing), {"lower": 2})
            with self.assertRaises(ImportValidationError):
                resolve_world_column("lower", 4, self.ctx(), existing=existing)
            with self.assertRaises(ImportValidationError):
                resolve_world_column("lower", 2, self.ctx())
            self.assertEqual(existing, {"lower": 1, "upper": 3})

    def test_full_nested_model_invariants_are_not_lost_in_field_validation(self):
        class Container(BaseModel):
            bounds: Bounds = Field(default_factory=Bounds)
        world_slice = WorldSlice("TEST-NESTED", Container, "multi_column", ("bounds",), facade=True)
        with patch.dict(WORLD_SLICE_BY_KEY, {"bounds": world_slice}):
            self.assertEqual(resolve_world_column("bounds", {"lower": 2}, self.ctx()),
                             {"bounds": {"lower": 2, "upper": 10}})
            with self.assertRaises(ImportValidationError):
                resolve_world_column("bounds", {"lower": 12}, self.ctx())

    def test_ignore_policy_still_validates_nullable_schema(self):
        class Ignored(BaseModel):
            value: IgnoreOnWire[int | None] = 5
        world_slice = WorldSlice("TEST-IGNORE", Ignored, "multi_column", ("value",), facade=True)
        with patch.dict(WORLD_SLICE_BY_KEY, {"value": world_slice}):
            self.assertEqual(resolve_world_column("value", None, self.ctx()), {"value": None})
            with self.assertRaises(ImportValidationError):
                resolve_world_column("value", "invalid", self.ctx())

    def test_independent_field_keeps_original_field_validator_context(self):
        class Validated(BaseModel):
            value: DefaultWhenMissing[int] = 5

            @field_validator("value")
            @classmethod
            def validate_value(cls, value, info):
                if info.field_name != "value" or value == 13:
                    raise ValueError("invalid value")
                return value

        world_slice = WorldSlice("TEST-FIELD", Validated, "multi_column", ("value",), facade=True)
        with patch.dict(WORLD_SLICE_BY_KEY, {"value": world_slice}):
            self.assertEqual(resolve_world_column("value", 6, self.ctx()), {"value": 6})
            with self.assertRaises(ImportValidationError) as error:
                resolve_world_column("value", 13, self.ctx())
            self.assertEqual(error.exception.errors[0].path, ("value",))

    def test_pure_resolve_does_not_mutate_caller_payload_on_rejection(self):
        class Mutating(BaseModel):
            value: list[int]

            @field_validator("value", mode="before")
            @classmethod
            def reject(cls, value):
                value.append("bad")
                raise ValueError("rejected")

        world_slice = WorldSlice("TEST-PURE", Mutating, "multi_column", ("value",), facade=True)
        raw = [1]
        with patch.dict(WORLD_SLICE_BY_KEY, {"value": world_slice}):
            with self.assertRaises(ImportValidationError):
                resolve_world_column("value", raw, self.ctx())
        self.assertEqual(raw, [1])

    def test_registry_guard_uses_world_fields_not_facade_coverage(self):
        self.assertLessEqual(COLUMN_INVALIDATES.keys(), {f.name for f in fields(World)})
        self.assertNotIn("fine_cells_per_map_cell", WORLD_SLICE_BY_KEY)

    def test_invalidation_only_for_supplied_changes_and_unions_tables(self):
        before = {"fine_cells_per_map_cell": 1000, "g": 1.0}
        self.assertEqual(invalidated_world_tables(before, {"fine_cells_per_map_cell": 1000}), frozenset())
        self.assertEqual(invalidated_world_tables(before, {"g": 2.0}), frozenset())
        with patch.dict(COLUMN_INVALIDATES, {"g": frozenset({"map_cells", "other"})}):
            self.assertEqual(invalidated_world_tables(before, {"fine_cells_per_map_cell": 2000, "g": 2}),
                             frozenset({"map_cells", "other"}))

    def test_apply_reports_consequences_after_validation(self):
        world = self.world()
        with patch.dict(COLUMN_INVALIDATES, {"g": frozenset({"test_table"})}):
            self.assertEqual(apply_world_column(world, "g", 2.0, self.ctx()), frozenset())
            self.assertEqual(apply_world_column(world, "g", 3.0, self.ctx()), frozenset({"test_table"}))


class _StubWorldRepo:
    def __init__(self, world: World) -> None:
        self.world = world
        self.saved: World | None = None

    async def get_by_id(self, world_uid: str) -> World | None:
        return self.world if self.world.world_uid == world_uid else None

    async def update(self, world: World) -> None:
        self.saved = world


class WorldUpdateInvalidationTests(unittest.IsolatedAsyncioTestCase):
    """W2-2: master PATCH derives cleanup from COLUMN_INVALIDATES."""

    def service(self) -> tuple[WorldService, _StubWorldRepo]:
        repo = _StubWorldRepo(World("w1", "World", "2026-10-12"))
        return WorldService(repo), repo

    async def test_unchanged_cell_size_saves_without_invalidation(self):
        service, repo = self.service()
        result = await service.update("w1", {"fine_cells_per_map_cell": 1000})
        self.assertFalse(result.requires_force)
        self.assertFalse(result.map_cells_invalidated)
        self.assertEqual(repo.saved.fine_cells_per_map_cell, 1000)

    async def test_changed_cell_size_requires_force_and_never_writes(self):
        service, repo = self.service()
        result = await service.update("w1", {"fine_cells_per_map_cell": 2000})
        self.assertTrue(result.requires_force)
        self.assertIn("1000", result.warning)
        self.assertIn("2000", result.warning)
        self.assertIsNone(repo.saved)
        self.assertEqual(result.world.fine_cells_per_map_cell, 1000)

    async def test_forced_cell_size_reports_cleanup(self):
        service, repo = self.service()
        result = await service.update("w1", {"fine_cells_per_map_cell": 2000, "force": True})
        self.assertFalse(result.requires_force)
        self.assertTrue(result.map_cells_invalidated)
        self.assertEqual(repo.saved.fine_cells_per_map_cell, 2000)

    async def test_unrelated_change_does_not_invalidate(self):
        service, repo = self.service()
        result = await service.update("w1", {"name": "Renamed"})
        self.assertFalse(result.requires_force)
        self.assertFalse(result.map_cells_invalidated)
        self.assertEqual(repo.saved.name, "Renamed")


if __name__ == "__main__":
    unittest.main()
