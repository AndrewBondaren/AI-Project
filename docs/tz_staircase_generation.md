# ТЗ: Генерация лестниц

## 0. Шпаргалка: алгоритм u_shape

### Шаг 1. Инварианты

```
march_depth = depth − 1
```
`march_depth` — кол-во ступеней на один марш (последний марш всегда depth−1).

---

```
N₁ = width + 2·depth − 2        (facing север/юг)
N₁ = 2·width + 2·depth − 4      (facing восток/запад)
N₂ = 2·width + 2·depth − 4
```
`N₁` — кол-во ячеек пути первого марша.  
`N₂` — кол-во ячеек пути второго и последующих маршей.  
`width` — ширина interior шахты. `depth` — глубина interior шахты.

---

```
march_count = ceil((z_height − 1) / march_depth)
```
`march_count` — кол-во прямых отрезков пути (маршей).  
`z_height` — высота лестницы в z-уровнях.

---

```
total_N = N₁ + N₂ × (march_count − 1)
assert total_N ≥ z_height
```
Валидация: ячеек пути должно хватать для всех ступеней.

---

```
flat = N₁ − z_height                                          (march_count == 1)
flat_per_march = ceil((total_N − z_height) / march_count)     (march_count > 1)
assert z_height ≥ total_N − flat_per_march × march_count
```
`flat` / `flat_per_march` — кол-во горизонтальных ячеек (stair_floor) на одну площадку.  
`ceil` округляет вверх: если `(total_N − z_height)` не делится ровно на `march_count`, отдельные площадки получат `flat_per_march − 1` ячеек, а «лишние» размещаются по правилам приоритета — это не ошибка.  
Геометрическая ошибка — когда `z_height < total_N − flat_per_march × march_count` (недостаточно ступеней для покрытия пути) или нарушение потолочного зазора в 2 ячейки.

---

```
ideal     = width
optimal   = width + 2 × (depth − 2)
mid_ideal = width × 2
```
Пороговые значения для правил расстановки flat.

---

### Шаг 2. Построение пути

Путь строится directed graph обходом interior: старт в fr_anchor, вектор V = V_init, поворот только в точках конца сегмента — V меняется на 90° по turn_vector. Оба прохода (подсчёт N и построение) используют один и тот же метод поворота.

```
anchors = [fr_anchor, far_anchor]   ← чередуются по маршам
z = z_lo
V = V_init                          ← начальное направление марша

для каждого марша i в range(march_count):
    pos = anchors[i % 2]
    steps = depth         (не последний марш, i < march_count−1)
    steps = march_depth   (последний марш)

    для шага в range(steps):
        place staircase(pos, z)
        pos += V;  z += 1

    если i < march_count − 1:
        tv = +turn_vector если i%2==0 иначе −turn_vector
        расставить flat_per_march ячеек stair_floor по правилам приоритета
        pos += tv × flat_per_march

    V = −V
```
`anchors` — стартовые XY-позиции маршей: чётные от fr_anchor, нечётные от far_anchor.  
`V_init` — направление первого марша (определяется из facing).  
`turn_vector` — направление поворота (перпендикуляр маршу, определяется из позиции fr_anchor).  
`V` — текущий вектор марша, инвертируется после каждого марша.  
`steps` — кол-во ступеней на данном марше.

---

### Правила распределения flat

U-образная лестница: вход и выход находятся на **одной стене** (near wall / anchor side), в противоположных углах. Far end — стена разворота. Это свойство шахты, фиксировано на весь подъём.

**Марш 1 (march_index == 0)** — near wall входит в pseudo-column, Pool 2 недоступен:

| Условие | Pool | Ячейки |
|---|---|---|
| flat ≤ ideal | 1 | Far end, центр первым |
| flat > ideal | 1 + 3 | + Боковые стены, от far end к near, tv-сторона первой |

**Марши 2+ (march_index > 0)** — near wall свободен:

| Условие | Pool | Ячейки |
|---|---|---|
| flat ≤ ideal | 1 | Far end, центр первым |
| flat ≤ mid_ideal | 1 + 2 | + Anchor side (near wall), центр первым |
| flat > mid_ideal | 1 + 2 + 3 | + Боковые стены, от far end к near, tv-сторона первой |

Размер каждого пула:
- Pool 1 = `far_sz` = `ideal`
- Pool 2 = `far_sz` → итого `mid_ideal = 2 × ideal`
- Pool 3 = `2 × lat` → итого `mid_ideal + 2 × lat`

---

### Псевдо-колонна (void-блок)

```
# Марш 1
pseudo = (w−2) × (d−1)
       = центральный блок (w−2)×(d−2)
       + средние ячейки стены якорей (исключая сами якоря по краям)

# Марши 2+
pseudo = (w−2) × (d−2)   ← только центральный блок
```

`w` — width interior, `d` — depth interior.  
Стена якорей — near side (ближняя сторона, где стоят fr_anchor и far_anchor).  
Все ячейки pseudo = `void` на всех z.

`far end` — торцевая стена шахты напротив fr_anchor.  
`anchor side` — стена, где стоит якорь текущего марша.

---

## 1. Основной принцип

**Лестница — транспортный механизм**, соединяющий две комнаты или коридора на разных уровнях.
`from` и `to` — реальные пространства (комнаты, коридоры), в которых находится игрок. Лестница НЕ является целью маршрута.

**Shaft (шахта)** — автогенерируемая инфраструктура между уровнями. Shaft генерирует только стены, пол внутри shaft НЕ создаётся. Shaft не объявляется как комната в `levels[].rooms` шаблона.

**Объявление в шаблоне:** массив `staircases` на верхнем уровне шаблона (см. tz_building_generator.md раздел 3.7b).
Каждая лестница задаёт `stops` — упорядоченный список комнат снизу вверх.
Генератор создаёт один shaft-сегмент на каждую соседнюю пару stops и размещает его смежно с комнатой назначения: `facing`-сторона shaft прилегает к стене `to_room`.

**`stops` — multi-floor лестница:**
```
"stops": ["main_hall", "corridor", "corridor_2"]
→ два shaft-сегмента: main_hall→corridor и corridor→corridor_2
→ одна вертикальная шахта выровнена по XY на всю высоту
```

**Высота лестницы** (`z_height`) = `abs(to_level.z - fr_level.z)`.
Задавать высоту в шаблоне запрещено — только через уровни здания.

**`to_anchor`** — первая `floor`-ячейка в комнате назначения (`to_room`) на `z_top`, достижимая шагом с последней ступени по вектору последнего марша. Никогда не находится внутри shaft.

**Пол на `z_top`** предоставляет комната назначения (`to_room`), не shaft-builder. Shaft-builder генерирует ячейки только в диапазоне `z_lo .. z_top − 1`.

---

## 2. Параметры shaft (в схеме `staircases`)

Shaft объявляется в массиве `staircases` шаблона (не в `levels[].rooms`).
Параметры shaft — поля записи в `staircases[]`:

### `has_walls: bool` (default: true)

| Значение | Поведение |
|----------|-----------|
| `true`   | Shaft замкнут стенами. Переход shaft → to_room — `archway` (автоматически). `outside` применим. |
| `false`  | Стены не генерируются (open shaft). Shaft **обязан** быть внутри здания. `outside` игнорируется. |

Shaft НИКОГДА не генерирует пол внутри interior.
Максимум что генерирует shaft-builder — стены по периметру.

### `outside: bool` (default: false, применяется только при `has_walls: true`)

| Значение | Поведение |
|----------|-----------|
| `false`  | Shaft замкнут, размещается где угодно (interior или edge-mounted). |
| `true`   | Shaft **обязан** быть edge-mounted: три стороны полностью снаружи здания. Внешние стены shaft заменяются на `floor` (открытая шахта, смотрит наружу). Entry-сторона (противоположная `facing`) = единственное примыкание к зданию через `archway`. |

При `outside: true` генератор форсирует периметральное размещение shaft. Entry-сторона shaft прикреплена к стене здания, три остальные стороны (включая facing) — за пределами контура здания.

**Комбинации `has_walls` × `outside`:**

| `has_walls` | `outside` | Паттерн |
|---|---|---|
| `true` | `false` | Закрытая лестничная клетка — interior или edge по усмотрению генератора |
| `true` | `true` | Внешняя лестничная башня — три стороны открыты наружу, одна примыкает к зданию |
| `false` | `false` | Открытая шахта внутри здания (atrium) |
| `false` | `true` | Невалидно → `ValidationError` |

### `in_a_room: bool` (default: false)

| Значение | Поведение |
|----------|-----------|
| `false`  | Shaft стоит отдельно, смежно с to_room. |
| `true`   | Shaft embedded внутри другого помещения. Требует `embed_in`. Несовместим с `outside: true` → `ValidationError`. |

### `facing: "north" | "south" | "east" | "west"` (опционально для `u_shape`, обязательно для `spiral`)

Направление **дальнего конца** (far end) — противоположная сторона от **entry**.

**Entry** = сторона shaft, прилегающая к to_room; именно с entry-стороны shaft соединяется с комнатой назначения.
`entry = opposite(facing)`

Генератор размещает shaft так, чтобы entry-сторона shaft совпадала со стеной to_room.

При `outside: false` остальные стороны могут быть как внешними, так и внутренними.
При `outside: true` все стороны кроме entry (противоположной `facing`) гарантированно снаружи.

| Тип        | Смысл                                                  |
|------------|--------------------------------------------------------|
| `straight` | Ось марша: N/S → Y, E/W → X                            |
| `u_shape`  | Направление начального подъёма = far end (противоположная entry/to_room). **Авто-детект**: движок сканирует floor-ячейки снаружи footprint на z_top; направление с максимальным количеством floor = exit direction; facing = противоположное. Значение из шаблона — fallback при score=0. |
| `spiral`   | Сторона дальнего конца; entry (противоположная facing) = выход в to_room; определяет CW/CCW обход |

### `embed_in: "room_id"` (только при `in_a_room: true`)

Явно указывает room_id родителя. Fallback: самая большая комната на том же z + WARNING.

---

## 3. Глобальные инварианты пути (все типы)

1. **Нет разрыва.** Каждая ступень смежна с предыдущей. Пробел = ошибка.

2. **Смена уровня только внутри footprint комнаты.** Вылет за границу = ошибка.

3. **+1 z за шаг.** Нельзя перепрыгнуть z-уровень или сменить уровень без ступени.

4. **Допустимые повороты:**

   | Тип        | Поворот                          |
   |------------|----------------------------------|
   | `straight` | 0° — повороты запрещены полностью |
   | `u_shape`  | max 90° через landing            |
   | `spiral`   | max 90° (углы периметра)         |

5. **Чистота пути.** Ни одна ячейка пути не заблокирована wall/column/чужим floor.
   Над каждой ячейкой пути (`staircase`, `stair_anchor`, `stair_floor`) — минимум 2 свободных ячейки по высоте (headroom). Нарушение = ошибка генерации.

7. **Смежные stair_floor одной площадки — один z уровень.** Все `stair_floor` ячейки одного поворота (landing между двумя маршами) обязаны быть на одном z уровне. Разные z внутри одной площадки = разрыв прохода = ошибка генерации.

6. **fr_anchor ≠ to_anchor** (все типы кроме `spiral`). Совпадение = ошибка вычисления якоря.
   `spiral` исключение: совпадение допустимо при `z_height % n == 0`.

---

## 4. Типы ячеек лестницы

| Тип              | Описание                                                                 |
|------------------|--------------------------------------------------------------------------|
| `stair_anchor`   | Крайняя ступень пути (z_lo). Вход на лестницу. Одна на лестницу.       |
| `staircase`      | Промежуточная ступень. Стрелка по направлению подъёма.                  |
| `stair_floor`    | Промежуточная площадка (landing) с поручнями в точке поворота. Только z_lo < z < z_top. Все ячейки одной площадки — строго на одном z уровне. |

`stair_anchor` и `staircase` семантически совпадают (оба — ступени с вертикальным переходом), но `stair_anchor` крайний в пути: должен быть доступен из коридора/комнаты, и к нему применяются отдельные правила размещения (нет стены/двери на расстоянии 1 клетки по направлению лестницы).

**Staircase builder генерирует ячейки только от z_lo до z_top−1.** На z_top находится пол коридора/комнаты — builder его не трогает.

---

## 4.1. Walkable-путь лестницы

Путь лестницы строится **при генерации** как упорядоченная последовательность ячеек `(x, y, z)`. Движок читает готовый путь — вычислять ничего не нужно.

### Общие правила

1. **Направление** (вверх / вниз) выбирает игрок. Ячейка лишь декларирует доступные переходы.
2. **Шаг переносит на следующую ячейку пути** — конкретную (x,y,z), не просто ±1z.
3. Для `trapdoor` и переносной лестницы: шаг меняет только z (x,y остаются). Исключение из правила 2.

Правила движения по ячейкам (`staircase`, `stair_anchor`, `stair_floor`) и headroom — задаются **отдельно для каждого типа лестницы**.

---

## 4.2. Параметры построения пути

При построении любой лестницы определяются следующие параметры:

| Параметр | Описание |
|---|---|
| **z_height** | Общая высота лестницы = `abs(z_top − z_lo)` |
| **march_count** | Количество маршей (прямых отрезков пути) |
| **march_depth** | Количество z-уровней в одном марше |
| **vector** | Текущий вектор движения `(dx, dy)` — направление марша |
| **turn_vector** | Изменение вектора в точке поворота |

### Правило поворота по типам

| Тип | Поворот |
|---|---|
| `straight` | Никогда не поворачивает. `turn_vector = (0,0)`. |
| `u_shape` | Поворачивает только в крайних точках прямоугольника/квадрата. Поворот строго 90°. |
| `spiral` | Поворачивает на каждом угловом шаге периметра. Поворот строго 90°. |
| `trapdoor` | Нет горизонтального движения — вектор не применяется. |

---

## 5. Тип: `straight` — прямой марш

### Ячейки и движение

| Тип ячейки    | z уровни           | Изменение при шаге                         |
|---------------|--------------------|---------------------------------------------|
| `stair_anchor` | z_lo только       | x/y меняется + z±1                          |
| `staircase`   | z_lo .. z_top−1    | x/y меняется + z±1                          |
| `stair_floor` | z_lo < z < z_top   | x/y меняется, z не меняется (при лишней глубине) |

На z_top — пол коридора/комнаты (`floor`). Staircase builder его не генерирует.

**Headroom**: над каждой ячейкой пути — минимум 2 свободных ячейки по высоте. Нарушение = ошибка генерации.

### Описание
Один марш, строго одно направление (по X или Y). Повороты запрещены.
Минимальная ширина марша: 1 клетка.

### Комната
```
Interior depth  = z_height      (1 ступень = 1 клетка глубины)
Interior width  = 1             (минимум)
Room depth      = z_height + 2
Room width      = 3
```
Пример z_height=3: комната 3×5.

### Ориентация
Лестница имеет **ось марша** (направление подъёма) и **ось ширины** (перпендикуляр):
- Марш N/S → ось марша = Y, ось ширины = X
- Марш E/W → ось марша = X, ось ширины = Y

Ширина заполняется одинаково на каждом z-уровне (дублирование ступени по оси ширины).

### Путь
```
# Марш вдоль оси марша, ширина заполняется по перпендикулярной оси
for step in range(z_height):
    for w in range(width_interior):
        place_stair(march_axis=anchor + step, perp_axis=anchor_w + w, z=z_lo + step)
```

**Лишняя длина** (`depth_interior > z_height`) — рекурсивное дробление floor-площадками:
```
split(segment_depth, segment_steps):
    if segment_depth == segment_steps:
        return
    mid_depth = segment_depth // 2
    mid_steps = segment_steps // 2
    place_landing(mid)          # floor в середине сегмента
    split(mid_depth, mid_steps)
    split(segment_depth - mid_depth, segment_steps - mid_steps)
```
Рекурсия завершается когда в каждом сегменте глубина = количеству ступеней.

### Якоря

**fr_anchor** = `stair_anchor`, первая ячейка пути на z_lo.

**to_anchor** = последняя ячейка пути (`staircase`) на z_top−1.
Шаг с to_anchor ведёт строго по вектору последнего шага пути на `floor`-ячейку коридора/комнаты на z_top.

Правило определения целевой ячейки:
- Вектор последнего шага: `(dx, dy) = path[-1] − path[-2]`
- Целевая ячейка: `(path[-1].x + dx, path[-1].y + dy, z_top)`
- Тип целевой ячейки должен быть `floor`. Диагональные переходы запрещены.
- Если целевая ячейка не `floor` → ошибка генерации с координатами ячейки, её типом, и координатами to_anchor.

fr_anchor ≠ to_anchor (Инвариант 6).

### Валидация
`depth_interior < z_height` → ошибка: комната слишком короткая.

---

## 6. Тип: `u_shape` — многомаршевая

### Ячейки и движение

| Тип ячейки    | z уровни           | Изменение при шаге                    |
|---------------|--------------------|---------------------------------------|
| `stair_anchor` | z_lo только       | x/y меняется + z±1                    |
| `staircase`   | z_lo .. z_top−1    | x/y меняется + z±1                    |
| `stair_floor` | z_lo < z < z_top   | x/y меняется, z не меняется (поворот) |

**Заполнение non-path interior-ячеек:**
| z уровень       | non-path ячейки |
|-----------------|-----------------|
| z_lo            | `floor` — основание лестницы, пол обязателен |
| z_lo+1 .. z_top−1 | `void` — шахта лестницы              |

На z_top — пол коридора/комнаты (`floor`). Staircase builder его не генерирует.

**Headroom**: над каждой ячейкой пути — минимум 2 свободных ячейки по высоте. Нарушение = ошибка генерации.

### Описание
N последовательных маршей, соединённых landing (stair_floor) у торцевых стен.
Марши чередуют направление: ↑ ↓ ↑ ↓ ...

**Глубина марша (`march_depth`):**
- march_count = 1 → `march_depth = depth_interior − 1`
- march_count > 1, не последний марш → `march_depth = depth_interior`
- march_count > 1, последний марш → `march_depth = depth_interior − 1`

**Количество ячеек пути (`N`):**

| Условие | Формула |
|---|---|
| Первый марш, N/S facing | `N₁ = width + 2·depth − 2` |
| Первый марш, E/W facing | `N₁ = 2·width + 2·depth − 4` |
| Второй и последующие марши (любой facing) | `N = 2·width + 2·depth − 4` |

**Определение march_count:**
```
min_z(march=1) = depth − 1
min_z(march=2) = depth + (depth − 1) = 2·depth − 1

если z_height < min_z(march=2) → march_count = 1
если z_height ≥ min_z(march=2) → march_count = 2
(аналогично для march > 2)
```

Для 3×3 interior: min_z(march=2) = 5, т.е. z_height < 5 → march_count = 1.

### Комната

#### Прямоугольная (interior width = 2)
- Нет псевдо-колонны.
- Два марша примыкают вдоль длины. Весь interior = staircase или floor.

#### Квадратная (interior N×N, N ≥ 3)
- Все interior-ячейки не входящие в путь = `void`. Заполнять запрещено.
- Включает центральный блок `(N-2)×(N-2)` и ячейки горловины U (открытая сторона, между двумя якорями).
- Все маршевые клетки примыкают к стенам (не отрываются от периметра).

| Interior | void (центр + горловина) |
|----------|--------------------------|
| 3×3      | (1×1) + (1 ячейка)       |
| 4×4      | (2×2) + (2 ячейки)       |
| 5×5      | (3×3) + (3 ячейки)       |

### Путь

Диаграмма — 2D-проекция пути сверху. Каждая стрелка = одна ячейка = один z-переход (+1z). `[_]` = `stair_floor` (горизонтальный поворот, z не меняется). `[.]` = пол коридора/комнаты на z_top (builder не генерирует).

### Конвенция facing

`facing` = направление начального подъёма = куда смотрит дальний конец U (far end).
Коридор/выход (`to_anchor` destination) находится **с противоположной стороны** от facing.
`[_]` stair_floor размещается приоритетно у far end (= в направлении facing).

### Стандартные примеры: 3×3 interior (north = вверх на диаграмме)

Легенда: стрелка = staircase (+1z), `[_]` = stair_floor (z не меняется), `[X]` = void, `[.]` = corridor floor на z_top (builder не генерирует).

#### z_height=3, march_count=1 (N=7, flat=4)

flat=4 ≤ optimal(5) → приоритет far end. Far end (север) = 3 ячейки, ещё 1 adjacent.

**facing=north** (коридор юг):
```
[_][_][_]    ← far end (3 flat)
[↑][X][_]    ← adjacent single flat (west col, 1 cell)
[↑][X][↓]
[.][.][.]   ← corridor floor at z_top
```
Путь: fr=(0,0)↑ (0,1)↑ (0,2)_(1,2)_(2,2)_ (2,1)_ → последний stair у (2,1)? 

> Примечание: конкретная раскладка flat зависит от реализации приоритетных правил.

#### z_height=5, march_count=2 (N₁=7, N₂=8, flat_per_march=5)

flat=5 = optimal(5) → приоритет far end + adjacent.

**facing=north** (коридор юг, площадка север):
```
[_][_][_]    ← far end landing (3 flat)
[↑][X][↓]
[↑][X][↓]
[.][.][.]   ← corridor floor at z_top
```
4 staircase + 3 stair_floor (оставшиеся 2 flat — часть near-end landing второго марша или смежные).

**facing=south** (коридор север, площадка юг):
```
[.][.][.]   ← corridor floor at z_top
[↓][X][↑]
[↓][X][↑]
[_][_][_]
```

**facing=west** (коридор восток, площадка запад):
```
[_][←][←][.]
[_][X][X][.]   ← corridor floor at z_top (east)
[_][→][→][.]
```

**facing=east** (коридор запад, площадка восток):
```
[.][→][→][_]
[.][X][X][_]   ← corridor floor at z_top (west)
[.][←][←][_]
```

### Расширение комнаты

**По оси глубины (y-expansion)** — более длинные марши, больше ступеней на петлю:
```
[_][_][_]       [_][_][_]
[↑][_][↓]       ← [_] у far end (1 уровень ниже landing)
[↑][X][↓]       [↑][X][↓]
[↑][X][↓]       [↑][X][↓]
[.][.][.]       [.][.][.]
depth=4, march_depth=3     Стандарт: depth=3, march_depth=2
```

**По оси ширины (x-expansion)** — шире landing и марши, те же ступени:
```
[.][←][←][_]       [.][.][.][.]
[.][X][X][_]        [↓][X][X][↑]
[.][X][X][_]        [↓][X][X][↑]
[.][→][→][_]        [_][_][_][_]
facing=east, 2-col (4 строки)   facing=south, 4-col (4 строки)
```

Глубже (5 строк interior):
```
[.][←][←][_]       [.][.][.][.]
[.][X][X][_]        [↓][X][X][↑]
[.][X][X][_]        [↓][X][X][↑]
[.][X][X][_]        [_][X][X][_]   ← угловые stair_floor, центр = псевдоколонна
[.][→][→][_]        [_][_][_][_]   ← full far-edge row (landing_width=4)
facing=east, 2-col (5 строк)    facing=south, sq_medium 4×4 interior
```

| Расширение | Эффект                              |
|------------|-------------------------------------|
| По глубине | `march_depth` ↑ → больше z на петлю |
| По ширине  | landing шире → те же z, больше вариативность |

**Структура пути по маршам:**
```
Марш 1: вдоль одной стены  (вектор V),  march_depth ступеней
[_]...[_] поворот у far end             (z не меняется, landing_flat ячеек)
Марш 2: вдоль другой стены (вектор −V), march_depth_last ступеней
...
```

**Расчёт flat ячеек:**
```
# march_count = 1
flat = ceil(N₁ / march_depth)

# march_count = 2
total_flat = (N₁ + N₂) − z_height
flat_per_march = total_flat / 2
```

**Рейтинг расположения flat (для любого марша):**
```
ideal     = width_interior
optimal   = width_interior + 2 × (depth_interior − 2)
mid_ideal = width_interior × 2
```

**Правила распределения flat (по убыванию приоритета):**

| Условие | Приоритетная сторона |
|---|---|
| flat == 1 | Центральная ячейка far end |
| flat ≤ ideal | Far end; центральная ячейка в приоритете |
| flat ≤ optimal | Far end; примыкающие одиночные ячейки тоже приоритетны |
| flat > mid_ideal И промежуточный марш (нет якоря) | Far end + anchor side |

`[_]` stair_floor размещается приоритетно у **far end** (направление `facing`).
Near-end landing использует `-turn_vector`.

Если выход блокирован или нарушены правила → пересчитать с другим начальным направлением.

### Якоря (только u_shape)

| Термин | Определение |
|---|---|
| `fr_anchor` | Первая ячейка пути (`stair_anchor`) на z_lo. Всегда в угловой ячейке interior на near side. |
| `far_anchor` | Стартовая позиция нечётных маршей. Диагонально противоположный угол interior от `fr_anchor`: `(width_interior−1 − fr_anchor.x, depth_interior−1 − fr_anchor.y)` в координатах interior. |
| `to_anchor` | `floor`-ячейка на z_top у entry-стороны шахты (arch threshold). Никогда внутри shaft interior. Сосед со стороны, противоположной exit_v, на z_top−1 — лестничная ячейка (`staircase` или `stair_anchor`) с `system_facing` в направлении exit_v. |

`fr_anchor ≠ to_anchor` — инвариант 6.

### Архитектура (только u_shape)

```
UShapeParams          ← dataclass, граница данных между геометрией и построением
  march_depth, march_count, loops
  landing_width, turn_vector
  fr_anchor, far_anchor
  path_2d_len

_compute_u_params(room, z_height) → UShapeParams
  └── вычисляет геометрию; вызывает _compute_path_2d_len
  └── fr_anchor вычисляется из room.position + facing + offset (не хранится в room)
  └── fr_anchor = random выбор из двух валидных углов near-side:
        facing=north → SW (ax, ay)  или SE (ax+w-1, ay)
        facing=south → NW (ax, ay+d-1) или NE (ax+w-1, ay+d-1)
        facing=east  → SW (ax, ay)  или NW (ax, ay+d-1)
        facing=west  → SE (ax+w-1, ay) или NE (ax+w-1, ay+d-1)
  └── turn_vector определяется из выбранного угла: от стены fr_anchor к противоположной

_compute_path_2d_len(params) → int
  └── первый проход directed graph, boundary-based, без landing_width

_turn(V, i, turn_vector) → V
  └── единственный метод поворота — используется в обоих проходах

_build_u_shape(params, z_lo, z_height) → List[Cell]
  └── второй проход; не получает room — только params
```

### Алгоритм построения (только u_shape)

Алгоритм построения пути не знает про форму комнаты. `_compute_u_params` вычисляет параметры из геометрии, путь строится только по ним. При добавлении новой формы комнаты — меняется только `_compute_u_params`.

**Шаг 1. `_compute_u_params(room, z_height)`:**
```
facing, w = width_interior, d = depth_interior  ← из комнаты

# Количество ячеек пути
is_ns = facing in ("north", "south")
N1 = (w + 2*d - 2) if is_ns else (2*w + 2*d - 4)   # первый марш
N2 = 2*w + 2*d - 4                                   # второй и далее

# march_count (порог: минимальный z_height для каждого числа маршей)
min_z_2 = d + (d - 1)     # минимальный z_height для march_count=2
if z_height < min_z_2:
    march_count = 1
else:
    march_count = 2        # аналогично для 3+

# march_depth
march_depth      = d - 1   # для march_count=1 и для последнего марша
march_depth_mid  = d       # для не-последних маршей при march_count > 1

# flat ячеек
if march_count == 1:
    flat = ceil(N1 / march_depth)
else:
    total_flat     = (N1 + N2) - z_height
    flat_per_march = total_flat / march_count

# рейтинг расположения flat
ideal     = w
optimal   = w + 2 * (d - 2)
mid_ideal = w * 2

loops        = ceil(march_count / 2)
turn_vector  = направление от стены fr_anchor к противоположной стене

# поворот
tv = +turn_vector для чётных маршей (0, 2, 4…) — far-end landing
tv = -turn_vector для нечётных маршей (1, 3, 5…) — near-end landing
```

N (path_2d_len) вычисляется directed graph обходом interior:
старт в fr_anchor, V = начальное направление,
поворот только в точках конца сегмента → V меняется на 90° по turn_vector.
Граф универсален для всех facing и форм комнат.

ВАЖНО: оба прохода (подсчёт N и построение пути) используют один и тот же метод поворота — расхождение логики между ними недопустимо.

`turn_vector` — определяется один раз из позиции якоря:
- facing=north, якорь у западной стены → `turn_vector = (1, 0)` (east)
- facing=north, якорь у восточной стены → `turn_vector = (-1, 0)` (west)

Направление поворота зависит от типа площадки:
- far-end landing (чётные марши: 0, 2, 4…) → `+turn_vector`
- near-end landing (нечётные марши: 1, 3, 5…) → `-turn_vector`

**Шаг 2. Построение пути:**
```
anchors = [fr_anchor.(x,y), far_anchor.(x,y)]   ← чередуются

z = z_lo
V = начальное направление (от fr_anchor к far end)

для каждого марша i в range(march_count):
    pos = anchors[i % 2]

    # фиксированная глубина марша (не divmod)
    steps = march_depth_mid если i < march_count − 1 иначе march_depth

    для каждого шага в range(steps):
        place staircase(pos, z)
        pos += V;  z += 1

    если i < march_count − 1:   ← последний марш — без landing
        tv = +turn_vector если i % 2 == 0 иначе −turn_vector
        # flat_per_march ячеек согласно правилам приоритета из Шага 1
        для каждой ячейки в range(flat_per_march):
            place stair_floor(pos, z)   ← z не меняется
            pos += tv

    V = −V   ← инвертировать для следующего марша
```

### Multi-loop: ветвление алгоритма

При `march_count > 2` путь делает более одной петли. Три различных среза:

**Вход** (fr_anchor + начало первой петли):
```
[_][_][_]   ← far-end landing
[↑][X][↓]
[↑][X][↓]
[↑][_][↓]   ← fr_anchor (west col) + near-end landing (центр) + начало march south (east col)
```

**Середина** (полные петли, повторяется):
```
[#][#][#]   ← стена или пустота (z выше)
[_][_][_]   ← far-end landing
[↑][X][↓]
[↑][X][↓]
[_][_][_]   ← near-end landing (-turn_vector)
[#][#][#]   ← стена или пустота (z ниже)
```

**Выход** (последний марш → to_anchor):
```
[_][_][_]   ← far-end landing (от предыдущей петли)
[ ][X][↓]
[ ][X][↓]
[ ][ ][↓]   ← to_anchor на near-end
[.][.][.]   ← corridor floor at z_top
```

`march_count` = общее кол-во маршей, включая финальный марш до `to_anchor`.

Позиция `to_anchor` зависит от чётности последнего марша (0-based):
- последний марш нечётный (1, 3, 5…) → марш идёт far→near → `to_anchor` на **near-end**
- последний марш чётный (0, 2, 4…) → марш идёт near→far → `to_anchor` на **far-end**

Near-end landing использует `-turn_vector` (противоположное направление от far-end landing).

---

Edge case — landing расширяется на смежные стены (stair_floor_per_march > far_wall_size):
```
[.][←][_][_]
[.][X][X][_]
[.][X][X][_]
[.][→][_][_]
```

Пример для 2×2 interior (facing=north, march_depth=1):
| `z_height` | `march_count` | `landing_width` | Путь |
|---|---|---|---|
| 2 | 2 | 2 | `↑ [_][_] ↓` — full far-edge |
| 3 | 3 | 1 | `↑ [_] ↓ ↓` — частичный (multi-loop) |

### Якоря

**fr_anchor** = `stair_anchor`, первая ячейка пути на z_lo.

**to_anchor** = `floor`-ячейка на z_top у entry-стороны шахты (arch threshold).

Правила:
- Тип: `floor` на z_top.
- Позиция: стена шахты со стороны entry (не внутри shaft interior). Совпадает по XY с archway между shaft и to_room.
- Сосед: ячейка `(to_anchor.x − exit_v.x, to_anchor.y − exit_v.y, z_top−1)` — лестничная (`staircase` или `stair_anchor`) с `system_facing == exit_v`. Без диагоналей.
- Если нет подходящей ячейки → ошибка генерации с координатами to_anchor и соседа.

fr_anchor ≠ to_anchor (Инвариант 6).

### Валидация
- `width_interior < 2` → ошибка: комната слишком узкая для u_shape.
- `landing_width < 1` → ошибка: невозможно построить поворот — минимум 1 stair_floor на far end обязателен.
- Если при вычислении `landing_width` для заданного `z_height` значение оказывается < 1 → ошибка генерации: комната слишком мала для данной высоты.

---

## 7. Тип: `spiral` — спиральная

### Ячейки и движение

> TODO: семантика движения по spiral отличается от straight/u_shape — описывается отдельно.

**Headroom**: над каждой ячейкой пути — минимум 2 свободных ячейки по высоте. Нарушение = ошибка генерации.

### Описание
Путь по периметру квадратного void-пространства. Только квадратные комнаты (min 3×3 interior).

### Комната

| Вариант   | Void interior | Периметр (n)   | Room  |
|-----------|---------------|----------------|-------|
| Spiral 3  | 3×3           | 8 позиций      | 5×5   |
| Spiral 4  | 4×4           | 12 позиций     | 6×6   |

Лимит без накладывания ступеней: `z_height ≤ n`. При `z_height > n` путь делает >1 оборота.

### Путь и заполнение
- Центральная клетка — `S` (newel post) на **каждом z-уровне**.
- Все переходы заполнены staircase-ячейками.
- **Свободные угловые клетки** (не занятые якорями) остаются void.

```
Для 3×3 (периметр: 4 угла C + 4 середины сторон):
[C][ ][C]    C = угол (void если не якорь)
[ ][S][ ]    S = центр (всегда staircase)
[C][ ][C]
```

Направление обхода (CW/CCW) определяется стороной archway/door из комнаты.

### Пример: Spiral 3×3 (z_height=3)

```
z=0 (нижний):
[ ][→][ ]
[↑][S][S]
[ ][S][ ]

z=1 (межэтажный):
[.][S][ ]
[S][S][↓]
[ ][←][ ]

z=2 (межэтажный):
[ ][→][ ]
[↑][S][S]
[ ][ ][S]

z=3 (верхний):
[ ][ ][ ]
[ ][S][↓]
[ ][ ][↓]
```
Центр `[S]` — newel post, присутствует на каждом z.
`.` у NW на z=1 — обычный floor (не staircase, не void).
Путь обвивает центр по часовой стрелке.

### Якоря
- **Правило S-1.** Якоря (вход и выход) размещаются только на **угловых позициях** периметра.
- **Правило S-2.** Два якоря на одном z (многоэтажный shaft) → между ними floor.
- fr_anchor == to_anchor допустимо при `z_height % n == 0`.

---

## 8. Проходы (passages)

Shaft прилегает к `to_room` с entry-стороны (противоположной `facing`). Переход shaft → to_room создаётся автоматически — явно объявлять archway в `connections` шаблона не нужно.

| Условие                       | Тип прохода             |
|-------------------------------|------------------------|
| `has_walls: true` (default)   | `archway` — авто между shaft и to_room |
| `has_walls: false`            | не нужен (стен нет)    |
| Basement / cellar             | `trapdoor`             |

`to_anchor` = ячейка `floor` в `to_room` (не в shaft) на `z_top`, куда ведёт шаг с последней ступени.
Archway совпадает с `to_anchor` по XY — это точка входа в to_room с лестницы.

---

## 9. Мутация комнаты

Пропускается всегда. Размер задаётся шаблоном под тип лестницы.

---

## 10. Комбинации флагов

| `in_a_room` | `has_walls` | Описание                                    |
|-------------|-------------|---------------------------------------------|
| `false`     | `true`      | Отдельный замкнутый лестничный блок (стандарт) |
| `false`     | `false`     | Отдельный открытый блок                     |
| `true`      | `true`      | Лестничная клетка внутри большого помещения |
| `true`      | `false`     | Открытая лестница внутри зала (atrium)      |

---

## 11. Архитектура: ShaftPlacer

За размещение shaft в пространстве здания отвечает отдельный класс **`ShaftPlacer`**.
Логика размещения зависит от флагов `in_a_room` и `outside` и не смешивается с layout engine и passage builder.

```python
class ShaftPlacer(ABC):
    @abstractmethod
    def place(
        self,
        shaft: _RoomInstance,
        fr_room: _RoomInstance,
        placed_rooms: list[_RoomInstance],
    ) -> bool:
        """Выставляет shaft.origin_x / shaft.origin_y. Возвращает True если успешно."""
```

### Стратегии размещения

| Флаги | Класс | Кейс |
|---|---|---|
| `in_a_room: false, outside: false` | `AdjacentShaftPlacer` | Shaft смежен с fr_room; to_room прилегает к entry-стороне shaft |
| `in_a_room: true` | `EmbeddedShaftPlacer` | Shaft размещается внутри `embed_in` комнаты |
| `in_a_room: false, outside: true` | `EdgeMountedShaftPlacer` | Shaft на периметре здания; entry-сторона прикреплена к зданию |

### AdjacentShaftPlacer (`in_a_room: false, outside: false`) — стандарт

1. Shaft создаётся программно как `_RoomInstance(is_shaft=True)` с размером из `staircases[].size`.
2. Shaft размещается смежно с fr_room (любая сторона без конфликтов).
3. Shaft добавляется в список комнат уровня fr_z как pre-placed.
4. `level_start[to_z] = shaft.origin` — уровень to_z начинается с позиции shaft.
5. На уровне to_z shaft добавляется как pre-placed pseudo-room с `is_shaft=True`.
6. BFS level to_z: to_room (corridor) размещается смежно с shaft через синтетический graph edge shaft ↔ to_room.
7. Entry-сторона shaft (противоположная `facing`) = общая стена shaft и to_room → archway создаётся автоматически.

### EmbeddedShaftPlacer (`in_a_room: true`)

1. Shaft размещается **внутри** `embed_in` комнаты (shaft.origin ⊂ interior(embed_in)).
2. to_room = embed_in — shaft находится внутри него; archway не нужен.
3. `level_start` для to_z не зависит от shaft (to_room уже является embed_in).
4. Shaft генерирует только ступени и стойки — внешние стены не нужны (они принадлежат embed_in).

### EdgeMountedShaftPlacer (`outside: true`)

1. Shaft размещается на периметре здания: три стороны полностью снаружи контура.
2. Entry-сторона shaft прикреплена к стене здания через archway.
3. Внешние стены shaft (3 стороны, включая facing) заменяются на `floor`.
4. Детали реализации — step 12 плана.

### Место вызова

`ShaftPlacer` вызывается из `StructureGeneratorService` — после layout уровня fr_z, до layout уровня to_z.
Shaft не объявляется в `levels[].rooms` шаблона и не появляется в `named_locations` результата.

---

## 12. Открытые вопросы

- [ ] `spiral`: формула при `z_height > n` (более одного оборота)?
- [ ] `in_a_room: true` + layout: как layout engine резервирует место внутри родителя?
- [ ] `has_walls: false`: нужен ли railing по краям?
- [ ] Материалы по типам (дерево/камень/металл).
