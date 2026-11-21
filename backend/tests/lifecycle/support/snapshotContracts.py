"""Named H2 carriers for the mock Lifecycle composition; no wire identities."""
from app.dataModel.patch.results.sectionResult import SectionRefused
from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyIssue
from tests.lifecycle.support.domainSections import MockSubjectIssue
from tests.lifecycle.support.domainSections import TestDomainSectionA, TestDomainSectionB
from tests.lifecycle.support.mixedContracts import LifecycleSectionAB
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.patch.request.assembly import PatchSetAssemblyInput
from app.dataModel.patch.request.patchSet import PatchSet


MockDiagnostic = LifecycleApplyIssue | MockSubjectIssue
MockSectionUnion = LifecycleSectionAB | TestDomainSectionA | TestDomainSectionB


class MockSnapshotApplyResult(SnapshotApplyResult[MockDiagnostic]):
    pass


class MockAssemblyInput(PatchSetAssemblyInput[MockSectionUnion]):
    pass


class MockPatchSet(PatchSet[MockSectionUnion]):
    pass


class MockLifecycleSectionRefused(SectionRefused[LifecycleApplyIssue]):
    pass


class MockSubjectSectionRefused(SectionRefused[MockSubjectIssue]):
    pass


class MockSectionRefused(SectionRefused[MockDiagnostic]):
    pass
