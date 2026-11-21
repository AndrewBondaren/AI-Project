"""Entity and transition identities, scoped by the captured publication."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.identity.uid import EntityUid


class LifecycleEntityRef[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    kind: T
    entity_uid: EntityUid


class LifecycleTransitionRef(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    world_uid: EntityUid
    origin_timeline_id: EntityUid
    change_uid: EntityUid
