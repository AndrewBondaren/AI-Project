"""Rainfall from zone moisture × world precipitation liquid phase band."""

import logging

from app.application.worldData.generators.climate.poleResolve import peak_bounds
from app.db.models.world import World

logger = logging.getLogger(__name__)

DEFAULT_PRECIPITATION_LIQUID = "water"
LIQUID_BAND_OUTER            = 0.1

_FALLBACK_WATER: dict = {
    "system_material":    "water",
    "material_category":  "liquid",
    "cool_into":          "ice",
    "cool_temp":          0,
    "heat_into":          "steam",
    "heat_temp":          100,
}

_warned_liquid_fallbacks: set[tuple[str, str]] = set()


def _warn_liquid_fallback_once(world_uid: str, reason: str, msg: str, *args: object) -> None:
    key = (world_uid, reason)
    if key in _warned_liquid_fallbacks:
        return
    _warned_liquid_fallbacks.add(key)
    logger.warning(msg, world_uid, *args)


def _material_entry(world: World, system_material: str) -> dict | None:
    for entry in world.material_registry or []:
        if isinstance(entry, dict) and entry.get("system_material") == system_material:
            return entry
    return None


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def resolve_world_precipitation_liquid(world: World) -> dict:
    """
    World precipitation liquid from material_registry.
    Priority: world.precipitation_liquid → water → first liquid → built-in water defaults.
    """
    key   = world.precipitation_liquid or DEFAULT_PRECIPITATION_LIQUID
    entry = _material_entry(world, key)
    if entry is not None and entry.get("material_category") == "liquid":
        return entry

    if entry is not None:
        _warn_liquid_fallback_once(
            world.world_uid,
            f"not_liquid:{key}",
            "precipitation_liquid fallback | world=%s requested=%s is not liquid (category=%s); trying water",
            key,
            entry.get("material_category"),
        )
    elif world.precipitation_liquid:
        _warn_liquid_fallback_once(
            world.world_uid,
            f"missing:{key}",
            "precipitation_liquid fallback | world=%s requested=%s not in material_registry; trying water",
            key,
        )

    water = _material_entry(world, DEFAULT_PRECIPITATION_LIQUID)
    if water is not None:
        if key != DEFAULT_PRECIPITATION_LIQUID or entry is not None:
            _warn_liquid_fallback_once(
                world.world_uid,
                f"resolved_water:{key}",
                "precipitation_liquid fallback | world=%s using registry water instead of requested=%s",
                key,
            )
        return water

    for entry in world.material_registry or []:
        if isinstance(entry, dict) and entry.get("material_category") == "liquid":
            _warn_liquid_fallback_once(
                world.world_uid,
                "first_liquid",
                "precipitation_liquid fallback | world=%s water missing; using first liquid=%s",
                entry.get("system_material"),
            )
            return entry

    _warn_liquid_fallback_once(
        world.world_uid,
        "builtin_water",
        "precipitation_liquid fallback | world=%s no liquid in material_registry; using built-in water defaults",
    )
    return _FALLBACK_WATER


def _phase_bounds(entry: dict) -> tuple[int | None, int | None]:
    cool = entry.get("cool_temp")
    heat = entry.get("heat_temp")
    if cool is not None and not entry.get("cool_into"):
        cool = None
    if heat is not None and not entry.get("heat_into"):
        heat = None
    return cool, heat


def liquid_precipitation_mult(temp: int, liquid_entry: dict) -> float:
    """
    0..1 multiplier: liquid precipitation possible when temp is inside material phase band.
    Outer 10% of band uses smoothstep (same compromise as tier temp blend).
    """
    cool, heat = _phase_bounds(liquid_entry)
    if cool is None and heat is None:
        return 1.0

    if cool is not None and heat is not None:
        if heat <= cool:
            return 1.0
        if temp <= cool or temp >= heat:
            return 0.0
        span     = heat - cool
        inner_lo = cool + span * LIQUID_BAND_OUTER
        inner_hi = heat - span * LIQUID_BAND_OUTER
        if temp <= inner_lo:
            band = inner_lo - cool
            return _smoothstep((temp - cool) / band) if band > 0 else 1.0
        if temp >= inner_hi:
            band = heat - inner_hi
            return _smoothstep((heat - temp) / band) if band > 0 else 1.0
        return 1.0

    if cool is not None:
        if temp <= cool:
            return 0.0
        band = max(1, abs(cool) // 10 + 10)
        if temp >= cool + band:
            return 1.0
        return _smoothstep((temp - cool) / band)

    assert heat is not None
    if temp >= heat:
        return 0.0
    band = max(1, abs(heat) // 10 + 10)
    if temp <= heat - band:
        return 1.0
    return _smoothstep((heat - temp) / band)


def clamp_temperature_to_peak(world: World, temp: int) -> int:
    peak_min, peak_max = peak_bounds(world)
    return max(peak_min, min(peak_max, temp))


def effective_rainfall(moisture: int, temp: int, world: World) -> int:
    requested_liquid = world.precipitation_liquid or DEFAULT_PRECIPITATION_LIQUID
    liquid           = resolve_world_precipitation_liquid(world)
    cool, heat       = _phase_bounds(liquid)
    mult             = liquid_precipitation_mult(temp, liquid)
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
