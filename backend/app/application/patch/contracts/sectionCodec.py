"""Pure canonical representation of a registered native section."""

from abc import ABC, abstractmethod

from app.application.patch.contracts.sectionHandler import SectionContract
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.values import FormatVersion


class SectionCodec[S: DomainSection](ABC):
    @property
    @abstractmethod
    def contract(self) -> SectionContract[S]: ...

    @abstractmethod
    def encode(self, section: S) -> bytes: ...

    @abstractmethod
    def decode(self, payload: bytes, version: FormatVersion) -> S:
        """Validate canonical bytes before any supported owning read-upgrade."""
        ...
