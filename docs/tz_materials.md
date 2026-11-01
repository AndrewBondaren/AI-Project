# ТЗ: Материалы

**Граница домена:** Materials владеет material identity, свойствами, defaults/validation, refs и принятием изменений свойств через будущий публичный Materials contract. Физические законы, формулы, процессы и соответствие `свойство → формула/эффект` принадлежат отдельному [ТЗ Physics](./tz_physics.md). Изменение material property может быть результатом Physics, но Physics не мутирует `WorldMaterialRegistry` или состояние размещённого вещества напрямую. Точные typed mutation API, scope и revision semantics — OPEN; это не разрешение на код.

## 1. Scope

`material_registry` — единый **Materials-owned** реестр определений материалов мира. Его typed свойства потребляют независимо:
- [Physics](./tz_physics.md) — для вычисления воздействия (течение, горение, замерзание, разрушение), без владения реестром или физическими уравнениями внутри Materials;
- генератор зданий — для выбора по `use_type`, `economic_tier`;
- `ExcavationNode` — для добычи по `hardness`, `mineable`.

**Изменяемость:** физическое воздействие может изменить свойства материала или локальное состояние размещённого вещества. Изменение определения материала для всего мира и изменение одного экземпляра/объёма **не эквивалентны**. Materials принимает изменения собственных material properties по утверждённой операции, а локальное состояние/размещение — через профильного владельца в согласовании с Materials; exact owner/POJO/patch/version для mutable local state OPEN. Подробный маршрут — [Physics §7](./tz_physics.md).

---

## 2. Структура записи

GEO-1 G9-ST: substrate_kind — nullable MaterialSubstrateKind (rock,
loose_sediment, other). Missing/null означает неизвестное доказательство,
а не other. Canonical stone=rock; earth/sand/dirt_road=loose_sediment;
остальные canonical материалы явно other. Custom solid без этого поля
остаётся unknown; category/tags/hardness и имя не заменяют этот факт.


`transparent` — конечное число процентов в диапазоне `[0, 100]`, включая дробные
значения. Missing → `0`; explicit null, bool, строки, NaN/Infinity и значения вне
диапазона — unresolved по общей runtime/worldEdit политике, без clamp/default.
Миграция прежнего bool-контракта: `false → 0`, `true → 100`; данные fixtures и
canonical entries обновлены явно, runtime не выполняет скрытую конверсию bool.
Для сетки автор задаёт процент конкретного исполнения. Из физического `density`
он автоматически не выводится. Правила ослабления видимости через несколько
объектов и связь с `vision_block` требуют отдельного контракта потребителя;
в этом срезе расчёт FOV не добавляется.

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
  "transparent":        0,
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
| `material_category` | string | Physics и другие consumers | Категория материала: `solid`, `liquid`, `gas`; eligibility физических процессов определена в [Physics §2–3](./tz_physics.md) |
| `tags` | string[] | генератор зданий | Классификация: `construction`, `metal`, `crafted`, `refined`, `raw`, `organic`, `consumable`, `mineral`, `magic` + кастомные |
| `use_type` | string[] | генератор зданий, дороги | `wall`, `floor`, `column`, `door`, `gate`, `railing`, `ceiling`, `roof`, `road`, `any` |
| `economic_tier` | string\|null | генератор зданий | ref → `economic_tier_registry`; null для liquid/gas |
| `hardness` | int (1–5)\|null | ExcavationNode | Твёрдость; null для liquid/gas |
| `density` | int | Physics | Плотность как свойство Materials; применение в слоении/плавучести/давлении — [Physics §2/§4](./tz_physics.md), единицы OPEN |
| `heat_conductivity` | float (0.0–1.0) | Physics | Нормированное свойство теплопроводности; формула, температура и source semantics — [Physics §2/§5](./tz_physics.md) |
| `viscosity` | float (0.0–1.0)\|null | Physics | Коэффициент вязкости для liquid; null для solid/gas. Зависимость скорости течения от коэффициента — [Physics §2/§4](./tz_physics.md), не Materials |
| `heat_into` | string\|null | Physics / Materials | ref → `system_material`; допустимая цель перехода при нагреве выше `heat_temp`. null — переход не задан; исполнение — [Physics §4.2](./tz_physics.md) |
| `heat_temp` | int\|null | Physics / Materials | Порог нагрева в engine temperature; null если `heat_into` не задан. Формула применения — [Physics §5](./tz_physics.md) |
| `cool_into` | string\|null | Physics / Materials | ref → `system_material`; допустимая цель перехода при охлаждении ниже `cool_temp`. null — переход не задан; исполнение — [Physics §4.2](./tz_physics.md) |
| `cool_temp` | int\|null | Physics / Materials | Порог охлаждения в engine temperature; null если `cool_into` не задан. Формула применения — [Physics §5](./tz_physics.md) |
| `structural_strength` | float (0–1)\|null | Physics, construction consumers | Прочность материала; null для liquid/gas. Формула failure/нагрузки — [Physics §2/§3](./tz_physics.md) |
| `flammable` | bool | Physics / damage consumer | Признак горючести; trigger и реакция — [Physics §2/§5](./tz_physics.md). Default: false |
| `corrodible` | bool | Physics / placed-state owner | Признак восприимчивости к коррозии; изменение вещества/объекта — [Physics §2/§7](./tz_physics.md). Default: true |
| `mineable` | bool | физика | Добывается инструментом. Default: false |
| `transparent` | number (0–100) | scene/vision consumer | Прозрачность в процентах; 0 — непрозрачен, 100 — полностью прозрачен, дробные значения допустимы. Default: 0; FOV — внешний consumer |
| `breakable` | bool | Physics / placed-state owner | Признак допустимости разрушения. Конкретное изменение локального состояния и `broken` semantics — [Physics §2/§7](./tz_physics.md). Default: false |
| `temp_damage` | bool | Physics / damage consumer | Признак контактного температурного урона, только liquid/gas; не объявляет материал источником тепла — [Physics §2/§5](./tz_physics.md) |
| `vision_block` | bool | scene/vision consumer | Признак блокирования видимости для liquid/gas; алгоритм FOV не принадлежит Physics |
| `components` | string[]\|null | крафт | Компоненты для `crafted`/`refined` материалов |

`material_category` фиксирован в движке. `tags` расширяются через `worlds.material_tag_registry` (N+1).

---

## 3. Дефолты при создании пользователем

| Поле | Default | Логика |
|---|---|---|
| `flammable` | `false` | только явно горючие материалы горят |
| `corrodible` | `true` | большинство материалов поддаются коррозии |
| `mineable` | `false` | только явно добываемые добываются |
| `transparent` | `0` | материал непрозрачен по умолчанию |
| `breakable` | `false` | только хрупкие разрушаются от удара |
| `heat_conductivity` | `0.1` | Базовый default свойства; не означает наличие воздуха/атмосферы и не задаёт физический solver. См. [Physics §5/§6](./tz_physics.md) |
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

**Физические правила перенесены в [ТЗ Physics §2–3](./tz_physics.md).** Здесь Materials задаёт только `material_category`, свойства/ссылки и их ограничения (§2–3). Применимость процессов, формулы, консервация/ошибки и различие PH-AGG/PH-LOCAL принадлежат Physics. Старое правило «пустая клетка = air» **не универсально**: фактическую ambient/vacuum policy определяет World Environment/SPATIAL SP-A; Materials не создаёт воздух из отсутствия блока.

### 4.1 Переходы между состояниями материалов

Ссылки `heat_into`/`cool_into` и пороги `heat_temp`/`cool_temp` остаются **полями Materials**; таблица примеров и расчёт применения/смены размещённого material identity перенесены в [Physics §4.2](./tz_physics.md). Целевой материал должен существовать в Materials registry. Изменение локального вещества не меняет автоматически определение материала во всём мире.

### 4.2 Тепловая диффузия (v1)

Исходная формула, `dt`, source semantics и их OPEN-ограничения перенесены в [Physics §5](./tz_physics.md). Materials определяет только свойства, но не исполняет per-cell тик или теплообмен.

---

## 5. Физика жидкостей

**Нормативный владелец законов течения, слоения, давления и фазовых переходов — [Physics §4](./tz_physics.md).** Materials предоставляет типизированные свойства.

### 5.1 Гравитационное течение (v1)

[Physics §4.1](./tz_physics.md): гравитация, density/viscosity и разные PH-AGG/PH-LOCAL вычисления. Формула скорости OPEN.

### 5.2 Переход solid → liquid

[Physics §4.2](./tz_physics.md): свойства/ссылки остаются Materials-owned; изменение конкретного размещения/объекта — отдельный domain change.

### 5.3 Давление (v2)

[Physics §4.3](./tz_physics.md): перенесён исходный эскиз формулы и ограничения его точности/единиц. Не делать глобальный SQL/Grade per-cell read.

---

## 6. Физика газов

Законы распространения газов, их связь с `density`, ambient/vacuum и взаимодействиями перенесены в [Physics §6](./tz_physics.md). `vision_block` / `temp_damage` остаются свойствами Materials; соответствующий scene/damage consumer не является Materials solver.

---

## 7. Пример реестра

```json
[
  { "system_material": "stone",     "display_name": "Камень",        "glossary_ref": null, "material_category": "solid",  "tags": ["construction", "mineral"],  "use_type": ["wall", "floor", "column"],          "economic_tier": "standard", "hardness": 3,    "density": 250, "heat_conductivity": 0.4, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": 0.8,  "flammable": false, "corrodible": true,  "mineable": true,  "transparent": 0, "components": null },
  { "system_material": "wood",      "display_name": "Дерево",        "glossary_ref": null, "material_category": "solid",  "tags": ["construction", "organic"],  "use_type": ["wall", "floor", "door", "railing"], "economic_tier": "basic",    "hardness": 2,    "density": 60,  "heat_conductivity": 0.2, "viscosity": null, "heat_into": "charcoal", "heat_temp": 150,  "cool_into": null,  "cool_temp": null, "structural_strength": 0.3,  "flammable": true,  "corrodible": true,  "mineable": false, "transparent": 0, "components": null },
  { "system_material": "iron",      "display_name": "Железо",        "glossary_ref": null, "material_category": "solid",  "tags": ["metal", "mineral"],         "use_type": ["wall", "door", "gate", "railing"],  "economic_tier": "standard", "hardness": 4,    "density": 800, "heat_conductivity": 0.9, "viscosity": null, "heat_into": "molten_iron", "heat_temp": 200,  "cool_into": null,  "cool_temp": null, "structural_strength": 0.9,  "flammable": false, "corrodible": true,  "mineable": false, "transparent": 0, "components": null },
  { "system_material": "earth",     "display_name": "Земля",         "glossary_ref": null, "material_category": "solid",  "tags": ["raw", "mineral"],           "use_type": ["floor"],                            "economic_tier": "poor",     "hardness": 1,    "density": 150, "heat_conductivity": 0.3, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": 0.2,  "flammable": false, "corrodible": true,  "mineable": true,  "transparent": 0, "components": null },
  { "system_material": "crystal",   "display_name": "Кристалл",      "glossary_ref": null, "material_category": "solid",  "tags": ["mineral", "magic"],         "use_type": ["wall", "floor"],                    "economic_tier": "premium",  "hardness": 3,    "density": 260, "heat_conductivity": 0.2, "viscosity": null, "heat_into": null,        "heat_temp": null, "cool_into": null,  "cool_temp": null, "structural_strength": 0.4,  "flammable": false, "corrodible": false, "mineable": false, "transparent": 100,  "components": null },
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
| `flammable` + `heat_into`: при воспламенении применяется transition ref или отдельная реакция? | [Physics §5/§9](./tz_physics.md) — OPEN, не решается Materials |
| `dt`/тепловой шаг: per-world settings POJO и сопоставление Physics time/LOD | [Physics §5/§9](./tz_physics.md) — OPEN; поля World не выдуманы |
| Формула скорости течения с `viscosity`, численные units и budgets | [Physics §4.1/§9](./tz_physics.md) — OPEN |
| Давление/затопление снизу/трубы (v2) | [Physics §4.3/§9](./tz_physics.md) — будущий gate |
| Структурная целостность/обрушение без опоры | [Physics §3/§9](./tz_physics.md) — будущий gate |
| Может ли Physics изменить **само определение материала** (world-wide свойства) и какой public Materials change contract/версия принимает это? | OPEN Materials + PH-PUBLISH; явный scope и Snapshot |
| Как моделируются **локально изменяемые** свойства/состояния вещества: Materials-owned property, placed-media/object state или вычисляемое effective property; кто хранит local state? | OPEN Materials + соответствующий domain owner + Physics; не смешивать с глобальным registry |

## 9. Технический долг зоны материалов

### MAT-T-1 — Подготовка материала с требуемыми характеристиками для потребителей

Статус: open. Подтверждено аудитом кода 2026-10-03.
Ответственность: зона материалов, не консьюмер экономической политики.
Первый потребитель: выбор материала общей стены по structural_strength,
[tz_economic_tier.md §11](tz_economic_tier.md#11-политики-строительных-материалов).

**Уже есть; не реализовывать повторно:**

- `MaterialRegistryEntry.structural_strength` проверяет диапазон 0–1, допускает
  None и имеет default None. Общий jsonValidation применяет field defaults и
  диагностику невалидных значений; это не гарантирует числовую прочность.
- WorldMaterialRegistry.entry_for ищет ключ, возвращает запись либо None.
  REF-W validation проверяет отдельные зарегистрированные ссылки при импорте;
  это не универсальная runtime-проверка материала для каждой операции.
- materialResolver.resolve_material использует fallback ближайший тир вниз →
  любой подходящий construction material → default с WARNING на последнем
  переходе. Он выбирает по tags/use_type/economic_tier и возвращает ключ.

**Подтверждённый пробел:** нет общей подготовки кандидата, гарантирующей
существующую запись и требуемую числовую structural_strength перед сравнением.
resolve_material не проверяет наличие strength у выбранного кандидата или
записи конечного default. entry_for не выполняет fallback или проверку
пригодности характеристик. Допустимое None, включая у solid, проходит модель.

В roadTravelResolver.effective_degradation_rate уже есть отдельная подстановка
strength=1.0 при неизвестном материале/None/0 через truthiness. Она локальна,
не является общим контрактом зоны материалов и смешивает допустимый ноль с
отсутствующей характеристикой. Не переносить её в экономический консьюмер.

**Целевой контракт:** зона материалов разрешает identity, использует существующие
defaults/fallback и проверяет характеристики, необходимые операции. Возвращает
подготовленного кандидата с provenance/диагностикой либо явную причину
невозможности подготовки. Консьюмер политики сравнивает готовые значения,
не чинит ссылки и не подставляет strength. Не назначать None произвольное
число; правила восстановления характеристик согласовать в зоне материалов.
None для liquid/gas остаётся допустимым, требование strength связано с операцией,
а не со всеми материалами. Ноль — валидное значение и сохраняется.

**Критерии закрытия:** переиспользованы имеющиеся проверки/fallback; проверены
неизвестный ключ, default без записи, строительный материал со strength=None,
невалидный диапазон, strength=0 и штатный кандидат; есть явная диагностика,
экономический консьюмер не реализует собственное восстановление. Локальные
потребители характеристик проверены на дублирование и несовместимые defaults.

Кодовые основания: materialRegistryEntry.py §structural_strength,
worldMaterialRegistry.py §entry_for, generators/utils/materialResolver.py
§resolve_material, jsonValidation/resolve.py §_resolve_field,
generators/road/roadTravelResolver.py §effective_degradation_rate.
# Runtime/worldEdit — миграция consumers E6 (2026-10-08)

Основа — [общая политика](tz_runtime_world_edit_policy.md). Неизвестный авторский
economic_tier/material ref и отсутствие кандидатов вместе с неизвестным default
дают unresolved; error fallback не создаёт несуществующий material key.
Штатный подбор по tier вниз → любой подходящий construction-кандидат → объявленный
terminal default сохраняется. Terminal defaults `window_glass`, `porthole_glass`,
`vent_mesh`, `dirt_road` включены в canonical material registry и fixture мира.
Они не имеют тега construction: возврат default при штатном отсутствии кандидатов
не расходует RNG; авторские construction-кандидаты сохраняют прежний алгоритм выбора.
