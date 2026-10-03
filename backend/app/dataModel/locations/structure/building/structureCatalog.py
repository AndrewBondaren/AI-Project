"""Resolvable snapshot of shared ``StructureTemplate`` geometry (5o split).

FS stdlib ⊕ SQL library rows — caller hydrates, then passes this into the
building catalog / assemblers. Key = ``system_name`` (uuid, model A).
"""

from __future__ import annotations

from collections.abc import Iterable

from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.buildingPurpose import (
    BuildingPurpose,
    BuildingPurposeFamily,
)


class StructureCatalog:
    """``structures`` unique by ``system_name`` — duplicates are rejected."""

    def __init__(self, structures: Iterable[StructureTemplate]) -> None:
        self._by_uid: dict[str, StructureTemplate] = {}
        for structure in structures:
            uid = str(structure.system_name)
            existing = self._by_uid.get(uid)
            if existing is not None:
                raise ValueError(
                    "StructureCatalog: duplicate system_name "
                    f"{uid} ({existing.display_name!r} vs "
                    f"{structure.display_name!r})"
                )
            self._by_uid[uid] = structure

    @classmethod
    def empty(cls) -> StructureCatalog:
        return cls(())

    @property
    def structures(self) -> tuple[StructureTemplate, ...]:
        return tuple(self._by_uid.values())

    def resolve(self, uid: str) -> StructureTemplate | None:
        return self._by_uid.get(str(uid))

    def leaves_of(self, plot: PlotLayoutTemplate) -> tuple[BuildingPurpose, ...]:
        """Purpose leaves of the plot's main building; virtual ``plaza`` for a
        public-family plot with no building (§4.2)."""
        body = plot.main_building
        if body is None:
            if plot.plot_type == BuildingPurposeFamily.PUBLIC:
                return (BuildingPurpose.PLAZA,)
            return ()
        structure = self.resolve(str(body.structure))
        if structure is None:
            return ()
        return tuple(structure.structure_types)
