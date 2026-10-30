"""Ordered runtime request; domain payloads are never interpreted here."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.values import FormatVersion
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef


class PatchSet[S: DomainSection](BaseModel):
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

    @model_validator(mode="after")
    def coherent_request(self) -> Self:
        if self.expected_world.world_uid != self.world_uid:
            raise ValueError("publication belongs to another world")
        if self.expected_world.pack_hash is None:
            raise ValueError("runtime request requires a pack")
        players = tuple(player.player_uid for player in self.expected_players)
        if len(set(players)) != len(players):
            raise ValueError("duplicate player expectation")
        keys = tuple(section.header.key for section in self.sections)
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate section key")
        return self
