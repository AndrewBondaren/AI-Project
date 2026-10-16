"""Deterministic world_uid from canonical world wire (bundle import when uid omitted)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Runtime / identity fields — not part of world definition fingerprint.
_WORLD_UID_HASH_EXCLUDE = frozenset({
    "world_uid",
    "created_at",
    "current_tick",
    "schema_version",
    "world_map_version",
})


def derive_world_uid(world_data: dict[str, Any]) -> str:
    """Stable uid from normalized ``world`` dict (post-``normalize_world``)."""
    canonical = {
        key: value
        for key, value in sorted(world_data.items())
        if key not in _WORLD_UID_HASH_EXCLUDE
    }
    payload = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"world-{digest}"
