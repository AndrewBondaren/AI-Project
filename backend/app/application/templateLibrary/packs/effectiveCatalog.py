"""Effective catalog of one world — runtime read facade (plan
``library-packs-model-done.md`` step 5a-1; TZ packs §1, §1.1, §5, §7).

Membership = the world's own packs ∪ declared defaults
(``membership.membership_pack_uids``); nothing else is a candidate — no
global ``list_all`` bypass, engine user packs reach a world only as
instances. ``world.library_pins`` is an author-usage marker (§1.1), not
availability: it never narrows the catalog or the pick candidates.

The facade is pure read over the public ``PackCatalogRepos`` + adapter map
— the write service's private scope is not involved. Bodies load lazily
per uid through the adapter and are cached on this object only: one
catalog = one world/one call, so a cache never suppresses another world's
warnings (§7). A member without a body stays a member here; the resolve
policy (step 5a-2) decides what that means.

Candidate order is deterministic — sort by ``template_uid`` — and does
not depend on pack instantiation order; registry order dies with the
registries in step 5b.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.application.worldData.libraryPacks.domainAdapters import PackDomainAdapter
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.membership import membership_pack_uids
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind

_MISSING = object()


class EffectiveCatalog:
    """Membership-scoped read view of one world's library packs."""

    def __init__(
        self,
        world_uid: str,
        pack_uids: tuple[str, ...],
        members: Mapping[str, LibraryPackMemberRow],
        adapters: Mapping[LibraryKind, PackDomainAdapter],
    ) -> None:
        self._world_uid = world_uid
        self._pack_uids = pack_uids
        self._members = dict(members)
        self._adapters = adapters
        self._bodies: dict[str, dict | None] = {}

    @property
    def world_uid(self) -> str:
        return self._world_uid

    @property
    def pack_uids(self) -> tuple[str, ...]:
        """Sorted uids of the packs in membership (owned ∪ defaults)."""
        return self._pack_uids

    def member(self, template_uid: str) -> LibraryPackMemberRow | None:
        """Membership lookup — None when the uid is not available to this world."""
        return self._members.get(template_uid)

    def available(self, template_uid: str, kind: LibraryKind) -> bool:
        """Member present in membership *and* of the requested kind."""
        member = self._members.get(template_uid)
        return member is not None and member.library_kind == LibraryKind(kind).value

    def candidates(self, kind: LibraryKind) -> tuple[LibraryPackMemberRow, ...]:
        """All members of *kind*, sorted by ``template_uid``."""
        value = LibraryKind(kind).value
        return tuple(
            m for _, m in sorted(self._members.items()) if m.library_kind == value
        )

    async def body(self, template_uid: str) -> dict | None:
        """Lazy per-uid body read via the member's domain adapter; cached.

        None for a uid outside membership or for a member whose body row is
        absent — the resolve policy (5a-2) turns that into diagnostics.
        """
        cached = self._bodies.get(template_uid, _MISSING)
        if cached is not _MISSING:
            return cached
        member = self._members.get(template_uid)
        if member is None:
            return None
        adapter = self._adapters.get(LibraryKind(member.library_kind))
        if adapter is None:
            raise LibraryPackValidationError(
                f"library_kind '{member.library_kind}' has no domain adapter wired"
            )
        found = await adapter.read_body(template_uid)
        self._bodies[template_uid] = found
        return found


class EffectiveCatalogLoader:
    """Container seam: builds an ``EffectiveCatalog`` for a world from the
    public pack repositories + adapter map (wiring — step 5a-3)."""

    def __init__(
        self,
        repos: PackCatalogRepos,
        adapters: Mapping[LibraryKind, PackDomainAdapter],
        *, ensure_defaults=None,
    ) -> None:
        self._repos = repos
        self._adapters = adapters
        self._ensure_defaults = ensure_defaults

    async def load(self, world_uid: str) -> EffectiveCatalog:
        if not world_uid:
            raise LibraryPackValidationError("effective catalog requires a world uid")
        if self._ensure_defaults is not None:
            await self._ensure_defaults()
        pack_uids = await membership_pack_uids(self._repos.packs, world_uid)
        members = await self._repos.members.list_by_packs(pack_uids)
        return EffectiveCatalog(
            world_uid,
            tuple(pack_uids),
            {m.template_uid: m for m in members},
            self._adapters,
        )
