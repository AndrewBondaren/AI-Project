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

from app.application.worldData.libraryPacks.packCatalog import attach_pack_catalog
from app.application.worldData.structureTemplateErrors import (
    StructureTemplateNotFoundError,
    StructureTemplateValidationError,
)
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.libraryPacks.packManifest import LibraryPackManifest
from app.db.database import Database, _in_transaction
from app.db.models.structureTemplate import StructureTemplateRow
from app.db.repositories.iLibraryPackDependencyRepository import (
    ILibraryPackDependencyRepository,
)
from app.db.repositories.iLibraryPackMemberRepository import ILibraryPackMemberRepository
from app.db.repositories.iLibraryPackRepository import ILibraryPackRepository
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
        packs: ILibraryPackRepository | None = None,
        members: ILibraryPackMemberRepository | None = None,
        deps: ILibraryPackDependencyRepository | None = None,
    ) -> None:
        self._repo = repo
        self._db = db
        self._packs = packs
        self._members = members
        self._deps = deps

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

    async def upsert_outline(
        self,
        outline: StructureTemplate,
        *,
        source_file: str | None = None,
    ) -> StructureTemplateRow:
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
        return await self.upsert_outline(outline, source_file=source_file)

    async def import_path(
        self,
        path: str | Path,
        *,
        domain_root: Path | None = None,
        enforce_domain_root: bool = True,
    ) -> list[StructureTemplateRow]:
        if self._db is not None and not _in_transaction.get():
            async with self._db.transaction():
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
        await self._attach_pack(outcome.manifest)
        return outcome.rows

    async def _attach_pack(self, manifest: LibraryPackManifest) -> None:
        """Bodies + membership land in the same unit of work (TZ §3)."""
        if self._packs is None or self._members is None or self._deps is None:
            raise RuntimeError(
                "StructureTemplateLibraryService: pack catalog repositories are not wired"
            )
        await attach_pack_catalog(
            manifest, packs=self._packs, members=self._members, deps=self._deps,
        )

    async def delete(self, template_uid: str) -> None:
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
