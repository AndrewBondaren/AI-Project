"""Side-effect imports register BuildingAssembler implementations."""

from app.application.worldData.generators.assemblers.buildingAssembler import (
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
