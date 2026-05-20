from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.defaultConfig import DefaultConfig
from app.application.llm.language import Language

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
    max_tokens:         int  = 2048
    language:           Language = Language.RUSSIAN
    repair_iterations:  int  = 4
    max_passes:         int  = 3

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
            kwargs["language"] = Language(kwargs["language"])  # validates + coerces str → Language

        for key, value in kwargs.items():
            if not hasattr(self, key):
                raise ValueError(f"Unknown setting: {key!r}")
            setattr(self, key, value)

        # if connection settings changed — invalidate cached clients
        if connection_keys & kwargs.keys():
            if self._container is not None:
                self._container.invalidate_clients()


# module-level singleton
app_settings = AppSettings()
