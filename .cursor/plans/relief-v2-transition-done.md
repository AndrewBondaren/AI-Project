# Relief pipeline v2 — план перехода (контракты на ревью) ✅ DONE

**SoT после ревью:** `docs/tz_terrain_relief.md` R41 / R42 / C35–C37.  
**Сейчас в коде:** R37 ray geom (L_ray, без L max 30) + v1 расписание (sample до пула, stamp затем fill, пики × 4 орто, нитка W=1).  
**Этот документ:** целевые контракты, локусы правок, шов с L2 materialize. **Код и ТЗ не менять**, пока мастер не утвердит §1.

Связь: [`docs/tz_terrain_relief.md`](../../docs/tz_terrain_relief.md) · домены `generators/terrain/relief/{sample,pick,geom,volume,canal}` · bake `pack/refine/detailedGrade*` + `fineChunk*`.

---

## Цель

v2 — актуальный алгоритм. v1 в ТЗ не параллельная норма: после ревью это historical / адаптер.

Три требования мастера:

1. Зафиксировать контракты (этот §1) → ревью.
2. Менять логику рельефа **внутри текущих доменов** (не новый оркестратор, не второй пул).
3. Смена origins/меса/фронта **не переписывает** L2 voxel materialize (R36i / GradeFormation / write-set / column fill).

---

## 1. Контракты (ревью)

### 1.1 Что стабильно (не трогать в v2)

Это **L2 paint**. Origins, меса, lockstep, fill→relief сюда не входят.

| Контракт | Где | Инвариант |
|---|---|---|
| Треугольник / отвес | `volume/volumeMaterialize.py` `plan_ribbon_volume` / `plan_seed_volume` | SLOPE: `sum(steps)==h`, дальний z закрывает Δz; SHEER L=1 колонка XY; inner `L_eff=min(L,h)` |
| Geom-A/B | `dataModel/.../reliefSlopeGeom.py` + `geom_resolve` | формулы; Geom-C не bake |
| Конверт θ/L/kind | `ReliefTerrainEnvelope` + `grade_constrained` | plains/forest `open_land`: θ≤20°, L min 20 без max, `L=min(L_ray, max(L_tpl, ceil(h/tan20°), 20))`; overflow → SHEER L=1; `|dz|=1` не stamp |
| Canal / R36m / R36t | `canal/*`, `obstacleClearance`, `r36t_corridor_cells` | упор в footprint после pick; якоря верха/низа не мутировать; canal-cut только при укорочении |
| Write-set | `GradeFormation` → `DetailedGradeResult` | uid-домен = состав Instance; overlay ⊆ uid; clip жмёт membership, не h/L |
| Entity | `ReliefGradeInstance` + `build_ribbon_grade_instance` | одна прямая = один Instance (C15); T-3c System later |
| Каталог швов | `TileFaceCatalog` **до** пула | `face_key` → `grade_uid`; не mint в воркере |
| Persist L2 | `FineChunkPersist` / FineTerrain cells | `system_grade_uid` только на surface z (PAR-G9); upsert instance |
| Контексты | один discover v2, **разное тело вершины** | не «open_land = v2, дорога = v1-лента» |

**Запрещено в v2:** переписывать `plan_ribbon_volume` под равнину; `if plains` в volume; второй writer `surface_z` вне write-set; tile-wide serial materialize; fill∥relief на одном rect; второй пул «на рельеф».

### 1.2 Новый шов: discover → paint (`GradePaintSpec`)

Сейчас pack materialize ест `PlannedGradeSegment` = `RibbonSegment` (список семян 1×L) + `RibbonGradeDecision` + `ref_cells` + uid. v2 origins (меса, фронт W, террасы) **не должны** притворяться N нитками.

**`GradePaintSpec`** — единственный вход L2 paint. Discover (sample/меса/луч) и C28 uid **снаружи**. Volume/corridor/canal-cut/instance **внутри**.

```text
GradePaintSpec
  # pick (уже есть, не origin)
  context, site_id, template_uid
  kind, h, requested_length, geom, sign
  canal knobs (earthen / structure_canal / refs)

  # occupancy (v1: W=1; v2: фронт)
  outward          # v2 day-1: cardinal (±1,0)|(0,±1)
  facing           # SLOPE: uphill; SHEER: none
  front            # W клеток k=1 (первый шаг вне месы / seed)
  crest_anchors    # верх R36t — не мутировать
  toe_anchors      # низ R36t, если известен до paint — не мутировать
  grade_uid        # с каталога / interior|{k} — уже выдан
```

Прямая дорога без поворота **выглядит как v1** (два орто-фронта). Это частный случай той же конструкции, не отдельный пайплайн. Pick **не** знает W. `grade_constrained(..., path_length=L_ray)` без изменений.

Диагональный **толстый** коридор (Murphy, R36r, W>1 по диагонали) — later. **Нитка** вдоль `(±1,±1)` (W=1, Chebyshev) уже рисуется тем же `outward_columns` — нужна на **повороте дороги**.

### 1.3 Discover — одно построение v2, тело вершины от контекста

Не два алгоритма. Каркас один: **вершина (тело) → кромка → непересекающиеся лучи/фронты → `GradePaintSpec`**. От контекста меняется только *что считается вершиной* и *куда нельзя стрелять*.

**Общие инварианты (все контексты)**

| | |
|---|---|
| Вершина | связное **тело** якорей, не каждая клетка тела |
| Интерьер тела | не сеет |
| В тело | луч **не** идёт (в якорь / вдоль тела в соседнюю клетку той же вершины) |
| В чужую вершину | луч **не** идёт (занятость клетки; соседняя меса / другая дорога / уже взятый коридор) |
| Лучи одной вершины | **не пересекаются**: клетка ≤ 1 фронта |
| 8 сторон | кандидаты с кромки (`Facing`, Chebyshev 1). Прямой участок часто использует 2 орто; **поворот** — диагонали |
| Stamp `|dz|=1` | нет Grade (R37), даже если кромка есть |
| Когда | после готового z rect (+ halo read). Не hunt пиков до fill |

**Контекст = определение тела**

| Context | Тело вершины | Кромка / куда стрелять | Прямой участок | Поворот |
|---|---|---|---|---|
| `open_land` | меса: 8-связная та же целая z | сосед **ниже** (не в ту же месу). Каскад высоких z → низ | фронт W вдоль стороны плато | угол месы: отдельный фронт на диагональ, если спуск только туда |
| `road_shoulder` | **связные клетки полотна** (`road`) = **одна** вершина. Не клетка дороги = не звезда | только **наружу от полотна**, обе обочины (R20). Не в дорогу. Не вдоль полотна в соседний якорь | два противоположных орто-фронта (= «v1 без поворотов») | 8-way: внешний угол — диагональный луч/фронт; внутренний — не два фронта в одну клетку |
| `shore` | связный run `SHORE` (или берег↔вода — уточнить при коде) | только **landward**, не в воду / не вдоль берега в соседний якорь | фронт вдоль берега | коса / мыс — диагональ, те же правила непересечения |
| `ravine` | тело маски `ravine` **или** связный bank — не downhill-дно (R TZ ravine) | со стены низины **внутрь маски** (seed = ravine cell), не в bank-якорь, не на плоский пол без Δz | фронт вдоль берега ямы | поворот каньона — 8-way, лучи не скрещиваются на дне |

Дорога: клетка полотна **не** получает SHEER (R20). Якоря неприкосновенны (R36t) = тело дороги не в overlay.

```text
прямо     NNNNN           поворот      . D N
          ROAD ROAD                    ROAD D
          SSSSS                        ROAD
                                       S S

N/S — орто-фронты одной вершины ROAD
D   — диагональ внешнего угла; не бьёт в ROAD и не в клетку N
внутренний угол: одна клетка — один фронт (или ничья → skip), не два луча
```

**Рабочая коллекция вершин — locked (скорость)**

Чанк ~32×32 + halo. Рабочий id вершины на bake = **номер слота** в `members` (1-based в сетке). `grade_system_uid` (uuid) **отдельно**, не в `at_grid`.

```text
ReliefVertices              # lx = x-x0, ly = y-y0
  origin, w, h
  at_grid:  array[int]      # w*h; 0 = пусто; иначе 1-based slot
  members:  list[dict[(x,y), z]]   # slot-1 → точки тела
  uids:     list[str]       # slot-1 → grade_system_uid; можно заполнить в конце persist
```

Запрещено в горячем пути: `dict[(x,y), uuid]`; `list` точек в members; uuid в ячейке сетки.

| Операция | Как |
|---|---|
| чья клетка | `at_grid[lx + ly*w] → slot` |
| точка в вершине | `members[slot-1][(x,y)]` |
| выколоть | `at_grid[…] = 0`; `del members[slot-1][(x,y)]` |
| uuid Instance | `uids[slot-1]` (mint в конце bake, если ещё нет) |

`idx_of: dict[uuid, slot]` — **не** часть locked ядра. Только если uuid уже есть до конца bake (merge/DEBUG). Иначе рабочий id = slot.

После paint: сторона → `Instance.grade_uid`; `Instance.grade_system_uid = uids[slot]`; коридор `system_grade_uid` = Instance; якоря omit. 1 грань → строку systems не пишем; ≥2 → System + `grade_instance_uids`.

**Сверка `members` ↔ `at_grid` (каскад сверху вниз).** Клетка в теле `slot` только если:

1. `(x,y) in members[slot-1]`;
2. `at_grid[lx+ly*w] == slot`;
3. клетка не в коридоре **другой** вершины (выше по z).

Иначе выколоть из members и обнулить сетку. Остальные точки живы. Пустой members → снять вершину.

```text
at_grid[lx,ly] == slot_A  и  (1,0) ∈ corridor(высокой)
→ at_grid[…] = 0; del members[slot_A-1][(1,0)]
```

Порядок: лучи высоких z → сверка → лучи нижних.

**L из шаблона** (`slope_length_cells` / Geom-B): это **L_tpl** = запрошенный выстрел и потолок **halo / max_scan** луча, не обязательный итоговый L.

| | |
|---|---|
| Дорога / shore / ravine | L_tpl (часто 2) ≈ длина луча; `free_gap` может укоротить |
| `open_land` plains/forest | пол R37 может **удлинить** до ≥20 / `ceil(h/tan 20°)`; `L_ray` и `free_gap` укорачивают |
| Halo чанка | `max(L_tpl, envelope floor)` — иначе равнина смотрит на 2 клетки при рампе 20 |

Не группировать «все точки локации» целиком: только клетки **этого `ColumnRect` + halo** (R38). Territory volume — не второй stencil.

### 1.4 Расписание ядра (R40 / R41)

```text
до пула (serial)
  catalog face_key → grade_uid          # без z, без семян
  НЕ sample open_land, НЕ stitch семян

pool task = один ColumnRect, одно ядро
  1) column fill всего rect с parent heightmap (без grade overlay)
  2) discover + pick → tuple[GradePaintSpec, ...]
  3) paint каждый spec → DetailedGradeResult
  4) corridor-refill: run_column_fill ТОЛЬКО по XY overlay
     (parent ⊕ overlay, uid bag) → заменить клетки этих колонок
  5) persist как сейчас

после чанков этого вызова
  merge instances по uid (уже FineChunkPersist / upsert)
  = такт 3 R41; не новый оркестратор
```

**Почему refill, а не «поменять z у живых MapCell»:** L2 колонка — набор клеток по z. Смена `surface_z` меняет набор. `run_column_fill` уже умеет rect + heightmap + `surface_grade_uid`. Второй вызов — узкий, не второй пул и не tile-wide materialize.

**Не:** fill∥relief; stamp затем fill на дырявом z; sample всех rect до пула по parent light.

Halo: `max(template L, envelope L floor на ожидаемый h)`, не только knobs `open_land_soft` L=2.

### 1.5 C28 после сдвига sample

| Было (v1) | v2 |
|---|---|
| sample всех rect → union-find семян → freeze uid → stamp | каталог uid до пула; прямая уже = один `GradePaintSpec` (фронт) |
| `split_mixed_outward` на смешанной ленте | discover не смешивает Facing в одном spec |
| `ctx.planned: tuple[PlannedGradeSegment]` до пула | `ctx.planned` для z-зависимых контекстов **пусто** до fill; uid только catalog |

`detailedGradeGraph.stitch_planned_segments` — не SoT v2 ни для одного контекста. Все контексты эмитят spec. Не развивать union-find пиков. Не оставлять дорогу на pre-pool ribbon «потому что v1».

### 1.6 Слои доменов (не смешивать)

```text
sample/     кто / где: кромка, меса, фронт, L_ray, path_length
pick/       какой Grade: template + envelope + kindRoll + geom
geom/       формулы, facing, terrain ray / later lockstep step
volume/     как красить: 1D plan × фронт W → columns; НЕ origins
canal/      cut / knobs resolve
pack/refine каталог, halo, compute_rect порядок, write-set apply, persist
```

Volume не импортирует mesa/peak. Sample не вызывает `plan_ribbon_volume`. Pick не знает rect/fill.

### 1.7 Открытые решения (нужен ответ на ревью)

1. **Corridor-refill (рекомендую)** vs патч клеток вручную vs fill сразу parent⊕overlay после discover **на том же** первом fill (тогда discover должен уложиться между «z готов» и «клетки из fill» — либо fill дважды, либо fill после paint как сейчас, но z для discover брать из heightmap **до** клеток). Рекомендация: heightmap fill-семантика = parent z уже есть в `TileSurfaceState` до воркера; «fill» в R40 = *колонки L2 из этого z*. Тогда discover может идти по **уже лежащему** `surface_z` rect+halo **после** того как воркер считает heightmap финальным для шума, и **до** `run_column_fill`. Это ближе к коду: `surface_state.heightmap` уже есть в prep. Уточнение: v2 «после fill» = после того как z rect **полный и больше не дырявый**, не обязательно после списка `MapCell`. Если upsample/шум дописывает z **внутри** `generate_chunk_cells_sync`, discover обязан быть **после** этого writer’а высот. Если heightmap в prep уже финальный — discover после него, затем **один** `run_column_fill` с overlay (как сейчас stamp→fill), только sample переезжает **в воркер** на готовый z. **Это развилка A/B:**

   - **A (рекомендую, меньше ломки L2):** z rect готов в `surface_state` до колонок → в воркере: discover+paint на этом z → **один** `run_column_fill`(parent⊕overlay), как сейчас. Меняется только *когда* sample (после готовности z, в воркере), не двойной fill.
   - **B:** если `generate_chunk_cells_sync` сам меняет z — сначала этот writer без grade, потом discover, потом refill overlay XY.

2. **Диагональ на повороте:** discover 8-way **нужен** (дорога). Paint day-1: орто W×L + **W=1** Chebyshev `(±1,±1)` тем же `outward_columns`. Толстый диагональный фронт (Murphy W>1) — later. Ревью: ок так резать?

3. **`PlannedGradeSegment`:** оставить как v1-адаптер → `GradePaintSpec`, или сразу заменить в runner/facade?

---

## 2. Локусы изменений (текущие домены)

Не трогать, пока §1 не утверждён. Ниже — карта, не чеклист коммитов.

### Не менять (L2 / persist / inner geom)

- `volume/volumeMaterialize.py` — тело 1D plan (можно *вызвать* из фронта)
- `geomResolve.py` inner, `partition_height`
- `GradeFormation` / `DetailedGradeResult.reconcile` / clip / merge
- `build_ribbon_grade_instance`, canal resolve, R36t cut
- `columnFillPass.run_column_fill` (сигнатура уже ок)
- `FineChunkPersist`, ASCII consumers `system_grade_uid`
- DAG nodes

### `dataModel`

- Без новых полей на Instance для W (ширина = `cell_refs` / коридор).
- Envelope уже v2-geom; halo читать `slope_length_min_cells` / `length_from_max_angle`, не дублировать литералы.

### `sample/` — построение вершины × контекст

| Файл | Роль v2 |
|---|---|
| общий helper вершины | тело → кромка → непересекающиеся фронты (8 кандидатов) |
| `open_land` | тело = z-меса; кромка = спуск |
| `road_shoulder` | тело = связное полотно; кромка = наружу; не в якорь / не вдоль дороги |
| `shore` / `ravine` | тело = hydro/mask run; стрельба только в свою сторону |
| `ribbonSiteSample.py` пики | не SoT |
| `terrainDescent.py` | стоп вокселя; lockstep фронта рядом |
| `detailedGradeSample.*` | контекстный эмиттер spec, не N ниток с каждой клетки якоря |

### `pick/`

- `grade_constrained` / `path_length` — **не** ломать.
- Не возвращать plateau-skip `|dz|=1`: это правило sample/discover.

### `volume/` + `pack/refine` paint

| Файл | Изменение |
|---|---|
| **новый** `volume/gradePaintSpec.py` (имя на ревью) | frozen spec §1.2 |
| `detailedGradeCorridor.py` | `outward_columns(seed)` → `front_strip(front, outward, L)`; W=1 ≡ сейчас |
| `volume_corridor_for_seed` | вход spec, не «seed + весь segment»; clearance по **полосе** W (v1: W=1) |
| `detailedGradeMaterialize.materialize_segment_meter` | ест spec / список spec; не знает пики |
| `detailedGradeGenerate.plan_rect_grade` | сборка spec + uid; open_land не `segmentize` по клетке |

### Расписание `pack/refine`

| Файл | Изменение |
|---|---|
| `fineChunkCompute.compute_rect` | не stamp-then-fill на pre-pool planned; см. §1.7 A/B |
| `fineChunkRunner.refine_rects` | убрать `plan_grade_for_rects` **до** пула для z-зависимых семян; catalog остаётся в prep |
| `fineTileContext.planned` | optional / только catalog-bound jobs; не occupancy open_land |
| `detailedGradeGraph` | не звать для open_land v2 |
| `grade_halo_cells` | учесть envelope L, не только JSON L=2 |
| `generate_detailed_grade` facade | тот же helper, что воркер: поверхность уже с z |

### Тесты (после кода)

- `test_relief_ontology_envelope.py` — geom/pick оставить.
- `test_detailed_grade_generate.py` — пики × facing заменить на кромка/меса/фронт; 4→3 нет stamp; 4→2 L=1 SHEER; ряд `4 4 4` восток = **один** spec W=3, не три.
- Не требовать pre-pool `ctx.planned` для open_land.

---

## 3. Абстракция, чтобы materialize L2 не страдал

Проблема: `materialize_segment_meter` + `volume_corridor_for_seed` **сами** ищут якоря, outward, 1D луч клеток. Смена «кто кромка» сегодня ломает paint.

```text
                    discover (меняется)
                    sample / mesa / front
                           │
                           ▼
                    GradePaintSpec          ◄── единственный шов
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   R36m clearance    plan_ribbon_volume   canal + R36t
   (полоса W)        (1D, без W)          (как сейчас)
         │                 │                 │
         └────────────┬────┘                 │
                      ▼                      ▼
              columns W × L ──────► GradeFormation
                      │                      │
                      ▼                      ▼
              DetailedGradeResult     ReliefGradeInstance
                      │
                      ▼
         run_column_fill(overlay XY) + persist   ◄── L2, не знает месу
```

Правила шва:

1. **1D plan не знает W.** `plan_ribbon_volume` как сейчас; pack/volume повторяет те же `columns[k].surface_z` на каждую клетку фронта на шаге k.
2. **Discover не пишет `surface_z` / uid.** Только spec.
3. **Paint не читает «локальный пик».** Только spec + `z_at` для clearance/якоря.
4. Прямая дорога = два орто-фронта той же вершины (вид «v1»), не второй materialize.
5. Поворот: диагональный spec с `outward=(±1,±1)`, W=1. Murphy (W>1 diag) позже меняет только `front_strip`.

---

## 4. Порядок имплементации (после утверждения §1)

По слоям, не «сначала меса на старом stamp→fill».

| Шаг | Что | Зачем |
|---|---|---|
| 0 | ТЗ: SoT = R41/R42; R38–R40 = v1 historical; вычистить «пики × facing», C33 4-neigh как норму, C28 sample-до-пула как SoT; **код сейчас = долг** явно | один документ |
| 1 | `GradePaintSpec` + адаптер `PlannedGradeSegment` → spec; materialize через адаптер, поведение = сейчас | шов без смены карты |
| 2 | `front_strip` W×L при W=1 ≡ `outward_columns` | готовность к фронту |
| 3 | Расписание A или B: discover в воркере на готовом z; catalog до пула | R40 без ломки fill |
| 4 | Общий discover: тело → непересекающиеся фронты. Плагин `open_land` (меса z) | каркас |
| 5 | Плагин `road_shoulder`: полотно = одна вершина; прямая = 2 орто; поворот = 8-way W=1 diag | не v1-лента |
| 6 | `shore` / `ravine` на тот же каркас | не копировать пики |
| 7 | Halo от envelope; каскад террас `open_land`; стоп θ | R37/R40 |
| 8 | Снять peak-sample / per-cell owner / pre-pool stitch | |

Не делать шаги 4–6 до 1–3. Не оставлять дорогу на старом `sample_road_shoulder_meter` «пока без поворотов».

Вне перехода: Murphy W>1 diag, R36o, T-3c, BAR-1, layout-origins локации.

---

## 5. Правки ТЗ (шаг 0, после ревью контрактов)

Не сейчас. Когда §1 утверждён:

- Баннер: R41/R42 SoT **в работе**; код ray/пики = долг.
- C26/C28/C33: v2 нормы; 4-neigh и sample-до-пула — struck / historical.
- R36e «пики × facing» → кромка × фронт.
- FineChunkRunner: fill/z готов → relief в воркере; не stamp+fill из pre-pool planned.
- § Mesa gy 901: 8-связность (диагональный `4` — та же меса).
- Changelog: v1→v2 переход, не две locked правды.
- `road_shoulder`: полотно = одна вершина; лучи не в якорь и не пересекаются; поворот 8-way. Прямая = частный случай (2 орто-фронта), не отдельный алгоритм.
- **ReliefVertices locked:** `at_grid` int slot, `members[slot] = dict[(x,y),z]`, uuid в `uids[]` отдельно; не `dict[(x,y), uuid]`. Сверка members↔grid; выкол клетки, не всей вершины.
