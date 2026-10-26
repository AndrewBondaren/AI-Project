"""Generic source collection — merge declared → anchors → autoresolve.

Canonical owner of ``MaskSourceCollector`` / ``default_collect`` (PC-11.6a
owner map). Generic over the caller's context type — no pack/bake types here;
the L0 execution runner belongs to a separate pack owner. The legacy
``masks/runMaskDomain`` path temporarily re-exports ``default_collect``;
``MaskDomainMaterializer`` structurally satisfies this protocol.
"""

from collections.abc import Callable
from typing import Protocol, TypeVar

from app.application.worldData.masks.mergeDeclare import merge_declare_over_auto
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy

SpecT = TypeVar("SpecT")  # list is mutable, so the spec parameter is invariant.
CtxT = TypeVar("CtxT")
CtxContraT = TypeVar("CtxContraT", contravariant=True)


class MaskSourceCollector(Protocol[CtxContraT, SpecT]):
    """Source side of a mask domain: declared/anchor/autoresolve spec loads.

    Structural protocol — contexts stay caller-owned (pack ctx, domain
    collect context); no execution/canvas methods here.
    """

    def load_declared(self, ctx: CtxContraT) -> list[SpecT]:
        """Wire ``declared_*[]`` only — not geographic / named anchors."""
        ...

    def load_anchor_specs(self, ctx: CtxContraT) -> list[SpecT]:
        """Optional named/geographic anchors → Spec. Not declare-path. Empty if none."""
        ...

    def autoresolve_specs(self, ctx: CtxContraT, policy: MaskCategoryPolicy) -> list[SpecT]: ...


def default_collect(
    collector: MaskSourceCollector[CtxT, SpecT],
    ctx: CtxT,
    policy: MaskCategoryPolicy,
    *,
    key: Callable[[SpecT], object],
) -> list[SpecT]:
    """Merge order: declared > anchors > autoresolve."""
    declared = collector.load_declared(ctx)
    anchors = collector.load_anchor_specs(ctx)
    base = merge_declare_over_auto(declared, anchors, key=key)
    if not bool(policy.autoresolve):
        return base
    auto = collector.autoresolve_specs(ctx, policy)
    return merge_declare_over_auto(base, auto, key=key)
