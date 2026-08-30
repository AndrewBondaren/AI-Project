"""C19 tmp blob before SQL commit — not a manifest entry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SettlementStructureTmpRef:
    settlement_uid: str
    tmp_path: Path
    content_hash: str
    nbytes: int
