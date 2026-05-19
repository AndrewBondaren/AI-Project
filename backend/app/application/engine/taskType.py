from enum import Enum


class TaskType(str, Enum):
    METAGAME_CHAT = "metagame_chat"

    #Scene related
    SCENE_NARRATION = "scene_narration_render"
    SCENE_COMBAT = "scene_combat_render"
    SCENE_CHANGE_LOCATION = "scene_change_location"

    #Character training
    PLAYER_CHARACTER_TRAINING = "player_character_training"
    PLAYER_CHARACTER_TRAINING_MENTOR = "player_character_training_with_mentor"

    #Character generation
    PLAYER_CHARACTER_GENERATION = "player_character_generation"
    NPC_CHARACTER_GENERATION = "npc_character_generation"

    #Event generation
    GENERATE_LOCAL_EVENT = "generate_local_event"
    GENERATE_WORLD_EVENT = "generate_world_event"
    GENERATE_PLAYER_EVENT = "generate_player_event"
    GENERATE_NEW_UNRELATED_EVENT = "generate_new_unrelated_event"
    GENERATE_QUEST_RELATED_EVENT = "generate_quest_related_event"

    #Analysis
    LOCAL_SCENE_ANALYSIS = "local_scene_analysis"
    LOCAL_REGION_ANALYSIS = "local_region_analysis"
    WORLD_STATE_ANALYSIS = "world_state_analysis"
    QUEST_STATE_ANALYSIS = "quest_state_analysis"
    CHARACTER_STATE_ANALYSIS = "character_state_analysis"

    #Crafring
    CRAFT_ARTIFACT = "craft_artifact"
    CRAFT_MATERIAL = "craft_material"
    UPGRADE_ARTIFACT = "upgrade_artifact"

    #Actions
    ACTION_SLEEP = "player_action_sleep"
    ACTION_REST = "player_action_rest"
    ACTION_SNEAK = "player_sneak_action"
    ACTION_DETECT = "player_detection_action"
    ACTION_RUN = "player_run_action"
    ACTION_CLIMB = "player_climb_action"