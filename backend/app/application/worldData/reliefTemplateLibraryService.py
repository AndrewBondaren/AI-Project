"""Global relief template library — SQL upsert CRUD (R11).

FS/pack import — ``reliefTemplateFsImport`` (RELIEF-T-12; packs only,
manifest required). ``upsert_outline(pack_uid=None)`` keeps the ownerless
uid for the transitional direct-CRUD path; pack-scoped flows always pass
the owner ``pack_uid`` (step 4a will close the ownerless path).
Domain errors — RELIEF-T-3 (no FastAPI here).
"""

from __future__ import annotations

from app.application.jsonValidation.resolve import resolve_model, UnresolvedModelError

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
    return (Path.cwd() / DOMAIN_ROOT).resolve()


class ReliefTemplateLibraryService:

    def __init__(
        self,
        repo: IReliefTemplateRepository,
        *,
        db: Database | None = None,
        catalog: PackCatalogRepos | None = None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._catalog = catalog

    async def find_by_uid(self, template_uid: str) -> ReliefTemplateRow | None:
        return await self._repo.get_by_uid(template_uid)

    async def get_by_uid(self, template_uid: str) -> ReliefTemplateRow:
        row = await self.find_by_uid(template_uid)
        if row is None:
            raise ReliefNotFoundError(f"Relief template '{template_uid}' not found")
        return row

    async def list_all(self) -> list[ReliefTemplateRow]:
        return await self._repo.list_all()

    async def upsert_outline(
        self,
        outline: ReliefTemplate,
        *,
        source_file: str | None = None,
        pack_uid: str | None = None,
    ) -> ReliefTemplateRow:
        uid = library_uid(LibraryKind.RELIEF_TEMPLATES, outline.system_name, pack_uid=pack_uid)
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
    ) -> list[ReliefTemplateRow]:
        if self._db is not None:
            async with self._db.transaction_if_needed():
                return await self._import(path, domain_root=domain_root,
                                          enforce_domain_root=enforce_domain_root)
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

    async def delete(self, template_uid: str) -> None:
        row = await self.find_by_uid(template_uid)
        if row is None:
            raise ReliefNotFoundError(f"Relief template '{template_uid}' not found")
        await self._repo.delete(template_uid)
        logger.info("relief | library delete uid=%s system_name=%s", template_uid, row.system_name)

    @staticmethod
    def row_as_dict(row: ReliefTemplateRow) -> dict:
        return asdict(row)
