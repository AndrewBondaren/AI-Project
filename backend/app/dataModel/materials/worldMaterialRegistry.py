"""Root POJO for `worlds.material_registry` JSON array."""

from __future__ import annotations

from typing import ClassVar

from pydantic import RootModel

from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.dataModel.materials.enums.materialCategory import MaterialCategory

# fixtures/world_template.json
_CANONICAL_ENTRIES: tuple[MaterialRegistryEntry, ...] = (
    MaterialRegistryEntry(
        system_material="earth",
        display_name="Земля",
        material_category=MaterialCategory.SOLID,
        tags=["raw"],
        economic_tier="poor",
        hardness=1,
        density=150,
    ),
    MaterialRegistryEntry(
        system_material="stone",
        display_name="Камень",
        material_category=MaterialCategory.SOLID,
        tags=["mineral"],
        economic_tier="standard",
        hardness=3,
        density=250,
    ),
    MaterialRegistryEntry(
        system_material="wood",
        display_name="Дерево",
        material_category=MaterialCategory.SOLID,
        tags=["organic"],
        economic_tier="basic",
        hardness=2,
        density=60,
        flammable=True,
    ),
    MaterialRegistryEntry(
        system_material="water",
        display_name="Вода",
        material_category=MaterialCategory.LIQUID,
        density=100,
        freezable=True,
        corrodible=False,
    ),
    MaterialRegistryEntry(
        system_material="sand",
        display_name="Песок",
        material_category=MaterialCategory.SOLID,
        tags=["mineral"],
        economic_tier="basic",
        hardness=1,
        density=160,
    ),
    MaterialRegistryEntry(
        system_material="ice",
        display_name="Лёд",
        material_category=MaterialCategory.SOLID,
        hardness=1,
        density=90,
    ),
)

# tz_locations.md § material_registry — engine-complete slice
_ENGINE_ENTRIES: tuple[MaterialRegistryEntry, ...] = (
    MaterialRegistryEntry(
        system_material="stone",
        display_name="Камень",
        material_category=MaterialCategory.SOLID,
        tags=["construction", "mineral"],
        use_type=["wall", "floor", "column"],
        economic_tier="standard",
        hardness=3,
        density=250,
        structural_strength=0.8,
        mineable=True,
    ),
    MaterialRegistryEntry(
        system_material="wood",
        display_name="Дерево",
        material_category=MaterialCategory.SOLID,
        tags=["construction", "organic"],
        use_type=["wall", "floor", "door", "railing"],
        economic_tier="basic",
        hardness=2,
        density=60,
        structural_strength=0.3,
        flammable=True,
    ),
    MaterialRegistryEntry(
        system_material="iron",
        display_name="Железо",
        material_category=MaterialCategory.SOLID,
        tags=["metal", "mineral"],
        use_type=["wall", "door", "gate", "railing"],
        economic_tier="standard",
        hardness=4,
        density=800,
        structural_strength=0.9,
        meltable=True,
    ),
    MaterialRegistryEntry(
        system_material="earth",
        display_name="Земля",
        material_category=MaterialCategory.SOLID,
        tags=["raw", "mineral"],
        use_type=["floor"],
        economic_tier="poor",
        hardness=1,
        density=150,
        structural_strength=0.2,
        mineable=True,
    ),
    MaterialRegistryEntry(
        system_material="crystal",
        display_name="Кристалл",
        material_category=MaterialCategory.SOLID,
        tags=["mineral", "magic"],
        use_type=["wall", "floor"],
        economic_tier="premium",
        hardness=3,
        density=260,
        structural_strength=0.4,
        corrodible=False,
        transparent=True,
    ),
    MaterialRegistryEntry(
        system_material="water",
        display_name="Вода",
        material_category=MaterialCategory.LIQUID,
        density=100,
        freezable=True,
        corrodible=False,
    ),
    MaterialRegistryEntry(
        system_material="lava",
        display_name="Лава",
        material_category=MaterialCategory.LIQUID,
        density=270,
        corrodible=False,
        temp_damage=True,
    ),
    MaterialRegistryEntry(
        system_material="air",
        display_name="Воздух",
        material_category=MaterialCategory.GAS,
        density=1,
        corrodible=False,
    ),
    MaterialRegistryEntry(
        system_material="smoke",
        display_name="Дым",
        material_category=MaterialCategory.GAS,
        density=2,
        corrodible=False,
        vision_block=True,
    ),
    MaterialRegistryEntry(
        system_material="toxic_gas",
        display_name="Токсичный газ",
        material_category=MaterialCategory.GAS,
        density=3,
        flammable=True,
        corrodible=False,
        temp_damage=True,
        vision_block=True,
    ),
)


class WorldMaterialRegistry(RootModel[list[MaterialRegistryEntry]]):
    SCHEMA_ID: ClassVar[str] = "SCH-WORLD-MATERIAL"
    """Root POJO for `worlds.material_registry`. Wire shape: JSON array."""

    root: list[MaterialRegistryEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldMaterialRegistry:
        """Fixture slice — fixtures/world_template.json."""
        return cls(list(_CANONICAL_ENTRIES))

    @classmethod
    def canonical_engine(cls) -> WorldMaterialRegistry:
        """Engine slice incl. air/gas — tz_locations.md § material_registry."""
        return cls(list(_ENGINE_ENTRIES))

    def entry_for(self, system_material: str) -> MaterialRegistryEntry | None:
        for entry in self.root:
            if entry.system_material == system_material:
                return entry
        return None

    def liquid_keys(self) -> frozenset[str]:
        return frozenset(
            e.system_material for e in self.root if e.material_category.is_liquid()
        )
