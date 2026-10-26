# Wilderness regions — географические сущности, размещение и покрытие (DRAFT)

> Карта межплановых зависимостей и критический путь:
> [`plan-dependency-graph.md`](plan-dependency-graph.md) — зависит от
> `runtime-world-edit-policy.md`, не от pack-модели.

**Статус:** направления и инварианты согласованы 2026-10-08; контракты зафиксированы в ТЗ 2026-10-16/17 (шаг 1 §4 выполнен). Ревью 2026-10-17 (`/analyze-wilderness-regions`) закрыло 8 открытых вопросов: placement tie-break (B), `region_states` + overlay по uid, degraded identity, declaration без veto, det-утилиты в `app/ids`, владение `WorldTopology`, cutover 3b/7b/10b, точки расширения flora/crop. Согласование не означает разрешение на имплементацию — каждый шаг §4 отдельно.

## Базовая политика runtime/worldEdit

Обязательный предшествующий этап — [общая основа runtime/worldEdit](./runtime-world-edit-policy.md); SoT — [tz_runtime_world_edit_policy.md](../../docs/tz_runtime_world_edit_policy.md). Wilderness использует общий resolver/result/diagnostic механизм: авторазрешение по placement priority, WarningError без error defaults при невозможности, одинаковая доменная диагностика runtime/worldEdit и отсутствие скрытой правки авторских данных. До реализации определить границу зависимой операции (регион и зависимые сущности), неполноту snapshot, reason/action и существующий sink. Приёмка включает разрешимый/неразрешимый конфликт, отсутствие defaults и одинаковое решение в двух режимах.

## Согласованное состояние на 2026-10-08

Этот раздел фиксирует итог обсуждения и заменяет исходную узкую постановку «forest/plain Specs». Численные параметры, полный набор shape enum и схемы wire ещё предстоит определить в ТЗ.

### География, покрытие и состояние

- Мир описывается географическими сущностями в пространстве; клетки L0/L2 — растеризованные представления, тайлы и чанки — единицы обработки и хранения.
- Географические сущности: континент, остров, полуостров, низина, равнина, горный массив, океан, море. Перечень не задаёт одну обязательную цепочку родителей.
- Океан может объединять моря; море может быть частью океана или самостоятельной сущностью.
- Отношения «часть целого», «расположен относительно» и «пространственно пересекается» различаются. Один универсальный parent_uid не должен подменять все эти отношения.
- Полуостров обязательно ссылается на континент и имеет с ним сухопутное соединение ненулевой ширины. Касания точкой недостаточно. Autoresolve обеспечивает соединение, declared проходит проверку в геометрии мира до растеризации.
- Остров окружён водой; смысловая принадлежность континенту не означает сухопутное соединение.
- Равнина как форма рельефа отделяется от открытого растительного покрытия. Лес может покрывать географическую равнину. Текущий термин plains требует разведения этих смыслов в целевых контрактах.
- Начальное описание мира, вычисленное/объявленное покрытие и текущее состояние симуляции — разные слои.
- Тип footprint — текущее состояние, а не постоянное свойство сущности (решение 2026-10-16): footprint любого типа может перейти в другой тип по **критериям перехода** (лес → озеро при изменении климата/гидрологии и т.д.). Промежуточный terrain-ключ не вводится; переход может пересекать границу домена (`terrain_masks` ↔ `world.hydrology`). Механизм — **отдельный state-change consumer**: единая точка изменения состояния, принимает доменные консьюмеры и их данные и **выводит целевое состояние из контекста** (совокупность фактов → какое покрытие соответствует области; не из таблицы пар A→B); домены чужой footprint сами не переписывают. Форма критериев и судьба `region_uid` при смене типа — §5 вопрос 11.

### Два способа размещения, один resolver

- Семантическое размещение задаёт опорную сущность/родителя, пространственное отношение, Facing стороны расположения, размер и необходимые ограничения расстояния/области поиска.
- Абсолютное размещение задаёт положение в мировых координатах. Связь с родителем может сохраняться как принадлежность и ограничение.
- Facing стороны относительно опоры и ориентация собственной формы — отдельные параметры.
- Оба способа проходят: описание → кандидат геометрии в мировых координатах → проверка ограничений и пересечений → разрешение конфликтов → зафиксированная геометрия.
- Пересечение не всегда конфликт: лес/равнина — покрытие; море/океан — часть целого; полуостров/континент — обязательное соединение. Для конкурирующих объектов задаются допустимые отношения и политика конфликта.
- Семантическое размещение может искать другой кандидат в разрешённых пределах. Абсолютный объект по умолчанию не перемещается молча: недопустимое положение даёт диагностируемый конфликт; сдвиг требует явной политики.
- Приоритеты и разрешение равенства должны быть детерминированными; состав bake-тайлов и порядок обхода не меняют результат.

### Placement priority и runtime (утверждено 2026-10-08)

- `placement_specificity` — целочисленный приоритет конкретности автора: большее значение выигрывает. Среди конкурентов с разрешёнными опорами порядок: specificity по убыванию → площадь исходного footprint по убыванию → стабильный region_uid по возрастанию.
- Площадь определяется геометрией мира с учётом topology до clipping/конфликтов, не bbox и не числом клеток. При равной конкретности большие объекты размещаются первыми; после изменения формы порядок не пересчитывается.
- Приоритет не отменяет связи опора→зависимый объект, обязательное соединение полуострова или допустимость покрытия/вложенности. Это placement priority, не terrain merge rank и не WP-20.
- Сначала resolver авторазрешает конкуренцию по этому порядку в пределах ограничений. Невозможное размещение в runtime — **WarningError в логе без default-подстановок**, явно неразрешённый результат; не exception/reject всего запуска. Абсолютный объект не сдвигается молча.
- Нормативный контракт: [tz_map_light_bake.md § Placement priority](../../docs/tz_map_light_bake.md#placement-priority). Общая политика и открытые решения worldEdit: [tz_runtime_world_edit_policy.md](../../docs/tz_runtime_world_edit_policy.md). Не вводить отдельную wilderness-only runtime policy.
- Диапазон и wire-поведение отсутствующего placement_specificity, diagnostic API и применение результата в worldEdit ещё требуют определения. Общая миграция существующих domain-specific defaults не выполняется этим планом.

### Идентичность и форма

- У региона стабильный UID в пространстве мира. Генерация привязана к world_uid/world_seed и стабильной идентичности кандидата, а не к текущему набору тайлов.
- Форма вычисляется детерминированно от идентичности/seed и typed параметров; необходима фиксация версии генератора и входных данных snapshot.
- Для разных wilderness-объектов вводятся собственные shape enum и typed объекты параметров. Общие геометрические примитивы и растеризация переиспользуются.
- UID не заменяет параметры и не кодирует произвольные authored вершины. Конкретная схема хранения resolved Specs, индекс поиска по пространству и формула UID — открытые технические контракты.

### Лес: авторское начальное состояние и симуляция

- Автоматическое forest/open-land покрытие вычисляется из условий мира. Suitability участвует в автоматическом возникновении леса.
- Явно объявленный автором forest ставится в начальном состоянии даже при неподходящих условиях. Климатическая suitability не отменяет declaration.
- Затем выигрывает симуляция: лес может деградировать, погибнуть, восстановиться или распространиться. Исходное declaration сохраняется; текущее состояние может ему уже не соответствовать.
- Повторное чтение/materialize не должно восстанавливать погибший лес поверх состояния симуляции. Разделение исходного Pack snapshot и gameplay deltas согласуется с WP-20; детализация состояния/дельт требует ТЗ.
- Начальный состав declared-леса и поведение при отсутствии подходящих видов ещё предстоит определить. Нельзя молча отказывать в forest paint из-за пустого suitability.

### L0/L2 и границы scope

- Термины масштаба и адресации (фиксируются, решения 2026-10-16; в плане, ТЗ и коде
  не переопределять. Каноническое имя = имя POJO/wire-поля; code alias — локальный
  синоним в коде):

  **Единица контракта — клетка.** Входной контракт всегда в клетках: координаты и
  размеры — fine cells. Суффикс `_m` в существующих wire-именах (`origin_x_m`,
  `radius_m`, `tile_macro`, `light_span`, `fine_to_*`) — наследие наименования;
  значения — клетки. Метры и имперские величины — display-интерпретации на выходе
  (`measurement_system` мира, `distance_unit`/`cell_size` app settings →
  narration/LLM/UI); на вход они не влияют. `fine_cell_size` (константа 1) —
  физический масштаб клетки для display. Имперский authored-ввод вне контракта;
  поддержка — только как conversion перед backend wire (UI/import layer), никогда
  внутри генератора. **Новые wire-поля Spec не используют суффикс `_m`** —
  безсуффиксные имена (`origin_x`, `radius`); существующие `_m`-поля не
  переименовываются этим планом (отдельная миграция).

  | Термин | POJO / wire имя | Code alias | Значение |
  |---|---|---|---|
  | **макро-тайл** | `TileManifestEntry.gx`/`gy`; `world_bounds` — AABB в единицах макро-тайлов | `gx, gy` | адресная единица мира, persist-атом пака |
  | сторона макро-тайла в fine cells | `fine_cells_per_map_cell` (worlds, `WorldGridSettings`, manifest) | `tile_macro` (`map_cell_fine_span`) | default 1000 → тайл 1000×1000 fine cells |
  | **light-клетка (L0 cell)** | `(tx, ty)` — клетка внутри макро-тайла | `tx, ty` (`LightCellRef`) | растровая единица L0, не сущность |
  | сторона тайла в light-клетках | `world_map_cells_per_tile` (worlds, manifest) | `side`, `cells_per_side` | default 32 |
  | fine cells на light-клетку | `light_span` (property `ParentLightTile`/`LightGridScale`, SoT `light_span_for`) | — | `fine_cells_per_map_cell // world_map_cells_per_tile` = 31 (int-деление; остаток поглощает краевая клетка) |
  | **fine cell (L2 cell)** | `fine_cell_size` (manifest, константа 1); позиция `(x, y)` — мировые fine-координаты | `Coord = (x, y)` | 1 fine cell = 1 м при `fine_cell_size=1` |
  | **чанк (persist-атом L2)** | `(cx, cy)` внутри макро-тайла (`FineTerrainChunkWire`, `ChunkRef`) | `cx, cy` | `chunk_columns` колонок на сторону (default 32×32) |
  | колонка в чанке | `(lx, ly)` (`FineTerrainColumnWire`) | `lx, ly` | chunk-local |

  Геометрия регионов и все преобразования положений, расстояний, размеров и допусков
  считаются в мировых fine-координатах через единый масштаб.
  `world_map_cells_per_tile` и `light_span` — параметры растеризации/хранения L0 и не
  меняют размер участка. Мир теоретически может увеличить `fine_cells_per_map_cell`,
  но разработчик этого не рекомендует.
- Прежний пример tile=3000 / light_m≈93 и связанные debug-сценарии относятся к устаревшему контракту и не являются доказательством текущего поведения кода или основой целевой архитектуры.
- Цель: resolved геометрия и правила покрытия — общий источник для L0 и L2; L0 не определяет точный контур через набор клеток.
- Для region-backed landcover контракт nearest carry уточняется: L2 пересчитывает покрытие из того же snapshot, включая восстановление фона вне точного контура, с сохранением более приоритетных доменов. Точка интеграции должна предшествовать выбору hills по terrain.
- Политика пересечений (геометрический overlay либо выбор победителя при запросе покрытия), правило растеризации и revision-check остаются проектными решениями для ТЗ.
- Топология поверхности planar/wrapped/sphere остаётся в этом плане как пространственная зависимость.
- **Топология нижнего слоя вынесена в отдельный план:** [deep-layer-topology.md](./deep-layer-topology.md). Она не блокирует согласование механики географических регионов и не реализуется этим планом.

---

**Актуальный запрос:** географические сущности с собственной геометрией, семантическое/абсолютное размещение через общий resolver, отдельное начальное и симулируемое покрытие; L0/L2 — представления одного пространственного мира. Исходный запрос касался лесов/полей/водоёмов вместо квадратных масок.

**ТЗ:** [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) § «Домены terrain_masks (target)», § «Declare = Spec в домене», § MaskDomain materialize (plugin map), § Forest mask → flora (A∧B); [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) § WP-19/20/22; [`docs/tz_flora.md`](../../docs/tz_flora.md) § Climate suitability.

**Предыстория решения:** сначала обсуждалась переключёвка чанков wilderness на мировые координаты (вариант A). Итог обсуждения: «квадратность» — проблема **генерации** (маски per-cell / AABB), не адресации файлов. Rekey чанков — ортогонально и **откладывается**; migration-script не нужен, пока storage остаётся per-chunk.

---

## 0. Зависимость: `world_topology_mode` (требование разработчика)

Новый скаляр мира — **координатная карта соседей** сетки (топология, не механика транзита):

```text
world_topology_mode: "planar" | "wrapped" | "sphere"   # default: "wrapped"
```

| Режим | Край x/y |
|---|---|
| `planar` | прямая поверхность, края **не** соединены: соседа за краем нет |
| `wrapped` | тор: за `x_max` → `x_min` (тот же y), за `y_max` → `y_min` (тот же x) — текущая семантика `antagonist_tile` |
| `sphere` | планета: по x — как у тора; **каждый** край y сшит сам с собой — за `y_max` и за `y_min` та же краевая строка со сдвигом `x' = (x + w/2) mod w` и инверсией Δy-intent — **новая** семантика |

**Решения разработчика (2026-10-07):**

- Три режима; mode выставляет **координатную карту соседей** (сами координаты клеток/тайлов не меняются). Единая точка резолва — `WorldTopology` policy (см. «Целевая реализация» ниже), `grid_neighbor`/`antagonist_tile` становятся её делегатами; `if mode ==` в потребителях не вводится.
- `closed_planet_grid` и целевая топология нижнего слоя — отдельная ось, вынесенная в [deep-layer-topology.md](./deep-layer-topology.md); не часть scope этого плана.
- Default `wrapped` — соответствует текущему поведению `full_bake` (шов уже строчится безусловно).

**Потребители topology lookup** (полный список — вопрос 14 ниже): `apply_world_seam`, `antagonist_tile`/wrap lookups, `gridNeighborHalo` на кромке (сейчас без wrap — рассинхрон с L0), транзит за край, контуры регионов у шва, pathfinding/дистанции, `RegionShape`-растеризация, climate field.

**Факты из кода:** шов тор уже безусловен (`worldMapBakeOrchestrator` full bake → `apply_world_seam`); `closed_planet_grid` живёт на `worlds` (SQL + `WorldTerrainScalars`), гейтит только magma; `antipode_xy` — half-width wrap (тор, не сфера); `gridNeighborHalo` — только `grid_neighbor`.

**Решения по топологии (2026-10-07 / 2026-10-16).** Открыт один под-вопрос — продуктовая семантика за краем `planar` (помечен «Открыто», не блокирует):

*Транзит (решено 2026-10-16 — обычное движение, не отдельный механизм):*

- Транзит за край = **обычный шаг по neighbor lookup**; `world_topology_mode`
  определяет только **координатную карту соседей** краевых клеток:
  `wrapped` — за `x_max` сосед `x_min` той же строки; за `y_max` сосед `y_min`
  того же столбца;
  `sphere` — по x как у тора; за `y_max` и за `y_min` — та же краевая строка
  со сдвигом `x' = (x + w/2) mod w` и инверсией Δy-компонента intent
  (север→юг, аналог magma ±z flip — часть координатной карты, не механика);
  `planar` — соседа нет → ребра пути нет (как void под `z_magma_bottom`,
  не ошибка).
- Отдельный transit-event **не требуется**: смена L0-координат идентична
  обычному движению, разница режимов — только в lookup. Наррационное событие
  (`world_edge_crossing`) — опционально и ортогонально, не часть контракта.
- Открыто по `planar`: продуктовая семантика за краем (impassable void /
  обрыв с падением) — не блокирует lookup-контракт.

*Sphere — сетка:*

5. Полюсный флип `x + w/2` требует чётной ширины — **решено 2026-10-16:
   чётность обязательна только по x** (число колонок `w = x_max − x_min + 1`
   чётно; на высоту требования нет) — как инвариант сетки, не валидация на
   вводе автора. Автор мира сетку не рассчитывает — движок нормализует
   `world_bounds` до чётной ширины при resolve (расширение на колонку),
   без reject-валидации в authored-вводе.
6. Крайняя строка y — **решено 2026-10-16: обычная строка, особых правил
   нет.** Термин «полюс» принадлежит climate-домену (`climate_pole`,
   `SurfaceClimateField`); в топологии полюс — не сущность и не точка, а
   шов-кромка краевой строки. Координатная карта: северный сосед `(x, y_max)` —
   `((x + w/2) mod w, y_max)`; южный сосед `(x, y_min)` —
   `((x + w/2) mod w, y_min)`; оба перехода инвертируют Δy-intent.
   Виртуальной строки/особого случая не вводится; в `wrapped`/`sphere` у
   каждой клетки всегда 4 соседа.

*Техническое:*

**Экстенты через шов (решено 2026-10-16 — переиспользовать идиомы, нового
механизма не вводить):** identity seam-сущности — canonical owner по образцу
`WorldBounds.wrap_owner_and_other` (`frozenset`-пара, owner = min — один
`region_uid`, а не две части); геометрия через шов — local-mod нормализация
на границе по образцу `antipode_xy` (`lx = x − x_min; mod w; + x_min` —
shape в unrolled-пространстве, `mod` при rasterize/lookup); writer шва —
canonical owner (region-anchor на owner-стороне). Новое — только применение
этих идиом к экстентам `RegionShape`/bbox `wilderness_region_entries`
(footprint сегодня шов не заворачивает).

13. Частичный bake — **решено 2026-10-16: pull-строчка, bake пишет только
    в свою пользу.** Ограничение «оба конца в bake» (`worldSeam.py`)
    снимается; направление owner → antagonist и `WorldSeamCopy` не меняются:
    - baked tile = `other` (antagonist) без owner → читает owner-rim из пака,
      применяет `WorldSeamCopy` к своему rim;
    - baked tile = `owner` без antagonist → ничего не строчит (его rim —
      источник; antagonist подтянет при своём bake — self-healing);
    - pack-write за пределы bake-scope **не вводится** (per-tile persist
      ownership не нарушается).
    Чтение чужого tile state — по идиоме detailed halo (`grid_neighbor`).
14. Потребители mode — **подтверждён расширенный список (2026-10-16):**
    `antagonist_tile`, `apply_world_seam`, `gridNeighborHalo` (L2), транзит
    (neighbor lookup), контуры регионов у шва, hydrology/z-continuity,
    **pathfinding/дистанции** (кратчайший путь через край — topology-aware
    рёбра A*), **растеризация `RegionShape` у шва** (unrolled + `mod`),
    **climate field** (согласование `SurfaceClimateField` с mode у полюсов).

**Целевая реализация (один механизм резолва; потребители mode не читают и
не ветвятся по `if mode ==`):**

- `worlds.world_topology_mode` — SQL-колонка + поле scalars POJO по прецеденту
  `closed_planet_grid` (`worlds` + `WorldTerrainScalars`); wire default
  `wrapped`.
- **Единый `WorldTopology` policy** (dataModel, владеет `mode` + `WorldBounds`) —
  единственная точка резолва смежности для всех потребителей из списка 14:
  - `neighbor(x, y, facing) -> (x', y') | None` — вся координатная карта
    (tor-wrap / sphere self-stitch / planar `None`);
  - признак edge-crossing и трансформ intent в результате lookup — потребитель
    (movement resolver) не детектит «пересёк ли край» сам: Δy-flip для
    sphere-y-кромки, identity иначе;
  - `canonicalize(x, y)` — local-mod нормализация (`lx = x − x_min; mod w`),
    идиома `antipode_xy`;
  - пары шва и их facings — из `WorldTopology`, не из захардкоженной
    тор-формулы `antagonist_tile` (которая становится делегатом).
- Нормализация чётности — в resolve `world_bounds`
  (`world_bounds_from_world` / scalars resolve): при `sphere` нечётное
  `w = x_max − x_min + 1` расширяется на колонку; authored-ввод не валидируется.
- `apply_world_seam`: пары и facings — из `WorldTopology`. x-края — owner →
  antagonist как сейчас; **sphere y-края — пары одной строки
  `(gx, y_edge) ↔ ((gx + w/2) mod w, y_edge)`, rim map NORTH↔NORTH / SOUTH↔SOUTH
  (facing партнёра НЕ `opposite` — отличие от текущего `_copy_rim`)**;
  `planar` — пар нет, no-op. Pull-семантика частичного bake — по решению 13.
- `gridNeighborHalo` — через `topology.neighbor` (устраняет рассинхрон L0/L2
  на кромке).
- Транзит/movement resolver — `topology.neighbor` + трансформ intent из
  результата; события нет.
- `RegionShape`/растеризация — координаты shape в unrolled-пространстве;
  `topology.canonicalize` на границе при rasterize/lookup; canonical owner
  для seam-регионов (`region_uid` один, anchor на owner-стороне).
- `antipode_xy`/`closed_planet_grid` — ось нижнего слоя
  ([deep-layer-topology.md](./deep-layer-topology.md)), не трогается.

**Реализация topology — отдельный план** (решение 2026-10-16, §5 вопрос 10):
[surface-topology.md](./surface-topology.md). Этот §0 — контракт-зависимость;
этапы реализации там, не в §4 этого плана.

---

## 1. Диагноз текущего состояния

| Домен | Сейчас | Проблема |
|---|---|---|
| Поселения | `territory_volume` AABB, `l.{uid}.terrain.zst` | footprint квадратный (LOC-T-3 AABB — ок для occupancy, но не форма) |
| Леса / равнины | `LandcoverContributor` — per-cell по climate profile, без сущности | нет «региона»: ни uid, ни контура, ни границы — только клетки |
| Горы / ravines | `MountainSpec`/`RavineSpec` → `MaskFootprint` | ✅ уже сущности (эталон) |
| Водоёмы | `world.hydrology.declared_*` Specs | ✅ уже сущности |
| Пашни | нет | `FarmlandSpec` в `declared_regions[]` — в плане сразу (#2); «later» снято |

Каркас готов: `MaskDomainMaterializer` protocol + `run_mask_domain` (declared > anchors > autoresolve → `MaskFootprint` → apply). Не хватает **Spec-типов и materializer'ов для forests/plains/fields** и **autoresolve регионов** (органические контуры вместо per-cell cliento paint).

**Граница engine/N+1 в связке домен→terrain-ключ (находка 2026-10-16):**

| Уровень | Сейчас | Следствие для регионов |
|---|---|---|
| Домен (`MaskDomainId`) | engine enum; новый член = PR | домен = механика materialize/apply, не тип покрытия |
| `system_terrain` | N+1 реестр мира (`WorldTerrainRegistry`) | степь/болото/… — записи реестра мира, не engine PR |
| Домен → ключ | фиксировано 1:1 (`default_*.system_terrain` → `system_terrain_for_domain()`) | для сменяемого типа связь разрывается: красящий ключ берётся из **состояния региона**, policy даёт только default/fallback |
| climate → ключ | `resolve_forest_plains` — if-цепочка из двух policy-ключей по rainfall | resolver «контекст → покрытие» обязан маппить на множество ключей `terrain_set` мира (N+1), не на хардкод двух полей — иначе N+1-ключ записать можно, покрасить нельзя |
| merge rank | по `MaskDomainId` (`TERRAIN_MERGE_RANK_HIGH_TO_LOW`) | решено 2026-10-16: целевое — rank per-key как поле `TerrainRegistryEntry` (данные мира, следует за `current_type` при переходах); domain-кортеж — переходное состояние |
| биом vs terrain | холодные зоны на `climate_zone_id`, terrain не трогают | region type — классификация покрытия; paint — terrain-ключ реестра; климат — отдельный слой (appearance + критерии перехода) |

## 2. Исходный forest/plain срез (уточняется согласованными решениями выше)

### Инварианты

1. Wilderness-домены (forests/plains/farmland) — **Spec-сущности**: `identity_key()`, declare/anchor/autoresolve merge через `default_collect`, materialize → `MaskFootprint` произвольной формы.
2. Spec — **resolution-independent геометрия** (параметры контура + seed), растеризуется на light grid (L0) и на fine grid (L2) одним SoT.
3. Тайл — только сетка растеризации и persist-атом чанка; контур региона пересекает тайлы свободно.
4. `LandcoverContributor` → thin: делегирует домены в `run_mask_domain`; per-cell climate paint остаётся **только** fallback для клеток вне любого региона (или убирается при полном покрытии — решает ТЗ).
5. Forest gate A∧B применяется к автоматическому возникновению леса, через shared suitability. Явный authored forest задаёт начальное состояние без климатического veto; дальнейшую жизнеспособность определяет симуляция. **Синхронизировано с ТЗ 2026-10-17:** `tz_map_light_bake` § Регионы покрытия › Declaration и suitability; § Forest mask → flora — A∧B только для autoresolve. Declared forest при B=∅ → лог `landcover | declared_without_suitability`, paint выполняется.
6. Water bodies **не** дублируются под terrain_masks: остаются `world.hydrology.declared_*`; регион-реестр (см. шаг 6) может **индексировать** их для read/debug, не владея.

### Слои и роли (исторический срез; актуальное — § Целевая архитектура ниже)

| Компонент | Ответственность |
|---|---|
| `dataModel/terrainMasks/regions/` (было `{forest,plain,farmland}/specs.py`) | Spec POJO домена: shape/knobs, `identity_key()`, optional `location_uid` |
| `dataModel/masks/enums/maskDomainId.py` | `MaskDomainId.LANDCOVER` — один член (было `FARMLAND`; снято — farmland внутри LANDCOVER) |
| `generators/terrain/landcover/` (было `masks/{forest,plain}/`) | один materializer-плагин: collect (default_collect), autoresolve (climate→seed→контур), materialize (shape→cells), apply (terrain paint) |
| `lightGrid/contributors/landcover.py` | Thin: `run_mask_domain(LANDCOVER)` (было FORESTS + PLAINS); per-cell fallback |
| `dataModel/spatial/regionShape.py` + `masks/regionRasterizer.py` | Общий контур региона → raster на произвольной сетке (light + fine) — shared, не копипаста |
| `pack/read/` + `fineChunk*` | L2: chunk-клетки внутри region mask → `system_terrain` региона + `region_uid` (стемпинг при materialize чанка); overlay по uid на read (#8) |
| manifest | `wilderness_region_entries[]`: индекс для read/debug/LLM. Resolved Spec — derive-on-read из world data (#8), не персистится |

### Data flow

```
world.terrain_masks.declared_regions[] ─┐
  anchors (named geo → Spec)            ├→ default_collect → Spec list
  autoresolve (climate seeds → blobs) ──┘        │
                                       materialize(spec) → MaskFootprint (organic)
                                              │
                          ┌───────────────────┼────────────────────┐
                          ▼ L0                ▼ manifest           ▼ L2
                    apply_terrain       region_entries[]      chunk cells:
                    (light canvas)      (debug/LLM/read)      in mask → region terrain
```

## 3. Исходный эскиз контрактов (требует пересмотра; фиксируется в ТЗ до кода)

```text
ForestSpec(BaseModel, frozen):
    entry_type: Literal["forest"]
    origin_x / origin_y: int    # ← снято 2026-10-17: координаты только в shape (см. каркас ниже)
    shape: RegionShape          # blob(radius+roughness+seed) | polygon(vertices)
    density / edge_falloff: …   # knobs домена
    placement_specificity: int | None   # § Placement priority; missing — решено 2026-10-17 (None ниже любого явного)
    location_uid: str | None    # optional link, как MountainSpec
    identity_key()

PlainSpec / FarmlandSpec — тот же каркас, свои knobs.
WorldTerrainMasks += declared_forests / declared_plains / declared_fields: list[Spec]
    # ← снято: единый declared_regions[] (см. «Решения контракта»)
```

Исторический эскиз; актуальный контракт — «Coverage region — каркас
контракта» ниже и ТЗ § Регионы покрытия.

SoT геометрии — `RegionShape` (resolution-independent): один shape → два rasterize.
`MaskFootprint` остаётся контрактом materialize **для L0** (`cells: frozenset[LightCellRef]`)
и не обобщается на fine-сетку (решение 2026-10-16, вариант B). Для L2 та же `shape`
растеризуется `regionShape.rasterize(shape, grid)` на fine-координаты; результат —
`set[Coord]` для merge в `surface_terrain`. Отдельный `FineMaskFootprint` вводится
только при появлении payload на колонку (z-override/facing) — не заранее.

### Coverage region — каркас контракта (решения 2026-10-16; draft до фиксации в ТЗ шагом 1)

```text
# dataModel/terrainMasks/landcover/specs.py (или regions/)

RegionSpecBase(BaseModel, frozen):
    name: str | None                  # identity declared (#1); обязателен при author-валидации
    shape: RegionShape                # bbox | ellipse | polygon | anchor_radius (#7); координаты — в shape, origin нет
    density: float = 1.0              # доля заполнения (#9)
    placement_specificity: int | None # ge=0; tie-break равного merge_rank (#7); None — ниже любого явного
    location_uid: str | None          # optional link, как MountainSpec
    identity_key()

ForestSpec(RegionSpecBase):    entry_type="forest"    # без flora — точка расширения (#9)
PlainSpec(RegionSpecBase):     entry_type="plains"
FarmlandSpec(RegionSpecBase):  entry_type="farmland"  # без crop — точка расширения (#9)
LandcoverDeclareEntry = ForestSpec | PlainSpec | FarmlandSpec | …
    # discriminated union по entry_type (паттерн MountainDeclareEntry)

WorldTerrainMasks += declared_regions[]: list[LandcoverDeclareEntry]
MaskDomainId += LANDCOVER                # один новый член; домен = механика, не тип
LandcoverRegionsCategoryPolicy           # enable / autoresolve / fallback-ключи
```

**Разведение «декларируемый вид» vs «состояние»:**

- `entry_type` Spec — **закрытый** typed union (forest/plains/farmland):
  декларируемый вид с typed knobs; новый декларируемый вид = engine PR.
- `current_type` состояния региона — **`system_terrain` ключ N+1** реестра мира:
  свободен, переходы целятся в ключи без Spec (степь, болото), engine PR не нужен.
- `entry_type` переиспользует значения terrain-ключей ("forest" → terrain `forest`),
  поэтому начальное состояние = identity-маппинг и `current_type` всегда является
  валидным `system_terrain`.

**Красящий ключ — из состояния, не из policy:**

```text
paint_key(region) =
    state.current_type        # слой состояния, когда есть (WP-20 patch)
    → spec.entry_type         # declaration = начальное состояние
    → policy fallback         # LandcoverRegionsCategoryPolicy
```

**Решения контракта (2026-10-16):**

- wire-форма: **единый `declared_regions[]`** — discriminated union по
  `entry_type`, один collect/merge pipeline; placement resolver работает на
  плоском множестве конкурентов всех типов (раздельные списки отвергнуты:
  конкуренция меж-типовая).
- merge rank: целевое — **rank per-key как поле `TerrainRegistryEntry`**
  (данные мира; `may_paint_terrain` сводится к сравнению rank). Domain-кортеж
  `TERRAIN_MERGE_RANK_HIGH_TO_LOW` удаляется **шагом 3b** (сразу после
  появления поля — два SoT ранга через шаги 4–7 не тащим).
- Домены: целевое — **один домен `LANDCOVER`**; `FORESTS`/`PLAINS` сливаются в
  `LandcoverRegionsCategoryPolicy`; `default_forests`/`default_plains`
  сохраняются как wire-алиасы fallback-политики. Cutover — **шаги 7b**
  (hills/open-land по реестру: `place_hills`, `openLandTerrains`) и **10b**
  (удаление enum-членов, `resolve_forest_plains`, policy-классов). Без них
  `current_type` открыт на бумаге, но холмы/open-land/merge работают только
  для forest/plains.
- Autoresolve eligibility: текущий `resolve_forest_plains` — хардкод двух
  ключей. Целевой resolver «условия → покрытие» подключается к **домену
  флоры** (`FloraSuitabilityIndex` + eligibility-данные) — отдельный большой
  трек вне этого плана; до него autoresolve использует упрощённую таблицу
  (форма таблицы — в шаге 1 ТЗ).
- kind→key индирекция не вводится (`entry_type` = terrain-ключ); если coverage
  type станет богаче ключа — маппинг как world data, отдельное решение тогда.

### Целевая архитектура (2026-10-16; консьюмеры универсальные, домены — плагины)

Принципы: один класс — одна ответственность; универсальные консьюмеры по
образцу `run_mask_domain` + `default_collect`; домены — данные + хуки-плагины,
не копии пайплайнов. `CoverageResolver` **один** на две точки потребления
(autoresolve bake-time и state-change runtime) — контракт «контекст →
покрытие» единый, отдельных initial/transition резолверов нет.

**dataModel — контракты (world data):**

| Класс / поле | Файл | Одна ответственность |
|---|---|---|
| `WorldTopology` | `dataModel/worldPack/wire/worldTopology.py` (рядом с `worldBounds.py`) — **владелец: `surface-topology.md` шаг 2**, здесь только потребляется | смежность: `neighbor` (+edge-crossing, intent transform), `canonicalize` (local-mod), пары шва |
| `worlds.world_topology_mode` | `db/models/world.py` + `db/migrations/0001_initial.sql` + `dataModel/terrain/worldTerrainScalars.py` — **владелец: surface-topology** | скаляр мира по прецеденту `closed_planet_grid` |
| `RegionSpecBase` + `ForestSpec`/`PlainSpec`/`FarmlandSpec` + `LandcoverDeclareEntry` | `dataModel/terrainMasks/regions/` (новый пакет по образцу `terrainMasks/mountain/`) | typed Spec-каркасы + discriminated union `entry_type`; `placement_specificity`, `density`, `name` |
| `declared_regions[]` | `dataModel/terrainMasks/worldTerrainMasks.py` | wire-поле union-списка |
| `MaskDomainId.LANDCOVER` | `dataModel/masks/enums/maskDomainId.py` | один член; `FORESTS`/`PLAINS` — переходные до шага 10b |
| `TerrainRegistryEntry.merge_rank` / `eligibility` / `inertia` / `hills` | `dataModel/terrain/terrainRegistryEntry.py` (+ canonical defaults builtin-ключей) | rank/eligibility/hills — данные мира на ключе; SQL не меняется (`worlds.terrain_registry` — JSON) |
| `RegionShape` | `dataModel/spatial/regionShape.py` | геометрия в unrolled fine-координатах (рядом с `Facing`); `contains`/`bbox`/`area` |
| `RegionState` | `dataModel/regions/regionState.py` (новый доменно-нейтральный пакет: тип региона может уходить за `terrain_masks`) | `current_type` + progress + overrides + history + revision + tombstone |
| `region_states` | `db/migrations/0001_initial.sql` + `db/models/regionState.py` + `db/repositories/regionStateRepository.py` | entity-store состояния (не WP-20) |
| `wilderness_region_entries[]` + `WildernessRegionEntry` | `dataModel/worldPack/meta/worldPackManifest.py` + `dataModel/worldPack/meta/wildernessRegionEntry.py` | индекс uid/current_type/bbox/status для read/debug |
| `WorldMapCellWire.region_uid?` / `FineTerrainColumnWire.region_uid?` | `dataModel/worldPack/wire/` | membership клетки для overlay по uid |

**application — engine:**

| Класс / функция | Файл | Одна ответственность |
|---|---|---|
| `seeded_u01` / `seeded_index` | `app/ids/deterministicIds.py` (перенос из `relief/geom`, шаг 0) | det-потоки; `bake_seed` удаляется в пользу `seed_root` |
| `LandcoverMaterializer` | `application/worldData/generators/terrain/landcover/` — `materializer.py` (протокол, тонкий), `collect.py` (declared/anchor/state-lookup/anchor-резолв), `autoresolve/seedGrid.py`, `autoresolve/claim.py`, `autoresolve/mergeSublocations.py` | плагин домена: адаптация к `run_mask_domain`; autoresolve — три модуля, не один класс (`class-size-limit`) |
| `RegionRasterizer` | `application/worldData/masks/regionRasterizer.py` | `RegionShape` → `frozenset[LightCellRef]` (L0) / `set[Coord]` (L2); seam через `topology.canonicalize` |
| `regionPrecedence` | `application/worldData/masks/regionPrecedence.py` | одна функция сравнения кандидатов клетки (rank → specificity → area → uid) для L0 и L2 |
| `run_mask_domain` + `default_collect` | `application/worldData/masks/runMaskDomain.py` (есть) | collect/merge — не трогаем; `materialize(spec, scale)` остаётся без ctx — всё, что требует ctx (anchor, state, topology), резолвится в `collect`, как у гор |
| `apply_terrain_footprint` | `application/worldData/masks/applyFootprint.py` (есть) | paint + rank + `region_uid`; rank-источник переезжает на `entry.merge_rank` (шаг 3b) |
| `LandcoverContributor` | `pack/bake/lightGrid/contributors/landcover.py` | thin: `run_mask_domain(LANDCOVER)` + per-cell fallback `default_*` |
| `apply_world_seam` | `pack/bake/lightGrid/worldSeam.py` — **владелец: surface-topology** | пары/facings из `WorldTopology`; pull per Q13 |
| `gridNeighborHalo` | `pack/refine/gridNeighborHalo.py` — **владелец: surface-topology** | соседи через `topology.neighbor` |
| `CoverageResolver` + `RegionFacts` | `application/worldData/regions/coverageResolver.py`, `regions/regionFacts.py` (новый пакет) | контекст → целевое покрытие (`current_type`/кандидаты) через eligibility реестра; не таблица A→B |
| `StateChangeConsumer` | `application/worldData/regions/stateChange/` — `consumer.py` (оркестрация), `progress.py` (гистерезис/порог/inertia), `history.py`, `morphEffects.py` (эффекты по роду ключа → очередь refine) | единый writer состояния: сбор фактов → `CoverageResolver` → `RegionState` в `region_states` через repo; не генератор, не bake |
| `regionStateOverlay` | `application/worldData/pack/read/regionStateOverlay.py` | один фасад read: подмена ключа по `region_uid` + state; tombstone → fallback |
| domain fact plugins | `application/worldData/regions/factConsumers/` | реестр консьюмеров фактов: climate / hydrology / relief / flora(=None) / time — только поставка фактов в контекст |

**Потребители:** LandcoverContributor (paint по `current_type`), fine refine
(тот же `RegionShape` → `surface_terrain`), manifest/debug API (region
entries), pathfinding/транзит (`topology.neighbor`), flora-трек
(eligibility), опциональная наррация `world_edge_crossing`.

**Логирование — ключевые точки (2026-10-16).** Формат по существующей
конвенции `logger.<level>("<domain> | <event> | key=value …")` (образцы:
`world_seam | owner=…`, `json_validation | WarningError | path=…`):
identity-fallback (регион без `name` → позиция), collect/merge (spec
отклонён приоритетом/конфликтом — с `region_uid`, reason), autoresolve
(кандидаты, выбранный вид + почему), rasterize/seam (`canonicalize` при
пересечении шва), paint (источник `paint_key`: state/spec/fallback;
merge-rank отказ на клетке), `CoverageResolver` (выбранный `current_type`
+ решающие факты — без него «почему степь, а не лес» не диагностируется),
state-change (переход типа, прогресс через порог, частичный переход),
unresolved (невалидный terrain-ключ, неразрешимый конфликт — WarningError,
без error defaults), revision-check при re-materialize.

## 4. Порядок имплементации (пересобран под решения 2026-10-16/17; ревью 2026-10-17)

Гейт: шаг без раздела ТЗ — не готов. Шаг 1 (ТЗ sync) **выполнен
2026-10-17**: раздел `tz_map_light_bake` § «Регионы покрытия» и разделы
`tz_world_pack_storage` § `WildernessRegionEntry` / § Region state store /
§ Region state overlay существуют; ссылки ниже — на их подзаголовки.
Шаги — атомарные: один слой / один контракт / одна группа файлов.
Разрешения на код нет; каждый шаг — отдельный заход с отчётом.

Сокращения путей: `dm/` = `backend/app/dataModel/`, `wd/` =
`backend/app/application/worldData/`, `ids/` = `backend/app/ids/`.

**Уточнение шага 0 (согласовано 2026-10-17):** каналы из §5 #4 задаются
`RegionRngChannel(StrEnum)` в `ids/regionRngChannel.py`, экспортируются через
`ids/__init__.py`: `SEED="seed"`, `CLAIM="claim"`, `EDGE="edge"`,
`DENSITY="density"`. DET-1 нормализует Enum через `.value`, поэтому
каноническая строка и RNG остаются идентичными строковым каналам; это
проверяется в `tests/test_deterministic_ids.py`. `UidKind.REGION`
по-прежнему вводится только шагом 3.

**Уточнение шага 2 по замечанию мастера (2026-10-17):** defaults
`entry_type` берутся через именованные accessors `WorldTerrainRegistry` из
существующих canonical forest/plains entries; canonical farmland entry
добавляется с категорией solid и defaults `TerrainRegistryEntry` для
остальных полей. `Literal` остаётся ограничением закрытых веток union,
новый terrain enum не вводится. Дополнительный файл:
`dm/terrain/worldTerrainRegistry.py`.

| # | Шаг | Цель | ТЗ | Файлы | Проверка |
|---|---|---|---|---|---|
| 0 | det-утилиты в `app/ids` | `seeded_u01`/`seeded_index` → `ids/deterministicIds.py` (тело без изменений); `bake_seed` удалить, потребители → `seed_root` (fallback `"world"` **не переносится** — объект без `world_uid` = ошибка вызова, чинить вызов); таблица каналов `UidKind.REGION` (#4) | `project_data_storage_tz` § DET-1 | `ids/deterministicIds.py`, `ids/__init__.py`; удалить `wd/generators/terrain/relief/geom/{seededHash,bakeSeed}.py`; импорты: `relief/__init__`, `relief/pick/{templatePick,kindRoll}`, `pack/refine/detailed/detailedGradeDiscover`, `generators/terrain/mountains/materializer` | `compileall`; тесты relief pick / kind roll без изменений результата; mountains materialize на тест-мире идентичен до/после |
| 1 | ТЗ sync | ✅ выполнен 2026-10-17 (контракт регионов, state store, overlay, cutover-строки) | — | `docs/tz_map_light_bake.md`, `docs/tz_world_pack_storage.md` | ревью разработчика — пройдено |
| 2 | dataModel: Specs + Shape | `RegionSpecBase{name, shape, entry_type, density=1.0, placement_specificity: int\|None (ge=0), location_uid?}` + `ForestSpec`/`PlainSpec`/`FarmlandSpec` (без `flora`/`crop` — § Точки расширения) + union `LandcoverDeclareEntry` + `WorldTerrainMasks.declared_regions`; `RegionShape` union (bbox/ellipse/polygon/anchor_radius + `EdgeNoise`), `contains(x,y)` / `bbox()` / `area()` (без edge_noise); author-валидация форм | `tz_map_light_bake` § Регионы покрытия › Spec union, › RegionShape, › Точки расширения | `dm/terrainMasks/regions/` (по образцу `terrainMasks/mountain/`), `dm/spatial/regionShape.py` | `compileall`, schema/validate, юнит union-discriminant; `rx<=0` / `vertices<3` / самопересечение → ошибка, не fallback |
| 2b | Placement tie-break | одна функция сравнения кандидатов клетки: `merge_rank(current_type)` ↓ → `placement_specificity` ↓ (`None` ниже любого явного) → `area()` ↓ → `region_uid` ↑; используется L0 `apply` (шаг 6) и L2 paint (шаг 7), собственных сравнений там нет | `tz_map_light_bake` § Регионы покрытия › Пересечения и приоритет; § Placement priority | `wd/masks/regionPrecedence.py` | юнит: равная specificity/разные площади; разная specificity; равенство → uid; перестановка входа не меняет исход; `None` проигрывает `0` |
| 3 | dataModel: реестр + uid | `TerrainRegistryEntry` += `merge_rank`, `eligibility: list[EligibilityRule]`, `inertia`, `hills: HillPolicy\|None`; canonical registry: `merge_rank`/`hills` builtin-ключей в `canonical_defaults()` (road>ravine>mountain>forest>plains — **не** литерал в application); `UidKind.REGION` + формула uid (#1: `name` strip+NFC, `\|` запрещён; fallback `bbox_min`+`kind` / `anchor_uid` / `seed_xy`); `state_fingerprint` — **существует** в `ids/deterministicIds.py`, только применить | `tz_map_light_bake` § Регионы покрытия › Identity, › Реестр и CoverageResolver | `dm/terrain/terrainRegistryEntry.py`, `dm/terrain/worldTerrainRegistry.py`, `ids/uidKind.py` | юнит: правка rx/ry именованного региона ≠ новый uid; безымянный bbox — сдвиг min-угла = новый uid + WarningError в логе; fingerprint меняется при edit |
| 3b | Merge rank cutover | `terrain_merge_rank` / `may_paint_terrain` → `entry.merge_rank` из реестра мира; удалить `TERRAIN_MERGE_RANK_HIGH_TO_LOW`, `WorldTerrainMasks.merge_rank_order`, `system_terrain_for_domain`; домен — writer, не приоритет | `tz_map_light_bake` § Merge `system_terrain`, § Hybrid C | `dm/masks/enums/maskDomainId.py`, `dm/terrainMasks/worldTerrainMasks.py`, `wd/masks/terrainMerge.py`, `wd/masks/applyFootprint.py`, `pack/bake/lightGrid/paintTerrain.py` | существующие тесты merge rank (дороги/ravine/горы/landcover) — тот же порядок; light bake smoke идентичен |
| 4 | `RegionRasterizer` | shape/claim → `frozenset[LightCellRef]` (L0) и `set[Coord]` (fine); seam через `topology.canonicalize`; обход seed-решётки через `topology.neighbor`. **Предусловие:** `surface-topology.md` шаги 1–2 сданы (`WorldTopology` в `dm/worldPack/wire/worldTopology.py`, владелец — surface-topology; здесь не создаётся) | `tz_map_light_bake` § Регионы покрытия › RegionShape; `tz_terrain_generation` § Форма мира (после surface-topology шаг 1) | `wd/masks/regionRasterizer.py` | юнит: та же shape → обе сетки; при `world_topology_mode=wrapped` seam-регион красит оба края |
| 5a | `CoverageResolver` + fact consumers | scorer по `EligibilityRule` (`required` → отсев; `score=Σw·s`; argmax; все отпали → WarningError, тип не меняется); typed `RegionFacts`; реестр `factConsumers/` (climate / hydrology / relief; flora → `None`); interim-правила — в canonical registry `eligibility` (**не** if-цепочка в application), комментарий «цель — rules мира + flora suitability» | `tz_map_light_bake` § Регионы покрытия › Реестр и CoverageResolver | `wd/regions/coverageResolver.py`, `wd/regions/regionFacts.py`, `wd/regions/factConsumers/{climate,hydrology,relief}.py` | юнит: required-отсев; argmax; все отпали → WarningError без default; одинаковые факты → одинаковый target при перестановке кандидатов |
| 5b | `LandcoverMaterializer` | плагин LANDCOVER: `load_declared` / `load_anchor_specs` / `autoresolve_specs` / `collect` (`default_collect`) / `materialize` / `apply`; autoresolve — отдельные модули: `autoresolve/seedGrid.py` (решётка + jitter, `channel="seed"`, `sx/sy`), `autoresolve/claim.py` (`w=f(dist)+шум`, `channel="claim"`, `max_radius`), `autoresolve/mergeSublocations.py` (компонента seed'ов одного вида → регион + саблокации, canonical min); declared/anchor — без climate-veto (› Declaration и suitability); резолв `AnchorRadiusShape` и state-lookup — в `collect`, `materialize(spec, scale)` остаётся чистым | `tz_map_light_bake` § MaskDomain materialize; § Регионы покрытия › Autoresolve, › Declaration и suitability | `wd/generators/terrain/landcover/{materializer,collect,autoresolve/*}.py` | materialize на тест-мире: контур органический; partial bake == full bake по клеткам; declared forest в arid-зоне красится, autoresolve там же — нет, лог `declared_without_suitability`; ни один класс > 300 строк |
| 6 | LandcoverContributor thin + `region_uid` на клетке | `run_mask_domain(LANDCOVER)`; `apply` пишет `system_terrain` (paint_key: state → spec → fallback) **и** `region_uid` победителя (по 2b); density-маска `channel="density"`; edge-шум `channel="edge"`; per-cell fallback `default_*` для клеток вне регионов | `tz_map_light_bake` § Регионы покрытия › Пересечения и приоритет, › L0/L2; `tz_world_pack_storage` § `WorldMapCellWire.region_uid` | `pack/bake/lightGrid/contributors/landcover.py`, `maskDomainRegistry.py`, `dm/worldPack/wire/worldMapCellWire.py`, `wd/masks/applyFootprint.py` | light bake smoke: леса/равнины/пашни = регионы с органическими границами; клетки регионов несут `region_uid`; лог paint-источника |
| 7 | L2 интеграция | ✅ выполнен 2026-10-17 (region paint поточечно в `build_tile_surface_state` между upsample и `place_hills`; `upsample_terrain_from_parent_light` → fallback-роль + restore вне точного контура; `FineTerrainColumnWire.region_uid`; `landcover/finePaint.py`) | `tz_map_light_bake` § Регионы покрытия › L0/L2; `tz_world_pack_storage` § Fine terrain column | `wd/materialize/terrainBatchOrchestrator.py`, `wd/generators/terrain/landcover/finePaint.py`, `dm/worldPack/wire/fineTerrainChunkWire.py` | ✅ refine на границе региона: край чёткий в fine cells, не лесенка L0; колонки несут `region_uid`; hydro-preserve; `test_landcover_fine_paint` 6/6 + регрессия 139 |
| 7b | L2 hills / open-land cutover | `place_hills(plains_key, forest_key, …)` → hills по `TerrainRegistryEntry.hills` ключа клетки (`default_forests.hills`/`default_plains.hills` — wire-совместимый источник до миграции данных мира); `openLandTerrains` → `supports_open_land_grade` записи реестра; `open_land_profile` (`plains`/`forest`) явно выбирает envelope и condition шаблона для N+1; физическая `terrain_category` не меняется | `tz_world_pack_storage` § L2 open-land hills | `wd/generators/terrain/hills/hillPlacement.py`, `wd/generators/terrain/relief/sample/openLandTerrains.py`, `terrainBatchOrchestrator.py` | refine чанка со `steppe`-регионом ставит холмы и open-land grade; forest/plains — результат как до шага |
| 8 | Manifest + debug | `wilderness_region_entries[]` (`region_uid`/`current_type`/`bbox`/`status`) при bake; render outline; region-селектор | `tz_world_pack_storage` § `WildernessRegionEntry` | `dm/worldPack/meta/worldPackManifest.py`, `dm/worldPack/meta/wildernessRegionEntry.py`, pack writer, `api/routes/map.py` (тонко) | manifest содержит регионы; smoke world-test-002 |
| 9a | `region_states` store | SQL-таблица в `0001_initial.sql` + dataclass + repo; single-writer — `StateChangeConsumer` (шаг 10a); массовая запись через `bulkSql` | `tz_world_pack_storage` § Region state store | `db/migrations/0001_initial.sql`, `db/models/regionState.py`, `db/repositories/regionStateRepository.py` | `validate_schema` при старте; recreate БД; юнит repo upsert/tombstone |
| 9b | `RegionState` POJO + revision-check | `RegionState{current_type, pending_target, progress, last_eval_tick, overrides, history[], spec_fingerprint, tombstone}`; при bake/refine тайла: `state_fingerprint(spec_wire)` ≠ store → клетки региона в этом тайле перекрашиваются | `tz_world_pack_storage` § Region state store | `dm/regions/regionState.py`, `wd/generators/terrain/landcover/collect.py` | юнит: fingerprint mismatch → re-materialize клеток тайла; match → без изменений |
| 9c | Region state overlay (read) | один фасад read path: клетка с `region_uid` и `state.current_type ≠ baked` → ключ подменяется; tombstone → policy-fallback ключ; применяется ко всем слоям WP-20 ниже `patch`; лог `overlap_rerank_deferred` при пересечении bbox | `tz_world_pack_storage` § Region state overlay | `wd/pack/read/regionStateOverlay.py` + точка вызова в read facade | юнит: forest→steppe в store → read отдаёт steppe без перепечки; `terrain_delta` patch поверх — не подменяется |
| 10a | `StateChangeConsumer` | единый writer: facts → `CoverageResolver` → прогресс/гистерезис (`strength·elapsed/inertia`, `transition_threshold`), `history[]`, `overrides`; частичный переход → child-регион (саблокация, specificity родителя+1 при равном ранге); доменные эффекты морфинга — **на materialize** (не на read); `elapsed_ticks` — заглушка-параметр (комментарий «заменить при появлении домена времени/LOD»); модули: `progress.py`, `history.py`, `morphEffects.py` | `tz_map_light_bake` § Регионы покрытия › Состояние и переходы | `wd/regions/stateChange/{consumer,progress,history,morphEffects}.py` | юнит: дрейф лес→степь по tick-параметру; гистерезис; частичный переход → child; ни один класс > 300 строк |
| 10b | Landcover domain cutover | удалить `MaskDomainId.FORESTS/PLAINS`, `MASK_DOMAIN_CONTRIBUTOR` → `LANDCOVER`; удалить `resolve_forest_plains`/`profile_for_zone_key`/`*_from_zone` (потребители `terrainZ` → `CoverageResolver` или фоновый ключ policy); `ForestsCategoryPolicy`/`PlainsCategoryPolicy` → `LandcoverRegionsCategoryPolicy` с fallback-ключом; `default_forests`/`default_plains` — wire-алиасы на чтение | `tz_map_light_bake` § Домены terrain_masks, § Plugin map, § Корни JSON | `dm/masks/enums/maskDomainId.py`, `dm/terrainMasks/worldTerrainMasks.py`, `wd/masks/resolveForestPlains.py` (удалить), `wd/generators/terrain/terrainZ.py`, `wd/generators/climate/terrainZ.py` | import world_test_002 без правок JSON; light bake smoke идентичен шагу 6 |
| 10c | worldEdit регионов | `add`/`remove`/`update` элемента `declared_regions[]` keyed by `name`; `remove` → tombstone в store; draft-валидация (`name` обязателен, коллизия имён) через `ResolveContext.validate_only` | `tz_runtime_world_edit_policy`; `tz_map_light_bake` § Регионы покрытия › Identity | import handlers (`validate_only` preflight), `wd/regions/stateChange/consumer.py` | `POST /worlds/import?validate_only=true` без `name` → issue; обычный импорт → WarningError + degraded uid; remove → tombstone; одинаковое решение в обоих режимах |

**Зависимости вне плана:** `surface-topology.md` шаги 1–2 → наш шаг 4
(ребро в `plan-dependency-graph.md`); LOD/время — `elapsed_ticks`
заглушка в шаге 10a; flora — `flora.*` канал eligibility (= `None`) в
шаге 5a, состав леса / культура пашни — точки расширения ТЗ, полей в Spec
нет; `json-validation-unknown-keys.md` шаг 2 — детект `flora`/`crop` как
unknown key в `declared_regions[]`.

Вне scope: rekey чанков на мировую сетку; file-per-region persist
(ломает WP-12/13 — отвергнуто); NamedLocation-объекты для регионов
(link optional, не declare-path — запрещено ТЗ); DAG-ноды; морфинг в
реку/море (река — линейный контракт, море — coastline/autoresolve, #6);
континент/остров/полуостров/море как сущности с владением (следующий
трек; placement priority в полном виде — там).

**Известный gap (фиксируется, не чинится этим планом):** overlap re-rank
— клетка в двух регионах, у одного из которых сменился `current_type`,
не пересчитывает победителя до ближайшего refine чанка / re-bake тайла
(overlay по uid, не по геометрии). Лог `region_state |
overlap_rerank_deferred | region_uid=… neighbors=…`.

## 5. Актуальные открытые вопросы

**Уточнение шага 9c, согласовано 2026-10-18:** лог `overlap_rerank_deferred`
эмитится в read-overlay через доменный `regions/regionStateLog.py` и общий
`loggingConfig` (`region_state/regionStateLog`), один WARNING на UID за batch,
без stdout storm. Writer 10a не дублирует событие чтения. Для batch-read
добавляется `IRegionStateRepository.get_many(world_uid, region_uids)`; metadata
`CellContribution.region_uid` сохраняет membership до общего merge. До 10b
tombstone-fallback — `default_plains.system_terrain`. Wiring — pack read factory
и container; проверки дополнены тестами общего JSON sink. Шаг не отмечается
выполненным до приёмки мастером.

**Детализация реализации 9b (2026-10-18, не отметка выполнен):**
RegionState — frozen, TerrainKey для всех ключей покрытия; overrides содержит
optional density 0..1; history в wire — массив, в POJO — immutable tuple
frozen-переходов. Cause enum: drift/declared_edit/event, at: str|int —
заглушка до доменов времени/событий. Nullable fingerprint унаследован от 9a
(NULL = неизвестная ревизия → mismatch). Типизированный row mapper и async
snapshot loader находятся в wd/regions/. Штатный L0 owner и FineChunkRunner
читают repo перед synchronous compute; DI передаёт репозиторий, отсутствие
repo/row оставляет spec/fallback. Collect ставит spec_fingerprint и
revision_changed на ResolvedRegion (сигнал writer 10a), не пишет state;
текущая форма растеризуется существующим путём в scope тайла. Fingerprint
единый для collect/index, считается до anchor resolution; auto включает
claim/entry_type. Tombstone исключается из materialize; L2 восстанавливает
parent region paint фоном даже при пустом collect. Reset progress/type/history
остаётся 10a, read overlay — 9c. Дополнительные файлы 9b: landcover/types.py,
regionRevision.py, finePaint.py, regionStateMapping.py/regionStateSnapshot.py,
LightGridBakeContext/landcoverInputs, bake/refine caller seams и DI worldData.
SQL, DAG и historical manifest read не меняются.

9b реализован и готов к приёмке, не отмечен выполненным: 109 профильных
тестов прошли (11 новых contract/revision/repo/caller-boundary; 53 прежних
landcover/coverage/index/store; 45 bake modes/parent-light/parallel/finalize).
compileall app и git diff --check чистые. Для тестов с временными pack/SQLite
использован запуск вне sandbox после отказа доступа к temp; окружение не
менялось. finalize запущен через discovery для штатного импорта соседнего
test helper. Регрессия изменения density после collect закрыта пересчётом
fingerprint в индексе (authored_anchor_shape сохраняет anchor reference).
Tombstone не красится; L2 очищает старое parent покрытие к policy-фону.
State writer/reset/history update — только 10a; сервер не запускался,
коммитов нет.

1. `region_uid` — **решено 2026-10-16.** Формула через центральный
   `backend/app/ids`: `entity_uid(world_uid, UidKind.REGION, **keys)`
   (новый член `UidKind` = contract change). Keys по источнику региона:
   - **declared:** `name` — обязателен при author-валидации. Нормализация
     ключа (решено 2026-10-17): `strip()` + Unicode NFC, **без** casefold;
     `UID_PART_SEPARATOR` (`|`) в имени — ошибка author-валидации. Разделение
     режимов — существующая идиома `ResolveContext.validate_only`
     (`jsonValidation/resolve.py`): author-check (JV/импорт, worldEdit draft)
     → issue в отчёт как ошибка; runtime (bake) без имени → **degraded
     fallback** (решено 2026-10-17; `origin_x/origin_y` снято — в Spec их нет):
     `bbox`/`ellipse`/`polygon` → `bbox_min=(x_min, y_min)` из `shape.bbox()`
     + `kind=<shape.kind>`; `anchor_radius` → `anchor_uid`. Плюс
     `FieldPathError` → `log_issues` (`logger.warning` «domain | WarningError
     | path=… code=…») — регион работает, факт degraded-identity в логе;
     сдвиг min-угла безымянного региона = новая сущность (ожидаемо для
     degraded-режима);
   - **anchor:** uid именованного anchor — by design, не fallback;
   - **autoresolve-регион:** seed-клетка `region_seed_xy=(x, y)` — детерминистический факт
     рождения; seed из world data, не от набора испечённых тайлов (связь
     с вопросом 4 — стабильность кандидатов).
   Техническое имя ключа вида формы — `shape_kind=shape.kind`: `kind` уже
   занят параметром `entity_uid(world_uid, kind, **keys)`. Смысл ключа из
   описания fallback `bbox_min + kind` не меняется; API DET-1 не меняется.
   Для `TerrainRegistryEntry.hills` модели `HillPolicy` / `HillShape`
   переносятся в `dm/terrain/`, старые пути `dm/terrainMasks/` — реэкспорты
   тех же классов (устранение цикла через `terrainMasks/__init__.py`).
   В формулу НЕ входят: геометрия (правки не убивают сущность), `entry_type`/
   `current_type`/домен (тип — состояние, морфинг сохраняет uid).
   Revision — отдельный токен `state_fingerprint(spec_wire)`
   (**существует**: `app.ids.deterministicIds.state_fingerprint`), не uid
   (вопрос 8).
2. Farmland — **решено 2026-10-16: в плане сразу.** `FarmlandSpec` входит в
   union `LandcoverDeclareEntry` с первого шага (union стартует полным:
   forest/plains/farmland); «later» из ТЗ снимается.
3. Разведение «равнины» — **решено 2026-10-16.** Два разных домена, два
   имени: `plains` — **только покрытие** (LANDCOVER-ключ рядом с
   `forest`/`steppe`/`swamp`/`farmland`; живёт в `declared_regions`,
   `RegionState`, `system_terrain`); плоский рельеф — факт
   elevation-домена с явным именем `elevation_plain` (предикат над
   высотой/variance, **не сущность и не terrain-ключ**). «Лес на равнине»
   в критериях переходов = «лес на `elevation_plain`» — факт elevation,
   не значение `system_terrain`. Если появится декларация плоского
   рельефа — это Spec relief-домена под своим именем, к landcover
   отношения не имеет.
4. Autoresolve — **решено 2026-10-16.** Placement domain = **поле в мировых
   координатах**, не набор baked-тайлов (partial/full bake идентичны):
   - Контекст — те же domain fact consumers (`factConsumers/`): чистая
     функция `(x, y)` + world data, независимо от bake scope.
   - Seed-точки — coarse-сетка `(sx, sy)` (**не** `gx, gy` — alias
     макро-тайла) + джиттер `seeded_u01(seed_root(world), UidKind.REGION,
     channel="seed", sx=…, sy=…)` в мировых координатах; шаг сетки = масштаб
     региона (knob). **Факт (2026-10-17):** `seeded_u01`/`seeded_index` живут
     в `generators/terrain/relief/geom/seededHash.py`, `bake_seed` — в
     `relief/geom/bakeSeed.py` (с тихим fallback `"world"`), а не в `app.ids`;
     перенос в `app/ids` и удаление fallback — шаг 0.
   - **Каналы рандома `UidKind.REGION`** (решено 2026-10-17; одинаковые
     root/kind/keys = один `Random`, поэтому `channel` обязателен):

     | Канал | Вызов |
     |---|---|
     | seed-решётка | `seeded_u01(seed, REGION, channel="seed", sx=, sy=)` |
     | claim-шум | `seeded_u01(seed, REGION, channel="claim", seed_xy=seed_xy, x=, y=)` |
     | edge_noise | `seed_rng(seed, REGION, channel="edge", uid=, x=, y=)` |
     | density-маска | `seeded_u01(seed, REGION, channel="density", uid=, x=, y=)` |

     `seed = seed_root(world)`; keys — только именованные (`seed_rng(…, **keys)`).
   - Вид seed'а — `CoverageResolver` на контексте seed (общий контракт
     «контекст → покрытие», тот же что state-change).
   - Claim — клетка к seed'у с лучшим `w = f(dist) + seeded-шум границы`,
     кап `max_radius`; declared/anchor выигрывают у claim через
     `placement_specificity` (autoresolve = `None`, #7) — отдельного правила нет.
   - Обход соседей seed-решётки — `topology.neighbor` (шов), не ручной `mod`.
   - `region_uid` = canonical min `seed_xy` (идиома `wrap_owner_and_other`).
   **Слияние одинаковых:** соседние seed'ы одного вида сливаются в **один
   регион**; каждый seed остаётся **саблокацией** — долей внутри региона
   («Тёмный лес» → «Северный»/«Южный»), адресуемой через `Facing`
   относительно региона; саблокация — свой uid от seed'а.
   Следствия: оценка компоненты слияния — обход seed-решётки в пределах
   `max_radius`-графа (детерминистично, граница — мир, не тайлы); при
   изменении климата слияние/распад меняет canonical owner → tombstone/
   relink uid — связь с #11.
5. L0/L2 интеграция — **проверено и решено 2026-10-16.** Текущий путь:
   `build_tile_surface_state` (`terrainBatchOrchestrator.py:150`) —
   `fine_terrain = upsample_terrain_from_parent_light` (nearest carry из
   L0-клетки) → `place_hills` → `merge_hydro_hard_corridor`. L2-покрытие
   сейчас целиком идёт через L0-контур — связка, которую разрываем.
   - **L0:** существующий пайплайн без смены роли — `run_mask_domain` +
     `LandcoverMaterializer` → `MaskFootprint` → `apply_terrain_footprint`
     → `cell.system_terrain`.
   - **L2:** `upsample_terrain_from_parent_light` деградирует до
     **policy-fallback** (фон непокрытых клеток — «state → spec →
     fallback»); затем членство региона вычисляется **поточечно в
     fine-координатах**: для declared — `RegionShape.contains(x, y)`,
     для autoresolve — та же claim-функция `w = f(dist) + seeded-шум`
     (#4) на метровых координатах. Контур чёткий в метрах, не лесенка L0.
   - **Порядок:** upsample → region paint → `place_hills` (hills видит
     корректное покрытие) → hydro merge (вода старше landcover). Одна
     точка правки — между upsample и `place_hills` в
     `build_tile_surface_state`.
   - **Шов:** членство через `topology.canonicalize` — seam-регион
     красит оба края.
6. Океаны/озёра — **решено 2026-10-16: общий wilderness-слой поверх hydro**
   (регион-сущность выше доменов; кросс-доменный переход лес→озеро требует).
   **Проверка инициализации гидрологии — выполнена 2026-10-17:**
   - Порядок `HydrologyGeneratorService.apply` (pass 1.5): coastal_sea →
     autoresolve seas → open_ocean → lakes → rivers → landforms; поздние
     генераторы получают `occupied` — приоритет sea>ocean>lake>river.
   - Роли: `is_open_water_role()` → liquid; `blocks_grade_seed()` — вода +
     river_bed блокируют grade-seeds. Озеро: `shoreline_segments` →
     кольцо → `_resolve_interior` → карвинг по дистанции + SHORE-кольцо.
   - Ravine↔вода связи нет: `apply_relief_objects_z` (pass 1.4) до hydro;
     при paint вода старше (`PRESERVE_HYDROLOGY_ROLES`). Общий слой
     порядок не трогает.
   - **Индексация безопасна:** слой читает `declared_*` + cell roles в
     region entries; владение init у hydro.
   - **Морфинг land→озеро осуществим:** `RegionShape` контур → полилиния →
     растр кольца = входная форма `generate_lakes`; карвинг/берег/bands
     переиспользуются. Шов: `HydrologyMasterInput` собирается из
     `declared_*` — нужен путь «region shape → lake-like input»
     (hydro-эффект по `current_type`, #11 п.3).
   - **Река ≠ площадь** (edge/intents) — морф в реку не мапится, отдельный
     контракт; море = coastline+autoresolve — тоже отдельно.
7. Wire-детали и worldEdit — **частично решено 2026-10-16.**
   **Пересечения (решено):**
   - Overlap declared-регионов **разрешён** (авторское слоение — лесная
     опушка внутри равнин); не ошибка валидации.
   - Конфликт на клетке — цепочка (решено 2026-10-17, вариант B):
     ```text
     1. merge_rank(current_type)   ↓   # разные ключи (TerrainRegistryEntry)
     2. placement_specificity      ↓   # равный rank; None — ниже любого явного (в т.ч. 0)
     3. RegionShape.area()         ↓   # без edge_noise — геометрический примитив
     4. region_uid                 ↑   # канонич. строка
     ```
     Это § Placement priority, применённый **на клетке после rank**:
     landcover-регионы не сдвигаются и не обрезаются (overlap = покрытие),
     specificity решает только цвет клетки. Отдельного поля `priority` нет.
     Одна функция сравнения (шаг 2b) для L0 `apply` и L2 paint.
   - `placement_specificity: int | None`, `ge=0`, без верхней границы.
     Autoresolve-регионы и их саблокации — `None` (ниже любого declared);
     саблокации наследуют specificity родителя; child-регион частичного
     перехода (#11) выигрывает у родителя рангом ключа, при равном ранге
     получает specificity родителя + 1 при создании.
   - Равный ранг + разные ключи — исход по п.2–4 + WarningError в лог
     (выбор непрозрачен → видим).
   - Один ключ + два declared — оба региона живут (uid/name свои, не
     сливаются в отличие от autoresolve); клетка в обоих footprint —
     ок, state у региона; факты клетки для state-контекста входят в
     оба региона (деталь для #11 — частичные переходы).
   - Declared/anchor выигрывают у autoresolve-claim через specificity
     `None` (#4) — не отдельное правило.
   - **Шум границ (решено):** граница пересечений/соседних регионов —
     не прямая линия; клетки «входят» друг в друга через seeded-шум
     (`seeded_u01(seed_root(world), REGION, channel="claim", seed_xy=seed_xy, x=x, y=y)` —
     детерминистичен по uid мира).
     Шум ограничен приграничной зоной (decay от геометрического края) —
     `merge_rank`-иерархия глобально не нарушается.
   **Shape-примитивы (решено 2026-10-16).** `RegionShape` — discriminated
   union по `kind`; координаты в мировой fine-сетке (unrolled), при
   растеризации канонизируются через `topology.canonicalize`:
   ```python
   class RegionShapeBase(BaseModel):
       kind: Literal[...]
       edge_noise: EdgeNoise | None = None   # общий knob, ниже

   class BboxShape(RegionShapeBase):      kind="bbox"
       x_min: int; y_min: int; x_max: int; y_max: int
   class EllipseShape(RegionShapeBase):   kind="ellipse"
       cx: int; cy: int; rx: int; ry: int            # rx,ry > 0
   class PolygonShape(RegionShapeBase):   kind="polygon"
       vertices: list[tuple[int, int]]               # >= 3, замкнутый
   class AnchorRadiusShape(RegionShapeBase): kind="anchor_radius"
       anchor_uid: str; radius: int                  # круг от якоря

   class EdgeNoise(BaseModel):
       amplitude: int   # амплитуда смещения края (fine-координаты)
       scale: int       # пространственный масштаб шума
   ```
   - Мемберство — `contains(x, y)` поточечно: геометрический предикат +
     смещение края от `edge_noise`; шум seeded по **uid региона**
     (`seed_rng(seed_root(world), UidKind.REGION, channel="edge",
     uid=region_uid, x=x, y=y)` — канал из таблицы #4) — когерентен вдоль
     края и уникален на регион. (Шум **разбиения** overlap-зоны между
     регионами — отдельно, `channel="claim"` по координатам клетки — см.
     пересечения выше.)
   - `area()` у любой формы — площадь геометрического примитива без
     edge_noise (`anchor_radius` → `π·r²`, резолв якоря не нужен) — для
     tie-break п.3.
   - `AnchorRadiusShape` — резолвит позицию именованного anchor при
     materialize; unresolvable anchor → ошибка author-валидации /
     WarningError runtime (паттерн #1).
   - Валидация author-side: `rx/ry > 0`, `vertices >= 3`,
     не-самопересекающийся polygon, bbox `x_min <= x_max` — ошибки
     валидации (не fallback).
   - `bbox()` у любой формы — для spatial index / отбора при bake.
   **worldEdit (решено 2026-10-16):**
   - Операции: `add` / `remove` / `update` региона целиком — элемент
     `declared_regions[]`, keyed by `name` (identity по #1); полевой
     patch (move/resize shape) = update элемента.
   - `remove` declared → `RegionState` в `region_states` получает
     **tombstone** + чистка при следующем чтении/bake («удалил —
     значит удалил», state не воскресает молча).
   - Draft-валидация: `name` обязателен (#1 — draft = ошибка, runtime
     = fallback + warning); uid-коллизия двух declared с одним именем —
     ошибка валидации.
   **#7 закрыт.**
8. Хранение — **решено 2026-10-16.**
   - **Resolved Specs — derive-on-read, не персистить.** `run_mask_domain`
     пересобирает на каждый bake из world data (declared из wire,
     autoresolve детерминистично по seed-решётке #4; горы/ravines — тот
     же паттерн). Персистированные Specs = второй SoT + sync-проблема.
   - **Manifest `wilderness_region_entries[]` — индекс, не SoT** (по
     образцу `location_terrain_entries`): `{region_uid, entry_type,
     current_type, bbox, status, parent_region_uid?, spec_fingerprint?}`
     — spatial lookup для bake/debug/API; переписывается при bake
     (`current_type` — snapshot на момент bake, актуальное — store).
   - **`RegionState` — SQL-таблица `region_states`, keyed by `region_uid`**
     (уточнено 2026-10-17; ранее «patch-слой WP-20» — неверно: WP-20 =
     `map_cell_patches` per-cell `(x,y,z)`, entity-state туда не ложится).
     Entity-store рядом с Patch Store, `0001_initial.sql` + dataclass +
     repo; runtime-мутация поверх authored declaration; поля: `current_type`,
     `pending_target`, `progress`, `last_eval_tick`, `overrides` (JSON),
     `history` (JSON append-only), `spec_fingerprint`, `tombstone`.
     Запись — только `StateChangeConsumer` (single-writer); массово — `bulkSql`.
   - **Путь до клеток — membership в pack + overlay по uid (вариант iv,
     решено 2026-10-17).** При bake клетка получает `system_terrain`
     (paint на момент bake — snapshot самодостаточен для raw-читателей)
     **и** `region_uid` победителя (optional поле `WorldMapCellWire` /
     `FineTerrainColumnWire`). Read path — **один фасад** overlay: есть
     `region_uid` и `state.current_type ≠ baked` → ключ подменяется;
     `tombstone` → policy-fallback ключ. Применяется ко всем слоям WP-20
     **ниже `patch`** (`terrain_delta` от взрыва остаётся кратером).
     Отвергнуто: re-bake тайлов (мастерский рычаг WP-7, симуляция
     невидима), flood `terrain_delta` (10⁶ строк на регион, WP-FIX-DEBT-1),
     геометрия на read (дублирует bake-paint, raw-читатели видят fallback).
     Overlay — только `system_terrain`; доменные эффекты морфинга (роль
     воды, bed carve) — на materialize/refine (#11). Известный gap —
     overlap re-rank (см. §4).
   - **Revision-check — `state_fingerprint(spec_wire)`** в `region_states`
     (и опционально в manifest-записи): при bake/refine тайла mismatch →
     клетки региона **в этом тайле** перекрашиваются (не немедленно по
     всему миру). Отдельно от `registry_hash` (версия реестра мира).
   - **Orphan-state:** declared удалён → uid не выводится → patch-state
     сиротеет; политика tombstone/hold — вместе с worldEdit (#7 остаток).
9. Поля Spec и состав леса — **решено 2026-10-16.**
   - `ForestSpec` — прямое пересечение с flora-доменом: вся флора
     (состав, виды, жизненный цикл) описывается там. **Решено 2026-10-17:
     поле `flora` НЕ вводится** (ранее — заглушка `FloraSpec | None`):
     `FloraSpec` нет ни в коде, ни в `tz_flora.md`; пустой POJO чужого
     домена = мёртвый код (`dataModel-no-hardcode`), `flora: {}` — тихий
     no-op. Точка расширения записана в ТЗ регионов (› Точки расширения)
     и в backlog `tz_flora.md`; до неё ключ `flora` в wire — unknown key
     (`json-validation-unknown-keys`). `flora.*` канал eligibility
     (`RegionFacts.flora = None`) — это fact-консьюмер, не wire-поле;
     остаётся.
   - `PlainSpec` — без доп-полей (минимум).
   - `FarmlandSpec` — та же судьба: `crop` **не вводится** до
     `crops_registry` в dataModel (сейчас была бы строка без membership).
     Union всё равно полный (forest/plains/farmland, #2); knobs farmland
     появятся с реестром культур.
   - `density: float = 1.0` — общий knob заполнения: paint =
     `contains(x,y)` AND density-маска (`seeded_u01(seed_root(world), REGION,
     channel="density", uid=…, x=x, y=y) < density`) — органичные пропуски,
     детерминистично; канал отличен от edge-шума (#4).
     Достаточно для coverage-контракта: «чаща»/кластерность/возраст —
     семантика флоры (тот же канал в сторону flora), не declaration.
   - Hills-политика остаётся в `default_forests`/`default_plains`
     (transitional), не в Spec.
   - Interim eligibility для autoresolve: climate-профиль (rainfall/
     temperature) на контексте — до флоры; suitability index flora —
     отдельный трек, тот же consumer-интерфейс.
10. Topology поверхности — **решено 2026-10-16: отдельный план
    [surface-topology.md](./surface-topology.md)** по аналогии с выделением
    `deep-layer-topology.md` (отдельный трек в `plan-dependency-graph.md`).
    §0 этого плана — контракт-зависимость; delivery plan wilderness не
    включает этапы topology.
11. Переход типов footprint (направление решено 2026-10-16): промежуточный
    terrain-ключ (`dead_forest` и т.п.) **не вводится**. Вместо него — **критерии
    перехода одного типа footprint на другой**: лес → равнина, лес → озеро при
    изменении климата/гидрологии и т.д. Форма механизма (предложение разработчика):
    **отдельный state-change consumer** — единая точка изменения состояния
    региона, принимает доменные консьюмеры и их данные (climate, hydrology,
    flora и др.) и переводит footprint в корректное состояние. Целевой тип
    **выводится из агрегированного контекста**: домены поставляют факты,
    consumer из совокупности фактов выводит, какое покрытие соответствует
    области — целевой тип не назначается доменом и не зашивается в таблицу
    пар «тип A → тип B». Тот же принцип, что вычисление покрытия из условий
    мира, применённый к существующему региону. По образцу
    contributor/materializer каркаса: registry + runner; домены сами чужой
    footprint не переписывают (single-writer на состояние). Не генератор и не
    persist — сервис состояния.
    Примеры (разработчик, 2026-10-16): осадки в лесу исчезли → лес на равнине
    вымирает **со временем** → переход в степь; осадков стало больше →
    в низинах внутри региона появляются болота + лес становится чащей.
    Следствия: переход — темпоральный процесс (накопленное состояние/
    прогресс, не мгновенный гейт); целью может быть **часть** footprint
    (низины → болото) — контекст включает пространственное распределение
    внутри региона (рельеф/низины), не только region-level факты;
    результатом может быть изменение интенсивности/параметров (чаща), а не
    только смена типа; целевые типы — N+1 ключи `WorldTerrainRegistry` мира
    (степь, болото), не `MaskDomainId`; красящий ключ региона берётся из
    состояния, связка «домен → ключ 1:1» разрывается (см. §1 таблицу
    engine/N+1).
    **Решено 2026-10-16:**
    - **Вход — typed facts per domain** (не dict): `RegionFacts{climate,
      hydrology, relief, flora?, declaration, elapsed_ticks}` — агрегат
      контекста; реестр `factConsumers`, отсутствующий домен → `None`.
    - **Вывод типа — scorer, не таблица A→B.** `EligibilityRule` —
      метаданные `TerrainRegistryEntry` (target): `{fact, op(gte/lte/
      in_range/flag), lo/hi, weight, required}`. `resolve(context)`:
      required-правило провалено → кандидат отпадает; иначе
      `score = Σ weightᵢ·satisfactionᵢ` (0..1: in_range — falloff,
      gte/lte — нормированное превышение, flag — 0/1); `target =
      argmax`, `strength` → темп прогресса. Все кандидаты отпали →
      WarningError, тип не меняется (no hidden defaults). Interim:
      hardcoded climate-правила в engine с явным комментарием «цель —
      rules на TerrainRegistryEntry + flora suitability как канал
      `flora.*`».
    - **Две гранулярности resolver:** region-level (агрегат по footprint
      — смена типа целиком) и cell-level (распределение внутри —
      частичный переход).
    - **Морфинг, не tombstone:** кросс-доменный переход (лес→озеро) —
      `current_type` меняется, та же сущность, тот же `region_uid`.
      Эффекты на клетках (hydrology_role SEA/LAKE/RIVER, bed carve) —
      метаданные рода ключа на `TerrainRegistryEntry` + доменный
      apply-path на materialize; домен владеет эффектом, не сущностью.
      **Уточнение 2026-10-17:** overlay на read (#8) подменяет только
      `system_terrain` — `current_type=lake` виден сразу; физика воды
      (роль, z) появляется при ближайшем refine чанков / re-bake тайла
      (очередь WP-12/13), не на read. `place_hills` видит landcover на
      момент build чанка; лес умер позже → холмы остаются (рельеф ≠
      покрытие — приемлемо, зафиксировано).
    - **Прогресс — накопление с гистерезисом:**
      `RegionState{current_type, pending_target, progress,
      last_eval_tick, overrides, history[], spec_fingerprint, tombstone}`
      в `region_states` (#8).
      target==current → progress затухает; target!=current →
      pending_target + `progress += strength·elapsed`; смена target →
      reset; порог → `current_type=target` + событие в лог.
      **`elapsed_ticks` — заглушка-параметр** (домен времени не
      реализован): рабочий параметр, используется в тестах; при
      имплементации — явный комментарий «переработать при появлении
      домена времени».
    - **Частичный переход — child region (саблокация #4):** низины внутри
      леса → болото = саблокация со своим uid (seed lowland-кластера) и
      `current_type`, paint внутри своего footprint перебивает родителя
      (merge_rank). Родитель держит тип снаружи. Фрагментация не нужна.
      Изменение интенсивности без смены типа («чаща») —
      `overrides.density` на `RegionState`.
    - **Transit:** регионы — покрытие, не закрытые локации; граница
      саблокации — линия смены `paint_key`, вход свободный по периметру,
      события перехода не нужно. Закрытая локация поверх региона —
      домен locations, отдельный трек.
    - **Declaration — факт с весом, не пружина:** `DeclarationFacts`
      (present/strength) в контексте → declared инертнее autoresolve;
      обратный переход выводится resolver'ом заново (может дать не
      declared-тип).
    - **Пороги/темп — гибрид (решено 2026-10-17):** `inertia: float = 1.0`
      на `TerrainRegistryEntry` (сопротивление ключа как текущего типа);
      глобальный `transition_threshold` в engine-policy; темп =
      `strength × elapsed / inertia(current)`; `DeclarationFacts.strength`
      добавляется к effective inertia.
    - **Триггер оценки — отложено в унифицированный LOD-трек (2026-10-17):**
      нужна единая механика LOD/синхронизации времени для механик —
      отдельная работа (как surface-topology). До неё `elapsed_ticks`
      остаётся рабочей заглушкой-параметром (тесты передают явно);
      при имплементации — комментарий «заменить при появлении домена
      времени/LOD».
    - **История `current_type` (решено 2026-10-17):** `RegionState`
      хранит append-only `history[]` переходов `{from_type, to_type,
      cause, at}` — uid один, локация одна, эволюция не теряется
      (лес→мёртвый лес→болото). `cause` — сводка фактов или ссылка на
      событие; `at` — время-заглушка. Связь с событиями («лес подожгли»
      — резкое изменение) и временем («вымер со временем») — потом, при
      доменах времени/событий; при имплементации — комментарий-заглушка.
    - **Declared edit → reset (детализация 2026-10-17):** тот же uid +
      тот же `entry_type` → `current_type` сохраняется, `progress`/
      `pending_target` reset; `entry_type` изменён → `current_type`
      сбрасывается к новому `entry_type` (+ запись в `history` с
      cause=declared_edit); rename → новая сущность, старый state →
      orphan → tombstone (#7).
    - **uid при смене типа — сохраняется** (тип не в uid, #1); меняется
      при: rename declared, merge/split autoresolve (canonical min-seed,
      #4) → tombstone/relink.


**Детализация шага 4 (2026-10-17):** `regionRasterizer.py` использует typed-входы
`regionRasterContext.py` (`RegionRasterContext`, `ClaimSeed`, `RegionClaim`) и
чистые функции `regionRasterNoise.py` для когерентного шума и decay от края.
Контекст содержит resolved macro-topology и `LightGridScale`; fine-extent
выводится из них. L0 семплирует центры клеток тем же предикатом, что L2.
Claim принимает готовые seeds, `max_radius` и `EdgeNoise` без policy-defaults:
`dist` — кратчайшее число шагов fine-графа `topology.neighbor`,
`f(dist)=max_radius-dist`; отрицательный итоговый вес не красит клетку,
кап радиуса жёсткий. `scope` фильтрует только результат, а не конкурентов
или обход. По явному ответу мастера claim-RNG дополнен ключом `seed_xy`:
общий шум по `(x,y)` сократился бы при сравнении и не искривлял бы границу.
Шум интерполируется на решётке с шагом `scale`; density остаётся поточечной
seeded-маской. Seed generation/merge и потребители не входят в этот шаг.
Шаг не отмечается выполненным до приёмки.

**Уточнение границы 5b (согласовано мастером 2026-10-17):** добавить
`MaskDomainId.LANDCOVER` и typed `LandcoverRegionsCategoryPolicy` в dataModel;
state lookup получает явно подготовленный read-only snapshot (пустой snapshot
должен быть передан явно), repo создаётся шагом 9a. `region_uid` winner
доступен в materializer, но persist membership и manifest остаются шагам 6/8.
До согласования canonical чисел seed_spacing/max_radius/claim_noise эти
параметры обязательны; скрытых application-defaults нет. Дополнительные
модули 5b: `types.py`, `apply.py`, `hydrologyIndex.py` в пакете landcover.
Для graph-claim `RegionCandidate.claim_area` передаёт площадь исходного
поля (объединение единичных fine-квадратов), до density/L0 sampling/scope;
`shape` auto-региона — только envelope, его bbox-area не участвует в tie-break.
Общий алгоритм `regionPrecedence` сохраняется; `claim_owners` rasterizer
открыт как чистый API для площади того же поля без второго алгоритма claim.

**Уточнение шага 5a (по указанию мастера, 2026-10-17):** операции
`EligibilityRule.op` задаются `EligibilityOp(StrEnum)` в
`dm/terrain/enums/eligibilityOp.py`: `GTE`, `LTE`, `IN_RANGE`, `FLAG`.
Модель использует `StrictEnumOnWire[EligibilityOp]`; валидатор,
canonical registry и resolver используют члены enum. Wire-значения
`gte/lte/in_range/flag` сохраняются; проверка — round-trip всех операций,
отказ неизвестной операции и существующие тесты scorer/реестра.

### Уточнение шага 7b (согласовано 2026-10-17)

`terrain_category` сохраняет физический смысл. На TerrainRegistryEntry вводятся `supports_open_land_grade: bool = False` и `open_land_profile: Literal["plains", "forest"] | None = None`. При включённом допуске профиль обязателен; при выключенном отсутствует. Canonical plains/forest сохраняют допуск и собственный профиль, остальные builtin — выключены. Допуск независим от hills. Профиль применяется в discover (envelope) и pick (envelope + template condition); фактический terrain и идентичность grade не переписываются. N+1 steppe явно задаёт допуск, профиль plains и hills. Приёмка включает отсутствие профиля, hills=None, выключенный допуск, неизменность builtin. Дополнительные файлы: terrainRegistryEntry.py, worldTerrainRegistry.py, jsonValidation/terrainHillRegistry.py, relief/sample/terrainMap.py, relief/discover/{core,fronts}.py, detailedGrade{Discover,FrontPick}.py и профильные тесты. Transitional hills применяются к builtin из default_* только при отсутствии явно заданного hills (включая null) на записи реестра. SQL не меняется. Шаг не отмечать выполненным до приёмки.

Проверка реализации 7b: 177 профильных unittest + 9 parent-light; compileall app и git diff --check чистые. Сравнение с прежним place_hills из HEAD: 60 сценариев (12 seeds × 5 палитр), полное равенство высот plains/forest. Smoke steppe: fine region paint через typed state snapshot (reader до 9a остаётся stub) → hills → discover/pick → grade instances; выключенный допуск даёт отсутствие grade. Готов к приёмке, не помечен выполненным.

### Уточнение приёмки шага 8 (согласовано 2026-10-18)

Индекс строится из результатов существующего collect, не создаёт новые источники регионов. Отсутствие anchor-регионов в конкретном мире допустимо; все статусы поддерживаются моделью/адаптером и проверяются на явно подготовленных входах. Требования всех четырёх статусов в одном bake world-test-002 в строке 8 нет. Правило NamedLocation → landcover Spec и создание NamedLocation не добавляются. Hydro-индекс без достоверных UID/type/геометрии не превращается в выдуманные coverage entries. Manifest — snapshot/debug index, не хранилище Specs.

Карта шага 8: dm/worldPack/meta/wildernessRegionEntry.py (status + fine bbox + snapshot entry), worldPackManifest.py (список/accessor); wd/pack/bake/wildernessRegionIndex.py (чистый адаптер collect), LightGridBakeContext/ LandcoverContributor/WorldMapBakeOrchestrator (передача результата в writer); pack/io/worldPackWriter.py (замена индекса); pack/read/wildernessRegionReadService.py (селектор snapshot); render/regions/regionOutline.py (контур из повторного collect/rasterize, не из manifest Spec); api/routes/map.py (thin GET /worlds/{world_uid}/map/regions/{region_uid}, GET .../{region_uid}/outline). Outline использует существующий ASCII kernel. Полный/частичный L0 bake переписывает world-scoped индекс из одного collect, UID и bbox не зависят от tile scope. Приёмка: round-trip manifest, replacement/removal, все статусы, parent, детерминизм, seam, selector 404/snapshot, outline; smoke fixture без старта сервера. Отметка выполнен — после приёмки.

### Инвариант UID шага 8 (указание мастера 2026-10-18)

Регион и каждая саблокация — разные сущности с уникальными UID. Для autoresolve-агрегата центральная region_uid получает отдельный источник region_seed_xy=canonical min seed; seed-саблокации сохраняют seed_xy. UID родителя не включается в UID саблокации, чтобы merge/split не менял идентичность seed-доли. UID агрегата в прежних baked клетках меняется после re-bake; миграция состояния не добавляется (store — шаг 9a). Разные источники имеют разные канонические ключи DET-1; collect проверяет уникальность ВСЕХ uid до paint. Manifest/его writer проверяют дубликаты, self-parent и ссылочную целостность до замены индекса. Коллизия — отказ операции с диагностикой; никакой случайной пересолки или молчаливой перезаписи. SQL не меняется. Дополнительные файлы шага: ids/regionIdentity.py, landcover/autoresolve/mergeSublocations.py, тесты identity/collect.

Реализация шага 8 готова к приёмке (2026-10-18), не отмечена выполненной. UID источников разделены через region_seed_xy/seed_xy; collect отклоняет коллизии до paint, auto merge использует seed-набор, а не UID (коллизия не скрывается дедупликацией). Индекс из collect → bake context → world-map writer manifest; отдельный io/wildernessRegionIndexWriter.py не расширяет большой WorldPackWriter. PackManifestStore перевалидирует изменяемые коллекции перед атомарной публикацией. Селектор возвращает явный snapshot; outline выводится из повторного collect/rasterize. Source entry_type сохраняется до state override. Fine bbox seam-aware и консервативен; manifest не хранит Specs. Hydro-индекс остаётся вне coverage manifest: текущие наблюдения не имеют полного UID/type/геометрии. Канонические числа генерации не вводились.

Проверки: 140 тестов UID/collect/index/paint/read + 17 тестов общего pack writer/reader/wire; compileall app, git diff --check. Smoke на world data fixtures/world_test_002.json: bounded L0 tiles, явно добавленный authored-регион (в исходном fixture declared_regions нет), production world-map orchestrator + LANDCOVER, запись/чтение pack, HTTP-селектор/outline/404/409 через TestClient без старта backend. Прочие contributors опущены в этом узком smoke; полный серверный bake fixture не запускался. Все четыре статуса, anchor input, уникальность, parent, partial/full, forced collision, сохранность старого manifest, merge/split seed UID проверены отдельно. SQL/DAG/коммитов нет.

### Техдолг WR-TD-1 — типизированные ссылки покрытия в resolved/manifest (2026-10-18)

**Статус: исправление реализовано, готово к приёмке (2026-10-18).**

**Проблема:** `ResolvedRegion.entry_type: str | None = None`, `ResolvedRegion.current_type: str`, `StateSnapshotEntry.current_type: str` и строковые `WildernessRegionEntry.entry_type/current_type` теряют типизированную связь с `WorldTerrainRegistry`. `CoverageResolver.TargetCoverage.target_key` уже имеет тип `TerrainKey`, но дальше контракт ослаблен. Collect проверяет membership только `current_type`; индекс проверяет лишь наличие `entry_type`, не принадлежность исходного ключа реестру. Некорректный caller может передать произвольный исходный ключ.

**Смысл полей:** в authored Spec `entry_type` остаётся discriminator закрытого union (существующие Literal forest/plains/farmland). В resolved/manifest `entry_type` — исходное покрытие из декларации либо первоначальный результат autoresolve; `current_type` — текущее покрытие. На этих уровнях оба значения — ключи terrain-реестра, включая N+1. Отдельный реестр типов регионов и новые поля для разведения этих понятий не требуются.

**ТЗ:** `docs/tz_json_validation.md` § RegistryKey[R] (N1-W identity); `docs/tz_map_light_bake.md` § Регионы покрытия › Spec union / Реестр и CoverageResolver; `docs/tz_world_pack_storage.md` § WildernessRegionEntry.

**Цель исправления:** использовать существующий `TerrainKey = RegistryKey[WorldTerrainRegistry]` для resolved/snapshot/manifest-полей покрытия; сделать `ResolvedRegion.entry_type` обязательным. Обеспечить проверку обоих ключей по разрешённому реестру конкретного мира на границе формирования resolved-региона/индекса. Обычная аннотация dataclass не обеспечивает runtime-валидацию; RegistryKey выражает принадлежность к реестру, но сам по себе не проверяет membership. Использовать существующую политику resolver/REF-W, без скрытого fallback и новых параллельных механизмов. При чтении исторического manifest сохранить snapshot-семантику: не подменять baked значения текущим состоянием и не выдавать их за live state.

**Файлы:** `wd/generators/terrain/landcover/{types,materializer,collect}.py`, `landcover/autoresolve/claim.py`, `dm/worldPack/meta/wildernessRegionEntry.py`, `wd/pack/bake/wildernessRegionIndex.py`, профильные тесты; дополнительные точки — только по результатам проверки существующих RegistryKey/REF-W consumers.

**Приёмка:** допустимые N+1 исходный/текущий ключи проходят round-trip; пропущенный/None исходный ключ не создаёт resolved-регион; неизвестный исходный или текущий ключ диагностируется на world-aware границе и не попадает в новый индекс; state override не меняет исходный ключ; authored union сохраняет закрытый discriminator; исторический manifest остаётся явно snapshot. Compileall и профильная регрессия.

Уточнение реализации WR-TD-1: ResolvedRegion и StateSnapshotEntry — frozen Pydantic dataclass с runtime-валидацией TerrainKey; entry_type обязателен как keyword-only поле, чтобы не менять смысл существующих positional-вызовов. Перед collect/index используется TypeAdapter с revalidate_instances и существующий validate_reference_value/WorldRegistryIndex по уже разрешённому terrain_registry; диагностика — общий reject_unresolved. Collect сохраняет отказ зависимого региона с WarningError, прямое построение индекса отклоняет операцию до публикации. Новый параметр build_region_index(..., registry=...) обязателен. Historical manifest не получает world-aware проверку при read. Дополнительный модуль: landcover/regionCoverageValidation.py; тесты test_region_coverage_contract.py.

Проверка WR-TD-1: 164 профильных теста UID/collect/index/L0/L2/pack I/O прошли, включая 7 новых проверок контракта. Подтверждены обязательность/non-null entry_type, runtime-branding TerrainKey, membership обоих ключей с REF_W_UNKNOWN, отсутствие публикации некорректного индекса, state override без изменения исходного типа, revalidation некорректного dataclass, N+1 round-trip и historical snapshot без live-membership. Compileall app и git diff --check чистые. Сервер не запускался; коммитов нет. Общий шаг 8 по-прежнему не помечен выполненным до приёмки мастером.


### Уточнение контракта shape_kind (2026-10-18)

По указанию мастера shape_kind должен ожидать корректный тип. Цель: единый RegionShapeKind (StrEnum) в dataModel/spatial/regionShape.py, используемый в Literal-discriminator моделей форм и в аннотации region_uid. None остаётся для остальных источников identity; bbox_min требует экземпляр enum, anchor_radius использует anchor_uid. Runtime отвергает произвольную строку и anchor_radius в bbox-ветке. Отложенный импорт enum внутри ids нужен из-за обратной зависимости dataModel → app.ids при инициализации пакетов. ТЗ: docs/tz_map_light_bake.md, раздел degraded identity bbox_min + shape_kind=<shape.kind>; строковые wire-значения и DET-1 UID сохраняются. Файлы: regionShape.py, ids/regionIdentity.py, tests/test_region_identity.py. Проверка: модели/discriminator JSON round-trip, прежняя формула UID, отказ некорректного типа/ветки, профильная регрессия и compileall. Done: тип един для модели и UID, проверяется при вызове.

Реализовано, готово к приёмке: shape_kind: RegionShapeKind | None; модели форм возвращают тот же enum. Прямой вызов со строкой (включая валидный wire-токен) отклоняется TypeError; anchor_radius с bbox_min — ValueError. 108 профильных тестов прошли, включая 3 новых теста типа/JSON/сохранности UID; compileall app и git diff --check чистые.


### Реализация 10a — готова к приёмке, не отметка «выполнен» (2026-10-18)

`regions/stateChange/` содержит `consumer.py`, `progress.py`, `history.py`,
`morphEffects.py`, `contracts.py`. Публичный вход — async
`StateChangeConsumer.evaluate(world_uid, RegionEvaluation) -> EvaluationResult`;
repo, WorldTerrainRegistry и LandcoverRegionsCategoryPolicy передаются явно.
Внешний caller сериализует оценки региона в своём UOW и передаёт elapsed_ticks,
at/updated_at, observation context; автоматического tick/read-триггера нет.
WorldEdit wiring остаётся 10c, LOD/время — отдельному треку.

Progress использует общий scorer и effective inertia `current.inertia +
declaration.strength`; policy threshold — POJO default 1.0, диапазон (0,1]
согласован с progress 0..1. Declared revision требует previous_entry_type:
форма сохраняет current и сбрасывает pending/progress, тип сбрасывает current
к entry_type с append-only history. Reset не тратит elapsed в той же оценке.
SQL audit timestamps задаёт caller, simulated time не подделывается.

SpatialEvaluation передаёт устойчивый seed lowland-кластера, resolved Spec
и context. Child UID — DET-1 с parent_region_uid и seed_xy; текущий target
не входит в identity. Родитель сохраняет тип вне child. Равный rank даёт
specificity parent+1 (None → 0). Родитель и children сохраняются одним
repo.upsert_bulk → существующий bulkSql; geometry не добавляется в SQL.
Caller повторно выводит spatial scopes и передаёт child-дескрипторы/typed
materialize signals в refine. Неполный scope не означает удаления child.
Tombstone ставится только явным методом consumer; обычная оценка не воскрешает.

Morph signals содержат Spec, прежний/новый state и registry metadata.
Optional `TerrainRegistryEntry.morph_hydrology_role` использует существующий
HydrologyCellRole; сейчас разрешён только LAKE (sea/river вне scope).
Роли воды/bed carve исполняет hydrology materializer по сигналу, не consumer
и не read. События transition/evaluation идут через regionStateLog и общий
loggingConfig; overlap_rerank_deferred остаётся только read-событием 9c.

Проверено: 114 профильных unittest (13 новых для 10a), включая consumer
с настоящим SQLite repo, child round-trip, hysteresis/strength/declaration,
declared reset, tombstone, N+1 lake morph signal; compileall app чистый.
Новый StateChangeConsumer — 112 строк, изменённые классы не превышают 300.
Async/SQLite тесты выполнены вне sandbox после диагностики зависания Windows
socketpair при создании asyncio event loop. Окружение не изменялось.
Шаг не отмечается «выполнен» до «ок» мастера.

### Реализация 10b — готова к приёмке (2026-10-18)

Замечание мастера к 10b: убрать повтор полей/конструирование rainfall rule
из application/terrainHillRegistry и key-based subsurface/magma selection
из terrainZ. Исправление этого же шага: POJO API применяет typed overrides;
canonical rainfall template переиспользуется, не копируется. Wire presence
остаётся на model-owned boundary. TerrainRegistryEntry получает typed
fill_roles (TerrainFillRole.SUBSURFACE/MAGMA) и fill_priority; column fill
выбирает доступную запись по priority, затем стабильному ключу. Canonical
plains предоставляет SUBSURFACE; отсутствие MAGMA использует SUBSURFACE,
отсутствие обеих ролей диагностируется, произвольный terrain не выбирается.
SQL не меняется: это поля JSON terrain registry. Мир и pack reader передают
готовый registry, а не списки имён кандидатов. Custom fixture явно задаёт
роли N+1 terrain; проверки покрывают N+1 selection и missing role.
Исправление реализовано: application/terrainHillRegistry — thin POJO call,
rainfall template общий с canonical registry, typed with_hills/with_eligibility
на TerrainRegistryEntry. terrainZ выбирает fill role через реестр, без
earth/magma key checks и первого ключа set. Проверено 353 регрессионных
теста + 37 pack/read/write, дополнительно 22 targeted после валидации
изменённого threshold template. Это исправление 10b, не новый шаг.

Указания мастера в этом чате: БД пуста, миры перегенерируются по новым
правилам; сохранение прежних baked-карт не требуется. Canonical knobs
фиксируются в POJO/ТЗ/плане: max_radius=2250, claim noise amplitude=125,
scale=250, threshold=1.0. seed_spacing не менять: поле остаётся обязательным
int > 0; canonical root factory задаёт 1000. Макро-масштаб — отдельное поле.
Для явного default_landcover seed_spacing по-прежнему обязателен.

Удалены отдельные mask-домены и старый climate resolver. Общий scorer
работает для background/skeleton и seed-кандидатов; entry без eligibility
не выбирается автоматическим покрытием с нулевым score. Новая policy —
единственный holder fallback/threshold/knobs и authored per-key overrides.
Legacy roots читаются на wire boundary, сериализуются только в новый root;
новые поля имеют приоритет при совместном вводе. Hills/eligibility
проецируются в registry; authored null/presence сохраняется. Legacy patch
конвертируется до merge, чтобы смена enable не стирала rainfall/hills.
Добавлены REF-W checks fallback/targets. Потребители: terrainZ x2,
landcover background/finePaint/materializer, skeleton callers, read overlay,
map occupancy и bake diagnostics. DAG/schema не затрагиваются.

Три новые fixtures: world_landcover_default/custom/mixed.json. Custom
полностью задаёт terrain_masks и custom terrain row, включая вложенные
policy/noise/hills; tests проверяют completeness и независимость от
изменения canonical defaults. Mixed проверяет наследование на уровне
полей вложенного noise. Существующие world_test_002/world_template/
world_terrain_test читаются без изменения файлов. Дополнены production
import/SQLite tests для всех трёх новых fixtures и world_test_002.

Проверено 347 тестов: landcover/state/coverage/import/SQLite/hills,
затронутые relief/read paths и logging. В двух старых MagicMock-входах
тестов detailed grade явно задан topology mode; тест чистого carry явно
выключает landcover. Production-проверки topology не ослаблены. Реальный
импорт всех трёх новых fixtures и исходного world_test_002 проходит.
compileall app чистый; наибольший изменённый application-класс — 122 строки.
Legacy mask/resolver symbols отсутствуют в backend; unrelated relief enum
PLAINS и terrain keys сохраняются. Не отметка «выполнен»; окончательный
статус — после приёмки мастером.

### Rename fingerprint (явное указание мастера, 2026-10-18)

Переименовать поле ревизии Spec из state_fingerprint в spec_fingerprint во всех region-контрактах, SQL 0001_initial.sql и row-модели, collect/snapshot/index/identity и тестах; синхронизировать ТЗ. Общая hash-утилита app.ids.state_fingerprint(value) сохраняет имя: применяется также к данным библиотек и world copy. Проверка: region/landcover/store/index и schema round-trip, compileall app, diff --check. Существующую БД не менять; schema recreate выполняет мастер по принятой политике.

Переименование реализовано: 78 профильных тестов прошли, включая schema/row round-trip и чтение старого manifest alias с сериализацией нового ключа. compileall app чистый. SQL обновлён только в 0001; существующая БД не изменялась.

### Реализация 10c — готова к приёмке (2026-10-18)

Typed операции `AddRegion`/`UpdateRegion`/`RemoveRegion` находятся в
`dm/terrainMasks/regions/edit.py`. HTTP seam —
`POST /worlds/{world_uid}/regions[?validate_only=true]`; payload, ответы и
ошибки зафиксированы в `tz_runtime_world_edit_policy` § Операции declared-регионов.
Update принимает полный элемент; rename задаётся новым region.name.
Preview проверяет результирующий мир без write-транзакции/записи.

`jsonValidation/declaredRegions.py` переиспользует существующую identity-функцию:
runtime без имени логирует degraded UID без отклонения импорта; имена/формы
проверяются существующими POJO. Коллизии UID отклоняются до записи.
WorldService вызывает `regions/declaredRegionEdit.py` для diff старой/новой
коллекции; create/import/PUT/операции используют общий путь записи мира и
состояний в одном UOW. DI передаёт editor с тем же Database и region repo.

StateChangeConsumer остаётся единственным writer. Его explicit add создаёт
чистое состояние после remove, включая уже очищенный tombstone; explicit remove
создаёт tombstone даже без прежней строки simulation state. Обычный evaluate
по-прежнему не воскрешает tombstone. Для update используется существующий
declared revision reset с elapsed_ticks=0 и previous_entry_type. Rename удаляет
старый UID и добавляет новый. Tombstone сохраняется для existing read-overlay и
исключения из collect; worldEdit не запускает bake или небезопасную очистку
строк, пока baked membership ещё ссылается на удалённую сущность.

Приёмка: 7 новых API/SQLite сценариев в `test_declared_region_edit` — missing
name preview/runtime import, одинаковые коллизии/NFC/pipe/ошибки формы,
resize/type/history/rename/remove/re-add, отсутствие записи/транзакции preview,
rollback, полный PUT, remove без state и add после cleanup. Регрессия:
117 tests region/identity/store/overlay/import/models/index/materializer/fine paint;
после расширения новых сценариев — 52 tests edit/state-change/import/cutover/contributor;
22 world-column-write и 11 world-grid-settings через discovery. Все прошли.
Asyncio/SQLite запускались вне sandbox после воспроизводимого зависания event loop;
окружение не менялось. compileall app и diff --check чистые.
Шаг не отмечен «выполнен» до «ок» мастера; SQL/DAG не менялись, backend не запускался.
