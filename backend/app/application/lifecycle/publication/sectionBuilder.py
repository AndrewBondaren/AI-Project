from pydantic import BaseModel
from typing import Any, cast

from app.application.lifecycle.contracts.sectionBinding import LifecycleSectionBinding
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.sections.section import SectionHeader
from app.dataModel.patch.sections.section import DomainSection
from app.application.lifecycle.contracts.typedViews import section_request_view
from app.dataModel.lifecycle.publication.section import LifecycleSection
from app.dataModel.patch.changes.patchData import PatchData


class LifecycleSectionBuilder[Q: BaseModel, S: DomainSection[Any]]:
    def __init__(self, binding: LifecycleSectionBinding[Q, S]) -> None:
        self._binding = binding

    def build(self, source: Q) -> S:
        request = section_request_view(source)
        contract = self._binding.section_contract
        version = next(iter(contract.supported_versions))
        dependencies = tuple(dict.fromkeys(entry.section for entry in request.domain_evidence))
        patches = tuple(self._binding.patch_model(prepared)(
            header=PatchHeader(ref=PatchRef(operation_id=request.operation_id, section_key=contract.key, ordinal=index),
                               format_version=version, depends_on=(), artifacts=()),
            prepared=prepared) for index, prepared in enumerate(request.changes))
        # Binding verified owning section inheritance and exact nested schemas.
        model = cast(type[LifecycleSection[PatchData, BaseModel]], contract.section_model)
        return cast(S, model(
            header=SectionHeader(key=contract.key, format_version=version, depends_on=dependencies),
            patches=patches, domain_evidence=request.domain_evidence))
