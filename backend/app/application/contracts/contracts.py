from pydantic import BaseModel
from typing import List, Dict, Any

from app.application.contracts.IntentItem import IntentItem


class NarrationContract(BaseModel):
    text: str


class IntentDetectionContract(BaseModel):
    intents: List[IntentItem]
    global_confidence: float | None = None
    reasoning: str | None = None


class SceneContract(BaseModel):
    title: str
    description: str
    location: str
    actors: List[str]


class CharacterCreationContract(BaseModel):
    name: str
    traits: List[str]
    motivation: str

class CharacterUpdateContract(BaseModel):
    name: str
    traits: List[str]
    motivation: str

class EventContract(BaseModel):
    name: str
    description: str
    impact: Dict[str, Any]


class AnalysisContract(BaseModel):
    summary: str
    conclusions: List[str]
    risks: List[str]