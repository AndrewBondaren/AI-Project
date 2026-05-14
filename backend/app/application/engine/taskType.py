from enum import Enum


class TaskType(str, Enum):
    CHAT = "chat"
    SCENE_NARRATION = "scene_narration"
    SCENE_CREATION = "scene_creation"
    SCENE_COMBAT = "scene_combat"
    CHARACTER_GENERATION = "character_generation"
    WORLD_EVENT = "generate_world_event"
    PLAYER_EVENT = "generate_player_event"
    CRAFT_ARTIFACT = "craft_artifact"
    ANALYSIS = "context_analysis"