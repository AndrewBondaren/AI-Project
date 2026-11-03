"""Frozen open-water V1 artifact identities, geometry and TLV budgets (§15.17)."""
from dataclasses import dataclass

from app.dataModel.artifacts.references import ArtifactFormatKey, ArtifactFormatRegistry, FormatVersion
from app.dataModel.encoding.decodeLimits import DecodeLimits, RecordLimits
from app.dataModel.registryKey import RegistryKey


FORMAT_VERSION: FormatVersion = 1
TILE_SIDE = 64
TILE_CELLS = TILE_SIDE ** 2
MAX_CONTAINER_ITEMS = 65_536
MAX_DEPTH = 64


@dataclass(frozen=True, kw_only=True)
class OpenWaterArtifactV1:
    key: ArtifactFormatKey
    max_bytes: int
    max_nodes: int

    def decode_limits(self, *fields: RecordLimits) -> DecodeLimits:
        return DecodeLimits(max_bytes=self.max_bytes, max_nodes=self.max_nodes,
                            max_depth=MAX_DEPTH, max_items=MAX_CONTAINER_ITEMS, field_sizes=fields)


ROOT_V1 = OpenWaterArtifactV1(key=RegistryKey[ArtifactFormatRegistry]("hydrology.open_water.root.tlv"),
                              max_bytes=16 * 1024**2, max_nodes=524_288)
SHARD_V1 = OpenWaterArtifactV1(key=RegistryKey[ArtifactFormatRegistry]("hydrology.open_water.shard.tlv"),
                               max_bytes=4 * 1024**2, max_nodes=262_144)
