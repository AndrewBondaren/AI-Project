"""Each declaration must fail Pyright and runtime contract admission."""
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.encoding.decodeLimits import CollectionLimit
from app.dataModel.hydrology.pack.shard import HydrologyPackShard
from app.dataModel.hydrology.query.source import WaterMembershipRun

CollectionLimit(tuple[int, ...], ref=FieldRef(lambda: HydrologyPackShard, lambda shard: shard.tx), maximum=1)
CollectionLimit(frozenset[WaterMembershipRun], ref=FieldRef(lambda: HydrologyPackShard, lambda shard: shard.wet_runs), maximum=1)
CollectionLimit(tuple[int, ...], ref=FieldRef(lambda: HydrologyPackShard, lambda shard: shard.wet_runs), maximum=1)
