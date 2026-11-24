"""Build coverage from ready subject sections; no IO or fingerprint computation."""
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.lifecycle.results.errors import LifecycleSectionRefused
from app.dataModel.lifecycle.results.issues import LifecycleRelationIssue, LifecycleRelationCode as Code
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from tests.lifecycle.support.domainSections import (BuildMockEvidenceA, BuildMockEvidenceB,
    MockEffectLinkA, MockEffectLinkB, TestDomainSectionA, TestDomainSectionB, TestDomainPatchA, TestDomainPatchB)
from tests.lifecycle.support.mixedContracts import CoverageA, CoverageB


def _issues(request: BuildMockEvidenceA | BuildMockEvidenceB) -> tuple[LifecycleRelationIssue, ...]:
    errors = ValidatorAggregationHelper[LifecycleRelationIssue]((LifecycleRelationIssue,))
    root = CheckedPath.root(type(request))
    dependency = root.field(FieldRef(lambda: type(request), lambda r: r.dependency))
    section = root.field(FieldRef(lambda: type(request), lambda r: r.section))
    links = root.field(FieldRef[BuildMockEvidenceA | BuildMockEvidenceB, tuple[MockEffectLinkA | MockEffectLinkB, ...]](
        lambda: type(request), lambda r: r.links))
    patches = section.field(FieldRef[TestDomainSectionA | TestDomainSectionB, tuple[TestDomainPatchA | TestDomainPatchB, ...]](
        lambda: type(request.section), lambda s: s.patches))
    if request.dependency.section_key != request.section.header.key:
        errors.add(LifecycleRelationIssue(code=Code.PATCH_SECTION_MISMATCH,
            path=dependency.field(FieldRef(lambda: type(request.dependency), lambda d: d.section_key)).freeze(),
            related_path=None, message="Dependency key differs from the subject section"))
    operation = request.section.patches[0].header.ref.operation_id
    for index, patch in enumerate(request.section.patches):
        ref_path = patches.item(index).field(FieldRef(lambda: type(patch), lambda p: p.header)).field(
            FieldRef(lambda: type(patch.header), lambda h: h.ref))
        if patch.header.ref.operation_id != operation:
            errors.add(LifecycleRelationIssue(code=Code.PATCH_OPERATION_MISMATCH,
                path=ref_path.field(FieldRef(lambda: type(patch.header.ref), lambda r: r.operation_id)).freeze(),
                related_path=None, message="Subject patch operation IDs differ"))
        if patch.header.ref.section_key != request.section.header.key:
            errors.add(LifecycleRelationIssue(code=Code.PATCH_SECTION_MISMATCH,
                path=ref_path.field(FieldRef(lambda: type(patch.header.ref), lambda r: r.section_key)).freeze(),
                related_path=None, message="Patch ref belongs to another section"))
    for index, link in enumerate(request.links):
        if any(previous == link for previous in request.links[:index]):
            errors.add(LifecycleRelationIssue(code=Code.COVERAGE_DUPLICATE, path=links.item(index).freeze(),
                related_path=None, message="Duplicate change/effect link"))
        if not any(link.effect in patch.effects for patch in request.section.patches):
            errors.add(LifecycleRelationIssue(code=Code.COVERAGE_MISSING,
                path=links.item(index).field(FieldRef(lambda: type(link), lambda l: l.effect)).freeze(),
                related_path=None, message="No subject patch contains this exact effect"))
    return errors.snapshot()


class MockLifecycleEvidenceBuilderA:
    def build(self, request: BuildMockEvidenceA) -> tuple[CoverageA, ...] | LifecycleSectionRefused:
        if type(request) is not BuildMockEvidenceA:
            raise TypeError("A builder requires exact BuildMockEvidenceA")
        request = BuildMockEvidenceA.model_validate(request, strict=True)
        issues = _issues(request)
        if issues:
            return LifecycleSectionRefused(issues=issues)
        return tuple(CoverageA(change_uid=link.change_uid, effect=link.effect, section=request.dependency,
            patch_refs=tuple(p.header.ref for p in request.section.patches if link.effect in p.effects))
            for link in request.links)


class MockLifecycleEvidenceBuilderB:
    def build(self, request: BuildMockEvidenceB) -> tuple[CoverageB, ...] | LifecycleSectionRefused:
        if type(request) is not BuildMockEvidenceB:
            raise TypeError("B builder requires exact BuildMockEvidenceB")
        request = BuildMockEvidenceB.model_validate(request, strict=True)
        issues = _issues(request)
        if issues:
            return LifecycleSectionRefused(issues=issues)
        return tuple(CoverageB(change_uid=link.change_uid, effect=link.effect, section=request.dependency,
            patch_refs=tuple(p.header.ref for p in request.section.patches if link.effect in p.effects))
            for link in request.links)
