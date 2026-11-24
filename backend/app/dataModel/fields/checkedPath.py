"""Construction-time typed path from a root POJO to the validated value.

Plan: ``.cursor/plans/error-contracts-1.md`` §3.9 C0-4. ``CurrentT`` is
invariant so a path to ``str`` never accepts an ``int`` value; container
steps are one overload per container kind used in POJO annotations.
The path is not serialized: ``freeze`` yields ``ValidatedFieldPath``.
"""

from collections.abc import Mapping, Sequence
from types import NoneType, UnionType
from typing import Annotated, Any, Generic, Literal, TypeVar, Union, cast, get_args, get_origin, overload

from pydantic import AliasChoices, BaseModel, Discriminator, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from app.dataModel.annotationPolicy import unwrap_wire_type
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.fields.validatedFieldPath import (
    FieldSegment,
    IndexSegment,
    KeySegment,
    ModelIdentity,
    PathSegment,
    ValidatedFieldPath,
    VariantSegment,
)

RootT = TypeVar("RootT", bound=BaseModel)
CurrentT = TypeVar("CurrentT")
RootModelT = TypeVar("RootModelT", bound=BaseModel)
ModelT = TypeVar("ModelT", bound=BaseModel)
ValueT = TypeVar("ValueT")
ItemT = TypeVar("ItemT")
KeyT = TypeVar("KeyT")
BranchT = TypeVar("BranchT", bound=BaseModel)

_SEQUENCES = (tuple, list, Sequence)
_MAPPINGS = (dict, Mapping)


class CheckedPathError(ValueError):
    """Programming error: a path step does not match the runtime annotation."""


def _strip(annotation: Any) -> Any:
    current = unwrap_wire_type(annotation)
    while get_origin(current) is Annotated:
        current = unwrap_wire_type(get_args(current)[0])
    return current


def _wire_names(name: str, info: Any) -> set[str]:
    names = {name}
    if isinstance(info.alias, str):
        names.add(info.alias)
    alias = info.validation_alias
    if isinstance(alias, str):
        names.add(alias)
    elif isinstance(alias, AliasChoices):
        names.update(choice for choice in alias.choices if isinstance(choice, str))
    return names


def _field_for_wire_name(model: type[BaseModel], element: str) -> str:
    matches = [name for name, info in model.model_fields.items() if element in _wire_names(name, info)]
    if len(matches) != 1:
        raise CheckedPathError("loc field is not declared or is ambiguous")
    return matches[0]


def _union_members(annotation: Any) -> tuple[Any, ...]:
    if get_origin(annotation) in (Union, UnionType):
        return get_args(annotation)
    return ()


class CheckedPath(Generic[RootT, CurrentT]):
    __slots__ = ("_root", "_current", "_segments", "_discriminator")

    def __init__(self, root: ModelIdentity, current: Any, segments: tuple[PathSegment, ...],
                 discriminator: str | Discriminator | None = None) -> None:
        self._root = root
        while get_origin(current) is Annotated:
            annotation, *metadata = get_args(current)
            for entry in metadata:
                if isinstance(entry, FieldInfo) and entry.discriminator is not None:
                    discriminator = entry.discriminator
            current = annotation
        self._current = _strip(current)
        self._segments = segments
        self._discriminator = discriminator

    @staticmethod
    def root(model: type[RootModelT]) -> "CheckedPath[RootModelT, RootModelT]":
        return CheckedPath(ModelIdentity.of(model), model, ())

    def _step(self, current: Any, segment: PathSegment,
              discriminator: str | Discriminator | None = None) -> "CheckedPath[Any, Any]":
        return CheckedPath(self._root, current, (*self._segments, segment), discriminator)

    def field(self: "CheckedPath[RootT, ModelT]", ref: FieldRef[ModelT, ValueT]) -> "CheckedPath[RootT, ValueT]":
        binding = bind_field(ref)
        current = self._current
        if not isinstance(current, type) or not issubclass(current, binding.model):
            raise CheckedPathError(f"field {binding.field!r} does not belong to the current path model")
        info = current.model_fields[binding.field]
        return self._step(info.annotation, FieldSegment(owner=ModelIdentity.of(binding.model), name=binding.field),
                          info.discriminator)

    def present(self: "CheckedPath[RootT, ValueT | None]") -> "CheckedPath[RootT, ValueT]":
        members = _union_members(self._current)
        if NoneType not in members:
            raise CheckedPathError("present() requires a nullable current value")
        rest = tuple(member for member in members if member is not NoneType)
        current = rest[0] if len(rest) == 1 else Union[rest]
        return CheckedPath(self._root, current, self._segments, self._discriminator)

    @overload
    def item(self: "CheckedPath[RootT, tuple[ItemT, ...]]", index: int) -> "CheckedPath[RootT, ItemT]": ...
    @overload
    def item(self: "CheckedPath[RootT, list[ItemT]]", index: int) -> "CheckedPath[RootT, ItemT]": ...
    @overload
    def item(self: "CheckedPath[RootT, Sequence[ItemT]]", index: int) -> "CheckedPath[RootT, ItemT]": ...
    def item(self: "CheckedPath[RootT, Any]", index: int) -> "CheckedPath[RootT, Any]":
        origin = get_origin(self._current)
        args = get_args(self._current)
        if origin not in _SEQUENCES or not args:
            raise CheckedPathError("item() requires a sequence current value")
        if type(index) is not int or index < 0:
            raise CheckedPathError("item() index must be a non-negative int")
        if origin is tuple and not (len(args) == 2 and args[1] is Ellipsis):
            if index >= len(args):
                raise CheckedPathError("item() index is outside the fixed tuple")
            element = args[index]
        else:
            element = args[0]
        return self._step(element, IndexSegment(index=index))

    @overload
    def key(self: "CheckedPath[RootT, dict[KeyT, ValueT]]", key: KeyT) -> "CheckedPath[RootT, ValueT]": ...
    @overload
    def key(self: "CheckedPath[RootT, Mapping[KeyT, ValueT]]", key: KeyT) -> "CheckedPath[RootT, ValueT]": ...
    def key(self: "CheckedPath[RootT, Any]", key: Any) -> "CheckedPath[RootT, Any]":
        args = get_args(self._current)
        if get_origin(self._current) not in _MAPPINGS or len(args) != 2:
            raise CheckedPathError("key() requires a mapping current value")
        if not isinstance(key, (str, int)) or isinstance(key, bool):
            raise CheckedPathError("key() supports str or int keys")
        try:
            TypeAdapter(args[0]).validate_python(key, strict=True)
        except ValidationError as exc:
            raise CheckedPathError("key() key does not match the mapping key type") from exc
        return self._step(args[1], KeySegment(key=key))

    def variant(self, branch: type[BranchT]) -> "CheckedPath[RootT, BranchT]":
        members = tuple(_strip(member) for member in _union_members(self._current))
        if branch not in members:
            raise CheckedPathError(f"{branch.__qualname__} is not a branch of the current union")
        return self._step(branch, VariantSegment(branch=ModelIdentity.of(branch)))

    def freeze(self) -> ValidatedFieldPath:
        if not self._segments:
            raise CheckedPathError("a field path needs at least one field segment")
        return ValidatedFieldPath(root=self._root, segments=self._segments)

    @staticmethod
    def from_pydantic_loc(root: type[BaseModel], loc: tuple[str | int, ...]) -> ValidatedFieldPath | None:
        """Resolve a Pydantic ``loc`` against the schema; ``None`` if it does not match."""
        path: CheckedPath[Any, Any] = CheckedPath.root(root)
        try:
            for element in loc:
                path = path._resolve_loc(element)
            return path.freeze()
        except CheckedPathError:
            return None

    def _resolve_loc(self, element: str | int) -> "CheckedPath[Any, Any]":
        current = self._current
        members = _union_members(current)
        if members:
            present = tuple(_strip(member) for member in members if member is not NoneType)
            if self._discriminator is not None:
                if not isinstance(self._discriminator, str):
                    raise CheckedPathError("callable discriminator is not a schema loc selector")
                tagged = []
                for member in present:
                    if not isinstance(member, type) or not issubclass(member, BaseModel):
                        raise CheckedPathError("discriminator branch must be a model")
                    field = _field_for_wire_name(member, self._discriminator)
                    tag_type = _strip(member.model_fields[field].annotation)
                    if get_origin(tag_type) is not Literal:
                        raise CheckedPathError("discriminator must declare literal tags")
                    if element in get_args(tag_type):
                        tagged.append(member)
                if len(tagged) != 1:
                    raise CheckedPathError("unknown or ambiguous discriminator tag")
                return self._step(tagged[0], VariantSegment(branch=ModelIdentity.of(tagged[0])))
            named = [member for member in present if getattr(member, "__name__", None) == element]
            if len(named) == 1:
                return self._step(named[0], VariantSegment(branch=ModelIdentity.of(named[0])))
            if named:
                raise CheckedPathError("ambiguous union branch name")
            if len(present) != 1:
                raise CheckedPathError("ambiguous union in loc")
            return CheckedPath(self._root, present[0], self._segments)._resolve_loc(element)
        if isinstance(current, type) and issubclass(current, BaseModel):
            if not isinstance(element, str):
                raise CheckedPathError("loc field is not declared")
            name = _field_for_wire_name(current, element)
            info = current.model_fields[name]
            return self._step(info.annotation, FieldSegment(owner=ModelIdentity.of(current), name=name),
                              info.discriminator)
        origin = get_origin(current)
        if origin in _SEQUENCES and isinstance(element, int):
            return cast(Any, self).item(element)
        if origin in _MAPPINGS:
            return cast(Any, self).key(element)
        raise CheckedPathError("loc element does not match the annotation")
