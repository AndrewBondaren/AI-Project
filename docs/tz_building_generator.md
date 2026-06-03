# ТЗ: Генератор зданий

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
| `template_uid` | string | required | Уникальный идентификатор шаблона |
| `structure_type` | string | required | Смысловой тип: tavern, shop, dungeon, house, etc. |
| `display_name` | string | required | Отображаемое название шаблона |
| `description` | string | optional | Описание для UI |
| `version` | string | required | Версия шаблона: `"1.0"` |
| `default_z_height` | int | optional | Высота потолка по умолчанию для всех уровней. Default: `3` |
| `min_z_height` | int | optional | Минимально допустимая высота потолка любого уровня. Default: `2` |
| `gap_policy` | string | optional | Поведение для gap-областей (внутри bounding box, вне всех комнат): `"clip"`, `"fill"`, `"random"`. Default: `"clip"` |
| `wealth_level` | string | optional | Уровень богатства здания для выбора материалов: `"poor"`, `"common"`, `"wealthy"`, `"noble"`, `"royal"`. Default: `"common"` |
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
| `room_type` | string | required | Смысловой тип: common_hall, kitchen, cellar, corridor, guest_room, etc. |
| `display_name` | string | required | Название для `NamedLocation.display_name` |
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
| `wealth_level` | string | optional | Переопределяет уровень богатства для этой комнаты. Если не задан — берётся из шаблона |
| `entry_point` | object | optional | Объявляет главный вход здания на этой комнате. Только одна комната в шаблоне |
| `back_entry_point` | object | optional | Объявляет чёрный вход здания на этой комнате. Только одна комната в шаблоне |

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

### 3.6 Поля entry_point / back_entry_point (на комнате)

| Поле | Тип | Описание |
|------|-----|----------|
| `wall` | string | Стена: `north`, `south`, `east`, `west` |
| `passage_type` | string | `main_entrance`, `service_entrance` |

Вход размещается на центральной ячейке указанной стены. Тип terrain: `door`.
`LocationPassage` создаётся с `from_level_uid = null` (внешнее пространство) → `to_level_uid` уровня этой комнаты.

---

### 3.7 Поля connection

| Поле | Тип | Описание |
|------|-----|----------|
| `from_room` | string | `room_id` источника |
| `to_room` | string | `room_id` цели |
| `passage_type` | string | `doorway`, `staircase`, `archway`, etc. |
| `required` | bool | Если обе комнаты сгенерированы — проход обязателен |
| `position` | string | optional. Только для `staircase`. Позиция ячейки лестницы внутри `to_room`: `"center"`, `"north"`, `"south"`, `"east"`, `"west"`, `"northwest"`, `"northeast"`, `"southwest"`, `"southeast"`. Если не задан — авто-резолв |
| `staircase_type` | string | optional. Только для `staircase`. Тип лестницы (см. раздел 3.9). Если не задан — авто-резолв по `z_height` |

Если одна из комнат не была сгенерирована (например, пропущена из-за ограничений footprint верхнего этажа) — connection пропускается.  
Для `staircase`: `from_level_uid.z ≠ to_level_uid.z`; ячейка типа `staircase` на обоих уровнях.

---

### 3.8 shape_type

`shape_type` — строка или массив строк. Если массив — генератор выбирает один случайно через `rng.choice(shape_type)`.

| `shape_type` | Описание | Алгоритм ячеек | Статус |
|---|---|---|---|
| `rectangle` | Прямоугольник | `x ∈ [x₀, x₀+w)` AND `y ∈ [y₀, y₀+d)`; стена на границе, пол внутри | **v1** |
| `square` | Квадрат | то же; `w = d = min(width, depth)` | **v1** |
| `semicircle` | Полукруг; плоская стена на стороне среза | `(x−cx)² + (y−cy)² ≤ r²` AND `y ≥ cy`; `r = width / 2` | v2 |
| `semi_oval` | Полуовал; плоская стена сверху | `(x/a)² + (y/b)² ≤ 1` AND `y ≥ 0`; `a = width / 2`, `b = depth` | v2 |
| `l_shape` | Г-образный; параметры `arm_width`, `arm_depth` | `R1 ∪ R2`; R1 = main body (`width × depth`), R2 = arm смещён в угол | v2 |
| `t_shape` | Т-образный; параметр `arm_depth` | `R1 ∪ R2 ∪ R3`; R1 = горизонтальная балка (`width × arm_depth`), R2/R3 = столбы | v2 |
| `circle` | Круг | `(x−cx)² + (y−cy)² ≤ r²`; `r = width / 2` | v2 |
| `polygon` | Произвольный полигон | ray-casting test для набора вершин из шаблона | v3 |

`width_range` / `depth_range` по shape_type:

| `shape_type` | `width_range` | `depth_range` |
|---|---|---|
| `rectangle` | ширина (X) | глубина (Y) |
| `square` | сторона | игнорируется |
| `semicircle` | диаметр | игнорируется |
| `semi_oval` | ширина (2a) | глубина полуоси (b) |
| `circle` | диаметр | игнорируется |

В v1 любой `shape_type` кроме `rectangle` и `square` → `UnsupportedShapeError` при загрузке шаблона.

---

### 3.9 Типы лестниц (staircase_type)

| `staircase_type` | Footprint | Описание | Применение |
|---|---|---|---|
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
если staircase_type не задан:
    если z_height <= 5 → standard
    иначе              → straight
```

> Детальная геометрия ячеек каждого типа (шаги, площадки, перила) — дополняется отдельно.

---

## 4. Пример: tavern_1

```json
{
  "template_uid":    "tavern_1",
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
    template_uid   TEXT PRIMARY KEY,
    structure_type TEXT NOT NULL,
    display_name   TEXT NOT NULL,
    version        TEXT NOT NULL DEFAULT '1.0',
    data           TEXT NOT NULL,   -- JSON blob (полный шаблон)
    source_file    TEXT             -- путь к исходному файлу, для дебага
);
```

Глобальная библиотека шаблонов. Не привязана к миру. Генератор напрямую не читает отсюда — только через per-world реестр.

**Удаление шаблона — RESTRICT:**

Шаблон нельзя удалить если хотя бы одно здание (`NamedLocation` с `template_uid`) ссылается на него. Приложение проверяет это до удаления и возвращает список зданий пользователю.

**Замена шаблона (update in-place):**

Пользователь может загрузить новый JSON с тем же `template_uid` — выполняется `UPDATE building_templates SET data=..., version=..., source_file=... WHERE template_uid=?` после валидации.

Если здания уже используют этот `template_uid`:
```
1. log WARNING "N зданий будут перегенерированы по новому шаблону"
2. для каждого здания с template_uid:
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
  { "template_uid": "tavern_1",  "imported_at": "2026-06-03T00:00:00Z" },
  { "template_uid": "manor_std", "imported_at": "2026-06-03T00:00:00Z" }
]
```

Генератор читает `template_uid` отсюда, затем загружает полный JSON из `building_templates`.

---

## 6. Загрузка и импорт шаблонов

### 6.1 Загрузка в глобальную библиотеку

- Пользователь загружает JSON-файл через UI (аналог импорта миров, см. tz_json_import.md)
- Один файл = один шаблон
- При загрузке: JSON валидируется через `validate_template()`; `template_uid` upsert по PK
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

При успехе: `template_uid` добавляется в `worlds.building_template_registry`.  
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

Здание (`NamedLocation` с `location_type="building"`):
- `template_uid` — ссылка на `building_templates.template_uid`; RESTRICT при удалении шаблона
- `map_x, map_y, map_z` — origin здания в глобальных координатах

Каждая комната — `NamedLocation` с:
- `location_type = "room"`, `location_subtype = room_type` из шаблона
- `parent_location_uid = building.location_uid`
- `map_x, map_y, map_z` — origin (левый нижний угол) footprint комнаты в глобальных координатах
- `is_public / is_forbidden` — из `room_type_registry.default_is_public/forbidden`

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
"stone": {
  "display_name": "Камень",
  "category": ["construction", "mineral"],
  "use_type": ["wall", "column"],
  "wealth_level": "common",
  "hardness": 3
}
```

| Поле | Тип | Описание |
|---|---|---|
| `display_name` | string | Отображаемое название |
| `category` | string[] | Одна или несколько из: `construction`, `metal`, `crafted`, `refined`, `raw`, `organic`, `consumable`, `mineral`, `magic` + кастомные из `world.material_category_registry` |
| `use_type` | string[] | `wall`, `floor`, `column`, `door`, `gate`, `railing`, `ceiling`, `roof`, `any` |
| `wealth_level` | string | `poor` → `common` → `wealthy` → `noble` → `royal` |
| `hardness` | int (1–5) | Твёрдость для `ExcavationNode` |
| `components` | string[] | optional. Компоненты для `crafted`/`refined` материалов |

Базовые категории фиксированы в движке (`MaterialCategory` enum). Мир может добавлять кастомные через `world.material_category_registry`.

**Алгоритм выбора материала:**

```
effective_wealth = room.wealth_level ?? template.wealth_level ?? "common"
wealth_order     = ["poor", "common", "wealthy", "noble", "royal"]

def find_candidates(use):
    candidates = [uid for uid, mat in world.material_registry.items()
                  if "construction" in mat.category
                  AND use in mat.use_type
                  AND mat.wealth_level == effective_wealth]

    если candidates пуст:
        -- fallback: искать ближайший уровень вниз
        idx = wealth_order.index(effective_wealth)
        for level in reversed(wealth_order[:idx]):
            candidates = [... mat.wealth_level == level ...]
            если candidates: break
        если всё ещё пуст:
            candidates = [uid for uid, mat in world.material_registry.items()
                          if "construction" in mat.category AND use in mat.use_type]
        если всё ещё пуст → log WARNING, return default_material
    return candidates

wall_material  = rng.choice(find_candidates("wall"))
floor_material = rng.choice(find_candidates("floor"))
```

Порядок богатства (от низшего): `poor` → `common` → `wealthy` → `noble` → `royal`.

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
        выбрать свободную сторону у уже размещённого соседа
            (приоритет: east → south → west → north)
        разместить room смежно с соседом
        placed[room.room_id] = (origin_x, origin_y)
    добавить соседей room в очередь
```

Комнаты без connections (изолированные вершины) размещаются после BFS в оставшееся свободное пространство.

**Шаг 3 — perimeter_required**

`perimeter_required`-комнаты являются листьями графа (degree=1) — BFS автоматически ставит их на край, т.к. их единственный сосед уже размещён. Дополнительного алгоритма не требуется.

Валидация: `perimeter_required=true` + degree > 1 → `ValidationWarning` (смежность с несколькими комнатами не гарантирует периметр).

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

| Ячейка | `system_terrain` | `is_structural` | `location_uid` |
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
            room_type     = "utility_space",
            display_name  = "Техническое помещение",
            location_type = "room",
            is_accessible = True,
            parent_location_uid = building.location_uid,
        )
        gap-ячейки → floor, location_uid = utility_room
        граница gap-области с соседней комнатой → shared segment (Проход 3)
        граница gap-области с внешней стеной → уже покрыта Проходом 1

        -- авто-дверь: найти самый длинный shared segment с соседней комнатой
        best_neighbor = argmax(len(shared_segment) for neighbor in adjacent_rooms)
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

| Ячейка | `system_terrain` | `is_structural` | `location_uid` |
|--------|-----------------|-----------------|----------------|
| Пол | `floor` | `False` | room |

Периметр комнаты генератором комнаты **не создаётся**.

**Проход 3 — внутренние несущие стены**

Для каждого ребра BFS-графа (пары смежных комнат) — shared segment: единственная стена на границе двух комнат. Стена принадлежит зданию.

| Ячейка | `system_terrain` | `is_structural` | `location_uid` |
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
- Ровно одна комната имеет `entry_point` (если нужен вход)
- Не более одной комнаты с `back_entry_point`
- `entry_point.room_id` и `back_entry_point.room_id` существуют в `levels[].rooms`
- Все `connections[].from_room` и `.to_room` существуют в `levels[].rooms`
- `attach_to` комнаты ссылается на `room_id` того же уровня
- `size.size_type` + `size.width_range`/`size.depth_range` одновременно → ValidationError
- `size.size_type` отсутствует и `size.width_range` не задан → ValidationError
- `width_range[0] ≤ width_range[1]`, то же для `depth_range`, `count_range`, `z_range`
- `count_range[0] < 1` → `ValidationError` (минимум `[1, 1]`)
- `gap_policy` не из `{"clip", "fill", "random"}` → `ValidationError`
- Нет дублирующихся `room_id` в рамках всего шаблона (не только уровня)
- `effective_z_height ≥ min_z_height` для каждого уровня
- Все `shape_type` — валидные значения `ShapeType`; v1: + `is_supported = True`
- Если `shape_type` — массив: все элементы валидны; в v1 все из `_V1_SHAPES`
- Комната с `entry_point` или `back_entry_point` + явным `perimeter_required: false` → ValidationWarning (не ошибка; генератор форсирует периметр)
- Комната с `attach_to` + `entry_point`/`back_entry_point` → ValidationWarning (архитектурно некорректно)
- `perimeter_required: true` + degree в connection-графе > 1 → ValidationWarning (периметр не гарантирован)
- Connection-граф каждого уровня (intra-level doorway/archway connections) ацикличен — циклы → `ValidationError` ("кольцевые связи не поддерживаются: комната не может быть смежна с двумя уже размещёнными")
- `connection.passage_type == "staircase"` + `from_room` и `to_room` на одном `z_offset` → ValidationError
- `staircase_type` не из `{"spiral_small", "spiral_standard", "standard", "straight"}` → ValidationError
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

---

## 11. Что НЕ входит в v1

| Фича | Статус |
|------|--------|
| shape_type: semicircle, semi_oval, l_shape, t_shape, circle, polygon | v2/v3 |
| Явное позиционирование комнат (координаты в шаблоне) | v2 |
| Вращение/зеркало здания при размещении | v2 |
| terrain_overrides на уровне комнаты | v2 |
| Процедурная генерация без шаблона | нет ТЗ |
| `ExcavationNode` — логика раскопки изолированного уровня | нет ТЗ |
| `TeleportNode` — логика телепорта к изолированному уровню | нет ТЗ |

---

## 12. Механика колонн и мостов

### 12.1 Column proximity algorithm

Вместо статичного флага `has_column: true` в шаблоне — динамическая проверка в рантайме:

```
для каждой edge-ячейки балкона (выступающий край):
    scan_radius = 3  # клетки
    has_support = EXISTS map_cell WHERE
        system_terrain = "column"
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

### 12.2 Bridge между зданиями

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

### 12.3 Статус

| Компонент | Статус |
|---|---|
| `has_column: true` в шаблоне → генератор ставит column-ячейки | v1 (упрощённо: `has_column` = флаг) |
| Column proximity algorithm (scan_radius=3) | v2 |
| Bridge passage между двумя зданиями | v2 |
| Чужая колонна как опора (cross-building proximity) | v2 |

---

## 13. Открытые вопросы

| Вопрос | Статус |
|--------|--------|
| `template_uid` на `NamedLocation` здания | Решено: хранится на здании; RESTRICT при удалении; замена → перегенерация всех зданий |
| Общие стены смежных комнат: `location_uid = building` или одной из комнат? | Решено: building, `is_structural=True`; комнаты генерируют только пол |
| `attach_wall: "any"` — генератор выбирает сторону по seed или по свободному месту? | Решено: зависит от позиции лестницы в коридоре |
| Внешний контур здания — bounding box или реальный периметр? | Решено: реальный контур + `gap_policy: "clip"/"fill"/"random"` |
| `count_range: [0, 0]` допустимо? | Решено: минимум `[1, 1]` → `ValidationError` если `count_range[0] < 1` |
