"""Exact-class native wrapper construction, fixed at composition time."""

from dataclasses import dataclass, field
from types import MappingProxyType
from collections.abc import Mapping

from pydantic import BaseModel

from app.application.lifecycle.contracts.preparationBinding import require_named_model, tuple_item, union_members
from app.application.patch.contracts.sectionHandler import SectionContract
from app.dataModel.patch.changes.patchData import PatchData
from app.dataModel.patch.sections.section import DomainSection


@dataclass(frozen=True, slots=True)
class LifecyclePatchModelBinding[P: BaseModel, N: PatchData]:
    prepared_model: type[P]
    patch_model: type[N]

    def __post_init__(self) -> None:
        require_named_model(self.prepared_model)
        require_named_model(self.patch_model)
        if not issubclass(self.patch_model, PatchData):
            raise TypeError("native wrapper must extend PatchData")
        if self.patch_model.model_fields["prepared"].annotation is not self.prepared_model:
            raise TypeError("wrapper must bind the exact prepared model")
        if set(self.patch_model.model_fields) != {"header", "prepared"}:
            raise TypeError("native wrapper has only header/prepared; evidence belongs to the section")


@dataclass(frozen=True, slots=True)
class LifecycleSectionBinding[Q: BaseModel, S: DomainSection]:
    request_model: type[Q]
    section_contract: SectionContract[S]
    patch_bindings: tuple[LifecyclePatchModelBinding, ...]
    _patch_models: Mapping[type[BaseModel], type[PatchData]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        require_named_model(self.request_model)
        model = require_named_model(self.section_contract.section_model)
        if type(self.patch_bindings) is not tuple or not self.patch_bindings:
            raise TypeError("patch bindings must be a nonempty immutable tuple")
        prepared = tuple(binding.prepared_model for binding in self.patch_bindings)
        patches = tuple(binding.patch_model for binding in self.patch_bindings)
        if len(set(prepared)) != len(prepared) or len(set(patches)) != len(patches):
            raise ValueError("duplicate prepared or native wrapper binding")
        if set(prepared) != set(union_members(tuple_item(self.request_model, "changes"))):
            raise TypeError("wrapper map must cover exactly the request changes union")
        if set(patches) != set(union_members(tuple_item(model, "patches"))):
            raise TypeError("wrapper map must cover exactly the section patch union")
        request_evidence = tuple_item(self.request_model, "domain_evidence")
        if request_evidence != tuple_item(model, "domain_evidence"):
            raise TypeError("request and section must preserve the same concrete evidence union")
        for evidence in union_members(request_evidence):
            require_named_model(evidence)
        if len(self.section_contract.supported_versions) != 1:
            raise ValueError("local v1 producer binding requires one explicit write version")
        object.__setattr__(self, "_patch_models", MappingProxyType(dict(zip(prepared, patches, strict=True))))

    def patch_model(self, prepared: BaseModel) -> type[PatchData]:
        try:
            return self._patch_models[type(prepared)]
        except KeyError as exc:
            raise TypeError("prepared model is not in the closed wrapper map") from exc

    def admit(self, request: Q) -> Q:
        if type(request) is not self.request_model:
            raise TypeError("section request does not have the exact bound class")
        # Check exact members before Pydantic could coerce a subclass to its parent.
        for change in request.changes:
            self.patch_model(change)
        evidence_models = union_members(tuple_item(self.request_model, "domain_evidence"))
        if any(type(entry) not in evidence_models for entry in request.domain_evidence):
            raise TypeError("evidence model is not in the closed roster")
        return self.request_model.model_validate(request, strict=True)
