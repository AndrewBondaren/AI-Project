class StateBuilder:
    def build(self, session_id: str, message: str):

        # позже сюда подключишь:
        # - session_repo
        # - character_repo
        # - game_data loader

        return {
            "session_id": session_id,
            "user_message": message,
            "character": {
                "name": "Hero",
                "level": 10,
            },
            "world_state": {},
            "memory": []
        }