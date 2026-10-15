"""Relief domain adapter — name-keyed bodies + ``relief_pick_policy``
world-side ref field + ``terrain_registry`` sync (TZ §0.2/§2).

Membership is the single availability source — the legacy
``relief_template_registry`` world column was removed in B7.
"""

from __future__ import annotations

from copy import deepcopy

from app.application.jsonValidation.resolve import (
    ResolveContext,
    UnresolvedModelError,
    report_issues,
)
from app.application.jsonValidation.types import FieldPathError
from app.application.worldData.libraryPacks.domainAdapters.bodyPreparation import (
    TemplateBodyPreparation,
    TemplatePreparationError,
)
from app.application.worldData.libraryPacks.domainAdapters.contract import (
    _SYSTEM_NAME_FIELD,
)
from app.application.worldData.libraryPacks.domainAdapters.remapRefs import (
    _remap_relief_pick_policy,
    remap_pins,
)
from app.application.worldData.libraryPacks.domainAdapters.refFields import relief_policy_refs
from app.application.worldData.libraryPacks.domainAdapters.templateBodyAdapter import TemplateBodyAdapter
from app.application.worldData.libraryPacks.lifecycleContracts import FallbackDecision
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefGeomWarn import warn_template_invalid_geom
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.worldData.reliefWorldImportService import ReliefWorldImportService
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.ids import LibraryKind


class ReliefBodyPreparation(TemplateBodyPreparation[ReliefTemplate]):
    """Name-keyed relief bodies for the membership-scoped read boundary (B5).

    World-side barrier/canal checks delegate to the injected
    ``ReliefWorldImportService`` (``PlotBodyPreparation`` pattern): an
    unwired service leaves one ``report_issues`` warning instead of
    silently skipping world checks (B6 review decision 2026-10-15).
    """

    library_kind = LibraryKind.RELIEF_TEMPLATES
    model = ReliefTemplate

    def __init__(self, world_import: ReliefWorldImportService | None = None) -> None:
        self._world_import = world_import

    def prepare_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        world=None,
    ) -> ReliefTemplate:
        body = super().prepare_body(
            raw, local_uid=local_uid, template_uid=template_uid, world=world,
        )
        try:
            warn_template_invalid_geom(body, template_uid=template_uid)
        except UnresolvedModelError as exc:
            raise TemplatePreparationError(tuple(exc.issues)) from exc
        return body

    def validate_world(self, body: ReliefTemplate, world, path: tuple) -> None:
        super().validate_world(body, world, path)
        if self._world_import is None:
            report_issues(ResolveContext(), [FieldPathError(
                path, "relief world checks skipped: world import service is not wired",
                code="WORLD_IMPORT_UNWIRED")])
            return
        try:
            self._world_import.validate_world_refs(world, body)
        except ReliefValidationError as exc:
            raise TemplatePreparationError((FieldPathError(
                path, str(exc), code="RELIEF_WORLD_REFS"),)) from exc


class ReliefPackAdapter(TemplateBodyAdapter):
    """Name-keyed relief bodies; availability is membership-only (B6)."""

    library_kind = LibraryKind.RELIEF_TEMPLATES

    def __init__(
        self,
        library: ReliefTemplateLibraryService,
        world_import: ReliefWorldImportService | None = None,
    ) -> None:
        self._library = library
        self.preparation = ReliefBodyPreparation(world_import)

    def world_refs(self, world):
        return relief_policy_refs(world)

    def resolve_fallback(self, *, world_uid):
        """R21 unresolved policy: no template substitution — reject (TZ §5)."""
        return FallbackDecision.rejected()


    def remap_body(self, body, *, template_uid, uid_map, local_uid=None):
        # Dict-copy keeps authored extension keys — the typed model drops
        # ``extra='ignore'`` fields on a validate/dump round-trip.
        result = dict(body)
        if local_uid is not None:
            result[_SYSTEM_NAME_FIELD] = local_uid
        return result

    def prepare_world_refs(self, world, uid_map, members):
        from app.application.worldData.reliefTerrainSync import missing_terrain_entries
        result = deepcopy(world)
        pins = remap_pins(result, uid_map)
        if pins is not None:
            result.library_pins = pins
        policy = _remap_relief_pick_policy(result, uid_map)
        if policy is not None:
            result.relief_pick_policy = policy
        needed = (c.terrain.value for rm in members if isinstance(rm.outline, ReliefTemplate)
                  for c in rm.outline.conditions)
        entries = missing_terrain_entries(result, needed)
        if entries:
            result.terrain_registry = list(result.terrain_registry or []) + [e.model_dump(mode="json") for e in entries]
        return result
