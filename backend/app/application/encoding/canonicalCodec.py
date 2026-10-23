"""Canonical TLV v1 from GEO-1 §6.31-A; no module names or object hashes."""

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from math import isfinite
from struct import pack

from pydantic import BaseModel
from pydantic import TypeAdapter
from typing import get_type_hints
from struct import unpack

from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest, CanonicalTypeKind


class CanonicalEncodingError(ValueError):
    """Invalid schema, unsupported value or noncanonical encoded data."""


@dataclass(frozen=True)
class CanonicalCodec:
    """Explicit immutable record/enum manifest; concrete codecs own validation.

    This encoder serves fingerprints. Storage decode/validation remains with
    CachePayloadCodec and must reject noncanonical bytes for that schema.
    """

    manifest: CanonicalSchemaManifest

    def __post_init__(self) -> None:
        CanonicalSchemaManifest.model_validate(self.manifest)
        for entry in self.manifest.entries:
            kind = entry.python_type
            valid = issubclass(kind, Enum) if entry.kind == CanonicalTypeKind.ENUM else (
                issubclass(kind, BaseModel) or is_dataclass(kind))
            if not valid:
                raise CanonicalEncodingError("manifest kind does not match owner type")

    def encode(self, value: object) -> bytes:
        return self._encode(value, set())

    def _type_id(self, value: object) -> int:
        for binding in self.manifest.entries:
            if type(value) is binding.python_type:
                return binding.type_id
        raise ValueError("unregistered canonical record/enum type")

    @staticmethod
    def _tlv(tag: int, payload: bytes) -> bytes:
        return bytes((tag,)) + len(payload).to_bytes(8, "big") + payload

    def _encode(self, value: object, active: set[int]) -> bytes:
        if value is None:
            return self._tlv(0, b"")
        if isinstance(value, Enum):
            if value.name not in type(value).__members__ or type(value).__members__[value.name] is not value:
                raise ValueError("invalid enum member")
            return self._tlv(6, self._encode((self._type_id(value), value.value), active))
        if type(value) is bool:
            return self._tlv(1, bytes((int(value),)))
        if isinstance(value, int):
            magnitude = abs(value)
            return self._tlv(2, bytes((int(value < 0),)) + magnitude.to_bytes(
                max(1, (magnitude.bit_length() + 7) // 8), "big"))
        if isinstance(value, float):
            if not isfinite(value):
                raise ValueError("non-finite canonical float")
            return self._tlv(3, pack(">d", 0.0 if value == 0 else value))
        if isinstance(value, str):
            return self._tlv(4, value.encode("utf-8"))
        if isinstance(value, bytes):
            return self._tlv(5, value)
        identity = id(value)
        if identity in active:
            raise ValueError("cyclic canonical value")
        active.add(identity)
        try:
            if type(value) is tuple:
                return self._tlv(8, b"".join(self._encode(child, active) for child in value))
            if type(value) is frozenset:
                return self._tlv(9, b"".join(sorted(self._encode(child, active) for child in value)))
            if isinstance(value, BaseModel):
                names = tuple(type(value).model_fields)
                if not type(value).model_config.get("frozen") or set(vars(value)) != set(names) or value.model_extra:
                    raise ValueError("incomplete, extra or mutable canonical model")
                # Reuse POJO validation rather than duplicating field/map rules.
                type(value).model_validate({name: getattr(value, name) for name in names}, strict=True)
            elif is_dataclass(value) and not isinstance(value, type):
                names = tuple(field.name for field in fields(value))
                if not getattr(type(value), "__dataclass_params__").frozen:
                    raise ValueError("mutable canonical dataclass")
                if hasattr(value, "__dict__") and set(vars(value)) != set(names):
                    raise ValueError("incomplete or extra canonical dataclass fields")
                annotations = get_type_hints(type(value), include_extras=True)
                for name in names:
                    TypeAdapter(annotations[name]).validate_python(getattr(value, name), strict=True)
            else:
                raise ValueError("unsupported canonical value")
            record = (self._type_id(value), tuple((name, getattr(value, name)) for name in names))
            return self._tlv(7, self._encode(record, active))
        finally:
            active.remove(identity)


def encode(value: object, manifest: CanonicalSchemaManifest) -> bytes:
    try:
        return CanonicalCodec(manifest).encode(value)
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc


def digest(value: object, manifest: CanonicalSchemaManifest) -> bytes:
    from hashlib import sha256
    return sha256(encode(value, manifest)).digest()


def _tuple(value: object) -> tuple:
    if type(value) is not tuple:
        raise CanonicalEncodingError("expected canonical tuple")
    return value


def _decode_one(encoded: bytes, manifest: CanonicalSchemaManifest) -> tuple[object, int]:
    if len(encoded) < 9:
        raise CanonicalEncodingError("truncated canonical header")
    tag, length = encoded[0], int.from_bytes(encoded[1:9], "big")
    end = 9 + length
    if end > len(encoded):
        raise CanonicalEncodingError("truncated canonical value")
    body = encoded[9:end]
    if tag == 0:
        if body:
            raise CanonicalEncodingError("invalid null")
        return None, end
    if tag == 1:
        if body not in (b"\x00", b"\x01"):
            raise CanonicalEncodingError("invalid boolean")
        return body == b"\x01", end
    if tag == 2:
        if len(body) < 2 or body[0] not in (0, 1) or (len(body) > 2 and body[1] == 0):
            raise CanonicalEncodingError("nonminimal canonical integer")
        magnitude = int.from_bytes(body[1:], "big")
        if body[0] == 1 and magnitude == 0:
            raise CanonicalEncodingError("negative integer zero")
        return -magnitude if body[0] else magnitude, end
    if tag == 3:
        if len(body) != 8:
            raise CanonicalEncodingError("invalid float width")
        value = unpack(">d", body)[0]
        if not isfinite(value) or (value == 0 and body != pack(">d", 0.0)):
            raise CanonicalEncodingError("noncanonical float")
        return value, end
    if tag == 4:
        return body.decode("utf-8", errors="strict"), end
    if tag == 5:
        return body, end
    if tag in (8, 9):
        values: list[object] = []
        parts: list[bytes] = []
        offset = 0
        while offset < len(body):
            value, used = _decode_one(body[offset:], manifest)
            parts.append(body[offset:offset + used])
            values.append(value)
            offset += used
        if tag == 8:
            return tuple(values), end
        if parts != sorted(set(parts)):
            raise CanonicalEncodingError("unordered or duplicate canonical set elements")
        result = frozenset(values)
        if len(result) != len(values):
            raise CanonicalEncodingError("canonical set value collision")
        return result, end
    if tag in (6, 7):
        inner, used = _decode_one(body, manifest)
        pair = _tuple(inner)
        if used != len(body) or len(pair) != 2 or type(pair[0]) is not int:
            raise CanonicalEncodingError("invalid canonical type header")
        entry = next((entry for entry in manifest.entries if entry.type_id == pair[0]), None)
        expected_kind = CanonicalTypeKind.ENUM if tag == 6 else CanonicalTypeKind.RECORD
        if entry is None or entry.kind != expected_kind:
            raise CanonicalEncodingError("unknown or wrong canonical type id")
        owner = entry.python_type
        if tag == 6:
            return TypeAdapter(owner).validate_python(pair[1]), end
        pairs = _tuple(pair[1])
        if any(type(field) is not tuple or len(field) != 2 or type(field[0]) is not str for field in pairs):
            raise CanonicalEncodingError("invalid record fields")
        names = tuple(owner.model_fields) if issubclass(owner, BaseModel) else tuple(field.name for field in fields(owner))
        if tuple(field[0] for field in pairs) != names:
            raise CanonicalEncodingError("missing, duplicate, extra or reordered record fields")
        values_by_name = dict(pairs)
        if issubclass(owner, BaseModel):
            return owner.model_validate(values_by_name, strict=True), end
        annotations = get_type_hints(owner, include_extras=True)
        for name in names:
            TypeAdapter(annotations[name]).validate_python(values_by_name[name], strict=True)
        return owner(**values_by_name), end
    raise CanonicalEncodingError("unknown canonical tag")


def decode[T](encoded: bytes, expected: type[T], manifest: CanonicalSchemaManifest) -> T:
    try:
        CanonicalCodec(manifest)
        if type(encoded) is not bytes:
            raise CanonicalEncodingError("canonical input must be bytes")
        value, used = _decode_one(encoded, manifest)
        if used != len(encoded) or encode(value, manifest) != encoded:
            raise CanonicalEncodingError("trailing bytes or noncanonical value")
        return TypeAdapter(expected).validate_python(value, strict=True)
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise CanonicalEncodingError(str(exc)) from exc
