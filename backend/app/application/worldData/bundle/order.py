"""Canonical import/export section order — tz_world_bundle.md."""

from __future__ import annotations

from app.dataModel.worldBundle.bundleSections import BundleSection

# Entity first, then library (after world for registry validate).
BUNDLE_IMPORT_ORDER: tuple[str, ...] = (
    BundleSection.WORLD,
    BundleSection.STATES,
    BundleSection.LOCATIONS,
    BundleSection.CONNECTION_NODES,
    BundleSection.CONNECTION_EDGES,
    BundleSection.RELIEF_TEMPLATES,
    BundleSection.BUILDING_TEMPLATES,
    BundleSection.RACE_TEMPLATES,
    BundleSection.PERK_TEMPLATES,
)
