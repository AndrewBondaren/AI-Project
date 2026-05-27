# Импорт = регистрация. Порядок не важен.

#LLM Nodes.
from app.application.engine.nodes.pojo.llm import IntentDetectionNode, ContextSnapGathererNode  # noqa: F401

#Python Nodes.
from app.application.engine.nodes.pojo.python import prepareAnalysisContextNode
from app.application.engine.nodes.pojo.python import checkSceneNode