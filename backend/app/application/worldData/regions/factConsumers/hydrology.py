"""Observed open-water coverage, without inventing groundwater or flood history."""

from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import HydroFacts
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def contribute(context: FactConsumerContext) -> HydroFacts | None:
    if context.surface is None or not context.cells or not context.surface.coarse_hydro:
        return None
    cells = set(context.cells)
    observed = [context.surface.coarse_hydro.get(cell) for cell in cells]
    if any(value is not None and not isinstance(value, MapCellHydrology) for value in observed):
        return None
    # The prepared hydro index is sparse: missing entries are dry within its surface extent.
    if any(cell not in context.surface.coarse_surface_z for cell in cells):
        return None
    water = sum(value is not None and value.role is not None and value.role.is_open_water_role()
                for value in observed)
    return HydroFacts(open_water_fraction=water / len(cells))
