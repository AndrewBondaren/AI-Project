"""Reproducible B5 workload. Run from backend; setup is outside measured calls."""

import argparse
import cProfile
import gc
import json
import platform
import sys
import time
import tracemalloc
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
from types import FrameType, CodeType
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from test_preparation_wilderness_chunks import WildernessChunkTransitionTests
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


def fixture(n: int, many: bool, heavy: bool, replacement: bool) -> tuple[PackPreparationState, tuple[PackWildernessChunkWrite, ...]]:
    helper = WildernessChunkTransitionTests()
    helper.setUp()
    if heavy:
        uses = tuple(helper.usage(marker).uses[0].model_copy(update={"dependencies": SourceDependencySet(objects=tuple(
            SourceVersionRef(object_id=EntityObjectId.model_validate(dict(kind=SourceDescriptorCategory.ENTITY,
                world_uid="world", descriptor="benchmark.entity", entity_uid=f"entity-{j}")),
                revision=SourceRevision(seq=1, content_hash=marker * 64)) for j in range(4)), collections=())})
            for marker in ("a", "b", "c", "d"))
        usage = SourceProofInput(world_uid="world", uses=uses)
        helper.proof = PackStoredProvenance(source_proof=SourceDurableProof(schema_version=1, world_uid="world", uses=uses), planning=())
    else:
        usage = SourceProofInput(world_uid="world", uses=())
    entries = []
    for i in range(n):
        item = helper.item(i % 16 if many else i, gx=i // 16 if many else 0)
        entries.append(PackWildernessChunkWrite(part=item.part, refine_role=None, metadata_inputs=tuple(
            evidence.model_copy(update={"source_usage": usage}) for evidence in item.metadata_inputs)))
    items = tuple(entries)
    state = helper.apply(helper.state, *items) if replacement else helper.state
    if replacement:
        items = tuple(item.model_copy(update={"part": item.part.model_copy(update={
            "artifact": item.part.artifact.model_copy(update={"content_hash": "f" * 64})})}) for item in items)
    return state, items


def execute(state: PackPreparationState, entries: tuple[PackWildernessChunkWrite, ...]) -> PackPreparationState:
    request = PackWildernessChunksInput(state=state, entries=entries)
    return PackPreparationService().write_wilderness_chunks(request)


def measure(n: int, many: bool, heavy: bool, replacement: bool) -> dict[str, object]:
    state, entries = fixture(n, many, heavy, replacement)
    gc.collect()
    start = time.perf_counter()
    result = execute(state, entries)
    seconds = time.perf_counter() - start
    assert len(result.parts) == n
    volumes = dict(base_parts=len(state.parts), input_parts=n, result_parts=len(result.parts),
        base_tiles=len(state.assembly.tiles), result_tiles=len(result.assembly.tiles),
        base_descriptions=len(state.metadata_dependencies), result_descriptions=len(result.metadata_dependencies))
    del result
    gc.collect()
    counts: Counter[str] = Counter()

    def trace(frame: FrameType, event: str, arg: object):
        if event == "call":
            if frame.f_code is apply_wilderness_chunks.__code__:
                counts["transition_calls"] += 1
            if (frame.f_code is BaseModel.__init__.__code__ and frame.f_back is not None
                    and frame.f_back.f_code is apply_wilderness_chunks.__code__):
                counts[type(frame.f_locals["self"]).__name__] += 1
        return None

    profiler = cProfile.Profile()
    tracemalloc.start()
    sys.settrace(trace)
    profiler.enable()
    try:
        result = execute(state, entries)
    finally:
        profiler.disable()
        sys.settrace(None)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    selected = {"check_state_identities", "check_subject_values", "check_metadata_groups", "_tile_basis_inputs",
                "check_wilderness_chunk", "valid_preparation_field", "immutable_value", "persisted_shape", "capture_worlds"}
    calls: dict[str, int] = {}
    for entry in profiler.getstats():
        code = entry.code
        if isinstance(code, CodeType) and code.co_name in selected:
            calls[f"{Path(code.co_filename).name}:{code.co_name}"] = entry.callcount
        elif isinstance(code, str) and "builtins.sorted" in code:
            calls["sorted"] = entry.callcount
    return dict(n=n, layout="many" if many else "one", weight="heavy" if heavy else "light",
        operation="replace" if replacement else "add", seconds=round(seconds, 6), peak_mib=round(peak / 2**20, 3),
        volumes=volumes, materializations=dict(counts), calls=calls)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 4000, 16000])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with (args.output.open("w", encoding="utf-8") if args.output else nullcontext(sys.stdout)) as output:
        output.write(json.dumps(dict(python=sys.version, platform=platform.platform(),
            timing="unprofiled request construction + service; separate profiled tracemalloc run")) + "\n")
        for n in args.sizes:
            for heavy in (False, True):
                for many in (False, True):
                    for replacement in (False, True):
                        print(f"START {n=} {heavy=} {many=} {replacement=}", flush=True, file=sys.stderr)
                        row = measure(n, many, heavy, replacement)
                        encoded = json.dumps(row)
                        output.write(encoded + "\n")
                        output.flush()
                        if args.output:
                            print(encoded, flush=True)


if __name__ == "__main__":
    main()
