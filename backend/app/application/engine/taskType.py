from enum import Enum


class TaskType(str, Enum):
    def __new__(cls, value: str, is_technical: bool = False):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.is_technical = is_technical
        return obj

    INTENT_DETECTION = ("intent_detection", True)
    SCENE_INIT       = ("scene_init",       True)

    #Scene related
    SCENE_NARRATION = ("scene_narration_render", False)
    SCENE_COMBAT = ("scene_combat_render", False)
    SCENE_CHANGE_LOCATION = ("scene_change_location", False)

    #Character training
    PLAYER_CHARACTER_TRAINING = ("player_character_training", False)
    PLAYER_CHARACTER_TRAINING_MENTOR = ("player_character_training_with_mentor", False)

    #Character generation
    PLAYER_CHARACTER_GENERATION = ("player_character_generation", False)
    NPC_CHARACTER_GENERATION = ("npc_character_generation", False)

    #Event generation
    GENERATE_LOCAL_EVENT = ("generate_local_event", False)
    GENERATE_WORLD_EVENT = ("generate_world_event", False)
    GENERATE_PLAYER_EVENT = ("generate_player_event", False)
    GENERATE_NEW_UNRELATED_EVENT = ("generate_new_unrelated_event", False)
    GENERATE_QUEST_RELATED_EVENT = ("generate_quest_related_event", False)

    #Analysis
    LOCAL_SCENE_ANALYSIS = ("local_scene_analysis", False)
    LOCAL_REGION_ANALYSIS = ("local_region_analysis", False)
    WORLD_STATE_ANALYSIS = ("world_state_analysis", False)
    QUEST_STATE_ANALYSIS = ("quest_state_analysis", False)
    CHARACTER_STATE_ANALYSIS = ("character_state_analysis", False)

    #Crafting
    CRAFT_ARTIFACT = ("craft_artifact", False)
    CRAFT_MATERIAL = ("craft_material", False)
    UPGRADE_ARTIFACT = ("upgrade_artifact", False)

    #Actions
    ACTION_SLEEP = ("player_action_sleep", False)
    ACTION_REST = ("player_action_rest", False)
    ACTION_SNEAK = ("player_sneak_action", False)
    ACTION_DETECT = ("player_detection_action", False)
    ACTION_RUN = ("player_run_action", False)
    ACTION_CLIMB = ("player_climb_action", False)
