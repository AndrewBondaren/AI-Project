# SPATIAL-1 — Пространственное распределение сред и материалов

**Актуальная приёмка 2026-11-02:** пользователь явно принял документальные SP-1
(scope §14.12), GEO EF-1 (scope EF-1.12) и GEO-SPATIAL-CONTRACT. Запись и исключения
— §14.14. Исторические НА ПРИЁМКЕ/OPEN этих трёх результатов ниже заменены этой
приёмкой; storage/implementation/runtime и остальные треки не приняты.

**Межплановые зависимости:** [WORLD-PLAN-GRAPH-1](./world-generation-plan-dependency-graph.md) — навигационный граф gates GEO/SPATIAL/GEN-DAG/Patches/DAG-TYPING/PHYSICS; нормативные контракты и статусы остаются в этом owning-плане.

## Порядок принятия контракта

**Сначала семантические инварианты → обоснованное представление и цена/качество
→ точные POJO/enum и файлы → отдельное разрешение на реализацию.** Freeze до кода
обязателен; freeze физических source-полей до выбора представления не требуется.

Этот план — нормативное место generic read (§3), spatial representation/Pack
(§7), materialization (§5/12) и их собственной контрактной приёмки. Hydrology
output описывается только в [GEO-1, начале плана](./geo-1-designed-water.md);
конкретные ноды/оркестрация — только в [GEN-DAG-1](./gen-dag-1-post-geo-ws.md).
[Соответствие, порядок freeze и пути — §13](#13-соответствие-контрактов-и-порядок-freeze).
Не копировать одну спецификацию POJO между планами. SPATIAL — общий контракт,
Hydrology реализует собственный reader/index. Shared exact freeze SP-1 принят
документально в scope §14.12; остальные owning freezes сохраняют собственные gates.
Эта запись не является разрешением на реализацию SPATIAL или DAG.

**Совместный domain/read контракт с GEO-1 принят документально** (§14.14):
A/R1/G1, дорогая однократная preparation допустима, bounded read без повторного
solve. Exact source — GEO EF-1; storage/materialization/reader implementation
остаются SP-P0/SP-M/SP-3/SP-4 по своим gates. Это не приёмка production evidence.


Статус: **архитектурный план / OPEN**. Направление и границы ответственности согласованы 2026-10-31; конкретные классы, POJO, контракты публикации, world ambient policy и production wiring требуют отдельной приёмки. **Обязательный трек SP-A0/A1/A2 — переработать существующие air policy и настройки World, а не только добавить новый reader.** Сам факт наличия плана **не разрешает реализацию или cutover**.

**Родитель и первый интеграционный трек:** [GEO-1 Designed Water](./geo-1-designed-water.md), G10-A. Обратная ссылка из GEO-1 обязательна. План общий для разных доменов, но первым доказательным потребителем является hydrology. Не переименовывать этот план в GEO-подзадачу, не внедрять generic domain внутрь hydrology. Aerial A4 остаётся OPEN и связанным вопросом, не закрывается записью этого плана.

**Отдельный будущий трек физики:** [PHYSICS-1 — Физическая эволюция пространственных сред](./physics-spatial-dynamics.md). SPATIAL-1 отвечает за то, что/где/как расположено в принятом состоянии, а Physics — за изменение: агрегированные упрощённые pressure/displacement/mixing/propagation и более детальную физику с полной **локальной** материализацией рядом с игроком. Оба режима Physics вне реализации SPATIAL-1; точные алгоритмы и переход между режимами OPEN. Generic spatial read остаётся read-only.

**Профильные ТЗ:** [Materials](../../docs/tz_materials.md), [Hydrology](../../docs/tz_terrain_hydrology.md), [Aerial](../../docs/tz_aerial.md), [Terrain Generation](../../docs/tz_terrain_generation.md), [World Pack](../../docs/tz_world_pack_storage.md), [Domain Patches & Snapshots](./world-domain-patches-snapshots.md), [World Snapshot](../../docs/tz_world_snapshot.md), [Layer Boundaries](../rules/layer-boundaries.mdc), [DAG interface](../rules/dag-generator-interface.mdc). При расхождении технической идеи с утверждёнными ТЗ/кодом фиксировать расхождение как OPEN, не молча переписывать доменную семантику.

## 1. Цель и не-цель

Цель: представлять достоверно рассчитанные пространственные факты компактно, выдавать их по ограниченному XYZ-окну и материализовать запрошенные области на L2, не выделяя все объёмные клетки мира заранее. Общая **абстракция пространственного чтения**, разные реализации и владельцы фактов: вода, полная геологическая толща (почва, глина, породы, рудные включения), локальные газы. Мир может не иметь атмосферы. Материал из material_registry может существовать в каталоге, но отсутствовать в пространстве. **Чтение общее, политика материализации различается:** жидкости/газы допускают временные оконные проекции без обязательных клеток; геология по требованию даёт полноценную физическую solid-материализацию, в том числе вновь обнажённых поверхностей при раскопке.

Не-цели: новый универсальный solver материалов; новая жидкостная/газовая физика; замена hydrology fill/spill/merge/routing; новый HY-RIV-1 source search; редизайн DAG; обязательный full-world L2; введение параллельного storage/snapshot или MaterialRegistryV2; silent fallback air; утверждение новых POJO до аудита.

Ключевое разделение: **подготовка истинных domain facts → пространственное чтение готовой revision → композиция и L2 представление → существующий persist**. Нельзя считать универсальный способ чтения универсальным способом расчёта физики.

## 2. Владение ответственностями

| Владелец | Что рассчитывает/публикует | Чего не делает |
|---|---|---|
| Materials | Каталог solid/liquid/gas, material identity, свойства и исходные характеристики/ограничения совместимости для других доменов | Не утверждает наличие материала во всех координатах по факту его регистрации и не рассчитывает фактическое смешение, перемещение или пространственное распределение |
| World / World Environment (доменный владелец принят; POJO/settings OPEN) | Объявляет, существует ли планетарная/мировая атмосфера, её базовый состав и ambient/vacuum policy как исходные условия мира; хранение и разрешение typed per-world settings, локальные overrides после SP-A | Не вычисляет климат/погоду, не симулирует движение и локальное распределение газов, не делает `air` из пустоты или одного registry key |
| Climate (потребитель World Environment) | Вычисляет temperature/rainfall/climate fields и профильные производные процессы по своим контрактам, используя объявленные World Environment условия там, где они нужны | Не объявляет существование атмосферы или её исходный состав, не подставляет air/vacuum при отсутствии world policy и не владеет локальной gas distribution |
| Terrain / Relief | Frozen natural geometry, solid/caves, принятые абсолютные basin/river bed heights, точную bounded-window выдачу | Не решает, какая жидкость заполняет бассейн |
| Hydrology | Bootstrap/producer-факты воды: wet footprint, физические body/union UID, начальные/effective уровни, spill/merge, route/receiver/shore, source mapping и полноту fine coverage; **runtime** — по вызову DAG принимает типизированный запрос, выведенный Physics, проверяет/подготавливает доменное изменение canonical water facts/footprint для Snapshot | Не вычисляет tick-based течение/распространение, не принимает физическое решение вместо Physics, не владеет W/L lifecycle, не мутирует SpatialSlice или pack и не публикует patch самостоятельно |
| Water Systems / Lifecycle (W/L) | Долговременная identity/lifecycle объектов и систем, активное membership, merge/split-преемники, primary и каскад системного уровня; метаданный consumer гидрологических фактов | Не рассчитывает wet geometry/fill/river bed и не материализует/не пишет клетки; не вызывает Hydrology скрыто внутри consumer |
| Geology / strata / ores (будущее) | Пространственный состав твёрдой толщи: почва, глина, горные породы, стратиграфические интервалы и 3D-залежи/рудные включения, их material identity, точная bounded выдача | Не определяет саму solid/void геометрию, не решает водные уровни и не выполняет раскопку/строительство; существующий terrain column fill и независимый ore pass требуют отдельного аудита границы |
| Gas distribution (будущее) | Локальную геометрию/концентрацию дополнительных газов и её текущие факты | Не определяет свойства gas materials; не подменяет runtime physics |
| SPATIAL — shared typed contracts (не отдельный orchestrating-домен) | Общая read-only форма XYZ window / `SpatialSlice[T]`, типизированная передача **уже определённых доменом** фактов/отсутствия/диагностики, provenance и revision binding; реализации и подготовленные индексы принадлежат Hydrology/Geology/Gas Distribution | **Не вычисляет наличие/отсутствие материала, не доказывает покрытие своим алгоритмом**, не владеет доменными facts/SQL/pack IO, не диспетчеризует домены и не симулирует жидкости/газы |
| Runtime physics + domain changes | Физические изменения, material transitions, tick-based movement; **Physics возвращает типизированный запрос на изменение водных фактов через DAG**, а соответствующий домен подготавливает собственную секцию/patch | **Physics не вызывает Hydrology напрямую**, не меняет immutable planning sources/SpatialSlice и не публикует состояние в обход Snapshot |
| Snapshot / Patches | Атомарное принятие подготовленных изменений и истории; согласованный runtime overlay поверх базовых фактов | Не рассчитывает hydrology/geology/gas, не запускает materialization и не превращает обычный read в patch |
| World Pack / storage | Иммутабельные компактные spatial artifacts исходного bake, staged blobs/refs и доменное физическое хранение по утверждённым контрактам; SQL может держать metadata/refs/heads | Не выбирает геологический состав, water level или materialization policy; не делает per-cell SQL обязательным представлением сред |
| Application L2 composition/materialization | Раздельные режимы: (а) временная bounded-проекция liquid/gas/ambient фактов без обязательной per-cell записи; (б) физическая solid-материализация geology в запрошенной области, включая обнажённые раскопкой стены/пол/потолок; (в) обычная материализация построек/объектов по их контрактам. Композиция работает после согласования геометрии и patches | Не дублирует hydrology/geology/gas/physics algorithms, не превращает query в изменение мира и не подменяет materialization объектов одной generic media-проекцией |
| DAG / bake / caller | Единственная междоменная оркестрация: вызывает Physics по его контракту, передаёт его typed request в Hydrology через публичную доменную операцию, собирает подготовленные domain patches в PatchSet и вызывает Snapshot; также выбирает окна/materialization | Не импортирует kernels и не самостоятельно рассчитывает водную физику или водные факты |

Тонкие planning providers только require/ref-binding и делегирование. В generic reader нет SQL, pack I/O, lifecycle orchestration или кэша живых чужих jobs. Domain physical rules принадлежат доменным исполнителям; generic composition policy не может скрыто считать density/viscosity/pressure или пересортировывать ownership. **Hydrology публикует физические water facts; W/L хранит жизненный цикл и динамическое членство, но не геометрию.** Materials предоставляет свойства материала, а решение о смешении/перераспределении объёмов имеет отдельного утверждаемого владельца. Geology отвечает за состав solid, Terrain/Relief — за принятую геометрию solid/void; согласовать это с действующим `generate-surface`/`generate-ores` до cutover. **Нормативная граница атмосферы:** World Environment — поддомен World и владелец объявления/настройки фоновой среды; Climate — потребитель, Materials — владелец свойств газов, Gas Distribution — локальных газовых фактов. Отдельный самостоятельный домен Atmosphere не требуется для одного world-config; будущая сложная атмосферная динамика не передаётся Climate автоматически.

## 3. Концептуальный интерфейс — не утверждённые классы

Предварительное имя: SpatialFieldReader[T].

- read_window(window) -> SpatialSlice[T] — **одна содержательная read-only операция**.
- Один подготовленный immutable source/index на корректную revision; многие независимые окна. Никаких prepare/fill/simulate/persist в generic interface.
- Вход: XYZ-область в явно названном coordinate space и topology, возможно union disjoint windows. AABB — быстрый индекс кандидатов, **не** доказанное фактическое покрытие.
- Выход: typed domain facts и **вынесенная из доменного результата** семантика known-present/known-absent/invalid-or-unresolved (если она необходима вызывающему контракту), source provenance и верифицируемый revision binding; детерминированность и независимость от разбиения окон. SPATIAL не пересчитывает доказательство покрытия и не объявляет обязательный общий coverage POJO.
- **Отсутствие записи само по себе не универсальный verdict.** Только домен в пределах собственного принятого description/scope определяет, что оно означает dry/empty; при неполном/несогласованном description это invalid/unresolved. В обязательном gameplay read такое состояние — типизированная ошибка + ERROR (§7), не нормальное `unknown` или fallback. Не смешивать «нет solid», «нет жидкости», «нет газа» и «нет данных».
- Не предписывать всем реализациям один material-per-voxel payload. Для воды возможны точные XY footprints + bed/water surface; для underground/gas — несколько Z-intervals/компонентов; для ores — composition/replacement. Качество контракта проверяется этими разными типами, а не абстрактной интеграцией dict.
- Prepared PlanRef нельзя принудительно применять как единственный version тип runtime gas/snapshot. Общее поле provenance должно явно связывать bootstrap source и изменённое состояние мира. Lifetime/index/cache eviction не скрывают устаревшие reads.
- SpatialWindow / SpatialSlice / WaterSpatialReader / GasSpatialReader / OreSpatialReader / SpatialIndexJob — **рабочие имена**, а не разрешение на классы. До проектирования новых POJO проверить RegionCoverage/CoverageSpan, GridBBox, FineSurfaceWindow, TerritoryVolume, PreparedNaturalTerrain, WaterBody/MaterializedWater, PlanEnvelope/PlanRef, FineTerrainZRun. Не использовать location-specific TerritoryVolume как общую семантику без отдельного обоснования.
- Generic read не должен превращаться в materializer. Materialization/composition — отдельная app-level ответственность, если такой слой действительно необходим; не делать его внутри provider/planner или внутри гидрологии.
- **Материализация сред — ограниченная проекция согласованного source view**, условно `project(source_facts, snapshot_overlay, window)`: выход относится только к запросу и полностью трассируется к source/revision. Это семантическое подмножество фактов, **не** требование наследовать модель metadata/Plan POJO или делать `MapCell` из каждого газа/жидкости. Выход может быть оконным набором интервалов/составов и временным cache-only результатом; повторный запрос не должен создавать новый world-state change.
- **Geology materialization отличается от media projection:** из стратиграфических/3D inclusion facts и актуальной solid/void geometry выдаёт физические solid-ячейки/поверхности для ограниченного L2-окна. Изменившаяся после раскопки геометрия определяет, какие стороны пород стали открытыми; reader геологии не копает и не изменяет рельеф. Постройки/другие объекты сохраняют собственные физические materialization contracts.

**SPATIAL Input/Read:** определить минимальные данные и гарантии для bounded
XYZ-чтения: принятый domain source, согласованная geometry, pinned публикация,
coordinate space/topology и ограниченное окно/union; typed результат и ошибки
неполных/несогласованных данных. Hydrology реализует этот общий контракт своим
reader. Повторные generate/fill/spill/merge/routing для чтения запрещены;
source загружается из сохранённого описания по owning storage/read contracts,
а не требуется как fresh NodeOutput текущего DAG execution.

**Canonical source и materialized view — разные представления.** Нормативный
состав authoritative water facts определяется только [GEO-1](./geo-1-designed-water.md).
Materialized view — запрошенная потребителем часть этих фактов, представленная
клетками, интервалами или объёмами той же согласованной revision. Она не является
второй истиной, не изменяет исходный source и не требует раскрывать весь бассейн.
Read slice может оставаться компактным; физическое раскрытие в клетки — отдельная
materialization operation по потребности consumer (§5/12). Освобождение view не
отменяет принятые facts/patches, её повторное построение не запускает resolution.

### Принятое решение SP-1: типизированный generic-результат (2026-11-01)

- Общий read-only контракт концептуально параметризован: `SpatialFieldReader[T].read_window(window) -> SpatialSlice[T]`. Это **типизированный generic**, а не единый универсальный spatial materializer или разрешение на конкретное имя класса.
- Оболочка `SpatialSlice[T]` несёт typed facts `T`, нужную вызывающему доменную семантику присутствия/отсутствия/отказа, provenance и проверяемую привязку к исходной/актуальной revision. **Не требует общего `SpatialCoverage` или повторного вычисления coverage;** точная форма полей и reuse существующих POJO остаются SP-0/SP-1 OPEN.
- `T` — типизированные факты владельца домена: например, водные footprint/level/bed/UID, геологические strata/inclusions, локальные gas composition/volume. Домены вправе представлять факты XY-footprint, Z-интервалами и другими собственными структурами. **Не требуется общий базовый `SpatialFact` или одинаковый material-filled XYZ/one-material-per-voxel payload** для воды, геологии и газов.
- Reader не выбирает priority материалов, не смешивает среды, не выполняет density/pressure/movement, не материализует `MapCell` и не пишет в World Pack/Snapshot. Typed media projection и физическая materialization solids/objects остаются отдельными операциями с разными контрактами.
- Это **приёмка архитектурного принципа**, а не утверждение новых POJO/кода, runtime wiring, формата pack wire или закрытие всего шага SP-1.

### Принятое решение SP-1: bootstrap PlanRef и runtime publication (2026-11-01)

- **Две разные идентичности:** frozen `PlanEnvelope/PlanRef` описывает исходный подготовленный результат планирования и его upstream dependencies; существующий `WorldPublicationRef` описывает опубликованное состояние мира. Его логический world CAS — `(pack_hash, snapshot_head)`, `publication_id` защищает смену head от ABA по уже принятому Snapshot-контракту. Не подменять `PlanRef` через `snapshot_head` и не изобретать второй spatial revision store/counter.
- **Доменное чтение актуального состояния:** согласованный (pinned) опубликованный world view = immutable base Pack + overlay выбранной snapshot-линии; для обычного текущего чтения — один текущий скомпактированный overlay, без replay истории тиков. Исходные неизменённые факты сохраняют provenance планирования; изменения читаются поверх из принятого snapshot state. Историческое чтение не подменяет закреплённую версию на latest.
- `SpatialSlice[T]` должен трассироваться и к bootstrap source/provenance, и к принятой world publication/state revision. Mixed-revision facts, stale prepared index или непроверенная связь дают **типизированный отказ + ERROR для обязательного gameplay read**; диагностический unresolved допустим только для явного preview, не silent merge. **Точный вид typed binding, pinning и domain invalidation остаётся SP-0/SP-1 OPEN.**
- Domain-owned read отвечает за свои факты и согласование base/overlay через утверждённые read/storage contracts. Общий SPATIAL generic — только типизированный read interface, **не WorldStateService**, не WS-посредник и не writer; Snapshot принимает/публикует изменения, но не выбирает или материализует данные для reader. DAG решает когда вызвать доменную операцию, а не собирает её внутренние источники вручную.
- Это приёмка **принципа связывания ревизий**; не утверждены новые классы, публичные сигнатуры, payload, кэш, SQL/pack I/O или реализация snapshot adapter.

### Принятое решение SP-1: общий контракт без нового Spatial-оркестратора (2026-11-01)

- SPATIAL — **общая типизированная read-only контрактная абстракция**, а не новый самостоятельный `SpatialDistributionService` или обязательный application-посредник. Shared форма окна/`SpatialSlice[T]` может переносить доменные результаты, диагностику и provenance/revision; **общий coverage/proof POJO не является обязательным требованием**. Точный путь и reuse выбираются на SP-0/SP-1 по существующим `dataModel/spatial`, planning contracts и caller map.
- `Hydrology`, `Geology`, `Gas Distribution` и будущие владельцы **сами реализуют domain-owned readers/prepared indexes** и толкуют отсутствие/наличие в своём принятом описании мира, с учётом Snapshot. Prepared index ускоряет запрос, но **не создаёт вторую истину или отдельный coverage solver**. Общая оболочка не управляет жизненным циклом доменных источников, не держит SQL/pack I/O и не превращается в cache готовых чужих jobs.
- Application L2 отдельно выполняет ограниченную композицию/материализацию по готовым срезам; **DAG остаётся единственным междоменным оркестратором**, а Snapshot — владельцем публикации runtime-изменений. Общая форма чтения не создаёт общего физического/материального solver.
- Архитектурный выбор принят, но **конкретные модули, POJO, интерфейсы и import/call placement OPEN до SP-0**. Общий package не создаётся ради названия или новой прослойки.

### Принятое решение SP-1/SP-PACK: наличие/отсутствие определяет домен по описанию мира (2026-11-01)

- **Bootstrap:** мир и домены формируют согласованное описание; гидрология уже задаёт water facts, поверхность/уровни/маршруты и собственную семантику сухого участка. Компактный immutable Pack сохраняет принятые доменные facts/refs, **не новый ответ SPATIAL на вопрос «есть ли вода»**. Geology и Gas Distribution применяют собственные правила к своим фактам; никакой общей 3D-карты presence/absence или отдельного универсального алгоритма доказательства покрытия нет.
- **Подтверждение кодом:** [`HydrologyWorkingFields`](../../backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py) содержит разреженный `coarse_hydro` и область известной поверхности `coarse_surface_z`; [`factConsumers/hydrology.py`](../../backend/app/application/worldData/regions/factConsumers/hydrology.py) в своём optional region-fact use case считает отсутствующую hydro-запись сухим участком **лишь в известной surface extent**, а при отсутствии данных не делает dry-вывод. **Найденный нюанс для SP-0:** ранняя проверка `not hydro` возвращает `None` даже при полностью сухой, но известной поверхности; это не готовый generic gameplay reader и требует отдельного negative case, а не копирования поведения в SPATIAL. [`FineSurfaceWindow`](../../backend/app/dataModel/terrain/sampling/fineSurfaceWindow.py) проверяет полноту fine surface внутри `RegionCoverage`; [`HydrologyFactsAssembler`](../../backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py) проверяет полное coarse-покрытие и согласованность принятых fine-сэмплов; [`FineWaterPublicationJob`](../../backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py) проверяет точные исходные refs/результат. Это **доменные validation/interpretation rules**, их переиспользуют, а не реализуют вторым способом в SPATIAL. Незавершённый GEO G10-A native fine-water cutover сохраняется блокером (§4).
- **Runtime:** действительное состояние = первоначальное описание из Pack + **только принятые** Snapshot-изменения; доменный reader интерпретирует их в своей семантике и возвращает типизированный результат, SPATIAL предоставляет форму запроса/передачи результата. Snapshot не считает воду, SPATIAL не выбирает владельца изменений; DAG остаётся оркестратором. `Unknown` от испорченного/неполного/неактуального состояния не становится нормальным исходом gameplay: обязательный read — типизированный отказ + `ERROR` по существующему logging contract, без подстановки материала.
- **Фактическое состояние code vs target:** сейчас [`MapCellQueryFacade`](../../backend/app/application/worldData/mapCells/mapCellQueryFacade.py) объединяет Pack с SQL-патчами через [`PatchStoreService`](../../backend/app/application/worldData/mapCells/patchStoreService.py), а [`IWorldSnapshotApply`](../../backend/app/application/worldSnapshot/contracts/applyPort.py) пока `Protocol` без полного runtime publication wiring. **Pack + Snapshot — целевой принятый контракт**, не заявление о завершённой интеграции; реализацию/миграцию вести по самостоятельному Snapshot плану. SPATIAL не внедряет обходной overlay.
- **Следствие для SP-PACK-V1:** не вводить обязательное поле `coverage_binding` в manifest, отдельный `CoverageProofService`, generic `SpatialCoverage` или принудительный owner-agnostic `present/absent` index. Источник/его валидированный scope и domain rules могут находиться в самих фактах/существующих зависимостях; дополнительные доменные refs допустимы **только при реальной потребности и после SP-0**. Доменные bounds/индексы — ускоритель поиска **внутри root artifact**, не поля общего manifest и не источник сухости.

## 4. Точная интеграция с гидрологией — PRODUCER SEAM

**Решение по точке подключения:** hydrology-owned пространственный read adapter строится **от уже опубликованных, согласованных финальных hydrology facts**, после water + routes + river relief + final, а **не** вызывается из water solver/routing. В коде конкретный publication seam — результат GeoHydrologyFinalPlanProvider.build, собираемый HydrologyFactsAssembler. Источник должен иметь evidence также из native fine-water и actual fine beds той же revision. Adapter/index имеет своего владельца в hydrology, реализует общий read contract. Это архитектурная точка, **не утверждённое имя нового файла/класса**.

**Принятое решение SP-H — источник water spatial facts (2026-11-01):** только Hydrology владеет canonical native final publication и domain-owned spatial read/index. Точка входа — опубликованный `PlanEnvelope[GeoHydrologyPlan]` **вместе с exact dependencies** fine-water/F, native routes и accepted river relief одной source revision; не новый независимый WaterSpatialPlan, L0 mask или индекс с собственными water facts. Переиспользовать `RegionCoverage` / full wet-dry evidence из точной успешной fine-water зависимости, а не переписывать полную геометрию в дублирующий SPATIAL POJO. Prepared hydrology-owned index строится **один раз на принятую revision** и обслуживает bounded `read_window`; чтение не повторяет fill/routes/relief/финальную сборку. **Сухость определяет Hydrology по принятой surface/footprint семантике**, а не SPATIAL по отсутствию строки: вне известного source scope у обязательного gameplay read — ошибка с логом, не `dry`.

**Подтверждённое новое состояние GEO (2026-11-01):** [NativeFinalPublicationJob](../../backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py) уже изолированно публикует `PlanEnvelope[GeoHydrologyPlan]` с exact F/routes/river closure; [NativeFinalFactsJob](../../backend/app/application/worldData/generators/hydrology/planning/assembly/final/nativeFacts.py) объединяет canonical open water и river roles. Но `GeoHydrologyPlan` ещё не несёт собственного coverage, доказательство остаётся доступно через exact fine-water F dependency; registered owning schema, coverage transport/query consumer и production G10-A **OPEN**. Это решение **не** объявляет cutover готовым. Конкретный PlanSlot, wire/ref и публичное transport API выбирает GEO-1 при G10-A, не SPATIAL. Подготовка индекса запрещена до принятия canonical final/coverage.

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

**Контрольный кейс SP-H/SP-PACK: старый и новый маршрут (обязательный anti-dual-path gate).**

| Режим | Производство и хранение | Что не считать доказанной новой реализацией |
|---|---|---|
| **Legacy / до G10-A** | `HydrologyRoutesAssembler.assemble_geo → WaterBodyPlanner.plan_geo(coarse surface_z)` и действующая финальная сборка; `HydrologyWorkingFields` используется для coarse/sparse-потребителей и L0 bake. Текущий `WorldPackWriter` пишет L0/L2-проекции, но не canonical hydrology domain-root для full fine XYZ/UID/level/coverage | Наличие отдельного `FineWaterJob.fill` или `FineWaterPublicationJob`, наличие L0 hydro-mask или успешно сохранённых terrain chunks **не означает** native production cutover и не доказывает публикацию spatial source в Pack |
| **Target / после соответствующих gates** | `FineWaterPublicationJob` с exact F → native fine routes → accepted river relief → canonical `NativeFinalPublicationJob`/final `GeoHydrologyPlan`; затем **отдельный** accepted bake/publication stage публикует immutable compact Hydrology root `ArtifactRef` в `WorldPackManifest` (вариант Б), а domain reader читает его вместе с принятым Snapshot overlay | `FineWaterJob.fill` только считает в памяти; `PlanEnvelope/PlanRef` — ещё **не** запись в Pack. Готовый индекс/read не должен повторно вызывать fill, routing или старый coarse producer |

**Два последовательных переключения, без смешивания:** (1) **G10-A producer cutover** заменяет старый production-route одним canonical native final source; после gate старый `plan_geo`-маршрут не должен оставаться вторым вызываемым production-поставщиком той же гидрологии. (2) **SP-P2R/P2W → SP-P2; SP-P3I/P3W → SP-P3 → SP-3 storage/read gates**, затем независимые **SP-4 bootstrap L2 / SP-4R runtime L2** и **SP-R1/R2 → SP-R gameplay-read gate** вводят canonical Hydrology root и bounded reader по разным owners; L0 mask и terrain L2 могут существовать как **производные проекции**, но не как резервный source truth. До каждого gate старый путь допускается только как явно помеченный временный путь, **не** как незаявленная подмена и не в смеси с native facts другого `PlanRef`. Переиспользуемые чистые алгоритмические helpers не равны второму end-to-end producer; отдельный callable production fallback на legacy запрещён.

**Стоимость initial solve (AS-IS, не целевое требование):** текущий `FineWaterJob.fill` требует полного fine-покрытия исходной topology и несёт соответствующую CPU/RAM-стоимость на source revision; он не пишет per-cell SQL и не публикует Pack самостоятельно. Это **ограничение существующего алгоритма, не контракт целевого compact source**: способ подготовки, компактное представление, стоимость и допустимая точность остаются OPEN в GEO-1 до producer cutover (§12, SP-H). Гарантия «считать при initial generation → один раз опубликовать компактный source на принятую revision → читать многократно» считается выполненной **только после доказанного pack round-trip и закрытого cutover**, а не по факту наличия `PlanEnvelope`/RAM cache. Изменение исходной revision допускает отдельный повторный bake, но не повторное вычисление при каждом L2-окне.

**Блокер SP-H1 (обязателен до первого reader):** завершить предусмотренный GEO-1 G10-A маршрут native fine water → native fine routes → actual river relief → canonical final facts и явно сохранить fine open-water wet/dry, UID/уровень, берег, исходную/финальную bed geometry, source_mapping и диагностику в согласованном контракте. Точную форму POJO/PlanSlot/версионирования определить в GEO-1; нельзя сохранять только coarse маску и маркировать fine dry.

**Блокер SP-H2 (river volume):** [riverBedProfile.river_bed_roles](../../backend/app/application/worldData/generators/hydrology/rivers/riverBedProfile.py) маркирует RIVER_BED и UID, но не полную water surface z для водной толщи. Без гидрологически утверждённого z_water(x,y) речной volumetric query не имеет права выдать слой жидкости «по догадке». Open-water lakes/seas и river-volume activation разделить; HY-RIV-1 source search сюда не затягивать.

**Принятое решение SP-H2 — river surface ownership (2026-11-01):**

- **Hydrology** определяет и публикует первоначальный подтверждённый wet footprint, профиль поверхности воды `z_water(x,y)`, связь с принимающими водоёмами и явные вертикальные переходы в пределах принятой final geometry/revision. **Terrain/Relief** владеет геометрией русла/дна; ни SPATIAL, ни L2 consumer не вычисляют исходный уровень реки или не исправляют несогласованное устье.
- Профиль может быть **кусочно-заданным**: водопады/перепады отражаются явными фактами перехода (существующий [WaterfallDrop](../../backend/app/dataModel/hydrology/waterfallDrop.py) — пример), а не принудительной непрерывной интерполяцией `z_water` через весь перепад. В устье согласование с уровнем принимающего водоёма выполняет Hydrology; конфликт не разрешается reader догадкой. Не считать падающий поток сплошным стоячим водяным столбом.
- **SPATIAL** читает утверждённые wet footprint + final bed + water surface/transition facts в одном источнике ревизии и выводит bounded интервалы/объём без физического solve. Если профиль/достаточные доменные факты отсутствуют, в обязательном gameplay read — типизированный отказ и ERROR, не синтетическая речная толща; в явно необязательном preview допустим диагностический unresolved. Компактное представление (например, сегменты/интервалы) допустимо; обязательного per-cell хранения нет.
- **Runtime Physics** отвечает за последующее физическое изменение/распространение воды через Snapshot/Patches, не за первоначальное гидрологическое планирование. Точная модель профиля, алгоритм расчёта, POJO и publication wire остаются **OPEN в GEO-1/SP-H2**; данная архитектурная приёмка их не реализует.

**Блокер SP-H3 (physical geometry):** bed height должен совпадать с frozen natural terrain и accepted basin/river relief после всех разрешённых геометрических операций. [NaturalWindowJob.materialize](../../backend/app/application/worldData/generators/terrain/planning/preWater/prepared/materialization.py) выдаёт natural-only FineSurfaceWindow; его нельзя автоматически трактовать как after-water/after-river solid geometry. Нужен подтверждённый состав final overlay и proof одного source revision. Планируемые L2 grade edits, меняющие дно, требуют authority/invalidation decision, а не silent пересчёт воды в generic adapter.

**Принятое решение SP-H3 — runtime geometry → Physics → DAG → Hydrology → Snapshot (2026-11-01):**

- Изменение solid/void геометрии сначала становится доменным terrain/geometry change по действующему Patch/Snapshot-контракту. Прямая геометрическая правка сама по себе **не поручает SPATIAL создавать новые wet cells** и не запускает повторную глобальную Hydrology generation.
- **Physics** на согласованном состоянии решает, распространяется ли вода в изменённую область, и возвращает **типизированный запрос на изменение гидрологических фактов**, а не непосредственно изменённый `SpatialSlice[T]` или запись Pack. **Только DAG** диспетчеризует этот результат как публичную операцию Hydrology; **прямой Physics → Hydrology вызов запрещён** принятой границей оркестрации.
- **Hydrology** проверяет доменную семантику изменённых wet footprint/UID/level/coverage и подготавливает соответствующее typed изменение/patch canonical water facts, **не повторяя tick-based физический solve**. DAG собирает PatchSet; **Snapshot** единственный принимает/публикует изменения и поддерживает runtime overlay. После принятия Hydrology spatial reader только читает новую revision. Ни Physics, ни Hydrology не мутируют прошлый `SpatialSlice` или base Pack.
- Вычисление и доменная подготовка могут быть отдельными DAG-операциями/тиками; конкретные сигнатуры, формат request/patch, версии, scope/invalidation и политика чтения ещё не пересчитанных derived projections **OPEN** до контрактов DAG/Physics/Snapshot. Не вводить общие `dict`-команды и не принимать mixed-revision geometry/water как достоверный physical volume.
- Для **initial bake** остаётся отдельный gate: принятая final hydrology с actual bed geometry одной исходной revision. Физический runtime-путь не используется как обход GEO-1 source proof.

Гарантия integration seam: hydrology остаётся владельцем **опубликованных физических** water UID/wet connectivity/levels и source mapping в соответствующей source revision, но **не** заменяет W/L как владельца долговременной истории систем, динамического membership и каскада уровней. Отсутствие воды в актуальном wet footprint не означает удаления самого водоёма или закрытия lifecycle. Spatial implementation лишь предоставляет **готовое** по запросу и никогда не повторяет flood, spill, route, carve или классификацию источников.

## 5. Точная интеграция с L2 — CONSUMER SEAM

**Место подключения к существующему пути:** [FineChunkRunner.refine_rects](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkRunner.py) → [fineTilePrep.prepare_fine_tile](../../backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py) → [fineChunkCompute.compute_rect](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkCompute.py) → [FineChunkPersist.persist_rect](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkPersist.py).

- На входе existing materialization job должен иметь **готовые** exact source refs/indexes для нужного мира и revision. Resolve/validate prepare делается на planning/application boundary **один раз на source revision**, не в каждой tile/chunk worker. Нынешний fineTilePrep получает SurfacePlanBundle + SurfaceWorkingMaps и строит полный tile state при любом маленьком rect: это **старый путь**, а не место для повторения подготовленного native GEO solve.
- **Конкретная worker точка:** FineChunkCompute.compute_rect, после existing discover_and_paint/grade local geometry и до выпуска ChunkComputeResult.cells на persist. Здесь можно вызвать ограниченный read_window и доменно-нейтральную L2 composition operation, **только** над готовыми indexed sources и согласованной geometry. Сам compute_rect не вычисляет гидрологию, не создаёт отдельный stage-пайплайн и не читает всю ревизию/мир.
- Solid column generation сейчас идёт через TerrainBatchOrchestrator.generate_chunk_cells_sync → TerrainGeneratorService.generate_surface_chunk → columnFillPass.run_column_fill. Generic water/gas/ore logic **не** внедрять в эти terrain kernels. Граница composition должна принять готовую solid geometry/cells и typed slices после окончательных локальных grade изменений, либо отвергнуть геометрическое несоответствие.
- FineChunkPersist и WorldPackWriter сохраняют ответственность только за запись и атомарность. Планировочный provider и generic spatial reader не получают SQL/pack write.
- **Проверенный type mismatch:** [GeoSurfacePlanBundle](../../backend/app/application/worldData/planning/contracts/surfacePlanBundle.py) существует отдельно от SurfacePlanBundle, а текущий fineTilePrep принимает SurfacePlanBundle. До GEO/L2 wiring обязательно выбрать стабильную публичную границу, не пытаться подсунуть GEO bundle через cast/kwargs.
- **Pack output — принятое разделение:** [FineTerrainZRun](../../backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py) хранит z-runs terrain/material, но не hydrology UID/role/level/composition; [mapCellToFineTerrainWire._compress_z_runs](../../backend/app/application/worldData/pack/read/mapCellToFineTerrainWire.py) не переносит MapCell.hydrology. **Не расширять terrain wire обязательными гидрологическими полями и не считать его источником водных фактов.** Canonical water facts (UID, wet footprint, surface level, actual bed provenance, coverage) имеют отдельное компактное typed representation/ref в World Pack, не дублирующее per-cell L2. Точный pack wire, manifest entry и versioning — **OPEN SP-0/SP-1**; действующий WorldPackManifest такой утверждённой ссылки ещё не содержит. L0 HydrologyMaskWire остаётся обзорной проекцией, не SoT.
- **Два разных L2-выхода:** normal solid/object materialization и специальная bounded materialization сред (liquid/gas/ambient), которая может возвращать только интервалы/компоненты без записи клеток. Вода/газы не получают обязательную per-cell L2-публикацию. Geology требует другого пути: материализовать solid-объём и открытые грани в локальном окне при необходимости, в том числе после excavation/cave/world-edit patch; источник состава — geology, источник изменённой occupancy — согласованная geometry + Snapshot. Не создавать второй независимый механизм истины, не делать full-world subsurface fill из-за раскопки.
- Конкретная insertion point в текущем `FineChunkCompute` подтверждена для water/L2 как **кандидат**, а geology/excavation path требует отдельной проверки существующих terrain/patch callers в SP-0. Не насаждать один materializer на media, geology и объектные contracts.
- Не выполнять всё вышеперечисленное в рамках G10-A без самостоятельной приёмки: G10-A сначала доказывает natural/fine-water/final geometry, SPATIAL-1 — read/composition и отдельный L2 consumer activation.

### Принятое решение SP-M/SP-4: L2 terrain и media facts не один wire (2026-11-01)

- **L2 terrain wire** отвечает за существующие physical geometry/solid material outputs; **компактные hydrology/gas facts** принадлежат профильным доменам и хранятся/читаются отдельно через согласованные immutable pack artifacts (после gameplay — с Snapshot overlay). `water_body_uid`, role, level и coverage не обязаны попадать в `FineTerrainZRun` и не должны пропадать при его сериализации: они остаются доступны из canonical spatial source.
- Для bounded L2 consumer данные среды поступают как типизированный `SpatialSlice[WaterFact]` / соответствующая временная media projection с доказанной revision/coverage. Composition не обязана создавать `MapCell`/ZRun для каждой клетки воды или газа; временный результат допустимо держать в RAM/cache и воспроизводить по тем же фактам без нового Patch/Snapshot.
- **Отдельный sidecar на каждый L2 chunk с копией water facts не требуется как правило архитектуры.** Если выбран дополнительный pack artifact/ref, он должен вести к одному canonical source, а не становиться независимой водной истиной. После старта gameplay base Pack immutable; опубликованные изменения принадлежат Snapshot/Patches.
- Специализированная materialization solids/geology и materialization объектов сохраняют свои контракты; будущая Physics-local full materialization — отдельный трек. Точная форма typed L2 output, pack wire/manifest, версия и подключение existing persist остаются **OPEN после SP-0/SP-1/SP-M**, без cutover.

### SP-R — отдельное игровое чтение scene volume (READ CONSUMER SEAM, OPEN)

**Не путать с `FineChunkCompute.compute_rect`:** SP-4 — base/pre-game L2 worker, SP-4R — runtime Snapshot-aware L2 worker; **обычный read сцены должен самостоятельно получать компактные liquid/gas/ambient facts из принятого world state** даже когда соответствующие `MapCell`/ZRun отсутствуют. Успешный water bake, Pack round-trip и работа L2 materializer **не доказывают** доступность воды для игрока/LLM/UI.

**Проверенная current master карта (2026-11-01):**

| Шов | Фактическое поведение | Риск / требуемый контракт |
|---|---|---|
| [`MapCellQueryFacade.get_scene_volume`](../../backend/app/application/worldData/mapCells/mapCellQueryFacade.py) | Получает patches одним bbox-запросом, перечисляет все XYZ в окне, `_layers_at` читает L2/L0/structure и возвращает только `MergedCellView.has_any_data()`; `get_scene_volume_as_map_cells` адаптирует в `MapCell` | Компактная вода/газ без клеточного слоя **не попадёт** в ответ автоматически. Нельзя реализовать SP-R вызовом `read_window` на каждый XYZ или скрытым L2 fill |
| [`MergedCellView` / `merge_layers`](../../backend/app/dataModel/worldPack/wire/mergeMapCells.py), [`WorldMapPackReader.world_map_contribution`](../../backend/app/application/worldData/pack/read/worldMapPackReader.py) | `hydrology: dict \| None` — cell-level поле; L0 даёт только поверхностный role/candidate; отдельного typed gas/volume slice в ответе нет | L0 hydrology candidate и существующая клеточная структура не доказывают full wet/dry/UID/level/3D volume; `has_any_data()` не должен отбрасывать факты сред только потому, что нет solid-клетки |
| [`MapCellService.get_scene_volume`](../../backend/app/application/worldData/mapCells/mapCellService.py), [`scene_volume_route`](../../backend/app/api/routes/map.py) | Service возвращает `list[MapCell]` через pack gameplay facade; HTTP route помечен **debug/no DAG** | Debug HTTP успешен ≠ runtime player/LLM читает media. Подтвердить реальную production consumer цепочку до response/narration/engine |
| [Domain Patches & Snapshots](./world-domain-patches-snapshots.md), [GEN-DAG-1](./gen-dag-1-post-geo-ws.md), [DAG-TYPING-1](./dag-typing-1.md) | **Действующий target:** DAG напрямую вызывает domain-owned `read`-контракты; конкретные output POJO/consumers уточняются в GEN-DAG. [Архивный WS-0](./world-state-crud-ws0-freeze.md) `SceneQuery(merged_scene)` годится только для AS-IS inventory, **не** как contract/gate | **Cross-plan blocker:** выбрать typed bounded scene response и owner композиции по Domain Patches/GEN-DAG, без центрального WS read mediator, второго scene facade или SQL `map_cells` в качестве SoT; текущий `MergedCellView` сам по себе media не переносит |

**Целевой путь (архитектура, не утверждённые сигнатуры):** один bounded scene request по фактическому caller/window policy и pinned `WorldPublicationRef` → **DAG вызывает утверждённые domain-owned read ports напрямую** по тому же окну/revision, включая bounded `SpatialFieldReader[T].read_window`, а solids/objects/patches получает из принятых доменных read/World Pack источников → typed read-only composition по согласованному owner/consumer contract GEN-DAG → **реально используемый** ответ engine/LLM/UI. Текущий WP-20/MapCell facade остаётся AS-IS seam для аудита и согласованного cutover, **не** новым WS read authority. Вызов hydrology/gas reader делается **за окно или обоснованные bounded части**, не по каждой XYZ-клетке. Пустая solid-ячейка не доказывает vacuum/air/dry; наличие media не требует отдельного `MapCell` или persist.

**Не выбирать скрыто DTO:** возможна выдача typed media slices/интервалов **рядом с** `MergedCellView` либо ограниченная совместимая on-demand проекция для конкретного legacy consumer. Точная форма результата, где выполняется композиция и как GEN-DAG node/response contract передаёт media без MapCell, — **OPEN SP-0/SP-1/SP-M/SP-R0 с владельцами соответствующих domain.read и GEN-DAG/DAG-TYPING; SP-R2 — отдельный GEN-DAG production binding, SP-R — E2E acceptance после внешних gates**. Не вводить второй `SceneFacade`/world state service, не добавлять универсальный material-filled XYZ и не превращать `MapCell` в обязательную persisted форму воды/газа. Existing debug route/serialization не ломать молча; миграцию/адаптацию публичного ответа согласовать отдельно.

**Жёсткий gameplay gate:** чисто загруженный immutable Pack с океаном, для которого **нет** water-cells в L2/SQL, должен отдавать реальному scene consumer корректные typed water facts; dry/shore/UID/level согласованы с Hydrology, а local gas/ambient/vacuum — после SP-A2/SP-5A с World Environment/Gas. Accepted Snapshot изменения видны в той же pinned revision, без mixed geometry/water; missing/corrupt domain root или uncovered window в обязательном gameplay read дают typed отказ + `ERROR`, **не** L0/legacy fallback и не неявный `air`. Проверить latency/allocations, bounded pack reads, отсутствие per-cell SQL/повторного solver и соблюдение существующих WP-13/WP-14 scene budgets. Никакого автоматического refine/mill или Patch от обычного read.

## 6. World environment, liquid и gas — профильные границы

В [tz_materials.md §4](../../docs/tz_materials.md) пока действует правило «пустая клетка -> air из material_registry», а [tz_aerial.md](../../docs/tz_aerial.md) считает aerial air implicit void для v1 и оставляет A4 (water/air volumetric layer) OPEN. Это **предмет исправления ТЗ/контракта**, не готовое свойство кода. Не подставлять обычный воздух на world без атмосферы.

Разделить: free of solid; explicit vacuum (отсутствие среды); material key air; ambient world/region/room environment; локальное распределение smoke/steam/toxic gas. Наличие air в registry не устанавливает атмосферу: на airless planet тот же материал может заполнять sealed room. Missing configuration ≠ explicit vacuum и ≠ fallback air; требуется согласованный unresolved/compat/migration режим. Вода может занимать часть воздуха; ore заменяет состав solid, а не обязательно конкурирует с водой в том же смысле. Multi-gas mixtures/concentration — OPEN: существующий один system_material на run не выражает смесь.

Materials определяет density/viscosity, heat/cool refs и условия материала; climate и runtime physics используют их. Tick flow/diffusion/pressure, изменения состава и смешение разных жидкостей не выполнять generic reader. Нужен отдельный владелец composition policy/совместимости и явная диагностика при неразрешимом overlap. Не вводить порядок water>ore>air. Фоновый air/ambient и локальные газы/жидкости не требуют обязательного выделения per-cell L2-данных: потребитель может получить bounded medium projection и отказаться от неё после запроса. Геологический solid, напротив, при L2-взаимодействии может потребовать физически сохранённой геометрии/материала.

### SP-A — обязательная переработка существующей политики воздуха и настроек World

**Владелец архитектурно принят:** World Environment как часть World объявляет наличие/отсутствие атмосферы и её исходный состав. Climate читает эти условия и рассчитывает климат по своему контракту, но не создаёт атмосферу; Materials описывает свойства компонентов, Gas Distribution — локальные концентрации/объёмы, Runtime Physics — их изменение. Не создавать отдельный Atmosphere-домен только ради настройки. Фактическое размещение typed settings/POJO/API и порядок scoped overrides остаются OPEN до SP-A0/SP-A1.

Это **миграция действующей семантики**, а не только проектирование нового ambient reader. Проверено на master 2026-11-01: `tz_materials.md` §4 предписывает «пустая клетка → air»; `tz_aerial.md` v1 называет воздух implicit void; `World.material_registry` — каталог, `WorldMaterialRegistry.canonical_engine()` содержит `air`. **Уже существуют** `World.world_environment` JSON-поле и typed `WorldEnvironmentSettings` / `WorldAtmosphereSettings` / `AtmosphereMode` / `AtmosphereGasComponent` в `backend/app/dataModel/worldEnvironment/worldEnvironmentSettings.py` (см. §7 V1-D). Это **наличие базовых POJO и точки storage**, а не доказательство принятого CRUD/API/engine policy, полной валидации или миграции. SP-A0 обязан проверить реальные callers/defaults/import/export и определить reuse vs gaps; не проектировать дубликат POJO или новое поле World автоматически.

**Целевая нормативная семантика (согласованное направление):**

1. `no solid` — геометрически свободное пространство; `vacuum` — явно заданное отсутствие газовой среды; `air` — только identity газового материала в registry; `ambient` — **явно разрешённая** фоновая среда мира/области; дополнительные локальные газы/смеси — отдельные spatial facts. Ни одна пара понятий автоматически не эквивалентна.
2. World явно задаёт режим фоновой среды: vacuum либо ambient material/composition. **Доменный owner — World Environment, не Climate.** Конкретную typed модель/путь настройки внутри World, допустимость смесей, scope world/region/room и правило local override определить на SP-A1 по действующим контрактам; не объявлять новую произвольную структуру World/POJO до аудита. Важен тот же `WorldMaterialRegistry` как каталог свойств, **не** как доказательство присутствия газа.
3. `missing/unresolved ambient configuration` ≠ `explicit vacuum` ≠ `air`. Unknown material key, неправильная категория или конфликт policy должны давать контролируемый отказ/diagnostics. Новый World без атмосферы не получает воздух автоматически; sealed/local volume с air на таком мире допустим. Не создавать synthetic `air` в registry.
4. Пересмотреть утверждённое в ТЗ правило `empty → air`, найти и заменить только подтверждённые реализации этого fallback в engine; согласовать world settings/normalization/validation, authoring/import/export, world CRUD/API (тонкий адаптер действующего доменного контракта) и затронутые readers. Изменение настроек — изменение authoritative world input/revision, а не тихая мутация frozen spatial index. Где хранить поля и как их разрешать — результат SP-A1, не предположение этого текста.
5. **Миграция существующих миров обязательна:** инвентаризировать миры/fixtures, где legacy неявный air был частью ожидаемого поведения; выбрать и отдельно утвердить явный migration/default rule, совместимость и version bump. Сохранить необходимое прежнее поведение только через осознанно записанную настройку, не через вечный silent fallback. Missing/corrupt нельзя молча трактовать как vacuum.
6. Согласованно обновить `docs/tz_materials.md` §4, `docs/tz_aerial.md` (A4 остаётся OPEN до своей приёмки) и другие затронутые нормативные ТЗ **в ходе SP-A2-1…5, до общего acceptance milestone SP-A2**; проверить world JSON/POJO normalization, SQL/pack serialization и runtime/engine/climate consumers. Не превращать эту работу в full gas solver, Aerial flight redesign или per-cell atmosphere bake.

**Граница завершения SP-A:** конфигурация и policy мира могут объяснить, почему свободный объём заполнен заданным ambient gas, является vacuum или unresolved; локальный gas reader может добавить доказанные компоненты; материализатор L2 только проецирует согласованное состояние. Ни регистрация материала, ни отсутствие solid-клетки не порождают произвольный воздух.

**Обязательные негативные сценарии:** (а) одинаковый registry с air — атмосферный мир и airless world дают разные результаты по явным настройкам; (б) airless world + герметичная комната с air не заполняет планету; (в) отсутствующая/битая конфигурация не превращается в air/vacuum; (г) существующий мир проходит утверждённую миграцию без скрытой смены поведения; (д) smoke/steam/toxic gas не исчезают из-за ambient fallback; (е) смена world policy инвалидирует затронутые source/projections и не смешивает revisions; (ж) для воздуха не появляются обязательные L2-клетки или per-cell SQL.

## 7. Revision, состояния мира и объём работы

- Bootstrap: frozen PlanEnvelope/PlanRef + точные upstream dependencies, deterministic prepared index. Не держать live job, mutable world registry, callback, SQL connection внутри опубликованного payload.
- Runtime: одобренные world-state CRUD → patches/snapshots → актуальный world state. **Принятая граница:** frozen bootstrap `PlanRef` отдельно от существующего `WorldPublicationRef`/`(pack_hash, snapshot_head)`; доменный read берёт согласованный pack + snapshot overlay и возвращает проверяемый provenance обоих источников. **OPEN:** точное typed revision binding, согласование overlay и domain invalidation затронутых spatial volumes. Не считать отсутствие patch автоматическим доказательством актуальности подготовленного индекса.
- Materialization: union запросов XYZ + обоснованные algorithm dependencies/halo, без расширения к одному giant bbox по умолчанию; wrapped/sphere topology seams сохранить. **Reuse доменного определения known present/absent и его source scope**, контроль stale index и gameplay ERROR при недоступной истине; универсального spatial coverage solve нет.
- Initial fine-water physical solve сейчас требует полный fine terrain world (FineWaterJob validates complete canonical coverage); новый reader НЕ обещает отмены этой стоимости. Сравнивать **отдельно** cold prepare и warm localized query, allocations, feature visits, cache/pack/SQL I/O. Маленький read_window не может вызвать full-tile host/map creation, пересборку depression tree, full hash/copy, per-cell SQL.
- **Target storage (архитектура принята):** после согласованного initial solve light bake публикует в immutable World Pack **корневые ссылки manifest на доменные compact spatial facts либо domain catalogs/indexes**; manifest не хранит универсальный material-filled payload, а Hydrology/Geology/Gas Distribution владеют содержимым, индексами и доказательством coverage. L0 map mask — только упрощённая проекция; `HydrologyMaskWire` (`role`, `width`) не доказательство fine XYZ/volume coverage и не SoT. Exact pack wire, manifest entry, shard/index topology и возможность reuse существующего `ArtifactRef` — **OPEN до архитектурного SP-P0 после SP-0/SP-1; SP-P1, SP-P2R/P2W и SP-P3I/P3W реализуют атомарные части; milestones SP-P2/SP-P3 принимают publication до SP-3**; не вводить альтернативный hydrology snapshot store или обязательный per-cell SQL.
- **После начала gameplay** базовый pack не переписывается: доменные изменения — PatchSet/Snapshot и текущий overlay; большие новые материализованные данные при необходимости — immutable staged artifacts по refs. `Patch` описывает **изменение**, а не является обязательным способом получить неизменявшийся океан/газ/породу; обычное чтение = base pack + согласованный snapshot overlay. Временная оконная проекция может жить в RAM/cache, удаляться и воспроизводиться без нового Patch/Snapshot. SQL допустим для metadata/refs/атомарного commit, но не вводить per-cell SQL для самого пространственного поля.
- **Количество воды:** для действующего W0 достаточно вычисляемого приближения `V ≈ A_water × (z_water_level − z_floor)` из согласованных area/floor/level одной ревизии. Не вводить volume как второй authoritative store; текущий `LevelledWater.approx_volume` в W-плане следует рассматривать как производное поле read/consumer-контракта до решения о persist. При изменении уровня/дна/footprint связанные area/floor summary должны быть актуализированы или помечены stale; не перемножать факты разных ревизий.
- **World ambient policy — versioned input:** мирская настройка фоновой среды и её effective scoped overrides обязаны участвовать в проверке актуальности соответствующего spatial source/index и medium projection. Изменение policy не подразумевает немедленную materialization, но stale ambient-результаты нельзя продолжать выдавать как актуальные. Конкретная схема revision binding — SP-A1/SP-1, не новый механизм snapshot.

### Принятое решение SP-PACK: manifest refs + domain-owned compact facts (2026-11-01)

- **Единый World Pack manifest** содержит в новом **spatial-разделе только корневые immutable refs доменных наборов** (существующие L0/L2 entries сохраняют собственные контракты), без общего списка spatial partitions/bounds/indexes. Hydrology/Geology/Gas Distribution сами выбирают, как root artifact хранит compact facts или указывает на собственный каталог/индекс/shards; сами доменные facts **не смешиваются в один общий wire** и не встраиваются в L0-mask/L2 terrain ZRuns. Полноту и семантику отсутствия определяет producer/owner, не generic manifest. Размеры частей и их индексы принадлежат доменам и выбираются по цене bounded reads; один universal tile/chunk размер не навязывается.
- **Владелец payload — профильный домен:** Hydrology/Geology/Gas Distribution задают typed формат и **сами определяют наличие/отсутствие по принятому описанию мира** с учётом Snapshot; shared manifest/ref формат позволяет найти, проверить и удержать canonical artifacts без SQL на каждую клетку. Bbox/tile-кандидат **не равен** доменному утверждению wet/dry/solid/gas; не вводить общий coverage solver или второй источник absence.
- **Привязка к принятой revision:** immutable bootstrap artifacts трассируются к своим producer facts/refs и manifest@hash; после старта gameplay base Pack заморожен, а изменённое состояние читается с Snapshot overlay и его staged immutable refs. Обычный read не пишет новый Pack и не порождает Patch; derived индекс/кэш не становится отдельной authoritative truth.
- **Существующие storage-контракты сначала аудитировать:** в [WorldPackManifest](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py) пока нет root-ref entries для spatial-доменов; в [ArtifactRef](../../backend/app/dataModel/artifacts/references.py) уже есть immutable typed kind/format/version/hash/size без storage path. Использование/расширение этих POJO, format registry, root wire, доменное shard/index layout, serialization/version migration и writer cutover **OPEN** до SP-0/SP-1. Нельзя молча переносить legacy file-path/overwrite semantics в новый contract.
- Архитектурное решение фиксирует **уровни хранения и ownership**, но пока **не** утверждает новый POJO, поля exact wire, бинарный codec, mandatory shard scheme или runtime реализацию.

### Принятое решение SP-PACK-V1-B: domain-root index в World Pack (2026-11-01)

**Выбран вариант Б:** в **spatial-разделе** единого immutable `WorldPackManifest` — одна логическая корневая ссылка на каждый опубликованный domain dataset, а не запись на каждый shard. Domain root содержит компактные факты непосредственно либо доменный каталог/индекс, через который владелец находит свои immutable shards по bounded запросу. Тип/масштаб индекса, source scope, топология и compression принадлежат домену; общий manifest не является spatial index и не вводит generic `partition_scope`/`candidate_bounds`/`index_ref`/`coverage_binding`. Публикация — общий staging/Pack CAS; gameplay mutation — Snapshot, base root immutable. **SP-0 аудитирует кандидаты reuse; SP-P0 после SP-1 + GEO-SPATIAL-CONTRACT принимает точный root-entry POJO/format и reuse существующего `ArtifactRef`**, не переоткрывает выбранную архитектуру.

### SP-PACK-V1 — первая версия логического storage-контракта (DRAFT / REVIEW, 2026-10-31)

**Статус:** согласованы immutable Pack, **вариант Б: только корневые domain refs в Manifest**, domain-owned payload/indices и отсутствие обязательного per-cell хранения. Таблицы ниже — **V1 предложения для архитектурной приёмки после SP-0**, а не утверждённые Python-классы, миграция manifest или разрешение менять runtime. Имена полей иллюстративны; нельзя добавлять новый POJO без сравнения с перечисленными существующими контрактами.

**Разделение:** Pack хранит **канонические компактные domain facts и при необходимости доменный индекс**, а `SpatialSlice[T]` является производным результатом bounded `read_window` и **не сериализуется/не кэшируется как authoritative pack-данные на каждое окно**.

#### V1-A. WorldPackManifest: ссылки на корневые доменные артефакты (**вариант Б принят 2026-11-01**)

**Граница каталога:** новый **spatial-раздел** `WorldPackManifest` содержит **только типизированные ссылки на корень каждого публикуемого доменного набора**, а не список его spatial partitions, XYZ bounds или индексов. Существующие L0/L2 entries сохраняются без изменений этим решением. Структуру внутреннего каталога/shards определяет соответствующий domain owner. Manifest не знает, как Hydrology, Geology или Gas Distribution разбили пространство, и не имеет общего map `window → shard`. Точное имя коллекции и POJO — после SP-0.

| Логическая часть root-entry | Требование | Переиспользование / статус |
|---|---|---|
| `owner_key` | Типизированная identity владельца набора/reader-contract для lookup корня; никакого generic spatial dispatch по координатам | Сверить `RegistryKey` и `ArtifactFormatKey`; не вводить отдельный registry без причины. **OPEN exact type** |
| `root_ref` | Immutable root `ArtifactRef(kind=BLOB)`: либо **непосредственно компактные domain facts** для небольшого набора, либо доменный каталог/индекс, указывающий на собственные immutable artifacts/shards | **Reuse** `ArtifactRef`, `ArtifactFormatKey`, `FormatVersion`, hash/size и существующий format registry. **OPEN exact format/wire** |
| Producer/source provenance | Корень должен однозначно связываться с принятой исходной domain revision и её dependencies, но не требует отдельного общего поля `source_binding` в Manifest | В доменном root contract переиспользовать `PlanRef/PlanEnvelope/PlanDependency` для bootstrap, в runtime — `WorldPublicationRef` для pinned base + Snapshot; **OPEN exact placement** |

**Не вводить в общий Manifest:** `partition_scope`, `candidate_bounds`, `index_ref` для каждого shard, `coverage_binding`, универсальные XYZ/3D bounds и списки всех доменных частей. Внутренний domain root может содержать собственные ограниченные области, refs, индексы и проверки пересечений **в нужном домену формате**; shared manifest не валидирует геометрию вместо владельца. `GridBBox`/`RegionIndexBounds` остаются возможными XY-кандидатами *внутри подходящего доменного индекса*, не полями общего каталога.

**Малые и большие наборы:** для малого набора `root_ref` может сразу указывать на facts, отдельный индексный blob не обязателен. Для большого набора root указывает на подготовленный при bake immutable domain catalog/index, а уже он — на shards. Один читатель bounded окна не должен читать/декодировать весь мир, искать по всем pack entries или заново выполнять hydrology/geology solve. Размер/форма domain shards и раздельность root/facts/index определяются после SP-0 и измерения cold-prepare/warm-read стоимости.

**Семантика отсутствия:** отсутствие root ref, пустой доменный индекс и **доказанное отсутствие фактов у активного домена** — не взаимозаменяемые состояния. Полностью сухой водоём/мир может иметь валидный пустой hydro-result и сохранять durable identity/lifecycle; отсутствие корня нельзя молча превратить в dry. Точное объявление обязательности/отсутствия доменного корня для конкретного World определяется доменом и world settings на SP-0/SP-1; для обязательного gameplay read несогласованность — typed ERROR, не fallback.

**Не дублировать** `world_uid`/pack hash из manifest, `kind/format_key/format_version/content_hash/nbytes` из `ArtifactRef`, физические storage paths/backend из артефактного слоя или `snapshot_head` из `WorldPublicationRef`. Никакого второго spatial revision counter и альтернативного Snapshot index authority.

#### V1-B. Контракт payload и индекса

1. Domain-owned immutable bytes декодируются по зарегистрированному **typed format contract**; для BLOB storage остаются bytes, в application domain codec восстанавливает утверждённую typed модель. Никаких произвольных dict, живых job/callback/SQL connection внутри payload.
2. Hydrology payload предоставляет/ссылается на принятые UID, wet footprint/role, уровень/river profile, bed provenance, source mapping и точную F-coverage. Geology — strata/3D inclusions; Gas Distribution — локальные gas composition/volume. Никакой один-material-per-voxel schema не навязывается, а домены не создают независимый источник фактов при подготовке индекса.
3. **Доменный reader** раскрывает `root_ref`: для малого набора читает непосредственно компактные facts, для большого по **собственному индексу** выбирает кандидатные внутренние refs для bounded окна. Никакого сканирования `WorldPackManifest` по spatial partitions, полного чтения мира и per-cell SQL. **Доменный reader применяет существующие правила своего source + принятого Snapshot overlay** (в Hydrology — sparse water в известной surface extent); он, а не общий слой, определяет water/dry/solid/gas и корректность отсутствия записи. Bbox — только кандидат. Сохранить wrapped/seam/disjoint semantics, не создавать универсальную карту пустот.
4. Несколько shards разрешены, **один общий фиксированный tile/chunk размер не является частью V1**; granularity и index layout принимаются по cold-prepare/warm-query IO, памяти и цене. Повторный запрос не запускает hydrology/geology solve и не перестраивает индекс.

#### V1-C. Публикация, чтение и защита ревизий

1. **До gameplay:** DAG вызывает доменную подготовку/materialization; данные помещаются в общий staging как immutable refs, проходят registry/schema/hash и **предусмотренную существующим доменным producer validation полноты/согласованности source** (не новый общий coverage алгоритм), затем pack manifest@hash атомарно активируется. Текущий координатный `WorldPackWriter._atomic_write`/перезапись пути — legacy, не утверждённый target для новых spatial refs.
2. **После gameplay:** pack manifest заморожен. Изменения фактов — typed domain patch через DAG → Snapshot, большие изменения — staged immutable refs, обычный read = pinned `WorldPublicationRef` (`pack_hash`, `snapshot_head`) + актуальный compact overlay. Не делать второй snapshot store/index authority.
3. **Read:** по `owner_key` получить root `ArtifactRef` из Manifest, проверить формат/hash/revision; **домен** раскрывает root (непосредственные facts либо index → shards), сам выбирает нужные части по bounded окну и интерпретирует факты и накладывает только принятый Snapshot overlay; выдаёт `SpatialSlice[T]`. Общий SPATIAL контракт не сканирует manifest partitions и не занимается пространственным index dispatch. Нет глобального replay тиков, обновления Pack, новых Patch и обязательных MapCell для воды/газов на чтении.
4. **Fail closed:** missing/corrupt/unsupported artifact, несовместимые partitions, stale index, смешанные PlanRef/pack/snapshot revisions или неполное доменное описание не превращаются в dry/air/water по отсутствию записи. Для обязательного gameplay read — **типизированный отказ + ERROR**, для явно необязательного preview — диагностический unresolved; отдельное spatial доказательство покрытия не пересчитывать.
5. **Gameplay incomplete domain state (принято):** для обязательного gameplay-read неполный/неактуальный доменный source (диагностический `unknown`) — **ошибка**, а не нормальная пустота. Owner bounded reader возвращает типизированный отказ/диагностику и инициирует **ERROR** в существующем domain logging pipeline; не подставлять `air`, dry, vacuum, zero solid или произвольный материал и не продолжать игровой переход как успешный. Только явно необязательные planning/debug-preview запросы могут показывать `unknown` как значение, сохраняя эту семантику в контракте; режим должен быть определён вызывающим use case, не догадкой reader.
6. **Логирование без дублирования:** переиспользовать [`tz_logging.md`](../../docs/tz_logging.md) и [`loggingConfig.py`](../../backend/app/core/loggingConfig.py): единый JSON facade, штатный `{domain}/{service}.log`, без нового handler/общего `app.log`. На границе, владеющей причиной отказа, **один агрегированный ERROR на bounded request/операцию**, а не по клетке; при повторениях предусмотреть контролируемую дедупликацию/счётчик без потери факта ошибки. Обязательный диагностический контекст: типизированная причина (exact enum/POJO — SP-0), owner/reader, `world_uid`, bounded scope/coordinate space, requested source/pack/snapshot revision, refs/хеши **если доступны**, request/correlation ID и результат отказа. Не логировать cell payload/большие geometry/SQL. Если первичная ошибка уже залогирована Artifact/Snapshot owner, downstream не эмитит дубль; конкретный logger route и event fields утверждать после SP-0.

#### V1-D. Проверенные существующие контракты: reuse и gaps

| Существующий файл/контракт | Решение V1 |
|---|---|
| [artifacts/references.py](../../backend/app/dataModel/artifacts/references.py) — `ArtifactRef`, `ArtifactKind.BLOB`, `ArtifactFormatKey`, `FormatVersion` | **Прямой кандидат на reuse** immutable ref вместо нового `SpatialBlobRef`; у `ArtifactRef` нет пространственного scope/provenance, они относятся к directory |
| [artifacts/contracts/formatBackend.py](../../backend/app/application/artifacts/contracts/formatBackend.py) — `ArtifactFormatContract` и [registry/artifactRegistry.py](../../backend/app/application/artifacts/registry/artifactRegistry.py) — `ArtifactFormatRegistryBinding` | Переиспользовать registered pure encode/decode, format/version и backend verification. BLOB contract оперирует `bytes`; typed domain decoding/validation остаётся на owner boundary |
| [planning/identity/planRef.py](../../backend/app/dataModel/planning/identity/planRef.py), [planEnvelope.py](../../backend/app/dataModel/planning/contracts/planEnvelope.py), [planDependency.py](../../backend/app/dataModel/planning/contracts/planDependency.py) | Переиспользовать bootstrap producer provenance; не класть весь `PlanEnvelope` с рабочими данными в manifest и не применять PlanRef как единственную runtime revision |
| [worldSnapshot/identity/publication.py](../../backend/app/dataModel/worldSnapshot/identity/publication.py) — `WorldPublicationRef` | Переиспользовать pinned `(pack_hash, snapshot_head)` для чтения effective runtime state; **не** дублировать этот head в Pack entry |
| [worldPack/meta/worldPackManifest.py](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py) — `WorldPackManifest`, `ChunkRef`, `TileManifestEntry`; [wildernessRegionEntry.py](../../backend/app/dataModel/worldPack/meta/wildernessRegionEntry.py) | Расширить manifest **только корневыми refs доменов** после SP-0; current spatial root refs отсутствуют. `RegionIndexBounds` — XY кандидат для доменного индекса, **не** mandatory manifest entry/bounds и не dry proof |
| [coordinateSpace.py](../../backend/app/dataModel/spatial/grid/coordinateSpace.py), [gridBBox.py](../../backend/app/dataModel/spatial/grid/gridBBox.py), [worldTopology.py](../../backend/app/dataModel/topology/worldTopology.py) | Reuse typed coordinate/topology declarations в bounded domain queries; `GridBBox` — XY, не универсальный XYZ и не поле общих root refs. Domain index handles seams/coverage |
| [coverageGeometry.py](../../backend/app/dataModel/terrain/regions/coverageGeometry.py) — `RegionCoverage/CoverageSpan`; [fineSurfaceWindow.py](../../backend/app/dataModel/terrain/sampling/fineSurfaceWindow.py) | Reuse точного GEO fine coverage/evidence по source dependency; не использовать terrain-specific `RegionCoverage` как универсальный gas/geology XYZ payload |
| [hydrologyPlan.py](../../backend/app/dataModel/hydrology/planning/hydrologyPlan.py) — `GeoHydrologyPlan`; [openWaterPlan.py](../../backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py) — `FineWaterResult` | Existing native producer/fine-water evidence; final PlanEnvelope и exact F/routes/river refs — источник bootstrap Hydrology, **не** готовый компактный Pack wire. G10-A/coverage transport OPEN |
| [hydrologyWorkingFields.py](../../backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py) и [factConsumers/hydrology.py](../../backend/app/application/worldData/regions/factConsumers/hydrology.py) | **Reuse семантики, не хранения:** отсутствие в sparse `coarse_hydro` означает dry **только в известной `coarse_surface_z` области**. В текущем optional fact consumer вне этой области **или при полностью пустой `coarse_hydro`** возвращается `None` (SP-0 gap для полностью сухого мира); обязательный gameplay reader обязан превращать неполные данные в типизированный отказ/ERROR, а не silent dry |
| [mapCellQueryFacade.py](../../backend/app/application/worldData/mapCells/mapCellQueryFacade.py), [patchStoreService.py](../../backend/app/application/worldData/mapCells/patchStoreService.py) и [worldSnapshot/contracts/applyPort.py](../../backend/app/application/worldSnapshot/contracts/applyPort.py) | **Current vs target:** текущий gameplay merge = Pack + SQL patches, `IWorldSnapshotApply` пока `Protocol`. SPATIAL следует утверждённому target Pack + Snapshot, но не выдаёт текущий SQL merge за уже подключённый Snapshot и не реализует собственный patch adapter |
| [fineTerrainChunkWire.py](../../backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py), [hydrologyMaskWire.py](../../backend/app/dataModel/worldPack/wire/hydrologyMaskWire.py) | **Не переиспользовать как SoT** canonical volume/UID/coverage: L2 terrain и L0 mask — отдельные производные проекции |
| [worldEnvironmentSettings.py](../../backend/app/dataModel/worldEnvironment/worldEnvironmentSettings.py) — `WorldEnvironmentSettings`, `WorldAtmosphereSettings`, `AtmosphereMode`, `AtmosphereGasComponent`; [World.world_environment](../../backend/app/db/models/world.py) | **Existing reuse baseline:** уже есть frozen typed declaration vacuum/mixture + components и JSON-поле World. SP-A0 проверяет фактический wire/read/write/API/validation и legacy fallback, SP-A1 утверждает **только недостающие** scoped policy/контракты/миграции. Не создавать второй atmosphere POJO, ещё одно SQL-поле или gas solver без evidence |
| [worldPackWriter.py](../../backend/app/application/worldData/pack/io/worldPackWriter.py), [tz_world_snapshot](../../docs/tz_world_snapshot.md) и [tz_world_pack_storage](../../docs/tz_world_pack_storage.md) | Writer содержит legacy path/overwrite semantics; publication target — общий staging, immutable blob/manifest@hash, holder/CAS по существующим ТЗ. Migration/version gate отдельный, без изменения pack во время gameplay |

#### V1-E. Обязательная приёмка после SP-0 (OPEN)

- Полный reuse/caller/import audit и выбор **минимального** typed domain-root directory в `WorldPackManifest` (owner key → root `ArtifactRef`); не плодить adapters и параллельный registry. Exact поле manifest, root format registration, schema/pack version bump, правила отсутствующего/пустого root и domain-specific index/shard wire — отдельный freeze **SP-P0**, до P1/P2/P3. До кода обязательна карта файлов/импортов из §8. **Никакого shared XYZ partition index.**
- Согласовать **provenance внутри domain root** и переиспользование существующего domain validation/extent/evidence для bounded reads без обязательного generic `source_binding`/`coverage_binding` в Manifest и без копирования F-geometry в каждый shard; deterministic domain index/shard serialization, overlap policy и retention/GC/rollback.
- Проверить golden: full-window == union disjoint small windows; holes/seams/negative coordinates; known dry != unknown; corrupted hash/unknown format/stale revision дают отказ; cold prepare / warm small read, bounded blob IO, отсутствие per-cell SQL и повторного solver.
- Для обязательного gameplay `read_window`: отсутствующий/повреждённый **domain root** или внутренний shard, stale revision и domain-coverage gap → типизированный отказ + **ERROR** в существующем sink с world/scope/revision/correlation, без silent fallback; тест без per-cell log storm и без повторного дублирования того же producer error.
- **Gameplay consumer round-trip (SP-R):** cold Pack hydrology root → bounded domain slice + WP-20 solids/objects/patch → фактический scene-read consumer/response, в том числе water-only XYZ без L2 water-cell; существующий `MergedCellView.has_any_data` учтён как AS-IS риск, а **принятые domain.read/GEN-DAG typed consumers** не теряют medium; архивный WS-0 не является gate. Проверить single pinned revision, ошибки, latency, отсутствие lazy full solve и per-cell I/O; тест только debug route не засчитывать за gameplay activation.
- Ничего из V1 не активирует GEO G10-A, ambient/gas SP-A2, новую физику или L2 cutover без их собственных gates.

## 8. Последовательный план работ и блокировки

**Обязательное существующее правило:** [code-gates.mdc](../rules/code-gates.mdc) и [folder-composition.mdc](../rules/folder-composition.mdc) уже требуют до кода точный путь **каждого** нового/изменяемого класса, owner/domain/layer, import graph, потребителей, количества файлов в папках и необходимую композицию. Здесь правило **не создаётся заново** — SPATIAL-1 обязан предъявить evidence его исполнения. Размещать новое «куда получится» при реализации запрещено.

**Второй обязательный gate — contract/POJO/enum freeze:** до **любого** относящегося к шагу кода (включая тесты, fixtures, schema и миграции) должны быть явно утверждены все используемые им публичные и межслойные контракты: signatures/typed input/output/error, producers/consumers, ownership, допустимые import edges; reuse существующих POJO/enum либо точные новые/изменяемые типы с file path, полями, типами, required/nullable/default, validation/invariants, enum variants и их семантикой, version/serialization/compat при необходимости. Если новые POJO/enum не требуются — явно зафиксировать reuse и отсутствие новых типов. **`OPEN/TBD` по необходимому контракту, полю или enum-варианту = implementation BLOCKED**; домысливать типы/поля/варианты или создавать лишние adapter/POJO в коде запрещено. Это уточнение **общего** [code-gates.mdc](../rules/code-gates.mdc), а не независимая политика SPATIAL.

**Граница архитектурной приёмки и layout freeze:** SP-0 делает read-only inventory существующих каталогов, файлов, POJO/enum, сигнатур, реестров и callers. Каждый последующий **архитектурный** шаг SP-1/SP-2/SP-A1/SP-M/SP-P0/SP-R0/SP-G дополняет **единую карту размещения** для своей части: компонент/класс → reuse или новый тип → domain owner → слой → **точный target file path** → утверждённый contract/signatures/errors + POJO fields/types/validation + enum variants/semantics → публичные producers/consumers → разрешённые импорты → судьба legacy файла/entrypoint → каталог и file counts до/после (+ `__init__.py`) → проверка 5-file WARN/10-file ceiling и нужных import migrations. Карта хранится **в этом плане**, не отдельным конкурентным документом. Если новый тип/контракт ещё не обоснован — `OPEN`, **не фиктивный файл, POJO или enum**; шаг implementation **BLOCKED** до freeze конкретных путей, всех нужных контрактов/POJO/enum и проверки композиции. Каждому кодовому шагу нужны свои ссылки на ТЗ, файлы, **точные typed contract/POJO/enum**, проверки и Done по [code-gates.mdc](../rules/code-gates.mdc); таблица ниже **не является разрешением писать код**. Формальные критерии архитектурной приёмки и отдельного code-step GO/NO-GO — §11.1–11.2.

**Проверенный dependency-порядок:** таблица ниже — **топологический порядок этапов и внешних gates**, не глобальный стопор между независимыми ветками. Строки `НЕ код`/`ВНЕШНИЙ gate` — приёмка или зависимость owning плана, **не** задача написать реализацию в SPATIAL. Каждый `код`-подшаг проходит собственные contract/POJO/enum/file freeze и отдельную итерацию по [code-gates.mdc](../rules/code-gates.mdc).

- **Hydrology/Pack bootstrap:** SP-0 → SP-1 → SP-P0 → SP-P1 → (SP-P2R + SP-P2W) → SP-P2; независимо GEO G10-A → SP-H; SP-H + SP-P0 + SP-P1 → SP-P3I; SP-P3I + SP-P2 → SP-P3W → SP-P3 → SP-3. **Только для base/pre-game L2:** SP-1 → SP-M, далее SP-M + SP-3 → SP-4. Source index/read не повторяет initial fine solve; Pack-root не может читаться до его publication.
- **Runtime Snapshot и gameplay:** принятый Runtime Snapshot apply + SP-3 → SP-3S; SP-4 + SP-3S → SP-4R (**только runtime L2**). SP-1 + SP-M → проектирование SP-R0; совместное согласование Domain Patches/GEN-DAG read contracts составляет evidence приёмки SP-R0; SP-R0 + SP-3S → SP-R1; SP-R1 + **принятые GEN-DAG/DAG-TYPING node bindings** → внешний SP-R2; SP-R1 + SP-R2 → SP-R end-to-end. **Архивные WS-0/WS-4 не prerequisites**; DAG вызывает domain.read напрямую, ownership композиции фиксирует SP-R0, а не SPATIAL выдумывает WS facade. Water gameplay-read не обязан ждать SP-4R или air migration.
- **Атмосфера/газы:** SP-0 → SP-A0 → SP-2 → SP-A1 → SP-A2-1 → SP-A2-2 → SP-A2-3 → SP-A2-4 → SP-A2-5 → SP-A2, затем по собственному плану Gas Distribution SP-5A после принятого Pack transport SP-P2. **SP-A0/SP-2/SP-A2 не блокируют water-only SP-M/SP-4/SP-R**: газовые overlap/composition policies должны быть готовы лишь к своей gas/ambient activation.
- **Геология:** SP-0 + SP-1 + SP-M → SP-G, затем по отдельному плану Geology SP-5G после SP-P2. Solid/void authority и excavation обязаны быть согласованы, но **Geology не ждёт air policy**.
- **Внешние gates:** GEO-1 G10-A, общий staged Pack/World publication, runtime Snapshot apply, GEN-DAG/DAG-TYPING contracts/node production activation принимаются своими owners. SPATIAL не объявляет их реализованными, не дублирует DAG/WorldState CRUD и не внедряет обходной storage/read pipeline.

| Шаг (ID) | Входной gate и критерий выхода |
|---|---|
| **SP-0 — аудит (только анализ)** | Инвентаризация existing spatial/coverage/material/PlanRef/Snapshot/pack POJO и full caller map; **включая ArtifactRef/FormatContract/RegistryBinding, WorldPackManifest/Writer, staged publication и точку domain-root registration (вариант Б)** (SP-PACK-V1 §7); GeoHydrologyPlan/FinalProvider, FineWaterResult, HydrologyWorkingFields, `HydrologyMaskWire`, fineTilePrep/FineChunkCompute/сериализатор; дополнительно Terrain layers/columnFill, `generate-ores`, W0–W3 и excavation/geometry patch callers. Отдельный inventory air policy делается SP-A0. **Обязателен сравнительный caller/import/API/DAG map legacy vs native GEO producer и legacy L0/L2 read vs domain-root read, с перечнем точек cutover и запретом второго production-маршрута (§4/§9).** **Отдельно трассировать gameplay scene path:** `MapCellQueryFacade.get_scene_volume/get_cell/get_cells`, `MapCellService`, `MergedCellView.has_any_data`, WP-20 L0 fallback, архивный WS-0/WS-4 `SceneQuery` (только AS-IS) и актуальные domain.read/GEN-DAG contracts, debug `scene-volume`, реальные DAG engine/LLM consumers (`eager_terrain`, `terrain_context` и прочие); показать места исчезновения media без `MapCell` и границу нового bounded read (§SP-R). **Результат аудита размещения и типов:** список затрагиваемых каталогов/файлов, существующих contract signatures/typed POJO/enum и их фактических owners, import/caller graph, reuse vs изменение/новый тип, текущие и плановые прямые file counts (включая `__init__.py`), кандидаты reuse/переноса и проверка лимитов `folder-composition.mdc`; **не выдавать ещё не выбранные имена новых классов за утверждённые пути**. Открытые решения записать, **код не менять** |
| **SP-1 — общий контракт (архитектура)** | **Принято:** общий типизированный generic `SpatialSlice[T]` с domain-owned `T`, shared read contract без самостоятельного Spatial orchestrating application/domain; ни общий material-filled XYZ, ни обязательный базовый `SpatialFact` не требуются. **OPEN после SP-0, обязательно заморозить до любого SP-3/SP-4/SP-R кода:** точная `read_window` signature и typed input/output/error contracts, перечень и конкретные поля всех reuse/new POJO и значения всех необходимых enum (с domain owner и путями), **переиспользование существующей доменной семантики present/absent/invalid** и способ типизированного отказа/diagnostics без generic coverage POJO, provenance/revision fields, coordinate/topology/XYZ format, POJO reuse, **точный target path/owner/layer каждого утверждаемого shared read POJO/contract и его import edges в обязательной карте размещения §8**; передать **exact storage root/format/schema/миграционный freeze в отдельный SP-P0**, не смешивать его с shared read contract. Правило один source/index → много окон; отделить canonical compact facts от L0-маски и source read от временной window projection; запрет лишних POJO |
| **SP-P0 — storage POJO/format freeze (архитектура, после SP-1 + GEO-SPATIAL-CONTRACT; SP-0 принят)** | На основании варианта Б утвердить exact `WorldPackManifest` domain-root entries, reuse `ArtifactRef(BLOB)`, format registry + wire/schema/version/migration, **полные поля/типы typed POJO, применимые enum variants и значения**, provenance и absent/empty semantics; выбрать **точные целевые пути для всех новых/затрагиваемых POJO, contract/codec и импорты**. Не вводить shared XYZ shard index, второй реестр, новый storage owner. **Без кода**; P1/P2/P3 blocked до приёмки |
| **SP-M — typed materialization/projection boundary (архитектура, после SP-1; water не зависит от SP-A0/SP-2)** | Заморозить три **разных** output contracts: временная bounded liquid projection, физическая geology/solid materialization и действующая самостоятельная object/structure materialization. Для water-only подтвердить typed output/error, source revision, cache eviction и **отсутствие per-cell persist** без ожидания ambient policy. **Газ/ambient composition и overlap не принимать этим water gate:** они определяются SP-2/SP-A1/SP-A2 и отдельным Gas owner. Exact POJO/enum, path, imports и consumers до кода, после SP-0; никакого универсального materializer |
| **SP-R0 — gameplay/domain-read contract freeze (архитектура, после SP-1 + SP-M; активные Domain Patches / GEN-DAG)** | По [Domain Patches & Snapshots](./world-domain-patches-snapshots.md) владелец каждого read contract — домен; DAG напрямую вызывает domain.read, **не** центральный WS/`SceneQuery`. Сверить AS-IS `MapCellQueryFacade`/`MergedCellView` и реальные engine/LLM/UI callers, согласовать с GEN-DAG/DAG-TYPING **точный owner композиции, typed input/output/error и файлы/POJO/enum для bounded scene response**, включая media-only окна, без второго gameplay facade. Архив WS-0/4 — только история, не gate; SP-R1/R2 BLOCKED до этого freeze |
| **SP-A0 — текущий air policy/settings inventory (только анализ, после SP-0)** | Проверить реальный reuse `World.world_environment`, `WorldEnvironmentSettings` / `WorldAtmosphereSettings` / `AtmosphereMode` / `AtmosphereGasComponent` и все неявные `air` fallback/absence semantics в materials/aerial/climate/engine, **существующие air-related contracts/POJO/enum и их фактические поля/значения**, конкретное per-world хранение, JSON validation/normalization, CRUD/API, import/export, fixtures, pack/SQL и потребителей; сопоставить действующие правила с целевой моделью. Полная карта вызовов, риски миграции и незакрытые расхождения; **код и ТЗ пока не менять** |
| **SP-2 — world ambient/material composition (архитектура)** | На основе SP-A0 закрепить уже принятое World Environment ownership и его границы с Climate/Materials/Gas Distribution; определить правила vacuum, unknown/migration, gas mixtures и liquid-gas-solid/ore composition отдельно. Проверить tz_materials §4, tz_aerial A4, правила материалов; не делать universal physics |
| **SP-A1 — контракт World air settings/policy (архитектура, после SP-A0 + SP-2)** | Под принятым владельцем World Environment утвердить **reuse или точные gap-изменения существующих `WorldEnvironmentSettings`/`AtmosphereMode` и их полей/enum**, не создавать новые сущности без SP-A0 evidence, явный vacuum/ambient/unresolved, region/room override precedence (если требуется), material refs, world CRUD/API/read boundary contracts и typed errors, provenance/revision, compat/migration для старых миров; **точные POJO/файлы/каталоги и обновление существующих consumers — freeze по SP-0/SP-A0, не выбирать в SP-A2.** Climate — потребитель, не owner. Отдельная явная приёмка до SP-A2 |
| **SP-G — геологическая граница и solid materialization (после SP-0/1/M, независимо от air policy, вне GEO-1)** | Отдельно согласовать Geology↔Terrain/Relief↔Materials, stratigraphy soil/clay/rock + 3D ore inclusions, порядок и ownership существующих `generate-surface`/`generate-ores`/caves. Доказать bounded физическую материализацию solid и обнажённых excavation-патчем поверхностей (пол/стены/потолок), без reroll geology, без полного subsurface fill и без вмешательства в object/structure materialization. **Freeze отдельной карты класса/пакета/файла и typed contracts/POJO/enum Geology ↔ Terrain ↔ Materials после SP-0; реализация по отдельному доменному плану, без ожидания SP-A2** |
| **SP-A2-1 — World environment typed normalization (код, после SP-A1; dataModel)** | Воспользоваться уже существующими `WorldEnvironmentSettings`, `WorldAtmosphereSettings`, `AtmosphereMode`, `AtmosphereGasComponent`; реализовать **только документированные SP-A1 gaps** validation/normalization/compat в одном dataModel шаге. Если код не требуется — предъявить reuse/validation evidence и закрыть шаг без нового класса; отдельные tests и поля по frozen карте, никакой engine/API миграции |
| **SP-A2-2 — World settings persistence (код, после SP-A2-1; storage/mapper)** | Установить согласованное чтение/запись существующего `World.world_environment` JSON, schema/revision/compat для legacy миров через frozen storage contract; schema/DDL менять **только если доказан gap**. Отдельная проверка import/export round-trip на уровне persisted representation; без CRUD/API или engine fallback cutover |
| **SP-A2-3 — World application policy port (код, после SP-A2-2; application)** | По SP-A1 внедрить/обновить typed domain-owned read/change operation, policy resolution и необходимую явную миграцию существующих world/fixtures. Тонкие фасады и engine consumers пока не переключать. Missing/unresolved ≠ vacuum/air; один owner, exact refs/revision, отдельные golden/negative tests |
| **SP-A2-4 — World thin API/authoring adapter (код, после SP-A2-3; API)** | Подключить уже принятый application/domain contract к World CRUD API, import/export и authoring через **тонкую** существующую границу, без собственной policy logic или дублирующего POJO. Отдельные API/serialization/invalid-setting cases; внешних вызовов без утверждённых контрактов не добавлять |
| **SP-A2-5 — engine air-fallback cutover (код, после SP-A2-4; consumers)** | Атомарно перевести **утверждённую группу** фактических engine/material/aerial consumers с legacy `empty→air` на resolved World Environment policy; если затронуты независимые группы файлов/слои — в SP-A1 дополнительно разбить этот подшаг до кода. Negative airless/sealed-room/missing config, logging, invalidation; без gas physics и per-cell air |
| **SP-A2 — air policy conformance gate (НЕ код, после SP-A2-1…5)** | Единая приёмка schema/settings/persistence/application/API/engine migration, version/rollback и совпадения normative docs `tz_materials.md` §4, `tz_aerial.md` (A4 отдельно OPEN). Подтвердить отсутствие второго runtime `air` fallback и новых per-cell air cells. **Только после SP-A2** разрешать ambient/gas consumer; воду gate не блокирует |
| **SP-P1 — World Pack schema/typed root entry (после SP-P0, слой dataModel)** | Атомарный шаг по утверждённой карте файлов: typed spatial domain-root entry/manifest schema и связанные версии (без Pack writer, Hydrology solve, runtime overlay). Ревизионные/empty/missing validation, schema/golden/migration tests. **Код только по отдельной явной просьбе и после gate файлов** |
| **SP-P2R — artifact read/verify port (код, после SP-P1; application/storage)** | Переиспользовать существующие `ArtifactRef(BLOB)`/registry для **одного** bounded immutable root/shard read и проверки hash/format/revision; без Pack publication/writer и full-world scan. Exact file map и read/error contracts из SP-P0, cold-read/golden tests |
| **SP-P2W — staged immutable Pack publication (код, после SP-P1 + принятого внешнего Pack/Snapshot staging-port gate)** | По owning World Pack/Snapshot contracts реализовать **только** publication path: staged blobs → manifest@hash/CAS, без legacy path overwrite, второго writer и SQL per cell. Отдельные commit/retry/rollback/manifest golden cases. Не выдавать план staging за готовый port |
| **SP-P2 — artifact/Pack transport acceptance (НЕ код, после SP-P2R + SP-P2W)** | Проверить согласованную typed root transport read/write revision/hash/empty semantics, cold round-trip, one staged publisher и сохранённые existing WP/Artifact owners. Без приёмки обоих отдельных application steps SP-P3W и другие root publishers BLOCKED |
| **SP-H — GEO producer proof (ВНЕШНИЙ gate GEO-1 G10-A; не шаг внедрения SPATIAL)** | **Принято:** canonical native final `PlanEnvelope[GeoHydrologyPlan]` с exact F/routes/river dependencies; `RegionCoverage` из F переиспользуется, не дублируется как отдельный SPATIAL SoT. Изолированный NativeFinalPublicationJob существует, но G10-A owning schema/coverage transport/query/production cutover **OPEN**. **При cutover проверить, что legacy `plan_geo` больше не вызывается ни одним production caller и не остаётся fallback к native final (§4/§9).** Нужны exact source revision, полные fine wet/dry/UID/level/shore/bed/mapping и доказательство coverage до reader; старый incomplete final не подходит |
| **SP-P3I — Hydrology compact root facts/index (код, после SP-H + SP-P0 + SP-P1)** | Hydrology-owned typed canonical native final + exact F/routes/bed revision → deterministic compact payload и, при необходимости, bounded index/shards. Это **подготовка** доменного root без публикации Pack и без второго hydrology solve/coverage service. Exact codec/files/POJO из SP-P0 + accepted GEO gate, golden window/coverage/source validation |
| **SP-P3W — Hydrology Pack-root publication binding (код, после SP-P3I + SP-P2 + SP-H)** | Подключить prepared Hydrology root к **существующему** staged Pack publication и light bake entrypoint по принятому DAG/Pack owner contract; один логический Hydrology `ArtifactRef` в Manifest, без второго producer/Pack writer/overwrite. Реальное GEN-DAG production activation — отдельный внешний gate; этот шаг не объявляет его принятым |
| **SP-P3 — Hydrology domain-root publication proof (НЕ код, после SP-P3W)** | Cold Pack round-trip от canonical final Hydrology root через принятый P2R/P2W transport, full wet/dry/UID/level/bed/coverage/source evidence и отсутствие per-cell SQL/второго producer. Только после этого SP-3 может честно читать опубликованный base source |
| **SP-3 — hydrology reader (после SP-1 + SP-H + SP-P3; Snapshot overlay только после внешнего runtime gate)** | Hydrology-owned immutable prepared/index от final published facts и final geometry; bounded open-water queries **с той же dry/absent семантикой, что у принятой Hydrology**, без generic coverage solver. Неполный source при обязательном gameplay read — отказ/ERROR, optional preview может сообщить unresolved. Подготовленный base-Pack index/reader проверять отдельно от будущей runtime Snapshot overlay; **полную runtime готовность не объявлять до приёмки Snapshot apply/invalidation**. Никакого hydrology solve в read; river volume только после SP-H2 |
| **SP-4 — bootstrap L2 bounded consumer (код, после SP-M + SP-3; ТОЛЬКО immutable base)** | По готовым frozen refs и domain slices подключить локальный read+water medium projection после согласованной grade geometry в `FineChunkCompute`, `FineChunkPersist` остаётся writer, water facts не обязаны стать cells/ZRun. Это **base/pre-game L2 gate**, допустимый без runtime Snapshot. Его нельзя использовать как доказательство корректного gameplay L2 после patch; runtime отдельно SP-4R. Golden and bounded cost, без fill/route/per-cell SQL |
| **SP-3S — Hydrology runtime Snapshot overlay/read (после SP-3 + принятого Runtime Snapshot apply, домен Hydrology)** | Доменный reader накладывает **только принятые** Hydrology PatchSet/Snapshot изменения на immutable base Pack, проверяет pinned `WorldPublicationRef`, invalidation changed volumes и согласованную solid/void geometry без второго spatial store/solver. Это **отдельный Hydrology code step** с собственной frozen file map и gate принятого Snapshot runtime port; без него нет complete gameplay source для SP-R. Отказы stale/mixed revision → typed ERROR, no silent old path | 
| **SP-4R — runtime L2 Snapshot-aware consumer (код, после SP-4 + SP-3S + принятого Snapshot runtime gate)** | Тот же bounded L2 consumer читает **актуальный pinned base+accepted overlay** после geometry/excavation changes, проверяет invalidation/stale revisions и не повторяет fill/materialization всей ревизии. Runtime activation/golden after patch отдельно от bootstrap SP-4; никакой второй spatial store/patch-on-read |
| **SP-R1 — bounded gameplay response composition (код, после SP-R0 + SP-3S; владелец по SP-R0)** | Подключить типизированные domain-owned water media slices к **одной согласованной операции чтения consumer** по окну и pinned revision с solids/objects/patch inputs; место композиции, точный file/POJO/enum, API и допустимые импорты — frozen в SP-R0 по Domain Patches/GEN-DAG, **не** новый WS facade. Это подготовка typed response, без изменения GEN-DAG runtime node registry/activation |
| **SP-R2 — GEN-DAG/engine consumer binding (ВНЕШНИЙ кодовый gate owning GEN-DAG после SP-R1 + принятых GEN-DAG/DAG-TYPING контракта и runtime Snapshot)** | В owning GEN-DAG плане отдельно активировать node/consumer read bindings, реально потребляющие typed spatial response в engine/LLM/UI; исключить legacy SQL `map_cells`/L0 fallback. **SPATIAL не правит DAG/engine nodes по этому шагу** и не создаёт центральный WorldStateService. Отладочный endpoint не считается активацией |
| **SP-R — real gameplay scene-read acceptance (НЕ код, после SP-R1 + SP-R2 + SP-3S)** | Cold Pack ocean **без persisted water MapCell/L2 ZRun/SQL** доступен фактическому GEN-DAG/engine/LLM consumer через принятые domain.read contracts и единый pinned WorldPublicationRef; ошибки missing/corrupt/stale дают typed ERROR без fallback, per-XYZ query/fill запрещены. Это **водный E2E gate** без требования SP-4R или SP-A2/5A; отдельная gas gameplay activation ждёт свой owning plan |
| **SP-5G — Geology/ore reader (вне GEO-1)** | После SP-G + SP-1, общего SP-P2 storage transport и **отдельно принятого Geology contract/POJO/enum freeze**, **по отдельному плану Geology**; own typed strata/inclusions, bounded read/materialization твердых материалов, проверка solid/void authority, excavation и перекрытий. Не ждать air migration/SP-A2. Отдельные domain-root payload/format и files/POJO freeze до кода, никакой hidden ore reroll |
| **SP-5A — Gas Distribution reader (вне GEO-1)** | После SP-A2 + SP-1, общего SP-P2 storage transport и **отдельно принятого Gas Distribution contract/POJO/enum freeze**, **по отдельному плану Gas Distribution** и принятой world ambient policy; own typed local gas facts/mixtures и bounded projection. Не заменять Atmosphere/World Environment, не материализовать весь air. Собственные domain-root payload/format и files/POJO freeze до кода, activation только после domain/gas acceptance |

**Статус и атомарность:** SP-A2, SP-P2, SP-P3 и SP-R — **приёмочные milestones без кода**; они не заменяют перечисленные атомарные implementation steps. SP-R2, SP-H, SP-5G/5A живут в owning external plans — не повод писать чужой код из SPATIAL. SP-4 = только bootstrap; runtime materialization не активировать до SP-4R/accepted Snapshot. Ни один water-only шаг не обязан дожидаться atmospheric World policy. **Каждый новый класс/POJO/enum/точный файл — после соответствующего architecture freeze**, иначе `OPEN/BLOCKED`; решение не выбирать при кодировании. Любые новые факты о cross-plan contracts → обновить §8, §10–11 и получить приёмку. Текущий план: архитектура, **никаких production code/test/schema/migration changes**.
## 9. Приёмка и негативные сценарии

1. Один frozen source, полное reference окно и union маленьких окон дают **те же доменно определённые** wet/dry, UID, уровни, actual floors, shores/deepening, source mapping; provenance идентичен, не теряется на seams и holes. Invalid/unresolved совпадает как диагностический preview или как типизированный gameplay отказ (не normal `unknown` в успешном gameplay).
2. Отдельно доказаны distinction между no-solid, dry, vacuum, ambient air, local gas и unknown; одинаковый material registry с air годится и для атмосферного, и для безатмосферного мира; sealed-room air не заполняет всю планету. Для SP-A2 — проверена **реальная смена текущего engine default и world config/read/write**, а не только модель в тесте: explicit policy, legacy migration, JSON/import/export и stale-source rejection.
3. Система отказывает при mixed-revision natural/water/river-relief/patch; не использует L0 corridor как доказательство full fine wet; не создаёт реки с неизвестным z_water(x,y).
4. Закрытые/открытые бассейны, острова, negative coordinates, wrapped/sphere seams, disjoint windows; overlap solids/liquids/ore/gases с ясно определённым исходом либо отказом.
5. L2 после grade changes не публикует воду с противоречащим дном без правила reconciliation; pack/read round-trip сохраняет hydrology UID и прочие обязательные facts, не только material key.
6. Во время read_window нет повторного fill, routing, selection, depression-tree, пересборки индексов и полного tile/мира на малый запрос; zero SQL/pack I/O per cell, измеримая bounded cost.
7. Тесты агента — вспомогательная проверка контрактов, не самостоятельное доказательство функциональной корректности. Нужны независимые golden/reference и ручная архитектурная проверка на границы ответственности.
8. Light-bake compact source → L0 projection и union малых L2 окон отражают одно физическое состояние; **SP-4 — bootstrap-only, после игровых patches аналогичное доказательство требует SP-4R и принятого Snapshot runtime apply**; role/width light mask не объявляется достаточным источником fine water geometry. Medium projection можно уничтожить и восстановить без Patch/Snapshot и без materialize всех air/gas/water cells. Неизменившийся океан читается без обязательного patch.
9. Геология: исходные слои почва→глина→порода и независимая рудная линза; раскопка меняет solid/void geometry через доменную операцию и patch, после чего локальная L2-материализация выдаёт правильный материал обнажённых пола/стен/потолка. Никакого нового ore placement, reroll strata или rebuild всего мира при чтении; объекты/постройки не теряют собственный materialization path.
10. W/L: пересыхание даёт zero wet footprint, но сохраняет body UID/lifecycle; системные изменения и физические факты разных revisions не смешиваются. `approx_volume` читается как derived quantity, а не независимо опубликованная истина.
11. World Environment владеет конфигурацией атмосферы: одно и то же material_registry не определяет ambient само; Climate использует явно разрешённые условия, но ни генерация климата, ни weather runtime не создают неявную атмосферу. Динамические локальные газы остаются за Gas Distribution/Runtime Physics, даже если Climate читает их эффекты.
12. Обязательный gameplay bounded-read с неполным/несогласованным domain source, missing artifact или stale revision завершается диагностируемым **ERROR** и типизированным отказом, а не материализацией `air`/dry по умолчанию; проверяется конкретный лог (owner, world, window/scope, refs/revision, request ID), отсутствие дублирования и per-cell шторма. Optional preview/read-only probe может вернуть диагностический unresolved без успешной игровой публикации.
13. На репрезентативной области сравнить доменный исходный verdict (Hydrology: known `coarse_surface_z` + sparse `coarse_hydro`, fine/F и принятые изменения) с bounded SPATIAL результатом: presence/absence совпадают до/после Snapshot; **полностью сухой мир с пустой hydro map и валидной surface не становится unknown** (учесть текущий `if not hydro: return None` в optional `factConsumers/hydrology.py`); пустой shard/отсутствие index hit **не объявляется автоматически dry**. Ни одного нового `CoverageProofService` или отдельного общего `coverage_binding`. Snapshot runtime activation проверяется собственными SP-3S/SP-4R gates; текущий SQL patch path не считать его реализацией.

14. Root-manifest вариант Б: spatial-раздел содержит только по одному логическому entry на domain dataset (не refs каждого shard); маленький root=facts и большой root=index→shards дают эквивалентный bounded результат. Отсутствие root отличается от валидного domain-empty, внутренние seams/negative coordinates не решаются общим manifest, маленькое окно не требует чтения всего домена.

15. **Анти-регрессия «legacy vs target» (обязательный двухэтапный cutover-кейс; §4):**
    - **До реализации:** SP-0 фиксирует два отдельных call graph от реальных API/DAG/bake entrypoints до producer, Pack writer и gameplay/L2 readers, со всеми consumers. Нельзя засчитывать изолированный unit-тест `FineWaterJob` как production activation.
    - **Producer gate G10-A:** инструментированный интеграционный проход с counters/spies по реальным entrypoints показывает **один** native final source на согласованную revision и **ноль** вызовов legacy `WaterBodyPlanner.plan_geo`/его прежней end-to-end ветки после переключения. Никаких двух независимо собранных final hydro plans, dual-run/merge по частям, скрытого fallback, смешанных `PlanRef`. Предыдущий production-route выключен/удалён; оставленный вызываемый альтернативный маршрут — **FAIL**.
    - **Storage/domain-read gate SP-P0/P1/P2R/P2W/P2/P3I/P3W/P3 → SP-3 (bootstrap L2 gate SP-4, runtime L2 gate SP-4R и независимый gameplay gate SP-R):** полный initial fine solve не пишет per-cell SQL; accepted publisher создаёт canonical compact Hydrology root `ArtifactRef` в Pack (лишь один логический hydrology root в manifest), и после холодной перезагрузки из Pack bounded reader выдаёт тот же доменный wet/dry/UID/level/bed verdict. При replay преднамеренно запрещены вызовы всех water producers, legacy `HydrologyWorkingFields` как source и чтение L0 hydro-mask как истины: успешность без них обязательна. Малое L2-окно не вызывает fill/route/второго полного prepare.
    - **Fault injection:** удалить/испортить root или shard при доступных legacy L0/working maps — обязательный gameplay read должен дать typed отказ + `ERROR`, **не** fallback к старому пути. Документированный pre-cutover route и derived L0/L2 projections разрешены только до своего gate/как отдельные проекции; после gate оба альтернативных production source/read маршрута не должны оставаться достижимыми. Сравнение выходных значений без проверки реально вызванных маршрутов недостаточно.

16. **SP-R: независимый gameplay scene-read gate (не SP-4/4R materialization).** На мире с неизменённым океаном, сохранённым только в compact hydrology root, а **не** в water `MapCell`/L2 ZRun/SQL, сделать cold Pack reload и вызвать **реальный** GEN-DAG/engine domain-read consumer от окна по `SceneVolumePolicy`. В ответе для player/LLM/UI наблюдаются UID, wet footprint/level/volume composition нужной области, даже если WP-20 `MergedCellView` для water-only XYZ оказался бы пустым. Контроль: (а) статичный Pack + snapshot changes, pinned revision без смешивания; (б) полностью dry, берег и gas/ambient/vacuum после SP-A2/SP-5A; (в) missing/corrupt root → typed ERROR, не fallback на L0 candidate/legacy SQL; (г) spies запрещают `FineWaterJob.fill`, routing, `FineChunkCompute`/refine, full-world prepare и per-XYZ вызов spatial reader; (д) scene budgets/allocations и единый WS entrypoint соблюдены. Проверка только `FineChunkCompute`, `read_window` unit или debug `GET /scene-volume` **не закрывает** SP-R.

17. **Архитектурный layout + typed contract/POJO/enum + dependency-order gate:** до любой code-итерации проверить полную карту owner/domain/layer/exact target file/import/caller/removal; все утверждённые API/port signatures/typed input/output/error, reuse существующих POJO/enum либо **точные** поля/типы/валидаторы новых/изменённых POJO и значения/семантику enum, совместимость и owners; прямые file counts для каждой затронутой папки с учётом `__init__.py`, пороги 5-file WARN/10-file composition и план всех обновляемых импортов. **Без точного файла, полного необходимого контракта, POJO/enum или согласованной композиции — FAIL**; `OPEN/TBD` внутри затронутого типа блокирует этот кодовый шаг, выбор в момент кодирования запрещён. Отдельно проверить топологический порядок §8: отсутствие циклов, неназванных producers/storage steps, двух активных legacy/target путей, кросс-доменных неявных prerequisites и ложной зависимости Geology от SP-A2. `SP-P2` не может завершиться до SP-P2R/SP-P2W и owning Pack publication gate; `SP-P3` — до SP-P3I/SP-P3W/GEO G10-A; `SP-3` — до SP-P3; runtime L2 `SP-4R` — до SP-4/SP-3S/Runtime Snapshot; `SP-R` — до SP-R1/SP-R2/GEN-DAG/Snapshot. Архивный WS-4 **не является** входным gate. Acceptance tests на отдельных POJO или debug API не подменяют внешний gate. **Пока карта `OPEN`, SPATIAL-1 не готов к production implementation; отдельно применять ARCH-1…ARCH-12 и CODE-READY (§11).**

## 10. Реестр решений и открытые вопросы

**Назначение раздела:** короткий индекс статусов, **не второй нормативный контракт**. Содержательная семантика живёт в §2–7, порядок/owner gates — в §8, доказательства — в §9/§11. Не изменять решение только здесь, оставив другой вариант в основном разделе.

| Принятое направление (2026-11-01) | Нормативная точка | Что ещё OPEN |
|---|---|---|
| Типизированный generic `SpatialSlice[T]`, domain-owned `T`, без универсального voxel `SpatialFact`/solver/оркестратора | §2–3 | Exact read_window signature, POJO/enum, file paths: SP-0/SP-1 |
| Bootstrap `PlanRef` и runtime `WorldPublicationRef` — разные binding; immutable Pack + accepted Snapshot overlay | §3/§7 | Pinning, domain invalidation и typed revision contract: SP-1/SP-3S |
| Native final Hydrology с exact fine F/routes/bed dependencies — единственный canonical source, sparse absence interpreted owner | §3–4 | GEO G10-A production proof и full final coverage: SP-H; SP-P3I/SP-P3W |
| Начальный river `z_water(x,y)`/wet footprint/перепады принадлежат Hydrology, bed — Terrain/Relief | §4 SP-H2 | Алгоритм/wire/POJO профиля и river-volume activation: GEO-1 SP-H2 |
| Runtime geometry → Physics decision → DAG domain call → Hydrology change → Snapshot, без прямого Physics→Hydrology | §2/§4/PHYSICS-1 | Exact typed requests/patches/invalidation и DAG ports: owning plans |
| Canonical media facts не обязаны быть L2 cells; temporary projection ≠ physical geology/solid/object materialization | §3/§5 | Typed output/revision/cache, bootstrap SP-4 и runtime SP-4R отдельно |
| World Environment объявляет атмосферу, Climate — потребитель; отсутствие записи не означает ambient/vacuum | §2/§6 | Existing WorldEnvironmentSettings/World.world_environment reuse, API/engine policy и миграция: SP-A0/A1/A2-1…5 |
| World Pack вариант Б — domain-root ArtifactRefs в Manifest, внутренние shards/index только у домена, без per-cell SQL | §7 SP-PACK-V1 | Root fields/schema/codec, artifact transport SP-P2R/P2W и Hydrology root SP-P3I/P3W |
| Presence/absence/coverage owner — домен; mandatory gameplay invalid/unresolved → typed ERROR, optional preview может показать unknown | §3/§7 | Exact error enum/log route и consumer policy: SP-1/SP-R0; no generic coverage solver |

**Открытые архитектурные решения и владельцы:**

- **SP-A0/SP-A1 — air/world policy:** точные consumers, precedence world/region/room overrides (если нужны), норматив compat/migration для существующего `World.world_environment`, CRUD/API/engine fallback removal. **POJO/enum уже частично существуют**; цель — reuse, не автоматическая новая модель.
- **PHYSICS-1/GEN-DAG/Snapshot:** typed Physics request/result, domain PatchSet, target revisions и invalidation scopes для Geometry → Physics → DAG → Hydrology → Snapshot. Владелец маршрута согласован, реализация и exact contracts OPEN (§4).
- **SP-P0/SP-P1/P2R/P2W/P3I/P3W:** exact root-entry POJO/owner key, ArtifactRef registry/codec, absent-vs-empty, bounded index/shard, provenance, manifest version/migration, staging/GC/rollback. Вариант Б не переоткрывать (§7).
- **SP-M/SP-G:** typed output/projection и bounded физическая geology materialization с существующими terrain/ore/cave/excavation callers. Source strata owned by Geology, solid/void by Terrain; cache ≠ Patch (§3/§5).
- **SP-R0/R1/R2/R — реальное игровое чтение:** какой GEN-DAG/engine consumer и typed POJO получает media-only water окно через **прямые domain.read**, где законно выполняется composition, как убрать legacy `MapCell`/SQL fallback. [Архив WS-0/4](./world-state-crud-ws0-freeze.md) — лишь AS-IS inventory; ни WS `SceneQuery`, ни central WorldStateService не являются target/gate. R2 реализует owning GEN-DAG план, SP-R только E2E proof.
- **SP-4/SP-4R:** bootstrap L2 от immutable Pack допустим до runtime Snapshot; после gameplay changes требуется pinned base+accepted overlay и SP-4R, без full-world rematerialization (§5/§8).
- **Layout/contract freeze:** до любого кодового шага нужны exact owner/domain/layer/file counts/import graph, typed input/output/error/POJO/enum, dependencies и negative cases по §8/§11. SP-0 принят (§0.15); exact проект SP-1 на приёмке (§14); SP-P0/R0/A1/M/G ещё OPEN; P2/P3/A2/R milestones **не код**, а отдельные acceptance gates.

**Текущее решение:** выбранные семантические границы не означают `CODE-READY`; внешние GEO G10-A, staged Pack, Snapshot runtime и GEN-DAG остаются blockers своих dependent steps. Никакого параллельного WS read layer или нового Spatial orchestration service не создавать.
## 11. Архитектурная приёмка (Definition of Done)

**Статусы не смешивать:** согласованное направление (§3–7) ≠ формально принятая архитектура ≠ разрешение на код ≠ production cutover. Приёмка проводится **по границам затронутого шага/трека**; независимые Geology/Gas/Air-гейты не объявлять обязательными для водного code step. Но неразрешённая зависимость **самого шага** всегда блокирует его выполнение.

### 11.1. Критерии архитектурной приёмки (ARCH-AC)

Для каждого пункта в SP-0 и соответствующем архитектурном freeze нужно предъявить **проверяемое evidence с ссылками на существующие классы/ТЗ и результат решения**. Набора формулировок «будет сделано» недостаточно. Критерии ниже — архитектурные: production-тесты и фактический cutover принимаются позже по §9.

| ID | Что должно быть принято | Доказательство / обязательный FAIL |
|---|---|---|
| **ARCH-1: owner/SoT** | Для каждого пространственного факта установлен единственный владелец и writer; Spatial — read contract, не универсальный solver и не новый orchestrator. | Матрица Hydrology/Geology/World Environment/Gas/Terrain/Physics/DAG/Snapshot с fact → owner → producer → consumer → право mutation. **FAIL:** два независимых владельца либо Spatial самостоятельно решает wet/dry, ore или ambient. |
| **ARCH-2: end-to-end data flow** | Показаны **два** пути: bootstrap world description → native GEO final → immutable Pack domain-root → domain reader → L2 **и** GEN-DAG/engine gameplay; runtime Physics request → DAG → domain PatchSet → Snapshot → pinned overlay → тот же bounded read. | Две AS-IS/TO-BE caller/dependency maps от реально существующих entrypoints до engine/LLM/UI consumers, с owner каждой границы, explicit seam/OPEN для пока не реализованного (§4/§8). **FAIL:** путь заканчивается на isolated reader/debug API или требуется прямой Physics → Hydrology call. |
| **ARCH-3: typed API contracts** | Точны signatures, input/output/error, revision/coordinates/window semantics, producers/consumers и совместимость каждого затронутого public/межслойного port, включая generic SpatialSlice[T]/read_window и GEN-DAG/domain.read typed consumer output (без WS mediator). | По каждому port: owner, exact method contract, linked ТЗ, caller map и обработка ошибок. **FAIL:** generic dict/строковые magic-коды, скрытая конверсия либо неописанный adapter заменяет договорённый контракт. |
| **ARCH-4: POJO/enum freeze** | Утверждены reuse/new/migrate для всех нужных POJO/enum, все поля/типы/nullable/default/validators и значения/семантика enum; wire/schema/version, где применимо. | Единая таблица type → exact file → owner → fields/variants → producer/consumer → reuse/migration. Если новых типов не нужно — явное обоснование. **FAIL:** необходимые POJO/enum/вариант/поле оставлены OPEN/TBD или возникают при кодировании. |
| **ARCH-5: file/layer layout** | Для каждого нового/изменяемого класса дан точный target path, domain/layer, разрешённые imports и судьба legacy caller; композиция каталогов соблюдена. | Карта файлов §8, import graph, file counts до/после (+ __init__.py), 5-file WARN / 10-file limit по folder-composition.mdc. **FAIL:** выбор папки во время кода, пересечение владельцев или нарушение лимита. |
| **ARCH-6: revision/lifecycle** | Immutable Pack не мутируется в gameplay; PlanRef bootstrap отделён от WorldPublicationRef и accepted Snapshot; local изменения и invalidation не смешивают разные revisions. | Конкретный read/pin/overlay/invalidation contract и ситуации stale/conflict/partial patch. **FAIL:** смешанные geology/geometry/water facts или новый независимый spatial state store. |
| **ARCH-7: presence/absence/error** | Наличие/отсутствие определяет домен, различены valid dry, vacuum, ambient, local gas, unknown/corrupt/missing source. | Типизированные outcomes и ownership логирования; mandatory gameplay failure даёт ERROR с world/scope/revision/request ID, а optional preview может показывать unresolved. **FAIL:** пустой shard молча становится dry/air либо есть fallback на L0/legacy SQL. |
| **ARCH-8: materialization boundaries** | Canonical compact water/gas/ambient facts не требуют persisted MapCell; bounded medium projection временная; geology/solids и объекты сохраняют собственные правила материального представления. | По типам output — owner, source revision, lifetime/cache, условия physical materialization и инвалидация; excavation показывает исходный материал без reroll. **FAIL:** materializer заново принимает placement/physics решение или пишет per-cell среду. |
| **ARCH-9: Pack and production cutover** | Manifest содержит domain-root refs (вариант Б), domain-owned shards/index; старый и новый production producer/read route не остаются одновременно достижимыми после gate. | После joint contract agreement независимы GEO G10-A/SP-H и storage SP-P0/P1/P2R/P2W/P2 по собственным gates; accepted source + SP-P0/P1 сходятся на SP-P3I, далее SP-P3W/P3 → SP-3/3S → SP-4/4R и SP-R1/R2/R. G10-A не prerequisite SP-P0/P1. Схемы storage/legacy closure и fault cases §9/15–16 обязательны. **FAIL:** двойной source/Pack writer, неполный root или успешный read после corruption через legacy fallback. |
| **ARCH-10: cost model** | Отдельно оценены **разовый** initial fine solve и Pack publication (без per-cell SQL) и **повторное** bounded read (без full-world/fine solve); материализация запускается по требованию. | Явная модель стоимости initial bootstrap и O(окно/необходимые shards) для повторного чтения, перечень I/O/allocations, способ измерения и **согласуемые**, а не выдуманные numerical budgets. **FAIL:** маленькое окно требует full-world prepare/route/fill. |
| **ARCH-11: external integration gates** | Указаны точные контракты и owners зависимостей GEO-1 G10-A, staged Pack publication, runtime Snapshot, Domain Patches domain.read, DAG-TYPING/GEN-DAG; архивный WS-4 не является gate; архитектура не объявляет их реализованными. | Таблица external gate → owner plan/ТЗ → required contract → blocking SP step. **FAIL:** чужую неподтверждённую реализацию считать DONE или обойти прямым вызовом. |
| **ARCH-12: порядок и отрицательные сценарии** | Кодовые этапы §8 атомарны, топологически упорядочены и независимые треки не превращены в ложные глобальные зависимости; запретные маршруты проверяемы. | Для каждого шага prerequisites, exact files/contracts, отдельные positive/negative acceptance cases §9; проверка циклов, двух путей, stale revisions и отсутствующих источников. **FAIL:** переход к consumer до producer/publication либо «тест прошёл» без реального caller path. |

### 11.2. Разрешение на отдельный кодовый шаг (CODE-READY)

У каждого кодового шага статус по умолчанию **BLOCKED** до выполнения одновременно всех условий:

1. **Архитектурная приёмка его области:** все применимые ARCH-1…ARCH-12 и соответствующие SP-0/1/2/A0/A1/M/P0/R0/G decisions приняты с evidence, нет необходимых OPEN/TBD.
2. **Contract/POJO/enum + file freeze:** точные signatures, поля/значения, ownership, paths, imports, schema/version/migration (если нужны); не создавать новые POJO/enum/adapter без утверждённого обоснования. Глобальные требования code-gates.mdc и folder-composition.mdc соблюдены.
3. **Входные prerequisites §8 приняты:** в том числе внешние gates владельцев GEO/Pack/Snapshot/Domain Patches/GEN-DAG, **если именно этот шаг** от них зависит. Принятая архитектура не подменяет реализацию чужих gates.
4. **Проверка заранее определена:** ссылка на точные разделы docs/tz_*.md, позитивные и негативные сценарии §9, диагностируемая ошибка без fallback, golden/cold Pack/revision evidence где применимо и измерения стоимости. Каждый шаг — один атомарный контракт/слой/группа файлов.
5. **Есть явная команда пользователя на код.** Общее согласие с архитектурой и этот документ сами по себе не являются разрешением на реализацию.

Если хотя бы одно условие не выполнено — **BLOCKED**, возвращаемся к архитектурному шагу, документируем нерешённый вопрос и согласуем обновление. Нельзя принимать code step на основании только unit-тестов POJO или debug endpoint. **PRODUCTION DONE** подтверждается отдельно реальными end-to-end cutover сценариями §9, а не этим checklist.

### 11.3. Специфика общего SPATIAL-1 DoD и текущий статус

Архитектурный пакет должен сохранять: минимальный типизированный generic contract без общего material-filled XYZ, domain-owned source/reader и exact hydrology final coverage; вариант Б World Pack с domain roots, immutable base + accepted Snapshot overlay и различением PlanRef/WorldPublicationRef; разные bootstrap L2 SP-4 и runtime L2 SP-4R bounded media, domain.read/GEN-DAG gameplay read SP-R и geology/solid/object materialization; границы Hydrology ↔ W/L ↔ Runtime Physics/DAG; состав воздуха как World Environment (а не Climate), typed ambient/vacuum settings, миграцию legacy air fallback и независимый SP-A2; source semantics, typed errors/logs и cost budget. Эти решения должны иметь конкретные contracts/POJO/enum и file map по ARCH-1…ARCH-12, **не только текстовое согласие**.

**Текущее состояние (2026-11-01):** SP-0 **DONE по явной приёмке пользователя** (§0.15); архитектурный проект SP-1 **НА ПРИЁМКЕ** (§14), freeze ещё не принят. Направление/границы согласованы, но общие ARCH-ACCEPTED и CODE-READY **не достигнуты**. Архитектурные SP-P0/M/R0/A0/2/A1/G — OPEN; code steps SP-A2-1…5, SP-P1/P2R/P2W/P3I/P3W, SP-3/3S, SP-4/4R, SP-R1/R2 и внешние SP-5G/5A — OPEN; milestones SP-A2/P2/P3/R — OPEN. GEO-1 G10-A, final coverage, staged Pack publication, runtime Snapshot, GEN-DAG/DAG-TYPING integration и Aerial A4 не объявлять принятыми без evidence в owning plans. **Архивный WS-4 не gate.** Прогресс независимого трека не отменяет blocker другого.

Изменения этого документа: planning only, без production code, POJO, migrations, tests, schema или runtime cutover.


## 12. Уточнение: возможность материализации воды и граница с GEO-1 (2026-11-01)

Зафиксировано по запросу владельца: **вода допускает явную материализацию**,
когда она нужна конкретному consumer. Это возможность spatial/application пути,
а не требование заранее создавать fine/XYZ-клетки всего бассейна или мира.
Общий контракт ограниченной пространственной выдачи, режимы projection/materialization
и L2 integration проектируются в SPATIAL-1 (SP-0/1/M/3/4). **Hydrology владеет
compact water source, подготовленным индексом и реализацией доменного reader**;
SPATIAL не создаёт самостоятельный runtime-сервис или второй индекс.
Новая жидкостная динамика остаётся PHYSICS-1, не переносится в generic reader.

Три разные операции не смешивать:
- **Physical resolution / подготовка принятого источника:** Hydrology владеет
  fill/spill/merge, связностью, фактическими уровнями/UID, wet/dry/unknown и
  согласованием basin/river facts с Terrain. Подготовка может требовать анализа
  всего связного бассейна; из этого не следует обязанность хранить все fine клетки.
- **Оконное пространственное чтение:** Hydrology-owned reader реализует общий
  SPATIAL read-контракт и читает принятую revision, возвращая typed domain
  slices/intervals с доменной семантикой coverage/absence/unknown. В `read_window`
  нет нового fill, выбора уровня, routing или мутации мира; generic SPATIAL
  контракт сам не определяет wet/dry.
- **Материализация воды по запросу:** application materialization использует
  hydrology-owned spatial implementation через общий SPATIAL-контракт, разворачивая
  необходимые water cells/columns/volumes в ограниченной XYZ-области. Готовность
  geometry/levels/material UID и соседние зависимости определяются профильными
  контрактами. SPATIAL отвечает за границу/представление, Hydrology — за смысл
  water facts; оркестратор только вызывает публичные операции.

SP-M/SP-4 должны явно предусмотреть временную medium projection и, отдельно,
явную локальную материализацию воды для consumers, которым недостаточно slices
(в том числе PH-LOCAL). Конкретные POJO, cell/column/interval формат, API и условия
persist OPEN после SP-0. Отдельный постоянный cell store не вводится автоматически;
существующие World Pack / Snapshot boundaries сохраняются. Освобождение временной
материализации не отменяет принятые изменения мира. Полная локальная materialization
для Physics не означает full-world/full-basin fine materialization.

**Полнота fine evidence не равна dense enumeration:** source обязан достоверно
отвечать wet/dry/unknown, UID, level и geometry в пределах заявленной coverage,
но конкретное компактное представление и доказательство точности ещё требуют
SP-H/GEO producer review. Нельзя объявить произвольную compact mask достаточной
или просто заменить solver локальным flood по запрошенному окну.

Связанный новый входной вопрос SP-H/SP-0: текущий FineWaterJob.fill требует полной
fine terrain мира и возвращает перечисленные fine факты. Это существующий
исполняемый/reference путь, **не утверждённая обязательная целевая модель** для
больших водоёмов. До G10-A production cutover пересогласовать producer scope,
representation/coverage, стоимость preparation и bounded materialization.
Нельзя закреплять обязательное раскрытие каждого принятого coarse footprint в
S^2 fine клеток всего бассейна ни до P2, ни после него только ради стыковки типов.
Решение о placement coordinate space само по себе эту проблему не закрывает.

Приёмка дополнения: compact source и materialization выбранных/disjoint окон
дают те же водные UID, уровни, membership и дно на одинаковой revision; reader
не запускает solver, маленький запрос не разворачивает весь бассейн/мир; фактически
измерены размер retained source, размер materialized окна и объём зависимостей.
Стоимость domain preparation измеряется отдельно, без ложного обещания O(window)
для глобальной hydrology операции. River volume остаётся заблокирован SP-H2.

Только уточнение архитектурного направления/распределения работ. Код, POJO и
production не менялись; SPATIAL-1, G10-A и точные контракты остаются OPEN.


## 13. Соответствие контрактов и порядок freeze

Это таблица связей, не копия доменных POJO. Каждая спецификация имеет одного
нормативного владельца; остальные планы ссылаются на неё.

| Предмет | Нормативный владелец | Проверяемое соответствие |
|---|---|---|
| **Hydrology Output:** принятые water facts / canonical source | [GEO-1, начальный контракт](./geo-1-designed-water.md) | Typed water payload реализует семантические требования общего read, сохраняет identity/levels/geometry и source meaning |
| **SPATIAL Input/Read:** bounded XYZ-запрос/результат | SPATIAL §3 | Domain-owned Hydrology reader реализует общий typed контракт; нет отдельного Spatial service/универсального coverage solver |
| Reuse исходных сущностей | SPATIAL §7 V1-D | GEO выбирает reuse/migrate/new с обоснованием по этой карте; WorldPublicationRef не подменён PlanRef/WorldSnapshotRef |
| Root representation/Pack format | SPATIAL §7, SP-P0 | Domain payload регистрируется существующим ArtifactRef/format механизмом принятого варианта Б; exact wire/versions freeze после выбора представления |
| Локальная materialization | SPATIAL §5/12 | Application consumer использует согласованные bounded slices; окно не меняет water resolution и не требует materialize всего мира |
| **DAG Binding:** typed передача результатов/зависимостей; concrete node contracts | [GEN-DAG-1](./gen-dag-1-post-geo-ws.md) | Композиция принятых доменных POJO без копирования полей; RequiredOutput обозначает зависимость ноды, не public domain.read |
| Runtime changes/publication | [Domain Patches](./world-domain-patches-snapshots.md), [PHYSICS-1](./physics-spatial-dynamics.md) | Typed запрос Physics и domain patch отделены от read; Snapshot принимает изменения |

Для **DAG Binding** сейчас согласуются требования typed передачи/ссылок,
зависимостей и revision consistency без прямой междоменной оркестрации. Это
третья часть согласования, а не ещё одна копия WaterFacts. Конкретные имена
нод, их Input/Output POJO, RequiredOutput declarations и wiring фиксирует GEN-DAG
после доменных контрактов. Bootstrap передача результатов и gameplay domain.read
различаются в путях ниже; цикл зависимостей GEO ↔ GEN-DAG не вводится.

**Порядок архитектурной приёмки:** (1) инварианты, (2) выбор представления с
ценой/качеством и geometry/coordinate/revision решениями, (3) точный freeze
POJO/enum/файлов соответствующим владельцем, (4) разрешение на код. Никаких
TBD обязательных полей при code-ready; до окончания архитектуры поля допустимо
оставлять OPEN вместо преждевременного утверждения. Каждый последующий шаг
проверяется по замороженному контракту, изменение которого требует явного review.
GEN-DAG получает доменные контракты после GEO; его конкретный node freeze не
является входным gate GEO producer. Общие engine требования совместимости
учитываются без предварительного проектирования конкретных нод в GEO.

**Разные пути исполнения** (имена операций/типов концептуальные, не freeze классов):

```text
Bootstrap:
DAG → Hydrology.generate/final (canonical facts)
    → Hydrology-owned compact representation → immutable Pack domain-root

Gameplay:
DAG → Hydrology.read_window(window, WorldPublicationRef)
    → SpatialSlice[WaterFacts] → gameplay composition / L2 consumer

Physical changes:
Physics → DAG → Hydrology.patch → Snapshot
```

Gameplay reader использует сохранённый Pack и принятый Snapshot overlay pinned
публикации. Новая генерация или fresh Hydrology NodeOutput в том же execution
не требуется. Domain-owned reader реализует общий SPATIAL контракт; read не
выполняет patch/physics/fill. DAG — единственный междоменный orchestrator.
Typed failures обязательного gameplay read и диагностический preview/unresolved
различаются по §3; KnownFact/UnknownFact не навязываются как универсальный результат.

Сверка reuse подтвердила уже перечисленные POJO; добавленный audit не вводит
дубликаты. FineTerrainZRun/L0 mask остаются производными, не water SoT;
TerritoryVolume не становится generic window без обоснования. Ограничение
BaseModel для output ноды учитывает GEN-DAG, оно не требует замены доменного
результата или создания node-wrapper внутри GEO. NativeFinalWaterQuery не
объявляется готовым runtime Pack+Snapshot/XYZ reader.

Редакционная консолидация 2026-11-01: удалены повторные audit/reconciliation/
ownership-correction блоки и зеркальная вводная спецификация. Существующие
SPATIAL §§2–11 и архитектурные gates сохранены. Изменена только документация;
реализация SPATIAL/engine DAG не выполнялась, G10-A/SPATIAL OPEN.

### Уточнение приёмки SP-R0/SP-P3W и области water — GRAPH-Q02/Q03/Q04 (2026-11-01)

- **SP-R0 (GRAPH-Q09):** принятые SP-1 + SP-M разрешают начало проектирования SP-R0. В ходе этого шага SPATIAL ведёт запись совместного evidence в своей карте §8: domain owners подтверждают scene/read contracts и revision semantics, GEN-P0 owner — требования и mapping конкретных consumer node IDs/callers. Evidence включает owner композиции, typed Input/Output/error, pinned revision, exact POJO fields/types/validators, enum semantics, file/import map и ссылки на согласованные доменные контракты. Совместное согласование этого пакета **является критерием приёмки SP-R0**, а не внешним входным gate самого шага. Принятый SP-R0 передаёт этот пакет в SP-R1 и для соответствующих concrete bindings GEN-P0; завершение всего GEN-P0 или production cutover для этого не требуется. Отдельный alias SCENE-READ-FREEZE удалён из графа. Exact contracts и сама приёмка SP-R0 остаются OPEN.
- **SP-P3W:** помимо SP-P3I + SP-P2 + SP-H требуется принятый DAG/World Pack контракт вызова staged publisher из light-bake entrypoint (`PACK-ENTRY-CONTRACT`). До кода перечислить entrypoint/caller, owner, exact typed input/output/errors, revision/manifest binding и правила publication/rollback. Isolated root-publication proof использует этот контракт; production bake E2E остаётся GEN-BAKE. Контракт OPEN; ни весь GEN cutover, ни обходной legacy publisher не становятся prerequisite/заменой.
- **River scope:** SP-3/SP-R для open-water ocean/lake не принимают river-volume query. Речной z_water(x,y), профиль/POJO/wire и отдельное reader/E2E evidence требуют GEO/Hydrology SP-H2. До их приёмки речная volumetric activation отложена; нельзя выводить liquid thickness из одного RIVER_BED/UID. SP-H2 не блокирует ocean/lake path. Exact river contracts остаются OPEN.

## Legacy inventory — предварительный, требует уточнения

**Статус: OPEN / НЕ ПРИНЯТ.** Scope — этот owning-план в WORLD-PLAN-GRAPH-1. Определения символов и приведённые call sites/factories найдены; таблица — начальный inventory, не полный аудит production wiring. Наличие target файла не означает включение target в production. Все строки требуют уточнения replacement, полного closure callers/регистраций и конкретного отключения/переноса/удаления; код не менять по этой таблице.

| AS-IS / legacy-кандидат: определение | Caller / DI / registration | Target / граница замены | Gate и оставшаяся проверка |
|---|---|---|---|
| [MapCellQueryFacade.get_scene_volume_as_map_cells](../../backend/app/application/worldData/mapCells/mapCellQueryFacade.py) (строка 155) | [MapCellService.get_scene_volume](../../backend/app/application/worldData/mapCells/mapCellService.py) (строка 166) | TARGET/OPEN: SP-R0/R1 typed media response; legacy-кандидат только для заменяемого water read | SP-R2/SP-R; whole facade не объявлен к удалению; **УТОЧНИТЬ** полный caller graph, replacement и disposition |
| [MergedCellView](../../backend/app/dataModel/worldPack/wire/mergeMapCells.py) (строка 65) | [MapCellQueryFacade.get_scene_volume](../../backend/app/application/worldData/mapCells/mapCellQueryFacade.py) (строка 131) | TARGET/OPEN: domain water slices; solid/debug DTO может сохраняться | SP-1/M/R0; не удалять DTO по одному water use case; **УТОЧНИТЬ** полный caller graph, replacement и disposition |

**Evidence 2026-11-01, HEAD `3a714326` + текущий working tree:** `rg` по именам символов и вызовам в `backend/app`, чтение найденных цепочек GEO/read/engine, AST-проверка определений всех символов таблицы. Известные ограничения: runtime не запускался; DI factories не равны доказательству вызова; exhaustive imports/re-exports/строковые IDs, tests/fixtures и динамический wiring ещё не проверены. **LEGACY-AC OPEN**, полнота и отсутствие mixed runtime не доказаны. При следующем уточнении повторить `rg -n` по каждому символу и старому ID, проверить вызывающие методы и registry closure, записать exact target/disposition и evidence.


## SP-0 — фактическая карта AS-IS (2026-11-01)
**Текущий статус: DONE, принят пользователем; evidence §0.1–0.14, приёмка §0.15.** Последующие записи «НА ПРИЁМКЕ» в истории описывают состояние до явной приёмки. LEGACY-AC последующего cutover остаётся OPEN.

**История до приёмки (§0.15): SP-0 НА ПРИЁМКЕ; DONE ещё не присвоен, LEGACY-AC OPEN.** Основной аудит выполнен статически на базе `05dbca5d` + working tree. Исторически до начала уже был изменён `world-generation-plan-dependency-graph.md`; первоначальный аудит его не менял. Уточнение по ревью на базе `72d61d44` добавляет §0.10–0.12 и синхронизирует строку SP-0 в графе. Ни код, ни тесты, ни schema, ни регистрации не изменены. Новые архитектурные решения не приняты. Статусы остальных SP-шагов и разрешение на код не меняются.
### 0.1. Метод и границы evidence
Прочитаны определения и тела ключевых producer/read/materialize методов; выполнены поиски имён, call sites, строковых node IDs, HTTP routes и регистраций по `backend/app`, `backend/tests`, планам и `frontend/src`. Ниже машинно извлечены объявления и прямые import edges из AST всех Python-файлов `backend/app` без импорта модулей. Это статический caller/import inventory, а не доказательство исполнения на конкретном мире. Backend, solver и runtime не запускались; наличие теста означает только наличие сценария, не его прохождение. Динамические `context[...]`, `node_results[...]`, registry/factory связи описаны отдельно. Отрицательные результаты ограничены названным поиском; runtime closure не объявляется доказанным.
### 0.2. Producer: legacy против native GEO
1. **Подключённая factory:** `core/container/worldData.py:surface_planning` → `register_world_plan_providers` (`planning/composition/planProviders.py`) → `WorldPlanProviders`. Регистрация final использует `HydrologyPlan` и `HydrologyFinalPlanProvider`, routes — `HydrologyRoutesPlanProvider` с `WaterBodyPlanner`, `CoarseRiverPlanner`, `FineRiverPlanner`, `DeclaredWaterPaintProjector`. `surfacePlanningCapture` фиксирует входы, `surfacePlanningAssembler` требует refs через planning service; local climate зависит от final. Это фактический путь factory, не новый native cutover.
2. **Native definitions:** `GeoWorldPlanProviders` типизирует `GeoHydrologyPlan`; `GeoHydrologyFinalPlanProvider` определён в том же provider-модуле. `WaterBodyPlanner.fill_fine`/fine publication → `FineWaterJob.fill`; native final publication связывает fine water, pre-water terrain, routes и river refs. Native final provider регистрируют integration/typing tests (`tests/geo1/integration/test_revisions.py`, `tests/typing/planning/valid/terrain/geoPipeline.py`). Production factory выше его не регистрирует. Не считать тестовую сборку production-активацией G10-A.
3. `FineWaterJob.fill(window: FineSurfaceWindow, inputs: GeoHydrologyPlanInput, ..., control: PlanBuildControl) -> PlanBuildResult[FineWaterResult]` проверяет точную fine topology и `len(surface_z) == bounds.width * bounds.height`, затем применяет basin floor и `assemble_water_bodies`; даже disabled branch находится после проверки полной поверхности. `FineWaterResult = tuple[FineSurfaceWindow, AssembledWater]`, `MaterializedWater.cells` перечисляет fine факты. Это существующая цена preparation; bounded compact source ею не доказан.
4. `NativeFinalWaterQuery` принимает два envelope и expected refs, проверяет fingerprints/dependencies/diagnostics и один раз admission coverage. `water_at(FineXY)` возвращает `KnownFact[EntityUid | None] | UnknownFact`: отсутствие строки сухо только внутри observed spans; вне — UnknownFact. Он отвечает XY identity, не XYZ volume/level/material composition; не читает Pack/Snapshot. Найденные внешние consumers — water-query и typing tests.
5. **Точки будущего cutover, без решения о реализации:** production provider registration; тип final в bundle/working fields и downstream climate/terrain; native facts → durable domain root publisher; cold Pack reader → bounded domain facts. Сегодня последней пары в manifest/read wiring нет. Нельзя доподключить native query рядом с legacy и объявить оба production-маршрутами принятой SPATIAL архитектуры. Точные replacement/disposition принадлежат SP-1/P0/H/R0.
### 0.3. L0/L2, materialization и потери водных фактов
`HydrologyWorkingFields.from_plan(HydrologyPlan, SurfaceGridSettings)` строит immutable mappings coarse hydro/surface и tile indices fine z/hydro. `TerrainBatchOrchestrator.build_tile_surface_state` использует fine overrides и parent L0 hydro corridor, merge с sparse fine hydro; `fineTilePrep` готовит контекст до chunk workers. `fineChunkCompute.compute_rect` делает discover/paint, затем `generate_chunk_cells_sync` → `TerrainGeneratorService.generate_surface_chunk` → `run_column_fill`. Water metadata прикрепляется к surface cell, это не liquid volume fill над дном.
`mapCellToFineTerrainWire` сжимает terrain/material z-runs; `FineTerrainZRun` не имеет hydrology UID/level/composition. Поэтому перенос hydrology в transient MapCell не означает сохранение canonical water в L2 blob. L0 `HydrologyMaskWire`/`WorldMapCellWire` хранит обзорные роли/поля; `WorldMapPackReader.world_map_contribution` на surface_z создаёт dict role/liquid_candidate, ниже — subsurface terrain до n_base, выше — None. Отсюда невозможно восстановить полноценный XYZ water volume.
`regions/factConsumers/hydrology.contribute` — optional coverage consumer: `not hydro` возвращает None даже при полностью известной сухой surface. При непустом hydro отсутствующие записи считаются dry только при полном попадании context.cells в coarse_surface_z. Это конкретный negative case, не готовая обязательная gameplay error policy.
### 0.4. Scene/API/engine — разные фактические цепочки
- **DI:** `PacksWiring.pack_read_services(world_uid)` → `build_pack_read_services` → `MapCellQueryFacade` + `PatchStoreService`, world-map reader, region-state overlay; factory кешируется по world_uid. `MapCellService` получает read factory.
- **Debug HTTP:** `GET /worlds/{world_uid}/map/scene-volume` (`api/routes/map.py:440`) → `MapCellService.get_scene_volume` → при Pack `gameplay.get_scene_volume_as_map_cells` → `get_scene_volume` → `get_cells` → `_layers_at` + `merge_layer_batches` → `MergedCellView.has_any_data` → `merged_view_to_map_cell` → HTTP serialization. Без Pack service идёт в repository bbox. Scene radius разворачивает все XYZ coordinates окна, загружая patches bbox одним запросом.
- **Point/batch:** `get_cell` при отсутствии переданного patch читает SQL patch, затем merge. `get_cells` принимает уже загруженный dict координат/patches. Point caller — `PackFineTerrainReadFacade`, также debug facade; debug batch использует `get_cells`. Layers: patch, fine terrain, city structure, location terrain, L0 world map; region overlay и climate применяются после сборки. Это Pack + SQL patch merge, не pinned Snapshot read.
- **Media loss:** `has_any_data` признаёт hydrology dict данными, поэтому hydrology-only существующий contribution не фильтруется сам по себе. Но отдельного medium slice вне клетки здесь нет: отсутствующие contributions/XYZ выше surface исчезают до фильтра; затем DTO/MapCell serialization передают только cell fields. Будущий SpatialSlice сам по себе в эти результаты не попадёт.
- **Реальный engine:** `nodes/__init__.py` импортирует terrain nodes; `@register_python` регистрирует `check_terrain/eager_terrain/lazy_terrain/terrain_context/terrain_summary`. `core/container/engine.py` кладёт `map_cell_repo` в context. `eager_terrain.execute` читает `context[map_cell_repo].get_by_location`, сериализует `asdict`; empty при has_terrain вызывает `EagerTerrainEmptyError`. `lazy_terrain` генерирует anchor при отсутствии terrain. `terrain_context` выбирает eager/lazy cells и записывает `shared_context[terrain]`; summary/weather consumers зависят от terrain_context. Этот путь не вызывает debug scene-volume или native water query. Media без MapCell здесь отсутствуют уже на repository input.
- **Архив/target:** `world-state-crud-ws0-freeze.md`/WS-4 SceneQuery — архивная спецификация, не действующая точка подключения. В `world-domain-patches-snapshots.md` принят прямой `DAG → domain.read(query)`, конкретные consumers/migration перечисляет `gen-dag-1-post-geo-ws.md`. Точные bounded scene Input/Output/errors и owner композиции остаются SP-R0; новый центральный SceneQuery/Facade этим аудитом не проектируется.
### 0.5. Pack, staging, publication и registration
`WorldPackWriter` использует `WorldPackPaths`, `TileCodec`, `PackManifestStore`, path-based blob writers и `_atomic_write`; `PackManifestStore.save` пишет temporary file и os.replace. Это атомарная замена файла, не доказательство общей staged publication всех roots. `WorldPackManifest` содержит tiles/chunks/location/settlement/region metadata; domain spatial root ArtifactRef коллекции нет.
`ArtifactRef` уже различает BLOB/SQL_ROWS, format/version/hash/nbytes/row_count. `ArtifactFormatContract` + `ArtifactFormatRegistryBinding.register(contract, backend)` — существующая точка привязки формата к backend; resolve проверяет identity контракта, registry проверяет версии и exact content model. `IArtifactStaging` имеет open_operation/reserve/seal/finish_preparation/verify/recover/cancel/collect; storage ports и encoding manifest существуют. Ни наличие Protocol, ни canonical type registration не означают подключённый water-root publisher. Production PacksWiring выше не собирает такой publisher. **Точки root-format registration и manifest publication для Hydrology отсутствуют; exact keys/wire/fields не выбирать в SP-0.**
`WorldPublicationRef` уже содержит world_uid/publication_id/pack_hash/snapshot_head/active_timeline_id/gameplay_started и coherence validator. PlanRef описывает provenance producer, не заменяет этот runtime binding. `IWorldSnapshotApply.apply(PatchSet[S]) -> SnapshotApplyResult` — Protocol; SQL publication stores не превращают текущий MapCellQueryFacade в Snapshot-aware reader.
### 0.6. Solids, ores, W/L и excavation
`TerrainGeneratorService.generate_surface` → surface pass → gap analysis → column fill. Fill выбирает surface/subsurface terrain и отдельную magma band, материализует ограниченную глубину; это не стратиграфический geology source. `generate_ores(World, list[MapCell]) -> list[MapCell]` — stub: около 3% subsurface cells, iron либо первый registry material, возвращает material-only клетки. Поиск generate_ores в backend/app нашёл только определение: действующий production caller не подтверждён; удалённый generate-ores HTTP route не восстанавливается по docstring/старой ошибке.
W0–W3 принадлежат `hydrology-water-systems.md`: PhysicalWaterUnion/WaterSystemKind/UID helpers уже существуют; это producer identity/union facts. W1 systems POJO, W2 dynamic consumer, W3 atomic lifecycle writer нельзя объявлять готовыми по одному physical union. Dry-state/lifecycle, membership и измерения остаются owning W/L контрактами, отдельного SPATIAL writer не найдено/не предлагается.
Поиск `excavat|digging|terrain_delta` по backend/app обнаружил AccessMechanic.EXCAVATION и MapCellPatchLayerKind.TERRAIN_DELTA; найденная enum-константа не является excavation orchestrator. MapCellService.save_pass/PatchStoreService — текущая patch boundary, field-wise merge не доказывает geometry invalidation или материализацию обнажённых стен/пола/потолка. Исполняемый excavation → geology rematerialization caller этим аудитом не подтверждён. Не объявлять будущий PHYSICS/SP-G путь существующим. Air policy inventory отдельно SP-A0; существующий WorldEnvironmentSettings повторно не проектируется.
### 0.7. Решения, оставленные OPEN
SP-1: exact window/result/revision/errors и reuse spatial types; SP-H: compact water preparation/coverage/cost и river volumes; SP-P0: root format/version/key и publisher contract; SP-M/G: composition/lifetime/materialization и solid/void после geometry patch; SP-R0: typed scene consumer и миграция engine repository path; SP-A0: фактическая ambient policy. Для каждого legacy entry ниже disposition пока **сохранить AS-IS; replacement/перенос/удаление не согласованы**. Наличие кандидата reuse не утверждает его target signature. Для SP-0 новые типы/пути/import migrations отсутствуют, file counts после равны текущим. Будущие additions OPEN и требуют пересчёта после freeze. LEGACY-AC и ARCH-ACCEPTED этим статическим аудитом не закрываются.
### 0.8. Каталоги: непосредственные файлы, включая __init__.py
- `backend/app/application/artifacts/contracts`: **4 → 4**.
- `backend/app/application/artifacts/registry`: **2 → 2**.
- `backend/app/application/worldData/generators/hydrology/materialize`: **2 → 2**.
- `backend/app/application/worldData/generators/hydrology/planning`: **2 → 2**.
- `backend/app/application/worldData/generators/hydrology/query`: **1 → 1**.
- `backend/app/application/worldData/mapCells`: **6 → 6**; >5 WARN, композиция по ответственностям при проектировании.
- `backend/app/application/worldData/pack/io`: **11 → 11**; >10, новые файлы запрещены до согласованной композиции.
- `backend/app/application/worldData/pack/read`: **22 → 22**; >10, новые файлы запрещены до согласованной композиции.
- `backend/app/application/worldData/pack/refine/fine/chunk`: **5 → 5**.
- `backend/app/application/worldData/pack/refine/fine/prep`: **3 → 3**.
- `backend/app/application/worldSnapshot/contracts`: **4 → 4**.
- `backend/app/dataModel/artifacts`: **3 → 3**.
- `backend/app/dataModel/hydrology/planning`: **3 → 3**.
- `backend/app/dataModel/hydrology/planning/stages`: **3 → 3**.
- `backend/app/dataModel/materials`: **4 → 4**.
- `backend/app/dataModel/planning/contracts`: **5 → 5**.
- `backend/app/dataModel/planning/identity`: **4 → 4**.
- `backend/app/dataModel/spatial`: **3 → 3**.
- `backend/app/dataModel/spatial/grid`: **6 → 6**; >5 WARN, композиция по ответственностям при проектировании.
- `backend/app/dataModel/terrain/regions`: **5 → 5**.
- `backend/app/dataModel/terrain/sampling`: **2 → 2**.
- `backend/app/dataModel/topology`: **6 → 6**; >5 WARN, композиция по ответственностям при проектировании.
- `backend/app/dataModel/worldPack/meta`: **7 → 7**; >5 WARN, композиция по ответственностям при проектировании.
- `backend/app/dataModel/worldPack/wire`: **18 → 18**; >10, новые файлы запрещены до согласованной композиции.
- `backend/app/dataModel/worldSnapshot/identity`: **3 → 3**.

### 0.9. Существующие declarations и прямые import edges
Ссылки ведут на исходный файл, поля/defaults/сигнатуры извлечены из AST текущего дерева. Validators перечислены как методы; точные тела проверок остаются в linked source, никакая новая семантика им не приписывается. Importer — прямой статический import модуля, не утверждение вызова каждого символа. Полный runtime порядок приведён выше. Owner/layer следует существующему пути: dataModel — значения/контракты домена, application — операции/ports; переносы не выбраны.

#### `backend/app/application/artifacts/contracts/formatBackend.py`

[Исходник](../../backend/app/application/artifacts/contracts/formatBackend.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class ArtifactFormatContract()
ArtifactFormatContract.key: ArtifactFormatKey
ArtifactFormatContract.kind: ArtifactKind
ArtifactFormatContract.supported_versions: frozenset[FormatVersion]
ArtifactFormatContract.content_model: type[C]
ArtifactFormatContract.encode: Callable[[C], bytes]
ArtifactFormatContract.decode: Callable[[bytes, FormatVersion], C]
ArtifactFormatContract.__post_init__(self) -> None
class ArtifactBackend(ABC)
ArtifactBackend.contract(self) -> ArtifactFormatContract[C]
async ArtifactBackend.write(self, reservation: StagingReservation, content: C) -> None
async ArtifactBackend.verify(self, ref: ArtifactRef) -> None
async ArtifactBackend.delete(self, ref: ArtifactRef) -> None
```
Прямые importers: `backend/app/application/artifacts/registry/artifactRegistry.py`.

#### `backend/app/application/artifacts/contracts/stagingPort.py`

[Исходник](../../backend/app/application/artifacts/contracts/stagingPort.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class IArtifactStaging(Protocol)
async IArtifactStaging.open_operation(self, operation_id: EntityUid, world_uid: EntityUid, kind: OperationKind, preparation_fingerprint: RevisionHex) -> OperationLeaseRef
async IArtifactStaging.reserve(self, lease: OperationLeaseRef, descriptor: ArtifactRef) -> StagingReservation
async IArtifactStaging.seal(self, reservation: StagingReservation) -> ArtifactRef
async IArtifactStaging.finish_preparation(self, lease: OperationLeaseRef, refs: tuple[ArtifactRef, ...]) -> OperationRecord
async IArtifactStaging.verify(self, ref: ArtifactRef, holder: ArtifactHolderRef) -> VerifiedArtifactRef
async IArtifactStaging.recover(self, operation_id: EntityUid) -> OperationRecord
async IArtifactStaging.cancel(self, operation_id: EntityUid, fence: int) -> OperationRecord
async IArtifactStaging.collect(self, operation_id: EntityUid, candidates: tuple[ArtifactRef, ...]) -> GcReport
```
Прямые importers: не найдены в backend/app (definition/test-only или import через другую форму требует caller evidence выше).

#### `backend/app/application/artifacts/registry/artifactRegistry.py`

[Исходник](../../backend/app/application/artifacts/registry/artifactRegistry.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class ArtifactFormatRegistryBinding()
ArtifactFormatRegistryBinding.__init__(self) -> None
ArtifactFormatRegistryBinding.register(self, contract: ArtifactFormatContract[C], backend: ArtifactBackend[C]) -> None
ArtifactFormatRegistryBinding.resolve(self, contract: ArtifactFormatContract[C]) -> ArtifactBackend[C]
ArtifactFormatRegistryBinding.metadata(self, key: ArtifactFormatKey) -> ArtifactFormatMetadata
ArtifactFormatRegistryBinding.encode(self, contract: ArtifactFormatContract[C], content: C) -> bytes
ArtifactFormatRegistryBinding.decode(self, contract: ArtifactFormatContract[C], payload: bytes, version: FormatVersion) -> C
async ArtifactFormatRegistryBinding.verify(self, ref: ArtifactRef) -> None
async ArtifactFormatRegistryBinding.delete(self, ref: ArtifactRef) -> None
```
Прямые importers: не найдены в backend/app (definition/test-only или import через другую форму требует caller evidence выше).

#### `backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py`

[Исходник](../../backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class HydrologyWorkingFields()
HydrologyWorkingFields.coarse_hydro: Mapping[Coord, MapCellHydrology]
HydrologyWorkingFields.coarse_surface_z: Mapping[Coord, int]
HydrologyWorkingFields.fine_z_overrides: Mapping[Coord, int]
HydrologyWorkingFields.sparse_fine_hydro: Mapping[Coord, MapCellHydrology]
HydrologyWorkingFields._fine_z: Mapping[Coord, Mapping[Coord, int]] = field(repr=False)
HydrologyWorkingFields._fine_hydro: Mapping[Coord, Mapping[Coord, MapCellHydrology]] = field(repr=False)
HydrologyWorkingFields._empty_z: Mapping[Coord, int] = field(repr=False)
HydrologyWorkingFields._empty_hydro: Mapping[Coord, MapCellHydrology] = field(repr=False)
HydrologyWorkingFields.from_plan(cls, plan: HydrologyPlan, grid: SurfaceGridSettings) -> Self
HydrologyWorkingFields.fine_z_for_tile(self, gx: GridX, gy: GridY) -> Mapping[Coord, int]
HydrologyWorkingFields.fine_hydro_for_tile(self, gx: GridX, gy: GridY) -> Mapping[Coord, MapCellHydrology]
```
Прямые importers: `backend/app/application/worldData/regions/factConsumers/context.py`; `backend/app/application/worldData/regions/inputs/landcoverInputs.py`; `backend/app/application/worldData/planning/composition/surfacePlanningEntry.py`; `backend/app/application/worldData/planning/contracts/surfaceWorkingMaps.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/sources.py`.

#### `backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py`

[Исходник](../../backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class HydrologyRoutesPlanProvider()
HydrologyRoutesPlanProvider.__init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan], water_placement: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan], assembler: HydrologyRoutesAssembler) -> None
HydrologyRoutesPlanProvider.build(self, request: PlanRequest[HydrologyPlanInput], dependencies: PlanDependencyReader, control: PlanBuildControl) -> PlanBuildResult[HydrologyRoutesPlan]
class GeoHydrologyRoutesPlanProvider()
GeoHydrologyRoutesPlanProvider.__init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan], water_placement: RegisteredPlanContract[GeoWaterPlacementInput, GeoWaterPlacementPlan], assembler: HydrologyRoutesAssembler, policy: PolicyResolver) -> None
GeoHydrologyRoutesPlanProvider.build(self, request: PlanRequest[GeoHydrologyPlanInput], dependencies: PlanDependencyReader, control: PlanBuildControl) -> PlanBuildResult[GeoHydrologyRoutesPlan]
class HydrologyFinalPlanProvider()
HydrologyFinalPlanProvider.__init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan], hydrology_routes: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan], river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan], assembler: HydrologyFactsAssembler) -> None
HydrologyFinalPlanProvider.build(self, request: PlanRequest[HydrologyFinalInput], dependencies: PlanDependencyReader, control: PlanBuildControl) -> PlanBuildResult[HydrologyPlan]
class GeoHydrologyFinalPlanProvider()
GeoHydrologyFinalPlanProvider.__init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan], hydrology_routes: RegisteredPlanContract[GeoHydrologyPlanInput, GeoHydrologyRoutesPlan], river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan], water_placement: RegisteredPlanContract[GeoWaterPlacementInput, GeoWaterPlacementPlan], assembler: HydrologyFactsAssembler) -> None
GeoHydrologyFinalPlanProvider.build(self, request: PlanRequest[HydrologyFinalInput], dependencies: PlanDependencyReader, control: PlanBuildControl) -> PlanBuildResult[GeoHydrologyPlan]
```
Прямые importers: `backend/app/application/worldData/planning/composition/planProviders.py`.

#### `backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py`

[Исходник](../../backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class NativeFinalWaterQuery()
NativeFinalWaterQuery.__init__(self, final: PlanEnvelope[GeoHydrologyPlan], water: PlanEnvelope[FineWaterResult], *, expected_final: PlanRef, expected_water: PlanRef, control: PlanBuildControl) -> None
NativeFinalWaterQuery.water_at(self, cell: FineXY) -> KnownFact[EntityUid | None] | UnknownFact
```
Прямые importers: не найдены в backend/app (definition/test-only или import через другую форму требует caller evidence выше).

#### `backend/app/application/worldData/mapCells/mapCellQueryFacade.py`

[Исходник](../../backend/app/application/worldData/mapCells/mapCellQueryFacade.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class MapCellQueryFacade()
MapCellQueryFacade.__init__(self, context: PackReadContext, patch_store: PatchStoreService, world_map_reader: WorldMapPackReader, *, city_raster: SettlementStructureRaster | None=None, region_state_repo: IRegionStateRepository | None=None) -> None
MapCellQueryFacade.has_pack(self) -> bool
MapCellQueryFacade.has_pack_for(self, world: World) -> bool
async MapCellQueryFacade.get_cell(self, world: World, x: int, y: int, z: int, *, patch: CellContribution | None=None) -> MergedCellView
async MapCellQueryFacade.merge_layer_batches(self, world: World, cells: CellLayers) -> list[MergedCellView]
async MapCellQueryFacade.get_cells(self, world: World, patches: dict[tuple[int, int, int], CellContribution | None]) -> list[MergedCellView]
async MapCellQueryFacade.get_scene_volume(self, world: World, x: int, y: int, z: int, *, xy_radius: int=SceneVolumePolicy.canonical_defaults().scene_xy_radius, z_below: int | None=None, z_above: int=SceneVolumePolicy.canonical_defaults().scene_z_above) -> list[MergedCellView]
async MapCellQueryFacade.get_scene_volume_as_map_cells(self, world: World, x: int, y: int, z: int, **kwargs) -> list[MapCell]
MapCellQueryFacade.invalidate_city_structure(self) -> None
async MapCellQueryFacade.get_footprint_terrain(self, world: World, *, x0: int, y0: int, x1: int, y1: int, location_uid: str | None=None) -> list[MapCell]
```
Прямые importers: `backend/app/core/container/packs.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorOrchestrator.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorTopologyJob.py`; `backend/app/application/worldData/pack/read/packDebugReadFacade.py`; `backend/app/application/worldData/pack/read/packFineTerrainReadFacade.py`; `backend/app/application/worldData/pack/read/packReadServices.py`.

#### `backend/app/application/worldData/mapCells/mapCellService.py`

[Исходник](../../backend/app/application/worldData/mapCells/mapCellService.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class MapCellReadServiceFactory(Protocol)
class MapCellService()
MapCellService.__init__(self, repo: IMapCellRepository, *, read_service_factory: MapCellReadServiceFactory | None=None) -> None
async MapCellService.bulk_persist_session(self) -> (не аннотирован)
async MapCellService.has_world_cells(self, world_uid: str) -> bool
MapCellService.uses_pack_read(self, world: World) -> bool
MapCellService.pack_read_services(self, world: World) -> PackReadServices | None
async MapCellService.get_all_for_read(self, world: World) -> list[MapCell]
async MapCellService.get_tile_cells_for_read(self, world: World, gx: int, gy: int) -> list[MapCell]
async MapCellService.export_for_debug(self, world: World) -> dict
MapCellService.world_map_tile_coords(self, world: World) -> list[tuple[int, int]]
async MapCellService.get_all(self, world_uid: str) -> list[MapCell]
async MapCellService.export(self, world_uid: str) -> list[dict]
async MapCellService.import_from_json(self, world_uid: str, data: list[dict]) -> ImportResult
async MapCellService.clear(self, world_uid: str) -> None
async MapCellService.get_location_uids_with_cells(self, world_uid: str) -> frozenset[str]
async MapCellService.has_column_cells(self, world_uid: str, x: int, y: int, *, world: World | None=None) -> bool
async MapCellService.get_z_slice_for_read(self, world: World, x_min: int, x_max: int, y_min: int, y_max: int, z_min: int, z_max: int) -> list[MapCell]
MapCellService.reject_legacy_generate_on_pack(self, world: World) -> None
async MapCellService.get_scene_volume(self, world: World, x: int, y: int, z: int, *, xy_radius: int=SceneVolumePolicy.canonical_defaults().scene_xy_radius, z_below: int | None=None, z_above: int=SceneVolumePolicy.canonical_defaults().scene_z_above) -> list[MapCell]
async MapCellService.save_generated(self, cells: list[MapCell]) -> ImportResult
async MapCellService.save_settlement_surface(self, cells: list[MapCell]) -> ImportResult
async MapCellService.save_pass(self, cells: list[MapCell], layer: LayerKind, *, insert_only: bool=False) -> ImportResult
async MapCellService.get_z_slice(self, world_uid: str, x_min: int, x_max: int, y_min: int, y_max: int, z_min: int, z_max: int) -> list[MapCell]
```
Прямые importers: `backend/app/core/container/worldData.py`; `backend/app/application/worldData/persist/settlementPersistService.py`; `backend/app/application/worldData/render/legacyMapGridRender.py`; `backend/app/application/worldData/render/mapGridRenderService.py`; `backend/app/application/worldData/materialize/climate/climateBatchOrchestrator.py`; `backend/app/application/worldData/materialize/shared/serialPersistQueue.py`.

#### `backend/app/application/worldData/pack/io/worldPackWriter.py`

[Исходник](../../backend/app/application/worldData/pack/io/worldPackWriter.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class WorldPackWriter()
WorldPackWriter.__init__(self, paths: WorldPackPaths, *, manifest: WorldPackManifest | None=None, codec: TileCodec | None=None, store: PackManifestStore | None=None, bake_defaults: PackBakeDefaults | None=None, parent_light_cache: ParentLightCache | None=None) -> None
WorldPackWriter.manifest(self) -> WorldPackManifest
WorldPackWriter.paths(self) -> WorldPackPaths
WorldPackWriter.parent_light_cache(self) -> ParentLightCache
WorldPackWriter.bake_defaults(self) -> PackBakeDefaults
WorldPackWriter.sync_world_metadata(self, world: World, *, cells_per_side: int) -> None
WorldPackWriter.write_world_map_tile(self, gx: int, gy: int, cells: list[WorldMapCellWire], *, cells_per_side: int) -> str
WorldPackWriter.write_wilderness_chunk(self, gx: int, gy: int, chunk: FineTerrainChunkWire, *, refine_role: ChunkRefineRole='background') -> str
WorldPackWriter.merge_grade_cell_slots_tile(self, gx: int, gy: int, cells) -> None
WorldPackWriter.merge_grade_cell_slots_location(self, location_uid: str, cells) -> None
WorldPackWriter.write_location_terrain(self, location_uid: str, columns: FineTerrainChunkWire, *, territory_volume) -> str
WorldPackWriter.encode_settlement_structure_tmp(self, location_uid: str, wire: SettlementStructureWire, *, registry: WorldTransitionTypeRegistry | None=None) -> SettlementStructureTmpRef
WorldPackWriter.publish_settlement_structure(self, tmp: SettlementStructureTmpRef, *, territory_volume, packed_district_uids: list[str] | None=None, structure_status: SettlementStructureStatus | None=None) -> str
WorldPackWriter.has_published_settlement(self, location_uid: str) -> bool
WorldPackWriter.load_settlement_structure_tmp(self, location_uid: str) -> SettlementStructureTmpRef | None
WorldPackWriter.settlement_structure_tmp_path(self, location_uid: str) -> (не аннотирован)
WorldPackWriter.write_climate_coarse(self, field: ClimateFieldWire) -> str
WorldPackWriter.write_climate_tile(self, gx: int, gy: int, field: ClimateFieldWire) -> str
WorldPackWriter.write_locations_index(self, index: LocationsIndexWire) -> Path
WorldPackWriter.commit_chunk(self, gx: int, gy: int, cx: int, cy: int, *, content_hash: str | None=None, nbytes: int | None=None, refine_role: ChunkRefineRole | None=None) -> None
WorldPackWriter.recalc_wilderness_status(self, gx: int, gy: int, *, expected_chunks: int | None=None) -> WildernessRefineStatus
WorldPackWriter.recalc_manifest_counters(self) -> None
WorldPackWriter.save_manifest(self) -> None
WorldPackWriter.pack_storage_path(self, *, db_path: str | None=None, existing: str | None=None) -> str
```
Прямые importers: `backend/app/core/container/packs.py`; `backend/app/application/worldData/pack/__init__.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorOrchestrator.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorSkip.py`; `backend/app/application/worldData/pack/climate/climatePackBakeOrchestrator.py`; `backend/app/application/worldData/pack/refine/gridNeighborHalo.py`; `backend/app/application/worldData/pack/refine/chunks/chunkRefineWorker.py`; `backend/app/application/worldData/pack/refine/entry/entryRefineOrchestrator.py`; `backend/app/application/worldData/pack/refine/fine/fineRectDrain.py`; `backend/app/application/worldData/pack/refine/fine/fineScenePathRefine.py`; `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkPersist.py`; `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkRunner.py`; `backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py`; `backend/app/application/worldData/pack/bake/detailed/detailedBakeRefine.py`; `backend/app/application/worldData/pack/bake/detailed/detailedBakeScope.py`; `backend/app/application/worldData/pack/bake/detailed/packDetailedBakeOrchestrator.py`; `backend/app/application/worldData/pack/bake/finalize/packBakeFinalize.py`; `backend/app/application/worldData/pack/bake/finalize/packBakePublisher.py`; `backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py`; `backend/app/application/worldData/pack/bake/l0/worldMapBakeOrchestrator.py`.

#### `backend/app/application/worldData/pack/read/mapCellToFineTerrainWire.py`

[Исходник](../../backend/app/application/worldData/pack/read/mapCellToFineTerrainWire.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
cells_to_fine_terrain_chunk(cx: int, cy: int, chunk_columns: int, origin_x: int, origin_y: int, cells: list[MapCell], region_uid_by_xy: dict[tuple[int, int], str] | None=None) -> FineTerrainChunkWire
```
Прямые importers: `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkPersist.py`.

#### `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkCompute.py`

[Исходник](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkCompute.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
rect_heightmap_from_overlay(heightmap: SurfaceHeightmap, overlay: dict[Coord, int], rect: ColumnRect) -> SurfaceHeightmap
compute_rect(terrain: TerrainBatchOrchestrator, ctx: FineTileContext, pair: tuple[int, ColumnRect]) -> ChunkComputeResult
```
Прямые importers: `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkRunner.py`.

#### `backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py`

[Исходник](../../backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
prepare_fine_tile(terrain: TerrainBatchOrchestrator, world: World, locations: list[NamedLocation], writer: WorldPackWriter, mat_ctx: MaterializationContext, surface_bundle: SurfacePlanBundle, tile_gx: int, tile_gy: int, rects: list[ColumnRect], volumes: list[TerritoryVolume], *, refine_role: ChunkRefineRole='scene', phase: str | None=None, relief_templates_by_uid: dict[str, ReliefTemplate] | None=None, stages: GradePipelineStages | None=None, region_state_snapshot: Mapping[str, StateSnapshotEntry], working: SurfaceWorkingMaps) -> FineTileContext
existing_grade_uids_from_pack(writer: WorldPackWriter, reader: WorldPackReader, tile_gx: int, tile_gy: int, fine_bbox: ColumnRect, chunk_size: int) -> dict[tuple[int, int], str]
```
Прямые importers: `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkRunner.py`.

#### `backend/app/application/worldSnapshot/contracts/applyPort.py`

[Исходник](../../backend/app/application/worldSnapshot/contracts/applyPort.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class IWorldSnapshotApply(Protocol)
async IWorldSnapshotApply.apply(self, patch_set: PatchSet[S]) -> SnapshotApplyResult
```
Прямые importers: не найдены в backend/app (definition/test-only или import через другую форму требует caller evidence выше).

#### `backend/app/dataModel/artifacts/references.py`

[Исходник](../../backend/app/dataModel/artifacts/references.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class ArtifactKind(StrEnum)
class ArtifactFormatRegistry(BaseModel)
ArtifactFormatRegistry.entries: tuple[ArtifactFormatMetadata, ...]
ArtifactFormatRegistry.unique_keys(self) -> Self
type ArtifactFormatKey = RegistryKey[ArtifactFormatRegistry]
class ArtifactFormatMetadata(BaseModel)
ArtifactFormatMetadata.key: ArtifactFormatKey
ArtifactFormatMetadata.supported_versions: frozenset[FormatVersion] = Field(min_length=1)
class ArtifactRef(BaseModel)
ArtifactRef.kind: ArtifactKind
ArtifactRef.format_key: ArtifactFormatKey
ArtifactRef.format_version: FormatVersion
ArtifactRef.content_hash: RevisionHex
ArtifactRef.nbytes: Annotated[StrictInt, Field(ge=0)]
ArtifactRef.row_count: Annotated[StrictInt, Field(ge=0)] | None = None
ArtifactRef.representation_fields(self) -> Self
```
Прямые importers: `backend/app/db/repositories/sqlite/snapshotCore/operations/operationStore.py`; `backend/app/dataModel/worldSnapshot/metadata/envelope.py`; `backend/app/dataModel/worldSnapshot/results/publication.py`; `backend/app/dataModel/patch/changes/header.py`; `backend/app/dataModel/patch/preconditions/runtime.py`; `backend/app/dataModel/patch/results/sectionResult.py`; `backend/app/dataModel/artifacts/lifecycle/gc.py`; `backend/app/dataModel/artifacts/lifecycle/holders.py`; `backend/app/dataModel/artifacts/lifecycle/lease.py`; `backend/app/dataModel/artifacts/lifecycle/operation/record.py`; `backend/app/application/artifacts/contracts/formatBackend.py`; `backend/app/application/artifacts/contracts/holderPort.py`; `backend/app/application/artifacts/contracts/stagingPort.py`; `backend/app/application/artifacts/encoding/coreManifest.py`; `backend/app/application/artifacts/registry/artifactRegistry.py`; `backend/app/application/artifacts/storage/artifactCatalog.py`; `backend/app/application/artifacts/storage/artifactLeases.py`.

#### `backend/app/dataModel/hydrology/planning/hydrologyPlan.py`

[Исходник](../../backend/app/dataModel/hydrology/planning/hydrologyPlan.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class LakePaint(BaseModel)
LakePaint.location_uid: EntityUid | None
LakePaint.shoreline_segments: tuple[tuple[FineXY, FineXY], ...]
class CoastlinePaint(BaseModel)
CoastlinePaint.location_uid: EntityUid | None
CoastlinePaint.segments: tuple[tuple[FineXY, FineXY], ...]
class SegmentRiverPaint(BaseModel)
SegmentRiverPaint.edge_uid: EntityUid
SegmentRiverPaint.location_uid: EntityUid | None
SegmentRiverPaint.segment: tuple[FineXY, FineXY]
SegmentRiverPaint.width_fine: FineDelta = Field(strict=True, gt=0)
class IntentRiverPaint(BaseModel)
IntentRiverPaint.river_uid: EntityUid
IntentRiverPaint.path: tuple[FineXY, ...] = Field(min_length=2)
IntentRiverPaint.width_wire: StrictInt
IntentRiverPaint.valid_wire_width(cls, value: int) -> int
class DeclaredWaterPaint(BaseModel)
DeclaredWaterPaint.lakes: tuple[LakePaint, ...]
DeclaredWaterPaint.coastlines: tuple[CoastlinePaint, ...]
DeclaredWaterPaint.segments: tuple[SegmentRiverPaint, ...]
DeclaredWaterPaint.intents: tuple[IntentRiverPaint, ...]
class RiverPathSegment(BaseModel, Generic[S])
RiverPathSegment.path: tuple[S, ...] = Field(min_length=1)
RiverPathSegment.connection_type: HydrologyConnectionType
RiverPathSegment.edge_uid: EntityUid | None
RiverPathSegment.location_uid: EntityUid | None
RiverPathSegment.declared: StrictBool
RiverPathSegment.river_connection(self) -> Self
class RiverRoute(BaseModel, Generic[S])
RiverRoute.river_uid: EntityUid
RiverRoute.segments: tuple[RiverPathSegment[S], ...] = Field(min_length=1)
RiverRoute.receiver_cell: S
RiverRoute.drainage: RiverDrainageLink
RiverRoute.confirmed_receiver(self) -> Self
require_map(rows: tuple[tuple[K, V], ...], order: Callable[[K], tuple[int, ...]]) -> None
coarse_order(cell: SurfaceGridCoord) -> tuple[int, ...]
fine_order(cell: FineXY) -> tuple[int, ...]
require_unique_water(bodies: tuple[WaterBody, ...], unions: tuple[PhysicalWaterUnion, ...]) -> set[str]
require_rooted_links(links: dict[str, str], roots: set[str]) -> None
class HydrologyRoutesPlan(BaseModel)
HydrologyRoutesPlan.coarse_open_water: tuple[tuple[SurfaceGridCoord, MapCellHydrology], ...]
HydrologyRoutesPlan.water_bodies: tuple[WaterBody, ...]
HydrologyRoutesPlan.physical_unions: tuple[PhysicalWaterUnion, ...]
HydrologyRoutesPlan.coarse_routes: tuple[RiverRoute[SurfaceGridCoord], ...]
HydrologyRoutesPlan.fine_routes: tuple[RiverRoute[FineXY], ...]
HydrologyRoutesPlan.fine_base_surface_z: tuple[tuple[FineXY, FineZ], ...]
HydrologyRoutesPlan.declared_paint: DeclaredWaterPaint
HydrologyRoutesPlan.proven_routes(self) -> Self
class HydrologyPlan(BaseModel)
HydrologyPlan.coarse_surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...]
HydrologyPlan.coarse_hydro: tuple[tuple[SurfaceGridCoord, MapCellHydrology], ...]
HydrologyPlan.sparse_fine_hydro: tuple[tuple[FineXY, MapCellHydrology], ...]
HydrologyPlan.fine_z_overrides: tuple[tuple[FineXY, FineZ], ...]
HydrologyPlan.water_bodies: tuple[WaterBody, ...]
HydrologyPlan.physical_unions: tuple[PhysicalWaterUnion, ...]
HydrologyPlan.declared_paint: DeclaredWaterPaint
HydrologyPlan.consistent_facts(self) -> Self
class GeoHydrologyPlan(HydrologyPlan)
GeoHydrologyPlan.source_mapping: SourceBodyMapping
GeoHydrologyPlan.classification_decisions: tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...]
GeoHydrologyPlan.consistent_geo_facts(self) -> Self
class GeoHydrologyRoutesPlan(BaseModel)
GeoHydrologyRoutesPlan.base: HydrologyRoutesPlan
GeoHydrologyRoutesPlan.source_mapping: SourceBodyMapping
GeoHydrologyRoutesPlan.classification_decisions: tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...]
GeoHydrologyRoutesPlan.coherent_sources(self) -> Self
```
Прямые importers: `backend/app/dataModel/hydrology/boundaries/boundaryWaterSnapshot.py`; `backend/app/dataModel/hydrology/policy/hydrologyPlacementPolicy.py`; `backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py`; `backend/app/dataModel/hydrology/planning/stages/riverRoutePlans.py`; `backend/app/application/worldData/planning/composition/planProviders.py`; `backend/app/application/worldData/planning/contracts/surfacePlanBundle.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/placement/adapters/coastline/attachedCoastline.py`; `backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/declaredBasins.py`; `backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/declaredRivers.py`; `backend/app/application/worldData/generators/climate/localFieldFromCoarse.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoatingSupport.py`; `backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py`; `backend/app/application/worldData/generators/terrain/relief/planning/riverReliefPlanner.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/sources.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/beds.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/execution.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/publication.py`; `backend/app/application/worldData/generators/hydrology/boundaries/boundaryGeometry.py`; `backend/app/application/worldData/generators/hydrology/boundaries/boundaryPlanner.py`; `backend/app/application/worldData/generators/hydrology/boundaries/boundaryPreparation.py`; `backend/app/application/worldData/generators/hydrology/boundaries/boundaryResult.py`; `backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py`; `backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py`; `backend/app/application/worldData/generators/hydrology/policy/hydrologyPlacementBinding.py`; `backend/app/application/worldData/generators/hydrology/policy/hydrologyPolicyFacts.py`; `backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyJob.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/proposals.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyRoutesAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/nativeRoutesPublication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/nativeFacts.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/riverFacts.py`; `backend/app/application/worldData/generators/hydrology/load/paint/declaredWaterPaintProjector.py`; `backend/app/application/worldData/generators/climate/planning/climatePlanProvider.py`.

#### `backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py`

[Исходник](../../backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class OpenWaterPlan(BaseModel)
OpenWaterPlan.coarse_open_water: tuple[tuple[SurfaceGridCoord, MapCellHydrology], ...]
OpenWaterPlan.water_bodies: tuple[WaterBody, ...]
OpenWaterPlan.physical_unions: tuple[PhysicalWaterUnion, ...]
OpenWaterPlan.source_mapping: SourceBodyMapping
OpenWaterPlan.consistent_water(self) -> Self
class MaterializedWater()
MaterializedWater.cells: tuple[tuple[Coord, MapCellHydrology], ...]
MaterializedWater.bodies: tuple[WaterBody, ...]
MaterializedWater.area_rows: tuple[tuple[str, int], ...]
MaterializedWater.floor_rows: tuple[tuple[str, int], ...]
MaterializedWater.uid_aliases: tuple[tuple[str, str], ...]
MaterializedWater.source_mapping: SourceBodyMapping
MaterializedWater.__post_init__(self) -> None
class AssembledWater()
AssembledWater.materialized: MaterializedWater
AssembledWater.physical_unions: tuple[PhysicalWaterUnion, ...]
AssembledWater.__post_init__(self) -> None
type FineWaterResult = tuple[FineSurfaceWindow, AssembledWater]
```
Прямые importers: `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/generators/terrain/relief/planning/riverReliefPlanner.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/execution.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/publication.py`; `backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py`; `backend/app/application/worldData/generators/hydrology/water/waterMaterialize.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterAssemblyResult.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyJob.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyPlanner.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/projection.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarseRiverPlanner.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fineRiverPlanner.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarse/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyRoutesAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/nativeFacts.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py`.

#### `backend/app/dataModel/materials/materialRegistryEntry.py`

[Исходник](../../backend/app/dataModel/materials/materialRegistryEntry.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class MaterialRegistryEntry(BaseModel)
MaterialRegistryEntry.system_material: StrictOnWire[RegistryKey[WorldMaterialRegistry]]
MaterialRegistryEntry.display_name: StrictOnWire[str]
MaterialRegistryEntry.glossary_ref: DefaultWhenMissing[str | None] = None
MaterialRegistryEntry.material_category: StrictEnumOnWire[MaterialCategory]
MaterialRegistryEntry.substrate_kind: DefaultWhenMissing[StrictEnumOnWire[MaterialSubstrateKind] | None] = None
MaterialRegistryEntry.tags: DefaultWhenMissing[list[str]] = Field(default_factory=list)
MaterialRegistryEntry.use_type: DefaultWhenMissing[list[str]] = Field(default_factory=list)
MaterialRegistryEntry.economic_tier: DefaultWhenMissing[EconomyTierKey | None] = None
MaterialRegistryEntry.hardness: DefaultWhenMissing[Annotated[int, Field(ge=HARDNESS_MIN, le=HARDNESS_MAX)] | None] = constrained_field(default=None)
MaterialRegistryEntry.density: DefaultWhenMissing[Annotated[int, Field(ge=1)] | None] = constrained_field(default=None)
MaterialRegistryEntry.heat_conductivity: DefaultWhenMissing[float] = constrained_field(default=0.1, greater_equals=0.0, lesser_equals=1.0)
MaterialRegistryEntry.viscosity: DefaultWhenMissing[Annotated[float, Field(ge=0.0, le=1.0)] | None] = constrained_field(default=None)
MaterialRegistryEntry.heat_into: DefaultWhenMissing[str | None] = None
MaterialRegistryEntry.heat_temp: DefaultWhenMissing[int | None] = None
MaterialRegistryEntry.cool_into: DefaultWhenMissing[str | None] = None
MaterialRegistryEntry.cool_temp: DefaultWhenMissing[int | None] = None
MaterialRegistryEntry.structural_strength: DefaultWhenMissing[Annotated[float, Field(ge=0.0, le=1.0)] | None] = constrained_field(default=None)
MaterialRegistryEntry.flammable: DefaultWhenMissing[bool] = False
MaterialRegistryEntry.freezable: DefaultWhenMissing[bool] = False
MaterialRegistryEntry.corrodible: DefaultWhenMissing[bool] = True
MaterialRegistryEntry.meltable: DefaultWhenMissing[bool] = False
MaterialRegistryEntry.mineable: DefaultWhenMissing[bool] = False
MaterialRegistryEntry.transparent: DefaultWhenMissing[float] = constrained_field(default=0.0, greater_equals=0.0, lesser_equals=100.0, strict=True, allow_inf_nan=False)
MaterialRegistryEntry.breakable: DefaultWhenMissing[bool] = False
MaterialRegistryEntry.temp_damage: DefaultWhenMissing[bool] = False
MaterialRegistryEntry.vision_block: DefaultWhenMissing[bool] = False
MaterialRegistryEntry.components: DefaultWhenMissing[list[str] | None] = None
```
Прямые importers: `backend/app/dataModel/materials/worldMaterialRegistry.py`; `backend/app/dataModel/materials/__init__.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/generators/climate/precipitation.py`; `backend/app/application/worldData/generators/utils/materialResolver.py`.

#### `backend/app/dataModel/planning/contracts/planDependency.py`

[Исходник](../../backend/app/dataModel/planning/contracts/planDependency.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class PlanDependency(BaseModel)
PlanDependency.slot: PlanSlot = Field(strict=True, min_length=1)
PlanDependency.ref: PlanRef
class PlanDependencyContract(BaseModel)
PlanDependencyContract.slot: PlanSlot = Field(strict=True, min_length=1)
PlanDependencyContract.contract_id: PlanContractId
PlanDependencyContract.schema_version: SchemaVersion = Field(strict=True, gt=0)
PlanDependencyContract.algorithm_version: AlgorithmVersion = Field(strict=True, gt=0)
PlanDependencyContract.accepts(self, dependency: PlanDependency) -> bool
require_canonical_dependencies(dependencies: tuple[PlanDependency, ...]) -> tuple[PlanDependency, ...]
```
Прямые importers: `backend/app/dataModel/surfacePlanning/surfacePlanBindings.py`; `backend/app/dataModel/planning/contracts/planEnvelope.py`; `backend/app/dataModel/planning/contracts/planRequest.py`; `backend/app/application/worldData/planning/composition/planProviders.py`; `backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/planning/composition/natural/preparedTerrain.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/publication.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainWindowJob.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/nativeRoutesPublication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py`; `backend/app/application/planning/providers/planProvider.py`; `backend/app/application/planning/providers/planRegistry.py`; `backend/app/application/planning/service/planFingerprints.py`.

#### `backend/app/dataModel/planning/contracts/planEnvelope.py`

[Исходник](../../backend/app/dataModel/planning/contracts/planEnvelope.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class PlanBuildResult(BaseModel, Generic[T])
PlanBuildResult.payload: T
PlanBuildResult.diagnostics: tuple[PlanDiagnostic, ...]
class PlanEnvelope(BaseModel, Generic[T])
PlanEnvelope.ref: PlanRef
PlanEnvelope.dependencies: tuple[PlanDependency, ...]
PlanEnvelope.payload: T
PlanEnvelope.diagnostics: tuple[PlanDiagnostic, ...]
```
Прямые importers: `backend/app/dataModel/terrain/designedWater/input.py`; `backend/app/dataModel/terrain/designedWater/geometry/authoredGeometry.py`; `backend/app/dataModel/hydrology/boundaries/boundaryWaterSnapshot.py`; `backend/app/dataModel/hydrology/policy/hydrologyPlacementPolicy.py`; `backend/app/application/worldData/planning/composition/planProviders.py`; `backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py`; `backend/app/application/worldData/planning/contracts/surfacePlanBundle.py`; `backend/app/application/worldData/planning/encoding/surfaceEnvelopeCodec.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/planning/composition/natural/preparedTerrain.py`; `backend/app/application/worldData/generators/climate/localFieldFromCoarse.py`; `backend/app/application/worldData/generators/terrain/planning/terrainPlanProvider.py`; `backend/app/application/worldData/generators/terrain/planning/waterPlacementPlanProvider.py`; `backend/app/application/worldData/generators/terrain/regions/regionExtent.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoatingSupport.py`; `backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py`; `backend/app/application/worldData/generators/terrain/relief/planning/riverReliefPlanner.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/publication.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBaseJob.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBasePlanner.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainWindowJob.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/prepared/provider.py`; `backend/app/application/worldData/generators/terrain/landcover/planning/preWaterHillHosts.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/designPreparation.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/designUniverse.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/proceduralDesignPreparation.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/proceduralWaterSourceAdapter.py`; `backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py`; `backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyJob.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyPlanner.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/projection.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarseRiverPlanner.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fineRiverPlanner.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarse/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyRoutesAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/nativeRoutesPublication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/nativeFacts.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py`; `backend/app/application/worldData/generators/hydrology/load/paint/declaredWaterPaintProjector.py`; `backend/app/application/worldData/generators/climate/planning/climatePlanProvider.py`; `backend/app/application/worldData/generators/assemblers/climateAssembler/passes/anchorCollectPass.py`; `backend/app/application/planning/providers/planProvider.py`; `backend/app/application/planning/providers/planRegistry.py`; `backend/app/application/planning/service/planningService.py`.

#### `backend/app/dataModel/planning/identity/planRef.py`

[Исходник](../../backend/app/dataModel/planning/identity/planRef.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class PlanRef(BaseModel)
PlanRef.key: PlanKey
PlanRef.output_fingerprint: OutputFingerprint = Field(strict=True, min_length=32, max_length=32)
```
Прямые importers: `backend/app/dataModel/terrain/designedWater/input.py`; `backend/app/dataModel/terrain/regions/regionPlanningInput.py`; `backend/app/dataModel/terrain/relief/surfaceCoating/surfaceCoatingFacts.py`; `backend/app/dataModel/terrain/designedWater/geometry/authoredGeometry.py`; `backend/app/dataModel/terrain/designedWater/geometry/waterDesignConstraints.py`; `backend/app/dataModel/terrain/designedWater/preparation/result.py`; `backend/app/dataModel/planning/contracts/planDependency.py`; `backend/app/dataModel/planning/contracts/planEnvelope.py`; `backend/app/dataModel/hydrology/boundaries/attachedCoastline.py`; `backend/app/dataModel/hydrology/boundaries/boundaryWaterSnapshot.py`; `backend/app/dataModel/hydrology/policy/hydrologyPlacementPolicy.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/generators/terrain/relief/planning/riverReliefPlanner.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/publication.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBasePlanner.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainWindowJob.py`; `backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyPlanner.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/projection.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fineRiverPlanner.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyRoutesAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/nativeRoutesPublication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py`; `backend/app/application/planning/service/planningService.py`.

#### `backend/app/dataModel/spatial/facing.py`

[Исходник](../../backend/app/dataModel/spatial/facing.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class Facing(StrEnum)
CARDINAL_FACINGS: frozenset[Facing] = frozenset({Facing.NORTH, Facing.SOUTH, Facing.EAST, Facing.WEST})
NS_FACINGS: frozenset[Facing] = frozenset({Facing.NORTH, Facing.SOUTH})
EW_FACINGS: frozenset[Facing] = frozenset({Facing.EAST, Facing.WEST})
INTERCARDINAL_FACINGS: frozenset[Facing] = frozenset({Facing.NORTHEAST, Facing.NORTHWEST, Facing.SOUTHEAST, Facing.SOUTHWEST})
OPPOSITE: dict[Facing, Facing] = {Facing.NORTH: Facing.SOUTH, Facing.SOUTH: Facing.NORTH, Facing.EAST: Facing.WEST, Facing.WEST: Facing.EAST, Facing.NORTHEAST: Facing.SOUTHWEST, Facing.NORTHWEST: Facing.SOUTHEAST, Facing.SOUTHEAST: Facing.NORTHWEST, Facing.SOUTHWEST: Facing.NORTHEAST}
_COMPACT: dict[str, Facing] = {'N': Facing.NORTH, 'S': Facing.SOUTH, 'E': Facing.EAST, 'W': Facing.WEST, 'NE': Facing.NORTHEAST, 'NW': Facing.NORTHWEST, 'SE': Facing.SOUTHEAST, 'SW': Facing.SOUTHWEST}
COMPACT_LETTER: dict[Facing, str] = {facing: letter for letter, facing in _COMPACT.items()}
parse_facing(value: str | Facing | None) -> Facing | None
coerce_facing_wire(value: object) -> Facing | None
parse_facing_or_default(value: str | Facing | None, *, default: Facing) -> Facing
CARDINAL_WALL_OUTWARD_DELTA: dict[Facing, tuple[int, int]] = {Facing.NORTH: (0, +1), Facing.SOUTH: (0, -1), Facing.EAST: (+1, 0), Facing.WEST: (-1, 0)}
CARDINAL_DELTA_TO_FACING: dict[tuple[int, int], Facing] = {delta: facing for facing, delta in CARDINAL_WALL_OUTWARD_DELTA.items()}
GRID_OUTWARD_DELTA: dict[Facing, tuple[int, int]] = {**CARDINAL_WALL_OUTWARD_DELTA, Facing.NORTHEAST: (1, 1), Facing.NORTHWEST: (-1, 1), Facing.SOUTHEAST: (1, -1), Facing.SOUTHWEST: (-1, -1)}
GRID_DELTA_TO_FACING: dict[tuple[int, int], Facing] = {delta: facing for facing, delta in GRID_OUTWARD_DELTA.items()}
cardinal_facing_for_delta(delta: tuple[int, int] | None) -> Facing | None
opposite(facing: Facing) -> Facing
is_meridional_edge(facing: Facing) -> bool
is_latitudinal_edge(facing: Facing) -> bool
is_corner(facing: Facing) -> bool
snap_bbox_edge_to_grid(facing: Facing, rel_x: int, rel_y: int, step_x: int, step_y: int, n_cols: int, n_rows: int) -> tuple[int, int]
```
Прямые importers: `backend/app/dataModel/spatial/__init__.py`; `backend/app/dataModel/topology/topologyGeometry.py`; `backend/app/dataModel/topology/worldBounds.py`; `backend/app/dataModel/topology/worldTopology.py`; `backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py`; `backend/app/dataModel/worldPack/wire/settlementStructureWire.py`; `backend/app/dataModel/worldPack/wire/worldMapCellWire.py`; `backend/app/dataModel/validation/diagnostics/runtimeIssueContext.py`; `backend/app/dataModel/terrain/relief/gradeRimRay.py`; `backend/app/dataModel/terrain/relief/gradeSlot.py`; `backend/app/dataModel/terrain/relief/planning/reliefPlan.py`; `backend/app/dataModel/terrain/relief/surfaceCoating/surfaceCoatingFacts.py`; `backend/app/dataModel/spatial/grid/lightGridScale.py`; `backend/app/dataModel/locations/structure/building/staircaseSpec.py`; `backend/app/dataModel/locations/structure/room/entryPoint.py`; `backend/app/dataModel/locations/structure/room/shapeParams.py`; `backend/app/dataModel/locations/settlement/area/perimeterBarrier.py`; `backend/app/dataModel/locations/settlement/district/districtTopologySlot.py`; `backend/app/application/worldData/debugStructureRotations.py`; `backend/app/application/worldData/facingArrows.py`; `backend/app/application/worldData/masks/regionRasterizer.py`; `backend/app/application/worldData/placement/geometry.py`; `backend/app/application/worldData/render/gradeRayDump.py`; `backend/app/application/worldData/render/mapSymbols.py`; `backend/app/application/worldData/render/structureAsciiSymbols.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorUids.py`; `backend/app/application/worldData/render/regions/regionOutline.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/pack/read/mapCellToFineTerrainWire.py`; `backend/app/application/worldData/pack/refine/fineGradeSurface.py`; `backend/app/application/worldData/pack/refine/gridNeighborHalo.py`; `backend/app/application/worldData/pack/refine/detailed/fronts/detailedGradeFrontUid.py`; `backend/app/application/worldData/pack/refine/detailed/grade/detailedGradeCatalog.py`; `backend/app/application/worldData/pack/refine/detailed/grade/detailedGradeResult.py`; `backend/app/application/worldData/pack/refine/detailed/grade/detailedJobUid.py`; `backend/app/application/worldData/pack/bake/lightGrid/cell.py`; `backend/app/application/worldData/pack/bake/lightGrid/worldSeam.py`; `backend/app/application/worldData/materialize/terrain/terrainBatchOrchestrator.py`; `backend/app/application/worldData/generators/barrier/perimeter.py`; `backend/app/application/worldData/generators/barrier/ribbonFence.py`; `backend/app/application/worldData/generators/coordinates/gridRay.py`; `backend/app/application/worldData/generators/structure/structureGeneratorService.py`; `backend/app/application/worldData/generators/structure/structureOrientation.py`; `backend/app/application/worldData/generators/terrain/terrainGeneratorService.py`; `backend/app/application/worldData/generators/terrain/landcover/types.py`; `backend/app/application/worldData/generators/terrain/mountains/rangeSideFill.py`; `backend/app/application/worldData/generators/terrain/passes/columnFillPass.py`; `backend/app/application/worldData/generators/terrain/passes/parentLightTerrain.py`; `backend/app/application/worldData/generators/terrain/relief/discover/fronts.py`; `backend/app/application/worldData/generators/terrain/relief/discover/neighbors.py`; `backend/app/application/worldData/generators/terrain/relief/discover/packSenders.py`; `backend/app/application/worldData/generators/terrain/relief/discover/seam.py`; `backend/app/application/worldData/generators/terrain/relief/discover/types.py`; `backend/app/application/worldData/generators/terrain/relief/geom/facing.py`; `backend/app/application/worldData/generators/terrain/relief/geom/terrainDescent.py`; `backend/app/application/worldData/generators/terrain/relief/mountain/sideGradeDecision.py`; `backend/app/application/worldData/generators/terrain/relief/planning/naturalRelief.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/geometry.py`; `backend/app/application/worldData/generators/terrain/relief/validate/emptySlotDiagram.py`; `backend/app/application/worldData/generators/terrain/relief/validate/gradeCellRays.py`; `backend/app/application/worldData/generators/terrain/relief/validate/gradeCellSlotValidate.py`; `backend/app/application/worldData/generators/terrain/landcover/autoresolve/mergeSublocations.py`; `backend/app/application/worldData/generators/terrain/landcover/autoresolve/seedGrid.py`; `backend/app/application/worldData/generators/structure/layout/layoutEngine.py`; `backend/app/application/worldData/generators/structure/layout/layoutEntry.py`; `backend/app/application/worldData/generators/structure/passages/builder.py`; `backend/app/application/worldData/generators/structure/passages/corridorConnector.py`; `backend/app/application/worldData/generators/structure/passages/doorPlacer.py`; `backend/app/application/worldData/generators/structure/passages/doorValidator.py`; `backend/app/application/worldData/generators/structure/passages/entry.py`; `backend/app/application/worldData/generators/structure/passages/shared.py`; `backend/app/application/worldData/generators/structure/passages/wallBreachPlacer.py`; `backend/app/application/worldData/generators/structure/passages/wallOpening.py`; `backend/app/application/worldData/generators/structure/passages/wallOpeningResolver.py`; `backend/app/application/worldData/generators/structure/room/roomFactory.py`; `backend/app/application/worldData/generators/structure/room/roomInstance.py`; `backend/app/application/worldData/generators/structure/shape/shapes.py`; `backend/app/application/worldData/generators/structure/staircase/embeddedUpperLayout.py`; `backend/app/application/worldData/generators/structure/staircase/facingHelper.py`; `backend/app/application/worldData/generators/structure/staircase/shaftPlacer.py`; `backend/app/application/worldData/generators/structure/staircase/undergroundTunnel.py`; `backend/app/application/worldData/generators/structure/staircase/uShape/facingResolver.py`; `backend/app/application/worldData/generators/structure/staircase/uShape/uShape.py`; `backend/app/application/worldData/generators/structure/staircase/uShape/uShapeHelper.py`; `backend/app/application/worldData/generators/structure/staircase/uShape/uShapeValidator.py`; `backend/app/application/worldData/generators/structure/staircase/verticalLadder/verticalLadderHelper.py`; `backend/app/application/worldData/generators/road/layouts/gridLayout.py`; `backend/app/application/worldData/generators/hydrology/boundaries/boundaryGeometry.py`; `backend/app/application/worldData/generators/assemblers/areaAssembler/areaSlot.py`; `backend/app/application/worldData/generators/assemblers/areaAssembler/areaThreshold.py`; `backend/app/application/worldData/generators/assemblers/buildingAssembler/structureContext.py`; `backend/app/application/worldData/generators/assemblers/buildingAssembler/vastHullAssembler.py`; `backend/app/application/worldData/generators/assemblers/districtAssembler/connectionEntry.py`; `backend/app/application/worldData/generators/assemblers/settlementAssembler/buildingCache.py`; `backend/app/application/worldData/generators/assemblers/settlementAssembler/planner/streets.py`; `backend/app/application/worldData/generators/assemblers/districtAssembler/planner/areaSlots.py`; `backend/app/application/worldData/generators/assemblers/districtAssembler/planner/barrierInset.py`; `backend/app/application/worldData/generators/assemblers/districtAssembler/planner/frontage.py`; `backend/app/application/worldData/generators/assemblers/districtAssembler/planner/types.py`; `backend/app/application/worldData/generators/assemblers/areaAssembler/planner/areaBarriers.py`; `backend/app/application/worldData/generators/assemblers/areaAssembler/planner/areaPaths.py`; `backend/app/application/worldData/generators/assemblers/areaAssembler/planner/measureApproach.py`; `backend/app/application/worldData/generators/assemblers/areaAssembler/planner/resolveThreshold.py`; `backend/app/application/artifacts/encoding/coreManifest.py`; `backend/app/api/routes/debug.py`.

#### `backend/app/dataModel/spatial/grid/coordinateSpace.py`

[Исходник](../../backend/app/dataModel/spatial/grid/coordinateSpace.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class CoordinateSpace(StrEnum)
```
Прямые importers: `backend/app/dataModel/terrain/designedWater/draft.py`; `backend/app/dataModel/terrain/designedWater/input.py`; `backend/app/dataModel/terrain/planning/waterPlacementPlan.py`; `backend/app/dataModel/terrain/relief/bathymetry/basinSpec.py`; `backend/app/dataModel/terrain/relief/bathymetry/floorProfile.py`; `backend/app/dataModel/terrain/designedWater/geometry/authoredGeometry.py`; `backend/app/dataModel/terrain/designedWater/preparation/result.py`; `backend/app/dataModel/spatial/grid/__init__.py`; `backend/app/dataModel/hydrology/boundaries/attachedCoastline.py`; `backend/app/dataModel/hydrology/boundaries/boundaryWaterSnapshot.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/placement/adapters/water.py`; `backend/app/application/worldData/generators/coordinates/space.py`; `backend/app/application/worldData/generators/terrain/planning/waterPlacementPlanProvider.py`; `backend/app/application/worldData/generators/terrain/regions/coverageMeasure.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/basinZ.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/floorProfile.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/placementPreparation.py`; `backend/app/application/worldData/generators/hydrology/autoresolve/proceduralRiverAutoresolve.py`; `backend/app/application/worldData/generators/hydrology/boundaries/boundaryGeometry.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarse/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/proposals.py`.

#### `backend/app/dataModel/spatial/grid/coordinateTypes.py`

[Исходник](../../backend/app/dataModel/spatial/grid/coordinateTypes.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
type FineXY = tuple[FineX, FineY]
class SurfaceGridCoord()
SurfaceGridCoord.gx: GridX
SurfaceGridCoord.gy: GridY
class FineGridCoord()
FineGridCoord.x: FineX
FineGridCoord.y: FineY
FineGridCoord.z: FineZ
class SurfaceGridRect()
SurfaceGridRect.gx0: GridX
SurfaceGridRect.gy0: GridY
SurfaceGridRect.gx1: GridX
SurfaceGridRect.gy1: GridY
SurfaceGridRect.as_tuple(self) -> tuple[int, int, int, int]
class FineGridRect()
FineGridRect.x0: FineX
FineGridRect.y0: FineY
FineGridRect.x1: FineX
FineGridRect.y1: FineY
FineGridRect.z: FineZ
FineGridRect.as_tuple(self) -> tuple[int, int, int, int, int]
class LightCellRef()
LightCellRef.gx: int
LightCellRef.gy: int
LightCellRef.tx: int
LightCellRef.ty: int
LightCellRef.as_absolute(self, side: int) -> tuple[int, int]
```
Прямые importers: `backend/app/dataModel/terrain/designedWater/draft.py`; `backend/app/dataModel/terrain/designedWater/input.py`; `backend/app/dataModel/terrain/hills/acceptedHill.py`; `backend/app/dataModel/terrain/planning/terrainPlan.py`; `backend/app/dataModel/terrain/regions/coverageGeometry.py`; `backend/app/dataModel/terrain/sampling/fineSurfaceWindow.py`; `backend/app/dataModel/terrain/relief/bathymetry/floorProfile.py`; `backend/app/dataModel/terrain/relief/planning/reliefPlan.py`; `backend/app/dataModel/terrain/relief/surfaceCoating/surfaceCoatingFacts.py`; `backend/app/dataModel/terrain/relief/planning/inputs/reliefPlanInput.py`; `backend/app/dataModel/terrain/planning/inputs/geoWaterPlacementInput.py`; `backend/app/dataModel/terrain/planning/inputs/terrainBaseInput.py`; `backend/app/dataModel/terrain/planning/inputs/waterPlacementInput.py`; `backend/app/dataModel/terrain/planning/natural/preparedTerrain.py`; `backend/app/dataModel/terrain/designedWater/fields/field.py`; `backend/app/dataModel/terrain/designedWater/fields/plateLayout.py`; `backend/app/dataModel/terrain/designedWater/geometry/authoredGeometry.py`; `backend/app/dataModel/terrain/designedWater/preparation/result.py`; `backend/app/dataModel/spatial/grid/__init__.py`; `backend/app/dataModel/hydrology/boundaries/boundaryWaterSnapshot.py`; `backend/app/dataModel/hydrology/planning/hydrologyPlan.py`; `backend/app/dataModel/hydrology/sources/proceduralWaterSource.py`; `backend/app/dataModel/hydrology/sources/waterSourceMetadata.py`; `backend/app/dataModel/hydrology/planning/inputs/geoHydrologyPlanInput.py`; `backend/app/dataModel/hydrology/planning/inputs/hydrologyPlanInput.py`; `backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py`; `backend/app/dataModel/hydrology/planning/stages/riverRoutePlans.py`; `backend/app/dataModel/climate/planning/climatePoints.py`; `backend/app/dataModel/climate/planning/inputs/climateBaseInput.py`; `backend/app/application/worldData/masks/footprint.py`; `backend/app/application/worldData/regions/factConsumers/climate.py`; `backend/app/application/worldData/planning/composition/surfacePlanningCapture.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/placement/adapters/water.py`; `backend/app/application/worldData/placement/adapters/waterTypes.py`; `backend/app/application/worldData/pack/climate/climatePackBakeOrchestrator.py`; `backend/app/application/worldData/pack/bake/lightGrid/contributors/climate.py`; `backend/app/application/worldData/materialize/terrain/terrainBatchOrchestrator.py`; `backend/app/application/worldData/generators/climate/anchorAssign.py`; `backend/app/application/worldData/generators/climate/climatePoleField.py`; `backend/app/application/worldData/generators/climate/poleResolve.py`; `backend/app/application/worldData/generators/climate/tierResolve.py`; `backend/app/application/worldData/generators/coordinates/types.py`; `backend/app/application/worldData/generators/terrain/hills/hillSelection.py`; `backend/app/application/worldData/generators/terrain/planning/terrainPlanProvider.py`; `backend/app/application/worldData/generators/terrain/regions/coverageMeasure.py`; `backend/app/application/worldData/generators/terrain/regions/shapeCoverage.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoatingSupport.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/floorProfile.py`; `backend/app/application/worldData/generators/terrain/relief/planning/naturalRelief.py`; `backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/sources.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/beds.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/execution.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBaseJob.py`; `backend/app/application/worldData/generators/terrain/planning/projection/coarseSurface.py`; `backend/app/application/worldData/generators/terrain/planning/projection/heightDelta.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/prepared/materialization.py`; `backend/app/application/worldData/generators/terrain/landcover/planning/capturedSources.py`; `backend/app/application/worldData/generators/terrain/landcover/planning/preWaterHillHosts.py`; `backend/app/application/worldData/generators/terrain/designedWater/fields/plateFieldGenerator.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/proceduralWaterSourceAdapter.py`; `backend/app/application/worldData/generators/terrain/designedWater/strategies/authoredRegionStrategy.py`; `backend/app/application/worldData/generators/terrain/designedWater/strategies/procedural/continentalNoiseStrategy.py`; `backend/app/application/worldData/generators/terrain/designedWater/strategies/procedural/plateNoiseStrategy.py`; `backend/app/application/worldData/generators/terrain/designedWater/strategies/procedural/plateStrategy.py`; `backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py`; `backend/app/application/worldData/generators/hydrology/placement/waterPlacementPass.py`; `backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py`; `backend/app/application/worldData/generators/hydrology/sources/waterSourceMetadataFactory.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyJob.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyPlanner.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/projection.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarseRiverPlanner.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fineRiverPlanner.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarse/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/proposals.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/nativeFacts.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/riverFacts.py`; `backend/app/application/worldData/generators/hydrology/load/paint/declaredWaterPaintProjector.py`; `backend/app/application/worldData/generators/climate/materialize/climateWorkingFields.py`; `backend/app/application/worldData/generators/climate/planning/basePoleLayout.py`; `backend/app/application/worldData/generators/climate/planning/climatePlanSampler.py`; `backend/app/application/worldData/generators/assemblers/climateAssembler/passes/anchorCollectPass.py`.

#### `backend/app/dataModel/spatial/grid/gridBBox.py`

[Исходник](../../backend/app/dataModel/spatial/grid/gridBBox.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class GridBBox()
GridBBox.x_min: int
GridBBox.x_max: int
GridBBox.y_min: int
GridBBox.y_max: int
GridBBox.diagonal(self) -> float
```
Прямые importers: `backend/app/dataModel/terrain/hills/acceptedHill.py`; `backend/app/dataModel/terrain/planning/terrainPlan.py`; `backend/app/dataModel/terrain/planning/inputs/terrainBaseInput.py`; `backend/app/dataModel/spatial/grid/__init__.py`; `backend/app/dataModel/climate/planning/climatePlan.py`; `backend/app/dataModel/climate/planning/inputs/climateBaseInput.py`; `backend/app/application/worldData/planning/composition/surfacePlanningCapture.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/pack/climate/climateCoarseBake.py`; `backend/app/application/worldData/generators/climate/climatePoleField.py`; `backend/app/application/worldData/generators/climate/poleResolve.py`; `backend/app/application/worldData/generators/coordinates/antipode.py`; `backend/app/application/worldData/generators/coordinates/worldTile.py`; `backend/app/application/worldData/generators/hydrology/hydrologyGeneratorService.py`; `backend/app/application/worldData/generators/hydrology/riverNetworkAssembler.py`; `backend/app/application/worldData/generators/hydrology/types.py`; `backend/app/application/worldData/generators/terrain/types.py`; `backend/app/application/worldData/generators/terrain/hills/hillLayout.py`; `backend/app/application/worldData/generators/terrain/hills/hillPlacement.py`; `backend/app/application/worldData/generators/terrain/hills/hillRaster.py`; `backend/app/application/worldData/generators/terrain/hills/hillSelection.py`; `backend/app/application/worldData/generators/terrain/passes/bbox.py`; `backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/beds.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBaseJob.py`; `backend/app/application/worldData/generators/terrain/planning/projection/coarseSurface.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/prepared/materialization.py`; `backend/app/application/worldData/generators/hydrology/placement/waterPlacementPass.py`; `backend/app/application/worldData/generators/hydrology/shore/fineRiverSampling.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyJob.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarse/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/execution.py`; `backend/app/application/worldData/generators/climate/planning/basePoleLayout.py`; `backend/app/application/worldData/generators/climate/planning/climatePlanProvider.py`; `backend/app/application/worldData/generators/climate/planning/climatePlanSampler.py`.

#### `backend/app/dataModel/spatial/grid/gridSettings.py`

[Исходник](../../backend/app/dataModel/spatial/grid/gridSettings.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class SurfaceGridSettings(BaseModel)
SurfaceGridSettings.fine_span: StrictInt = Field(gt=0)
SurfaceGridSettings.light_side: StrictInt = Field(gt=0)
```
Прямые importers: `backend/app/dataModel/terrain/designedWater/input.py`; `backend/app/dataModel/terrain/regions/regionPlanningInput.py`; `backend/app/dataModel/terrain/relief/surfaceCoating/surfaceSupportInput.py`; `backend/app/dataModel/terrain/relief/planning/inputs/reliefPlanInput.py`; `backend/app/dataModel/terrain/planning/inputs/geoWaterPlacementInput.py`; `backend/app/dataModel/terrain/planning/inputs/terrainBaseInput.py`; `backend/app/dataModel/terrain/planning/inputs/waterPlacementInput.py`; `backend/app/dataModel/terrain/designedWater/geometry/authoredGeometry.py`; `backend/app/dataModel/terrain/designedWater/geometry/waterDesignConstraints.py`; `backend/app/dataModel/terrain/designedWater/preparation/result.py`; `backend/app/dataModel/hydrology/boundaries/attachedCoastline.py`; `backend/app/dataModel/hydrology/boundaries/boundaryWaterSnapshot.py`; `backend/app/dataModel/hydrology/planning/inputs/geoHydrologyPlanInput.py`; `backend/app/dataModel/hydrology/planning/inputs/hydrologyPlanInput.py`; `backend/app/application/worldData/regions/inputs/landcoverInputs.py`; `backend/app/application/worldData/planning/composition/surfacePlanningCapture.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/planning/composition/support/surfaceSupportCapture.py`; `backend/app/application/worldData/pack/bake/lightGrid/bakeContext.py`; `backend/app/application/worldData/generators/terrain/passes/lightSurfaceRefine.py`; `backend/app/application/worldData/generators/terrain/passes/parentLightUpsample.py`; `backend/app/application/worldData/generators/terrain/regions/coverageMeasure.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/applyReliefObjectsZ.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/basinZ.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/floorProfile.py`; `backend/app/application/worldData/generators/terrain/planning/projection/coarseSurface.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/designPreparation.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/designUniverse.py`; `backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py`.

#### `backend/app/dataModel/spatial/grid/lightGridScale.py`

[Исходник](../../backend/app/dataModel/spatial/grid/lightGridScale.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
light_span_for(tile_macro: int, side: int) -> int
class LightGridScale()
LightGridScale.tile_macro: int
LightGridScale.side: int
LightGridScale.light_span: int
LightGridScale.from_tile(cls, tile_macro: int, side: int) -> LightGridScale
LightGridScale.rim_tx_ty(self, facing: Facing) -> tuple[tuple[int, int], ...]
```
Прямые importers: `backend/app/dataModel/worldPack/wire/worldMapCellsPerTile.py`; `backend/app/application/worldData/masks/regionRasterContext.py`; `backend/app/application/worldData/pack/read/wildernessRegionReadService.py`; `backend/app/application/worldData/pack/bake/lightGrid/coords.py`; `backend/app/application/worldData/pack/bake/lightGrid/contributors/landcover/apply.py`; `backend/app/application/worldData/materialize/terrain/terrainBatchOrchestrator.py`; `backend/app/application/worldData/generators/terrain/landcover/materializer.py`; `backend/app/application/worldData/generators/terrain/landcover/types.py`; `backend/app/application/worldData/generators/terrain/relief/planning/naturalRelief.py`; `backend/app/application/worldData/generators/terrain/relief/planning/reliefPlanProvider.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBaseJob.py`; `backend/app/application/worldData/generators/terrain/planning/projection/coarseSurface.py`; `backend/app/application/worldData/generators/terrain/landcover/planning/capturedSources.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/projection.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/proposals.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/nativeFacts.py`; `backend/app/application/worldData/generators/coordinates/light/grid.py`.

#### `backend/app/dataModel/spatial/regionShape.py`

[Исходник](../../backend/app/dataModel/spatial/regionShape.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class RegionShapeKind(StrEnum)
class EdgeNoise(BaseModel)
EdgeNoise.amplitude: int = Field(ge=0)
EdgeNoise.scale: int = Field(gt=0)
class RegionShapeBase(BaseModel)
RegionShapeBase.edge_noise: EdgeNoise | None = None
RegionShapeBase.projected(self, divisor: int) -> Self
class BboxShape(RegionShapeBase)
BboxShape.kind: Literal[RegionShapeKind.BBOX] = RegionShapeKind.BBOX
BboxShape.x_min: int
BboxShape.y_min: int
BboxShape.x_max: int
BboxShape.y_max: int
BboxShape.ordered_bounds(self) -> Self
BboxShape.contains(self, x: float, y: float) -> bool
BboxShape.bbox(self) -> Bounds
BboxShape.area(self) -> float
BboxShape.projected(self, divisor: int) -> BboxShape
class EllipseShape(RegionShapeBase)
EllipseShape.kind: Literal[RegionShapeKind.ELLIPSE] = RegionShapeKind.ELLIPSE
EllipseShape.cx: int
EllipseShape.cy: int
EllipseShape.rx: int = Field(gt=0)
EllipseShape.ry: int = Field(gt=0)
EllipseShape.contains(self, x: float, y: float) -> bool
EllipseShape.bbox(self) -> Bounds
EllipseShape.area(self) -> float
EllipseShape.projected(self, divisor: int) -> EllipseShape
class PolygonShape(RegionShapeBase)
PolygonShape.kind: Literal[RegionShapeKind.POLYGON] = RegionShapeKind.POLYGON
PolygonShape.vertices: tuple[Point, ...] = Field(min_length=3)
PolygonShape.simple_ring(self) -> Self
PolygonShape.contains(self, x: float, y: float) -> bool
PolygonShape.bbox(self) -> Bounds
PolygonShape.area(self) -> float
PolygonShape.projected(self, divisor: int) -> PolygonShape
class AnchorRadiusShape(RegionShapeBase)
AnchorRadiusShape.kind: Literal[RegionShapeKind.ANCHOR_RADIUS] = RegionShapeKind.ANCHOR_RADIUS
AnchorRadiusShape.anchor_uid: str = Field(min_length=1)
AnchorRadiusShape.radius: int = Field(gt=0)
AnchorRadiusShape.contains(self, x: float, y: float) -> bool
AnchorRadiusShape.bbox(self) -> Bounds
AnchorRadiusShape.area(self) -> float
AnchorRadiusShape.projected(self, divisor: int) -> AnchorRadiusShape
class CorridorShape(RegionShapeBase)
CorridorShape.kind: Literal[RegionShapeKind.CORRIDOR] = RegionShapeKind.CORRIDOR
CorridorShape.path: tuple[Point, ...] = Field(min_length=2)
CorridorShape.width: int = Field(gt=0)
CorridorShape.nonzero_path(self) -> Self
CorridorShape.distance(self, x: float, y: float) -> float
CorridorShape.contains(self, x: float, y: float) -> bool
CorridorShape.bbox(self) -> Bounds
CorridorShape.area(self) -> float
CorridorShape.projected(self, divisor: int) -> CorridorShape
```
Прямые importers: `backend/app/ids/regionIdentity.py`; `backend/app/dataModel/hydrology/declaredBasin.py`; `backend/app/dataModel/placement/intent.py`; `backend/app/dataModel/terrainMasks/landcoverRegionsCategoryPolicy.py`; `backend/app/dataModel/terrainMasks/regions/specs.py`; `backend/app/dataModel/terrain/regions/regionPlanningInput.py`; `backend/app/application/worldData/masks/regionIdentity.py`; `backend/app/application/worldData/masks/regionRasterContext.py`; `backend/app/application/worldData/masks/regionRasterizer.py`; `backend/app/application/worldData/masks/regionRasterNoise.py`; `backend/app/application/worldData/regions/inputs/landcoverInputs.py`; `backend/app/application/worldData/regions/stateChange/contracts.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/placement/adapters/coastlineShape.py`; `backend/app/application/worldData/placement/adapters/lakeShape.py`; `backend/app/application/worldData/placement/adapters/waterShape.py`; `backend/app/application/worldData/generators/terrain/landcover/collect.py`; `backend/app/application/worldData/generators/terrain/landcover/finePaint.py`; `backend/app/application/worldData/generators/terrain/landcover/types.py`; `backend/app/application/worldData/generators/terrain/regions/regionExtent.py`; `backend/app/application/worldData/generators/terrain/regions/shapeCoverage.py`; `backend/app/application/worldData/generators/terrain/landcover/autoresolve/claim.py`; `backend/app/application/worldData/generators/terrain/landcover/autoresolve/mergeSublocations.py`; `backend/app/application/worldData/generators/terrain/landcover/autoresolve/seedGrid.py`; `backend/app/application/worldData/generators/terrain/landcover/planning/capturedSources.py`; `backend/app/application/worldData/generators/terrain/landcover/planning/preWaterHillHosts.py`.

#### `backend/app/dataModel/terrain/regions/coverageGeometry.py`

[Исходник](../../backend/app/dataModel/terrain/regions/coverageGeometry.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class CoverageSpan(TerrainRegionModel)
CoverageSpan.y: Annotated[FineY, Field(strict=True)]
CoverageSpan.x0: Annotated[FineX, Field(strict=True)]
CoverageSpan.x1: Annotated[FineX, Field(strict=True)]
CoverageSpan.nonempty_interval(self) -> Self
class RegionCoverage(TerrainRegionModel)
RegionCoverage.region_uid: EntityUid
RegionCoverage.spans: tuple[CoverageSpan, ...]
RegionCoverage.canonical_intervals(self) -> Self
```
Прямые importers: `backend/app/dataModel/terrain/designedWater/input.py`; `backend/app/dataModel/terrain/regions/regionPlanningInput.py`; `backend/app/dataModel/terrain/regions/terrainRegionsSnapshot.py`; `backend/app/dataModel/terrain/sampling/fineSurfaceWindow.py`; `backend/app/dataModel/terrain/planning/natural/preparedTerrain.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/generators/terrain/regions/coverageMeasure.py`; `backend/app/application/worldData/generators/terrain/regions/regionExtent.py`; `backend/app/application/worldData/generators/terrain/regions/shapeCoverage.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoatingSupport.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBaseJob.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBasePlanner.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainWindowJob.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/prepared/materialization.py`; `backend/app/application/worldData/generators/terrain/landcover/planning/preWaterHillHosts.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/coastlineWaterSourceAdapter.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/designUniverse.py`.

#### `backend/app/dataModel/terrain/sampling/fineSurfaceWindow.py`

[Исходник](../../backend/app/dataModel/terrain/sampling/fineSurfaceWindow.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class FineSurfaceWindow(BaseModel)
FineSurfaceWindow.coverage: RegionCoverage
FineSurfaceWindow.surface_z: tuple[tuple[FineXY, Annotated[FineZ, Field(strict=True)]], ...]
FineSurfaceWindow.topology: WorldTopology
FineSurfaceWindow.protected_cells: frozenset[Coord]
FineSurfaceWindow.complete_surface(self) -> Self
```
Прямые importers: `backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBasePlanner.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainWindowJob.py`; `backend/app/application/worldData/generators/terrain/planning/projection/coarseSurface.py`; `backend/app/application/worldData/generators/terrain/planning/projection/heightDelta.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/prepared/materialization.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyPlanner.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/nativeFacts.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py`.

#### `backend/app/dataModel/topology/worldTopology.py`

[Исходник](../../backend/app/dataModel/topology/worldTopology.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class NeighborResult(BaseModel)
NeighborResult.coord: Coord
NeighborResult.edge_crossing: bool
NeighborResult.invert_dy: bool
class SeamPair(BaseModel)
SeamPair.owner: Coord
SeamPair.other: Coord
SeamPair.owner_facing: Facing
SeamPair.other_facing: Facing
SeamPair.invert_dy: bool
class WorldTopology(BaseModel)
WorldTopology.mode: WorldTopologyMode = Field(default_factory=lambda: WorldTerrainScalars.canonical_defaults().world_topology_mode)
WorldTopology.bounds: WorldBounds
WorldTopology.resolve_bounds(cls, bounds: WorldBounds, info: ValidationInfo) -> WorldBounds
WorldTopology.grid_neighbor(self, x: int, y: int, facing: Facing) -> Coord | None
WorldTopology.neighbor(self, x: int, y: int, facing: Facing) -> NeighborResult | None
WorldTopology.antagonist_tile(self, x: int, y: int, facing: Facing) -> Coord | None
WorldTopology.canonicalize(self, x: int, y: int) -> Coord | None
WorldTopology.seam_pairs(self) -> tuple[SeamPair, ...]
```
Прямые importers: `backend/app/dataModel/hydrology/riverDrainageLink.py`; `backend/app/dataModel/hydrology/riverRouting.py`; `backend/app/dataModel/hydrology/waterfallDrop.py`; `backend/app/dataModel/placement/batch.py`; `backend/app/dataModel/topology/fineTopology.py`; `backend/app/dataModel/topology/topologyGeometry.py`; `backend/app/dataModel/terrain/designedWater/draft.py`; `backend/app/dataModel/terrain/designedWater/input.py`; `backend/app/dataModel/terrain/planning/waterPlacementPlan.py`; `backend/app/dataModel/terrain/regions/regionPlanningInput.py`; `backend/app/dataModel/terrain/sampling/fineSurfaceWindow.py`; `backend/app/dataModel/terrain/relief/bathymetry/basinSpec.py`; `backend/app/dataModel/terrain/relief/bathymetry/floorProfile.py`; `backend/app/dataModel/terrain/relief/surfaceCoating/surfaceSupportInput.py`; `backend/app/dataModel/terrain/relief/planning/inputs/reliefPlanInput.py`; `backend/app/dataModel/terrain/planning/inputs/geoWaterPlacementInput.py`; `backend/app/dataModel/terrain/planning/inputs/waterPlacementInput.py`; `backend/app/dataModel/terrain/planning/natural/preparedTerrain.py`; `backend/app/dataModel/terrain/designedWater/fields/field.py`; `backend/app/dataModel/terrain/designedWater/geometry/authoredGeometry.py`; `backend/app/dataModel/terrain/designedWater/geometry/waterDesignConstraints.py`; `backend/app/dataModel/hydrology/boundaries/attachedCoastline.py`; `backend/app/dataModel/hydrology/boundaries/boundaryWaterSnapshot.py`; `backend/app/dataModel/hydrology/planning/inputs/geoHydrologyPlanInput.py`; `backend/app/dataModel/hydrology/planning/inputs/hydrologyPlanInput.py`; `backend/app/dataModel/hydrology/planning/stages/openWaterPlan.py`; `backend/app/application/worldData/masks/regionRasterContext.py`; `backend/app/application/worldData/masks/regionRasterizer.py`; `backend/app/application/worldData/masks/regionRasterNoise.py`; `backend/app/application/worldData/placement/geometry.py`; `backend/app/application/worldData/render/regions/regionOutline.py`; `backend/app/application/worldData/regions/inputs/landcoverInputs.py`; `backend/app/application/worldData/planning/composition/surfacePlanningCapture.py`; `backend/app/application/worldData/planning/composition/surfacePlanningEntry.py`; `backend/app/application/worldData/planning/encoding/surfaceManifest.py`; `backend/app/application/worldData/planning/composition/support/surfaceSupportCapture.py`; `backend/app/application/worldData/placement/adapters/coastlineShape.py`; `backend/app/application/worldData/placement/adapters/lakeShape.py`; `backend/app/application/worldData/placement/adapters/water.py`; `backend/app/application/worldData/placement/adapters/waterTypes.py`; `backend/app/application/worldData/pack/bake/lightGrid/bakeContext.py`; `backend/app/application/worldData/generators/hydrology/hydrologyGeneratorService.py`; `backend/app/application/worldData/generators/hydrology/riverNetworkAssembler.py`; `backend/app/application/worldData/generators/hydrology/waterBodyAssembler.py`; `backend/app/application/worldData/generators/terrain/hills/hillLayout.py`; `backend/app/application/worldData/generators/terrain/landcover/finePaint.py`; `backend/app/application/worldData/generators/terrain/landcover/types.py`; `backend/app/application/worldData/generators/terrain/materialize/terrainWorkingFields.py`; `backend/app/application/worldData/generators/terrain/planning/waterPlacementPlanProvider.py`; `backend/app/application/worldData/generators/terrain/regions/coverageMeasure.py`; `backend/app/application/worldData/generators/terrain/regions/shapeCoverage.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/applyReliefObjectsZ.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/basinZ.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/distanceField.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/bathymetry/floorProfile.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/riverBed/riverBedSpec.py`; `backend/app/application/worldData/generators/terrain/reliefObjects/riverBed/riverBedZ.py`; `backend/app/application/worldData/generators/terrain/relief/surfaceCoating/geometry.py`; `backend/app/application/worldData/generators/terrain/relief/planning/river/beds.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBaseJob.py`; `backend/app/application/worldData/generators/terrain/planning/preWater/terrainBasePlanner.py`; `backend/app/application/worldData/generators/terrain/planning/projection/coarseSurface.py`; `backend/app/application/worldData/generators/terrain/landcover/autoresolve/mergeSublocations.py`; `backend/app/application/worldData/generators/terrain/landcover/autoresolve/seedGrid.py`; `backend/app/application/worldData/generators/terrain/designedWater/fields/noiseFieldGenerator.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/coastlineConstraintPreparer.py`; `backend/app/application/worldData/generators/terrain/designedWater/preparation/placementPreparation.py`; `backend/app/application/worldData/generators/hydrology/autoresolve/proceduralRiverAutoresolve.py`; `backend/app/application/worldData/generators/hydrology/boundaries/boundaryGeometry.py`; `backend/app/application/worldData/generators/hydrology/geom/polylineRasterize.py`; `backend/app/application/worldData/generators/hydrology/load/buildHydrologyMasterInput.py`; `backend/app/application/worldData/generators/hydrology/load/resolveHydrologyTopology.py`; `backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py`; `backend/app/application/worldData/generators/hydrology/placement/waterPlacementPass.py`; `backend/app/application/worldData/generators/hydrology/rivers/classifyRiverSegments.py`; `backend/app/application/worldData/generators/hydrology/rivers/resolveDeclaredRiverPath.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverBedProfile.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverGeometry.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverMouth.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverNetworkPlanner.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverReceivers.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverRequestOrder.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverRouteRequests.py`; `backend/app/application/worldData/generators/hydrology/rivers/riverRouteSearch.py`; `backend/app/application/worldData/generators/hydrology/shore/fineHydrologyIndex.py`; `backend/app/application/worldData/generators/hydrology/shore/fineRiverSampling.py`; `backend/app/application/worldData/generators/hydrology/shore/waterSideFootprint.py`; `backend/app/application/worldData/generators/hydrology/water/componentLabel.py`; `backend/app/application/worldData/generators/hydrology/water/depressionTree.py`; `backend/app/application/worldData/generators/hydrology/water/levelFill.py`; `backend/app/application/worldData/generators/hydrology/water/shoreDerive.py`; `backend/app/application/worldData/generators/hydrology/water/waterClassifier.py`; `backend/app/application/worldData/generators/hydrology/water/waterMaterialize.py`; `backend/app/application/worldData/generators/hydrology/water/waterSources.py`; `backend/app/application/worldData/generators/hydrology/waterfalls/riverDrops.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterAssemblyResult.py`; `backend/app/application/worldData/generators/hydrology/water/planning/waterBodyJob.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/coarse/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/execution.py`; `backend/app/application/worldData/generators/hydrology/rivers/planning/fine/proposals.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py`; `backend/app/application/worldData/generators/hydrology/planning/assembly/final/riverFacts.py`.

#### `backend/app/dataModel/worldPack/meta/worldPackManifest.py`

[Исходник](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class ChunkRef(BaseModel)
ChunkRef.cx: int
ChunkRef.cy: int
ChunkRef.refine_role: ChunkRefineRole | None = None
ChunkRef.content_hash: str | None = None
ChunkRef.bytes: int | None = None
class TileManifestEntry(ClimateBakeStatusMixin)
TileManifestEntry.gx: int
TileManifestEntry.gy: int
TileManifestEntry.world_map_path: str | None = None
TileManifestEntry.world_map_hash: str | None = None
TileManifestEntry.wilderness_refine_status: WildernessRefineStatus = 'absent'
TileManifestEntry.chunks: list[ChunkRef] = Field(default_factory=list)
class SettlementStructureEntry(BaseModel)
SettlementStructureEntry.location_uid: str
SettlementStructureEntry.territory_volume: TerritoryVolume
SettlementStructureEntry.structure_path: str | None = None
SettlementStructureEntry.structure_hash: str | None = None
SettlementStructureEntry.bytes: int | None = None
SettlementStructureEntry.structure_status: SettlementStructureStatus = 'absent'
SettlementStructureEntry.packed_district_uids: list[str] = Field(default_factory=list)
class LocationTerrainEntry(ClimateBakeStatusMixin)
LocationTerrainEntry.location_uid: str
LocationTerrainEntry.territory_volume: TerritoryVolume
LocationTerrainEntry.terrain_path: str | None = None
LocationTerrainEntry.terrain_hash: str | None = None
LocationTerrainEntry.z_band: str | None = None
LocationTerrainEntry.bytes: int | None = None
class WorldPackManifest(BaseModel)
WorldPackManifest.SCHEMA_ID: ClassVar[str] = 'SCH-WORLD-PACK-MANIFEST'
WorldPackManifest.pack_version: str = PACK_WIRE_VERSION
WorldPackManifest.world_uid: str
WorldPackManifest.content_hash: str | None = None
WorldPackManifest.codec_version: int = PACK_CODEC_VERSION
WorldPackManifest.payload_format: str = 'json'
WorldPackManifest.registry_hash: str | None = None
WorldPackManifest.bake_mode: BakeMode = 'light'
WorldPackManifest.fine_cells_per_map_cell: int = FINE_CELLS_PER_MAP_CELL_DEFAULT
WorldPackManifest.world_map_cells_per_tile: int = WORLD_MAP_CELLS_PER_TILE
WorldPackManifest.fine_cell_size: int = FINE_CELL_SIZE
WorldPackManifest.map_subsurface_depth: int = 0
WorldPackManifest.location_terrain_entries: list[LocationTerrainEntry] = Field(default_factory=list)
WorldPackManifest.settlement_structure_entries: list[SettlementStructureEntry] = Field(default_factory=list)
WorldPackManifest.wilderness_region_entries: list[WildernessRegionEntry] = Field(default_factory=list)
WorldPackManifest.tiles: list[TileManifestEntry] = Field(default_factory=list)
WorldPackManifest.world_map_cells: int = 0
WorldPackManifest.wilderness_tiles_total: int = 0
WorldPackManifest.wilderness_chunks_baked: int = 0
validator WorldPackManifest._reject_removed_size_keys
WorldPackManifest.valid_region_index(cls, entries: list[WildernessRegionEntry]) -> list[WildernessRegionEntry]
WorldPackManifest.wilderness_region_entry(self, region_uid: str) -> WildernessRegionEntry | None
WorldPackManifest.tile_entry(self, gx: int, gy: int) -> TileManifestEntry | None
WorldPackManifest.chunk_ref(self, gx: int, gy: int, cx: int, cy: int) -> ChunkRef | None
WorldPackManifest.location_entry(self, location_uid: str) -> LocationTerrainEntry | None
WorldPackManifest.settlement_structure_entry(self, location_uid: str) -> SettlementStructureEntry | None
```
Прямые importers: `backend/app/dataModel/worldPack/__init__.py`; `backend/app/dataModel/worldPack/bake/detailedBakeScope.py`; `backend/app/dataModel/worldPack/bake/wildernessRefineStatus.py`; `backend/app/dataModel/worldPack/wire/settlementStructureStatus.py`; `backend/app/application/worldData/mapCells/mapCellQueryFacade.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorSkip.py`; `backend/app/application/worldData/pack/io/packManifestStore.py`; `backend/app/application/worldData/pack/io/wildernessRegionIndexWriter.py`; `backend/app/application/worldData/pack/io/worldPackReader.py`; `backend/app/application/worldData/pack/io/worldPackWriter.py`; `backend/app/application/worldData/pack/refine/fine/fineRectDrain.py`; `backend/app/application/worldData/pack/refine/fine/fineScenePathRefine.py`; `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkRunner.py`; `backend/app/application/worldData/pack/refine/fine/prep/fineTileContext.py`; `backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py`; `backend/app/application/worldData/pack/bake/detailed/detailedBakeScope.py`; `backend/app/application/worldData/pack/bake/finalize/packCompletenessClassifier.py`.

#### `backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py`

[Исходник](../../backend/app/dataModel/worldPack/wire/fineTerrainChunkWire.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class FineTerrainZRun(BaseModel)
FineTerrainZRun.z0: int
FineTerrainZRun.z1: int
FineTerrainZRun.system_terrain: str
FineTerrainZRun.system_material: str | None = None
FineTerrainZRun.cells(self) -> list[tuple[int, int, int]]
class FineTerrainColumnWire(BaseModel)
FineTerrainColumnWire.lx: int
FineTerrainColumnWire.ly: int
FineTerrainColumnWire.runs: list[FineTerrainZRun]
FineTerrainColumnWire.system_facing: Facing | None = None
FineTerrainColumnWire.system_grade_uid: str | None = None
FineTerrainColumnWire.region_uid: str | None = None
validator FineTerrainColumnWire._parse_facing
class FineTerrainChunkWire(BaseModel)
FineTerrainChunkWire.SCHEMA_ID: ClassVar[str] = 'SCH-FINE-TERRAIN-CHUNK-WIRE'
FineTerrainChunkWire.cx: int
FineTerrainChunkWire.cy: int
FineTerrainChunkWire.chunk_columns: int
FineTerrainChunkWire.columns: list[FineTerrainColumnWire]
validator FineTerrainChunkWire._positive_chunk
```
Прямые importers: `backend/app/dataModel/worldPack/__init__.py`; `backend/app/application/worldData/render/fineTerrainAsciiKernel.py`; `backend/app/application/worldData/render/pack/locationCityPackRenderer.py`; `backend/app/application/worldData/render/pack/locationTerrainPackRenderer.py`; `backend/app/application/worldData/render/pack/wildernessTilePackRenderer.py`; `backend/app/application/worldData/pack/io/packBlobWire.py`; `backend/app/application/worldData/pack/io/worldPackReader.py`; `backend/app/application/worldData/pack/io/worldPackWriter.py`; `backend/app/application/worldData/pack/read/fineTerrainDecodeCache.py`; `backend/app/application/worldData/pack/read/mapCellToFineTerrainWire.py`; `backend/app/application/worldData/pack/read/packRenderReadFacade.py`; `backend/app/application/worldData/pack/read/terrainContributions.py`; `backend/app/application/worldData/pack/refine/gridNeighborHalo.py`; `backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py`.

#### `backend/app/dataModel/worldPack/wire/hydrologyMaskWire.py`

[Исходник](../../backend/app/dataModel/worldPack/wire/hydrologyMaskWire.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class WorldMapHydrologyRole(IntEnum)
WorldMapHydrologyRole.from_wire(cls, value: int | str | WorldMapHydrologyRole | None) -> WorldMapHydrologyRole
WorldMapHydrologyRole.to_fine_role(self) -> HydrologyCellRole | None
WorldMapHydrologyRole.merge_rank(self) -> int
WorldMapHydrologyRole.merge(cls, a: WorldMapHydrologyRole, b: WorldMapHydrologyRole) -> WorldMapHydrologyRole
class HydrologyMaskWire(BaseModel)
HydrologyMaskWire.SCHEMA_ID: ClassVar[str] = 'SCH-HYDROLOGY-MASK-WIRE'
HydrologyMaskWire.role: WorldMapHydrologyRole = WorldMapHydrologyRole.NONE
HydrologyMaskWire.width: int | None = None
validator HydrologyMaskWire._clamp_width
```
Прямые importers: `backend/app/dataModel/worldPack/__init__.py`; `backend/app/dataModel/worldPack/wire/worldMapCellWire.py`; `backend/app/dataModel/hydrology/planning/hydrologyPlan.py`; `backend/app/application/worldData/masks/terrainMerge.py`; `backend/app/application/worldData/render/light/lightMapCells.py`; `backend/app/application/worldData/render/worldMap/worldMapMacroRender.py`; `backend/app/application/worldData/pack/read/worldMapPackReader.py`; `backend/app/application/worldData/pack/bake/l0/worldMapHydrology.py`; `backend/app/application/worldData/pack/bake/lightGrid/bake.py`; `backend/app/application/worldData/pack/bake/lightGrid/cell.py`; `backend/app/application/worldData/pack/bake/log/worldMap.py`; `backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/coarseOpenWater.py`; `backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/declaredBasins.py`; `backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/declaredRivers.py`; `backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/raster.py`; `backend/app/application/worldData/generators/hydrology/shore/parentLightHydroCorridor.py`; `backend/app/application/worldData/generators/hydrology/load/paint/declaredWaterPaintProjector.py`.

#### `backend/app/dataModel/worldPack/wire/territoryVolume.py`

[Исходник](../../backend/app/dataModel/worldPack/wire/territoryVolume.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class TerritoryVolume(BaseModel)
TerritoryVolume.SCHEMA_ID: ClassVar[str] = 'SCH-TERRITORY-VOLUME'
TerritoryVolume.x0: int
TerritoryVolume.y0: int
TerritoryVolume.z0: int
TerritoryVolume.x1: int
TerritoryVolume.y1: int
TerritoryVolume.z1: int
validator TerritoryVolume._normalize_bounds
TerritoryVolume.contains(self, x: int, y: int, z: int) -> bool
empty_inclusive(a0: int, a1: int, b0: int, b1: int) -> int
volumes_conflict(vol_a: TerritoryVolume, vol_b: TerritoryVolume, policy: TerritoryVolumePolicy) -> bool
inside_location_volume(x: int, y: int, z: int, volumes: list[TerritoryVolume]) -> bool
```
Прямые importers: `backend/app/dataModel/worldPack/__init__.py`; `backend/app/dataModel/worldPack/meta/worldPackManifest.py`; `backend/app/application/worldData/locations/settlementMapOccupancy.py`; `backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py`; `backend/app/application/worldData/render/pack/locationCityPackRenderer.py`; `backend/app/application/worldData/render/pack/locationTerrainPackRenderer.py`; `backend/app/application/worldData/pack/read/locationTerritoryVolumes.py`; `backend/app/application/worldData/pack/read/packRenderReadFacade.py`; `backend/app/application/worldData/pack/refine/fine/fineRectDrain.py`; `backend/app/application/worldData/pack/refine/fine/fineScenePathRefine.py`; `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkGeom.py`; `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkPersist.py`; `backend/app/application/worldData/pack/refine/fine/chunk/fineChunkRunner.py`; `backend/app/application/worldData/pack/refine/fine/prep/fineTileContext.py`; `backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py`; `backend/app/application/worldData/pack/bake/detailed/detailedBakeScope.py`.

#### `backend/app/dataModel/worldSnapshot/identity/publication.py`

[Исходник](../../backend/app/dataModel/worldSnapshot/identity/publication.py). Статус: existing, reuse-кандидат / точное изменение OPEN.

```text
class WorldPublicationRef(BaseModel)
WorldPublicationRef.world_uid: EntityUid
WorldPublicationRef.publication_id: EntityUid
WorldPublicationRef.pack_hash: RevisionHex | None
WorldPublicationRef.snapshot_head: WorldSnapshotRef | None
WorldPublicationRef.active_timeline_id: EntityUid | None
WorldPublicationRef.gameplay_started: bool
WorldPublicationRef.coherent_refs(self) -> Self
class PlayerHeadExpectation(BaseModel)
PlayerHeadExpectation.player_uid: EntityUid
PlayerHeadExpectation.expected_head: PlayerSnapshotRef | None
PlayerHeadExpectation.coherent_refs(self) -> Self
```
Прямые importers: `backend/app/db/repositories/sqlite/snapshotCore/publications/playerPublicationStore.py`; `backend/app/db/repositories/sqlite/snapshotCore/publications/worldPublicationStore.py`; `backend/app/dataModel/worldSnapshot/results/apply.py`; `backend/app/dataModel/worldSnapshot/results/publication.py`; `backend/app/dataModel/patch/request/patchSet.py`; `backend/app/application/worldSnapshot/contracts/context.py`; `backend/app/application/worldSnapshot/storage/publicationStore.py`; `backend/app/application/patch/encoding/patchSetCodec.py`; `backend/app/application/artifacts/encoding/coreManifest.py`.

### 0.10. Сквозная bake-трасса: уточнение по ревью (2026-11-01)

Evidence: HEAD `72d61d44`; прочитаны тела методов цепочек ниже и выполнен поиск call sites по `backend`, `scripts` (`*.py`). Стрелки означают статически прослеженный вызов/передачу результата, а не лог успешного bake конкретного мира. Runtime/CLI/HTTP не запускались. Первоначальная карта фабрик §0.2 сама по себе была недостаточным evidence; настоящий раздел дополняет её entrypoint-to-persist цепочкой.

**HTTP light/full — вход и конкретная DI-сборка.**

1. [map.py](../../backend/app/api/routes/map.py), `POST /worlds/{world_uid}/map/pack/bake` → `bake_world_pack`: загружает World/locations/connection graph, создаёт materialization context, вызывает `surface_materialization_orchestrator()`, получает writer через `world_pack_writer_for(world)`, передаёт этот экземпляр в `stack.bake_pack(..., mode, wait=RequestPlanWait.unbounded())`. После результата читает loading progress; HTTP 200/207 не является отдельной публикацией.
2. [container/worldData.py](../../backend/app/core/container/worldData.py), `surface_materialization_orchestrator` → `WorldSurfaceMaterializationOrchestrator(pack=self.pack_materialization_orchestrator(), planning=self.surface_planning(), capture=..., ...)`. `pack_materialization_orchestrator` передаёт тому же L0 orchestrator `planning=self.surface_planning()`, `capture`, `publisher=self.pack_bake_publisher()`. Publisher получает DB/world repository/source guard/read-context factory. Это реальные аргументы constructor, а не вывод из импортов.
3. [worldSurfaceMaterializationOrchestrator.py](../../backend/app/application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py), `bake_pack`: light → `materialize_pack_light` → `_pack.materialize_light_pack`; full → `materialize_pack_full` → `_pack.materialize_full_pack`. Оба приходят в [PackMaterializationOrchestrator._materialize_l0_pack](../../backend/app/application/worldData/pack/bake/l0/packMaterializationOrchestrator.py). Различаются scope/tile cap; full затем вызывает outdoor `plan_topology`, а не полный fine-water solve.

**От prepare до фактического hydrology producer.**

4. `_materialize_l0_pack` проверяет planning/capture и запрет validate_only, загружает templates → `SurfacePlanningEntry.capture_view` → `prepare_captured`. [surfacePlanningEntry.py](../../backend/app/application/worldData/planning/composition/surfacePlanningEntry.py) → `prepare_captured_bundle` → [SurfacePlanningAssembler.prepare](../../backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py), именно `prepare`, не `prepare_geo`. Assembler собирает climate base → terrain → water placement → relief → hydrology routes → river relief → hydrology final → local climate, с явными dependency refs.
5. `surface_planning()` в container создаёт assembler с результатом `register_world_plan_providers`. `_build` assembler вызывает [PlanningService.get_or_build](../../backend/app/application/planning/service/planningService.py). **Cache hit** возвращает проверенный envelope, producer повторно не запускается. **Cache miss**: executor → `PlanningService._build` → `PlanRegistry.build` → closure зарегистрированного provider → `provider.build` ([planRegistry.py](../../backend/app/application/planning/providers/planRegistry.py)). Поэтому фактический producer выводится из request contract + переданных providers, а не из наличия native class.
6. Зарегистрированный routes producer: [HydrologyRoutesPlanProvider.build](../../backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py) → [HydrologyRoutesAssembler.assemble](../../backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyRoutesAssembler.py) → `WaterBodyPlanner.plan` → [WaterBodyJob.plan](../../backend/app/application/worldData/generators/hydrology/water/planning/waterBodyJob.py). После проверки topology/surface/scopes disabled/no-water branch возвращает пустой OpenWaterPlan; активная ветка → `_materialize` → `assemble_water_bodies` на coarse surface/specs. Затем assembler `_routes` вызывает coarse/fine river planners и declared paint projector. Это legacy/coarse production-контракт, не `FineWaterJob.fill` native source.
7. Final producer: `HydrologyFinalPlanProvider.build` требует relief/routes/river envelopes и проверяет refs → [HydrologyFactsAssembler.assemble](../../backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py): coverage/receiver checks, объединение coarse open water и river roles, fine river roles, создание `HydrologyPlan`. Результат возвращается через registry/service в `SurfacePlanBundle.hydrology`. `SurfacePlanningEntry.prepare_captured` строит из него `HydrologyWorkingFields` внутри `SurfaceWorkingMaps`. Native `GeoHydrologyFinalPlanProvider`, `prepare_geo`, `FineWaterPublicationJob/FineWaterJob.fill`, `NativeFinalWaterQuery` в этой прослеженной цепочке не вызываются; это не глобальное доказательство отсутствия иных динамических маршрутов.

**От результата producer до файлов и world metadata.**

8. `_materialize_l0_pack` после prepare загружает region states, планирует tiles; при включённом background drain сначала вызывает `_entry.drain_persisted(..., surface_bundle, working)`. Затем coarse climate bake и `writer.write_locations_index`; [WorldMapBakeOrchestrator.bake_tiles](../../backend/app/application/worldData/pack/bake/l0/worldMapBakeOrchestrator.py) получает тот же bundle/working → `LightGridBakeContext` → `compose_light_grid`.
9. [maskDomainRegistry.py](../../backend/app/application/worldData/pack/bake/lightGrid/maskDomainRegistry.py) строит contributors по COMPOSE_CONTRIBUTOR_ORDER; HYDRO factory — `HydroContributor`. Его `apply` читает `bundle.hydrology.payload.declared_paint` и вызывает declared rivers/basins + coarse open water projection. Результат compose → `to_wire_tile` → `writer.write_world_map_tile`. Full дополнительно применяет world seam. Relief grades сохраняются отдельно; затем climate fine L0 policy может записать дополнительные climate tiles. Это несколько фактических write paths в одном bake, а не только вызов writer factory.
10. [WorldPackWriter.write_world_map_tile](../../backend/app/application/worldData/pack/io/worldPackWriter.py) → `world_map_tile_payload` → `TileCodec.encode` → `_atomic_write`: временный файл, `write_bytes`, `os.replace` по координатному пути, hash. Обновляются manifest tile entry и parent-light cache. Другие blobs к этому моменту также уже могут быть записаны.
11. `_materialize_l0_pack` → `self._publisher.publish` (в production DI publisher передан) → [PackBakePublisher.publish](../../backend/app/application/worldData/pack/bake/finalize/packBakePublisher.py): DB `transaction_if_needed`, `SourcePublicationGuard.require_fresh`, counters → [finalize_pack_on_world](../../backend/app/application/worldData/pack/bake/finalize/packBakeFinalize.py). Finalizer проверяет world identities, готовит detached row, вызывает `writer.save_manifest`, затем сохраняет `terrain_pack_path`/`terrain_pack_hash` через `world_repository.update`. В finally инвалидирует read-context old/new pack roots, в том числе при ошибке SQL/validation после изменения файлов.
12. `save_manifest`: counters → canonical JSON без content_hash → SHA256 → [PackManifestStore.save](../../backend/app/application/worldData/pack/io/packManifestStore.py): temporary file + `os.replace`. **Граница атомарности:** замена отдельного blob/manifest и SQL transaction; запись файлов предшествует обновлению world row, общей rollback-гарантии файлов и SQL эта цепочка не даёт. Это действующая path-based финализация, не staged ArtifactRef/domain-root publication и не WorldPublicationRef/Snapshot activation. SP-P2/P3W не закрываются её наличием.

**HTTP detailed — отдельная ветка того же входа.**

`bake_pack(mode=detailed)` → `materialize_pack_detailed`: capture/prepare через тот же legacy assembler → region states → [PackDetailedBakeOrchestrator.bake](../../backend/app/application/worldData/pack/bake/detailed/packDetailedBakeOrchestrator.py) → `_refine_tiles` → [refine_detailed_tiles](../../backend/app/application/worldData/pack/bake/detailed/detailedBakeRefine.py): parent-light gate → `FineChunkRunner.refine_rects` → prepare_fine_tile/compute_rect → TerrainBatchOrchestrator/columnFill (§0.3) → [FineChunkPersist](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkPersist.py) → `cells_to_fine_terrain_chunk` → `write_wilderness_chunk` (location cells обрабатываются отдельной веткой persist). После L2/climate работ surface orchestrator в DB transaction проверяет source freshness, пересчитывает counters и вызывает `save_manifest`; затем возможен C11 settlement materialize. Здесь нет вызова L0 PackBakePublisher/finalize_pack_on_world. Не считать detailed автоматическим повторением L0 world-row publication или native water activation.

### 0.11. CLI и legacy caller/disposition evidence

**Offline CLI:** [backend/scripts/bake_world_pack.py](../../backend/scripts/bake_world_pack.py), `main` → `_run`: ConfigManager/Database/Container → planning_resources → DB connect → World/locations/graph → context → `container.world_pack_writer(world_uid)` (не HTTP `world_pack_writer_for(world)`) → `surface_materialization_orchestrator`. Только mode=light вызывает `materialize_pack_light` напрямую, обходя `bake_pack` dispatch; далее совпадает с шагами 3–12 выше, включая publisher. Parser допускает light/tile/full, но `_run` для любого не-light печатает not implemented и возвращает 2. `world_pack_writer` использует `world_pack_paths(world_uid)`/`from_db_parent`; HTTP writer использует `WorldPackPaths.for_world(world, db_path)`. Равенство root при настроенном terrain_pack_path нельзя предполагать. В finally CLI вызывает shutdown_planning и disconnect.

**HTTP CLI wrappers:** [light_and_full_bake.py](../../backend/scripts/light_and_full_bake.py) вызывает `api_pack_bake` для light/full; [detailed_bake.py](../../backend/scripts/detailed_bake.py) — для detailed. Helper [debug_api_helpers.api_pack_bake](../../backend/scripts/debug_api_helpers.py) выполняет POST map/pack/bake; `debug_surface_helpers` импортирует этот helper. Это клиенты HTTP цепочки, не самостоятельные native producer/publisher. Скрипты при аудите не запускались (в том числе их reset/import действия).

**Уточнение caller closure и disposition (решения об удалении не приняты):**

- Поиск `.bake_pack(`: app caller — `api/routes/map.py`; также `tests/test_detailed_bake_c11.py`. `.materialize_pack_light(`: offline CLI и dispatch surface orchestrator; `.materialize_pack_full(`: surface dispatch. `.materialize_light_pack/full_pack(`: делегаты surface orchestrator и отдельные тесты. Override `pack_orchestrator` у `materialize_pack_light` существует, штатные HTTP/CLI его не передают. Disposition: сохранить эти входы AS-IS до согласованного cutover; нельзя добавить native маршрут только в одной factory и считать все entrypoints переведёнными.
- `finalize_pack_on_world(`: помимо PackBakePublisher есть прямые app callers в `map.py` — refine-from-entry, refine-chunk, schedule-chunk-refine; также tests/test_pack_bake_finalize.py. Следовательно, publisher не единственная действующая точка финализации Pack. Disposition: каждый direct route требует отдельного migration decision; не удалять finalizer и не объявлять closure одной bake цепочкой.
- Native provider/query и legacy provider разделены §0.2/0.10; scene debug и SQL engine callers разделены §0.4. Native classes/tests/format declarations не доказывают production binding. Для пути будущего domain-root reader/publisher точного replacement пока нет. Disposition MergedCellView/MapCellService/facade: сохранять до SP-R0, не удалять целиком из-за water-only use case.
- Полнота поиска ограничена Python call spellings и статическими registry/factory связями текущего дерева. Dynamic aliases, external clients, jobs persisted ранее, concurrent requests, cache contents и фактический запуск окружения этим не проверены. **LEGACY-AC OPEN:** нет доказательства полного списка всех runtime callers и отсутствия mixed runtime. Ни одно отсутствие найденного import/call site не заменяет такую приёмку.

### 0.12. Статус после уточнения

**SP-0 — НА ПРИЁМКЕ.** Основной анализ и сквозная статическая трасса HTTP/CLI bake предъявлены; решение владельца остаётся OPEN. Строка SP-0 в WORLD-PLAN-GRAPH-1 синхронизирована с этим статусом. **Не DONE; LEGACY-AC OPEN; SP-1 и кодовые gates не приняты.** Новых архитектурных решений, POJO, схем, runtime wiring и production-кода это уточнение не вводит. Для завершения нужна согласованная приёмка результата и применимого legacy caller/disposition evidence; статический source trace не переименовывается в успешный runtime smoke.

### 0.13. Приёмочное ревью evidence §0.1–0.12 (2026-11-01)

**Обновление после доработки:** SP0-REV-1/2 документально обработаны в §0.14 и ожидают повторного review. Ниже сохранены исходные замечания; это не текущий список неисправленных пропусков. SP-0 остаётся НА ПРИЁМКЕ, LEGACY-AC OPEN.

**Вердикт: требуется документальная доработка; SP-0 остаётся НА ПРИЁМКЕ, не DONE; LEGACY-AC OPEN.** Review baseline `8d1eda09`, чистое рабочее дерево до начала ревью. Это проверка предъявленного evidence и точечный поиск пропущенных callers, не повторный аудит и не архитектурный freeze. Код, тесты, registry и schema не менялись.

**Подтверждено кодом:** HTTP light/full → surface facade → L0 orchestrator → captured bundle → `prepare`/registered legacy providers → L0 compose/writer → publisher/finalizer; разделение cache hit/miss; offline CLI light-only и отличие writer factory; native FineWaterJob требует полной fine surface, NativeFinalWaterQuery возвращает XY identity с domain coverage semantics, а не Pack/Snapshot XYZ; MapCell scene/read, SQL eager/lazy engine и потеря не представленных клетками media; отсутствие hydrology fields в terrain z-runs; optional region consumer не различает пустой hydro и полностью сухую известную surface. Проверенные прямые `finalize_pack_on_world` callers в map routes соответствуют §0.11. Подсчёты уже перечисленных в §0.8 каталогов совпадают с текущим деревом. Статус графа соответствует §0.12. Существенных опровержений этих выводов не найдено.

**SP0-REV-1 [P2] — не доведён caller/disposition для settlement-потребителей facade.**

§0.9 содержит их как importers `MapCellQueryFacade`, но §0.4/0.11 не фиксирует исполняемые edges: [container/worldData.py](../../backend/app/core/container/worldData.py), строки 297–298, передаёт `writer_for=self.world_pack_writer_for` и `facade_for=self.map_cell_query_facade` в SettlementOutdoorOrchestrator. Его `plan_topology` → `SettlementOutdoorTopologyJob.plan_batch/plan_one` → [get_footprint_terrain](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorTopologyJob.py) (строка 143); `materialize` → `SettlementOutdoorPackingJob.run_queue` → [get_footprint_terrain](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py) (строка 128). Это callers внутри уже названных full/C23 и detailed/C11 веток, а не только тестовые imports. Их read contract — footprint surface MapCells, отличный от scene XYZ read. Общего «сохранять facade до SP-R0» недостаточно для оценки миграции: из карты нельзя понять, что эти consumers должны продолжать получать surface read и не становятся автоматически consumers water slices.

Для закрытия замечания: добавить эти конкретные edges и отдельный disposition footprint API/его consumers (сохранение существующего контракта либо решение OPEN с названным owning gate); указать входы в settlement orchestrator, которые остаются вне прослеженных bake веток. Выбирать новый reader/POJO или переносить код для этого не требуется.

**SP0-REV-2 [P2] — inventory публикации ограничен finalizer и пропускает прямой manifest commit.**

§0.10 корректно описывает L0 finalizer и отдельно detailed `save_manifest`, но §0.11 не даёт полного caller/disposition для других действующих публикаций: [SettlementOutdoorPackingJob.materialize_district](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py), строка 283 → [WorldPackWriter.publish_settlement_structure](../../backend/app/application/worldData/pack/io/worldPackWriter.py), строка 266 → `self.save_manifest()` (строка 307). Этот путь достижим в уже указанном C11 после detailed и меняет manifest отдельным writer; его нельзя считать покрытым утверждением о том, что detailed не вызывает L0 publisher/finalizer. Прямой script caller того же метода — [debug_settlement_persist.py](../../backend/scripts/debug_settlement_persist.py), строка 124 — также отсутствует в CLI disposition. Это существующие path-based writes, не staged publication; сам код здесь не оценивается как дефект.

Точечный поиск `.save_manifest(` дополнительно обнаружил [FineRectDrain.refine_rect](../../backend/app/application/worldData/pack/refine/fine/fineRectDrain.py), строка 69. При этом поиск `refine_rect(` по app/scripts не обнаружил внешнего caller публичного метода; queued path вызывает `_refine_rect` через `refine_queued_chunk` и не выполняет этот save. Это нужно классифицировать как существующий публичный API с неподтверждённым production caller, а не ошибочно приписать save каждому background drain.

Для закрытия замечания: дополнить publication inventory прямыми save/publish edges, разделить manifest-only commit и world-row finalization, указать конкретные callers и disposition этих входов. Существующий §0.10 не надо переписывать в предположение об общей транзакции и не надо добавлять staged publisher.

**Оставшиеся ограничения и критерий повторного review.** Общие оговорки о dynamic aliases/external clients в §0.11 честно оставляют LEGACY-AC OPEN, но не заменяют перечисление известных статических callers выше. Runtime smoke не проводился и не требуется только ради повторной проверки этих двух документальных замечаний: их можно закрыть кодовыми ссылками/call edges/disposition. После уточнения проверить именно SP0-REV-1/2 и применимость legacy-критерия SP-0; автоматической приёмки, перехода SP-1 в READY или разрешения на код этот review не даёт. Новых архитектурных решений не предложено.

### 0.14. Доработка SP0-REV-1/2: caller/disposition evidence (2026-11-01)

**Статус доработки: оба замечания документально обработаны, переданы на повторную приёмку.** База кода `8d1eda09`; §0.13 и строка графа уже присутствовали в working tree до этой доработки и сохранены. Проверялись именно пропуски ревью: определения, DI-аргументы, вызовы footprint API, settlement publisher и прямые save_manifest. Backend/CLI/tests не запускались; production wiring не менялся. Вердикт §0.13 — история первого review; текущая готовность: evidence дополнен, **SP-0 НА ПРИЁМКЕ, DONE не присвоен, LEGACY-AC OPEN**.

#### SP0-REV-1 — settlement footprint read и конкретные входы

**Связь DI и потребителей.** [Container.settlement_outdoor_orchestrator](../../backend/app/core/container/worldData.py) передаёт `writer_for=self.world_pack_writer_for`, `facade_for=self.map_cell_query_facade` и pack-context factory. [SettlementOutdoorOrchestrator._require_pack](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorOrchestrator.py) получает facade через эту factory и проверяет `has_pack_for(world)`.

- Full bake: `WorldSurfaceMaterializationOrchestrator.materialize_pack_full` после L0 вызывает `_outdoor.plan_topology(world_uid)` → `SettlementOutdoorOrchestrator.plan_topology` → `SettlementOutdoorTopologyJob.plan_batch` → `plan_one` → [facade.get_footprint_terrain](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorTopologyJob.py), строка 143. Передаются XY bounds territory volume и location UID. При готовой topology `plan_one` может завершиться до чтения footprint; наличие вызова в методе не означает чтение в каждом запросе.
- Detailed/C11: `_maybe_materialize_c11` вызывает `outdoor.materialize` только для подходящего location scope/settlement target → `SettlementOutdoorOrchestrator.materialize` → `SettlementOutdoorPackingJob.run_queue` → [facade.get_footprint_terrain](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py), строка 128. Skip/error branches могут завершиться раньше. Surface cells входят в DistrictPackContext и передаются `generate_layout` при `materialize_district`.
- Входы вне bake: [locations.py](../../backend/app/api/routes/locations.py), `POST /worlds/{world_uid}/locations/{location_uid}/generate-settlement` → `materialize` (включая district_uid/at_x/at_y); `POST /worlds/{world_uid}/generate-settlements` с ровно одним selector `all|under|state_uid` → `materialize_all|materialize_under|materialize_state` → `_materialize_many` → `materialize` для каждой выбранной location. Эти debug routes используют тот же orchestrator, не отдельную packing implementation. Отдельного app/script caller `plan_topology` вне full bake в выполненном поиске не найдено.
- Script HTTP consumer single route: [debug_api_helpers.api_generate_settlement](../../backend/scripts/debug_api_helpers.py) → POST generate-settlement; [debug_settlement_persist.test_persist_outdoor_http](../../backend/scripts/debug_settlement_persist.py) вызывает helper дважды. Это HTTP smoke, отличное от in-process direct publisher ниже. Legacy `lazySettlementNode` в engine использует SQL `map_cell_repo` и `generate_map_cells`, не этот facade/packing orchestrator; не приписывать ему C11 path (см. также §0.4).

**Фактический read contract.** [MapCellQueryFacade.get_footprint_terrain](../../backend/app/application/worldData/mapCells/mapCellQueryFacade.py): `async (world: World, *, x0: int, y0: int, x1: int, y1: int, location_uid: str | None = None) -> list[MapCell]`. Собирает surface columns из location terrain, при пустом наборе использует L0 surface samples, затем применяет patches в bbox выбранных surface z и batch merge/overlay. Это не XYZ z-flood и не city-structure raster read; возвращённые клетки используются как terrain input settlement geometry. Пустой набор возвращается пустым; ни water slice, ни ambient gas composition этот API не обещает.

**Disposition на стадии SP-0:** сохранять существующие `get_footprint_terrain`, topology/packing consumers и их surface-MapCell контракт. Они **не являются автоматически заменяемой частью water-only scene read**. Не удалять facade целиком при SP-R migration. Возможная последующая модификация footprint/terrain composition — OPEN в SP-M/SP-G (при необходимости согласования scene facade также SP-R0); требует отдельного contract/caller freeze, а не подстановки SpatialSlice вместо list[MapCell]. Для HTTP single/batch и C11/full входов disposition одинаков: сохранить текущий вход и делегирование; replacement не выбран. Это фиксация AS-IS, не утверждение новой архитектуры.

#### SP0-REV-2 — manifest commit, world-row finalization и direct callers

**Полный результат точечного поиска прямого `.save_manifest(` в backend/app:** четыре места: `WorldPackWriter.publish_settlement_structure`, `FineRectDrain.refine_rect`, `WorldSurfaceMaterializationOrchestrator.materialize_pack_detailed`, `finalize_pack_on_world`. Последние два уже разобраны в §0.10; первые два раскрыты ниже. Поиск выполнен также по backend/scripts: прямого save_manifest там не найдено, но есть вызов settlement publisher. Это closure для конкретного call spelling и найденных методов, не доказательство отсутствия произвольных внешних/динамических consumers.

1. **Production C11 и HTTP single/batch:** `SettlementOutdoorPackingJob.run_queue` перебирает district queue → `materialize_district` → generate_layout/extract → `writer.encode_settlement_structure_tmp` → `await self._sql.persist(extracted)` → [writer.publish_settlement_structure](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorPackingJob.py), строка 283 → `_invalidate(world, facade)`. DI invalidator вызывает `context.invalidate_pack(world)` и `facade.invalidate_city_structure`. Входы — detailed C11 и settlement routes из блока REV-1; full topology сама не вызывает district publisher.
2. [WorldPackWriter.publish_settlement_structure](../../backend/app/application/worldData/pack/io/worldPackWriter.py), строка 266: переносит tmp blob через `os.replace` либо при retry проверяет уже опубликованный blob на размер/hash; обновляет SettlementStructureEntry (path/hash/bytes/status/packed district UIDs) → `self.save_manifest()` (строка 307). Возвращает content hash. Это **blob + manifest publication** после SQL persist caller-а. Здесь нет `world_repository.update`, `finalize_pack_on_world`, SourcePublicationGuard либо общей staged ArtifactRef/Snapshot publication. Следовательно, не отождествлять manifest.content_hash с гарантированно обновлённым terrain_pack_hash world row. В multi-district queue публикация выполняется на district, а не один раз на весь batch; SQL/files rollback общей операцией из этой цепочки не следует.
3. **Отдельный in-process script caller:** [debug_settlement_persist.test_persist_outdoor_inprocess](../../backend/scripts/debug_settlement_persist.py), строка 124: создаёт временные smoke.db и `WorldPackPaths(Path(tmp) / pack, world_uid)`, layout/extract/SQL persist, вызывает `publish_settlement_structure` напрямую, проверяет read-back; finally удаляет временный каталог. Это smoke harness с собственным writer, не ещё один production bake entrypoint. Отдельная HTTP-функция того же скрипта использует route из REV-1; эти два режима не объединять. Скрипт при аудите не исполнялся.
4. **FineRectDrain:** [refine_rect](../../backend/app/application/worldData/pack/refine/fine/fineRectDrain.py), строка 56 → `_refine_rect` → FineChunkRunner → `writer.save_manifest()` (строка 69), без world-row finalizer. В app/scripts внешний caller публичного refine_rect не найден; найден тест `test_pack_fine_terrain_refine_parallel.py`. DI действительно содержит FineRectDrain, но это не доказательство вызова данного public метода.
5. **Queued branch отличается:** `FineRectDrain.refine_queued_chunk` → `_refine_rect`, минуя public refine_rect/save. Его app callers: [ChunkRefineWorker](../../backend/app/application/worldData/pack/refine/chunks/chunkRefineWorker.py), drain persisted/queue, и `map.py` refine-chunk route. Поэтому `_entry.drain_persisted` внутри L0 bake не получает промежуточный save из public refine_rect; L0 завершает публикацию через свой publisher. Refine-chunk route отдельно выполняет finalizer, как уже указано в §0.11. Нельзя выводить лишний nested commit из одного наличия метода refine_rect.

**Disposition по входам:** существующие settlement district publisher, single/batch HTTP и их C11 consumers сохраняются; это object/structure persistence, не замена canonical water-root writer. In-process script сохраняется как smoke harness, HTTP helper — как клиент существующего route. Public FineRectDrain.refine_rect сохраняется как existing API с test caller и неподтверждённым production caller; не удалять по отрицательному поиску и не активировать его в queued path ради SPATIAL. Finalizer/detailed manifest commit сохраняют отдельные disposition §0.10/0.11. Если будущий SP-P0/P2W/P3W cutover затронет общий writer/publication transport, все перечисленные manifest commit edges входят в обязательный compatibility/migration review; точные replacement и порядок переноса OPEN у owning Pack/GEN-DAG и SP-M/R0 по их области. Новый publisher или изменение SQL/files ordering этим inventory не выбирается.

**Дополнение file counts к §0.8:** непосредственные файлы, включая __init__.py: `backend/app/application/worldData/settlementOutdoor` **15 → 15**, `backend/app/api/routes` **16 → 16**, `backend/app/application/worldData/pack/refine/fine` **6 → 6**, `backend/app/application/worldData/pack/refine/chunks` **4 → 4**, `backend/app/application/worldData/pack/refine/entry` **4 → 4**, `backend/scripts` **21 → 21**. Новых файлов/import migrations нет. Для >5 действует WARN; в каталогах >10 добавления запрещены до согласованной композиции, существующие файлы этот анализ не переносит.

**Проверка доработки:** кодовые ссылки и call edges выше сверены с исходниками; REV-1 теперь содержит известные DI/consumer/HTTP/script edges и раздельный footprint disposition; REV-2 содержит все найденные прямые save_manifest call sites app/scripts, direct settlement publisher callers и различие public/queued refine. Замечания отмечаются как **исправленные в evidence, ожидают повторного review**, а не автоматически принятые. Остаточный LEGACY-AC OPEN относится к общей полноте runtime/cutover и внешним/динамическим consumers; он не маскирует эти два известных пропуска. Runtime smoke не заявлен, новые архитектурные решения и кодовые gates не приняты.

### 0.15. Приёмка SP-0 владельцем (2026-11-01)

Пользователь явно сообщил: «Принимаю SP-0». **SP-0 — DONE.** Принят фактический статический inventory §0.1–0.14, включая доработки SP0-REV-1/2. Исторические статусы НА ПРИЁМКЕ в §0.12–0.14 сохраняют историю и заменены настоящей записью. Это приёмка архитектурного аудита и достаточности его caller/disposition evidence для перехода к SP-1, а не runtime smoke или production cutover. **Глобальный LEGACY-AC остаётся OPEN** для последующей миграции/отключения путей; известные AS-IS пути и временное сохранение перечислены, готовность будущего target не утверждается. Новая команда разрешает архитектурный SP-1, не production-код.

## 14. SP-1 — exact shared read contract: проект на согласование

**Статус: документальный архитектурный результат ПРИНЯТ пользователем в scope §14.12; запись приёмки — §14.14. Implementation не принят.** Начат после явной приёмки SP-0; ниже один конкретный предлагаемый контракт, не молчаливое архитектурное решение. Никаких Python-файлов/POJO/enum/schema/tests/wiring не создано. Основание: §3, §7, §8 SP-1, §11 ARCH-3/4/6/7; профильные требования — [Terrain Generation](../../docs/tz_terrain_generation.md), [World Pack](../../docs/tz_world_pack_storage.md), [World Snapshot](../../docs/tz_world_snapshot.md), [Hydrology](../../docs/tz_terrain_hydrology.md). Exact water payload/source остаётся GEO; exact root format — SP-P0; materialization — SP-M; gameplay consumer/composition — SP-R0.

### 14.1. Reuse против новых деклараций

- **Reuse без изменений:** [CoordinateSpace](../../backend/app/dataModel/spatial/grid/coordinateSpace.py) и [FineX/FineY/FineZ](../../backend/app/dataModel/spatial/grid/coordinateTypes.py); [WorldTopology](../../backend/app/dataModel/topology/worldTopology.py)/WorldBounds и WorldTopologyMode; [PlanRef](../../backend/app/dataModel/planning/identity/planRef.py); [WorldPublicationRef](../../backend/app/dataModel/worldSnapshot/identity/publication.py); [ArtifactRef](../../backend/app/dataModel/artifacts/references.py); [FieldPathError](../../backend/app/dataModel/validation/diagnostics/fieldPathError.py). Fields/validators этих моделей не копируются в новый wire; применяются существующие определения. Строгость вложенного WorldTopology/WorldBounds не наследуется от внешнего ConfigDict; точная admission-проверка frame задана ниже.
- **Новый SpatialBox обоснован:** GridBBox/SurfaceGridRect — XY; FineGridRect — XY + один z; FineGridCoord — точка. [TerritoryVolume](../../backend/app/dataModel/worldPack/wire/territoryVolume.py) — location-specific inclusive AABB с int-coercion и сортировкой перевёрнутых границ. Расширять/менять его ради общего read означало бы изменить legacy location контракт. Предлагаемый box использует half-open bounds, strict coordinates и отказ вместо исправления запроса. Конверсия existing inclusive territory по конкретному caller — `(x0,y0,z0,x1+1,y1+1,z1+1)` вне shared reader, без изменения TerritoryVolume; такие callers пока не активируются.
- **Не копировать:** RegionCoverage/CoverageSpan/FineSurfaceWindow — domain terrain coverage/fine evidence, а не общий XYZ request/proof. FineTerrainZRun и HydrologyMaskWire — производные Pack проекции. MapCell/MergedCellView — legacy cell output. KnownFact/UnknownFact — existing policy observation types с собственными ограничениями; они могут быть частью подходящего доменного T, но не навязываются всем результатам. Нет нового SpatialFact/SpatialCoverage, общего material registry, owner registry или revision counter.
- **Минимальные новые declarations:** SpatialBox + SpatialWindow; SpatialReadRequest + SpatialReadMode; SpatialSlice[T]; SpatialReadFailure + SpatialReadError + SpatialReadFailureReason; SpatialFieldReader[T] Protocol и aliases SpatialReadRevision/SpatialSourceRef/SpatialReadResult[T]. Отдельного Binding/Provenance/Status POJO нет: существующие refs хранятся напрямую. stdlib UUID используется только как request correlation, не durable EntityUid/новый UidKind.

### 14.2. Exact window и request (предлагаемый freeze)

Все новые data records — Pydantic BaseModel, `extra=forbid`, `frozen=True`, `strict=True`, `revalidate_instances=always`. Новые коллекции — tuple, без mutable list/dict/default_factory. T остаётся доменным типом без обязательного BaseModel-наследования; domain contract обязан обеспечивать immutable data (frozen records/tuples/scalars), не job/callback/connection. Новые records in-process: не добавлять SCHEMA_ID/Pack format/encoding registry до SP-P0 и owning codec review. Pydantic serialization не является разрешением persist результата.

| Тип / поле | Exact type и required/default | Инвариант / validation |
|---|---|---|
| SpatialBox.x0, x1 | `Annotated[FineX, Field(strict=True)]`, required | x0 < x1 |
| SpatialBox.y0, y1 | `Annotated[FineY, Field(strict=True)]`, required | y0 < y1 |
| SpatialBox.z0, z1 | `Annotated[FineZ, Field(strict=True)]`, required | z0 < z1 |
| SpatialWindow.space | `Literal[CoordinateSpace.WORLD_FINE_GRID]`, required, без default | coarse/location space отклоняется, не конвертируется |
| SpatialWindow.topology | `WorldTopology`, required | bounds именно world fine grid, не coarse bounds; точное равенство frame подготовленного source проверяет доменный reader |
| SpatialWindow.boxes | `tuple[SpatialBox, ...]`, required, min_length=1 | canonical union, правила ниже |
| SpatialReadRequest.request_id | `uuid.UUID`, required | correlation запроса, не часть source/revision/content equality |
| SpatialReadRequest.window | `SpatialWindow`, required | неизменяемое окно |
| SpatialReadRequest.revision | `SpatialReadRevision = PlanRef | WorldPublicationRef`, required | различение bootstrap/runtime по concrete type, нет implicit conversion |
| SpatialReadRequest.mode | `SpatialReadMode`, required | REQUIRED или PREVIEW; caller задаёт явно |

**Admission topology (часть предлагаемого freeze).** Поле topology принимает только уже построенный `WorldTopology`, не dict; bounds — existing `WorldBounds`. До вложенной валидации SpatialWindow проверяет `type(v) is int` для четырёх bounds, наличие existing WorldTopologyMode и чётную ширину SPHERE; иначе construction ValidationError. Это проверка готового frame, без повторного вызова `even_width()` для исправления входа. Существующие WorldBounds допускает coercion/extra=ignore, WorldTopology нормализует нечётную SPHERE width; внешний strict/revalidate_instances эти правила не заменяет и не может восстановить утраченный raw input. Поэтому raw topology разбирает owning caller до создания request по собственному boundary contract; SP-1 не обещает отклонить ранее выполненную legacy-нормализацию. Reader сравнивает полный готовый frame с source (FRAME_MISMATCH). Existing `topology/fineTopology.py: fine_topology(topology, tile_macro)` даёт inclusive fine bounds `[min*S,(max+1)*S-1]`; caller использует принятый scale source, не передаёт coarse bounds с новой меткой space. GEO выбрал A: общая P2-сессия в fine frame; это не разрешает повторный lift уже fine topology. Exact producer refs/versions/caller migration остаются owning GEO freeze (актуальные решения — GEO, совместный проект §§9–10).

**Bounds и canonical union.** Каждый box — `[x0,x1) × [y0,y1) × [z0,z1)` дискретных fine cells; bool/float/string coordinates запрещены; перевёрнутые/пустые границы не сортируются. Координаты отрицательные допустимы. Boxes строго лексикографически отсортированы по `(y0,x0,z0,y1,x1,z1)`, дубликаты и объёмные пересечения запрещены (касание гранью/ребром/вершиной разрешено). Модель проверяет геометрическую корректность запроса, **не доменное coverage**. Не требуется склеивать соседние boxes; разделение запроса не меняет смысл его union.

XY box должен полностью лежать в canonical fine topology bounds: `bounds.x_min <= x0 < x1 <= bounds.x_max+1` и аналогично Y. Seam-crossing запрос caller явно разбивает по существующей WorldTopology на canonical disjoint boxes **до** вызова; generic read не выполняет wrap/clamp, не выбирает соседей и не изобретает второй seam solver. SPHERE использует уже принятый fine topology frame и его existing mapping. Z не wraps и не масштабируется; допустимый vertical source scope определяет домен, превышение scope не объявляется пустотой. Проект сохраняет world-fine-only initial scope: если конкретному consumer понадобятся continuous/local coordinates, это отдельное изменение freeze, не неявная трактовка int в метрах.

**SpatialReadMode (новый StrEnum):** `REQUIRED = required`, `PREVIEW = preview`. REQUIRED означает полный достоверный ответ по объявленному domain query scope; неполный source даёт Failure. PREVIEW разрешает domain-owned unresolved внутри T с diagnostic issues. PREVIEW не ослабляет revision/frame/hash проверки и не является игровым fallback. Неизвестный enum value — validation failure. В required gameplay caller не может переключиться в PREVIEW после ошибки.

### 14.3. Exact result, failure и содержательная операция

Предлагается один `SpatialFieldReader[T]` Protocol, без constructor/factory/prepare в shared interface:

`async def read_window(self, request: SpatialReadRequest) -> SpatialReadResult[T]`

`SpatialReadResult[T] = SpatialSlice[T] | SpatialReadFailure`. Без неаннотированных kwargs, materialize/fill/persist/query_at второго API. Async выбран из-за доменного bounded Pack IO; Protocol сам не выполняет IO. Доменные реализации владеют загрузкой source/index и согласованным overlay. Создание подготовленного reader/index — отдельная owning operation вне этого контракта.

| Тип / поле | Exact type и required/default | Семантика / validation |
|---|---|---|
| SpatialSlice[T].request | `SpatialReadRequest`, required | exact echo входа, включая request_id; frame и revision не подменяются |
| SpatialSlice[T].payload | `T`, required, без общего nullable/default | typed domain facts; present/absent/unresolved только по смыслу T |
| SpatialSlice[T].source_refs | `tuple[SpatialSourceRef, ...]`, required, min_length=1 | `SpatialSourceRef = PlanRef | ArtifactRef`; immutable provenance текущего source, не все shards и не universal coverage proof |
| SpatialSlice[T].issues | `tuple[FieldPathError, ...]`, required | `()` для результата без замечаний; nonempty только PREVIEW unresolved/диагностика |
| SpatialReadFailure.request | `SpatialReadRequest`, required | exact echo валидного запроса |
| SpatialReadFailure.errors | `tuple[SpatialReadError, ...]`, required, min_length=1 | все обнаруженные ошибки; immutable sequence, без primary reason |
| SpatialReadError.reason | `SpatialReadFailureReason`, required | типизированная причина конкретной ошибки |
| SpatialReadError.issue | `FieldPathError`, required | existing path/message/context этой ошибки |

Дополнительные validators Slice: все PlanRefs в source_refs принадлежат миру request.revision (`PlanRef.key.world_uid` либо `WorldPublicationRef.world_uid`); refs уникальны по полному value (проверяет shared validator); порядок задаёт domain source contract и сохраняет одинаковым между окнами, generic validator не сортирует чужие refs и не вводит свой codec. В bootstrap exact request PlanRef должен присутствовать в source_refs; runtime нужен как минимум один ArtifactRef(kind=BLOB) корневого принятого source, а не только PlanRef. Дополнительные refs не отменяют эту проверку; принадлежность root pin проверяется admission boundary, как в §14.4. Generic validator проверяет состав/identity refs, но не раскрывает artifact payload или его domain coverage. REQUIRED Slice обязан иметь `issues=()`; unresolved/invalid T не допускается даже при пустых issues (это обязательная domain postcondition, а не generic semantic inspection T). Утверждаемая spatial occupancy/absence ограничена request union; domain metadata и исходные границы пересекающего окно интервала могут выходить за него (принятый SP1-F1, §§14.8–14.9). Source provenance может ссылаться на больший source. Отказ не содержит partial payload; типизированный unknown в PREVIEW не превращается в принятый игровой успех.

**SpatialReadFailureReason (новый StrEnum, закрытый набор):**

| Variant / wire value | Значение |
|---|---|
| FRAME_MISMATCH / frame_mismatch | корректный request имеет несовместимые с source coordinate/topology bounds |
| REVISION_MISMATCH / revision_mismatch | expected pin не совпадает, index stale, mixed dependencies/overlay |
| SOURCE_MISSING / source_missing | обязательного root/shard/source нет; не доказанное отсутствие среды |
| SOURCE_CORRUPT / source_corrupt | checksum/decode/invariants принятого source нарушены |
| UNSUPPORTED_FORMAT / unsupported_format | неподдержанный format/version, без fallback на legacy |
| SOURCE_INCOMPLETE / source_incomplete | домен не может достоверно ответить по всему required scope |
| DOMAIN_REJECTED / domain_rejected | валидный общий запрос недопустим по профильному domain contract |
| RESOURCE_LIMIT / resource_limit | запрос не помещается в принятый domain/caller budget, без молчаливого обрезания |
| SOURCE_UNAVAILABLE / source_unavailable | временно недоступен storage/prepared source, без автоматического solve |

Malformed raw request отклоняется existing Pydantic ValidationError при construction/validate до read; это отдельно от typed отказа уже принятого SpatialReadRequest. HTTP/DAG boundary должен переводить validation в принятый owning boundary error (точные transport/node mapping — будущий SP-R0/owning DAG freeze; draft GEN-DAG не является accepted evidence), не принимает незавалидированный dict. Expected domain/IO failures внутри valid read должны стать SpatialReadFailure; asyncio cancellation/shutdown и programming defects не маскируются SOURCE_INCOMPLETE или success и не превращаются в dry. FieldPathError переиспользуется со своей existing строкой message/code; новые magic error-code strings вместо enum reason не вводятся.

**Owner ошибок:** реализация доменного reader классифицирует failure, владелец причины пишет один агрегированный ERROR для REQUIRED request с request_id/world/frame/revision/errors; shared POJO/Protocol не логируют. Consumer не дублирует этот ERROR по клетке и не запускает fallback/solve/patch. PREVIEW unresolved может иметь issues в payload/Slice по доменному контракту; missing/corrupt/stale всё равно Failure. Будущие retry/backoff/dedupe численные настройки не выдуманы; read остаётся без mutation. Неизвестные значения reason/type — validation error, не generic unknown success.

### 14.4. Revision binding, pin и независимость окон

1. **Bootstrap:** request.revision — exact PlanRef принятого финального domain source, не input fingerprint и не ref зависимости вместо final. Подготовленный index привязан к нему и всем его принятым geometry/dependency refs. Slice source_refs содержит этот PlanRef; остальные необходимые source refs domain owner добавляет детерминированно. PlanEnvelope остаётся во владении planning, весь envelope/working maps не переносятся в результат.
2. **Runtime/pre-game Pack:** request.revision — exact WorldPublicationRef с non-null pack_hash. Snapshot_head может быть None по existing модели; это осмысленный pin base state, не запрос latest. Для gameplay применяются existing gameplay_started/active_timeline/head coherence/ancestry rules. Null pack_hash на Pack read → DOMAIN_REJECTED, не bootstrap fallback. Generic read не добавляет pack_hash/snapshot_head копии, новый counter, SQL head или свою history.
3. Доменная admission operation до чтения связывает root ArtifactRef/format с pinned manifest@pack_hash и принятой source provenance; runtime reader применяет только overlay pinned snapshot_head. Отсутствие root недопустимо толковать как dry/vacuum. ArtifactRef сам по себе не доказывает принадлежность pin: её должна проверять owning Pack/Snapshot admission operation после своего freeze. Existing WorldPublicationRef проверяет лишь coherence полей; существующий legacy Pack path не доказывает такую root/pin binding. Применимость source-aware binding остаётся Q01 OPEN. Exact domain root wire и ancestry/overlay loading signatures — внешний SP-P0/SP-3S freeze, а не новый hidden shared resolver.
4. Read проверяет request pin/frame против своего source/index, не переключается на latest при смене world head. Изменение head во время чтения не меняет запрос: либо retained pinned source даёт согласованный Slice, либо typed Failure. Общая runtime revision geometry/medium/dependencies согласуется через ту же публикацию; mismatch → REVISION_MISMATCH до выдачи facts. Invalidation запрещает reuse stale index для нового pin; запрос старого pin допустим только при доступности всех его retained refs. Eviction не запускает generation/fill.
5. Один принятый source/index обслуживает много windows. Source refs идентифицируют root/source, не выбранные shards, поэтому не меняются из-за разбиения окна на boxes. Payload и issues детерминированы при равных window/revision/mode; request_id только correlation. Семантическое объединение payloads disjoint windows должно равняться payload полного union (canonical ordering/absence semantics задаёт T), без повторного flood/routing или изменения уровня воды. Байт-в-байт equality shared wrapper при другом request_id/разбиении не требуется.
6. **Не выдавать проект за готовый domain payload:** точные WaterFacts/river profile/source membership и интерпретация пустого результата замораживаются GEO/SP-H, geology/gas — их owners. SP-1 точно определяет обёртку и обязанности, не объявляет существующий NativeFinalWaterQuery реализацией этого API. До domain T freeze нельзя реализовать concrete reader на generic dict или MapCell маске.

### 14.5. Единая карта target файлов / owner / imports (предлагается, не создано)

Всё ниже — shared декларации dataModel/spatial, без самостоятельного application Spatial service/dispatcher/index. Новые файлы перечислены для последующего freeze; пока это proposal. `__init__.py` пустые, без eager re-exports (исключает цикл topology → spatial.facing → spatial.read → topology).

| Exact target path от backend/app/ | Declaration / owner / producers → consumers | Разрешённые imports |
|---|---|---|
| dataModel/spatial/query/__init__.py | пустой package marker; shared spatial | нет |
| dataModel/spatial/query/window.py | SpatialBox, SpatialWindow; caller задаёт запрос, domain reader читает | pydantic/typing; spatial.grid.coordinateTypes/coordinateSpace; topology.worldTopology/worldBounds; topology.enums.worldTopologyMode |
| dataModel/spatial/read/__init__.py | пустой package marker; shared spatial | нет |
| dataModel/spatial/read/request.py | SpatialReadRevision alias, SpatialReadMode, SpatialReadRequest; caller → reader | stdlib enum/uuid/typing; pydantic; query.window; planning.identity.planRef; worldSnapshot.identity.publication |
| dataModel/spatial/read/failure.py | SpatialReadFailureReason, SpatialReadError, SpatialReadFailure; reader → caller | enum/typing/pydantic; read.request; validation.diagnostics.fieldPathError |
| dataModel/spatial/read/result.py | SpatialSourceRef, SpatialSlice[T], SpatialReadResult[T]; reader → composition consumer | typing/pydantic; read.request/failure; artifacts.references; planning.identity.planRef; validation.diagnostics.fieldPathError |
| dataModel/spatial/read/reader.py | SpatialFieldReader[T] Protocol; domain implements, application/DAG caller invokes | typing.Protocol; read.request/result |

**Counts:** существующий `dataModel/spatial` 3 → 3 непосредственных файла (новые подпапки не считаются файлами); `query` 0 → 2; `read` 0 → 5 с __init__.py. Не увеличиваются existing `spatial/grid` 6 → 6 и `topology` 6 → 6, planning/identity 4 → 4, worldSnapshot/identity 3 → 3, artifacts 3 → 3, validation/diagnostics 3 → 3. Порог >5 для новой композиции не пересекается, потолок 10 соблюдён; существующие grid/topology >5 требуют WARN, но здесь reuse без правки/добавления файлов.

**Import/caller map и legacy disposition:** domain-owned Hydrology/Geology/Gas application readers импортируют shared reader/request/result declarations, а shared declarations не импортируют implementations, World/MapCell SQL models, registry services, kernels, storage IO или engine nodes. Будущие GEN-DAG/domain.read/L2 callers импортируют типизированный public domain API и нужные shared value types; точные caller file/node contracts — SP-R0/SP-M и owning GEN-DAG, не фиктивные пути в SP-1. Domain reader concrete file paths — freeze SP-3/SP-G/SP-5A после domain T/source review. Shared file paths выше точны; новый конкретный WaterSpatialReader.py здесь не утверждается. Legacy MapCell scene/read, SQL engine, native water_at и footprint/settlement APIs остаются AS-IS по §0.11/0.14; общий Protocol не переименовывает их signatures и не делает второй production read. Existing POJO files не перемещаются, import migrations в SP-1 отсутствуют. Snapshot/Pack refs reused, никакого переноса WorldPublicationRef в spatial.

### 14.6. Проверка проекта и точка согласования

До code-ready отдельно согласовать предложенные решения SP-1: half-open world-fine-only canonical boxes и caller-owned seam split; async single-read union outcome; required/preview semantics; revision union с existing refs, immutable domain T и direct source_refs; точную карту семи shared файлов. Никакое из них не считается принятым только по записи этого раздела.

Предстоящие contract acceptance cases (сейчас спецификация, не новые тесты): reject coercion/empty/inverted/overlapping/unsorted boxes; negative coords и seam-disjoint/sphere frame; union vs disjoint semantic equivalence; bootstrap exact PlanRef и runtime same pin при смене latest; mixed geometry/water revisions, missing root/shard и stale index → enum Failure; malformed ref без обязательного hash/version → construction ValidationError, неподдержанный валидный format/version → UNSUPPORTED_FORMAT; REQUIRED unresolved → Failure без MapCell/L0 fallback; valid empty domain answer ≠ missing source; PREVIEW unresolved ≠ corrupted source; no per-cell SQL/log storm; повторные warm reads не выполняют prepare/fill/patch и не раскрывают весь мир. Numerical IO/memory/time budgets и exact shard representation принимаются SP-P0/SP-H, не угадываются здесь.

**SP-1 остаётся НА ПРИЁМКЕ, не ARCH-ACCEPTED/CODE-READY.** SP-P0/M/R0 не объявляются готовыми до приёмки SP-1; GEO/native production, Snapshot runtime и staged publication не принимаются этим проектом. Следующий шаг — review этого контракта владельцем; production-code permission отсутствует.

### GEO-SPATIAL-CONTRACT — совместное согласование producer/read boundary (2026-11-02)

**Направление согласовано пользователем; exact contract OPEN.** GEO-1/Hydrology остаётся producer исходных water facts. Целевой путь: canonical GEO final → Hydrology-owned immutable Pack root → Hydrology-owned reader по общему Spatial-контракту → L2/gameplay/Physics. SPATIAL не становится solver, вторым producer или центральным orchestrator; runtime overlay требует отдельных Snapshot gates.

**Начало работы:** использовать принятый SP-0, проект SP-1 §14 и GEO Task11; совместный дизайн возможен сейчас. **Приёмка результата:** принятый SP-1 и совместное evidence GEO/SPATIAL по пунктам ниже. Task11 coordinate/source decision входит в этот результат; не требовать G10-A или SP-P0 DONE на входе. Это именованный результат существующего совместного review, не новый implementation step.

| Согласуемая граница | Ответственный / evidence до приёмки |
|---|---|
| Координаты, topology и окно | GEO выбрал A: общая fine P2-сессия; exact source/proof refs Task11 ещё требуют freeze; SPATIAL — совместимость с принятой query/window семантикой SP-1. World-fine query не требует автоматически переводить всех участников P2 на fine grid. Выбор A принят в GEO, совместный проект §9; прежние A/B OPEN исторические. |
| Полнота и семантика воды | Hydrology определяет UID, wet/dry/unknown, уровни/bed/shore и coverage; reader сохраняет эти различия. Ocean/lake scope отдельно от river-volume SP-H2. Ни отсутствие записи, ни L0 mask не заменяют доказательство dry. |
| Revisions и publication | Отдельно exact source PlanRefs/dependencies и runtime WorldPublicationRef; описать привязку source к root/index и запрет mixed revisions. Source-aware binding applicability остаётся Q01, accepted Snapshot не подразумевается. |
| Представление и стоимость | GEO обосновывает source representation/precision и цену подготовки; SPATIAL/Hydrology reader — bounded read без fill/route/full-world scan. Зафиксировать совместимость source с будущим компактным root без нового solve; exact codec/schema/shards и численные budgets замораживает SP-P0/профильный owner. |
| Типы, файлы и миграция | Сослаться на reuse/new POJO/enum и exact paths в owning freeze; сверить legacy producer/read callers, один source на revision и отдельные точки producer cutover, root publication, reader activation. Наличие native class не доказывает production binding. |

**Выход:** один совместно согласованный пакет решений с взаимными ссылками на GEO Task11/source contract и SPATIAL SP-1/storage requirements; owners подтверждают свои части, статус принятия отражается в обоих планах и графе. До этого зависимый GEO producer code/cutover и приёмка зависимого storage freeze SP-P0 заблокированы. SP-P0 может проектироваться параллельно; он не является prerequisite этого согласования. Exact contracts не выбирать при реализации.

**Разблокирует:** GEO G10-A после собственных code gates и SP-P0 acceptance после собственных требований. Pack schema/transport/root/read реализуются далее по SP-P1/P2/P3/SP-3; GEO не ждёт полного SPATIAL DONE, runtime Snapshot, PHYSICS или GEN cutover. Production switch не объединяется с read activation одним неатомарным mega-step.


**Сверка 2026-11-02:** этот совместный раздел фиксирует обязательства и критерии согласования, но не заменяет exact contract. SP-1 §14 содержит точный проект shared API (НА ПРИЁМКЕ); Hydrology exact payload/codec/revision mapping ещё требуют freeze; направления A/R1/G1 и water interval уже приняты (актуализация §14.8). Для приёмки GEO-SPATIAL-CONTRACT нужны взаимные ссылки на конкретные поля/типы, единицы/границы, ошибки, revisions и target/legacy file/caller map; общего перечисления требований недостаточно. Root schema/codec/version/migration принимаются отдельно в SP-P0. Статусы приёмки этим уточнением не закрываются.


## Hydrology → Spatial: проверенные legacy-пути и места перехода (2026-11-02)

**Статус: статический caller audit выполнен; migration/LEGACY-AC OPEN.** Legacy здесь означает заменяемую роль source/read в целевом водном пути, а не все классы Hydrology. Проверены определения и прямые imports/calls в backend/app и backend/tests через rg и чтение ключевых implementations. Dynamic caller closure, runtime replay и отключение production путей не проверялись. Новые concrete reader/root классы и сигнатуры не выдуманы: они OPEN у соответствующих freezes.

| ID / disposition | Точные существующие классы/методы | Подтверждённые callers / evidence | Где переводится / что сохраняется |
|---|---|---|---|
| HSP-01 — legacy producer, GEO owns | [HydrologyFinalPlanProvider.build; GeoHydrologyFinalPlanProvider.build](../../backend/app/application/worldData/generators/hydrology/planning/hydrologyPlanProvider.py); [HydrologyFactsAssembler.assemble](../../backend/app/application/worldData/generators/hydrology/planning/assembly/hydrologyFactsAssembler.py) | [planProviders.py: registration](../../backend/app/application/worldData/planning/composition/planProviders.py) | GEO Task11/G10-A: заменить production source на принятый native final; SP-H проверяет полноту. Assembler выдаёт coarse hydro и sparse fine river roles; это не полный native open-water source. Удаление конкретных классов только после проверки всех callers; shared файл не удалять целиком. |
| HSP-02 — legacy water read source | [HydrologyWorkingFields.from_plan / fine_hydro_for_tile / fine_z_for_tile](../../backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py) | [SurfacePlanningEntry.prepare_captured](../../backend/app/application/worldData/planning/composition/surfacePlanningEntry.py); [TerrainBatchOrchestrator.build_tile_surface_state](../../backend/app/application/worldData/materialize/terrain/terrainBatchOrchestrator.py) | SP-P3I/P3W публикуют root; SP-3 читает его; SP-M/SP-4 заменяют использование working maps как истины water medium в L2. fine_z — geometry dependency, её нельзя удалить вместе с water-read без отдельного source mapping. Полное удаление класса НЕ согласовано. |
| HSP-03 — legacy L0-as-truth | [hydro_mask_from_parent; merge_hydro_hard_corridor](../../backend/app/application/worldData/generators/hydrology/shore/parentLightHydroCorridor.py) | [TerrainBatchOrchestrator.build_tile_surface_state](../../backend/app/application/worldData/materialize/terrain/terrainBatchOrchestrator.py) | SP-M проектирует, SP-4 переключает water consumer. Merge сейчас допускает sparse fine только внутри L0 mask: это несовместимо с canonical fine water verdict. Маска также передаётся paint_regions_fine/place_hills — их policy inputs проверять отдельно, не удалять helper без disposition этих callers. |
| HSP-04 — L2 seam, сохраняемый orchestrator | [prepare_fine_tile](../../backend/app/application/worldData/pack/refine/fine/prep/fineTilePrep.py); [compute_rect (функция, не класс)](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkCompute.py) | [TerrainBatchOrchestrator.generate_chunk_cells_sync](../../backend/app/application/worldData/materialize/terrain/terrainBatchOrchestrator.py); [fineChunkPersist.py](../../backend/app/application/worldData/pack/refine/fine/chunk/fineChunkPersist.py) | SP-M фиксирует typed projection/input и exact decomposition responsibilities/methods/files/imports TerrainBatchOrchestrator.build_tile_surface_state по требованию GEO. SP-4 реализует согласованное разделение multi-operation body до активации bounded base reader после grade geometry. Сохранение класса не означает сохранения доменных алгоритмов в orchestrator. Существующий persist остаётся writer. SP-3S/SP-4R отдельно добавляют accepted runtime overlay; base cutover не доказывает runtime. |
| HSP-05 — native, НЕ legacy Spatial | [NativeFinalWaterQuery.__init__ / water_at](../../backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py) | Поиск backend/app: только определение; backend/tests/geo1/water_query и typing используют класс. | Сохранить как native XY observation/evidence, reuse admission semantics рассмотреть в SP-3. Это KnownFact[UID | None] / UnknownFact, не XYZ volume API и не Pack/Snapshot reader. Не переименовывать в готовый Spatial reader и не объявлять production migration завершённой. |
| HSP-06 — native producer, сохраняется ownership | [NativeFinalPublicationJob.publish](../../backend/app/application/worldData/generators/hydrology/planning/assembly/final/publication.py); [FineWaterPublicationJob](../../backend/app/application/worldData/generators/hydrology/water/planning/fine/publication.py) | [NativeFinalWaterQuery](../../backend/app/application/worldData/generators/hydrology/query/nativeFinalWaterQuery.py) | GEO G10-A — production join; SP-H — source proof. SP-P3I строит compact root из accepted source, SP-3 не вызывает fill/routes/publication. Exact source representation и signatures всё ещё требуют joint freeze. |
| HSP-07 — соседние consumers, запрет слепого удаления | [HydrologyWorkingFields](../../backend/app/application/worldData/generators/hydrology/materialize/hydrologyWorkingFields.py) | [ClimatePackBakeOrchestrator: fine_z_for_tile](../../backend/app/application/worldData/pack/climate/climatePackBakeOrchestrator.py); [SupportSources.__init__](../../backend/app/application/worldData/generators/terrain/relief/surfaceCoating/sources.py); [LandcoverObservations / prepare_landcover_inputs](../../backend/app/application/worldData/regions/inputs/landcoverInputs.py); [contribute](../../backend/app/application/worldData/regions/factConsumers/hydrology.py) | Остаются AS-IS до individual mapping в GEO-SPATIAL-CONTRACT/SP-M и профильных owners. Не обещать автоматический перевод всех на SP-3: coarse observation/geometry и water volume имеют разные contracts. Полностью сухая известная поверхность сейчас даёт None при not hydro; dry/unknown acceptance case обязателен. |
| HSP-08 — L0 projection сохраняется, не SoT | [world_map_hydro_role_from_cell](../../backend/app/application/worldData/pack/bake/l0/worldMapHydrology.py) | [coarseOpenWater.py](../../backend/app/application/worldData/pack/bake/lightGrid/contributors/hydro/coarseOpenWater.py); [worldMapBakeOrchestrator.py](../../backend/app/application/worldData/pack/bake/l0/worldMapBakeOrchestrator.py) | GEO G10-A согласует source cutover L0 callers; SP-H сверяет L0 projection с canonical facts. HydrologyMaskWire/role/width не удаляются только из-за Spatial, но SP-3/SP-4 не используют их как доказательство fine wet/dry. |
| HSP-09 — кандидат cleanup, не доказанный live route | [merge_fine_hydro_for_tile; apply_declared_fine_river_carves](../../backend/app/application/worldData/generators/hydrology/shore/fineHydrologyIndex.py) | Поиск backend/**/*.py: merge — только определение; apply_declared — определение и tests, production caller не найден. | GEO legacy cleanup после caller/import closure; не добавлять эти функции в Spatial reader. Отсутствие прямых вызовов не доказывает отсутствие dynamic consumers. River-volume остаётся отдельным SP-H2. |
| HSP-10 — bootstrap algorithms не legacy из-за Spatial | [resolve_water_levels](../../backend/app/application/worldData/generators/hydrology/water/waterBodyResolver.py); [materialize_water](../../backend/app/application/worldData/generators/hydrology/water/waterMaterialize.py) | [waterBodyAssembler.py](../../backend/app/application/worldData/generators/hydrology/waterBodyAssembler.py) | Физическое bootstrap разрешение остаётся Hydrology; конкретный reuse/retirement решает GEO producer cutover, не общий read API. Runtime flow/dry effects принадлежат Physics; запрещено запускать bootstrap solve из read_window. |

**Порядок миграции:** SP-1 + GEO-SPATIAL-CONTRACT принимают точную source/read compatibility и caller dispositions → GEO G10-A переключает producer, SP-H принимает source proof; независимо SP-P0/P1 готовят формат → SP-P3I/P3W/P3 с transport/publication gates → SP-3 base reader → SP-M + SP-4 L2 water consumer. Runtime отдельно SP-3S/SP-4R, реальные gameplay callers — SP-R0/R1/R2. Не добавлены новые gates; все внешние prerequisites общего графа сохраняются.

**До кода каждого перехода:** для затронутых HSP-ID дополнить exact replacement symbol/path, typed input/output/errors/revision, caller imports, remove/retain rationale и negative cases. Пока соответствующий target OPEN, шаг не CODE-READY. При SP-4 подтвердить cold-Pack water read без working-map water source, L0-as-truth, fill/routes; при удалении HydrologyWorkingFields проверить Climate/Landcover/coating и geometry callers. Tests, закрепляющие hard corridor (test_parent_light_refine.py, planning/consumers/test_l0_l2.py), требуют осмысленной замены water assertions, а не механического удаления. River и non-water consumers не включать молча в ocean/lake cutover. Общая приёмка legacy требует отсутствия второго активного water source на одной revision.


**SP-M/SP-4 — обязательное уточнение приёмки (2026-11-02):** требование GEO о разделении multi-operation body TerrainBatchOrchestrator входит в SP-M freeze и SP-4 implementation/acceptance (HSP-04), не новый gate. До reader activation проверить exact responsibility/import map и отсутствие доменных алгоритмов в orchestration seam. G10-A принимает source join и contract-level совместимость с L2; SP-4 принимает реальный L2 cutover/cold-Pack evidence и не является prerequisite G10-A. Domain geometry/landcover/hills operations не становятся алгоритмами generic Spatial.


### 14.7. Архитектурное ревью SP-1 после принятого SP-0 (2026-11-02)

**Вердикт: уточнённый shared проект предъявлен на приёмку; freeze не принят.** SP-0 §0.15 остаётся DONE; повторный аудит SP-0 не выполнялся. Проверены declarations и imports existing refs, coordinate types, WorldTopology/WorldBounds/fine_topology, FieldPathError/RuntimeIssueContext и NativeFinalWaterQuery, GEO Task11/GEO-SPATIAL-CONTRACT и Hydrology fine publication/query requirements. Это статическое архитектурное evidence, без запуска runtime или новых тестов.

Подтверждённые противоречия исправлены: внешний strict ConfigDict больше не объявлен гарантией strict nested topology; зафиксированы готовый frame и точные дополнительные проверки без изменения legacy POJO. Добавлена существующая fine_topology formula вместо неявного coarse→fine relabel. Проверка root/pin больше не названа готовой existing Pack/Snapshot операцией: её контракт и Q01 applicability ещё OPEN. Imports window дополнены фактически нужными WorldBounds/WorldTopologyMode; карта остаётся семью новыми shared файлами, без application service или переноса existing POJO. Проверка уникальности source_refs — по equality полного value, без требования hashability refs; PlanKey.scope может содержать region UID, refs не заменяются одним fingerprint.

Request/result/error проверены совместно: validation до read отличается от Failure валидного request; source отсутствует/повреждён/stale — Failure и в PREVIEW; допустимый пустой T определяется доменом. REQUIRED допускает только полный достоверный T и пустые issues. FieldPathError — frozen dataclass с optional code/reference/runtime_context, а не новый BaseModel или обязательный runtime context: shared wrapper сохраняет existing тип. Не вводится generic wet/dry status. Актуализация по принятому F3 (§14.10): Failure.errors сохраняет все фактически обнаруженные SpatialReadError, без primary reason/precedence. Прежнее предложение выбирать первую причину отозвано. Непроведённые зависимые проверки не порождают ошибки; порядок traversal задаёт домен. Cancellation и defects не маскируются.

**Граница приёмки:** владелец принимает shared окно/request/outcome/revision obligations и карту §14.1–14.6. Это не закрывает GEO-SPATIAL-CONTRACT: На момент этого ревью GEO ещё должен был определить domain T, fine physical source/coverage, Z units/bed/level boundaries, Task11 mapping и exact dependency proofs; актуальные принятые A/R1/G1 и Z convention учтены в §14.8. Сохраняется различие PlanRef.output_fingerprint (32 bytes) и publication pack_hash (RevisionHex, 64 hex chars). NativeFinalWaterQuery проверяет exact final/water refs и output proofs при admission и возвращает XY KnownFact/UnknownFact; он не предоставляет XYZ volume, root IO или runtime overlay. Нельзя вывести dry из отсутствующего root, coarse membership либо пустой sparse map. Ocean/lake scope и river SP-H2 не объединяются этим ревью. Новые доменные payload/codec/reader paths не выбраны.

В acceptance cases §14.6 добавляются: raw dict topology rejected; bool/string bounds в готовом frame rejected; нечётный готовый SPHERE frame rejected без расширения; coarse frame при fine space даёт FRAME_MISMATCH; retained pin не заменяется latest; equality refs работает и для region scope. Shared решение можно принять отдельно; совместный GEO результат, SP-P0 acceptance и любые реализации остаются за собственными gates. Код и downstream steps не начаты.


### 14.8. Финальное архитектурное ревью — A/R1/G1 и water interval (2026-11-02)

**SP-1 предъявлен пользователю НА ПРИЁМКУ; автоматической приёмки/freeze нет.** Настоящий раздел актуализирует §14.7 и устаревшие OPEN по выбранным направлениям, но не повторяет SP-0. Основание — [GEO: совместный проект и принятые решения §§7–10](./geo-1-designed-water.md#10-exact-geometry-g1-и-вертикальная-граница--решения-пользователя-2026-11-02). A = единая fine P2 competition, R1 = exact resolved membership row runs, G1 = retained exact final bed; full-fine однократная preparation допустима. Ни R1, ни G1 не обещают дешёвую preparation или компактность в worst case. Эти решения приняты; exact Hydrology T, source graph, versions и storage freeze этим не закрыты.

**Проверенное code evidence / реальные callers.** `dataModel/topology/{worldBounds,worldTopology,fineTopology}.py`: inclusive bounds, coercion/extra=ignore у bounds, SPHERE even_width normalization, lift `[min*S,(max+1)*S-1]`. Callers fine_topology есть в hydrologyFactsAssembler.assemble_fine, reliefPlanProvider и boundary preparation; helper не определяет, является ли переданный frame уже fine. Shared admission §14.2 и сравнение с source обязательны; один и тот же scale не применяется дважды. Existing coordinate NewType — int в runtime, самостоятельного runtime unit proof не даёт. WorldPublicationRef.coherent_refs проверяет поля/world, ancestry принадлежит ports; ArtifactRef не содержит world/pin, format registry membership и root binding не доказываются самим POJO. PlanRef — полный key + 32-byte output proof, не pack hash. FieldPathError остаётся frozen dataclass, code optional, не closed error enum.

`NativeFinalWaterQuery.__init__/water_at` проверяет final/water/dependency fingerprints на admission и читает XY coverage/sparse rows; статический поиск app находит определение, tests/geo1/water_query — callers. RIVER_BED даёт identity observation, не доказательство liquid volume. `HydrologyFactsAssembler.publish_fine` реально вызывает NativeFinalPublicationJob.publish; production planProviders по-прежнему регистрирует HydrologyFinalPlanProvider. Наличие wrapper/test fixture не доказывает G10-A join. `FineWaterPublicationJob.publish` проверяет exact surface ref, batch snapshot и accepted footprint equality: A согласуется с этим принципом, но не закрывает migration всех P2 callers/versions. Реальный `TerrainBatchOrchestrator.build_tile_surface_state` использует clamp fine_z по z_band и L0 hard corridor; не объявлен G1 consumer. Его migration принадлежит SP-M/SP-4, не shared API.

**Вертикальная совместимость.** Принятый Hydrology interval `bed < z <= level` эквивалентен `[bed+1,level+1)` и совместим с half-open SpatialBox. Для box вертикальная часть occupancy: `[max(z0,bed+1), min(z1,level+1))`; пуста при lower >= upper, но только resolved membership и доказанный scope дают known absence. Это следствие принятой convention, не generic water solver. При bed=3, level=5 клетки воды — 4,5; `[3,4)` воды не содержит, `[5,6)` содержит 5, `[6,7)` воды не содержит в известном scope. Shore, reserved placement footprint и river bed жидкость не доказывают.

Existing `FineTerrainZRun.cells` разворачивает inclusive `[z0,z1]`, `_compress_z_runs` сохраняет крайние реальные MapCell.z, `_surface_cell` выбирает max z. `generators/terrain/passes/columnFillPass.py:run_column_fill` строит solid до z_top включительно и stamp hydrology только на z_top; RIVER_BED может назначить liquid_body на этом слое. Это legacy surface projection, не реализация `(bed,level]`. Disposition: сохранить terrain wire inclusive и его callers; не менять codec или сдвигать все terrain runs ради shared window. При будущей water projection SP-M/SP-4 отдельно согласовать bed geometry, vertical scope и исключение ложной жидкости на bed; river-volume остаётся SP-H2. G1 final bed нельзя подменить clamped L2 top.

**Уточнения проекта: F1/F2/F3 приняты пользователем в scope §§14.9–14.10; общий SP-1 ещё на приёмке:**

- **SP1-F1 — extent payload, вариант 1 принят пользователем (2026-11-02).** Ограничить окном *утверждаемую occupancy/absence*, разрешив domain-owned body metadata и исходные bed/level пересекающей окно колонки за его пределами. Consumer интерпретирует объём только в intersection request union; shared T не переписывается и heights не clamp-ятся. Это устраняет коллизию прежнего полного запрета facts вне окна с GEO WaterColumnFact/WaterWindowFacts. Точные поля/clipping/normalization T утверждает GEO. Semantic union equality относится к occupancy и согласованным domain facts, а не конкатенации body tables/дублированных колонок.
- **SP1-F2 — строгость in-process discriminants, вариант 1 принят пользователем (§14.10).** Before-validation: `space` — actual CoordinateSpace member WORLD_FINE_GRID; `mode` — actual SpatialReadMode; `revision` — actual PlanRef либо WorldPublicationRef; source_refs — actual PlanRef/ArtifactRef, с последующей existing revalidation. Literal[StrEnum] и BaseModel strict сами по себе не являются запретом равной строки/dict для всех вложенных типов. Raw wire decoding остаётся caller boundary. Новые shared модели не принимают model_construct/model_copy как обход проверки; topology до nested validation проверяется на existing bounds instance, actual mode, strict int, ordered bounds и SPHERE even width. Ранее нормализованный legacy raw input восстановить нельзя. Это принятое ограничение in-process API; transport decoding не переносится в reader.
- **SP1-F3 — несколько ошибок, решение пользователя (§14.10).** Возвращаются все обнаруженные ошибки в `SpatialReadFailure.errors`, каждая с собственным typed reason и FieldPathError. Единственного primary reason нет. Предложения о выборе одной причины и общем precedence в §§14.7–14.8 заменены этим решением. Дополнительные проверки после невозможности продолжить не требуются; неизвестные причины не выдумываются. Cancellation/defects не маскируются.

**Карта shared файлов повторно сверена.** Семь target файлов §14.5 ещё отсутствуют; counts существующих каталогов подтверждены (3/6/6/4/3/3/3). Новых imports/callers сейчас нет. result.py импортирует `ArtifactKind` вместе с `ArtifactRef` из artifacts.references для BLOB check; request.py использует existing refs, window.py — existing topology types. Shared не импортирует Hydrology, Pack codecs, application orchestration или Snapshot loaders. Нужда runtime в BLOB root — предлагаемый контракт §14.3, не свойство всех ArtifactRef (existing SQL_ROWS тоже валиден). Root schema/hash verification/shard index — SP-P0/Pack; actual pinned overlay/history/invalidation — SP-3S/4R/Snapshot/Q01; exact public domain reader imports — SP-3/SP-M/SP-R0. Draft GEN-DAG не использован ни как принятая signature, ни как proof готового error transport или caller activation.

**Предмет приёмки:** §14.1–14.6 с уточнениями SP1-F1/F2/F3 выше: world-fine canonical disjoint half-open windows, строгий request, async single read с Slice/Failure, REQUIRED/PREVIEW, existing revision/provenance refs, семь shared файлов и направленные imports. F1/F2/F3 приняты в scope §§14.9–14.10; общий freeze SP-1 ещё требует явной приёмки пользователя. Она не означает приёмку Hydrology payload/source freeze, GEO-SPATIAL-CONTRACT целиком, Pack codec/budgets/publication, runtime overlay, production activation или transport/node контрактов. Глобальный LEGACY-AC OPEN. Проверка статическая; backend/runtime/tests не запускались, код/downstream steps не начаты; SP-0 DONE не пересматривался.


### 14.9. F1 — решение пользователя и локальный интервал вокруг игрока (2026-11-02)

Пользователь: «F1. Первый вариант нужен. Второй вариант может быть нужен для возвращения интервала вокруг игрока». **F1, вариант 1 принят:** shared результат допускает domain-owned metadata и настоящие границы пересекающего окно интервала; ответ о присутствии/отсутствии действует только внутри request union. Исходные bed/level сохраняются, ограничение окна не становится новым физическим дном или уровнем.

**Потребность в clipped interval вокруг игрока отмечена как возможная, без выбора exact API.** Она совместима с вариантом 1: из исходного интервала и окна можно получить локальное пересечение. Например, bed=3, level=10 и окно `[7,9)` дают локальные клетки 7 и 8, сохраняя исходные bed=3/level=10. При disjoint union пересечение может состоять из нескольких интервалов; нельзя заполнять промежутки между boxes. Это математическое следствие clipping, не новый water solve.

Где возвращать такое представление — в domain payload, отдельной consumer projection или response — и нужны ли дополнительные поля, решают owning GEO/SP-M/SP-R0 freezes при подтверждённом caller. Shared API не получает автоматически второй метод, mode или новый POJO. Поля обрезанного интервала не называются физическими bed/level; clipping не доказывает membership/coverage, не превращает unknown в dry и не меняет revision/provenance. Отдельная реализация или downstream-проектирование этим решением не начаты.

На момент записи §14.9 F2/F3 оставались на согласовании; последующее решение — §14.10. Это частичная приёмка F1, не принятие всего SP-1, Hydrology payload, Pack codec или runtime overlay.


### 14.10. F2/F3 — решения пользователя (2026-11-02)

**F2 принят, вариант 1.** Пользователь: «Вариант 1. В этом весь смысл». In-process request принимает типизированные значения по SP1-F2, с явными before-checks и повторной валидацией existing refs; decoding raw wire остаётся на owning caller boundary. Строгость вложенных legacy models не предполагается автоматически.

**F3 принят с изменением предложенного API.** Пользователь: «Возвращаем все ошибки массивом, если словили несколько ошибок». `SpatialReadFailure.errors: tuple[SpatialReadError, ...]` обязателен и непуст; tuple — immutable in-process представление массива. Новый frozen/strict `SpatialReadError` содержит required `reason: SpatialReadFailureReason` и `issue: FieldPathError`. Единственная ошибка возвращается массивом из одного элемента. Несколько ошибок одного класса с разными paths сохраняются отдельными элементами. Полей failure.reason/failure.issues и выделенного primary reason больше нет; типизированный reason связан со своей диагностикой внутри каждого элемента, а не параллельными массивами.

Возвращаются все ошибки, фактически обнаруженные при выполнении допустимых проверок. Решение не требует дополнительного полного scan, unsafe decode неподдержанного формата или продолжения зависимых проверок без необходимых данных. Нельзя отбросить уже обнаруженные ошибки ради одной «главной»; нельзя придумывать ошибки непроведённых проверок. Domain contract задаёт стабильный порядок для одинаковых исходных условий; порядок массива не означает severity/precedence. REQUIRED failure логируется одним агрегированным ERROR с массивом, без per-cell повторов и partial payload. PREVIEW не превращает missing/corrupt/stale в success. Cancellation/shutdown и programming defects сохраняют прежнее отдельное поведение.

`SpatialReadError` находится в предложенном `dataModel/spatial/read/failure.py`, imports enum/pydantic/FieldPathError уже предусмотрены; карта остаётся семью shared файлами. Acceptance cases: одна ошибка; несколько различных reasons; несколько paths одного reason; все обнаруженные ошибки сохранены; зависимые непроверенные факты не объявляются дополнительными ошибками. Malformed request до read остаётся Pydantic ValidationError, не SpatialReadFailure без валидного request.

Это приёмка уточнений F2/F3 вместе с ранее принятым F1. **SP-1 целиком остаётся НА ПРИЁМКЕ пользователя**; код, downstream steps, Hydrology payload, Pack codec и runtime overlay этим не разрешены.

### 14.11. Совместное ревью с GEO EF-1 — пакет на приёмку (2026-11-02)

Сверены фактические EF-1 и §14.1–14.10; evidence definitions/callers и **единый
перечень контрактов/оставшихся blockers** находятся в [GEO EF-1.10–1.11](./geo-1-designed-water.md#ef-110-совместное-ревью-актуальных-geo-ef-1--spatial-sp-1-2026-11-02).
Это один joint ledger, не вторая копия Hydrology fields. GEN-DAG draft не использован;
код и приёмки не выполнялись. Принятые F1/F2/F3 сохранены, SP-1 целиком, EF-1 и
GEO-SPATIAL-CONTRACT остаются НА ПРИЁМКЕ, не DONE.

- **F1:** GEO WaterVolumeRun теперь разделяет исходные bed_z/level_z и clipped
  z0/z1. Occupancy только внутри request union; исходные физические границы и
  body/union metadata могут выходить за окно. При разном physical bed соседние
  columns не сливаются из-за случайного равенства clipped z0/z1. На общем уровне
  второй API/mode не добавлен. Это domain proposal по принятому F1, не его реализация.
- **F2:** actual typed request/ref/discriminants и before-check готового topology,
  strict integer/enum validation сведены с domain admission. NewType не даёт
  runtime unit proof; legacy normalization/coercion не исправляются outer ConfigDict.
  Revalidation после model_construct/model_copy обязательна. Raw transport decode
  остаётся caller boundary; совместимость нельзя вывести из названия fine поля.
- **F3:** GEO EF-1.5 использует Failure.errors с SpatialReadError(reason,issue),
  без reason/issues на Failure и без first-failed precedence. Все обнаруженные
  ошибки сохраняются; missing shard не порождает выдуманный bad checksum. Полный
  scan/unsafe decode ради новых ошибок не требуется. Slice.issues остаётся только
  диагностикой успешного preview, не альтернативным контейнером Failure errors.
- **Refs:** bootstrap revision — exact canonical-open-water envelope.ref,
  native_final.ref остаётся upstream dependency. Pack reader — WorldPublicationRef
  с pinned root ArtifactRef; сам ArtifactRef не доказывает world/pin. Domain source
  graph freeze не закрывает SP-P0 root wire, SP-3 IO или Snapshot overlay/Q01.
- **Gates:** producer G10-A/SP-H и storage SP-P0/P1 после joint agreement идут
  независимо по собственным gates. Ветки сходятся на source integration SP-P3I;
  legacy closure/consumer activation остаются следующими scopes. ARCH-9 trace
  исправлен вместе с GEO EF-1.8, чтобы не сохранять скрытый G10-A→SP-P0 prerequisite.
- **Files:** SpatialReadError остаётся failure.py, семь shared файлов; domain window
  records/imports принадлежат Hydrology. Canonical source serialization не означает
  регистрацию/persistence каждого WaterWindowFacts/SpatialSlice как Pack source.

Повторно прочитанные existing consumers: NativeFinalWaterQuery, run_column_fill,
_compress_z_runs/_surface_cell и terrainContributions — XY identity/solid inclusive
terrain projection, не готовый canonical liquid XYZ read. SP-M/SP-4 должны сохранить
physical bed, terrain surface и отдельное medium composition. PREVIEW unknown/dry
и required failures не выводятся из отсутствия MapCell/L0 записи. Численные budgets,
runtime/cold-Pack evidence и dynamic caller closure не доказаны этим статическим
review; их gates перечислены в joint ledger.

### 14.12. Итоговый review verdict пакета (2026-11-02)

Актуальные exact definitions и закрытие findings перепроверены точечно, без нового
полного SP-0 аудита. **SP-1 готов к пользовательской приёмке shared архитектурного
scope; блокирующих findings не осталось.** F1 physical bed/level отделены от
clipped occupancy в GEO; F2 typed/before validation не подменена outer strict;
F3 Failure.errors сохраняет все обнаруженные ошибки без primary reason и без
ошибок пропущенных dependent checks. Files/import directions и stable source refs
согласованы с доменным T. Это verdict review, не приёмка SP-1.

Три отдельных вердикта, downstream ограничения и уточнение source admission —
[GEO EF-1.12](./geo-1-designed-water.md#ef-112-итоговое-архитектурное-ревью--три-отдельных-вердикта-2026-11-02).
GEO EF-1 и GEO-SPATIAL-CONTRACT предъявлены отдельно; не считаются принятыми
по готовности shared SP-1. После joint agreement producer G10-A/SP-H и storage
SP-P0/P1 идут независимо по своим gates, сходятся на SP-P3I. Production caller
closure, root format/budgets, Pack IO/pin, L2 activation и runtime overlay остаются
downstream scopes. GEN-DAG draft и текущая Snapshot 4C3-B реализация не использованы
как accepted dependencies; reuse revision value types не принимает Snapshot ports.
Код не менялся, runtime/tests не запускались; все три результата **НА ПРИЁМКЕ**.

### 14.13. Окончательный пакет приёмки SP-1 / EF-1 / совместной границы (2026-11-02)

Три точных предмета приёмки, обязательные решения пользователя, blockers и
разблокируемые/downstream scopes собраны в [GEO EF-1.13](./geo-1-designed-water.md#ef-113-окончательный-пакет-трёх-отдельных-приёмок-2026-11-02).
После последнего verdict §14.12/EF-1.12 изменений этих owning-планов до подготовки
пакета не обнаружено (сравнение `0c0ce092..11891e1c` и working tree); полный аудит
не повторялся. F3 errors tuple без primary/выдуманных dependent errors и отсутствие
G10-A prerequisite для SP-P0/P1 повторно подтверждены.

**SP-1 готов к отдельной приёмке:** предмет §§14.1–14.6 с принятыми уточнениями
F1/F2/F3 §§14.9–14.10 и совместной сверкой §§14.11–14.12; блокирующих findings нет.
Решение пользователя — принять общий exact shared freeze, не повторно выбирать F1–F3.
Приёмка снимает shared prerequisite профильных freezes (SP-M; SP-P0 вместе с
совместным agreement), но не принимает domain/source, root/codec/budgets, reader
implementation, producer/runtime/consumer activation. EF-1 и GEO-SPATIAL-CONTRACT
предъявлены отдельно, их приёмки не следуют автоматически из SP-1.

После совместного agreement producer и storage идут по собственным gates;
ветки сходятся на SP-P3I, не до SP-P0/P1. GEN-DAG draft и непринятый Snapshot B
не использованы как accepted dependencies. Код не менялся. **Все три результата
готовы к приёмке, но остаются НА ПРИЁМКЕ до явного решения пользователя.**

### 14.14. Явная приёмка пользователя — три документальных результата (2026-11-02)

Пользователь прямо сообщил: «Принимаю документальные архитектурные результаты:
1. Spatial SP-1 в scope итогового verdict §14.12. 2. GEO EF-1 в scope EF-1.12.
3. GEO-SPATIAL-CONTRACT — совместимость domain/shared contracts и независимость
producer/storage веток».

- **SP-1 — ПРИНЯТ документальный архитектурный результат**, exact scope §14.12.
- **GEO EF-1 — ПРИНЯТ документальный архитектурный результат**, exact scope GEO EF-1.12.
- **GEO-SPATIAL-CONTRACT — ПРИНЯТ**, совместимость domain/shared contracts и
  независимость producer/storage веток. Это отдельная явная совместная приёмка.

Запись заменяет исторические НА ПРИЁМКЕ/OPEN по этим трём документальным результатам,
включая §§14.12–14.13. Приёмка **не включает реализацию, G10-A cutover, Pack
storage/publication, runtime overlay, L2/gameplay activation или downstream evidence**.
Остальные шаги плана не объявляются DONE. SP-P0/P1 идут по собственным gates,
без G10-A prerequisite; accepted source нужен на SP-P3I. Ссылки на revision value
types не принимают непринятый Snapshot B; GEN-DAG draft не использован.

Зеркальная приёмка — [GEO EF-1.14](./geo-1-designed-water.md#ef-114-явная-приёмка-трёх-документальных-результатов-2026-11-02).
Следующий GEO step [GEO-I1](./geo-1-designed-water.md#geo-i1--следующий-ограниченный-implementation-step-canonical-source-records)
подготовлен **только на согласование до кода**: domain source records R1/G1/Z и
их validators/tests, без producer/shared read/Pack/activation. Он не является
реализацией SP-1, новым gate Spatial или автоматическим разрешением реализации.


## 15. SP-P0 — storage freeze proposal V1 (2026-11-02)

**Статус: документальный SP-P0 подготовлен / НА СОГЛАСОВАНИЕ, не CODE-READY.** Проверена явная приёмка SP-1/GEO EF-1/GEO-SPATIAL-CONTRACT в §14.14 и GEO EF-1.14. G10-A не prerequisite этого проектирования. Ниже конкретное предложение для начального open-water scope, включая предлагаемые численные ограничения; они не измеренные характеристики и не уже принятое решение пользователя. Изменена только документация. GEN-DAG draft и непринятые Snapshot adapters не использованы как принятые ports.

### 15.1. Проверенные existing contracts / callers

- [WorldPackManifest](../../backend/app/dataModel/worldPack/meta/worldPackManifest.py): pack_version=1.0.0, extra=ignore, mutable lists; domain roots отсутствуют. Frozen outer field не делает этот manifest immutable.
- [PackManifestStore.load/save](../../backend/app/application/worldData/pack/io/packManifestStore.py): JSON + model_validate, save через temp/os.replace. Это file replacement, не accepted staged manifest CAS.
- [WorldPackReader.load_manifest/manifest](../../backend/app/application/worldData/pack/io/worldPackReader.py): path/stamp cache; не pinned read по WorldPublicationRef. [WorldPackWriter](../../backend/app/application/worldData/pack/io/worldPackWriter.py) меняет текущий manifest; не становится новым publisher через добавление поля.
- [ArtifactRef/ArtifactKind/ArtifactFormatMetadata](../../backend/app/dataModel/artifacts/references.py): reuse BLOB ref с format_key/version/hash/nbytes и row_count=None, без storage path.
- [ArtifactFormatContract](../../backend/app/application/artifacts/contracts/formatBackend.py): **BLOB content_model обязан быть bytes**. Нельзя зарегистрировать HydrologyRoot как BLOB BaseModel. [ArtifactFormatRegistryBinding.register/encode/decode](../../backend/app/application/artifacts/registry/artifactRegistry.py) проверяет exact model и backend contract identity.
- [ContentAddressedBlobBackend.write/verify/delete](../../backend/app/storage/artifacts/blobBackend.py): bytes/hash/path/claim lifecycle; публичного read нет. SP-P2R должен отдельно предъявить verified bounded byte-read; не использовать private _path и не объявлять verify методом чтения.
- [CanonicalCodec](../../backend/app/application/encoding/canonicalCodec.py) и [SurfaceEnvelopeCodec](../../backend/app/application/worldData/planning/encoding/surfaceEnvelopeCodec.py): reuse deterministic TLV и strict decode/re-encode admission. [SURFACE_MANIFEST](../../backend/app/application/worldData/planning/encoding/surfaceManifest.py) содержит IDs до 297 в проверенной редакции; его future GEO изменения не включаются автоматически в storage schema.
- [FineSurfaceWindow](../../backend/app/dataModel/terrain/sampling/fineSurfaceWindow.py) проверяет exact row-major coverage/surface и protected subset. [RegionCoverage/CoverageSpan](../../backend/app/dataModel/terrain/regions/coverageGeometry.py), WaterBody/PhysicalWaterUnion/SourceBodyMapping и MapCellHydrology reuse по EF-1, без новых копий их полей.

### 15.2. Manifest boundary и version migration

Предлагаемый World Pack wire version **2.0.0**. Существующий SCHEMA_ID SCH-WORLD-PACK-MANIFEST сохраняется; это version change wire, не второй manifest. Добавить required `spatial_roots: tuple[SpatialDomainRootRef, ...]` для V2. Новый record: `domain: SpatialDatasetKind`, `root: ArtifactRef`, оба required. Новый StrEnum SpatialDatasetKind: только `HYDROLOGY_OPEN_WATER = hydrology_open_water` в V1; другие domain datasets добавляются отдельным согласованным version change. Rows sorted по domain.value, unique domain; root.kind=BLOB, root format/key/version проверяются owning domain boundary. Manifest не получает bounds, shards, coverage, source PlanRefs или generic index.

V1 decode разрешает отсутствие spatial_roots и преобразует его в пустой tuple только как explicit legacy decoding policy; это **не доказательство dry**. V2 missing/null spatial_roots — invalid manifest. До cutover existing V1 writer не переключается одним изменением PACK_WIRE_VERSION default: сохраняет V1 либо явно отказывает попытке записать V2 через legacy save. V2 encode/publish — лишь принятый SP-P2W/P3W путь. Старый читатель extra=ignore может потерять roots, поэтому reader/writer version admission обязателен до активации; неизвестная major version — refusal. Все existing save/load callers проверяются в SP-P1/P2 до кода; массовая смена формата старых Pack без source не выполняется.

Отсутствующий hydrology entry — SOURCE_MISSING для required water read, включая PREVIEW failure; legacy L0/MapCell fallback запрещён. Empty domain публикуется **явным root** с достоверным observation и G1 dry geometry. Empty coverage означает unknown вне неё, не весь мир dry. Отсутствующий shard, указанный root, — corruption/missing, не dry. Manifest entry единственный на dataset и publication; root immutable.

### 15.3. Exact Hydrology root и shard records (предлагается)

Все новые records BaseModel frozen/strict/extra=forbid/revalidate_instances=always; required поля без defaults, tuple collections. Strict int excludes bool; nested existing refs/geometry/body records проходят explicit EF-1/SP-1 checks, outer config не исправляет их coercion. Root и shards — storage representation, не SpatialSlice/WaterWindowFacts persistence.

| Record | Exact required fields |
|---|---|
| HydrologyPackRoot | source_ref: PlanRef; dependencies: tuple[PlanDependency,...]; diagnostics: tuple[PlanDiagnostic,...]; topology: WorldTopology; coverage_region_uid: EntityUid; z_min: FineZ; z_max: FineZ; bodies: tuple[WaterBody,...]; unions: tuple[PhysicalWaterUnion,...]; source_mapping: SourceBodyMapping; shards: tuple[HydrologyShardRef,...] |
| HydrologyShardRef | tx: StrictInt; ty: StrictInt; artifact: ArtifactRef |
| HydrologyPackShard | source_ref: PlanRef; tx: StrictInt; ty: StrictInt; bed: FineSurfaceWindow; wet_runs: tuple[WaterMembershipRun,...]; shore_rows: tuple[tuple[FineXY,MapCellHydrology],...] |

`source_ref` — exact canonical-open-water envelope.ref, dependencies — его семь exact slots EF-1, diagnostics — его diagnostics, не refs выбранных shards. Root world извлекается из source_ref.key.world_uid, без второго world_uid. Root topology WORLD_FINE frame; root z bounds — exact source. Bodies/unions/mapping — полные source tables, canonical ordering и graph consistency EF-1; не только visible-window metadata. Этот bounded V1 ограничивает размер metadata root, превышение не обрезается.

**Partition V1:** фиксированные XY tiles 64×64 fine cells, origin=(0,0); tx=floor(x/64), ty=floor(y/64), включая отрицательные координаты. Tile box [64tx,64(tx+1))×[64ty,64(ty+1)); topology bounds могут обрезать tile. Seam caller split остаётся SP-1; shards не wrap-ятся. Root shards sorted (ty,tx), unique; запись только для непустого observed coverage tile, максимум одна на tile. Полный список объявляет все observed tiles: отсутствие tile entry даёт unknown, не dry.

Shard bed.coverage.region_uid равен root.coverage_region_uid, topology равен root.topology; coverage — точное пересечение source coverage с tile, непустое. Surface/protected — только exact G1 source samples/subset, no clamp. wet runs разделяются на границе tiles, canonical внутри tile; повторное объединение соседних runs одного body при reconstruct восстанавливает source. shore_rows exact source subset. Поля body/union tables не дублируются в shards; validation использует root tables. `source_ref` и ArtifactRef binding не заменяют checksum/admission.

Root builder проверяет disjoint union shard coverage = source bed.coverage, все samples/protection/wet/shore равны source, tables равны source, reconstructed canonical envelope имеет original fingerprint. Это source→encoding proof SP-P3I, без повторного solve. При cold admission hash-verified root/index даёт карту known candidates, каждый прочитанный shard проходит hash/version/frame/source_ref/record checks. Если требуется повторно доказать весь source fingerprint без доверия accepted root, это отдельный полный cold audit, не скрытая часть warm read. Не считать криптографический hash доказательством истинности publisher facts.

Дополнительный admission root/index: каждый shard ref имеет kind=BLOB, format_key=`hydrology.open_water.shard.tlv`, format_version=1, row_count=None и 0<nbytes≤4 MiB; manifest root ref — root key/version из §15.4, 0<nbytes≤16 MiB. tx/ty и source_ref decoded shard обязаны совпасть с выбранной записью/root. Все wet/shore/protected координаты входят в observed coverage; bed/water Z и body references проверяются по EF-1, включая dry samples и physical boundaries. root source_ref — `hydrology.canonical_open_water`, schema_version=1, algorithm_version=1; семь dependencies и их world/scope/revisions проверяются по принятому EF-1, а не только по числу элементов. Неверный ref не допускается к IO; неверное содержимое не становится empty.

### 15.4. Codec, IDs и registration

Предлагаемые ArtifactFormatKey строки:
`hydrology.open_water.root.tlv`, `hydrology.open_water.shard.tlv`; version **1**, kind BLOB, row_count=None. Format registry получает две bytes contracts (`ArtifactFormatContract[bytes]`); bytes encode/decode сохраняют bytes, domain codec отдельно декодирует и валидирует содержание. Backend verify проверяет bytes/hash, domain admission — схему/смысл. Pure encode/decode не выполняют IO.

Domain codec — existing canonical TLV v1, **без compression в format v1**: предсказуемый byte cap, без decompress bomb и скрытого выбора zstd параметров. G1 сохраняется losslessly как samples; R1 остаётся row runs. Новый compression требует нового format version, не silent codec replacement. SHA-256 ArtifactRef вычисляется по фактическим TLV bytes; source fingerprint остаётся отдельной identity существующего planning codec.

Storage schema manifest фиксируется отдельно: reuse existing SURFACE_MANIFEST V1 entries с их текущими IDs; никакого `latest entries + ...` на read. Исторический V1 manifest snapshot должен оставаться immutable при будущих GEO schema changes. Предлагаемые новые IDs в этом format-local manifest: 60001 HydrologyPackRoot; 60002 HydrologyShardRef; 60003 HydrologyPackShard; 60004 WaterMembershipRun; 60005 ArtifactRef; 60006 ArtifactKind. Existing вложенные types берутся из проверенного surface snapshot, не перенумеровываются. Эти ID **не резервируют** future planning surfaceManifest IDs. SpatialDomainRootRef/SpatialDatasetKind — JSON manifest wire, TLV ID не требуется. Ни SpatialSlice, ни query errors не регистрируются как persisted water source.

Проверенная исходная редакция surfaceManifest.py: SHA-256 `de00a17c8c3a2c149b22e2392f45d1c69979fd921b9e3c496f277331c73d7b2d`. Проверены existing IDs WorldTopology=53, PlanRef=94, PlanDependency=101, PlanDiagnostic=105, MapCellHydrology=150, WaterBody=153, PhysicalWaterUnion=154, SourceBodyMapping=226, SourceBodyMappingEntry=227, FineSurfaceWindow=283. Новые 60001–60006 с ними не пересекаются. Этот hash фиксирует таблицу назначения, не все транзитивные Python declarations: implementation admission обязан проверить closure nested types и golden bytes; изменение imported record shape без version bump запрещено.

Exact API кандидаты: `encode_root(root: HydrologyPackRoot) -> bytes`, `decode_root(payload: bytes, version: FormatVersion) -> HydrologyPackRoot`; аналогично encode_shard/decode_shard. Decode: byte cap до TLV decode, exact version, immutable strict validation, re-encode equality для rejection noncanonical/trailing bytes, then cross-record admission. Код с domain types появится по собственным gates после реализации нужных EF-1 records; отсутствие их реализации не отменяет документальный P0.

### 15.5. Бюджеты V1 — конкретное предложение на согласование

Это выбранные проектные лимиты-кандидаты, **не benchmark evidence**. Изменение формата/размера partition требует review; runtime policy может только ужесточать лимиты без изменения wire. Предлагаемый profile `open_water_v1`:

| Ограничение | Значение / поведение |
|---|---|
| Root bytes | ≤16 MiB, включая tables и каталог |
| Shard bytes | ≤4 MiB; до 4096 observed cells, не более 4096 wet runs и 4096 shore rows |
| Root entries | ≤65536 shards; при превышении новый согласованный paged-root format, не truncate |
| Один read request | ≤64 boxes; ≤1,048,576 запрошенных XYZ cells в disjoint union; ≤64 distinct touched tiles |
| Cold read bytes | ≤272 MiB = root 16 + 64 shards×4; sequential decode не более одного shard payload одновременно |
| Retained byte cache | ≤64 MiB raw artifacts; content-keyed eviction, no stale pin reuse; отсутствие cache не запускает producer |
| Output | ≤65536 volume runs; full immutable result, превышение → RESOURCE_LIMIT без partial payload |

Значения conservative operational caps, не заявление о пригодности для любого размера мира. Для миров вне V1 envelope публикация явно отклоняется до activation; требуется новый профиль/format, а не потеря observed facts. Decoded Python heap не равен encoded bytes: exact численные object-heap/time SLA этим не доказаны. Acceptance SP-P1/P3I включает измерение worst-case decode/source build на fixture под этими structural caps; если недостаточно, P0 budgets пересогласуются до production activation. Deadline/cancel передаются caller lifecycle, не новый scheduler/таймер в codec. Подготовка остаётся full-fine допустимой по EF-1, бюджеты read не обещают дешёвый solve.

Reader не перебирает все shards для окна: admission root один раз, immutable lookup (ty,tx)→ref; enumerates bounded tiles для каждого box, dedupe до IO. Root catalog full load ограничен root cap; только domain index, не manifest generic index. Ошибки всех проведённых безопасных проверок возвращаются по F3 errors tuple; при отсутствии необходимого source зависимые проверки не продолжаются. SP-3 владеет exact reader/cache implementation, SP-P2R — verified bytes port и resource-safe IO.

### 15.6. Exact target file/import map (предложение, файлы не созданы)

| Путь от backend/app | Символы / owner / шаг |
|---|---|
| dataModel/worldPack/meta/spatial/__init__.py | пустой marker, SP-P1 |
| dataModel/worldPack/meta/spatial/domainRoot.py | SpatialDatasetKind, SpatialDomainRootRef; Pack owner, imports ArtifactRef/enum/pydantic |
| dataModel/worldPack/meta/worldPackManifest.py | изменение WorldPackManifest.spatial_roots/version admission; imports new record; без domain payload imports |
| dataModel/hydrology/pack/__init__.py | пустой marker |
| dataModel/hydrology/pack/root.py | HydrologyPackRoot, HydrologyShardRef; domain records + planning refs/dependencies/diagnostics + ArtifactRef; no application |
| dataModel/hydrology/pack/shard.py | HydrologyPackShard; EF-1 WaterMembershipRun + FineSurfaceWindow + MapCellHydrology; no IO |
| application/worldData/generators/hydrology/encoding/__init__.py | пустой marker |
| application/worldData/generators/hydrology/encoding/packSchema.py | frozen format-local TLV manifest and IDs; reuse schema declarations, no storage IO |
| application/worldData/generators/hydrology/encoding/packCodec.py | четыре pure encode/decode функции; CanonicalCodec + strict domain admission |
| application/worldData/generators/hydrology/encoding/packFormats.py | две ArtifactFormatContract[bytes] constants, format keys/version; no registration side effects |

Прямые file counts: worldPack/meta существующие 7→7 (новая подпапка; existing >5 WARN), meta/spatial 0→2; hydrology/pack 0→3; hydrology/encoding 0→4. Проверить counts повторно перед реализацией. Domain source query records EF-1 не дублируются в pack folder. Manifest codec snapshots импортируют только existing data declarations; направление application codec → dataModel, never dataModel → application. Связывание backend/registry — внешняя composition SP-P2/P3, не import-side effect в этих файлах. Concrete build/index/publisher/reader paths принадлежат следующим freezes; generic P0 не выдаёт за них случайные новые сервисы.

### 15.7. Migration/caller map и publication/retention seam

| AS-IS символ / ссылка | Disposition / точка смены |
|---|---|
| WorldPackManifest / PackManifestStore.load/save (ссылки §15.1) | SP-P1 version-aware model/decode; legacy save не публикует V2; accepted staged replacement только SP-P2W/P3W |
| WorldPackReader.load_manifest/manifest | RETAIN legacy clients до явного migration; mtime cache не accepted pin. SP-P2R/SP-3 дают pinned root bytes, не модификация private paths из Hydrology |
| WorldPackWriter manifest mutation/save path | RETAIN AS-IS до owning publisher switch; atomic os.replace не manifest CAS. Не объявлять его default writer нового root |
| CanonicalWaterSourceJob.prepare (EF-1 proposal) | SP-P3I consumes admitted canonical envelope, partitions/encodes once; G10-A/SP-H required здесь, не перед SP-P0/P1 |
| HydrologyWorkingFields / parentLightHydroCorridor | HSP-02/03 retain соседних callers; не Pack source, SP-M/SP-4 отдельный cutover |
| NativeFinalWaterQuery.water_at | RETAIN XY evidence, не root reader; no automatic rename |
| ArtifactFormatRegistryBinding / BLOB backend | REUSE bytes registration/write/verify/delete contracts; отсутствие read не обходить через private _path; SP-P2R добавляет/принимает owning port |

**Publication ordering:** stage+seal shards → root referencing exact shards → candidate V2 manifest → accepted pregame CAS/pin. До activation должны быть durable и protected **все** refs. root→shard references сами не создают GC holds. SP-P3W обязан предъявить явный closure refs и удержание root+shards через accepted staging/publication owners; retained refs/metadata mapping использовать только после принятия соответствующего Snapshot contract/implementation. Нельзя считать непринятый 4C3-B доказательством готового handoff. Не вводить собственный hydrology GC или прямой SQL writer. Publication refusal не изменяет active root; abandoned staged data освобождается общим lifecycle.

Для domain root admission: format/version/hash/size → exact source/world/frame/dependencies → root/index consistency → queried shard facts. Pack root привязывается к manifest выбранного WorldPublicationRef; его принадлежность pin не доказывается source_ref или format key. Q01/overlay/SP-3S остаются внешними gates. Snapshot domain changes не переписывают immutable base shards.

### 15.8. Предмет согласования и acceptance evidence

На согласование вынесен **весь SP-P0 V1**: V2 manifest root-only entries; root/shard records и tile=64; TLV без compression, ключи/версии/format-local IDs; явная empty/unknown семантика; structural/byte caps и их ограничения; карта файлов и migration. Ничего из этого не объявляется принятым фактом по наличию текста.

До приёмки P0 проверить domain refs/types/IDs closure, storage codec/schema consistency, dry/unknown при отсутствующем tile и сохранение G1/protected/shore/body mapping; согласовать пригодность предложенных лимитов мира. До SP-P1 кода отдельно зафиксировать реализационный scope и существование нужных EF-1 declarations. До downstream activation: canonical decode negative cases, unknown major/minor/format/ref kind, bad hash/size/noncanonical TLV, absent vs explicit dry, negative/seam tiles, cross-shard runs reconstruction, source fingerprint replay, max-limit/refusal cases, concurrent publication/retention/CAS evidence, cold read без solve/L0/working maps, pin mismatch, GC safety всех shards. Это будущие проверки, не проведённые тесты.

SP-P0 может приниматься без реализации G10-A, Snapshot ports и GEN. Его приёмка не закрывает SP-P2R/W, PACK-ENTRY-CONTRACT, SP-P3I/W, SP-3, SP-M или runtime. Общий graph hard edges не изменяются. Остаточная работа по time/heap measurements, verified byte-read и retention/pin интеграции явно принадлежит указанным downstream gates; если пересмотр структурного budget/формата потребуется по measurement, он возвращается на P0 review, не решается молча в коде.

### 15.9. Архитектурное ревью SP-P0 (2026-11-02)

**Verdict: требуется документальная доработка до предъявления exact storage freeze.** Выбранное root-only направление согласуется с принятыми SP-1 §14.12 и GEO EF-1.12/1.14; перечисленные ниже findings не переоткрывают A/R1/G1. Это verdict ревью, **не пользовательская приёмка/freeze**. SP-P1, публикация и runtime activation не начаты. G10-A не prerequisite проектирования или исправления этих findings.

Проверка статическая по текущим файлам; runtime/tests/benchmarks не запускались. Existing изменения рабочего дерева сохранены. Evidence: CanonicalCodec._encode/_decode_one/decode, SurfaceEnvelopeCodec, surfaceManifest.py, planFingerprints.output_fingerprint, PlanEnvelope, FineSurfaceWindow/RegionCoverage, WorldPackManifest, PackManifestStore, WorldPackReader/Writer, ArtifactFormatContract/ArtifactFormatRegistryBinding, ContentAddressedBlobBackend. Hash surfaceManifest из §15.4 подтверждён; IDs 60001–60006 допустимы по RegisteredTypeEntry (положительный StrictInt, без 16-bit ограничения) и не пересекаются с текущими bindings. hydrology/query/source.py ещё отсутствует: принятые EF-1 declarations остаются проектом, не существующим codec port.

**P0-R1 — P1 / schema и fingerprint replay не замкнуты (§15.3–15.4).** Storage IDs регистрируют WaterMembershipRun, но не CanonicalOpenWaterSource; текущий SURFACE_MANIFEST не содержит обоих новых типов. Existing output_fingerprint хеширует `(payload, dependencies, diagnostics)`, а не envelope целиком. Следовательно, storage hash root/shards сам по себе не позволяет выполнить обещанный replay original output fingerprint: нужен отдельно фиксированный planning source manifest с ID CanonicalOpenWaterSource/WaterMembershipRun и версией, используемый самим canonical producer. Два format-local пространства IDs допустимы и не обязаны совпадать. До freeze указать точный owning source codec/version/ID handoff, формулу replay и её imports; реализация producer остаётся downstream. Не решать это чтением latest SURFACE_MANIFEST. Отдельно перечислить транзитивную closure storage snapshot и политику изменения imported record shapes: hash одного surfaceManifest.py подтверждает назначения, но не замораживает определения Python-типов, от которых decoder получает names/types динамически. Golden bytes и negative cases проверяются при реализации, однако точная схема должна быть определена до неё.

**P0-R2 — P1 / byte cap недостаточен для bounded decode (§15.4–15.5).** Existing _decode_one рекурсивно разбирает произвольные tuple/set/record значения до domain validation, копирует body[offset:] и сохраняет parts; лимитов глубины/числа TLV nodes нет, RecursionError не переводится canonical decoder в CanonicalEncodingError. Payload ≤4/16 MiB может превысить recursion depth до проверки shard/root caps; re-encode equality выполняется позже. «Sequential один payload» не ограничивает transient copies, decoded root/index, result и metadata closure. До freeze задать численные parser depth/node/collection caps и отказ до allocation/recursion, owner безопасного decoder и точный target file/import disposition. Существующий codec нельзя объявлять готовым resource-safe storage decoder только по byte cap. Heap/time measurements допустимо оставить SP-P1/P3I, но отсутствие проектного bound нельзя заменить будущим benchmark. Полный root scan ограничен 16 MiB/65536 entries и приемлем как bounded index admission; 272 MiB — верхняя граница raw artifact bytes одного read, не memory/time SLA.

**P0-R3 — P2 / V1/V2 migration map недостаточно точна (§15.2, §15.6–15.7).** PackManifestStore.load сейчас json.loads→model_validate без version admission, WorldPackManifest.pack_version — произвольная str с default, extra=ignore; старый reader примет V2 и последующий save может стереть roots. Новый required tuple нельзя просто добавить общей модели без version-dispatched V1 policy. Фактические mutation/save callers помимо WorldPackWriter: `application/worldData/pack/bake/finalize/packBakeFinalize.py:finalize_pack_on_world`, `application/worldData/pack/refine/fine/fineRectDrain.py:FineRectDrain.refine_rect`, `application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py`; re-export PACK_WIRE_VERSION есть в `dataModel/worldPack/__init__.py`. До freeze внести их отдельные dispositions и target files version dispatcher/legacy-save guard; определить admission для unsupported minor/patch и V1 с неожиданным spatial_roots, не только unknown major. Unmodified old binaries не получают guard задним числом: явно определить rollout/exclusive writer policy для V2 storage. Не требовать сейчас реализации CAS и не выдавать os.replace за CAS.

**Exact source split/reconstruction — представление достаточно, алгоритм нормализации нужно уточнить.** Root сохраняет полные tables/mapping (включая explicit empty entries), dependencies/diagnostics/ref; shards — все dry/wet bed samples, protected subset и SHORE. Fixed WORLD_FINE space восстанавливается из контракта; topology/region_uid/Z — из root. Разбиение R1 на tile boundaries обратимо. При сборке необходимо канонически объединять **и coverage spans**, не только wet runs: RegionCoverage отвергает adjacent spans одной строки, поэтому простая конкатенация shard.coverage не восстанавливает валидный source. Затем восстановить global row-major surface/shore, union protected_cells, merged same-body wet runs, исходные tables и envelope fields; проверять equality payload/dependencies/diagnostics и output_fingerprint по P0-R1. Это требуемое уточнение source→encoding proof, не новый solve. Empty coverage допустима и означает unknown; полностью dry observed coverage требует shards с G1 samples. Пропуск такого dry shard ради compactness нарушит EF-1.

**Absent/empty/unknown и provenance — согласованы.** Missing manifest root/указанный shard не dry; отсутствующая tile entry вне observed coverage unknown. После admitted publication root полнота каталога опирается на publisher proof; selective cold read не доказывает заново весь source hash. Это явно объявленная trust boundary, не дефект. Source PlanRef, artifact SHA и WorldPublicationRef pin — разные identities; source_ref не подтверждает принадлежность выбранному manifest. RESOURCE_LIMIT уже входит в принятый закрытый enum §14.3; новые причины ошибок для budgets не нужны. PREVIEW не превращает corruption/missing в empty.

**Retention всех shards — верное требование, готового механизма не доказано.** §15.7 правильно требует closure `root + все shard ArtifactRef`, включая shards вне текущего окна/cache, до manifest activation. ArtifactFormatRegistryBinding/BlobBackend не обходят вложенные refs и не создают holds из содержимого root. Необходим downstream evidence SP-P3W: explicit closure перед CAS, непрерывное удержание при staging→publication и rollback, retained old pin после смены active root, concurrent GC, release abandoned staging и окончательное освобождение после последнего pin. Root-only hold и lazy hold только прочитанных shards неприемлемы. Сохранение семи PlanDependency refs — provenance, не обещание retention upstream artifacts; обязательный cold gameplay read должен обходиться root/shards без upstream solve. Snapshot adapters/4C3-B и GEN-DAG draft не приняты как ports; их отсутствие не блокирует P0 design, но запрещает объявлять publication/read integration готовой. Public verified bounded byte-read отсутствует в ArtifactBackend/ContentAddressedBlobBackend, остаётся SP-P2R; verify читает весь файл и не возвращает bytes.

**Численные budgets — только предложенный envelope.** 64×64, 65536 shards, 4096 samples/runs/shore rows и raw-byte ceilings дают конечный storage/read профиль; это не доказательство пригодности для текущих миров или дешёвой подготовки. 65536 полных tiles дают максимум 268435456 observed XY cells, при sparse coverage меньше; допускается явный отказ большому source, не потеря фактов. Ограничение request XYZ volume не ограничивает общий объём retained source. Cache 64 MiB не включает decoded root/index/output, поэтому оно не закрывает P0-R2. Численные heap/time SLA по-прежнему отсутствуют; до приёмки следует либо определить их проектные значения/методику, либо явно согласовать более узкий scope bounded bytes/structure, не объявлять весь прежний memory/time budget gate закрытым.

Для повторного review: закрыть P0-R1/R2/R3 документально, уточнить canonical reconstruction и scope budgets. Runtime verification, golden bytes, max-limit fixtures, GC/CAS и cold replay остаются своими downstream gates. Существующие folder counts §15.6 (meta=7) подтверждены; чистые domain→dataModel и codec→dataModel imports разумны, но добавленные dispositions/decoder/source codec paths должны дополнить exact map. Никакая запись этого review не принимает freeze за пользователя.

### 15.10. Проработка решений после review — проект V1.1 (2026-11-02)

**Статус: проект уточнений, не freeze и не CODE-READY.** Пользователь согласился продолжить проработку конструкции после объяснения контекста budgets. Это не приёмка конкретных IDs, parser limits или Pack migration. Настоящий раздел уточняет §§15.2–15.8; §15.9 сохраняется как история findings. Код, SP-P1 и публикация не начаты. G10-A не prerequisite этого проекта; непринятые Snapshot adapters и GEN-DAG не используются как готовые ports.

#### 15.10.1. Одна source identity и две задачи encoding

Предлагается один фиксированный `OPEN_WATER_SOURCE_SCHEMA_V1`, общий для CanonicalWaterSourceJob и source replay. Он не зависит от импортируемого «latest SURFACE_MANIFEST». Existing назначения snapshot §15.4 сохраняются; дополнения: **60004 WaterMembershipRun**, **60007 CanonicalOpenWaterSource**, **60008 PlanEnvelope[CanonicalOpenWaterSource]**. ID 60004 общий для source/storage manifests; IDs 60001–60003/60005–60006 остаются storage-only. WaterSourceIssueCode, WaterWindowFacts и Spatial read errors не входят в persisted source closure и новых IDs здесь не получают. Добавление source IDs не является регистрацией production provider.

`OPEN_WATER_PACK_SCHEMA_V1` использует тот же frozen baseline и source entries, дополняя их storage records. Наличие source bindings в storage manifest не разрешает принимать envelope вместо root/shard: decode требует exact ожидаемый top-level type. Source key `hydrology.canonical_open_water`, schema1/algorithm1 и root/shard format version1 однозначно выбирают эти таблицы. Не добавляем independently selectable codec revision в root. Следующая несовместимая source schema требует нового source schema_version и нового поддерживающего pack format version; изменение только algorithm_version не разрешает менять TLV shape.

Freeze baseline означает literal bindings с IDs из проверенной редакции §15.4 и зафиксированные shapes, а не runtime merge с текущим SURFACE_MANIFEST. Для использованных вложенных types lock включает ordered record fields, типы полей (включая tuple/frozenset, optional/union/literal), enum wire values и defaults. Closure начинается с source/envelope и root/shard, транзитивно включает существующие geometry/body/mapping/ref/dependency/diagnostic records; сохраняет их existing IDs. Implementer предъявляет полный machine-readable lock и golden bytes перед приёмкой реализации. Его location — constants в sourceSchema.py/packSchema.py, без отдельного runtime schema registry. Golden fixtures находятся в tests. Проверка lock должна отвергать shape drift до decode/encode; одного hash surfaceManifest.py недостаточно. Если existing declaration несовместимо изменится, прежняя поддерживаемая версия требует сохранённого version-specific wire declaration/decoder либо явного отказа; подмена новым class под старым ID запрещена. Наличие ещё не реализованных EF-1 типов не восполняется storage DTO-копией.

Формула replay — existing `output_fingerprint(source.payload, source.dependencies, source.diagnostics, OPEN_WATER_SOURCE_SCHEMA_V1) == source.ref.output_fingerprint`. Хешировать envelope с включённым собственным ref не требуется. Input fingerprint остаётся сохранённым в PlanRef.key: root не содержит всех producer inputs и не обещает пересчитать его. Replay проверяет payload output identity и сохранность provenance, не повторяет исходный solve и не доказывает истинность producer facts. SHA-256 каждого ArtifactRef вычисляется отдельно по actual stored bytes.

Source producer и SP-P3I importer обязаны использовать один source schema; importer отвергает envelope, fingerprint которого не воспроизводится. SP-P3I не назначает новый ref исходному source. И producer, и source replay импортируют sourceSchema.py; sourceSchema не импортирует packCodec, IO или публикацию. Этот handoff должен быть зеркально учтён owning GEO codec implementation при его отдельной подготовке; принятые поля EF-1 не меняются.

#### 15.10.2. Обратимое partition и reconstruction

Build сохраняет exact source tables/mapping/dependencies/diagnostics и topology/region_uid/Z в root. Каждая observed XY-клетка попадает ровно в один 64×64 tile по floor, включая отрицательные координаты. Публикуются также полностью dry tiles с observed bed; пустые observed tiles не создаются. В shard помещаются точное пересечение coverage, bed/protected/shore subset и clipped R1 runs. Никакой дополнительный coverage, bed interpolation или Z clamp не вводится.

Reconstruction выполняется в следующем порядке:

1. Admit root и все referenced shards; проверить refs, tile/source/frame binding, отсутствие повторного покрытия и чужих coordinates.
2. Собрать coverage spans глобально по (y,x0), слить adjacent spans одной строки; overlap отклонить. Это обязательно для RegionCoverage, который запрещает adjacent spans.
3. Собрать surface_z и shore_rows в global row-major order, protected_cells — union без посторонних cells. Surface проверяется existing FineSurfaceWindow.complete_surface. Повторяющиеся coordinates отклоняются, а не перезаписываются словарём.
4. Собрать wet runs по (y,x0), слить adjacent same-body runs; overlap или конфликт body отклонить. Сохранить разрывы coverage и topology seam. Подставить fixed WORLD_FINE space, root Z и неизменённые полные body/union/mapping tables.
5. Восстановить source envelope с original ref/dependencies/diagnostics, проверить payload equality исходному admitted source при build и output fingerprint по §15.10.1. При полном cold audit проверить fingerprint без наличия исходного payload в памяти.

Build/audit может проходить весь source; обычный read читает только selected shards и доверяет completeness proof принятой immutable публикации. Root-only admission не изображает полный replay. Source preparation остаётся full-fine допустимой; per-read source reconstruction запрещена. Protected membership и explicit empty dry mapping entries сохраняются независимо от wet runs.

#### 15.10.3. Bounded storage decoder без изменения TLV wire

Предлагается общий opt-in `decode_bounded(encoded, expected, manifest, *, limits)` в новом `application/encoding/boundedCanonicalDecode.py`; existing fingerprint encoder и existing callers `canonicalCodec.decode` не переключаются автоматически. Новый decoder реализует тот же TLV v1 с offset/memoryview traversal: не вызывает рекурсивный _decode_one с body[offset:] и не накапливает копии encoded parts. Общие проверки schema/record semantics переиспользуются или выделяются в existing canonicalCodec.py при реализации с golden parity; второй wire format не вводится. Exact encoded bytes после decode сверяются existing canonical encode.

Первый проход до создания domain models проверяет TLV boundaries, полный расход input, depth/node/container counters, registered tags/type IDs, exact record field roster и ожидаемые field collection limits. Нарушение завершает decode до model constructors. Проверки nested immutable graph/domain consistency выполняются после структурного admission; parser limits продолжают действовать при materialization. Не допускается «сначала old decode, затем проверить limits».

Предлагаемые hard parser limits: **depth ≤64** (top-level depth=1, каждый вложенный TLV +1), **root ≤524288 TLV nodes**, **shard ≤131072 nodes**, **один container ≤65536 непосредственных элементов**. Считаются все nodes, включая record wrappers/field-name strings. Дополнительно schema-aware caps: shard surface/protected/coverage spans/wet/shore ≤4096 каждого, root shard entries ≤65536, dependencies ровно семь. Остальные variable collections ограничены container/node/byte caps и domain validators. Все caps применяются одновременно: entries ceiling не обещает, что 65536 самых больших refs поместятся в byte/node ceilings. Values и факты не обрезаются; build обязан отказать source, который не помещается. Полнота source важнее успешной публикации.

Root ≤16 MiB / shard ≤4 MiB проверяются до decoder, actual bytes должны совпасть с ref size/hash. Бounded IO обязан прекращать oversized stream, а не читать его целиком ради последующей проверки. Это требование SP-P2R, не существующая возможность verify. При чтении опубликованного artifact нарушение parser/schema caps — SOURCE_CORRUPT; неподдержанная format version — UNSUPPORTED_FORMAT. Превышение read request/output budget — RESOURCE_LIMIT. Build refusal не публикует candidate. Async cancellation остаётся cancellation; не маскируется ошибкой source.

Эти числа — проектные ограничения, не measurements. До freeze проверить их совместимость с минимальным/типичным source и nested type closure; на SP-P1 — adversarial nesting, unknown tags/IDs, oversized collection, truncation/noncanonical input и golden parity. Time/heap SLA остаётся открытой частью budgets; данный decoder даёт structural work bound, не доказанную задержку.

#### 15.10.4. Pack V1/V2 admission и защита от потери roots

Остаётся один логический WorldPackManifest. Decode dispatch выполняется в новом `application/worldData/pack/encoding/packManifestCodec.py` до permissive model_validate. Предлагаемые pure API: `decode_manifest(payload: bytes) -> WorldPackManifest`, `encode_legacy_manifest(manifest: WorldPackManifest) -> bytes`. V2 candidate encoding — отдельная функция в том же codec, вызываемая только принятым publisher по SP-P2W/P3W; legacy store её не вызывает. Duplicate JSON object keys и malformed version отклоняются. Manifest-wide byte/depth cap не выводится из 16 MiB hydrology root: это иной документ; его resource contract остаётся в Pack IO freeze.

Exact supported versions — **1.0.0 и 2.0.0**, остальные major/minor/patch отклоняются до модели. Для legacy manifest без pack_version допускается явная историческая интерпретация как 1.0.0. `PACK_WIRE_VERSION` сохраняет legacy default 1.0.0; V2 candidate задаёт 2.0.0 явно. V1 с присутствующим spatial_roots (даже []) отклоняется как неоднозначный wire. Для V1 decoder вводит внутренний пустой tuple; V1 encoder всегда исключает это поле. V2 требует spatial_roots, missing/null invalid; JSON arrays/strings преобразуются явным transport decoder в typed tuples/enums, а не передаются strict in-process boundary как raw dict. Root rows strict, sorted/unique; unknown domain/format/version отклоняются owning boundary. Внутренняя пустая V1 коллекция не доказывает dry и не превращает V1 в V2.

Legacy save разрешён только для admitted V1 без spatial roots. Guard срабатывает в WorldPackWriter constructor для loaded/injected V2 **до любых file mutations**, повторяется в save_manifest **до recalc/content_hash mutation** и в PackManifestStore.save до temp/replace. Чтение V2 existing WorldPackReader допускается после version-aware codec, но mtime cache остаётся legacy terrain reader, не pinned spatial reader. Любая следующая V2 mutation/publication требует owning accepted path; preserve-roots через legacy rewrite не обход guard.

Caller dispositions (пути от backend/app):

- `application/worldData/pack/io/packManifestStore.py`: load использует dispatcher; save только legacy encoder/guard. File replacement не CAS.
- `application/worldData/pack/io/worldPackWriter.py`: constructor/save guards выше; новая legacy manifest остаётся V1; не становится V2 publisher.
- `application/worldData/pack/io/worldPackReader.py`: version admission через store; не удаляет roots и не меняет pin semantics.
- `application/worldData/pack/bake/finalize/packBakeFinalize.py:finalize_pack_on_world`: V1-only legacy финализация; V2 не доходит до world-row update через этот путь.
- `application/worldData/pack/refine/fine/fineRectDrain.py:FineRectDrain.refine_rect` и `application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py`: legacy writer construction отвергает V2 до записи terrain blobs. Future V2 refinement migration — отдельный owning scope, не молчаливое отключение guard.
- `dataModel/worldPack/__init__.py`: сохранить existing exports и V1 default; новые eager domain/codec exports не добавлять.

Old binaries не соблюдают новые guards. Поэтому V2 activation допускается только после deployment version-aware readers/guards и прекращения old writer jobs на этом storage namespace. До выполнения этого условия candidate не активируется; rollback к old executable с записью V2 namespace запрещён, используется retained V1 pack в отдельном namespace либо новый binary с V2 support. Способ fencing/exclusive ownership доказывает owning publisher gate, не «наличие» непринятого Snapshot adapter. При concurrent старом writer V2 publication gate не пройден. Гарантия всех сторонних writers без контроля deployments здесь не заявляется.

#### 15.10.5. Budgets, retention и дополнение file map

64 touched tiles и 272 MiB сохраняются **предлагаемым batch envelope**, не обещанной interactive latency. Отдельный интерактивный профиль должен только ужесточать те же limits после выбора реального caller; новый формат/reader/source для него не нужен. До этого caller activation не считается обеспеченным численными SLA. Output ≤65536 runs, ≤64 boxes/1048576 XYZ cells и cache ≤64 MiB raw сохраняются. Decoded root/index, output и transient allocations не входят в raw cache cap. На SP-P1/P3I предъявляются peak heap/cold/warm time и concurrency measurements на max-admissible и adversarial fixtures; числа SLA должны быть согласованы до production activation. Принятие всего прежнего memory/time budget scope одним согласием с batch byte ceiling не подразумевается.

Retention closure для публикации — `unique(root_ref + все root.shards.artifact)`, независимо от query/cache. Closure проверяется и удерживается staging owner до handoff; publication/retained pins обязаны обеспечить непрерывность holds. CAS failure оставляет active closure неизменной; abandoned staging освобождается по общему lifecycle. Смена active root не освобождает shards старого retained pin; shared artifacts освобождаются только после последнего holder. Читатель не создаёт lazy retention только для touched tiles. Exact accepted port/signature передачи closure остаётся SP-P3W/owning lifecycle freeze, не выдумывается поверх непринятых adapters. Upstream PlanRefs — provenance, не dependency на доступность upstream blobs при cold read.

Дополнение §15.6 (новые paths не созданы): `application/worldData/generators/hydrology/encoding/sourceSchema.py` — source bindings/shape lock, imports только data declarations/schemaManifest; `packSchema.py` — storage additions, imports sourceSchema + storage declarations, never live SURFACE_MANIFEST. `packCodec.py` импортирует boundedCanonicalDecode и existing encode. `application/encoding/boundedCanonicalDecode.py` — generic opt-in structural decoder, imports encoding schema/types и canonical helpers, без Hydrology/Pack/IO. `application/worldData/pack/encoding/packManifestCodec.py` — JSON version dispatcher/encoders, imports WorldPackManifest + spatial root declarations, без hydrology payload/registry/SQL. Existing canonicalCodec.py может получить общие private validation helpers, сохраняя public old API/wire. Новый application hydrology/encoding count теперь **0→5** вместо 0→4; остальные новые domain folder counts §15.6 сохраняются. Existing application/encoding: 2→3; pack/io: 11→11 (WARN, новый codec вынесен в отдельную подпапку); новый pack/encoding: 0→2 с пустым __init__.py и packManifestCodec.py. Counts и выбранное распределение helpers повторно проверяются перед implementation scope.

**Промежуточный verdict:** для P0-R1/R2/R3 предложены конкретные решения, автоматического закрытия findings нет. На следующем review проверить source/storage lock closure и IDs, parser limits против выбранных fixtures, guards всех mutation entrypoints и rollout feasibility. Открыты согласование parser/batch limits, полный source shape lock, численные heap/time SLA и owning downstream ports/evidence. Freeze остаётся пользовательским решением; ни G10-A, ни Snapshot/GEN readiness не подставляются в prerequisites P0 design.

### 15.11. Принятые решения по scope budgets, V2 writers и превышению caps (2026-11-02)

Пользователь ответил «Ок» на три конкретных предложения после обсуждения §15.10. Приняты следующие решения; эта запись уточняет предыдущий промежуточный verdict только в указанном scope.

1. **Scope budgets P0:** фиксируются byte и structural caps; численные heap/time SLA остаются открытыми до измерений и выбора реального caller. Production activation требует отдельной приёмки этих SLA. Предложенные parser limits проверяются на fixtures до freeze; согласие с разделением scope не является безусловной приёмкой всех предложенных чисел. Весь прежний performance scope одним SP-P0 не закрывается.
2. **V2 mutation:** legacy writer полностью запрещено изменять V2 Pack. Refinement/materialization переводятся отдельным согласованным шагом; до него соответствующий legacy путь явно отказывает на V2. V2 активируется после остановки старых writers и установки version guards. Preserve-roots через legacy rewrite не заменяет принятый publisher.
3. **Source вне V1 caps:** публикация явно отклоняется, текущий active Pack сохраняется. Факты не обрезаются. Paged-root проектируется отдельным format scope при подтверждённой потребности, без скрытого расширения V1 в implementation.

Это **частичная пользовательская приёмка трёх решений**, не полный SP-P0 freeze, не приёмка всех деталей §15.10 и не закрытие P0-R1/R2/R3 без verification. Остаются source/storage schema lock и IDs closure, проверка parser limits/guards/rollout и отдельные downstream ports/evidence. G10-A не prerequisite P0 design. SP-P1, реализация, публикация и runtime activation не разрешаются этой записью и не начаты.
