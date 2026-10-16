"""Parse object-level relief_pick_policy wire (RELIEF-T-20).

Lives in application (not generators): typed boundary before bake consumers.
"""

from __future__ import annotations

from app.application.jsonValidation.resolve import ResolveContext, resolve_model
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy


def parse_object_relief_pick_policy(
    raw: object | None,
    *,
    owner_uid: str = "?",
) -> ObjectReliefPickPolicy | None:
    if raw is None:
        return None
    return resolve_model(ObjectReliefPickPolicy, raw,
                         ctx=ResolveContext(path_prefix=("objects", owner_uid, "relief_pick_policy")))
