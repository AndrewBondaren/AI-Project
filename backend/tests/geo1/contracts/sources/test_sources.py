"""Source structure/identity invariants without generation or active capture."""

from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from app.application.cascade.cascadeLink import EmptyLink, Link
from app.application.cascade.contextResolver import extend
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationScope as Scope
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.generation.waterGenerationSettings import BodyWaterGenerationSettings
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.sources.proceduralWaterSource import ProceduralWaterSource
from app.dataModel.hydrology.sources.waterDesignSource import (
    AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource,
    WaterDesignSource, WaterDesignSourceKind,
)
from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.spatial.regionShape import BboxShape


def procedural(**updates):
    return ProceduralWaterSource.model_validate(dict(source_uid="source", generation_region_uid="region",
        kind=BasinKind.OCEAN, liquid="water") | updates)


class WaterSourceTests(TestCase):
    def test_procedural_source_has_no_fabricated_geometry_and_roundtrips(self):
        for kind in BasinKind:
            source = procedural(kind=kind)
            self.assertEqual(source.model_fields_set, {"source_uid", "generation_region_uid", "kind", "liquid"})
            self.assertIsNone(source.z_water_level)
            self.assertEqual(source.generation, BodyWaterGenerationSettings())
            self.assertNotIn("footprint", type(source).model_fields)
            self.assertNotIn("floor_z", type(source).model_fields)
            self.assertEqual(type(source).model_validate_json(source.model_dump_json()), source)
            with self.assertRaises(ValidationError):
                source.source_uid = "changed"

    def test_binding_has_one_owner_even_when_duplicate_values_agree(self):
        for uid in ("region", "other"):
            with self.assertRaises(ValidationError):
                procedural(generation=BodyWaterGenerationSettings(generation_region_uid=uid))
        forged = procedural().model_copy(update={"generation": BodyWaterGenerationSettings(generation_region_uid="region")})
        with self.assertRaises(ValidationError):
            ProceduralSource(value=forged)

    def test_body_region_binding_does_not_enter_cascade(self):
        settings = BodyWaterGenerationSettings(generation_region_uid="authored-region", water_fraction=0.2)
        ctx = extend(WaterGenerationContext.root(object()), EmptyLink(Scope.WORLD))
        ctx = extend(ctx, EmptyLink(Scope.CATEGORY))
        ctx = extend(ctx, Link(Scope.WATER_BODY, settings))
        self.assertEqual(ctx.water_fraction, 0.2)
        self.assertNotIn("generation_region_uid", ctx.provenance)
        self.assertNotIn("generation_region_uid", type(ctx).model_fields)

    def test_required_identity_and_closed_types_are_strict(self):
        for updates in ({"source_uid": ""}, {"generation_region_uid": " x"}, {"kind": "ocean"},
                        {"kind": "river"}, {"liquid": None}, {"z_water_level": True},
                        {"placement_specificity": -1}, {"placement_specificity": True}, {"footprint": ()}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                procedural(**updates)

    def test_union_preserves_each_existing_source_kind(self):
        path = (HydrologyWaypoint(x=0, y=0), HydrologyWaypoint(x=3, y=0), HydrologyWaypoint(x=3, y=3))
        sources = (
            AuthoredBasinSource(value=DeclaredBasin(location_uid="basin", kind=BasinKind.SEA, floor_z=-5,
                footprint=BboxShape(x_min=0, y_min=0, x_max=3, y_max=3))),
            AuthoredLakeSource(value=DeclaredLake(location_uid="lake", shoreline=path)),
            CoastlineWaterSource(value=DeclaredCoastline(location_uid="coast", kind=BasinKind.SEA, path=path)),
            ProceduralSource(value=procedural()),
        )
        adapter = TypeAdapter(WaterDesignSource)
        for wrapper in sources:
            self.assertEqual(adapter.validate_json(adapter.dump_json(wrapper)), wrapper)
            with self.assertRaises(ValidationError):
                adapter.validate_python(wrapper.model_copy(update={"kind": "unknown"}))
        # Passing a different legacy model must not erase its fields via dump/coercion.
        with self.assertRaises(ValidationError):
            AuthoredLakeSource.model_validate({"value": sources[2].value})

    def test_legacy_instances_are_revalidated_without_losing_their_invariants(self):
        source = DeclaredBasin(location_uid="basin", kind=BasinKind.SEA, floor_z=-5,
            footprint=BboxShape(x_min=0, y_min=0, x_max=3, y_max=3))
        for value in (source.model_copy(update={"location_uid": ""}),
                      source.model_copy(update={"floor_z": 4, "z_water_level": 1}),
                      source.model_copy(update={"footprint": source.footprint.model_copy(update={"x_max": -1})})):
            with self.assertRaises(ValidationError):
                AuthoredBasinSource(value=value)

    def test_metadata_checks_its_values_without_mapping_or_default_resolution(self):
        raw = dict(source_uid="source", source_kind=WaterDesignSourceKind.PROCEDURAL,
            body_kind=BasinKind.OCEAN, liquid="water", level=FineZ(0),
            bands=HydrologyBands(min=1, max=4), source_path=("hydrology", "procedural_bodies", 0), default_depth=10)
        metadata = WaterSourceMetadata.model_validate(raw)
        self.assertEqual(WaterSourceMetadata.model_validate_json(metadata.model_dump_json()), metadata)
        for updates in ({"default_depth": 0}, {"default_depth": True}, {"level": False},
                        {"source_path": ("hydrology", True)}, {"source_kind": "procedural"},
                        {"bands": HydrologyBands(min=5, max=1)},
                        {"bands": metadata.bands.model_copy(update={"max": 100})}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                WaterSourceMetadata.model_validate(raw | updates)

    def test_production_sources_are_not_extended_or_registered(self):
        self.assertNotIn("procedural_bodies", WorldHydrology.model_fields)
        for source_type in (DeclaredBasin, DeclaredLake, DeclaredCoastline):
            self.assertNotIn("generation", source_type.model_fields)
