# R41-T-25 — переход pack на новый контракт слотов

**Статус:** план агента · код **не** начат · ждать явной команды мастера писать  
**SoT:** [`docs/tz_terrain_relief.md`](../../docs/tz_terrain_relief.md) § Pack-слот / Правила стрелок; [`docs/tz_terrain_relief_consume.md`](../../docs/tz_terrain_relief_consume.md) § Тело sidecar  
**ID:** [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md) **R41-T-25**  
**Не SoT:** этот файл. Расхождение с ТЗ — править ТЗ (по команде мастера), не «как удобнее в плане».

Mill Q1/Q2, C41, SQL catalog, `Facing` на Instance — **не** этот переход. DAG / `0002_*.sql` / Occupancy v1 — не трогать.

---

## Команда следующему агенту (копировать в чат)

```text
Имплементируй R41-T-25 по плану .cursor/plans/relief-pack-slot-contract-t25.md.

SoT: docs/tz_terrain_relief.md § Pack-слот + Правила стрелок;
     docs/tz_terrain_relief_consume.md § Тело sidecar (SCH-GRADE-CELL-SLOTS).

Не трогать: mill C41 / SQL catalog / DAG / 0002_*.sql / Occupancy v1.
Locked-карты backend/tests/test_relief_r41_t25_locked_cases.py — без правки
до отдельной просьбы.

Не коммитить, пока не скажу. Backend не поднимать.
```

Пока этой команды нет — **не писать код**.

---

## Целевое состояние

```text
Mill (без изменений контракта)
  Q1/Q2 → Rim/Front/Seam → paint Instance → SQL catalog
  Facing = StrEnum (SQL / system_facing)

Pack (новый)
  z_height_map → один проход пар → 8 int на клетку обхода
  sidecar SCH-GRADE-CELL-SLOTS  { x, y, slots[8] }

Dump / валидатор
  только читают slots → глиф / ERROR
  не invent из z, не opposite, не rays[]
```

| Слой | Делает | Не делает |
|---|---|---|
| **dataModel** | 4 IntEnum + POJO клетки sidecar | глифы; один mega-enum |
| **Pack writer** | правила пары → коды | leftover mill first-wins в sidecar; `downhill_leftover` |
| **I/O** | compact JSON `cells[]` | pretty `rays[]`; колонка FineTerrain |
| **Dump** | таблица код→глиф | `FACING_ARROW[slot.facing]` как поток |
| **Валидатор** | нет кода на позиции = ERROR | закрыть «нет соседа» без `SEAM`; обход только leftover+halo |

---

## Контракт (уже в ТЗ)

### Коды (четыре enum, общая нумерация только wire)

| Enum | Члены | Wire |
|---|---|---|
| `GradeOctant` | `NORTHWEST`…`SOUTHEAST` (имена как `Facing`) | 0…7 = **поток** SLOPE |
| `GradeSeam` | `SEAM` | 8 |
| `GradeSheer` | `SHEER` | 9 |
| `GradeCouple` | `COUPLE` | 10 |

Позиция края ≠ код: индекс 0…7 = NW…SE. На WEST ямы код посадки = `EAST` (4), не 3.

`Facing.EAST` ↔ `GradeOctant.EAST` только на границе mill↔pack.

### Файл

Пути те же: `tiles/r.{gx}.{gy}.grade_rays.json`, `locations/l.{uid}.grade_rays.json`.

```json
{ "schema_id": "SCH-GRADE-CELL-SLOTS", "cells": [
  { "x": 0, "y": 1, "slots": [8, 10, 10, 8, 4, 8, 10, 10] }
]}
```

Compact JSON. `slots.length ≠ 8` или код ∉ 0…10 → reject. Старый `SCH-GRADE-RAY-SIDECAR` / `rays[]` — не читать как SoT (после среза writer не писать).

Merge: first-wins `(x, y, позиция)`.

### Правила пары → код

| Сосед в `z_height_map` | Оба конца (шов — один) |
|---|---|
| нет ключа | `SEAM` |
| та же z | `COUPLE` |
| другая z, θ ∈ (0, 80) | тот же `GradeOctant` (поток к нижней) |
| другая z, θ ∈ [80, 90) | `SHEER` |

θ = `atan(\|Δz\| / 1)` для leftover L=1. `|dz|=2` ≈63° → Octant, не SHEER. Не `slope_outcome` 45°.

Dump: Octant → `↖↑↗←→↙↓↘`; `SHEER`→`┃`; `SEAM`→`.`; `COUPLE`→`+`.

Эталоны приёмки (не переносить в writer как хардкод карт): generate § Карты-эталоны (яма `4` вокруг `2`, пул `4|3|2`).

---

## Срез старого кода (после нового writer)

Не патчить. Удалить с пути persist:

| Что | Где сейчас |
|---|---|
| `downhill_leftover_rim_rays` + `_downhill_leftover_kind` | `gradeRimRay.py` |
| `couple_rim_rays` на leftover+halo | `gradeRimRay.py` |
| `receiver_rim_ray` / `pack_rim_slot_rays` как источник sidecar | `gradeRimRay.py` |
| `leftover_plus_halo` как вселенная валидатора | `gradeCellRays.py` |
| `pack_slots_for_persist` (leftover→downhill→couple) | `gradeRimRays.py` |
| dump: глиф из `Facing` слота | `mapSymbols.grade_ray_glyph` |
| pretty `GradeRaySidecar.rays` | `gradeRaySidecar.py` |

**Оставить:** mill `rim_rays_from_front` / `walk_pack_senders` как след C41 **для mill/SQL**, не first-wins в sidecar. `Facing`, Instance `ReliefSideKind` SLOPE/SHEER, SQL catalog, merge instances/systems.

---

## Gate до кода writer (мастер)

В ТЗ обход на тайле 1e6 **открыт**. Writer не стартовать, пока не сказано одно:

1. **Обход = все клетки `z_height_map` unit** (wilderness tile / location volume) — sidecar полный, равнина = 8×`COUPLE`; или  
2. **Обход = рельефное множество** (явное определение: напр. клетка с хотя бы одним соседом другой z ∪ её 8-соседи ∪ край heightmap) — зафиксировать в ТЗ до имплементации.

Без gate снова leftover+halo или дыры ямы.

---

## Порядок слоёв (когда скажут кодить)

Не слайсить «сначала только dump». Каркас типов → I/O → writer → dump/валидатор → persist.

| # | Слой | Сделать |
|---|---|---|
| 0 | **Типы** | `GradeOctant` / `GradeSeam` / `GradeSheer` / `GradeCouple` (отдельные IntEnum, имена = смысл). POJO `GradeCellSlots` + sidecar `schema_id`. Хелперы: позиция↔дельта, `Facing`↔octant, decode int→член, dump-таблица глифов в **render**, не в generate |
| 1 | **I/O** | `load`/`write` `SCH-GRADE-CELL-SLOTS`; reject битой длины/кода; compact dump JSON. Split tile/location как сейчас (клетка целиком в свой файл) |
| 2 | **Writer** | Чистая функция: `z_height_map` + набор клеток → `list[{x,y,slots[8]}]`. Один проход пар. Не mill leftover. θ L=1 по § Угол |
| 3 | **Dump** | `slots[i]` → глиф; центр = z. Не `opposite` |
| 4 | **Валидатор** | Обход = тот же набор, что writer. Нет кода = ERROR `relief_error`. Не abort. Не дописывать. Сверка код↔пара (SEAM iff нет соседа, …) |
| 5 | **Persist** | `FineChunkPersist.finish`: writer вместо `pack_slots_for_persist`. Срез функций из таблицы выше |
| 6 | **Тесты** | Golden по эталонам ямы / пула (новые тесты). **Не** менять `test_relief_r41_t25_locked_cases.py` карты, пока мастер не скажет |

После 0–1 dump может временно не видеть старые bake (старый `rays[]` не SoT). Live bake без 2–5 останется на interim — не смешивать оба writer в одном finish.

---

## Data flow (target persist)

```text
FineChunkPersist.finish
  fine_surface_z  →  pack_cell_slots(z, occupancy)
  → write_grade_slot_sidecar (tile | location)
  → validate_grade_cell_slots (тот же occupancy)
  mill instances / systems — без изменений порядка SQL
```

Dump: `WorldPackReader` → load cells → `draw_grade_ray_grid` по `slots`.

---

## Не делать

- Один IntEnum на 0…10  
- Глифы / `"north_east"` / `"slope"` в sidecar  
- `opposite(Facing)` как посадка  
- Dump invent из z  
- Тело×8 Instance  
- Валидатор skip «нет leftover»  
- Dual-read `rays[]` + `cells[]` как вечный адаптер (срез, не вечная совместимость)  
- Растр/zstd sidecar (ТЗ: не этот контракт)  
- Правка DAG-нод, `0002_*.sql`, Occupancy v1  
- Коммит / старт backend без просьбы  

---

## Готово когда

- Bake пишет `SCH-GRADE-CELL-SLOTS`; яма 3×3 без Instance имеет 9×8 кодов, край `SEAM`, дно тот же Octant, что уход  
- Пул `4|3|2`: EAST-поток на обоих концах (`EAST`, не WEST→`←`)  
- Dump совпадает с эталонами ТЗ (глифы)  
- Валидатор ERROR на дырке кода, не на явном `SEAM`  
- Interim `downhill_leftover` / `leftover_plus_halo` / R44-halo нет на persist-пути  
- Locked-файл эталонов — только после явной просьбы мастера  

---

## История плана

| Дата | |
|---|---|
| 2026-08-26 | Первый черновик: слои 0–6, срез leftover-pack, gate обхода, locked-тесты не трогать |
