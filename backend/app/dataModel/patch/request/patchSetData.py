"""Shared structure, without relations between fields of the complete batch.

The two child roles share these fields by user decision (2026-11-18),
documented in tz_patch_system.md: input admits relation failures, result does not.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.values import FormatVersion
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef


class PatchSetData[S: DomainSection](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    format_version: FormatVersion
    operation_id: EntityUid
    preparation_fingerprint: RevisionHex
    world_uid: EntityUid
    timeline_id: EntityUid
    turn_id: Annotated[StrictInt, Field(ge=1)]
    expected_world: WorldPublicationRef
    expected_players: tuple[PlayerHeadExpectation, ...]
    sections: tuple[S, ...]
