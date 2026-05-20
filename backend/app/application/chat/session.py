from dataclasses import dataclass, field
from app.core.appSettings import app_settings
from app.application.llm.language import Language
from app.application.engine.repair.repairMode import RepairMode


@dataclass
class Session:
    llm_provider: str
    model:        str
    session_id:      str
    meta:         dict

    max_tokens:        int        = field(default_factory=lambda: app_settings.max_tokens)
    repair_iterations: int        = field(default_factory=lambda: app_settings.repair_iterations)
    repair_mode:       RepairMode = field(default_factory=lambda: app_settings.repair_mode)
    language:          Language   = field(default_factory=lambda: app_settings.language)
    max_passes:        int        = field(default_factory=lambda: app_settings.max_passes)
    timeout:           int        = 120
