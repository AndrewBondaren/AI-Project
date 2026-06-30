"""Rainfall from zone moisture × world precipitation liquid phase band."""

import logging

from app.application.worldData.generators.climate.loggingHelpers import warn_once
from app.application.worldData.generators.climate.loggingHelpers import debug_once
from app.application.worldData.generators.climate.math import smoothstep
from app.application.worldData.generators.climate.poleResolve import peak_bounds
from app.application.worldData.jsonValidation.normalize.climateDefaults import (
    DEFAULT_PRECIPITATION_LIQUID,
    LEGACY_STANDALONE_WATER_MATERIAL,
)
from app.db.models.world import World

logger = logging.getLogger(__name__)

LIQUID_BAND_OUTER = 0.1


def _material_entry(world: World, system_material: str) -> dict | None:
    for entry in world.material_registry or []:
        if isinstance(entry, dict) and entry.get("system_material") == system_material:
            return entry
    return None


def _precipitation_liquid_key(world: World) -> str:
    key = world.precipitation_liquid
    if key is None:
        warn_once(
            world.world_uid,
            "null_precipitation_liquid",
            "precipitation_liquid | world=%s field null; using %r (import normalize target)",
            DEFAULT_PRECIPITATION_LIQUID,
        )
        return DEFAULT_PRECIPITATION_LIQUID
    return key


def resolve_world_precipitation_liquid(world: World) -> dict:
    """
    World precipitation liquid from material_registry.
    Explicit DB value required after import normalize; legacy gaps warn once.
    """
    key = _precipitation_liquid_key(world)
    entry = _material_entry(world, key)
    if entry is not None and entry.get("material_category") == "liquid":
        return entry

    water = _material_entry(world, DEFAULT_PRECIPITATION_LIQUID)
    if water is not None:
        if entry is not None:
            warn_once(
                world.world_uid,
                f"not_liquid:{key}",
                "precipitation_liquid fallback | world=%s requested=%s is not liquid (category=%s); using water",
                key,
                entry.get("material_category"),
            )
        elif key != DEFAULT_PRECIPITATION_LIQUID:
            warn_once(
                world.world_uid,
                f"missing:{key}",
                "precipitation_liquid fallback | world=%s requested=%s not in material_registry; using water",
                key,
            )
        return water

    for mat in world.material_registry or []:
        if isinstance(mat, dict) and mat.get("material_category") == "liquid":
            warn_once(
                world.world_uid,
                "first_liquid",
                "precipitation_liquid fallback | world=%s requested=%s; water missing; using first liquid=%s",
                key,
                mat.get("system_material"),
            )
            return mat

    warn_once(
        world.world_uid,
        "standalone_water",
        "precipitation_liquid fallback | world=%s requested=%s; no liquid in material_registry; using legacy standalone water",
        key,
    )
    return dict(LEGACY_STANDALONE_WATER_MATERIAL)


def _phase_bounds(entry: dict) -> tuple[int | None, int | None]:
    cool = entry.get("cool_temp")
    heat = entry.get("heat_temp")
    if cool is not None and not entry.get("cool_into"):
        cool = None
    if heat is not None and not entry.get("heat_into"):
        heat = None
    return cool, heat


def liquid_precipitation_mult(
    temp: int,
    liquid_entry: dict,
    world_uid: str | None = None,
) -> float:
    """
    0..1 multiplier: liquid precipitation possible when temp is inside material phase band.
    Outer 10% of band uses smoothstep (same compromise as tier temp blend).
    """
    cool, heat = _phase_bounds(liquid_entry)
    if cool is None and heat is None:
        return 1.0

    if cool is not None and heat is not None:
        if heat <= cool:
            if world_uid:
                material = liquid_entry.get("system_material", "?")
                warn_once(
                    world_uid,
                    f"invalid_phase_band:{material}",
                    "liquid_precipitation_mult | world=%s material=%s heat_temp=%s <= cool_temp=%s; using mult=1.0",
                    material,
                    heat,
                    cool,
                )
            return 1.0
        if temp <= cool or temp >= heat:
            return 0.0
        span     = heat - cool
        inner_lo = cool + span * LIQUID_BAND_OUTER
        inner_hi = heat - span * LIQUID_BAND_OUTER
        if temp <= inner_lo:
            band = inner_lo - cool
            return smoothstep((temp - cool) / band) if band > 0 else 1.0
        if temp >= inner_hi:
            band = heat - inner_hi
            return smoothstep((heat - temp) / band) if band > 0 else 1.0
        return 1.0

    if cool is not None:
        if temp <= cool:
            return 0.0
        band = max(1, abs(cool) // 10 + 10)
        if temp >= cool + band:
            return 1.0
        return smoothstep((temp - cool) / band)

    assert heat is not None
    if temp >= heat:
        return 0.0
    band = max(1, abs(heat) // 10 + 10)
    if temp <= heat - band:
        return 1.0
    return smoothstep((heat - temp) / band)


def clamp_temperature_to_peak(world: World, temp: int) -> int:
    peak_min, peak_max = peak_bounds(world)
    clamped            = max(peak_min, min(peak_max, temp))
    if clamped != temp:
        debug_once(
            world.world_uid,
            "peak_clamp",
            "temperature clamp | world=%s raw=%d -> clamped=%d peak=[%d,%d]",
            temp,
            clamped,
            peak_min,
            peak_max,
        )
    return clamped


def effective_rainfall(moisture: int, temp: int, world: World) -> int:
    requested_liquid = _precipitation_liquid_key(world)
    liquid           = resolve_world_precipitation_liquid(world)
    cool, heat       = _phase_bounds(liquid)
    mult             = liquid_precipitation_mult(temp, liquid, world.world_uid)
    rainfall         = max(0, min(100, round(moisture * mult)))

    logger.debug(
        "rainfall | world=%s requested_liquid=%s resolved_liquid=%s "
        "moisture=%d temp=%d cool_temp=%s heat_temp=%s mult=%.4f -> rainfall=%d",
        world.world_uid,
        requested_liquid,
        liquid.get("system_material"),
        moisture,
        temp,
        cool,
        heat,
        mult,
        rainfall,
    )
    return rainfall
