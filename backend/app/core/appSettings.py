from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.defaultConfig import DefaultConfig
from app.application.llm.language import Language
from app.application.engine.repair.repairMode import RepairMode
from app.core.logLevel import LogLevel, to_logging_level

if TYPE_CHECKING:
    from app.core.container import Container


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
    max_tokens:                  int        = 2048
    language:                    Language   = Language.RUSSIAN
    repair_iterations:           int        = 4
    max_passes:                  int        = 3
    repair_mode:                 RepairMode = RepairMode.MAXIMUM

    # --- Anthropic ---
    anthropic_thinking_budget:   int        = 10000

    # --- Logging ---
    log_level:                   LogLevel   = LogLevel.DEBUG

    # internal — set by Container after creation
    _container: "Container | None" = field(default=None, init=False, repr=False, compare=False)

    def update(self, **kwargs) -> None:
        connection_keys = {
            "qwen_base_url", "qwen_api_key",
            "openai_base_url", "openai_api_key",
            "anthropic_base_url", "anthropic_api_key",
            "llm_streaming",
        }
        if "language" in kwargs:
            kwargs["language"] = Language(kwargs["language"])
        if "repair_mode" in kwargs:
            kwargs["repair_mode"] = RepairMode(kwargs["repair_mode"])
        if "log_level" in kwargs:
            kwargs["log_level"] = LogLevel(kwargs["log_level"])

        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise ValueError(f"Unknown setting: {key!r}")
            setattr(self, key, value)

        if connection_keys & kwargs.keys():
            if self._container is not None:
                self._container.invalidate_clients()

        if "log_level" in kwargs:
            from app.core.logging_config import setup_logging
            setup_logging(level=to_logging_level(self.log_level))


# module-level singleton
app_settings = AppSettings()
