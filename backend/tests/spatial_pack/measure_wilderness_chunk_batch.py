"""L2 single-tile fixture harness; not a real-world or L0 acceptance test."""

import argparse
import cProfile
import ctypes
import gc
import json
import platform
import sys
import time
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from types import CodeType
from unittest.mock import patch
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.spatial_pack.test_preparation_wilderness_chunks import WildernessChunkTransitionTests
from app.application.worldData.pack.preparation.packPreparationService import PackPreparationService
from app.application.worldData.pack.preparation.wildernessChunkWrite import apply_wilderness_chunks
from app.dataModel.worldPack.preparation.operations import PackWildernessChunksInput, PackWildernessChunkWrite
from app.dataModel.worldPack.preparation.state import PackPreparationState
from app.dataModel.worldPack.preparation.provenance import PackStoredProvenance
from app.dataModel.sourceVersioning.sourceProofInput import SourceProofInput
from app.dataModel.sourceVersioning.sourceDurableProof import SourceDurableProof
from app.dataModel.sourceVersioning.sourceDependencies import SourceDependencySet
from app.dataModel.sourceVersioning.sourceVersionRef import SourceVersionRef
from app.dataModel.sourceVersioning.sourceObjectId import EntityObjectId
from app.dataModel.sourceVersioning.sourceDescriptor import SourceDescriptorCategory
from app.dataModel.sourceVersioning.sourceObjectRevision import SourceRevision
from app.application.worldData.generators.coordinates.worldTile import fine_bbox_for_tile, iter_fine_chunks
from app.application.worldData.pack.preparation.metadataProjection import metadata_input_fingerprint
from app.dataModel.worldPack.preparation.metadataDependencies import PackMetadataInputField, PackMetadataValueInputSelector


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong),
                ("peak", ctypes.c_size_t), ("working", ctypes.c_size_t),
                ("paged_peak", ctypes.c_size_t), ("paged", ctypes.c_size_t),
                ("nonpaged_peak", ctypes.c_size_t), ("nonpaged", ctypes.c_size_t),
                ("pagefile", ctypes.c_size_t), ("pagefile_peak", ctypes.c_size_t)]


def memory() -> tuple[int, int]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong)
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(counters.working), int(counters.peak)


def fixture(base_tiles: int, chunk_count: int | None, heavy: bool, replacement: bool) -> tuple[PackPreparationState, tuple[PackWildernessChunkWrite, ...]]:
    helper = WildernessChunkTransitionTests()
    helper.setUp()
    if base_tiles < 0 or (replacement and base_tiles == 0):
        raise ValueError("replacement requires at least one existing tile; base_tiles must be nonnegative")
    if heavy:
        uses = tuple(helper.usage(marker).uses[0].model_copy(update={"dependencies": SourceDependencySet(objects=tuple(
            SourceVersionRef(object_id=EntityObjectId.model_validate(dict(kind=SourceDescriptorCategory.ENTITY,
                world_uid="world", descriptor="benchmark.entity", entity_uid=f"entity-{j}")),
                revision=SourceRevision(seq=1, content_hash=marker * 64)) for j in range(1)), collections=())})
            for marker in ("a", "b"))
        usage = SourceProofInput(world_uid="world", uses=uses)
        helper.proof = PackStoredProvenance(source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=uses), planning=())
    else:
        usage = SourceProofInput(world_uid="world", uses=())
    assembly = helper.state.assembly
    bbox = fine_bbox_for_tile(0, 0, assembly.fine_cells_per_map_cell)
    side = assembly.terrain_chunk_columns
    coordinates = tuple(((rect.x_min - bbox.x_min) // side, (rect.y_min - bbox.y_min) // side)
                        for rect in iter_fine_chunks(bbox, side))
    count = len(coordinates) if chunk_count is None else chunk_count
    if not 1 <= count <= len(coordinates):
        raise ValueError("L2 request must fit the actual chunk grid of one tile")

    def tile_items(gx: int, limit: int) -> tuple[PackWildernessChunkWrite, ...]:
        entries = []
        for cx, cy in coordinates[:limit]:
            item = helper.item(cx, gx=gx)
            address = item.part.address.model_copy(update={"cy": cy})
            evidence = []
            for supplied in item.metadata_inputs:
                assert isinstance(supplied.input, PackMetadataValueInputSelector)
                value = address if supplied.input.field is PackMetadataInputField.ADDRESS else item.refine_role
                evidence.append(supplied.model_copy(update={"source_usage": usage,
                    "value_fingerprint": metadata_input_fingerprint(supplied.input, value)}))
            entries.append(PackWildernessChunkWrite(part=item.part.model_copy(update={"address": address}),
                refine_role=item.refine_role, metadata_inputs=tuple(evidence)))
        return tuple(entries)

    state = helper.state
    for gx in range(base_tiles):
        state = helper.apply(state, *tile_items(gx, len(coordinates)))
    items = tile_items(0 if replacement else base_tiles, count)
    if replacement:
        items = tuple(item.model_copy(update={"part": item.part.model_copy(update={
            "artifact": item.part.artifact.model_copy(update={"content_hash": "f" * 64})})}) for item in items)
    return state, items


def execute(state: PackPreparationState, entries: tuple[PackWildernessChunkWrite, ...]) -> PackPreparationState:
    request = PackWildernessChunksInput(state=state, entries=entries)
    return PackPreparationService().write_wilderness_chunks(request)


def measure(base_tiles: int, chunk_count: int | None, heavy: bool, replacement: bool) -> dict[str, object]:
    state, entries = fixture(base_tiles, chunk_count, heavy, replacement)
    n = len(entries)
    gc.collect()
    baseline, setup_peak = memory()
    start = time.perf_counter()
    result = execute(state, entries)
    seconds = time.perf_counter() - start
    retained, peak = memory()
    assert len(result.parts) == len(state.parts) + (0 if replacement else n)
    volumes = dict(base_parts=len(state.parts), input_parts=n, result_parts=len(result.parts),
        base_tiles=len(state.assembly.tiles), result_tiles=len(result.assembly.tiles),
        base_descriptions=len(state.metadata_dependencies), result_descriptions=len(result.metadata_dependencies))
    del result
    gc.collect()
    counts: Counter[str] = Counter()

    original_init = BaseModel.__init__

    def counted_init(value: BaseModel, **data: object) -> None:
        if sys._getframe(1).f_code is apply_wilderness_chunks.__code__:
            counts[type(value).__name__] += 1
        original_init(value, **data)

    profiler = cProfile.Profile()
    with patch.object(BaseModel, "__init__", counted_init):
        profiler.enable()
        try:
            result = execute(state, entries)
        finally:
            profiler.disable()
    selected = {"check_state_identities", "check_subject_values", "check_metadata_groups", "_tile_basis_inputs",
                "check_wilderness_chunk", "valid_preparation_field", "immutable_value", "persisted_shape", "capture_worlds"}
    calls: dict[str, int] = {}
    for entry in profiler.getstats():
        code = entry.code
        if code is apply_wilderness_chunks.__code__:
            counts["transition_calls"] = entry.callcount
        if isinstance(code, CodeType) and code.co_name in selected:
            calls[f"{Path(code.co_filename).name}:{code.co_name}"] = entry.callcount
        elif isinstance(code, str) and "builtins.sorted" in code:
            calls["sorted"] = entry.callcount
    return dict(input_chunks=n, base_tiles=base_tiles, level="L2", input_tiles=1, fixture_only=True,
        weight="heavy" if heavy else "light",
        operation="replace" if replacement else "add", seconds=round(seconds, 6), peak_mib=round(peak / 2**20, 3),
        baseline_mib=round(baseline / 2**20, 3), setup_peak_mib=round(setup_peak / 2**20, 3), retained_mib=round(retained / 2**20, 3),
        volumes=volumes, materializations=dict(counts), calls=calls)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-tiles", type=int, default=0)
    parser.add_argument("--chunks", type=int, default=None, help="omit for full tile coverage")
    parser.add_argument("--heavy", action="store_true")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--run-fixture", action="store_true", help="explicit opt-in; not real-world acceptance")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.run_fixture:
        parser.error("real-world tests are deferred; use --run-fixture only to inspect the L2 harness")
    with (args.output.open("w", encoding="utf-8") if args.output else nullcontext(sys.stdout)) as output:
        output.write(json.dumps(dict(python=sys.version, platform=platform.platform(),
            timing="unprofiled request construction + service; separate counter run",
            memory="fresh child process OS peak working set through timed call, INCLUDING setup/imports; baseline and setup peak reported separately")) + "\n")
        output.write(json.dumps(measure(args.base_tiles, args.chunks, args.heavy, args.replace)) + "\n")


if __name__ == "__main__":
    main()
