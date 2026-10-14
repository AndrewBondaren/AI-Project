"""A6: pure conversion, declared identities and preservation of edited bodies."""
from copy import deepcopy
from dataclasses import replace
import unittest

from app.application.jsonValidation.types import ImportValidationError
from app.application.worldData.libraryPacks.legacyDomainContracts import LegacyDomainRecord, LegacyDomainShape
from app.application.worldData.libraryPacks.legacyDomainSplit import split_legacy_domains
from app.application.worldData.libraryPacks.legacyPack import legacy_member_row
from app.application.worldData.libraryPacks.uidMap import compose_template_uid_maps
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, library_uid, runtime_uid

S, B, P = LibraryKind.STRUCTURE_TEMPLATES, LibraryKind.BUILDING_TEMPLATES, LibraryKind.PLOT_TEMPLATES


def member(kind, name, *, scope="target"):
    pack = library_uid(LibraryKind.LIBRARY_PACKS, scope)
    return LibraryPackMemberRow(library_uid(kind, name, pack_uid=pack), pack, kind.value, name)


def plot(structure, **fields):
    return {"system_name": "plot", "display_name": "Edited plot",
            "main_building": {"structure": structure}, **fields}


def record(kind, body, *, shape=LegacyDomainShape.PLOT, source=None, scope="w1", path=("registry", 0)):
    row = legacy_member_row(kind, body.get("system_name", "geometry") if kind != S else "geometry",
                            world_uid=scope, source_template_uid=source)
    return LegacyDomainRecord(row, kind if shape == LegacyDomainShape.MODERN else B,
                              shape, body, path, source, "edited.json")


class LegacyDomainSplitTests(unittest.TestCase):
    def setUp(self):
        self.structure = member(S, "geometry")

    def convert(self, *records, **kwargs):
        return split_legacy_domains(records, available_members=kwargs.pop("available_members", (self.structure,)), **kwargs)

    def test_plot_keeps_main_secondary_envelopes_and_original_without_creating_building_members(self):
        old = runtime_uid()
        raw = plot(self.structure.template_uid,
            occupied_footprint={"width": 7, "depth": 9, "min_x": 0, "min_y": -2},
            secondary_buildings=[{"structure": self.structure.template_uid,
                "foundation_depth": 0, "porch_has_roof": False, "roof_material": None}])
        raw["main_building"].update(roof_type="flat", foundation_material=None, porch_has_roof=True)
        source = record(P, raw, source=old)
        before = deepcopy(source)
        result = self.convert(source)
        value, = result.require_valid()
        self.assertEqual(source, before)
        self.assertEqual(result.sources[0].body, raw)
        self.assertIsNot(result.sources[0].body, raw)
        self.assertEqual(value.member, source.member)
        self.assertEqual(value.member.source_template_uid, old)
        self.assertEqual(value.body["main_building"]["roof_type"], "flat")
        self.assertTrue(value.body["main_building"]["porch_has_roof"])
        self.assertIsNone(value.body["main_building"]["foundation_material"])
        self.assertEqual(value.body["occupied_footprint"], raw["occupied_footprint"])
        self.assertEqual(value.body["secondary_buildings"][0]["foundation_depth"], 0)
        self.assertFalse(value.body["secondary_buildings"][0]["porch_has_roof"])
        self.assertIsNone(value.body["secondary_buildings"][0]["roof_material"])
        self.assertEqual([entry.path for entry in value.embedded],
            [("registry", 0, "main_building"), ("registry", 0, "secondary_buildings", 0)])
        self.assertEqual(dict(result.uid_map)[old], source.member.template_uid)
        self.assertEqual(value.provenance.source_kind, B)
        self.assertEqual(value.provenance.target_kind, P)

    def test_plot_without_main_building_does_not_synthesize_default(self):
        for raw in ({"system_name": "plot", "display_name": "Vacant"},
                    {"system_name": "plot", "display_name": "Vacant", "main_building": None,
                     "secondary_buildings": []}):
            with self.subTest(raw=raw):
                value, = self.convert(record(P, raw)).require_valid()
                self.assertIsNone(value.body["main_building"])
                self.assertEqual(value.embedded, ())

    def test_outline_with_explicit_structure_becomes_building_and_preserves_overrides(self):
        raw = {"system_name": "house", "display_name": "Edited house", "structure": self.structure.template_uid,
               "foundation_depth": 0, "roof_type": "flat", "porch_material": None, "porch_has_roof": False}
        value, = self.convert(record(B, raw, shape=LegacyDomainShape.BUILDING_OUTLINE)).require_valid()
        self.assertEqual(value.body["structure"], self.structure.template_uid)
        self.assertEqual(value.body["foundation_depth"], 0)
        self.assertEqual(value.body["roof_type"], "flat")
        self.assertIsNone(value.body["porch_material"])
        self.assertFalse(value.body["porch_has_roof"])
        self.assertFalse(value.embedded)

    def test_outline_without_structure_is_diagnosed_and_original_is_retained(self):
        raw = {"system_name": "house", "display_name": "House"}
        source = record(B, raw, shape=LegacyDomainShape.BUILDING_OUTLINE)
        result = self.convert(source)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].path, source.path + ("structure",))
        self.assertEqual(result.sources[0].body, raw)
        self.assertEqual(result.converted, ())
        with self.assertRaises(ImportValidationError):
            result.require_valid()

    def test_unmapped_outline_geometry_or_inline_fields_are_not_silently_dropped(self):
        for raw, kind, shape in (
            ({"system_name": "house", "display_name": "House", "structure": self.structure.template_uid,
              "rooms": [{"edited": True}]}, B, LegacyDomainShape.BUILDING_OUTLINE),
            (plot(self.structure.template_uid, levels=[{"edited": True}]), P, LegacyDomainShape.PLOT),
            (plot(self.structure.template_uid, occupied_footprint={"width": 2, "depth": 3,
                "unknown_dimension": 4}), P, LegacyDomainShape.PLOT),
            (plot(self.structure.template_uid, main_building={"structure": self.structure.template_uid,
                                                             "unknown_edited_field": 7}), P, LegacyDomainShape.PLOT)):
            with self.subTest(raw=raw):
                result = self.convert(record(kind, raw, shape=shape))
                self.assertFalse(result.valid)
                self.assertTrue(any(i.code == "LEGACY_FIELD_UNREPRESENTABLE" for i in result.issues))
                self.assertEqual(result.sources[0].body, raw)

    def test_identical_bodies_with_distinct_source_identities_are_not_merged(self):
        raw = plot(self.structure.template_uid)
        a = record(P, raw, source=runtime_uid(), scope="a")
        b = record(P, raw, source=runtime_uid(), scope="b", path=("registry", 1))
        result = self.convert(a, b)
        left, right = result.require_valid()
        self.assertEqual(left.body, right.body)
        self.assertNotEqual(left.member.template_uid, right.member.template_uid)
        self.assertEqual(len(result.uid_map), 2)

    def test_composed_old_engine_world_map_updates_all_refs_and_structure_identity(self):
        old, intermediate = runtime_uid(), runtime_uid()
        structure = record(S, {"system_name": old, "display_name": "Edited geometry",
            "description": "Authored change", "default_z_height": 5, "door_height_max": 7,
            "levels": [], "connections": [], "staircases": []}, shape=LegacyDomainShape.MODERN,
            source=old, path=("structures", 0))
        source = record(P, plot(old, secondary_buildings=[{"structure": intermediate}]), source=runtime_uid())
        result = self.convert(structure, source, available_members=(),
            uid_maps=({old: intermediate}, {intermediate: structure.member.template_uid}))
        geometry, converted_plot = result.require_valid()
        self.assertEqual(geometry.body["system_name"], structure.member.template_uid)
        self.assertEqual(geometry.body["description"], "Authored change")
        self.assertEqual(geometry.body["default_z_height"], 5)
        self.assertEqual(converted_plot.body["main_building"]["structure"], structure.member.template_uid)
        self.assertEqual(converted_plot.body["secondary_buildings"][0]["structure"], structure.member.template_uid)
        self.assertEqual(dict(result.uid_map)[old], structure.member.template_uid)
        self.assertEqual(dict(result.uid_map)[intermediate], structure.member.template_uid)

    def test_legacy_name_resolves_only_when_unique_with_resolution_path(self):
        source = record(P, plot("geometry"))
        value, = self.convert(source).require_valid()
        self.assertEqual(value.body["main_building"]["structure"], self.structure.template_uid)
        resolution, = value.references
        self.assertEqual(resolution.path, source.path + ("main_building.structure",))
        self.assertEqual(resolution.source_value, "geometry")

    def test_ambiguous_name_lists_candidates_and_explicit_map_can_disambiguate(self):
        other = member(S, "geometry", scope="other")
        source = record(P, plot("geometry"))
        result = self.convert(source, available_members=(self.structure, other))
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "LEGACY_REF_AMBIGUOUS")
        self.assertIn(self.structure.template_uid, result.issues[0].message)
        self.assertIn(other.template_uid, result.issues[0].message)
        value, = self.convert(source, available_members=(self.structure, other),
            name_map={(S, "geometry"): other.template_uid}).require_valid()
        self.assertEqual(value.body["main_building"]["structure"], other.template_uid)

    def test_unknown_name_unavailable_uid_and_wrong_kind_are_errors(self):
        wrong = member(B, "geometry")
        for token, expected in (("missing", "LEGACY_REF_UNKNOWN"),
                                (runtime_uid(), "LEGACY_REF_UNAVAILABLE"),
                                (wrong.template_uid, "LEGACY_REF_KIND")):
            with self.subTest(token=token):
                result = self.convert(record(P, plot(token)), available_members=(wrong,))
                self.assertFalse(result.valid)
                self.assertEqual(result.issues[0].code, expected)

    def test_modern_bodies_keep_extensions_and_declared_provenance(self):
        old = runtime_uid()
        raw = plot(old, custom_extension={"flag": False, "values": [0, None]})
        raw["main_building"]["custom_inline_extension"] = {"edited": 2}
        source = record(P, raw, shape=LegacyDomainShape.MODERN, source=runtime_uid())
        value, = self.convert(source, uid_maps=({old: self.structure.template_uid},)).require_valid()
        self.assertEqual(value.member, source.member)
        self.assertEqual(value.source_file, "edited.json")
        self.assertEqual(value.body["custom_extension"], raw["custom_extension"])
        self.assertEqual(value.body["main_building"]["custom_inline_extension"], {"edited": 2})
        self.assertNotIn("roof_type", value.body["main_building"])
        self.assertEqual(value.body["main_building"]["structure"], self.structure.template_uid)

    def test_modern_name_ref_is_not_accepted_by_compatibility_name_map(self):
        result = self.convert(record(P, plot("geometry"), shape=LegacyDomainShape.MODERN),
                              name_map={(S, "geometry"): self.structure.template_uid})
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "TEMPLATE_REF_UID")

    def test_repeat_conversion_is_stable_and_converted_record_can_pass_as_modern(self):
        source = record(P, plot(self.structure.template_uid), source=runtime_uid())
        first = self.convert(source)
        self.assertEqual(first, self.convert(source))
        value, = first.require_valid()
        modern = LegacyDomainRecord(value.member, P, LegacyDomainShape.MODERN, value.body,
                                    source.path, value.member.template_uid, value.source_file)
        again, = self.convert(modern).require_valid()
        self.assertEqual(again.member, value.member)
        self.assertEqual(again.body, value.body)

    def test_invalid_values_remain_errors_instead_of_defaults(self):
        for field, value in (("foundation_depth", -1), ("roof_type", None), ("structure", None)):
            raw = plot(self.structure.template_uid)
            raw["main_building"][field] = value
            result = self.convert(record(P, raw))
            self.assertFalse(result.valid)
            self.assertEqual(result.sources[0].body, raw)

    def test_bad_record_prevents_partial_conversion_of_whole_input_batch(self):
        good = record(P, plot(self.structure.template_uid))
        bad = record(B, {"system_name": "broken", "display_name": "Broken"},
                     shape=LegacyDomainShape.BUILDING_OUTLINE, path=("registry", 1))
        result = self.convert(good, bad)
        self.assertFalse(result.valid)
        self.assertEqual(result.sources, (good, bad))
        self.assertFalse(result.converted)
        self.assertFalse(result.uid_map)

    def test_declared_shape_and_destination_kind_must_agree(self):
        source = record(B, plot(self.structure.template_uid))
        result = self.convert(source)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "LEGACY_DOMAIN_KIND")

    def test_duplicate_destination_uid_and_conflicting_source_map_are_rejected(self):
        a = record(P, plot(self.structure.template_uid), source=runtime_uid())
        for b in (replace(a, path=("registry", 1)),
                  record(P, plot(self.structure.template_uid), source=a.source_uid, scope="other")):
            result = self.convert(a, b)
            self.assertFalse(result.valid)
            self.assertTrue(any(i.code in ("LEGACY_IDENTITY", "LEGACY_UID_MAP") for i in result.issues))

    def test_composed_mapping_accepts_convergent_edges_rejects_cycles_and_conflicts(self):
        a, b, c, d = (runtime_uid() for _ in range(4))
        self.assertEqual(compose_template_uid_maps({a: b}, {b: c}, {a: c}), {a: c, b: c})
        for mappings in (({a: b}, {b: a}), ({a: b}, {a: d})):
            with self.assertRaises(ValueError):
                compose_template_uid_maps(*mappings)

    def test_explicit_null_structure_identity_is_not_filled(self):
        source = record(S, {"system_name": None, "display_name": "Geometry"}, shape=LegacyDomainShape.MODERN)
        result = self.convert(source)
        self.assertFalse(result.valid)
        self.assertIsNone(result.sources[0].body["system_name"])

    def test_invalid_explicit_name_map_does_not_fall_back_to_unique_name(self):
        result = self.convert(record(P, plot("geometry")), name_map={(S, "geometry"): None})
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "LEGACY_UID_MAP")

    def test_non_object_source_is_retained_with_diagnostic(self):
        source = record(P, plot(self.structure.template_uid))
        result = self.convert(replace(source, body=["edited", None]))
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "EXPECTED_OBJECT")
        self.assertEqual(result.sources[0].body, ["edited", None])


from test_library_packs_4b import _ServiceCase


class PureConverterBoundaryTests(_ServiceCase):
    async def test_conversion_has_no_sql_or_canonical_attach_side_effects(self):
        structure = member(S, "geometry")
        trace = []
        await self.db.main_conn.set_trace_callback(trace.append)
        try:
            result = split_legacy_domains((record(P, plot(structure.template_uid)),),
                                           available_members=(structure,))
        finally:
            await self.db.main_conn.set_trace_callback(None)
        self.assertTrue(result.valid)
        self.assertEqual(trace, [])
        self.assertFalse(await self.packs.list_all())
