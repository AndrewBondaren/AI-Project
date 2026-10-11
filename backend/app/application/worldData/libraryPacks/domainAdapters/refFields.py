"""One declaration of nested reference fields for extraction and remap."""
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from app.application.jsonValidation.resolve import resolve_model
from app.application.jsonValidation.worldRow import relief_pick_policy
from app.application.worldData.libraryPacks.domainAdapters.contract import _POINTER_UID_FIELD
from app.application.worldData.libraryPacks.lifecycleContracts import MemberRef
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy, WorldReliefPickPolicy
from app.db.models.world import World
from app.ids import LibraryKind


@dataclass(frozen=True)
class NestedRefField:
    parent_field: str
    uid_field: str
    library_kind: LibraryKind
    repeated: bool = False

    def entries(self, model: BaseModel) -> Iterator[tuple[str, BaseModel]]:
        value = getattr(model, self.parent_field)
        if self.repeated:
            yield from ((f'{self.parent_field}[{i}]', entry) for i, entry in enumerate(value))
        elif value is not None:
            yield self.parent_field, value

    def references(self, model: BaseModel, consumer: str, prefix: str = '') -> tuple[MemberRef, ...]:
        return tuple(MemberRef(self.library_kind.value, str(uid), consumer,
                               f'{prefix}{path}.{self.uid_field}')
                     for path, entry in self.entries(model)
                     if (uid := getattr(entry, self.uid_field)))

    def remap(self, model: BaseModel, uid_map: Mapping[str, str]) -> BaseModel | list[BaseModel] | None:
        entries, changed = [], False
        for _, entry in self.entries(model):
            remapped = self.remap_entry(entry, uid_map)
            changed = changed or remapped is not entry
            entries.append(remapped)
        if not changed:
            return None
        return entries if self.repeated else entries[0]

    def remap_entry(self, entry: BaseModel, uid_map: Mapping[str, str]) -> BaseModel:
        uid = getattr(entry, self.uid_field)
        replacement = uid_map.get(str(uid)) if uid is not None else None
        return (entry.model_copy(update={self.uid_field: replacement})
                if replacement is not None and replacement != str(uid) else entry)


STRUCTURE_REF_FIELDS = (
    NestedRefField('main_building', 'structure', LibraryKind.STRUCTURE_TEMPLATES),
    NestedRefField('secondary_buildings', 'structure', LibraryKind.STRUCTURE_TEMPLATES, repeated=True),
)

_RELIEF_DEFAULTS = WorldReliefPickPolicy.canonical_defaults()
RELIEF_POLICY_REF_FIELDS = tuple(
    NestedRefField(name, 'default_template_uid', LibraryKind.RELIEF_TEMPLATES)
    for name in WorldReliefPickPolicy.model_fields
    if isinstance(getattr(_RELIEF_DEFAULTS, name), ReliefContextPickPolicy)
)


def structure_ref_model(raw: dict, *, label: str) -> PlotLayoutTemplate | None:
    if (not isinstance(raw, dict) or _POINTER_UID_FIELD in raw
            or not any(raw.get(field.parent_field) for field in STRUCTURE_REF_FIELDS)):
        return None
    return resolve_model(PlotLayoutTemplate, raw, label=label)


def structure_refs(raw: dict, consumer: str) -> tuple[MemberRef, ...]:
    plot = structure_ref_model(raw, label=consumer)
    return (() if plot is None else tuple(ref for field in STRUCTURE_REF_FIELDS
                                          for ref in field.references(plot, consumer)))


def relief_policy_refs(world: World) -> tuple[MemberRef, ...]:
    policy = relief_pick_policy(world)
    return tuple(ref for field in RELIEF_POLICY_REF_FIELDS
                 for ref in field.references(policy, f'world:{world.world_uid}', 'relief_pick_policy.'))
