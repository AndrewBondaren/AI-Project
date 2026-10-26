"""World-owned declaration diff; state mutation belongs to the consumer."""

from datetime import datetime, timezone
from typing import NoReturn

from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved
from app.application.jsonValidation.types import FieldPathError
from app.application.jsonValidation.worldSlices import slice_column_key
from app.application.jsonValidation.worldRow import terrain_masks, terrain
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.application.worldData.regions.factConsumers.context import FactConsumerContext
from app.application.worldData.regions.regionFacts import DeclarationFacts
from app.application.worldData.regions.stateChange.consumer import StateChangeConsumer
from app.application.worldData.regions.stateChange.contracts import RegionEvaluation
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.dataModel.cascade.cascadeGraph import bind_field
from app.dataModel.terrainMasks.worldTerrainMasks import DECLARED_REGIONS
from app.dataModel.terrainMasks.regions.specs import REGION_NAME
from app.dataModel.terrainMasks.regions import RegionSpecBase
from app.dataModel.terrainMasks.regions.edit import AddRegion, RemoveRegion, DeclaredRegionEdit
from app.db.database import Database
from app.db.models.world import World
from app.db.repositories.iRegionStateRepository import IRegionStateRepository


def apply_region_operation(masks: WorldTerrainMasks, operation: DeclaredRegionEdit,
                           ctx: ResolveContext) -> dict:
    def invalid(message: str) -> NoReturn:
        reject_unresolved(ctx, [FieldPathError(ctx.path_prefix + (bind_field(REGION_NAME).field,), message,
                                             code="REGION_EDIT_INVALID")])
    entries = list(masks.declared_regions)
    index = next((i for i, entry in enumerate(entries) if entry.name == operation.name), None)
    if isinstance(operation, AddRegion):
        if index is not None or operation.region.name != operation.name:
            invalid("add requires an unused name matching region.name")
        entries.append(operation.region)
    else:
        if index is None:
            invalid(f"declared region not found: {operation.name}")
        if isinstance(operation, RemoveRegion):
            entries.pop(index)
        else:
            if operation.region.name is None:
                invalid("update requires region.name")
            entries[index] = operation.region
    return {slice_column_key(WorldTerrainMasks): {
        bind_field(DECLARED_REGIONS).field: [entry.model_dump(mode="json") for entry in entries]}}


class DeclaredRegionEditor:
    def __init__(self, db: Database, repo: IRegionStateRepository) -> None:
        self._db, self._repo = db, repo

    def transaction(self):
        return self._db.transaction_if_needed()

    async def reconcile(self, before: World | None, after: World) -> None:
        masks = terrain_masks(after)
        consumer = StateChangeConsumer(self._repo, registry=terrain(after), policy=masks.default_landcover)

        def indexed(world: World | None) -> dict[str, RegionSpecBase]:
            return {declared_region_identity(after.world_uid, spec).region_uid: spec
                    for spec in terrain_masks(world).declared_regions} if world else {}
        old, new = indexed(before), indexed(after)
        now = datetime.now(timezone.utc).isoformat()

        def request_for(uid: str, spec: RegionSpecBase,
                        previous: RegionSpecBase | None = None) -> RegionEvaluation:
            identity = declared_region_identity(after.world_uid, spec)
            # Replace the author audit marker when event/time supplies a clock.
            return RegionEvaluation(region_uid=uid, spec=spec, entry_type=spec.entry_type,
                spec_fingerprint=identity.spec_fingerprint, context=FactConsumerContext(None, ()),
                elapsed_ticks=0, at=now, updated_at=now, declaration=DeclarationFacts(True, 0),
                previous_entry_type=previous.entry_type if previous else None)

        for uid in old.keys() - new.keys():
            await consumer.remove_declared(after.world_uid, request_for(uid, old[uid]))
        for uid, spec in new.items():
            previous = old.get(uid)
            if previous == spec:
                continue
            request = request_for(uid, spec, previous)
            if previous is None:
                await consumer.add_declared(after.world_uid, request)
            else:
                await consumer.evaluate(after.world_uid, request)
