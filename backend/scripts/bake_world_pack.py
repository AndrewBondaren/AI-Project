#!/usr/bin/env python3
"""Offline World Pack bake CLI — master/CI only.

Usage:
  python scripts/bake_world_pack.py --world-uid <uid> --mode light
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.application.worldData.materializationContext import resolve_materialization_context
from app.core.configManager import ConfigManager
from app.core.container import Container
from app.db.database import Database


async def _run(world_uid: str, mode: str, max_tiles: int) -> int:
    config = ConfigManager()
    db = Database(config)
    await db.connect()
    container = Container(config, db)

    world = await container.world_service().get_by_id(world_uid)
    locations = await container.location_service().get_all(world_uid)
    nodes = await container.connection_graph_service().get_nodes(world_uid)
    edges = await container.connection_graph_service().get_edges(world_uid)
    mat_ctx = resolve_materialization_context(world)
    writer = container.world_pack_writer(world_uid)
    stack = container.surface_materialization_orchestrator()

    if mode != "light":
        print(f"mode '{mode}' not implemented", file=sys.stderr)
        return 2

    report = await stack.materialize_pack_light(
        world_uid, world, locations, mat_ctx, writer,
        max_tiles=max_tiles,
        nodes=nodes, edges=edges,
    )
    print(report.to_dict())
    return 0 if report.terrain.failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Bake World Pack")
    parser.add_argument("--world-uid", required=True)
    parser.add_argument("--mode", default="light", choices=["light", "tile", "full"])
    parser.add_argument("--max-tiles", type=int, default=16)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.world_uid, args.mode, args.max_tiles)))


if __name__ == "__main__":
    main()
