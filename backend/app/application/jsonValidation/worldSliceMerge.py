"""Import/CRUD merge of ``WORLD_SLICES`` into a world dict (RELIEF-T-29).

Runtime resolve stays in ``worldSlices``; this module is write-path only.
"""

from __future__ import annotations

from typing import Any

from app.application.jsonValidation.resolve import (
    ResolveContext,
    resolve_model,
    resolve_root_dict,
    resolve_root_list,
)
from app.application.jsonValidation.worldSlices import (
    WorldSlice,
    facade_world_slices,
)


def _slice_ctx(ctx: ResolveContext, world_slice: WorldSlice) -> ResolveContext:
    return ResolveContext(
        mode=ctx.mode,
        partial=ctx.partial,
        path_prefix=ctx.path_prefix,
        errors=ctx.errors,
        schema_id=world_slice.schema_id,
    )


def _merge_multi_column(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    assert world_slice.wire_from_mapping is not None
    column_keys = frozenset(world_slice.world_keys)
    if ctx.partial and not any(key in out for key in column_keys):
        return

    present_keys = {key for key in column_keys if key in out}
    wire = world_slice.wire_from_mapping(out)
    if ctx.partial:
        wire = {key: wire[key] for key in present_keys}
    resolved = resolve_model(
        world_slice.pojo_cls,
        wire,
        label=world_slice.schema_id,
        ctx=ctx,
    )
    dump = resolved.model_dump(mode="json")
    keys_to_write = column_keys if not ctx.partial else present_keys
    for key in keys_to_write:
        if key in dump:
            out[key] = dump[key]


def _merge_registry_list(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    key = world_slice.world_keys[0]
    if key not in out:
        return

    assert world_slice.empty_factory is not None
    raw = out.get(key)
    if world_slice.wire_adapter is not None:
        raw = world_slice.wire_adapter(raw)
        if raw is None:
            return

    resolved = resolve_root_list(
        world_slice.pojo_cls,
        raw,
        empty_factory=world_slice.empty_factory,
        label=key,
        ctx=ctx.child(key),
    )
    dump_kw: dict[str, Any] = {"mode": "json"}
    if world_slice.dump_by_alias:
        dump_kw["by_alias"] = True
    out[key] = [entry.model_dump(**dump_kw) for entry in resolved.root]


def _merge_registry_dict(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    key = world_slice.world_keys[0]
    if key not in out:
        return

    assert world_slice.empty_factory is not None
    raw = out.get(key)
    resolved = resolve_root_dict(
        world_slice.pojo_cls,
        raw,
        empty_factory=world_slice.empty_factory,
        label=key,
        ctx=ctx.child(key),
    )
    out[key] = resolved.model_dump(mode="json")


def _merge_json_blob(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    key = world_slice.world_keys[0]
    if key not in out:
        return

    raw = out.get(key)
    if not raw:
        return

    resolved = resolve_model(
        world_slice.pojo_cls,
        raw,
        label=key,
        ctx=ctx.child(key),
    )
    out[key] = resolved.model_dump(mode="json")


def merge_world_slice(
    out: dict[str, Any],
    world_slice: WorldSlice,
    ctx: ResolveContext,
) -> None:
    if not world_slice.facade:
        return

    slice_ctx = _slice_ctx(ctx, world_slice)
    if world_slice.wire_kind == "multi_column":
        _merge_multi_column(out, world_slice, slice_ctx)
    elif world_slice.wire_kind == "registry_list":
        _merge_registry_list(out, world_slice, slice_ctx)
    elif world_slice.wire_kind == "registry_dict":
        _merge_registry_dict(out, world_slice, slice_ctx)
    elif world_slice.wire_kind == "json_blob":
        _merge_json_blob(out, world_slice, slice_ctx)


def merge_facade_slices(out: dict[str, Any], ctx: ResolveContext) -> None:
    for world_slice in facade_world_slices():
        merge_world_slice(out, world_slice, ctx)
