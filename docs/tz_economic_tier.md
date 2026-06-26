# ТЗ: economic_tier — реестр, резолв, утилиты

Отдельное доменное ТЗ. Базовое описание реестра и полей — в [tz_locations.md](tz_locations.md) §«Экономические уровни»; использование в генерации города — [tz_city_generation.md](tz_city_generation.md); semantic-first — [tz_assembler_hierarchy.md](tz_assembler_hierarchy.md) §1.1.

---

## 1. Два уровня абстракции

Мастер и генератор работают с **двумя разными понятиями**. Их нельзя смешивать в одной функции.

| Понятие | Источник | Python-модуль | Когда |
|---|---|---|---|
| **`system_tier`** | `worlds.economic_tier_registry[]` — конкретное имя тира мира (`"standard"`, `"premium"`, …) | `generators/utils/tierRegistry.py` | Сравнения, поля записи registry, fallback материалов по `base_value` |
| **`economic_tier_band`** | Абстрактная 5-ступенчатая шкала: `poor` → `common` → `middle` → `wealthy` → `rich` | `generators/utils/economicTierBands.py` | Шаблоны и дефолты, не зависящие от числа тиров в мире |

**Зависимость:** `economicTierBands` использует `tierRegistry.tiers_sorted`; обратной зависимости нет.

---

## 2. `tierRegistry` — примитивы реестра

Модуль: `backend/app/application/worldData/generators/utils/tierRegistry.py`

| Функция | Назначение |
|---|---|
| `tiers_sorted(registry)` | Единый порядок по `base_value` ASC |
| `tier_entry(registry, system_tier)` | Запись тира; неизвестный → `None` |
| `tier_rank(registry, system_tier)` | Ordinal-индекс; null / неизвестный → **0** |
| `tier_at_least` / `tier_at_most` | Условия «не беднее / не богаче» |
| `median_system_tier(registry)` | Медианный тир; пустой registry → `None` |

**Не делает:** не мапит N тиров в bands, не выбирает материалы.

---

## 3. `economicTierBands` — нормализация N → 5

Модуль: `backend/app/application/worldData/generators/utils/economicTierBands.py`

Формула (не менять без явного решения):

```
sorted by base_value ASC:
  index 0           → poor
  1 .. median-1     → common
  median            → middle      // median = (n-1) // 2
  median+1 .. n-2   → wealthy
  n-1               → rich
N=1 → middle; N=2 → poor, rich
```

| Функция | Назначение |
|---|---|
| `tier_band_map(world)` | Все `system_tier` → band |
| `band_of(world, system_tier)` | Один тир → band; неизвестный → `None` |
| `tiers_for_band(world, band)` | Обратный маппинг: band → список `system_tier` |

**Не делает:** не сравнивает два `system_tier` напрямую, не читает поля registry.

Band — **входной язык намерения** в шаблонах. Перед резолвом материалов/дорог band разворачивается в конкретный `system_tier` (см. §5).

---

## 4. `TierResolver` — каскад effective tier

Модуль: `backend/app/application/worldData/generators/utils/tierResolver.py`

Порядок (от частного к общему):

```
room_tier  →  building.system_economic_tier  →  district.system_economic_tier  →  city.system_economic_tier
```

Если на всех уровнях `null` → `median_system_tier(world.economic_tier_registry)` + **WARNING** в лог (см. [tz_locations.md](tz_locations.md), поле `named_locations.system_economic_tier`).

Explicit `system_tier` на более глубоком уровне **перебивает** наследование с родителя.

---

## 5. Кейсы мастера

### 5.1 Только `system_tier` (ref → registry)

Мастер задаёт конкретные имена: город `"standard"`, район `economic_tier_range: {min, max}`, здание `"premium"`.

```
TierResolver → effective system_tier → tierRegistry (материалы, placement, поля registry)
```

`economicTierBands` не участвует, пока правило явно привязано к `system_tier`.

### 5.2 Только `economic_tier_band`

Мастер задаёт намерение: `"economic_tier_band": "wealthy"` (поле в шаблонах — **запланировано**, в JSON пока не стандартизовано).

```
economic_tier_band
  → tiers_for_band(world, band)
  → выбор одного system_tier (rng / центр band / пересечение с parent)
  → tierRegistry для всех последующих правил
```

Исключение: чисто band-дефолты (например ширина тротуара), если в registry нет per-tier полей — достаточно `band_of` без materialize.

### 5.3 Смешанный: город = tier, район = band, здание = tier

| Уровень | Значение |
|---|---|
| Город | `system_economic_tier: "standard"` |
| Район | `economic_tier_band: "wealthy"` |
| Здание | `system_economic_tier: "premium"` |

Правила:

1. Explicit `system_tier` сильнее band на том же и более глубоком уровне → здание `"premium"` побеждает band района.
2. Band района разворачивается только если у здания tier не задан; опционально clamp ±1 от tier города ([tz_city_generation.md](tz_city_generation.md), `building_tier_compatible` в `plan_area_placements`).
3. Tier города — якорь для `placement_conditions` (`economic_tier_min` / `economic_tier_max`).
4. После получения одного `system_tier` — только `tierRegistry`.

### 5.4 `system_tier` отсутствует в registry мира

Пример: в шаблоне `"luxury"`, в `economic_tier_registry` такого `system_tier` нет.

---

## 6. Валидация при import — **намеренно отложена**

> **Решение (v1):** жёсткая проверка ref `system_economic_tier` ↔ `economic_tier_registry` при JSON-import **не включена**.

**Причина:** отказоустойчивость и проверка fallback-цепочек на практике — генератор должен деградировать предсказуемо, а не падать на первом битом ref.

**Целевое поведение (будущий validator, тот же для UI редактора миров):**

- `system_economic_tier` в `NamedLocation`, `economic_tier` в `material_registry`, `tier` в `placement_conditions`, `economic_tier_range.min/max` — все ref должны существовать в `worlds.economic_tier_registry`.
- `economic_tier_band` — ref в фиксированный enum `{poor, common, middle, wealthy, rich}`.
- Ошибка import с понятным сообщением; без silent fix.

**До включения validator:** см. §7.

---

## 7. Runtime fallback (текущее поведение)

При неизвестном или отсутствующем `system_tier`:

| Компонент | Поведение |
|---|---|
| `tier_entry` | `None` — поля registry недоступны |
| `tier_rank` | **0** (как самый бедный) — сравнения `tier_at_least` / `tier_at_most` могут дать ложный результат |
| `band_of` | `None` |
| `TierResolver`, все null | `median_system_tier` + WARNING |
| `materialResolver` | нет кандидатов по tier → fallback вниз по `base_value` → любой подходящий материал → hard default + WARNING |
| `sidewalkWidthResolver` | нет полей в entry → hardcoded default по имени / `_DEFAULT_WIDTH = 2` |

**Важно:** rank=0 для неизвестного tier — осознанный компромисс v1; после включения validator битые ref не должны доходить до генератора.

---

## 8. Где что используется (код, v1)

| Место | Утилита |
|---|---|
| `settlementAssembler._build_skeleton` | `TierResolver.resolve(city=…)` |
| `planner/placement.py` | `tier_at_least`, `tier_at_most` |
| `materialResolver.py` | `median_system_tier`, `tiers_sorted`, fallback вниз |
| `sidewalkWidthResolver.py` | `tier_entry` + `band_of` fallback |
| `structureGeneratorService.py` | `TierResolver.resolve(world, building, band, rng)` |
| `economicTierBands.py` | `materialize_band`, `band_of` в sidewalk fallback |

Соседи (не дублировать):

- `TierResolver` — только каскад «откуда взять tier».
- `materialResolver` — выбор материала + fallback.
- `economicTierBands` — только N→5 bands; формула §3 не сливать с `tier_rank`.

---

## 9. Связанные поля в данных

| Поле | Где | Тип ref |
|---|---|---|
| `worlds.economic_tier_registry[]` | World N+1 | источник истины |
| `named_locations.system_economic_tier` | локация | → `system_tier` |
| `building_template_registry[].economic_tier_range` | шаблон здания | `{min, max}` → `system_tier` |
| `district_template_registry[].economic_tier_range` | шаблон района | `{min, max}` → `system_tier` |
| `district_template_registry[].placement_conditions` | `{type: economic_tier_min/max, tier}` | → `system_tier` |
| `economic_tier_band` | шаблон города/района/здания | → band enum (§3) — **planned** |
| `rooms[].economic_tier` | шаблон здания | → `system_tier` (override комнаты) |
| `material_registry[].economic_tier` | World N+1 | → `system_tier` |

---

## 10. Roadmap

1. Подключить `economicTierBands` в `sidewalkWidthResolver` (fallback через `band_of`, не по raw имени tier).
2. Реализовать разворот `economic_tier_band` в `TierResolver` / отдельном `BandResolver`.
3. `plan_area_placements` / `buildingCache`: `economic_tier_range` + ±1 через `building_tier_compatible` и `tier_rank`.
4. **Validator** при import и в редакторе миров (§6) — после стабилизации fallback-тестов.
5. При включении validator: рассмотреть `tier_rank(unknown) → -1` или явный `is_known_tier()`, чтобы сравнения не маскировали битые ref.
