"""Validated replacement of the world-scoped index on the pack writer's manifest."""
from collections.abc import Iterable
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry, require_region_index


def replace_region_index(manifest: WorldPackManifest, entries: Iterable[WildernessRegionEntry]) -> None:
    validated = [WildernessRegionEntry.model_validate(e.model_dump()) for e in entries]
    require_region_index(validated)
    manifest.wilderness_region_entries = sorted(validated, key=lambda e: e.region_uid)
