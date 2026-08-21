"""Hill footprint kinds for open-land consumers — not a mask domain.

SoT: ``docs/tz_world_pack_storage.md`` § L2 open-land hills (shapes).
"""

from __future__ import annotations

from enum import StrEnum


class HillShape(StrEnum):
    """Wire tokens for ``HillPolicy.shapes``."""

    CIRCLE = "circle"
    OVAL = "oval"
    DOUBLE_CIRCLE = "double_circle"
    DOUBLE_OVAL = "double_oval"

    @classmethod
    def catalog(cls) -> tuple[HillShape, ...]:
        """Full set — empty policy array draws from this via world uid."""
        return tuple(cls)
