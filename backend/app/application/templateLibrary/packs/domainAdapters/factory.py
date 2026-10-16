"""Container seam — one domain adapter per supported ``library_kind``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.templateLibrary.packs.domainAdapters.building import (
    BuildingPackAdapter,
)
from app.application.templateLibrary.packs.domainAdapters.relief import (
    ReliefPackAdapter,
)
from app.application.templateLibrary.packs.domainAdapters.structure import (
    StructurePackAdapter,
)
from app.ids import LibraryKind
from app.application.templateLibrary.packs.domainAdapters.plot import PlotPackAdapter

if TYPE_CHECKING:
    from app.application.templateLibrary.plotTemplateLibraryService import PlotTemplateLibraryService
    from app.application.templateLibrary.buildingTemplateLibraryService import (
        BuildingTemplateLibraryService,
    )
    from app.application.templateLibrary.packs.domainAdapters.contract import (
        PackDomainAdapter,
    )
    from app.application.templateLibrary.reliefTemplateLibraryService import (
        ReliefTemplateLibraryService,
    )
    from app.application.templateLibrary.reliefWorldImportService import (
        ReliefWorldImportService,
    )
    from app.application.templateLibrary.structureTemplateLibraryService import (
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
