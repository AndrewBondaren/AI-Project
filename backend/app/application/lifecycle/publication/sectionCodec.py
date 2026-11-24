from app.application.patch.contracts.sectionCodec import SectionCodec
from app.application.patch.contracts.sectionHandler import SectionContract
from app.dataModel.lifecycle.publication.section import LifecycleSection
from app.dataModel.lifecycle.publication.patch import LifecycleTransitionPatch
from app.dataModel.patch.values import FormatVersion
from app.encoding.canonicalCodec import decode, encode
from typing import Any


class LifecycleSectionCodec[S: LifecycleSection[Any, Any]](SectionCodec[S]):
    def __init__(self, contract: SectionContract[S]) -> None:
        if contract.supported_versions != frozenset({LifecycleSection.FORMAT_VERSION}):
            raise ValueError("Lifecycle codec supports only the current effect-enum section format")
        self._contract = contract

    @property
    def contract(self) -> SectionContract[S]:
        return self._contract

    def encode(self, section: S) -> bytes:
        if type(section) is not self._contract.section_model:
            raise TypeError("codec requires the exact bound section model")
        checked = self._contract.section_model.model_validate(section, strict=True)
        if checked.header.key != self._contract.key or checked.header.format_version not in self._contract.supported_versions:
            raise ValueError("section key/version differs from codec binding")
        if any(p.header.format_version != LifecycleTransitionPatch.FORMAT_VERSION for p in checked.patches):
            raise ValueError("unsupported lifecycle transition patch version")
        return encode(checked, self._contract.manifest)

    def decode(self, payload: bytes, version: FormatVersion) -> S:
        if type(version) is not int or version not in self._contract.supported_versions:
            raise ValueError("unsupported lifecycle section version")
        section = decode(payload, self._contract.section_model, self._contract.manifest)
        if section.header.key != self._contract.key or section.header.format_version != version:
            raise ValueError("decoded section header differs from the declared binding")
        self.encode(section)
        return section
