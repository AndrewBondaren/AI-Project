"""PC-0I: immutable source collections retain their wire and REF-W contracts."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
