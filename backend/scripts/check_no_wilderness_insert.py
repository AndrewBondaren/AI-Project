#!/usr/bin/env python3
"""CI gate: no new wilderness INSERT INTO map_cells (table renamed to map_cell_patches)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

FORBIDDEN = re.compile(
    r"INSERT\s+INTO\s+map_cells\b",
    re.IGNORECASE,
)

ALLOWLIST = {
    APP / "db" / "repositories" / "sqlite" / "mapCellRepository.py",
}


def main() -> int:
    violations: list[str] = []
    for path in APP.rglob("*.py"):
        if path in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                violations.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
    if violations:
        print("Wilderness map_cells INSERT gate failed:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        return 1
    print("check_no_wilderness_insert: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
