"""WorldBundleService — thin facade (BUNDLE-2 / tz_world_bundle.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.application.worldData.bundle.archive import BundleArchiveError, read_archive, write_archive
from app.dataModel.worldBundle.bundleManifest import BundleKind, BundleManifest, BundleWorldSource
from app.dataModel.worldBundle.bundleSections import SECTION_PATHS
from app.application.importResult import ImportResult
from app.application.worldData.libraryPacks.archiveSources import pack_to_wire, packs_from_wire
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.bundle.worldCopyImport import WorldCopyImport
from app.application.worldData.bundle.worldLibraries import export_libraries, import_libraries
from app.application.jsonValidation.bundle import normalize_bundle_connections
from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.types import FieldPathError, ImportValidationReport
from app.application.jsonValidation.resolve import ResolveContext, StrictFieldError, UnresolvedModelError, reject_unresolved
from app.application.worldData.reliefErrors import ReliefValidationError
from pydantic import ValidationError
from app.application.worldData.bundle.handler import IBundleSectionHandler
from app.application.worldData.bundleRemapService import remap_bundle
from app.application.worldData.deriveWorldUid import derive_world_uid
from app.application.worldData.libraryPacks.legacyWorldInput import extract_legacy_world_input
from app.application.worldData.pack.import_.importLevels import (
    ImportLevel,
    filter_bundle_for_export,
    validate_bundle_for_import,
)
from app.application.worldData.worldService import WorldService
from app.dataModel.worldBundle.bundleSections import BundleSection
from app.db.database import Database


class _ImportFailed(Exception):
    pass


def _cleanse_consumed_rows(world: dict) -> dict:
    """Legacy registry columns are pure migration input (B2/B7): after
    extraction nothing may reach ``World`` — the fields no longer exist."""
    cleansed = dict(world)
    cleansed.pop("building_template_registry", None)
    cleansed.pop("relief_template_registry", None)
    return cleansed


class WorldBundleService:

    def __init__(
        self,
        db: Database,
        world_service: WorldService,
        handlers: list[IBundleSectionHandler],
        library_archives=None,
        legacy_migration=None,
    ) -> None:
        self._db = db
        self._world = world_service
        self._handlers = handlers
        self._by_key = {h.key: h for h in handlers}
        self._archives = library_archives
        self._migration = legacy_migration
        self._copy_import = WorldCopyImport(db, world_service, handlers, library_archives, legacy_migration)

    async def export(self, world_uid: str, *, level: ImportLevel = "skeleton") -> dict:
        world = await self._world.get_by_id(world_uid)
        bundle: dict = {}
        allowed = BundleSection.for_level(level)
        for handler in self._handlers:
            if handler.key not in allowed:
                continue
            payload = await handler.export_section(world_uid, world=world)
            if payload is None:
                continue
            bundle[handler.key] = payload
        if self._archives is not None and level == "skeleton":
            bundle = await export_libraries(self._archives, bundle, world_uid)
        return filter_bundle_for_export(bundle, level)

    def write_archive(self, sections: dict, *, path: Path) -> Path:
        sections = dict(sections)
        packs = packs_from_wire(sections.pop(BundleSection.LIBRARY_PACKS, []))
        world = sections[BundleSection.WORLD]
        manifest = BundleManifest(
            kind=BundleKind.WORLD,
            format_version=1,
            source=BundleWorldSource(
                kind=BundleKind.WORLD,
                world_uid=world["world_uid"],
                world_name=world["name"],
                exporter="AI Project",
                exported_at=datetime.now(timezone.utc),
            ),
            sections={key: SECTION_PATHS[key] for key in sections},
        )
        return write_archive(sections, manifest, path=path, library_packs=packs)

    def read_archive(self, path: Path) -> dict:
        contents = read_archive(path)
        if contents.manifest.kind != BundleKind.WORLD:
            raise BundleArchiveError("World import requires a world archive")
        result = dict(contents.sections)
        if contents.library_packs:
            result[BundleSection.LIBRARY_PACKS] = [pack_to_wire(p) for p in contents.library_packs]
        return result

    async def import_bundle(
        self,
        data: dict,
        *,
        level: ImportLevel = "skeleton",
        validate_only: bool = False,
        decisions=(),
        preview_token: str | None = None,
    ) -> tuple[dict[str, ImportResult], bool] | ImportValidationReport:
        ctx = ResolveContext.for_import(validate_only=validate_only)
        try:
            data, legacy = self._prepare_bundle(data, level=level, ctx=ctx)
        except ImportValidationError as exc:
            if validate_only:
                return ImportValidationReport(tuple(exc.errors))
            raise
        if validate_only:
            return ImportValidationReport()

        return await self._copy_import.run(data, level=level, decisions=decisions,
                                         preview_token=preview_token, legacy=legacy)

    def _prepare_bundle(self, data: dict, *, level: ImportLevel, ctx: ResolveContext):
        """Shared pipeline. This phase has no repository/Pack/task access."""
        if not isinstance(data.get(BundleSection.WORLD), dict):
            raise ImportValidationError([FieldPathError((BundleSection.WORLD,), "expected world object", code="EXPECTED_OBJECT")])
        raw_world = data[BundleSection.WORLD]
        if self._migration is not None:
            raw_for_normalize = _cleanse_consumed_rows(raw_world)
        else:
            raw_for_normalize = raw_world

        try:
            validate_bundle_for_import(data, level)
            world_data = normalize_world(dict(raw_for_normalize), ctx=ctx)
            if not world_data.get("world_uid"):
                world_data["world_uid"] = derive_world_uid(world_data)
            data = {**data, BundleSection.WORLD: world_data}
            data = normalize_bundle_connections(data, ctx=ctx)
        except ImportValidationError:
            raise
        except UnresolvedModelError as exc:
            raise ImportValidationError(exc.issues) from exc
        except StrictFieldError as exc:
            raise ImportValidationError([FieldPathError(exc.path, exc.detail, code="STRICT_REQUIRED")]) from exc
        except ValueError as exc:
            raise ImportValidationError([FieldPathError((), str(exc), code="BUNDLE_INVALID")]) from exc

        if BundleSection.MAP_CELLS in data:
            raise ImportValidationError([FieldPathError((BundleSection.MAP_CELLS,), "use World Pack import", code="BUNDLE_INVALID")])
        try:
            world = self._world.prepare_import(data[BundleSection.WORLD])
        except ValidationError as exc:
            raise ImportValidationError([FieldPathError((BundleSection.WORLD,) + tuple(e["loc"]), e["msg"], code=e["type"]) for e in exc.errors()]) from exc
        except ValueError as exc:
            raise ImportValidationError([FieldPathError((BundleSection.WORLD,), str(exc), code="VALIDATION_ERROR")]) from exc
        legacy = None
        if self._migration is not None:
            # Raw extraction before the consumed sections/registry rows are normalized away.
            legacy = extract_legacy_world_input(
                {**raw_world, "world_uid": world_data["world_uid"]}, data)
        consumed = set()
        if self._archives is not None:
            migrate = self._migration is not None and self._migration.has_content(legacy)
            # Convert raw compatibility bodies before the legacy section handlers can normalize them.
            try:
                packs, consumed = import_libraries(data, legacy_migration=migrate)
                self._archives.validate_bodies(packs, world)
                if migrate:
                    if legacy.issues:
                        ctx.errors.extend(legacy.issues)
                    else:
                        ctx.errors.extend(self._migration.plan_wire(legacy, packs))
            except ImportValidationError as exc:
                ctx.errors.extend(exc.errors)
                consumed = {BundleSection.PLOT_TEMPLATES, BundleSection.BUILDING_TEMPLATES}
            except (ValueError, LibraryPackValidationError) as exc:
                ctx.errors.append(FieldPathError((BundleSection.LIBRARY_PACKS,), str(exc), code="LIBRARY_INVALID"))
                consumed = {BundleSection.PLOT_TEMPLATES, BundleSection.BUILDING_TEMPLATES}
        for handler in self._handlers:
            if handler.key not in data or handler.key == BundleSection.WORLD or handler.key in consumed:
                continue
            section_ctx = ctx.child(handler.key)
            try:
                handler.validate_section(world, data[handler.key], ctx=section_ctx)
            except UnresolvedModelError:
                continue
            except (ValueError, ReliefValidationError) as exc:
                try:
                    reject_unresolved(section_ctx, [FieldPathError(section_ctx.path_prefix, str(exc), code="VALIDATION_ERROR")])
                except UnresolvedModelError:
                    continue
        if ctx.errors:
            raise ImportValidationError(list(ctx.errors))
        return data, legacy
