from dataclasses import dataclass, field

from app.core.defaultConfig import DefaultConfig
from app.application.llm.language import Language
from app.application.engine.repair.repairMode import RepairMode
from app.core.logLevel import LogLevel
from app.core.distanceUnit import DistanceUnit


@dataclass
class AppSettings:
    # --- LLM connection ---
    qwen_base_url:      str  = field(default_factory=lambda: DefaultConfig.QWEN_BASE_URL)
    qwen_api_key:       str  = field(default_factory=lambda: DefaultConfig.QWEN_API_KEY)

    openai_base_url:    str  = field(default_factory=lambda: DefaultConfig.OPENAI_BASE_URL)
    openai_api_key:     str  = field(default_factory=lambda: DefaultConfig.OPENAI_API_KEY)

    anthropic_base_url: str  = field(default_factory=lambda: DefaultConfig.ANTHROPIC_BASE_URL)
    anthropic_api_key:  str  = field(default_factory=lambda: DefaultConfig.ANTHROPIC_API_KEY)

    # --- Infra ---
    llm_streaming:      bool = field(default_factory=lambda: DefaultConfig.LLM_STREAMING)

    # --- Behaviour ---
    max_tokens:                 int          = 2048
    language:                   Language     = Language.RUSSIAN
    repair_iterations:          int          = 4
    max_passes:                 int          = 3
    repair_mode:                RepairMode   = RepairMode.MAXIMUM

    # --- World units ---
    distance_unit:              DistanceUnit = DistanceUnit.METERS
    cell_size:                  int          = 10  # метров в одной ячейке карты

    # --- Anthropic ---
    anthropic_thinking_budget:  int        = 10000

    # --- Prompt role ---
    system_role_providers:      frozenset  = field(default_factory=frozenset)

    # --- Database ---
    db_path:                    str        = field(default_factory=lambda: DefaultConfig.DB_PATH)

    # --- Logger overrides ---
    logger_levels:              dict       = field(default_factory=lambda: dict(DefaultConfig.LOGGER_LEVELS))

    # --- Logging ---
    log_level:                  LogLevel   = LogLevel.DEBUG

    def update(self, **kwargs) -> None:
        if "language" in kwargs:
            kwargs["language"] = Language(kwargs["language"])
        if "repair_mode" in kwargs:
            kwargs["repair_mode"] = RepairMode(kwargs["repair_mode"])
        if "log_level" in kwargs:
            kwargs["log_level"] = LogLevel(kwargs["log_level"])
        if "distance_unit" in kwargs:
            kwargs["distance_unit"] = DistanceUnit(kwargs["distance_unit"])
        if "system_role_providers" in kwargs:
            kwargs["system_role_providers"] = frozenset(kwargs["system_role_providers"])

        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise ValueError(f"Unknown setting: {key!r}")
            setattr(self, key, value)


# module-level singleton
app_settings = AppSettings()
