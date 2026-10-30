"""Distinct immutable state/history references; payload remains domain-owned."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.values import FormatVersion
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef


class SectionStateRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    snapshot: SnapshotRef
    section_key: SectionKey
    format_version: FormatVersion


class SectionHistoryRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    snapshot: SnapshotRef
    section_key: SectionKey
    format_version: FormatVersion
