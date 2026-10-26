# Cascade — декларативные привязки параметров — DONE

**Статус:** имплементировано (S0–S4). 69 каскад-тестов зелёные.

## Мотивация

`contextResolver.py` смешивает две зоны: generic-механизм (`extend`,
обход цепочки) и per-param привязки — три диспатча по identity
(`_materialize`, `_apply_fold`, `_resolve_default`), растущие линейно
с каждым новым `Cascade`-параметром.

Дефолт — **невидимый дрейф контракта**: `cascadeParams` декларирует
`CANONICAL_DEFAULT`, но *какой* именно дефолт — отдельный факт в
engine-таблице. Верификатор покрытие привязок не проверяет:
тихая подмена (`CITY_SIZE` → `DistrictDensity.default()`) или забытая
ветка ловятся только в рантайме. Тот же антипаттерн, что spec
запрещает для рёбер: «two independent facts that can silently
disagree».

## Целевое состояние

**Принцип:** всё, что выражается **значением или именем** — живёт в
декларации параметра (dataModel); всё, что требует world/rng — имя в
dataModel + binding в application. Engine — чистый механизм, ни одного
`param is X`.

### Слои

| Слой | Что живёт |
|---|---|
| `dataModel/cascade/cascadeSpec.py` | `Cascade` + `default_value`, `materialize` (имя), `default_registry` (имя) |
| `dataModel/cascade/cascadeVerify.py` | presence/absence привязок по политике; тип `default_value` сверяется с аннотацией поля контекста |
| `dataModel/locations/context/cascadeParams.py` | самодостаточные декларации: дефолт подтянут из POJO, имена резолверов |
| `generators/utils/economicTierBands.py` | `materialize_tier_input` — BAND/RANGE dispatch + tier-range (доменная семантика) |
| `generators/utils/materialResolver.py` | `fold_dominant_material` — seeded tier→material pick |
| `application/worldData/context/contextResolver.py` | только механизм: `extend`, chain walk, три lookup-таблицы по **имени**, policy interpreter |

### Контракты

```python
# cascadeSpec.Cascade +=
default_value: object | None = None      # CANONICAL_DEFAULT: значение из POJO
materialize: str | None = None           # имя резолвера для BAND/RANGE
default_registry: str | None = None      # имя world-реестра для REGISTRY_MEDIAN

# cascadeParams.py — значения тянутся ИЗ POJO, не литералы:
SETTLEMENT_DENSITY = Cascade(...,
    default=DefaultPolicy.CANONICAL_DEFAULT,
    default_value=DistrictDensity.default())
ECONOMIC_TIER = Cascade(...,
    default=DefaultPolicy.REGISTRY_MEDIAN,
    materialize="economic_tier",
    default_registry="economic_tiers")

# engine — сигнатуры привязок:
_MATERIALIZE: dict[str, fn]   # (world, kind, raw, anchor, rng) -> value | None
_FOLDS:       dict[str, fn]   # (level, objects, resolved, world) -> (value, source)
_REGISTRIES:  dict[str, fn]   # world -> registry (метод .resolve_default(policy))
```

### Data flow (без изменений семантики)

`extend` → chain walk узлов уровня → `VALUE`: raw | `BAND`/`RANGE`:
`_MATERIALIZE[param.materialize](...)` → наследие → `fold`:
`_FOLDS[param.fold](...)` → default: `CANONICAL_DEFAULT` →
`param.default_value`; `REGISTRY_MEDIAN` →
`_REGISTRIES[param.default_registry](world).resolve_default(...)`.
`model_copy(update=)` не валидирует → тип `default_value` гарантирует
**верификатор**, не рантайм.

### Правила верификатора (новые)

- `default_value` обязателен ⟺ `CANONICAL_DEFAULT`; запрещён иначе
- `default_registry` обязателен ⟺ `REGISTRY_MEDIAN`; запрещён иначе
- `materialize` обязателен при наличии не-`VALUE` каналов; иначе `None`
- тип `default_value` — подтип аннотации поля контекста
- покрытие binding-таблиц (имена резолвимы) — проверка на import
  engine-модуля (dataModel verify не знает application-callables)

## Шаги

Один шаг за заход: шаг → отчёт → «ок» → следующий.

### S0 — правка ТЗ

- **Цель:** зафиксировать декларативные привязки в контракте ТЗ
- **ТЗ:** `tz_cascade_context.md` §3 (таблица `Cascade` + абзац про
  materialize как «локальную привязку движка» — стр. 203–212), §4
  (движок = name-lookup, стр. 279–285)
- **Файлы:** `docs/tz_cascade_context.md`
- **Контракт:** в §3 добавить `default_value`/`materialize`/
  `default_registry` в таблицу полей; переписать абзац «Materialize…
  привязкой по имени поля внутри contextResolver» → имя на `Cascade`,
  binding-таблицы engine; §4 — движок не содержит `param is X`
- **Проверка:** глазами, разделы согласованы
- **Done:** ТЗ описывает целевое состояние

### S1 — контракт: spec + params + verify

- **Цель:** декларации становятся самодостаточными; рантайм не меняется
  (engine поля ещё не читает)
- **ТЗ:** `tz_cascade_context.md` §3 (обновлённый в S0)
- **Файлы:** `dataModel/cascade/cascadeSpec.py`,
  `dataModel/cascade/cascadeVerify.py`,
  `dataModel/locations/context/cascadeParams.py`
- **Контракт:** три новых поля `Cascade`; правила verify из таблицы
  выше; `default_value` заполняется вызовами POJO-accessor'ов
  (`DistrictDensity.default()`, `CONSTRUCTION_MATERIAL_DEFAULTS.*`,
  `WorldSettlementSizeRegistry.default_system_size()`), не литералами
- **Проверка:** `python -m unittest tests.test_location_context_contract
  tests.test_context_extend` из `backend/` — зелёные; verify проходит
  с новыми правилами
- **Done:** контракт объявлен и проверяется; engine не тронут

### S2 — доменные резолверы

- **Цель:** семантика уезжает домой; engine пока вызывает через
  существующие диспатчи (тонкая делегация, поведение 1:1)
- **ТЗ:** `tz_cascade_context.md` §4 (семантика materialize тира)
- **Файлы:** `generators/utils/economicTierBands.py`
  (+ `materialize_tier_input`: BAND → `materialize_band`, RANGE →
  перенесённый `_materialize_tier_range`),
  `generators/utils/materialResolver.py`
  (+ `fold_dominant_material`: перенос seeded-pick из `_apply_fold`),
  `contextResolver.py` (только делегация в диспатчах)
- **Контракт:** сигнатуры `_MATERIALIZE`/`_FOLDS` из §Контракты
- **Проверка:** те же unittest + `python -m compileall app`
- **Done:** доменная логика живёт в доменных модулях; identity-диспатчи
  в engine остаются (снимаются в S3)

### S3 — engine = чистый механизм

- **Цель:** удалить все `param is X` из `contextResolver.py`
- **ТЗ:** `tz_cascade_context.md` §4
- **Файлы:** `contextResolver.py`
- **Контракт:** `_MATERIALIZE`/`_FOLDS`/`_REGISTRIES` по имени;
  generic policy interpreter для default; покрытие имён — проверка на
  import модуля; опционально `_check_level` (валидация уровня из
  `extend`, ~20 строк)
- **Проверка:** `python -m unittest tests.test_context_extend
  tests.test_location_context_contract tests.test_cascade_context_baseline
  tests.test_cascade_migration_m2` — зелёные; `grep "param is "` в
  файле = 0
- **Done:** engine ~150–180 строк чистого механизма; диспатчей нет

### S4 — slim engine: лог-формат → cascadeLog, `_CASCADE_FIELDS`

- **Цель:** из `extend` уходят две не-resolver зоны: presentation лога
  и повторный скан `model_fields` на каждый вызов
- **ТЗ:** `tz_cascade_context.md` §4 «Логирование» — формат сообщения
  не меняется, меняется владелец форматирования
- **Файлы:** `application/worldData/context/cascadeLog.py`,
  `contextResolver.py`
- **Контракт:** `log_scope_resolve(params=)` принимает структуру
  `dict[str, (value, inherited_source, source)]`; форматирование
  `parent=`/`child=` — внутри cascadeLog. `_CASCADE_FIELDS` —
  модульная константа (модель frozen), её же читает `_check_bindings`
- **Проверка:** `python -m unittest tests.test_context_extend
  tests.test_location_context_contract tests.test_cascade_context_baseline
  tests.test_cascade_migration_m2`; DEBUG-строки лога идентичны
- **Done:** `extend` = gate → resolve → copy → log; дубля скана нет

## Deferred / не в scope

- `param.levels` coverage-семантика, level-agnostic каналы — из
  `nl-typed-host-payload.md`, отдельная ветка
- Новые каскад-параметры после рефактора объявляются только в
  `cascadeParams` + binding-строкой — это и есть приёмка дизайна
