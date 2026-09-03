"""Settlement assembler package — lazy exports to avoid import cycles."""

from __future__ import annotations

from typing import Any

__all__ = ["SettlementAssembler", "SettlementLayout"]


def __getattr__(name: str) -> Any:
    if name == "SettlementAssembler":
        from app.application.worldData.generators.assemblers.settlementAssembler.settlementAssembler import (
            SettlementAssembler,
        )
        return SettlementAssembler
    if name == "SettlementLayout":
        from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
            SettlementLayout,
        )
        return SettlementLayout
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
