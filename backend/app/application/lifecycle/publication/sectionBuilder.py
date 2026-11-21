from pydantic import BaseModel

from app.application.lifecycle.contracts.sectionBinding import LifecycleSectionBinding
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.sections.section import SectionHeader


class LifecycleSectionBuilder:
    def __init__(self, binding: LifecycleSectionBinding) -> None:
        self._binding = binding

    def build(self, request: BaseModel) -> BaseModel:
        contract = self._binding.section_contract
        version = next(iter(contract.supported_versions))
        dependencies = tuple(dict.fromkeys(entry.section for entry in request.domain_evidence))
        patches = tuple(self._binding.patch_model(prepared)(
            header=PatchHeader(ref=PatchRef(operation_id=request.operation_id, section_key=contract.key, ordinal=index),
                               format_version=version, depends_on=(), artifacts=()),
            prepared=prepared) for index, prepared in enumerate(request.changes))
        return contract.section_model(
            header=SectionHeader(key=contract.key, format_version=version, depends_on=dependencies),
            patches=patches, domain_evidence=request.domain_evidence)
