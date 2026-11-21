from app.application.patch.contracts.sectionCodec import SectionCodec
from app.application.patch.contracts.sectionHandler import SectionContract
from app.dataModel.patch.values import FormatVersion
from app.dataModel.time.changes.section import TimeAdvanceSection, TIME_ADVANCE_SECTION_FORMAT
from app.dataModel.time.storage.state import CLOCK_SECTION
from app.encoding.canonicalCodec import CanonicalEncodingError, decode, encode


class TimeSectionCodec(SectionCodec[TimeAdvanceSection]):
    def __init__(self, contract: SectionContract[TimeAdvanceSection]) -> None:
        if contract.section_model is not TimeAdvanceSection or contract.key != CLOCK_SECTION:
            raise ValueError("Time codec requires its concrete native section contract")
        if contract.supported_versions != frozenset({TIME_ADVANCE_SECTION_FORMAT}):
            raise ValueError("Time codec requires exactly the native section version")
        self._contract = contract

    @property
    def contract(self) -> SectionContract[TimeAdvanceSection]:
        return self._contract

    def encode(self, section: TimeAdvanceSection) -> bytes:
        try:
            if type(section) is not TimeAdvanceSection:
                raise TypeError("expected concrete TimeAdvanceSection")
            checked = TimeAdvanceSection.model_validate(section, strict=True)
            if checked.header.format_version not in self.contract.supported_versions:
                raise ValueError("unsupported Time section version")
            return encode(checked, self.contract.manifest)
        except (TypeError, ValueError) as error:
            raise CanonicalEncodingError("cannot encode Time section") from error

    def decode(self, payload: bytes, version: FormatVersion) -> TimeAdvanceSection:
        try:
            if type(version) is not int or version not in self.contract.supported_versions:
                raise ValueError("unsupported Time section version")
            section = decode(payload, TimeAdvanceSection, self.contract.manifest)
            checked = TimeAdvanceSection.model_validate(section, strict=True)
            if checked.header.format_version != version:
                raise ValueError("Time section version mismatch")
            return checked
        except (TypeError, ValueError) as error:
            raise CanonicalEncodingError("cannot decode Time section") from error
