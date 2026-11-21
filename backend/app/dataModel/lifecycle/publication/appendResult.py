"""Own append postcondition, not a durable publication result."""
from pydantic import BaseModel, ConfigDict
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.worldSnapshot.sections.retention import SectionHistoryRetention, SectionStateRetention


class LifecycleAppended(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    state: SectionStateRetention | None
    history: SectionHistoryRetention | None
    changed: tuple[PatchRef, ...]
