"""Smoke: entry refine + background chunk schedule (WP-13).

Separate from detailed_bake / light|full L0. Verifies:
1. ``POST …/map/refine-from-entry`` (blocking scene)
2. optional ``schedule_bg`` enqueue (rings / path-ahead)
3. optional standalone ``POST …/map/schedule-chunk-refine``
4. poll ``loading-progress`` while in-process queue may drain

Assumes world already has L0 parent light. Does **not** wipe pack.

Reports → ``.local/map-render/{uid}/entry-bg/``

Requires a running backend (``npm run backend``) — agents must not start it.

Examples:
  python backend/scripts/entry_bg_refine.py --world-uid world-test-002
  python backend/scripts/entry_bg_refine.py --world-uid world-test-002 \\
      --anchor-x 2 --anchor-y 2 --poll-seconds 30
  python backend/scripts/entry_bg_refine.py --world-uid world-test-002 \\
      --schedule-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, TextIO

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from debug_api_helpers import (
    api_client,
    api_list_locations,
    api_refine_from_entry,
    api_schedule_chunk_refine,
)
from debug_surface_helpers import api_loading_progress
from render_maps import _print_summary, dump_map_renders

_DEFAULT_TIMEOUT_S = float(os.environ.get("DEBUG_API_TIMEOUT", "600"))


class _TeeStream:
    def __init__(self, primary: TextIO, log_file: TextIO) -> None:
        self._primary = primary
        self._log = log_file

    def write(self, data: str) -> int:
        self._primary.write(data)
        self._log.write(data)
        return len(data)

    def flush(self) -> None:
        self._primary.flush()
        self._log.flush()

    def reconfigure(self, **kwargs: Any) -> None:  # noqa: ANN401
        reconf = getattr(self._primary, "reconfigure", None)
        if callable(reconf):
            reconf(**kwargs)


@contextmanager
def _tee_stdio(log_path: Path) -> Iterator[Path]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8", newline="\n")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = _TeeStream(old_out, log_file)  # type: ignore[assignment]
    sys.stderr = _TeeStream(old_err, log_file)  # type: ignore[assignment]
    try:
        yield log_path
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
        log_file.flush()
        log_file.close()
        print(f"\nfull transcript saved: {log_path}", file=old_out, flush=True)


def _report_dir(world_uid: str) -> Path:
    return REPO / ".local" / "map-render" / world_uid / "entry-bg"


def _pack_dir(world_uid: str) -> Path:
    return REPO / "db" / "worlds" / world_uid / "pack"


def _resolve_anchor(
    client,
    world_uid: str,
    *,
    anchor_x: int | None,
    anchor_y: int | None,
    location_uid: str | None,
) -> tuple[int, int, str | None]:
    if anchor_x is not None and anchor_y is not None:
        return int(anchor_x), int(anchor_y), location_uid

    locs = api_list_locations(client, world_uid)
    if location_uid:
        for loc in locs:
            if loc.get("location_uid") == location_uid:
                mx, my = loc.get("map_x"), loc.get("map_y")
                if mx is None or my is None:
                    raise SystemExit(f"location {location_uid} has no map_x/map_y")
                return int(mx), int(my), location_uid
        raise SystemExit(f"location_uid not found: {location_uid}")

    for loc in locs:
        mx, my = loc.get("map_x"), loc.get("map_y")
        if mx is not None and my is not None:
            return int(mx), int(my), loc.get("location_uid")
    raise SystemExit(
        "need --anchor-x/--anchor-y or a location with map_x/map_y",
    )


def _progress_snapshot(progress: dict) -> dict[str, Any]:
    wm = progress.get("worldMapLoading") or progress.get("world_map") or {}
    if not isinstance(wm, dict):
        wm = {}
    completeness = progress.get("pack_completeness") or {}
    return {
        "tiles_pct": wm.get("tiles_pct"),
        "locations_pct": wm.get("locations_pct"),
        "wilderness_pct": wm.get("wilderness_pct"),
        "l0_baked": completeness.get("l0_baked"),
        "locations_detailed": completeness.get("locations_detailed"),
        "locations_expected": completeness.get("locations_expected"),
        "has_climate_coarse": progress.get("has_climate_coarse"),
    }


def _poll_progress(
    client,
    world_uid: str,
    *,
    poll_seconds: float,
    poll_interval: float,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    if poll_seconds <= 0:
        snap = _progress_snapshot(api_loading_progress(client, world_uid))
        snap["t_s"] = 0.0
        samples.append(snap)
        return samples

    deadline = time.perf_counter() + poll_seconds
    t0 = time.perf_counter()
    while True:
        now = time.perf_counter()
        snap = _progress_snapshot(api_loading_progress(client, world_uid))
        snap["t_s"] = round(now - t0, 2)
        samples.append(snap)
        print(
            f"  poll t={snap['t_s']:.1f}s  "
            f"locations_pct={snap.get('locations_pct')}  "
            f"wilderness_pct={snap.get('wilderness_pct')}  "
            f"locations_detailed={snap.get('locations_detailed')}"
        )
        if now >= deadline:
            break
        time.sleep(min(poll_interval, max(0.0, deadline - now)))
    return samples


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    os.environ.setdefault("DEBUG_API_TIMEOUT", str(int(_DEFAULT_TIMEOUT_S)))

    parser = argparse.ArgumentParser(
        description="Smoke entry refine + background schedule_chunk_refine",
    )
    parser.add_argument("--world-uid", required=True)
    parser.add_argument("--anchor-x", type=int, default=None)
    parser.add_argument("--anchor-y", type=int, default=None)
    parser.add_argument("--location-uid", default=None, help="Prefer this loc for anchor")
    parser.add_argument(
        "--schedule-bg",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pass schedule_bg on refine-from-entry (default: on)",
    )
    parser.add_argument(
        "--schedule-only",
        action="store_true",
        help="Skip refine-from-entry; only POST schedule-chunk-refine",
    )
    parser.add_argument(
        "--extra-schedule",
        action="store_true",
        help="After entry, also call schedule-chunk-refine once more",
    )
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument(
        "--render",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--mark-locations",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()

    world_uid = args.world_uid
    report_root = _report_dir(world_uid)
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    transcript = report_root / "entry-bg-latest.log"
    stamped_log = report_root / f"entry-bg-{stamp}.log"

    print(f"report dir: {report_root}")
    print(f"transcript: {transcript}")

    with _tee_stdio(transcript), api_client() as client:
        if not (_pack_dir(world_uid) / "manifest.json").is_file():
            raise SystemExit(
                f"no pack manifest for {world_uid} — run light/full bake first"
            )

        ax, ay, loc_uid = _resolve_anchor(
            client,
            world_uid,
            anchor_x=args.anchor_x,
            anchor_y=args.anchor_y,
            location_uid=args.location_uid,
        )
        print(f"anchor=({ax},{ay}) location_uid={loc_uid}")

        before = _progress_snapshot(api_loading_progress(client, world_uid))
        print(f"progress before: {before}")

        entry_resp: dict[str, Any] | None = None
        schedule_resp: dict[str, Any] | None = None

        if args.schedule_only:
            print("\n=== schedule-chunk-refine only ===")
            t0 = time.perf_counter()
            schedule_resp = api_schedule_chunk_refine(client, world_uid, x=ax, y=ay)
            print(
                f"schedule: {time.perf_counter() - t0:.2f}s  "
                f"enqueued={schedule_resp.get('enqueued')}  "
                f"queue={schedule_resp.get('refine_queue_depth')}"
            )
        else:
            print("\n=== refine-from-entry ===")
            t0 = time.perf_counter()
            entry_resp = api_refine_from_entry(
                client,
                world_uid,
                x=ax,
                y=ay,
                location_uid=loc_uid,
                schedule_bg=args.schedule_bg,
            )
            print(
                f"entry: {time.perf_counter() - t0:.2f}s  "
                f"chunks_done={entry_resp.get('chunks_done')}  "
                f"queue={entry_resp.get('refine_queue_depth')}  "
                f"scheduled_enqueued={entry_resp.get('scheduled_enqueued')}  "
                f"schedule_bg={entry_resp.get('schedule_bg')}"
            )
            if args.extra_schedule:
                print("\n=== extra schedule-chunk-refine ===")
                t1 = time.perf_counter()
                schedule_resp = api_schedule_chunk_refine(
                    client, world_uid, x=ax, y=ay,
                )
                print(
                    f"schedule: {time.perf_counter() - t1:.2f}s  "
                    f"enqueued={schedule_resp.get('enqueued')}  "
                    f"queue={schedule_resp.get('refine_queue_depth')}"
                )

        print(f"\n=== poll loading-progress ({args.poll_seconds}s) ===")
        samples = _poll_progress(
            client,
            world_uid,
            poll_seconds=args.poll_seconds,
            poll_interval=args.poll_interval,
        )
        after = samples[-1] if samples else before

        report: dict[str, Any] = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "world_uid": world_uid,
            "anchor": {"x": ax, "y": ay, "location_uid": loc_uid},
            "schedule_bg": args.schedule_bg,
            "schedule_only": args.schedule_only,
            "entry": entry_resp,
            "schedule": schedule_resp,
            "progress_before": before,
            "progress_samples": samples,
            "progress_after": after,
        }
        json_latest = report_root / "entry-bg-latest.json"
        json_stamped = report_root / f"entry-bg-{stamp}.json"
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        json_latest.write_text(payload, encoding="utf-8")
        json_stamped.write_text(payload, encoding="utf-8")
        print(f"\nJSON report: {json_latest}")

        if args.render:
            print("\n=== map render after entry/bg ===")
            summary = dump_map_renders(
                client,
                world_uid,
                out_root=report_root / "after-entry",
                mark_locations=args.mark_locations,
            )
            _print_summary(summary)
            report["render"] = summary
            payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            json_latest.write_text(payload, encoding="utf-8")
            json_stamped.write_text(payload, encoding="utf-8")

        stamped_log.write_text(transcript.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"stamped transcript: {stamped_log}")


if __name__ == "__main__":
    main()
