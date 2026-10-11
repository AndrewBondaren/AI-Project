"""One membership-scoped reference index (TZ packs §1.2)."""
from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.libraryPacks.defaults import default_pack_uids
from app.application.worldData.libraryPacks.lifecycleContracts import MemberRef
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind


@dataclass
class CatalogSnapshot:
    members: dict[str, LibraryPackMemberRow]
    bodies: dict[str, dict]
    source_files: dict[str, str | None]


async def load_catalog(scope, world_uid: str | None) -> CatalogSnapshot:
    packs = (await scope.packs.list_world_owned(world_uid) if world_uid is not None
             else await scope.packs.list_engine())
    uids = sorted({p.pack_uid for p in packs} | set(default_pack_uids()))
    members = await scope.members.list_by_packs(uids)
    bodies, files = {}, {}
    for member in members:
        found = await scope.adapter_for(LibraryKind(member.library_kind)).read_body_row(member.template_uid)
        if found is None:
            raise LibraryPackValidationError(f"member '{member.template_uid}' has no body")
        bodies[member.template_uid], files[member.template_uid] = found
    return CatalogSnapshot({m.template_uid: m for m in members}, bodies, files)


def collect_refs(scope, catalog: CatalogSnapshot, world=None) -> tuple[MemberRef, ...]:
    refs = []
    for uid, member in catalog.members.items():
        refs.extend(scope.adapter_for(LibraryKind(member.library_kind)).body_refs(catalog.bodies[uid], uid))
    if world is not None:
        for adapter in scope.adapters.values():
            refs.extend(adapter.world_refs(world))
    return tuple(refs)


def reference_index(refs, members):
    index, diagnostics = {}, []
    for ref in refs:
        member = members.get(ref.template_uid)
        if member is None or member.library_kind != ref.library_kind:
            diagnostics.append(f"unavailable {ref.library_kind}:{ref.template_uid} at {ref.reason}")
        else:
            index.setdefault(ref.template_uid, []).append(ref.reason)
    return ({uid: tuple(sorted(set(reasons))) for uid, reasons in index.items()},
            tuple(sorted(set(diagnostics))))


def pin_index(world, members):
    if world is None:
        return {}
    from app.dataModel.libraryPacks.libraryPinEntry import LibraryPinEntry
    result = {}
    for raw in world.library_pins or []:
        pin = LibraryPinEntry.model_validate(raw)
        member = members.get(pin.template_uid)
        if member is not None and member.library_kind == pin.library_kind:
            result[pin.template_uid] = (f"world:{world.world_uid}:library_pins",)
    return result


async def member_usages(scope, member, world):
    catalog = await load_catalog(scope, None if world is None else world.world_uid)
    refs = collect_refs(scope, catalog, world)
    index, _ = reference_index(refs, catalog.members)
    return list(index.get(member.template_uid, ())) + list(pin_index(world, catalog.members).get(member.template_uid, ()))
