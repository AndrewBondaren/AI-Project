from enum import Enum


class TaskType(str, Enum):
    CHAT = "chat"
    NARRATION = "narration"
    SCENE = "scene"
    CHARACTER = "character"
    EVENT = "event"
    ANALYSIS = "analysis"