"""WorldBundleService — thin facade (BUNDLE-2 / tz_world_bundle.md)."""

from __future__ import annotations

from app.application.importResult import ImportResult
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


class WorldBundleService:

    def __init__(
        self,
        db: Database,
        world_service: WorldService,
        handlers: list[IBundleSectionHandler],
    ) -> None:
        self._db = db
        self._world = world_service
        self._handlers = handlers
        self._by_key = {h.key: h for h in handlers}

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
        return filter_bundle_for_export(bundle, level)

    async def import_bundle(
        self,
        data: dict,
        *,
        level: ImportLevel = "skeleton",
        validate_only: bool = False,
    ) -> tuple[dict[str, ImportResult], bool] | ImportValidationReport:
        ctx = ResolveContext.for_import(validate_only=validate_only)
        try:
            data = self._prepare_bundle(data, level=level, ctx=ctx)
        except ImportValidationError as exc:
            if validate_only:
                return ImportValidationReport(tuple(exc.errors))
            raise
        if validate_only:
            return ImportValidationReport()

        world_uid = data[BundleSection.WORLD]["world_uid"]
        existing = await self._world.find_by_id(world_uid)
        if existing is not None:
            version_n = await self._world.next_version_number(existing.name)
            data = remap_bundle(data, version_n, self._world.strip_version_suffix)
            world_uid = data[BundleSection.WORLD]["world_uid"]

        results: dict[str, ImportResult] = {}
        rolled_back = False
        try:
            async with self._db.transaction():
                for handler in self._handlers:
                    if handler.key not in data:
                        continue
                    results[handler.key] = await handler.import_section(
                        world_uid, data[handler.key],
                    )
                    if (
                        handler.key == BundleSection.WORLD
                        and results[handler.key].failed > 0
                    ):
                        raise _ImportFailed()
                if any(r.failed > 0 for r in results.values()):
                    raise _ImportFailed()
        except _ImportFailed:
            rolled_back = True

        return results, rolled_back

    def _prepare_bundle(self, data: dict, *, level: ImportLevel, ctx: ResolveContext) -> dict:
        """Shared pipeline. This phase has no repository/Pack/task access."""
        if not isinstance(data.get(BundleSection.WORLD), dict):
            raise ImportValidationError([FieldPathError((BundleSection.WORLD,), "expected world object", code="EXPECTED_OBJECT")])

        try:
            validate_bundle_for_import(data, level)
            world_data = normalize_world(dict(data[BundleSection.WORLD]), ctx=ctx)
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
        for handler in self._handlers:
            if handler.key not in data or handler.key == BundleSection.WORLD:
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
        return data
