"""When to write denser per-tile climate on L0 light/full bake."""

from __future__ import annotations

from typing import Literal

# spawn_player — fine on player spawn tile only (current default behaviour)
# none — no fine on L0; detailed / runtime only
# all_baked_tiles — fine on every L0 tile written in this bake
LightFineTilePolicy = Literal["spawn_player", "none", "all_baked_tiles"]
