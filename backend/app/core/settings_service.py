from app.core.appSettings import app_settings
from app.core.logging_config import setup_logging
from app.core.logLevel import to_logging_level


class SettingsService:

    _CONNECTION_KEYS = {
        "qwen_base_url", "qwen_api_key",
        "openai_base_url", "openai_api_key",
        "anthropic_base_url", "anthropic_api_key",
        "llm_streaming",
    }

    def __init__(self, config_manager, container):
        self._config_manager = config_manager
        self._container = container

    def update(self, **kwargs) -> None:
        app_settings.update(**kwargs)
        self._config_manager.save(app_settings)
        if self._CONNECTION_KEYS & kwargs.keys():
            self._container.invalidate_clients()
        if "log_level" in kwargs:
            setup_logging(level=to_logging_level(app_settings.log_level))
