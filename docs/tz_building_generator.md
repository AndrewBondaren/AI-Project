# ТЗ: Генератор зданий

> **Архитектура нод:** ноды structure-домена пишут только в `state.structure_context: StructureContext` — типизированный контекст на `ExecutionState`. `shared_context` не использовать как канал передачи данных. См. `tz_engine_node_context.md`.

## 1. Scope

Генератор зданий строит полную структуру здания — этажи, комнаты, проходы, ячейки карты — из JSON-шаблона с рандомизацией в рамках заданных диапазонов.

Шаблоны:
- JSON-файлы, загружаемые пользователем (аналог импорта миров)
- Хранятся в БД, применимы к любому зданию в любом мире
- Детерминированная рандомизация: один и тот же шаблон + здание → один и тот же результат

---

## 2. Термины

| Термин | Смысл |
|--------|-------|
| **Шаблон** | JSON-файл, описывающий тип здания: этажи, комнаты, связи, входы |
| **structure_type** | Смысловой тип здания: `tavern`, `shop`, `dungeon`, `house`, etc. |
| **Комната** | Под-локация внутри здания (отдельная `NamedLocation` с `parent_uid = building.location_uid`) |
| **Уровень** | Один этаж: `LocationLevel` с конкретным `z` |
| **Проход** | `LocationPassage` между двумя комнатами или уровнями |
| **Точка входа** | Главный вход снаружи → в здание; объявляется на конкретной комнате |
| **Чёрный вход** | Служебный вход снаружи → в здание; опциональный, тоже на комнате |
| **Коридор** | Обычная комната с `room_type: "corridor"`. Необязателен — этажи без коридора существуют. Комнаты без коридора соединяются напрямую дверью через `connections` |
| **attach_to** | Комнаты прикрепляются вдоль стены комнаты-хоста (обычно коридора) |
| **z_height** | Высота потолка уровня в z-юнитах (1 юнит = 1м) |

---

## 3. Схема шаблона (JSON)

### 3.1 Поля верхнего уровня

| Поле | Тип | Обязательность | Описание |
|------|-----|---------------|----------|
| `system_name` | string | required | Уникальный системный идентификатор шаблона: `"tavern_1"`, `"manor_std"`. Используется для генерации `template_uid = uuid5(NAMESPACE_DNS, system_name)` |
| `structure_type` | string | required | Смысловой тип: tavern, shop, dungeon, house, etc. |
| `display_name` | string | required | Отображаемое название шаблона |
| `description` | string | optional | Описание для UI |
| `version` | string | required | Версия шаблона: `"1.0"` |
| `default_z_height` | int | optional | Высота потолка по умолчанию для всех уровней. Default: `3` |
| `min_z_height` | int | optional | Минимально допустимая высота потолка любого уровня. Default: `2` |
| `gap_policy` | string | optional | Поведение для gap-областей (внутри bounding box, вне всех комнат): `"clip"`, `"fill"`, `"random"`. Default: `"clip"` |
| `economic_tier` | string | optional | Экономический уровень здания для выбора материалов: ref → `worlds.economic_tier_registry`. Default: `"standard"`. Всегда имеет значение после резолва — используется как fallback если `room.economic_tier` не задан |
| `building_context` | string | optional | Контекст здания для фильтрации материалов лестницы-ladder: `"indoor"`, `"underground"`, `"nautical"`. Default: `"indoor"` |
| `window_z_ratio` | float | optional | Пропорциональная высота окон по умолчанию для всех уровней: `window_z = floor(z_height * ratio)`. Default: `0.4`. Переопределяется на уровне через `level.window_z_ratio` или `level.window_z_offset` |
| `door_height_ratio` | float | optional | Коэффициент высоты дверей для `z_height >= 4`: `door_height = floor(z_height * ratio)`. Default: `0.75` |
| `door_height_max` | int | optional | Максимальная высота двери в z-юнитах. Default: `5`. Cap для высоких этажей — дверь не растёт бесконечно |
| `underground_expansion` | int | optional | Макс. расширение подземных уровней за границы ground floor footprint в ячейках. Default: `2`. Защита от конфликта с соседними зданиями |
| `foundation_depth` | int | optional | Глубина фундамента в z-юнитах. Default: `1`. Передаётся в `StructureContext` если не задан явно (`context.foundation_depth ?? template.foundation_depth ?? 1`) |
| `levels` | array | required | Массив уровней, минимум 1 |
| `connections` | array | required | Межкомнатные связи и лестницы |

`entry_point` и `back_entry_point` объявляются **на комнате** (поле `entry_point` / `back_entry_point` в room-объекте), не на верхнем уровне шаблона.

---

### 3.2 Поля уровня (level)

| Поле | Тип | Обязательность | Описание |
|------|-----|---------------|----------|
| `z_offset` | int | required | Смещение этажа: `0` = земля, `1` = второй этаж, `-1` = подвал |
| `display_name` | string | required | Название: "Первый этаж", "Подвал", "Чердак" |
| `z_height` | int | optional | Высота потолка в z-юнитах. Если не задана — берётся `default_z_height` шаблона |
| `window_z_offset` | int | optional | Явная высота окон от base_z этажа. Переопределяет `window_z_ratio`. Используется когда нужен точный контроль |
| `window_z_ratio` | float | optional | Пропорциональная высота окон: `window_z = floor(z_height * ratio)`. Переопределяет `template.window_z_ratio` для этого уровня |
| `isolated` | bool | optional | Уровень не имеет физического прохода из других уровней. Default: `false` |
| `access_mechanic` | string[] | optional | Способы доступа к изолированному уровню: `"excavation"`, `"teleport"`. Пустой массив = недостижим без механики. Игнорируется если `isolated: false` |
| `rooms` | array | required | Список комнат на уровне, минимум 1 |

**Вычисление `LocationLevel.z`:**
```
z(z_offset=0) = building.map_z
z(z_offset=N>0) = building.map_z + sum(level.z_height for z_offset in 0..N-1)
z(z_offset=N<0) = building.map_z - sum(level.z_height for z_offset in N..-1)
```
Каждый уровень стекируется поверх предыдущего на его собственную `z_height`.

---

### 3.3 Размерные пресеты (RoomSize)

Фиксированный реестр размеров — не расширяется пользователем. Задаёт диапазоны x, y и z для комнаты.

| `size` | `width_range` (X) | `depth_range` (Y) | `z_range` (высота потолка) |
|--------|-------------------|-------------------|---------------------------|
| `small` | 2–4 | 2–4 | 3–3 |
| `medium` | 5–10 | 5–10 | 3–3 |
| `big` | 10–20 | 10–20 | 3–5 |
| `huge` | 10–20 | 10–20 | 5–10 |
| `colossal` | 20–100 | 20–100 | 7–20 |

`big` и `huge` имеют одинаковые x/y — различаются только высотой потолка.  
`z_range` — диапазон высоты потолка конкретной комнаты в z-юнитах (рандомизируется через `rng`).

**Приоритет при конфликте с уровнем:**
```
room_z  = rng.randint(z_range[0], z_range[1])   -- из пресета или явного z_range
level_z = level.z_height ?? max(room_z for room in level.rooms)

если room_z > level_z:
    log WARNING f"Room '{room_id}': z_range даёт {room_z}, уровень ограничен {level_z} — потолок обрезан"
    actual_room_z = level_z
иначе:
    actual_room_z = room_z
```

Если `level.z_height` не задан явно — он вычисляется как `max(room_z)` всех комнат уровня.

---

### 3.4 Поля комнаты (room)

| Поле | Тип | Обязательность | Описание |
|------|-----|---------------|----------|
| `room_id` | string | required | Локальный ID внутри шаблона; используется в connections и attach_to |
| `room_type` | string | required | Смысловой тип: common_hall, kitchen, cellar, corridor, guest_room, etc. Должен существовать в `worlds.room_type_registry` — валидируется при импорте шаблона в мир |
| `display_name` | string | required | Название для `NamedLocation.display_name` |
| `is_public` | bool | required | Комната доступна для всех. Зависит от контекста здания: холл таверны = true, холл частного дома = false |
| `is_forbidden` | bool | required | Комната запрещена для входа. Зависит от контекста здания: палуба лайнера = false, палуба военного корабля = true |
| `shape_type` | string \| string[] | required | Форма footprint (см. раздел 3.8). Строка = фиксированная; массив = генератор выбирает один случайно |
| `size` | object | required | Объект размера комнаты (см. раздел 3.5) |
| `required` | bool | required | Если true — комната всегда генерируется |
| `count` | int | conditional | Фиксированное кол-во экземпляров (только при `required: true`) |
| `count_range` | [int, int] | conditional | Диапазон кол-ва (только при `required: false`) |
| `perimeter_required` | bool | optional | Комната должна касаться внешней стены здания. Default: `false`. Принудительно `true` если объявлен `entry_point` или `back_entry_point` (см. правило ниже) |
| `attach_to` | string | optional | `room_id` комнаты-хоста (коридора); эта комната прикрепляется вдоль его стены |
| `attach_wall` | string | conditional | Обязателен если `attach_to` задан. `"north"`, `"south"`, `"east"`, `"west"`, `"both"`, `"any"` |
| `max_overhang` | int | optional | Макс. выступ за границы ground floor footprint в ячейках. Default: `0`. Разрешён только для `room_type: "balcony"`. Без `has_column`: не более 2. С `has_column`: не более 4 |
| `has_column` | bool | optional | Балкон опирается на колонны. Увеличивает лимит `max_overhang` до 4. Генератор размещает ячейки `column` на ground floor под выступающими углами балкона |
| `economic_tier` | string | optional | Переопределяет экономический уровень для этой комнаты. Если не задан — берётся из шаблона |
| `entry_point` | object | optional | Объявляет главный вход здания на этой комнате. Только одна комната в шаблоне |
| `back_entry_point` | object | optional | Объявляет чёрный вход здания на этой комнате. Только одна комната в шаблоне |
| `wall_openings` | array | optional | Отверстия в стенах комнаты: окна, бойницы, люки, иллюминаторы и др. (см. раздел 3.10) |
| `underground_fallback` | bool | optional | Если комнату невозможно разместить на текущем уровне — перенести на уровень ниже. Default: `false`. Уместно для складских, подсобных, кладовых, котельных |
| `shape_params` | object | conditional | Параметры специфичные для формы. Обязателен для `l_shape` и `t_shape`. Игнорируется для остальных |

**Правило `perimeter_required` + entry_point:**

```
если room.entry_point OR room.back_entry_point объявлены:
    effective_perimeter_required = True   -- всегда, независимо от поля

    если room.perimeter_required == False (явно):
        log WARNING f"Room '{room_id}': perimeter_required=false игнорируется — "
                    f"entry_point/back_entry_point требует периметра"
```

Генератор обеспечивает периметральное размещение такой комнаты при layout. `attach_to` на комнате с `entry_point`/`back_entry_point` — дополнительный WARNING: архитектурно некорректно, но технически допустимо.

Либо `count`, либо `count_range` — не оба одновременно.

---

### 3.5 Объект size

Три допустимые формы — взаимно исключающие по `size_type`:

```json
{ "size_type": "big" }
```
```json
{ "size_type": "big", "z_range": [5, 5] }
```
```json
{ "width_range": [3, 5], "depth_range": [3, 4] }
```

| Поле | Тип | Обязательность | Описание |
|------|-----|---------------|----------|
| `size_type` | string | conditional | Пресет: `small`, `medium`, `big`, `huge`, `colossal`. Определяет `width_range` и `depth_range`. Взаимоисключает явные диапазоны |
| `width_range` | [int, int] | conditional | Явный диапазон X. Обязателен если `size_type` не задан |
| `depth_range` | [int, int] | conditional | Явный диапазон Y. Обязателен если `size_type` не задан и `shape_type` требует Y |
| `z_range` | [int, int] | optional | Диапазон высоты потолка. Допустим в обеих формах. Default если не задан: из пресета или `(3, 3)` |

**Правила:**
- `size_type` задан → `width_range` и `depth_range` берутся из пресета. Нельзя их переопределить
- `size_type` не задан → `width_range` и `depth_range` обязательны
- `z_range` — единственное поле, которое можно указать поверх `size_type`
- `size_type` + `width_range`/`depth_range` одновременно → `ValidationError`

```
if size_type присутствует:
    if width_range OR depth_range в объекте → ValidationError
    base        = ROOM_SIZE_PRESETS[size_type]
    width_range = base.width_range
    depth_range = base.depth_range
    z_range     = size.z_range ?? base.z_range
else:
    width_range = size.width_range   -- обязательно
    depth_range = size.depth_range   -- обязательно (если shape требует)
    z_range     = size.z_range ?? (3, 3)
```

---

### 3.5b Объект shape_params

Обязателен для `l_shape` и `t_shape`. Для остальных форм игнорируется.

**`l_shape`:**

```json
{
  "arm_width_range": [2, 4],
  "arm_depth_range": [3, 5],
  "arm_corner": "northeast"
}
```

| Поле | Описание |
|---|---|
| `arm_width_range` | Ширина руки (вдоль оси X). Обязательно |
| `arm_depth_range` | Глубина руки (вдоль оси Y). Обязательно |
| `arm_corner` | Угол прикрепления руки: `"northeast"` \| `"northwest"` \| `"southeast"` \| `"southwest"` \| `"any"`. Default: `"any"` (rng выбирает) |

Геометрия: `R1` (main body: `width × depth`) ∪ `R2` (arm: `arm_width × arm_depth`, смещён в указанный угол).

---

**`t_shape`:**

```json
{
  "stem_width_range": [2, 3],
  "stem_wall": "south"
}
```

| Поле | Описание |
|---|---|
| `stem_width_range` | Ширина стержня. Обязательно. Должна быть < `size.width_range[0]` |
| `stem_wall` | С какой стороны балки выходит стержень: `"north"` \| `"south"` \| `"east"` \| `"west"` \| `"any"`. Default: `"any"` |

Геометрия: `R1` (балка: `width × depth`) ∪ `R2` (стержень: `stem_width × depth`, центрирован вдоль `stem_wall`).  
Глубина стержня = `size.depth_range` (бо́льшая из двух осей). Балка занимает `arm_depth`... но так как T-shape использует `width × depth` для bounding box, стержень = часть этого box.

Валидация: `stem_width_range[1] < size.width_range[0]` → иначе `ValidationError` (стержень шире балки).

---

### 3.6 Поля entry_point / back_entry_point (на комнате)

| Поле | Тип | Описание |
|------|-----|----------|
| `wall` | string | Стена: `north`, `south`, `east`, `west` |
| `passage_type` | string | `main_entrance`, `service_entrance` |
| `width` | int | optional. Ширина проёма в ячейках. Default: `1`. `2` = двустворчатая, `3+` = воротный проём |
| `door_height` | int | optional. Явная высота проёма в z-юнитах. Если не задана — авто-резолв (см. ниже) |
| `frame_material` | string\|null | optional. Материал дверной коробки. Fallback: `wall_material` комнаты |
| `panel_material` | string\|null | optional. Материал дверного полотна. Fallback: `economic_tier` → `material_registry`. `null` = открытый проём |
| `access_type` | string | optional. Переход снаружи к двери при перепаде высот. `"auto"` \| `"none"` \| `"steps"` \| `"porch"`. Default: `"auto"` |

**Авто-резолв `door_height`:**

```
если door_height задан явно → использовать
если z_height <= 3:
    door_height = z_height - 1
иначе:
    door_height = min(
        floor(z_height * template.door_height_ratio),  -- default 0.75
        template.door_height_max                        -- default 5
    )

Примеры (ratio=0.75, max=5):
  z=2  → 1    z=3  → 2    z=4  → 3
  z=6  → 4    z=7  → 5    z=10 → 5 (cap)
  z=20 → 5    (cap)
```

Валидация: `door_height >= 1` и `door_height < z_height` → иначе `ValidationError`.

**Центрирование:** `entry_point` всегда центрируется на указанной стене.

```
mid = len(wall_cells) // 2
если width нечётный: cells = [mid - width//2 .. mid + width//2]
если width чётный:   cells = [mid - width//2 .. mid + width//2 - 1]
```

Каждая ячейка проёма: `system_terrain = "door"`, `is_structural = false`, `system_material = frame_material`.  
`cell_states`: `system_state = "closed"` для каждой ячейки.  
`LocationPassage` создаётся с `from_level_uid = null` (внешнее пространство) → `to_level_uid` уровня этой комнаты.

**Авто-резолв `access_type` (выполняется ассемблером):**

```
gap = building.map_z - terrain_z[entry_x, entry_y]

если gap <= 0:              access_type = "none"   -- вход с уровня земли
если gap in [1, 2]:         access_type = "steps"  -- 1–2 ступени
если gap >= 3:              access_type = "porch"  -- крыльцо
```

Явный `access_type` в шаблоне переопределяет авто-резолв.

| `access_type` | Ячейки | NamedLocation | subtype |
|---|---|---|---|
| `"none"` | — | — | — |
| `"steps"` | `staircase` от terrain до door; ширина = `entry_point.width` | ✓ всегда | `entrance_steps` |
| `"porch"` | `floor`-платформа на уровне двери + `staircase` вниз | ✓ всегда | `porch` |

`NamedLocation` создаётся для любого ненулевого `access_type` — LLM должен описывать место перед входом как отдельную сцену.

**`entrance_steps`**: транзитная локация (1–2 ступени); `display_name` = "Ступени"; `is_public = true`; `is_outdoor = true`; `is_sheltered = false`; `is_transit = true`.  
Движок проходит через неё автоматически — отдельная сцена не создаётся. LLM описывает ступени как часть описания при входе в здание.

**`porch`**: полноценная сцена; `display_name` = "Крыльцо"; `is_public = true`; `is_outdoor = true`.  
- `porch_has_roof: false` → `is_sheltered = false` (открытое крыльцо, полная погода)  
- `porch_has_roof: true` → `is_sheltered = true` (навес; дождь не достаёт, ливень/шторм проникает)

`LocationPassage`:
```
"none"  → from_level_uid = null (внешнее) → to_level_uid = entry_room
"steps" → from_level_uid = null           → to_level_uid = entry_room
          (ступени — транзитная зона, не отдельный уровень)
"porch" → from_level_uid = null           → to_level_uid = entry_room
          + внутренний passage: porch → entry_room через дверь
```

Материалы:
```
step_material  = context.porch_material ?? building.parent_floor_material
porch_material = context.porch_material ?? building.parent_floor_material
```

---

### 3.7 Поля connection

| Поле | Тип | Описание |
|------|-----|----------|
| `from_room` | string | `room_id` источника |
| `to_room` | string | `room_id` цели |
| `passage_type` | string | `doorway`, `staircase`, `archway`, etc. |
| `required` | bool | Если обе комнаты сгенерированы — проход обязателен |
| `width` | int | optional. Только для `doorway`/`archway`. Ширина проёма в ячейках. Default: `1` |
| `door_height` | int | optional. Только для `doorway`/`archway`. Явная высота проёма. Если не задана — тот же авто-резолв что в `entry_point` |
| `frame_material` | string\|null | optional. Материал дверной коробки / арки. Fallback: `wall_material` from_room |
| `panel_material` | string\|null | optional. Только для `doorway`. Материал дверного полотна. Fallback: `economic_tier` → `material_registry`. `null` = проём без двери |
| `step_material` | string\|null | optional. Только для `staircase`. Материал ступеней. Fallback: `floor_material` from_room |
| `railing_material` | string\|null | optional. Только для `staircase`. Материал поручня. `null` = без поручня. Fallback: `economic_tier` → `material_registry` |
| `position` | string | optional. Только для `staircase`. Позиция ячейки лестницы внутри `to_room`: `"center"`, `"north"`, `"south"`, `"east"`, `"west"`, `"northwest"`, `"northeast"`, `"southwest"`, `"southeast"`. Если не задан — авто-резолв |
| `staircase_type` | string | optional. Только для `staircase`. Тип лестницы (см. раздел 3.9). Если не задан — авто-резолв по `z_height` |

**Fallback материалов:**

```
frame_material:   connection.frame_material ?? room.wall_material ?? find_candidates("wall")
panel_material:   connection.panel_material ?? find_candidates("door")   -- null = проём
step_material:    connection.step_material  ?? room.floor_material ?? find_candidates("floor")
railing_material: connection.railing_material ?? find_candidates("railing") -- null = без поручня
```

`find_candidates` — тот же алгоритм что в 8.5b: фильтр по `use_type` + `economic_tier` + fallback вниз по `tiers_sorted`.

**Центрирование doorway на общей стене:**

```
shared_segment = общие ячейки границы двух комнат
mid = len(shared_segment) // 2
если width нечётный: cells = [mid - width//2 .. mid + width//2]
если width чётный:   cells = [mid - width//2 .. mid + width//2 - 1]
если width > len(shared_segment) → width = len(shared_segment) + WARNING
```

**Разбиваемость двери:** определяется `material_registry[panel_material].breakable`.  
Деревянная дверь (`breakable: true`) → состояние `broken` доступно.  
Железная дверь (`breakable: false`) → только `closed` / `open` / `locked`.

Если одна из комнат не была сгенерирована (например, пропущена из-за ограничений footprint верхнего этажа) — connection пропускается.  
Для `staircase`: `from_level_uid.z ≠ to_level_uid.z`; ячейка типа `staircase` на обоих уровнях.

---

### 3.8 shape_type

`shape_type` — строка или массив строк. Если массив — генератор выбирает один случайно через `rng.choice(shape_type)`.

| `shape_type` | Описание | Алгоритм ячеек | Статус |
|---|---|---|---|
| `rectangle` | Прямоугольник | `x ∈ [x₀, x₀+w)` AND `y ∈ [y₀, y₀+d)`; стена на границе, пол внутри | **v1** |
| `square` | Квадрат | то же; `w = d = min(width, depth)` | **v1** |
| `semicircle` | Полукруг; плоская стена на стороне среза | `(x−cx)² + (y−cy)² ≤ r²` AND `y ≥ cy`; `r = width / 2` | **v1** |
| `semi_oval` | Полуовал; плоская стена сверху | `(x/a)² + (y/b)² ≤ 1` AND `y ≥ 0`; `a = width / 2`, `b = depth` | **v1** |
| `l_shape` | Г-образный; параметры `arm_width`, `arm_depth` | `R1 ∪ R2`; R1 = main body (`width × depth`), R2 = arm смещён в угол | **v1** |
| `t_shape` | Т-образный; параметр `arm_depth` | `R1 ∪ R2 ∪ R3`; R1 = горизонтальная балка (`width × arm_depth`), R2/R3 = столбы | **v1** |
| `circle` | Круг | `(x−cx)² + (y−cy)² ≤ r²`; `r = width / 2` | **v1** |
| `polygon` | Произвольный полигон | ray-casting test для набора вершин из шаблона | v3 |

`width_range` / `depth_range` по shape_type:

| `shape_type` | `width_range` | `depth_range` |
|---|---|---|
| `rectangle` | ширина (X) | глубина (Y) |
| `square` | сторона | игнорируется |
| `semicircle` | диаметр | игнорируется |
| `semi_oval` | ширина (2a) | глубина полуоси (b) |
| `circle` | диаметр | игнорируется |

**Алгоритм генерации ячеек shape-agnostic:**

Стены и полы строятся одинаково для любой формы — по множеству room_cells:
```
room_cells = {(x,y) : формула shape_type = true}
для (x,y) в room_cells → floor
для (x,y) в room_cells, сосед (nx,ny) ∉ room_cells → wall на (nx,ny)
```

**Выпрямление стены под дверь (chord flattening) — для circle, semicircle, semi_oval:**

Если на комнате объявлен `entry_point.wall` или `back_entry_point.wall`, на соответствующем краю вырезается плоский сегмент (хорда) шириной `entry_point.width`:

```
wall = "north" → extremal_y = min(y) в room_cells
    flat_x_start = cx - floor(width / 2)
    flat_x_end   = cx + ceil(width / 2) - 1

    для x в [flat_x_start, flat_x_end]:
        заменить ячейки кривой стены на прямые wall-ячейки при y = extremal_y
        (отсечь ячейки room_cells у которых y < extremal_y в этом диапазоне x)
```

Комната остаётся почти круглой, но имеет прямой участок у входа. Архитектурно корректно — реальные круглые залы с дверями всегда имеют такой срез.

`wall_openings` на круглой стене — `window_z` единый, а симметричное размещение по дуге считается через arc-length вдоль exterior_wall_cells.

В v1 `polygon` → `UnsupportedShapeError` при загрузке шаблона.

---

### 3.9 Типы лестниц (staircase_type)

| `staircase_type` | Footprint | Описание | Применение |
|---|---|---|---|
| `ladder` | 1×1 (1 ячейка) | Приставная лестница; не стационарная. Материал из `world.material_registry` по `building_context` | Подвалы, чердаки, бедные постройки |
| `spiral_small` | 1×2 (2 ячейки) | Крутая, размещается у края стены | Чердак, подвал, тесные пространства |
| `spiral_standard` | 2×2 (4 ячейки) | Идёт по кругу | Башни, вторичные лестницы |
| `standard` | 2×2 (4 ячейки) | П-образная без пробела: два марша + площадка | Стандартный этаж-в-этаж |
| `straight` | 1×N (формула) | Прямой марш без площадки | Большие здания, парадные лестницы |

**Формула длины `straight`:**

```
stair_length = max(2, ceil(z_height * 1.3))
```

| z_height | stair_length |
|---|---|
| 2 | 3 |
| 3 | 4 |
| 5 | 7 |
| 10 | 13 |
| 20 | 26 |

Коэффициент 1.3 соответствует углу ~38° (комфортная лестница, соотношение проступи к подступёнку).

**Авто-резолв `staircase_type`:**

```
effective_tier = to_room.economic_tier ?? template.economic_tier

tiers_sorted = sorted(economic_tier_registry, key=lambda t: t.base_value)  -- ASC
tier_rank    = tiers_sorted.index(effective_tier)   -- 0 = самый дешёвый
tier_count   = len(tiers_sorted)

если staircase_type не задан:
    если z_height <= 3 AND tier_rank < ceil(tier_count / 3) → ladder  -- нижняя треть реестра
    если z_height <= 5 → standard
    иначе              → straight
```

**Размещение блока лестницы по `position`:**

`position` применяется к `to_room`. Позиция `from_room` — всегда авто-резолв (см. раздел 8.8).

| `position` | `ladder` (1×1) | `spiral_small` (1×2) | `spiral_standard` (2×2) | `standard` (2×2 П) | `straight` (1×N) |
|---|---|---|---|---|---|
| `north` | 1 ячейка у сев. стены, центрирована по X | 2 ячейки вдоль сев. стены, центрированы по X | блок 2×2 у сев. стены, центрирован по X | блок 2×2 у сев. стены, центрирован по X; **П открывается на юг** | 1×N идёт на юг, центрирован по X |
| `south` | аналогично | аналогично | аналогично | **П открывается на север** | идёт на север |
| `east` | 1 ячейка у вост. стены, центрирована по Y | 2 ячейки вдоль вост. стены, центрированы по Y | у вост. стены, центрирован по Y | **П открывается на запад** | 1×N идёт на запад, центрирован по Y |
| `west` | аналогично | аналогично | аналогично | **П открывается на восток** | идёт на восток |
| `center` | 1 ячейка в центре комнаты | 2 ячейки по оси Y, центрированы XY | блок 2×2 в центре | блок 2×2 в центре; **П открывается на юг** | 1×N по оси Y, центрирован по X |
| `northwest` | угол NW | угол в NW; длинная ось вдоль сев. стены | угол 2×2 в NW-угол | `ValidationWarning` → авто-резолв к `north` | `ValidationWarning` → авто-резолв к `north` |
| `northeast` | угол NE | угол в NE; длинная ось вдоль сев. стены | угол 2×2 в NE-угол | авто-резолв к `north` | авто-резолв к `north` |
| `southwest` | угол SW | угол в SW; длинная ось вдоль юж. стены | угол 2×2 в SW-угол | авто-резолв к `south` | авто-резолв к `south` |
| `southeast` | угол SE | угол в SE; длинная ось вдоль юж. стены | угол 2×2 в SE-угол | авто-резолв к `south` | авто-резолв к `south` |

`standard` (П-образная): **П открывается в сторону, противоположную стене** — entry-ячейка всегда ближайшая к центру комнаты сторона блока.

**Проверка fit перед размещением:**

Перед тем как поставить лестницу, проверяется что её footprint вписывается в `to_room`:

```
fit(staircase_type, to_room):
    ladder          → 1×1  → всегда fit
    spiral_small    → 1×2  → to_room.width >= 1 AND to_room.depth >= 2
    spiral_standard → 2×2  → to_room.width >= 2 AND to_room.depth >= 2
    standard        → 2×2  → то же
    straight        → 1×N  → to_room в направлении движения >= stair_length
                           где stair_length = max(2, ceil(z_height * 1.3))
```

Если `staircase_type` задан явно и не вписывается — применяется **fallback chain**:

```
straight → standard → spiral_standard → spiral_small → ladder
```

Каждый тип проверяется через `fit()`. Первый подходящий используется.
Если в шаблоне задан явный `staircase_type` и он не прошёл fit — начать fallback с следующего по chain.
`ladder` (1×1) проходит fit всегда — GenerationError невозможен только из-за лестницы.

```
log WARNING "Лестница '{connection}': {original_type} не вписывается
             в to_room '{room_id}' — заменена на {fallback_type}"
```

Если блок вписывается по размеру, но не вписывается при заданном `position` — сдвиг к ближайшей допустимой позиции + `log WARNING`.

---

### 3.10 Поля wall_opening

`wall_openings` — массив объектов. Каждый объект описывает один тип отверстия на стенах комнаты.

| Поле | Тип | Обязательность | Описание |
|---|---|---|---|
| `terrain_type` | string | required | ref → `terrain_registry`. Тип ячейки: `window`, `arrow_slit`, `porthole`, `vent`, `hatch`, etc. Должен иметь `terrain_category: "barrier"` |
| `wall` | string | required | На какой стене размещать: `"north"`, `"south"`, `"east"`, `"west"`, `"any"`, `"all"`, `"perimeter"`, `"interior"` |
| `frame_material` | string | optional | ref → `material_registry`. Материал рамы. Если не задан — берётся из `wall_material` комнаты |
| `glass_material` | string\|null | optional | ref → `material_registry`. Материал заполнения (стекло, кристалл). `null` = нет заполнения (бойница, решётка). Default: `null` |
| `count` | int | conditional | Фиксированное кол-во. Взаимоисключает `count_range` |
| `count_range` | [int, int] | conditional | Диапазон кол-ва. Взаимоисключает `count` |
| `distribution` | string | optional | Расположение вдоль стены: `"evenly"`, `"random"`, `"centered"`. Default: `"evenly"` |
| `size` | int | optional | Ширина отверстия в ячейках. Default: `1` |

**Значения `wall`:**

| Значение | Описание |
|---|---|
| `"north"` / `"south"` / `"east"` / `"west"` | Конкретная стена; только exterior-ячейки этого направления |
| `"any"` | Генератор выбирает одну exterior-стену случайно |
| `"all"` | Все exterior-стены комнаты |
| `"perimeter"` | Все exterior-стены (default — окна всегда наружу) |
| `"interior"` | Только interior-стены (явный opt-in; используется для внутренних окон-передаточных) |

**Default `wall`: `"perimeter"`** — окна смотрят наружу по умолчанию.

---

**Общие правила размещения:**

**Правило 1 — наружу по умолчанию.**  
`wall` без явного `"interior"` → только exterior wall-ячейки (сосед не принадлежит ни одной комнате).

**Правило 2 — симметричное кратное размещение.**

```
available = exterior_wall_cells
    - door_cells (±1 ячейка от двери)
    - corner_cells (±1 от угла footprint)

spacing = 1   -- минимальный зазор между отверстиями
max_count = floor((len(available) + spacing) / (size + spacing))
count = min(resolved_count, max_count)

-- симметричное размещение по центру стены:
total_width = count * size + (count - 1) * spacing
start_offset = floor((len(available) - total_width) / 2)
positions = [start_offset + i * (size + spacing) for i in 0..count-1]
```

Если `count_range` задан — берётся максимальный count который вписывается симметрично.  
Если `count = 0` после вычислений → log WARNING "Стена слишком короткая для размещения отверстия", пропустить.

**Правило 3 — единая высота окон на этаже.**

```
window_z = level.window_z_offset                      -- явный override (приоритет 1)
         ?? floor(z_height * level.window_z_ratio)    -- пропорция уровня (приоритет 2)
         ?? floor(z_height * template.window_z_ratio) -- пропорция шаблона (приоритет 3)
         ?? floor(z_height * 0.4)                     -- системный дефолт
```

Все `wall_openings` на данном уровне размещаются на `z = level.base_z + window_z`.  
Разные этажи с разной `z_height` имеют разный физический `window_z` — это архитектурно корректно: высокий первый этаж имеет окна физически выше, чем низкий второй.

**Конфликт interior-окон:** если две смежные комнаты обе объявляют `wall: "interior"` на одну стену — размещает комната с меньшим `room_id` лексикографически.

**Состояния отверстия (`cell_states`):**

| Состояние | Условие | Эффект |
|---|---|---|
| `closed` | default | Непроходимо; `glass_material` блокирует видимость если `transparent: false` |
| `open` | если рама позволяет | Проходимо (лезть/прыгать); ветер, температура проникают |
| `broken` | `glass_material.breakable = true` + урон | Стекло уничтожено, рама цела; проходимо с уроном от осколков |
| `destroyed` | рама разрушена | Полная дыра в стене; проходимо свободно |

Разбиваемость определяется `material_registry[glass_material].breakable`. Рама без стекла (`glass_material: null`) — состояния `closed`/`open`/`destroyed` (нет `broken`).

**Примеры:**

```json
// Таверна — деревянные рамы, обычное стекло, бьётся
"wall_openings": [
  { "terrain_type": "window", "frame_material": "wood", "glass_material": "glass",
    "wall": "perimeter", "count_range": [2, 4], "distribution": "evenly", "size": 1 }
]

// Замковая бойница — каменная, без стекла
"wall_openings": [
  { "terrain_type": "arrow_slit", "frame_material": "stone", "glass_material": null,
    "wall": "all", "count_range": [2, 6], "distribution": "evenly", "size": 1 }
]

// Каюта корабля — железный иллюминатор, толстое стекло (не бьётся)
"wall_openings": [
  { "terrain_type": "porthole", "frame_material": "iron", "glass_material": "thick_glass",
    "wall": "east", "count": 1, "distribution": "centered", "size": 1 }
]

// Современная квартира — панорамное окно на юг
"wall_openings": [
  { "terrain_type": "window", "frame_material": "aluminum", "glass_material": "tempered_glass",
    "wall": "south", "count": 1, "distribution": "centered", "size": 4 }
]
```

`terrain_type` — любой тип из `terrain_registry` с `terrain_category: "barrier"`. Новые типы (бойница, иллюминатор, вентиляционная шахта) добавляются в реестр без изменения генератора.

---

## 4. Пример: tavern_1

```json
{
  "system_name":     "tavern_1",
  "structure_type":  "tavern",
  "display_name":    "Таверна тип 1",
  "description":     "Двухэтажная таверна с подвалом. 1й этаж: прямое соединение (нет коридора). 2й этаж: коридор с жилыми комнатами по обе стороны.",
  "version":         "1.0",
  "default_z_height": 3,
  "min_z_height":     2,

  "levels": [
    {
      "z_offset":    -1,
      "display_name": "Подвал",
      "rooms": [
        {
          "room_id":      "cellar",
          "room_type":    "cellar",
          "display_name": "Подвал",
          "shape_type":   "rectangle",
          "size":         { "size_type": "medium" },
          "required":     true,
          "count":        1
        }
      ]
    },
    {
      "z_offset":    0,
      "display_name": "Первый этаж",
      "rooms": [
        {
          "room_id":      "main_hall",
          "room_type":    "common_hall",
          "display_name": "Главный зал",
          "shape_type":   "square",
          "size":         { "size_type": "big" },
          "required":     true,
          "count":        1,
          "entry_point": {
            "wall":         "south",
            "passage_type": "main_entrance"
          }
        },
        {
          "room_id":      "kitchen",
          "room_type":    "kitchen",
          "display_name": "Кухня",
          "shape_type":   ["square", "rectangle"],
          "size":         { "size_type": "small" },
          "required":     true,
          "count":        1,
          "back_entry_point": {
            "wall":         "north",
            "passage_type": "service_entrance"
          }
        }
      ]
    },
    {
      "z_offset":    1,
      "display_name": "Второй этаж",
      "rooms": [
        {
          "room_id":      "corridor",
          "room_type":    "corridor",
          "display_name": "Коридор",
          "shape_type":   "rectangle",
          "size":         { "width_range": [8, 14], "depth_range": [2, 2] },
          "required":     true,
          "count":        1
        },
        {
          "room_id":      "guest_room",
          "room_type":    "guest_room",
          "display_name": "Комната для съёма",
          "shape_type":   "rectangle",
          "size":         { "width_range": [3, 5], "depth_range": [3, 4] },
          "required":     false,
          "count_range":  [2, 6],
          "attach_to":    "corridor",
          "attach_wall":  "both"
        }
      ]
    }
  ],

  "connections": [
    {
      "from_room":    "main_hall",
      "to_room":      "kitchen",
      "passage_type": "doorway",
      "required":     true
    },
    {
      "from_room":    "main_hall",
      "to_room":      "cellar",
      "passage_type": "staircase",
      "required":     true
    },
    {
      "from_room":    "main_hall",
      "to_room":      "corridor",
      "passage_type": "staircase",
      "required":     true
    },
    {
      "from_room":    "corridor",
      "to_room":      "guest_room",
      "passage_type": "doorway",
      "required":     true
    }
  ]
}
```

---

## 5. Хранение шаблонов

### 5.1 Глобальная библиотека — `building_templates`

```sql
CREATE TABLE IF NOT EXISTS building_templates (
    template_uid   TEXT PRIMARY KEY,   -- UUID5 hash: uuid5(NAMESPACE_DNS, system_name)
    system_name    TEXT NOT NULL UNIQUE, -- user-defined key: "tavern_1", "manor_std"
    display_name   TEXT NOT NULL,
    structure_type TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT '1.0',
    data           TEXT NOT NULL,   -- JSON blob (полный шаблон)
    source_file    TEXT             -- путь к исходному файлу, для дебага
);
```

Глобальная библиотека шаблонов. Не привязана к миру. Генератор напрямую не читает отсюда — только через per-world реестр.

**Удаление шаблона — RESTRICT:**

Шаблон нельзя удалить если хотя бы одно здание (`NamedLocation` с `system_template_uid`) ссылается на него. Приложение проверяет это до удаления и возвращает список зданий пользователю.

**Замена шаблона (update in-place):**

Пользователь может загрузить новый JSON с тем же `system_name` — выполняется `UPDATE building_templates SET data=..., version=..., source_file=... WHERE template_uid=?` после валидации.

Если здания уже используют этот `system_template_uid`:
```
1. log WARNING "N зданий будут перегенерированы по новому шаблону"
2. для каждого здания с system_template_uid:
     удалить существующие map_cells здания и его комнат
     удалить существующие NamedLocation комнат
     удалить существующие LocationPassage, LocationLevel здания
     вызвать BuildingGeneratorService.generate_from_template()
     сохранить новый BuildingLayout
```

Перегенерация выполняется синхронно до подтверждения пользователю об успехе замены шаблона.

### 5.2 Per-world реестр — `worlds.building_template_registry`

Хранится как JSON-массив внутри `worlds` (аналогично `terrain_registry`, `material_registry`):

```json
[
  { "system_template_uid": "<uuid5>", "display_template_name": "Таверна тип 1",  "imported_at": "2026-06-03T00:00:00Z" },
  { "system_template_uid": "<uuid5>", "display_template_name": "Манор стандарт", "imported_at": "2026-06-03T00:00:00Z" }
]
```

Генератор читает `system_template_uid` отсюда, затем загружает полный JSON из `building_templates`.

---

## 6. Загрузка и импорт шаблонов

### 6.1 Загрузка в глобальную библиотеку

- Пользователь загружает JSON-файл через UI (аналог импорта миров, см. tz_json_import.md)
- Один файл = один шаблон
- При загрузке: JSON валидируется через `validate_template()`; `template_uid = uuid5(system_name)` upsert по PK
- Шаблон хранится в `building_templates.data` как JSON blob

### 6.2 Импорт шаблона в мир

Явная операция пользователя: выбрать шаблон из глобальной библиотеки → импортировать в конкретный мир.

При импорте выполняется **валидация совместимости с миром**:

```
для каждого room в template.levels[].rooms:
    для wall_material, floor_material из шаблона:
        material IN worlds.material_registry → OK
        material NOT IN worlds.material_registry → ImportError

для каждого shape_type в template:
    ShapeType(shape_type).is_supported → OK
    иначе → ImportWarning (шаблон импортируется, но комната не будет сгенерирована в v1)
```

При успехе: `system_template_uid` + `display_template_name` добавляются в `worlds.building_template_registry`.  
Импортированный шаблон можно удалить из мира (убрать из реестра) — глобальная запись в `building_templates` не затрагивается.

---

## 7. BuildingLayout (возвращаемый результат)

```python
@dataclass
class BuildingLayout:
    cells:     list[MapCell]
    levels:    list[LocationLevel]
    passages:  list[LocationPassage]
    rooms:     list[NamedLocation]   # под-локации здания (каждая комната)
```

Здание (`NamedLocation` с `system_location_type="building"`):
- `system_template_uid` — ссылка на `building_templates.template_uid`; RESTRICT при удалении шаблона
- `map_x, map_y, map_z` — origin здания в глобальных координатах

Каждая комната — `NamedLocation` с:
- `system_location_type = "room"`, `system_location_subtype = room_type` из шаблона
- `parent_location_uid = building.location_uid`
- `map_x, map_y, map_z` — origin (левый нижний угол) footprint комнаты в глобальных координатах
- `is_public / is_forbidden` — из полей шаблона на комнате (не из реестра; реестр не хранит дефолты доступа)

Здание (`NamedLocation` типа `building`) после генерации получает:
- `system_template_uid` — ссылка на использованный шаблон
- `parent_wall_material` — резолвленный wall_material (ref → `world.material_registry`); fallback для ассемблера и LLM-контекста
- `parent_floor_material` — резолвленный floor_material (ref → `world.material_registry`)

---

## 8. Алгоритм генерации

### 8.1 Рандомизация

Seed: `int(md5(world_uid + building.location_uid))`. Используется `random.Random(seed)` — всё детерминировано.

### 8.2 Resolve: z_height уровней

```
effective_z_height(level) = level.z_height ?? template.default_z_height ?? 3
if effective_z_height(level) < template.min_z_height → TemplateValidationError
```

### 8.3 Resolve: shape_type комнаты

```
if isinstance(shape_type, list):
    chosen = rng.choice(shape_type)
else:
    chosen = shape_type

if ShapeType(chosen) not in _V1_SHAPES → UnsupportedShapeError
```

### 8.4 Resolve: сколько комнат генерировать

```
required=true, count=N → всегда N
required=false, count_range=[min, max] → rng.randint(min, max)
```

Для `count > 1` или `count_range` — суффикс: "Комната 1", "Комната 2", etc.

### 8.5 Resolve: размеры комнат

```
width = rng.randint(width_range[0], width_range[1])
depth = rng.randint(depth_range[0], depth_range[1])  # игнорируется для square/circle/semicircle
```

### 8.5b Resolve: материалы комнаты

**Структура записи в `world.material_registry`:**

```json
[
  {
    "system_material":    "stone",
    "display_name":       "Камень",
    "glossary_ref":       null,
    "material_category":  "solid",
    "tags":               ["construction", "mineral"],
    "use_type":           ["wall", "floor", "column"],
    "economic_tier":      "standard",
    "hardness":           3,
    "density":            250,
    "structural_strength": 0.8,
    "flammable":          false,
    "freezable":          false,
    "corrodible":         true,
    "meltable":           false,
    "mineable":           true,
    "transparent":        false,
    "components":         null
  }
]
```

| Поле | Тип | Описание |
|---|---|---|
| `system_material` | string | Уникальный ключ материала |
| `display_name` | string | Отображаемое название |
| `glossary_ref` | string\|null | nullable; ref → `lore_registry`; лор-описание для LLM |
| `material_category` | string | Физическое состояние: `solid`, `liquid`, `gas` |
| `tags` | string[] | Классификационные теги: `construction`, `metal`, `crafted`, `refined`, `raw`, `organic`, `consumable`, `mineral`, `magic` + кастомные |
| `use_type` | string[] | `wall`, `floor`, `column`, `door`, `gate`, `railing`, `ceiling`, `roof`, `any` |
| `economic_tier` | string | ref → `worlds.economic_tier_registry.system_tier` |
| `hardness` | int (1–5) | Твёрдость для `ExcavationNode` |
| `density` | int | Плотность; используется физикой (утопание, слоение жидкостей) |
| `structural_strength` | float (0–1) | Прочность; null для liquid/gas |
| `flammable` | bool | Горит. Default: false |
| `freezable` | bool | Замерзает. Default: false |
| `corrodible` | bool | Поддаётся коррозии. Default: true |
| `meltable` | bool | Плавится. Default: false |
| `mineable` | bool | Добывается. Default: false |
| `transparent` | bool | Прозрачен. Default: false |
| `components` | string[]\|null | optional. Компоненты для `crafted`/`refined` материалов |
| `temp_damage` | bool | только liquid/gas. Наносит температурный урон |
| `vision_block` | bool | только liquid/gas. Блокирует видимость |

`material_category` фиксирован в движке (solid/liquid/gas). `tags` — расширяемы через `world.material_tag_registry` (N+1).

**Прослойка: сортировка тиров по `base_value`:**

```
tiers_sorted = sorted(economic_tier_registry, key=lambda t: t.base_value)  -- ASC; строится один раз на генерацию
tier_value(tier) = economic_tier_registry[tier].base_value
```

Все сравнения тиров — через `tier_value()` и позицию в `tiers_sorted`. Никаких хардкоженных имён и числовых порогов.

**Алгоритм выбора материала:**

```
effective_tier = room.economic_tier ?? template.economic_tier ?? tiers_sorted[len//2].system_tier

def find_candidates(use):
    candidates = [mat["system_material"] for mat in world.material_registry
                  if "construction" in mat["tags"]
                  AND use in mat["use_type"]
                  AND mat["economic_tier"] == effective_tier]

    если candidates пуст:
        -- fallback: ближайший тир вниз по base_value
        current_val = tier_value(effective_tier)
        lower = [t for t in tiers_sorted if t.base_value < current_val]
        for tier in reversed(lower):  -- от ближайшего вниз
            candidates = [mat["system_material"] for mat in world.material_registry
                          if "construction" in mat["tags"]
                          AND use in mat["use_type"]
                          AND mat["economic_tier"] == tier.system_tier]
            если candidates: break
        если всё ещё пуст:
            candidates = [mat["system_material"] for mat in world.material_registry
                          if "construction" in mat["tags"] AND use in mat["use_type"]]
        если всё ещё пуст → log WARNING, return default_material
    return candidates

wall_material  = rng.choice(find_candidates("wall"))
floor_material = rng.choice(find_candidates("floor"))

# ladder: материал из world.material_registry по building_context + economic_tier
если staircase_type == "ladder":
    LADDER_CONTEXT_CATEGORIES = {
        "indoor":      ("organic", "metal", "refined"),
        "underground": ("organic", "metal", "refined", "crafted"),
        "nautical":    ("organic", "metal", "refined", "crafted"),
    }
    allowed = LADDER_CONTEXT_CATEGORIES[template.building_context ?? "indoor"]

    ladder_material = rng.choice([mat["system_material"] for mat in world.material_registry
                                  if any(c in mat["tags"] for c in allowed)
                                  AND mat["economic_tier"] == effective_tier])
    если пуст → fallback вниз по tiers_sorted (тот же allowed) + WARNING
    если всё ещё пуст → log WARNING, return default_material

    -- tags фильтрация по контексту:
    -- indoor + standard:      wood (tags: organic) ✓  rope (tags: crafted) ✗  stone ✗
    -- underground + basic:    wood ✓  rope ✓  iron (tags: metal) ✓  stone ✗
    -- nautical + quality:     дерево ✓  верёвка ✓  бронза (tags: metal) ✓
```

### 8.6 Layout: размещение комнат

Два режима — определяются наличием `attach_to` на уровне:

---

**Режим A — graph-guided placement (без коридора)**

Применяется когда ни одна комната уровня не имеет `attach_to`.

**Шаг 1 — граф смежности**

Строится неориентированный граф из `connections` данного уровня. Ребро `(A, B)` означает: A и B должны делить общую стену.

**Шаг 2 — порядок размещения (BFS)**

```
start = комната с entry_point на уровне
        (z_offset > 0 или z_offset < 0, не isolated) → комната со staircase-connection от ближайшего уровня
        (isolated: true) → комната с наибольшим degree; ничья → первая в rooms[]

очередь BFS: [start]
placed = {}

для каждой комнаты room из BFS:
    если room не размещена:
        neighbors_placed = [n for n in graph.neighbors(room) if n in placed]

        если len(neighbors_placed) >= 2:
            -- Комната должна касаться двух уже размещённых соседей (цикл в графе)
            найти угловую позицию где room одновременно смежна с neighbors_placed[0] и [1]:
                перебрать свободные позиции вдоль стен обоих соседей
                первая позиция где room касается обоих → разместить
            если угловая позиция не найдена:
                log WARNING "Room '{room_id}': кольцевая связь с {n0} и {n1}
                             геометрически невозможна — связь с {n1} пропущена"
                разместить смежно только с neighbors_placed[0] (доминантный сосед)

        иначе:
            выбрать свободную сторону у уже размещённого соседа
                (приоритет: east → south → west → north)

        если свободная сторона найдена:
            разместить room смежно с соседом
            placed[room.room_id] = (origin_x, origin_y)
        иначе (нет свободных сторон):
            → underground_fallback(room, current_level)
    добавить соседей room в очередь
```

Комнаты без connections (изолированные вершины) размещаются после BFS в оставшееся свободное пространство.

**Underground fallback:**

```
def underground_fallback(room, current_level):
    если room.underground_fallback == false:
        если room.required == false → пропустить + log WARNING
        иначе → GenerationError "Комната '{room_id}': нет места на уровне {z_offset}"

    target_z = current_level.z_offset - 1

    если уровень с target_z не существует:
        создать новый уровень:
            z_offset    = target_z
            display_name = "Подуровень {target_z}"
            z_height    = template.default_z_height
        log INFO "Авто-создан уровень z_offset={target_z} для '{room_id}'"

    разместить room на уровне target_z (свободное пространство)

    все connections к room от current_level → конвертировать в staircase
        если staircase-connection уже есть между уровнями → добавить room в тот же уровень
        иначе → создать новый staircase connection (авто-резолв room-приёмника на current_level)

    log INFO "Комната '{room_id}' перенесена на уровень z_offset={target_z}"
```

Если на target_z тоже нет места → рекурсия на target_z - 1 (глубже), но не более 2 уровней вниз → GenerationError.

**Шаг 3 — perimeter_required + entry_point wall direction**

`perimeter_required`-комнаты являются листьями графа (degree=1) — BFS автоматически ставит их на край, т.к. их единственный сосед уже размещён. Дополнительного алгоритма не требуется.

Валидация: `perimeter_required=true` + degree > 1 → `ValidationWarning` (смежность с несколькими комнатами не гарантирует периметр).

**Направленное размещение по `entry_point.wall`:**

Если на комнате объявлен `entry_point` или `back_entry_point` с конкретной стеной — BFS ставит комнату так, чтобы эта стена оказалась на внешнем периметре здания:

```
entry_point.wall = "south" → комната ставится в нижний ряд footprint (south-грань = exterior)
entry_point.wall = "north" → верхний ряд
entry_point.wall = "east"  → правый столбец
entry_point.wall = "west"  → левый столбец
```

Если нужная позиция занята другой комнатой:
```
1. Попробовать соседнюю свободную позицию вдоль того же края
2. Если весь край занят → разместить на любом свободном периметре + log WARNING
   "Room '{room_id}': entry_point.wall={wall} недостижима — размещена на другом периметре"
3. Если периметра нет вообще → GenerationError
```

`perimeter_required` форсируется автоматически для всех комнат с `entry_point` / `back_entry_point`.

**Пример — первый этаж таверны:**
```
start: main_hall (entry_point)
граф: main_hall — kitchen

[main_hall 12×12] [kitchen 3×3]
      └──── doorway ─────┘
```

Дверной проём: центр общей стены. Если высоты комнат не совпадают — центр по меньшей из двух.

---

**Режим B — коридорное соединение** (`attach_to`)

Применяется для комнат с `attach_to`. Коридор — обычная комната с `room_type: "corridor"` и своим `shape_type`, структурно ничем не отличается.

**Форма коридора** определяется `shape_type`:

| `shape_type` коридора | Описание | Статус |
|---|---|---|
| `rectangle` | Прямой коридор; комнаты вдоль длинной стороны | **v1** |
| `square` | Коридор-хаб; комнаты по всем четырём сторонам | **v1** |
| `l_shape` | Г-образный коридор | v2 |
| `t_shape` | Т-образный коридор с развилкой | v2 |

**Прикреплённые комнаты — двухпроходной расчёт:**

```
-- Проход 1: оценочный count
corridor_length = resolved corridor.width
sides           = 2 if attach_wall == "both" else 1
estimate_slots  = floor(corridor_length / min(room.width_range)) * sides
actual_count    = min(resolved_count, estimate_slots)

-- Проход 2: resolve размеры и проверить реальный fit
widths = [rng.randint(width_range[0], width_range[1]) for _ in range(actual_count)]
while sum(widths) > corridor_length и actual_count > 0:
    actual_count -= 1
    widths.pop()
    log WARNING f"Room '{room_id}': count уменьшен до {actual_count} — фактические размеры не вмещаются в коридор"
```

Прикреплённые комнаты не переносятся в "следующую строку" — только вдоль стен коридора.  
При `attach_wall: "both"` — чередуются по обе стороны.

`"any"` — генератор выбирает сторону по позиции лестницы в коридоре:
```
staircase.position IN (north, northeast, northwest) → attach_wall = "south"
staircase.position IN (south, southeast, southwest) → attach_wall = "north"
staircase.position IN (east, west, center)          → attach_wall = rng.choice(["north", "south"])
staircase-connection к коридору отсутствует         → attach_wall = rng.choice(["north", "south"])
```  
Дверной проём — на стене комнаты, смежной с коридором.

**Ограничение верхних этажей (overhang rule):**

Ground floor footprint = bounding box всех комнат на `z_offset = 0`.

Для каждой комнаты с `z_offset > 0`:
```
allowed = room.max_overhang ?? 0
room.x_min >= footprint.x_min - allowed
room.x_max <= footprint.x_max + allowed
room.y_min >= footprint.y_min - allowed
room.y_max <= footprint.y_max + allowed
```

**Ограничение подземных этажей (underground expansion rule):**

Подземные уровни (`z_offset < 0`) могут быть шире ground floor — нет гравитационного ограничения. Но расширение ограничено чтобы не конфликтовать с соседними зданиями.

Для каждой комнаты с `z_offset < 0`:
```
expansion = template.underground_expansion  -- default: 2
room.x_min >= footprint.x_min - expansion
room.x_max <= footprint.x_max + expansion
room.y_min >= footprint.y_min - expansion
room.y_max <= footprint.y_max + expansion
```

Если комната не вписывается даже с учётом `expansion` — обрезать до допустимых границ (тот же алгоритм что для верхних этажей, но с `expansion` вместо `max_overhang`). Обрезка ниже `width_range[0]` / `depth_range[0]` → пропустить + WARNING (или GenerationError если `required=true`).

Если комната выходит за `allowed`:
```
новый_width = min(room.width, footprint.x_max - room.x0 + allowed)
новый_depth = min(room.depth, footprint.y_max - room.y0 + allowed)

если новый_width < size.width_range[0] OR новый_depth < size.depth_range[0]:
    если required == true → GenerationError
                             "Комната '{room_id}': невозможно вписать в footprint — "
                             "обрезка нарушает минимальный размер"
    иначе → пропустить комнату + WARNING
иначе:
    log WARNING "Комната '{room_id}': размер обрезан до {новый_width}×{новый_depth} "
                "для соответствия footprint верхнего этажа"
    использовать новый_width, новый_depth
```

Балкон с `has_column: true` → ячейки `column` (is_structural=True) размещаются на **ground floor** (z_offset=0) под каждым выступающим углом балкона. `column` — terrain type, `cell_material` = wall_material здания.

### 8.7 Cells

Генерация ячеек — три отдельных прохода. Комнаты **не генерируют стен** — только пол.

**Проход 1 — внешний контур здания**

Exterior wall строится по реальному контуру комнат — не bounding box:

```
room_cells = union всех (x, y) footprint всех комнат уровня

для каждой (x, y) в room_cells:
    для каждого соседа (nx, ny) в 4 направлениях:
        если (nx, ny) ∉ room_cells:
            поставить wall на (nx, ny)  -- exterior wall
```

| Ячейка | `system_building_element` | `is_structural` | `location_uid` |
|--------|-----------------|-----------------|----------------|
| Внешняя стена | `wall` | `True` | building |
| Дверь entry_point / back_entry_point | `door` | `False` | building |

**Gap-области** (внутри bounding box, вне room_cells) — обрабатываются по `gap_policy`:

```
effective_policy = gap_policy
если gap_policy == "random":
    effective_policy = rng.choice(["clip", "fill"])

если effective_policy == "clip":
    gap-ячейки не создаются — снаружи пустота

если effective_policy == "fill":
    для каждой связной gap-области:
        создать NamedLocation(
            system_location_subtype = "utility_space",
            display_name            = "Техническое помещение",
            system_location_type    = "room",
            is_accessible = True,
            parent_location_uid = building.location_uid,
        )
        gap-ячейки → floor, location_uid = utility_room
        граница gap-области с соседней комнатой → shared segment (Проход 3)
        граница gap-области с внешней стеной → уже покрыта Проходом 1

        -- авто-дверь: найти самый длинный shared segment с соседней комнатой
        -- исключить сегменты уже занятые дверью другого gap-региона
        candidates = sorted(adjacent_rooms,
                            key=lambda r: len(shared_segment(utility_room, r)),
                            reverse=True)
        best_neighbor = first candidate WHERE shared_segment не содержит уже размещённую door
        если все сегменты заняты:
            best_neighbor = candidates[0]  -- использовать лучшего несмотря на занятость
            смещать door на ±1 ячейку от центра пока не найдём свободную позицию
            если позиции нет → gap-регион остаётся без двери + log WARNING
                               "Gap-регион: все сегменты с '{best_neighbor}' заняты"

        поставить door в центре shared_segment(utility_room, best_neighbor)
        создать LocationPassage(
            passage_type     = "doorway",
            is_bidirectional = True,
            from_room        = utility_room,
            to_room          = best_neighbor,
        )
```

**Проход 2 — пол комнат**

Для каждой комнаты вызов cell-генератора по `shape_type` — только interior-ячейки:

| Ячейка | `system_building_element` | `is_structural` | `location_uid` |
|--------|-----------------|-----------------|----------------|
| Пол | `floor` | `False` | room |

Периметр комнаты генератором комнаты **не создаётся**.

**Проход 3 — внутренние несущие стены**

Для каждого ребра BFS-графа (пары смежных комнат) — shared segment: единственная стена на границе двух комнат. Стена принадлежит зданию.

| Ячейка | `system_building_element` | `is_structural` | `location_uid` |
|--------|-----------------|-----------------|----------------|
| Несущая стена (shared segment) | `wall` | `True` | building |
| Дверной проём в несущей стене | `door` | `False` | building |

Shared segment = один ряд ячеек на границе footprint двух комнат. Дверь — центр отрезка пересечения их смежных сторон; если стороны разной длины — центр по **меньшей** из двух.

Нет дублирующихся `(world_uid, x, y, z)`: здание создаёт внешний контур один раз, комнаты создают только пол, несущие стены создаются по рёбрам графа один раз.

### 8.8 Passages (LocationPassage)

Каждый connection → один `LocationPassage`:
- `from_x/from_y` — центр дверного проёма в from_room
- `to_x/to_y` — центр дверного проёма в to_room
- `is_bidirectional = True` по умолчанию

**Разрешение уровня по room_id:**

`room_id` уникален по всему шаблону (гарантируется валидацией) → уровень комнаты определяется однозначно:

```
level_of(room_id) = level где объявлен room_id
from_level_uid    = level_uid(level_of(connection.from_room))
to_level_uid      = level_uid(level_of(connection.to_room))
```

**`staircase`:**
- `from_level_uid.z ≠ to_level_uid.z` — обязательное условие; нарушение → `ValidationError`
- Если `count_range > 1` у целевой комнаты — connection адресует instance_0 (первый экземпляр)

Позиция staircase-ячейки в `to_room` — из поля `position` на connection. Если `position` не задан:
```
to_room.room_type == "corridor"              → edge (west или east, rng.choice)
to_room.room_type IN ("common_hall", "hall") → center
иначе                                        → edge
```

Позиция staircase-ячейки в `from_room` — симметрично: тот же приоритет по room_type from_room.

> Детальная структура лестниц (геометрия ячеек, типы маршей) — дополняется отдельно.

**Авто-резолв staircase (fallback):**

Если уровень `isolated=false` и ни один `staircase`-connection к нему не объявлен:
```
log WARNING "Уровень '{display_name}': staircase не объявлен — авто-резолв"

to_room = первая комната с room_type "corridor"
          ?? первая с room_type "common_hall"
          ?? комната с наибольшим degree в connection-графе уровня
          ?? первая в rooms[]

from_room = комната смежного уровня по той же приоритетной цепочке
```
Авто-резолв создаёт `LocationPassage` типа `staircase` и staircase-ячейки аналогично явному connection.

**`entry_point` / `back_entry_point`:**
- `LocationPassage` с `from_level_uid = null` (внешнее пространство) → `to_level_uid` уровня комнаты
- `from_x/from_y = null`; `to_x/to_y` = координата door-ячейки на указанной стене

### 8.9 Levels (LocationLevel)

```python
level_uid = uuid5(building_uid, f"level_{z_offset}")
level_z   = computed via z_height stacking (см. раздел 3.2)
```

---

## 9. Интерфейс сервиса

```python
class BuildingGeneratorService:

    def generate_from_template(
        self,
        world:    World,
        building: NamedLocation,
        template: dict,           # уже загруженный JSON как dict
    ) -> BuildingLayout: ...

    def validate_template(self, data: dict) -> list[str]:
        """Возвращает список ошибок валидации. Пустой список = OK."""
        ...
```

---

## 10. Валидация шаблона

`validate_template` проверяет:
- Все обязательные поля присутствуют
- `room_type` каждой комнаты существует в `worlds.room_type_registry` → иначе `ImportError`
- `is_public` и `is_forbidden` присутствуют на каждой комнате → иначе `ValidationError`
- Ровно одна комната имеет `entry_point` (если нужен вход)
- Не более одной комнаты с `back_entry_point`
- `entry_point.room_id` и `back_entry_point.room_id` существуют в `levels[].rooms`
- Все `connections[].from_room` и `.to_room` существуют в `levels[].rooms`
- `attach_to` комнаты ссылается на `room_id` того же уровня
- `size.size_type` + `size.width_range`/`size.depth_range` одновременно → ValidationError
- `size.size_type` отсутствует и `size.width_range` не задан → ValidationError
- `width_range[0] ≤ width_range[1]`, то же для `depth_range`, `count_range`, `z_range`
- `required: false` + `count_range` отсутствует → `ValidationError` ("room '{room_id}': required=false требует count_range")
- `count_range[0] < 1` → `ValidationError` ("room '{room_id}': count_range минимум [1, 1]")
- `gap_policy` не из `{"clip", "fill", "random"}` → `ValidationError`
- `building_context` не из `{"indoor", "underground", "nautical"}` → `ValidationError`
- Нет дублирующихся `room_id` в рамках всего шаблона (не только уровня)
- `effective_z_height ≥ min_z_height` для каждого уровня
- Все `shape_type` — валидные значения `ShapeType`; v1: + `is_supported = True`
- Если `shape_type` — массив: все элементы валидны; в v1 все из `_V1_SHAPES`
- Комната с `entry_point` или `back_entry_point` + явным `perimeter_required: false` → ValidationWarning (не ошибка; генератор форсирует периметр)
- Комната с `attach_to` + `entry_point`/`back_entry_point` → ValidationWarning (архитектурно некорректно)
- `perimeter_required: true` + degree в connection-графе > 1 → ValidationWarning (периметр не гарантирован)
- Циклы в connection-графе (intra-level doorway/archway) → `ValidationWarning`; генератор пытается разместить геометрически (см. ниже)
- `connection.passage_type == "staircase"` + `from_room` и `to_room` на одном `z_offset` → ValidationError
- `staircase_type` не из `{"ladder", "spiral_small", "spiral_standard", "standard", "straight"}` → ValidationError
- `staircase_type` задан на non-staircase connection → ValidationWarning (игнорируется)
- `position` задан на non-staircase connection → ValidationWarning (игнорируется)
- `connection.passage_type != "staircase"` + `from_room` и `to_room` на разных `z_offset` → ValidationError
- `connection` к `room_id` с `count_range > 1` → ValidationWarning (адресует instance_0)
- `max_overhang > 0` допустим только для `room_type: "balcony"`
- `max_overhang > 2` требует `has_column: true`
- `max_overhang > 4` → ValidationError (абсолютный максимум)
- `has_column: true` без `max_overhang > 2` → ValidationWarning (колонна без смысла)
- Минимум 1 уровень, минимум 1 комната на уровне
- Уровень без staircase-connection и без `isolated: true` → `ValidationError` ("уровень недостижим")
- `isolated: true` + `access_mechanic: []` (пустой или не задан) → `ValidationWarning` ("уровень недостижим без механики доступа")
- `isolated: false` + `access_mechanic` задан → `ValidationWarning` ("access_mechanic игнорируется на не-изолированном уровне")
- `access_mechanic` содержит неизвестное значение → `ValidationError`
- `underground_fallback: true` + `required: true` — допустимо; fallback создаст уровень если нужно
- `underground_fallback: true` + `required: false` — бессмысленно (required=false и так пропускается); `ValidationWarning`

---

## 11. StructureAssembler

`BuildingGeneratorService` генерирует **interior box** — комнаты, стены, проходы. Он не знает, стоит ли здание на земле, парит в мегаструктуре или является палубой корабля.

`StructureAssembler` — обёртка, которая добавляет **фундамент** и **крышу** в зависимости от контекста здания.

```
BuildingGeneratorService.generate_from_template()  →  interior box
           ↓
StructureAssembler.assemble()                       →  полный BuildingLayout
```

---

### 11.1 StructureContext

```python
@dataclass
class StructureContext:
    foundation_type:     str              # "none" | "slab" | "perimeter" | "full" | "stilts" | "hull"
    roof_type:           str | list[str]  # строка или список → выбирает по footprint; "auto" = авто
    foundation_depth:    int   = 1        # z-юниты вглубь; только для "slab" / "hull"
    slope_step:          float = 1.0      # ячеек shrink за 1 z-юнит; 1.0 ≈ 45°
    foundation_material: str | None = None  # Fallback: building.parent_wall_material
    roof_material:       str | None = None  # Fallback: building.parent_wall_material
    porch_material:      str | None = None  # Fallback: building.parent_floor_material
    porch_has_roof:      bool = False       # Навес над крыльцом → создаёт NamedLocation
```

---

### 11.2 Типы фундамента

**Инвариант:** пол здания (`building.map_z`) всегда плоский. Terrain под ним может быть неровным — фундамент адаптируется.

Ассемблер читает terrain под footprint здания из `map_cells` перед генерацией:

```
для каждой (x, y) в footprint:
    terrain_z[x,y] = max(z) WHERE world_uid AND x AND y  -- поверхностная ячейка
    gap[x,y] = building.map_z - terrain_z[x,y]           -- сколько ячеек заполнить
    если gap[x,y] <= 0: ячейка не нужна (terrain на уровне пола или выше)
```

**Конфликт с terrain:** foundation-ячейки заменяют terrain-ячейки на тех же (x, y, z) — INSERT OR REPLACE.

| `foundation_type` | Описание | Глубина | Форма |
|---|---|---|---|
| `"none"` | Нет фундамента | — | — |
| `"slab"` | Монолитная плита фиксированной толщины | `foundation_depth` (не читает terrain) | все (x,y) footprint |
| `"perimeter"` | Периметральная лента вдоль рельефа | `gap[x,y]` per-column | только внешний контур |
| `"full"` | Полный массив вдоль рельефа | `gap[x,y]` per-column | все (x,y) footprint |
| `"stilts"` | Колонны-опоры | `gap[x,y]` per-column | N support-точек; между ними `open_space` |
| `"hull"` | Корпусная плита | `foundation_depth` (не читает terrain) | все (x,y) footprint |

**`"slab"` vs `"perimeter"`:**
- `"slab"` — terrain заранее выровнен или нужна строго заданная толщина; глубина фиксирована
- `"perimeter"` / `"full"` — неровный рельеф; фундамент заполняет разрыв между terrain и полом здания per-column

Ячейки фундамента: `is_structural = True`, `location_uid = building.location_uid`.

**Подвал ниже фундамента:**

Уровни с `z_offset < 0` смещаются ниже фундаментного слоя. Ассемблер применяет поправку к z-расчёту раздела 3.2:

```
z(z_offset < 0) = building.map_z
                  - context.foundation_depth     ← пропуск фундаментного слоя
                  - Σ(z_height for z_offset in N..-1)
```

Пример: `foundation_depth=2`, подвал `z_height=3`:
```
foundation:  z = -2, -1        (фундаментный слой)
basement:    z = -5, -4, -3    (ниже фундамента)
```

Для `foundation_type="none"`: `foundation_depth=0` → поправка не применяется, поведение как прежде.

**Лестница через фундамент:** staircase-ячейки имеют `system_building_element="staircase"` и перезаписывают foundation-ячейки на тех же (x,y,z) — INSERT OR REPLACE. Здание побеждает над фундаментом.

---

### 11.3 Типы крыши

Крыша — геометрический алгоритм поверх **реального контура** здания. Ассемблер читает фактический footprint из `BuildingLayout` и строит крышу по нему — форма крыши зависит от формы здания.

`roof_type` — строка или массив строк. Если массив — ассемблер выбирает первый совместимый тип по форме footprint:
```
roof_type = ["hip", "gable", "flat"]
→ пробует hip (прямоугольник?), затем gable, fallback flat
```

---

**Базовые z-координаты:**
```
roof_base_z = z(top_level) + z_height(top_level)
```

Ячейки крыши: `system_terrain = "roof"`, `is_structural = True`, `location_uid = building.location_uid`.

---

**Алгоритм shrink (общий для скатных крыш):**

Скатная крыша строится послойно: каждый z-слой — footprint, сжатый внутрь на `slope_step` ячеек:

```
для z = roof_base_z, roof_base_z+1, roof_base_z+2 ...:
    layer_footprint = shrink(outer_footprint, offset=(z - roof_base_z) * slope_step)
    если layer_footprint пуст → остановить
    создать roof-ячейки для layer_footprint
```

`slope_step` (default: 1) — как быстро крыша сужается. `slope_step=1` ≈ 45°; `slope_step=0.5` ≈ пологая; `slope_step=2` ≈ крутая.

---

**Типы крыш:**

| `roof_type` | Русское название | Shrink-направление | Совместимость footprint | Статус |
|---|---|---|---|---|
| `"none"` | Нет крыши | — | любой | v1 |
| `"flat"` | Плоская | нет (1 слой) | любой | v1 |
| `"gable"` | Двускатная | north + south (или east + west) | прямоугольник | v1 |
| `"hip"` | Вальмовая | все 4 стороны равномерно | прямоугольник / квадрат | v2 |
| `"half_hip"` | Полувальмовая | 2 скоса + 2 вальмовых торца | прямоугольник | v2 |
| `"pyramid"` | Шатровая | все 4 стороны, сходятся в точку | квадрат / near-square | v2 |
| `"multi_gable"` | Многощиповая | несколько gable-секций | сложный (L/T/неровный) | v2 |
| `"mansard"` | Мансардная | крутой нижний скат + пологий верх | прямоугольник | v2 |
| `"battlements"` | Зубцы | чередующиеся wall/open_space по периметру | любой | v2 |
| `"hull"` | Корпусная крышка | нет (1 слой, hull-материал) | любой | v1 |

---

**Двускатная (`"gable"`) — v1:**

```
ось конька: вдоль длинной стороны прямоугольника
shrink: только по короткой оси (north + south)
конёк: центральный ряд ячеек на max z
```

Пример, прямоугольник 10×6, slope_step=1:
```
roof_base_z+0: 10×6  (полный периметр)
roof_base_z+1: 10×4  (shrink по N+S на 1)
roof_base_z+2: 10×2  (shrink ещё на 1)
roof_base_z+3: 10×0  → конёк: 10×1
```

---

**Мансардная (`"mansard"`) — v2:**

Два пояса:
```
нижний пояс (slope_step=2, steep): занимает ~40% высоты крыши
верхний пояс (slope_step=0.5, shallow): плоская зона → жилое пространство (мансарда)
```
Жилая зона мансарды → `LocationLevel` с типом `attic` на `roof_base_z + lower_height`.  
Доступ: лестница от верхнего этажа (см. 11.3.1).

---

**Совместимость `roof_type` × `shape_type`:**

| `shape_type` | `gable` | `hip` | `pyramid` | `flat` | `hull` | `none` |
|---|---|---|---|---|---|---|
| `rectangle` | ✓ | ✓ | — | ✓ | ✓ | ✓ |
| `square` | деген. | ✓ | ✓ | ✓ | ✓ | ✓ |
| `circle` | ✗ | — | ✓ (конус) | ✓ | ✓ | ✓ |
| `semicircle` | ✗ | — | — | ✓ | ✓ | ✓ |
| `semi_oval` | ✗ | — | — | ✓ | ✓ | ✓ |
| `l_shape` | ✗ | ✓ (valley) | — | ✓ | ✓ | ✓ |
| `t_shape` | ✗ | ✓ (два valley) | — | ✓ | ✓ | ✓ |

`gable` требует две чётко противоположные параллельные стороны — не применим к круглым и составным формам.  
`pyramid` требует near-square footprint — для circle естественно даёт конус.  
`l_shape`/`t_shape` + `hip` → shrink-алгоритм создаёт **valley (ендову)** в местах соединения секций — архитектурно корректно.

**Несовместимая комбинация → fallback:**
```
если roof_type несовместим с shape_type здания:
    fallback: hip → flat
    log WARNING "roof_type={type} несовместим с shape={shape} — заменён на {fallback}"
```

---

**Авто-выбор по фактическому footprint:**

`"auto"` анализирует **building_footprint** — union всех room_cells после layout. Не зависит от `shape_type` отдельных комнат (BFS может создать L-форму из прямоугольных комнат).

```
building_footprint = union(room_cells for all rooms on level)
bbox               = bounding_box(building_footprint)
coverage           = len(building_footprint) / (bbox.width × bbox.height)
aspect             = max(bbox.width, bbox.height) / min(bbox.width, bbox.height)

если coverage < 0.75:
    → сложная форма (L/T/нерегулярная) → "hip"
иначе если aspect > 2.0:
    → вытянутый прямоугольник → "gable"
иначе если aspect ≤ 1.2:
    → near-square / квадрат → "pyramid"
иначе:
    → "hip"
```

`coverage < 0.75` — footprint занимает менее 75% bounding box → L/T-форма или нерегулярный контур → valley при hip корректна.

Примеры:
```
10×10 square room:          coverage=1.0, aspect=1.0  → pyramid
14×4 corridor + 3×4 rooms:  coverage=0.65, aspect=3.5 → hip (coverage < 0.75)
12×6 rect hall:             coverage=1.0, aspect=2.0  → gable
L-shape (все rect комнаты): coverage=0.7, aspect=1.3  → hip
```

---

### 11.3.1 Доступ на крышу

`"flat"` и `"mansard"` создают жилую зону на крыше → нужен `LocationLevel` + стaircase.

**v1:** roof-ячейки генерируются, `LocationLevel` не создаётся. Крыша физически существует, но недостижима через навигацию — только через игровые механики.

**v2:** добавить `roof_access_room: str | None` в `StructureContext`. Ассемблер создаёт `LocationLevel` + staircase от указанной комнаты верхнего этажа (`None` = авто-выбор).

---

Крыша строится в самом конце — после того как `BuildingGeneratorService` вернул полный layout с реальным footprint.

---

### 11.4 Интерфейс

```python
class StructureAssembler:

    def assemble(
        self,
        world:         World,
        building:      NamedLocation,
        template:      dict,
        context:       StructureContext,
        terrain_cells: list[MapCell] | None = None,
        # terrain_cells актуален только для ground-based зданий.
        # Для корабля, космического корабля, среза мегаздания — None:
        # нет terrain под зданием, foundation_type = "hull" | "none"
    ) -> BuildingLayout:
        layout = BuildingGeneratorService().generate_from_template(world, building, template)
        if context.foundation_type != "none":
            layout.cells.extend(self._generate_foundation(layout, context, terrain_cells))
        if context.roof_type != "none":
            layout.cells.extend(self._generate_roof(layout, context))
        return layout
```

`terrain_cells` — запрашиваются вызывающим кодом до вызова ассемблера для ground-based зданий:
```
terrain_cells = map_cell_repo.get_surface_cells(world_uid, footprint_xy_list)
```
Для `foundation_type in ("hull", "none")` — `terrain_cells = None`; ассемблер не читает рельеф.

---

### 11.5 Примеры контекстов

| Здание | `foundation_type` | `roof_type` | Примечание |
|---|---|---|---|
| Таверна (v1) | `"perimeter"` | `"gable"` | двускатная; длинная ось = конёк |
| Таверна (v2) | `"perimeter"` | `["hip", "gable"]` | предпочтительно вальмовая |
| Дом жилой | `"perimeter"` | `["hip", "gable", "flat"]` | авто по форме |
| Замок, башня (v1) | `"full"` | `"flat"` | плоская; battlements → v2 |
| Замок, башня (v2) | `"full"` | `["battlements", "hip"]` | зубцы или вальмовая |
| Особняк с мансардой | `"full"` | `"mansard"` | жилой чердак; v2 |
| Шатровая башня | `"full"` | `"pyramid"` | square footprint; v2 |
| Современный дом | `"slab"` | `"flat"` | terrain выровнен |
| Дом на сваях / пристань | `"stilts"` | `"gable"` | над водой; uneven terrain |
| Срез мегаздания (Cyberpunk) | `"none"` | `"none"` | нет terrain; нет крыши |
| Палуба корабля | `"hull"` | `"hull"` | terrain_cells = None |
| Палуба космического корабля | `"hull"` | `"hull"` | terrain_cells = None |
| Пещерный комплекс | `"none"` | `"none"` | скала вокруг = и есть стены |
| Подземный данж | `"none"` | `"flat"` | потолок = flat, пол на terrain |

---

### 11.6 Источник контекста

`StructureContext` не хранится в шаблоне — шаблон описывает только interior.  
Контекст определяется на вызывающем уровне:

- `CityGeneratorService` вызывает `StructureAssembler` с контекстом на основе `location_type` здания и настроек мира
- При ручном размещении здания — пользователь выбирает контекст в UI
- `building_template_registry` может хранить рекомендованный контекст (`default_structure_context`) как подсказку — не обязательный

---

## 12. Что НЕ входит в v1

| Фича | Статус |
|------|--------|
| shape_type: polygon (ray-casting по произвольным вершинам) | v3 |
| Явное позиционирование комнат (координаты в шаблоне) | v2 |
| Вращение/зеркало здания при размещении | v2 |
| terrain_overrides на уровне комнаты | v2 |
| Процедурная генерация без шаблона | нет ТЗ |
| `ExcavationNode` — логика раскопки изолированного уровня | нет ТЗ |
| `TeleportNode` — логика телепорта к изолированному уровню | нет ТЗ |

---

## 13. Механика колонн и мостов

### 13.1 Column proximity algorithm

Вместо статичного флага `has_column: true` в шаблоне — динамическая проверка в рантайме:

```
для каждой edge-ячейки балкона (выступающий край):
    scan_radius = 3  # клетки
    has_support = EXISTS map_cell WHERE
        system_building_element = "column"
        AND distance(edge_cell, column_cell) <= scan_radius
        AND z = level.z  -- колонна на том же уровне или ниже

if has_support:
    effective_max_overhang = 4
else:
    effective_max_overhang = 2
```

Шаблон объявляет `max_overhang` как **запрошенный** выступ. Генератор вычисляет **effective_max_overhang** через proximity check и обрезает до минимума:

```
actual_overhang = min(room.max_overhang, effective_max_overhang)
```

Колонна может быть:
- размещена самим генератором (при `has_column: true` в шаблоне → генератор ставит `column` и затем проверяет proximity)
- уже существующей в `map_cells` (колонны от предыдущей генерации, ручного размещения, другого здания)

Это делает алгоритм открытым: чужая колонна во дворе тоже считается опорой.

### 13.2 Bridge между зданиями

Балконная механика как шаблон для перехода между зданиями на верхнем этаже:

```
Здание A (балкон east, max_overhang=4, has_column)
Здание B (балкон west, max_overhang=4, has_column)

gap = B.footprint.x_min - A.footprint.x_max
bridge_possible = gap <= A.actual_overhang + B.actual_overhang
```

Если `bridge_possible`:
- Балкон A и балкон B смыкаются или перекрываются по x
- Создаётся `LocationPassage` типа `bridge` с:
  - `from_level_uid` = level_uid здания A (z_offset=1)
  - `to_level_uid` = level_uid здания B (z_offset=1)
  - `is_bidirectional = True`
- Ячейки моста: `floor`, `location_uid = null` или отдельная NamedLocation типа `bridge`

**Применение:**
- Переход между крыльями одного здания (манор, замок)
- Улица с аркадами — балконы нескольких зданий смыкаются в проход
- Подвесной мост между башнями
- Знатный дом с внутренним двором — крытые галереи на втором этаже

### 13.3 Статус

| Компонент | Статус |
|---|---|
| `has_column: true` в шаблоне → генератор ставит column-ячейки | v1 (упрощённо: `has_column` = флаг) |
| Column proximity algorithm (scan_radius=3) | v2 |
| Bridge passage между двумя зданиями | v2 |
| Чужая колонна как опора (cross-building proximity) | v2 |

---

## 14. Открытые вопросы

| Вопрос | Статус |
|--------|--------|
| `system_template_uid` на `NamedLocation` здания | Решено: хранится на здании; RESTRICT при удалении; замена → перегенерация всех зданий |
| Общие стены смежных комнат: `location_uid = building` или одной из комнат? | Решено: building, `is_structural=True`; комнаты генерируют только пол |
| `attach_wall: "any"` — генератор выбирает сторону по seed или по свободному месту? | Решено: зависит от позиции лестницы в коридоре |
| Внешний контур здания — bounding box или реальный периметр? | Решено: реальный контур + `gap_policy: "clip"/"fill"/"random"` |
| `count_range: [0, 0]` допустимо? | Решено: минимум `[1, 1]` → `ValidationError` если `count_range[0] < 1` |
| `arm_width`/`arm_depth` для `l_shape`/`t_shape` — как задаётся в объекте `size` | Решено: отдельный объект `shape_params` на уровне комнаты (раздел 3.5b) |
| Valley-ячейки (`hip` на `l_shape`/`t_shape`) — какой terrain type | Решено: все ячейки крыши = `roof`; valley — геометрический эффект shrink, не отдельный тип |
| `dominant shape_type` для `auto` крыши — алгоритм определения | Решено: анализ фактического footprint (coverage + aspect ratio), не shape_type комнат |
| `porch`/`entrance_steps` — добавить как субтипы в `location_type_registry` | Решено: субтипы `room` в реестре; `is_outdoor` override на уровне записи |
| `is_transit` — поведение в engine flow (сквозной переход без остановки сцены) | Решено: `SceneStartLocationSelectNode` пропускает транзитную локацию и идёт к следующей через passage |
| `StructureAreaAssembler` — алгоритм вывода `StructureContext` | закрывается в отдельном ТЗ; см. [tz_assembler_hierarchy.md](tz_assembler_hierarchy.md) |
