"""The single checked heterogeneous section dispatch boundary."""

from collections.abc import Awaitable, Callable
from types import UnionType
from typing import Union, cast, get_args, get_origin
from pydantic import BaseModel, TypeAdapter
from app.application.patch.errors import SectionHandlerContractError
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.modelContractChecks import ModelContractChecks
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.fieldBinding import bind_field

from app.encoding.canonicalCodec import merge_manifests
from app.application.patch.encoding.coreManifest import PATCH_CORE_SCHEMA
from app.application.patch.contracts.sectionHandler import DomainSectionHandler, SectionContract
from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.patch.registry.sectionMetadata import PatchSectionMetadata, SectionKey
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionApplyReceipt, SectionRefused, SectionValidation
from app.dataModel.patch.sections.section import DomainSection
from app.application.patch.contracts.sectionCodec import SectionCodec
from app.application.patch.registry.boundSectionCodec import BoundSectionCodec


_REFUSAL_DIAGNOSTICS = bind_field(FieldRef(lambda: SectionRefused, lambda refusal: refusal.diagnostics))


def _diagnostic_types(model: type[SectionRefused]) -> frozenset[type[BaseModel]]:
    if (not isinstance(model, type) or not issubclass(model, SectionRefused)
            or model is SectionRefused or model.__pydantic_generic_metadata__.get("parameters")
            or model.__pydantic_generic_metadata__.get("origin") is not None):
        raise TypeError("refusal requires a named closed carrier")
    if tuple(model.model_fields) != tuple(SectionRefused.model_fields):
        raise TypeError("refusal carrier cannot add fields")
    if not ModelContractChecks.same_validation_config(model.model_config, SectionRefused.model_config):
        raise TypeError("refusal must retain immutable strict validation")
    for name, field in SectionRefused.model_fields.items():
        actual = model.model_fields[name]
        if (not actual.is_required() or actual.metadata != field.metadata
                or name != _REFUSAL_DIAGNOSTICS.field and actual.annotation != field.annotation):
            raise TypeError("refusal must retain field constraints")
    if not ModelContractChecks.same_validators(model, SectionRefused):
        raise TypeError("refusal carrier cannot add semantic validators")
    annotation = model.model_fields[_REFUSAL_DIAGNOSTICS.field].annotation
    args = get_args(annotation)
    if get_origin(annotation) is not tuple or len(args) != 2 or args[1] is not Ellipsis:
        raise TypeError("refusal diagnostics must be an ordered tuple")
    member = args[0]
    types = get_args(member) if get_origin(member) in (Union, UnionType) else (member,)
    for issue in types:
        if (not isinstance(issue, type) or not issubclass(issue, BaseModel)
                or issue in (BaseModel, FieldPathError)
                or issue.__pydantic_generic_metadata__.get("parameters")
                or issue.__pydantic_generic_metadata__.get("origin") is not None
                or not ModelContractChecks.same_validation_config(issue.model_config, SectionRefused.model_config)):
            raise TypeError("diagnostics must be named concrete immutable models")
    return frozenset(types)


class BoundSectionHandler[D: BaseModel]:
    def __init__[S: DomainSection, L: BaseModel](self, contract: SectionContract[S],
            handler: DomainSectionHandler[S, L], refusal_model: type[SectionRefused[D]]) -> None:
        if not isinstance(handler, DomainSectionHandler):
            raise TypeError("handler must implement DomainSectionHandler")
        if handler.contract is not contract:
            raise ValueError("handler must declare the registered contract instance")
        # Revalidate even a contract constructed through an unchecked boundary.
        contract.__post_init__()
        local_model = handler.refusal_model
        local_types = _diagnostic_types(local_model)
        if not local_types <= _diagnostic_types(refusal_model):
            raise ValueError("handler diagnostics are outside composition roster")
        diagnostic_adapter = TypeAdapter[tuple[D, ...]](refusal_model.model_fields[_REFUSAL_DIAGNOSTICS.field].annotation)
        self._metadata = PatchSectionMetadata(key=contract.key, supported_versions=contract.supported_versions)
        self._model: type[DomainSection] = contract.section_model

        def checked(section: DomainSection) -> S:
            if type(section) is not contract.section_model:
                raise TypeError("section does not have the exact registered model")
            result = contract.section_model.model_validate(cast(S, section), strict=True)
            if result.header.key != contract.key or result.header.format_version not in contract.supported_versions:
                raise ValueError("section key or format version does not match its contract")
            return result

        def output[R: BaseModel](value: object, success: type[R]) -> R | SectionRefused[D]:
            try:
                if type(value) is success:
                    return success.model_validate(value, strict=True)
                if type(value) is not local_model:
                    raise TypeError("handler returned an undeclared output type")
                local = cast(SectionRefused[L], value)
                if any(type(issue) not in local_types for issue in local.diagnostics):
                    raise TypeError("handler returned an undeclared diagnostic type")
                local = local_model.model_validate(local, strict=True)
                diagnostics = diagnostic_adapter.validate_python(local.diagnostics, strict=True)
                if tuple(map(type, diagnostics)) != tuple(map(type, local.diagnostics)):
                    raise TypeError("composition changed diagnostic types")
                return refusal_model(category=local.category, diagnostics=diagnostics)
            except (TypeError, ValueError, AttributeError) as exc:
                raise SectionHandlerContractError("section handler output contract violated") from exc

        async def validate(section: DomainSection, context: SnapshotValidationContext) -> SectionValidation[D]:
            result = await handler.validate(checked(section), context)
            return output(result, SectionAccepted)

        async def apply(section: DomainSection, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused[D]:
            result = await handler.apply(checked(section), context)
            return output(result, SectionApplyReceipt)

        self._validate: Callable[[DomainSection, SnapshotValidationContext], Awaitable[SectionValidation[D]]] = validate
        self._apply: Callable[[DomainSection, SnapshotApplyContext], Awaitable[SectionApplyReceipt | SectionRefused[D]]] = apply

    @property
    def metadata(self) -> PatchSectionMetadata:
        return self._metadata

    @property
    def section_model(self) -> type[DomainSection]:
        return self._model

    async def validate(self, section: DomainSection, context: SnapshotValidationContext) -> SectionValidation[D]:
        return await self._validate(section, context)

    async def apply(self, section: DomainSection, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused[D]:
        return await self._apply(section, context)



class SectionRegistry[D: BaseModel]:
    def __init__(self, refusal_model: type[SectionRefused[D]]) -> None:
        self._diagnostic_types = _diagnostic_types(refusal_model)
        self._refusal_model = refusal_model
        self._bindings: dict[SectionKey, BoundSectionHandler[D]] = {}
        self._codecs: dict[SectionKey, BoundSectionCodec] = {}
        self._manifest = PATCH_CORE_SCHEMA

    @property
    def refusal_model(self) -> type[SectionRefused[D]]:
        return self._refusal_model

    @property
    def diagnostic_types(self) -> frozenset[type[BaseModel]]:
        return self._diagnostic_types

    def register[S: DomainSection, L: BaseModel](self, contract: SectionContract[S], handler: DomainSectionHandler[S, L],
                                  codec: SectionCodec[S]) -> None:
        # C1 accepted exception: preserve fail-fast configuration errors; publish only after all checks.
        if contract.key in self._bindings:
            raise ValueError("duplicate section key")
        if any(bound.section_model is contract.section_model for bound in self._bindings.values()):
            raise ValueError("section model already registered")
        bound = BoundSectionHandler(contract, handler, self._refusal_model)
        representation = BoundSectionCodec(contract, codec)
        manifest = merge_manifests(self._manifest, representation.manifest)
        self._bindings[contract.key] = bound
        self._codecs[contract.key] = representation
        self._manifest = manifest

    @property
    def manifest(self) -> CanonicalSchemaManifest:
        return self._manifest

    def require(self, key: SectionKey) -> BoundSectionHandler[D]:
        try:
            return self._bindings[key]
        except KeyError as exc:
            raise ValueError("unknown section key") from exc

    def resolve(self, section: DomainSection) -> BoundSectionHandler[D]:
        bound = self.require(section.header.key)
        if type(section) is not bound.section_model:
            raise TypeError("section does not have the exact registered model")
        # Reject corrupt constructed instances before resolving, not only on invocation.
        bound.section_model.model_validate(section, strict=True)
        if section.header.format_version not in bound.metadata.supported_versions:
            raise ValueError("unsupported section version")
        return bound

    def require_codec(self, key: SectionKey) -> BoundSectionCodec:
        try:
            return self._codecs[key]
        except KeyError as exc:
            raise ValueError("unknown section key") from exc

    def resolve_codec(self, section: DomainSection) -> BoundSectionCodec:
        bound = self.require_codec(section.header.key)
        if type(section) is not bound.section_model:
            raise TypeError("section does not have the exact registered model")
        bound.section_model.model_validate(section, strict=True)
        if section.header.format_version not in bound.metadata.supported_versions:
            raise ValueError("unsupported section version")
        return bound
