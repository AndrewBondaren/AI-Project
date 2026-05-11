from pydantic import BaseModel
from typing import List, Dict, Any


class NarrationContract(BaseModel):
    text: str


class SceneContract(BaseModel):
    title: str
    description: str
    location: str
    actors: List[str]


class CharacterContract(BaseModel):
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


CONTRACT_REGISTRY = {
    "narration": NarrationContract,
    "scene": SceneContract,
    "character": CharacterContract,
    "event": EventContract,
    "analysis": AnalysisContract,
}