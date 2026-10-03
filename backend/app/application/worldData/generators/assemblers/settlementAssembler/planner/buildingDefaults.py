"""Builtin building layouts when world.building_template_registry is empty."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from app.application.jsonValidation.worldRow import world_building_layout_overrides
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_warning,
)
from app.dataModel.locations.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.locations.structure.building.plotLayoutTemplate import (
    PlotLayoutTemplate,
    plot_type_defaulted,
)
from app.dataModel.locations.structure.building.structureCatalog import StructureCatalog
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.building.worldBuildingLayoutDefaults import canonical_defaults
from app.db.models.structureTemplate import StructureTemplateRow

logger = logging.getLogger(__name__)


def _warn_plot_type_defaulted(plot: PlotLayoutTemplate) -> None:
    packing_warning(
        PackingStep.CACHE,
        district="defaults",
        system_name=plot.system_name,
        reason=PackingReason.PLOT_TYPE_DEFAULTED,
    )


def assemble_structure_catalog(
    library_rows: Iterable[StructureTemplateRow] = (),
) -> StructureCatalog:
    """FS stdlib ⊕ SQL library rows (SQL wins on the same uid)."""
    from app.application.worldData.structureTemplateFsImport import (
        load_structure_stdlib,
    )

    by_uid: dict[str, StructureTemplate] = {
        str(structure.system_name): structure
        for structure in load_structure_stdlib()
    }
    for row in library_rows:
        data = row.data if isinstance(row.data, dict) else {}
        try:
            structure = StructureTemplate.model_validate(data)
        except Exception as exc:
            logger.warning(
                "structure | catalog skip invalid row uid=%s err=%s",
                row.template_uid,
                exc,
            )
            continue
        by_uid[str(structure.system_name)] = structure
    return StructureCatalog(by_uid.values())


def assemble_building_catalog(
    world: Any,
    library_layouts: Iterable[PlotLayoutTemplate] = (),
    structures: StructureCatalog | None = None,
) -> BuildingCatalog:
    """builtins ⊕ SQL library layouts ⊕ world plot-shaped rows (later wins)."""
    ordered: list[PlotLayoutTemplate] = []
    for plot in canonical_defaults():
        if plot_type_defaulted(plot):
            _warn_plot_type_defaulted(plot)
        ordered.append(plot)
    ordered.extend(library_layouts)
    ordered.extend(world_building_layout_overrides(world))
    return BuildingCatalog.from_layouts(
        ordered,
        structures if structures is not None else assemble_structure_catalog(),
    )


def merge_building_registry(world: Any) -> list[PlotLayoutTemplate]:
    """World plot-shaped rows + engine builtins (world wins on name collision)."""
    return list(assemble_building_catalog(world).layouts)


def lookup_building_template(
    world: Any,
    system_name: str,
    catalog: BuildingCatalog | None = None,
) -> PlotLayoutTemplate | None:
    if catalog is not None:
        return catalog.by_system_name(system_name)
    return assemble_building_catalog(world).by_system_name(system_name)
