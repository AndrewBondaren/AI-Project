"""Two-pass canonical TLV reader for a caller-supplied schema and budget."""
from dataclasses import fields
from enum import Enum
from functools import lru_cache
from types import UnionType
from typing import Any, Annotated, Literal, NewType, TypeAliasType, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from app.encoding.canonicalCodec import CanonicalCodec, CanonicalEncodingError, _decode_scalar, encode, validate_decoded_identity
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind
from app.dataModel.planning.diagnostics.planDiagnostic import IssueT, PlanDiagnostic, admits_diagnostic_type
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.encoding.decodeLimits import DecodeLimits


def _alternatives(annotation, substitutions):
    # Collection elements are read later, outside this alias's binding scope.
    # Specialize the complete annotation while those bindings are available.
    if substitutions and get_origin(annotation) is not None:
        parameters = getattr(annotation, "__parameters__", ())
        if any(param in substitutions for param in parameters):
            annotation = annotation[tuple(substitutions.get(param, param) for param in parameters)]
    if annotation in substitutions:
        yield from _alternatives(substitutions[annotation], {})
    elif isinstance(annotation, TypeAliasType):
        yield from _alternatives(annotation.__value__, substitutions)
    elif isinstance(annotation, NewType):
        yield from _alternatives(annotation.__supertype__, substitutions)
    else:
        origin, args = get_origin(annotation), get_args(annotation)
        if origin is Annotated:
            yield from _alternatives(args[0], substitutions)
        elif origin in (Union, UnionType):
            for choice in args:
                yield from _alternatives(choice, substitutions)
        elif isinstance(origin, TypeAliasType):
            params = dict(zip(origin.__type_params__, args, strict=True))
            yield from _alternatives(origin.__value__, substitutions | params)
        else:
            yield annotation


@lru_cache(maxsize=256)
def _options(annotation):
    return tuple(_alternatives(annotation, {}))


_PLAN_CARRIER = PlanDiagnostic[Any]


def _matches(option, owner, value=None):
    # ID 105 is the unparameterized field carrier. Its IssueT uses the
    # declared field-issue default even when the enclosing envelope is generic.
    if option is IssueT:
        return _matches(IssueT.__default__, owner, value)
    if option is _PLAN_CARRIER:
        return admits_diagnostic_type(owner)
    if get_origin(option) is Literal:
        return any(type(member) is owner and member == value for member in get_args(option))
    target = get_origin(option) or option
    if isinstance(target, type) and issubclass(target, FieldPathError) and (
        target is FieldPathError or target.__pydantic_generic_metadata__["origin"] is FieldPathError
    ):
        return issubclass(owner, target) or (
            issubclass(owner, FieldPathError) and target.__pydantic_generic_metadata__["args"] == (Any,)
        )
    if target is owner:
        return True
    # Branded string keys have the same scalar wire representation as str.
    return owner is str and isinstance(target, type) and issubclass(target, str) and not issubclass(target, Enum)


class _Reader:
    def __init__(self, data, manifest, limits):
        self.data = memoryview(data)
        self.manifest = manifest
        self.bindings = {e.type_id: e for e in manifest.entries}
        self.limits = limits
        self.sizes = {(record.owner, rule.bound.field): (rule.minimum, rule.maximum)
                      for record in limits.field_sizes for rule in record.collections}
        self.layouts = {}

    def run(self, expected, *, build):
        self.pos = self.nodes = 0
        self.build = build
        value = self.value(len(self.data), 1, expected)
        self.require_end(len(self.data))
        return value

    def require_end(self, end):
        if self.pos != end:
            raise CanonicalEncodingError("trailing or missing canonical data")

    def header(self, bound, depth, expected_tag=None):
        self.nodes += 1
        if depth > self.limits.max_depth or self.nodes > self.limits.max_nodes:
            raise CanonicalEncodingError("canonical depth/node limit")
        start = self.pos
        self.pos += 9
        if self.pos > bound:
            raise CanonicalEncodingError("truncated canonical header")
        tag = self.data[start]
        end = self.pos + int.from_bytes(self.data[start + 1:self.pos], "big")
        if end > bound or (expected_tag is not None and tag != expected_tag):
            raise CanonicalEncodingError("invalid canonical length or tag")
        return tag, end

    def scalar(self, tag, end):
        start, self.pos = self.pos, end
        return _decode_scalar(tag, self.data[start:end])

    def value(self, bound, depth, annotation, size=None):
        tag, end = self.header(bound, depth)
        options = _options(annotation)
        if tag <= 5:
            value = self.scalar(tag, end)
            if any(_matches(option, type(value), value) for option in options):
                return value
        elif tag in (8, 9):
            owner = tuple if tag == 8 else frozenset
            for option in options:
                if get_origin(option) is owner:
                    return self.collection(end, depth, owner, get_args(option), size)
        elif tag in (6, 7):
            return self.typed(tag, end, depth, options)
        raise CanonicalEncodingError("wrong canonical field type or tag")

    def collection(self, end, depth, owner, args, size):
        low, high = size or (0, self.limits.max_items)
        fixed = owner is tuple and args[-1:] != (Ellipsis,)
        values = [] if self.build else None
        previous = None
        count = 0
        while self.pos < end:
            if count >= min(high, self.limits.max_items) or (fixed and count >= len(args)):
                raise CanonicalEncodingError("canonical collection limit")
            start = self.pos
            value = self.value(end, depth + 1, args[count] if fixed else args[0])
            if owner is frozenset:
                # Retain at most one preceding element for lexical comparison.
                current = bytes(self.data[start:self.pos])
                if previous is not None and previous >= current:
                    raise CanonicalEncodingError("unordered or duplicate canonical set")
                previous = current
            if values is not None:
                values.append(value)
            count += 1
        if count < low or (fixed and count != len(args)):
            raise CanonicalEncodingError("invalid canonical collection width")
        if values is not None:
            return owner(values)

    def typed(self, tag, end, depth, options):
        _, pair_end = self.header(end, depth + 1, 8)
        if pair_end != end or self.limits.max_items < 2:
            raise CanonicalEncodingError("invalid canonical type header")
        identity = self.value(end, depth + 2, int)
        entry = self.bindings.get(identity)
        kind = CanonicalTypeKind.ENUM if tag == 6 else CanonicalTypeKind.RECORD
        if entry is None or entry.kind is not kind:
            raise CanonicalEncodingError("unknown or wrong canonical type ID")
        owner = entry.python_type
        if tag == 6:
            members = [(m, getattr(m, "wire_value", m.value)) for m in owner]
            wire = self.value(end, depth + 2, Union[tuple(type(v) for _, v in members)])
            matches = [m for m, v in members if type(v) is type(wire) and wire == v]
            if len(matches) != 1 or not any(_matches(o, owner, matches[0]) for o in options):
                raise CanonicalEncodingError("unexpected canonical enum")
            self.require_end(end)
            return matches[0]
        if not any(_matches(option, owner) for option in options):
            raise CanonicalEncodingError("unexpected canonical record")
        return self.record(owner, end, depth)

    def record(self, owner, end, depth):
        _, fields_end = self.header(end, depth + 2, 8)
        if fields_end != end:
            raise CanonicalEncodingError("invalid canonical field tuple")
        if owner not in self.layouts:
            if issubclass(owner, BaseModel):
                layout = [(n, f.annotation) for n, f in owner.model_fields.items()]
            else:
                hints = get_type_hints(owner, include_extras=True)
                layout = [(f.name, hints[f.name]) for f in fields(owner)]
            self.layouts[owner] = layout
        layout = self.layouts[owner]
        if len(layout) > self.limits.max_items:
            raise CanonicalEncodingError("canonical record width limit")
        values = {} if self.build else None
        for name, annotation in layout:
            _, pair_end = self.header(end, depth + 3, 8)
            if self.value(pair_end, depth + 4, str) != name:
                raise CanonicalEncodingError("missing, extra or reordered record field")
            value = self.value(pair_end, depth + 4, annotation, self.sizes.get((owner, name)))
            self.require_end(pair_end)
            if values is not None:
                values[name] = value
        self.require_end(end)
        if values is not None:
            validate_decoded_identity(owner, values, self.manifest)
            return owner.model_validate(values, strict=True) if issubclass(owner, BaseModel) else owner(**values)


def _reader(encoded, manifest, limits):
    if type(encoded) is not bytes or len(encoded) > limits.max_bytes:
        raise CanonicalEncodingError("invalid canonical payload type or byte limit")
    CanonicalCodec(manifest)
    return _Reader(encoded, manifest, limits)


def validate_bounded(encoded, expected, manifest, *, limits):
    """Check encoded representation and budgets without constructing owner models."""
    try:
        _reader(encoded, manifest, limits).run(expected, build=False)
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc


def decode_bounded[T](encoded: bytes, expected: type[T], manifest: CanonicalSchemaManifest, *, limits: DecodeLimits) -> T:
    try:
        reader = _reader(encoded, manifest, limits)
        reader.run(expected, build=False)
        result = reader.run(expected, build=True)
        if type(result) is not expected or encode(result, manifest) != encoded:
            raise CanonicalEncodingError("noncanonical decoded representation")
        return result
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc
