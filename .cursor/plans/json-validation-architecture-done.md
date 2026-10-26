# jsonValidation — целевая архитектура (POJO-first) ✅ DONE

**Канон:** [`docs/tz_json_validation.md`](../docs/tz_json_validation.md)

Статус: **v1 slice живёт**; ниже — краткая выжимка для агента. Не откат к `worldData/jsonValidation` v0.1.

## Слои (строго сверху вниз)

```
wire JSON / World row
    → jsonValidation/facade      (import / CRUD write, strict → 422)
    → jsonValidation/worldRow    (runtime read, warn-only)
         ↓ оба через
    → jsonValidation/resolve     (единый policy engine)
         ↓ читает только
    → dataModel POJO             (поля, policy, canonical_*, SCHEMA_ID)
         ↓ колонки
    → db/models/world.py + 0001_initial.sql

import-only (позже):
    → jsonValidation/index       (REF-W cross-ref после normalize)

generators / DAG:
    → worldRow accessors ONLY    (не raw row для POJO-полей)
    → world_seed() и прочая чистая математика — в generators, не в POJO
```

## Что живёт где

| Слой | Ответственность | Запрещено |
|------|-----------------|-----------|
| **dataModel** | POJO, `StrictOnWire`/`OptionalOnWire`, `canonical_*`, `SCHEMA_ID`, wire projection helpers для multi-column slices | import orchestration, HTTP, generator logic |
| **resolve** | per-field policy; `ResolveMode.IMPORT` vs `RUNTIME` | дублировать defaults литералами |
| **worldRow** | `World` → POJO (runtime) | списки wire-ключей вручную |
| **facade** | wire dict → normalized dict (import) | отдельные `normalize/*.py` с константами |
| **index** | registry index, REF-W (только import) | runtime fallback |
| **worldService** | technical invariants (`fine_cells_per_map_cell`, …) | domain defaults дублирующие POJO |
| **generators** | симуляция | `dict.get` по registry rows; literals из POJO |

## WorldSlice — единый дескриптор (целевой)

Каждый кусок `worlds`, покрытый POJO, описывается **один раз**:

```python
@dataclass(frozen=True)
class WorldSlice:
    schema_id: str           # "SCH-WORLD-ECON-TIER"
    pojo_cls: type           # WorldEconomyTierRegistry
    wire_kind: Literal["multi_column", "registry_list", "registry_dict", "json_blob"]
    world_keys: tuple[str, ...]  # ("economic_tier_registry",) или climate 8-col
    empty_factory: Callable    # canonical_defaults | canonical_empty
    wire_from_mapping: Callable | None  # multi_column only; иначе getattr(data, key)
```

- **facade** и **worldRow** итерируют `WORLD_SLICES` — не свои `_LIST_REGISTRY_KEYS`.
- Новый POJO → одна запись в реестре + колонки в `World` + assert при старте.

Эталон multi-column: `WorldClimateScalars` + `climate_scalar_wire_from_mapping`.

## SCHEMA_ID

- Константа `SCHEMA_ID` на модуле POJO (не только docstring `__init__.py`).
- Пробрасывается в `ResolveContext` → `FieldPathError` / HTTP 422.
- `loc` + `schema_id` + `code` — контракт для будущего редактора миров.

## Import vs runtime (не смешивать)

| | Import | Runtime |
|---|--------|---------|
| StrictOnWire | 422 | warn, omit/skip row |
| Optional | default + log | default + log |
| Пустой registry `[]` | политика import (явно) | `canonical_*` + warn |
| Cross-ref | index после normalize | не проверять |

`world_seed(world)` — **вне** POJO/jsonValidation; детерминизм процедурки от `world_uid`.

## Порядок имплементации каркаса (не фичи)

0. **Generators → worldRow** — очередь **GV-1…7** в [`docs/tz_json_validation.md`](../docs/tz_json_validation.md) § *Generators — миграция на worldRow (GV)*
1. `SCHEMA_ID` на покрытых POJO + в ошибках resolve
2. `worldSlices.py` — реестр slice для уже подключённых POJO (climate, tiers, materials, terrain, hydrology, climate_zones)
3. Рефактор `facade` + `worldRow` на общий реестр
4. `index/` stub + контракт REF-W (без всех validators v0.1)
5. Правило: generators → только worldRow для POJO-backed полей
6. Миграция оставшихся `worlds.*_registry` → POJO → slice → facade

## Не делать

- Восстанавливать orchestrator + `validators/*.py` v0.1 с ручными правилами
- `normalize/climateDefaults.py` и параллельные default-таблицы
- Gates в `api/utils/*Gate.py` до стабилизации facade API
- Фичи (peak on import, races) **до** slice registry + SCHEMA_ID

## Ссылки

- [`docs/tz_json_validation.md`](../../docs/tz_json_validation.md) — **канон**
- `.cursor/rules/pojo-world-row-wire.mdc` — multi-column projection
- `.cursor/rules/dataModel-no-hardcode.mdc` — POJO source of truth
- `.cursor/rules/layer-boundaries.mdc` — generators не владеют import
