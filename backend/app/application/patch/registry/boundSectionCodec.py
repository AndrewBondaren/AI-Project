"""The single checked heterogeneous section dispatch boundary."""

from collections.abc import Callable
from typing import cast

from app.encoding.canonicalCodec import merge_manifests
from app.application.patch.encoding.coreManifest import PATCH_CORE_SCHEMA
from app.application.patch.contracts.sectionHandler import SectionContract
from app.application.patch.contracts.sectionCodec import SectionCodec
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.patch.registry.sectionMetadata import PatchSectionMetadata
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.values import FormatVersion


class BoundSectionCodec:
    def __init__[S: DomainSection](self, contract: SectionContract[S], codec: SectionCodec[S]) -> None:
        if not isinstance(codec, SectionCodec):
            raise TypeError("codec must implement SectionCodec")
        if codec.contract is not contract:
            raise ValueError("codec must declare the registered contract instance")
        # Revalidate even a contract constructed through an unchecked boundary.
        contract.__post_init__()
        self._metadata = PatchSectionMetadata(key=contract.key, supported_versions=contract.supported_versions)
        self._model: type[DomainSection] = contract.section_model
        self._manifest = merge_manifests(PATCH_CORE_SCHEMA, contract.manifest)

        def checked(section: DomainSection) -> S:
            if type(section) is not contract.section_model:
                raise TypeError("section does not have the exact registered model")
            result = contract.section_model.model_validate(cast(S, section), strict=True)
            if result.header.key != contract.key or result.header.format_version not in contract.supported_versions:
                raise ValueError("section key or format version does not match its contract")
            return result

        def encode(section: DomainSection) -> bytes:
            section = checked(section)
            payload = codec.encode(section)
            if type(payload) is not bytes:
                raise TypeError("section encoder must return bytes")
            return payload

        def decode(payload: bytes, version: FormatVersion) -> DomainSection:
            if type(payload) is not bytes or type(version) is not int or version not in contract.supported_versions:
                raise ValueError("unsupported section bytes or version")
            # The domain codec selects its immutable format manifest and validates
            # original canonical bytes before upgrading. Current model fields
            # cannot validate historical formats with a different declaration.
            return checked(codec.decode(payload, version))

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

    def encode(self, section: DomainSection) -> bytes:
        return self._encode(section)

    def decode(self, payload: bytes, version: FormatVersion) -> DomainSection:
        return self._decode(payload, version)
