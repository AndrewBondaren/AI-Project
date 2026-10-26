# План завершён: техдолг ревью шага 5/6 — HY-12 (реки на waterline + topology + cleanup)

## Контекст

Ревью коммита `54e9644` («remove legacy lake/sea autoresolve modules and
basin kind resolver after migration to Pass 1.4 water placement adapter»,
2026-10-21) — реализация шага 5 и приёмочной части шага 6 плана
[`hy-12-sea-elevation-contract-done.md`](hy-12-sea-elevation-contract-done.md).

Архитектура соответствует плану: реки не writer z (`RiverBedSpec` →
единственный relief writer `riverBedZ`), устье = open-water роль или strict
`z < z_water_level` при body UID (`is_river_mouth`), typed `WaterfallDrop` в
`HydrologyResult.waterfall_drops`, `canonical_neighbors8`/`neighbors8_unrolled`
в topology-домене, legacy-модули (`proceduralLakeAutoresolve`,
`proceduralSeaAutoresolve`, `basinKindResolver`, `lakeBasinGenerator`,
`deepeningBandCarver`, bathymetry stub) удалены, `pre_river_z` snapshot
исключает двойной carve в fine-пути. Профили собираются на одном
pre-bed snapshot — контракт «planner → spec → relief apply → роли» выдержан.

Ниже — находки по критериям ревью: неявные контракты, хардкоды,
«один модуль — одна ответственность», «один метод — одна функция».

## Карта находок → шаги

| # | Находка | Критерий | Файлы | Шаг |
|---|---------|----------|-------|-----|
| 1 | `topology=None` — три разных фолбэка: `segments_from_declared` молча пропускает canonicalize; `plan_river_network` resolve из мира; `river_topology` принудительный **PLANAR** из `heightmap.bbox`, игнорируя `terrain_scalars.world_topology_mode`. Standalone-вызов без topology на wrapped/sphere мире тихо теряет seam-семантику: планировщик идёт по planar-соседям, а `river_bed_spec`/`is_river_mouth` — по world-топологии | неявный контракт | `hydrology/rivers/riverGeometry.py:14-21`, `riverNetworkPlanner.py:73-80,213-217`, `classifyRiverSegments.py:16-24`, `resolveDeclaredRiverPath.py:51-58`, `riverNetworkAssembler.py:50-52` | 1 |
| 2 | `_channel_depth_step` — underscore-имя, импортируется тремя модулями (assembler, fineHydrologyIndex, test helper). Кросс-модульный приватный контракт; сигнатура и смысл политики нигде не зафиксированы | неявный контракт | `hydrology/rivers/riverBedCarver.py:20-25`; импорты в `riverNetworkAssembler.py:8`, `shore/fineHydrologyIndex.py:24`, `tests/hydrology_geometry_helpers.py:30` | 2 |
| 3 | `generate_rivers(*args, **kwargs)` — нетипизированный compat-shim → 3-tuple; живёт ради `test_hydrology_hy5c`. Второй публичный шов в новом модуле, прячет контракт `AssembledRivers` | неявный контракт, SRP | `riverNetworkAssembler.py:121-123`, `tests/test_hydrology_hy5c.py:5,79` | 3 |
| 4 | `AssembledRivers.bed_specs` — поле результата без потребителей (apply внутри `assemble_rivers`). Либо задел под spec-queue, либо лишний выходной контракт | неявный контракт | `riverNetworkAssembler.py:40,118` | 3 |
| 5 | Алиасинг `hm.surface_z is surface_z`: корректность возврата `apply_declared_fine_river_carves` держится на том, что `apply_river_bed_z(hm, specs)` пишет в тот же dict, что возвращается — в FINE_GRID через конструктор, в SURFACE_GRID через `replace`. Будущий `dict()`-слой молча теряет русла | неявный контракт | `shore/fineHydrologyIndex.py:52-67,85-86,100-102` | 4 |
| 6 | Fine-путь: `resolve_declared_river_intents(..., occupied={})` — planning слеп к принимающей воде; `occupied` из coarse_hydro собирается после и проецируется только на клетки полилиний (`samples`). Устье при планировании не видно, усечение делегировано `river_bed_spec` — неявный двухфазный контракт. Вопрос: осознанно или регрессия относительно старого `merged_hydro`? | неявный контракт | `shore/fineHydrologyIndex.py:72-88` | 4 (решение мастера) |
| 7 | `with_*` вручную перечисляют поля; при расширении модели возможна потеря полей. Исправление должно сохранять валидацию: голый `model_copy(update=...)` её не выполняет | неявный контракт / валидация | `dataModel/hydrology/physicalWaterUnion.py:19-53`, `waterBody.py:24-34`, `mapCellHydrology.py:73-82` | 5 |
| 8 | `HydrologyResult.river_segments` теперь = только accepted-сегменты (пустой `spec.bed_z` → не попадает); раньше возвращались все спланированные. Молчаливое изменение выходного контракта сервиса | неявный контракт | `riverNetworkAssembler.py:94-98,118`, `hydrologyGeneratorService.py:93` | 6 |
| 9 | Autoresolve dedup `segment.polyline_cells[:-1]` — пересечение по последней клетке (устью) теперь допустимо; старый код пропускал сегмент при любом пересечении. Послабление не задокументировано | неявный контракт | `riverNetworkAssembler.py:108-109` | 6 |
| 10 | `claimed` в planner: было `set(occupied.keys())` (все занятые), стало только `is_river_mouth or _blocked_cell` — SHORE и прочие роли больше не отсекают истоки рек | неявный контракт | `riverNetworkPlanner.py:231-232` | 6 |
| 11 | `plan_path_to_target`: ранг `is_river_mouth(n)` завершает путь на любом принимающем теле до target (старое `and n == target` было мёртвым условием); `_polyline_for_river`: пустой leg → `return []` (было `continue` — нога терялась молча) | неявный контракт | `riverNetworkPlanner.py:186-187`, `resolveDeclaredRiverPath.py:131` | 6 |
| 12 | `base = 1` — lowland depth step литералом; после cleanup единственный источник глубины для обоих проходов. Mountain идёт через `type_classify.mountain_bed_steepness_factor` — lowland не через реестр/policy | хардкод | `riverBedCarver.py:20-25` | 2 (вопрос мастеру) |
| 13 | Внешний `min(z, ...)` защищает от подъёма рельефа при `z < z_min`; исходный вывод о мёртвом коде неверен без инварианта `z >= z_min`. Поведение сохраняется | уточнение ревью / инвариант | `riverBedCarver.py:30-31` | 2 |
| 14 | `max_radius=24` унаследован в `_nearest_water_cell`; метрика сменилась Manhattan-кольца → `dist2` (Euclidean²), значение не пересмотрено. Плюс `dist2` считается дважды на кандидата (filter + min key), скан всех `occupied` вместо ring-поиска | хардкод / perf | `resolveDeclaredRiverPath.py:51-58` | 6 |
| 15 | `z_min=0` дефолт в `apply_test_river` — расходится с production `world_z_min`; helper может скрывать клэмп | хардкод | `tests/hydrology_geometry_helpers.py:28-32` | 5 (minor) |
| 16 | `riverNetworkAssembler.py` — docstring скопирован со старого carver'а («River channel carve on declare polylines — D HY-4, U24/U28»); модуль — assembler, не carver. `from typing import Any` в середине import-блока | SRP / гигиена | `riverNetworkAssembler.py:1,13` | 3 |
| 17 | `riverBedCarver.py` — имя «Carver», carving переехал в `reliefObjects/riverBed/riverBedZ`; модуль держит три зоны: depth-политика + spec emission + roles | SRP / нейминг | `rivers/riverBedCarver.py` целиком | 2 |
| 18 | `river_topology` — фабрика fallback-политики внутри geometry-модуля; дублирует fallback-логику `resolve_hydrology_topology` (там — bounds из world/bbox + mode из scalars; тут — PLANAR). Политика ≠ геометрия | SRP | `riverGeometry.py:14-21`, `load/resolveHydrologyTopology.py:24-34` | 1 |
| 19 | `apply_declared_fine_river_carves` — два режима в одной функции: load + topology lift + segments + coarse→fine sampling + occupied projection + re-classify + spec/roles/apply (~60 строк); ветка `WORLD_SURFACE_GRID` (77–92) — отдельная зона + 3 локальных импорта | один метод — одна функция | `shore/fineHydrologyIndex.py:39-102` | 4 |
| 20 | `classify_autoresolve_polyline` в fine-пути используется ради одного поля `connection_type` — строится целый `RiverSegment` и выбрасывается | один метод — одна функция | `shore/fineHydrologyIndex.py:89-92`, `classifyRiverSegments.py:31-49` | 4 |
| 21 | `prepare` в `assemble_rivers` — замыкание из 4 действий на сегмент (truncate polyline → spec → roles → drops); границы размыты, списки мутируются извне | один метод — одна функция | `riverNetworkAssembler.py:82-99` | 3 |

## Согласованные решения мастера — 2026-10-21

Это целевой контракт предстоящей правки review-debt. Документационная
фиксация не означает реализацию перечисленных изменений.

- **R-1 — topology обязательна.** Caller один раз разрешает topology из мира;
  все нижележащие river-функции, которым нужна топология, получают явный
  `WorldTopology`. Тесты также явно задают режим. Неявный PLANAR-fallback
  удаляется; отсутствие topology — ошибка входа. Повторного resolve внутри
  planner/геометрических helpers нет. Helpers, читающие готовый canonical
  индекс без геометрических операций, не получают фиктивную topology.
- **R-2 — вода видна до planning.** Fine intents получают resolved водный
  индекс до построения маршрута. Усечение spec на пересечённой воде остаётся
  защитой дна, но не заменяет поиск принимающего тела при planning.
  Coarse→fine доступ не требует полного разворачивания мира в fine-клетки.
- **R-3 — явный отказ и runtime-fallback.** `river_segments` содержит
  материализованные принятые участки; отказ не исчезает молча и обязательно
  диагностируется, особенно в логе. Runtime сначала пытается достичь заданной
  цели; при неудаче разрешено перенаправить объект в **ближайший достижимый
  водоём**, включая другое тело. Выбор использует topology, соблюдает правила
  маршрута/спуска и детерминирован при равенстве кандидатов. Успех fallback
  сохраняет UID исходного объекта, authored-цель не переписывается молча.
  Общая клетка устья у рек допустима; сухой SHORE проходим. Невозможный
  обязательный участок не пропускается: исходная попытка отклоняется,
  затем применяется runtime-fallback.
- **R-3/log — полный `WarningError`.** Перенаправление логирует world UID,
  UID и тип перенаправленного объекта, исходную цель (UID/координаты),
  конкретную причину её недостижимости, UID и тип выбранного водоёма,
  фактическую клетку устья. Недостаточно сообщения «fallback applied».
  Если в мире **нет водоёмов**, объект не материализуется и выпускается
  отдельный `WarningError`. Если тела есть, но **нет достижимого**, объект
  также не материализуется, с отличимой причиной в отдельном `WarningError`.
  Материализация остальных объектов продолжается; фиктивная вода/русло
  вместо отказавшего объекта не создаётся. Ошибка отсутствующей topology
  по R-1 не маскируется перенаправлением. Import/validate-only не должны
  молча применять runtime-fallback.
- **R-4 — глубина в POJO, default 3 cells.** Поле
  `world.hydrology.default_rivers.channel_depth_cells` — положительный int,
  default **3**, единицы **cells** по вертикали Z. Генератор читает POJO;
  локального fallback-литерала нет. Старое имя из примера ТЗ
  `channel_depth_step_m` заменяется. Mountain-множитель
  `mountain_bed_steepness_factor` сохраняется поверх базовой глубины,
  с текущим округлением: `max(1, round(depth * factor))`, то есть
  default 3 и factor 1.5 дают 4 cells. Это поле глубины, не эвристика
  классификатора типа реки. Override отдельной authored реки в этом
  обсуждении отдельно не утверждён и этим решением не добавляется.
- **R-5 — наружный `bed_specs` удалить.** Инвентаризация кода и ТЗ не нашла
  потребителей `AssembledRivers.bed_specs`: relief apply уже выполнен внутри
  assembler. Это новый лишний выходной контракт шага 5, вошедший в
  `54e9644e`, а не обязательный legacy API. Сам `RiverBedSpec` и внутренняя
  последовательность planner → specs → relief apply → роли сохраняются.
- **R-6 — единый допуск поиска устья.** Настраиваемая policy расстояния
  задаётся в **world-fine cells** и имеет одинаковый физический смысл в
  coarse/fine проходах. Радиус не измеряется в клетках текущей рабочей сетки.
  Числовой default согласован мастером: **200 world-fine cells** (размер клетки L2).
  Прежний литерал `24` заменяется; coarse-проход пересчитывает тот же допуск
  в свою сетку, не трактует его как 200 coarse/L0-клеток.
  Допуск привязки authored mouth и выбор другого тела при runtime-fallback —
  разные операции; согласие на допуск не отменяет R-3.

### Технические уточнения по результатам проверки ревью

- **Находка 13 исправлена:** `min(z, max(z_min, z - depth_step))` не является
  мёртвым кодом без предпосылки `z >= z_min`. При `z=-10`, `z_min=0`, depth=1
  текущая формула сохраняет -10, предложенная замена поднимает дно до 0.
  При рефакторинге сохраняется поведение «river carve не поднимает рельеф»;
  удалять защиту без отдельного входного инварианта нельзя.
- **Находка 7 уточнена:** голый `model_copy(update=...)` не валидирует
  обновления и не равноценен существующим конструкторам. Рефакторинг должен
  одновременно сохранять все поля модели и валидацию обновлений.
- **Находка 11 уточнена:** у `plan_path_to_target` нет callers в текущем коде;
  изменение этого helper не доказательство production-регрессии. Его судьба
  определяется инвентаризацией API, а не автоматическим возвратом старого условия.

### Статус согласования

Все решения R-1…R-6 согласованы, включая default допуска authored mouth
**200 world-fine cells**. Открытого вопроса о числовом default больше нет.
Это допуск привязки authored-точки; runtime-fallback в ближайший достижимый
водоём остаётся отдельной операцией по R-3. Шаги 1–2 выполнены; шаги 3–6 впереди.

## Шаги

### Шаг 1 — единый контракт `topology` в river-модулях (выполнен 2026-10-21)

- **Цель:** caller разрешает topology один раз, геометрические river-потребители
  требуют её явно; wrapped/sphere семантика не теряется молча.
- **ТЗ:** `tz_terrain_generation` § Топология поверхности; TOPO-1 строка
  «↳ реки» (`docs/tz_generator_technical_debt.md`); план HY-12 шаг 5.
- **Файлы:** `hydrology/rivers/riverGeometry.py`, `riverNetworkPlanner.py`,
  `classifyRiverSegments.py`, `resolveDeclaredRiverPath.py`,
  `riverNetworkAssembler.py`, `load/resolveHydrologyTopology.py`.
- **Контракт:** R-1: caller разрешает `WorldTopology` из мира;
  нижележащие функции требуют явный параметр, без повторного resolve.
  PLANAR-fallback `river_topology` удаляется. `segments_from_declared`
  получает topology явно; тесты задают planar/wrapped/sphere явно.
- **Проверка:** unit — wrapped topology доходит до planner/spec/ustье без
  planar-подмены; регрессия `test_hydrology_hy12_rivers`,
  `test_hydrology_hy5*`, `test_hydrology_determinism`; `compileall`.
- **Done:** один resolve на границе caller, отсутствие topology — ошибка;
  ни один вызов не получает PLANAR для wrapped/sphere мира.

**Отчёт шага 1 — 2026-10-21.** Удалён `river_topology` с неявным PLANAR/bbox fallback. `segments_from_declared`, declared intent resolver, source/descent/target/network planner, autoresolve и assembler требуют явный POJO `WorldTopology`; пропуск аргумента или явный None отклоняется, включая пустой input. Read-only spec/mouth helpers готового canonical индекса не получают ненужный параметр. Геометрия остаётся на `topologyGeometry`/`WorldTopology`, новых raw neighbors, метрик или policy-defaults нет.

Caller wiring входит в шаг 1: `HydrologyGeneratorService` разрешает topology один раз для bodies+rivers; `surfaceTerrainContext` использует topology pre-relief water pass либо общий world resolver и передаёт тот же объект facade. Fine caller получает обязательную world-fine topology через доменный `fine_topology`; внутри `fineHydrologyIndex` повторного resolve/lift больше нет. Затронутые standalone tests явно задают topology. Geometry-only fine test исправлен на fine extent, содержащий authored координаты, вместо фиктивного bbox 0…1.

Проверки: **108 tests OK** — hydrology river suites, HY-5a/b/c, coarse/fine, water placement pass/world_test_004, smoke, hash-seed determinism, world topology и unrolled geometry. Новый `test_hydrology_river_topology_contract`: 4 tests с subtests — required/None topology, один resolve для bodies+rivers, отсутствие повторного resolve для explicit topology, declared assembler через wrapped seam/sphere fold с сохранением mouth floor. compileall и diff-check изменённых backend-файлов выполнены. Шаги 2–6 (POJO глубины 3 cells и допуска 200 fine cells, fallback/log, API/fine/POJO cleanup) этим не объявляются выполненными. Backend не запускался, коммит не создавался.

### Шаг 2 — river-модуль: политика глубины, нейминг, сохранение клэмпа (выполнен 2026-10-21)

- **Цель:** модуль с честным именем и публичным seam; depth-политика
  типизирована.
- **ТЗ:** `tz_terrain_hydrology` § реки (устье/профиль); правило
  `dataModel-no-hardcode` (глубина через POJO по принятому R-4).
- **Файлы:** `hydrology/rivers/riverBedCarver.py` (вероятный rename, напр.
  `riverBedProfile.py`), `riverNetworkAssembler.py`,
  `shore/fineHydrologyIndex.py`, `tests/hydrology_geometry_helpers.py`,
  `dataModel/hydrology/rivers.py`, loader политики, `docs/tz_terrain_hydrology.md`.
- **Контракт:** `_channel_depth_step` → публичное имя (или перенос в
  модуль-владелец политики); R-4: POJO `channel_depth_cells`, default 3 cells,
  mountain-множитель сохраняется. Не поднимать уже низкий рельеф;
  внешнюю защиту `min(z,…)` не удалять как якобы мёртвую.
- **Проверка:** grep `_channel_depth_step` — нет underscore-импортов;
  регрессия river-тестов; `compileall`.
- **Done:** нет кросс-модульных приватных имён; клэмп читаем.

**Отчёт шага 2 — 2026-10-21.** `HydrologyRiversPolicy.channel_depth_cells` — `DefaultWhenMissing[int]`, strict positive int, единственный default **3 cells** в POJO. Публичный `channel_depth_for(HydrologyConnectionType)` принадлежит этому POJO, читает базовую глубину и существующий `type_classify.mountain_bed_steepness_factor`, сохраняет округление и положительный минимум; неподходящий connection kind отклоняется. Coarse assembler и fine materializer читают `hydrology(world).default_rivers` через общий typed reader, без raw dict access и локальных fallback-литералов. Поле не добавлено в runtime `RiverTypeClassify`: глубина не является эвристикой классификации. Missing использует модельный default, supplied invalid не заменяется default.

`rivers/riverBedCarver.py` переименован в `riverBedProfile.py`; старый `_channel_depth_step` удалён без compat shim, все callers/test imports переключены. Модуль профиля содержит read-only spec/role emission, relief остаётся единственным z-writer. Клэмп разбит на понятные операции с сохранением внешнего `min`: пол ниже `z_min` не поднимается. Helper `apply_test_river` только переключён на новый import; изменение его `z_min` default остаётся шагу 5.

Проверки: **157 tests OK** (river depth/topology, HY-1/4/5a–c/12, declared wire, coarse/fine/UID, world_test_004 smoke, placement pass, hash-seed determinism, topology/unrolled geometry, relief objects). Новый `test_hydrology_river_depth_policy` — **8 tests**: missing/default и custom wire round-trip, strict invalid values/import/runtime, mountain rounding и минимум, неверный kind, custom глубина в обоих materializers с защитой устья, сохранение пола ниже z_min. Три старых assertions обновлены с глубины 1 на согласованные 3 cells; явные тесты `depth_step=1` сохранены. compileall/diff-check выполнены. Шаги 3–6 и допуск 200 fine cells/runtime-fallback/log этим не объявляются реализованными. Backend не запускался, коммит не создавался.

### Шаг 3 — riverNetworkAssembler: один публичный seam (выполнен 2026-10-21)

- **Цель:** модуль-ассемблер с одним входом, честным docstring и без
  мёртвых выходов.
- **ТЗ:** план HY-12 шаг 5 («`riverNetworkAssembler` собирает все профили
  на одном pre-bed snapshot»).
- **Файлы:** `riverNetworkAssembler.py`, `rivers/{riverRouteRequests,riverRouting,riverRouteDiagnostics,riverPrepare}.py`,
  `dataModel/hydrology/{riverRouting,rivers}.py`, `resolveDeclaredRiverPath`,
  `riverNetworkPlanner`, `geom/smoothRiverPolyline` (численная граница поворота),
  `hydrologyGeneratorService`/`types.py`,
  `tests/test_hydrology_hy5c.py` и routing regression tests.
  Это необходимые контракты/подключение R-3 в рамках шага 3; fine-cutover остаётся шагу 4.
  Полный контракт до кода: `tz_terrain_hydrology` § River routing: кодовые контракты review-debt шага 3.
- **Контракт:** `generate_rivers` удалён; `test_hydrology_hy5c` переведён
  на `assemble_rivers`; наружный `bed_specs` удалён по R-5, внутренние specs
  сохраняются; docstring переписан под
  роль assembler'а; `prepare` вынесен в приватную функцию верхнего уровня
  (принимает/возвращает явно, без замыкания на списки) либо задокументирован
  как job; по R-3 — docstring фиксирует «segments = accepted only» и
  допустимое общее устье. Ошибки и runtime-fallback следуют R-3:
  ближайшее достижимое тело, полные WarningError, отдельные причины
  отсутствия тел/достижимых тел. Новые кодовые контракты diagnostics и
  fallback до реализации описать в ТЗ; это предстоящая работа шага,
  не реализованное поведение.
- **Проверка:** `test_hydrology_hy5c` зелёный без shim; перенаправление в
  ближайшее достижимое тело, недостижимый ближайший кандидат, равенство
  расстояний/детерминизм, отсутствие тел, отсутствие достижимых тел,
  полнота WarningError, отсутствие частичной материализации при отказе;
  grep `generate_rivers` — только история; `compileall`.
- **Done:** один публичный API `assemble_rivers`; результат без
  неиспользуемых полей.

**Отчёт шага 3 — 2026-10-21.** Удалены `generate_rivers` и наружный `bed_specs`; assembler публикует только принятые segments после единственного relief apply. Подготовка запросов, read-only route search, профили и diagnostic sink разделены на модули, без closure на списки. Все segments одной authored-реки принимаются атомарно на pre-bed snapshot; успешные объекты резервируют interior bed, shared mouth сохраняется, независимые отказы не блокируют остальные объекты. Явные ошибки исходной попытки сохраняются, runtime ищет ближайшее достижимое принимающее тело по topology; import/preview не перенаправляют. Отдельны no-bodies/no-reachable/invalid-source, лог перенаправления содержит полный typed POJO с исходной целью и фактическим приёмником; facade сохраняет diagnostics.

Политики локального mouth query и бюджета пути находятся в POJO: `mouth_search_radius_fine=200`, `max_path_cells=128` (перенос прежнего planner cap). Допуск одинаков в физических fine-единицах; coarse query сохраняет authored subcell-позицию, кандидаты проецируются общим coordinate hub, геометрия — через доменный `fine_topology`/`dist2`. Runtime fallback не ограничен локальным mouth radius, но соблюдает terrain, waterline, занятость, turn limit и бюджет пути. В shared turn helper исправлена численная ошибка: точный 45° не отклоняется из-за float `45.00000000000001`; 90° по-прежнему запрещён. Это необходимое исправление граничного сравнения, без изменения допустимого угла.

Проверки: **468 tests OK** — расширенный HY-12 набор, включая hydrology, declared rivers, placement, bathymetry, terrain, pack bake, topology и relief. Новый routing suite — **18 tests**: полные WarningError, ближайший недостижимый кандидат, deterministic tie/permutation, атомарность, independent objects/shared mouth, preview/import, отдельные отказы, higher waterline, missing anchor/receiver UID, wrapped/sphere fallback, POJO limits/strict wire, одинаковый physical radius и точная граница 200/201 fine cells внутри coarse-клетки, 45°/90°. Sandbox-прогон остановлен при зависании временной SQLite; тот же полный набор вне sandbox прошёл. Отбор процедурных candidate sources остаётся HY-RIV-1; диагностика шага покрывает запросы материализации assembler. Fine R-2/R-3 остаётся шагу 4. Backend не запускался, коммит не создавался.

### Шаг 4 — fine river carve: явный контракт surface_z и выделение sampling-зоны (выполнен 2026-10-21)

- **Цель:** возврат z не зависит от алиасинга dict; coarse→fine-проекция —
  отдельная функция; intents видят воду по R-2.
- **ТЗ:** план HY-12 шаг 5 («fine profiles читают один snapshot»),
  `tz_map_light_bake` § fine-координаты.
- **Файлы:** `shore/fineHydrologyIndex.py`,
  `shore/fineRiverSampling.py`, `terrain/passes/surfaceTerrainContext.py` (caller),
  shared `rivers/{riverRouteRequests,riverPrepare,classifyRiverSegments}.py` и
  `riverNetworkAssembler.py` (общий prepare job, явный coordinate space), tests.
  Уточнение шага 4 до кода: runtime-fallback использует тот же prepare job;
  shared helpers получают явный CoordinateSpace для координат diagnostics.
  Coarse sampling ограничен authored paths и окнами из POJO max_path_cells /
  mouth_search_radius_fine, canonicalize через topology; полный мир в fine
  не разворачивается. Вода проецируется до intent resolver; после snap новые
  route cells досэмплируются до классификации и profile emission.
- **Контракт:** функция возвращает `hm.surface_z` напрямую (единственный
  SoT результата), без зависимости от алиасинга локальной переменной; ветка
  `WORLD_SURFACE_GRID` вынесена (например `_sample_coarse_to_fine`,
  `_project_coarse_hydro`); локальные импорты — наверх;
  re-classify undeclared сегментов — отдельная функция, не
  `classify_autoresolve_polyline` ради одного поля; по R-2 resolved вода
  доступна для intent-planning заранее, усечение в spec — только защита дна.
  Runtime-fallback и diagnostics соответствуют R-3 в обоих проходах.
- **Проверка:** unit — русла в возвращаемом surface_z в обоих режимах;
  `test_hydrology_hy12_rivers` (fine sampling, отсутствие двойного carve);
  `compileall`.
- **Done:** удаление алиасинга не ломает поведение; функция ≤ ~40 строк
  в основном теле.

**Отчёт шага 4 — 2026-10-21.** Fine resolver получает resolved воду до построения маршрута. Отдельный `fineRiverSampling` читает pre-river snapshot, проецирует coarse hydro, затем досэмплирует клетки после mouth-snap и классифицирует тип через `classify_river_type` без повторной эмиссии геометрии. Рабочая зона ограничена authored paths и POJO-окнами поиска; по одной известной мокрой точке coarse-клетки сохраняется для корректной диагностики наличия удалённой воды. Клетки только поискового окна не попадают в overrides. Исходные elevation/hydro не мутируются; coarse bed уточняемой authored-реки исключается из чужой занятости, reservations между fine-объектами остаются.

Fine и coarse используют общий `prepare_river_requests`: атомарные профили на одном pre-bed snapshot → один relief apply → роли/диагностика. Request и prepare получают явный CoordinateSpace; fine diagnostic координаты не умножаются повторно на coarse span. Результат fine helper — напрямую `hm.surface_z`, без зависимости от alias локального dict. Caller передаёт `water_bodies` и единый ResolveContext в оба прохода, topology поднимается доменным helper один раз на caller. Основное тело fine helper — около 35 строк, sampling вынесен отдельно; локальные imports убраны.

Проверки: расширенный набор **478 tests OK** (hydrology/placement/bathymetry/terrain/pack/topology/relief), затем **38 tests OK** после финального уточнения imports/итерации и добавления seam/pole/remote-water cases. Новый `test_hydrology_fine_river_planning` — **12 tests**: resolved water до snap, post-snap sampling и реальный mountain type, writer заменяет dict в обоих пространствах, runtime-fallback и fine diagnostic coords, preview/import, dry failure без частичного bed, отсутствие самоблокировки coarse bed, независимые объекты, wrapped/sphere sampling, sparse overrides и remote-water presence. Старые UID/успешные fine tests дополнены реальной принимающей водой и явным POJO budget для длинных маршрутов; mock результатов coarse hydro дополнен water_bodies. Это изменение фикстур под согласованный R-3, не маскировка отказа. compileall/diff-check выполнены. Backend не запускался, коммит не создавался.

Находки раунда 2 (разделение UID цели, terminal confluence/cycles, invalid kind boundary, RECEIVER_METADATA и уточнения source failure) остаются шагу 7; подключение общего job к fine не объявляет эти исправления реализованными. POJO with_* остаются шагу 5.

### Шаг 5 — POJO `with_*`: сохранение полей и валидации + test helper (выполнен 2026-10-21)

- **Цель:** copy-методы не теряют будущие поля; test-helper не скрывает
  клэмп.
- **ТЗ:** `contract-creation` (строгая типизация и валидация обновлений сохраняются).
- **Файлы:** `dataModel/hydrology/physicalWaterUnion.py`,
  `dataModel/hydrology/waterBody.py`, `dataModel/hydrology/mapCellHydrology.py`,
  `tests/hydrology_geometry_helpers.py`, callers в `test_hydrology_hy4.py` /
  `test_hydrology_water_body_uid.py`, `tests/test_hydrology_pojo_updates.py`.
  Уточнение до кода: используется существующий проектный pattern
  `type(self).model_validate(self.model_dump(round_trip=True, by_alias=True) | updates)`;
  новый base class/helper для трёх моделей не вводится. Тесты добавляют
  обязательное поле/validator только в подкласс POJO, не в production wire.
  Уточнение совместимости: requirements допускает Pydantic >=2.7; новый
  by_name parameter не используется. Python round-trip dump сохраняет
  aliases, что отдельно проверяется обязательным полем подкласса с alias.
- **Контракт:** `with_*` сохраняют все поля модели и валидируют обновления,
  без ручного перечисления полей и без слепого `model_copy(update=...)`;
  имена/сигнатуры снаружи не меняются. `apply_test_river` — обязательный
  `z_min` или `world_z_min` из фикстуры, без `=0`.
- **Проверка:** юнит — новое поле POJO сохраняется через `with_*`,
  невалидное обновление отклоняется как до рефакторинга;
  регрессия hydrology/water-тестов.
- **Done:** ни один `with_*` не перечисляет поля вручную.

**Отчёт шага 5 — 2026-10-21.** Все шесть `with_*` в PhysicalWaterUnion (4), WaterBody (1), MapCellHydrology (1) используют полный `model_dump(round_trip=True, by_alias=True)` и `type(self).model_validate` с обновлением только запрошенных полей. Неизменённые поля вручную не перечисляются, тип подкласса сохраняется, field/model validation выполняется повторно. Новый общий base/helper и production wire-поля не вводились. API совместим с заявленным Pydantic >=2.7, без нового by_name parameter или повышения dependency floor. Blind model_copy(update=...) не используется.

`apply_test_river` требует явный z_min. Все обычные callers в HY-4/UID tests получают его через world_z_min фикстуры; единственный пропуск аргумента в новом тесте намеренно проверяет TypeError. Отрицательный floor и защита существующего пола ниже z_min подтверждены; production carve/clamp не менялся.

Проверки: **117 tests OK** — новый `test_hydrology_pojo_updates` (5 tests с subtests), water resolver/UID, HY-4, HY-12 contract/rivers/smoke, routing/depth/fine planning, water placement. Проверены обязательное новое поле и alias в test subclass, сохранение остальных данных и исходного экземпляра, clearing parent=None, invalid updates, повторное выполнение model validators и role/liquid normalization. compileall backend/app и diff-check выполнены. Backend не запускался, коммит не создавался. Шаги 6–7 не объявляются выполненными; согласованные находки раунда 2 остаются шагу 7.

### Шаг 6 — фиксация семантик в документах (выполнен 2026-10-21)

- **Цель:** подтверждённые изменения поведения записаны в ТЗ/docstring,
  не остаются «знанием diff'а».
- **ТЗ:** `tz_terrain_hydrology` § реки.
- **Файлы:** `docs/tz_terrain_hydrology.md`, docstring'и
  `riverNetworkPlanner.py`, `riverNetworkAssembler.py`,
  `resolveDeclaredRiverPath.py`.
- **Контракт:** синхронизация принятых R-1…R-6 с реализацией: материализованные
  `river_segments`, общее устье, проходимый SHORE, ошибка исходной попытки →
  runtime-fallback → ближайшее достижимое тело либо отказ с WarningError.
  Полнота логов обязательна. Не переносить поведение неиспользуемого
  `plan_path_to_target` в production-контракт без caller. Допуск поиска
  authored mouth — policy с default **200 world-fine cells**.
  Глубина — default 3 cells из POJO с mountain-множителем.
- **Проверка:** ревью мастера формулировок; код не меняется.
- **Done:** каждая семантика из находок 8–11, 14 либо задокументирована,
  либо возвращена к прежнему поведению.

**Отчёт шага 6 (2026-10-21).** ТЗ и docstring assembler/planner/intent resolver
сверены с текущим кодом. Находка 8: результат содержит только accepted segments
с непустым bed spec; terminal receiver остаётся в polyline без carve его дна.
Находка 9: общая terminal water cell допустима, interiors резервируются;
слияние с чужой рекой этим не объявляется реализованным. Находка 10: сухой
SHORE не блокирует ни маршрут, ни кандидатный исток при прочих выполненных
условиях. Находка 11: пустой rasterized leg отклоняет candidate; helper
plan_path_to_target не имеет production callers и не задаёт контракт intents.
Находка 14: mouth snap использует topology Euclidean distance в fine-метрике,
default 200 из POJO, с детерминированными ties; это отдельная операция от
runtime fallback. Подтверждены default глубины 3 cells, mountain-множитель,
атомарный prepare → relief apply → роли и полный diagnostic sink. Исправлены
устаревшие будущие времена в статусах R-1/R-5/R-6. Известные UID/error-boundary/
tributary/metadata уточнения оставлены явно целевыми для шага 7.

Проверки: compileall backend/app и git diff --check — OK; сравнение AST трёх
Python-модулей с HEAD после удаления docstring подтверждает отсутствие изменений
исполняемого кода. Новые тесты не добавлялись, алгоритмическая регрессия повторно
не запускалась: шаг меняет только документы/docstring, предыдущие 117 tests OK
относятся к шагу 5. Backend не запускался, коммит не создавался. Шаг 7 открыт.

## Ревью раунда 2 — реализация шагов 1–3 (commit `49e78d41`, 2026-10-21)

Повторное ревью после отчётов шагов 1–3. Реализация соответствует
согласованным R-1…R-6: явный `WorldTopology` без PLANAR-fallback и
TypeError-гейты, один resolve на caller (service + `surfaceTerrainContext`),
`channel_depth_cells=3`/`mouth_search_radius_fine=200`/`max_path_cells=128`
в `HydrologyRiversPolicy`, `channel_depth_for` на POJO, rename
`riverBedCarver`→`riverBedProfile`, удалены shim `generate_rivers` и
`bed_specs`, атомарное планирование → один `apply_river_bed_z` → роли/drops,
typed `RiverRouteDiagnostic` с полным контентом, детерминированный
runtime-fallback BFS. Критичных регрессий не выявлено; ниже — находки
раунда 2 по тем же критериям. Кандидатный **шаг 7** требует согласования —
состав шести шагов молча не расширяется.

### Карта находок раунда 2

| # | Находка | Критерий | Файлы | Шаг |
|---|---------|----------|-------|-----|
| R2-1 | `requested_mouth.location_uid` несёт **две семантики**: у intents — authored location uid; у edge/auto requests (`request_from_segments`) туда пишется `occupied[target].water_body_uid` — uid водоёма в поле «location». `validate_route` → `WRONG_BODY` сравнивает его с `water_body_uid`: работает только при конвенции `declared body uid == location_uid`; intent с устьем в локации над autoresolve-водой (`auto-*` uid) всегда получает WRONG_BODY → redirect. Диагностика показывает body uid под именем location. Та же конвенция в `_nearest_water_cell(target_uid=mouth.location_uid)`: вода с auto-uid в заданной локации не находится → authored mouth не привязывается | неявный контракт | `rivers/riverRouteRequests.py:56-60`, `rivers/riverRouting.py:87-91`, `rivers/resolveDeclaredRiverPath.py:36-56` | 7 |
| R2-2 | `is_river_mouth(target, {}, occupied)` в `request_from_segments` — пустой `surface_z` молча отключает половину предиката (`z < z_water_level`); `target_uid` определяется только по open-water роли | неявный контракт | `rivers/riverRouteRequests.py:58` | 7 |
| R2-3 | Multi-edge группировка обязана чейниться клетка-к-клетке: edges с общим `object_uid` склеиваются в один `RiverRouteRequest`; `cells[0] != path[-1]` между сегментами → `DISCONNECTED_PATH` → отказ всего объекта; fallback сводит объект к одному пути, ветви теряются. Legacy резал каждый edge независимо — контракт «один объект = один связный путь» или регрессия? | неявный контракт | `rivers/riverRouting.py:67-73`, `rivers/riverRouteRequests.py:66-83` | 7 (решение мастера) |
| R2-4 | `policy=None → HydrologyRiversPolicy()` в `plan_descent_path`/`plan_path_to_target` — снова «None = canonical defaults», четвёртая семантика `None` после R-1. Допустимо (POJO default), но противоречит «явное на границе» | неявный контракт | `rivers/riverNetworkPlanner.py:99-115,157-171` | 7 |
| R2-5 | Рассинхрон code/reason: источник на чужом русле (`Failure.BLOCKED`) — `invalid_source` не покрывает BLOCKED → fallback возвращает () по той же причине → код `NO_REACHABLE_WATER` при reason=`blocked_river_bed`. `invalid_source` — третья копия проверок источника (после `validate_route` и `fallback_route`) | неявный контракт | `rivers/riverPrepare.py:58-69`, `rivers/riverRouting.py:59-64,100-103` | 7 |
| R2-6 | Асимметрия режимов: `prepare_river` запрещает fallback при `mode is not RUNTIME`; `emit_river_diagnostic` шлёт в `report_issues` при `validate_only or mode is IMPORT` — гипотетический третий режим: fallback запрещён, но эмиссия идёт в `log_issues`. Условия не зеркальны | неявный контракт | `rivers/riverPrepare.py:65`, `rivers/riverRouteDiagnostics.py:11-14` | 7 |
| R2-7 | `RiverRoutingFailure.RECEIVER_METADATA` — enum-член без эмиттера: в `fallback_route` отсутствие `water_body_uid`/`receiver_kind` молча дисквалифицирует mouth; отдельная причина существует, но никогда не ставится | неявный контракт / мёртвый член | `dataModel/hydrology/riverRouting.py:31`, `rivers/riverRouting.py:129-134` | 7 (решение мастера) |
| R2-8 | `HydrologyConnectionType(segment.connection_type)` — `ValueError` валит весь `apply` (coarse `prepare_river`, fine `fineHydrologyIndex`) вместо per-river диагностики. «Неподходящий kind отклоняется» реализован crash'ем прохода | хардкод / error boundary | `rivers/riverPrepare.py:88`, `shore/fineHydrologyIndex.py:96-98`, `dataModel/hydrology/rivers.py:47-53` | 7 (решение мастера) |
| R2-9 | Non-null `topology` в `surfaceTerrainContext` — неявный инвариант: `fine_topology(topology, …)` упадёт при `water.topology is None`; спасает только то, что `resolve_hydrology_topology` с heightmap не возвращает None (негласно, из overload'ов) | неявный контракт | `terrain/passes/surfaceTerrainContext.py:96-127`, `load/resolveHydrologyTopology.py:14-34` | 7 |
| R2-10 | Одноимённые модули `riverRouting`: `dataModel/hydrology/riverRouting.py` (POJO/enums) и `generators/hydrology/rivers/riverRouting.py` (validate/fallback) — оба импортируются в `riverPrepare`/`riverNetworkAssembler`, двусмысленность имён | SRP / нейминг | оба файла | 7 |
| R2-11 | `math.isclose(angle, max_turn_deg)` — дефолтные `rel_tol=1e-9`/`abs_tol=0` без комментария; `source_fine = (river.source.x, river.source.y)` без `int()` при `_waypoint_fine` с `int()`; sentinel-резервация `MapCellHydrology(role=RIVER_BED)` без uid — контракт «занято, но не вода» читается двумя предикатами | хардкод / гигиена | `geom/smoothRiverPolyline.py:32-33`, `rivers/riverRouteRequests.py:98`, `riverNetworkAssembler.py:51-54` | 7 |
| R2-12 | Мелкие: per-edge `request_from_segments` вычисляется и выбрасывается (нужен только uid); `_selected_segments` молча отбрасывает сегменты до 1 клетки; `initial_failure` в `validate_route` проверяется после terrain/source-checks — `MISSING_ANCHOR` маскируется в `MISSING_TERRAIN` при `source=None`; `diagnostic_cell` — конвертер coarse→fine-origin внутри request-factory; `declared_river_requests` ~55 строк, две зоны (edges grouping + intents) | один метод — одна функция / гигиена | `rivers/riverRouteRequests.py:63-119`, `rivers/riverPrepare.py:31-47`, `rivers/riverRouting.py:56-66` | 7 |
| R2-13 | `fallback_route`: ancestry-walk O(d) на каждое состояние; states=(prev,cell) допускает повтор клетки с разных направлений — осознанно («retains distinct approach directions»), но при `occupied` порядка всей карты и лимите 128 — perf-характеристика стоит пометки | perf-note | `rivers/riverRouting.py:95-143` | 7 (опционально) |

### Открытые вопросы мастера (раунд 2)

- **Q-1 (R2-1/R2-2) — решён мастером:** сохранять authored
  `HydrologyMouth.location_uid` как UID локации, разрешённый UID принимающего
  тела хранить отдельно в typed request/diagnostic. Не требовать равенства
  location UID и body UID. Mouth-snap и проверка WRONG_BODY используют
  разрешённую идентичность тела, а не authored UID локации; auto-водоём
  в указанной локации является допустимым приёмником. Исходная цель и
  фактический приёмник при fallback сохраняются раздельно. При определении
  принимающей воды использовать реальный surface_z, не пустой словарь.
- **Q-2 (R2-3) — решён мастером:** одна река — отдельный объект со своим
  UID, истоком и непрерывным направленным маршрутом; приток — другая река.
  Приток вправе завершаться на русле принимающей реки: это слияние, а не
  запрещённое пересечение. Принимающая река продолжает сток к водоёму.
  Связь UID притока → UID принимающей реки фиксируется явно; цепочка стока
  проверяется на циклы. Транзит через чужое русло остаётся запрещённым.
  Атомарность — на уровне каждой реки: отказ притока не отменяет принимающую
  реку. Это целевой контракт; текущий безусловный BLOCKED для чужого
  RIVER_BED его ещё не реализует. См. ТЗ § «Притоки и слияние рек».
- **Q-3 (R2-8) — решён мастером:** невалидный `connection_type` даёт
  явную диагностику отказа конкретного объекта и WarningError; остальные
  объекты продолжают материализацию. Граница ошибки охватывает уже сборку
  request (`request_from_segments`), где ValueError возникает раньше
  `prepare_river`, а также последующую подготовку профиля. Ошибочный объект
  не оставляет частичного русла; подстановка допустимого типа вместо
  невалидного запрещена. Перед кодом уточнить typed-контракт diagnostics
  для такого входа; не ограничиваться try/except только в prepare_river.
- **Q-4 (R2-7) — решён мастером:** сохранить `RECEIVER_METADATA` и
  возвращать эту причину, когда именно отсутствие метаданных достижимого
  приёмника не позволяет завершить fallback. Поиск других допустимых
  приёмников продолжается; наличие корректного кандидата позволяет
  завершить fallback успешно. Каждый отброшенный кандидат отдельно
  не логируется. Итоговая диагностика отказа сохраняет также конкретную
  причину неудачи исходной попытки по R-3/log. Это целевой контракт шага 7,
  текущий поиск пока не возвращает причину отказа fallback.
- **Q-5 (R2-5/R2-6) — исполнен в согласованном шаге 7:** унифицировать код отказа источника (BLOCKED источника
  → свой код или INVALID_SOURCE) и зеркалить условия режима между
  `prepare_river` и `emit_river_diagnostic`.

### Шаг 7 — находки раунда 2 (выполнен 2026-10-22)

**Уточнение реализации до кода (2026-10-22).** Команда выполнить шаг 7
подтверждает его состав. Q-5 реализуется как INVALID_SOURCE для blocked истока
с сохранением BLOCKED reason; общий runtime-предикат управляет fallback/sink.
Инвентаризация: RiverSystemIndex/DeclaredRiver.parent_location_uid описывают
authored иерархию, WaterSystemKind — объединения воды, BasinKind — только бассейны;
готового факта направленного стока нет. Добавляется frozen RiverDrainageLink
(river_uid, river_type: HydrologyConnectionType, receiver_uid, receiver_kind: BasinKind | HydrologyConnectionType,
receiver_cell world-fine), tuple links в AssembledRivers/HydrologyResult и
optional river_drainage в MapCellHydrology (fine API сохраняет прежнюю пару).
Так fine/persist метаданные не теряют связь и не меняют UID принимающей реки.
Приёмник-река допустим только при подтверждённой цепочке до бассейна, без циклов.
Requests упорядочиваются по зависимостям terminal target на путь другой реки;
неудача родителя не отменяет независимые объекты. Один pre-bed snapshot,
один relief writer; новые application helpers только читают/готовят данные.
Для неверного типа object_type=None, rejected_connection_type: str сохраняет
невалидный вход (осознанное исключение, не игровой enum); INVALID_CONNECTION_TYPE
не допускает fallback. requested_receiver_uid отделён от authored mouth, reason
сохраняет исходный отказ, fallback_reason — причину неудачи поиска. Поиск
переименовывается в riverRouteSearch, диагностический POJO остаётся riverRouting.
Геометрические helpers требуют явную policy; тесты передают POJO defaults.
Порядок: контракты → receivers/search → requests/prepare → coarse/fine callers →
регрессии → документация/отчёт. Новые файлы в рамках этой ответственности:
dataModel/hydrology/riverDrainageLink.py, rivers/riverReceivers.py,
riverRouteSearch.py (rename), riverRequestOrder.py и round2 regression suite.
Геометрический prepass сохраняет future-river target до snap и не создаёт claims.
В рамках слияния riverDrops читает итоговый пол terminal bed; assembler передаёт
подтверждённые claims, чтобы факты перепадов включали границу приток → река.

- **Цель:** убрать двусмысленности uid/роли, довести диагностику до полного
  контракта R-3/log, закрыть crash-границу и гигиенические пункты.
- **ТЗ:** `tz_terrain_hydrology` § реки; решения Q-1…Q-5.
- **Файлы:** `rivers/{riverRouteRequests,riverRouting,riverPrepare,
  riverRouteDiagnostics,resolveDeclaredRiverPath}.py`,
  `dataModel/hydrology/riverRouting.py`, `dataModel/hydrology/declaredRiver.py`
  (при Q-1), `riverNetworkAssembler.py`, `riverNetworkPlanner.py`,
  `terrain/passes/surfaceTerrainContext.py`, `shore/fineHydrologyIndex.py`,
  `geom/smoothRiverPolyline.py`, routing tests.
- **Контракт:** по решениям Q-1…Q-5; R-1-принцип распространить на policy
  (явный параметр или осознанный canonical default с пометкой);
  BLOCKED-источник → отличимый код; mouth-snap/target_uid — typed поле,
  не перегруженное `location_uid`; коэрция kind — per-river отказ;
  non-null topology в context — явная проверка, не негласный инвариант.
  По решённому Q-1: разделить authored location UID и разрешённый UID
  принимающего тела, не путать исходную цель с фактическим fallback-приёмником;
  не отключать часть is_river_mouth передачей пустого surface_z.
  По решённому Q-3: ошибка типа изолируется на уровне объекта начиная со
  сборки request, без подстановки типа и без частичной материализации.
  По решённому Q-2: разрешить терминальное слияние отдельной реки-притока
  с принимающей рекой, явно сохранить связь UID, исключить циклы стока;
  транзит через чужое русло запрещён, атомарность сохраняется для каждого
  объекта. До кода инвентаризировать существующие POJO речных связей и
  тип приёмника: текущий BasinKind в diagnostic не представляет реку.
  Не подменять реку озером/морем и не вводить raw поля вместо typed-контракта.
  По решённому Q-4: вернуть `RECEIVER_METADATA`, если fallback не завершён
  именно из-за отсутствующих метаданных достижимого приёмника; не логировать
  каждый отвергнутый кандидат и не терять причину исходной попытки.
- **Проверка:** unit — intent устье на auto-теле (Q-1/Q-2 кейс), невалидный
  kind → диагностика без падения прохода, source-on-bed код, receiver
  metadata, mode parity; регрессия routing/depth/topology suites.
  Q-2: река → река → водоём; запрет транзитного пересечения и цикла;
  отказ притока не отменяет успешную принимающую реку, её русло/UID
  в точке слияния сохраняются.
  Q-4: достижимый приёмник без метаданных даёт `RECEIVER_METADATA`;
  недостижимый кандидат сам по себе не даёт эту причину; корректный
  альтернативный приёмник позволяет успех, отдельных логов кандидатов нет.
  Q-1: location UID отличается от auto body UID — исходный маршрут принят
  без ложного WRONG_BODY/redirect; roleless waterline использует surface_z.
  Q-3: невалидный тип на стадии request и на стадии profile даёт диагностику,
  не обрывает соседний корректный объект и не оставляет частичного русла.
- **Done:** находки R2-1…R2-12 закрыты или зафиксированы как контракт.


**Отчёт шага 7 (2026-10-22).**

- R2-1/2: authored HydrologyMouth.location_uid не подменяется water UID;
  requested_receiver_uid хранится отдельно, roleless mouth query читает реальный
  surface_z. Auto-тело в named location принимается без WRONG_BODY/redirect.
- R2-3: frozen RiverDrainageLink + river_type сохраняет явный сток в результате
  и MapCellHydrology. Geometry-only prepass не даёт claims; порядок requests
  разрешает terminal зависимости. Только принятые профили резервируют русло.
  Цепочка до бассейна обязательна, циклы отклоняются; терминальное слияние
  сохраняет дно/UID приёмника, транзит запрещён. Факты перепадов учитывают
  итоговый пол принимающей реки. Неудачный приток не отменяет stem.
- R2-4: policy обязательна для обоих геометрических planner helpers,
  отсутствующая/None policy — TypeError; defaults читают из POJO на caller.
- R2-5/6: единый source_failure и is_runtime_river_context; blocked source
  даёт INVALID_SOURCE/BLOCKED без бессмысленного поиска. Условия sink/fallback
  зеркальны. Реального третьего ResolveMode не было; отдельный режим не введён.
- R2-7: поиск возвращает самостоятельный fallback_reason. RECEIVER_METADATA
  отражается только при достижимом неполном кандидате и отсутствии корректной
  альтернативы; исходный reason сохраняется, отдельных логов кандидатов нет.
- R2-8: неверный тип изолирован с request construction до profile boundary;
  object_type=None и rejected_connection_type сохраняют отказ без подстановки.
  Остальные coarse/fine объекты продолжаются, частичных profiles/claims нет.
- R2-9/10: явный WorldTopology gate перед relief в surface context;
  application riverRouting переименован в riverRouteSearch, POJO имя сохранено.
- R2-11/12: пояснён isclose как компенсация float acos, waypoint без лишнего
  int(), sentinel claims заменены реальными POJO drainage. UID lookup не создаёт
  выбрасываемый request; edge/intent подготовка разделена; initial_failure
  предшествует source validation, one-cell boundary без профиля явно описан.
  diagnostic_cell остаётся адаптером координат на границе request/diagnostic.
- R2-13: ancestry-walk O(depth) и directed approach states явно описаны в search
  docstring; бюджет берётся из policy, отдельная оптимизация не заявляется.

Проверки: **515 tests OK** — hydrology/declared rivers/placement/bathymetry/
terrain/relief/topology/pack bake/DET-1; новый round2 suite — **22 tests**.
Предварительный расширенный прогон: 512 OK; после уточнения policy gate и
confluence drops финальный набор 515 OK. Sandbox прогон остановлен на прежнем
ограничении temporary SQLite; разрешённый прогон вне sandbox прошёл. Старые
позитивные roleless fixtures дополнены WaterBody, ocean fixtures — UID;
инвариант проверяется полноценными метаданными вместо выдуманного приёмника.
compileall app и git diff --check — OK. Backend/HTTP не запускались;
коммит агентом не создавался. HY-7/9/10, HY-RIV-1, HY-WF-1 и W/L не закрываются
этим review-debt. План перенесён в -done; старый адрес оставлен указателем для
установленного skill, canonical SoT — этот завершённый файл.

## Порядок

1 (контракт topology, блокер для 4) → 2 (модуль/политика) → 3 (assembler
seam) → 4 (fine carve, зависит от R-2) → 5 (POJO, независим) → 6 (документы,
в конец — после решений R-3/R-4).

Решения R-1…R-6 зафиксированы выше, default допуска — 200 world-fine cells.
Шаги 1–7 выполнены; review-debt этого плана закрыт 2026-10-22.
Исходные шесть шагов сохранены; согласованный раунд 2 выполнен отдельным шагом 7.
