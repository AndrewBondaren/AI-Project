"""Typed purpose/target, shared wire normalization and canonical encoding."""

from unittest import TestCase

from pydantic import TypeAdapter, ValidationError

from app.application.encoding.canonicalCodec import encode, decode
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError, import_validation_http_detail
from app.application.worldData.planning.encoding.surfaceManifest import SURFACE_MANIFEST
from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose as Purpose, DeclaredCoastline
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource, WaterDesignSource


def coast(**changes):
    return dict(location_uid="coast", kind="sea", path=[dict(x=4, y=4), dict(x=8, y=8)]) | changes


class CoastlinePurposeTests(TestCase):
    def test_legacy_wire_defaults_only_missing_purpose_to_water_source(self):
        value = DeclaredCoastline.model_validate(coast())
        self.assertIs(value.purpose, Purpose.WATER_SOURCE)
        self.assertTrue(value.is_water_source)
        self.assertIsNone(value.target_source_uid)
        normalized = normalize_world({"world_uid": "world", "hydrology": {"declared_coastlines": [coast()]}})
        self.assertEqual(normalized["hydrology"]["declared_coastlines"][0]["purpose"], "water_source")

    def test_source_and_boundary_roundtrip_and_remain_frozen(self):
        for raw in (coast(purpose="water_source"), coast(purpose="body_boundary", target_source_uid="water-source")):
            value = DeclaredCoastline.model_validate(raw)
            self.assertEqual(DeclaredCoastline.model_validate_json(value.model_dump_json()), value)
            with self.assertRaises(ValidationError):
                value.purpose = Purpose.BODY_BOUNDARY

    def test_body_boundary_requires_target_and_source_rejects_target(self):
        for raw in (coast(purpose="body_boundary"), coast(purpose="body_boundary", target_source_uid=None),
                    coast(target_source_uid="water-source"), coast(purpose="water_source", target_source_uid="water-source")):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                DeclaredCoastline.model_validate(raw)
        self.assertTrue(DeclaredCoastline.model_validate(coast(target_source_uid=None)).is_water_source)

    def test_target_uses_existing_strict_opaque_uid_without_trim_or_coercion(self):
        for target in ("", " ", " source", "source ", True, 4, [], {}):
            with self.subTest(target=target), self.assertRaises(ValidationError):
                DeclaredCoastline.model_validate(coast(purpose="body_boundary", target_source_uid=target))

    def test_supplied_invalid_purpose_is_not_defaulted(self):
        for purpose in (None, True, 0, "shore", "", []):
            with self.subTest(purpose=purpose), self.assertRaises(ValidationError):
                DeclaredCoastline.model_validate(coast(purpose=purpose))

    def test_existing_closed_water_side_distinct_points_and_kind_contracts_remain(self):
        for changes in ({"closed": True}, {"kind": "shore"}, {"path": [dict(x=1, y=1)]},
                        {"purpose": "body_boundary", "target_source_uid": "source", "closed": True}):
            with self.assertRaises(ValidationError):
                DeclaredCoastline.model_validate(coast(**changes))

    def test_source_wrapper_rejects_boundary_including_copied_instances(self):
        source = DeclaredCoastline.model_validate(coast())
        boundary = DeclaredCoastline.model_validate(coast(purpose="body_boundary", target_source_uid="source"))
        adapter = TypeAdapter(WaterDesignSource)
        self.assertEqual(CoastlineWaterSource(value=source).value, source)
        for value in (boundary, source.model_copy(update={"purpose": Purpose.BODY_BOUNDARY, "target_source_uid": "source"})):
            with self.assertRaises(ValidationError):
                CoastlineWaterSource(value=value)
        with self.assertRaises(ValidationError):
            adapter.validate_python(CoastlineWaterSource.model_construct(value=boundary))

    def test_shared_import_validator_rejects_unknown_enum_and_invalid_combinations(self):
        for raw in (coast(purpose="unknown"), coast(purpose=None), coast(purpose="body_boundary"),
                    coast(target_source_uid="source"), coast(purpose="body_boundary", target_source_uid=True)):
            with self.subTest(raw=raw), self.assertRaises(ImportValidationError):
                normalize_world({"world_uid": "world", "hydrology": {"declared_coastlines": [raw]}})
        with self.assertRaises(ImportValidationError) as raised:
            normalize_world({"world_uid": "world", "hydrology": {"declared_coastlines": [coast(purpose="unknown")]}})
        self.assertTrue(any(e["code"] == "UNKNOWN_ENUM" for e in import_validation_http_detail(raised.exception)))

    def test_source_ref_stays_opaque_until_runtime_support_resolution(self):
        raw = coast(purpose="body_boundary", target_source_uid="future-auto-water-source")
        normalized = normalize_world({"world_uid": "world", "hydrology": {"declared_coastlines": [raw]}})
        value = normalized["hydrology"]["declared_coastlines"][0]
        self.assertEqual(value["purpose"], "body_boundary")
        self.assertEqual(value["target_source_uid"], "future-auto-water-source")

    def test_new_enum_and_target_are_registered_in_the_surface_canonical_codec(self):
        source = DeclaredCoastline.model_validate(coast())
        boundary = DeclaredCoastline.model_validate(coast(purpose="body_boundary", target_source_uid="source"))
        for value in (source, boundary):
            self.assertEqual(decode(encode(value, SURFACE_MANIFEST), DeclaredCoastline, SURFACE_MANIFEST), value)
        self.assertNotEqual(encode(source, SURFACE_MANIFEST), encode(boundary, SURFACE_MANIFEST))
