"""Read hydrology autoresolve flags from world POJO — D HY-5a."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.jsonValidation import hydrology
from app.dataModel.hydrology.lakes import HydrologyLakesPolicy
from app.dataModel.hydrology.seas import HydrologySeasPolicy


@dataclass(frozen=True)
class RiversAutoresolvePolicy:
    rivers_enabled: bool
    autoresolve: bool


@dataclass(frozen=True)
class LakesAutoresolvePolicy:
    lakes_enabled: bool
    autoresolve: bool


@dataclass(frozen=True)
class SeasAutoresolvePolicy:
    seas_enabled: bool
    autoresolve_coastal_sea: bool
    autoresolve_open_ocean: bool


def seas_autoresolve_policy(world: Any) -> SeasAutoresolvePolicy:
    seas = _seas_section(world)
    enabled = bool(seas.enabled if seas.enabled is not None else True)
    coastal = bool(
        seas.autoresolve_coastal_sea if seas.autoresolve_coastal_sea is not None else True,
    )
    ocean = bool(
        seas.autoresolve_open_ocean if seas.autoresolve_open_ocean is not None else True,
    )
    return SeasAutoresolvePolicy(
        seas_enabled=enabled,
        autoresolve_coastal_sea=coastal,
        autoresolve_open_ocean=ocean,
    )


def _seas_section(world: Any) -> HydrologySeasPolicy:
    policy = hydrology(world)
    seas = policy.default_seas
    if seas is None:
        return HydrologySeasPolicy()
    if isinstance(seas, dict):
        return HydrologySeasPolicy.model_validate(seas)
    return seas


def _lakes_section(world: Any) -> HydrologyLakesPolicy:
    policy = hydrology(world)
    lakes = policy.default_lakes
    if lakes is None:
        return HydrologyLakesPolicy()
    if isinstance(lakes, dict):
        return HydrologyLakesPolicy.model_validate(lakes)
    return lakes


def lakes_autoresolve_policy(world: Any) -> LakesAutoresolvePolicy:
    lakes = _lakes_section(world)
    enabled = bool(lakes.enabled if lakes.enabled is not None else True)
    autoresolve = bool(lakes.autoresolve if lakes.autoresolve is not None else True)
    return LakesAutoresolvePolicy(lakes_enabled=enabled, autoresolve=autoresolve)


def _rivers_section(world: Any):
    from app.dataModel.hydrology.rivers import HydrologyRiversPolicy

    policy = hydrology(world)
    rivers = policy.default_rivers
    if rivers is None:
        return HydrologyRiversPolicy()
    if isinstance(rivers, dict):
        return HydrologyRiversPolicy.model_validate(rivers)
    return rivers


def rivers_autoresolve_policy(world: Any) -> RiversAutoresolvePolicy:
    rivers = _rivers_section(world)
    enabled = bool(rivers.enabled if rivers.enabled is not None else True)
    autoresolve = bool(rivers.autoresolve if rivers.autoresolve is not None else True)
    return RiversAutoresolvePolicy(rivers_enabled=enabled, autoresolve=autoresolve)
