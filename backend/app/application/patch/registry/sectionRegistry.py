"""The single checked heterogeneous section dispatch boundary."""

from collections.abc import Awaitable, Callable
from typing import cast

from app.application.patch.contracts.sectionHandler import DomainSectionHandler, SectionContract
from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.patch.registry.sectionMetadata import PatchSectionMetadata, SectionKey
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt, SectionRefused, SectionValidation
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.values import FormatVersion


class BoundSectionHandler:
    def __init__[S: DomainSection](self, contract: SectionContract[S], handler: DomainSectionHandler[S]) -> None:
        if not isinstance(handler, DomainSectionHandler):
            raise TypeError("handler must implement DomainSectionHandler")
        if handler.contract is not contract:
            raise ValueError("handler must declare the registered contract instance")
        # Revalidate even a contract constructed through an unchecked boundary.
        contract.__post_init__()
        self._metadata = PatchSectionMetadata(key=contract.key, supported_versions=contract.supported_versions)
        self._model: type[DomainSection] = contract.section_model
        self._manifest = contract.manifest

        def checked(section: DomainSection) -> S:
            if type(section) is not contract.section_model:
                raise TypeError("section does not have the exact registered model")
            result = contract.section_model.model_validate(cast(S, section), strict=True)
            if result.header.key != contract.key or result.header.format_version not in contract.supported_versions:
                raise ValueError("section key or format version does not match its contract")
            return result

        async def validate(section: DomainSection, context: SnapshotValidationContext) -> SectionValidation:
            return await handler.validate(checked(section), context)

        async def apply(section: DomainSection, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused:
            return await handler.apply(checked(section), context)

        def encode(section: DomainSection) -> bytes:
            payload = handler.encode(checked(section))
            if type(payload) is not bytes:
                raise TypeError("section encoder must return bytes")
            return payload

        def decode(payload: bytes, version: FormatVersion) -> DomainSection:
            if type(payload) is not bytes or type(version) is not int or version not in contract.supported_versions:
                raise ValueError("unsupported section bytes or version")
            return checked(handler.decode(payload, version))

        self._validate: Callable[[DomainSection, SnapshotValidationContext], Awaitable[SectionValidation]] = validate
        self._apply: Callable[[DomainSection, SnapshotApplyContext], Awaitable[SectionApplyReceipt | SectionRefused]] = apply
        self._encode: Callable[[DomainSection], bytes] = encode
        self._decode: Callable[[bytes, FormatVersion], DomainSection] = decode

    @property
    def metadata(self) -> PatchSectionMetadata:
        return self._metadata

    @property
    def section_model(self) -> type[DomainSection]:
        return self._model

    @property
    def manifest(self) -> CanonicalSchemaManifest:
        return self._manifest

    async def validate(self, section: DomainSection, context: SnapshotValidationContext) -> SectionValidation:
        return await self._validate(section, context)

    async def apply(self, section: DomainSection, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused:
        return await self._apply(section, context)

    def encode(self, section: DomainSection) -> bytes:
        return self._encode(section)

    def decode(self, payload: bytes, version: FormatVersion) -> DomainSection:
        return self._decode(payload, version)


class SectionRegistry:
    def __init__(self) -> None:
        self._bindings: dict[SectionKey, BoundSectionHandler] = {}

    def register[S: DomainSection](self, contract: SectionContract[S], handler: DomainSectionHandler[S]) -> None:
        if contract.key in self._bindings:
            raise ValueError("duplicate section key")
        if any(bound.section_model is contract.section_model for bound in self._bindings.values()):
            raise ValueError("section model already registered")
        bound = BoundSectionHandler(contract, handler)
        self._bindings[contract.key] = bound

    def require(self, key: SectionKey) -> BoundSectionHandler:
        try:
            return self._bindings[key]
        except KeyError as exc:
            raise ValueError("unknown section key") from exc

    def resolve(self, section: DomainSection) -> BoundSectionHandler:
        bound = self.require(section.header.key)
        if type(section) is not bound.section_model:
            raise TypeError("section does not have the exact registered model")
        # Reject corrupt constructed instances before resolving, not only on invocation.
        bound.section_model.model_validate(section, strict=True)
        if section.header.format_version not in bound.metadata.supported_versions:
            raise ValueError("unsupported section version")
        return bound
