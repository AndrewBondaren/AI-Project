# dataModel — расхождения POJO (дубли SoT)

**Тип:** инженерное ТЗ / living registry. Не продуктовый алгоритм.  
**Scope:** `backend/app/dataModel/` + потребители, которые дублируют поля/defaults POJO (generators, `db/models`, debug routes).  
**Правило:** [`.cursor/rules/dataModel-no-hardcode.mdc`](../.cursor/rules/dataModel-no-hardcode.mdc).  
**Срез:** 2026-09-03 (~223 файла, ~90 BaseModel/RootModel).  
**Связанные:** [`tz_json_validation.md`](./tz_json_validation.md), [`tz_generator_technical_debt.md`](./tz_generator_technical_debt.md) (HY-5 wire enum), [`tz_structure_connections.md`](./tz_structure_connections.md) §3.7.

Новый smell → новый ID; resolved не удалять.

| Поле | Значение |
|---|---|
| **ID** | `POJO-D-*` |
| **Severity** | `critical` / `medium` / `minor` / `info` |
| **Status** | `open` / `partial` / `resolved` |

---

## Критичные

### POJO-D-1 — двойной SoT `road_tier_bonus` / `road_tier_durability`

**Severity:** critical · **Status:** **resolved** 2026-09-03

**Было:** три источника одних полей.

| Источник | Значение |
|---|---|
| `EconomyTierEntry` Field default | `1.0` / `1.0` |
| `_ROAD_DEFAULTS` в registry | TZ §3.7 per-tier |
| `canonical_defaults()` | tiers **без** road-полей → срабатывал Field `1.0` |
| `canonical_engine()` | единственный путь с TZ §3.7 |

Runtime `economic_tiers(world)` шёл через `canonical_defaults` / world JSON. Fixture без `road_tier_*` получал нейтральные `1.0`; `canonical_engine()` не применялся, если строка тира уже была в реестре.

**Сделано:**

- SoT-таблица `ROAD_TIER_DEFAULTS` + `road_modifiers_for()` на `EconomyTierEntry`
- omitted wire → per-tier TZ (`IgnoreOnWire` + `model_validator`, чтобы resolve не штамповал `1.0` до validate)
- `canonical_defaults()` материализует TZ; `canonical_engine()` = `canonical_defaults()`
- Field `1.0` остаётся нейтралью: unknown tier / `fallback()` / TZ «material=null»
- fixtures `world_template` / `world_test*` / `world_terrain_test` — явные `road_tier_*`

---

### POJO-D-2 — литералы `"stone"` / `"wood"` vs `ConstructionMaterialDefaults`

**Severity:** critical · **Status:** **resolved** 2026-09-03

**SoT:** `constructionMaterialDefaults.py` — `DEFAULT_WALL_MATERIAL` / `DEFAULT_FLOOR_MATERIAL`.

**Было (consumers):** `structureGeneratorService`, `foundationBuilder`, `roofBuilder`, `structureAreaAssembler`, `buildingCache`, `barrier/material.py`, `planner/barriers.py`, `api/routes/debug.py`.

**Сделано:** fallback и probe-defaults читают POJO-константы. Не тронуты: ключи реестра (`system_material="stone"`), `pick_from=["stone"]` в barrier templates, `stone_fence` (тип шаблона, не материал).

Часть generators уже была на POJO: `materialResolver`, `stampApproach`, `streets`, `dominantMaterial`.

---

## Средние

### POJO-D-3 — словарь `connection_type` в нескольких модулях

**Severity:** medium · **Status:** **resolved** 2026-09-03

**Сделано:** `WorldConnectionTypeRegistry.keys()` / `require` / `require_engine`. Именные подмножества `ROAD_MASK_CONNECTION_TYPE_KEYS`, `LANE_BASED_CONNECTION_TYPE_KEYS`, `HYDROLOGY_CONNECTION_TYPE_KEYS`. Width/road settings резолвят ключи через `require_engine`; road-mask — `road_mask_connection_types()`. Numeric width/settings **не** слиты в `ConnectionTypeEntry`.

Wire-имена полей (`DistrictConnection.connection_type` vs `system_connection_type`) — контракт JSON, не merge.

---

### POJO-D-4 — fixture / engine tuples без mechanical derive

**Severity:** medium · **Status:** **resolved** 2026-09-03

**Сделано:** `dataModel/registryEngine.py` → `engine_rows(fixture, extra, key=, drop=)`.

| Registry | Derive |
|---|---|
| connection types | fixture + alley/yard_path |
| materials | fixture + engine delta, drop sand/ice |
| terrain | уже было: outdoor + interior + settlement |
| location types | engine SoT; fixture = `fixture_identity()` |

---

### POJO-D-5 — литерал `32` в разных семантиках

**Severity:** medium · **Status:** **resolved** 2026-09-03

| Константа | Смысл |
|---|---|
| `WORLD_MAP_CELLS_PER_TILE` | L0 mask side; manifest default ссылается сюда |
| `TERRAIN_CHUNK_COLUMNS_DEFAULT` | persist chunk; POJO Field + `db/models/world.py` |

---

### POJO-D-6 — `WorldTerrainScalars.resolved_*` inline fallback

**Severity:** medium · **Status:** **resolved** 2026-09-03

`CANONICAL_Z_MIN` / `CANONICAL_Z_MAX` / `CANONICAL_ELEVATION_LAPSE_RATE` → только `canonical_defaults()`. `resolved_*` читает POJO; `None` там — `RuntimeError`, не второй литерал.

---

### POJO-D-7 — `HydrologyConnectionType` vs connection registry

**Severity:** medium · **Status:** **resolved** 2026-09-03

Enum values = `WorldConnectionTypeRegistry.require_engine(...)`. Состав членов = `HYDROLOGY_CONNECTION_TYPE_KEYS` (assert на импорте).

---

### POJO-D-8 — `map_cell_size_m = 1000` / `codec_version = 1`

**Severity:** medium · **Status:** **resolved** 2026-09-03

- `MAP_CELL_SIZE_M_DEFAULT` — manifest + `World.map_cell_size_m`
- `PACK_CODEC_VERSION` — `PackBakeDefaults` + manifest

---

### POJO-D-9 — copy-paste legacy climate validators

**Severity:** medium · **Status:** **resolved** 2026-09-03

`promote_legacy_climate_status` + `ClimateBakeStatusMixin`. `ClimateFieldWire` (`legacy_key=tier`); `TileManifestEntry` / `LocationTerrainEntry` (`climate_tier`).

---

## Minor / info (open, не баг)

### POJO-D-10 — `ReliefRoleCase` flat wire ↔ `ReliefGradeKnobs`

**Severity:** info · **Status:** open (осознанный wire flatten)

Один набор knobs в `reliefGradeKnobs.py`, flat Mode A в `reliefRoleCase.py` / `reliefTemplate.py`. Композиция: `ReliefRoleCase.mode_a_grade_knobs()`. Не объединять без смены wire.

---

### POJO-D-11 — `PackBakeMode` vs `PackTilePlanScope`

**Severity:** minor · **Status:** open

`Literal["light", "full"]` повторён; `PackTilePlanScope` — подмножество `PackBakeMode`. Общий alias.

---

### POJO-D-12 — `WildernessRefineStatus` объявлен в manifest

**Severity:** minor · **Status:** open

Тип живёт в `worldPackManifest.py`; `wildernessRefineStatus.py` re-import. Перенести тип в модуль статуса.

---

### POJO-D-13 — `from_wire()` boilerplate (~16 enums)

**Severity:** minor · **Status:** open

Одинаковый шаблон. Кандидат: generic helper. Не дублирование доменных значений.

---

### POJO-D-14 — `RaceTemplateOutline` / `PerkTemplateOutline` identity fill

**Severity:** minor · **Status:** open

Одинаковый `template_uid` / `system_name` / uuid. Optional `TemplateIdentityMixin`.

---

### POJO-D-15 — `DEFAULT_CONNECTION_TYPE = "road"`

**Severity:** info · **Status:** open

Единственный SoT district street default в `districtConnection.py`. Литерал не ссылается на registry key helper — не баг, слабая связь.

---

## Не расхождение

| Что | Почему |
|---|---|
| `ClimateZone` enum → `ClimateZoneEntry` registry | derive, не копия |
| `SceneVolumePolicy` vs `TerritoryVolumePolicy` | делегация `scene_xy_radius` |
| `HydrologyLakesPolicy` / `SeasPolicy` | наследуют `MaskCategoryPolicy` |
| Climate module constants → enums | один upstream (`worldClimateScalars`) |
| `db/models/world.py` scalar columns `None` | defaults в POJO resolve |
| `worldScalarWire` / `*_WIRE_KEYS` из `model_fields` | нет параллельных frozenset в jsonValidation |
| Engine DAG nodes | почти без domain literals (gate: не трогать) |

---

## Очередь (minor)

| P | ID | Действие |
|---|---|---|
| P3 | POJO-D-10…D-15 | wire flatten / aliases / mixins — не баги SoT |
