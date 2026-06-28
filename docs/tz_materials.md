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
  "heat_conductivity":  0.1,
  "viscosity":          null,
  "heat_into":          null,
  "heat_temp":          null,
  "cool_into":          null,
  "cool_temp":          null,
  "structural_strength": null,
  "flammable":          false,
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
| `use_type` | string[] | генератор зданий, дороги | `wall`, `floor`, `column`, `door`, `gate`, `railing`, `ceiling`, `roof`, `road`, `any` |
| `economic_tier` | string\|null | генератор зданий | ref → `economic_tier_registry`; null для liquid/gas |
| `hardness` | int (1–5)\|null | ExcavationNode | Твёрдость; null для liquid/gas |
| `density` | int | физика | Плотность; слоение жидкостей, плавучесть твёрдых |
| `heat_conductivity` | float (0.0–1.0) | физика | Тепловая проводимость; 0.0 = не проводит (фиксированный источник тепла), 1.0 = мгновенная передача |
| `viscosity` | float (0.0–1.0)\|null | физика | Вязкость. Только для `material_category: "liquid"`. Скорость течения: 0.0 = мгновенно, 1.0 = почти не течёт. null для solid/gas |
| `heat_into` | string\|null | физика | ref → `system_material`; во что переходит при нагреве выше `heat_temp`. null = не реагирует на жар |
| `heat_temp` | int\|null | физика | Порог нагрева (в единицах engine temperature); null если `heat_into` не задан |
| `cool_into` | string\|null | физика | ref → `system_material`; во что переходит при охлаждении ниже `cool_temp`. null = не реагирует на холод |
| `cool_temp` | int\|null | физика | Порог охлаждения (в единицах engine temperature); null если `cool_into` не задан |
| `structural_strength` | float (0–1)\|null | физика | Прочность конструкции; null для liquid/gas |
| `flammable` | bool | физика | Горит при контакте с огнём. Default: false |
| `corrodible` | bool | физика | Поддаётся коррозии/кислоте. Default: true |
| `mineable` | bool | физика | Добывается инструментом. Default: false |
| `transparent` | bool | физика | Не блокирует видимость. Default: false |
| `breakable` | bool | физика | Разрушается от удара (хрупкие материалы). Переводит ячейку в состояние `broken`. Default: false |
| `temp_damage` | bool | физика | только liquid/gas. Наносит температурный урон при контакте |
| `vision_block` | bool | физика | только liquid/gas. Блокирует видимость |
| `components` | string[]\|null | крафт | Компоненты для `crafted`/`refined` материалов |

`material_category` фиксирован в движке. `tags` расширяются через `worlds.material_tag_registry` (N+1).

---

## 3. Дефолты при создании пользователем

| Поле | Default | Логика |
|---|---|---|
| `flammable` | `false` | только явно горючие материалы горят |
| `corrodible` | `true` | большинство материалов поддаются коррозии |
| `mineable` | `false` | только явно добываемые добываются |
| `transparent` | `false` | материал непрозрачен по умолчанию |
| `breakable` | `false` | только хрупкие разрушаются от удара |
| `heat_conductivity` | `0.1` | воздух — базовый уровень конвекции |
| `viscosity` | `null` | только liquid-материалы имеют вязкость |
| `heat_into` | `null` | |
| `heat_temp` | `null` | |
| `cool_into` | `null` | |
| `cool_temp` | `null` | |
| `glossary_ref` | `null` | |
| `components` | `null` | |

В БД все поля хранятся явно — пустых значений нет.

---

## 4. Физика по категориям

> **Пустая ячейка (нет блока)** — движок использует запись `air` из `material_registry`. Это правило движка, не поле реестра. Поскольку `material_registry` хранится per-world, свойства воздуха (плотность, проводимость, вязкость) настраиваются на уровне мира.

| `material_category` | Физика движка |
|---|---|
| `solid` | падает если `g > 0` и нет опоры снизу; всплывает если `density < liquid.density`; горит если `flammable`; переходит в другой материал если `cool_into` задан; разрушается кислотой если `corrodible`; переходит в другой материал если `heat_into` задан; добывается если `mineable`; блокирует обзор если `transparent: false` |
| `liquid` | течёт вниз по z; слоение: более плотная жидкость опускается ниже; утопание; температурный урон если `temp_damage`; блокирует видимость если `vision_block` |
| `gas` | движение по z определяется `density` относительно соседей: тяжелее → оседает вниз, легче → поднимается; блокирует видимость если `vision_block`; токсичность если `temp_damage` |

### 4.1 Переходы между состояниями материалов

Каждый материал несёт два ref-поля:

| Материал | `heat_into` | `cool_into` |
|---|---|---|
| `iron_ore` | `molten_iron` | null |
| `molten_iron` | null | `iron` |
| `iron` | `molten_iron` | null |
| `wood` | `charcoal` | null |
| `charcoal` | `ash` | null |
| `ash` | null | null |
| `water` | `steam` | `ice` |
| `steam` | `superheated_steam` | `water` |
| `lava` | null | `stone` |

Движок читает `heat_into`/`cool_into`, находит целевой материал в `material_registry` и заменяет ячейку. Целевой материал должен существовать в реестре — движок не создаёт его автоматически.

Температурный порог, при котором происходит переход — открытый вопрос (см. секцию 8).

---

### 4.2 Тепловая диффузия (v1)

Каждый тик симуляции для каждой ячейки `C`:

```
delta = Σ (neighbor.temperature - C.temperature) × neighbor.material.heat_conductivity × dt
C.temperature += delta
```

`dt` — конфигурационный параметр мира (хранится в `world` наряду с `material_registry`). Позволяет замедлить или ускорить теплообмен для конкретного мира.

Ячейки с `temp_damage: true` (лава, огонь) — **фиксированные источники тепла**:
- их `temperature` не обновляется диффузией (они задают температуру, а не получают)
- всегда излучают в соседей через формулу выше
- `heat_conductivity: 0.0` означает, что ячейка не поглощает тепло от соседей — только отдаёт

---

## 5. Физика жидкостей

### 5.1 Гравитационное течение (v1)

Жидкость течёт вниз по z при каждом тике. Слоение: более плотная жидкость опускается ниже.

Скорость течения обратно пропорциональна `viscosity`: вода (`viscosity: 0.1`) течёт быстро, лава (`viscosity: 0.9`) — медленно. Конкретная формула (тики на шаг) — конфигурация движка.

### 5.2 Переход solid → liquid

Когда ячейка достигает порога нагрева, движок читает `heat_into` и заменяет материал. Целевой материал (например, `molten_iron`) — отдельная запись в реестре с `material_category: "liquid"` и своим `viscosity`. Обратный переход: `cool_into` при охлаждении ниже порога.

### 5.3 Давление (v2)

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

`vision_block: true` → блокирует линию обзора.  
`temp_damage: true` → урон персонажам в ячейке каждый тик.

---

## 7. Пример реестра

```json
[
  { "system_material": "stone",     "display_name": "Камень",        "glossary_ref": null, "material_category": "solid",  "tags": ["construction", "mineral"],  "use_type": ["wall", "floor", "column"],          "economic_tier": "standard", "hardness": 3,    "density": 250, "heat_conductivity": 0.4, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": 0.8,  "flammable": false, "corrodible": true,  "mineable": true,  "transparent": false, "components": null },
  { "system_material": "wood",      "display_name": "Дерево",        "glossary_ref": null, "material_category": "solid",  "tags": ["construction", "organic"],  "use_type": ["wall", "floor", "door", "railing"], "economic_tier": "basic",    "hardness": 2,    "density": 60,  "heat_conductivity": 0.2, "viscosity": null, "heat_into": "charcoal", "heat_temp": 150,  "cool_into": null,  "cool_temp": null, "structural_strength": 0.3,  "flammable": true,  "corrodible": true,  "mineable": false, "transparent": false, "components": null },
  { "system_material": "iron",      "display_name": "Железо",        "glossary_ref": null, "material_category": "solid",  "tags": ["metal", "mineral"],         "use_type": ["wall", "door", "gate", "railing"],  "economic_tier": "standard", "hardness": 4,    "density": 800, "heat_conductivity": 0.9, "viscosity": null, "heat_into": "molten_iron", "heat_temp": 200,  "cool_into": null,  "cool_temp": null, "structural_strength": 0.9,  "flammable": false, "corrodible": true,  "mineable": false, "transparent": false, "components": null },
  { "system_material": "earth",     "display_name": "Земля",         "glossary_ref": null, "material_category": "solid",  "tags": ["raw", "mineral"],           "use_type": ["floor"],                            "economic_tier": "poor",     "hardness": 1,    "density": 150, "heat_conductivity": 0.3, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": 0.2,  "flammable": false, "corrodible": true,  "mineable": true,  "transparent": false, "components": null },
  { "system_material": "crystal",   "display_name": "Кристалл",      "glossary_ref": null, "material_category": "solid",  "tags": ["mineral", "magic"],         "use_type": ["wall", "floor"],                    "economic_tier": "premium",  "hardness": 3,    "density": 260, "heat_conductivity": 0.2, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": 0.4,  "flammable": false, "corrodible": false, "mineable": false, "transparent": true,  "components": null },
  { "system_material": "water",     "display_name": "Вода",          "glossary_ref": null, "material_category": "liquid", "tags": [],                           "use_type": [],                                   "economic_tier": null,       "hardness": null, "density": 100, "heat_conductivity": 0.5, "viscosity": 0.1, "heat_into": "steam",       "heat_temp": 100,  "cool_into": "ice", "cool_temp": 0, "structural_strength": null, "flammable": false, "corrodible": false, "temp_damage": false, "vision_block": false, "components": null },
  { "system_material": "lava",      "display_name": "Лава",          "glossary_ref": null, "material_category": "liquid", "tags": [],                           "use_type": [],                                   "economic_tier": null,       "hardness": null, "density": 270, "heat_conductivity": 0.0, "viscosity": 0.9, "heat_into": null,        "heat_temp": null,  "cool_into": "stone", "cool_temp": 50, "structural_strength": null, "flammable": false, "corrodible": false, "temp_damage": true,  "vision_block": false, "components": null },
  { "system_material": "air",       "display_name": "Воздух",        "glossary_ref": null, "material_category": "gas",    "tags": [],                           "use_type": [],                                   "economic_tier": null,       "hardness": null, "density": 1,   "heat_conductivity": 0.1, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": null, "flammable": false, "corrodible": false, "temp_damage": false, "vision_block": false, "components": null },
  { "system_material": "smoke",     "display_name": "Дым",           "glossary_ref": null, "material_category": "gas",    "tags": [],                           "use_type": [],                                   "economic_tier": null,       "hardness": null, "density": 2,   "heat_conductivity": 0.05, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": null, "flammable": false, "corrodible": false, "temp_damage": false, "vision_block": true,  "components": null },
  { "system_material": "toxic_gas", "display_name": "Токсичный газ", "glossary_ref": null, "material_category": "gas",    "tags": [],                           "use_type": [],                                   "economic_tier": null,       "hardness": null, "density": 3,   "heat_conductivity": 0.05, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": null, "flammable": true,  "corrodible": false, "temp_damage": true,  "vision_block": true,  "components": null }
]
```

---

## 7.1 Climate: `precipitation_liquid`

`World.precipitation_liquid` → запись в `material_registry` с `material_category: "liquid"`.

Генератор климата использует **`cool_temp` / `heat_temp`** (и наличие `cool_into` / `heat_into`) как **фазовую полосу** жидких осадков:

- `temp` внутри полосы → `liquid_mult ≈ 1`
- ниже `cool_temp` или выше `heat_temp` → `liquid_mult = 0` (снег/град — runtime через `weather_type_registry`)
- outer 10% полосы — smoothstep (как tier temp blend)

Fallback: `water` → первый `liquid` в registry → built-in `{ cool_temp: 0, heat_temp: 100 }`.  
При fallback — `logger.warning` (once per world); каждый расчёт — `logger.debug`. См. [`tz_climate.md`](./tz_climate.md) § precipitation.

Не привязывать к 0°C / 100°C на уровне движка — только к полям материала.

---

## 8. Открытые вопросы

| Вопрос | Статус |
|---|---|
| Температурные пороги переходов (`heat_temp`/`cool_temp`) — per-material поля | закрыт |
| Целевой материал при переходе (`heat_into`/`cool_into`) — ref-поля на записи | закрыт |
| Пример реестра неполный: `charcoal`, `ash`, `molten_iron`, `steam`, `ice`, `superheated_steam` упомянуты в `heat_into`/`cool_into` но отсутствуют в примере — добавить или вынести в отдельное приложение? | открыт |
| `breakable` — поле есть в таблице, но отсутствует в JSON-схеме и примере реестра; уточнить семантику и добавить | открыт |
| `flammable` + `heat_into`: при воспламенении движок применяет `heat_into` для определения продукта или отдельная логика? | открыт |
| `dt` (шаг диффузии) per-world — поле не добавлено в модель `World` и миграцию | открыт |
| Формула скорости течения через `viscosity` — конкретные тики на шаг | открыт |
| Давление жидкостей (затопление снизу, трубы) | v2 |
| Структурная целостность — обрушение стен без опоры | нет ТЗ |
