from pydantic import BaseModel
from typing import ClassVar
from app.dataModel.patch.changes.patchData import PatchData
from app.dataModel.patch.sections.section import DomainSection


class LifecycleSection[P: PatchData, C: BaseModel](DomainSection[P]):
    FORMAT_VERSION: ClassVar[int] = 2
    domain_evidence: tuple[C, ...]
