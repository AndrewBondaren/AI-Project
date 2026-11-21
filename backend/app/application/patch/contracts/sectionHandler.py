"""Typed domain behavior and explicit schema binding, outside immutable Patch data."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import UnionType
from typing import Union, get_args, get_origin
from annotated_types import MinLen
from pydantic import TypeAdapter
from app.dataModel.patch.changes.patchData import PatchData

from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt, SectionRefused, SectionValidation
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.values import FormatVersion


@dataclass(frozen=True, slots=True)
class SectionContract[S: DomainSection]:
    key: SectionKey
    section_model: type[S]
    supported_versions: frozenset[FormatVersion]
    manifest: CanonicalSchemaManifest

    def __post_init__(self) -> None:
        TypeAdapter(SectionKey).validate_python(self.key, strict=True)
        TypeAdapter(frozenset[FormatVersion]).validate_python(self.supported_versions, strict=True)
        if not self.supported_versions:
            raise ValueError("section needs at least one supported version")
        model = self.section_model
        if not isinstance(model, type) or not issubclass(model, DomainSection):
            raise TypeError("section model must be a concrete DomainSection")
        if model is DomainSection or model.__pydantic_generic_metadata__.get("parameters"):
            raise TypeError("unbound generic section model")
        if (model.model_config.get("frozen") is not True or model.model_config.get("strict") is not True
                or model.model_config.get("extra") != "forbid"
                or model.model_config.get("revalidate_instances") != "always"):
            raise TypeError("section model must be frozen and strict with instance revalidation")
        for name, inherited in DomainSection.model_fields.items():
            bound = model.model_fields[name]
            if inherited.is_required() and not bound.is_required():
                raise TypeError("native section field constraints must remain required")
            for constraint in inherited.metadata:
                if isinstance(constraint, MinLen):
                    minima = [item.min_length for item in bound.metadata if isinstance(item, MinLen)]
                    if not minima or any(minimum < constraint.min_length for minimum in minima):
                        raise TypeError("native section field constraints must retain the minimum length")
                elif constraint not in bound.metadata:
                    raise TypeError("native section field constraints must retain inherited metadata")
        patch_annotation = model.model_fields["patches"].annotation
        patch_args = get_args(patch_annotation)
        if (model.model_fields["header"].annotation is not SectionHeader
                or get_origin(patch_annotation) is not tuple or len(patch_args) != 2 or patch_args[1] is not Ellipsis):
            raise TypeError("section must retain its typed header and ordered patch tuple")
        patch_type = patch_args[0]
        patch_models = get_args(patch_type) if get_origin(patch_type) in (Union, UnionType) else (patch_type,)
        for patch_model in patch_models:
            if (not isinstance(patch_model, type) or not issubclass(patch_model, PatchData)
                    or patch_model is PatchData or patch_model.__pydantic_generic_metadata__.get("parameters")):
                raise TypeError("section needs concrete patch models, not an untyped payload")
        CanonicalSchemaManifest.model_validate(self.manifest)
        if not any(entry.python_type is model and entry.kind is CanonicalTypeKind.RECORD
                   for entry in self.manifest.entries):
            raise ValueError("canonical manifest must declare the concrete section model")


class DomainSectionHandler[S: DomainSection](ABC):
    # SNAPSHOT-V1-BOUNDARY: deferred external contracts remain v1; this is not
    # a v1 adapter. Admit native section contracts only, without legacy conversion.
    # Scope: .cursor/plans/snapshot-public-contracts-dag-integration.md, section 7.
    @property
    @abstractmethod
    def contract(self) -> SectionContract[S]: ...

    @abstractmethod
    async def validate(self, section: S, context: SnapshotValidationContext) -> SectionValidation:
        """Read-only semantic/precondition checks on the captured base."""
        ...

    @abstractmethod
    async def apply(self, section: S, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused:
        """Append prepared changes using bound storage; never materialize or commit."""
        ...
