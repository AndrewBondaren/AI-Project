"""World initialization smoke — import fixture, materialize terrain.

Default (pack): ``POST …/map/pack/bake`` — world_map light World Pack, no wilderness INSERT.
Legacy (freeze): ``POST …/map/materialize-stack`` — fine grid into map_cell_patches path.

Requires running backend (``npm run dev`` or ``npm run backend``).

Examples:
  python scripts/initialize_world.py --fixture ../fixtures/world_terrain_test.json
  python scripts/initialize_world.py --target legacy --fixture ../fixtures/world_test_all.json
  python scripts/smoke_world_pack.py --fixture ../fixtures/world_terrain_test.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from app.application.worldData.pack.importLevels import filter_bundle_for_export
from debug_api_helpers import BASE_URL, DebugApiError, _require_ok, api_clear_map, api_client
from debug_surface_helpers import (
    api_list_bootstrap_tiles,
    api_loading_progress,
    api_materialize_surface_stack,
    api_pack_bake,
)


def _import_fixture(client, path: str) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    bundle = filter_bundle_for_export(raw, "skeleton")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8",
    ) as tmp:
        json.dump(bundle, tmp, ensure_ascii=False)
        tmp_path = tmp.name
    try:
        r = client.post("/worlds/import", data={"path": tmp_path})
        _require_ok(r, f"POST /worlds/import {path}")
        data = r.json()
        if not isinstance(data, dict):
            raise DebugApiError(f"import: expected object, got {type(data)}")
        return data
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _fixture_world_uid(fixture: Path) -> str:
    data = json.loads(fixture.read_text(encoding="utf-8"))
    return data.get("world", data)["world_uid"]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Bootstrap world init for testing")
    parser.add_argument("--fixture", type=Path, default=REPO / "fixtures" / "world_terrain_test.json")
    parser.add_argument("--world-uid", default=None, help="defaults to fixture world_uid")
    parser.add_argument("--max-tiles", type=int, default=16, help="0 = no cap on bootstrap tiles")
    parser.add_argument(
        "--target",
        choices=("pack", "legacy"),
        default="pack",
        help="pack = World Pack light bake (default); legacy = materialize-stack INSERT path",
    )
    parser.add_argument(
        "--mode",
        choices=("bootstrap", "full", "light"),
        default=None,
        help="legacy: bootstrap|full; pack: light (default per target)",
    )
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--skip-clear", action="store_true")
    args = parser.parse_args()

    fixture = args.fixture.resolve()
    if not fixture.is_file():
        raise SystemExit(f"fixture not found: {fixture}")

    world_uid = args.world_uid or _fixture_world_uid(fixture)

    if args.target == "pack":
        mode = args.mode or "light"
        if mode != "light":
            raise SystemExit("pack target supports only --mode light (use --target legacy for bootstrap/full)")
    else:
        mode = args.mode or "bootstrap"
        if mode == "light":
            raise SystemExit("legacy target does not support --mode light (use --target pack)")

    with api_client() as client:
        if not args.skip_import:
            imp = _import_fixture(client, str(fixture))
            print("import:", {k: v for k, v in imp.items() if k not in ("rolled_back", "rollback_reason")})

        if not args.skip_clear:
            api_clear_map(client, world_uid)
            print(f"cleared map patches: {world_uid}")
            if args.target == "pack":
                print("note: pack dir on disk is not deleted — rebake overwrites tiles; wipe manually for clean slate")

        preview = api_list_bootstrap_tiles(client, world_uid, max_tiles=args.max_tiles)
        print(
            f"bootstrap tiles (preview): {preview.get('tile_count')} "
            f"max_tiles={preview.get('max_tiles')}"
        )
        for tile in preview.get("tiles") or []:
            print(f"  Gx{tile['gx']}_Gy{tile['gy']}")

        if args.target == "pack":
            bake = api_pack_bake(client, world_uid, mode="light", max_tiles=args.max_tiles)
            terrain = bake.get("terrain") or {}
            print("pack bake:", {
                "terrain_succeeded": terrain.get("succeeded"),
                "terrain_failed": terrain.get("failed"),
                "pack_mode": bake.get("pack_mode"),
            })
            progress = bake.get("loading_progress") or api_loading_progress(client, world_uid)
            print("loading:", progress)
        else:
            stack = api_materialize_surface_stack(
                client,
                world_uid,
                mode=mode,  # type: ignore[arg-type]
                max_tiles=args.max_tiles,
            )
            print("surface:", stack.surface)
            print("climate:", stack.climate)


if __name__ == "__main__":
    main()
