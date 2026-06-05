---
name: project-data-storage-tz
description: "ТЗ по хранению данных — схема сущностей, статы, скиллы, формулы, инвентарь, лор, миграции"
metadata: 
  node_type: memory
  type: project
  originSessionId: 633eddca-8d16-4119-94ab-ef548d071851
---

## Видение продукта
Не просто RPG игра — **платформа для симуляции AI RPG**. Пользователь определяет свою систему правил (статы, формулы, действия), AI выступает мастером по этим правилам. Аналог Foundry VTT но с AI-мастером и кастомным движком механик.

## Хранилище
SQLite (игровые данные) + config.toml (настройки приложения).

SQLite настройки: WAL-режим (`PRAGMA journal_mode=WAL`), async driver (`aiosqlite`).

### Архитектура доступа к данным — Repository pattern

Весь доступ к БД только через репозитории. Сервисы и движок не знают о конкретной БД.

```
Services / Engine
    │
    ▼
Repository interface        (PlayerRepository, WorldRepository, MessageRepository, ...)
    │
    ▼
SqlitePlayerRepository      (сейчас)
PostgreSQLPlayerRepository  (будущее — мультиплеер)
```

- Прямые SQL-запросы только внутри конкретной реализации репозитория
- Смена БД = новая реализация интерфейса, код сервисов не трогаем
- Закладывается сейчас, PostgreSQL-реализация — когда понадобится мультиплеер

---

## Сущности

### messages
```sql
messages (message_id, player_id, world_id, player_input, llm_output, local_time)
```
Плоская таблица, без сложных связей.

### character_sheet (общая база — игроки и NPC)
Хранит прямые значения. Импорт/экспорт независимо от мира.

Паттерн полей: каждое поле имеет пару `system_*` (для движка и LLM) и `display_*` (для UI).

**Системные флаги (engine-only, без display-пары):**
- `system_alive` — `true` | `false`; при смерти движок ставит `false`; персонаж остаётся в БД; история, отношения и ссылки сохраняются
- `system_conscious` — `true` | `false`; только если `faint_check_formula` задана; `false` = без сознания (faint); при смерти принудительно `false`

**Идентификация:**
- `system_uid` / `display_name`
- `system_class` / `display_class`
- `system_race` / `display_race`
- `system_gender` / `display_gender` — пол персонажа
- `system_nickname` / `display_nickname` — генерируется по правилу nickname (TODO)
- `system_reputation` / `display_reputation` — генерируется по правилу reputation (TODO)
- `system_social_status` / `display_social_status` — статус из таблицы `social_status`; на карточке отображается только `display_social_status`
- `system_age_type` / `display_age_type` — возрастная группа из таблицы `age_type`; на карточке только `display_age_type`; у каждой расы свой lifespan
- `system_location` / `display_location` — текущая локация
- `system_barrier` / `display_barrier` — барьер/защита; если `display_barrier` пусто — механика отключена
- `system_title` / `display_title` — nullable; официальный титул/звание ("Рыцарь", "Доктор", "Изгнанник"); отличается от `system_nickname` (неформальное); применимо ко всем персонажам

**TODO — механика движка (все персонажи):**
- `wanted_status` — статус разыскиваемого; зависит от фракций (кем разыскивается, уровень); отдельная механика, отложено до системы фракций

**Механика (complex objects):**
- `system_stats` / `display_stats` — статы
- `system_mastery` / `display_mastery` — скиллы/мастерство
- `system_inventory` / `display_inventory` — инвентарь; содержит:
  - `equipped` — верхнеуровневый объект экипированных предметов по слотам (слоты декларирует мир):
    ```json
    {
      "equipped": {
        "weapon":    [{ "item_uid": "..." }, { "item_uid": "..." }],
        "head":      [{ "item_uid": "..." }],
        "gloves":    [{ "item_uid": "..." }],
        "trousers":  [{ "item_uid": "..." }],
        "boots":     [{ "item_uid": "..." }],
        "accessory": [{ "item_uid": "..." }, { "item_uid": "..." }]
      }
    }
    ```
  - `general` — список неэкипированных предметов
  - `system_money` / `display_money` — первая валюта; дополнительные: `system_money_1` / `display_money_1`, ... n+1 паттерн; определяются миром; будущее: система курсов обмена
- `system_perks` / `display_perks` — перки (два массива: общие по uid-ссылке + уникальные inline)
- `system_state` / `display_state` — **механические** статусные эффекты; хранятся в `character_states` (нормализовано)

**Нарратив и история:**
- `system_relations` — отражается при подзагрузке из `world_relations` (не хранится в character_sheet)
- `system_history` — вынесено в таблицу `character_history` (см. Нормализация)
- `system_state_narrative` — вынесено в таблицу `character_narrative_states` (см. Нормализация)
- `system_description` / `display_description` → **object narrative** (см. ниже)

**Object narrative** (вложенный объект в description):
- `system_character` / `display_character` — характер; вложенный объект:
  - `system_traits` — engine-only JSON; не отображается игроку; **источник правды** для черт характера; display_* поля генерирует LLM на основе traits:
    ```json
    [
      { "system_trait": "brave",   "intensity": 0.4, "intensity_base": 0.8 },
      { "system_trait": "fearful", "intensity": 0.6, "intensity_base": 0.0 }
    ]
    ```
    `intensity_base` — исходное значение при создании, никогда не меняется; `intensity` — текущее значение; дрейф = `intensity_base - intensity`
  - `system_general` / `display_general`
  - `system_pros` / `display_pros`
  - `system_cons` / `display_cons`
  - `system_likes` / `display_likes`
  - `system_dislikes` / `display_dislikes`
  - `system_habits` / `display_habits`
  - Расширяемо: `system_character_1` / `display_character_1`, n+1
- `system_appearance` / `display_appearance` — внешность; шаблон зависит от `system_gender`:

  **Правило вложенных объектов (для пользовательских object-типов):** каждый object-тип имеет свои поля по паттерну `system_*/display_*` + n+1 для пользовательских полей. Вложенность строго один уровень — пользовательский объект не может содержать другой объект. Engine-internal поля (например `system_traits`) этим правилом не ограничены.

  ```json
  { "system_hair": { "system_color": "black", "display_color": "Чёрный", "system_hair_1": "...", "display_hair_1": "..." } }
  ```

  **Паттерн измеримых полей:**
  Хранится число + явный тип единицы (всегда канонический). Конвертация только при чтении по `world.measurement_system`:
  ```json
  { "system_measurement": 65, "system_measurement_unit": "centimeters", "display_measurement": "65 cm" }
  ```
  - `system_measurement_unit` — константа при записи ("centimeters" / "grams"); защита от рассинхрона
  - При чтении: если `measurement_system = "imperial"` → конвертируем для display и LLM контекста
  - Данные в базе никогда не меняются при смене настройки мира

  **Канонические единицы хранения:**
  - Длина и объёмы (height, waist, hips, breast, hair length, beard): centimeters
  - Вес тела: grams → display в kilograms / pounds

  **Общие поля (базовые — нельзя удалить):**
  - `system_height` / `display_height` — int centimeters
  - `system_age` / `display_age` — int
  - `system_weight` / `display_weight` — int grams
  - `system_hair` / `display_hair` — object:
    - `system_length` / `display_length` — int (см/дюймы, автоконвертация); если 0 → волос нет → `system_hair_shape` = bold
    - `system_colour` / `display_colour`
    - `system_hair_shape` / `display_hair_shape` — object:
      - `system_hair_type` / `display_hair_type` — из таблицы `hair_type`; каждый тип имеет свои shapes
      - `system_hair_shape` / `display_hair_shape` — форма
      - `system_hair_description` / `display_hair_description` — заполняет LLM по всем полям; опционально
    - `system_hair_1` / `display_hair_1` — n+1
  - `system_brows` / `display_brows` — object (базовые поля нельзя удалить):
    - `system_brows_type` / `display_brows_type` — из таблицы `brows_type`; управляется race-контрактом
    - `system_brows_shape` / `display_brows_shape` — из таблицы `brows_shape`; доступные формы задаёт race-контракт
    - `system_brows_colour` / `display_brows_colour` — ключ из `colour_registry`; по умолчанию = `system_hair.system_colour`; можно переопределить
  - `system_skin` / `display_skin` — object (базовые поля нельзя удалить):
    - `system_skin_type` / `display_skin_type` — тип покрытия тела из таблицы `skin_type`; управляется race-контрактом
    - `system_colour` / `display_colour` — цвет покрытия; допустимые значения из race-контракта
    - `system_texture` / `display_texture` — зависит от расы и `age_type`
    - `system_skin_1` / `display_skin_1` — n+1
  - `system_eye` / `display_eye` — object:
    - `system_eye_count` / `display_eye_count` — int; дефолт 2; допустимые значения задаёт race contract
    - `system_eye_placement` / `display_eye_placement` — из таблицы `eye_placement`; дефолт `forward`
    - `system_eye_type` / `display_eye_type` — главный тип из таблицы `eye_type`; если `none` → глаз отсутствует, остальные поля игнорируются
    - `system_eye_roundness` / `display_eye_roundness` — из таблицы `eye_roundness`
    - `system_eye_iris_type` / `display_eye_iris_type` — тип радужки из таблицы `eye_iris_type`
    - `system_eye_lid_type` / `display_eye_lid_type` — тип век из таблицы `eye_lid_type`
    - `system_eye_pupil_type` / `display_eye_pupil_type` — тип зрачка из таблицы `eye_pupil_type`
    - `system_eye_iris_colour` / `display_eye_iris_colour` — ключ из `colour_registry`
    - `system_eye_pupil_colour` / `display_eye_pupil_colour` — ключ из `colour_registry`
  - `system_muscle` / `display_muscle` — из таблицы `muscle`; управляется race; принимает одну характеристику (alias стата) → коэффициент = `char_stat / world_max_stat`, если выше макс → 100% (удвоение weight); эффективный weight = `base_weight * (1 + coeff)`
  - `system_constitution` / `display_constitution` — аналогичное правило с коэффициентом стата
  - `system_body_type_description` / `display_body_type_description` — генерирует LLM на основе height, constitution, muscle; опционально
  - `system_body_hair` / `display_body_hair` — object; ключи = зоны/части из `body_schema_registry` (определяются race contract); если зона отсутствует → волос нет; каждая зона: `{ system_hair_type, system_density, system_colour }`
  - `system_beard` / `display_beard` — object; применимость определяется race-контрактом; структура по аналогии с `system_hair`:
    - `system_length` / `display_length` — int (см/дюймы, автоконвертация); если 0 → бороды нет → `system_beard_shape` = none
    - `system_colour` / `display_colour` — по умолчанию берётся из `system_hair.system_colour`; можно переопределить
    - `system_beard_shape` / `display_beard_shape` — object (по аналогии с `hair_shape`):
      - `system_beard_type` / `display_beard_type` — из таблицы `beard_type`
      - `system_beard_shape` / `display_beard_shape` — форма из таблицы `beard_shape`
      - `system_beard_description` / `display_beard_description` — LLM опционально
    - `system_beard_1` / `display_beard_1` — n+1
  - `system_waist` / `display_waist` — object; применимость определяется race-контрактом:
    - `system_measurement` / `display_measurement` — int cm (58–105); `system_measurement_unit`
  - `system_hips` / `display_hips` — object; применимость определяется race-контрактом:
    - `system_measurement` / `display_measurement` — int cm (85–120); `system_measurement_unit`
  - `system_breast` / `display_breast` — object; применимость определяется race-контрактом:
    - `system_breast_type` / `display_breast_type` — из таблицы `breast_type`; управляется race-контрактом
    - `system_breast_shape` / `display_breast_shape` — из таблицы `breast_shape`
    - `system_measurement` / `display_measurement` — int cm; `system_measurement_unit`
  - `system_mouth` / `display_mouth` — object:
    - `system_mouth_type` / `display_mouth_type` — из таблицы `mouth_type`; управляется race-контрактом
    - `system_lip_shape` / `display_lip_shape` — из таблицы `lip_shape`
    - `system_lip_colour` / `display_lip_colour` — ключ из `colour_registry`
    - `system_teeth_type` / `display_teeth_type` — из таблицы `teeth_type`
    - `system_jaw_shape` / `display_jaw_shape` — из таблицы `jaw_shape`
  - `system_nose` / `display_nose` — object:
    - `system_nose_type` / `display_nose_type` — из таблицы `nose_type`; управляется race-контрактом
    - `system_nose_shape` / `display_nose_shape` — из таблицы `nose_shape`
    - `system_nose_colour` / `display_nose_colour` — ключ из `colour_registry`; опционально
  - `system_ear` / `display_ear` — object:
    - `system_ear_type` / `display_ear_type` — из таблицы `ear_type`; управляется race-контрактом
    - `system_ear_shape` / `display_ear_shape` — из таблицы `ear_shape`
    - `system_ear_colour` / `display_ear_colour` — ключ из `colour_registry`; опционально
  - `system_genitals` / `display_genitals` — object; применимость определяется race-контрактом:
    - `system_genitals_type` / `display_genitals_type` — из таблицы `genitals_type`
    - `system_genitals_1` / `display_genitals_1` — n+1; игрок расширяет сам
  - `system_voice` / `display_voice` — object; зависит от наличия рта:
    - `system_voice_pitch` / `display_voice_pitch` — из таблицы `voice_pitch`
    - `system_voice_timbre` / `display_voice_timbre` — из таблицы `voice_timbre`
    - `system_voice_1` / `display_voice_1` — n+1
    - **Engine-правило:** `system_mouth_type = none` ИЛИ `applicable_fields.mouth = false` → `system_voice` полностью игнорируется движком и LLM
  - `system_common_1` / `display_common_1` — n+1; применимость определяется race-контрактом
- `character_traits_dirty` — bool; engine-only; `true` когда `system_traits` изменились и `display_character` требует перегенерации; сбрасывается нодой актуализации после регенерации
- `system_birthday` / `display_birthday` — дата рождения
- `system_origin` / `display_origin` — происхождение
- `system_motivation` / `display_motivation` — мотивация
- `system_background` / `display_background` — предыстория
- Расширяемо: `system_narrative_N` / `display_narrative_N` — пользователь задаёт имя, N = порядковый номер

### players
Расширяет `character_sheet`. Глобальный, не привязан к миру.
- Специальные поля — декларирует мир (`player_fields`)
- Игрок может быть импортирован как NPC в другой мир → кастомные поля структурно совместимы с NPC

### npcs
Расширяет `character_sheet`. Принадлежит миру.
- Специальные поля — декларирует мир (`npc_fields`)

**Кастомные нарративные поля NPC:**

`node_category` — захардкоженные категории; движок и ноды понимают их семантику:
| node_category | Назначение | Ноды-подписчики |
|---|---|---|
| `faction_context` | Нарративная лояльность, идеология, отношение к фракции | Faction node |
| `profession_detail` | Детали профессии, специализация | Trade / Craft node |
| `combat_profile` | Боевой стиль, тактика, предпочтительное оружие | Combat node — **TODO**: вернуться после реализации боевой системы и формул |
| `psychological_profile` | Психология, триггеры, страхи | Dialogue / Persuasion node |
| `secret` | Тайные мотивы, скрытая информация | Investigation / Deception node |
| `social_connections` | Ключевые связи, долги, обязательства | Relation node |
| `personal_history` | Предыстория, травмы, достижения | Actualization node |

`worlds.npc_fields` (N+1) — пользователь создаёт типы полей, обязан указать категорию:
```json
[
  { "system_name": "faction_loyalty",   "display_name": "Лояльность фракции",     "node_category": "faction_context"     },
  { "system_name": "political_view",    "display_name": "Политические взгляды",   "node_category": "faction_context"     },
  { "system_name": "implant_detail",    "display_name": "Детали импланта",         "node_category": "profession_detail"   },
  { "system_name": "hidden_agenda",     "display_name": "Скрытая повестка",        "node_category": "secret"              }
]
```
Список `node_category` — захардкожен в движке. Список типов внутри категории — N+1, пользователь расширяет.

**`character_custom_fields`** — единая таблица для NPC и игроков:
```sql
character_custom_fields (
  character_id,   -- FK → character_sheet ON DELETE CASCADE
  system_field,   -- ref → worlds.npc_fields или worlds.player_fields [system_name]
  system_value,   -- text; заполняет LLM
  display_value,  -- text; заполняет LLM
  PRIMARY KEY (character_id, system_field)
)
```
Одна таблица для обоих типов — при импорте player → NPC поля маппятся на `node_category` целевого мира.

**Lifecycle при удалении поля из реестра:** данные остаются (orphan); движок игнорирует orphan-записи при сборке контекста. Очистка — отдельный скрипт по запросу пользователя с фронта: `DELETE FROM character_custom_fields WHERE system_field NOT IN (SELECT system_name FROM npc_fields UNION SELECT system_name FROM player_fields)`.

**Фильтрация через декларацию на ноде (не отдельная нода в DAG):**

Каждая нода регистрируется декоратором — он одновременно задаёт `node_type` строку и кладёт ноду в `NodeContextRegistry`:
```python
@register_node("dialogue")
class DialogueNode(BaseNode):
    context_fields = ["psychological_profile", "social_connections"]

@register_node("faction")
class FactionNode(BaseNode):
    context_fields = ["faction_context"]

@register_node("trade")
class TradeNode(BaseNode):
    context_fields = ["profession_detail"]
```

**Реестр:** `NodeContextRegistry` — словарь `{ "dialogue" → [categories], ... }`. Заполняется при импорте модуля (через декоратор), не при первом запросе. Проблемы порядка импорта нет. Пересоздание — перезапуск приложения.

**Ошибка заметная:** забыл декоратор — нода не регистрируется и не вызывается вовсе. Не молчаливый баг в рантайме.

`DAGExecutor` при сборке плана:
1. Читает `context_fields` каждой ноды из `NodeContextRegistry` по `node_type` строке
2. Собирает union всех категорий по нодам плана
3. Один раз тянет нужные `character_custom_fields` из БД
4. Инжектирует в контекст каждой ноды только её категории

**Реализация:** написать декоратор `@register_node` и `NodeContextRegistry` при имплементации нод.

Работает одинаково для NPC и игрока. LLM не получает нерелевантные поля. Нет лишней ноды в графе.

**`worlds.player_fields`** (N+1) — нарративные поля игрока; тот же паттерн что `npc_fields`:
```json
[
  { "system_name": "reputation_detail", "display_name": "Детальная репутация", "node_category": "faction_context" }
]
```
Сеттинг-специфичные поля (prophecy, divine_mark и т.п.) — пользователь добавляет сам через N+1.

**Системные поля движка** (постоянные колонки, не входят в `npc_fields`):
```sql
system_current_target          -- nullable JSON; вычисляется из needs + goal + character_traits;
                               -- может быть перезаписан LLM во время взаимодействия с игроком;
                               -- ОЧИЩАЕТСЯ при завершении сцены
                               -- формат: { "system_target_type": "patrol",
                               --           "display_target_type": "...",
                               --           "target_uid": "loc_456",
                               --           "system_description": "...",
                               --           "display_description": "..." }

system_current_needs           -- nullable JSON array; персистентно; не очищается при выходе из сцены;
                               -- движок обновляет по increment_per_tick и событиям локации
                               -- формат: [{ "system_need": "hunger", "value": 75 }, ...]

system_npc_goal                -- nullable JSON; стратегическая цель NPC; персистентно;
                               -- формат: { "system_goal_type": "survival",
                               --           "display_goal_type": "...",
                               --           "system_description": "...",
                               --           "display_description": "..." }

system_current_thoughts        -- nullable text; LLM-нарратив текущих мыслей NPC в сцене
display_current_thoughts       -- ОЧИЩАЕТСЯ при завершении сцены; не передаётся LLM если NPC вне сцены

-- system_thoughts_about_player → вынесено в таблицу npc_thoughts_about (см. ниже)
```

**TODO — расписание NPC:**
Логика work_ticks / rest_ticks / free_ticks — реализуется отдельными нодами по тикам; отложено.

**Правила движка:**
- `NPC выходит из сцены` → `system_current_thoughts = null`, `display_current_thoughts = null`, `system_current_target = null`
- `system_current_needs` → движок применяет `increment_per_tick` из `npc_needs_registry` + `need_modifiers` из активных `location_states` локации NPC
- `system_current_target` вычисляется: `needs (urgent) + system_npc_goal + character.system_traits → target_type + target_uid`
- `system_current_target` может быть перезаписан LLM когда NPC взаимодействует с игроком
- `npc_thoughts_about` обновляется **нодой актуализации** после сцены с целью; обновляется для конкретного `target_uid` участвовавшего в сцене

**`npc_thoughts_about`** — мысли NPC о конкретных целях (персистентно):
```sql
npc_thoughts_about (
  character_id,      -- FK → character_sheet (NPC) ON DELETE CASCADE
  target_uid,        -- uid цели (игрок, другой NPC, фракция и т.п.)
  system_thoughts,   -- text; LLM-нарратив мыслей об этой цели
  display_thoughts,  -- text
  updated_at,
  PRIMARY KEY (character_id, target_uid)
)
```
Не очищается при выходе из сцены. Обновляется нодой актуализации для `target_uid` кто участвовал в прошлой сцене. LLM получает запись только если цель присутствует в текущей сцене.

**Нода актуализации** — вызывается движком перед сценой, при анализе поведения NPC или при сборке контекста:
- Проверяет `character_traits_dirty = true` → LLM регенерирует `display_character` из `system_traits` → `dirty = false`
- Проверяет `character_history.is_narrated = false` → LLM генерирует `display_description` для pending записей → `is_narrated = true`
- Обновляет `npc_thoughts_about[target_uid]` для целей с которыми NPC взаимодействовал в прошлой сцене

**Фракция** (постоянные колонки на `npcs`; детали при проектировании системы фракций):
```sql
system_faction_uid    -- nullable FK → factions; null = None (нет фракции)
system_faction_rank   -- nullable text; ранг внутри фракции; null если нет фракции
display_faction_rank  -- nullable text
```

**Поля привязки и возрождения** (постоянные колонки на `npcs`):
```sql
home_location_uid         -- nullable FK → named_locations; где живёт / спит / возвращается в idle
work_location_uid         -- nullable FK → named_locations; где работает в рабочее время
                          -- может совпадать с локацией где NPC = owner_uid (кузнец владеет кузницей)
spawn_location_uid        -- nullable FK → named_locations; точка первого появления;
                          -- null = совпадает с home_location_uid
can_respawn               -- bool; default = false
respawn_after_ticks       -- nullable int; через сколько тиков после смерти возрождается
system_respawn_place_type -- nullable ref → worlds.respawn_type_registry; валидация при записи: target.is_active=true обязан быть true; нарушение = ошибка
respawn_location_uid      -- nullable FK → named_locations; явная точка возрождения;
                          -- фолбек если location_tag не найден
```

**Правила инициализации и возрождения:**
```
Инициализация мира:
  NPC.system_location = spawn_location_uid ?? home_location_uid

Idle поведение (needs low + no goal):
  system_current_target = { target_type: "idle", target_uid: home_location_uid }

Смерть NPC:
  system_alive = false
  can_respawn = false → персонаж остаётся мёртвым; character_history сохраняется
  can_respawn = true  → через respawn_after_ticks тиков:
    respawn_point = resolve_respawn_location()
    system_alive = true
    system_location = respawn_point
    system_current_needs сбрасываются до базовых значений

resolve_respawn_location():
  if system_respawn_place_type != null:
    tag = respawn_type_registry[type].location_tag
    if tag != null → ближайшая named_location WHERE tag_refs CONTAINS tag
      (не найдена → respawn_location_uid ?? home_location_uid)
    else → respawn_location_uid ?? home_location_uid
  else → respawn_location_uid ?? home_location_uid
```

### worlds
- `stat_schema` JSON — схемы статов (см. единую схему)
- `skill_schema` JSON — схемы скиллов (та же структура)
- `derived_formulas` JSON — формулы производных статов
- `action_formulas` JSON — формулы действий (обязательны, иначе недоступно)
- `slots` JSON — кастомизация системных слотов инвентаря; типы слотов фиксированы движком (engine-level константы, не N+1); мир задаёт только `display_name` и `max`:
  ```json
  [
    { "id": "weapon",    "display_name": "Оружие",        "max": 10 },
    { "id": "head",      "display_name": "Головной убор", "max": 1  },
    { "id": "hands",     "display_name": "Перчатки",      "max": 1  },
    { "id": "body",      "display_name": "Броня",         "max": 1  },
    { "id": "feet",      "display_name": "Обувь",         "max": 1  },
    { "id": "accessory", "display_name": "Аксессуары",    "max": 20 }
  ]
  ```
  Системные ID (`weapon`, `head`, `hands`, `body`, `feet`, `accessory`) — неизменяемы; движок и `item_category_registry.valid_slots` ссылаются на них напрямую. `display_name` — любой язык/сеттинг. `max` — диапазон 1–10 (кроме accessory).
- `combat_settings` JSON — настройки боевой системы:
  ```json
  {
    "round_seconds": 6,         // длина раунда в секундах; мин 4, макс 12; дефолт 6
    "base_action_seconds": 3,   // фолбэк длительности для действий без формулы; дефолт 3
    "base_movement_speed": 1.4  // м/с фолбэк если у персонажа нет стата скорости
  }
  ```
  `round_seconds` копируется в `combat_state` при создании боя — изменение настройки не ломает активный бой.
- `default_economic_tier` — `"standard"` (дефолт); ref → `economic_tier_registry`; фолбек когда `named_locations.economic_tier = null` и нет parent
- `measurement_system` — `"metric"` | `"imperial"`; управляет display и unit для всех измеримых полей
- `weight_enabled`, `volume_enabled` — глобальные переключатели (0 = отключено)
- `overload_penalty_formula` — формула штрафа при перегрузе
- `hp_enabled` — bool; включает HP-систему жизни (HP стат достигает 0 → смерть)
- `faint_threshold` — float 0.0–1.0 (default 0.05); работает только если `hp_enabled=true`; при HP ≤ threshold × maxHP персонаж может потерять сознание; 0.0 = порог отключён
- `faint_check_formula` — nullable FormulaNode; если null → faint-система отключена; если задана — персонаж бросает проверку на сознание при пересечении порога; переменные и примеры — в документе формул
- `wounds_enabled` — bool; включает систему ранений (`character_wounds`); когда активна — раны всегда добавляют `effects` (дебаффы, штрафы к статам); `effects` non-nullable при `wounds_enabled=true`
- `wound_death_formula` — FormulaNode; используется **только** когда `hp_enabled=false` и `wounds_enabled=true`; переменные: `total_severity` (сумма severity всех активных ран), `vital_wound` (bool — есть ли vital-рана), `vital_severity` (severity самой тяжёлой vital-раны); пример: `"total_severity > 80 OR (vital_wound AND vital_severity > 60)"`
- **Правило:** `hp_enabled OR wounds_enabled` обязано быть `true`; нарушение = ошибка валидации при сохранении мира
- `wound_type_registry` JSON — реестр типов ранений; N+1:
  ```json
  [
    { "system_wound_type": "cut",      "glossary_ref": "wound_cut",      "vital": false },
    { "system_wound_type": "fracture", "glossary_ref": "wound_fracture",  "vital": false },
    { "system_wound_type": "burn",     "glossary_ref": "wound_burn",      "vital": false },
    { "system_wound_type": "piercing", "glossary_ref": "wound_piercing",  "vital": true  }
  ]
  ```
  `vital: true` — тип раны потенциально смертелен; движок учитывает при вычислении `wound_death_formula`

**Логика смерти по режиму:**

| hp_enabled | wounds_enabled | Смерть наступает при | Раны дают |
|---|---|---|---|
| true | false | HP стат = 0 | — |
| false | true | `wound_death_formula = true` → `system_alive = false` | effects + условие смерти |
| true | true | HP стат = 0 | effects (дебаффы, штрафы к статам); `wound_death_formula` не применяется |

**Faint:** при `hp_enabled=true` и заданной `faint_check_formula` — если HP ≤ `faint_threshold × maxHP` → движок запускает проверку; неудача → `system_conscious = false`; при восстановлении HP выше порога → повторная проверка на пробуждение.
- `colour_registry` JSON — глобальный реестр цветов мира; плоский список, ключи переиспользуются везде (skin, hair, beard, brows, eye):
  ```json
  [
    { "system_colour": "ivory",   "display_colour": "Слоновая кость" },
    { "system_colour": "olive",   "display_colour": "Оливковый" },
    { "system_colour": "emerald", "display_colour": "Изумрудный" }
  ]
  ```
  Race contract и character_sheet хранят только `system_colour` ключ; `display_colour` резолвится при чтении.
- `texture_registry` JSON — глобальный реестр текстур мира; плоский список, переиспользуется в skin_types:
  ```json
  [
    { "system_texture": "smooth",     "display_texture": "Гладкая" },
    { "system_texture": "aged",       "display_texture": "Постаревшая" },
    { "system_texture": "rough",      "display_texture": "Грубая" },
    { "system_texture": "iridescent", "display_texture": "Переливающаяся" },
    { "system_texture": "scaly",      "display_texture": "Чешуйчатая" }
  ]
  ```
  Race contract хранит только ключ `system_texture`; `display_texture` резолвится при чтении.
- `lore_registry` JSON — реестр лор-записей мира
- `tag_registry` JSON — реестр тегов мира
- `intensity_level_registry` JSON — универсальный конвертер int 0–100 → метку; используется для `entry_difficulty`, `guard_level`, `character_wounds.severity`, `location_faction_influence.influence`; N+1; `display_level` — нейтральное прилагательное, LLM применяет в контексте ("extreme" → "extreme difficulty" / "extreme dominance" / "extreme severity"):
  ```json
  [
    { "system_level": "none",    "display_level": "Нет",      "threshold": 0  },
    { "system_level": "low",     "display_level": "Низкая",   "threshold": 1  },
    { "system_level": "medium",  "display_level": "Средняя",  "threshold": 26 },
    { "system_level": "high",    "display_level": "Высокая",  "threshold": 51 },
    { "system_level": "extreme", "display_level": "Крайняя",  "threshold": 76 }
  ]
  ```
  `threshold` — минимальное int-значение для уровня; движок вычисляет display_level при сборке LLM-контекста: `последний уровень где threshold <= value`; пользователь может переименовать display или сдвинуть пороги
- `narrative_type_registry` JSON — реестр типов нарративных состояний; фиксированные типы системы + пользовательские (n+1):
  ```json
  [
    { "system_type_narrative": "physical_condition", "display_type_narrative": "Физическое состояние" },
    { "system_type_narrative": "emotional_state",    "display_type_narrative": "Эмоциональное состояние" },
    { "system_type_narrative": "environmental",      "display_type_narrative": "Окружение" },
    { "system_type_narrative": "social",             "display_type_narrative": "Социальное" },
    { "system_type_narrative": "mental",             "display_type_narrative": "Ментальное" }
  ]
  ```
- `player_fields` JSON — специальные поля игроков (декларация)
- `npc_fields` JSON — специальные поля NPC (декларация)
- `resist_schema` JSON — схема резистов (та же структура что stat_schema: system_name, display_name, alias, lore_ref, tag_refs); n+1 паттерн
- `stat_conflict_mode`, `stat_migrations` — настройки миграции
- `respawn_type_registry` JSON — типы возрождения; N+1; несколько могут быть активны одновременно:
  ```json
  [
    { "system_respawn_type": "temple",  "display_respawn_type": "Воскрешение в храме",   "glossary_ref": "respawn_temple",  "location_tag": "tag_temple",  "is_active": true  },
    { "system_respawn_type": "cloning", "display_respawn_type": "Клонирование",           "glossary_ref": "respawn_cloning", "location_tag": "tag_cloning", "is_active": false },
    { "system_respawn_type": "magic",   "display_respawn_type": "Магическое возрождение", "glossary_ref": "respawn_magic",   "location_tag": null,          "is_active": true  }
  ]
  ```
  `is_active = false` — тип существует в реестре но не работает; включается без удаления; `location_tag` — если задан, движок ищет ближайшую локацию с этим тегом как точку возрождения
- `trait_change_log_threshold` — float (default 0.2); минимальный Δintensity для записи в `character_history`; новые и исчезающие черты логируются всегда независимо от порога
- `npc_target_type_registry` JSON — виды активности NPC; N+1:
  ```json
  [
    { "system_target_type": "combat",    "glossary_ref": "npc_target_combat"   },
    { "system_target_type": "patrol",    "glossary_ref": "npc_target_patrol"   },
    { "system_target_type": "rest",      "glossary_ref": "npc_target_rest"     },
    { "system_target_type": "trade",     "glossary_ref": "npc_target_trade"    },
    { "system_target_type": "flee",      "glossary_ref": "npc_target_flee"     },
    { "system_target_type": "interact",  "glossary_ref": "npc_target_interact" },
    { "system_target_type": "work",      "glossary_ref": "npc_target_work"     },
    { "system_target_type": "idle",      "glossary_ref": "npc_target_idle"     }
  ]
  ```
- `npc_needs_registry` JSON — виды потребностей NPC; N+1:
  ```json
  [
    { "system_need": "hunger",  "glossary_ref": "npc_need_hunger",  "increment_per_tick": 1, "initial_value": 20 },
    { "system_need": "thirst",  "glossary_ref": "npc_need_thirst",  "increment_per_tick": 2, "initial_value": 20 },
    { "system_need": "sleep",   "glossary_ref": "npc_need_sleep",   "increment_per_tick": 1, "initial_value": 10 },
    { "system_need": "safety",  "glossary_ref": "npc_need_safety",  "increment_per_tick": 0, "initial_value": 0  },
    { "system_need": "social",  "glossary_ref": "npc_need_social",  "increment_per_tick": 0, "initial_value": 30 }
  ]
  ```
  **Шкала потребностей: 0 = полностью удовлетворена, 100 = критическая** — высокое значение → NPC срочно ищет способ удовлетворить потребность; согласуется с остальными шкалами системы (entry_difficulty, severity)
  `increment_per_tick` — насколько растёт значение за тик; 0 = не растёт автоматически, управляется событиями
  `initial_value` — значение при создании NPC; при respawn сбрасывается к `initial_value`

**Механика сна (применяется к NPC и игроку):**

Параметры:
- `race_traits.sleep_requirement_ticks` — сколько тиков сна нужно расе за цикл (дефолт 8)
- `worlds.calendar.hours_per_day` → `ticks_per_day` — длина суток в тиках

Формула бодрствования:
```
wakefulness_ratio  = actual_sleep_ticks / sleep_requirement_ticks
wakefulness_ticks  = (ticks_per_day - actual_sleep_ticks) × wakefulness_ratio
```
Недосып (`ratio < 1`) → меньше активного времени + штрафы. Пересып (`ratio > 1`) → пропорционально больше активного времени.

Долг сна:
```
sleep_debt_ticks = sleep_requirement_ticks - actual_sleep_ticks  (если > 0)
```
Хранится в `character_states` как механический эффект. Накапливается; не уходит до полного отсыпания.

Штрафы от долга — формула мира (`sleep_penalty_formula` в `worlds.action_formulas`):
```
penalty = sleep_penalty_formula(sleep_debt_ticks, character_stats)
→ debuffs на статы и скиллы через character_states.effects
```

**Стимуляторы (кофе, зелья, магия):**

Предмет или заклинание добавляет `character_state` типа `stimulant_suppression`:
- Подавляет применение `sleep_penalty_formula` пока стейт активен
- Долг при этом продолжает накапливаться
- По истечении стейта штраф возвращается по накопленному долгу

**Толерантность к стимуляторам:**

Каждое использование стимулятора инкрементирует `stimulant_tolerance_count` в `character_states`:
```
effective_suppression = base_suppression × reduction_factor ^ tolerance_count
```
Пример при `reduction_factor = 0.6`:
- 1-е использование: 100% → полное подавление
- 2-е: 60% → частичное
- 3-е: 36% → почти не работает

`reduction_factor` — настраивается в `worlds.action_formulas`.

**Crash:** если `tolerance_count > crash_threshold` (мир задаёт) и стимулятор истёк → накладывается усиленный штраф (`crash_formula` в `worlds.action_formulas`).

**Сброс толерантности:** полный цикл сна (`actual_sleep >= sleep_requirement_ticks`) → `stimulant_tolerance_count = 0`. Частичный сон — пропорциональный сброс.

- `npc_goal_type_registry` JSON — виды стратегических целей NPC; N+1:
  ```json
  [
    { "system_goal_type": "survival",    "glossary_ref": "npc_goal_survival"    },
    { "system_goal_type": "work",        "glossary_ref": "npc_goal_work"        },
    { "system_goal_type": "social",      "glossary_ref": "npc_goal_social"      },
    { "system_goal_type": "combat",      "glossary_ref": "npc_goal_combat"      },
    { "system_goal_type": "quest",       "glossary_ref": "npc_goal_quest"       },
    { "system_goal_type": "exploration", "glossary_ref": "npc_goal_exploration" }
  ]
  ```
- `character_trait_registry` JSON — черты характера; определяют множители потребностей; N+1:
  ```json
  [
    { "system_trait": "brave",    "glossary_ref": "trait_brave",    "need_multipliers": { "safety": 0.3 } },
    { "system_trait": "cowardly", "glossary_ref": "trait_cowardly", "need_multipliers": { "safety": 2.0 } },
    { "system_trait": "social",   "glossary_ref": "trait_social",   "need_multipliers": { "social": 1.8 } },
    { "system_trait": "loyal",    "glossary_ref": "trait_loyal",    "need_multipliers": { "safety": 0.8 } }
  ]
  ```
  **Формула вычисления нужды:**
  ```
  raw_need       = current_value + Σ(location_state.need_modifiers[need])
  effective_need = raw_need × Π(trait_multiplier × intensity)  -- для каждой активной черты
  ```
  `location_state.need_modifiers` — аддитивны (+50 = прибавить 50 к raw); черты характера — мультипликативны (0.3 = уменьшить в ~3 раза)
- `world_map_version` — hash схемы карты: `hash(terrain_category_registry + terrain_registry + road_type_registry + location_type_registry)`; пересчитывается при изменении любого из реестров карты; не влияет на `schema_version` (персонажи не хранят ссылки на terrain/road типы напрямую)

### `item_category_registry` (engine-level константа, hardcoded в Python)

Движок строит механику экипировки и размещения на этих категориях. Не расширяется пользователем — аналогично системным слотам и `material_category`. `valid_slots` ссылается на фиксированные системные ID слотов.

```json
[
  { "system_category": "weapon",     "is_equippable": true,  "valid_slots": ["weapon"],                     "is_placeable": true  },
  { "system_category": "armor",      "is_equippable": true,  "valid_slots": ["head","body","hands","feet"], "is_placeable": false },
  { "system_category": "accessory",  "is_equippable": true,  "valid_slots": ["accessory"],                  "is_placeable": false },
  { "system_category": "tool",       "is_equippable": false, "valid_slots": [],                             "is_placeable": true  },
  { "system_category": "furniture",  "is_equippable": false, "valid_slots": [],                             "is_placeable": true  },
  { "system_category": "decor",      "is_equippable": false, "valid_slots": [],                             "is_placeable": true  },
  { "system_category": "consumable", "is_equippable": false, "valid_slots": [],                             "is_placeable": false },
  { "system_category": "container",  "is_equippable": false, "valid_slots": [],                             "is_placeable": true  },
  { "system_category": "material",   "is_equippable": false, "valid_slots": [],                             "is_placeable": false }
]
```

### items — глобальный реестр

```sql
items (
  item_uid,           -- hash(name + timestamp)
  item_name,          -- системное имя
  item_category,      -- ref → item_category_registry
  glossary_ref,       -- nullable; глобальный лор-ref
  tag_refs,           -- nullable JSON array
  properties,         -- JSON: stat_modifiers, terrain_access, effects
  weight,             -- int граммы
  volume,             -- int мл
  is_placeable,       -- bool; можно разместить в location_objects (дублирует item_category.is_placeable, но позволяет override)
  placement_types,    -- nullable JSON array; ["floor","wall","ceiling","embedded_floor","embedded_wall","on_object"]
                      -- ref → placement_type_registry (см. tz_locations); null если is_placeable = false
  item_value_tier     -- ref → worlds.economic_tier_registry; относительная ценность предмета
)
```

`placement_types` — куда предмет CAN быть размещён; движок валидирует при создании `location_objects`.  
Примеры: картина `["wall","embedded_wall"]`; люстра `["ceiling"]`; книга `["floor","on_object"]`; мозаика `["embedded_floor"]`.

### world_items — реестр предметов мира

```sql
world_items (
  world_id,             -- FK → worlds
  item_uid,             -- FK → items
  item_cost,            -- nullable JSON; { "gold": 50 } — ключи совпадают с валютами мира (system_money_N)
  world_glossary_ref,   -- nullable; лор-переопределение для этого мира
  PRIMARY KEY (world_id, item_uid)
)
```

`item_cost` — per-world; один и тот же предмет стоит 50 золотых в мире A и 3 кредита в мире B.  
Фактическая цена при торговле = `item_value_tier.base_value × location.economic_modifier × ...` (отложено до системы экономики).

### Нормализация character_sheet
Сложные объекты (перки, инвентарь) выносятся в отдельные таблицы — персонаж ссылается, не хранит дубли.

```
character_perks            (character_id, perk_uid, current_rank)          — общие перки
character_unique_perks     (character_id, perk_uid, snapshot JSON)          — уникальные перки (полная схема)
character_inventory        (character_id, item_uid, slot, quantity)         — инвентарь
character_states           (character_id, type, effects JSON)               — активные статусы, один ряд на тип
character_history          (id, character_id, system_world_date, display_world_date,
                             system_event_type,     -- "trait_change" | "battle" | "death" | ... N+1
                             display_event_type,
                             system_participants, display_participants,
                             system_description,    -- структурный факт; заполняется сразу
                             display_description,   -- nullable; нарратив; генерирует LLM при вызове ноды актуализации
                             is_narrated,           -- bool; false = display_description ещё не сгенерирован
                             created_at)
character_narrative_states (id, character_id,
                             system_state, display_state,
                             system_description, display_description,
                             system_type, display_type,
                             system_duration_type, display_duration_type,
                             created_at)
character_wounds           (wound_uid, character_id,
                             body_part,             -- ref → body_schema_registry parts (head, torso, arm, leg...)
                             system_wound_type,     -- ref → worlds.wound_type_registry
                             display_wound_type,
                             severity,              -- int 0–100; движок использует int; LLM получает display через intensity_level_registry
                             healing_state,         -- fresh | healing | scarred | healed
                             effects,               -- JSON non-nullable ([] если нет эффектов); механические эффекты (тот же формат что character_states.effects); обязателен когда wounds_enabled=true
                             created_at)
```

`healing_state = healed` → эффекты сняты, запись остаётся как история тела. `healing_state = scarred` → постоянный нарратив без механических эффектов.

**character_history** — история событий персонажа; генерируется движком по ходу игры; `system_participants` = JSON array uid-ов других персонажей | null.

**character_narrative_states** — нарративные состояния; генерирует LLM-нода для персонажей сцены; влияет только на интерпретацию LLM-мастера, не на механику:
- `system_type` — ссылка на `narrative_type_registry` мира
- `system_duration_type` — `permanent` | `temporary`; permanent = до явного удаления; temporary = LLM решает при генерации удалить или сохранить
- Для NPC — автоочистка `temporary` записей: `DELETE WHERE system_duration_type = 'temporary' AND character_id IN (npc_ids)` через N ходов (настройка мира)

Все таблицы: `character_id FK → character_sheet ON DELETE CASCADE`.

**Жизненный цикл персонажа:**
- **Смерть** → `system_alive = false`; персонаж остаётся в БД; история, отношения и ссылки сохраняются
- **Физическое удаление** (только явное действие пользователя) → одна транзакция, два шага:
  1. `DELETE FROM character_sheet WHERE character_id = X` — БД автоматически каскадно удаляет все дочерние записи через FK: `character_perks`, `character_unique_perks`, `character_inventory`, `character_states`, `character_history`, `character_narrative_states`, `character_wounds`, `registry_dependencies`
  2. `DELETE FROM world_relations WHERE source_uid = X OR target_uid = X` — ручная очистка; `world_relations` не имеет FK на `character_sheet` (поле хранит uid разных типов сущностей), поэтому CASCADE не достаёт
  - Оба шага внутри одной транзакции: при падении процесса — полный откат, частичного состояния нет

### Таблица registry_dependencies

Индекс зависимостей сущностей от ключей мировых реестров. Обеспечивает быстрый lookup при редактировании реестра и dry-run миграции без сканирования JSON-колонок.

```sql
registry_dependencies (
    id,
    registry_type,  -- "colour" | "texture" | "body_schema" |
                    -- "hair_type" | "skin_type" | "beard_type" | "brows_type" |
                    -- "eye_type" | "eye_iris_type" | "eye_lid_type" | "eye_pupil_type" |
                    -- "mouth_type" | "teeth_type" | "lip_shape" | "jaw_shape" |
                    -- "nose_type" | "nose_shape" | "ear_type" | "ear_shape" |
                    -- "breast_type" | "breast_shape" | "genitals_type" |
                    -- "voice_pitch" | "voice_timbre" |
                    -- "muscle_table" | "constitution_table"
    registry_key,   -- значение ключа: "ivory", "smooth", "straight", ...
    entity_type,    -- "character" | "race" | "world"
    entity_id       -- character_id / race_uid / world_id
)

INDEX (registry_type, registry_key)  -- lookup: сколько записей зависит от ключа
INDEX (entity_type, entity_id)       -- переиндексация при сохранении сущности
```

**Жизненный цикл:**
- Сохранение персонажа / расы / мира → `DELETE WHERE entity_type+entity_id` + `INSERT` актуальных зависимостей
- Редактирование ключа реестра → мгновенный `SELECT COUNT(*)` без JSON-сканирования
- Импорт сущности → полная переиндексация

**Repository:**
```python
class RegistryRepository:
    def find_dependents(self, registry_type: str, key: str) -> DependencyReport: ...
    def reindex_entity(self, entity_type: str, entity_id: str) -> None: ...
```

**Структура `effects` JSON** — массив отдельных эффектов, источник истины:
```json
[
  {
    "instance_uid":              "hash(origin + created_at)",
    "system_status_name":        "...", "display_status_name":        "...",
    "system_status_origin":      "...", "display_status_origin":       "...",
    "system_status_type":        "Str", "display_status_type":         "...",
    "system_status_value":       -5,    "display_status_value":        "-5",
    "system_status_type_1":      "Con", "display_status_type_1":       "...",
    "system_status_value_1":     -3,    "display_status_value_1":      "-3",
    "system_status_duration":    "...", "display_status_duration":     "..."
  }
]
```

- `system_status_type` / `system_status_type_N` — alias конкретного стата, скилла или резиста (n+1 паттерн); один эффект может бить по нескольким целям
- При вычислении характеристики: суммируем все эффекты где `type` или `type_N` совпадает с alias
- **Агрегат** по alias — вычисляется при чтении, не хранится
- `instance_uid` — генерируется при наложении эффекта
- `system_status_origin` — ссылка на action или equipment item
- `system_status_duration` — формула снятия (FormulaNode); определяется правилами мира

world_relations     (world_id, source_uid, target_uid, relation_data JSON) — отношения на уровне мира
```

**world_relations / relation_data** — n+1 внутри одной направленной связи:
```json
{
  "system_relation":   "...", "display_relation":   "...",
  "system_motives":    "...", "display_motives":    "...",
  "system_relation_1": "...", "display_relation_1": "..."
}
```

- Отношения **направленные**: `source_uid → target_uid` (A→B и B→A независимы)
- Запись создаётся только при установлении значимой связи через геймплей
- Нет записи = нейтрально по умолчанию
- При открытии карточки персонажа — подзагрузка: `WHERE source_uid = character_uid`

```
character_sheet становится тонким: статы, скиллы, нарративные поля. Реестровые данные живут один раз.

### Снапшоты и таймлайны (save/load + time travel)

Каждый ход сохраняется слепок всего состояния мира. Архивный паттерн: не держим в памяти, загружаем по требованию, данные сжаты.

```
timelines
  timeline_id
  world_id
  created_at
  — НЕ хранит parent_snapshot_id; структура дерева живёт в world_snapshots

world_snapshots
  snapshot_id
  timeline_id
  world_id
  turn_id                — номер хода
  created_at
  parent_snapshot_id     — REFERENCES world_snapshots(snapshot_id) ON DELETE RESTRICT
                           null = первый снапшот главной линии
                           иначе = предыдущий снапшот (в той же ветке или точка ответвления)
  snapshot_data          — сжатый blob (схема мира + NPC + игрок + сессия)
  snapshot_checksum      — SHA256(snapshot_data); проверяется при загрузке
```

**Дерево снапшотов:**
```
snap_1 (turn 1, main,     parent = null)
snap_2 (turn 2, main,     parent = snap_1)
snap_3 (turn 3, main,     parent = snap_2)
  └── snap_4 (turn 1, branch_A, parent = snap_3)
      └── snap_5 (turn 2, branch_A, parent = snap_4)
```
Навигация по дереву — рекурсивный CTE по `parent_snapshot_id`, без join через `timelines`.

**Защита branch points:**
`ON DELETE RESTRICT` на `parent_snapshot_id` — БД запрещает удалить снапшот у которого есть дети. Попытка удалить branch point через API блокируется до SQL.

**Bulk delete через API:**
- Удалить таймлайн — удаляет все его снапшоты (leaf → вверх, пока нет детей в других ветках)
- Оставить последние N ходов — удаляет старые снапшоты без детей
- Branch points защищены автоматически через `ON DELETE RESTRICT`

**Освобождение места на диске:**
```sql
PRAGMA auto_vacuum = INCREMENTAL;  -- включить при создании БД
PRAGMA incremental_vacuum;         -- запускать после массового удаления
```

**Обработка ошибки checksum:**
- Загрузка блокируется — повреждённый снапшот никогда не загружается молча
- Пользователь получает явную ошибку: `Snapshot #N (ход X, timeline Y) повреждён — checksum не совпадает`
- Предлагаются варианты:
  1. Загрузить предыдущий валидный снапшот того же таймлайна
  2. Выбрать снапшот вручную из списка (все таймлайны)
  3. Отменить
- Если валидных снапшотов в таймлайне нет → только варианты 2 и 3

**Что входит в слепок:** схема мира на момент хода, состояние всех NPC, состояние игрока, состояние сессии.

**Time travel назад** → загружаем snapshot → продолжаем → новый `timeline_id`, первый снапшот новой ветки ссылается на точку ответвления через `parent_snapshot_id`. Будущее не перезаписывается.

**Time travel вперёд** → переход на любой snapshot любого существующего timeline.

**Синхронизация событий между таймлайнами** — открытая проблема, реализуется в последнюю очередь.

---

## Боевая система

### Два масштаба времени

- **Мировое время** — тики (1 тик = 1 час): путешествие, крафт, отдых, добыча, регенерация
- **Боевое время** — секунды (1 раунд = `combat_settings.round_seconds`): бой, быстрые действия внутри сцены

### Пространство боя

**1 клетка локальной сетки = 1 метр** (константа движка, как 1 тик = 1 час). Отображение — через `measurement_system` мира (метры → футы при imperial).

Иерархия пространства:
```
Мир → Регион → Локация (named_location) → Клетка (x, y, z) = 1 метр
```
`map_cells` — уровень карты мира. `(x, y, z)` внутри `named_location` — локальная сетка, поле боя.

### T = S / V — универсальная формула

**Движение в бою:**
```
T_seconds = distance_meters / V_meters_per_second
```
V — из формулы персонажа или `combat_settings.base_movement_speed` (фолбэк).

**Мировое путешествие:**
```
T_ticks = distance_cells × cell_size / V_world
```
(см. `map_settings`, отложено)

### action_registry

Реестр всех действий мира; N+1 на уровне мира. `action_formulas` мира заполняет формульные слоты.

```json
[
  { "system_action": "move",       "parent_action": null,     "duration_formula_slot": "movement_duration",   "default_seconds": null },
  { "system_action": "attack",     "parent_action": null,     "duration_formula_slot": "attack_duration",     "default_seconds": 3    },
  { "system_action": "heavy_cast", "parent_action": "attack", "duration_formula_slot": "heavy_cast_duration", "default_seconds": 3    }
]
```

- `parent_action` — наследование формул: нет `heavy_cast_duration` в мире → берётся из `attack_duration` → нет и там → `default_seconds`
- `move` — всегда T = S / V; `default_seconds: null` = действие без скорости недоступно
- `default_seconds: 3` — фолбэк движка; то же значение что `combat_settings.base_action_seconds`
- Если `duration_formula_slot` не заполнен в `worlds.action_formulas` — действие использует наследование → фолбэк

### combat_state и combat_positions

```sql
combat_state (
  battle_uid,
  session_id,         -- FK → game_sessions
  location_uid,       -- где происходит бой
  round_number,       -- текущий раунд
  round_seconds,      -- копия из combat_settings.round_seconds на момент начала боя
  started_at_tick,
  PRIMARY KEY (battle_uid)
)

combat_positions (
  battle_uid,         -- FK → combat_state ON DELETE CASCADE
  character_uid,      -- FK → character_sheet
  x, y, z,           -- текущая позиция на локальной сетке (в метрах)
  PRIMARY KEY (battle_uid, character_uid)
)
```

**История позиций во время боя** — in-memory cache:
```python
# battle_uid → { round_number → { character_uid → (x, y, z) } }
combat_history_cache: dict[str, dict[int, dict[str, tuple]]]
```
LLM и движок читают историю из кэша для контекста ("где все стояли 2 раунда назад"). Кэш сбрасывается после боя.

**Откат раунда** — через снапшоты (снапшот per round захватывает `combat_positions`). Игрок откатывается → новая ветка таймлайна → переигрывает раунд.

**После боя:** `combat_state` + `combat_positions` удаляются, кэш очищается, итог пишется в `character_history` событием типа `"battle"`.

---

## Игровая сессия и Pipeline State

### Архитектура движка

**Ноды — чистые трансформеры стейта:** `input state → GATHER → COMPUTE → APPLY → output state`. Нода не знает как она вызвана — не обращается к EventBus напрямую. Только через executor. Это правило обязательно для всех нод.

**Два режима движка (по конфигу `engine_mode`):**

```
engine_mode = "single"      # SinglePlayerDAGExecutor
engine_mode = "multiplayer" # MultiplayerDAGExecutor
```

```python
class DAGExecutorBase(ABC):
    @abstractmethod
    async def execute(self, state: ExecutionState) -> ExecutionResult: ...

class SinglePlayerDAGExecutor(DAGExecutorBase): ...  # реализован сейчас
class MultiplayerDAGExecutor(DAGExecutorBase): ...   # TODO
```

Ноды не меняются при смене режима. При переходе single → multiplayer данные совместимы — игрок продолжает игру без потери прогресса (рестарт для поднятия персистентного EventBus).

**Инициатива в мультиплеере** — решается FIFO очередью asyncio event loop. Кто первым попал в очередь — тот действует первым. Никакого отдельного roll initiative.

**Мультипротагонист (два персонажа в одном мире)** — TODO, потенциальная кор-механика. Архитектура `UNIQUE(world_id, player_character_id)` закладывает фундамент. Полный дизайн — отдельная задача.

**Режим сцены (`scene_mode`)** — не хранится. `INTENT_DETECTION` нода определяет `TaskType`-ы по сообщению игрока. Режим может перетекать внутри одного хода (бой + диалог). Лимит TaskType за один ход и условия группировки — TODO после реализации нод.

### game_sessions

```sql
game_sessions (
  id,
  world_id,                    -- FK → worlds
  player_character_id,         -- FK → character_sheet
  restored_from_snapshot_id,   -- nullable FK → world_snapshots
  created_at,
  last_active_at,
  UNIQUE (world_id, player_character_id)
)
```

Одна сессия на пару `(world, player)`. Множество игроков в одном мире — отдельные сессии. `current_tick` хранится на `worlds` — сессия читает оттуда. При восстановлении снапшота `current_tick` восстанавливается вместе с миром автоматически.

**Импорт игрока в форкнутый мир (as-is):** player state импортируется в текущем состоянии; движок не проверяет расхождение тиков. Пользователь получает явное предупреждение об этом при импорте.

### scene_participants

Мастер (движок или пользователь) выбирает АКТИВНЫХ участников сцены из NPC локации. Ambient NPC (присутствуют в локации, но не вовлечены) — выводятся из `system_location`, не хранятся в таблице.

```sql
scene_participants (
  session_id,     -- FK → game_sessions ON DELETE CASCADE
  character_uid,  -- FK → character_sheet
  PRIMARY KEY (session_id, character_uid)
)
```

Игрок и NPC — одинаковые записи. Очистка `scene_participants` — при событии конца сцены (выход из локации, завершение взаимодействия).

---

## Архитектура нод пайплайна

### IntentDetectionNode — универсальный вход

`IntentDetectionNode` — единственная точка входа для любого текстового ввода пользователя. Работает с минимальным стейтом: есть ли мир, персонаж, активная сцена, активный бой.

**Дочерние контекстные ноды** обогащают intent запрос условно — DAG включает их только если стейт позволяет:

```
IntentDetectionNode (deps: [])
    ├── LocalSceneShortContextNode  — deps: ["intent_detection"]
    │     запускается: если scene_participants не пустой
    │     не запускается: холодный старт, создание персонажа, пустая сессия
    ├── CombatContextNode           — deps: ["intent_detection"]  (TODO)
    │     запускается: если combat_state активен
    └── (другие контекстные ноды по мере роста системы)
```

`IntentDetectionNode` DSL принимает опциональный контекст от дочерних нод — если они не запустились, LLM работает с голым сообщением пользователя.

**AS IS:** `IntentDetectionNode` → LLM с голым сообщением, без контекста сцены.
**TO BE:** дочерние ноды добавляют контекст если он есть; если нет — ничего не добавляется.

**Создание персонажа:** пользователь указывает семантически ("хочу создать персонажа") → `IntentDetectionNode` детектирует intent и запускает соответствующий pipeline. Отдельный режим не нужен. Пошаговый creation wizard — TODO.

**Прямые API вызовы** (форма в UI, JSON импорт) — обходят `IntentDetectionNode` полностью, идут напрямую в специфический pipeline.

### LocalSceneShortContextNode

Python нода. Запускается как дочерняя от `IntentDetectionNode` только при активной сцене.

Адаптируется под ситуацию:
- **Холодный старт** (нет сцены): не запускается
- **Активная сцена, не бой**: собирает `scene_participants` + ambient NPC из локации, их статусы, possible targets
- **Активный бой**: собирает `combat_positions`, раунд, статусы участников

Результат инжектируется в контекст `IntentDetectionNode` как опциональный блок.

---

## Ключевые правила

### Единая схема статов и скиллов
```json
{
  "system_name": "Fire",
  "display_name": "Огонь",
  "alias": "Fr",
  "description": "Ability to master fire.",
  "lore_ref": "great_burning_forbidden_arts",
  "tag_refs": ["tag_forbidden", "tag_rare"]
}
```
- `system_name` — внутренний ключ, неизменяемый
- `display_name` — что видит пользователь, любой язык
- `alias` — короткий код: используется в формулах И в LLM контексте (экономия токенов)
- `lore_ref` — ссылка на Lore Registry мира
- `tag_refs` — ссылки на Tag Registry мира

**LLM получает компактно:** `Str:15 Dex:12 Fr:45` вместо полных имён.

### Статы
- Динамические, определяются миром. Персонаж хранит только значения.
- Нет дефолтов в коде — всё явно в конфиге мира.

### Скиллы / Мастерство
- Динамические, определяются миром через `skill_schema` (N+1; та же структура что `stat_schema` + `initial_value`).
- Диапазон значений: `0–100`. Прокачиваются через опыт.
- Используются напрямую в формулах действий через alias.
- Совместимость персонаж ↔ мир — та же логика что со статами (AliasRegistry, `stat_migrations`, `stat_conflict_mode`).

**`skill_schema` — запись реестра:**
```json
{
  "system_name":   "fire",
  "display_name":  "Огонь",
  "alias":         "Fr",
  "description":   "Владение огненной магией.",
  "lore_ref":      "great_burning_forbidden_arts",
  "tag_refs":      ["tag_forbidden", "tag_rare"],
  "initial_value": 0
}
```
`initial_value` — значение присваивается всем существующим персонажам при добавлении нового скилла в мир; диапазон 0–100.

**Хранение значений персонажа:**
```sql
character_mastery (
  character_id,   -- FK → character_sheet ON DELETE CASCADE
  system_skill,   -- ref → worlds.skill_schema[system_name]
  value           -- int 0–100
  PRIMARY KEY (character_id, system_skill)
)
```

**Жизненный цикл при изменении `skill_schema`:**
- **Добавление скилла** → движок вставляет строку `(character_id, system_name, initial_value)` для всех персонажей мира в одной транзакции
- **Удаление скилла** → строки `character_mastery` для этого `system_name` удаляются; данные не переносятся
- **Переименование** → через `stat_migrations` (alias замена); `system_name` неизменяем — данные не трогаются

### Действия
```json
{
  "system_name": "attack_melee",
  "display_name": "Удар мечом",
  "damage_formula": "Str * 1.5 + Fr * 0.5"
}
```
- Логика статическая в коде, формулы всегда из мира. Нет формулы — действие недоступно.
- `system_name` — внутренний ключ, движок работает только через него.
- Пользователь переименовывает и переопределяет формулу → получает своё действие.

### Мировые реестры

**Lore Registry** — нарративные записи, на которые ссылаются статы/скиллы/предметы:
```json
{ "id": "great_burning_forbidden_arts", "title": "...", "content": "..." }
```

**Tag Registry** — определения тегов, специфичные для каждого мира:
```json
{ "id": "tag_forbidden", "label": "Запрещённое", "meaning": "Казнь на месте по закону Империи" }
```
В другом мире `tag_forbidden` может означать просто социальную стигму.

### Совместимость персонаж ↔ мир
При входе: статы и скиллы персонажа которых нет в мире → игнорируются + предупреждение со списком.

### Инвентарь
- Типы слотов фиксированы движком (`weapon`, `head`, `hands`, `body`, `feet`, `accessory`); мир кастомизирует только `display_name` и `max`
- Удалённый слот → предметы падают в общий инвентарь
- Вес и объём статические у каждого предмета и инвентаря
- `weight_enabled = 0` или `volume_enabled = 0` → свойство не применяется
- Перегруз → штраф по мировой формуле (`overload_penalty_formula`)
- Предметы влияют на статы пока экипированы
- Подсумки и рюкзаки — контейнерная механика, обсуждается позже

### Генерация описания персонажа
Нода в движке: статы + скиллы персонажа → лор и теги из мира → нарративное описание → контекст AI-мастера.
База более широкой системы генерации. AI-мастер получает персонажа как нарратив, не как цифры.

### Перки

**Схема перка** (единая для общих и уникальных):
```json
{
  "system_uid": "hash(system_name + created_at)",
  "system_name":        "...", "display_name":        "...",
  "system_description": "...", "display_description": "...",
  "system_rank_value":  [{ "rank": "Базовый", "value": [1, 5] }, ...],
  "display_rank_value": "Базовый: 1–5, ...",
  "system_tags":        [...], "display_tags":        "...",
  "system_condition":   "...", "display_condition":   "...",
  "terrain_access":     ["liquid", "aerial"]
}
```
- `value` — диапазон `[min, max]` для вычисления при активации
- `system_condition` — триггер активации: движок проверяет при вычислении любого действия
- `system_tags` — динамически вычисляются LLM из списков action/skill; мост между перком и действием
- `terrain_access` — nullable; список категорий местности которые персонаж может проходить пока перк активен

**Два вида перков:**

| | Общие | Уникальные |
|---|---|---|
| Реестр | `world_perks` (мир) | нет, inline на персонаже |
| Хранение у персонажа | uid-ссылка + текущий ранг | полный объект |
| Кто имеет | много персонажей | только один персонаж |
| Генерация | пользователь | AI |

**UID** — залог уникальности для экспорта/импорта у обоих видов. `hash(system_name + created_at)`.

**Валидация при импорте** — та же логика что у статов и предметов: совпадение по UID → ok, конфликт → `soft` предупреждение или `migrate` по маппингу.

### Крафт
Отдельная система, обсуждается позже. Механизм создания динамических предметов.

### Вычисление формул — FormulaNode

Формулы — первоклассная механика движка. Все вычисления через DAG.

**FormulaNode** — новый тип ноды в движке:
- `input`: строка формулы + контекст `{alias → value}` из `ExecutionState`
- `output`: результат (число или bool для conditions)

**FormulaEvaluator** — внутри ноды, AST-based, whitelist операций:
- Операторы: `+`, `-`, `*`, `/`, `**`, `>`, `<`, `>=`, `<=`, `==`, `and`, `or`
- Функции: `rnd(min, max)`, `floor()`, `ceil()`, `min()`, `max()`
- Ноль внешних зависимостей

**Применяется для:**
- `action_formulas` — урон, эффекты действий
- `derived_formulas` — производные статы
- `overload_penalty_formula` — штраф перегруза
- `system_condition` перка — триггер активации (→ bool)
- `system_rank_value` перка — диапазон `rnd(min, max)`

Контекст (alias → значение стата/скилла персонажа) передаётся через `ExecutionState`.
Детальное проектирование FormulaNode — отдельная задача.

### Контекстные профили LLM-нод

Каждый тип ноды (task type) собирает свой срез данных из `ExecutionState` — только релевантное для данной сцены.

```
CombatContext:    stats + skills + status_effects + equipped_items + barrier
DialogueContext:  appearance + character_traits + social_status + relations + narrative_state
NarrativeContext: appearance + character + history + motivation + narrative_state
```

- `ExecutionState` хранит полный character_sheet
- Каждая LLM-нода имеет `context_builder` — извлекает нужный срез перед вызовом LLM
- LLM не получает нерелевантные данные → качество выше, токены экономятся
- Профили тестируются эмпирически: минимально необходимый контекст определяется экспериментом

**DAG управляет двумя вещами одновременно:**
1. Логические зависимости между нодами (порядок выполнения)
2. Ресурсы — какие ноды можно запускать параллельно, какие последовательно

**Лимиты на task type** — определяются после построения полной системы нод и списка task type. Преждевременная оптимизация до понимания реальной структуры нецелесообразна.

### Alias Registry — lookup alias → категория

Статусы, формулы и движок оперируют alias как строками (`"Str"`, `"FrRes"`, `"Fire"`). Движку нужно знать к какой категории относится alias при вычислении.

**Решение:** при загрузке мира строится единый `AliasRegistry` из всех схем:

```
stat_schema    → { alias: "Str",   category: "stat",    system_name: "strength" }
skill_schema   → { alias: "Fire",  category: "mastery", system_name: "fire"     }
resist_schema  → { alias: "FrRes", category: "resist",  system_name: "fire_res" }
```

Lookup: `alias → { category, system_name, current_value }`.

- Строится один раз при загрузке мира, живёт в памяти на время сессии
- Используется FormulaNode, системой статусов, LLM контекстом
- Alias уникален в пределах мира — конфликт alias при загрузке = ошибка валидации
- **Валидация при записи** — перед сохранением нового стата/скилла/резиста alias проверяется против текущего AliasRegistry; коллизия блокирует сохранение с явной ошибкой: `Alias "Fr" уже используется: стат "Fire"`
- **Обновление в памяти** — после любого изменения схемы (добавить/переименовать/удалить стат/скилл/резист) AliasRegistry обновляется немедленно; коллизия никогда не попадает в БД

---

## Система миграции (общая)
Один контракт и один `conflict_mode` покрывают все сущности: статы, скиллы, предметы, формулы, реестры мира.

```json
{
  "stat_conflict_mode": "soft" | "migrate",
  "stat_migrations": [
    { "from": "Con",   "to": "Dex" },
    { "from": "Power", "to": "Charizma" }
  ],
  "registry_migrations": {
    "colour":      [{ "from": "ivory",   "to": "pearl" }],
    "texture":     [{ "from": "smooth",  "to": "silky" }],
    "hair_type":   [{ "from": "coily",   "to": "kinky" }],
    "skin_type":   [...],
    "beard_type":  [...],
    "brows_type":  [...],
    "eye_type":    [...],
    "eye_iris_type":  [...],
    "eye_lid_type":   [...],
    "eye_pupil_type": [...],
    "mouth_type":     [...],
    "teeth_type":     [...],
    "lip_shape":      [...],
    "jaw_shape":      [...],
    "nose_type":      [...],
    "nose_shape":     [...],
    "ear_type":       [...],
    "ear_shape":      [...],
    "genitals_type":  [...],
    "breast_type":    [...],
    "breast_shape":   [...],
    "voice_pitch":    [...],
    "voice_timbre":   [...],
    "body_schema":    [{ "from": "humanoid", "to": "humanoid_v2" }],
    "terrain_type":       [{ "from": "woodland", "to": "forest"     }],
    "road_type":          [{ "from": "highway",  "to": "royal_road" }],
    "location_type":      [{ "from": "town",     "to": "settlement" }],
    "difficulty_level":   [{ "from": "extreme",  "to": "legendary"  }],
    "connection_type":    [{ "from": "gate",     "to": "door"       }],
    "wound_type":         [{ "from": "slash",    "to": "cut"        }],
    "npc_target_type":    [{ "from": "attack",   "to": "combat"     }],
    "npc_need_type":      [{ "from": "food",     "to": "hunger"     }],
    "npc_goal_type":      [{ "from": "protect",  "to": "survival"   }],
    "character_trait":    [{ "from": "fearless", "to": "brave"      }],
    "respawn_type":       [{ "from": "revival",  "to": "temple"     }]
  }
}
```

- `soft` — конфликты всплывают при входе, данные не трогаем
- `migrate` — применяем маппинг ко всем сущностям и реестрам; без маппинга → soft + предупреждение
- `stat_conflict_mode` распространяется на `registry_migrations` тоже — один режим для всего
- UI формирует JSON, бэкенд исполняет. Без явного маппинга миграция не запускается.

**Покрытие миграции alias** — `stat_migrations` применяются ко всем местам где используется alias:
- `worlds.derived_formulas` — строки формул (поиск и замена по word boundary: `\bOldAlias\b`)
- `worlds.action_formulas` — строки формул (то же правило)
- `character_states.effects[].system_status_type` и `system_status_type_N` — прямые alias-ссылки
- `character_states.effects[].system_status_duration` — формула снятия (строка, word boundary замена)
- `character_perks / character_unique_perks` → `system_condition` и `system_rank_value` — формулы перков
- Без маппинга для alias → `soft`: предупреждение при загрузке, статус/формула с мёртвым alias игнорируется движком

**Миграция — атомарная операция (одна SQL транзакция):**
```
1. Обновить данные всех затронутых сущностей (apply mappings)
2. reindex_entity() для каждой затронутой сущности → rebuild registry_dependencies
3. Пересчитать worlds.schema_version hash
4. Обновить world_schema_version у всех персонажей мира
```
Миграция и переиндексация неразрывны — запускаются вместе, не по отдельности.

**После миграции — обязательный перезапуск сессии.**
AliasRegistry живёт в памяти и не инвалидируется на лету. Перезапуск пересобирает его из актуальной схемы.
История чата сохраняется — теряется только in-memory состояние сессии.

**Schema versioning:**
- `worlds.schema_version` — hash содержимого схемы: `hash(stat_schema + skill_schema + resist_schema + colour_registry + texture_registry + body_schema_registry + muscle_tables + constitution_tables + hair_type + hair_shape + skin_type + brows_type + brows_shape + beard_type + beard_shape + eye_type + eye_placement + eye_iris_type + eye_lid_type + eye_pupil_type + eye_roundness + mouth_type + lip_shape + teeth_type + jaw_shape + nose_type + nose_shape + ear_type + ear_shape + breast_type + breast_shape + genitals_type + voice_pitch + voice_timbre + body_hair_density + wound_type_registry + race contracts)`
- Пересчитывается при каждом изменении схемы мира
- `character_sheet.world_schema_version` — hash схемы на момент последней миграции персонажа
- При загрузке: `character.world_schema_version != world.schema_version` → схемы отличаются → миграция
- При импорте из другого мира: hash глобально уникален по содержимому → случайное совпадение исключено
- Одинаковый hash = идентичные схемы, миграция не нужна даже если миры разные

---

---

## Системные таблицы

### Расы и гендер

**system_gender** — таблица полов (immutable keys, display зависит от языка):
`male`, `female`, `asexual`, `both`
При изменении `system_gender` → обновляются все display-таблицы (отдельный механизм обновления).

**Иерархия правил генерации внешности:**
1. `race` — базовый контракт (цвет кожи, тип волос, доступные shapes, lifespan, применимые поля тела и т.д.)
2. `social_status` — дополнительные правила поверх расы

### Таблица races (race-контракт)

```
race_uid     — hash(display_race + created_at)
display_race
race_traits  — JSON; расовые свойства уровня всей расы (не зависят от пола)
male         — JSON | null
female       — JSON | null
asexual      — JSON | null
both         — JSON | null
```

**`race_traits`** — подобъект уровня расы:
```json
{
  "terrain_access": ["liquid"],
  "tag_refs": ["tag_aquatic", "tag_cold_blooded"],
  "sleep_requirement_ticks": 8
}
```
- `terrain_access` — расовые способности передвижения по умолчанию для всех полов
- `tag_refs` — теги из `tag_registry`; LLM получает как расовый контекст
- `sleep_requirement_ticks` — сколько тиков (часов) расе нужно спать за цикл; дефолт 8; используется в формуле бодрствования

**Фолбек `terrain_access`:**
```
effective_terrain_access = gender.terrain_access ?? race_traits.terrain_access ?? []
```
Gender-объект может опционально переопределить для конкретного пола. Отсутствие поля в gender → берётся из `race_traits`.

**Доступность гендера:** поле `null` или отсутствует → гендер недоступен для расы.

**Гендерный объект** — все поля опциональные:
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
  "beard_types": {
    "human_beard": { "shapes": ["full", "goatee"], "colours": ["black", "brown"] },
    "feathered":   { "shapes": ["display", "ruffled"], "colours": ["crimson", "golden"] }
  },
  "brows_types": {
    "human_brows": { "shapes": ["thin", "thick", "arched"], "colours": ["black", "brown"] },
    "ridge":       { "shapes": ["flat", "pronounced"],      "colours": ["grey", "ivory"] }
  },
  "eye_options": {
    "eye_counts":    [2],
    "eye_placements": ["forward"],
    "eye_types": {
      "human": {
        "roundness":     ["almond", "round"],
        "iris_types":    ["normal"],
        "lid_types":     ["single", "double"],
        "pupil_types":   ["round"],
        "iris_colours":  ["amber", "blue", "green"],
        "pupil_colours": ["black"]
      },
      "cat": {
        "roundness":     ["almond"],
        "iris_types":    ["feline"],
        "lid_types":     ["single"],
        "pupil_types":   ["vertical_slit"],
        "iris_colours":  ["yellow", "green"],
        "pupil_colours": ["black"]
      }
    }
  },
  "mouth_options": {
    "mouth_types": {
      "human_mouth": {
        "lip_shapes":  ["thin", "full", "wide"],
        "lip_colours": ["rose", "pale"],
        "teeth_types": ["human", "fangs"],
        "jaw_shapes":  ["oval", "square"]
      },
      "beak": { "jaw_shapes": ["curved", "straight"] }
    }
  },
  "nose_options": {
    "nose_types": {
      "human": { "shapes": ["straight", "flat", "hooked"] },
      "snout": { "shapes": ["short", "long"] }
    }
  },
  "ear_options": {
    "ear_types": {
      "pointed": { "shapes": ["long", "medium", "short"] },
      "animal":  { "shapes": ["round", "tufted"] }
    }
  },
  "breast_options": {
    "breast_types": {
      "human":    { "shapes": ["natural", "lifted", "round", "teardrop"] },
      "multiple": { "shapes": ["round"] }
    }
  },
  "voice_options": {
    "pitches": ["deep", "medium"],
    "timbres": ["rough", "smooth"]
  },
  "muscle_stat":        "Str",
  "constitution_stat":  "Con",
  "muscle_table":       "insectoid",
  "constitution_table": "insectoid",
  "applicable_fields": {
    "beard":     true,
    "waist":     false,
    "hips":      false,
    "breast":    false,
    "body_hair": true,
    "mouth":     true,
    "nose":      true,
    "ear":       true,
    "genitals":  false
  },
  "terrain_access": ["liquid"]
  -- опционально; если отсутствует → берётся из race_traits.terrain_access
}
```

**Правила полей:**
- Поле отсутствует (не-базовое) → фильтрация не работает, доступны все значения из мировых таблиц
- `applicable_fields` отсутствует → все поля доступны без ограничений
- Конкретное поле в `applicable_fields` отсутствует → это поле доступно без ограничений
- `applicable_fields` не распространяется на базовые поля — они всегда присутствуют: `skin`, `height`, `weight`, `age`, `muscle`, `constitution`

**Базовые поля — цепочка фолбеков:**
Применяется к: `lifespan`, `skin_types`, `height_range`, `weight_range`, `muscle_stat`, `constitution_stat`
1. Текущий гендерный объект
2. Любой другой заполненный гендерный объект этой расы
3. **Human preset** — системные константы (не хранятся в БД)

**Фолбек шаг 3 — world seed data:**
Не хардкод в движке. При создании нового мира генерируется дефолтная конфигурация (seed):
- `colour_registry` с базовыми оттенками кожи, волос, глаз
- Раса "Human" с заполненными диапазонами, lifespan, skin_types
- Все редактируемо — пользователь может изменить или удалить

Движок не знает о "людях" — он работает только с тем что есть в БД мира.

**Валидация при загрузке мира:**
- `muscle_stat` / `constitution_stat` — alias должен существовать в AliasRegistry мира
- `hair_types` ключи — должны существовать в таблице `hair_type`; `shapes` и `colours` опциональны (отсутствие = все значения доступны)
- `beard_types` ключи — должны существовать в таблице `beard_type`; `shapes` и `colours` опциональны
- `brows_types` ключи — должны существовать в таблице `brows_type`; `shapes` и `colours` опциональны
- `eye_options.eye_types` ключи — должны существовать в таблице `eye_type`; все sub-поля опциональны
- `skin_types` ключи — должны существовать в таблице `skin_type`; `colours` ключи из `colour_registry`, `textures` ключи из `texture_registry`; оба опциональны
- `muscle_table` / `constitution_table` — `table_id` должен существовать в `worlds.muscle_tables` / `worlds.constitution_tables`
- `body_schema` — `schema_id` должен существовать в `worlds.body_schema_registry`
- `mouth_options.mouth_types` ключи — должны существовать в таблице `mouth_type`; `lip_shapes` из `lip_shape`, `teeth_types` из `teeth_type`, `jaw_shapes` из `jaw_shape`, `lip_colours` из `colour_registry`
- `nose_options.nose_types` ключи — должны существовать в таблице `nose_type`; `shapes` из `nose_shape`
- `ear_options.ear_types` ключи — должны существовать в таблице `ear_type`; `shapes` из `ear_shape`
- `breast_options.breast_types` ключи — должны существовать в таблице `breast_type`; `shapes` из `breast_shape`
- `voice_options.pitches` ключи — должны существовать в таблице `voice_pitch`
- `voice_options.timbres` ключи — должны существовать в таблице `voice_timbre`
- `lifespan` — диапазоны не перекрываются, без пробелов
- `height_range` / `weight_range` — `system_measurement_unit` обязателен при наличии диапазона

### Таблица social_status (полностью редактируемая, минимум 2 записи)
```
system_social_status | display_social_status | social_status_weight
poor                 | ...                   | 0
common               | ...                   | 1
middle               | ...                   | 2
rich                 | ...                   | 4
very rich            | ...                   | 6
rich and powerful    | ...                   | 8
ruler                | ...                   | 15
system_social_status_1 N+1
```
`social_status_weight` — числовой вес для генерации; цифры редактируемы.

### Таблица age_type (нельзя удалить записи, только переименовать display)
```
system_age_type | display_age_type
baby            | ...
child           | ...
young           | ...
adult           | ...
mature          | ...
elderly         | ...
old             | ...
very old        | ...
```
У каждой расы свой lifespan — маппинг возраст (int) → age_type.

### Таблица hair_type (immutable keys, display зависит от языка)
Обобщённый тип — "что покрывает голову". Включает нечеловеческие варианты.
```
system_hair_type | display_hair_type
straight         | ...
wavy             | ...
curly            | ...
coily            | ...
horns            | ...
scale            | ...
feathers         | ...
chitin           | ...
```
Правило: доступные значения для расы задаёт race-контракт (`hair_types` ключи).

### Таблица hair_shape (N+1, редактируемая)
```
system_hair_shape | display_hair_shape | system_hair_shape_is_auto
short             | ...                | 0
long pony tail    | ...                | 0
bowl cut          | ...                | 0
bold              | ...                | 1
system_hair_shape_1 N+1
```
`system_hair_shape_is_auto = 1` — запись скрыта в UI-выборке, устанавливается только движком по условию.
Правило: `system_hair.system_length = 0` → движок принудительно ставит `hair_shape = bold`, пользователь выбрать не может.
Запись можно только переименовать (`display_hair_shape`), но не удалить.

### Реестры muscle_tables / constitution_tables

Мир хранит именованные таблицы мышечности и телосложения. Race contract ссылается на нужную по `table_id`. Нет ссылки → таблица с `table_id: "default"`.

**`worlds.muscle_tables`** — JSON массив:
```json
[
  {
    "table_id": "default",
    "display_name": "Стандартная",
    "entries": [
      { "system_muscle": "atrophy",      "display_muscle": "...", "system_muscle_weight": 0  },
      { "system_muscle": "basic",        "display_muscle": "...", "system_muscle_weight": 3  },
      { "system_muscle": "athletic",     "display_muscle": "...", "system_muscle_weight": 6  },
      { "system_muscle": "great physic", "display_muscle": "...", "system_muscle_weight": 9  },
      { "system_muscle": "super muscle", "display_muscle": "...", "system_muscle_weight": 12 }
    ]
  },
  {
    "table_id": "insectoid",
    "display_name": "Насекомоподобная",
    "entries": [
      { "system_muscle": "frail",  "display_muscle": "...", "system_muscle_weight": 0  },
      { "system_muscle": "normal", "display_muscle": "...", "system_muscle_weight": 5  },
      { "system_muscle": "dense",  "display_muscle": "...", "system_muscle_weight": 10 }
    ]
  }
]
```

Аналогично **`worlds.constitution_tables`** — дефолтные записи: skinny(0), lean(3), normal(6), bulky(9), huge(12), enormous(15).

**Правило коэффициента стата** (единое для всех таблиц):
```
coeff            = min(char_stat / world_max_stat, 1.0)
effective_weight = base_weight * (1 + coeff)
```
Пример: athletic (base=6), char_stat=80, world_max=100 → coeff=0.8 → effective=10.8 → great physic (9) < 10.8 → super muscle (12).

**Общее правило весов** — автосортировка по весу при изменении; применяется ко всем таблицам реестров.

### Общее правило весов
Все таблицы с весами (`*_weight`): при изменении веса → автосортировка записей от меньшего к большему.
`none` / weight=0 — специальное значение: означает отсутствие признака, всегда первым.

### Таблица eye_placement (immutable keys, display зависит от языка, N+1)
```
system_eye_placement | display_eye_placement
forward              | ...   (вперёд — человек, кошка, сова; бинокулярное зрение)
lateral              | ...   (по бокам — лошадь, рыба; широкое поле зрения)
top                  | ...   (сверху — лягушка, крокодил)
compound             | ...   (фасеточные — насекомые)
system_eye_placement_1 N+1
```

### Таблица eye_iris_type (immutable keys, display зависит от языка, N+1)
```
system_eye_iris_type | display_eye_iris_type
normal               | ...
feline               | ...
annular              | ...   (кольцеобразная)
system_eye_iris_type_1 N+1
```

### Таблица eye_lid_type (immutable keys, display зависит от языка, N+1)
```
system_eye_lid_type | display_eye_lid_type
single              | ...   (одно веко)
double              | ...   (двойное веко)
nictitating         | ...   (мигательная перепонка)
system_eye_lid_type_1 N+1
```

### Таблица eye_pupil_type (immutable keys, display зависит от языка, N+1)
```
system_eye_pupil_type | display_eye_pupil_type
round                 | ...
vertical_slit         | ...
horizontal_slit       | ...
star                  | ...
system_eye_pupil_type_1 N+1
```

### Таблица eye_roundness (редактируемые веса)
```
system_eye_roundness | display_eye_roundness | system_eye_roundness_weight
none                 | ...                   | 0
```
N+1 — пользователь добавляет формы.

### Таблица eye_type (редактируемые веса; none = глаз отсутствует)
```
system_eye_type | display_eye_type | system_eye_type_weight
none            | ...              | 0
```
N+1 — пользователь добавляет типы.

### Таблица skin_type (immutable keys, display зависит от языка, N+1)
Тип покрытия тела. Управляет доступными цветами и текстурами в связке с race-контрактом.
```
system_skin_type | display_skin_type
skin             | ...
horns            | ...
scale            | ...
feathers         | ...
chitin           | ...
system_skin_type_1 N+1
```
Правило: доступные значения для расы задаёт race-контракт (`skin_types`).

### Таблица brows_type (immutable keys, display зависит от языка, N+1)
```
system_brows_type | display_brows_type
human_brows       | ...
ridge             | ...   (костяной/хитиновый гребень)
system_brows_type_1 N+1
```
Правило: доступные значения для расы задаёт race-контракт (`brows_types` ключи).

### Таблица brows_shape (N+1, редактируемая)
```
system_brows_shape | display_brows_shape
thin               | ...
thick              | ...
arched             | ...
straight           | ...
bushy              | ...
system_brows_shape_1 N+1
```

### Таблица beard_type (immutable keys, display зависит от языка, N+1)
Тип бороды/покрытия подбородка. Управляет доступными формами и цветами через race-контракт.
```
system_beard_type | display_beard_type
human_beard       | ...
feathered         | ...
chitinous         | ...
system_beard_type_1 N+1
```
Правило: доступные значения для расы задаёт race-контракт (`beard_types` ключи).

### Таблица beard_shape (N+1, редактируемая)
```
system_beard_shape | display_beard_shape | system_beard_shape_is_auto
none               | ...                 | 1
full               | ...                 | 0
goatee             | ...                 | 0
stubble            | ...                 | 0
system_beard_shape_1 N+1
```
`none` — `is_auto=1`: устанавливается движком при `system_beard.system_length = 0`, не отображается в выборке.

### Реестр body_schema_registry

Мировой реестр схем тела. Хранится как JSON-колонка `worlds.body_schema_registry`. Race contract ссылается по `schema_id`.

```json
[
  {
    "schema_id": "humanoid",
    "display_name": "Гуманоид",
    "parts": {
      "head":     { "count": 1 },
      "arms":     { "count": 2 },
      "body":     { "zones": ["chest", "abdomen", "back"] },
      "genitals": { "zones": ["genitals"] },
      "pelvis":   { "zones": ["pelvis"] },
      "butt":     { "zones": ["butt"] },
      "legs":     { "count": 2 }
    }
  },
  {
    "schema_id": "insectoid",
    "display_name": "Насекомоподобный",
    "parts": {
      "head":     { "count": 1 },
      "thorax":   { "count": 1 },
      "abdomen":  { "count": 1 },
      "arms":     { "count": 6 },
      "legs":     { "count": 6 },
      "antennae": { "count": 2 }
    }
  }
]
```

**Правила частей:**
- `count` — часть без зон; hair применяется к части целиком (`"arms": 2` → ключ `"arms"`)
- `zones` — массив именованных зон; hair настраивается отдельно на каждую зону

**Race contract** ссылается на схему и опционально ограничивает зоны:
```json
"body_schema": "humanoid",
"body_hair_options": {
  "chest": { "hair_types": ["straight", "curly"], "colours": ["black", "brown"] },
  "arms":  { "hair_types": ["straight"] },
  "legs":  { "hair_types": ["straight", "curly"] }
}
```
Отсутствие зоны в `body_hair_options` → волос на этой зоне нет для расы.

**`character.system_body_hair`** — объект, ключи = зоны/части из body_schema:
```json
{
  "chest": { "system_hair_type": "straight", "system_density": "middle", "system_colour": "brown" },
  "arms":  { "system_hair_type": "straight", "system_density": "low",    "system_colour": "black" },
  "legs":  { "system_hair_type": "curly",    "system_density": "hairy",  "system_colour": "black" }
}
```
`system_hair_type` — ключ из таблицы `hair_type`; `system_colour` — ключ из `colour_registry`; `system_density` — ключ из `body_hair_density`.

**Валидация при загрузке мира:**
- `body_schema` должен существовать в `body_schema_registry`
- `body_hair_options.hair_types` ключи — должны существовать в таблице `hair_type`
- `body_hair_options.colours` ключи — должны существовать в `colour_registry`

**registry_dependencies:** тип `"body_schema"` — отслеживает какие расы используют какую схему.

### Таблица mouth_type (immutable base keys, N+1)
```
system_mouth_type | display_mouth_type
human_mouth       | ...
beak              | ...
mandibles         | ...
none              | ...
system_mouth_type_1 N+1
```

### Таблица lip_shape (N+1, редактируемая)
```
system_lip_shape | display_lip_shape
thin             | ...
full             | ...
wide             | ...
system_lip_shape_1 N+1
```

### Таблица teeth_type (immutable base keys, N+1)
```
system_teeth_type | display_teeth_type
human             | ...
fangs             | ...
tusks             | ...
beak              | ...
none              | ...
system_teeth_type_1 N+1
```

### Таблица jaw_shape (N+1, редактируемая)
```
system_jaw_shape | display_jaw_shape
oval             | ...
square           | ...
pointed          | ...
system_jaw_shape_1 N+1
```

### Таблица nose_type (immutable base keys, N+1)
```
system_nose_type | display_nose_type
human            | ...
snout            | ...
slits            | ...
beak             | ...
none             | ...
system_nose_type_1 N+1
```

### Таблица nose_shape (N+1, редактируемая)
```
system_nose_shape | display_nose_shape
straight          | ...
hooked            | ...
flat              | ...
system_nose_shape_1 N+1
```

### Таблица ear_type (immutable base keys, N+1)
```
system_ear_type | display_ear_type
human           | ...
pointed         | ...
animal          | ...
none            | ...
system_ear_type_1 N+1
```

### Таблица ear_shape (N+1, редактируемая)
```
system_ear_shape | display_ear_shape
round            | ...
oval             | ...
large            | ...
small            | ...
system_ear_shape_1 N+1
```

### Таблица genitals_type (immutable base keys, N+1)
```
system_genitals_type | display_genitals_type
human_male           | ...
human_female         | ...
none                 | ...
system_genitals_type_1 N+1
```

### Таблица breast_type (immutable base keys, N+1)
```
system_breast_type | display_breast_type
human              | ...
multiple           | ...   (несколько пар — фэнтези)
none               | ...   (отсутствует)
system_breast_type_1 N+1
```

### Таблица breast_shape (N+1, редактируемая)
```
system_breast_shape | display_breast_shape
natural             | ...
lifted              | ...
round               | ...
teardrop            | ...
system_breast_shape_1 N+1
```

### Таблица voice_pitch (immutable base keys, N+1)
```
system_voice_pitch | display_voice_pitch
very_deep          | ...
deep               | ...
medium             | ...
high               | ...
very_high          | ...
system_voice_pitch_1 N+1
```

### Таблица voice_timbre (immutable base keys, N+1)
```
system_voice_timbre | display_voice_timbre
rough               | ...
smooth              | ...
melodic             | ...
raspy               | ...
breathy             | ...
metallic            | ...
system_voice_timbre_1 N+1
```

### Таблица body_hair_density (редактируемые веса, можно добавлять записи)
```
system_body_hair_density | display_body_hair_density | system_body_hair_weight
low                      | ...                       | 0
accurate                 | ...                       | 2
middle                   | ...                       | 4
hairy                    | ...                       | 6
fully hair               | ...                       | 8
wild dense hair          | ...                       | 10
system_body_hair_density_1 N+1
```

---

## Система времени

Всё время внутри движка строится на одной канонической единице — тике.

**1 тик = 1 час** (неизменяемая константа движка).

### `worlds.calendar` JSON

```json
{
  "hours_per_day": 24,
  "days_per_month": 30,
  "seasons": [
    { "system_season": "winter", "display_season": "Зима"  },
    { "system_season": "spring", "display_season": "Весна" },
    { "system_season": "summer", "display_season": "Лето"  },
    { "system_season": "autumn", "display_season": "Осень" }
  ],
  "months": [
    { "system_month": "month_1",  "display_month": "Фростмар", "season": "winter" },
    { "system_month": "month_2",  "display_month": "Снежень",  "season": "winter" },
    { "system_month": "month_3",  "display_month": "Оттепель", "season": "spring" },
    { "system_month": "month_N",  "display_month": "...",      "season": "..." }
  ],
  "epoch_list": [
    { "system_epoch": "age_of_gods", "display_epoch": "Эпоха Богов", "duration_years": 1000 }
  ],
  "current_epoch": { "system_epoch": "age_of_war", "display_epoch": "Эпоха Войн" },
  "start_date": { "year": 1247, "month": "month_3", "day": 15, "tick": 6 },
  "time_of_day_periods": [
    { "system_period": "early_morning", "display_period": "Раннее утро", "from_hour": 4  },
    { "system_period": "morning",       "display_period": "Утро",        "from_hour": 7  },
    { "system_period": "noon",          "display_period": "Полдень",     "from_hour": 12 },
    { "system_period": "afternoon",     "display_period": "Послеобед",   "from_hour": 13 },
    { "system_period": "evening",       "display_period": "Вечер",       "from_hour": 17 },
    { "system_period": "night",         "display_period": "Ночь",        "from_hour": 22 }
  ]
}
```

**N+1 паттерн:**
- `seasons` — массив N+1; пользователь добавляет сезоны; минимум 1
- `months` — массив N+1; пользователь добавляет месяцы; `system_month` = `"month_N"` по порядку
- `time_of_day_periods` — массив N+1; пользователь настраивает под свой `hours_per_day`; минимум 1
- `epoch_list` — массив N+1; опциональный; можно не заполнять

**Деривации (вычисляются движком, не хранятся):**
```
ticks_per_day   = hours_per_day
ticks_per_month = hours_per_day × days_per_month
ticks_per_year  = hours_per_day × days_per_month × len(months)
```

**Текущее время** хранится как `current_tick` (int, абсолютный счётчик) в состоянии сессии. Конвертация в читаемую дату вычисляется из `current_tick` + `start_date` + `calendar` при чтении.

**Если `calendar` не задан** → `display_world_date = "Ход N"`, `current_tick = turn_id`.

**Время суток** — вычисляется движком при сборке LLM-контекста, не хранится:
```
current_hour = current_tick % hours_per_day
system_time_of_day = последний period где from_hour <= current_hour
```
LLM получает `system_time_of_day` + `display_time_of_day` как готовое поле.

**Правила валидации:**
- `len(months) >= len(seasons)` — каждый сезон должен иметь хотя бы один месяц; нарушение = ошибка при сохранении
- Каждый `months[].season` должен существовать в `seasons[].system_season`
- `start_date.month` должен существовать в `months[].system_month`
- `hours_per_day >= 1`, `days_per_month >= 1`
- `time_of_day_periods`: минимум 1 период; хотя бы один с `from_hour = 0`; все `from_hour < hours_per_day`

---

## Локации и карта мира

Мир строится как **sparse grid** — ячейки существуют только там где определены. Форма мира (королевства, континенты) органически задаётся набором ячеек, без фиксированных прямоугольных границ.

### Два уровня

**Уровень 1 — `map_cells`** — сырая матрица местности:
```sql
map_cells (
  world_id,
  x, y,
  elevation,                    -- int; высота в метрах относительно уровня моря
  system_terrain,               -- ref → worlds.terrain_registry
  travel_modifier_override,     -- nullable; перекрывает terrain_registry.travel_modifier
  danger_level_override,        -- nullable; перекрывает terrain_registry.danger_level
  gap_width_override,           -- nullable int (метры); перекрывает terrain_registry.gap_width для конкретной ячейки
  temperature_base,             -- nullable int; базовая температура; заполняется нодой генерации из climate_zone + elevation
  rainfall,                     -- nullable int 0–100; влажность/осадки; заполняется нодой генерации
  location_uid                  -- nullable FK → named_locations
)
INDEX (world_id, x, y)
```

**Уровень 2 — `named_locations`** — агрегат ячеек с именем:
```sql
named_locations (
  location_uid,
  world_id,
  parent_location_uid,          -- nullable FK → named_locations (self-ref дерево)
  location_type,                -- ref → worlds.location_type_registry.system_type
  location_subtype,             -- nullable; ref → location_type_registry[type].subtypes
  display_name,                 -- "Тёмный лес", "Хребет Дракона", "Столица"
  system_terrain,               -- доминирующий тип местности
  system_description,
  display_description,
  glossary_ref,                 -- nullable; расширенный лор из lore_registry
  tag_refs,                     -- JSON array; ссылки на tag_registry
  is_discovered,                -- bool; скрыта до исследования
  is_accessible,                -- bool; управляется движком через события
  interior_width,               -- nullable int; ширина внутренней сетки (только has_map_cells=false)
  interior_height,              -- nullable int; высота внутренней сетки
  entry_difficulty,             -- nullable int 0–100; сложность физического препятствия входа (стены, засов)
  guard_level,                  -- nullable int 0–100; охраняемость (стража, ловушки, барьер)
  system_location_mood,         -- nullable text; LLM-нарратив атмосферы локации на основе активных location_states
  display_location_mood,        -- "Город охватила паника. На улицах пусто, двери заперты."
                                -- все NPC в локации получают это поле в контексте сцены
  owner_uid,                    -- nullable FK → character_sheet (NPC или игрок); персональный владелец
                                -- фракционное влияние — отдельно в location_faction_influence
                                -- null = нет ограничений (открытая местность)
                                -- движок работает с int; LLM получает display_level из intensity_level_registry
  climate_zone                  -- nullable ref → worlds.climate_zone_registry; задаётся пользователем на уровне локации;
                                -- null = наследует от parent_location_uid ?? world default
)
```

Несколько ячеек с одним `location_uid` = одна именованная локация. LLM видит только `named_locations`, сырой матрицы не получает.

### `worlds.terrain_category_registry` (N+1)
```json
[
  { "system_category": "solid",       "display_category": "Твёрдая поверхность", "passable": true,  "jumpable": false },
  { "system_category": "liquid",      "display_category": "Жидкость",            "passable": false, "jumpable": false },
  { "system_category": "aerial",      "display_category": "Воздух",              "passable": false, "jumpable": false },
  { "system_category": "underground", "display_category": "Подземелье",          "passable": true,  "jumpable": false },
  { "system_category": "crevice",     "display_category": "Расщелина",           "passable": false, "jumpable": true  }
]
```
- `passable: false` → непроходим обычным движением без спец. способности (`terrain_access`)
- `jumpable: true` → барьер можно попытаться перепрыгнуть через jump action; дистанция — `gap_width`
- `aerial` terrain_access обходит все категории с `passable: false`, включая `crevice`

### `worlds.terrain_registry` (N+1)
```json
[
  { "system_terrain": "plains",   "glossary_ref": "terrain_plains",   "terrain_category": "solid",  "travel_modifier": 1.5, "danger_level": "none"    },
  { "system_terrain": "forest",   "glossary_ref": "terrain_forest",   "terrain_category": "solid",  "travel_modifier": 2.5, "danger_level": "medium"  },
  { "system_terrain": "swamp",    "glossary_ref": "terrain_swamp",    "terrain_category": "solid",  "travel_modifier": 4.0, "danger_level": "high"    },
  { "system_terrain": "mountain", "glossary_ref": "terrain_mountain", "terrain_category": "solid",  "travel_modifier": 5.0, "danger_level": "high"    },
  { "system_terrain": "water",    "glossary_ref": "terrain_water",    "terrain_category": "liquid",  "travel_modifier": null, "danger_level": "high",    "gap_width": null },
  { "system_terrain": "lava",     "glossary_ref": "terrain_lava",     "terrain_category": "liquid",  "travel_modifier": null, "danger_level": "extreme", "gap_width": null },
  { "system_terrain": "crevice",  "glossary_ref": "terrain_crevice",  "terrain_category": "crevice", "travel_modifier": null, "danger_level": "high",    "gap_width": 2    }
]
```
- `system_terrain` — N+1; пользователь добавляет типы
- `display_terrain` — не хранится; берётся из `lore_registry` по `glossary_ref` при чтении
- `terrain_category` — ref → `terrain_category_registry`; определяет проходимость
- `travel_modifier: null` → непроходимо (категория `passable: false`)
- `danger_level` — `none | low | medium | high | extreme`
- `gap_width` — nullable int (метры); только для категорий с `jumpable: true`; дистанция прыжка
- `travel_modifier`, `danger_level`, `gap_width` могут быть переопределены на конкретной ячейке (`map_cells.*_override`)

**Правило эффективного модификатора:**
```
effective_modifier      = travel_modifier_override ?? terrain_registry[system_terrain].travel_modifier
effective_danger_level  = danger_level_override    ?? terrain_registry[system_terrain].danger_level
```

### Точки входа в локации

**`location_entry_points`** — конкретные (x, y) точки входа/выхода на внешней карте:
```sql
location_entry_points (
  entry_uid,
  location_uid,                -- FK → named_locations (локация в которую входим)
  x, y,                        -- координаты ячейки в map_cells (точка входа)
  leads_to_uid,                -- nullable FK → named_locations (в какой district/room попадаем); null = попадаем в саму локацию
  display_name,                -- "Северные ворота", "Задний вход", "Пролом в стене"
  entry_difficulty_override,   -- nullable int 0–100; перекрывает named_locations.entry_difficulty
  guard_level_override,        -- nullable int 0–100; перекрывает named_locations.guard_level
  is_discovered,               -- bool; туман войны — игрок видит только известные точки входа
  is_accessible,               -- bool; управляется движком через события (заблокировано, обрушено и т.д.)
  glossary_ref,                -- nullable
  tag_refs                     -- nullable JSON array
)
```

**Правила effective значений:**
```
effective_entry_difficulty = entry_point.entry_difficulty_override ?? location.entry_difficulty ?? 0
effective_guard_level      = entry_point.guard_level_override      ?? location.guard_level      ?? 0
```

**Семантика:**
- `entry_difficulty` — физическое препятствие: стены, засов, узкий лаз; action-путь: climbing, lockpick
- `guard_level` — охраняемость: стража, ловушки, магический барьер; action-путь: stealth, social, combat
- `effective = 0` → обычное передвижение работает без action
- `effective > 0` → нужен action или способность; выше значение → сложнее; движок передаёт int в FormulaNode
- `leads_to_uid = null` → персонаж оказывается в самой локации (без привязки к конкретному district)

**Pathfinding:**
- При маршруте К локации — движок выбирает ближайший entry point где `is_discovered = true` AND `is_accessible = true` как целевую ячейку A*
- Если у локации несколько известных точек входа — движок передаёт игроку все варианты (с их effective difficulty/guard_level); выбор за игроком или NPC
- Если у локации нет entry points или нет известных → A* использует центроид ячеек локации (открытая территория)
- При маршруте ОТ локации — аналогично: ближайший известный entry point текущей локации как стартовая ячейка
- `is_discovered` устанавливается движком: разведка, информация от NPC, квест, способность (зависит от системы событий)

**Примеры:**

| Локация | entry_difficulty | guard_level |
|---|---|---|
| Регион / открытое поле | null | null |
| Деревня | 5 | 5 |
| Город | 40 | 60 |
| Крепость | 80 | 85 |
| Тайный вход (override) | 15 | 10 |

### `worlds.location_type_registry` (N+1)
```json
[
  {
    "system_type": "region",
    "display_type": "Регион",
    "parent_types": [null],
    "has_map_cells": true,
    "subtypes": []
  },
  {
    "system_type": "territory",
    "display_type": "Территория",
    "parent_types": ["region"],
    "has_map_cells": true,
    "subtypes": [
      { "system_subtype": "island",   "display_subtype": "Остров",           "border_category": "liquid" },
      { "system_subtype": "mountain", "display_subtype": "Горная местность", "border_category": null     },
      { "system_subtype": "coastal",  "display_subtype": "Побережье",        "border_category": null     }
    ]
  },
  {
    "system_type": "settlement",
    "display_type": "Поселение",
    "parent_types": ["territory"],
    "has_map_cells": true,
    "subtypes": [
      { "system_subtype": "city",    "display_subtype": "Город",      "border_category": null },
      { "system_subtype": "village", "display_subtype": "Деревня",    "border_category": null },
      { "system_subtype": "dungeon", "display_subtype": "Подземелье", "border_category": null }
    ]
  },
  {
    "system_type": "district",
    "display_type": "Район",
    "parent_types": ["settlement"],
    "has_map_cells": false,
    "subtypes": []
  },
  {
    "system_type": "room",
    "display_type": "Помещение",
    "parent_types": ["district", "settlement"],
    "has_map_cells": false,
    "subtypes": []
  }
]
```
- `system_type` — immutable ключ движка; `display_type` — редактируемое имя (пользователь может переименовать "Поселение" → "Крепость-форт"); N+1 паттерн: пользователь добавляет свои типы
- `parent_types: [null]` — тип может быть корнем без родителя
- `subtypes` — N+1 внутри типа; пользователь добавляет подтипы
- `border_category` — nullable; если задан, граничные ячейки локации должны быть этой категории
- `has_map_cells: false` — тип существует только логически, не имеет ячеек в `map_cells`

**Правила валидации:**
- `named_locations.parent.location_type` обязан входить в `child.location_type_registry.parent_types`
- `location_subtype` обязан существовать в `location_type_registry[location_type].subtypes`
- При размещении локации с `border_category`: граничные ячейки матрицы должны иметь `terrain_category = border_category`; при AI-генерации — движок авто-заполняет граничные ячейки

**Генерация vs загрузка мира:**
- Оба варианта дают одну структуру данных в БД
- **Генерация:** world seed → дефолтный `location_type_registry` → AI генерирует `named_locations` + `map_cells`
- **Загрузка:** импорт-файл → валидация → populate `named_locations` + `map_cells`

### `worlds.road_type_registry` (N+1)
```json
[
  { "system_road_type": "royal_road", "glossary_ref": "road_royal",   "travel_modifier": 0.8 },
  { "system_road_type": "common_road","glossary_ref": "road_common",  "travel_modifier": 1.0 },
  { "system_road_type": "trail",      "glossary_ref": "road_trail",   "travel_modifier": 1.3 },
  { "system_road_type": "pass",       "glossary_ref": "road_pass",    "travel_modifier": 1.8 }
]
```
- `system_road_type` — N+1; пользователь добавляет типы
- `display_road_type` — не хранится; берётся из `lore_registry` по `glossary_ref`
- `travel_modifier` — множитель к `base_ticks_per_cell`; < 1.0 = быстрее базы (мощёная дорога), > 1.0 = медленнее

### Дороги (`roads`)
Явные рёбра между `named_locations` поверх матрицы:
```sql
roads (
  road_uid,
  world_id,
  display_name,                 -- "Королевский тракт"
  road_type,                    -- ref → worlds.road_type_registry
  travel_modifier_override,     -- nullable; перекрывает road_type.travel_modifier
  from_location,                -- FK → named_locations
  to_location,                  -- FK → named_locations
  is_bidirectional,             -- bool
  danger_level,                 -- none | low | medium | high | extreme
  glossary_ref,                 -- nullable; лор дороги из lore_registry; нет ссылки = нет лора
  tag_refs                      -- nullable JSON array; ссылки на tag_registry
)
```

**Правило effective modifier для дороги:**
```
effective_modifier = travel_modifier_override ?? road_type_registry[road_type].travel_modifier
```

### Проходимость и доступ к местности

`passable: false` на `terrain_category` — дефолт для всех. Персонаж может преодолеть его через три источника:

**1. Раса** — врождённая способность; два уровня с фолбеком:
```
effective_terrain_access = gender.terrain_access ?? race_traits.terrain_access ?? []
```
- `race_traits.terrain_access` — дефолт для всей расы
- `gender.terrain_access` — опциональный override для конкретного пола

**2. Перк / способность** — приобретённая; в схеме перка:
```json
"terrain_access": ["liquid", "aerial"]
```

**3. Экипировка / транспорт** — пока предмет экипирован; в `item.properties`:
```json
"terrain_access": ["liquid"]
```

**Движок агрегирует перед патфайндингом:**
```
character_terrain_access = union(
    race.terrain_access,
    active_perks[].terrain_access,
    equipped_items[].terrain_access
)
can_traverse(category) = category.passable OR category IN character_terrain_access
```
Маршрутный отчёт учитывает возможности персонажа — путь через непроходимый terrain показывается только если персонаж имеет доступ.

**Прыжок через расщелину:**

Для ячеек с `terrain_category.jumpable = true` доступно jump action:
```
effective_gap_width = map_cells.gap_width_override ?? terrain_registry[system_terrain].gap_width
jump_result         = jump_formula(character_stats)   -- динамическая формула из worlds.action_formulas
```
- `jump_formula = null` → jump action отключено в мире
- `jump_result >= effective_gap_width` → персонаж перепрыгивает
- `jump_result < effective_gap_width` → движок генерирует **assessment event**: *"персонаж оценивает прыжок как невозможный"*; попытка всё равно доступна
- Попытка при недостаточном `jump_result` → падение → `fall_formula` (урон; в worlds.action_formulas)
- NPC принимает решение о попытке через `system_npc_goal` + `system_traits` (desperate/reckless → может прыгнуть вопреки оценке)
- `aerial` terrain_access → обходит расщелину без прыжка

**TODO — Магия:**
Магический доступ к местности (воздушная магия, хождение по воде) — это **действие**, не пассивное свойство персонажа. Не может быть записано в `terrain_access` как перк. Требует проектирования системы магии и системы активных действий. Отложено.

### Привязка персонажа
`character.system_location` → ссылается на `named_locations.location_uid`. Конкретная ячейка персонажу не нужна — он "в локации".

### Маршрутный отчёт движка

Движок всегда считает **оба варианта** и передаёт LLM готовый отчёт. LLM не навигирует граф самостоятельно.

```json
{
  "direct": {
    "terrain_sequence": ["plains", "forest", "swamp"],
    "description":      "Через Туманный лес и Болото Теней",
    "danger_level":     "high",
    "travel_ticks":     24
  },
  "road": {
    "waypoints":        ["Деревня", "Перекрёсток", "Столица"],
    "road_names":       ["Королевский тракт"],
    "description":      "По Королевскому тракту через Перекрёсток",
    "danger_level":     "low",
    "travel_ticks":     16
  }
}
```

- `danger_level` маршрута = максимальный по всем сегментам пути
- Прямой путь — A* по `map_cells` с terrain модификаторами
- Путь по дороге — поиск по графу `roads` между `named_locations`
- Отчёт используется и для анализа поведения NPC: какой маршрут выбрал NPC, почему, какова была опасность

### Динамика мира

Мир нестатичен — города разрушаются, территории меняются, катаклизмы меняют рельеф.

**`location_states`** — активные состояния локации (несколько одновременно):
```sql
location_states (
  id,
  location_uid,          -- FK → named_locations ON DELETE CASCADE
  system_state,          -- "destroyed" | "besieged" | "abandoned" | "plague" | ...
  display_state,
  system_description,
  display_description,
  need_modifiers,        -- nullable JSON; как состояние влияет на потребности NPC в локации
                         -- формат: { "safety": 50, "social": -30, "hunger": 10 }
                         -- движок применяет к system_current_needs всех NPC в локации
  created_at
)
```
`system_state` — N+1; пользователь и движок добавляют типы состояний.

При изменении активных `location_states` → `named_locations.system_location_mood` помечается для перегенерации нодой актуализации.

### Владение и влияние фракций

**`location_faction_influence`** — распределение влияния фракций в локации:
```sql
location_faction_influence (
  id,
  location_uid,   -- FK → named_locations ON DELETE CASCADE
  faction_uid,    -- FK → factions (система фракций — будущее; placeholder)
  influence,      -- int 0–100; доля влияния фракции
  created_at
)
INDEX (location_uid)
```

**Правило суммы:** `SUM(influence) WHERE location_uid = X = 100` если записи есть; `COUNT(*) = 0` → локация независима.

**Правило перераспределения (вариант C):**
- **Явное событие** (война, захват, сделка) → движок/LLM указывает получателя напрямую; победитель получает нужную долю, проигравший теряет
- **Постепенное угасание** (чума, запустение, вакуум власти) → потеря перераспределяется пропорционально среди оставшихся фракций
- Валидация после любого изменения: `SUM = 100`; нарушение = ошибка

**Для LLM:** `influence` конвертируется через `intensity_level_registry` → `"extreme dominance"` / `"low presence"` и т.д.

### Отношения между фракциями (скетч)

> Детальный контракт — при проектировании системы фракций. Ниже — структура данных для резервирования.

**`worlds.faction_relation_type_registry`** (N+1):
```json
[
  { "system_relation": "hostile",   "display_relation": "Враждебные",   "is_hostile": true,  "glossary_ref": "rel_hostile"   },
  { "system_relation": "neutral",   "display_relation": "Нейтральные",  "is_hostile": false, "glossary_ref": "rel_neutral"   },
  { "system_relation": "tolerant",  "display_relation": "Толерантные",  "is_hostile": false, "glossary_ref": "rel_tolerant"  },
  { "system_relation": "allied",    "display_relation": "Союзники",     "is_hostile": false, "glossary_ref": "rel_allied"    }
]
```

**`faction_relations`** — глобальные отношения (двунаправленные):
```sql
faction_relations (
  faction_a_uid,    -- FK → factions
  faction_b_uid,    -- FK → factions
  system_relation,  -- ref → worlds.faction_relation_type_registry
  PRIMARY KEY (faction_a_uid, faction_b_uid)
)
```
Запись одна на пару; движок ищет по обоим направлениям. Нет записи → нейтральные по умолчанию.

**Отношения — drift-система:** `system_relation` не меняется мгновенно; события сдвигают отношение постепенно. Drift определяется двумя факторами (детали при проектировании системы фракций):
- `trust` — уровень доверия между фракциями (числовой показатель, drift по событиям)
- Отношения между предводителями фракций — персональный фактор поверх институционального доверия

**`location_faction_access`** — локальный запрет/разрешение (перекрывает глобальное отношение):
```sql
location_faction_access (
  location_uid,   -- FK → named_locations ON DELETE CASCADE
  faction_uid,    -- FK → factions
  is_allowed,     -- bool; false = фракция запрещена в локации
  PRIMARY KEY (location_uid, faction_uid)
)
```
`is_hostile = true` между фракциями в одной локации → конфликт (event system, отложено).
Запрещённая фракция (`is_allowed = false`) → NPC фракции-хозяина реагируют враждебно независимо от глобального отношения.

**`world_history`** — лог событий мира (параллельно `character_history`):
```sql
world_history (
  id,
  world_id,
  location_uid,          -- nullable; событие глобальное или привязано к локации
  system_world_date,
  display_world_date,
  system_event_type,     -- "war" | "cataclysm" | "founding" | "destruction" | ...
  display_event_type,
  system_description,
  display_description,
  created_at
)
```
`system_event_type` — N+1.

**Мутация terrain** — катаклизм может изменить `map_cells.system_terrain` напрямую (лес → пепелище). Это мутация карты, фиксируется в `world_history`.

**Снапшот** захватывает `location_states` + актуальные `map_cells` — при откате времени откатывается и состояние мира.

**Последствия событий** (NPC вытеснены, дороги перекрыты, `is_accessible = false`) — логика движка/событийной системы; отложено до проектирования системы событий.

### Ресурсы локаций

**`worlds.resource_type_registry`** (N+1):
```json
[
  { "system_resource": "iron_ore", "glossary_ref": "res_iron_ore", "is_renewable": false, "base_regen_per_tick": null, "default_yield": 10, "yield_item_uid": "item_iron_ore", "tag_refs": ["tag_mineral"] },
  { "system_resource": "timber",   "glossary_ref": "res_timber",   "is_renewable": true,  "base_regen_per_tick": 5,    "default_yield": 5,  "yield_item_uid": "item_log",      "tag_refs": ["tag_natural"] }
]
```
- `display_*` не хранится; берётся из `lore_registry` по `glossary_ref`
- `is_renewable: false` — невозобновляемый; `quantity` только убывает
- `is_renewable: true` — возобновляемый; `quantity` регенерирует до `max_quantity`
- `default_yield` — константа добычи за одно действие когда формулы нет
- `yield_item_uid` — ref → items; сырой предмет за одно действие добычи; обработка (руда → слиток) — в системе крафта

**`location_resources`**:
```sql
location_resources (
  id,
  location_uid,         -- FK → named_locations ON DELETE CASCADE
  system_resource,      -- ref → worlds.resource_type_registry
  quantity,             -- int; текущий запас
  max_quantity,         -- int; ёмкость (невозобновляемый = размер месторождения; возобновляемый = предел регенерации)
  regen_override,       -- nullable int; перекрывает base_regen_per_tick для этой локации
  is_discovered,        -- bool; игрок не знает о ресурсе до исследования
  is_accessible         -- bool; управляется движком
)
```

**Добыча:**
- Каждый NPC/игрок вычисляет честно и индивидуально: `yield = extract_formula ?? default_yield`
- `extract_formula` — в `action_formulas` мира; если null → используется `default_yield`
- `quantity -= yield` после каждого действия добычи; `quantity` не уходит ниже 0
- Агрегация добычи per tick (batch по всем NPC) — оптимизация, отложено

**TODO — будущее:**
- Инструмент как обязательное условие действия добычи (кирка для руды, удочка для рыбы)
- Магическое действие добычи (альтернативный способ без инструмента)
- Добыча требует постройки: для каждого типа ресурса — своя постройка (шахта, лесопилка, ферма); `building_type_registry` (N+1) в worlds; каждый тип постройки ссылается на `system_resource` который добывает; детальный контракт — при проектировании системы построек

**TODO — нода генерации мира:**
При процедурной генерации нода должна вычислять для каждого ресурса:
- `spawn_chance` — вероятность появления ресурса в локации (зависит от типа terrain/location, редкости ресурса)
- `max_quantity` — зависит от: редкости ресурса, типа спавна, количества прилегающих локаций с тем же ресурсом (жила может тянуться через несколько локаций)
- Логика генерации — в ноде; контракт данных (`quantity`, `max_quantity`) остаётся без изменений
- Если игрок создаёт мир вручную — заполняет `location_resources` напрямую без ноды генерации

### Версионирование карты

`worlds.world_map_version` = `hash(terrain_category_registry + terrain_registry + road_type_registry + location_type_registry)`

При переименовании типов → `registry_migrations` применяет маппинг к `map_cells`, `roads`, `named_locations` в одной транзакции → пересчитывается `world_map_version`.

### Внутренние пространства (interior)

Локации с `has_map_cells: false` (district, room) не имеют terrain-сетки. Навигация — через логические связи и локальную сетку объектов.

**`location_connections`** — логические переходы между interior-локациями:
```sql
location_connections (
  connection_uid,
  world_id,
  from_location,       -- FK → named_locations
  to_location,         -- FK → named_locations
  is_bidirectional,    -- bool
  connection_type,     -- ref → worlds.connection_type_registry
  is_locked,           -- bool; управляется движком через события
  display_name,        -- "Дубовая дверь", "Винтовая лестница"
  glossary_ref,        -- nullable
  tag_refs             -- nullable JSON array
)
```

**`worlds.connection_type_registry`** (N+1):
```json
[
  { "system_type": "door",      "display_type": "Дверь"    },
  { "system_type": "corridor",  "display_type": "Коридор"  },
  { "system_type": "staircase", "display_type": "Лестница" },
  { "system_type": "portal",    "display_type": "Портал"   }
]
```
Нет `travel_ticks` — interior-переходы не имеют временной стоимости (логические).

**`location_objects`** — статические объекты с позицией; источник истины для LLM:
```sql
location_objects (
  object_uid,
  location_uid,        -- FK → named_locations ON DELETE CASCADE
  display_name,        -- "Дубовый сундук", "Факел на стене"
  x, y,                -- позиция в локальной сетке
  z,                   -- nullable int; высота объекта (платформа, ступени)
  system_description,
  display_description,
  is_interactive,      -- bool; можно взаимодействовать
  item_uid,            -- nullable FK → items; объект содержит предмет
  is_accessible        -- bool; управляется движком
)
```

**Локальная сетка** — `interior_width` / `interior_height` на `named_locations`; если оба `null` → нет сетки, только нарратив.

LLM получает объекты как факты: `"chest at (3,1,0), torch at (0,2,1), door at (5,0,0)"` — консистентность гарантирована данными, не памятью LLM.

**Высоты:**
- Exterior — `map_cells.elevation` (int, метры над уровнем моря)
- Interior — `location_objects.z` (относительная высота внутри локации)
- Логика подъёма/спуска влияет на передвижение и бой — расчёт через action-ноды; отложено

**Боевая система** — персонажи получат позиции `(x, y, z)` внутри локации во время сцены; interior grid станет основой тактического боя.

### Климат и погода

**Принцип:** пользователь задаёт `climate_zone` на уровне `named_locations`; нода генерации вычисляет `temperature_base` и `rainfall` для каждой `map_cells` автоматически. Пользователь никогда не редактирует параметры ячеек вручную.

**Никаких ограничений на климат.** Система поддерживает любой сеттинг — реалистичный, фэнтезийный, sci-fi, абсурдный:
- `base_temperature` — без ограничений: -200°C (космическая станция), +500°C (вулканический мир), 0 (вечная мерзлота)
- `rainfall` — 0–100, но смысл задаёт мир: 0 = безводная пустыня / вакуум; 100 = постоянный ливень / кислотные осадки
- `elevation_lapse_rate` — может быть отрицательным (чем выше — тем теплее), нулевым (высота не влияет), экстремальным
- `season_temp_offsets` — все нули = мир без сезонов; экстремальные значения = мир с убийственными зимами
- `weather_type_registry` — N+1; пользователь создаёт любые типы погоды: кислотный дождь, радиационный шторм, магические бури, нулевая гравитация, пылевые смерчи
- `climate_zone_registry` — N+1; любое количество зон с любыми параметрами; лорная зона с уникальным микроклиматом — просто ещё одна запись

Движок не знает о "реалистичности" — он обрабатывает параметры. Смысл задаёт пользователь через `glossary_ref` и `display_*`.

---

**`worlds.climate_zone_registry`** (N+1):
```json
[
  { "system_climate": "arctic",    "base_temperature": -25, "temperature_variance": 8,  "base_rainfall": 20, "rainfall_variance": 10, "glossary_ref": "climate_arctic"    },
  { "system_climate": "tundra",    "base_temperature": -5,  "temperature_variance": 10, "base_rainfall": 30, "rainfall_variance": 15, "glossary_ref": "climate_tundra"    },
  { "system_climate": "temperate", "base_temperature": 12,  "temperature_variance": 8,  "base_rainfall": 55, "rainfall_variance": 20, "glossary_ref": "climate_temperate" },
  { "system_climate": "desert",    "base_temperature": 30,  "temperature_variance": 12, "base_rainfall": 10, "rainfall_variance": 5,  "glossary_ref": "climate_desert"    },
  { "system_climate": "tropical",  "base_temperature": 28,  "temperature_variance": 5,  "base_rainfall": 80, "rainfall_variance": 15, "glossary_ref": "climate_tropical"  }
]
```
`display_*` — из `lore_registry` по `glossary_ref`. `climate_zone` — метка для LLM; движок погоды использует `temperature_base` и `rainfall` напрямую.

**Наследование / перезапись `climate_zone`:**

Механизм рекурсивного обхода вверх по дереву `parent_location_uid`:
```
resolve_climate(location):
  if location.climate_zone != null → return location.climate_zone   -- явная перезапись
  if location.parent_location_uid != null → return resolve_climate(parent)
  return worlds.default_climate_zone                                 -- фолбек мира
```
- **Регион** (верхний уровень дерева) задаёт климат — все вложенные локации наследуют его автоматически
- **Локация** с явным `climate_zone` перезаписывает родительский климат для себя и своих детей
- Нода генерации вызывает `resolve_climate()` для каждой локации перед вычислением параметров ячеек

---

**Нода генерации — вычисление параметров ячейки:**
```
temperature_base = zone.base_temperature
                 + elevation_lapse_rate × (elevation / 100)     -- высота охлаждает
                 + Σ(neighbor_zone.base_temperature × w(dist))  -- влияние соседних зон
                 + random(±zone.temperature_variance)

rainfall         = zone.base_rainfall
                 + Σ(neighbor_zone.base_rainfall × w(dist))
                 + random(±zone.rainfall_variance)
```
`w(dist)` — убывающий вес по расстоянию (в пределах `neighbor_blend_radius`).

**Вертикальный климат:** тропическая зона у подножия горы → при высоком `elevation` ячейки вершины получают арктические параметры несмотря на `climate_zone = tropical`. `climate_zone` остаётся меткой локации, параметры ячеек отражают реальный климат.

---

**`worlds.season_temp_offsets`** — сдвиг температуры по сезонам:
```json
{ "spring": 3, "summer": 12, "autumn": -2, "winter": -18 }
```
`effective_temperature = map_cells.temperature_base + season_temp_offsets[current_season]`

---

**`worlds.weather_type_registry`** (N+1) — условия через параметры, порядок по `priority`:
```json
[
  { "system_weather": "blizzard",  "temp_max": -5,  "temp_min": null, "rainfall_min": 60, "priority": 1, "travel_modifier": 3.0, "need_modifiers": {"warmth": 70}, "glossary_ref": "weather_blizzard" },
  { "system_weather": "snow",      "temp_max": 0,   "temp_min": null, "rainfall_min": 20, "priority": 2, "travel_modifier": 2.0, "need_modifiers": {"warmth": 40}, "glossary_ref": "weather_snow"     },
  { "system_weather": "fog",       "temp_max": 15,  "temp_min": null, "rainfall_min": 70, "priority": 3, "travel_modifier": 1.5, "need_modifiers": {},             "glossary_ref": "weather_fog"      },
  { "system_weather": "rain",      "temp_max": 25,  "temp_min": null, "rainfall_min": 40, "priority": 4, "travel_modifier": 1.3, "need_modifiers": {"warmth": 10}, "glossary_ref": "weather_rain"     },
  { "system_weather": "heat_wave", "temp_max": null,"temp_min": 35,   "rainfall_min": null,"priority":5, "travel_modifier": 1.5, "need_modifiers": {"thirst": 40}, "glossary_ref": "weather_heat"     },
  { "system_weather": "clear",     "temp_max": null,"temp_min": null, "rainfall_min": null,"priority":99,"travel_modifier": 1.0, "need_modifiers": {},             "glossary_ref": "weather_clear"    }
]
```
Движок перебирает по `priority` → первое совпадение = текущая погода. `clear` — фолбек (priority 99).
`need_modifiers` — тот же формат что `location_states.need_modifiers`; аддитивны.

---

**`location_weather`** — текущая погода локации:
```sql
location_weather (
  location_uid,    -- FK → named_locations ON DELETE CASCADE
  system_weather,  -- ref → worlds.weather_type_registry
  intensity,       -- int 0–100; через intensity_level_registry → "light rain" / "heavy storm"
  remaining_ticks  -- через сколько тиков пересчитать погоду
)
```
`intensity` масштабирует эффекты: `effective_modifier = 1 + (travel_modifier - 1) × intensity / 100`

**Пересчёт погоды per tick:**
```
effective_temp = map_cells.temperature_base + season_temp_offsets[season]  -- среднее по ячейкам локации
system_weather = первый weather_type где (effective_temp в диапазоне AND rainfall >= rainfall_min)
intensity      = насколько параметры выражены внутри диапазона правила (0–100)
remaining_ticks = random(weather_duration_min..weather_duration_max)       -- из weather_type_registry
```

---

**`map_settings` (отложено) — параметры ноды генерации:**
```json
{
  "elevation_lapse_rate": -0.65,    -- температура на 100м подъёма; дефолт реальный мир
  "neighbor_blend_radius": 3,       -- радиус ячеек влияния соседней зоны
  "default_climate_zone": "temperate"
}
```

### Открытые вопросы (отложены)
- `map_settings` (масштаб ячейки, 4-directional vs 8-directional, `base_ticks_per_cell`, `elevation_lapse_rate`, `neighbor_blend_radius`) — отложено
- Туман войны (fog of war) — `is_discovered` на ячейках vs только на `named_locations` — отложено

---

## Открытые риски (низкий приоритет)

- **Битый JSON в `character_states.effects`** — невалидный JSON в колонке effects → статус не считается, ошибка без явной причины; решение: валидация структуры при записи
- **Race contract без валидации при сохранении** — невалидный контракт можно сохранить, ошибка всплывёт только при загрузке мира; решение: валидировать при сохранении расы
- **Импорт персонажа с чужими ключами реестра** — `colour_registry`/`muscle_table` из другого мира могут отсутствовать в текущем; resolution flow не определён
- **`character_unique_perks` при миграции alias** — inline snapshot содержит формулы (`system_condition`, `system_rank_value`); миграция alias должна сканировать и эти данные

---

## Открытые темы
- **`ticks_per_turn`** — сколько тиков продвигается время за один ход; решение отложено: зависит от удалённости игрока и типа вычисления тика (бой = детально, путешествие = агрегированно)
- Специальные поля players и npcs (декларация мира)
- Подсумки и рюкзаки (контейнерная механика)
- Локации — map_settings (масштаб ячейки, направленность движения); fog of war на уровне ячеек
- Состояние игровой сессии (state пайплайна)
- Квесты / события
- Крафт
- **Магия как действие** — магический доступ к местности (воздушная магия и т.п.) требует системы активных действий + системы магии; отложено до их проектирования
- **Система последствий событий** — логика движка: разграбленный город → NPC вытеснены, дороги перекрыты, `is_accessible = false`; требует проектирования событийной системы
- Синхронизация событий между таймлайнами (последняя очередь)
- Путешествие в будущее (последняя очередь)
- World Lore и Tag Registry — детальное проектирование
- **Фракции** — полный контракт (скетч есть: `faction_relations`, `location_faction_access`, `faction_relation_type_registry`; детали: структура самой таблицы `factions`, экономика фракций, дипломатия)

---

## Архитектурные замечания

### `meta: dict` в Session — неявный контракт
Сейчас `Session.meta` несёт `world_uid` и `character_id` как неструктурированный словарь. При росте нод это становится неявным контрактом — нода ожидает ключ которого нет и падает в рантайме без явной ошибки. **Решение:** ввести типизированный `SessionContext` dataclass когда количество нод потребует явной структуры.

### DSL как файлы — динамические промпты
Промпты живут в `app/dsl/` как `.txt` файлы. Открытый вопрос: нужны ли динамические промпты на уровне мира — когда пользователь меняет поведение движка без релиза кода. Если да → хранение в БД. **Решение:** принимать при необходимости.

### Семантика уровней логов → node_execution_logs

DEBUG-логи — внутренний шум движка (SQL-запросы, HTTP-запросы к LLM, детали пайплайна). Они полезны при разработке но бессмысленны в игровом контексте.

INFO-логи — значимые игровые события: результат IntentDetection, вычисления формул, симуляции NPC, итоги боевых действий. Это естественные кандидаты для `node_execution_logs`.

**Практическое правило:** если нода пишет INFO — это то, что стоит сохранять в `node_execution_logs`. Если DEBUG — только для разработчика, в БД не идёт.

Следствие: логи ошибок (`ERROR`) намеренно не сохраняются — ошибки транзиентны, история чата остаётся чистой нарративной записью.
