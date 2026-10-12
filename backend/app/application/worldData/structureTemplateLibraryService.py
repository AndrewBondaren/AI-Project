"""Global structure template library — SQL upsert CRUD (5o split, model A).

``template_uid`` == ``StructureTemplate.system_name`` — the pack-owned
``library_uid(STRUCTURE_TEMPLATES, local_uid, pack_uid=…)`` carried inside the
JSON body (TZ §2 wire contract). One global set; worlds point into it.
FS/pack import — ``structureTemplateFsImport`` (packs only, manifest required).
Domain errors — ``structureTemplateErrors`` (no FastAPI here).
"""

from __future__ import annotations

from app.application.jsonValidation.resolve import resolve_model, UnresolvedModelError

import logging
import os
from dataclasses import asdict
from pathlib import Path

from app.application.worldData.libraryPacks.packCatalog import (
    PackCatalogRepos,
    attach_pack_catalog,
)
from app.application.worldData.structureTemplateErrors import (
    StructureTemplateNotFoundError,
    StructureTemplateValidationError,
)
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.db.database import Database
from app.ids import LibraryKind, library_uid
from app.db.models.structureTemplate import StructureTemplateRow
from app.db.repositories.iStructureTemplateRepository import IStructureTemplateRepository

logger = logging.getLogger(__name__)

DOMAIN_ROOT = "structures_templates"
_ENV_ROOT = "STRUCTURES_TEMPLATES_ROOT"


def resolve_structures_domain_root() -> Path:
    """SoT FS root for structure templates. Override: env STRUCTURES_TEMPLATES_ROOT."""
    env = os.environ.get(_ENV_ROOT)
    if env:
        return Path(env).expanduser().resolve()
    return (Path.cwd() / DOMAIN_ROOT).resolve()


class StructureTemplateLibraryService:

    def __init__(
        self,
        repo: IStructureTemplateRepository,
        *,
        db: Database | None = None,
        catalog: PackCatalogRepos | None = None,
        write_provider=None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._catalog = catalog
        self._write_provider = write_provider

    async def find_by_uid(self, template_uid: str) -> StructureTemplateRow | None:
        return await self._repo.get_by_uid(template_uid)

    async def get_by_uid(self, template_uid: str) -> StructureTemplateRow:
        row = await self.find_by_uid(template_uid)
        if row is None:
            raise StructureTemplateNotFoundError(
                f"Structure template '{template_uid}' not found"
            )
        return row

    async def list_all(self) -> list[StructureTemplateRow]:
        return await self._repo.list_all()

    async def persist_prepared(self, outline, *, template_uid, source_file, added):
        from app.application.worldData.libraryPacks.preparedPersistence import persist_body_row
        row = StructureTemplateRow(template_uid=template_uid, display_name=outline.display_name,
            version=outline.version, data=outline.model_dump(mode="json"), source_file=source_file)
        return await persist_body_row(self._repo, row, added=added)

    async def upsert_outline(
        self,
        outline: StructureTemplate,
        *,
        source_file: str | None = None,
        pack_uid: str | None = None, local_uid: str | None = None, world_uid: str | None = None,
    ) -> StructureTemplateRow:
        if self._write_provider is not None:
            from app.application.worldData.libraryPacks.domainWriteEntry import write_domain_body
            return await write_domain_body(self._write_provider(), LibraryKind.STRUCTURE_TEMPLATES,
                outline, pack_uid=pack_uid, local_uid=local_uid, source_file=source_file, world_uid=world_uid)
        if self._db is not None:
            raise RuntimeError("SQL library writes require the common write service")
        uid = str(outline.system_name)
        existing = await self._repo.get_by_uid(uid)
        data = outline.model_dump(mode="json")
        if existing is not None and existing.data != data:
            logger.warning(
                "structure | library replace body uid=%s display_name=%s source=%s",
                uid,
                outline.display_name,
                source_file,
            )
        row = StructureTemplateRow(
            template_uid=uid,
            display_name=outline.display_name,
            version=outline.version,
            data=data,
            source_file=source_file,
        )
        await self._repo.upsert(row)
        logger.info(
            "structure | library upsert uid=%s display_name=%s source=%s",
            uid,
            outline.display_name,
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
    ) -> StructureTemplateRow:
        try:
            outline = resolve_model(StructureTemplate, raw, label="StructureTemplate")
        except UnresolvedModelError as exc:
            logger.warning(
                "structure | library reject invalid outline source=%s err=%s",
                source_file,
                exc,
            )
            raise StructureTemplateValidationError(str(exc)) from exc
        if expected_stem is not None and str(outline.system_name) != expected_stem:
            msg = (
                f"filename stem '{expected_stem}' != system_name"
                f" '{outline.system_name}'"
            )
            logger.warning("structure | library reject %s", msg)
            raise StructureTemplateValidationError(msg)
        if local_uid is not None and pack_uid is not None:
            expected_uid = library_uid(
                LibraryKind.STRUCTURE_TEMPLATES, local_uid, pack_uid=pack_uid
            )
            if str(outline.system_name) != expected_uid:
                msg = (
                    f"member identity library_uid(structure_templates, "
                    f"'{local_uid}', pack_uid=…) '{expected_uid}' != body "
                    f"system_name '{outline.system_name}' (model A, TZ §2)"
                )
                logger.warning("structure | library reject %s", msg)
                raise StructureTemplateValidationError(msg)
        return await self.upsert_outline(outline, source_file=source_file, pack_uid=pack_uid, local_uid=local_uid)

    async def import_path(
        self,
        path: str | Path,
        *,
        domain_root: Path | None = None,
        enforce_domain_root: bool = True,
        decisions=(), preview_token=None,
    ) -> list[StructureTemplateRow]:
        if self._write_provider is not None:
            from app.application.worldData.libraryPacks.packResults import PackImportResult
            result = await self._write_provider()._fs_writes.import_path(LibraryKind.STRUCTURE_TEMPLATES,
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
    ) -> list[StructureTemplateRow]:
        from app.application.worldData.structureTemplateFsImport import (
            import_structure_templates_path,
        )

        outcome = await import_structure_templates_path(
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
            raise StructureTemplateNotFoundError(
                f"Structure template '{template_uid}' not found"
            )
        await self._repo.delete(template_uid)
        logger.info(
            "structure | library delete uid=%s display_name=%s",
            template_uid,
            row.display_name,
        )

    @staticmethod
    def row_as_dict(row: StructureTemplateRow) -> dict:
        return asdict(row)
