"""Read-only typed library snapshots; no I/O, resolution or generation.

TZ: tz_domain_template_libraries.md §1/3/5. Availability and cross-domain
reference checks belong to the loader/adapters (later implementation steps).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from uuid import UUID

from pydantic import BaseModel

from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate
from app.dataModel.locations.structure.building.plotTemplate import PlotTemplate
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


@dataclass(frozen=True)
class TemplateEntry[T: BaseModel]:
    """Catalog identity and owning pack, independent of the body name."""

    template_uid: str
    pack_uid: str
    body: T

    def __post_init__(self) -> None:
        for name in ("template_uid", "pack_uid"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise ValueError(f"{name} must be a UUID string")
            try:
                parsed = UUID(value)
            except ValueError as exc:
                raise ValueError(f"{name} must be a UUID string") from exc
            if str(parsed) != value:
                raise ValueError(f"{name} must be a canonical UUID string")
        if not isinstance(self.body, BaseModel):
            raise TypeError("template body must be a prepared POJO")


def _readonly_index[T: BaseModel](
    entries: Mapping[str, TemplateEntry[T]], model: type[T],
) -> Mapping[str, TemplateEntry[T]]:
    indexed = {}
    for uid, entry in sorted(entries.items()):
        if not isinstance(entry, TemplateEntry) or entry.template_uid != uid:
            raise ValueError("snapshot key must match the entry template_uid")
        if not isinstance(entry.body, model):
            raise TypeError(f"snapshot requires {model.__name__} bodies")
        if isinstance(entry.body, StructureTemplate) and str(entry.body.system_name) != uid:
            raise ValueError("structure body identity must match template_uid (model A)")
        indexed[uid] = entry
    return MappingProxyType(indexed)


@dataclass(frozen=True)
class WorldTemplateSnapshot:
    """One world's prepared graph, indexed and ordered by member UID."""

    world_uid: str
    plots: Mapping[str, TemplateEntry[PlotTemplate]] = field(default_factory=dict)
    buildings: Mapping[str, TemplateEntry[BuildingTemplate]] = field(default_factory=dict)
    structures: Mapping[str, TemplateEntry[StructureTemplate]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        seen = set()
        for name, model in (
            ("plots", PlotTemplate), ("buildings", BuildingTemplate),
            ("structures", StructureTemplate),
        ):
            index = _readonly_index(getattr(self, name), model)
            if seen.intersection(index):
                raise ValueError("one template_uid cannot belong to multiple domains")
            seen.update(index)
            object.__setattr__(self, name, index)


@dataclass(frozen=True)
class ReliefTemplateSnapshot:
    """Separate relief-domain view; conditions/pick policy stay with the domain."""

    world_uid: str
    templates: Mapping[str, TemplateEntry[ReliefTemplate]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "templates", _readonly_index(self.templates, ReliefTemplate))
