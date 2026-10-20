"""Coverage Spec/Shape wire, geometry, and shared author-validation contract."""

import copy
import json
import math
import unittest

from pydantic import TypeAdapter, ValidationError

from app.application.jsonValidation.resolve import ResolveContext
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldColumnResolve import resolve_world_column
from app.dataModel.spatial.regionShape import (
    AnchorRadiusShape, BboxShape, CorridorShape, EllipseShape, PolygonShape, RegionShape,
)
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.regions import (
    FarmlandSpec, ForestSpec, LandcoverDeclareEntry, PlainSpec,
)


SHAPES = (
    {"kind": "bbox", "x_min": -4, "y_min": -2, "x_max": 4, "y_max": 2},
    {"kind": "ellipse", "cx": 0, "cy": 0, "rx": 4, "ry": 2},
    {"kind": "polygon", "vertices": [[-4, -2], [4, -2], [0, 2]]},
    {"kind": "anchor_radius", "anchor_uid": "anchor-1", "radius": 4},
    {"kind": "corridor", "path": [[-4, -2], [4, 2]], "width": 2},
)
SPEC_TYPES = {"forest": ForestSpec, "plains": PlainSpec, "farmland": FarmlandSpec}
SHAPE_TYPES = (BboxShape, EllipseShape, PolygonShape, AnchorRadiusShape, CorridorShape)


def declarations():
    return [
        {"name": f"{entry_type}-{i}", "entry_type": entry_type, "shape": shape}
        for entry_type in SPEC_TYPES for i, shape in enumerate(SHAPES)
    ]


class RegionWireTests(unittest.TestCase):
    def test_declaration_defaults_are_registered_terrain_keys(self):
        registry = WorldTerrainRegistry.canonical_defaults()
        for spec_cls in SPEC_TYPES.values():
            with self.subTest(spec=spec_cls.__name__):
                spec = spec_cls(shape=SHAPES[0])
                self.assertIsNotNone(registry.entry_for(spec.entry_type))
                self.assertEqual(sum(entry.system_terrain == spec.entry_type
                                     for entry in registry.root), 1)
                self.assertEqual(WorldTerrainRegistry.require_engine_terrain_key(spec.entry_type),
                                 spec.entry_type)

    def test_world_json_all_shape_union_variants_round_trip(self):
        raw = {"declared_regions": declarations()}
        masks = WorldTerrainMasks.model_validate_json(json.dumps(raw), context={"validate_only": True})
        for i, spec in enumerate(masks.declared_regions):
            self.assertIsInstance(spec, SPEC_TYPES[spec.entry_type])
            self.assertIsInstance(spec.shape, SHAPE_TYPES[i % len(SHAPE_TYPES)])
            self.assertEqual(spec.density, 1.0)
            self.assertIsNone(spec.placement_specificity)
            self.assertIsNone(spec.location_uid)
        self.assertEqual(WorldTerrainMasks.model_validate_json(masks.model_dump_json()), masks)
        schema = WorldTerrainMasks.model_json_schema()
        prop = schema["properties"]["declared_regions"]
        if "$ref" in prop:  # DefaultWhenMissing wraps the array in $defs
            prop = schema["$defs"][prop["$ref"].rsplit("/", 1)[-1]]
        union = prop["items"]
        self.assertEqual(union["discriminator"]["propertyName"], "entry_type")
        self.assertEqual(set(union["discriminator"]["mapping"]), set(SPEC_TYPES))
        self.assertEqual(schema["$defs"]["ForestSpec"]["properties"]["shape"]
                         ["discriminator"]["propertyName"], "kind")

    def test_world_column_author_validation_keeps_typed_wire(self):
        raw = {"declared_regions": declarations()}
        original = copy.deepcopy(raw)
        result = resolve_world_column("terrain_masks", raw,
                                      ResolveContext.for_import(validate_only=True))
        self.assertEqual(raw, original)
        self.assertEqual(len(WorldTerrainMasks.model_validate(result["terrain_masks"]).declared_regions), len(SHAPES) * len(SPEC_TYPES))

    def test_missing_names_are_issues_only_on_author_path(self):
        for value in (None, "", "  ", "missing"):
            entry = {"entry_type": "forest", "shape": SHAPES[0]}
            if value != "missing":
                entry["name"] = value
            raw = {"declared_regions": [entry]}
            with self.subTest(name=value):
                self.assertIsNone(WorldTerrainMasks.model_validate(raw).declared_regions[0].name)
                ctx = ResolveContext.for_import(validate_only=True)
                with self.assertRaises(ImportValidationError) as raised:
                    resolve_world_column("terrain_masks", raw, ctx)
                self.assertTrue(any(issue.path[-1] == "name" for issue in raised.exception.errors))
                self.assertTrue(ctx.report.issues)

    def test_name_normalization_and_uniqueness_across_types(self):
        first = ForestSpec(name="  Cafe\u0301  ", shape=SHAPES[0])
        self.assertEqual(first.name, "Café")
        second = PlainSpec(name="Café", shape=SHAPES[1])
        self.assertEqual(first.identity_key(), second.identity_key())
        with self.assertRaises(ValidationError):
            WorldTerrainMasks(declared_regions=[first, second])
        masks = WorldTerrainMasks(declared_regions=[first, PlainSpec(name="CAFÉ", shape=SHAPES[0])])
        self.assertEqual(len(masks.declared_regions), 2)
        with self.assertRaises(ValidationError):
            ForestSpec(name="a|b", shape=SHAPES[0])

    def test_optional_runtime_name_and_identity_do_not_need_uid_generation(self):
        shape = BboxShape.model_validate(SHAPES[0])
        first = ForestSpec(shape=shape)
        resized = ForestSpec(shape=BboxShape(x_min=-4, y_min=-2, x_max=20, y_max=30))
        self.assertEqual(first.identity_key(), resized.identity_key())
        self.assertNotEqual(first.identity_key(), ForestSpec(shape=SHAPES[1]).identity_key())
        self.assertEqual(ForestSpec(shape=SHAPES[3]).identity_key(),
                         FarmlandSpec(shape=SHAPES[3]).identity_key())

    def test_reject_unknown_fields_and_invalid_discriminators(self):
        adapter = TypeAdapter(LandcoverDeclareEntry)
        base = {"entry_type": "forest", "name": "region", "shape": SHAPES[0]}
        for key in ("flora", "crop", "origin_x", "origin_y", "priority"):
            with self.subTest(key=key), self.assertRaises(ValidationError) as raised:
                adapter.validate_python({**base, key: {}})
            self.assertEqual(raised.exception.errors()[0]["type"], "extra_forbidden")
        invalid = (
            {"name": "region", "shape": SHAPES[0]},
            {**base, "entry_type": "steppe"},
            {**base, "shape": {"x_min": 0}},
            {**base, "shape": {"kind": "blob"}},
            {**base, "shape": {**SHAPES[0], "radius": 10}},
            {**base, "shape": None},
            {**base, "density": None},
            {**base, "density": -0.1},
            {**base, "density": 1.1},
            {**base, "density": float("nan")},
            {**base, "placement_specificity": -1},
        )
        for wire in invalid:
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                adapter.validate_python(wire)
        self.assertEqual(adapter.validate_python({**base, "placement_specificity": 0})
                         .placement_specificity, 0)

    def test_new_collection_default_preserves_existing_policies(self):
        masks = WorldTerrainMasks.canonical_defaults()
        self.assertEqual(masks.declared_regions, [])
        self.assertEqual(masks.default_landcover.terrain_policy(WorldTerrainRegistry.forest_terrain_key()).system_terrain, "forest")
        self.assertEqual(masks.default_landcover.fallback_terrain, "plains")
        with self.assertRaises(ValidationError):
            masks.declared_regions = []


class RegionGeometryTests(unittest.TestCase):
    def test_bbox_and_ellipse_world_coordinates_and_boundaries(self):
        bbox = BboxShape.model_validate(SHAPES[0])
        self.assertEqual(bbox.bbox(), (-4, -2, 4, 2))
        self.assertEqual(bbox.area(), 45)  # coverage cells: (8+1) * (4+1)
        ellipse = EllipseShape.model_validate(SHAPES[1])
        self.assertEqual(ellipse.bbox(), bbox.bbox())
        self.assertAlmostEqual(ellipse.area(), 8 * math.pi)
        for shape in (bbox, ellipse):
            self.assertTrue(shape.contains(0, 0))
            self.assertTrue(shape.contains(4, 0))
            self.assertTrue(shape.contains(0, -2))
            self.assertFalse(shape.contains(5, 0))
        self.assertFalse(ellipse.contains(4, 2))
        self.assertTrue(bbox.contains(4, 2))
        self.assertEqual(BboxShape(x_min=1, x_max=1, y_min=0, y_max=0).area(), 1)

    def test_polygon_concave_both_windings_and_explicit_closure(self):
        vertices = [(10, 10), (14, 10), (14, 12), (12, 12), (12, 14), (10, 14)]
        for ring in (vertices, vertices[::-1], vertices + vertices[:1]):
            shape = PolygonShape(vertices=ring)
            self.assertEqual(shape.vertices, ring)
            self.assertEqual(shape.area(), 12)
            self.assertEqual(shape.bbox(), (10, 10, 14, 14))
            for point in ((11, 13), (13, 11), (12, 12), (14, 10), (10, 12)):
                self.assertTrue(shape.contains(*point), point)
            for point in ((13, 13), (9, 11), (15, 10)):
                self.assertFalse(shape.contains(*point), point)

    def test_noise_does_not_change_geometry(self):
        adapter = TypeAdapter(RegionShape)
        for wire in SHAPES:
            plain = adapter.validate_python(wire)
            noisy = adapter.validate_python({**wire, "edge_noise": {"amplitude": 100, "scale": 7}})
            self.assertEqual(plain.area(), noisy.area())
            if isinstance(plain, AnchorRadiusShape):
                continue
            self.assertEqual(plain.bbox(), noisy.bbox())
            for point in ((0, 0), (-4, -2), (5, 0), (2, 1)):
                self.assertEqual(plain.contains(*point), noisy.contains(*point))

    def test_unresolved_anchor_has_area_but_no_absolute_position(self):
        shape = AnchorRadiusShape.model_validate(SHAPES[3])
        self.assertAlmostEqual(shape.area(), 16 * math.pi)
        with self.assertRaisesRegex(ValueError, "resolved in collect"):
            shape.contains(0, 0)
        with self.assertRaisesRegex(ValueError, "resolved in collect"):
            shape.bbox()

    def test_malformed_geometry_rejected_without_repairs(self):
        adapter = TypeAdapter(RegionShape)
        invalid = [
            {**SHAPES[0], "x_max": -5}, {**SHAPES[0], "y_max": -3},
            *[{**SHAPES[1], key: value} for key in ("rx", "ry") for value in (0, -1)],
            *[{**SHAPES[3], "radius": value} for value in (0, -1)],
            {**SHAPES[3], "anchor_uid": ""},
            *[{"kind": "polygon", "vertices": ring} for ring in (
                [(0, 0), (1, 1)],
                [(0, 0), (1, 1), (0, 0)],
                [(0, 0), (1, 1), (2, 2)],
                [(0, 0), (4, 4), (0, 4), (4, 0)],
                [(0, 0), (4, 0), (2, 0), (2, 3), (0, 3)],
                [(0, 0), (4, 0), (4, 4), (2, 0), (0, 4)],
                [(0, 0), (4, 0), (4, 4), (0, 0), (0, 4)],
            )],
            *[{**SHAPES[0], "edge_noise": noise} for noise in (
                {"amplitude": -1, "scale": 1}, {"amplitude": 1, "scale": 0},
                {"amplitude": 1, "scale": -1}, {"amplitude": 1},
                {"amplitude": 1, "scale": 1, "seed": 4},
            )],
        ]
        for wire in invalid:
            original = copy.deepcopy(wire)
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                adapter.validate_python(wire)
            self.assertEqual(wire, original)
        # Collinear forward edges remain valid on a simple ring.
        self.assertEqual(PolygonShape(vertices=[(0, 0), (2, 0), (4, 0), (0, 4)]).area(), 8)


if __name__ == "__main__":
    unittest.main()
