"""Common placement facade; domain adapters consume this single resolver."""

# GEO-LEGACY-51: Remove the eager V1 resolver import and export.
from app.application.worldData.placement.resolver import resolve_placements

__all__ = ["resolve_placements"]
