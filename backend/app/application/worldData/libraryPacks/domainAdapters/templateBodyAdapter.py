"""Shared typed body seam; identity/policy/transactions stay in the common writer."""

from app.application.worldData.libraryPacks.domainAdapters.contract import (
    _SYSTEM_NAME_FIELD,
    PackDomainAdapter,
)
from app.application.worldData.libraryPacks.domainAdapters.mixins import _LibraryBodyMixin


class TemplateBodyAdapter(_LibraryBodyMixin, PackDomainAdapter):
    def prepare_body(self, raw, *, local_uid, template_uid, world=None):
        return self.preparation.prepare_body(raw, local_uid=local_uid,
            template_uid=template_uid, world=world)

    def body_refs(self, body, consumer):
        typed = self.preparation.model.model_validate(body)
        return self.preparation.body_refs(typed, consumer)

    def remap_body(self, body, *, template_uid, uid_map, local_uid=None):
        typed = self.preparation.model.model_validate(body)
        remapped = self.preparation.remap_body(typed, uid_map)
        name = template_uid if self.preparation.model_a else local_uid
        if name is not None:
            remapped = remapped.model_copy(update={_SYSTEM_NAME_FIELD: name})
        return remapped.model_dump(mode="json")

    def prepare_world_refs(self, world, uid_map, members):
        from copy import deepcopy
        from app.application.worldData.libraryPacks.domainAdapters.remapRefs import remap_pins
        result = deepcopy(world)
        remap_pins(result, uid_map)
        return result
