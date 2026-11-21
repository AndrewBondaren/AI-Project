from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.evidence.effects import DomainEffect
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.sections.dependency import PreparedSectionDependency


class PreparedEffectBinding[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal["prepared"] = "prepared"
    change_uid: EntityUid
    effect: DomainEffect[T]
    section: PreparedSectionDependency
    patch_refs: tuple[PatchRef, ...] = Field(min_length=1)
