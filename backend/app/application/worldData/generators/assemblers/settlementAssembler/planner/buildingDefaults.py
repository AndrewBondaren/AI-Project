"""Build packing catalogs from the world template snapshot (B3).

No filesystem stdlib, no world registry-column reads, no global ``list_all``
— the snapshot loader already resolved membership and prepared bodies at the
async boundary.
"""

from __future__ import annotations

from app.application.worldData.templateContracts import WorldTemplateSnapshot
from app.dataModel.locations.structure.building.buildingCatalog import (
    BuildingCatalog,
    CatalogPlot,
)
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog


def structure_catalog_from_snapshot(snapshot: WorldTemplateSnapshot) -> StructureCatalog:
    """UID-keyed structure view of the world's membership (model A bodies)."""
    return StructureCatalog.from_entries(
        {uid: entry.body for uid, entry in snapshot.structures.items()}
    )


def building_catalog_from_snapshot(snapshot: WorldTemplateSnapshot) -> BuildingCatalog:
    """Plot candidates of the world, keyed by member ``template_uid``."""
    return BuildingCatalog(
        (CatalogPlot(uid, entry.body) for uid, entry in snapshot.plots.items()),
        structures=structure_catalog_from_snapshot(snapshot),
    )
