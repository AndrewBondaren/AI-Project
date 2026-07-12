"""World bundle import/export levels — WP-24 thin layer over dataModel."""

from __future__ import annotations

from app.dataModel.worldBundle.bundleSections import BundleSection, ImportLevel

__all__ = [
    "ImportLevel",
    "BundleSection",
    "SKELETON_SECTIONS",
    "REGISTRY_SECTIONS",
    "sections_for_level",
    "filter_bundle_for_export",
    "validate_bundle_for_import",
]

SKELETON_SECTIONS: frozenset[str] = BundleSection.SKELETON
REGISTRY_SECTIONS: frozenset[str] = BundleSection.REGISTRY


def sections_for_level(level: ImportLevel) -> frozenset[str]:
    return BundleSection.for_level(level)


def filter_bundle_for_export(bundle: dict, level: ImportLevel) -> dict:
    allowed = sections_for_level(level)
    return {key: value for key, value in bundle.items() if key in allowed}


def validate_bundle_for_import(data: dict, level: ImportLevel) -> None:
    allowed = sections_for_level(level)
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValueError(
            f"Bundle sections {sorted(unknown)} not allowed for import level '{level}'",
        )
