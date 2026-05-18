from enum import Enum


class TaskType(str, Enum):
    METAGAME_CHAT = "metagame_chat"
    SCENE_NARRATION = "scene_narration"
    SCENE_CREATION = "scene_creation"
    SCENE_COMBAT = "scene_combat"
    PLAYER_CHARACTER_GENERATION="player_characrter_generation"
    NPC_CHARACTER_GENERATION = "npc_character_generation"
    GENERATE_LOCAL_EVENT = "generate_local_event"
    GENERATE_WORLD_EVENT = "generate_world_event"
    GENERATE_PLAYER_EVENT = "generate_player_event"
    CRAFT_ARTIFACT = "craft_artifact"
    ANALYSIS = "context_analysis"