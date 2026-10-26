"""Shared test seam: canonical-pack catalogs without SQL.

B3 identity is the library member ``template_uid``; tests that need "the
engine default catalog" hydrate the declared canonical fixtures under the
same member uids the canonical attach writes to SQL.
"""

from __future__ import annotations

from pathlib import Path

from app.application.templateLibrary.structureTemplateFsImport import load_structure_stdlib
from app.dataModel.libraryPacks.defaultPacks import canonical_member_uid
from app.dataModel.locations.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.structure.building.worldBuildingLayoutDefaults import canonical_defaults
from app.ids import LibraryKind

STRUCTURES_ROOT = Path(__file__).resolve().parents[2] / "structures_templates"


def canonical_structure_catalog() -> StructureCatalog:
    return StructureCatalog(load_structure_stdlib(STRUCTURES_ROOT))


def canonical_plot_uid(local_uid: str) -> str:
    return canonical_member_uid(LibraryKind.PLOT_TEMPLATES, local_uid)


def canonical_building_catalog() -> BuildingCatalog:
    return BuildingCatalog.from_entries(
        {
            canonical_plot_uid(layout.system_name): layout
            for layout in canonical_defaults()
        },
        structures=canonical_structure_catalog(),
    )
