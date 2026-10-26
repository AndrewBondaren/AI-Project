"""Observed open-water coverage, without inventing groundwater or flood history."""

from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import HydroFacts
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def contribute(context: FactConsumerContext) -> HydroFacts | None:
    if context.hydrology is not None:
        hydro = context.hydrology.coarse_hydro
        surface_z = context.hydrology.coarse_surface_z
    else:
        hydro, surface_z = context.hydro, context.surface_z
        if context.surface is not None:
            if hydro is None:
                hydro = context.surface.coarse_hydro
            if surface_z is None:
                surface_z = context.surface.coarse_surface_z
    if not context.cells or not hydro or surface_z is None:
        return None
    cells = set(context.cells)
    observed = [hydro.get(cell) for cell in cells]
    if any(value is not None and not isinstance(value, MapCellHydrology) for value in observed):
        return None
    # The prepared hydro index is sparse: missing entries are dry within its surface extent.
    if any(cell not in surface_z for cell in cells):
        return None
    water = sum(value is not None and value.role is not None and value.role.is_open_water_role()
                for value in observed)
    return HydroFacts(open_water_fraction=water / len(cells))
