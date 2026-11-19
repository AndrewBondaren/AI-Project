"""Input role of the shared PatchSetData schema; relation failures are admitted.

Shared fields with PatchSet are explicitly authorized in tz_patch_system.md.
"""

from app.dataModel.patch.request.patchSetData import PatchSetData
from app.dataModel.patch.sections.section import DomainSection


class PatchSetAssemblyInput[S: DomainSection](PatchSetData[S]):
    pass
