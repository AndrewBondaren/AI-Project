"""B1: detached snapshots -> a deterministic migration plan, without I/O."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from app.application.worldData.libraryPacks.defaults import PLOTS_BASE_SYSTEM_NAME
from app.application.worldData.libraryPacks.legacyDomainContracts import LegacyDomainShape
from app.application.worldData.libraryPacks.legacyWorldContracts import LegacyPackRoute, LegacyWorldFacts
from app.application.worldData.libraryPacks.legacyWorldInput import extract_legacy_world_input
from app.application.worldData.libraryPacks.legacyWorldPlan import plan_legacy_world_migration
from app.application.worldData.libraryPacks.legacyWorldProjection import project_pack
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportMember, WriteImportSource
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, library_uid, runtime_uid

S, B, P, R = (LibraryKind.STRUCTURE_TEMPLATES, LibraryKind.BUILDING_TEMPLATES,
              LibraryKind.PLOT_TEMPLATES, LibraryKind.RELIEF_TEMPLATES)


def graph(name="engine.user", owner=None):
    uid = library_uid(LibraryKind.LIBRARY_PACKS, name)
    pack = LibraryPackRow(uid, name, "test", name, owner_world_uid=owner)
    rows = [LibraryPackMemberRow(library_uid(k, "same", pack_uid=uid), uid, k.value, "same") for k in (S, B, P)]
    s, b, p = rows
    bodies = ({"system_name": s.template_uid, "display_name": "Structure"},
              {"system_name": "same", "display_name": "Building", "structure": s.template_uid},
              {"system_name": "same", "display_name": "Plot", "main_building": {
                  "structure": s.template_uid, "roof_material": None}, "secondary_buildings": [
                      {"structure": s.template_uid, "foundation_depth": 0, "porch_has_roof": False}]})
    return WriteImportSource(pack, tuple(WriteImportMember(m, body) for m, body in zip(rows, bodies)))


def world(*uids, rows=(), **fields):
    return {"world_uid": "w1", "building_template_registry": [
        {"system_template_uid": u, "display_template_name": "obsolete", "imported_at": "yesterday"}
        for u in uids] + list(rows), **fields}


def plan(raw, *packs, sections=None, aliases=(), shapes=()):
    return plan_legacy_world_migration(extract_legacy_world_input(raw, sections),
        LegacyWorldFacts(tuple(packs), tuple(aliases), tuple(shapes)))


def instance(source, *, edited=False):
    pack, rows = project_pack(source, LegacyPackRoute.INSTANCE, "w1")
    mapping = {u: m.template_uid for u, m in rows.items()}
    members = []
    for entry in source.members:
        body = deepcopy(entry.body)
        if entry.member.library_kind == S.value:
            body["system_name"] = mapping[entry.member.template_uid]
        if "structure" in body:
            body["structure"] = mapping[body["structure"]]
        for inline in ([body["main_building"]] if body.get("main_building") else []) + body.get("secondary_buildings", []):
            inline["structure"] = mapping[inline["structure"]]
        if edited:
            body["display_name"] = "Owned edit"
        members.append(WriteImportMember(rows[entry.member.template_uid], body))
    return WriteImportSource(pack, tuple(members))


class LegacyWorldMigrationTests(unittest.TestCase):
    def setUp(self):
        self.source = graph()
        self.s, self.b, self.p = self.source.members

    def valid(self, value):
        self.assertTrue(value.valid, value.issues)
        return value

    def test_default_pointer_is_pin_without_copy(self):
        default = graph(PLOTS_BASE_SYSTEM_NAME)
        result = self.valid(plan(world(default.members[2].member.template_uid), default))
        self.assertEqual(result.packs, ())
        self.assertEqual(result.uid_map, ())
        self.assertEqual(result.pointers[0].route, "default")
        self.assertEqual(result.pins[0].library_kind, P.value)

    def test_owned_pointer_keeps_identity_and_body(self):
        owned = graph("owned", "w1")
        result = self.valid(plan(world(owned.members[1].member.template_uid), owned))
        self.assertEqual(result.pointers[0].route, "owned")
        self.assertEqual(result.pins[0].template_uid, owned.members[1].member.template_uid)
        self.assertEqual(result.packs[0].route, LegacyPackRoute.REUSE)

    def test_engine_pointer_expands_once_and_remaps_entire_graph(self):
        raw = world(self.p.member.template_uid, self.b.member.template_uid)
        before = deepcopy((raw, self.source))
        with patch("sqlite3.connect", side_effect=AssertionError("planner must not access SQL")):
            result = self.valid(plan(raw, self.source))
        self.assertEqual((raw, self.source), before)
        self.assertEqual(len(result.packs), 1)
        action, = result.packs
        self.assertEqual(action.route, LegacyPackRoute.INSTANCE)
        self.assertEqual(len(action.members), 3)
        mapping = dict(result.uid_map)
        bodies = result.catalog.bodies
        self.assertEqual(bodies[mapping[self.b.member.template_uid]]["structure"], mapping[self.s.member.template_uid])
        self.assertEqual(bodies[mapping[self.s.member.template_uid]]["system_name"], mapping[self.s.member.template_uid])
        p = bodies[mapping[self.p.member.template_uid]]
        self.assertIsNone(p["main_building"]["roof_material"])
        self.assertEqual(p["secondary_buildings"][0]["foundation_depth"], 0)
        self.assertFalse(p["secondary_buildings"][0]["porch_has_roof"])
        self.assertTrue(any(i.code == "LIBRARY_EXPANSION" for i in result.diagnostics))
        self.assertEqual(result.projected_world["building_template_registry"], raw["building_template_registry"])
        self.assertEqual(result, plan(raw, self.source))

    def test_existing_instance_reuses_provenance_and_preserves_edits(self):
        owned = instance(self.source, edited=True)
        # Provenance is authoritative even when the instance UID/name is different.
        owned_uid = runtime_uid()
        owned = replace(owned, pack=replace(owned.pack, pack_uid=owned_uid, system_name="custom.instance"),
            members=tuple(replace(e, member=replace(e.member, pack_uid=owned_uid)) for e in owned.members))
        result = self.valid(plan(world(self.b.member.template_uid), self.source, owned))
        action, = result.packs
        self.assertEqual(action.target_pack.pack_uid, owned_uid)
        self.assertEqual(action.route, LegacyPackRoute.REUSE)
        self.assertTrue(all(e.body["display_name"] == "Owned edit" for e in action.members))
        self.assertEqual(result.pins[0].template_uid, owned.members[1].member.template_uid)

    def test_incomplete_instance_does_not_refresh_or_create_missing_member(self):
        owned = instance(self.source)
        owned = replace(owned, members=owned.members[:1])
        result = self.valid(plan(world(self.b.member.template_uid), self.source, owned))
        self.assertEqual(result.pins, ())
        self.assertEqual(len(result.packs[0].members), 1)
        self.assertTrue(result.diagnostics)

    def test_multiple_instances_are_blocking_and_preserve_original(self):
        owned = instance(self.source)
        other = replace(owned, pack=replace(owned.pack, pack_uid=runtime_uid()),
                        members=())
        raw = world(self.b.member.template_uid)
        result = plan(raw, self.source, owned, other)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "LEGACY_PROVENANCE")
        self.assertEqual(result.projected_world, raw)
        self.assertEqual(result.packs, ())

    def test_unknown_foreign_and_wrong_kind_pointers_have_no_pin(self):
        foreign = graph("foreign", "w2")
        result = self.valid(plan(world(runtime_uid(), self.s.member.template_uid,
            foreign.members[1].member.template_uid), self.source, foreign))
        self.assertEqual(result.pins, ())
        self.assertEqual(result.packs, ())
        self.assertEqual(len(result.diagnostics), 3)

    def test_identical_raw_body_compares_after_defaults_and_remap(self):
        raw = world(self.p.member.template_uid, rows=[deepcopy(self.p.body)])
        result = self.valid(plan(raw, self.source))
        self.assertEqual(result.comparisons[0].changes, ())
        self.assertEqual(result.packs[0].route, LegacyPackRoute.INSTANCE)

    def test_edited_raw_body_moves_full_pack_to_legacy_without_losing_other_bodies(self):
        raw = world(self.p.member.template_uid, self.b.member.template_uid)
        raw["building_template_registry"][0]["body"] = {**self.p.body, "display_name": "World edit"}
        result = self.valid(plan(raw, self.source))
        action, = result.packs
        self.assertEqual(action.route, LegacyPackRoute.LEGACY)
        self.assertEqual(action.source_pack_uids, (self.source.pack.pack_uid,))
        self.assertEqual(len(action.members), 3)
        mapping = dict(result.uid_map)
        self.assertEqual(result.catalog.bodies[mapping[self.p.member.template_uid]]["display_name"], "World edit")
        self.assertEqual(result.catalog.bodies[mapping[self.b.member.template_uid]]["display_name"], "Building")
        self.assertTrue(result.comparisons[0].changes)
        self.assertTrue(all(p.template_uid in mapping.values() for p in result.pins))

    def test_duplicate_local_names_from_distinct_sources_are_preserved(self):
        other = graph("engine.other")
        raw = world(self.p.member.template_uid, other.members[2].member.template_uid)
        for row, source in zip(raw["building_template_registry"], (self.source, other)):
            row["body"] = {**source.members[2].body, "display_name": "Edited"}
        result = self.valid(plan(raw, self.source, other))
        action, = result.packs
        self.assertEqual(len(action.members), 6)
        self.assertEqual(len({e.member.template_uid for e in action.members}), 6)
        self.assertEqual({e.member.local_uid for e in action.members}, {"same"})

    def test_unqualified_body_name_is_ambiguous_among_pointers(self):
        other = graph("engine.other")
        result = plan(world(self.p.member.template_uid, other.members[2].member.template_uid,
            rows=[self.p.body]), self.source, other)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "LEGACY_REF_AMBIGUOUS")
        self.assertIn("candidates=", result.issues[0].message)

    def test_authored_plot_preserves_inline_composition_without_synthetic_buildings(self):
        default = graph(PLOTS_BASE_SYSTEM_NAME)
        raw = deepcopy(default.members[2].body)
        raw["system_name"] = "authored"
        result = self.valid(plan(world(rows=[raw]), default))
        action, = result.packs
        self.assertEqual(len(action.members), 1)
        self.assertEqual(action.members[0].member.library_kind, P.value)
        self.assertEqual(action.members[0].body["main_building"]["structure"], default.members[0].member.template_uid)
        self.assertEqual(result.pins, ())
        self.assertEqual(action.dependencies, (default.pack.pack_uid,))

    def test_unknown_pointer_with_explicit_body_is_rescued_into_legacy(self):
        uid = runtime_uid()
        raw = world(uid)
        raw["building_template_registry"][0]["body"] = {"system_name": "vacant", "display_name": "Vacant", "main_building": None}
        result = self.valid(plan(raw))
        self.assertEqual(result.packs[0].route, LegacyPackRoute.LEGACY)
        self.assertEqual(result.pointers[0].route, "legacy")
        self.assertEqual(result.pins[0].template_uid, dict(result.uid_map)[uid])

    def test_alias_composition_reaches_final_instance(self):
        old, intermediate = runtime_uid(), runtime_uid()
        result = self.valid(plan(world(old), self.source,
            aliases=((old, intermediate), (intermediate, self.p.member.template_uid))))
        mapping = dict(result.uid_map)
        self.assertEqual(mapping[old], mapping[self.p.member.template_uid])
        self.assertEqual(mapping[intermediate], mapping[old])

    def test_conflicting_aliases_do_not_silently_pick_last(self):
        old = runtime_uid()
        result = plan(world(old), self.source,
            aliases=((old, self.b.member.template_uid), (old, self.p.member.template_uid)))
        self.assertFalse(result.valid)

    def test_repeated_instance_plan_has_same_pins_and_no_new_instance(self):
        raw = world(self.p.member.template_uid)
        first = self.valid(plan(raw, self.source))
        action, = first.packs
        persisted = WriteImportSource(action.target_pack, action.members, action.dependencies)
        second = self.valid(plan(raw, self.source, persisted))
        self.assertEqual(first.pins, second.pins)
        self.assertEqual(second.packs[0].route, LegacyPackRoute.REUSE)
        self.assertEqual(len(second.packs), 1)

    def test_missing_dependency_is_diagnostic_without_implicit_instantiation(self):
        missing = runtime_uid()
        source = replace(self.source, dependencies=(missing,))
        result = self.valid(plan(world(self.p.member.template_uid), source))
        self.assertEqual(len(result.packs), 1)
        self.assertEqual(result.packs[0].dependencies, (missing,))
        self.assertTrue(any(i.code == "LIBRARY_DEPENDENCY" for i in result.diagnostics))

    def test_malformed_raw_rows_fail_without_actions_and_keep_raw_input(self):
        for fields in ({"building_template_registry": {}},
                       {"building_template_registry": [None]},
                       {"building_template_registry": [{"system_template_uid": None}]},
                       {"library_pins": {}}, {"library_pins": [{"library_kind": B.value, "template_uid": "bad"}]}):
            with self.subTest(fields=fields):
                raw = {"world_uid": "w1", **fields}
                result = plan(raw)
                self.assertFalse(result.valid)
                self.assertEqual(result.packs, ())
                self.assertEqual(result.projected_world, raw)

    def test_empty_input_retains_unrelated_world_fields(self):
        raw = {"world_uid": "w1", "authored_extension": {"x": False}}
        result = self.valid(plan(raw))
        self.assertEqual(result.projected_world, {**raw, "library_pins": []})
        self.assertEqual(result.packs, ())

    def test_legacy_mixed_building_member_splits_to_plot_with_explicit_shape(self):
        old = replace(self.p, member=replace(self.p.member, library_kind=B.value))
        source = replace(self.source, members=(self.s, old))
        result = self.valid(plan(world(old.member.template_uid), source,
            shapes=((old.member.template_uid, LegacyDomainShape.PLOT),)))
        self.assertEqual(result.pins[0].library_kind, P.value)
        self.assertEqual({e.member.library_kind for e in result.packs[0].members}, {S.value, P.value})

    def test_authored_cross_body_refs_and_structure_identity_are_remapped_together(self):
        s_uid, p_uid = runtime_uid(), runtime_uid()
        sections = {S.value: [{"system_name": s_uid, "local_uid": "geometry", "display_name": "Authored"}],
            P.value: [{"system_name": "plot", "template_uid": p_uid, "display_name": "Authored plot",
                       "main_building": {"structure": s_uid}}]}
        result = self.valid(plan(world(p_uid), sections=sections))
        mapping = dict(result.uid_map)
        self.assertEqual(result.catalog.bodies[mapping[s_uid]]["system_name"], mapping[s_uid])
        self.assertEqual(result.catalog.bodies[mapping[p_uid]]["main_building"]["structure"], mapping[s_uid])
        self.assertEqual(len(result.packs[0].members), 2)

    def test_edited_reused_instance_keeps_other_owned_edits_in_legacy_projection(self):
        owned = instance(self.source, edited=True)
        raw = world(self.p.member.template_uid)
        raw["building_template_registry"][0]["body"] = {**self.p.body, "display_name": "Raw edit"}
        result = self.valid(plan(raw, self.source, owned))
        legacy = next(a for a in result.packs if a.route == LegacyPackRoute.LEGACY)
        by_kind = {e.member.library_kind: e for e in legacy.members}
        self.assertEqual(by_kind[B.value].body["display_name"], "Owned edit")
        self.assertEqual(by_kind[P.value].body["display_name"], "Raw edit")
        self.assertEqual(by_kind[B.value].body["structure"], by_kind[S.value].member.template_uid)

    def test_modern_extensions_are_retained_including_nested_structure_data(self):
        s = replace(self.s, body={**self.s.body, "custom": {"x": False}})
        p = replace(self.p, body={**self.p.body, "custom": [0, None], "main_building": {
            **self.p.body["main_building"], "custom": 17}})
        source = replace(self.source, members=(s, self.b, p))
        result = self.valid(plan(world(p.member.template_uid), source))
        mapping = dict(result.uid_map)
        self.assertEqual(result.catalog.bodies[mapping[s.member.template_uid]]["custom"], {"x": False})
        self.assertEqual(result.catalog.bodies[mapping[p.member.template_uid]]["main_building"]["custom"], 17)

    def test_unrepresentable_legacy_fields_block_instead_of_disappearing(self):
        raw = world(rows=[{"system_name": "plot", "display_name": "Plot", "main_building": None,
                           "edited_geometry": {"x": 1}}])
        result = plan(raw)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "LEGACY_FIELD_UNREPRESENTABLE")
        self.assertEqual(result.original.raw_world, raw)

    def test_relief_pointer_policy_and_existing_pin_remap_share_one_uid_map(self):
        pack_uid = library_uid(LibraryKind.LIBRARY_PACKS, "engine.relief")
        uid = library_uid(R, "land", pack_uid=pack_uid)
        source = WriteImportSource(LibraryPackRow(pack_uid, "engine.relief", "relief", "Relief"), (
            WriteImportMember(LibraryPackMemberRow(uid, pack_uid, R.value, "land"),
                {"system_name": "land", "display_name": "Land", "context": "open_land"}),))
        old = runtime_uid()
        raw = {"world_uid": "w1", "relief_template_registry": [{"system_template_uid": old, "context": "obsolete"}],
               "relief_pick_policy": {"open_land": {"mode": "fixed", "default_template_uid": old, "custom": 7}},
               "library_pins": [{"library_kind": R.value, "template_uid": old}]}
        result = self.valid(plan(raw, source, aliases=((old, uid),)))
        target = dict(result.uid_map)[old]
        self.assertEqual(len(result.pins), 1)
        self.assertEqual(result.pins[0].template_uid, target)
        self.assertEqual(result.projected_world["relief_pick_policy"]["open_land"]["default_template_uid"], target)
        self.assertEqual(result.projected_world["relief_pick_policy"]["open_land"]["custom"], 7)
        self.assertEqual(result.packs[0].members[0].body["context"], "open_land")

    def test_repeated_legacy_plan_keeps_same_members_and_pins(self):
        raw = world(self.p.member.template_uid)
        raw["building_template_registry"][0]["body"] = {**self.p.body, "display_name": "Edit"}
        first = self.valid(plan(raw, self.source))
        action, = first.packs
        persisted = WriteImportSource(action.target_pack, action.members, action.dependencies)
        second = self.valid(plan(raw, self.source, persisted))
        self.assertEqual(first.pins, second.pins)
        self.assertEqual(first.packs[0].members, second.packs[0].members)

    def test_pointer_diagnostics_use_shared_reference_reasons(self):
        foreign = graph("foreign", "w2")
        result = self.valid(plan(world(runtime_uid(), self.s.member.template_uid,
            foreign.members[1].member.template_uid), self.source, foreign))
        self.assertEqual([i.reference.reason.value for i in result.diagnostics],
            ["unknown_template", "library_kind_mismatch", "owner_pack_unavailable"])

    def test_invalid_member_provenance_blocks_even_for_relief(self):
        broken = replace(self.b, member=replace(self.b.member, creation_kind="pack_copy"))
        source = replace(self.source, members=(self.s, broken, self.p))
        result = plan(world(self.b.member.template_uid), source)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "LEGACY_PROVENANCE")

    def test_duplicate_pack_copy_provenance_is_not_resolved_by_order(self):
        owned = instance(self.source)
        duplicate = replace(owned.members[1], member=replace(owned.members[1].member, template_uid=runtime_uid()))
        owned = replace(owned, members=(*owned.members, duplicate))
        result = plan(world(self.b.member.template_uid), self.source, owned)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "LEGACY_PROVENANCE")

    def test_source_body_missing_fails_with_path_without_partial_copy(self):
        source = replace(self.source, members=(self.s, replace(self.b, body=None), self.p))
        result = plan(world(self.b.member.template_uid), source)
        self.assertFalse(result.valid)
        self.assertEqual(result.packs, ())
        self.assertIn(self.b.member.template_uid, result.issues[0].path)

    def test_malformed_world_policy_is_blocking_and_unknown_policy_ref_is_diagnostic(self):
        result = plan(world(relief_pick_policy={"open_land": {"mode": "fixed"}}))
        self.assertFalse(result.valid)
        result = self.valid(plan(world(relief_pick_policy={"open_land": {
            "mode": "fixed", "default_template_uid": runtime_uid()}})))
        self.assertEqual(result.diagnostics[0].reference.reason.value, "unknown_template")

    def test_explicit_structure_alias_resolves_before_model_a_identity_check(self):
        old = runtime_uid()
        raw_structure = {**self.s.body, "system_name": old, "description": "Edited structure"}
        result = self.valid(plan(world(), self.source,
            sections={S.value: [raw_structure]}, aliases=((old, self.s.member.template_uid),)))
        row = next(e for e in result.packs[0].members if e.member.library_kind == S.value)
        self.assertEqual(row.body["system_name"], row.member.template_uid)
        self.assertEqual(row.body["description"], "Edited structure")

    def test_identical_body_of_reused_instance_does_not_make_legacy_duplicate(self):
        owned = instance(self.source, edited=True)
        raw = world(self.p.member.template_uid)
        raw["building_template_registry"][0]["body"] = owned.members[2].body
        result = self.valid(plan(raw, self.source, owned))
        self.assertFalse(result.comparisons[0].changes)
        self.assertEqual(result.packs[0].route, LegacyPackRoute.REUSE)

    def test_edited_default_is_copied_and_canonical_bodies_remain_unchanged(self):
        default = graph(PLOTS_BASE_SYSTEM_NAME)
        p = default.members[2]
        raw = world(p.member.template_uid)
        raw["building_template_registry"][0]["body"] = {**p.body, "display_name": "Edited"}
        result = self.valid(plan(raw, default))
        self.assertEqual(result.catalog.bodies[p.member.template_uid]["display_name"], "Plot")
        self.assertEqual(result.catalog.bodies[result.pins[0].template_uid]["display_name"], "Edited")
        self.assertEqual(result.packs[0].route, LegacyPackRoute.LEGACY)

    def test_legacy_name_resolves_before_virtual_instance_rows_are_added(self):
        source = replace(self.source, members=(self.s, self.p))
        raw = world(self.p.member.template_uid, rows=[{**self.p.body,
            "main_building": {"structure": "same"}}])
        result = self.valid(plan(raw, source))
        self.assertEqual(result.packs[0].route, LegacyPackRoute.INSTANCE)
        self.assertEqual(result.catalog.bodies[result.pins[0].template_uid]["main_building"]["structure"],
            dict(result.uid_map)[self.s.member.template_uid])

    def test_edited_owned_body_does_not_remove_the_original_owned_library(self):
        owned = graph("owned", "w1")
        p = owned.members[2]
        raw = world(p.member.template_uid)
        raw["building_template_registry"][0]["body"] = {**p.body, "display_name": "Raw override"}
        result = self.valid(plan(raw, owned))
        self.assertIn(p.member.template_uid, result.catalog.members)
        self.assertNotEqual(result.pins[0].template_uid, p.member.template_uid)
        self.assertEqual(result.catalog.bodies[p.member.template_uid]["display_name"], "Plot")
        self.assertEqual(len(result.packs), 2)


if __name__ == "__main__":
    unittest.main()
