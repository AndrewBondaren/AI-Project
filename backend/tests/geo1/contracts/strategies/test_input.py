"""Identity, world scale and discriminated immutable input admission."""

from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredLakeSource, CoastlineWaterSource
from app.dataModel.planning.identity.planKey import RegionPlanScope
from app.dataModel.planning.contracts.planDependency import PlanDependency
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.terrain.designedWater.input import WaterDesignInput
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
from app.dataModel.validation.immutableValue import validate_immutable
from tests.geo1.contracts.strategies.fixtures import inputs, draft_for

ADAPTER = TypeAdapter(WaterDesignInput)


class StrategyInputTests(TestCase):
    def test_all_variants_roundtrip_and_admit_deeply_immutable_values(self):
        for strategy in Strategy:
            with self.subTest(strategy=strategy):
                value = inputs(strategy)
                validate_immutable(value)
                self.assertEqual(ADAPTER.validate_json(ADAPTER.dump_json(value)), value)
                self.assertEqual(value.pre_hydrology_ref, value.pre_hydrology.ref)
                self.assertEqual(value.validate_draft(draft_for(value)), draft_for(value))
                with self.assertRaises(ValidationError):
                    value.seed_root = "changed"

    def test_rejects_identity_and_area_mismatches_in_copied_records(self):
        value = inputs()
        updates = (
            {"metadata": value.metadata.model_copy(update={"source_uid": "other"})},
            {"metadata": value.metadata.model_copy(update={"liquid": "oil"})},
            {"metadata": value.metadata.model_copy(update={"body_kind": "lake"})},
            {"budget": value.budget.model_copy(update={"source_uid": "other"})},
            {"budget": value.budget.model_copy(update={"generation_region_uid": "other"})},
            {"budget": value.budget.model_copy(update={"requested_fine2": 17})},
            {"region": value.region.model_copy(update={"region_uid": "other"})},
            {"region": value.region.model_copy(update={"generation_area_fine2": 15})},
            {"region_coverage": value.region_coverage.model_copy(update={"region_uid": "other"})},
            {"context": value.context.model_copy(update={"strategy": Strategy.PLATE})},
            {"context": WaterGenerationContext.root(object())},
        )
        for update in updates:
            with self.subTest(update=update), self.assertRaises(ValidationError):
                ADAPTER.validate_python(value.model_copy(update=update))

    def test_recipe_discriminator_seed_and_fine_scale_must_match(self):
        value = inputs()
        for recipe in (inputs(Strategy.PLATE).field_policy,
                       value.field_policy.model_copy(update={"seed_root": "other"}),
                       value.field_policy.model_copy(update={"topology": value.topology})):
            with self.subTest(recipe=recipe), self.assertRaises(ValidationError):
                ADAPTER.validate_python(value.model_copy(update={"field_policy": recipe}))
        authored = inputs(Strategy.AUTHORED_REGION)
        with self.assertRaises(ValidationError):
            ADAPTER.validate_python(authored.model_dump() | {"field_policy": value.field_policy})
        with self.assertRaises(ValidationError):
            ADAPTER.validate_python(value.model_copy(update={"source": authored.source}))

    def test_explicit_source_level_and_binding_are_preserved(self):
        value = inputs()
        for update in ({"generation_region_uid": "other"}, {"z_water_level": 1}):
            source = value.source.model_copy(update={"value": value.source.value.model_copy(update=update)})
            with self.assertRaises(ValidationError):
                ADAPTER.validate_python(value.model_copy(update={"source": source}))

    def test_coverage_coordinates_use_fine_span_not_light_side(self):
        value = inputs()
        coverage = value.region_coverage.model_copy(update={"spans": tuple(
            s.model_copy(update={"y": s.y + 4}) for s in value.region_coverage.spans)})
        with self.assertRaises(ValidationError):
            ADAPTER.validate_python(value.model_copy(update={"region_coverage": coverage}))
        terrain = value.pre_hydrology.payload
        bad = terrain.model_copy(update={"bbox": type(terrain.bbox)(0, 1, 1, 1),
            "surface_z": ((SurfaceGridCoord(0, 1), 3), (SurfaceGridCoord(1, 1), 5))})
        with self.assertRaises(ValidationError):
            ADAPTER.validate_python(value.model_copy(update={"pre_hydrology": value.pre_hydrology.model_copy(update={"payload": bad})}))

    def test_cross_world_envelope_dependency_rejected(self):
        value = inputs()
        ref = value.pre_hydrology_ref
        other = ref.model_copy(update={"key": ref.key.model_copy(update={"world_uid": "other"})})
        dependency = PlanDependency(slot="terrain", ref=other)
        envelope = value.pre_hydrology.model_copy(update={"dependencies": (dependency,)})
        with self.assertRaises(ValidationError):
            ADAPTER.validate_python(value.model_copy(update={"pre_hydrology": envelope}))

    def test_all_authored_source_variants_preserve_metadata(self):
        value = inputs(Strategy.AUTHORED_REGION)
        lake = AuthoredLakeSource(value=DeclaredLake(location_uid="source"))
        coast = CoastlineWaterSource(value=DeclaredCoastline(location_uid="source", kind=BasinKind.SEA,
            path=(HydrologyWaypoint(x=-4, y=4), HydrologyWaypoint(x=-3, y=5))))
        for source, kind in ((lake, BasinKind.LAKE), (coast, BasinKind.SEA)):
            metadata = value.metadata.model_copy(update={"source_kind": source.kind, "body_kind": kind})
            ready = ADAPTER.validate_python(value.model_copy(update={"source": source, "metadata": metadata}))
            self.assertEqual(ready.source, source)
            self.assertEqual(ADAPTER.validate_json(ADAPTER.dump_json(ready)), ready)

    def test_ref_region_and_surface_completeness_are_validated(self):
        value = inputs()
        ref = value.pre_hydrology_ref
        other = ref.model_copy(update={"key": ref.key.model_copy(update={"scope": RegionPlanScope(region_uid="other")})})
        for envelope in (value.pre_hydrology.model_copy(update={"ref": other}),
                         value.pre_hydrology.model_copy(update={"payload": value.pre_hydrology.payload.model_copy(update={"surface_z": ()})})):
            with self.assertRaises(ValidationError):
                ADAPTER.validate_python(value.model_copy(update={"pre_hydrology": envelope}))
