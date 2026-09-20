"""Serialize wire POJOs to pack blob payloads."""

from __future__ import annotations

import struct

import orjson

from app.application.worldData.pack.io.tileCodec import (
    BLOB_HEADER,
    BLOB_HEADER_SIZE,
    PAYLOAD_KIND_SETTLEMENT_STRUCTURE,
    TileCodec,
)
from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire
from app.dataModel.worldPack.settlementStructureWire import (
    DistrictStructureWire,
    SettlementStructureWire,
    ShellCellWire,
)
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire

SETTLEMENT_STRUCTURE_FRAMES_MAGIC = b"SSF1"
_RECORD_LEN = struct.Struct("!I")


def world_map_tile_payload(cells_per_side: int, cells: list[WorldMapCellWire]) -> dict:
    return {
        "cells_per_side": cells_per_side,
        "cells": [cell.model_dump(mode="json") for cell in cells],
    }


def parse_world_map_tile_payload(payload: dict) -> tuple[int, list[WorldMapCellWire]]:
    side = int(payload["cells_per_side"])
    cells = [WorldMapCellWire.model_validate(row) for row in payload.get("cells", [])]
    return side, cells


def fine_terrain_chunk_payload(chunk: FineTerrainChunkWire) -> dict:
    return chunk.model_dump(mode="json")


def parse_fine_terrain_chunk_payload(payload: dict) -> FineTerrainChunkWire:
    return FineTerrainChunkWire.model_validate(payload)


def climate_field_payload(field: ClimateFieldWire) -> dict:
    return field.model_dump(mode="json")


def parse_climate_field_payload(payload: dict) -> ClimateFieldWire:
    return ClimateFieldWire.model_validate(payload)


def settlement_structure_payload(wire: SettlementStructureWire) -> dict:
    return wire.model_dump(mode="json")


def parse_settlement_structure_payload(payload: dict) -> SettlementStructureWire:
    return SettlementStructureWire.model_validate(payload)


def _compress_record(payload: dict, codec: TileCodec) -> bytes:
    body = codec.compress(orjson.dumps(payload))
    return _RECORD_LEN.pack(len(body)) + body


def _header_payload(wire: SettlementStructureWire) -> dict:
    return {
        "settlement_uid": wire.settlement_uid,
        "barrier_cells": [cell.model_dump(mode="json") for cell in wire.barrier_cells],
    }


def is_settlement_structure_framed(data: bytes) -> bool:
    magic_end = BLOB_HEADER_SIZE + len(SETTLEMENT_STRUCTURE_FRAMES_MAGIC)
    if len(data) < magic_end:
        return False
    return data[BLOB_HEADER_SIZE:magic_end] == SETTLEMENT_STRUCTURE_FRAMES_MAGIC


def encode_settlement_structure_frames(
    wire: SettlementStructureWire,
    codec: TileCodec,
) -> bytes:
    records = [_compress_record(_header_payload(wire), codec)]
    for district in wire.districts:
        records.append(_compress_record(district.model_dump(mode="json"), codec))
    return (
        codec.pack_header(PAYLOAD_KIND_SETTLEMENT_STRUCTURE)
        + SETTLEMENT_STRUCTURE_FRAMES_MAGIC
        + b"".join(records)
    )


def append_settlement_structure_district(
    blob: bytes,
    district: DistrictStructureWire,
    codec: TileCodec,
) -> bytes:
    if not is_settlement_structure_framed(blob):
        raise ValueError("settlement structure blob is not framed; cannot append")
    return blob + _compress_record(district.model_dump(mode="json"), codec)


def write_settlement_structure_blob(
    wire: SettlementStructureWire,
    *,
    existing: bytes | None,
    codec: TileCodec,
) -> bytes:
    if not existing:
        return encode_settlement_structure_frames(wire, codec)
    if not is_settlement_structure_framed(existing):
        old = parse_settlement_structure_blob(existing, codec)
        merged = SettlementStructureWire(
            settlement_uid=wire.settlement_uid or old.settlement_uid,
            barrier_cells=list(old.barrier_cells or wire.barrier_cells),
            districts=[*old.districts, *wire.districts],
        )
        return encode_settlement_structure_frames(merged, codec)
    blob = existing
    for district in wire.districts:
        blob = append_settlement_structure_district(blob, district, codec)
    return blob


def parse_settlement_structure_blob(
    data: bytes,
    codec: TileCodec,
) -> SettlementStructureWire:
    if len(data) < BLOB_HEADER_SIZE:
        raise ValueError("blob too short for header")
    version, kind = BLOB_HEADER.unpack_from(data)
    if version != codec.codec_version:
        raise ValueError(f"unsupported codec version {version}")
    if kind != PAYLOAD_KIND_SETTLEMENT_STRUCTURE:
        raise ValueError("expected settlement_structure blob")
    rest = data[BLOB_HEADER_SIZE:]
    if rest.startswith(SETTLEMENT_STRUCTURE_FRAMES_MAGIC):
        return _parse_frames(
            rest[len(SETTLEMENT_STRUCTURE_FRAMES_MAGIC):], codec,
        )
    raw = codec.decompress(rest)
    payload = orjson.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return parse_settlement_structure_payload(payload)


def _parse_frames(body: bytes, codec: TileCodec) -> SettlementStructureWire:
    records: list[dict] = []
    offset = 0
    while offset < len(body):
        if offset + _RECORD_LEN.size > len(body):
            raise ValueError("truncated settlement structure record length")
        (nbytes,) = _RECORD_LEN.unpack_from(body, offset)
        offset += _RECORD_LEN.size
        end = offset + nbytes
        if end > len(body):
            raise ValueError("truncated settlement structure record")
        payload = orjson.loads(codec.decompress(body[offset:end]))
        if not isinstance(payload, dict):
            raise ValueError("settlement structure record must be a JSON object")
        records.append(payload)
        offset = end
    if not records:
        raise ValueError("settlement structure frames missing header")
    header = records[0]
    districts = [DistrictStructureWire.model_validate(row) for row in records[1:]]
    cells = [
        ShellCellWire.model_validate(row)
        for row in header.get("barrier_cells", [])
    ]
    return SettlementStructureWire(
        settlement_uid=str(header["settlement_uid"]),
        barrier_cells=cells,
        districts=districts,
    )
