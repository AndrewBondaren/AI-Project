"""One declaration of nested reference fields for extraction and remap."""
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from app.application.jsonValidation.resolve import resolve_model
from app.application.jsonValidation.worldRow import relief_pick_policy
from app.application.worldData.libraryPacks.domainAdapters.contract import _POINTER_UID_FIELD
from app.application.worldData.libraryPacks.lifecycleContracts import MemberRef
from app.dataModel.locations.structure.building.plotLayoutTemplate import PlotLayoutTemplate
from app.dataModel.locations.structure.building.buildingTemplate import BuildingTemplate
from app.dataModel.terrain.relief.worldReliefPickPolicy import ReliefContextPickPolicy, WorldReliefPickPolicy
from app.db.models.world import World
from app.ids import LibraryKind


@dataclass(frozen=True)
class DirectRefField:
    uid_field: str
    library_kind: LibraryKind

    def references(self, model: BaseModel, consumer: str, prefix: str = '') -> tuple[MemberRef, ...]:
        uid = getattr(model, self.uid_field)
        return (() if not uid else
                (MemberRef(self.library_kind.value, str(uid), consumer, prefix + self.uid_field),))

    def remap_entry(self, entry: BaseModel, uid_map: Mapping[str, str]) -> BaseModel:
        uid = getattr(entry, self.uid_field)
        replacement = uid_map.get(str(uid)) if uid is not None else None
        return (entry.model_copy(update={self.uid_field: replacement})
                if replacement is not None and replacement != str(uid) else entry)


BUILDING_STRUCTURE_REF = DirectRefField('structure', LibraryKind.STRUCTURE_TEMPLATES)


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
        return tuple(ref
                     for path, entry in self.entries(model)
                     for ref in DirectRefField(self.uid_field, self.library_kind).references(
                         entry, consumer, f'{prefix}{path}.'))

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
        return DirectRefField(self.uid_field, self.library_kind).remap_entry(entry, uid_map)


STRUCTURE_REF_FIELDS = (
    NestedRefField('main_building', BUILDING_STRUCTURE_REF.uid_field, BUILDING_STRUCTURE_REF.library_kind),
    NestedRefField('secondary_buildings', BUILDING_STRUCTURE_REF.uid_field,
                   BUILDING_STRUCTURE_REF.library_kind, repeated=True),
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


def template_body_refs(kind: LibraryKind, body: BaseModel, consumer: str) -> tuple[MemberRef, ...]:
    """Target body declarations; inline buildings are not separate member refs.

    Declared refs only target ``STRUCTURE_TEMPLATES`` — the snapshot loader
    drops referrers of absent bodies in a single pass, closed because
    structure bodies declare no refs of their own. Keep this invariant.
    """
    if kind == LibraryKind.PLOT_TEMPLATES and isinstance(body, PlotLayoutTemplate):
        refs = tuple(ref for field in STRUCTURE_REF_FIELDS for ref in field.references(body, consumer))
    elif kind == LibraryKind.BUILDING_TEMPLATES and isinstance(body, BuildingTemplate):
        refs = BUILDING_STRUCTURE_REF.references(body, consumer)
    else:
        refs = ()
    assert all(ref.library_kind == LibraryKind.STRUCTURE_TEMPLATES.value for ref in refs)
    return refs


def remap_template_body(kind: LibraryKind, body: BaseModel, uid_map: Mapping[str, str]) -> BaseModel:
    """Read/remap share exactly the same declared fields, without mutating input."""
    if kind == LibraryKind.BUILDING_TEMPLATES and isinstance(body, BuildingTemplate):
        return BUILDING_STRUCTURE_REF.remap_entry(body, uid_map)
    if kind == LibraryKind.PLOT_TEMPLATES and isinstance(body, PlotLayoutTemplate):
        update = {field.parent_field: value for field in STRUCTURE_REF_FIELDS
                  if (value := field.remap(body, uid_map)) is not None}
        return body.model_copy(update=update) if update else body
    return body


def relief_policy_refs(world: World) -> tuple[MemberRef, ...]:
    policy = relief_pick_policy(world)
    return tuple(ref for field in RELIEF_POLICY_REF_FIELDS
                 for ref in field.references(policy, f'world:{world.world_uid}', 'relief_pick_policy.'))


# Persisted location refs (5b/B4): a generated building stores the applied
# plot member in ``system_template_uid`` and the structure actually
# materialized in ``system_structure_template_uid``. ``system_template_uid``
# is polymorphic by caller contract, so the ref adopts the resolved member's
# kind — names are never reinterpreted as identity.
LOCATION_TEMPLATE_REF_FIELDS: tuple[str, ...] = (
    'system_template_uid',
    'system_structure_template_uid',
)


def named_location_template_refs(rows, members) -> tuple[MemberRef, ...]:
    """Usage refs of persisted NamedLocation rows against the member catalog.

    Refs targeting members absent from the given catalog are not usages of
    this scope — dangling identity is diagnosed by the ref checks, not here.
    """
    refs = []
    for row in rows:
        for field in LOCATION_TEMPLATE_REF_FIELDS:
            uid = getattr(row, field, None)
            member = members.get(uid) if isinstance(uid, str) else None
            if member is not None:
                refs.append(MemberRef(member.library_kind, uid,
                                      f'named_location:{row.location_uid}', field))
    return tuple(refs)
