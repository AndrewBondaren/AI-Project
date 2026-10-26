"""Application container: facade over domain wiring mixins.

Each wiring module owns one domain's lazy slots and factory methods
(see `.cursor/plans/worlddata-domain-restructure.md`, step 11).
"""

from app.core.templateRepositories import TemplateRepositoryProviders
from app.db.database import Database

from app.core.container.repositories import RepositoriesWiring
from app.core.container.llm import LlmWiring
from app.core.container.engine import EngineWiring
from app.core.container.templateLibrary import TemplateLibraryWiring
from app.core.container.packs import PacksWiring
from app.core.container.worldData import WorldDataWiring
from app.core.container.worldBundle import WorldBundleWiring
from app.core.container.session import SessionWiring


class Container(
    RepositoriesWiring,
    LlmWiring,
    EngineWiring,
    TemplateLibraryWiring,
    PacksWiring,
    WorldDataWiring,
    WorldBundleWiring,
    SessionWiring,
    TemplateRepositoryProviders,
):
    """Public DI surface — unchanged set of factory/singleton methods."""

    def __init__(self, config_manager, db: Database):
        super().__init__(db)
        self._config_manager = config_manager
