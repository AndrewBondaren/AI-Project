"""Typed world library pointers; empty is a valid unbound library."""
from typing import ClassVar
from pydantic import RootModel
from app.dataModel.races.raceTemplateRegistryEntry import RaceTemplateRegistryEntry


class WorldRaceTemplateRegistry(RootModel[list[RaceTemplateRegistryEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLDRACETEMPLATEREGISTRY"

    @classmethod
    def canonical_defaults(cls):
        return cls([])
