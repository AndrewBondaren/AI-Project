"""Character validation context loader — JV-6 T7."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


async def load_world_validation_context(
    *,
    world_service,
    race_service,
    location_service,
    seed_service,
    world_uid: str,
) -> dict[str, Any]:
    """Load world blob + section snapshots for character sheet validation."""
    world = asdict(await world_service.get_by_id(world_uid))
    races = [asdict(r) for r in await race_service.get_all(world_uid)]
    locations = [asdict(row) for row in await location_service.get_all(world_uid)]
    seed_snapshot = await seed_service.export_all()
    return {
        "world_context": world,
        "races_snapshot": races,
        "locations_snapshot": locations,
        "seed_snapshot": seed_snapshot,
        "expected_world_schema_version": world.get("schema_version"),
    }
