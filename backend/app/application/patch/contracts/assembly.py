"""Pure assembly operation called directly by the owning DAG node."""

from typing import Protocol
from app.dataModel.patch.request.assembly import PatchSetAssemblyInput
from app.dataModel.patch.results.assembly import PatchSetAssemblyResult
from app.dataModel.patch.sections.section import DomainSection


class IPatchSetAssembly[S: DomainSection](Protocol):
    def assemble(self, request: PatchSetAssemblyInput[S]) -> PatchSetAssemblyResult[S]: ...
