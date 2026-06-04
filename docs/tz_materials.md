# ТЗ: Материалы

## 1. Scope

`material_registry` — единый реестр всех материалов мира. Используется одновременно:
- физикой локаций (течение, горение, замерзание)
- генератором зданий (выбор по `use_type`, `economic_tier`)
- `ExcavationNode` (добыча по `hardness`, `mineable`)

---

## 2. Структура записи

```json
{
  "system_material":    "water",
  "display_name":       "Вода",
  "glossary_ref":       null,
  "material_category":  "liquid",
  "tags":               [],
  "use_type":           [],
  "economic_tier":      null,
  "hardness":           null,
  "density":            100,
  "structural_strength": null,
  "flammable":          false,
  "freeze_temp":        0,
  "melt_temp":          null,
  "boil_temp":          100,
  "corrodible":         false,
  "mineable":           false,
  "transparent":        false,
  "temp_damage":        false,
  "vision_block":       false,
  "components":         null
}
```

| Поле | Тип | Кто использует | Описание |
|---|---|---|---|
| `system_material` | string | все | Уникальный ключ |
| `display_name` | string | LLM, UI | Отображаемое название |
| `glossary_ref` | string\|null | LLM | nullable; ref → `lore_registry`; лор-описание |
| `material_category` | string | физика | Физическое состояние: `solid`, `liquid`, `gas` |
| `tags` | string[] | генератор зданий | Классификация: `construction`, `metal`, `crafted`, `refined`, `raw`, `organic`, `consumable`, `mineral`, `magic` + кастомные |
| `use_type` | string[] | генератор зданий | `wall`, `floor`, `column`, `door`, `gate`, `railing`, `ceiling`, `roof`, `any` |
| `economic_tier` | string\|null | генератор зданий | ref → `item_value_tier_registry`; null для liquid/gas |
| `hardness` | int (1–5)\|null | ExcavationNode | Твёрдость; null для liquid/gas |
| `density` | int | физика | Плотность; слоение жидкостей, плавучесть твёрдых |
| `structural_strength` | float (0–1)\|null | физика | Прочность конструкции; null для liquid/gas |
| `flammable` | bool | физика | Горит при контакте с огнём. Default: false |
| `freeze_temp` | int\|null | физика | Температура замерзания °C; null = не замерзает |
| `melt_temp` | int\|null | физика | Температура плавления °C; null = не плавится |
| `boil_temp` | int\|null | физика | Температура кипения °C; null = не испаряется |
| `corrodible` | bool | физика | Поддаётся коррозии/кислоте. Default: true |
| `mineable` | bool | физика | Добывается инструментом. Default: false |
| `transparent` | bool | физика | Не блокирует видимость. Default: false |
| `breakable` | bool | физика | Разрушается от удара (стекло, хрупкие материалы). Используется для состояния `broken` у окон. Default: false |
| `temp_damage` | bool | физика | только liquid/gas. Наносит температурный урон при контакте |
| `vision_block` | bool | физика | только liquid/gas. Блокирует видимость |
| `components` | string[]\|null | крафт | Компоненты для `crafted`/`refined` материалов |

`material_category` фиксирован в движке. `tags` расширяются через `worlds.material_tag_registry` (N+1).

---

## 3. Дефолты при создании пользователем

| Поле | Default |
|---|---|
| `flammable` | false |
| `breakable` | false |
| `corrodible` | true |
| `mineable` | false |
| `transparent` | false |
| `freeze_temp` | null |
| `melt_temp` | null |
| `boil_temp` | null |
| `glossary_ref` | null |
| `components` | null |

В БД все поля хранятся явно — пустых значений нет.

---

## 4. Температурная система

### 4.1 Данные vs состояние

**Данные** (в `material_registry`) — пороги конкретного материала:
```
freeze_temp, melt_temp, boil_temp
```

**Состояние** (runtime, не хранится в материале) — температура ячейки:
```
cell_temperature = climate_zone.base_temperature
                 + weather_modifier
                 + terrain_modifier
                 + local_heat_modifier  -- от огня, лавы рядом
```

### 4.2 Переходы состояний

```
если cell_temperature <= material.freeze_temp:
    liquid → solid (вода → лёд)

если cell_temperature >= material.melt_temp:
    solid → liquid (лёд → вода, железо → расплав)

если cell_temperature >= material.boil_temp:
    liquid → gas (вода → пар)
```

Переход создаёт новую ячейку с целевым `system_material` (определяется через `components` или конфигурацию движка).

### 4.3 Тепловые источники (v1)

Ячейки с `temp_damage: true` (лава, огонь) дают локальный модификатор соседним ячейкам:

```
для каждой ячейки с system_terrain = "fire" или system_material = "lava":
    соседи в радиусе 1 → local_heat_modifier += heat_radius_1
    соседи в радиусе 2 → local_heat_modifier += heat_radius_2
```

Конкретные значения `heat_radius_*` — конфигурация движка.

### 4.4 Полная теплопередача (v2)

Каждый тик симуляции температура распространяется между ячейками по градиенту. Отложено.

---

## 5. Физика жидкостей

### 5.1 Гравитационное течение (v1)

Жидкость течёт вниз по z при каждом тике. Слоение: более плотная жидкость опускается ниже.

### 5.2 Давление (v2)

Давление — **формула**, не данные. Вычисляется в рантайме из высоты столба жидкости над ячейкой:

```
pressure(cell) = sum(density * height for fluid_cells above)
```

При давлении > 0 жидкость может течь вверх (затопление снизу, трубы). Отложено.

---

## 6. Физика газов

Газ движется по z в зависимости от `density` относительно окружения:
- `density` газа > `density` окружающего воздуха → оседает вниз
- `density` газа < `density` окружающего воздуха → поднимается вверх

`vision_block: true` → ячейка непроходима для линии обзора.  
`temp_damage: true` → урон персонажам в ячейке каждый тик.

---

## 7. Пример реестра

```json
[
  { "system_material": "stone",     "display_name": "Камень",        "glossary_ref": null, "material_category": "solid",  "tags": ["construction", "mineral"], "use_type": ["wall", "floor", "column"],          "economic_tier": "standard", "hardness": 3, "density": 250, "structural_strength": 0.8,  "flammable": false, "freeze_temp": null, "melt_temp": 1600, "boil_temp": null, "corrodible": true,  "mineable": true,  "transparent": false, "components": null },
  { "system_material": "wood",      "display_name": "Дерево",        "glossary_ref": null, "material_category": "solid",  "tags": ["construction", "organic"],  "use_type": ["wall", "floor", "door", "railing"],  "economic_tier": "basic",    "hardness": 2, "density": 60,  "structural_strength": 0.3,  "flammable": true,  "freeze_temp": null, "melt_temp": null,  "boil_temp": null, "corrodible": true,  "mineable": false, "transparent": false, "components": null },
  { "system_material": "iron",      "display_name": "Железо",        "glossary_ref": null, "material_category": "solid",  "tags": ["metal", "mineral"],         "use_type": ["wall", "door", "gate", "railing"],   "economic_tier": "standard", "hardness": 4, "density": 800, "structural_strength": 0.9,  "flammable": false, "freeze_temp": null, "melt_temp": 1538, "boil_temp": null, "corrodible": true,  "mineable": false, "transparent": false, "components": null },
  { "system_material": "earth",     "display_name": "Земля",         "glossary_ref": null, "material_category": "solid",  "tags": ["raw", "mineral"],           "use_type": ["floor"],                             "economic_tier": "junk",     "hardness": 1, "density": 150, "structural_strength": 0.2,  "flammable": false, "freeze_temp": null, "melt_temp": null,  "boil_temp": null, "corrodible": true,  "mineable": true,  "transparent": false, "components": null },
  { "system_material": "water",     "display_name": "Вода",          "glossary_ref": null, "material_category": "liquid", "tags": [],                           "use_type": [],                                    "economic_tier": null,       "hardness": null, "density": 100, "structural_strength": null, "flammable": false, "freeze_temp": 0,    "melt_temp": 0,     "boil_temp": 100,  "corrodible": false, "mineable": false, "transparent": false, "temp_damage": false, "vision_block": false, "components": null },
  { "system_material": "lava",      "display_name": "Лава",          "glossary_ref": null, "material_category": "liquid", "tags": [],                           "use_type": [],                                    "economic_tier": null,       "hardness": null, "density": 270, "structural_strength": null, "flammable": false, "freeze_temp": 700,  "melt_temp": 700,   "boil_temp": null, "corrodible": false, "mineable": false, "transparent": false, "temp_damage": true,  "vision_block": false, "components": null },
  { "system_material": "air",       "display_name": "Воздух",        "glossary_ref": null, "material_category": "gas",    "tags": [],                           "use_type": [],                                    "economic_tier": null,       "hardness": null, "density": 1,   "structural_strength": null, "flammable": false, "freeze_temp": null, "melt_temp": null,  "boil_temp": null, "corrodible": false, "mineable": false, "transparent": true,  "temp_damage": false, "vision_block": false, "components": null },
  { "system_material": "toxic_gas", "display_name": "Токсичный газ", "glossary_ref": null, "material_category": "gas",    "tags": [],                           "use_type": [],                                    "economic_tier": null,       "hardness": null, "density": 3,   "structural_strength": null, "flammable": true,  "breakable": false, "freeze_temp": null, "melt_temp": null,  "boil_temp": null, "corrodible": false, "mineable": false, "transparent": false, "temp_damage": true,  "vision_block": true,  "components": null },
  { "system_material": "glass",     "display_name": "Стекло",        "glossary_ref": null, "material_category": "solid",  "tags": ["crafted", "mineral"],       "use_type": ["window"],                            "economic_tier": "basic",    "hardness": 1,    "density": 250, "structural_strength": 0.1,  "flammable": false, "breakable": true,  "freeze_temp": null, "melt_temp": 700,   "boil_temp": null, "corrodible": false, "mineable": false, "transparent": true,  "components": null }
]
```

---

## 8. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Давление жидкостей (затопление снизу, трубы) | v2 |
| Полная теплопередача между ячейками | v2 |
| Конкретные значения `heat_radius_*` для тепловых источников | открыт |
| Целевой материал при переходе состояний (вода→лёд, железо→расплав) — конфиг движка или поле реестра? | открыт |
| Структурная целостность — обрушение стен без опоры | нет ТЗ |
