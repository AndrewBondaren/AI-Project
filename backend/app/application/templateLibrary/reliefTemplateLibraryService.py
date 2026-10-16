"""Relief body reads/prepared persistence and common L-4 write delegation.

Standalone in-memory callers keep their test seam; SQL callers require
the common pack boundary. Domain errors contain no FastAPI types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.application.worldData.libraryPacks.writeResults import PolicyRequired

from app.application.jsonValidation.resolve import resolve_model, UnresolvedModelError
from app.application.canonicalLibrary import ensure_canonical
from app.application.worldData.libraryPacks.reliefCanonicalSpec import RELIEF_CANONICAL_SPEC

import logging
import os
from dataclasses import asdict
from pathlib import Path

from app.ids import LibraryKind, library_uid
from app.application.worldData.libraryPacks.packCatalog import (
    PackCatalogRepos,
    attach_pack_catalog,
)
from app.application.worldData.reliefErrors import ReliefNotFoundError, ReliefValidationError
from app.application.worldData.reliefGeomWarn import warn_template_invalid_geom
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.database import Database
from app.db.models.reliefTemplate import ReliefTemplateRow
from app.db.repositories.iReliefTemplateRepository import IReliefTemplateRepository

logger = logging.getLogger(__name__)

DOMAIN_ROOT = "relief_templates"
_ENV_ROOT = "RELIEF_TEMPLATES_ROOT"


def relief_template_uid(system_name: str) -> str:
    """Ownerless library uid — transitional helper for in-memory/test callers;
    pack-owned writes go through ``library_uid(…, pack_uid=…)``."""
    return library_uid(LibraryKind.RELIEF_TEMPLATES, system_name)


def resolve_relief_domain_root() -> Path:
    """SoT FS root for R29 (RELIEF-T-7). Override: env RELIEF_TEMPLATES_ROOT."""
    env = os.environ.get(_ENV_ROOT)
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[4] / DOMAIN_ROOT


class ReliefTemplateLibraryService:

    def __init__(
        self,
        repo: IReliefTemplateRepository,
        *,
        db: Database | None = None,
        catalog: PackCatalogRepos | None = None,
        write_provider=None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._catalog = catalog
        self._write_provider = write_provider

    async def find_by_uid(self, template_uid: str) -> ReliefTemplateRow | None:
        await ensure_canonical(RELIEF_CANONICAL_SPEC, self._db)
        return await self._repo.get_by_uid(template_uid)

    async def get_by_uid(self, template_uid: str) -> ReliefTemplateRow:
        row = await self.find_by_uid(template_uid)
        if row is None:
            raise ReliefNotFoundError(f"Relief template '{template_uid}' not found")
        return row

    async def list_all(self) -> list[ReliefTemplateRow]:
        await ensure_canonical(RELIEF_CANONICAL_SPEC, self._db)
        return await self._repo.list_all()

    async def persist_prepared(self, outline, *, template_uid, source_file, added):
        from app.application.worldData.libraryPacks.preparedPersistence import persist_body_row
        row = ReliefTemplateRow(template_uid=template_uid, system_name=outline.system_name,
            display_name=outline.display_name, context=outline.context.value, version=outline.version,
            data=outline.model_dump(mode="json"), source_file=source_file)
        return await persist_body_row(self._repo, row, added=added)

    async def upsert_outline(
        self,
        outline: ReliefTemplate,
        *,
        source_file: str | None = None,
        pack_uid: str | None = None,
        template_uid: str | None = None,
        world_uid: str | None = None,
    ) -> ReliefTemplateRow:
        if self._write_provider is not None:
            from app.application.worldData.libraryPacks.domainWriteEntry import write_domain_body
            return await write_domain_body(self._write_provider(), LibraryKind.RELIEF_TEMPLATES,
                outline, pack_uid=pack_uid, template_uid=template_uid, source_file=source_file, world_uid=world_uid)
        if self._db is not None:
            raise RuntimeError("SQL library writes require the common write service")
        uid = template_uid or library_uid(LibraryKind.RELIEF_TEMPLATES, outline.system_name, pack_uid=pack_uid)
        row = ReliefTemplateRow(
            template_uid=uid,
            system_name=outline.system_name,
            display_name=outline.display_name,
            context=outline.context.value,
            version=outline.version,
            data=outline.model_dump(mode="json"),
            source_file=source_file,
        )
        await self._repo.upsert(row)
        logger.info(
            "relief | library upsert system_name=%s uid=%s context=%s source=%s",
            outline.system_name,
            uid,
            outline.context.value,
            source_file,
        )
        return row

    async def upsert_from_dict(
        self,
        raw: dict,
        *,
        source_file: str | None = None,
        expected_stem: str | None = None,
        pack_uid: str | None = None,
        local_uid: str | None = None,
    ) -> ReliefTemplateRow:
        try:
            outline = resolve_model(ReliefTemplate, raw, label="ReliefTemplate")
        except UnresolvedModelError as exc:
            logger.warning("relief | library reject invalid outline source=%s err=%s", source_file, exc)
            raise ReliefValidationError(str(exc)) from exc
        if expected_stem is not None and outline.system_name != expected_stem:
            msg = (
                f"filename stem '{expected_stem}' != system_name '{outline.system_name}' (R29)"
            )
            logger.warning("relief | library reject %s", msg)
            raise ReliefValidationError(msg)
        if local_uid is not None and outline.system_name != local_uid:
            msg = (
                f"member local_uid '{local_uid}' != body system_name "
                f"'{outline.system_name}' (TZ §2 member identity)"
            )
            logger.warning("relief | library reject %s", msg)
            raise ReliefValidationError(msg)
        warn_template_invalid_geom(outline, source_file=source_file)
        return await self.upsert_outline(outline, source_file=source_file, pack_uid=pack_uid)

    async def import_path(
        self,
        path: str | Path,
        *,
        domain_root: Path | None = None,
        enforce_domain_root: bool = True,
        decisions=(), preview_token=None,
    ) -> list[ReliefTemplateRow] | PolicyRequired:
        if self._write_provider is not None:
            from app.application.worldData.libraryPacks.packResults import PackImportResult
            result = await self._write_provider().import_path(LibraryKind.RELIEF_TEMPLATES,
                path, domain_root=domain_root, enforce_domain_root=enforce_domain_root,
                decisions=decisions, preview_token=preview_token)
            return list(result.bodies) if isinstance(result, PackImportResult) else result
        if self._db is not None:
            raise RuntimeError("SQL library imports require the common write service")
        return await self._import(path, domain_root=domain_root,
                                  enforce_domain_root=enforce_domain_root)

    async def _import(
        self,
        path: str | Path,
        *,
        domain_root: Path | None,
        enforce_domain_root: bool,
    ) -> list[ReliefTemplateRow]:
        from app.application.worldData.reliefTemplateFsImport import import_relief_path

        outcome = await import_relief_path(
            path,
            upsert_from_dict=self.upsert_from_dict,
            domain_root=domain_root,
            enforce_domain_root=enforce_domain_root,
        )
        await attach_pack_catalog(outcome.manifest, self._catalog)
        return outcome.rows

    async def delete_prepared(self, template_uid: str) -> None:
        from app.db.database import _in_transaction
        if not _in_transaction.get():
            raise RuntimeError("prepared deletion requires caller UOW")
        await self._repo.delete(template_uid)

    async def delete(self, template_uid: str, *, world_uid=None) -> None:
        if self._write_provider is not None:
            await self._write_provider().delete_member(template_uid, world_uid=world_uid)
            return
        if self._db is not None:
            raise RuntimeError("SQL library writes require the common write service")
        row = await self.find_by_uid(template_uid)
        if row is None:
            raise ReliefNotFoundError(f"Relief template '{template_uid}' not found")
        await self._repo.delete(template_uid)
        logger.info("relief | library delete uid=%s system_name=%s", template_uid, row.system_name)

    @staticmethod
    def row_as_dict(row: ReliefTemplateRow) -> dict:
        return asdict(row)
