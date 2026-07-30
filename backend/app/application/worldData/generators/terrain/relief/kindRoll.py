"""Seeded SLOPE|SHEER roll from weights (R15/R27)."""

from __future__ import annotations

import hashlib

from app.application.worldData.generators.terrain.relief.reliefLog import relief_debug
from app.dataModel.terrain.relief.enums import ReliefSideKind


def kind_roll(
    *,
    world_seed: str,
    context: str,
    template_uid: str,
    site_id: str,
    slope_weight: float,
    sheer_weight: float,
    side_index: int | None = None,
) -> ReliefSideKind:
    """Deterministic roll; weights already validated sum==1."""
    if sheer_weight <= 0:
        kind = ReliefSideKind.SLOPE
        reason = "sheer_weight=0"
    elif slope_weight <= 0:
        kind = ReliefSideKind.SHEER
        reason = "slope_weight=0"
    else:
        key = f"{world_seed}|{context}|{template_uid}|{site_id}"
        if side_index is not None:
            key += f"|{side_index}"
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        # map first 8 bytes → [0, 1)
        u = int.from_bytes(digest[:8], "big") / float(2**64)
        kind = ReliefSideKind.SHEER if u < sheer_weight else ReliefSideKind.SLOPE
        reason = f"u={u:.6f}<sheer={sheer_weight}"

    relief_debug(
        "kind_roll",
        template_uid=template_uid,
        site_id=site_id,
        kind=kind.value,
        slope_weight=slope_weight,
        sheer_weight=sheer_weight,
        reason=reason,
    )
    return kind
