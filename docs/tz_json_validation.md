# JSON Validation — Technical Specification

**Версия документа: 1.2** (2026-07)

**Статус кода:** v1 vertical slice — POJO-first `application/jsonValidation/`.  
**Не является:** откатом к `worldData/jsonValidation/` v0.1 (orchestrator + `normalize/*.py` + `validators/*.py`).

| Поле | Значение |
|------|----------|
| Код | `backend/app/application/jsonValidation/` |
| Покрытие import | `world` slice: climate scalars, tiers, materials, terrain, hydrology, climate_zones |
| Покрытие runtime | `worldRow` — те же POJO через `resolve` (warn-only) |
| Bundle sections | `world` ✅; `connection_*` — JV-0b ⬜; races, perks, locations — ⬜ |
| JV-0 ENUM gate | JV-0a ✅ `resolve` + `UNKNOWN_ENUM`; JV-0b bundle DTO — ⬜ |
| REF-W index | ✅ (MVP) |
| `SCHEMA_ID` в 422 | ✅ |
| `worldSlices.py` реестр | ✅ |

---

## Назначение

Единый контракт **семантической** проверки и **normalize-on-import** master JSON: bundle import, CRUD мира, будущий редактор миров.

| Документ | Роль |
|----------|------|
| **Этот ТЗ** | архитектура v1, field policy, import/runtime, SCH-* ↔ dataModel |
| [`tz_json_import.md`](./tz_json_import.md) | HTTP transport, `ImportResult`, repos |
| [`project_data_storage_tz.md`](./project_data_storage_tz.md) | N+1, `system_*` / `display_*`, L1/L2/L3 N1-S |
| [`tz_races.md`](./tz_races.md) | домен race contract (JV-8) |
| Domain `tz_*.md` | доменные правила по ссылке из SCH-* |
| [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) | HY-5 wire enum, generator debt |

**Out of scope:** `engine/` + LLM turn contract; geometry post-generate; faction sketch.

**Аудитория:** мастер мира (import, editor). Игрок реестры и JSON validation не видит.

---

## §0 — Vocabulary (ENUM-E / N1-S / N1-W)

> Полные таблицы N1-S L1/L2/L3 — [`project_data_storage_tz.md`](./project_data_storage_tz.md).  
> Исторический Field Contract Registry v0.1 (помесячные таблицы полей) — git `f25dd3e:docs/tz_json_validation.md`; для **POJO-covered** полей контракт перенесён в `dataModel/`.

### Три слоя (не смешивать)

| Слой | ID | Суть | Пример |
|------|-----|------|--------|
| Engine-closed тип | `ENUM-E` | StrEnum; unknown на import → reject | `material_category`, `graph_level`; `node_category` — engine post-JV (`NpcFieldCategory`) |
| N1-S schema | `N1-S` | `system_name` / `display_name` в schema tables | `stat_schema`, `npc_fields` |
| N1-W vocabulary | `N1-W` | мастер расширяет строки реестра | `material_registry[]`, `climate_zone_registry` |

**Правило:**

```
ref на сущность     → ключ ∈ N1-S или N1-W index мира (import: после normalize)
поле type/category  → ∈ ENUM-E (strict reject unknown)
```

Preset keys в fixtures (`temperate`, `water`) — **строки N1-W**, не отдельный ENUM gate.

### REF-W → N1-W (cross-ref, import-only)

| REF-W | N1-W | Match field |
|-------|------|-------------|
| REF-W-MATERIAL | N1-W-01 | `system_material` |
| REF-W-LIQUID | N1-W-01 | row `material_category=liquid` |
| REF-W-TERRAIN | N1-W-02 | `system_terrain` |
| REF-W-CLIMATE | N1-W-04 | `system_climate` |
| REF-W-ECON-TIER | N1-W-09 | `system_tier` |
| REF-W-CONN | N1-W-06 | `system_connection_type` |
| REF-W-LOC-TYPE | N1-W-07 | `system_location_type` |

Полная таблица — git history v0.1 § Field Contract Registry.  
Имплементация: `jsonValidation/index/` (✅ MVP), **после** `resolve` + normalize.

### Wire enum parse

`jsonValidation/wire.py` — `parse_enum()` / `WireEnumError` на границе **import** (ENUM-E).  
Generators — enum members, не string literals ([`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) HY-5).  
Полный план имплементации — § **JV-0**.

---

## Архитектура v1 — POJO-first

### Слои (сверху вниз)

```
wire JSON / World row
    → jsonValidation/facade       (import / CRUD write)
    → jsonValidation/worldRow     (runtime read)
         ↓ оба через
    → jsonValidation/resolve      (единый policy engine)
         ↓ читает только
    → dataModel POJO              (поля, policy, canonical_*, SCHEMA_ID)
         ↓ колонки
    → db/models/world.py + migrations/0001_initial.sql

import-only (✅ MVP):
    → jsonValidation/index        (REF-W после normalize)

generators / DAG:
    → worldRow accessors          (POJO-backed поля)
    → world_seed() и др. math     (в generators, не в POJO)
```

### Размещение кода

```
backend/app/application/jsonValidation/
├── resolve.py      # policy engine: IMPORT vs RUNTIME; JV-0a: StrEnum → parse_enum
├── facade.py       # normalize_world() — import/CRUD
├── worldRow.py     # runtime accessors → POJO
├── wire.py         # ENUM-E parse (parse_enum, WireEnumError)
├── bundle/         # JV-0b: import-row DTOs (connection_nodes, …) ⬜
├── types.py        # FieldPathError, ImportValidationError
└── index/          # REF-W после normalize (MVP)

backend/app/dataModel/              # единственный source of truth defaults
backend/app/application/worldData/  # WorldService, bundle — без domain validate
```

**Запрещено (антипаттерн v0.1):**

- `worldData/jsonValidation/normalize/*.py` с literals параллельно POJO
- `validators/*.py`, дублирующие `Field` / `StrictOnWire`
- `api/utils/*Gate.py` до стабилизации facade API
- generators импортируют defaults из validation layer

### Мир ≠ персонаж

| Сущность | Пакет |
|----------|--------|
| World bundle / CRUD | `application/jsonValidation/` |
| Character sheet | `character/jsonValidation/` (⬜, JV-6) |

---

## Field policy (annotationPolicy)

Контракт поля на POJO — `dataModel/annotationPolicy.py`:

| Annotation | Import (facade) | Runtime (worldRow) |
|------------|-----------------|---------------------|
| `StrictOnWire` | **422**, запись не идёт | warning, поле/строка пропускается |
| `OptionalOnWire` / без аннотации | `Field(default)` + **log** | то же |
| `IgnoreOnWire` | wire as-is, без автозаполнения | то же |

**Ядерный fallback запрещён:** одна ошибка в registry **не** заменяет весь POJO на `canonical_defaults()`.

**Пустой registry `[]` / отсутствие ключа:**

| Режим | Поведение (текущее) |
|-------|---------------------|
| Import, ключ отсутствует | колонка не трогается; dataclass defaults |
| Import, `[]` | `resolve_root_list` → `canonical_defaults()` |
| Runtime, null/пусто | `canonical_*` + warning |

Политика empty-on-import — уточняется per-slice в POJO; не дублировать в facade.

---

## SCH-* ↔ dataModel

Идентификатор схемы (`SCHEMA_ID`) — на модуле POJO (целевое: константа в коде, не только docstring).

| SCHEMA_ID | POJO | `worlds` column(s) | facade | worldRow |
|-----------|------|-------------------|--------|----------|
| SCH-WORLD-CLIMATE | `WorldClimateScalars` | 8 scalar columns | ✅ | ✅ |
| SCH-WORLD-ECON-TIER | `WorldEconomyTierRegistry` | `economic_tier_registry` | ✅ | ✅ |
| SCH-WORLD-MATERIAL | `WorldMaterialRegistry` | `material_registry` | ✅ | ✅ |
| SCH-WORLD-TERRAIN | `WorldTerrainRegistry` | `terrain_registry` | ✅ | ✅ |
| SCH-WORLD-HYDROLOGY | `WorldHydrology` | `hydrology` | ✅ | ✅ |
| SCH-WORLD-CLIMATE-ZONE | `WorldClimateZoneRegistry` | `climate_zone_registry` | ✅ | ✅ |
| SCH-WORLD-BARRIER-TEMPLATE | `WorldBarrierTemplateRegistry` | `barrier_template_registry` | ⬜ | ✅ runtime |
| SCH-WORLD-CITY-SIZE | `WorldCitySizeRegistry` | `city_size_registry` | ⬜ | ✅ runtime |
| SCH-WORLD-DISTRICT-TEMPLATE | `WorldDistrictTemplateRegistry` | `district_template_registry` | ⬜ | ✅ runtime |
| SCH-WORLD-TERRAIN-SCALARS | `WorldTerrainScalars` | multi-column | ✅ wire | ✅ `terrain_scalars()` |
| SCH-WORLD-ROAD-SETTINGS | `WorldRoadSettings` | `road_settings` | ⬜ | ✅ runtime |
| SCH-WORLD-CONN | `WorldConnectionTypeRegistry` | `connection_type_registry` | ⬜ | ⬜ |
| SCH-RACE-* | — | `races` table | ⬜ JV-8 | ⬜ |

Поля без POJO — пока struct/ad-hoc в `WorldService._validate` (technical invariants).

---

## Wire projection (multi-column slices)

Когда POJO мапится на **несколько колонок** `worlds` (не один JSON-ключ):

1. Имена полей — **только** из `POJO.model_fields`
2. Helper на модуле POJO: `*_wire_from_mapping(source)`
3. Startup assert: `POJO fields ⊆ World columns` (эталон: `validate_world_row_climate_columns`)
4. **Не дублировать** списки ключей в `facade.py` / `worldRow.py`

Эталон: `WorldClimateScalars` + `climate_scalar_wire_from_mapping`; terrain — `WorldTerrainScalars` + `terrain_scalar_wire_from_mapping`.

### WorldSlice (целевой реестр)

Каждый покрытый кусок `worlds` — **один дескриптор** в `worldSlices.py` (✅):

```python
@dataclass(frozen=True)
class WorldSlice:
    schema_id: str
    pojo_cls: type
    wire_kind: Literal["multi_column", "registry_list", "registry_dict", "json_blob"]
    world_keys: tuple[str, ...]
    empty_factory: Callable
    wire_from_mapping: Callable | None  # multi_column only
```

`facade` и `worldRow` итерируют `WORLD_SLICES` — не свои `_LIST_REGISTRY_KEYS`.

**Чеклист нового POJO на `worlds`:**

1. POJO + field policies
2. `World` column(s) + `0001_initial.sql` (recreate БД)
3. Wire helper + assert при старте
4. Запись в `WORLD_SLICES`
5. `SCHEMA_ID` константа

---

## Import path (write)

### Точки входа

| Trigger | Вызов |
|---------|--------|
| `POST /worlds` | `facade.normalize_world(data)` → `WorldService.create` |
| `PUT /worlds/{uid}` | `normalize_world(data, partial=True)` → update |
| `POST /worlds/import` | `normalize_world(bundle.world)` + bundle sections (JV-0b) **до** транзакции |
| `WorldService.import_from_json` | normalize внутри service |
| `WorldBundleService.import_bundle` | `world` → facade; `connection_nodes` / `connection_edges` → `jsonValidation/bundle/` (JV-0b) |

### HTTP — ошибки

| Ситуация | HTTP | Тело |
|----------|------|------|
| JSON не парсится | 422 | `JSON parse failed: …` (`JsonResolver`) |
| `StrictOnWire` | 422 | `detail: [{ "loc": [...], "msg": "..." }]` |
| ENUM-E unknown (JV-0) | 422 | `code: "UNKNOWN_ENUM"` + список допустимых wire values |
| Normalize warnings | 200/201 | **не в HTTP** — только server log |
| Technical (`map_cell_size_m`, …) | 422 | `WorldService._validate` |

**Формат strict error (422):**

```json
{
  "detail": [{
    "schema_id": "SCH-WORLD-ECON-TIER",
    "loc": ["economic_tier_registry", 0, "system_tier"],
    "code": "STRICT_REQUIRED",
    "msg": "strict field is required"
  }]
}
```

### Normalize vs reject

| Действие | Пример |
|----------|--------|
| **reject** | `StrictOnWire` missing/invalid; unknown ENUM-E (будущее) |
| **normalize** | optional field missing → `Field(default)` explicit в normalized dict |
| **warn (runtime only)** | legacy null в БД at generate |

**Отложено (после каркаса):**

- peak `-40/45` explicit on import (`canonical_defaults` только на import)
- `precipitation_liquid` ∈ `material_registry` liquid rows — **✅ import** (`index/validate.py`); runtime fallback в generators до JV-7

---

## Runtime path (read)

### Принцип: DB-first

После успешного import данные в SQLite считаются проверенными. Generators **не** вызывают facade.

```
WRITE (strict)                    READ (permissive)
JSON → facade → resolve → persist   DB → worldRow → resolve (RUNTIME) → POJO
     → 422                              → warn + canonical_* on gaps
```

### worldRow

Тонкие accessors: `climate_scalars(world)`, `materials(world)`, …  
Все через `resolve` в режиме `RUNTIME`.

**Generators:** POJO-backed поля — через `worldRow`, не `world.climate_pole_mode` напрямую (transitional допускается до рефактора; см. § **Generators — миграция на worldRow (GV)**).

### Resolve log (wire → resolved)

При отличии wire от resolved POJO — `INFO` в `resolve.py`:

```
json_validation | resolve | label=… mode=import|runtime | wire={…} | resolved={…}
```

Только при `wire ≠ resolved`; field-level warnings (`missing; using field default`) остаются отдельно.

### world_seed — вне jsonValidation

`world_seed(world)` = `hash(world_uid)` — детерминизм процедурки (climate autoresolve offset, terrain noise).

- **Не** колонка `worlds`
- **Не** POJO / import
- Живёт в `generators/climate/math.py`

Опционально в будущем: `worlds.generation_seed` для переката процедурки без смены uid.

### Anti-patterns (runtime)

- ❌ `facade.normalize_world` из generators
- ❌ semantic REF-W reject at generate (только `warn_once` + fallback до JV-7)
- ❌ дублировать POJO defaults литералами в generators

---

## Technical validation (SCH-WORLD-ROW-TECH)

Скалярные инварианты **без** POJO domain policy:

- `map_cell_size_m` — int, ≥1000, кратно 1000
- `grid_bbox_padding` ≥ 0
- `terrain_chunk_columns` ≥ 1
- `map_subsurface_depth` ≥ 10

Сейчас: `WorldService._validate`.  
Целевое: отдельный technical pass или поля на `World` metadata POJO — **не** смешивать с `WorldClimateScalars`.

---

## Generators — миграция на worldRow (GV)

**Назначение:** зафиксировать перенос `application/worldData/generators/` с сырого `world.*` / `dict.get` на typed accessors `jsonValidation/worldRow` → `dataModel` POJO.

**Не входит:** layout JSON зданий (`levels`, `rooms`, `connections`) — отдельный контракт structure; `world_seed()`; technical invariants (`map_cell_size_m`, …).

**Правило:** generators читают master-data **только** через `worldRow`; `model_dump()` в generators — не целевой путь (допустим только в resolve-логах и import facade).

### Статус по доменам

| Домен | worldRow accessor | Generators | Статус |
|-------|-------------------|------------|--------|
| Economic tiers | `economic_tiers()` | tierRegistry, economicTierBands, tierResolver, materialResolver, settlement economic/barriers | ✅ |
| Materials | `materials()` | materialResolver, precipitation, oresGenerator | ✅ |
| Terrain registry | `terrain()` / `terrain_system_keys()` | mapOccupancy, columnFill, caves, climate passes | ✅ |
| Climate zones | `climate_zones()` | `climate/registry.py` | ✅ |
| Climate scalars | `climate_scalars()` | anchorAssign, poleResolve, precipitation, tierResolve, climateRuntimeAssembler, climatePoleField, climateGeneratorService, climateSurfaceAssembler | ✅ |
| Hydrology | `hydrology()` | resolveHydrologyBands, resolveRiverTypeClassify, loadHydrologyFromWorld | ✅ POJO; ◐ `hydrology_dict` shim |
| Road settings | `road_settings()` | connectionPolicy, roadTravelResolver | ✅ runtime |
| Barrier templates | `barrier_templates()` | barrierDefaults, barriers, areaBarriers | ✅ |
| City sizes | `city_sizes()` | `footprint.footprint_multiplier` | ✅ |
| District templates | `district_templates()` | footprint → placement → DistrictSlot → roads | ✅ |
| Building layouts | `building_layout_templates()` | buildingDefaults, buildingCache | ◐ merge в worldRow; тело — `list[dict]` |
| Terrain scalars | `terrain_scalars()` | worldMapSettings, columnFillPass, climateGeneratorService (lapse) | ✅ |
| Connection types | ⬜ | — | ⬜ POJO есть, consumers нет |
| Location types, lore, weather, room types, terrain categories, location mood | ⬜ | — | ⬜ |
| Material category / use_type registries | ⬜ | enum-only в `materialCategory.py` | ⬜ |

### Частично: POJO / accessor есть, generators ещё читают `world.*`

| Поле / slice | Сейчас в generators | Целевое |
|--------------|---------------------|---------|
| `grid_bbox_padding` | `worldMapSettings` | technical / metadata accessor (не domain POJO) |
| `default_passage_height` | structureGeneratorService, passages | ⬜ structure defaults POJO или worldRow |
| `world_bounds` | `terrain/passes/bbox.py` | JSON blob accessor (отдельное решение) |

~~GV-1 (climate scalars):~~ … **✅ через `climate_scalars(world)`**.  
~~GV-2 (terrain scalars):~~ `terrain_chunk_columns`, `map_subsurface_depth`, `z_min`, `z_max`, `elevation_lapse_rate`, `magma_band_thickness`, `closed_planet_grid` — **✅ через `terrain_scalars(world)`** (`grid_bbox_padding` — technical `world.*`).

### Намеренно wire-shaped (не world registry POJO)

| Что | Где | Следующий шаг |
|-----|-----|----------------|
| Building layout bodies | `structure/`, assemblers, `building_layout_templates()` | JV-4 / typed layout POJO |
| `economic_tier_band` на template dict | `tierResolver.band_from_template` | POJO шаблонов или bundle |
| `building_tier_compatible(template: dict)` | economic.py, buildingCache | после layout POJO |

### Facade import — пробелы (symmetry с runtime)

`normalize_world` **не** нормализует (⬜): `barrier_template_registry`, `city_size_registry`, `district_template_registry`, `road_settings`, terrain scalars, building templates.  
Runtime уже читает через `resolve` в `worldRow` для barrier / city / district.

### Очередь GV (приоритет)

| ID | Scope | P | Зависимость |
|----|-------|---|-------------|
| GV-1 | Дожать **climate scalars** — убрать прямой `world.climate_*` / `precipitation_liquid` / `season_temp_offsets` | P1 | — | ✅ |
| GV-2 | **`terrain_scalars(world)`** в worldRow + wire projection; worldMapSettings, columnFillPass, lapse | P1 | — | ✅ |
| GV-3 | Facade: barrier, city_size, district, road_settings, terrain scalars | P1 | JV-1b удобнее после GV-1/2 |
| GV-4 | Убрать `hydrology_dict` shim; consumers только `hydrology()` POJO | P2 | — |
| GV-5 | Подключить реестры с POJO без consumers (connection_type, location_type, …) по мере появления в generators | P2 | JV-2 REF-W |
| GV-6 | Building layout typed POJO (не только `building_layout_templates` dict merge) | P2 | JV-4 |
| GV-7 | Удалить transitional `*_rows()` shims после полного GV | P3 | GV-1…6 |

**Порядок:** ~~GV-1~~ ~~GV-2~~ ~~JV-1b~~ → GV-3 → остальное.  
Архитектура (slice registry) не блокирует GV-1/2, но снижает дубли в facade/worldRow.

---

## Связь с v0.1 (история)

| v0.1 (`worldData/jsonValidation/`) | v1 (текущее) |
|-----------------------------------|--------------|
| `JsonValidationFacade` + orchestrator | `facade` + `resolve` |
| `normalize/climateDefaults.py` | `WorldClimateScalars` + `resolve` |
| `validators/*.py` per SCH | POJO `StrictOnWire` |
| `WorldRegistryIndex` monolith | `index/` ✅ MVP поверх normalized POJO |
| `api/utils/*Gate.py` | прямой вызов из `WorldService` / bundle |
| Field Contract tables в TZ | POJO `model_fields` + annotations |

**Берём из v0.1 идеи, не код:** REF-W index, `ValidationKind` dispatch для bundle sections, structured issues с `schema_id`.

---

## JV-0 — ENUM-E import gate

**Цель:** замкнуть петлю «мастер прислал JSON → semantic gate на ENUM-E → только потом persist» для world POJO и bundle rows.  
**Связь с HY-5:** generators уже читают `StrEnum` members; JV-0 закрывает **write path** (import / CRUD).  
**Не входит:** `engine/` DAG vocabulary; bulk-перенос barrel-only enum без import slice; character sheet (JV-6).

### Асимметрия (текущее)

| Путь | Статус |
|------|--------|
| `bundle.world` → `normalize_world()` → `resolve` | ✅ strict 422 |
| `connection_nodes`, races, locations, … → raw `dict` → dataclass | ❌ без ENUM-E gate |
| `wire.parse_enum` | ✅; вызывается из `resolve` на IMPORT (JV-0a) |
| `MaterialCategory` на `material_registry[]` | ✅ `parse_enum` → 422 `UNKNOWN_ENUM` (JV-0a) |

### Целевой поток

```
WRITE (strict)                         READ (permissive)
JSON → facade / bundle normalize       DB → worldRow → resolve (RUNTIME)
     → resolve + parse_enum (IMPORT)         → warn + canonical_* on gaps
     → 422 UNKNOWN_ENUM                      generators НЕ вызывают facade
     → persist
```

**Правила:**

- ENUM-E **reject** только на import (`ResolveMode.IMPORT`); runtime — warn + skip/default.
- Defaults и wire-контракт — **только** `dataModel`; не дублировать в `jsonValidation`.
- `generators/registries/wireEnums.py` — re-export barrel **для jsonValidation**; generators не импортируют (HY-5).
- N1-W registry keys (`system_material`, …) — REF-W (JV-2), не `parse_enum`.
- Preset keys в fixtures (`temperate`, `water`) — N1-W, не ENUM-E.

### Интеграция `parse_enum` (вариант A — рекомендуемый)

В `resolve._resolve_field`: если unwrapped annotation — `StrEnum`, на IMPORT:

1. `parse_enum(enum_cls, wire, field=field_name)`  
2. `WireEnumError` → `FieldPathError` с `code="UNKNOWN_ENUM"`, `schema_id`, `loc`  
3. На RUNTIME — прежний permissive путь (Pydantic / default)

**Альтернатива A+:** `BeforeValidator` на отдельных bundle import-row DTO — для секций без полного POJO на `worlds`.

Не делать в Slice 0: массовая замена всех `StrictOnWire[str]` → `StrictOnWire[Enum]` без закрытого контракта в `dataModel`.

### Формат 422 (ENUM-E)

```json
{
  "detail": [{
    "schema_id": "SCH-WORLD-MATERIAL",
    "loc": ["material_registry", 0, "material_category"],
    "code": "UNKNOWN_ENUM",
    "msg": "material_category: unknown wire value 'slid'; expected one of: solid, liquid, gas"
  }]
}
```

### Bundle row DTO (вариант A+ для секций вне `worlds`)

Модуль: `jsonValidation/bundle/` (новый). Hook в `WorldBundleService.import_bundle` **до** `import_list` / repo upsert.

**Эталон первого среза — `connection_nodes`:**

| wire key | Тип | Примечание |
|----------|-----|------------|
| `node_uid`, coords | `StrictOnWire[…]` / required | идентичность + геометрия |
| `node_type` | `StrictOnWire[ConnectionNodeType]` | wire key до **CONN-1** (`connection_node_type`) |
| `graph_level` | `StrictOnWire[GraphLevel]` | ENUM-E |
| `portal_type` | `PortalType \| None` | только при `node_type=portal` |

`connection_edges.connection_type` — **N1-W** (`REF-W-CONN`), не ENUM-E.

```python
# Целевой контракт (псевдокод)
class ConnectionNodeImportRow(BaseModel): ...
def normalize_connection_nodes(rows: list[dict], *, ctx) -> list[dict]: ...
```

### Очередь срезов JV-0

| Slice | Scope | PR | Критерий готовности |
|-------|--------|-----|---------------------|
| **JV-0a** | `resolve` + `parse_enum` hook | 1 | ✅ invalid `material_category` → 422 `UNKNOWN_ENUM` |
| **JV-0b** | `ConnectionNodeImportRow` (+ edge row) + `WorldBundleService` hook | 1 | invalid `node_type` в bundle → 422, rollback транзакции |
| **JV-0c** | Аудит world POJO: `StrictOnWire[Enum]` где enum уже в `dataModel` | по мере slice | `climate_pole_mode`, district `street_layout` — вместе с JV-4 / GV-3 |

**Порядок:** JV-0a → JV-0b → JV-0c (не блокирует GV-3 / JV-4, но enum-поля шаблонов лягут туда же).

### Соседние треки

| Трек | Отношение |
|------|-----------|
| HY-5 | generators P1 ✅; JV-0 — import-сторона |
| CONN-1 | rename `node_type` → `connection_node_type` — отдельный PR + recreate БД; JV-0b может стартовать со старым wire key |
| JV-2 | REF-W после normalize; совместно с N1-W полями на edges |
| JV-4 | barrier / district / building template import — больше ENUM-E |
| Engine | `npc_fields.node_category` → `NpcFieldCategory` — **post-JV-0** |
| Barrel-only enum | `BorderCategory`, `SeasonKey`, `SystemGender`, … — только при появлении import DTO |

### Out of scope JV-0

- Возврат v0.1 orchestrator / `validators/*.py`
- Запуск backend агентом (smoke — мастер)
- Character import (JV-6), races (JV-8)
- Preemptive migration всех `wireEnums` без consumer на import

---

## Impl queue (JV)

| ID | Scope | P | Статус |
|----|-------|---|--------|
| JV-0 | ENUM-E import gate (§ JV-0) | P1 | ◐ JV-0a ✅ |
| JV-0a | `resolve` hook + `UNKNOWN_ENUM` 422 | P1 | ✅ |
| JV-0b | bundle DTO `connection_nodes` / edges + `WorldBundleService` | P1 | ⬜ |
| JV-0c | world POJO `StrictOnWire[Enum]` audit (с JV-4/GV-3) | P2 | ⬜ |
| JV-1 | POJO resolve + facade world slice | P1 | ✅ v1 |
| JV-1b | `worldSlices.py` + `SCHEMA_ID` в 422 | P1 | ✅ |
| JV-2 | REF-W index после normalize | P1 | ✅ MVP |
| JV-3 | peak explicit on import; hydrology import rules | P1 | ⬜ |
| JV-4 | building/district/barrier template import | P2 | ⬜ |
| JV-5 | N1-S normalize (`stat_schema` map→array) | P2 | ⬜ |
| JV-6 | character validation sibling package | P3 | ⬜ |
| JV-7 | remove runtime SCH-RUNTIME-* hardcodes | P2 | ⬜ |
| JV-8 | races import (SCH-RACE-*) | P3 | ⬜ |
| GV-* | generators → worldRow (см. § Generators — миграция на worldRow) | P1–P3 | ◐ |

**Порядок (архитектура перед фичами):** ~~GV-1~~ ~~GV-2~~ ~~JV-1b~~ ~~JV-2 MVP~~ → **JV-0a → JV-0b** → GV-3… → JV-8.

---

## Legacy (transitional)

| ID | Поведение |
|----|-----------|
| SCH-RUNTIME-HYDROLOGY | `canonical_empty()` + warn если `hydrology` пусто |
| SCH-RUNTIME-CLIMATE | peak NULL → `resolve_peak_bounds` canonical |
| `precipitation.py` fallback chain | warn_once; target: explicit DB after import |
| `legacy_standalone_water_material()` | last-resort `"water"` |

Целевое ([`tz_climate.md`](./tz_climate.md) v3): defaults материализованы в БД через import normalize; generate только читает.

---

## Changelog

| Версия | Дата | Изменение |
|--------|------|-----------|
| 0.1 | 2026-06 | Field Contract Registry, orchestrator, `worldData/jsonValidation/` |
| — | 2026-07 | Удаление v0.1 code (`dc6b171`); пауза simple CRUD |
| **1.0** | 2026-07 | POJO-first `application/jsonValidation/`: resolve, facade, worldRow; wire projection B; документ v1 |
| **1.1** | 2026-07 | § Generators — миграция на worldRow (GV): статус, очередь GV-1…7; resolve log; SCH rows barrier/city/district/terrain scalars |
| **1.1.1** | 2026-07 | GV-1: climate generators на `climate_scalars(world)` (poleResolve, precipitation, tierResolve, climateRuntimeAssembler) |
| **1.1.2** | 2026-07 | GV-2: `terrain_scalars(world)` + wire projection; worldMapSettings, columnFillPass, climateGeneratorService (lapse) |
| **1.1.3** | 2026-07 | JV-1b: `worldSlices.py` (`WORLD_SLICES`), `SCHEMA_ID` на POJO, `schema_id`+`code` в 422; facade через slice registry |
| **1.1.4** | 2026-07 | JV-2 MVP: `jsonValidation/index/` — `WorldRegistryIndex`, REF-W на import (`precipitation_liquid`, climate zone, hydrology shore, material tier) |
| **1.2.1** | 2026-07 | JV-0a: `resolve._resolve_str_enum` + unwrap `StrictOnWire[T]`; 422 `UNKNOWN_ENUM` (`material_category` smoke) |
