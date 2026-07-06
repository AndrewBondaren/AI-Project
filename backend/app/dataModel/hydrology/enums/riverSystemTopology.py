"""River system group topology — confluence A vs basin B."""

from __future__ import annotations

from enum import StrEnum


class RiverSystemTopology(StrEnum):
  CONFLUENCE = "confluence"
  BASIN = "basin"

  @classmethod
  def from_wire(cls, key: str | RiverSystemTopology | None) -> RiverSystemTopology | None:
      if key is None:
          return None
      if isinstance(key, cls):
          return key
      norm = str(key).strip().lower()
      for member in cls:
          if member.value == norm:
              return member
      return None
