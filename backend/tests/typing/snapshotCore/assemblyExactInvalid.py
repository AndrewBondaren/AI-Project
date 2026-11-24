"""Negative static fixture: foreign input and result cannot cross exact bindings."""
from app.application.patch.assembly.patchSetAssembler import PatchSetAssembler
from app.application.patch.contracts.assembly import IPatchSetAssembly
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput, MockPatchSet
from tests.snapshotCore.support.fakeSection import FakeAssemblyInput, FakePatchSet


def invalid(request: FakeAssemblyInput) -> None:
    service = PatchSetAssembler[MockAssemblyInput, MockPatchSet](MockAssemblyInput, MockPatchSet)
    service.assemble(request)  # EXPECT: reportArgumentType
    PatchSetAssembler[MockAssemblyInput, MockPatchSet](MockAssemblyInput, FakePatchSet)  # EXPECT: reportArgumentType
    foreign: IPatchSetAssembly[MockAssemblyInput, FakePatchSet] = service  # EXPECT: reportAssignmentType
