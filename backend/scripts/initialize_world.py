"""World initialization smoke — import fixture, bootstrap surface, climate.

Bootstrap mode materializes full fine grids only for priority macro tiles
(anchors + declared hydrology), not the entire location bbox.

Requires running backend (``npm run dev`` or ``npm run backend``).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from debug_api_helpers import BASE_URL, DebugApiError, _require_ok, api_clear_map, api_client
from debug_surface_helpers import api_list_bootstrap_tiles, api_materialize_surface_stack


def _import_fixture(client, path: str) -> dict:
    r = client.post("/worlds/import", data={"path": path})
    _require_ok(r, f"POST /worlds/import {path}")
    data = r.json()
    if not isinstance(data, dict):
        raise DebugApiError(f"import: expected object, got {type(data)}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap world init for testing")
    parser.add_argument("--fixture", type=Path, default=REPO / "fixtures" / "world_test_all.json")
    parser.add_argument("--world-uid", default=None, help="defaults to fixture world_uid")
    parser.add_argument("--max-tiles", type=int, default=16, help="0 = no cap on bootstrap tiles")
    parser.add_argument("--mode", choices=("bootstrap", "full"), default="bootstrap")
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--skip-clear", action="store_true")
    args = parser.parse_args()

    fixture = args.fixture.resolve()
    if not fixture.is_file():
        raise SystemExit(f"fixture not found: {fixture}")

    with api_client() as client:
        if not args.skip_import:
            imp = _import_fixture(client, str(fixture))
            print("import:", {k: v for k, v in imp.items() if k not in ("rolled_back", "rollback_reason")})

        world_uid = args.world_uid
        if not world_uid:
            import json
            world_uid = json.loads(fixture.read_text(encoding="utf-8"))["world"]["world_uid"]

        if not args.skip_clear:
            api_clear_map(client, world_uid)
            print(f"cleared map: {world_uid}")

        preview = api_list_bootstrap_tiles(client, world_uid, max_tiles=args.max_tiles)
        print(
            f"bootstrap tiles (preview): {preview.get('tile_count')} "
            f"max_tiles={preview.get('max_tiles')}"
        )
        for tile in preview.get("tiles") or []:
            print(f"  Gx{tile['gx']}_Gy{tile['gy']}")

        stack = api_materialize_surface_stack(
            client,
            world_uid,
            mode=args.mode,
            max_tiles=args.max_tiles,
        )
        print("surface:", stack.surface)
        print("climate:", stack.climate)


if __name__ == "__main__":
    main()
