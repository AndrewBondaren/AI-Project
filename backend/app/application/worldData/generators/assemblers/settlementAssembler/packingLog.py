"""C22 packing log helper — docs/tz_logging.md settlement / settlementAssembler.

Step / reason strings: tz_structure_connections.md §5.1.3 «Debug packing».
Callers pass ``PackingStep`` / ``PackingReason`` — not ad-hoc literals.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger("app.application.worldData.generators.assemblers")

# Console L8: fit storm is file-only (not the TZ step name).
FIT_ACTIVITY = "c22_packing_fit"


class PackingStep(StrEnum):
    ANCHORS = "anchors"
    DISTRICT_BARRIER = "district_barrier"
    CACHE = "cache"
    TOKENS = "tokens"
    PASS1 = "pass1"
    FRAME = "frame"
    PASS2 = "pass2"
    FIT = "fit"
    PLACE = "place"
    LEFTOVER = "leftover"
    ALLEY = "alley"
    GRAPH = "graph"
    AREA = "area"
    FRONTAGE = "frontage"


class PackingReason(StrEnum):
    SKIP_NO_PERIMETER_BARRIER = "skip_no_perimeter_barrier"
    DISTRICT_BARRIER_ALWAYS = "district_barrier_always"
    SETTLEMENT_BARRIER_SHRINK = "settlement_barrier_shrink"
    INNER_EMPTY = "inner_empty"
    SKIP_NO_ENTRY_NODES = "skip_no_entry_nodes"
    NO_CANDIDATES = "no_candidates"
    NO_CACHE = "no_cache"
    PLACE = "place"
    SKIP_NO_HOLE = "skip_no_hole"
    CENTER = "center"
    EMPTY_LIST = "empty_list"
    OK = "ok"
    REJECT_AXIS = "reject_axis"
    LEFTOVER = "leftover"
    FROM_CONNECTIONS = "from_connections"
    NOT_IN_SETTINGS = "not_in_settings"
    SINGLE_PLOT = "single_plot"
    WIDTH = "width"
    PLAZA = "plaza"
    RNG = "rng"
    SKIP_UNKNOWN = "skip_unknown"
    THREAD_COUNT = "thread_count"
    FOOTPRINT_MISS = "footprint_miss_reservation"
    NO_ASSEMBLER = "no_assembler"
    EMPTY_FOOTPRINT = "empty_footprint"
    MISSING_TEMPLATE = "missing_template"


class PackingHost(StrEnum):
    SETTLEMENT = "settlement"


def _wire(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return str(value)
    return value


def _fmt(fields: dict[str, Any]) -> str:
    return " ".join(
        f"{k}={_wire(v)!r}" for k, v in fields.items() if v is not None
    )


def _message(district: str, step: PackingStep, fields: dict[str, Any]) -> str:
    body = _fmt(fields)
    step_s = str(step)
    if body:
        return f"C22 packing | district={district} step={step_s} {body}"
    return f"C22 packing | district={district} step={step_s}"


def packing_info(step: PackingStep, /, *, district: str, **fields: Any) -> None:
    logger.info(_message(district, step, fields), extra={"activity": str(step)})


def packing_warning(step: PackingStep, /, *, district: str, **fields: Any) -> None:
    logger.warning(_message(district, step, fields), extra={"activity": str(step)})


def packing_debug(step: PackingStep, /, *, district: str, **fields: Any) -> None:
    extra = {"activity": FIT_ACTIVITY if step is PackingStep.FIT else str(step)}
    logger.debug(_message(district, step, fields), extra=extra)
