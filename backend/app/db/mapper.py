import dataclasses
import json
from typing import Any, Type, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Field helpers — используются в моделях вместо голого dataclasses.field()
# ---------------------------------------------------------------------------

def json_col(
    *,
    default: Any = dataclasses.MISSING,
    default_factory: Any = dataclasses.MISSING,
) -> Any:
    """dict-поле: пустой dict → NULL в БД, NULL → {}."""
    kw: dict[str, Any] = {"metadata": {"db_type": "json"}}
    if default_factory is not dataclasses.MISSING:
        kw["default_factory"] = default_factory
    elif default is not dataclasses.MISSING:
        kw["default"] = default
    return dataclasses.field(**kw)


def json_nullable_col(default: Any = None) -> Any:
    """dict-поле: None → NULL в БД, NULL → None."""
    return dataclasses.field(default=default, metadata={"db_type": "json_nullable"})


def bool_col(default: bool = True) -> Any:
    """bool-поле: хранится как INTEGER 0/1 в SQLite."""
    return dataclasses.field(default=default, metadata={"db_type": "bool"})


# ---------------------------------------------------------------------------
# Внутренние хелперы
# ---------------------------------------------------------------------------

def _col_name(f: dataclasses.Field) -> str:
    return f.metadata.get("col", f.name)


def _serialize(f: dataclasses.Field, value: Any) -> Any:
    db_type = f.metadata.get("db_type")
    if db_type == "json":
        return json.dumps(value, ensure_ascii=False) if value else None
    if db_type == "json_nullable":
        return json.dumps(value, ensure_ascii=False) if value is not None else None
    if db_type == "bool":
        return int(value)
    return value


def _deserialize(f: dataclasses.Field, value: Any) -> Any:
    db_type = f.metadata.get("db_type")
    if db_type == "json":
        return json.loads(value) if value else {}
    if db_type == "json_nullable":
        return json.loads(value) if value is not None else None
    if db_type == "bool":
        return bool(value)
    return value


# ---------------------------------------------------------------------------
# Публичное API маппера
# ---------------------------------------------------------------------------

def pk_col(cls: type) -> str:
    """Возвращает имя колонки первичного ключа."""
    pk_field_name: str = cls.__pk__
    for f in dataclasses.fields(cls):
        if f.name == pk_field_name:
            return _col_name(f)
    return pk_field_name


def to_row(obj: Any) -> tuple[list[str], list[Any]]:
    """(columns, values) для INSERT. Добавляет дискриминаторные колонки."""
    discriminator: dict = getattr(type(obj), "__discriminator__", {})
    cols, vals = [], []
    for f in dataclasses.fields(obj):
        cols.append(_col_name(f))
        vals.append(_serialize(f, getattr(obj, f.name)))
    for col, val in discriminator.items():
        cols.append(col)
        vals.append(val)
    return cols, vals


def to_update_row(obj: Any) -> tuple[list[str], list[Any], Any]:
    """(SET-клаузы, значения, pk_value) для UPDATE.
    Автоматически исключает PK, created_at и поля из __update_exclude__."""
    cls = type(obj)
    pk_field: str = cls.__pk__
    extra_exclude: frozenset = getattr(cls, "__update_exclude__", frozenset())
    exclude = {pk_field, "created_at"} | extra_exclude

    set_clauses: list[str] = []
    set_vals: list[Any] = []
    pk_val: Any = None

    for f in dataclasses.fields(obj):
        if f.name == pk_field:
            pk_val = getattr(obj, f.name)
        if f.name in exclude:
            continue
        set_clauses.append(f"{_col_name(f)} = ?")
        set_vals.append(_serialize(f, getattr(obj, f.name)))

    return set_clauses, set_vals, pk_val


def model_columns(cls: type) -> set[str]:
    """Набор имён колонок модели включая дискриминаторные."""
    cols = {_col_name(f) for f in dataclasses.fields(cls)}
    cols |= set(getattr(cls, "__discriminator__", {}).keys())
    return cols


def from_row(cls: Type[T], row: Any) -> T:
    """Строит экземпляр модели из aiosqlite Row."""
    kwargs = {}
    for f in dataclasses.fields(cls):
        col = _col_name(f)
        kwargs[f.name] = _deserialize(f, row[col])
    return cls(**kwargs)
