"""Common placement facade; domain adapters consume this single resolver."""

from app.application.worldData.placement.resolver import resolve_placements

__all__ = ["resolve_placements"]
