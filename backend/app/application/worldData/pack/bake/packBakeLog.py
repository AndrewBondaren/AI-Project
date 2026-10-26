"""Diagnostics for World Pack bake / fine-terrain refine — mirrors terrainParallelLog.

Per-world bake file (survive terminal scrollback)::

    logs/generation/{world_uid}/bake-light-latest.log

Attached for the duration of ``PackMaterializationOrchestrator.materialize_light_pack``
via ``app.core.generationLogging.generation_world_log``.

Facade only — the implementation is split by bake phase under
``app.application.worldData.pack.bake.log``. Import points for callers do
not change.
"""

from app.application.worldData.pack.bake.log import *  # noqa: F401,F403
from app.application.worldData.pack.bake.log import __all__  # noqa: F401
