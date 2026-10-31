# SPATIAL-1 — Пространственное распределение сред и материалов

Статус: **архитектурный план / OPEN**. Направление и границы ответственности согласованы 2026-10-31; конкретные классы, POJO, контракты публикации, world ambient policy и production wiring требуют отдельной приёмки. Сам факт наличия плана **не разрешает реализацию или cutover**.

**Родитель и первый интеграционный трек:** [GEO-1 Designed Water](./geo-1-designed-water.md), G10-A. Обратная ссылка из GEO-1 обязательна. План общий для разных доменов, но первым доказательным потребителем является hydrology. Не переименовывать этот план в GEO-подзадачу, не внедрять generic domain внутрь hydrology. Aerial A4 остаётся OPEN и связанным вопросом, не закрывается записью этого плана.

**Профильные ТЗ:** [Materials](../../docs/tz_materials.md), [Hydrology](../../docs/tz_terrain_hydrology.md), [Aerial](../../docs/tz_aerial.md), [Terrain Generation](../../docs/tz_terrain_generation.md), [World Pack](../../docs/tz_world_pack_storage.md), [World State CRUD](./world-state-crud-transition.md), [Layer Boundaries](../rules/layer-boundaries.mdc), [DAG interface](../rules/dag-generator-interface.mdc). При расхождении технической идеи с утверждёнными ТЗ/кодом фиксировать расхождение как OPEN, не молча переписывать доменную семантику.

## 1. Цель и не-цель

Цель: представлять достоверно рассчитанные пространственные факты компактно, выдавать их по ограниченному XYZ-окну и материализовать запрошенные области на L2, не выделяя все объёмные клетки мира заранее. Общая **абстракция пространственного чтения**, разные реализации и владельцы фактов: вода, руды/порода, локальные газы. Мир может не иметь атмосферы. Материал из material_registry может существовать в каталоге, но отсутствовать в пространстве.

Не-цели: новый универсальный solver материалов; новая жидкостная/газовая физика; замена hydrology fill/spill/merge/routing; новый HY-RIV-1 source search; редизайн DAG; обязательный full-world L2; введение параллельного storage/snapshot или MaterialRegistryV2; silent fallback air; утверждение новых POJO до аудита.

Ключевое разделение: **подготовка истинных domain facts → пространственное чтение готовой revision → композиция и L2 представление → существующий persist**. Нельзя считать универсальный способ чтения универсальным способом расчёта физики.

## 2. Владение ответственностями

| Владелец | Что рассчитывает/публикует | Чего не делает |
|---|---|---|
| Materials | Каталог solid/liquid/gas, material identity, свойства, подготовку требуемых характеристик; правила совместимости/смешения material types — по профильным ТЗ | Не утверждает наличие материала во всех координатах по факту его регистрации |
| World environment (owner/POJO OPEN) | Явно определённую фоновую среду мира/области: vacuum либо ambient medium/composition | Не объявляет air при missing/unresolved, не генерирует геометрию водоёмов |
| Terrain / Relief | Frozen natural geometry, solid/caves, принятые абсолютные basin/river bed heights, точную bounded-window выдачу | Не решает, какая жидкость заполняет бассейн |
| Hydrology | Wet footprint, body/system UID, water levels, spill/merge, route/receiver/shore, source mapping и полноту fine coverage | Не реализует движение жидкости по тикам, смешение разных liquid material, обычный pack writer |
| Geology / ores (будущее) | Залежи, состав/замещение породы | Не управляет open-water уровнями |
| Gas distribution (будущее) | Локальную геометрию/концентрацию дополнительных газов и её текущие факты | Не определяет свойства gas materials; не подменяет runtime physics |
| Spatial Distribution (общий интерфейс) | XYZ query, точное membership и coverage, bounded typed slices, provenance/revision, возможный spatial index | Не вызывает генераторы, не выбирает material priority, не симулирует жидкости/газы |
| Runtime physics + world state | Физические изменения, material transitions, tick-based movement; принятые изменения через world-state mutation/snapshot/patch | Не мутирует immutable planning sources за спиной reader |
| Application L2 composition/materialization | Согласует готовые solid/liquid/gas/ore факты по явно утверждённой policy и готовит конечный chunk/column records | Не дублирует hydrology/ore/gas algorithms |
| DAG / bake / caller | Когда вызывать публичные domain operations, какие окна запросить и когда materialize | Не импортирует детали kernels и не самостоятельно «решает» water/ore/air |

Тонкие planning providers только require/ref-binding и делегирование. В generic reader нет SQL, pack I/O, lifecycle orchestration или кэша живых чужих jobs. Domain physical rules принадлежат доменным исполнителям; generic composition policy не может скрыто считать density/viscosity/pressure или пересортировывать ownership.

## 3. Концептуальный интерфейс — не утверждённые классы

Предварительное имя: SpatialFieldReader[T].

- read_window(window) -> SpatialSlice[T] — **одна содержательная read-only операция**.
- Один подготовленный immutable source/index на корректную revision; многие независимые окна. Никаких prepare/fill/simulate/persist в generic interface.
- Вход: XYZ-область в явно названном coordinate space и topology, возможно union disjoint windows. AABB — быстрый индекс кандидатов, **не** доказанное фактическое покрытие.
- Выход: typed domain facts, доказанная coverage/unknown, source provenance и верифицируемый revision binding; гарантированная детерминированность и независимость от разбиения окон.
- Внутри доказанной coverage отсутствие объекта может быть dry/empty; за пределами coverage отсутствие записи означает unknown. Нужно различать «нет solid», «нет жидкости», «нет газовой среды» и «неизвестно».
- Не предписывать всем реализациям один material-per-voxel payload. Для воды возможны точные XY footprints + bed/water surface; для underground/gas — несколько Z-intervals/компонентов; для ores — composition/replacement. Качество контракта проверяется этими разными типами, а не абстрактной интеграцией dict.
- Prepared PlanRef нельзя принудительно применять как единственный version тип runtime gas/snapshot. Общее поле provenance должно явно связывать bootstrap source и изменённое состояние мира. Lifetime/index/cache eviction не скрывают устаревшие reads.
- SpatialWindow / SpatialSlice / WaterSpatialReader / GasSpatialReader / OreSpatialReader / SpatialIndexJob — **рабочие имена**, а не разрешение на классы. До проектирования новых POJO проверить RegionCoverage/CoverageSpan, GridBBox, FineSurfaceWindow, TerritoryVolume, PreparedNaturalTerrain, WaterBody/MaterializedWater, PlanEnvelope/PlanRef, FineTerrainZRun. Не использовать location-specific TerritoryVolume как общую семантику без отдельного обоснования.
- Generic read не должен превращаться в materializer. Materialization/composition — отдельная app-level ответственность, если такой слой действительно необходим; не делать его внутри provider/planner или внутри гидрологии.

## 4. Точная интеграция с гидрологией — PRODUCER SEAM

**Решение по точке подключения:** hydrology-owned пространственный read adapter строится **от уже опубликованных, согласованных финальных hydrology facts**, после water + routes + river relief + final, а **не** вызывается из water solver/routing. В коде конкретный publication seam — результат GeoHydrologyFinalPlanProvider.build, собираемый HydrologyFactsAssembler. Источник должен иметь evidence также из native fine-water и actual fine beds той же revision. Adapter/index имеет своего владельца в hydrology, реализует общий read contract. Это архитектурная точка, **не утверждённое имя нового файла/класса**.

Проверенная карта current master (2026-10-31, до production GEO cutover):

| Шов | Точный класс / файл | Фактическое состояние и требование |
|---|---|---|
| Native fine water | [FineWaterJob.fill](../../backend/app/application/worldData/generators/hydrology/water/planning/fine/execution.py), [FineWaterPublicationJob.publish](../../backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py) | Exact pre-water/placement ref; полная fine terrain evidence; basin carve → physical water; FineWaterResult = post-basin FineSurfaceWindow + AssembledWater/MaterializedWater. Нельзя заменить solver локальным read |
| Native fine routes | [FineRiverPublicationJob.publish](../../backend/app/application/worldData/generators/hydrology/rivers/planning/fine/publication.py) и [FineRiverJob.plan_fine](../../backend/app/application/worldData/generators/hydrology/rivers/planning/fine/execution.py) | Требует точную fine-water revision. Отдельные rejected routes могут оставлять diagnostics; наличие envelope ≠ все intended routes приняты |
| Текущий основной GEO routes | [HydrologyRoutesAssembler.assemble_geo](../../backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyRoutesAssembler.py) | **Пока вызывает WaterBodyPlanner.plan_geo(coarse surface_z), затем coarse/fine legacy routes**, а не native FineWaterPublicationJob → FineRiverPublicationJob. Это G10-A cutover blocker, не обходить новым spatial adapter |
| River relief | [RiverReliefPlanProvider](../../backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py) + RiverReliefPlan | Принятые actual bed heights; перед final должен быть exact route/relief ref join, не реконструировать river bed через старую L2 маску |
| Финальная сборка | [HydrologyFactsAssembler.assemble](../../backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py) | Current fine = _river_roles(...) — **open-water occupancy native fine здесь не объединена**. Текущие sparse_fine_hydro/fine_z_overrides не доказательство полного wet/dry. Вынести в GEO работу по canonical final source, не создавать «правду» в reader |
| Финальная публикация | [GeoHydrologyFinalPlanProvider.build](../../backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py) | Require exact relief/routes/river-relief/water-placement refs и публикует GeoHydrologyPlan. Это source revision anchor reader; provider не должен индексировать геометрию или вызывать новые генераторы |
| Current consumer-index | [HydrologyWorkingFields.from_plan](../../backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py) | Indexed coarse + sparse fine по tile. **Не готовый WaterSpatialReader**: отсутствуют полная native open water, Z-volume, точная evidence coverage; working maps сами по себе не несут PlanEnvelope provenance |

**Блокер SP-H1 (обязателен до первого reader):** завершить предусмотренный GEO-1 G10-A маршрут native fine water → native fine routes → actual river relief → canonical final facts и явно сохранить fine open-water wet/dry, UID/уровень, берег, исходную/финальную bed geometry, source_mapping и диагностику в согласованном контракте. Точную форму POJO/PlanSlot/версионирования определить в GEO-1; нельзя сохранять только coarse маску и маркировать fine dry.

**Блокер SP-H2 (river volume):** [riverBedProfile.river_bed_roles](../../backend/app/application/worldData/generators/hydrology/rivers/riverBedProfile.py) маркирует RIVER_BED и UID, но не полную water surface z для водной толщи. Без гидрологически утверждённого z_water(x,y) речной volumetric query не имеет права выдать слой жидкости «по догадке». Open-water lakes/seas и river-volume activation разделить; HY-RIV-1 source search сюда не затягивать.

**Блокер SP-H3 (physical geometry):** bed height должен совпадать с frozen natural terrain и accepted basin/river relief после всех разрешённых геометрических операций. [NaturalWindowJob.materialize](../../backend/app/application/worldData/generators/terrain/planning/preWater/prepared/materialization.py) выдаёт natural-only FineSurfaceWindow; его нельзя автоматически трактовать как after-water/after-river solid geometry. Нужен подтверждённый состав final overlay и proof одного source revision. Планируемые L2 grade edits, меняющие дно, требуют authority/invalidation decision, а не silent пересчёт воды в generic adapter.

Гарантия integration seam: hydrology остаётся единственным владельцем water UID/wet connectivity/levels и source mapping. Spatial implementation лишь предоставляет **готовое** по запросу и никогда не повторяет flood, spill, route, carve или классификацию источников.

## 5. Точная интеграция с L2 — CONSUMER SEAM

**Место подключения к существующему пути:** [FineChunkRunner.refine_rects](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkRunner.py) → [fineTilePrep.prepare_fine_tile](../../backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py) → [fineChunkCompute.compute_rect](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkCompute.py) → [FineChunkPersist.persist_rect](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkPersist.py).

- На входе existing materialization job должен иметь **готовые** exact source refs/indexes для нужного мира и revision. Resolve/validate prepare делается на planning/application boundary **один раз на source revision**, не в каждой tile/chunk worker. Нынешний fineTilePrep получает SurfacePlanBundle + SurfaceWorkingMaps и строит полный tile state при любом маленьком rect: это **старый путь**, а не место для повторения подготовленного native GEO solve.
- **Конкретная worker точка:** FineChunkCompute.compute_rect, после existing discover_and_paint/grade local geometry и до выпуска ChunkComputeResult.cells на persist. Здесь можно вызвать ограниченный read_window и доменно-нейтральную L2 composition operation, **только** над готовыми indexed sources и согласованной geometry. Сам compute_rect не вычисляет гидрологию, не создаёт отдельный stage-пайплайн и не читает всю ревизию/мир.
- Solid column generation сейчас идёт через TerrainBatchOrchestrator.generate_chunk_cells_sync → TerrainGeneratorService.generate_surface_chunk → columnFillPass.run_column_fill. Generic water/gas/ore logic **не** внедрять в эти terrain kernels. Граница composition должна принять готовую solid geometry/cells и typed slices после окончательных локальных grade изменений, либо отвергнуть геометрическое несоответствие.
- FineChunkPersist и WorldPackWriter сохраняют ответственность только за запись и атомарность. Планировочный provider и generic spatial reader не получают SQL/pack write.
- **Проверенный type mismatch:** [GeoSurfacePlanBundle](../../backend/app/application/worldData/planning/contracts/surfacePlanBundle.py) существует отдельно от SurfacePlanBundle, а текущий fineTilePrep принимает SurfacePlanBundle. До GEO/L2 wiring обязательно выбрать стабильную публичную границу, не пытаться подсунуть GEO bundle через cast/kwargs.
- **Pack output blocker:** [FineTerrainZRun](../../backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py) имеет один system_material на run, нет water_body_uid, hydrology role, level или composition. [mapCellToFineTerrainWire._compress_z_runs](../../backend/app/application/worldData/pack/read/mapCellToFineTerrainWire.py) группирует по terrain/material/z и **не переносит MapCell.hydrology**. Поэтому даже подготовленная вода может потерять identity при persist. До L2 cutover выбрать и утвердить сохранение гидрологических объёмных facts (отдельный sidecar или изменение wire/другой контракт), без слепого утверждения, что existing FineTerrainZRun уже подходит.
- Не выполнять всё вышеперечисленное в рамках G10-A без самостоятельной приёмки: G10-A сначала доказывает natural/fine-water/final geometry, SPATIAL-1 — read/composition и отдельный L2 consumer activation.

## 6. World environment, liquid и gas — профильные границы

В [tz_materials.md §4](../../docs/tz_materials.md) пока действует правило «пустая клетка -> air из material_registry», а [tz_aerial.md](../../docs/tz_aerial.md) считает aerial air implicit void для v1 и оставляет A4 (water/air volumetric layer) OPEN. Это **предмет исправления ТЗ/контракта**, не готовое свойство кода. Не подставлять обычный воздух на world без атмосферы.

Разделить: free of solid; explicit vacuum (отсутствие среды); material key air; ambient world/region/room environment; локальное распределение smoke/steam/toxic gas. Наличие air в registry не устанавливает атмосферу: на airless planet тот же материал может заполнять sealed room. Missing configuration ≠ explicit vacuum и ≠ fallback air; требуется согласованный unresolved/compat/migration режим. Вода может занимать часть воздуха; ore заменяет состав solid, а не обязательно конкурирует с водой в том же смысле. Multi-gas mixtures/concentration — OPEN: существующий один system_material на run не выражает смесь.

Materials определяет density/viscosity, heat/cool refs и условия материала; climate и runtime physics используют их. Tick flow/diffusion/pressure, изменения состава и смешение разных жидкостей не выполнять generic reader. Нужен отдельный владелец composition policy/совместимости и явная диагностика при неразрешимом overlap. Не вводить порядок water>ore>air.

## 7. Revision, состояния мира и объём работы

- Bootstrap: frozen PlanEnvelope/PlanRef + точные upstream dependencies, deterministic prepared index. Не держать live job, mutable world registry, callback, SQL connection внутри опубликованного payload.
- Runtime: одобренные world-state CRUD → patches/snapshots → актуальный world state. Связь с bootstrap revision и invalidation затронутых spatial volumes — открытый контракт. Не считать отсутствие patch автоматическим доказательством актуальности подготовленного индекса.
- Materialization: union запросов XYZ + обоснованные algorithm dependencies/halo, без расширения к одному giant bbox по умолчанию; wrapped/sphere topology seams сохранить. Coverage proof + dry/unknown semantics и контроль stale index.
- Initial fine-water physical solve сейчас требует полный fine terrain world (FineWaterJob validates complete canonical coverage); новый reader НЕ обещает отмены этой стоимости. Сравнивать **отдельно** cold prepare и warm localized query, allocations, feature visits, cache/pack/SQL I/O. Маленький read_window не может вызвать full-tile host/map creation, пересборку depression tree, full hash/copy, per-cell SQL.

## 8. Последовательный план работ и блокировки

Каждый шаг требует анализа, контракта, тест-кейсов и явной приёмки до следующего. Не запускать несколько шагов агента одним большим рефакторингом.

| ID | Шаг | Входной gate и критерий выхода |
|---|---|---|
| **SP-0 — аудит (только анализ)** | Инвентаризация existing spatial/coverage/material/PlanRef/WorldState/pack POJO и full caller map; особенно заглянуть в GeoHydrologyPlan/FinalProvider, FineWaterResult, HydrologyWorkingFields, fineTilePrep, FineChunkCompute и сериализатор. Открытые решения записать, **код не менять** |
| **SP-1 — общий контракт (архитектура)** | После SP-0 выбрать minimal read_window signature, scoped coverage/unknown/provenance, coordinate/topology/XYZ format, typed fact vs interval model; правило один source/index → много окон; при необходимости разделить read и materialization; запрет лишних POJO |
| **SP-2 — world ambient/material composition (архитектура)** | Назначить владельца фоновой среды и режима vacuum, unknown/migration; решать газовые mixtures, liquid-gas-solid и ore composition отдельно. Проверить tz_materials §4, tz_aerial A4, правила материалов; не делать universal physics |
| **SP-H — GEO producer proof (владелец GEO-1, prerequisite)** | G10-A production wiring: native fine water → native routes → accepted river relief → final, exact source revision и полный fine wet/dry/UID/level/shore/bed/mapping. Не реализовывать spatial reader поверх incomplete final |
| **SP-3 — hydrology reader (после SP-1 + SP-H)** | Hydrology-owned immutable prepared/index от final published facts и final geometry; точные bounded open-water queries, dry/unknown; никакого hydrology solve в read. River volume только после SP-H2 river water surface contract |
| **SP-4 — L2 contract + consumer (после SP-2 + SP-3 и отдельного согласования)** | Вход source refs/readers в FineChunkRunner context один раз, локальный read+composition в FineChunkCompute после grade geometry, доказанный persisted hydro UID/level output; FineChunkPersist остаётся writer; первая активация только после golden и pack/read replay |
| **SP-5 — другие домены (вне GEO-1)** | Gas distributions/ore replacement используют тот же query; проверить отсутствие интеграции чужой физики. Реализация по отдельным доменным планам, не условие завершения G10-A |

Детали SP-1/SP-2 **не считать утверждёнными**, пока не будет явной архитектурной приёмки. SP-H — зависимость, а не разрешение на тихую подмену существующего GEO-1 плана. DAG/engine nodes не менять по этому плану.

## 9. Приёмка и негативные сценарии

1. Один frozen source, полное reference окно и union маленьких окон дают те же wet/dry/unknown, UID, уровни, actual floors, shores/deepening, source mapping; provenance идентичен, не теряется на seams и holes.
2. Отдельно доказаны distinction между no-solid, dry, vacuum, ambient air, local gas и unknown; одинаковый material registry с air годится и для атмосферного, и для безатмосферного мира; sealed-room air не заполняет всю планету.
3. Система отказывает при mixed-revision natural/water/river-relief/patch; не использует L0 corridor как доказательство full fine wet; не создаёт реки с неизвестным z_water(x,y).
4. Закрытые/открытые бассейны, острова, negative coordinates, wrapped/sphere seams, disjoint windows; overlap solids/liquids/ore/gases с ясно определённым исходом либо отказом.
5. L2 после grade changes не публикует воду с противоречащим дном без правила reconciliation; pack/read round-trip сохраняет hydrology UID и прочие обязательные facts, не только material key.
6. Во время read_window нет повторного fill, routing, selection, depression-tree, пересборки индексов и полного tile/мира на малый запрос; zero SQL/pack I/O per cell, измеримая bounded cost.
7. Тесты агента — вспомогательная проверка контрактов, не самостоятельное доказательство функциональной корректности. Нужны независимые golden/reference и ручная архитектурная проверка на границы ответственности.

## 10. Открытые решения

- Где именно owning World Environment POJO и default/migration, в том числе явный vacuum, room/local overrides и multi-gas atmosphere?
- Какой общий результат оптимален: типизированные domain observations или material-filled XYZ intervals; допускается ли один тип для water, ores, gas без скрытой arbitration?
- Как связать bootstrap PlanRef и runtime state revision, не меняя generic read в world-state write service?
- В каком hydro final POJO/PlanSlot публикуется exact native fine open-water coverage и actual final waterbed evidence после river relief? Как не дублировать исходные данные?
- Кто владеет river surface profile z_water(x,y) и какова его семантика на водопадах/устьях?
- Какой L2 output contract сохраняет water UID/role/level, если FineTerrainZRun сейчас не умеет; нужен ли новый sidecar, version bump или иной доступный существующий wire?
- Как согласовать L2 grade/terrain edits с hydrology waterbed и snapshot/patch invalidation без локального пересчёта мировых water systems?
- После SP-0 определить, нужен ли вообще отдельный application package общего интерфейса либо достаточно shared contract и domain-owned implementations. Не создавать самостоятельный orchestrating «бог-домен» по умолчанию.

## 11. Definition of Done для архитектурной стадии

Только когда согласованы: минимальный typed shared contract, POJO reuse, источник truth и placement read seam после final hydrology, точное место L2 consumer, ambient/vacuum policy, composition policy owner, plan/runtime revisions, форма корректного serialized output, негативные доказательства и cost budget. Операции и API остаются в собственных слоях; новую физику/оркестрацию внутрь интерфейса не добавлять. На текущей дате **SP-0/1/2/3/4/5 и SP-H остаются OPEN**. GEO-1 G10-A, final coverage и Aerial A4 не объявлять завершёнными.

Изменения этого документа: planning only, без production code, POJO, migrations, tests, schema или runtime cutover.
