"""``instantiate_pack`` / ``copy_pack`` — the TZ §2 snapshot remap job.

A copy+remap of the whole pack (partial instances do not exist, §1):
a new ``pack_uid`` under the new owner, members minted by the central
formula, ``source_template_uid``/``source_pack_uid`` provenance,
internal body refs rewritten, refs to other packs untouched. The source
pack is never modified.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from app.application.worldData.libraryPacks.defaults import is_default_pack_uid
from app.application.worldData.libraryPacks.domainAdapters import RemappedMember
from app.application.worldData.libraryPacks.errors import (
    LibraryPackConflictError,
    LibraryPackValidationError,
)
from app.application.worldData.libraryPacks.packOps import _PackOps
from app.application.worldData.libraryPacks.packResults import PackRemapResult
from app.application.worldData.libraryPacks.lifecycleContracts import ReinstantiatePreview
from app.application.worldData.libraryPacks.packScope import _PackScope
from app.application.worldData.libraryPacks.packIdentity import (
    instance_system_name as _instance_system_name, published_system_name,
)
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackDependency import LibraryPackDependencyRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.db.models.world import World
from app.ids import LibraryKind, remapped_library_uid

logger = logging.getLogger(__name__)


def _uid_map_for(
    members: Iterable[LibraryPackMemberRow], pack_uid: str
) -> dict[str, str]:
    """source member uid → member uid under ``pack_uid`` (central formula)."""
    return {
        m.template_uid: remapped_library_uid(
            LibraryKind(m.library_kind), source_template_uid=m.template_uid, target_pack_uid=pack_uid
        )
        for m in members
    }


class _RemapOps:
    """``instantiate_pack`` / ``copy_pack`` — the TZ §2 snapshot remap job."""

    def __init__(self, scope: _PackScope, pack_ops: _PackOps) -> None:
        self._scope = scope
        self._packs = pack_ops  # get()

    async def instantiate(
        self, source_pack_uid: str, world_uid: str, *, confirm=False, preview_token=None
    ) -> PackRemapResult | ReinstantiatePreview:
        scope = self._scope
        source = await self._packs.get(source_pack_uid)
        if source.owner_world_uid is not None:
            raise LibraryPackValidationError(
                f"pack '{source.system_name}' is world-owned — only engine "
                "libraries instantiate into worlds (TZ §1.1)"
            )
        if is_default_pack_uid(source.pack_uid):
            raise LibraryPackValidationError(
                f"pack '{source.system_name}' is a declared default — already "
                "available to every world; an owned instance would be cut "
                "off from canonical attach (TZ §6)"
            )
        world = await scope.worlds.find_by_id(world_uid)
        if world is None:
            raise LibraryPackValidationError(
                f"world '{world_uid}' does not exist"
            )
        existing = await scope.packs.find_instance(world_uid, source.pack_uid)
        if existing is not None:
            from app.application.worldData.libraryPacks.reinstantiateOps import reinstantiate
            return await reinstantiate(scope, source, existing, world,
                                       confirm=confirm, preview_token=preview_token)
        return await self._copy(
            source,
            system_name=_instance_system_name(world_uid, source.system_name),
            owner_world_uid=world_uid,
            world=world,
        )

    async def copy(
        self,
        source_pack_uid: str,
        *,
        system_name: str | None = None,
    ) -> PackRemapResult:
        """Publish world→engine — the same remap with ``owner=NULL``."""
        source = await self._packs.get(source_pack_uid)
        if source.owner_world_uid is None:
            raise LibraryPackValidationError(
                f"pack '{source.system_name}' is an engine library — "
                "copy_pack publishes world-owned packs (TZ §4.1)"
            )
        return await self._copy(
            source,
            system_name=system_name or published_system_name(source.system_name),
            owner_world_uid=None,
        )

    async def _copy(
        self,
        source: LibraryPackRow,
        *,
        system_name: str,
        owner_world_uid: str | None,
        world: World | None = None,
    ) -> PackRemapResult:
        scope = self._scope
        system_name, new_pack_uid = await scope.new_pack_identity(system_name)
        members = await scope.members.list_by_pack(source.pack_uid)
        uid_map = _uid_map_for(members, new_pack_uid)

        pack_row = LibraryPackRow(
            pack_uid=new_pack_uid,
            system_name=system_name,
            pack_name=source.pack_name,
            display_name=source.display_name,
            version=source.version,
            owner_world_uid=owner_world_uid,
            source_pack_uid=source.pack_uid,
        )
        dep_rows = [
            LibraryPackDependencyRow(new_pack_uid, dep.required_pack_uid)
            for dep in await scope.deps.list_for_pack(source.pack_uid)
        ]
        new_rows: list[LibraryPackMemberRow] = []
        per_kind: dict[str, list[RemappedMember]] = {}

        async def _write() -> None:
            await scope.insert_pack_row(pack_row)
            if dep_rows:
                await scope.deps.insert_missing(dep_rows)
            for src in members:
                adapter = scope.adapter_for(LibraryKind(src.library_kind))
                found = await adapter.read_body_row(src.template_uid)
                if found is None:
                    raise LibraryPackValidationError(
                        f"source member '{src.template_uid}' has no body — "
                        "incomplete source pack, cannot remap"
                    )
                body, source_file = found
                new_uid = uid_map[src.template_uid]
                outline = await adapter.write_body(
                    adapter.remap_body(
                        body, template_uid=new_uid, uid_map=uid_map
                    ),
                    local_uid=src.local_uid,
                    template_uid=new_uid,
                    pack=pack_row,
                    world=world,
                    source_file=source_file,
                )
                member = LibraryPackMemberRow(
                    template_uid=new_uid,
                    pack_uid=new_pack_uid,
                    library_kind=src.library_kind,
                    local_uid=src.local_uid,
                    source_template_uid=src.template_uid,
                    creation_kind='pack_copy',
                )
                new_rows.append(member)
                per_kind.setdefault(src.library_kind, []).append(
                    RemappedMember(member=member, outline=outline)
                )
            await scope.members.insert_missing(new_rows)
            if world is not None:
                # Dual-write + world-side refs (TZ §2): pointers land on
                # the instance member uids; refs to source members follow
                # the same map. Refetch between adapters — two kinds can
                # share one world column.
                for kind, kind_members in per_kind.items():
                    fresh = await scope.worlds.find_by_id(world.world_uid)
                    if fresh is None:
                        raise LibraryPackValidationError(
                            f"world '{world.world_uid}' disappeared during remap"
                        )
                    await scope.adapter_for(LibraryKind(kind)).remap_world_refs(
                        fresh, uid_map, kind_members
                    )

        await scope.atomic(_write)
        missing = await scope.diagnose_missing(pack_row)
        logger.info(
            "packs | remap %s → %s owner=%s members=%d",
            source.pack_uid, new_pack_uid, owner_world_uid, len(new_rows),
        )
        return PackRemapResult(
            pack=pack_row,
            members=tuple(new_rows),
            uid_map=uid_map,
            missing_dependencies=tuple(sorted(missing)),
        )
