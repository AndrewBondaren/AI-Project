"""Exact construction binding and pure all-or-nothing batch assembly."""

from types import UnionType
from typing import Union, get_args, get_origin
from pydantic import BaseModel

from app.application.patch.assembly.patchSetAssemblyValidator import PatchSetAssemblyValidator
from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.fields.validatedFieldPath import ModelIdentity
from app.dataModel.patch.changes.patchData import PatchData
from app.dataModel.patch.changes.header import PatchHeader
from app.dataModel.patch.request.assembly import PatchSetAssemblyInput
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused, PatchSetAssemblyResult
from app.dataModel.patch.sections.section import DomainSection, SectionHeader


class PatchSetAssembler[S: DomainSection]:
    def __init__(self, request_model: type[PatchSetAssemblyInput[S]],
                 result_model: type[PatchSet[S]]) -> None:
        for model, base in ((request_model, PatchSetAssemblyInput), (result_model, PatchSet)):
            if not isinstance(model, type) or not issubclass(model, base):
                raise TypeError("assembly requires input and result child models")
            self._require_native_model(model)
            if tuple(model.model_fields) != tuple(base.model_fields):
                raise TypeError("assembly child must retain the shared field schema")
            for name, field in base.model_fields.items():
                bound = model.model_fields[name]
                if (name != "sections" and bound.annotation != field.annotation
                        or bound.metadata != field.metadata or not bound.is_required()):
                    raise TypeError("assembly children must retain field types and constraints")
        sections = request_model.model_fields["sections"].annotation
        if sections != result_model.model_fields["sections"].annotation:
            raise TypeError("input and result must bind the same closed section union")
        args = get_args(sections)
        if get_origin(sections) is not tuple or len(args) != 2 or args[1] is not Ellipsis:
            raise TypeError("assembly requires an ordered section tuple")
        section_type = unwrap_wire_type(args[0])
        models = get_args(section_type) if get_origin(section_type) in (Union, UnionType) else (section_type,)
        for section_model in models:
            if not isinstance(section_model, type) or not issubclass(section_model, DomainSection):
                raise TypeError("assembly requires native section models")
            self._require_native_model(section_model)
            patch_annotation = section_model.model_fields["patches"].annotation
            patch_args = get_args(patch_annotation)
            if (section_model.model_fields["header"].annotation is not SectionHeader
                    or get_origin(patch_annotation) is not tuple or len(patch_args) != 2
                    or patch_args[1] is not Ellipsis):
                raise TypeError("native section must retain its header and ordered patch tuple")
            patch_type = unwrap_wire_type(patch_args[0])
            patches = get_args(patch_type) if get_origin(patch_type) in (Union, UnionType) else (patch_type,)
            for patch_model in patches:
                if (not isinstance(patch_model, type) or not issubclass(patch_model, PatchData)
                        or patch_model is PatchData):
                    raise TypeError("native patch must have the shared header")
                self._require_native_model(patch_model)
                if patch_model.model_fields["header"].annotation is not PatchHeader:
                    raise TypeError("native patch must retain PatchHeader")
        self._request_model = request_model
        self._result_model = result_model
        self._validator = PatchSetAssemblyValidator()

    @staticmethod
    def _require_native_model(model: type[BaseModel]) -> None:
        ModelIdentity.of(model)
        if (model.model_config.get("frozen") is not True or model.model_config.get("strict") is not True
                or model.model_config.get("extra") != "forbid"
                or model.model_config.get("revalidate_instances") != "always"):
            raise TypeError("assembly models must retain strict immutable validation")

    def assemble(self, request: PatchSetAssemblyInput[S]) -> PatchSetAssemblyResult[S]:
        if type(request) is not self._request_model:
            raise TypeError("request must be the exact bound input child")
        request = self._request_model.model_validate(request, strict=True)
        diagnostics = self._validator.validate(request)
        if diagnostics:
            return PatchSetAssemblyRefused(diagnostics=diagnostics)
        return self._result_model(
            format_version=request.format_version, operation_id=request.operation_id,
            preparation_fingerprint=request.preparation_fingerprint, world_uid=request.world_uid,
            timeline_id=request.timeline_id, turn_id=request.turn_id, expected_world=request.expected_world,
            expected_players=request.expected_players, sections=request.sections,
        )
