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


class TerrainPlanningPayloadTests(unittest.TestCase):
    def grid(self):
        from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
        return SurfaceGridSettings(fine_span=1000, light_side=4)

    def topology(self):
        from app.dataModel.topology.worldBounds import WorldBounds
        from app.dataModel.topology.worldTopology import WorldTopology
        return WorldTopology(bounds=WorldBounds(x_min=0, x_max=10, y_min=0, y_max=6))

    def water_result(self):
        from app.application.worldData.generators.hydrology.placement import run_water_placement_pass
        from tests.hydrology_fixtures import flat_heightmap
        from tests.test_water_placement_pass import _basin_world
        return run_water_placement_pass(_basin_world(), [], flat_heightmap(0, 10, 0, 6))

    def test_grid_and_terrain_inputs_require_explicit_valid_values(self):
        from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
        from app.dataModel.spatial.grid.gridBBox import GridBBox
        from app.dataModel.spatial.grid.coordinateTypes import FineZ
        from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
        for wire in ({}, {"fine_span": 100}, {"fine_span": True, "light_side": 2},
                     {"fine_span": 0, "light_side": 2}, {"fine_span": 100, "light_side": -1}):
            with self.assertRaises(ValidationError):
                SurfaceGridSettings.model_validate(wire)
        original = TerrainBaseInput(seed=42, bbox=GridBBox(0, 1, 0, 0),
                                    z_min=FineZ(-10), z_max=FineZ(10), grid=self.grid())
        for update in ({"z_min": 11}, {"z_max": True}, {"bbox": GridBBox(1, 0, 0, 0)}):
            with self.assertRaises(ValidationError):
                TerrainBaseInput.model_validate(original.model_dump() | update)

    def test_surface_coverage_and_working_copy_are_independent(self):
        from app.dataModel.spatial.grid.gridBBox import GridBBox
        from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord
        from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
        left, right = SurfaceGridCoord(GridX(0), GridY(0)), SurfaceGridCoord(GridX(1), GridY(0))
        cells = ((left, FineZ(3)), (right, FineZ(4)))
        plan = TerrainPlan(bbox=GridBBox(0, 1, 0, 0), surface_z=cells)
        working = {(coord.gx, coord.gy): z for coord, z in plan.surface_z}
        working[(0, 0)] = 99
        self.assertEqual(plan.surface_z, cells)
        for bad in ((), cells[:1], (cells[0], cells[0]), tuple(reversed(cells)),
                    (cells[0], (SurfaceGridCoord(GridX(2), GridY(0)), FineZ(4)))):
            with self.assertRaises(ValidationError):
                TerrainPlan(bbox=plan.bbox, surface_z=bad)
        with self.assertRaises(ValidationError):
            plan.surface_z = ()
        with self.assertRaises(FrozenInstanceError):
            plan.surface_z[0][0].gx = GridX(99)

    def test_basin_move_preserves_identity_and_original_invariants(self):
        from app.application.worldData.generators.terrain.reliefObjects.bathymetry.basinSpec import BasinSpec as Old
        from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
        self.assertIs(Old, BasinSpec)
        spec = self.water_result().basin_specs[0]
        self.assertIsInstance(spec, BasinSpec)
        for updates in ({"footprint": frozenset()}, {"floor_z": spec.z_water_level}):
            with self.assertRaises(ValueError):
                replace(spec, **updates)
        with self.assertRaises(FrozenInstanceError):
            spec.floor_z = 100

    def test_water_plan_joins_by_uid_and_rejects_inconsistent_records(self):
        from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
        from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
        result = self.water_result()
        wire = dict(coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID, topology=result.topology,
                    records=result.records, basin_specs=result.basin_specs)
        plan = WaterPlacementPlan(**wire)
        spec = plan.basin_specs[0]
        # The second source is intentionally in the opposite order in the spec tuple.
        record = result.records[0]
        identity = record.placement.identity.model_copy(update={"source_uid": "second"})
        intent = record.placement.prepared.intent.model_copy(update={"identity": identity})
        prepared = record.placement.prepared.model_copy(update={"intent": intent})
        other = record.model_copy(update={"placement": record.placement.model_copy(update={"prepared": prepared})})
        joined = WaterPlacementPlan(**(wire | {"records": (record, other),
                                              "basin_specs": (replace(spec, source_uid="second"), spec)}))
        self.assertEqual(len(joined.records), 2)
        for update in ({"coordinate_space": CoordinateSpace.WORLD_FINE_GRID},
                       {"basin_specs": ()}, {"records": (record, record)},
                       {"basin_specs": (replace(spec, liquid="lava"),)},
                       {"basin_specs": (replace(spec, footprint=frozenset({(0, 0)})),)},
                       {"basin_specs": (replace(spec, kind=None),)},
                       {"basin_specs": (replace(spec, z_water_level=spec.z_water_level + 1),)}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                WaterPlacementPlan(**(wire | update))
        empty = WaterPlacementPlan(**(wire | {"records": (), "basin_specs": ()}))
        self.assertEqual(empty.records, ())

    def test_water_inputs_are_immutable_and_capture_bounds_and_liquid_vocabulary(self):
        from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
        from app.dataModel.hydrology.seas import HydrologySeasPolicy
        from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
        from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
        from app.dataModel.validation.enums.resolutionMode import ResolutionMode
        wire = dict(enabled=False, resolution_mode=ResolutionMode.RUNTIME, default_water_level=0,
                    seas=HydrologySeasPolicy(), lakes=HydrologyLakesPolicy(), basins=(), coastlines=(),
                    declared_lakes=(), anchors=(), topology=self.topology(), grid=self.grid(), z_min=-10, z_max=10,
                    liquid_keys=frozenset({RegistryKey[WorldMaterialRegistry]("water")}))
        captured = WaterPlacementInput.model_validate(wire)
        with self.assertRaises(ValidationError):
            captured.grid.fine_span = 2
        for update in ({"z_max": -11}, {"enabled": 0}, {"basins": []}):
            with self.assertRaises(ValidationError):
                WaterPlacementInput.model_validate(wire | update)
        self.assertEqual(captured.basins, ())
        from app.dataModel.hydrology.declaredBasin import DeclaredBasin
        basin = DeclaredBasin.model_validate({"location_uid": "declared", "kind": "lake", "floor_z": -2,
            "footprint": {"kind": "bbox", "x_min": 0, "x_max": 1, "y_min": 0, "y_max": 1}})
        self.assertEqual(WaterPlacementInput.model_validate(wire | {"basins": (basin,)}).basins, (basin,))
        for bad in (basin.model_copy(update={"floor_z": -11}),
                    basin.model_copy(update={"z_water_level": 11}),
                    basin.model_copy(update={"liquid": RegistryKey[WorldMaterialRegistry]("unknown")})):
            with self.assertRaises(ValidationError):
                WaterPlacementInput.model_validate(wire | {"basins": (bad,)})

    def test_terrain_contract_imports_do_not_load_application(self):
        script = ("import sys; from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan; "
                  "from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput; "
                  "assert not any(n.startswith(('app.application', 'app.db')) for n in sys.modules)")
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class ReliefPlanningPayloadTests(unittest.TestCase):
    def peak(self, **updates):
        return MountainSpec.model_validate({**PEAK, "sides": [{"kind": "slope"}] * 6} | updates)

    def merge(self):
        from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import TerrainMergeEntry
        return (TerrainMergeEntry(key=RegistryKey[WorldTerrainRegistry]("mountain"), merge_rank=10),
                TerrainMergeEntry(key=RegistryKey[WorldTerrainRegistry]("ravine"), merge_rank=5))

    def layout(self, **updates):
        from app.dataModel.terrain.relief.planning.reliefPlan import MountainLayout
        from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
        return MountainLayout.model_validate(dict(entries=(self.peak(),), templates=(),
            world_pick=ReliefContextPickPolicy(), terrain_key="mountain") | updates)

    def light(self, **updates):
        from app.dataModel.spatial.grid.coordinateTypes import FineZ, LightCellRef
        from app.dataModel.terrain.relief.planning.reliefPlan import LightReliefPlan
        return LightReliefPlan.model_validate(dict(base_surface_z=tuple(
            (LightCellRef(0, 0, tx, ty), FineZ(3)) for ty in range(2) for tx in range(2)),
            mountain_cells=(), ravine_cells=(), ravine_terrain="ravine", terrain_merge=self.merge()) | updates)

    def test_mountain_layout_preserves_full_specs_and_requires_stamped_sides(self):
        ridge = MountainRangeSpec.model_validate({"spine": [[0, 0], [10, 0]], "peaks": [self.peak()],
            "peak_spacings_m": [9], "saddles": [{"peak_a_index": 0, "peak_b_index": 1}], "location_uid": "ridge"})
        layout = self.layout(entries=(ridge, self.peak()))
        self.assertEqual(layout.entries[0], ridge)
        self.assertEqual(layout.entries[0].identity_key(), ridge.identity_key())
        self.assertEqual(layout.entries[0].peak_spacings_m, (9,))
        for entries in ((self.peak(), self.peak()), (MountainSpec.model_validate(PEAK),),
                        (ridge.model_copy(update={"peaks": (MountainSpec.model_validate(PEAK),)}),)):
            with self.assertRaises(ValidationError):
                self.layout(entries=entries)
        with self.assertRaises(ValidationError):
            layout.entries[0].peaks[0].origin_x_m = 99

    def test_templates_are_unique_sorted_and_retain_recipe_edit(self):
        from app.dataModel.terrain.relief.enums import ReliefContext
        from app.dataModel.terrain.relief.planning.reliefPlan import MountainTemplateInput
        template = MountainTemplateInput(template_uid="a", context=ReliefContext.MOUNTAIN, side_recipe=None)
        self.assertIsNone(self.layout(templates=(template,)).templates[0].side_recipe)
        other = template.model_copy(update={"template_uid": "b"})
        for templates in ((template, template), (other, template)):
            with self.assertRaises(ValidationError):
                self.layout(templates=templates)
        with self.assertRaises(ValidationError):
            MountainTemplateInput(template_uid="wrong", context=ReliefContext.SHORE, side_recipe=None)
        edited = template.model_copy(update={"side_recipe": MountainSideRecipe(side_kinds=("slope", "sheer"))})
        self.assertNotEqual(self.layout(templates=(template,)), self.layout(templates=(edited,)))

    def test_light_effects_require_unique_ordered_cells_inside_the_base(self):
        from app.dataModel.spatial.grid.coordinateTypes import FineZ, LightCellRef
        from app.dataModel.terrain.relief.planning.reliefPlan import LightMountainCell
        light = self.light()
        first = light.base_surface_z[0][0]
        effect = LightMountainCell(cell=first, surface_z=FineZ(7), facing=None)
        self.assertEqual(self.light(mountain_cells=(effect,)).mountain_cells[0].surface_z, 7)
        for updates in ({"base_surface_z": (light.base_surface_z[0],) * 2},
                        {"base_surface_z": tuple(reversed(light.base_surface_z))},
                        {"mountain_cells": (effect, effect)},
                        {"mountain_cells": (effect.model_copy(update={"cell": LightCellRef(1, 0, 0, 0)}),)},
                        {"terrain_merge": tuple(reversed(self.merge()))}):
            with self.assertRaises(ValidationError):
                self.light(**updates)
        with self.assertRaises(ValidationError):
            light.mountain_cells = ()

    def test_relief_surface_retains_coarse_and_light_extent(self):
        from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord
        from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan
        surface = ((SurfaceGridCoord(GridX(0), GridY(0)), FineZ(7)),)
        plan = ReliefPlan(surface_z=surface, mountain_layout=self.layout(), light=self.light())
        self.assertEqual(plan.surface_z, surface)
        with self.assertRaises(ValidationError):
            ReliefPlan(surface_z=(), mountain_layout=self.layout(), light=self.light())

    def test_relief_input_and_river_depths_capture_existing_policy_values(self):
        from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Kind
        from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
        from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
        from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy
        from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
        from app.dataModel.terrainMasks.worldTerrainMasks import RavinesCategoryPolicy
        grid = SurfaceGridSettings(fine_span=1000, light_side=2)
        captured = ReliefPlanInput.model_validate(dict(seed=42, masks_enabled=True, mountains=MountainsCategoryPolicy(),
            ravines=RavinesCategoryPolicy(), declared_mountains=(MountainSpec.model_validate(PEAK),), anchors=(), grid=grid,
            z_min=-10, z_max=10, mountain_templates=(), mountain_pick=ReliefContextPickPolicy(), terrain_merge=self.merge()))
        self.assertEqual(captured.declared_mountains[0].sides, ())  # source has not been stamped yet
        policy = HydrologyRiversPolicy()
        depths = tuple((kind, policy.channel_depth_for(kind)) for kind in sorted((Kind.RIVER, Kind.MOUNTAIN_RIVER)))
        wire = dict(z_min=-10, z_max=10, grid=grid, topology=TerrainPlanningPayloadTests().topology(), channel_depths=depths)
        self.assertEqual(RiverReliefInput.model_validate(wire).channel_depths, depths)
        for updates in ({"channel_depths": depths[:1]}, {"channel_depths": (depths[0], depths[0])},
                        {"channel_depths": ((depths[0][0], True), depths[1])}, {"z_min": 11}):
            with self.assertRaises(ValidationError):
                RiverReliefInput.model_validate(wire | updates)

    def test_river_beds_keep_spaces_and_reject_duplicate_uids_or_missing_surface(self):
        from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord
        from app.dataModel.terrain.relief.planning.reliefPlan import RiverBedRecord, RiverReliefPlan
        coord = SurfaceGridCoord(GridX(0), GridY(0))
        coarse = RiverBedRecord[SurfaceGridCoord](river_uid="river", bed_z=((coord, FineZ(2)),))
        from app.dataModel.spatial.grid.coordinateTypes import FineXY
        fine = RiverBedRecord[FineXY](river_uid="river", bed_z=(((FineX(0), FineY(0)), FineZ(1)),))
        wire = dict(surface_z=coarse.bed_z, fine_surface_z=fine.bed_z, coarse_beds=(coarse,), fine_beds=(fine,))
        plan = RiverReliefPlan(**wire)
        self.assertEqual(plan.coarse_beds[0].river_uid, plan.fine_beds[0].river_uid)
        for updates in ({"coarse_beds": (coarse, coarse)}, {"fine_surface_z": ()}, {"coarse_beds": (fine,)}):
            with self.assertRaises(ValidationError):
                RiverReliefPlan(**(wire | updates))
        with self.assertRaises(ValidationError):
            RiverBedRecord[SurfaceGridCoord](river_uid="river", bed_z=coarse.bed_z * 2)

    def test_relief_modules_import_in_both_orders_without_application(self):
        paths = ("app.dataModel.terrain.relief.planning.reliefPlan", "app.dataModel.terrain.relief.planning.inputs.reliefPlanInput")
        for order in (paths, tuple(reversed(paths))):
            script = (f"import importlib,sys; [importlib.import_module(p) for p in {order!r}]; "
                      "assert not any(n.startswith(('app.application', 'app.db')) for n in sys.modules)")
            result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


class HydrologyPlanningPayloadTests(unittest.TestCase):
    def paint(self):
        from app.dataModel.hydrology.planning.hydrologyPlan import DeclaredWaterPaint
        return DeclaredWaterPaint(lakes=(), coastlines=(), segments=(), intents=())

    def body(self):
        from app.dataModel.hydrology.waterBody import WaterBody
        return WaterBody(water_body_uid="lake", location_uid="lake-location", kind="lake",
                         liquid="water", declared_level=2, z_water_level=2, parent_system_uid="system")

    def route(self, uid="river", receiver="lake", *, fine=False):
        from app.dataModel.hydrology.enums.basinKind import BasinKind
        from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Kind
        from app.dataModel.hydrology.planning.hydrologyPlan import RiverPathSegment, RiverRoute
        from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
        from app.dataModel.spatial.grid.coordinateTypes import FineXY, SurfaceGridCoord
        a, b = ((FineX(0), FineY(0)), (FineX(1), FineY(0))) if fine else (
            SurfaceGridCoord(GridX(0), GridY(0)), SurfaceGridCoord(GridX(1), GridY(0)))
        coordinate_type = FineXY if fine else SurfaceGridCoord
        segment = RiverPathSegment[coordinate_type](path=(a, b), connection_type=Kind.RIVER,
            edge_uid=None, location_uid=None, declared=False)
        drainage = RiverDrainageLink(river_uid=uid, river_type=Kind.RIVER, receiver_uid=receiver,
            receiver_kind=BasinKind.LAKE if receiver == "lake" else Kind.RIVER,
            receiver_cell=(1, 0) if fine else (1000, 0))
        return RiverRoute[coordinate_type](river_uid=uid, segments=(segment,), receiver_cell=b, drainage=drainage)

    def routes(self, **updates):
        from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyRoutesPlan
        return HydrologyRoutesPlan.model_validate(dict(coarse_open_water=(), water_bodies=(self.body(),),
            physical_unions=(), coarse_routes=(self.route(),), fine_routes=(), fine_base_surface_z=(),
            declared_paint=self.paint()) | updates)

    def test_scope_move_preserves_identity_values_and_bootstrap(self):
        from app.application.worldData.generators.hydrology.types import HydrologyScope as Old, HYDROLOGY_BOOTSTRAP_SCOPES as OldSet
        from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope, HYDROLOGY_BOOTSTRAP_SCOPES
        self.assertIs(Old, HydrologyScope)
        self.assertIs(OldSet, HYDROLOGY_BOOTSTRAP_SCOPES)
        self.assertEqual(tuple(scope.value for scope in HydrologyScope), ("coastal_sea", "open_ocean", "lakes", "rivers", "landforms"))
        self.assertNotIn(HydrologyScope.LANDFORMS, HYDROLOGY_BOOTSTRAP_SCOPES)

    def test_declared_paint_keeps_geometry_and_two_width_units(self):
        from app.dataModel.hydrology.planning.hydrologyPlan import DeclaredWaterPaint, IntentRiverPaint, SegmentRiverPaint
        from app.dataModel.spatial.grid.coordinateTypes import FineDelta
        path = ((FineX(0), FineY(0)), (FineX(10), FineY(5)))
        segment = SegmentRiverPaint(edge_uid="edge", location_uid=None, segment=path, width_fine=FineDelta(100))
        intent = IntentRiverPaint(river_uid="river", path=path, width_wire=0)
        paint = DeclaredWaterPaint(lakes=(), coastlines=(), segments=(segment,), intents=(intent,))
        self.assertEqual(DeclaredWaterPaint.model_validate_json(paint.model_dump_json()), paint)
        self.assertEqual(paint.intents[0].path, path)
        for updates in ({"width_wire": -1}, {"width_wire": 999}, {"width_wire": True}, {"path": path[:1]}):
            with self.assertRaises(ValidationError):
                IntentRiverPaint.model_validate(intent.model_dump() | updates)
        with self.assertRaises(ValidationError):
            SegmentRiverPaint.model_validate(segment.model_dump() | {"width_fine": 0})

    def test_routes_require_terminal_receiver_bed_and_matching_drainage(self):
        from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute
        from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
        route = self.route()
        for updates in ({"receiver_cell": route.segments[0].path[0]},
                        {"segments": (route.segments[0].model_copy(update={"path": (route.receiver_cell,)}),)},
                        {"drainage": route.drainage.model_copy(update={"river_uid": "wrong"})},
                        {"drainage": route.drainage.model_copy(update={"receiver_uid": "river"})}):
            with self.assertRaises(ValidationError):
                RiverRoute[SurfaceGridCoord].model_validate(route.model_dump() | updates)
        self.assertEqual(route.drainage.receiver_cell, (1000, 0))  # diagnostic fine coordinate is preserved

    def test_rooted_drainage_and_fine_height_coverage(self):
        fine = self.route(fine=True)
        base = tuple((cell, 3) for cell in fine.segments[0].path)
        self.assertEqual(self.routes(fine_routes=(fine,), fine_base_surface_z=base).fine_routes[0], fine)
        for updates in ({"coarse_routes": (self.route(), self.route())},
                        {"coarse_routes": (self.route(receiver="missing"),)},
                        {"coarse_routes": (self.route(uid="a", receiver="b"), self.route(uid="b", receiver="a"))},
                        {"fine_routes": (fine,), "fine_base_surface_z": base[:1]}):
            with self.assertRaises(ValidationError):
                self.routes(**updates)
        accepted = self.routes(coarse_routes=(self.route(uid="tributary", receiver="main"), self.route(uid="main")))
        self.assertEqual(len(accepted.coarse_routes), 2)
        from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
        route = self.route()
        invalid = route.model_copy(update={"drainage": route.drainage.model_copy(
            update={"receiver_kind": HydrologyConnectionType.RIVER})})
        with self.assertRaises(ValidationError):
            self.routes(coarse_routes=(invalid,))

    def test_final_facts_detach_from_working_map_and_round_trip(self):
        from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
        from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan
        from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord
        coord = SurfaceGridCoord(GridX(0), GridY(0))
        cell = MapCellHydrology(role="lake", water_body_uid="lake", z_water_level=2)
        working = {coord: cell}
        plan = HydrologyPlan(coarse_surface_z=((coord, FineZ(1)),), coarse_hydro=tuple(working.items()),
            sparse_fine_hydro=(), fine_z_overrides=(), water_bodies=(self.body(),), physical_unions=(), declared_paint=self.paint())
        working.clear()
        self.assertEqual(plan.coarse_hydro[0][1].water_body_uid, "lake")
        self.assertEqual(HydrologyPlan.model_validate_json(plan.model_dump_json()), plan)
        self.assertEqual(plan.water_bodies[0].parent_system_uid, "system")
        with self.assertRaises(ValidationError):
            plan.water_bodies[0].z_water_level = 99
        for updates in ({"coarse_hydro": plan.coarse_hydro * 2}, {"coarse_surface_z": ()},
                        {"water_bodies": plan.water_bodies * 2}):
            with self.assertRaises(ValidationError):
                HydrologyPlan.model_validate(plan.model_dump() | updates)

    def test_inputs_keep_mode_scope_and_nullable_anchor_fields_explicit(self):
        from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope, HYDROLOGY_BOOTSTRAP_SCOPES
        from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput, HydrologyFinalInput, HydrologyAnchorInput
        from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
        from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
        from app.dataModel.hydrology.seas import HydrologySeasPolicy
        from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
        from app.dataModel.validation.enums.resolutionMode import ResolutionMode
        grid = SurfaceGridSettings(fine_span=1000, light_side=2)
        anchor = HydrologyAnchorInput(location_uid="anchor", position=None, z=None, subtype=None)
        wire = dict(enabled=False, seed=42, resolution_mode=ResolutionMode.RUNTIME, scopes=HYDROLOGY_BOOTSTRAP_SCOPES,
            default_water_level=0, seas=HydrologySeasPolicy(), lakes=HydrologyLakesPolicy(), rivers=HydrologyRiversPolicy(),
            declared_rivers=(), coastlines=(), declared_lakes=(), anchors=(anchor,), grid=grid,
            topology=TerrainPlanningPayloadTests().topology(), z_min=-10, z_max=10, liquid_keys=frozenset(), change_uid="change")
        captured = HydrologyPlanInput.model_validate(wire)
        self.assertEqual(captured.anchors, (anchor,))
        for updates in ({"scopes": frozenset({HydrologyScope.LANDFORMS})}, {"z_min": 11}, {"seed": True}):
            with self.assertRaises(ValidationError):
                HydrologyPlanInput.model_validate(wire | updates)
        with self.assertRaises(ValidationError):
            HydrologyAnchorInput.model_validate({"location_uid": "anchor", "position": None, "z": None})
        final = HydrologyFinalInput(enabled=False, grid=grid, topology=wire["topology"])
        self.assertNotIn("rivers", type(final).model_fields)

    def test_hydrology_contract_imports_do_not_load_application_or_db(self):
        script = ("import sys; from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan; "
                  "from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput; "
                  "assert not any(n.startswith(('app.application', 'app.db')) for n in sys.modules)")
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class HydrologyStagePayloadTests(unittest.TestCase):
    def setUp(self):
        from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
        from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan, RiverRouteBatch
        from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
        from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
        from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord, FineXY
        self.Open, self.Coarse, self.Fine, self.Batch = OpenWaterPlan, CoarseRiverPlan, FineRiverPlan, RiverRouteBatch
        self.Cell, self.FineXY, self.Hydro, self.Role = SurfaceGridCoord, FineXY, MapCellHydrology, HydrologyCellRole
        self.fixture = HydrologyPlanningPayloadTests()

    def claim(self, route, edge_uid=None):
        return self.Hydro(role=self.Role.RIVER_BED, water_body_uid=route.river_uid,
                          connection_edge_uid=edge_uid, river_drainage=route.drainage)

    def coarse(self):
        route = self.fixture.route()
        return self.Coarse(routes=(route,), claims=((route.segments[0].path[0], self.claim(route)),))

    def test_open_water_reuses_body_union_and_coordinate_contracts(self):
        from app.dataModel.hydrology.physicalWaterUnion import PhysicalWaterUnion
        body = self.fixture.body()
        union = PhysicalWaterUnion(water_system_uid="system", member_uids=("lake",), child_system_uids=(), z_water_level=2)
        cell = self.Cell(GridX(0), GridY(0))
        plan = self.Open(coarse_open_water=((cell, self.Hydro(role=self.Role.LAKE, water_body_uid="lake", z_water_level=2)),),
                         water_bodies=(body,), physical_unions=(union,))
        self.assertEqual(self.Open.model_validate_json(plan.model_dump_json()), plan)
        self.assertEqual(plan.water_bodies[0].parent_system_uid, union.water_system_uid)
        for updates in ({"water_bodies": (body, body)}, {"physical_unions": (union, union)},
                        {"coarse_open_water": plan.coarse_open_water * 2},
                        {"coarse_open_water": ((self.Cell(GridX(1), GridY(0)), plan.coarse_open_water[0][1]), *plan.coarse_open_water)},
                        {"coarse_open_water": (((FineX(0), FineY(0)), plan.coarse_open_water[0][1]),)}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.Open.model_validate(plan.model_dump() | updates)

    def test_coarse_alias_and_route_claim_json_round_trip(self):
        self.assertIs(self.Coarse, self.Batch[self.Cell])
        batch = self.coarse()
        self.assertEqual(self.Coarse.model_validate_json(batch.model_dump_json()), batch)
        self.assertEqual(batch.claims[0][1].river_drainage, batch.routes[0].drainage)

    def test_claims_require_exact_bed_coverage_and_route_metadata(self):
        batch = self.coarse()
        cell, claim = batch.claims[0]
        route = batch.routes[0]
        for updates in ({"claims": ()}, {"routes": ()}, {"routes": batch.routes * 2},
                        {"claims": batch.claims * 2}, {"claims": (*batch.claims, (route.receiver_cell, claim))},
                        {"claims": (((FineX(0), FineY(0)), claim),)}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.Coarse.model_validate(batch.model_dump() | updates)
        for updates in ({"role": self.Role.LAKE}, {"water_body_uid": "another"},
                        {"connection_edge_uid": "wrong-edge"}, {"river_drainage": None}):
            invalid = claim.model_copy(update=updates)
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.Coarse(routes=batch.routes, claims=((cell, invalid),))

    def test_shared_segment_boundary_uses_last_published_edge_metadata(self):
        from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute, RiverPathSegment
        route = self.fixture.route()
        a, b = route.segments[0].path
        c = self.Cell(GridX(2), GridY(0))
        first = route.segments[0].model_copy(update={"edge_uid": "first", "path": (a, b)})
        second = route.segments[0].model_copy(update={"edge_uid": "second", "path": (b, c)})
        route = RiverRoute[self.Cell](river_uid=route.river_uid, segments=(first, second),
                                     receiver_cell=c, drainage=route.drainage)
        claims = ((a, self.claim(route, "first")), (b, self.claim(route, "second")))
        batch = self.Coarse(routes=(route,), claims=claims)
        self.assertEqual(batch.claims[1][1].connection_edge_uid, "second")
        with self.assertRaises(ValidationError):
            self.Coarse(routes=(route,), claims=((a, self.claim(route, "first")), (b, self.claim(route, "first"))))

    def test_parent_bed_remains_claimed_when_it_is_a_tributary_receiver(self):
        from app.dataModel.hydrology.planning.hydrologyPlan import RiverRoute
        parent = self.fixture.route(uid="parent")
        junction = parent.segments[0].path[0]
        source = self.Cell(GridX(0), GridY(1))
        template = self.fixture.route(uid="child", receiver="parent")
        child = RiverRoute[self.Cell](river_uid="child", receiver_cell=junction, drainage=template.drainage,
            segments=(template.segments[0].model_copy(update={"path": (source, junction)}),))
        batch = self.Coarse(routes=(parent, child), claims=((junction, self.claim(parent)), (source, self.claim(child))))
        self.assertEqual(batch.claims[0][1].water_body_uid, "parent")

    def test_fine_batch_preserves_its_space_and_rejects_unspecialized_mixed_spaces(self):
        fine = self.fixture.route(fine=True)
        cell = fine.segments[0].path[0]
        batch = self.Batch[self.FineXY](routes=(fine,), claims=((cell, self.claim(fine)),))
        self.assertEqual(self.Batch[self.FineXY].model_validate_json(batch.model_dump_json()), batch)
        coarse = self.coarse()
        with self.assertRaises(ValidationError):
            self.Batch(routes=(*coarse.routes, fine.model_copy(update={"river_uid": "fine",
                "drainage": fine.drainage.model_copy(update={"river_uid": "fine"})})), claims=coarse.claims)
        with self.assertRaises(ValidationError):
            self.Batch[self.FineXY](routes=coarse.routes, claims=coarse.claims)

    def test_fine_samples_include_receiver_and_preserve_unrelated_retained_samples(self):
        fine = self.fixture.route(fine=True)
        rows = tuple((cell, 7) for cell in fine.segments[0].path) + (((FineX(2), FineY(0)), 11),)
        plan = self.Fine(routes=(fine,), base_surface_z=rows)
        self.assertEqual(plan.base_surface_z[-1][1], 11)
        self.assertEqual(self.Fine.model_validate_json(plan.model_dump_json()), plan)
        # Samples from rejected authored routes can remain even without accepted routes.
        self.assertEqual(self.Fine(routes=(), base_surface_z=rows).base_surface_z, rows)
        for updates in ({"base_surface_z": rows[:1]}, {"base_surface_z": rows[1:]},
                        {"base_surface_z": tuple(reversed(rows))}, {"base_surface_z": rows * 2},
                        {"routes": (fine, fine)}, {"routes": (self.fixture.route(),)},
                        {"base_surface_z": ((self.Cell(GridX(0), GridY(0)), 7),)}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.Fine.model_validate(plan.model_dump() | updates)

    def test_stage_contracts_are_required_strict_and_recursively_frozen(self):
        for owner, payload in ((self.Open, dict(coarse_open_water=(), water_bodies=(), physical_unions=())),
                               (self.Coarse, dict(routes=(), claims=())), (self.Fine, dict(routes=(), base_surface_z=()))):
            model = owner.model_validate(payload)
            for name in payload:
                with self.subTest(owner=owner, field=name), self.assertRaises(ValidationError):
                    owner.model_validate({k: v for k, v in payload.items() if k != name})
                with self.assertRaises(ValidationError):
                    owner.model_validate(payload | {name: []})
                with self.assertRaises(ValidationError):
                    setattr(model, name, ())
            with self.assertRaises(ValidationError):
                owner.model_validate(payload | {"unplanned": ()})
        batch = self.coarse()
        with self.assertRaises(ValidationError):
            batch.claims[0][1].water_body_uid = "changed"
        with self.assertRaises(ValidationError):
            batch.routes[0].drainage.receiver_uid = "changed"
        with self.assertRaises(ValidationError):
            self.Fine(routes=(), base_surface_z=(((FineX(0), FineY(0)), True),))
        with self.assertRaises(ValidationError):
            self.Fine(routes=(), base_surface_z=(((True, FineY(0)), 1),))

    def test_existing_build_result_keeps_explicit_diagnostic_disposition(self):
        from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
        from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
        from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
        plan = self.Open(coarse_open_water=(), water_bodies=(), physical_unions=())
        for disposition in PlanDiagnosticDisposition:
            fact = PlanDiagnostic(issue=FieldPathError(("hydrology",), "producer decision", code="opaque"), disposition=disposition)
            result = PlanBuildResult[self.Open](payload=plan, diagnostics=(fact,))
            self.assertEqual(result.diagnostics[0].disposition, disposition)
            self.assertEqual(PlanBuildResult[self.Open].model_validate_json(result.model_dump_json()), result)

    def test_stage_contract_imports_do_not_load_application_or_db(self):
        script = ("import sys; from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan; "
                  "from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan; "
                  "assert not any(n.startswith(('app.application', 'app.db')) for n in sys.modules)")
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
