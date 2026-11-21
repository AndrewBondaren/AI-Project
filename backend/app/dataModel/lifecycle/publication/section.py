from pydantic import BaseModel
from app.dataModel.patch.changes.patchData import PatchData
from app.dataModel.patch.sections.section import DomainSection


class LifecycleSection[P: PatchData, C: BaseModel](DomainSection[P]):
    domain_evidence: tuple[C, ...]
