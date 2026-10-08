"""Typed world library pointers; empty is a valid unbound library."""
from typing import ClassVar
from pydantic import RootModel
from app.dataModel.perks.perkTemplateRegistryEntry import PerkTemplateRegistryEntry


class WorldPerkTemplateRegistry(RootModel[list[PerkTemplateRegistryEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLDPERKTEMPLATEREGISTRY"

    @classmethod
    def canonical_defaults(cls):
        return cls([])
