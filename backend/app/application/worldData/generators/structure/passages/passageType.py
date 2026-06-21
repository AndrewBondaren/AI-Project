from enum import Enum


class PassageType(str, Enum):
    def __str__(self) -> str:
        return self.value

    STAIRCASE        = "staircase"
    DOORWAY          = "doorway"
    ARCHWAY          = "archway"
    MAIN_ENTRANCE    = "main_entrance"
    SERVICE_ENTRANCE = "service_entrance"
