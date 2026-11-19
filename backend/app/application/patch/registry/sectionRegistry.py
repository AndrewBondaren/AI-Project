"""The single checked heterogeneous section dispatch boundary."""

from collections.abc import Awaitable, Callable
from typing import cast

from app.encoding.canonicalCodec import merge_manifests
from app.application.patch.encoding.coreManifest import PATCH_CORE_SCHEMA
from app.application.patch.contracts.sectionHandler import DomainSectionHandler, SectionContract
from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.patch.registry.sectionMetadata import PatchSectionMetadata, SectionKey
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt, SectionRefused, SectionValidation
from app.dataModel.patch.sections.section import DomainSection
from app.application.patch.contracts.sectionCodec import SectionCodec
from app.application.patch.registry.boundSectionCodec import BoundSectionCodec


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

        self._validate: Callable[[DomainSection, SnapshotValidationContext], Awaitable[SectionValidation]] = validate
        self._apply: Callable[[DomainSection, SnapshotApplyContext], Awaitable[SectionApplyReceipt | SectionRefused]] = apply

    @property
    def metadata(self) -> PatchSectionMetadata:
        return self._metadata

    @property
    def section_model(self) -> type[DomainSection]:
        return self._model

    async def validate(self, section: DomainSection, context: SnapshotValidationContext) -> SectionValidation:
        return await self._validate(section, context)

    async def apply(self, section: DomainSection, context: SnapshotApplyContext) -> SectionApplyReceipt | SectionRefused:
        return await self._apply(section, context)



class SectionRegistry:
    def __init__(self) -> None:
        self._bindings: dict[SectionKey, BoundSectionHandler] = {}
        self._codecs: dict[SectionKey, BoundSectionCodec] = {}
        self._manifest = PATCH_CORE_SCHEMA

    def register[S: DomainSection](self, contract: SectionContract[S], handler: DomainSectionHandler[S],
                                  codec: SectionCodec[S]) -> None:
        # C1 accepted exception: preserve fail-fast configuration errors; publish only after all checks.
        if contract.key in self._bindings:
            raise ValueError("duplicate section key")
        if any(bound.section_model is contract.section_model for bound in self._bindings.values()):
            raise ValueError("section model already registered")
        bound = BoundSectionHandler(contract, handler)
        representation = BoundSectionCodec(contract, codec)
        manifest = merge_manifests(self._manifest, representation.manifest)
        self._bindings[contract.key] = bound
        self._codecs[contract.key] = representation
        self._manifest = manifest

    @property
    def manifest(self) -> CanonicalSchemaManifest:
        return self._manifest

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
