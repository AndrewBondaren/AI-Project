"""Side-effect imports register StructureAssembler implementations."""

from app.application.worldData.generators.assemblers.structureAssembler import (
    buildingAssembler,
    resourceExtractionAssembler,
    ruinsAssembler,
    vastHullAssembler,
)

__all__ = [
    "buildingAssembler",
    "resourceExtractionAssembler",
    "ruinsAssembler",
    "vastHullAssembler",
]
