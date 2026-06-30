---
name: tz-races
description: "ТЗ race-контракта — prototype inheritance, appearance stack, gender blobs, refs N1-G/N1-W/N1-S"
metadata:
  node_type: memory
  type: project
---

# Race contract — Technical Specification

**Версия документа: 0.1** (2026-06)

## Назначение

Race contract — **отдельная подсистема**, не N1-W vocabulary на `worlds`.

| | N1-W (`material_registry` on `worlds`) | **Race contract** |
|---|---|---|
| Storage | JSON blob на `worlds` | **таблица `races`** (bundle section `races[]`) |
| ID | `system_material`, … | **`race_uid`** (PK) |
| Display | inline `display_*` | **`display_race`** |
| Роль | vocabulary мира | фильтры appearance + simulation flags + merge по полу |

**Character bind:** `character_sheet.system_race` → **`races.race_uid`** (slug в fixtures; TZ: hash `display_race + created_at`).  
`display_race` на персонаже — denormalized UI; **не** ключ контракта.

| Документ | Роль |
|---|---|
| **Этот ТЗ** | домен: контракт, merge, appearance stack, validation rules |
| [`tz_json_validation.md`](./tz_json_validation.md) | **SCH-RACE-*** field contracts, JV-8 import policy |
| [`tz_json_import.md`](./tz_json_import.md) | HTTP import, merge-demo (упрощённый пример) |
| [`project_data_storage_tz.md`](./project_data_storage_tz.md) | DDL, character sheet columns, `registry_dependencies`, `schema_version` |

**Статус impl:** ORM ✅ · import struct-only ◐ · merge / validation / runtime refs ⬜

**Код:** [`Race`](../backend/app/db/models/race.py), [`RaceService`](../backend/app/application/worldData/raceService.py)

---

## L1 / L2 / L3 — таблица `races`

| Уровень | Значение |
|---|---|
| **L1** | SQLite таблица **`races`** (не колонка на `worlds`) |
| **L2** | одна строка = один race; **5 JSON blobs** + scalar meta |
| **L3** | поля **внутри** каждого blob |

```
races (SQLite)
  ├── race_uid, world_uid, display_race, created_at   ← L1 scalars
  ├── race_traits   ← L2 blob (уровень расы)
  ├── male          ← L2 blob | null  (= gender недоступен)
  ├── female
  ├── asexual
  └── both
```

**ENUM-E E-22 `SystemGender`:** `male`, `female`, `asexual`, `both` — имена **колонок** L2 на `races` и значение `character.system_gender` при merge.

---

## Appearance stack (три слоя правил)

```text
1. race contract     ← races (+ merge gender blob)
2. social_status       ← N1-G seed; character.system_social_status (не в races)
3. character values  ← system_appearance, stats, …
```

**system_gender** — immutable keys: `male`, `female`, `asexual`, `both`.  
При изменении `system_gender` → обновляются display-таблицы (отдельный механизм).

**social_status** — N1-G таблица; минимум 2 записи; `social_status_weight` для генерации. См. [`project_data_storage_tz.md`](./project_data_storage_tz.md) §«Таблица social_status».

---

## L3 — `race_traits` (уровень расы, не пол)

Simulation / LLM-контекст **всей** расы:

```json
{
  "terrain_access": ["liquid"],
  "tag_refs": ["tag_aquatic", "tag_cold_blooded"],
  "sleep_requirement_ticks": 8
}
```

| L3 field | Семантика |
|---|---|
| `terrain_access` | string[] — расовые способности передвижения по умолчанию для всех полов; keys → terrain **category** |
| `tag_refs` | string[] — теги из `tag_registry`; LLM получает как расовый контекст |
| `sleep_requirement_ticks` | int — тиков сна за цикл; дефолт 8 at runtime |

**Не смешивать** с appearance trees в gender blobs.

**Фолбек `terrain_access`:**

```
effective_terrain_access = gender.terrain_access ?? race_traits.terrain_access ?? []
```

Gender-объект может опционально переопределить для конкретного пола.

**Агрегация на персонаже** (pathfinding): union с perks и equipment — [`project_data_storage_tz.md`](./project_data_storage_tz.md) §«Проходимость и доступ к местности»; [`tz_locations.md`](./tz_locations.md) `character_terrain_access`.

---

## L3 — gender blob (`male` / `female` / …)

**Доступность гендера:** колонка `null` или отсутствует → гендер **недоступен** для расы.

Все поля **опциональны**. Полный пример структуры:

```json
{
  "lifespan": [
    { "from": 0,  "to": 15,  "age_type": "child" },
    { "from": 16, "to": 120, "age_type": "adult" }
  ],
  "height_range": { "min": 150, "max": 190, "system_measurement_unit": "centimeters" },
  "weight_range": { "min": 50000, "max": 100000, "system_measurement_unit": "grams" },
  "skin_types": {
    "skin":  { "colours": ["ivory", "olive"],   "textures": ["smooth", "aged"] },
    "scale": { "colours": ["emerald"],           "textures": ["iridescent", "scaly"] }
  },
  "hair_types": {
    "straight": { "shapes": ["short", "long pony tail"], "colours": ["black", "blonde"] },
    "horns":    { "shapes": ["curved", "straight_up"],   "colours": ["ivory", "obsidian"] }
  },
  "beard_types": { "human_beard": { "shapes": ["full", "goatee"], "colours": ["black", "brown"] } },
  "brows_types": { "human_brows": { "shapes": ["thin", "thick"], "colours": ["black", "brown"] } },
  "eye_options": {
    "eye_counts": [2],
    "eye_placements": ["forward"],
    "eye_types": {
      "human": {
        "roundness": ["almond", "round"],
        "iris_types": ["normal"],
        "lid_types": ["single", "double"],
        "pupil_types": ["round"],
        "iris_colours": ["amber", "blue"],
        "pupil_colours": ["black"]
      }
    }
  },
  "mouth_options": { "mouth_types": { "human_mouth": { "lip_shapes": ["thin"], "teeth_types": ["human"] } } },
  "nose_options": { "nose_types": { "human": { "shapes": ["straight", "flat"] } } },
  "ear_options": { "ear_types": { "pointed": { "shapes": ["long", "medium"] } } },
  "breast_options": { "breast_types": { "human": { "shapes": ["natural", "round"] } } },
  "voice_options": { "pitches": ["deep", "medium"], "timbres": ["rough", "smooth"] },
  "muscle_stat": "Str",
  "constitution_stat": "Con",
  "muscle_table": "insectoid",
  "constitution_table": "insectoid",
  "body_schema": "humanoid",
  "body_hair_options": {
    "chest": { "hair_types": ["straight", "curly"], "colours": ["black", "brown"] },
    "arms":  { "hair_types": ["straight"] }
  },
  "applicable_fields": {
    "beard": true, "waist": false, "hips": false, "breast": false,
    "body_hair": true, "mouth": true, "nose": true, "ear": true, "genitals": false
  },
  "terrain_access": ["liquid"]
}
```

### Правила полей

| Rule | Policy |
|---|---|
| Поле отсутствует (не-базовое) | фильтрация не работает, доступны все значения из мировых таблиц |
| `applicable_fields` absent | все не-базовые поля **разрешены** (permissive) |
| `applicable_fields.X = false` | поле выключено (e.g. `mouth=false` → voice ignored) |
| Базовые поля | всегда присутствуют: `skin`, `height`, `weight`, `age`, `muscle`, `constitution` — **не** под `applicable_fields` |

### Базовые поля — цепочка фолбеков

Применяется к: `lifespan`, `skin_types`, `height_range`, `weight_range`, `muscle_stat`, `constitution_stat`

1. Текущий гендерный объект
2. Любой другой заполненный гендерный объект этой расы
3. **Human preset** — seed при создании мира (не хардкод в движке)

**Фолбек шаг 3 — world seed data:** при создании нового мира генерируется дефолтная конфигурация (`colour_registry`, раса Human с диапазонами). Движок не знает о «людях» — только о том, что есть в БД мира.

### body_schema и body_hair

Race contract ссылается на `worlds.body_schema_registry` по `schema_id` и опционально ограничивает зоны в `body_hair_options`. Отсутствие зоны → волос на зоне нет для расы.

Полная схема реестра — [`project_data_storage_tz.md`](./project_data_storage_tz.md) §«Реестр body_schema_registry».  
`character.system_body_hair` — ключи = зоны/части из body_schema.

### muscle / constitution tables

Мир хранит `muscle_tables` / `constitution_tables`. Race contract ссылается по `table_id`. Нет ссылки → таблица с `table_id: "default"`.

---

## Merge at character init (runtime)

Prototype inheritance:

```text
race_traits   ← базовый уровень
├── male       ← override / extend
├── female
├── asexual
└── both
```

```
effective = race_traits ⊕ race[system_gender]
```

- Гендерные значения **побеждают** при конфликте scalar/object keys
- Списки: стратегия replace vs extend — TBD character service ([`tz_json_import.md`](./tz_json_import.md) § merge-demo)
- Validator **import не merge** — только целостность каждого blob (JV-8)
- Character bind + appearance vs effective contract — JV-6

---

## Ref graph (одна строка `races`)

| Layer | Race contract refs |
|---|---|
| **N1-G seed** | `hair_type`, `skin_type`, `eye_*`, `mouth_*`, `age_type`, `voice_*`, … (29 tables via `POST /api/seed/import`) |
| **N1-W world** | `colour_registry`, `texture_registry`, `body_schema_registry`, `muscle_tables`, `constitution_tables`, `tag_registry` |
| **N1-S** | stat aliases (`muscle_stat: "Str"`) |
| **N1-G (character)** | `social_status` — layer 2, not in race row |

**colour / texture:** race contract хранит только `system_*` keys; `display_*` резолвится при чтении ([`project_data_storage_tz.md`](./project_data_storage_tz.md) § colour/texture rules).

### Validation rules (domain)

- `muscle_stat` / `constitution_stat` — alias ∈ AliasRegistry (N1-S)
- `hair_types` / `skin_types` / … keys — ref → соответствующие **N1-G seed** tables; nested lists ⊆ world registries where applicable
- `muscle_table` / `constitution_table` — `table_id` ∈ N1-W muscle/constitution tables
- `body_schema` — `schema_id` ∈ **body_schema_registry**
- `lifespan[].age_type` — ref → **N1-G** `age_type`
- `lifespan` ranges — no gaps, no overlap
- `height_range` / `weight_range` — `system_measurement_unit` обязателен при наличии диапазона

Детали wire/import policy — [`tz_json_validation.md`](./tz_json_validation.md) **SCH-RACE-***.

---

## registry_dependencies и schema_version

При save race → reindex keys (`entity_type=race`, `entity_id=race_uid`). Типы: `colour`, `texture`, `body_schema`, `hair_type`, … — [`project_data_storage_tz.md`](./project_data_storage_tz.md) §«Таблица registry_dependencies».

`worlds.schema_version` hash включает **serialized race contracts** — storage TZ §«Schema versioning».

---

## Wire dialects (fixture drift)

| Source | `race_traits` example | Status |
|---|---|---|
| [`fixtures/world_template.json`](../fixtures/world_template.json) | `{ "adaptive": true }` | ad-hoc stub |
| [`fixtures/world_test.json`](../fixtures/world_test.json) | `{ "night_vision": true, "lifespan_years": 80 }` | **не** этот ТЗ |
| **Этот ТЗ** | `terrain_access`, `tag_refs`, `sleep_requirement_ticks` | **target L3 race_traits** |

Gender blobs в fixtures **отсутствуют**; ORM columns exist.

Merge-demo в [`tz_json_import.md`](./tz_json_import.md) (`lifespan_years`, `strength_bonus`) — **упрощённый пример**, не appearance-контракт.

---

## Seed tables (N1-G) — правило для рас

Доступные значения для расы задаёт race-контракт ключами в `hair_types`, `skin_types`, `beard_types`, `brows_types`, …  
Полные таблицы seed — [`project_data_storage_tz.md`](./project_data_storage_tz.md) §«Системные таблицы» (hair_type, skin_type, …).

---

## Impl backlog

| ID | Задача |
|---|---|
| JV-8 | import validation: blob shape + ref integrity |
| JV-6 | character `system_race` ∈ races; appearance vs effective contract |
| — | merge service at character init |
| — | validate-on-save race (сейчас ошибка только при load) |

---

## Changelog

| Версия | Дата | Изменение |
|---|---|---|
| **0.1** | 2026-06 | Выделено из `project_data_storage_tz.md` §«Таблица races» + `tz_json_validation.md` §0.2 |
