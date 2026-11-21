"""Canonical native codec for the two synthetic subject sections."""
from app.application.patch.contracts.sectionCodec import SectionCodec
from app.application.patch.contracts.sectionHandler import SectionContract
from app.dataModel.patch.values import FormatVersion
from app.encoding.canonicalCodec import encode, decode
from tests.lifecycle.support.domainSections import TestDomainSectionA, TestDomainSectionB


class MockSubjectCodec[S: (TestDomainSectionA, TestDomainSectionB)](SectionCodec[S]):
    def __init__(self, contract: SectionContract[S]) -> None:
        self._contract = contract

    @property
    def contract(self) -> SectionContract[S]:
        return self._contract

    def encode(self, section: S) -> bytes:
        if type(section) is not self._contract.section_model:
            raise TypeError("subject codec requires its exact native model")
        return encode(section, self._contract.manifest)

    def decode(self, payload: bytes, version: FormatVersion) -> S:
        if version not in self._contract.supported_versions:
            raise ValueError("unsupported subject section version")
        return decode(payload, self._contract.section_model, self._contract.manifest)
