"""Pass 1 index from N1-G seed tables — docs/tz_json_validation.md JV-8."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SeedRegistryIndex:
    _keys: dict[str, frozenset[str]] = field(default_factory=dict)

    def has_seed(self, table: str, key: str) -> bool:
        return key in self._keys.get(table, frozenset())

    def keys(self, table: str) -> frozenset[str]:
        return self._keys.get(table, frozenset())

    def register_many(self, table: str, keys: set[str]) -> None:
        if not keys:
            return
        current = self._keys.get(table, frozenset())
        self._keys[table] = current | frozenset(keys)


def _table_keys(rows: Any, pk_field: str) -> set[str]:
    if not isinstance(rows, list):
        return set()
    out: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get(pk_field)
        if isinstance(key, str) and key:
            out.add(key)
    return out


def build_seed_registry_index(seed_data: dict[str, Any]) -> SeedRegistryIndex:
    """Build index from seed export `{ table: rows[] }` (PK = `system_{table}`)."""
    index = SeedRegistryIndex()
    if not isinstance(seed_data, dict):
        return index
    for table, rows in seed_data.items():
        if not isinstance(table, str):
            continue
        index.register_many(table, _table_keys(rows, f"system_{table}"))
    return index
