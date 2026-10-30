"""Frozen policy bindings for a native source preparation run; no water geometry."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.sources.waterDesignSource import ProceduralSource
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.intent import PlacementIdentity, PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader


class ResolvedProceduralSource(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    source: ProceduralSource
    context: ResolvedWaterGenerationContext
    generation: HydrologyGenerationDecision
    placement_identity: PlacementIdentity
    source_path: tuple[str | int, ...]


class ProceduralSourceAdmissions(BaseModel, frozen=True):
    model_config = ResolvedProceduralSource.model_config

    world_context: ResolvedWaterGenerationContext
    sources: tuple[ResolvedProceduralSource, ...]
    batch: PlacementBatchV2
    water_intents: tuple[PlacementIntent, ...]

    def admission_for(self, identity: PlacementIdentity) -> PlacementAdmissionInput:
        """Read the canonical initial admission; session owns subsequent decisions."""
        for admission in self.batch.objects:
            if admission.header.identity == identity:
                return admission
        raise ValueError("native binding must reference an admission in the joint batch")

    @model_validator(mode="after")
    def coherent_bindings(self) -> Self:
        identities = tuple(binding.placement_identity for binding in self.sources)
        if len({identity.region_uid for identity in identities}) != len(identities):
            raise ValueError("duplicate native placement binding")
        if len({binding.source.value.source_uid for binding in self.sources}) != len(self.sources):
            raise ValueError("duplicate native source binding")
        intents = {intent.identity.region_uid: intent for intent in self.water_intents}
        if len(intents) != len(self.water_intents) or intents.keys() != {i.region_uid for i in identities}:
            raise ValueError("native bindings require exactly one original water intent each")
        for binding in self.sources:
            identity = binding.placement_identity
            if identity.world_uid != self.batch.world_uid or identity.source_uid != binding.source.value.source_uid:
                raise ValueError("native placement identity must match source and batch world")
            admission = self.admission_for(identity)
            if PlacementHeader.from_intent(intents[identity.region_uid]) != admission.header:
                raise ValueError("native admission header must be projected from its original intent")
        return self
