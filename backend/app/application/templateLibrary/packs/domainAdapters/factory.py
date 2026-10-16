"""Container seam — one domain adapter per supported ``library_kind``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.worldData.libraryPacks.domainAdapters.building import (
    BuildingPackAdapter,
)
from app.application.worldData.libraryPacks.domainAdapters.relief import (
    ReliefPackAdapter,
)
from app.application.worldData.libraryPacks.domainAdapters.structure import (
    StructurePackAdapter,
)
from app.ids import LibraryKind
from app.application.worldData.libraryPacks.domainAdapters.plot import PlotPackAdapter

if TYPE_CHECKING:
    from app.application.worldData.plotTemplateLibraryService import PlotTemplateLibraryService
    from app.application.worldData.buildingTemplateLibraryService import (
        BuildingTemplateLibraryService,
    )
    from app.application.worldData.libraryPacks.domainAdapters.contract import (
        PackDomainAdapter,
    )
    from app.application.worldData.reliefTemplateLibraryService import (
        ReliefTemplateLibraryService,
    )
    from app.application.worldData.reliefWorldImportService import (
        ReliefWorldImportService,
    )
    from app.application.worldData.structureTemplateLibraryService import (
        StructureTemplateLibraryService,
    )


def build_pack_domain_adapters(
    *,
    relief_library: ReliefTemplateLibraryService,
    structure_library: StructureTemplateLibraryService,
    building_library: BuildingTemplateLibraryService,
    plot_library: PlotTemplateLibraryService,
    relief_world_import: ReliefWorldImportService | None = None,
) -> dict[LibraryKind, PackDomainAdapter]:
    """Container seam — one adapter per supported ``library_kind``."""
    return {
        LibraryKind.PLOT_TEMPLATES: PlotPackAdapter(plot_library),
        LibraryKind.RELIEF_TEMPLATES: ReliefPackAdapter(
            relief_library, relief_world_import
        ),
        LibraryKind.STRUCTURE_TEMPLATES: StructurePackAdapter(structure_library),
        LibraryKind.BUILDING_TEMPLATES: BuildingPackAdapter(building_library),
    }
