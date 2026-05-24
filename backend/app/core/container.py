from app.core.settings_service import SettingsService
from app.application.llm.clients.qwenClient import QwenClient
from app.application.llm.clients.openAIClient import OpenAIClient
from app.application.llm.clients.anthropicClient import AnthropicClient
from app.application.llm.router import LLMRouter
from app.application.chat.chatService import ChatService
from app.db.database import Database
from app.db.repositories.iWorldRepository import IWorldRepository
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository
from app.db.repositories.iSessionRepository import ISessionRepository
from app.db.repositories.sqlite.sessionRepository import SqliteSessionRepository
from app.db.repositories.iMessageRepository import IMessageRepository
from app.db.repositories.sqlite.messageRepository import SqliteMessageRepository
from app.db.repositories.iPlayerRepository import IPlayerRepository
from app.db.repositories.sqlite.playerRepository import SqlitePlayerRepository
from app.db.repositories.iNpcRepository import INpcRepository
from app.db.repositories.sqlite.npcRepository import SqliteNpcRepository
from app.db.repositories.iRaceRepository import IRaceRepository
from app.db.repositories.sqlite.raceRepository import SqliteRaceRepository
from app.db.repositories.iWorldPerkRepository import IWorldPerkRepository
from app.db.repositories.sqlite.worldPerkRepository import SqliteWorldPerkRepository
from app.db.repositories.iNamedLocationRepository import INamedLocationRepository
from app.db.repositories.sqlite.namedLocationRepository import SqliteNamedLocationRepository
from app.application.worldData.worldService import WorldService
from app.application.worldData.raceService import RaceService
from app.application.worldData.worldPerkService import WorldPerkService
from app.application.worldData.namedLocationService import NamedLocationService
from app.application.worldData.seedService import SeedService
from app.application.worldData.worldBundleService import WorldBundleService
from app.application.worldData.playerService import PlayerService
from app.application.worldData.gameSessionService import GameSessionService

from app.application.engine.dag.dagExecutor import DAGExecutor
from app.application.engine.llmExecutionEngine import LLMExecutionEngine
from app.application.engine.graphs.graphCompiler import GraphCompiler
from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.execution.llmAggregateExecutor import LLMAggregateExecutor
from app.application.engine.execution.nodeRunner import NodeRunner
from app.application.engine.prompt.dslRegistry import DSLRegistry
from app.application.engine.prompt.dslResolver import DSLResolver
from app.application.engine.prompt.llmGroupPayloadBuilder import LLMGroupPayloadBuilder
from app.application.engine.validation.llmValidator import LLMValidator
from app.application.engine.validation.contractValidator import ContractValidator
from app.application.engine.validation.nodeValidator import NodeValidator
from app.application.engine.repair.repairOrchestrator import RepairOrchestrator
from app.application.engine.repair.repairBuilder import RepairBuilder
from app.application.engine.repair.patchApplier import PatchApplier
from app.application.engine.repair.dslFailureProjector import DSLFailureProjector
from app.application.engine.rules.ruleEngine import RuleEngine
from app.application.engine.rules.ruleCompiler import RuleCompiler
from app.application.engine.rules.ruleHandlerRegistry import RuleHandlerRegistry
from app.application.engine.rules.taskRuleHandler import TaskRuleHandler

# Импорт нод = их регистрация в NODE_REGISTRY
import app.application.engine.nodes  # noqa: F401

from app.application.cancellation.snapshotStore import snapshot_store
from app.core.appSettings import app_settings


class Container:

    def __init__(self, config_manager, db: Database):
        self._config_manager = config_manager
        self._db = db

        # REPOSITORIES
        self._world_repository: IWorldRepository | None = None
        self._session_repository: ISessionRepository | None = None
        self._player_repository: IPlayerRepository | None = None
        self._npc_repository: INpcRepository | None = None
        self._message_repository: IMessageRepository | None = None
        self._race_repository: IRaceRepository | None = None
        self._perk_repository: IWorldPerkRepository | None = None
        self._location_repository: INamedLocationRepository | None = None

        # DOMAIN SERVICES
        self._player_service: PlayerService | None = None
        self._game_session_service: GameSessionService | None = None
        self._world_service: WorldService | None = None
        self._race_service: RaceService | None = None
        self._perk_service: WorldPerkService | None = None
        self._location_service: NamedLocationService | None = None
        self._seed_service: SeedService | None = None
        self._world_bundle_service: WorldBundleService | None = None

        # CLIENTS
        self._qwen_client = None
        self._openai_client = None
        self._anthropic_client = None

        # ROUTING
        self._llm_router = None

        # RULES
        self._rule_handler_registry = None
        self._rule_compiler = None
        self._rule_engine = None

        # GRAPH
        self._graph_compiler = None

        # EXECUTION
        self._node_runner = None
        self._python_node_executor = None
        self._llm_aggregate_executor = None
        self._dag_executor = None

        # PROMPT
        self._dsl_registry = None
        self._dsl_resolver = None
        self._payload_builder = None

        # VALIDATION & REPAIR
        self._node_validator = None
        self._llm_validator = None
        self._repair_orchestrator = None
        self._patch_applier = None

        # ENGINE & SERVICES
        self._llm_engine = None
        self._chat_service = None
        self._settings_service = None

    # =====================================================
    # CLIENTS
    # =====================================================

    def invalidate_clients(self) -> None:
        self._qwen_client      = None
        self._openai_client    = None
        self._anthropic_client = None
        self._llm_router       = None

    def qwen_client(self):
        if self._qwen_client is None:
            self._qwen_client = QwenClient(
                base_url=app_settings.qwen_base_url,
                api_key=app_settings.qwen_api_key,
                streaming=app_settings.llm_streaming,
            )
        return self._qwen_client

    def openai_client(self):
        if self._openai_client is None:
            self._openai_client = OpenAIClient(
                base_url=app_settings.openai_base_url,
                api_key=app_settings.openai_api_key,
                streaming=app_settings.llm_streaming,
            )
        return self._openai_client

    def anthropic_client(self):
        if self._anthropic_client is None:
            self._anthropic_client = AnthropicClient(
                base_url=app_settings.anthropic_base_url,
                api_key=app_settings.anthropic_api_key,
                streaming=app_settings.llm_streaming,
            )
        return self._anthropic_client

    # =====================================================
    # ROUTING
    # =====================================================

    def llm_router(self):
        if self._llm_router is None:
            self._llm_router = LLMRouter(
                qwen_client=self.qwen_client(),
                openai_client=self.openai_client(),
                anthropic_client=self.anthropic_client()
            )
        return self._llm_router

    # =====================================================
    # RULES
    # =====================================================

    def rule_handler_registry(self):
        if self._rule_handler_registry is None:
            registry = RuleHandlerRegistry()
            registry.register("task", TaskRuleHandler())
            self._rule_handler_registry = registry
        return self._rule_handler_registry

    def rule_compiler(self):
        if self._rule_compiler is None:
            self._rule_compiler = RuleCompiler(
                registry=self.rule_handler_registry()
            )
        return self._rule_compiler

    def rule_engine(self):
        if self._rule_engine is None:
            self._rule_engine = RuleEngine()
        return self._rule_engine

    # =====================================================
    # GRAPH
    # =====================================================

    def graph_compiler(self):
        if self._graph_compiler is None:
            compiler = GraphCompiler(
                rule_engine=self.rule_engine(),
                rule_compiler=self.rule_compiler()
            )
            compiler.precompile()
            self._graph_compiler = compiler
        return self._graph_compiler

    # =====================================================
    # PROMPT
    # =====================================================

    def dsl_registry(self):
        if self._dsl_registry is None:
            self._dsl_registry = DSLRegistry(base_path="app/dsl")
        return self._dsl_registry

    def dsl_resolver(self):
        if self._dsl_resolver is None:
            self._dsl_resolver = DSLResolver(
                dsl_registry=self.dsl_registry()
            )
        return self._dsl_resolver

    def payload_builder(self):
        if self._payload_builder is None:
            self._payload_builder = LLMGroupPayloadBuilder(
                dsl_resolver=self.dsl_resolver()
            )
        return self._payload_builder

    # =====================================================
    # VALIDATION
    # =====================================================

    def node_validator(self):
        if self._node_validator is None:
            self._node_validator = NodeValidator()
        return self._node_validator

    def llm_validator(self):
        if self._llm_validator is None:
            self._llm_validator = LLMValidator(
                contract_validator=ContractValidator(),
                node_validator=self.node_validator()
            )
        return self._llm_validator

    # =====================================================
    # REPAIR
    # =====================================================

    def patch_applier(self):
        if self._patch_applier is None:
            self._patch_applier = PatchApplier()
        return self._patch_applier

    def repair_orchestrator(self):
        if self._repair_orchestrator is None:
            self._repair_orchestrator = RepairOrchestrator(
                dsl_resolver=self.dsl_resolver(),
                repair_builder=RepairBuilder(
                    payload_builder=self.payload_builder(),
                    failure_projector=DSLFailureProjector()
                ),
                llm_validator=self.llm_validator()
            )
        return self._repair_orchestrator

    # =====================================================
    # EXECUTION
    # =====================================================

    def python_node_executor(self):
        if self._python_node_executor is None:
            self._python_node_executor = PythonNodeExecutor()
        return self._python_node_executor

    def llm_aggregate_executor(self):
        if self._llm_aggregate_executor is None:
            self._llm_aggregate_executor = LLMAggregateExecutor(
                payload_builder=self.payload_builder(),
                llm_validator=self.llm_validator(),
                dsl_resolver=self.dsl_resolver(),
                dsl_registry=self.dsl_registry(),
                repair_orchestrator=self.repair_orchestrator(),
                router=self.llm_router()
            )
        return self._llm_aggregate_executor

    def node_runner(self):
        if self._node_runner is None:
            self._node_runner = NodeRunner(
                node_validator=self.node_validator()
            )
        return self._node_runner

    def dag_executor(self):
        if self._dag_executor is None:
            self._dag_executor = DAGExecutor(
                node_runner=self.node_runner(),
                llm_aggregate_executor=self.llm_aggregate_executor()
            )
        return self._dag_executor

    def executors(self) -> dict:
        return {
            PythonNodeExecutor: self.python_node_executor(),
        }

    # =====================================================
    # ENGINE
    # =====================================================

    def llm_engine(self):
        if self._llm_engine is None:
            self._llm_engine = LLMExecutionEngine(
                dag_executor=self.dag_executor(),
                graph_compiler=self.graph_compiler(),
                patch_applier=self.patch_applier(),
                executors=self.executors(),
                snapshot_store=snapshot_store,
            )
        return self._llm_engine

    # =====================================================
    # SERVICES
    # =====================================================

    def chat_service(self):
        if self._chat_service is None:
            self._chat_service = ChatService(
                llm_engine=self.llm_engine()
            )
        return self._chat_service

    def settings_service(self):
        if self._settings_service is None:
            self._settings_service = SettingsService(
                config_manager=self._config_manager,
                container=self,
            )
        return self._settings_service

    # =====================================================
    # REPOSITORIES
    # =====================================================

    def world_repository(self) -> IWorldRepository:
        if self._world_repository is None:
            self._world_repository = SqliteWorldRepository(db=self._db)
        return self._world_repository

    def race_repository(self) -> IRaceRepository:
        if self._race_repository is None:
            self._race_repository = SqliteRaceRepository(db=self._db)
        return self._race_repository

    def perk_repository(self) -> IWorldPerkRepository:
        if self._perk_repository is None:
            self._perk_repository = SqliteWorldPerkRepository(db=self._db)
        return self._perk_repository

    def location_repository(self) -> INamedLocationRepository:
        if self._location_repository is None:
            self._location_repository = SqliteNamedLocationRepository(db=self._db)
        return self._location_repository

    def world_service(self) -> WorldService:
        if self._world_service is None:
            self._world_service = WorldService(repo=self.world_repository())
        return self._world_service

    def race_service(self) -> RaceService:
        if self._race_service is None:
            self._race_service = RaceService(repo=self.race_repository())
        return self._race_service

    def perk_service(self) -> WorldPerkService:
        if self._perk_service is None:
            self._perk_service = WorldPerkService(repo=self.perk_repository())
        return self._perk_service

    def location_service(self) -> NamedLocationService:
        if self._location_service is None:
            self._location_service = NamedLocationService(repo=self.location_repository())
        return self._location_service

    def seed_service(self) -> SeedService:
        if self._seed_service is None:
            self._seed_service = SeedService(db=self._db)
        return self._seed_service

    def world_bundle_service(self) -> WorldBundleService:
        if self._world_bundle_service is None:
            self._world_bundle_service = WorldBundleService(
                world_service=self.world_service(),
                race_service=self.race_service(),
                perk_service=self.perk_service(),
                location_service=self.location_service(),
            )
        return self._world_bundle_service

    def session_repository(self) -> ISessionRepository:
        if self._session_repository is None:
            self._session_repository = SqliteSessionRepository(db=self._db)
        return self._session_repository

    def message_repository(self) -> IMessageRepository:
        if self._message_repository is None:
            self._message_repository = SqliteMessageRepository(db=self._db)
        return self._message_repository

    def player_repository(self) -> IPlayerRepository:
        if self._player_repository is None:
            self._player_repository = SqlitePlayerRepository(db=self._db)
        return self._player_repository

    def player_service(self) -> PlayerService:
        if self._player_service is None:
            self._player_service = PlayerService(repo=self.player_repository())
        return self._player_service

    def game_session_service(self) -> GameSessionService:
        if self._game_session_service is None:
            self._game_session_service = GameSessionService(
                repo=self.session_repository(),
                world_repo=self.world_repository(),
                player_repo=self.player_repository(),
            )
        return self._game_session_service

    def npc_repository(self) -> INpcRepository:
        if self._npc_repository is None:
            self._npc_repository = SqliteNpcRepository(db=self._db)
        return self._npc_repository