"""P1 contract boundaries: authored intent, prepared data, policy and outcomes."""

from itertools import permutations
from math import inf, nan
import unittest

from pydantic import Field, TypeAdapter, ValidationError

from app.application.jsonValidation.resolve import (
    ResolveContext, UnresolvedModelError, report_issues, resolve_patch, resolve_result,
)
from app.application.jsonValidation.types import FieldPathError
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
from app.dataModel.placement import (
    CoastlinePlacementFact, PlacementBatch, PlacementBatchResult, PlacementCandidate,
    PlacementDependency, PlacementDiagnostic, PlacementFootprint, PlacementIdentity,
    PlacementIntent, PlacementIssueCode, PlacementOutcome, PlacementSeparation,
    PreparedPlacement, ResolvedPlacement, ResolvedWaterPlacement, UnresolvedPlacement,
)
from app.dataModel.placement.common import PlacementModel
from app.dataModel.registryKey import RegistryKey, registry_key_target
from app.dataModel.spatial.regionShape import BboxShape, CorridorShape
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


def intent_wire(uid="region-a", **updates):
    return {"identity": {"world_uid": "world-a", "source_uid": f"source-{uid}", "region_uid": uid},
            "mode": "absolute", "shape": None, "absolute_movement": "forbid",
            "dependencies": (), "permitted_overlaps": (), "separations": (), **updates}


def candidate(uid="candidate-a", x=0):
    return PlacementCandidate(candidate_uid=uid, preference=0,
                              footprint=PlacementFootprint(cells={(x, 0)}, z_min=None, z_max=None))


def prepared(uid="region-a", **updates):
    return PreparedPlacement(**{"intent": intent_wire(uid, placement_specificity=5),
                                "original_area": 1.0, "candidates": (candidate(),),
                                "auto_specificity": None, "coastline": None, **updates})


def failure(obj, code=PlacementIssueCode.NO_CANDIDATES):
    issue = PlacementDiagnostic(code=code, region_uid=obj.intent.identity.region_uid, detail="no solution")
    return UnresolvedPlacement(prepared=obj, diagnostics=(issue,))


class PlacementIntentContractTests(unittest.TestCase):
    def test_missing_null_auto_and_explicit_zero_keep_presence(self):
        absent = PlacementIntent.model_validate(intent_wire())
        explicit_null = PlacementIntent.model_validate(intent_wire(placement_specificity=None))
        explicit_zero = PlacementIntent.model_validate(intent_wire(placement_specificity=0))
        self.assertNotIn("placement_specificity", absent.model_fields_set)
        self.assertIn("placement_specificity", explicit_null.model_fields_set)
        self.assertIsNone(absent.placement_specificity)
        self.assertIsNone(explicit_null.placement_specificity)
        self.assertEqual(explicit_zero.placement_specificity, 0)
        self.assertIsNone(prepared(intent=absent).effective_specificity)
        self.assertEqual(prepared(intent=absent, auto_specificity=3).effective_specificity, 3)
        self.assertEqual(prepared(intent=explicit_zero, auto_specificity=3).effective_specificity, 0)

    def test_full_rejects_invalid_priority_instead_of_using_auto(self):
        for value in (-1, True, False, "7", 1.5, 2.0, {}, []):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                prepared(intent=intent_wire(placement_specificity=value), auto_specificity=4)
        self.assertEqual(PlacementIntent.model_validate(
            intent_wire(placement_specificity=2**80)).placement_specificity, 2**80)

    def test_required_fields_unknown_keys_and_null_collections(self):
        for key in ("identity", "mode", "shape", "dependencies", "permitted_overlaps", "separations"):
            data = intent_wire()
            data.pop(key)
            with self.subTest(key=key), self.assertRaises(ValidationError):
                PlacementIntent.model_validate(data)
        for key in ("identity", "mode", "absolute_movement", "dependencies", "permitted_overlaps", "separations"):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                PlacementIntent.model_validate(intent_wire(**{key: None}))
        for data in (intent_wire(mode="guess"), intent_wire(typo_priority=10)):
            with self.assertRaises(ValidationError):
                PlacementIntent.model_validate(data)

    def test_identity_is_strict_without_silent_normalization(self):
        for value in ("", " ", " x", "x ", "x\n", "\nx", 5, True, None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PlacementIdentity(world_uid="world", source_uid="source", region_uid=value)
        identity = PlacementIdentity(world_uid="world", source_uid="автор/1", region_uid="stable:1")
        self.assertEqual(identity.source_uid, "автор/1")

    def test_shared_shapes_roundtrip_and_invalid_copied_shape_is_revalidated(self):
        for shape in (BboxShape(x_min=0, y_min=0, x_max=3, y_max=4),
                      CorridorShape(path=[(0, 0), (3, 0)], width=2),
                      {"kind": "anchor_radius", "anchor_uid": "location-a", "radius": 5}):
            obj = PlacementIntent.model_validate(intent_wire(shape=shape))
            self.assertEqual(PlacementIntent.model_validate_json(obj.model_dump_json()), obj)
        invalid = BboxShape(x_min=0, y_min=0, x_max=3, y_max=4).model_copy(update={"x_max": -1})
        with self.assertRaises(ValidationError):
            PlacementIntent.model_validate(intent_wire(shape=invalid))

    def test_self_relations_duplicate_relations_and_negative_reserves_reject(self):
        for name, relation in (("dependencies", {"relation": "resolved"}),
                               ("permitted_overlaps", {"relation": "embedding"}),
                               ("separations", {"min_xy": 0, "min_z": 0})):
            for targets in (("region-a",), ("region-b", "region-b")):
                data = [{"target_uid": uid, **relation} for uid in targets]
                with self.subTest(name=name, targets=targets), self.assertRaises(ValidationError):
                    PlacementIntent.model_validate(intent_wire(**{name: data}))
        for value in (-1, True, "0"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PlacementSeparation(target_uid="other", min_xy=value, min_z=0)
        # Missing support is a domain unresolved case in P2, not malformed intent.
        obj = PlacementIntent.model_validate(intent_wire(dependencies=[
            {"target_uid": "not-yet-present", "relation": "supported_by"}]))
        self.assertIsInstance(obj.dependencies[0], PlacementDependency)


class PlacementPreparedContractTests(unittest.TestCase):
    def test_geometry_rejects_empty_fractional_or_reversed_bounds_without_repair(self):
        invalid = ({"cells": []}, {"cells": [(True, 0)]}, {"cells": [(0.5, 0)]},
                   {"cells": [(0, 0)], "z_min": 0},
                   {"cells": [(0, 0)], "z_min": 4, "z_max": 3},
                   {"cells": [(0, 0)], "z_min": None, "z_max": 3})
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                PlacementFootprint.model_validate({"z_min": None, "z_max": None, **data})
        self.assertEqual(PlacementFootprint(cells={(0, 0)}, z_min=2, z_max=2).z_min, 2)

    def test_original_area_is_required_positive_finite_and_independent_of_cells(self):
        for value in (0, -1, inf, nan, True, "1"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                prepared(original_area=value)
        data = prepared().model_dump()
        data.pop("original_area")
        with self.assertRaises(ValidationError):
            PreparedPlacement.model_validate(data)
        # Analytic source area is not rewritten to one sampled cell or a bbox.
        self.assertEqual(prepared(original_area=12.5).original_area, 12.5)

    def test_absolute_alternatives_require_explicit_policy_and_unique_ids(self):
        variants = (candidate("a"), candidate("b", 1))
        with self.assertRaises(ValidationError):
            prepared(candidates=variants)
        for fields in ({"mode": "semantic"}, {"absolute_movement": "explicit_candidates"}):
            obj = prepared(intent=intent_wire(placement_specificity=2, **fields), candidates=variants)
            self.assertEqual(len(obj.candidates), 2)
        with self.assertRaises(ValidationError):
            prepared(intent=intent_wire(mode="semantic"), candidates=(candidate(), candidate()))

    def test_coastline_precarve_fact_never_rewrites_authored_priority(self):
        for authored in (None, 0, 99):
            original = PlacementIntent.model_validate(intent_wire(placement_specificity=authored))
            for presence, expected in (("present", authored), ("absent", 0), ("unknown", None)):
                obj = prepared(intent=original, coastline=CoastlinePlacementFact(
                    snapshot_uid="snapshot-a", water_presence=presence, reason="pre-carve evidence"))
                with self.subTest(authored=authored, presence=presence):
                    self.assertEqual(obj.effective_specificity, expected)
                    self.assertEqual(obj.intent.placement_specificity, authored)
                    self.assertEqual(len(obj.candidates), 1)
        for data in ({"water_presence": None}, {"water_presence": "guessed"}, {"reason": " "}):
            with self.assertRaises(ValidationError):
                CoastlinePlacementFact.model_validate({"snapshot_uid": "s", "water_presence": "absent",
                                                       "reason": "no water", **data})

    def test_candidate_order_is_explicit_data_not_list_order(self):
        variants = (candidate("a"), candidate("b", 1))
        for ordering in permutations(variants):
            obj = prepared(intent=intent_wire(mode="semantic", placement_specificity=2), candidates=ordering)
            picked = ResolvedPlacement(prepared=obj, candidate_uid="b")
            self.assertEqual(picked.footprint.cells, frozenset({(1, 0)}))
            self.assertEqual(picked.original_area, 1.0)


class PlacementResultContractTests(unittest.TestCase):
    def test_resolved_rejects_unknown_candidate_and_unresolved_priority(self):
        for obj, uid in ((prepared(), "invented"),
                         (prepared(intent=intent_wire()), "candidate-a"),
                         (prepared(candidates=()), "candidate-a")):
            with self.subTest(uid=uid), self.assertRaises(ValidationError):
                ResolvedPlacement(prepared=obj, candidate_uid=uid)
        forged = prepared().model_copy(update={"auto_specificity": -1})
        with self.assertRaises(ValidationError):
            ResolvedPlacement(prepared=forged, candidate_uid="candidate-a")

    def test_unresolved_is_not_an_empty_result_and_cannot_carry_footprint(self):
        obj = prepared(candidates=())
        failed = failure(obj)
        with self.assertRaises(ValidationError):
            UnresolvedPlacement(prepared=obj, diagnostics=())
        with self.assertRaises(ValidationError):
            failure(obj, PlacementIssueCode.COASTLINE_PRIORITY_LOWERED)
        with self.assertRaises(ValidationError):
            UnresolvedPlacement.model_validate({**failed.model_dump(), "footprint": {"cells": [(0, 0)]}})
        self.assertFalse(hasattr(failed, "footprint"))
        adapter = TypeAdapter(PlacementOutcome)
        self.assertEqual(adapter.validate_json(adapter.dump_json(failed)), failed)
        good = ResolvedPlacement(prepared=prepared(), candidate_uid="candidate-a")
        from tests.test_placement_resolver import SNAPSHOT_REVISION
        mixed = PlacementBatchResult(world_uid="world-a", snapshot_uid="s", snapshot_revision=SNAPSHOT_REVISION,
                                     results=(good, failure(prepared(uid="other", candidates=()))))
        self.assertEqual(PlacementBatchResult.model_validate_json(mixed.model_dump_json()), mixed)
        self.assertEqual(PlacementBatchResult(world_uid="world-a", snapshot_uid="s",
            snapshot_revision=SNAPSHOT_REVISION, results=()).results, ())

    def test_water_record_reuses_material_key_and_requires_resolved_metadata(self):
        placement = ResolvedPlacement(prepared=prepared(), candidate_uid="candidate-a")
        record = ResolvedWaterPlacement(placement=placement, z_water_level=7, kind="sea", liquid="water")
        self.assertEqual(record.source_uid, placement.identity.source_uid)
        self.assertEqual(record.footprint_cells, placement.footprint.cells)
        self.assertIs(record.kind, BasinKind.SEA)
        self.assertIsInstance(record.liquid, RegistryKey)
        self.assertIs(registry_key_target(ResolvedWaterPlacement.model_fields["liquid"].annotation),
                      WorldMaterialRegistry)
        self.assertEqual(ResolvedWaterPlacement.model_validate_json(record.model_dump_json()), record)
        for key, value in (("kind", "river"), ("liquid", None), ("z_water_level", True)):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                ResolvedWaterPlacement.model_validate({**record.model_dump(), key: value})
        for key in ("liquid", "kind", "z_water_level"):
            data = record.model_dump()
            data.pop(key)
            with self.assertRaises(ValidationError):
                ResolvedWaterPlacement.model_validate(data)


class PlacementBatchContractTests(unittest.TestCase):
    def test_revision_required_strict_and_json_hex_round_trip(self):
        batch = self.batch()
        self.assertEqual(PlacementBatch.model_validate_json(batch.model_dump_json()), batch)
        wire = batch.model_dump()
        wire.pop("snapshot_revision")
        with self.assertRaises(ValidationError):
            PlacementBatch.model_validate(wire)
        for invalid in (None, b"short", "a" * 32, True):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                self.batch(snapshot_revision=invalid)

    def batch(self, **updates):
        from tests.test_placement_resolver import SNAPSHOT_REVISION
        return PlacementBatch(**{"world_uid": "world-a", "snapshot_uid": "snapshot-a", "phase": "pre_relief",
                                 "snapshot_revision": SNAPSHOT_REVISION,
                                 "topology": WorldTopology(bounds=WorldBounds(x_min=0, x_max=7,
                                                                              y_min=0, y_max=7)),
                                 "objects": (), "accepted": (), **updates})

    def test_late_pass_carries_prior_decisions_without_redeclaring_them(self):
        accepted = ResolvedPlacement(prepared=prepared(), candidate_uid="candidate-a")
        batch = self.batch(phase="dependent", accepted=(accepted,), objects=(prepared(uid="child"),))
        self.assertEqual(batch.accepted[0].candidate_uid, "candidate-a")
        self.assertEqual(PlacementBatch.model_validate_json(batch.model_dump_json()), batch)
        with self.assertRaises(ValidationError):
            batch.accepted[0].candidate_uid = "moved"
        for updates in ({"accepted": (accepted,)},
                        {"phase": "dependent", "accepted": (accepted,), "objects": (prepared(),)},
                        {"objects": (prepared(), prepared())},
                        {"objects": (prepared(intent=intent_wire(identity={"world_uid": "other",
                           "source_uid": "source", "region_uid": "region-a"})),)}):
            with self.subTest(updates=updates), self.assertRaises(ValidationError):
                self.batch(**updates)

    def test_coastline_fact_requires_matching_precarve_snapshot(self):
        obj = prepared(coastline={"snapshot_uid": "snapshot-a", "water_presence": "absent", "reason": "dry"})
        self.assertEqual(self.batch(objects=(obj,)).objects[0].effective_specificity, 0)
        with self.assertRaises(ValidationError):
            self.batch(objects=(obj,), snapshot_uid="different")
        with self.assertRaises(ValidationError):
            self.batch(objects=(obj,), phase="dependent")


class PlacementWirePolicyTests(unittest.TestCase):
    def test_declared_factory_is_used_once_by_existing_resolver(self):
        calls = []

        def schema_default():
            calls.append("called")
            return 8

        class WithFactory(PlacementModel):
            amount: DefaultWhenMissing[int] = Field(default_factory=schema_default, alias="wire_amount")

        ctx = ResolveContext.for_import(validate_only=True)
        missing = resolve_result(WithFactory, {}, ctx=ctx)
        self.assertEqual(missing.value.amount, 8)
        self.assertEqual(calls, ["called"])
        self.assertEqual(missing.issues, ())
        explicit = resolve_result(WithFactory, {"wire_amount": 0}, ctx=ResolveContext(validate_only=True))
        self.assertEqual(explicit.value.amount, 0)
        self.assertEqual(explicit.issues, ())
        self.assertEqual(calls, ["called"])

    def test_absolute_movement_default_is_forbid(self):
        raw = intent_wire(placement_specificity=0)
        raw.pop("absolute_movement")
        result = resolve_result(PlacementIntent, raw, ctx=ResolveContext(validate_only=True))
        self.assertTrue(result.resolved)
        self.assertEqual(result.value.absolute_movement, "forbid")
        self.assertEqual(result.issues, ())

    def test_missing_default_uses_existing_normalization_log_in_both_modes(self):
        wire = intent_wire()  # priority omitted; the declared default is None/auto.
        runtime = ResolveContext.for_import(validate_only=False).child("placements").child("region-a")
        master = ResolveContext.for_import(validate_only=True).child("placements").child("region-a")
        with self.assertLogs("app.application.jsonValidation.resolve", level="INFO") as logs:
            ordinary = resolve_result(PlacementIntent, wire, ctx=runtime)
        with self.assertLogs("app.application.jsonValidation.resolve", level="INFO") as preview_logs:
            preview = resolve_result(PlacementIntent, wire, ctx=master)
        self.assertTrue(ordinary.resolved)
        self.assertTrue(preview.resolved)
        self.assertEqual(ordinary.value, preview.value)
        self.assertIsNone(preview.value.placement_specificity)
        # Existing normalization logging owns applied defaults. Reports retain
        # their existing role for invalid inputs and domain diagnostics.
        self.assertEqual(ordinary.issues, ())
        self.assertEqual(runtime.errors, [])
        self.assertEqual(master.errors, [])
        self.assertEqual(preview.issues, ())
        for captured in (logs, preview_logs):
            self.assertIn("wire=", captured.output[0])
            self.assertIn("resolved=", captured.output[0])
            self.assertTrue(all(record.levelname == "INFO" for record in captured.records))
        self.assertEqual(master.validate_only, master.child("nested").validate_only)
        self.assertIs(master.report, master.child("nested").report)
        self.assertNotIn("placement_specificity", wire)  # no authored repair/write

    def test_explicit_null_and_value_are_preserved(self):
        for priority in (None, 0, 9):
            ctx = ResolveContext(validate_only=True)
            result = resolve_result(PlacementIntent, intent_wire(placement_specificity=priority), ctx=ctx)
            with self.subTest(priority=priority):
                self.assertTrue(result.resolved)
                self.assertEqual(result.value.placement_specificity, priority)
                self.assertEqual(ctx.report.issues, [])
                self.assertEqual(result.issues, ())

    def test_missing_required_prepared_data_is_not_silently_empty(self):
        models = ((PreparedPlacement, prepared().model_dump(), ("candidates", "auto_specificity", "coastline")),
                  (PlacementFootprint, candidate().footprint.model_dump(), ("cells", "z_min", "z_max")))
        for cls, complete, fields in models:
            for name in fields:
                data = {key: value for key, value in complete.items() if key != name}
                ctx = ResolveContext.for_import(validate_only=True)
                result = resolve_result(cls, data, ctx=ctx)
                with self.subTest(model=cls.__name__, field=name):
                    self.assertFalse(result.resolved)
                    self.assertTrue(any(issue.path == (name,) for issue in result.issues))

    def test_patch_keeps_missing_and_null_then_validates_complete_merge(self):
        ctx = ResolveContext(validate_only=True)
        base = intent_wire(placement_specificity=7)
        self.assertEqual(resolve_patch(PlacementIntent, {}, ctx=ctx), {})
        patch = resolve_patch(PlacementIntent, {"placement_specificity": None}, ctx=ctx)
        self.assertEqual(patch, {"placement_specificity": None})
        result = resolve_result(PlacementIntent, {**base, **patch}, ctx=ctx)
        self.assertTrue(result.resolved)
        self.assertIsNone(result.value.placement_specificity)
        for raw in ({"placement_specificity": True}, {"dependencies": None}, {"unexpected": 5}):
            with self.subTest(raw=raw), self.assertRaises(UnresolvedModelError):
                resolve_patch(PlacementIntent, raw, ctx=ctx)
        # Partial validity cannot bypass whole-object self-reference checks after merge.
        patch = resolve_patch(PlacementIntent, {"dependencies": [
            {"target_uid": "region-a", "relation": "resolved"}]}, ctx=ctx)
        self.assertFalse(resolve_result(PlacementIntent, {**base, **patch}, ctx=ctx).resolved)

    def test_runtime_preview_make_identical_wire_decisions_and_share_diagnostic_sink(self):
        payload = intent_wire(placement_specificity=-1)
        runtime = ResolveContext(path_prefix=("placements", "region-a"))
        preview = ResolveContext(validate_only=True, path_prefix=runtime.path_prefix)
        with self.assertLogs("app.application.jsonValidation.resolve", level="WARNING") as log:
            result_runtime = resolve_result(PlacementIntent, payload, ctx=runtime)
        with self.assertNoLogs("app.application.jsonValidation.resolve", level="WARNING"):
            result_preview = resolve_result(PlacementIntent, payload, ctx=preview)
        self.assertFalse(result_runtime.resolved)
        self.assertEqual(result_runtime.issues, result_preview.issues)
        self.assertIn("WarningError", " ".join(log.output))
        self.assertEqual(runtime.report.issues, preview.report.issues)
        self.assertEqual(result_runtime.issues[0].path, ("placements", "region-a", "placement_specificity"))
        # P2 will bridge the typed spatial facts through this existing API.
        diagnostic = failure(prepared()).diagnostics[0]
        issue = FieldPathError(path=preview.path_prefix, code=diagnostic.code.value, message=diagnostic.detail)
        report_issues(preview, (issue,))
        self.assertEqual(preview.report.issues[-1].code, "PLACEMENT_NO_CANDIDATES")


if __name__ == "__main__":
    unittest.main()
