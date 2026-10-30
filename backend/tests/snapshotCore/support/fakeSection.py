"""Test-only domain contracts; never registered in production."""

from pydantic import BaseModel, ConfigDict
from app.application.patch.contracts.sectionHandler import DomainSectionHandler, SectionContract
from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.dataModel.patch.changes.header import PatchHeader
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionApplyReceipt, SectionValidation
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.values import FormatVersion


class FakeTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    name: str


class FakeChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    amount: int


class FakePrepared(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    values: tuple[int, ...]


class FakePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")
    header: PatchHeader
    target: FakeTarget
    change: FakeChange
    prepared: FakePrepared


class FakeSection(DomainSection[FakePatch]):
    pass


class FakeSectionHandler(DomainSectionHandler[FakeSection]):
    def __init__(self, contract: SectionContract[FakeSection]) -> None:
        self._contract = contract
        self.calls: list[str] = []

    @property
    def contract(self) -> SectionContract[FakeSection]:
        return self._contract

    async def validate(self, section: FakeSection, context: SnapshotValidationContext) -> SectionValidation:
        self.calls.append("validate")
        return SectionAccepted()

    async def apply(self, section: FakeSection, context: SnapshotApplyContext) -> SectionApplyReceipt:
        self.calls.append("apply")
        return SectionApplyReceipt(section_key=section.header.key, state_refs=(), history_refs=(),
                                   changed=(), retained_artifacts=())

    def encode(self, section: FakeSection) -> bytes:
        self.calls.append("encode")
        return section.model_dump_json().encode("utf-8")

    def decode(self, payload: bytes, version: FormatVersion) -> FakeSection:
        self.calls.append("decode")
        return FakeSection.model_validate_json(payload)
