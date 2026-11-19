"""Public pure assembly, checked paths and exact construction binding."""

import unittest
from unittest.mock import patch
from pydantic import Field, ValidationError

from app.application.patch.assembly.patchSetAssembler import PatchSetAssembler
from app.application.patch.assembly.patchSetAssemblyValidator import PatchSetAssemblyValidator
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import ModelIdentity, VariantSegment
from app.dataModel.patch.request.assembly import PatchSetAssemblyInput
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.request.patchSetData import PatchSetData
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.validation.invariantDetails import PatchSetInvariantCode as Code
from app.dataModel.patch.validation.patchSetInvariants import PatchSetInvariants
from tests.snapshotCore.support.fakeSection import (
    HeaderOnlyPatch, FakePatch, FakeTarget, FakeChange, FakePrepared,
)
from tests.snapshotCore.contracts.test_patch_invariants import section, values


class NativeSection(DomainSection[HeaderOnlyPatch | FakePatch]):
    pass


class OtherSection(NativeSection):
    pass


class AssemblyInput(PatchSetAssemblyInput[NativeSection | OtherSection]):
    pass


class AssemblyResult(PatchSet[NativeSection | OtherSection]):
    pass


class SiblingInput(AssemblyInput):
    pass


class OtherResult(PatchSet[OtherSection]):
    pass


def native(key="x", refs=None, dependencies=(), model=NativeSection):
    data = section(key, refs, dependencies)
    return model(header=data.header, patches=data.patches)


class PatchAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.assembler = PatchSetAssembler(AssemblyInput, AssemblyResult)

    def test_success_preserves_order_and_payload_without_handler(self):
        source = native("z")
        payload = FakePatch(header=source.patches[0].header, target=FakeTarget(name="t"),
                            change=FakeChange(amount=3), prepared=FakePrepared(values=(4, 2)))
        source = NativeSection(header=source.header, patches=(payload,))
        request = AssemblyInput(**values((source, native("a", model=OtherSection))))
        before = request.model_dump_json()
        with patch("tests.snapshotCore.support.fakeSection.FakeSectionHandler.apply",
                   side_effect=AssertionError("assembly must not apply")):
            result = self.assembler.assemble(request)
        self.assertIs(type(result), AssemblyResult)
        self.assertEqual(result.sections, request.sections)
        self.assertIs(type(result.sections[0].patches[0]), FakePatch)
        self.assertEqual(request.model_dump_json(), before)
        self.assertIs(type(self.assembler.assemble(AssemblyInput(**values()))), AssemblyResult)

    def test_all_independent_diagnostics_and_checked_union_paths(self):
        request = AssemblyInput(**values((
            native("x", refs=(("A", "x", 0), ("B", "x", 0)), dependencies=("y", "missing")),
            native("y", model=OtherSection),
        )))
        with patch.object(PatchSetInvariants, "check_core", wraps=PatchSetInvariants.check_core) as core:
            result = self.assembler.assemble(request)
            self.assertEqual(core.call_count, 1)  # No partial result construction on refusal.
        self.assertIsInstance(result, PatchSetAssemblyRefused)
        issues = result.diagnostics
        self.assertEqual([issue.details.code for issue in issues], [
            Code.PATCH_OPERATION_MISMATCH, Code.PATCH_OPERATION_MISMATCH, Code.DUPLICATE_PATCH_ORDINAL,
            Code.PREPARED_DEPENDENCY_ORDER, Code.MISSING_PREPARED_DEPENDENCY])
        self.assertEqual(issues[2].path.projection(), ("sections", 0, "patches", 1, "header", "ref", "ordinal"))
        self.assertEqual(issues[2].related_path.projection(), ("sections", 0, "patches", 0, "header", "ref", "ordinal"))
        self.assertEqual(issues[3].path.projection(), ("sections", 0, "header", "depends_on", 0, "section_key"))
        self.assertEqual(issues[3].related_path.projection(), ("sections", 1, "header", "key"))
        for issue in issues:
            self.assertEqual(issue.path.root, ModelIdentity.of(AssemblyInput))
            self.assertTrue(any(isinstance(segment, VariantSegment) for segment in issue.path.segments))
        self.assertEqual(issues[0].details.expected_operation_id, "op")
        with self.assertRaises(ValidationError):
            AssemblyResult(**values(request.sections))
        self.assertIs(type(self.assembler.assemble(AssemblyInput(**values()))), AssemblyResult)

    def test_structural_failures_do_not_invoke_relation_validator(self):
        valid = AssemblyInput(**values())
        malformed = valid.model_copy(update={"turn_id": True})
        with patch.object(PatchSetAssemblyValidator, "validate", side_effect=AssertionError("not admitted")):
            for wrong in (SiblingInput(**values()), PatchSetData(**values()), {}, AssemblyResult(**values())):
                with self.assertRaises(TypeError):
                    self.assembler.assemble(wrong)
            with self.assertRaises(ValidationError):
                self.assembler.assemble(malformed)
            with self.assertRaises(ValidationError):
                AssemblyInput(**values(), unknown=True)

    def test_construction_rejects_wrong_binding_and_unbound_models(self):
        for input_model, output_model in (
            (AssemblyInput, OtherResult), (PatchSetAssemblyInput, PatchSet),
            (PatchSetAssemblyInput[NativeSection], PatchSet[NativeSection]),
            (PatchSetData, AssemblyResult), (AssemblyResult, AssemblyResult),
        ):
            with self.assertRaises((ValueError, TypeError)):
                PatchSetAssembler(input_model, output_model)

    def test_construction_retains_section_minimum(self):
        class EmptySection(DomainSection[HeaderOnlyPatch]):
            patches: tuple[HeaderOnlyPatch, ...]

        class ZeroMinimumSection(DomainSection[HeaderOnlyPatch]):
            patches: tuple[HeaderOnlyPatch, ...] = Field(min_length=0)

        class StrongerSection(DomainSection[HeaderOnlyPatch]):
            patches: tuple[HeaderOnlyPatch, ...] = Field(min_length=2)

        for section_model in (EmptySection, ZeroMinimumSection, StrongerSection):
            class Input(PatchSetAssemblyInput[section_model]):
                pass

            class Result(PatchSet[section_model]):
                pass

            with self.subTest(section=section_model.__name__):
                if section_model is not StrongerSection:
                    empty = section_model(header=section("x").header, patches=())
                    request = Input(**values((empty,)))
                    self.assertEqual(request.sections[0].patches, ())
                    with self.assertRaisesRegex(TypeError, "section field constraints"):
                        PatchSetAssembler(Input, Result)
                else:
                    assembler = PatchSetAssembler(Input, Result)
                    data = section("x", refs=(("op", "x", 0), ("op", "x", 1)))
                    valid = section_model(header=data.header, patches=data.patches)
                    self.assertIs(type(assembler.assemble(Input(**values((valid,))))), Result)

    def test_world_player_section_and_patch_key_paths(self):
        from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef, PlayerHeadExpectation
        data = values((native("x", refs=(("op", "wrong", 0),)), native("x", model=OtherSection)))
        data["world_uid"] = "wrong"
        data["expected_world"] = WorldPublicationRef(world_uid="world", publication_id="p", pack_hash=None,
            snapshot_head=None, active_timeline_id=None, gameplay_started=False)
        player = PlayerHeadExpectation(player_uid="p", expected_head=None)
        data["expected_players"] = (player, player)
        request = AssemblyInput(**data)
        result = self.assembler.assemble(request)
        self.assertIsInstance(result, PatchSetAssemblyRefused)
        self.assertEqual([issue.path.projection() for issue in result.diagnostics], [
            ("expected_world", "world_uid"), ("expected_world", "pack_hash"),
            ("expected_players", 1, "player_uid"), ("sections", 1, "header", "key"),
            ("sections", 0, "patches", 0, "header", "ref", "section_key")])
        facts = PatchSetInvariants.check_core(request)
        self.assertEqual(tuple(issue.details for issue in result.diagnostics), tuple(f.details for f in facts))
        with self.assertRaises(ValidationError):
            PatchSetAssemblyRefused(diagnostics=())

    def test_parent_selector_cannot_be_used_as_concrete_root(self):
        with self.assertRaises((ValueError, TypeError)):
            CheckedPath.root(AssemblyInput).field(
                FieldRef(lambda: PatchSetData, lambda value: value.world_uid)).freeze()

    def test_payload_union_path_and_collector_admission(self):
        from app.dataModel.patch.results.assemblyIssues import PatchSetAssemblyRelationIssue
        from app.dataModel.validation.diagnostics.validatorAggregationHelper import (
            ValidatorAggregationHelper, IssueAdmissionError,
        )
        source = native(refs=(("wrong", "x", 0),))
        payload = FakePatch(header=source.patches[0].header, target=FakeTarget(name="t"),
                            change=FakeChange(amount=3), prepared=FakePrepared(values=(4, 2)))
        request = AssemblyInput(**values((NativeSection(header=source.header, patches=(payload,)),)))
        refusal = self.assembler.assemble(request)
        issue = refusal.diagnostics[0]
        branches = [s.branch for s in issue.path.segments if isinstance(s, VariantSegment)]
        self.assertEqual(branches, [ModelIdentity.of(NativeSection), ModelIdentity.of(FakePatch)])
        errors = ValidatorAggregationHelper((PatchSetAssemblyRelationIssue,))
        with self.assertRaises(IssueAdmissionError):
            errors.add(PatchSetInvariants.check_core(request)[0])
        errors.add(issue)
        self.assertEqual(errors.snapshot(), (issue,))


if __name__ == "__main__":
    unittest.main()
