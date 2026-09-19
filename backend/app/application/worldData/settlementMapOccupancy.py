"""Settlement map occupancy — LOC-T-3 AABB + reserve. Not C22 packing."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.application.jsonValidation.settlementSizeResolve import resolve_settlement_size_key
from app.application.jsonValidation.settlementVolumeSeparation import (
    REASON_DECLARATION_ORDER,
    REASON_FOOTPRINT,
    log_settlement_volume_separation,
)
from app.application.jsonValidation.worldRow import city_sizes
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    settlement_footprint_side_fine,
    territory_volume_for_location,
)
from app.dataModel.locations.locationFootprintPolicy import named_location_is_settlement_map_site
from app.dataModel.worldPack.territoryVolume import TerritoryVolume, empty_inclusive, volumes_conflict
from app.dataModel.worldPack.territoryVolumePolicy import TerritoryVolumePolicy
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

IndexedLocation = tuple[int, NamedLocation]


@dataclass(frozen=True)
class SettlementVolumeConflict:
    winner: NamedLocation
    loser: NamedLocation
    reason: str
    empty_x: int
    empty_y: int
    empty_z: int
    winner_volume: TerritoryVolume
    loser_volume: TerritoryVolume
    winner_side_fine: int
    loser_side_fine: int


@dataclass(frozen=True)
class OccupancyPick:
    occupants: list[NamedLocation]
    conflicts: tuple[SettlementVolumeConflict, ...]


@dataclass(frozen=True)
class _Candidate:
    location: NamedLocation
    declaration_index: int
    volume: TerritoryVolume
    side_fine: int


def _pin_map_z(location: NamedLocation, policy: TerritoryVolumePolicy) -> int:
    if location.map_z is None:
        return policy.pin_map_z_fallback
    return int(location.map_z)


def _size_key(world: World, location: NamedLocation) -> str:
    return str(
        resolve_settlement_size_key(
            city_sizes(world),
            location.system_city_size,
            world_uid=getattr(world, "world_uid", "") or "",
        )
    )


def pick_occupants(
    world: World,
    locations_with_index: Iterable[IndexedLocation],
    policy: TerritoryVolumePolicy | None = None,
) -> OccupancyPick:
    """Greedy map occupants: larger footprint_side_fine, else earlier declaration_index."""
    resolved = policy or TerritoryVolumePolicy.canonical_defaults()
    candidates: list[_Candidate] = []
    for declaration_index, location in locations_with_index:
        if not named_location_is_settlement_map_site(location):
            continue
        volume = territory_volume_for_location(world, location)
        side = settlement_footprint_side_fine(world, location)
        if volume is None or side is None:
            continue
        candidates.append(
            _Candidate(
                location=location,
                declaration_index=declaration_index,
                volume=volume,
                side_fine=side,
            )
        )
    ranked = sorted(candidates, key=lambda item: (-item.side_fine, item.declaration_index))
    accepted: list[_Candidate] = []
    conflicts: list[SettlementVolumeConflict] = []
    for candidate in ranked:
        rival = next(
            (
                occupant
                for occupant in accepted
                if volumes_conflict(candidate.volume, occupant.volume, resolved)
            ),
            None,
        )
        if rival is None:
            accepted.append(candidate)
            continue
        reason = (
            REASON_FOOTPRINT
            if rival.side_fine != candidate.side_fine
            else REASON_DECLARATION_ORDER
        )
        conflicts.append(
            SettlementVolumeConflict(
                winner=rival.location,
                loser=candidate.location,
                reason=reason,
                empty_x=empty_inclusive(
                    rival.volume.x0, rival.volume.x1,
                    candidate.volume.x0, candidate.volume.x1,
                ),
                empty_y=empty_inclusive(
                    rival.volume.y0, rival.volume.y1,
                    candidate.volume.y0, candidate.volume.y1,
                ),
                empty_z=empty_inclusive(
                    rival.volume.z0, rival.volume.z1,
                    candidate.volume.z0, candidate.volume.z1,
                ),
                winner_volume=rival.volume,
                loser_volume=candidate.volume,
                winner_side_fine=rival.side_fine,
                loser_side_fine=candidate.side_fine,
            )
        )
    return OccupancyPick(
        occupants=[item.location for item in accepted],
        conflicts=tuple(conflicts),
    )


def settlement_map_occupants(
    world: World,
    locations_with_index: Iterable[IndexedLocation],
    policy: TerritoryVolumePolicy | None = None,
) -> list[NamedLocation]:
    return pick_occupants(world, locations_with_index, policy).occupants


def occupancy_locations(
    world: World,
    locations: list[NamedLocation],
    policy: TerritoryVolumePolicy | None = None,
) -> list[NamedLocation]:
    """Non-settlement rows plus settlement map-site occupants (original order)."""
    occupant_uids = {
        loc.location_uid
        for loc in settlement_map_occupants(world, enumerate(locations), policy)
    }
    return [
        loc
        for loc in locations
        if not named_location_is_settlement_map_site(loc)
        or loc.location_uid in occupant_uids
    ]


def emit_settlement_volume_conflicts(
    world: World,
    conflicts: Iterable[SettlementVolumeConflict],
    policy: TerritoryVolumePolicy | None = None,
) -> None:
    resolved = policy or TerritoryVolumePolicy.canonical_defaults()
    for conflict in conflicts:
        winner = conflict.winner
        loser = conflict.loser
        log_settlement_volume_separation(
            winner_uid=winner.location_uid,
            loser_uid=loser.location_uid,
            winner_name=winner.display_name,
            loser_name=loser.display_name,
            winner_subtype=winner.system_location_subtype,
            loser_subtype=loser.system_location_subtype,
            winner_size=_size_key(world, winner),
            loser_size=_size_key(world, loser),
            winner_side_fine=conflict.winner_side_fine,
            loser_side_fine=conflict.loser_side_fine,
            winner_map_z=_pin_map_z(winner, resolved),
            loser_map_z=_pin_map_z(loser, resolved),
            winner_z0=conflict.winner_volume.z0,
            winner_z1=conflict.winner_volume.z1,
            loser_z0=conflict.loser_volume.z0,
            loser_z1=conflict.loser_volume.z1,
            empty_x=conflict.empty_x,
            empty_y=conflict.empty_y,
            empty_z=conflict.empty_z,
            min_xy=resolved.min_settlement_separation_xy,
            min_z=resolved.min_settlement_separation_z,
            reason=conflict.reason,
        )
