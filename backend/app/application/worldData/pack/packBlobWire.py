"""Serialize wire POJOs to pack blob payloads."""

from __future__ import annotations

from app.dataModel.worldPack.climateFieldWire import ClimateFieldWire
from app.dataModel.worldPack.l2ChunkWire import L2ChunkWire
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire


def l0_tile_payload(cells_per_side: int, cells: list[WorldMapCellWire]) -> dict:
    return {
        "cells_per_side": cells_per_side,
        "cells": [cell.model_dump(mode="json") for cell in cells],
    }


def parse_l0_tile_payload(payload: dict) -> tuple[int, list[WorldMapCellWire]]:
    side = int(payload["cells_per_side"])
    cells = [WorldMapCellWire.model_validate(row) for row in payload.get("cells", [])]
    return side, cells


def l2_chunk_payload(chunk: L2ChunkWire) -> dict:
    return chunk.model_dump(mode="json")


def parse_l2_chunk_payload(payload: dict) -> L2ChunkWire:
    return L2ChunkWire.model_validate(payload)


def climate_field_payload(field: ClimateFieldWire) -> dict:
    return field.model_dump(mode="json")


def parse_climate_field_payload(payload: dict) -> ClimateFieldWire:
    return ClimateFieldWire.model_validate(payload)
