# ТЗ: Генератор города

## 1. Scope

Генератор города строит наполнение поселения — здания, улицы, районы — из скелета города.  
Скелет генерируется **при создании мира** для всех поселений сразу. Детали (интерьеры, планировки) — **lazy**, при первом посещении игроком.

---

## 2. Принцип: Skeleton-first

### Проблема

Если LLM описывает город до того как он сгенерирован — она фантазирует.  
Если описание появилось раньше геометрии — они расходятся. Игрок входит и иллюзия рушится.

### Решение

```
Мир создан → скелет всех городов (instant)
LLM описывает → только из скелета (ограничена данными)
Игрок входит в город → генерируются здания (lazy)
Игрок входит в здание → генерируется интерьер (lazy, через BuildingGeneratorService)
Описание совпадает с геометрией ✓
```

**Инвариант движка:** LLM никогда не получает данные которых нет. Скелет — минимум гарантированных данных о любом поселении.

---

## 3. Скелет города (CitySkeletonFields)

Скелет хранится на `NamedLocation` поселения. Большинство полей уже существует.

| Поле | Тип | Откуда | Описание |
|---|---|---|---|
| `economic_tier` | string | `system_economic_tier` на `NamedLocation` | Общий экономический уровень → материалы, плотность, тип зданий |
| `system_location_mood` | string | уже есть | Атмосфера: `prosperous`, `declining`, `militarized`, `mysterious`, etc. |
| `display_location_mood` | string | уже есть | Человекочитаемый аналог для LLM |
| `system_city_size` | string | уже есть | ref → `city_size_registry`; определяет radius и плотность |
| `dominant_material` | string | новое | ref → `worlds.material_registry`; главный строительный материал города |
| `architectural_style` | string | новое | ref → `worlds.architectural_style_registry` (N+1); визуальный стиль |
| `settlement_density` | string | новое | `sparse` / `medium` / `dense`; как плотно стоят здания |
| `state_uid` | string | уже есть | Государство → политический контекст для LLM |

**Что LLM получает из скелета:**
- `display_location_mood` → тон описания
- `dominant_material` → из чего построено ("мраморные стены", "деревянные дома")
- `economic_tier` → богатство ("ухоженные фасады" vs "облупившаяся штукатурка")
- `architectural_style` → визуальный язык ("готические арки", "плоские крыши")
- `system_city_size` → масштаб

---

## 4. Реестры (N+1 в `worlds`)

### `worlds.architectural_style_registry`

```json
[
  { "system_style": "medieval_stone",  "glossary_ref": "style_medieval_stone"  },
  { "system_style": "nordic_wood",     "glossary_ref": "style_nordic_wood"     },
  { "system_style": "mediterranean",   "glossary_ref": "style_mediterranean"   },
  { "system_style": "cyberpunk",       "glossary_ref": "style_cyberpunk"       },
  { "system_style": "brutalist",       "glossary_ref": "style_brutalist"       }
]
```

`display_*` и описание стиля — из `lore_registry` по `glossary_ref`.

### `worlds.location_mood_registry`

```json
[
  { "system_mood": "prosperous",   "display_mood": "Процветающий"   },
  { "system_mood": "declining",    "display_mood": "Приходящий в упадок" },
  { "system_mood": "militarized",  "display_mood": "Милитаризованный" },
  { "system_mood": "mysterious",   "display_mood": "Таинственный"   },
  { "system_mood": "dangerous",    "display_mood": "Опасный"        },
  { "system_mood": "abandoned",    "display_mood": "Заброшенный"    }
]
```

---

## 5. Фазы генерации

### Фаза 1 — World creation (eager)

Для каждого поселения в `locations[]` мирового JSON:
- Валидируется скелет (обязательные поля)
- Вычисляется `dominant_material` если не задан явно (из `economic_tier` + `material_registry`)
- Скелет сохраняется на `NamedLocation`

Результат: все поселения имеют скелет. LLM может описывать любой город сразу.

### Фаза 2 — City entry (lazy)

При первом входе игрока в поселение:
- `CityGeneratorService.generate_layout(world, city)` — строит здания по улицам
- Читает скелет (`economic_tier`, `architectural_style`, `settlement_density`, `dominant_material`)
- Выбирает шаблоны зданий из `building_template_registry` по `structure_type` и `economic_tier`
- Размещает здания на `map_cells` города
- Создаёт `NamedLocation` для каждого здания (без интерьера)

### Фаза 3 — Building entry (lazy)

При первом входе в конкретное здание:
- `BuildingGeneratorService.generate_from_template(world, building, template)`
- Полный интерьер: комнаты, ячейки, проходы

---

## 6. Алгоритм размещения зданий (v1)

### 6.1 Входные данные

- `city.map_x, map_y` — origin города на глобальной карте
- `city_size_registry[city.system_city_size].radius` — радиус в map_cells
- `settlement_density` → плотность застройки
- `building_template_registry` — доступные шаблоны

### 6.2 Сетка улиц

```
city_footprint = квадрат radius×radius вокруг origin
главная улица  = горизонтальная или вертикальная полоса через центр (rng)
вторичные улицы = перпендикулярные ответвления; количество зависит от city_size
кварталы = прямоугольные блоки между улицами
```

### 6.3 Заполнение кварталов

```
для каждого квартала:
    тип квартала: residential / commercial / civic / mixed
        (зависит от distance от центра: центр → commercial/civic, периферия → residential)
    
    для каждого слота в квартале:
        выбрать шаблон из building_template_registry
            фильтр: structure_type совместим с типом квартала
            фильтр: economic_tier совместим с city.economic_tier (±1 тир)
        разместить здание → NamedLocation (без интерьера)
        mark slot занятым
```

### 6.4 Особые объекты

Civic-здания (ратуша, храм, рынок) — размещаются в центре, обязательно при `city_size >= town`.

---

## 7. Интеграция с LLM

**До генерации (только скелет):**

LLM получает:
```
display_name, display_description, display_location_mood,
dominant_material → display_name из material_registry,
architectural_style → lore_registry[glossary_ref],
economic_tier → display_tier из economic_tier_registry,
state → display_name из states
```

LLM **не получает**: список зданий, планировку улиц, интерьеры.

**После генерации:**

LLM дополнительно получает список `NamedLocation` зданий с их `display_name`, `system_location_type`.

**Инвариант:** описание LLM всегда согласовано с данными. "Мраморные здания" → только если `dominant_material` указывает на мрамор.

---

## 8. Режим полной инициализации (Eager World Bake)

Опциональный режим — пользователь явно запускает его до начала игры.

### Триггер

UI-кнопка "Инициализировать мир" на странице мира. Запускается вручную, не автоматически.

### Что происходит

```
для каждого поселения в мире:
    CityGeneratorService.generate_layout(world, city)       -- фаза 2
    для каждого здания в городе:
        BuildingGeneratorService.generate_from_template(...)  -- фаза 3
```

Всё записывается через `executemany` в одной транзакции на поселение.

### UX

- Прогресс-бар: "Город 3 из 12 — Айронхолд (здание 47 из 120)"
- По завершении: сводка — сколько городов, зданий, ячеек сгенерировано
- Если мир уже частично сгенерирован (игрок посещал часть городов) — пропустить уже сгенерированные, сгенерировать только оставшиеся

### Когда уместно

- Пользователь хочет "запечь" мир до начала игры
- Нужен полный экспорт мира с геометрией
- Тестирование и отладка шаблонов — проверить все здания сразу

### Ограничение

Полная инициализация большого мира может занять десятки секунд. Пользователь предупреждается об этом до запуска.

---

## 9. Шаблоны районов (`district_template_registry`)

Район — шаблон. `CityAssembler` размещает шаблоны районов на позиции глобальных ячеек города,
проверяя условия появления. `DistrictAssembler` получает уже выбранный шаблон.

### 9.1 Хранение

Аналогично `building_templates` — глобальная таблица шаблонов, не привязанная к конкретному миру.
Per-world реестр: `worlds.district_template_registry` (JSON-массив, как `building_template_registry`).

### 9.2 Схема шаблона района

| Поле | Тип | Обязательность | Описание |
|---|---|---|---|
| `system_name` | string | required | Уникальный ключ: `"port_district"`, `"merchant_quarter"` |
| `display_name` | string | required | Отображаемое название |
| `district_type` | string | required | Семантический тип: `"residential"`, `"commercial"`, `"civic"`, `"military"`, `"port"`, `"industrial"` и др. (N+1) |
| `placement_conditions` | array | optional | Условия появления района (см. 9.3). Пустой массив = всегда доступен |
| `max_per_city` | int | optional | Максимальное количество районов этого типа в одном городе. `null` = без ограничений |
| `size_pct` | object | optional | Диапазон размера района как доля глобальной ячейки: `{ "width": [0.3, 1.0], "depth": [0.3, 1.0] }`. `1.0` = вся ячейка |
| `allowed_structure_types` | string[] | optional | `structure_type` из `building_template`, допустимые в этом районе. `null` = без ограничений |
| `economic_tier_range` | object | optional | `{ "min": "poor", "max": "exceptional" }` — диапазон тиров зданий в районе |
| `density` | string | optional | `"sparse"`, `"medium"`, `"dense"`. Переопределяет `city_skeleton.settlement_density` для этого района |
| `required_structures` | array | optional | Особые обязательные постройки (ратуша, храм, рынок) — см. 9.4 |

### 9.3 Условия появления (`placement_conditions`)

Каждое условие — объект с полем `type`. `CityAssembler` проверяет все условия до размещения.
Все условия должны быть выполнены (AND-логика).

| `type` | Параметры | Описание |
|---|---|---|
| `adjacent_terrain` | `terrain_types: string[]`, `min_count: int` | Смежная с ячейкой города terrain-ячейка должна иметь один из указанных `system_terrain`. Пример: порт требует `["liquid_body"]` |
| `min_city_size` | `size: string` | ref → `city_size_registry.system_size`; город не меньше указанного размера |
| `economic_tier_min` | `tier: string` | Минимальный `system_economic_tier` города |
| `economic_tier_max` | `tier: string` | Максимальный `system_economic_tier` города |
| `requires_district_type` | `district_type: string` | В городе уже должен быть район указанного типа |
| `excludes_district_type` | `district_type: string` | В городе НЕ должно быть района указанного типа |

Пример — шаблон портового района:
```json
{
  "system_name": "port_district",
  "display_name": "Портовый район",
  "district_type": "port",
  "max_per_city": 1,
  "placement_conditions": [
    { "type": "adjacent_terrain", "terrain_types": ["liquid_body"], "min_count": 1 },
    { "type": "min_city_size", "size": "town" }
  ],
  "allowed_structure_types": ["warehouse", "tavern", "shop", "guild"],
  "density": "dense"
}
```

### 9.4 Обязательные особые постройки (`required_structures`)

Civic-постройки (ратуша, рынок, храм) объявляются в шаблоне района:

```json
"required_structures": [
  { "building_template": "town_hall",  "count": 1, "position": "center" },
  { "building_template": "market",     "count": 1, "position": "any"    }
]
```

`position`:
- `"center"` — размещается ближе к геометрическому центру района
- `"any"` — произвольная позиция

### 9.5 Алгоритм размещения районов (`CityAssembler`)

```
для каждой позиции глобальной ячейки города:
    кандидаты = [t for t in district_template_registry
                 if _check_conditions(t, cell_position, city, terrain)]
    
    отсортировать кандидаты по приоритету (специализированные > общие)
    
    выбрать шаблон (rng или детерминированный выбор)
    
    DistrictSlot(
        origin_x = cell_x * cell_size_m + offset,
        origin_y = cell_y * cell_size_m + offset,
        width_m  = width_pct  * cell_size_m,
        depth_m  = depth_pct  * cell_size_m,
        ground_z = terrain_z_at(cell_x, cell_y),
        district_template = выбранный шаблон,
    )
```

`cell_size_m` читается из `world.map_settings["global_cell_size_m"]`.

---

## 10. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Алгоритм сетки улиц — простая сетка или органичнее (Voronoi кварталы)? | открыт |
| Размещение нескольких районов в одной глобальной ячейке — разбиение на sub-cells | открыт |
| `dominant_material` авто-вычисление — из economic_tier или explicit обязателен? | открыт |
| Regeneration — если скелет изменился после генерации, перегенерировать город? | открыт |
| Механика дорог внутри района и между районами | нет ТЗ |
| `adjacent_terrain` — проверка связанности (река должна куда-то выходить) | не описано |
