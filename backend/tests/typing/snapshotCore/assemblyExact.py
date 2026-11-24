"""Exact named assembly output can cross a node edge without conversion."""
from typing import assert_type
from app.application.patch.contracts.assembly import IPatchSetAssembly
from app.application.patch.assembly.patchSetAssembler import PatchSetAssembler
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput, MockPatchSet


def exact_output(request: MockAssemblyInput) -> MockPatchSet | PatchSetAssemblyRefused:
    service: IPatchSetAssembly[MockAssemblyInput, MockPatchSet] = PatchSetAssembler(MockAssemblyInput, MockPatchSet)
    result = service.assemble(request)
    assert_type(result, MockPatchSet | PatchSetAssemblyRefused)
    return result
