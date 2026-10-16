"""Repository lazy singletons, shared by the application container."""

from app.db.repositories.iWorldRepository import IWorldRepository
from app.db.repositories.sqlite.worldRepository import SqliteWorldRepository
from app.db.repositories.iSessionRepository import ISessionRepository
from app.db.repositories.sqlite.sessionRepository import SqliteSessionRepository
from app.db.repositories.iMessageRepository import IMessageRepository
from app.db.repositories.sqlite.messageRepository import SqliteMessageRepository
from app.db.repositories.iPendingRepository import IPendingRepository
from app.db.repositories.sqlite.pendingRepository import SqlitePendingRepository
from app.db.repositories.iSceneRepository import ISceneRepository
from app.db.repositories.sqlite.sceneRepository import SqliteSceneRepository
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
from app.db.repositories.iMapCellRepository import IMapCellRepository
from app.db.repositories.sqlite.mapCellRepository import SqliteMapCellRepository
from app.db.repositories.iConnectionNodeRepository import IConnectionNodeRepository
from app.db.repositories.sqlite.connectionNodeRepository import SqliteConnectionNodeRepository
from app.db.repositories.iConnectionEdgeRepository import IConnectionEdgeRepository
from app.db.repositories.sqlite.connectionEdgeRepository import SqliteConnectionEdgeRepository
from app.db.repositories.iConnectionEdgeCellRepository import IConnectionEdgeCellRepository
from app.db.repositories.sqlite.connectionEdgeCellRepository import SqliteConnectionEdgeCellRepository
from app.db.repositories.iStateRepository import IStateRepository
from app.db.repositories.sqlite.stateRepository import SqliteStateRepository
from app.db.repositories.iLocationLevelRepository import ILocationLevelRepository
from app.db.repositories.sqlite.locationLevelRepository import SqliteLocationLevelRepository
from app.db.repositories.iReliefTemplateRepository import IReliefTemplateRepository
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository
from app.db.repositories.sqlite.reliefTemplateRepository import SqliteReliefTemplateRepository
from app.db.repositories.sqlite.reliefGradeRepository import SqliteReliefGradeRepository
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository
from app.db.repositories.sqlite.libraryPackRepository import SqliteLibraryPackRepository
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.sqlite.libraryPackMemberRepository import SqliteLibraryPackMemberRepository
from app.db.repositories.iLibraryPackDependencyRepository import ILibraryPackDependencyRepository
from app.db.repositories.sqlite.libraryPackDependencyRepository import SqliteLibraryPackDependencyRepository
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository
from app.db.repositories.sqlite.chunkRefineJobRepository import SqliteChunkRefineJobRepository


class RepositoriesWiring:
    """Lazy Sqlite* repository singletons over ``self._db``."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._world_repository: IWorldRepository | None = None
        self._session_repository: ISessionRepository | None = None
        self._player_repository: IPlayerRepository | None = None
        self._npc_repository: INpcRepository | None = None
        self._message_repository: IMessageRepository | None = None
        self._pending_repository: IPendingRepository | None = None
        self._scene_repository: ISceneRepository | None = None
        self._race_repository: IRaceRepository | None = None
        self._perk_repository: IWorldPerkRepository | None = None
        self._location_repository: INamedLocationRepository | None = None
        self._location_level_repository: ILocationLevelRepository | None = None
        self._map_cell_repository: IMapCellRepository | None = None
        self._connection_node_repository: IConnectionNodeRepository | None = None
        self._connection_edge_repository: IConnectionEdgeRepository | None = None
        self._connection_edge_cell_repository: IConnectionEdgeCellRepository | None = None
        self._state_repository: IStateRepository | None = None
        self._relief_template_repository: IReliefTemplateRepository | None = None
        self._relief_grade_repository: IReliefGradeRepository | None = None
        self._library_pack_repository: ILibraryPackRepository | None = None
        self._library_pack_member_repository: ILibraryPackMemberRepository | None = None
        self._library_pack_dependency_repository: ILibraryPackDependencyRepository | None = None
        self._chunk_refine_job_repository = None

    def world_repository(self) -> IWorldRepository:
        if self._world_repository is None:
            self._world_repository = SqliteWorldRepository(db=self._db)
        return self._world_repository

    def session_repository(self) -> ISessionRepository:
        if self._session_repository is None:
            self._session_repository = SqliteSessionRepository(db=self._db)
        return self._session_repository

    def message_repository(self) -> IMessageRepository:
        if self._message_repository is None:
            self._message_repository = SqliteMessageRepository(db=self._db)
        return self._message_repository

    def pending_repository(self) -> IPendingRepository:
        if self._pending_repository is None:
            self._pending_repository = SqlitePendingRepository(db=self._db)
        return self._pending_repository

    def scene_repository(self) -> ISceneRepository:
        if self._scene_repository is None:
            self._scene_repository = SqliteSceneRepository(db=self._db)
        return self._scene_repository

    def player_repository(self) -> IPlayerRepository:
        if self._player_repository is None:
            self._player_repository = SqlitePlayerRepository(db=self._db)
        return self._player_repository

    def npc_repository(self) -> INpcRepository:
        if self._npc_repository is None:
            self._npc_repository = SqliteNpcRepository(db=self._db)
        return self._npc_repository

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

    def location_level_repository(self) -> ILocationLevelRepository:
        if self._location_level_repository is None:
            self._location_level_repository = SqliteLocationLevelRepository(db=self._db)
        return self._location_level_repository

    def map_cell_repository(self) -> IMapCellRepository:
        if self._map_cell_repository is None:
            self._map_cell_repository = SqliteMapCellRepository(db=self._db)
        return self._map_cell_repository

    def chunk_refine_job_repository(self) -> IChunkRefineJobRepository:
        if self._chunk_refine_job_repository is None:
            self._chunk_refine_job_repository = SqliteChunkRefineJobRepository(db=self._db)
        return self._chunk_refine_job_repository

    def connection_node_repository(self) -> IConnectionNodeRepository:
        if self._connection_node_repository is None:
            self._connection_node_repository = SqliteConnectionNodeRepository(db=self._db)
        return self._connection_node_repository

    def connection_edge_repository(self) -> IConnectionEdgeRepository:
        if self._connection_edge_repository is None:
            self._connection_edge_repository = SqliteConnectionEdgeRepository(db=self._db)
        return self._connection_edge_repository

    def connection_edge_cell_repository(self) -> IConnectionEdgeCellRepository:
        if self._connection_edge_cell_repository is None:
            self._connection_edge_cell_repository = SqliteConnectionEdgeCellRepository(db=self._db)
        return self._connection_edge_cell_repository

    def state_repository(self) -> IStateRepository:
        if self._state_repository is None:
            self._state_repository = SqliteStateRepository(db=self._db)
        return self._state_repository

    def relief_template_repository(self) -> IReliefTemplateRepository:
        if self._relief_template_repository is None:
            self._relief_template_repository = SqliteReliefTemplateRepository(db=self._db)
        return self._relief_template_repository

    def relief_grade_repository(self) -> IReliefGradeRepository:
        if self._relief_grade_repository is None:
            self._relief_grade_repository = SqliteReliefGradeRepository(db=self._db)
        return self._relief_grade_repository

    def library_pack_repository(self) -> ILibraryPackRepository:
        if self._library_pack_repository is None:
            self._library_pack_repository = SqliteLibraryPackRepository(db=self._db)
        return self._library_pack_repository

    def library_pack_member_repository(self) -> ILibraryPackMemberRepository:
        if self._library_pack_member_repository is None:
            self._library_pack_member_repository = SqliteLibraryPackMemberRepository(db=self._db)
        return self._library_pack_member_repository

    def library_pack_dependency_repository(self) -> ILibraryPackDependencyRepository:
        if self._library_pack_dependency_repository is None:
            self._library_pack_dependency_repository = SqliteLibraryPackDependencyRepository(db=self._db)
        return self._library_pack_dependency_repository
