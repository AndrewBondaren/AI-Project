"""Relief domain adapter — name-keyed bodies + ``relief_pick_policy``
world-side ref field + ``terrain_registry`` sync (TZ §0.2/§2).

Membership is the single availability source — the legacy
``relief_template_registry`` world column was removed in B7.
"""

from __future__ import annotations


from copy import deepcopy

from app.application.jsonValidation.resolve import UnresolvedModelError
from app.application.jsonValidation.types import FieldPathError
from app.application.templateLibrary.packs.domainAdapters.bodyPreparation import (
    TemplateBodyPreparation,
    TemplatePreparationError,
)
from app.application.templateLibrary.packs.domainAdapters.contract import (
    SYSTEM_NAME_FIELD,
)
from app.application.templateLibrary.packs.domainAdapters.remapRefs import (
    remap_relief_pick_policy,
    remap_pins,
)
from app.application.templateLibrary.packs.domainAdapters.refFields import relief_policy_refs
from app.application.templateLibrary.packs.domainAdapters.templateBodyAdapter import TemplateBodyAdapter
from app.application.templateLibrary.packs.lifecycleContracts import FallbackDecision
from app.application.templateLibrary.reliefErrors import ReliefValidationError
from app.application.templateLibrary.reliefGeomWarn import warn_template_invalid_geom
from app.application.templateLibrary.reliefTemplateLibraryService import (
    ReliefTemplateLibraryService,
)
from app.application.templateLibrary.reliefWorldRefValidation import (
    validate_relief_world_refs,
)
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.ids import LibraryKind


class ReliefBodyPreparation(TemplateBodyPreparation[ReliefTemplate]):
    """Name-keyed relief bodies — pure schema/body checks only (B5).

    World-side barrier/canal validation lives on the write seam
    (``ReliefPackAdapter`` → ``validate_relief_world_refs``); the read
    boundary never sees it (B7 review decision 2026-10-15, variant B).
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


class ReliefPackAdapter(TemplateBodyAdapter):
    """Name-keyed relief bodies; availability is membership-only (B6).

    Barrier/canal world-refs run only on this write/import seam — the
    read boundary stays free of world-refs validation.
    """

    library_kind = LibraryKind.RELIEF_TEMPLATES
    preparation = ReliefBodyPreparation()

    def __init__(
        self,
        library: ReliefTemplateLibraryService,
    ) -> None:
        self._library = library

    def prepare_body(self, raw, *, local_uid, template_uid, world=None):
        outline = super().prepare_body(raw, local_uid=local_uid,
            template_uid=template_uid, world=world)
        if world is None:
            return outline
        try:
            validate_relief_world_refs(world, outline)
        except ReliefValidationError as exc:
            raise TemplatePreparationError((FieldPathError(
                (self.library_kind.value, template_uid), str(exc),
                code="RELIEF_WORLD_REFS"),)) from exc
        return outline

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
            result[SYSTEM_NAME_FIELD] = local_uid
        return result

    def prepare_world_refs(self, world, uid_map, members):
        from app.application.templateLibrary.reliefTerrainSync import missing_terrain_entries
        result = deepcopy(world)
        pins = remap_pins(result, uid_map)
        if pins is not None:
            result.library_pins = pins
        policy = remap_relief_pick_policy(result, uid_map)
        if policy is not None:
            result.relief_pick_policy = policy
        needed = (c.terrain.value for rm in members if isinstance(rm.outline, ReliefTemplate)
                  for c in rm.outline.conditions)
        entries = missing_terrain_entries(result, needed)
        if entries:
            result.terrain_registry = list(result.terrain_registry or []) + [e.model_dump(mode="json") for e in entries]
        return result
