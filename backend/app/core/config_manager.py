import sys
from pathlib import Path

import tomlkit

_APP_NAME = "AIProject"


class ConfigManager:

    def __init__(self, path: Path | None = None):
        self.path = path or self._resolve_path()

    @staticmethod
    def _resolve_path() -> Path:
        if getattr(sys, "frozen", False):
            import os
            appdata = Path(os.environ.get("APPDATA", Path.home()))
            config_dir = appdata / _APP_NAME
            config_dir.mkdir(parents=True, exist_ok=True)
            return config_dir / "config.toml"
        return Path(__file__).parent.parent.parent / "config.toml"

    def load(self) -> dict:
        if not self.path.exists():
            self._write_defaults()
        with open(self.path, encoding="utf-8") as f:
            data = tomlkit.load(f)
        return self._to_flat(data)

    def save(self, settings) -> None:
        doc = self._to_nested(settings)
        with open(self.path, "w", encoding="utf-8") as f:
            tomlkit.dump(doc, f)

    def _write_defaults(self) -> None:
        from app.core.appSettings import AppSettings
        self.save(AppSettings())

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _to_flat(self, data) -> dict:
        llm        = data.get("llm", {})
        qwen       = llm.get("qwen", {})
        openai_    = llm.get("openai", {})
        anthropic_ = llm.get("anthropic", {})
        behaviour  = data.get("behaviour", {})
        infra      = data.get("infra", {})
        logging_   = data.get("logging", {})

        result: dict = {}

        _copy(result, qwen,       "base_url",        "qwen_base_url")
        _copy(result, qwen,       "api_key",          "qwen_api_key")
        _copy(result, openai_,    "base_url",         "openai_base_url")
        _copy(result, openai_,    "api_key",          "openai_api_key")
        _copy(result, anthropic_, "base_url",         "anthropic_base_url")
        _copy(result, anthropic_, "api_key",          "anthropic_api_key")
        _copy(result, anthropic_, "thinking_budget",  "anthropic_thinking_budget")

        _copy(result, behaviour, "language")
        _copy(result, behaviour, "repair_iterations")
        _copy(result, behaviour, "max_passes")
        _copy(result, behaviour, "max_tokens")
        _copy(result, behaviour, "repair_mode")
        if "system_role_providers" in behaviour:
            result["system_role_providers"] = list(behaviour["system_role_providers"])

        _copy(result, infra,    "streaming", "llm_streaming")
        _copy(result, logging_, "level",     "log_level")

        return result

    def _to_nested(self, s) -> dict:
        return {
            "llm": {
                "qwen": {
                    "base_url": s.qwen_base_url,
                    "api_key":  s.qwen_api_key,
                },
                "openai": {
                    "base_url": s.openai_base_url,
                    "api_key":  s.openai_api_key,
                },
                "anthropic": {
                    "base_url":        s.anthropic_base_url,
                    "api_key":         s.anthropic_api_key,
                    "thinking_budget": s.anthropic_thinking_budget,
                },
            },
            "behaviour": {
                "language":              str(s.language),
                "repair_iterations":     s.repair_iterations,
                "max_passes":            s.max_passes,
                "max_tokens":            s.max_tokens,
                "repair_mode":           str(s.repair_mode),
                "system_role_providers": sorted(s.system_role_providers),
            },
            "infra": {
                "streaming": s.llm_streaming,
            },
            "logging": {
                "level": str(s.log_level),
            },
        }


def _copy(dst: dict, src: dict, src_key: str, dst_key: str | None = None) -> None:
    if src_key in src:
        dst[dst_key or src_key] = src[src_key]
