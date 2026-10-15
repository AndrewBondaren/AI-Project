"""Relief domain adapter — name-keyed bodies + ``relief_pick_policy``
world-side ref field + ``terrain_registry`` sync (TZ §0.2/§2).

Membership is the single availability source (B6): no
``relief_template_registry`` pointer rows are written here.
"""

from __future__ import annotations

from copy import deepcopy

from app.application.jsonValidation.resolve import UnresolvedModelError, resolve_model
from app.application.worldData.libraryPacks.domainAdapters.bodyPreparation import (
    TemplateBodyPreparation,
    TemplatePreparationError,
)
from app.application.worldData.libraryPacks.domainAdapters.contract import (
    PackDomainAdapter,
)
from app.application.worldData.libraryPacks.domainAdapters.mixins import (
    _LibraryBodyMixin,
)
from app.application.worldData.libraryPacks.domainAdapters.remapRefs import (
    _remap_relief_pick_policy,
    remap_pins,
)
from app.application.worldData.libraryPacks.domainAdapters.refFields import relief_policy_refs
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.lifecycleContracts import FallbackDecision
from app.application.worldData.reliefErrors import ReliefValidationError
from app.application.worldData.reliefGeomWarn import warn_template_invalid_geom
from app.application.worldData.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.worldData.reliefWorldImportService import ReliefWorldImportService
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.db.models.world import World
from app.ids import LibraryKind


class ReliefBodyPreparation(TemplateBodyPreparation[ReliefTemplate]):
    """Name-keyed relief bodies for the membership-scoped read boundary (B5).

    World-side barrier/canal checks stay with ``ReliefPackAdapter`` (write
    path); the reader reports missing/invalid geometry through the shared
    issue channel instead of substituting a different template.
    """

    library_kind = LibraryKind.RELIEF_TEMPLATES
    model = ReliefTemplate

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


class ReliefPackAdapter(_LibraryBodyMixin, PackDomainAdapter):
    """Name-keyed relief bodies; availability is membership-only (B6)."""

    library_kind = LibraryKind.RELIEF_TEMPLATES

    def __init__(
        self,
        library: ReliefTemplateLibraryService,
        world_import: ReliefWorldImportService | None = None,
    ) -> None:
        self._library = library
        self._world_import = world_import

    def prepare_body(
        self,
        raw: dict,
        *,
        local_uid: str,
        template_uid: str,
        world: World | None = None,
    ) -> ReliefTemplate:
        if not isinstance(raw, dict):
            raise LibraryPackValidationError(
                f"relief body for '{local_uid}' must be a JSON object"
            )
        try:
            if world is not None and self._world_import is not None:
                outline = self._world_import.prepare_body(
                    world, raw, template_uid=template_uid)  # warns geom
            else:
                outline = resolve_model(ReliefTemplate, raw, label=local_uid)
                warn_template_invalid_geom(outline, template_uid=template_uid)
        except (ValueError, ReliefValidationError) as exc:
            raise LibraryPackValidationError(str(exc)) from exc
        if outline.system_name != local_uid:
            raise LibraryPackValidationError(
                f"relief body system_name '{outline.system_name}' != "
                f"member local_uid '{local_uid}'"
            )
        return outline


    def world_refs(self, world):
        return relief_policy_refs(world)

    def resolve_fallback(self, *, world_uid):
        """R21 unresolved policy: no template substitution — reject (TZ §5)."""
        return FallbackDecision.rejected()


    def remap_body(self, body, *, template_uid, uid_map, local_uid=None):
        from app.application.worldData.libraryPacks.domainAdapters.contract import _SYSTEM_NAME_FIELD
        result = dict(body)
        if local_uid is not None:
            result[_SYSTEM_NAME_FIELD] = local_uid
        return result

    def prepare_world_refs(self, world, uid_map, members, *, removed_uids=()):
        from app.application.worldData.reliefTerrainSync import missing_terrain_entries
        result = deepcopy(world)
        remap_pins(result, uid_map)
        policy = _remap_relief_pick_policy(result, uid_map)
        if policy is not None:
            result.relief_pick_policy = policy
        needed = (c.terrain.value for rm in members if isinstance(rm.outline, ReliefTemplate)
                  for c in rm.outline.conditions)
        entries = missing_terrain_entries(result, needed)
        if entries:
            result.terrain_registry = list(result.terrain_registry or []) + [e.model_dump(mode="json") for e in entries]
        return result
