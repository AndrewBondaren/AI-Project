"""Session-facing wiring: chat, settings, player, game session."""

from app.core.settingsService import SettingsService
from app.application.chat.chatService import ChatService
from app.application.session.playerService import PlayerService
from app.application.session.gameSessionService import GameSessionService


class SessionWiring:
    """Player/session/chat/settings services."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._player_service: PlayerService | None = None
        self._game_session_service: GameSessionService | None = None
        self._chat_service = None
        self._settings_service = None

    def chat_service(self):
        if self._chat_service is None:
            self._chat_service = ChatService(
                llm_engine=self.llm_engine(),
                message_repo=self.message_repository(),
                pending_repo=self.pending_repository(),
            )
        return self._chat_service

    def settings_service(self):
        if self._settings_service is None:
            self._settings_service = SettingsService(
                config_manager=self._config_manager,
                container=self,
            )
        return self._settings_service

    def player_service(self) -> PlayerService:
        if self._player_service is None:
            self._player_service = PlayerService(repo=self.player_repository())
        return self._player_service

    def game_session_service(self) -> GameSessionService:
        if self._game_session_service is None:
            self._game_session_service = GameSessionService(
                repo=self.session_repository(),
                world_repo=self.world_repository(),
                player_repo=self.player_repository(),
            )
        return self._game_session_service
