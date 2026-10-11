"""``resolve_ref`` — runtime template-ref resolve over the effective catalog
(plan ``library-packs-model.md`` step 5a-2; TZ packs §1.1, §5, §7).

Path: UID → membership → availability → body. Three input states of a ref
field (§5): a member ``uid``; an explicit ``default`` marker (the domain's
stored POJO-default choice, no warning); empty/broken (implicit fallback).
Three outcomes: ``RESOLVED`` (member + body), ``DEFAULT`` (domain default
contract applied, stored ref untouched), ``REJECTED`` — raised as
``RefRejected`` (an ``UnresolvedModelError``) for domains without a
substitution contract (relief R21).

Diagnostics: unknown uid / owner pack unavailable / kind mismatch / member
without body / missing pack dependency (closure over ``deps`` with a
visited-set, §5) / empty ref. Exactly **one** warning record per event, at
this boundary, through the policy-resolve sink (``jsonValidation/resolve``
``report_issues`` with ``ReferenceIssueContext``, §7) — callers and adapters
never duplicate it. No instance is ever created by a check; no other
library candidate is ever substituted.

Wire form of the explicit default marker belongs to each domain spec —
domain readers map wire → ``TemplateRef`` before calling the resolver.
``referenceResolver.py`` (write-path usage index, step 4c) is not involved.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from app.application.jsonValidation.resolve import (
    ResolveContext,
    UnresolvedModelError,
    report_issues,
)
from app.application.jsonValidation.types import (
    FieldPathError,
    ReferenceIssueContext,
    ReferenceIssueReason,
)
from app.application.worldData.libraryPacks.domainAdapters import PackDomainAdapter
from app.application.worldData.libraryPacks.effectiveCatalog import EffectiveCatalog
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.packCatalog import PackCatalogRepos
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind

LIBRARY_REFERENCE_CODE = "LIBRARY_REFERENCE"


@dataclass(frozen=True)
class TemplateRef:
    """Ref-field input in one of three states (TZ §5)."""
    uid: str | None = None
    explicit_default: bool = False

    @classmethod
    def of(cls, uid: str | None) -> TemplateRef:
        """uid string → ``uid`` state; None/blank → implicit fallback state."""
        uid = (uid or "").strip() or None
        return cls(uid=uid)

    @classmethod
    def default(cls) -> TemplateRef:
        return cls(explicit_default=True)

    @property
    def is_missing(self) -> bool:
        return self.uid is None and not self.explicit_default


class RefOutcome(StrEnum):
    RESOLVED = "resolved"
    DEFAULT = "default"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ResolvedRef:
    outcome: RefOutcome
    kind: LibraryKind
    ref: TemplateRef
    member: LibraryPackMemberRow | None = None
    body: dict | None = None
    default: Any = None
    issue: FieldPathError | None = None

    @property
    def resolved(self) -> bool:
        return self.outcome is RefOutcome.RESOLVED


class RefRejected(UnresolvedModelError):
    """Domain refused substitution — the ``REJECTED`` outcome as the one
    rejection point (same contract as ``reject_unresolved``)."""

    def __init__(self, result: ResolvedRef) -> None:
        self.result = result
        super().__init__([result.issue])


class RefResolver:
    """Resolve template refs of one world against its effective catalog."""

    def __init__(
        self,
        repos: PackCatalogRepos,
        adapters: Mapping[LibraryKind, PackDomainAdapter],
    ) -> None:
        if repos.deps is None:
            raise LibraryPackValidationError(
                "RefResolver requires the dependency repository (TZ §5 closure)"
            )
        self._repos = repos
        self._adapters = adapters

    async def resolve(
        self,
        catalog: EffectiveCatalog,
        kind: LibraryKind,
        ref: TemplateRef,
        *,
        consumer: str,
        path: str,
        ctx: ResolveContext | None = None,
    ) -> ResolvedRef:
        kind = LibraryKind(kind)
        ctx = ctx if ctx is not None else ResolveContext()
        if ref.explicit_default:
            return self._fallback(catalog, kind, ref, None, ctx, consumer, path)
        if ref.is_missing:
            issue = self._issue(catalog, kind, ref, ReferenceIssueReason.DEFAULT_APPLIED,
                                consumer, path, "empty template reference")
            return self._fallback(catalog, kind, ref, issue, ctx, consumer, path)

        member = catalog.member(ref.uid)
        if member is None:
            issue = await self._unavailable_issue(catalog, kind, ref, consumer, path)
            return self._fallback(catalog, kind, ref, issue, ctx, consumer, path)
        if member.library_kind != kind.value:
            issue = self._issue(catalog, kind, ref, ReferenceIssueReason.KIND_MISMATCH,
                                consumer, path,
                                f"member is {member.library_kind}, not {kind.value}",
                                owner_pack_uid=member.pack_uid)
            return self._fallback(catalog, kind, ref, issue, ctx, consumer, path)
        missing_dep = await self._missing_dependency(catalog, member.pack_uid)
        if missing_dep is not None:
            issue = self._issue(catalog, kind, ref, ReferenceIssueReason.MISSING_DEPENDENCY,
                                consumer, path,
                                f"owner pack requires unavailable pack '{missing_dep}'",
                                owner_pack_uid=member.pack_uid, dependency_pack_uid=missing_dep)
            return self._fallback(catalog, kind, ref, issue, ctx, consumer, path)
        body = await catalog.body(member.template_uid)
        if body is None:
            issue = self._issue(catalog, kind, ref, ReferenceIssueReason.BODY_MISSING,
                                consumer, path, "member has no body row",
                                owner_pack_uid=member.pack_uid)
            return self._fallback(catalog, kind, ref, issue, ctx, consumer, path)
        return ResolvedRef(RefOutcome.RESOLVED, kind, ref, member=member, body=body)

    # ------------------------------------------------------------------

    async def _unavailable_issue(self, catalog, kind, ref, consumer, path) -> FieldPathError:
        """Distinguish an unknown uid from a member whose owner the world
        cannot see — ownership is diagnosed, never made available."""
        known = await self._repos.members.get_by_uid(ref.uid)
        if known is None:
            return self._issue(catalog, kind, ref, ReferenceIssueReason.UNKNOWN_TEMPLATE,
                               consumer, path, "unknown template uid")
        if known.library_kind != kind.value:
            return self._issue(catalog, kind, ref, ReferenceIssueReason.KIND_MISMATCH,
                               consumer, path,
                               f"member is {known.library_kind}, not {kind.value}",
                               owner_pack_uid=known.pack_uid)
        return self._issue(catalog, kind, ref, ReferenceIssueReason.OWNER_UNAVAILABLE,
                           consumer, path, "owner pack is not available to this world",
                           owner_pack_uid=known.pack_uid)

    async def _missing_dependency(self, catalog: EffectiveCatalog, pack_uid: str) -> str | None:
        """First declared dependency (transitive closure, visited-set) that is
        outside the world's membership; None when the closure is satisfied."""
        available = set(catalog.pack_uids)
        visited: set[str] = set()
        stack = [pack_uid]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for required in sorted(await self._repos.deps.required_uids(current)):
                if required not in available:
                    return required
                if required not in visited:
                    stack.append(required)
        return None

    def _fallback(self, catalog, kind, ref, issue, ctx, consumer, path) -> ResolvedRef:
        adapter = self._adapters.get(kind)
        if adapter is None:
            raise LibraryPackValidationError(
                f"library_kind '{kind.value}' has no domain adapter wired"
            )
        decision = adapter.resolve_fallback(world_uid=catalog.world_uid)
        if decision.reject:
            if issue is None:
                issue = self._issue(catalog, kind, ref, ReferenceIssueReason.DEFAULT_APPLIED,
                                    consumer, path, "domain declares no default layer")
            report_issues(ctx, [issue])
            raise RefRejected(ResolvedRef(RefOutcome.REJECTED, kind, ref, issue=issue))
        if issue is not None:
            issue = replace(issue, reference=replace(
                issue.reference, selected_default=decision.selected_default))
            report_issues(ctx, [issue])
        return ResolvedRef(RefOutcome.DEFAULT, kind, ref, default=decision.value, issue=issue)

    @staticmethod
    def _issue(catalog, kind, ref, reason, consumer, path, message, *,
               owner_pack_uid=None, dependency_pack_uid=None) -> FieldPathError:
        return FieldPathError(
            (consumer, path),
            f"{message}: {kind.value}:{ref.uid}" if ref.uid else message,
            code=LIBRARY_REFERENCE_CODE,
            reference=ReferenceIssueContext(
                reason, kind.value, world_uid=catalog.world_uid,
                requested_template_uid=ref.uid, owner_pack_uid=owner_pack_uid,
                dependency_pack_uid=dependency_pack_uid, consumer=consumer,
            ),
        )
