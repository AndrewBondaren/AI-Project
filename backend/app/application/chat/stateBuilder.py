class StateBuilder:
    def build(self, session: str, message: str):

        # позже сюда подключишь:
        # - session_repo
        # - character_repo
        # - game_data loader

        return {
            "session": session,
            "user_message": message,
            "character": {
                "name": "Hero",
                "level": 10,
            },
            "world_state": {},
            "memory": []
        }