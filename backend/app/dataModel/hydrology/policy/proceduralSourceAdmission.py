"""Frozen policy bindings for a native source preparation run; no water geometry."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.sources.waterDesignSource import ProceduralSource
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput


class ResolvedProceduralSource(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    source: ProceduralSource
    context: ResolvedWaterGenerationContext
    generation: HydrologyGenerationDecision
    admission: PlacementAdmissionInput
    source_path: tuple[str | int, ...]


class ProceduralSourceAdmissions(BaseModel, frozen=True):
    model_config = ResolvedProceduralSource.model_config

    world_context: ResolvedWaterGenerationContext
    sources: tuple[ResolvedProceduralSource, ...]
    batch: PlacementBatchV2
    water_intents: tuple[PlacementIntent, ...]
