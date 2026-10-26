"""C19 tmp blob before SQL commit — not a manifest entry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SettlementStructureTmpRef:
    """Caller retains this receipt after SQL commit until manifest publication succeeds.

    The path may disappear during publish; hash/size still identify the published
    payload when retrying an interrupted manifest save.
    """

    settlement_uid: str
    tmp_path: Path
    content_hash: str
    nbytes: int
