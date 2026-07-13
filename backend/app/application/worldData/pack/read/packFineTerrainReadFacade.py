"""Debug fine-terrain pack read — WP-A4 smoke / manual curl."""

from __future__ import annotations

from typing import Any

from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.db.models.world import World


class PackFineTerrainReadFacade:
    """Inspect fine terrain blobs + manifest + merged gameplay read."""

    def __init__(self, context: PackReadContext, gameplay: MapCellQueryFacade) -> None:
        self._ctx = context
        self._gameplay = gameplay

    def read_tile(self, world: World, gx: int, gy: int) -> dict[str, Any]:
        if not self._ctx.has_pack_for(world):
            return {"ok": False, "error": "no_pack"}
        manifest = self._ctx.reader_for(world).manifest
        tile = manifest.tile_entry(gx, gy)
        if tile is None:
            return {
                "ok": True,
                "read_mode": "tile",
                "world_uid": world.world_uid,
                "gx": gx,
                "gy": gy,
                "listed_in_manifest": False,
            }
        return {
            "ok": True,
            "read_mode": "tile",
            "world_uid": world.world_uid,
            "gx": gx,
            "gy": gy,
            "listed_in_manifest": True,
            "world_map_path": tile.world_map_path,
            "world_map_hash": tile.world_map_hash,
            "wilderness_refine_status": tile.wilderness_refine_status,
            "climate_status": tile.climate_status,
            "chunks": [
                {
                    "cx": c.cx,
                    "cy": c.cy,
                    "refine_role": c.refine_role,
                    "content_hash": c.content_hash,
                    "bytes": c.bytes,
                    "blob_on_disk": self._ctx.reader_for(world).chunk_exists(gx, gy, c.cx, c.cy),
                }
                for c in tile.chunks
            ],
        }

    def read_wilderness_chunk(
        self,
        world: World,
        gx: int,
        gy: int,
        cx: int,
        cy: int,
        *,
        sample_columns: int = 3,
    ) -> dict[str, Any]:
        if not self._ctx.has_pack_for(world):
            return {"ok": False, "error": "no_pack"}
        reader = self._ctx.reader_for(world)
        manifest = reader.manifest
        ref = manifest.chunk_ref(gx, gy, cx, cy)
        blob_on_disk = reader.chunk_exists(gx, gy, cx, cy)
        payload: dict[str, Any] = {
            "ok": True,
            "read_mode": "wilderness_chunk",
            "world_uid": world.world_uid,
            "gx": gx,
            "gy": gy,
            "cx": cx,
            "cy": cy,
            "manifest_listed": ref is not None,
            "blob_on_disk": blob_on_disk,
        }
        if ref is not None:
            payload["manifest"] = {
                "refine_role": ref.refine_role,
                "content_hash": ref.content_hash,
                "bytes": ref.bytes,
            }
        if not blob_on_disk:
            payload["column_count"] = 0
            return payload
        chunk = reader.read_wilderness_chunk(gx, gy, cx, cy)
        payload["chunk_columns"] = chunk.chunk_columns
        payload["column_count"] = len(chunk.columns)
        limit = max(0, sample_columns)
        payload["sample_columns"] = [
            {
                "lx": col.lx,
                "ly": col.ly,
                "run_count": len(col.runs),
                "runs": [
                    {
                        "z0": run.z0,
                        "z1": run.z1,
                        "system_terrain": run.system_terrain,
                        "system_material": run.system_material,
                    }
                    for run in col.runs[:3]
                ],
            }
            for col in chunk.columns[:limit]
        ]
        return payload

    def read_location_terrain(
        self,
        world: World,
        location_uid: str,
        *,
        sample_columns: int = 3,
    ) -> dict[str, Any]:
        if not self._ctx.has_pack_for(world):
            return {"ok": False, "error": "no_pack"}
        reader = self._ctx.reader_for(world)
        entry = reader.manifest.location_entry(location_uid)
        if entry is None:
            return {
                "ok": True,
                "read_mode": "location_terrain",
                "world_uid": world.world_uid,
                "location_uid": location_uid,
                "listed_in_manifest": False,
            }
        blob_on_disk = bool(entry.terrain_path) and reader.paths.location_terrain_path(location_uid).is_file()
        payload: dict[str, Any] = {
            "ok": True,
            "read_mode": "location_terrain",
            "world_uid": world.world_uid,
            "location_uid": location_uid,
            "listed_in_manifest": True,
            "terrain_path": entry.terrain_path,
            "terrain_hash": entry.terrain_hash,
            "climate_status": entry.climate_status,
            "z_band": entry.z_band,
            "bytes": entry.bytes,
            "blob_on_disk": blob_on_disk,
            "territory_volume": entry.territory_volume.model_dump(mode="json"),
        }
        if not blob_on_disk:
            payload["column_count"] = 0
            return payload
        chunk = reader.read_location_terrain(location_uid)
        payload["chunk_columns"] = chunk.chunk_columns
        payload["column_count"] = len(chunk.columns)
        limit = max(0, sample_columns)
        payload["sample_columns"] = [
            {
                "lx": col.lx,
                "ly": col.ly,
                "run_count": len(col.runs),
                "runs": [
                    {
                        "z0": run.z0,
                        "z1": run.z1,
                        "system_terrain": run.system_terrain,
                        "system_material": run.system_material,
                    }
                    for run in col.runs[:3]
                ],
            }
            for col in chunk.columns[:limit]
        ]
        return payload

    async def read_merged_cell(self, world: World, x: int, y: int, z: int) -> dict[str, Any]:
        if not self._ctx.has_pack_for(world):
            return {"ok": False, "error": "no_pack"}
        merged = await self._gameplay.get_cell(world, x, y, z)
        return {
            "ok": True,
            "read_mode": "merged_cell",
            "world_uid": world.world_uid,
            "x": x,
            "y": y,
            "z": z,
            "has_data": merged.has_any_data(),
            "field_sources": {k: v.name for k, v in merged.field_sources.items()},
            "system_terrain": merged.system_terrain,
            "system_material": merged.system_material,
            "location_uid": merged.location_uid,
        }
