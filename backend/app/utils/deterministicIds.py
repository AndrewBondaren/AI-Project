"""Stable UUIDs and independent random streams scoped by entity identity."""

from random import Random
from uuid import NAMESPACE_DNS, uuid5


def det_uuid(*parts: str) -> str:
    return str(uuid5(NAMESPACE_DNS, "|".join(parts)))


def scoped_rng(*parts: str) -> Random:
    return Random(det_uuid(*parts))
