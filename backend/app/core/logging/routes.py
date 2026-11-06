"""Existing logger-prefix and server-sink catalog."""

_R44_ACTIVITY = "grade_cell_empty_ray"

PROFILE_SERVER = "server"
PROFILE_SCRIPT = "script"

# Longest prefix first. ``app.relief`` is handled in route_for (R44 split).
_PREFIX_ROUTES: tuple[tuple[str, str, str], ...] = tuple(
    sorted(
        (
            (
                "app.application.worldData.regions.regionStateLog",
                "region_state",
                "regionStateLog",
            ),
            (
                "app.application.worldData.pack.bake.detailed.packDetailedBakeOrchestrator",
                "pack",
                "packDetailedBake",
            ),
            (
                "app.application.worldData.pack.bake.packBakeLog",
                "pack",
                "packBakeLog",
            ),
            (
                "app.application.worldData.pack.refine",
                "pack",
                "fineChunkPersist",
            ),
            (
                "app.application.worldData.render.dumpLog",
                "render",
                "dumpLog",
            ),
            (
                "app.application.worldData.materialize.terrain.terrainParallelLog",
                "terrain",
                "terrainParallelLog",
            ),
            (
                "app.application.worldData.generators.assemblers.climateAssembler",
                "climate",
                "climateLog",
            ),
            (
                "app.application.worldData.generators.assemblers",
                "settlement",
                "settlementAssembler",
            ),
            (
                "app.application.worldData.generators.climate",
                "climate",
                "climateLog",
            ),
            (
                "app.application.cascade",
                "cascade",
                "cascadeLog",
            ),
            (
                "app.application.jsonValidation",
                "jsonValidation",
                "resolve",
            ),
            ("app.application.physics", "physics", "physicsLog"),
            ("http", "http", "api"),
            ("app.engine.dag", "engine", "dagExecution"),
            ("app.artifacts", "artifacts", "artifactLifecycle"),
            ("app.time.operations", "time", "operations"),
        ),
        key=lambda row: len(row[0]),
        reverse=True,
    )
)

# Server profile allowlist — catalog process=server plus unmatched sink.
# Do not include script/* or render/dumpLog (script-only).
SERVER_SINKS: frozenset[tuple[str, str]] = frozenset({
    ("engine", "dagExecution"),
    ("artifacts", "artifactLifecycle"),
    ("time", "operations"),
    ("region_state", "regionStateLog"),
    ("http", "api"),
    ("pack", "packBakeLog"),
    ("pack", "packDetailedBake"),
    ("pack", "fineChunkPersist"),
    ("relief", "reliefLog"),
    ("relief", "gradeCellRays"),
    ("terrain", "terrainParallelLog"),
    ("climate", "climateLog"),
    ("jsonValidation", "resolve"),
    ("physics", "physicsLog"),
    ("settlement", "settlementAssembler"),
    ("structure", "headroom"),
    ("cascade", "cascadeLog"),
    ("core", "runtime"),
})

_DUMP_SINK = ("render", "dumpLog")
_RUNTIME_SINK = ("core", "runtime")


def _matches_prefix(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def route_for(logger_name: str, activity: object | None = None) -> tuple[str, str] | None:
    """Map logger name (+ optional ``activity`` extra) to ``(domain, service)``.

    Unmatched names return ``None`` (server profile then uses ``core/runtime``).
    """
    name = logger_name or ""
    if _matches_prefix(name, "app.relief"):
        if activity == _R44_ACTIVITY:
            return ("relief", "gradeCellRays")
        return ("relief", "reliefLog")
    for prefix, domain, service in _PREFIX_ROUTES:
        if _matches_prefix(name, prefix):
            return (domain, service)
    return None
