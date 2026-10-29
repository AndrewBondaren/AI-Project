"""G10-A typed pipeline admission and canonical replay, before activation."""

from enum import Enum, StrEnum
from dataclasses import is_dataclass
from typing import TypeAliasType, get_args, get_type_hints
from unittest import TestCase

from pydantic import BaseModel, ValidationError

from app.application.encoding.canonicalCodec import decode, encode
from app.application.worldData.planning.contracts.surfacePlanningView import GeoSurfacePlanningView
from app.application.worldData.planning.contracts.surfacePlanBundle import GeoSurfacePlanBundle
from app.application.worldData.planning.encoding.surfaceEnvelopeCodec import SurfaceEnvelopeCodec
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping, SourceBodyMappingEntry
from app.dataModel.hydrology.sources.proceduralWaterSource import ProceduralWaterSource
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, AuthoredLakeSource, CoastlineWaterSource, ProceduralSource
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.spatial.regionShape import BboxShape
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from tests.geo1.integration.support.pipeline import view, bundle, rebuild, placement_plan
from tests.geo1.placement_policy.fixtures import coastline


class SurfaceContractTests(TestCase):
    def setUp(self):
        self.view = view()

    def test_complete_codec_type_closure_including_empty_variants(self):
        registered = {entry.python_type for entry in SURFACE_MANIFEST.entries}
        seen = set()

        def visit(kind):
            if isinstance(kind, Enum):
                kind = type(kind)
            if kind in seen:
                return
            seen.add(kind)
            if isinstance(kind, TypeAliasType):
                visit(kind.__value__)
            elif isinstance(kind, type) and kind not in (Enum, StrEnum) and (
                    issubclass(kind, (BaseModel, Enum)) or is_dataclass(kind)):
                self.assertIn(kind, registered, kind.__name__)
                if issubclass(kind, BaseModel):
                    for field in kind.model_fields.values():
                        visit(field.annotation)
                elif is_dataclass(kind):
                    for annotation in get_type_hints(kind).values():
                        visit(annotation)
            else:
                for arg in get_args(kind):
                    try:
                        hash(arg)
                    except TypeError:
                        continue
                    visit(arg)

        visit(GeoSurfacePlanningView)
        visit(GeoSurfacePlanBundle)

    def test_complete_view_bundle_and_each_phase_replay(self):
        plans = bundle(self.view)
        for value in (self.view, plans, *(
                getattr(plans, name) for name in type(plans).model_fields
                if isinstance(getattr(plans, name), PlanEnvelope))):
            with self.subTest(type=type(value).__name__):
                wire = encode(value, SURFACE_MANIFEST)
                restored = decode(wire, type(value), SURFACE_MANIFEST)
                self.assertEqual(restored, value)
                self.assertEqual(encode(restored, SURFACE_MANIFEST), wire)
                if isinstance(value, PlanEnvelope):
                    codec = SurfaceEnvelopeCodec(type(value), SURFACE_MANIFEST)
                    self.assertEqual(codec.decode(codec.encode(value)), value)

    def test_all_source_variants_survive_capture_codec(self):
        path = tuple(HydrologyWaypoint(x=x, y=y) for x, y in ((0, 0), (1, 0), (1, 1)))
        sources = (
            AuthoredBasinSource(value=DeclaredBasin(location_uid="basin", kind=BasinKind.SEA, floor_z=-5,
                footprint=BboxShape(x_min=0, x_max=1, y_min=0, y_max=1))),
            AuthoredLakeSource(value=DeclaredLake(location_uid="lake", shoreline=path)),
            CoastlineWaterSource(value=DeclaredCoastline(location_uid="coast", kind=BasinKind.SEA, path=path)),
            ProceduralSource(value=ProceduralWaterSource(source_uid="auto", generation_region_uid="region",
                kind=BasinKind.OCEAN, liquid="water")))
        inputs = rebuild(self.view.water_placement, sources=sources)
        captured = rebuild(self.view, water_placement=inputs)
        self.assertEqual(decode(encode(captured, SURFACE_MANIFEST), type(captured), SURFACE_MANIFEST), captured)

    def test_nonempty_placement_outcomes_metadata_decisions_and_budget_replay(self):
        plan = placement_plan()
        restored = decode(encode(plan, SURFACE_MANIFEST), type(plan), SURFACE_MANIFEST)
        self.assertEqual(restored, plan)
        self.assertEqual(tuple(item.status for item in restored.outcomes), ("resolved", "disabled", "unresolved"))
        self.assertEqual(tuple(item.identity.source_uid for item in restored.outcomes), ("basin", "off", "missing"))

    def test_resolution_modes_are_coherent(self):
        for name in ("water_placement", "hydrology", "boundary_input", "coating_input"):
            with self.subTest(phase=name), self.assertRaisesRegex(ValidationError, "execution mode"):
                rebuild(self.view, **{name: rebuild(getattr(self.view, name), resolution_mode=ResolutionMode.VALIDATE_ONLY)})

    def test_every_spatial_phase_requires_the_captured_grid(self):
        grid = SurfaceGridSettings(fine_span=self.view.terrain_base.grid.fine_span + 1, light_side=2)
        for name in ("water_placement", "region_input", "relief", "hydrology", "river_relief",
                     "hydrology_final", "boundary_input", "surface_support"):
            with self.subTest(phase=name), self.assertRaisesRegex(ValidationError, "captured grid"):
                rebuild(self.view, **{name: rebuild(getattr(self.view, name), grid=grid)})

    def test_every_topology_phase_requires_the_captured_topology(self):
        original = self.view.water_placement.topology
        other = WorldTopology(mode="planar", bounds=original.bounds)
        if other == original:
            other = WorldTopology(mode="wrapped", bounds=original.bounds)
        for name in ("region_input", "hydrology", "river_relief", "hydrology_final", "boundary_input", "surface_support"):
            with self.subTest(phase=name), self.assertRaisesRegex(ValidationError, "captured topology"):
                rebuild(self.view, **{name: rebuild(getattr(self.view, name), topology=other)})

    def test_authored_bounds_presence_and_z_range_cannot_drift(self):
        with self.assertRaisesRegex(ValidationError, "world-bounds presence"):
            rebuild(self.view, region_input=rebuild(self.view.region_input, declared_world_bounds=None))
        water = self.view.water_placement
        with self.assertRaisesRegex(ValidationError, "world bounds"):
            rebuild(water, declared_world_bounds=WorldBounds(x_min=0, x_max=5, y_min=0, y_max=1))
        for name in ("water_placement", "relief", "hydrology", "river_relief"):
            with self.subTest(phase=name), self.assertRaisesRegex(ValidationError, "z range"):
                rebuild(self.view, **{name: rebuild(getattr(self.view, name), z_min=self.view.terrain_base.z_min - 1)})

    def test_admission_rejects_forged_mutable_and_invalid_legacy_instances(self):
        for name, change in (("water_placement", {"sources": []}), ("hydrology", {"anchors": []}),
                             ("water_placement", {"seas": self.view.water_placement.seas.model_copy(
                                 update={"placement_specificity": -1})})):
            with self.subTest(phase=name, change=change), self.assertRaises(ValidationError):
                rebuild(self.view, **{name: getattr(self.view, name).model_copy(update=change)})

    def test_duplicate_and_unknown_liquid_sources_are_rejected(self):
        source = ProceduralSource(value=ProceduralWaterSource(source_uid="auto", generation_region_uid="region",
            kind=BasinKind.OCEAN, liquid="water"))
        with self.assertRaisesRegex(ValidationError, "duplicate water source"):
            rebuild(self.view.water_placement, sources=(source, source))
        with self.assertRaisesRegex(ValidationError, "material membership"):
            rebuild(self.view.water_placement, sources=(source,), liquid_keys=frozenset())

    def test_boundary_cannot_share_identity_with_body_producer(self):
        source = coastline()
        boundary = coastline(True).model_copy(update={"location_uid": source.value.location_uid})
        with self.assertRaisesRegex(ValidationError, "body-producing source universe"):
            rebuild(self.view, water_placement=rebuild(self.view.water_placement, sources=(source,)),
                boundary_input=rebuild(self.view.boundary_input, sources=(boundary,)))

    def test_bundle_rejects_foreign_phase_versions_worlds_and_dependency_refs(self):
        plans = bundle(self.view)
        for key_update in ({"world_uid": "other"}, {"schema_version": 999}, {"contract_id": "wrong.phase"}):
            envelope = plans.water_placement
            forged = rebuild(envelope, ref=rebuild(envelope.ref, key=rebuild(envelope.ref.key, **key_update)))
            with self.subTest(change=key_update), self.assertRaisesRegex(ValidationError, "foreign world/scope/phase/version"):
                rebuild(plans, water_placement=forged)
        deps = plans.coating.dependencies
        forged = rebuild(deps[0], ref=rebuild(deps[0].ref, output_fingerprint=b"x" * 32))
        with self.assertRaisesRegex(ValidationError, "dependency refs"):
            rebuild(plans, coating=rebuild(plans.coating, dependencies=(forged, *deps[1:])))

    def test_bundle_preserves_route_mapping_in_final_fill(self):
        plans = bundle(self.view)
        mapping = SourceBodyMapping(entries=(SourceBodyMappingEntry(source_uid="dry-source", body_uids=()),))
        final = rebuild(plans.hydrology, payload=rebuild(plans.hydrology.payload, source_mapping=mapping))
        with self.assertRaisesRegex(ValidationError, "preserve route-stage"):
            rebuild(plans, hydrology=final)
