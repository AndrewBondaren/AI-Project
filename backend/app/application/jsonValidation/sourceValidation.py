"""Validate cascade source channels before domain materialization/extend.

Discovery uses POJO metadata; registries use the existing WorldSlice catalog.
No policy/default decisions live here: facts reach the shared reject sink.
"""
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.application.jsonValidation.resolve import ResolveContext, reject_unresolved, resolve_model
from app.application.jsonValidation.types import FieldPathError
from app.application.jsonValidation.index.worldRegistryIndex import WorldRegistryIndex
from app.application.jsonValidation.worldSlices import canonical_registry_wire, slice_for_pojo, resolve_registry_list_world
from app.dataModel.cascade.cascadeSpec import CascadeChannel, ChannelKind
from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.dataModel.registryKey import registry_key_target


def registry_vocabulary(world, registry_cls: type, ctx: ResolveContext, path: tuple) -> frozenset[str]:
    sl = slice_for_pojo(registry_cls)
    raw = getattr(world, sl.world_keys[0], None) if sl is not None else None
    if raw is None:
        reject_unresolved(ctx, [FieldPathError(path, "reference index unavailable", code="REF_W_UNAVAILABLE")])
    if sl.wire_adapter is not None:
        raw = sl.wire_adapter(raw)
    # Declared overlays fill missing fields only. Explicit malformed values
    # remain supplied and fail the same typed schema below.
    raw = canonical_registry_wire(sl, raw)
    try:
        registry = registry_cls.model_validate(raw)
    except ValidationError:
        reject_unresolved(ctx, [FieldPathError(path, "reference index unavailable: invalid registry",
                                               code="REF_W_UNAVAILABLE")])
    # Explicit canonical completion of declared catalogs (e.g. size ranks) is
    # their normal contract; malformed rows have already been rejected above.
    registry = resolve_registry_list_world(world, registry_cls)
    keys = set()
    for row in registry.root:
        for name, info in type(row).model_fields.items():
            if registry_key_target(info.annotation) is registry_cls:
                keys.add(str(getattr(row, name)))
    return frozenset(keys)


def validate_reference_value(world, annotation, value, ctx, path, cache=None):
    cache = WorldRegistryIndex() if cache is None else cache
    if value is None:
        return
    target = registry_key_target(annotation)
    if target is not None:
        if cache.keys_for_registry(target) is None:
            cache.registry_vocabularies[target] = registry_vocabulary(world, target, ctx, path)
        tokens = list(enumerate(value)) if isinstance(value, (list, tuple)) else [(None, value)]
        for index, token in tokens:
            if str(token) not in cache.keys_for_registry(target):
                reject_unresolved(ctx, [FieldPathError(path if index is None else path + (index,),
                    f"unknown reference: {token!r}", code="REF_W_UNKNOWN")])
    elif isinstance(value, BaseModel):
        for name, info in type(value).model_fields.items():
            validate_reference_value(world, info.annotation, getattr(value, name), ctx, path + (name,), cache)


def validate_source(world, source: BaseModel, *, ctx: ResolveContext):
    """Validate all source channels, even if another channel overrides them."""
    # Typed instances can have come from model_copy/model_construct. Preserve
    # authored presence and recheck model invariants before entering the graph.
    from app.dataModel.locations.namedLocation import BundleNamedLocation
    validation_context = None
    if isinstance(source, BundleNamedLocation):
        from app.application.jsonValidation import location_types
        validation_context = {"location_type_registry": location_types(world)}
    resolve_model(type(source), source.model_dump(mode="python", exclude_unset=True), ctx=ctx,
                  validation_context=validation_context)
    cache = WorldRegistryIndex()
    for name, info in type(source).model_fields.items():
        channels = [m for m in info.metadata if isinstance(m, CascadeChannel)]
        if not channels:
            continue
        value = getattr(source, name)
        path = ctx.path_prefix + (name,)
        try:
            value = TypeAdapter(info.rebuild_annotation()).validate_python(value)
        except ValidationError as exc:
            reject_unresolved(ctx, [FieldPathError(path + tuple(e["loc"]), e["msg"], code=e["type"])
                                   for e in exc.errors()])
        if value is None:
            continue
        validate_reference_value(world, info.annotation, value, ctx, path, cache)
        if any(c.kind is ChannelKind.BAND for c in channels):
            if EconomicTierBand.from_wire(value) is None:
                reject_unresolved(ctx, [FieldPathError(path, f"unknown economic tier band: {value!r}",
                                                       code="DOMAIN_BAND")])
        if any(c.kind is ChannelKind.RANGE for c in channels):
            from app.application.jsonValidation import economic_tiers
            ordered = economic_tiers(world).sorted_by_base_value()
            ranks = {str(row.system_tier): i for i, row in enumerate(ordered)}
            if ranks[str(value.min)] > ranks[str(value.max)]:
                reject_unresolved(ctx, [FieldPathError(path, "range min exceeds max", code="DOMAIN_RANGE")])
    return source
