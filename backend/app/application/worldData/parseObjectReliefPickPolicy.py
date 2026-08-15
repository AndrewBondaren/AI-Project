"""Parse object-level relief_pick_policy wire (RELIEF-T-20).

Lives in application (not generators): typed boundary before bake consumers.
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.log.log import relief_warning
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy


def parse_object_relief_pick_policy(
    raw: object | None,
    *,
    owner_uid: str = "?",
) -> ObjectReliefPickPolicy | None:
    if not raw:
        return None
    if isinstance(raw, ObjectReliefPickPolicy):
        return raw
    try:
        return ObjectReliefPickPolicy.model_validate(raw)
    except Exception as exc:
        relief_warning(
            "object_policy_invalid",
            owner_uid=owner_uid,
            reason=str(exc),
        )
        return None
