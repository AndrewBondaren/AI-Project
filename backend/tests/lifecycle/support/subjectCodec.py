"""Canonical native codec for the two synthetic subject sections."""
from app.application.patch.contracts.sectionCodec import SectionCodec
from app.application.patch.contracts.sectionHandler import SectionContract
from app.dataModel.patch.values import FormatVersion
from app.encoding.canonicalCodec import encode, decode
from tests.lifecycle.support.domainSections import TestDomainSectionA, TestDomainSectionB


class MockSubjectCodec[S: (TestDomainSectionA, TestDomainSectionB)](SectionCodec[S]):
    def __init__(self, contract: SectionContract[S]) -> None:
        if contract.supported_versions != frozenset({2}):
            raise ValueError("subject codec requires effect-enum format 2")
        self._contract = contract

    @property
    def contract(self) -> SectionContract[S]:
        return self._contract

    def encode(self, section: S) -> bytes:
        if type(section) is not self._contract.section_model:
            raise TypeError("subject codec requires its exact native model")
        if section.header.format_version != 2 or any(p.header.format_version != 2 for p in section.patches):
            raise ValueError("unsupported subject section/patch format")
        return encode(section, self._contract.manifest)

    def decode(self, payload: bytes, version: FormatVersion) -> S:
        if version not in self._contract.supported_versions:
            raise ValueError("unsupported subject section version")
        section = decode(payload, self._contract.section_model, self._contract.manifest)
        self.encode(section)
        return section
