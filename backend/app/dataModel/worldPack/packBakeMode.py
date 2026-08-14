"""Pack bake mode wire — docs/tz_world_pack_storage.md § Bake modes (WP-27)."""

from __future__ import annotations

from typing import Literal

# HTTP / CLI API modes
PackBakeApiMode = Literal["light", "full", "detailed"]

# Manifest last completed L0 mode (detailed does not write this)
PackBakeMode = Literal["light", "full"]

PACK_BAKE_LIGHT: PackBakeMode = "light"
PACK_BAKE_FULL: PackBakeMode = "full"
