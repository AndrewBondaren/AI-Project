"""Single DAG emitter; loggingConfig owns routing, handlers and formatting."""

import logging

from pydantic import TypeAdapter

from app.application.engine.diagnostics.events import LevelDiagnostic, ReplanDiagnostic
from app.dataModel.engine.dag.diagnostics import ExecutionDiagnostic, ExecutionSeverity

_logger = logging.getLogger("app.engine.dag")
_levels = {
    ExecutionSeverity.DEBUG: logging.DEBUG,
    ExecutionSeverity.INFO: logging.INFO,
    ExecutionSeverity.WARNING: logging.WARNING,
    ExecutionSeverity.ERROR: logging.ERROR,
}
_base_schema = TypeAdapter[ExecutionDiagnostic](ExecutionDiagnostic)
_replan_schema = TypeAdapter[ReplanDiagnostic](ReplanDiagnostic)
_level_schema = TypeAdapter[LevelDiagnostic](LevelDiagnostic)


def emit(event: ExecutionDiagnostic) -> None:
    # Revalidate with the declared event schema: unknown subclass fields must
    # not leak payloads into the wire. Nested causes use the base schema too.
    if isinstance(event, LevelDiagnostic):
        admitted = LevelDiagnostic.model_validate(_level_schema.dump_python(event, mode="python"))
    elif isinstance(event, ReplanDiagnostic):
        admitted = ReplanDiagnostic.model_validate(_replan_schema.dump_python(event, mode="python"))
    else:
        admitted = ExecutionDiagnostic.model_validate(_base_schema.dump_python(event, mode="python"))
    _logger.log(_levels[admitted.severity], admitted.code.value,
                extra={"activity": admitted.code.value, "event": admitted.model_dump(mode="json")})
