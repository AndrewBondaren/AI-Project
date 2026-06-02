# Импорт = регистрация. Порядок не важен.

#LLM Nodes.
from app.application.engine.nodes.pojo.llm import IntentDetectionNode, ContextSnapGathererNode  # noqa: F401

#Python Nodes.
from app.application.engine.nodes.pojo.python import prepareAnalysisContextNode
from app.application.engine.nodes.pojo.python import checkSceneNode
from app.application.engine.nodes.pojo.python import sceneInitNode
from app.application.engine.nodes.pojo.python import sceneLocationSelectNode
from app.application.engine.nodes.pojo.python.terrain import checkTerrainNode
from app.application.engine.nodes.pojo.python.terrain import eagerTerrainNode
from app.application.engine.nodes.pojo.python.terrain import lazyTerrainNode
from app.application.engine.nodes.pojo.python.terrain import terrainContextNode