"""Result role of PatchSetData with core relations enforced on construction.

Shared fields with assembly input are authorized in tz_patch_system.md.
Prepared-order is an admission guarantee, not a constructor invariant.
"""

from typing import Self
from pydantic import model_validator
from app.dataModel.patch.request.patchSetData import PatchSetData
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.validation.patchSetInvariants import PatchSetInvariants
from app.dataModel.patch.validation.coreInvariantError import PatchSetCoreInvariantError


class PatchSet[S: DomainSection](PatchSetData[S]):
    @model_validator(mode="after")
    def coherent_request(self) -> Self:
        violations = PatchSetInvariants.check_core(self)
        if violations:
            raise PatchSetCoreInvariantError(violations)
        return self
