"""Measure the live type and alias closure of the Open Water source."""
import dataclasses
import hashlib
import typing
from enum import Enum

from pydantic import BaseModel, PlainValidator

from app.application.worldData.generators.hydrology.encoding import sourceBindings
from app.dataModel.hydrology.query.source import CanonicalOpenWaterSource
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.registryKey import RegistryKey
from app.encoding.canonicalCodec import CanonicalEncodingError


def shape_repr(annotation):
    description = repr(annotation)
    if isinstance(annotation, PlainValidator):
        function = annotation.func
        return description.replace(repr(function), function.__module__ + "." + function.__qualname__)
    for argument in typing.get_args(annotation):
        description = description.replace(repr(argument), shape_repr(argument))
    return description


def source_snapshot():
    seen, aliases, shapes = set(), {}, {}
    alias_owners = {}

    def walk(owner):
        if isinstance(owner, (typing.TypeAliasType, typing.NewType)):
            name = owner.__name__
            if name in alias_owners:
                if alias_owners[name] is not owner:
                    raise CanonicalEncodingError(f"open-water source v1 alias collision: {name}")
                return
            alias_owners[name] = owner
            target = owner.__value__ if isinstance(owner, typing.TypeAliasType) else owner.__supertype__
            aliases[name] = shape_repr(target)
            walk(target)
            return
        if isinstance(owner, Enum):
            walk(type(owner))
            return
        origin = typing.get_origin(owner)
        if origin is not None and dataclasses.is_dataclass(origin):
            walk(origin)
        if owner is PlanDiagnostic[typing.Any]:  # concrete roots are walked separately
            return
        if origin is RegistryKey:  # registry parameter is phantom, not payload
            return
        for argument in typing.get_args(owner):
            walk(argument)
        if not isinstance(owner, type) or owner in seen:
            return
        if not (issubclass(owner, (BaseModel, Enum)) or dataclasses.is_dataclass(owner)):
            return
        seen.add(owner)
        if issubclass(owner, Enum):
            if not owner.__members__:  # abstract StrEnum
                return
            shape = "; ".join(n + "=" + repr(getattr(v, "wire_value", v.value))
                              for n, v in owner.__members__.items())
        else:
            model = issubclass(owner, BaseModel)
            fields = owner.model_fields if model else {f.name: f for f in dataclasses.fields(owner)}
            hints = typing.get_type_hints(owner, include_extras=True)
            parts = []
            for name, field in fields.items():
                annotation = owner.model_fields[name].annotation if model else hints[name]
                walk(annotation)
                default = "MISSING" if field.default is dataclasses.MISSING else repr(field.default)
                factory = getattr(field, "default_factory", None)
                if factory is not None and factory is not dataclasses.MISSING:
                    default = "factory→" + repr(factory())
                metadata = "; metadata=" + repr(field.metadata) if hasattr(field, "metadata") else ""
                parts.append(name + ": " + shape_repr(annotation) + "; default=" + default + metadata)
            shape = "<br>".join(parts)
        qualified = owner.__module__ + "." + owner.__name__
        shapes[owner] = hashlib.sha256((qualified + "\n" + shape).encode()).hexdigest()

    walk(PlanEnvelope[CanonicalOpenWaterSource])
    for carrier, fact in sourceBindings.DIAGNOSTIC_FACTS.items():
        walk(carrier)
        walk(fact)
    return shapes, tuple(sorted(aliases.items()))
