"""Pure assembly operation called directly by the owning DAG node."""

from typing import Protocol
from app.dataModel.patch.request.assembly import PatchSetAssemblyInput
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused
from app.dataModel.patch.request.patchSet import PatchSet


class IPatchSetAssembly[Q: PatchSetAssemblyInput, P: PatchSet](Protocol):
    def assemble(self, request: Q) -> P | PatchSetAssemblyRefused: ...
