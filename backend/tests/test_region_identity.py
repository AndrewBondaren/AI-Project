"""Region entity identity, revision, and author/runtime diagnostics."""

import unittest
from dataclasses import replace

from pydantic import TypeAdapter

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape, EllipseShape, PolygonShape
from app.dataModel.spatial.regionShape import RegionShape, RegionShapeKind
from app.dataModel.terrainMasks.regions import ForestSpec, PlainSpec
from app.ids import UID_PART_SEPARATOR, UidKind, entity_uid, state_fingerprint
from app.ids.regionIdentity import region_uid

LOG = "app.application.jsonValidation.resolve"


class RegionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.world_uid = "world-region-test"
        self.other_world_uid = "world-region-other"
        self.name = "Café"
        self.anchor_uid = "anchor-region-test"
        self.seed_xy = (20, -10)
        self.path = ("terrain_masks", "declared_regions", 0)
        self.ctx = ResolveContext(path_prefix=self.path)
        self.shape = EllipseShape(cx=10, cy=20, rx=5, ry=3)
        self.spec = ForestSpec(name=self.name, shape=self.shape)

    def test_named_identity_uses_only_normalized_name_and_world(self):
        decomposed_name = "  Cafe\u0301  "
        expected = entity_uid(self.world_uid, UidKind.REGION, name=self.name)
        self.assertEqual(region_uid(self.world_uid, name=decomposed_name), expected)
        self.assertEqual(declared_region_identity(self.world_uid, self.spec).region_uid, expected)
        self.assertNotEqual(region_uid(self.world_uid, name=self.name.upper()), expected)
        self.assertNotEqual(region_uid(self.other_world_uid, name=self.name), expected)

    def test_named_resize_density_and_type_change_preserve_uid_but_change_revision(self):
        original = declared_region_identity(self.world_uid, self.spec)
        changes = (
            self.spec.model_copy(update={"shape": self.shape.model_copy(update={"rx": 8, "ry": 7})}),
            self.spec.model_copy(update={"density": 0.5}),
            PlainSpec(name=self.name, shape=self.shape),
            self.spec.model_copy(update={"name": self.name + " renamed"}),
        )
        for changed in changes:
            with self.subTest(spec=changed):
                identity = declared_region_identity(self.world_uid, changed)
                self.assertNotEqual(identity.state_fingerprint, original.state_fingerprint)
                self.assertEqual(identity.region_uid == original.region_uid, changed.name == self.name)

    def test_anonymous_bbox_shift_changes_uid_and_reports_degraded_identity(self):
        shape = BboxShape(x_min=-10, y_min=5, x_max=10, y_max=20)
        spec = ForestSpec(shape=shape)
        shifted = spec.model_copy(update={"shape": shape.model_copy(update={"x_min": -11})})
        with self.assertLogs(LOG, level="WARNING") as caught:
            original = declared_region_identity(self.world_uid, spec, ctx=self.ctx)
            moved = declared_region_identity(self.world_uid, shifted, ctx=self.ctx)
        self.assertNotEqual(original.region_uid, moved.region_uid)
        self.assertEqual(original.region_uid, entity_uid(
            self.world_uid, UidKind.REGION, bbox_min=(-10, 5), shape_kind=shape.kind,
        ))
        self.assertEqual(len(caught.records), 2)
        for record, issue in zip(caught.records, self.ctx.report.issues):
            self.assertIn("WarningError", record.getMessage())
            self.assertIn("landcover | degraded_identity", record.getMessage())
            self.assertEqual(issue.code, "REGION_DEGRADED_IDENTITY")
            self.assertEqual(issue.path, self.path + ("name",))

    def test_anonymous_shapes_share_bbox_min_rule_and_include_shape_kind(self):
        bbox = BboxShape(x_min=5, y_min=17, x_max=15, y_max=23)
        polygon = PolygonShape(vertices=[(5, 17), (15, 17), (5, 23)])
        identities = []
        for shape in (bbox, self.shape, polygon):
            with self.subTest(shape=shape), self.assertLogs(LOG, level="WARNING"):
                identity = declared_region_identity(self.world_uid, ForestSpec(shape=shape))
            self.assertEqual(identity.region_uid, region_uid(
                self.world_uid, bbox_min=(5, 17), shape_kind=shape.kind,
            ))
            identities.append(identity.region_uid)
        self.assertEqual(len(set(identities)), 3)

    def test_anonymous_anchor_uses_anchor_identity_without_absolute_geometry(self):
        shape = AnchorRadiusShape(anchor_uid=self.anchor_uid, radius=10)
        spec = ForestSpec(shape=shape)
        resized = spec.model_copy(update={"shape": shape.model_copy(update={"radius": 20})})
        with self.assertLogs(LOG, level="WARNING"):
            original = declared_region_identity(self.world_uid, spec)
            changed = declared_region_identity(self.world_uid, resized)
        expected = entity_uid(self.world_uid, UidKind.REGION, anchor_uid=self.anchor_uid)
        self.assertEqual(original.region_uid, expected)
        self.assertEqual(changed.region_uid, expected)
        self.assertNotEqual(original.state_fingerprint, changed.state_fingerprint)
        with self.assertNoLogs(LOG, level="WARNING"):
            self.assertEqual(region_uid(self.world_uid, anchor_uid=self.anchor_uid), expected)

    def test_autoresolve_uses_seed_coordinates_and_separates_other_sources(self):
        expected = entity_uid(self.world_uid, UidKind.REGION, seed_xy=self.seed_xy)
        self.assertEqual(region_uid(self.world_uid, seed_xy=self.seed_xy), expected)
        self.assertNotEqual(region_uid(self.world_uid, seed_xy=(21, -10)), expected)
        self.assertNotEqual(region_uid(self.world_uid, bbox_min=self.seed_xy, shape_kind=self.shape.kind), expected)

    def test_shape_discriminator_round_trip_produces_enum_and_preserves_wire(self):
        adapter = TypeAdapter(RegionShape)
        shapes = (
            BboxShape(x_min=0, y_min=0, x_max=5, y_max=5),
            self.shape,
            PolygonShape(vertices=[(0, 0), (5, 0), (0, 5)]),
            AnchorRadiusShape(anchor_uid=self.anchor_uid, radius=10),
        )
        for shape in shapes:
            with self.subTest(kind=shape.kind):
                wire = shape.model_dump(mode="json")
                self.assertIs(type(wire["kind"]), str)
                self.assertEqual(wire["kind"], shape.kind.value)
                restored = adapter.validate_json(adapter.dump_json(shape))
                self.assertIs(restored.kind, shape.kind)
                self.assertIsInstance(restored.kind, RegionShapeKind)
                self.assertEqual(restored, shape)

    def test_typed_shape_kind_preserves_existing_uid_formula(self):
        for kind in RegionShapeKind:
            if kind is RegionShapeKind.ANCHOR_RADIUS:
                continue
            with self.subTest(kind=kind):
                self.assertEqual(
                    region_uid(self.world_uid, bbox_min=self.seed_xy, shape_kind=kind),
                    entity_uid(self.world_uid, UidKind.REGION,
                               bbox_min=self.seed_xy, shape_kind=kind.value),
                )

    def test_shape_identity_rejects_untyped_kind_and_anchor_bbox(self):
        for invalid in ("bbox", "garbage", "", 1, object()):
            with self.subTest(kind=invalid), self.assertRaises(TypeError):
                region_uid(self.world_uid, bbox_min=self.seed_xy, shape_kind=invalid)
        with self.assertRaises(ValueError):
            region_uid(self.world_uid, bbox_min=self.seed_xy,
                       shape_kind=RegionShapeKind.ANCHOR_RADIUS)

    def test_missing_name_is_author_error_without_degraded_uid(self):
        author_ctx = replace(self.ctx, validate_only=True)
        with self.assertNoLogs(LOG, level="WARNING"), self.assertRaises(UnresolvedModelError):
            declared_region_identity(self.world_uid, ForestSpec(shape=self.shape), ctx=author_ctx)
        self.assertEqual(len(author_ctx.report.issues), 1)
        self.assertEqual(author_ctx.report.issues[0].path, self.path + ("name",))

    def test_invalid_name_reaches_shared_issue_sink_even_for_unchecked_typed_input(self):
        invalid_name = self.name + UID_PART_SEPARATOR + "invalid"
        unchecked = self.spec.model_copy(update={"name": invalid_name})
        for validate_only in (True, False):
            ctx = ResolveContext(path_prefix=self.path, validate_only=validate_only)
            log_context = (self.assertNoLogs(LOG, level="WARNING") if validate_only
                           else self.assertLogs(LOG, level="WARNING"))
            with self.subTest(validate_only=validate_only), log_context:
                with self.assertRaises(UnresolvedModelError):
                    declared_region_identity(self.world_uid, unchecked, ctx=ctx)
            self.assertEqual(ctx.report.issues[0].path, self.path + ("name",))

    def test_fingerprint_is_wire_based_repeatable_and_key_order_independent(self):
        wire = self.spec.model_dump(mode="json")
        expected = state_fingerprint(wire)
        first = declared_region_identity(self.world_uid, self.spec)
        self.assertEqual(first.state_fingerprint, expected)
        self.assertEqual(first, declared_region_identity(self.world_uid, self.spec))
        self.assertEqual(state_fingerprint(dict(reversed(list(wire.items())))), expected)

    def test_identity_rejects_missing_or_competing_sources_without_fallback(self):
        cases = (
            {}, {"name": "  "}, {"shape_kind": self.shape.kind}, {"bbox_min": self.seed_xy},
            {"name": self.name, "anchor_uid": self.anchor_uid},
            {"seed_xy": self.seed_xy, "anchor_uid": self.anchor_uid},
        )
        for keys in cases:
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                region_uid(self.world_uid, **keys)


if __name__ == "__main__":
    unittest.main()
