"""PC-0I: immutable source collections retain their wire and REF-W contracts."""

import unittest
from dataclasses import FrozenInstanceError, replace
import subprocess
import sys

from pydantic import BaseModel, ConfigDict, ValidationError

from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.jsonValidation.resolve import (
    ResolveContext, UnresolvedModelError, validate_contracts,
)
from app.application.templateLibrary.reliefTemplateLibraryService import relief_template_uid
from app.application.worldData.generators.terrain.mountains.reliefSidesStamp import stamp_entries_from_relief
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.declaredRiver import DeclaredRiver
from app.dataModel.materials.worldMaterialRegistry import MaterialKey
from app.dataModel.spatial.regionShape import CorridorShape, PolygonShape
from app.dataModel.terrain.relief.mountainSideRecipe import MountainSideRecipe
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrainMasks.mountain.specs import MountainRangeSpec, MountainSpec
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy
from app.db.models.world import World
from app.dataModel.climate.climatePoleBlendDefaults import CLIMATE_POLE_BLEND
from app.dataModel.climate.enums.climatePoleMode import ClimatePoleMode
from app.dataModel.climate.enums.climatePolePreset import ClimatePolePreset
from app.dataModel.climate.enums.climateZone import ClimateZoneProfileData
from app.dataModel.climate.enums.poleKind import PoleKind
from app.dataModel.climate.enums.poleSource import PoleSource
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan, ResolvedClimateProfile
from app.dataModel.climate.planning.climatePoints import AnchorSource, ClimateAnchorPoint, ClimatePolePoint, PoleClimateSample
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput, ManualPoleInput
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateFeaturePolicy, ClimateLocalInput, ProminenceScale, ProminenceThresholds
from app.dataModel.registryKey import RegistryKey
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY, FineX, FineY


POINTS = [{"x": 0, "y": 0, "z": 0}, {"x": 10, "y": 0, "z": 0},
          {"x": 0, "y": 10, "z": 0}]
PEAK = {"origin_x_m": 0, "origin_y_m": 0, "radius_m": 100}
RIVER = {"location_uid": "river", "declare_mode": "via_locations",
         "route_location_uids": ["source", "mouth"]}


class ReferencePayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    lakes: tuple[DeclaredLake, ...]
    materials: tuple[MaterialKey | None, ...]


class ImmutableSourceCollectionsTests(unittest.TestCase):
    def test_json_arrays_round_trip_to_tuples_and_detach_from_input(self):
        cases = (
            (PolygonShape, {"kind": "polygon", "vertices": [[0, 0], [10, 0], [0, 10]]}, ("vertices",)),
            (CorridorShape, {"kind": "corridor", "path": [[0, 0], [10, 0]], "width": 2}, ("path",)),
            (DeclaredCoastline, {"location_uid": "sea", "kind": "sea", "path": POINTS}, ("path",)),
            (DeclaredLake, {"location_uid": "lake", "shoreline": POINTS}, ("shoreline",)),
            (DeclaredRiver, RIVER, ("route_location_uids", "segments")),
            (DeclaredRiver, {"location_uid": "river", "declare_mode": "segments", "segments": [
                {"from": POINTS[0], "to": POINTS[1], "connection_type": "river"}]},
             ("route_location_uids", "segments")),
            (MountainSpec, {**PEAK, "sides": [{"kind": "slope"}]}, ("sides",)),
            (MountainRangeSpec, {"spine": [[0, 0], [10, 0]], "peaks": [PEAK],
                "peak_spacings_m": [10], "saddles": [{"peak_a_index": 0, "peak_b_index": 1}]},
             ("spine", "peaks", "peak_spacings_m", "saddles")),
            (MountainsCategoryPolicy, {"sides": [{"kind": "slope"}]}, ("sides",)),
            (MountainSideRecipe, {"side_kinds": ["slope", "sheer"]}, ("side_kinds",)),
        )
        for model, wire, fields in cases:
            with self.subTest(model=model.__name__, wire=wire):
                source = model.model_validate(wire)
                encoded = source.model_dump(mode="json", by_alias=True)
                restored = model.model_validate_json(source.model_dump_json(by_alias=True))
                self.assertEqual(restored, source)
                for field in fields:
                    collection = getattr(source, field)
                    self.assertIsInstance(collection, tuple)
                    self.assertIsInstance(encoded[field], list)
                    with self.assertRaises(AttributeError):
                        collection.append(None)
                    if collection:
                        with self.assertRaises(TypeError):
                            collection[0] = None
                with self.assertRaises(ValidationError):
                    setattr(source, fields[0], ())
        raw = [[0, 0], [10, 0], [0, 10]]
        shape = PolygonShape(vertices=raw)
        raw[0][0] = 99
        self.assertEqual(shape.vertices[0], (0, 0))

    def test_missing_empty_null_and_required_fields(self):
        for model, wire, fields in (
            (MountainSpec, PEAK, ("sides",)),
            (MountainRangeSpec, {"spine": [[0, 0], [10, 0]]}, ("peaks", "peak_spacings_m", "saddles")),
            (MountainsCategoryPolicy, {}, ("sides",)),
            (DeclaredLake, {"location_uid": "lake"}, ("shoreline",)),
            (DeclaredRiver, RIVER, ("segments",)),
        ):
            for field in fields:
                with self.subTest(model=model.__name__, field=field):
                    self.assertEqual(getattr(model.model_validate(wire), field), ())
                    self.assertEqual(getattr(model.model_validate(wire | {field: []}), field), ())
                    with self.assertRaises(ValidationError):
                        model.model_validate(wire | {field: None})
        self.assertIsNone(MountainSideRecipe().side_kinds)
        self.assertIsNone(MountainSideRecipe.model_validate({"side_kinds": None}).side_kinds)
        with self.assertRaises(ValidationError):
            MountainSideRecipe.model_validate({"side_kinds": []})
        for model, field, wire in (
            (PolygonShape, "vertices", {}), (CorridorShape, "path", {"width": 2}),
            (MountainRangeSpec, "spine", {}),
            (DeclaredCoastline, "path", {"location_uid": "sea", "kind": "sea"}),
        ):
            for value in ({}, {field: None}, {field: []}):
                with self.subTest(model=model.__name__, value=value), self.assertRaises(ValidationError):
                    model.model_validate(wire | value)

    def test_ref_w_reaches_tuple_children_and_optional_tuple_keys(self):
        ctx = ResolveContext(path_prefix=("payload",), validate_only=True)
        references = WorldRegistryIndex(materials=frozenset({"water"}))
        wire = {"lakes": [{"location_uid": "lake", "shoreline": POINTS}],
                "materials": [None, "water"]}
        validate_contracts(ReferencePayload, wire, ctx=ctx, references=references)
        for invalid, path in (
            ({**wire, "lakes": [{**wire["lakes"][0], "liquid": "unknown"}]},
             ("payload", "lakes", 0, "liquid")),
            ({**wire, "materials": [None, "unknown"]}, ("payload", "materials", 1)),
        ):
            with self.subTest(path=path):
                with self.assertRaises(UnresolvedModelError) as error:
                    validate_contracts(ReferencePayload, invalid, ctx=ctx, references=references)
                self.assertEqual(error.exception.issues[0].path, path)
                self.assertEqual(error.exception.issues[0].code, "REF_W_UNKNOWN")

    def test_stamping_copies_keep_nested_collections_immutable_and_identity(self):
        uid = relief_template_uid("gentle_dome")
        template = ReliefTemplate.model_validate({"system_name": "gentle_dome", "display_name": "Dome",
            "context": "mountain", "side_recipe": {"default_side_kind": "slope"}})
        world = World(world_uid="w", name="W", created_at="2026-01-01T00:00:00Z",
                      relief_pick_policy={"mountain": {"mode": "fixed", "default_template_uid": uid}})
        peak = MountainSpec.model_validate(PEAK)
        ridge = MountainRangeSpec.model_validate({"spine": [[0, 0], [10, 0]], "peaks": [PEAK]})
        stamped = stamp_entries_from_relief([peak, ridge], world=world, world_seed="w", templates_by_uid={uid: template})
        self.assertEqual(peak.identity_key(), ("mountain", None, 0, 0, 100))
        self.assertEqual(ridge.identity_key(), ("range", None, ((0, 0), (10, 0)), ridge.width_m))
        self.assertEqual(stamped[0].identity_key(), peak.identity_key())
        self.assertEqual(stamped[1].identity_key(), ridge.identity_key())
        self.assertIsInstance(stamped[0].sides, tuple)
        self.assertIsInstance(stamped[1].peaks, tuple)
        self.assertIsInstance(stamped[1].peaks[0].sides, tuple)
        with self.assertRaises(ValidationError):
            stamped[1].peaks[0].sides[0].kind = "sheer"
        self.assertEqual(peak.sides, ())
        self.assertIsInstance(MountainsCategoryPolicy().resolved_sides(), tuple)


class ClimatePlanningPayloadTests(unittest.TestCase):
    def profiles(self):
        return tuple(ResolvedClimateProfile(key=RegistryKey[WorldClimateZoneRegistry](key),
            values=ClimateZoneProfileData(temperature, 3, 50, 4, 8))
            for key, temperature in (("custom", 12), ("arctic", -25)))

    def point(self, **updates):
        return ClimatePolePoint(**(dict(gx=GridX(1), gy=GridY(2), pole_kind=PoleKind.COLD,
            system_climate_zone=RegistryKey[WorldClimateZoneRegistry]("custom"),
            base_temperature=-10, weight=1.0, location_uid=None, source=PoleSource.MANUAL) | updates))

    def base_input(self, **updates):
        return ClimateBaseInput.model_validate(dict(seed=42, bbox=None, fine_span=100,
            mode=ClimatePoleMode.MANUAL, preset=ClimatePolePreset.ICE, peak_min=-30, peak_max=40,
            default_zone="custom", manual_poles=(), profiles=self.profiles(), blend=CLIMATE_POLE_BLEND) | updates)

    def test_base_captures_profiles_and_keeps_manual_order(self):
        first = ManualPoleInput(location_uid="first", position=(FineX(0), FineY(0)), kind=PoleKind.COLD,
                                zone=RegistryKey[WorldClimateZoneRegistry]("custom"))
        second = first.model_copy(update={"location_uid": "second"})
        captured = self.base_input(manual_poles=(second, first))
        self.assertEqual(tuple(p.location_uid for p in captured.manual_poles), ("second", "first"))
        profile = captured.profiles[0]
        edited = profile.model_copy(update={"values": replace(profile.values, base_temperature=13)})
        next_input = self.base_input(profiles=(edited, captured.profiles[1]))
        self.assertNotEqual(captured.profiles, next_input.profiles)
        # The future canonical fingerprint consumes these retained profile values.
        self.assertNotEqual(self.base_input().model_dump_json(), next_input.model_dump_json())
        self.assertEqual(profile.values.base_temperature, 12)
        with self.assertRaises(FrozenInstanceError):
            profile.values.base_temperature = 99
        with self.assertRaises(ValidationError):
            captured.manual_poles = ()

    def test_missing_duplicate_and_unresolved_profiles_are_rejected(self):
        profile = self.profiles()[0]
        for updates in ({"profiles": ()}, {"profiles": (profile, profile)}, {"peak_min": 41},
                        {"fine_span": 0}, {"seed": True}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.base_input(**updates)
        for profiles in ((), (profile, profile), (self.profiles()[1],)):
            with self.assertRaises(ValidationError):
                ClimateBasePlan(poles=(self.point(),), bbox=None, default_zone=profile.key,
                                profiles=profiles, blend=CLIMATE_POLE_BLEND)

    def test_point_contracts_validate_actual_values_and_keep_old_symbol_identity(self):
        from app.application.worldData.generators.climate.climatePole import ClimatePolePoint as OldPole
        from app.application.worldData.generators.climate.climateAnchor import ClimateAnchorPoint as OldAnchor, AnchorSource as OldSource
        from app.application.worldData.generators.climate.climatePoleField import PoleClimateSample as OldSample
        from app.application.worldData.generators.climate.anchorDetect import ProminenceScale as OldScale, ProminenceThresholds as OldThresholds
        for old, new in ((OldPole, ClimatePolePoint), (OldAnchor, ClimateAnchorPoint), (OldSource, AnchorSource),
                         (OldSample, PoleClimateSample), (OldScale, ProminenceScale), (OldThresholds, ProminenceThresholds)):
            self.assertIs(old, new)
        self.assertEqual(self.point(pole_kind="cold").pole_kind, PoleKind.COLD)
        for weight in (0.0, -1.0, float("inf"), float("nan"), True):
            with self.assertRaises(ValidationError):
                self.point(weight=weight)
        with self.assertRaises(ValidationError):
            self.point(gx=True)
        with self.assertRaises(ValidationError):
            self.point(pole_kind="unknown")

    def test_local_source_has_only_declared_points_and_unchanged_feature_defaults(self):
        policy = ClimateFeaturePolicy(synthetic_surface_terrain=RegistryKey[WorldTerrainRegistry]("plains"),
                                      water_feature_terrain=RegistryKey[WorldTerrainRegistry]("liquid_body"))
        self.assertEqual((policy.scale, policy.peak_min, policy.basin_min, policy.liquid_min,
                          policy.max_features, policy.manual_exclusion_grid), (ProminenceScale.METRIC, 50, 25, 10, 32, 2))
        manual = ClimateAnchorPoint(GridX(1), GridY(2), RegistryKey[WorldClimateZoneRegistry]("custom"), "anchor", AnchorSource.MANUAL)
        captured = ClimateLocalInput(manual=(manual,), admin=(), feature_policy=policy)
        result = ClimateLocalPlan(anchors=captured.manual)
        with self.assertRaises(FrozenInstanceError):
            result.anchors[0].gx = GridX(4)
        self.assertEqual(result.anchors[0].system_climate_zone, "custom")
        from app.application.worldData.generators.climate.anchorDetect import metric_prominence_thresholds, MAX_AUTO_FEATURES
        from app.application.worldData.generators.climate.climateAnchor import MANUAL_EXCLUSION_GRID
        self.assertEqual(metric_prominence_thresholds(), ProminenceThresholds(50, 25, 10))
        self.assertEqual((MAX_AUTO_FEATURES, MANUAL_EXCLUSION_GRID), (policy.max_features, policy.manual_exclusion_grid))
        with self.assertRaises(ValidationError):
            ClimateLocalInput(manual=(replace(manual, source=AnchorSource.AUTO),), admin=(), feature_policy=policy)

    def test_legacy_pole_builders_and_sampler_accept_moved_points(self):
        from app.application.worldData.generators.climate.poleResolve import autoresolve_poles
        from app.application.worldData.generators.climate.climatePoleField import ClimatePoleField
        from app.dataModel.spatial.grid.gridBBox import GridBBox
        world = World(world_uid="climate-regression", name="Climate", created_at="now")
        bbox = GridBBox(0, 10, 0, 10)
        poles = tuple(autoresolve_poles(world, bbox))
        self.assertTrue(poles)
        self.assertTrue(all(isinstance(p.pole_kind, PoleKind) for p in poles))
        for points, extent in (((), bbox), ((poles[0],), bbox), ((poles[0],), None), (poles, bbox)):
            sample = ClimatePoleField(poles=points, bbox=extent).sample(world, 3, 4)
            self.assertIsInstance(sample, PoleClimateSample)
            self.assertIsInstance(sample.typical_elevation_z, int)

    def test_climate_contract_imports_do_not_load_application_or_live_world(self):
        script = ("import sys; from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput; "
                  "from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput; "
                  "assert not any(n.startswith(('app.application', 'app.db')) for n in sys.modules)")
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
