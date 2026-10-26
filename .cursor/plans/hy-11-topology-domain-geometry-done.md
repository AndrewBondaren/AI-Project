# HY-11 — топология как домен геометрии: hydrology на `WorldTopology` — done

**Долг:** HY-11 (high) в [`docs/tz_generator_technical_debt.md`](../../docs/tz_generator_technical_debt.md).
**Родительский трек:** [TOPO-1](topo-1-domain-consumers.md) — топология как домен, карта консьюмеров, очередь (этот план = домен-сервисы + гидрология-консьюмер).
**ТЗ:** [`tz_terrain_generation.md`](../../docs/tz_terrain_generation.md) § Форма мира / `world_topology_mode`; [`tz_terrain_hydrology.md`](../../docs/tz_terrain_hydrology.md) § SeaBasinGenerator (HY-6 water-side); [`tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) § Шов мира L0.
**Принцип (мастер):** топология — **домен, владеющий геометрией мира и поведением на швах**. Потребители вызывают сервисы домена; сырые `neighbors4`/евклид/«край = void» вне домена запрещены. Уже зафиксировано в ТЗ: «потребители не ветвятся по mode и не вычисляют собственный wrap».

## Проблема

Hydrology — единственный домен, который реализует собственную planar-смежность (16 мест `neighbors4`, `compute_land_centroid`, `distance_and_projection`, `rasterize_segments`, `_autoresolve_from_map_boundary`) в `wrapped`-мире (default). Море через шов невозможно; центроид/метрика на шве неверны. Маски/landcover/seam/halo уже ходят через `WorldTopology` — гидрология обходит контракт.

## Целевая архитектура

### Сервисы домена топологии

| Сервис | Семантика | Статус |
|---|---|---|
| `topology.neighbor(x, y, facing)` | `NeighborResult{coord, edge_crossing, invert_dy}` | есть |
| `topology.canonicalize(x, y)` | unrolled → каноническая координата / `None` (planar) | есть |
| `topology.seam_pairs()` | seam-пары для bake | есть |
| `unrolled_images(cell)` | образы клетки в периодическом tiling (wrapped: ±w,±h; sphere: + fold-образы с `invert_dy`); planar: единственный образ | ✅ HY-11 |
| `dist2(p, q)` / `nearest_on_segment(p, a, b)` | min евклидова по образам — wrapped-метрика | ✅ HY-11 |
| `centroid(cells, weights, anchor)` | unwrap каждой клетки к ближайшему образу anchor, взвешенное среднее | ✅ HY-11 |
| `rasterize` через шов | rasterize в unrolled → `canonicalize` каждой клетки | ✅ шаг 3b |

`fine_topology(topology, tile_macro)` — переехать из `masks/regionRasterContext.py` в домен (re-export на старом месте до миграции импортов).

**Размещение — доменный корень.** Топология — контракт поверхности мира, не pack wire-формат: `worldPack/wire/` сейчас держит её случайно. По repo-конвенции «один домен = один корень» целевой дом — `dataModel/topology/`:

```
dataModel/topology/
  worldTopology.py         # WorldTopology — политика + lookup (переезд из wire/)
  worldBounds.py           # extent + координатная арифметика (переезд из wire/)
  enums/worldTopologyMode.py
  topologyGeometry.py      # unrolled_images, dist2, nearest_on_segment, centroid (новое)
```

`dataModel/spatial/` остаётся примитивами (`Facing`, `RegionShape`); `world_topology_mode` — authored-скаляр в `WorldTerrainScalars` (не доменный объект). `fine_topology` — переезд из `masks/regionRasterContext.py` в домен (re-export на старом месте до миграции импортов).

### Модель для потребителей

**Unrolled compute + canonical write** (как `regionRasterizer`): flood/геометрия считает на unrolled-координатах; в grid пишется по `canonicalize`. `passable(c) = canonicalize(c) ∈ heightmap` — planar получает `None` → void бесплатно. `n(K)`/dot/проекция в unrolled-кадре — корректны и на шве, т.к. метрика уже топологична.

### Семантика шва для воды

- `wrapped`/`sphere`: водная сторона за краем bounds продолжается на противоположной стороне — «море за краем» **существует** (противопоставление HY-6 «вода только в bounds» — уточняется: только в bounds после unwrap, но flood идёт через шов).
- `planar`: как сейчас — void, warning `water_dist=0`.
- `n(K)` на сегменте, пересекающем шов: шаг вычисляется в unrolled-кадре сегмента; определить в ТЗ.

## Шаги

### Шаг 1 — ТЗ: домен владеет геометрией

| Поле | Содержание |
|---|---|
| Цель | зафиксировать сервисы домена + запрет сырой смежности вне него |
| ТЗ | `tz_terrain_generation.md` § Топология поверхности — таблица сервисов (neighbor/canonicalize/seam_pairs + unrolled_images/метрика/centroid/rasterize), «unrolled compute + canonical write», запрет raw adjacency вне домена; `tz_terrain_hydrology.md` § SeaBasinGenerator — правка «вода только в bounds» → «через шов» + `n(K)` на шве |
| Файлы | `docs/tz_terrain_generation.md`, `docs/tz_terrain_hydrology.md` |
| Контракт | таблица сервисов домена (выше) — имена/семантика сервисов до кода |
| Проверка | согласовано с мастером |
| Done | разделы обновлены |

### Шаг 2a — доменный корень

| Поле | Содержание |
|---|---|
| Цель | топология — свой домен в `dataModel/`, не pack wire |
| ТЗ | § Топология поверхности (шаг 1) |
| Файлы | move `wire/worldTopology.py`, `wire/worldBounds.py`, `wire/worldTopologyMode.py` → `dataModel/topology/`; импорты ~11 консьюмеров; `fine_topology` → домен (re-export в `regionRasterContext`) |
| Контракт | без изменений API — только пути |
| Проверка | `compileall`, `python -m unittest` затронутых сьютов; `git diff --check` |
| Done | импортёров `worldPack.wire.worldTopology` не осталось |

### Шаг 2b — topology domain services

| Поле | Содержание |
|---|---|
| Цель | домен отдаёт метрику/центроид/rasterize для всех режимов |
| ТЗ | § Топология поверхности (шаг 1) |
| Файлы | new `dataModel/topology/topologyGeometry.py` (`unrolled_images`, `dist2`, `nearest_on_segment`, `centroid`, `neighbors4_unrolled`); tests `test_topology_unrolled_geometry.py` |
| Контракт | pure функции от `WorldTopology` (координатная арифметика — wire-слой домена); `passable`/membership — в консьюмере (application); planar — degenerate (один образ, `canonicalize`→None за bounds); sphere — fold-образы с `invert_dy` |
| Проверка | `python -m unittest backend.tests.test_topology_unrolled_geometry`: wrapped dist через шов < прямого, sphere fold-сдвиг `w/2`, centroid через шов, planar void |
| Done | сервисы + тесты зелёные |

### Шаг 3a — flood-ядро → домен

**Уточнение по инвентаризации кода (2026-10-20):** удаляемый
`deepeningBandCarver._neighbors4` импортируют также `basins/lakeBasinGenerator.py`
и `autoresolve/proceduralLakeAutoresolve.py`. В шаге 3a эти импорты/вызовы
механически заменяются на доменный `neighbors4_unrolled`, без изменения
алгоритмов озёр. `proceduralSeaAutoresolve` получает обязательный `topology`
для вызовов shore-helper; bbox-edge семантика остаётся шагом 3b.

**Уточнение сервиса (2026-10-20):** sphere-fold даёт равноудалённые образы
одного query с разным `dot` (вода против торца). В шаге 3a
`nearest_on_segment` получает необязательный application `tie_breaker`
только для равных минимумов, чтобы сохранить HY-6 max-dot; прежний default
не меняется. Контракт уточнён в обоих ТЗ, покрывается доменным и HY-11 тестами.

| Поле | Содержание |
|---|---|
| Цель | footprint/carver не содержат raw смежности/евклида на мировых координатах |
| ТЗ | § SeaBasinGenerator + § Топология поверхности |
| Файлы | `shore/waterSideFootprint.py` (BFS unrolled + `canonical_passable`, `at()` через `nearest_on_segment`, `seeds`/`land_shore` через домен-метрику), `shore/deepeningBandCarver.py` (signature += `topology`, `compute_land_centroid`→`topology.centroid`), call-site resolve `WorldTopology` из world |
| Контракт | `carve_deepening_bands(heightmap, segments, bands, *, topology, water_body_uid, z_sea)`; `passable` остаётся параметром (шов HY-8) |
| Проверка | `test_hydrology_hy11.py`: wrapped — coastline на `x_min` → вода на `x_max` (BFS через шов); sphere — y-шов со сдвигом; centroid через шов; planar — void + warning; регрессии hy2/hy5a/hy6 зелёные |
| Done | море через шов в declared-flood; `neighbors4` в `shore/` = 0 |

### Шаг 3b — consumers → домен

**Уточнение (2026-10-20):** для loader добавлен доменный `canonical_frame`
с переносом всей spec в единый кадр канонического anchor. Это сохраняет
authored extent/связность при fine→grid; независимая канонизация концов
исказила бы геометрию. Семантика зафиксирована в обоих ТЗ; topology loader
без heightmap использует world bounds/locations, при их отсутствии оставляет
unrolled-ввод runtime. Внешние API генераторов не меняются.

| Поле | Содержание |
|---|---|
| Цель | autoresolve/master-input/rasterize на домене; в hydrology ноль raw adjacency |
| ТЗ | § SeaBasinGenerator + § Топология поверхности |
| Файлы | `autoresolve/proceduralSeaAutoresolve.py` (bbox-edge семантика через `edge_tiles`/`neighbor`, `flood_from_bbox_ocean_edge`), `load/buildHydrologyMasterInput.py` (fine→grid через `canonicalize`), `geom/polylineRasterize.py` (rasterize через шов) |
| Контракт | без новых сигнатур наружу — потребители зовут домен |
| Проверка | те же `test_hydrology_hy11` + grep `neighbors4` по `generators/hydrology/` → 0; регрессии |
| Done | `neighbors4` в hydrology = 0; море через шов end-to-end |

### Шаг 4 — smoke

| Поле | Содержание |
|---|---|
| Цель | море через шов на реальном мире |
| ТЗ | smoke по HY-6 плану |
| Файлы | `fixtures/world_test_004.json`: coastline **обратно** на x=−1500 (gx=−2, край) — в wrapped water-side = запад → вода на gx=+2 (восточный край) |
| Контракт | без schema/контрактов |
| Проверка | rebake → coarse evidence: `water_dist` клетки gx=+2; warning'и не ложные; L0 без band (HY-10) — проверка по coarse/acceptance. **Backend агенту не стартовать** — через мастера или уже поднятый сервер |
| Done | море через шов в данных |

## Приёмка

### Итоговая приёмка — 2026-10-20

- Шаги 1, 2a, 2b, 3a, 3b выполнены. Итоговый прогон гидрологии,
  топологии, регионов и рендера: **233 теста OK**; compileall и diff-check
  с учётом CRLF — OK. Собственных `neighbors4`/`_neighbors4` в hydrology нет
  (`rg '\b_?neighbors4\b'`); вызовы доменного `neighbors4_unrolled` допустимы.
- Шаг 4: fixture coastline и coast-pin возвращены на `x=-1500`, y/z и
  ocean-pin сохранены. Чистый production `prepare_surface_terrain_context`
  на нормализованной реальной фикстуре даёт `wrapped`, 25 coarse-клеток,
  15 hydro-клеток, 10 water-footprint клеток. Все `(gx=2, gy=-2..2)` имеют
  `water_dist=1` и `deepening_index=1`. Warning `water_dist=0` отсутствует;
  `water extent 2 <= bands.min 5` ожидаем для interim bands.
- Evidence: [hy11-coarse-acceptance.json](../../.local/map-render/world-test-004/hy11-coarse-acceptance.json),
  включая SHA256 фикстуры. Это **offline pure planning, не HTTP rebake**.
- После запуска backend мастером runtime coastline/coast-pin синхронизированы
  на `x=-1500` через HTTP; y/z, bounds и режим `wrapped` сохранены.
  Старый pack перемещён в `.local/map-render/1ff7d3a4-a832-4951-ad33-fe9cb314336c/hy11-pack-before-20261020T132320/`.
- **HTTP smoke выполнен:** light — HTTP 200, 10240 L0 cells / 10 tiles;
  full — HTTP 200, 25600 L0 cells / 25 tiles; render-world-grid — HTTP 200,
  `read_path=pack`. Runtime UID: `1ff7d3a4-a832-4951-ad33-fe9cb314336c`.
- [Generation evidence](../../.local/map-render/1ff7d3a4-a832-4951-ad33-fe9cb314336c/hy11-generation-evidence.json)
  содержит выдержки обоих generation logs: `coastal_sea cells=15`,
  `coarse_hydro=15`, ожидаемый warning `water extent 2 <= bands.min 5`;
  `water_dist=0` отсутствует. Логи: `bake-light-20261020T102458Z.log` и
  `bake-full-20261020T102514Z.log` в `backend/logs/generation/{uid}/`.
- [Runtime coarse acceptance](../../.local/map-render/1ff7d3a4-a832-4951-ad33-fe9cb314336c/hy11-runtime-coarse-acceptance.json):
  production planning на актуальных world/locations, прочитанных через HTTP
  после rebake: все пять `(2, gy)` имеют `deepening_index=1`.
  [L0 ASCII](../../.local/map-render/1ff7d3a4-a832-4951-ad33-fe9cb314336c/hy11-world-map.txt).
  Отсутствие band в L0 остаётся HY-10, не критерий провала HY-11.
- HY-11 → **resolved**; домен и первый консьюмер в TOPO-1 закрыты.
  Остальные домены TOPO-1, включая river `_neighbors8`, остаются открыты.
  Backend агент не запускал.

- `python -m unittest backend.tests.test_topology_unrolled_geometry backend.tests.test_hydrology_hy11` зелёные; регрессии hy2/hy5a/hy6 без новых падений относительно baseline съюта.
- `compileall` изменённых модулей, `git diff --check` после каждого шага.
- Grep `neighbors4` по `generators/hydrology/` → 0.
- HY-11 в `tz_generator_technical_debt.md` → `resolved`; план → `hy-11-topology-domain-geometry-done.md`.

## Не входит

- HY-10 (band в L0), HY-7 (shore×mountain), HY-8 (вода-уровень), HY-9 (формы), HY-BATH-1.
- Seam-запись L0 pack (seam-pairs уже пишутся — `tz_world_pack_storage` § Шов мира L0).
- Climate field / pathfinding на швах — свои домены; здесь только гидрология-консьюмер + домен-сервисы.

## Потребители домена (прицел, не scope этого плана)

Контракт сервисов закладывается под **всех** консьюмеров — домен не переписывается под каждый. Текущее состояние по коду:

| Домен | Сейчас | После подключения |
|---|---|---|
| **Маски/landcover** | `fine_topology` + `canonicalize` + `smooth_field(topology)` — регионы через шов | ✅ уже проводной — эталон |
| **Климат** | `ClimatePoleField.sample` → `dist_euclidean` к полюсам (planar) | `topology.dist2(cell, pole)` — blend через шов; ТЗ именует «climate field на краях» консьюмером |
| **Рельеф** | `relief/discover/*` (apron, fronts, rim, seam), `reliefObjects/depressionDetect` — raw | unrolled-метрика; объект через шов |
| **Горы** | `terrain/mountains/geom.py`, `sideFill` — raw | то же |
| **Гидрология** | 16× `neighbors4`, планарный центроид | **этот план** |
| **Локации** | anchors/pins — планарные координаты; district/settlement «neighbor» — внутренний граф, не мировая топология | `canonicalize` для позиций/claims |
| **Pack seam** | `worldSeam.py` + `gridNeighborHalo.py` — L0 seam-pairs/halo | ✅ пишется |

Переключение климат/рельеф/горы/локаций — отдельные планы; здесь только чтобы сервисный контракт их покрывал.
