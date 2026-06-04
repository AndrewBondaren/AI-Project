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
economic_tier → display_tier из item_value_tier_registry,
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

## 9. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Алгоритм сетки улиц — простая сетка или органичнее (Voronoi кварталы)? | открыт |
| Типы кварталов — как определяется тип (distance от центра, explicit в шаблоне города?) | открыт |
| Шаблон города — нужен ли аналог building_template для городов? | открыт |
| `dominant_material` авто-вычисление — из economic_tier или explicit обязателен? | открыт |
| Regeneration — если скелет изменился после генерации, перегенерировать город? | открыт |
