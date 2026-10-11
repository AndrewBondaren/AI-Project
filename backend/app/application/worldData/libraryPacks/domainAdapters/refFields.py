"""Declared building-to-structure fields; no arbitrary JSON UUID scanning."""
from app.application.jsonValidation.resolve import resolve_model
from app.application.worldData.libraryPacks.lifecycleContracts import MemberRef
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.ids import LibraryKind


def structure_refs(raw: dict, consumer: str) -> tuple[MemberRef, ...]:
    if not any(raw.get(key) for key in ('main_building', 'secondary_buildings')):
        return ()
    plot = resolve_model(PlotLayoutTemplate, raw, label=consumer)
    refs = []
    if plot.main_building is not None:
        refs.append(MemberRef(LibraryKind.STRUCTURE_TEMPLATES.value,
                              str(plot.main_building.structure), consumer, 'main_building.structure'))
    refs.extend(MemberRef(LibraryKind.STRUCTURE_TEMPLATES.value, str(item.structure),
                          consumer, f'secondary_buildings[{i}].structure')
                for i, item in enumerate(plot.secondary_buildings or []))
    return tuple(refs)
