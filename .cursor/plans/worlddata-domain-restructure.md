# Реструктура `application/worldData` — вынос чужих доменов + нарезка корня

## Проблема

`backend/app/application/worldData/` стал catch-all пакетом: рядом с доменом
«генерация и хранение данных мира» (`generators/`, `pack/`, `masks/`, `render/`,
`settlementOutdoor/`, `transitions/`) лежат:

- **`ids/`** — центральная det-uid формула (`uuid5`, `UidKind`, `LibraryKind`).
  Чистый kernel: stdlib-only, импортируют `dataModel`-adjacent потребители,
  `canonicalLibrary`, `engine`, pack, transitions, сервисы (~50 файлов).
  `dataModel` обходит импорт строковой валидацией `library_kind`
  (см. docstring `dataModel/libraryPacks/libraryPinEntry.py`).
- **`context/`** — generic cascade-движок (`extend()`, `runtimeChain`,
  `cascadeLink`, `cascadeLog`) поверх `dataModel/cascade` + location-glue
  (`locationScope`). Импортируют `core/loggingConfig`, `core/generationLogging`,
  `api/routes/debug`, генераторы.
- **`libraryPacks/`** + `*TemplateLibraryService` + `*TemplateFsImport` +
  `*Errors` + `reliefWorldImportService` + `loadReliefTemplatesForWorld` +
  `reliefGeomWarn` — домен библиотек шаблонов (`tz_template_library_packs`),
  sibling `dataModel/libraryPacks`.
- **`bundle/`** + `worldBundleService` + `bundleRemapService` +
  `deriveWorldUid` + `connectionGraphService` — обмен/портативность мира
  (`tz_world_bundle`), sibling `dataModel/worldBundle`.
- **`playerService`, `gameSessionService`** — обслуживают
  `api/routes/characters.py` и `sessions.py`; к данным мира отношения нет.
- **~25 плоских файлов в корне** без доменной группировки (map-cells,
  materialize-оркестрация, persist, реестры мира, relief-каталог).

Сопутствующий smell: `app/core/container.py` — 925 строк, ~140 строк
импортов, ~30 lazy-синглтонов и ~15 per-world фабрик по всем доменам
сразу (нарушение `class-size-limit`: тело класса ~780 строк). Каждый шаг
переезда в любом случае трогает его импорты — логично закрыть разрез
Container в этом же плане.

## Целевое состояние

```text
app/
  ids/                        ← worldData/ids/ (решение мастера: топ-уровень,
                                т.к. uid-идентичность будут использовать
                                будущие домены simulation/mechanics)
    deterministicIds.py, uidKind.py
  application/
    cascade/                  ← worldData/context/ целиком
      contextResolver.py, runtimeChain.py, cascadeLink.py,
      cascadeLog.py, locationScope.py
    templateLibrary/          ← домен библиотек шаблонов
      packs/                  ← worldData/libraryPacks/ core-модель:
                                manifest, defaults, errors, uidMap,
                                packIdentity, packScope, membership,
                                memberOps, packOps, packResults,
                                packCatalog, packService, lifecycleContracts,
                                effectiveCatalog, reliefCanonicalSpec,
                                templateCanonical{Persistence,Service,Source},
                                provenanceResolver, refResolve,
                                referenceResolver, templateGraphValidation
        domainAdapters/       ← shared kernel, как было
        write/                ← write* (contracts/service/factory/planner/
                                planContracts/preview/executor/results/
                                retentionPlanner/policy/inspectionContracts/
                                inspector/sourceReader/stateReader/facade),
                                authoringWrite, memberWritePlanner,
                                packWritePlanner, preparedPersistence,
                                domainWriteEntry, fsWrite{Service,Source},
                                bodyDiff
        legacy/               ← legacy{Domain*,World*,Write,Pack} (12 файлов)
        reinstantiate/        ← reinstantiate* (5 файлов)
        archive/              ← archive{Service,Sources}
      buildingTemplateLibraryService.py, plotTemplateLibraryService.py
      structureTemplateLibraryService.py, structureTemplateFsImport.py,
      structureTemplateErrors.py
      reliefTemplateLibraryService.py, reliefTemplateFsImport.py,
      reliefWorldImportService.py, reliefErrors.py, reliefGeomWarn.py,
      reliefTerrainSync.py, reliefWorldRefValidation.py,
      loadReliefTemplatesForWorld.py
      templateContracts.py, templateSnapshotLoader.py
    worldBundle/              ← обмен/портативность мира
      handler.py, registry.py, order.py, errors.py, copyTokens.py,
      legacyTemplateBodies.py, worldCopyImport.py, worldLibraries.py,
      archive/, entity/, library/   ← содержимое worldData/bundle/
      worldBundleService.py, bundleRemapService.py, deriveWorldUid.py,
      connectionGraphService.py
    session/                  ← playerService.py, gameSessionService.py
    worldData/                ← только генерация и хранение данных мира
      generators/, pack/, masks/, render/, settlementOutdoor/, transitions/
      materialize/            materializationContext, parallelPolicy,
                              chunkComputePool, serialPersistQueue,
                              terrainParallelLog, loadingProgress,
                              persistResult, terrainBatchOrchestrator,
                              climateBatchOrchestrator,
                              worldSurfaceMaterializationOrchestrator
      mapCells/               mapCellService, mapCellReadService,
                              mapCellQueryFacade, patchStoreService,
                              bootstrapMapCellWriter
      persist/                settlementPersistService, settlementPersistScope,
                              connectionPersistService, connectionUids,
                              persistReliefGrades
      locations/              namedLocationService, locationPayloadAccess,
                              settlementSkeletonAccess, settlementMapOccupancy
      registries/             worldService, raceService, worldPerkService,
                              stateService, seedService, repairWorldDefaults
      relief/                 gradeCatalog, gradeInstanceMerge,
                              gradeVertexSystem, parseObjectReliefPickPolicy
      facingArrows.py         остаётся в корне: docstring фиксирует, что
                              перенос в render/ ломает circular-import
      debugStructureRotations.py  остаётся в корне (leaf debug-утилита)
  core/
    container/
      __init__.py             class Container(*Wiring) — facade + _db/_config
      repositories.py         repo lazy-синглтоны (mixin)
      llm.py                  clients + router (mixin)
      engine.py               rules/graph/prompt/validation/repair/execution
                              + llm_engine (mixin)
      worldData.py            worldData-сервисы, оркестраторы, pack-фабрики
                              (mixin)
      session.py              player/session/chat/settings (mixin)
```

Container разрезается **mixin-стилем**: `container.xxx()` API для всех
caller'ов (routes, тесты) не меняется — шаг чисто механический.
Границы mixin'ов = границы доменов целевого дерева.

**Инварианты:**

- `app/ids` — единственный владелец det-uid формулы и `UidKind`/`LibraryKind`;
  импортируемо из любого слоя, включая `dataModel` (см. Follow-up).
- `application/cascade` — доменно-агностичный движок; его binding-таблица
  (`_MATERIALIZE`, `_FOLDS`) по-прежнему указывает на callables в
  `worldData.generators.utils` — направление `cascade → worldData` принято
  мастером (вынос целиком). Ужесточение — отдельный долг, не этот план.
- `application/{templateLibrary,worldBundle,session}` — sibling-домены,
  зеркалят `dataModel/{libraryPacks,worldBundle}` по духу.
- Шаг = `git mv` + repo-wide замена dotted-path импортов + compileall +
  профильные тесты. Поведение не меняется; сигнатуры не трогаем.
- `Container` делится на wiring-mixin'ы по доменам; callers видят тот же
  `container.<service>()`.

## Шаги

### Шаг 1 — `ids/` → `app/ids/` — выполнен 2026-10-09

- **Цель:** kernel uid-формулы на топ-уровень, вне application.
- **ТЗ:** `docs/project_data_storage_tz.md` § DET-1; `docs/tz_template_library_packs.md` §2.
- **Файлы:** `worldData/ids/{__init__,deterministicIds,uidKind}.py` → `app/ids/`; rewrite `app.application.worldData.ids` → `app.ids` (~50 файлов: application, dataModel-adjacent нет — dataModel не импортирует; tests; scripts; `core/`).
- **Контракт:** модульный путь; API без изменений.
- **Проверка:** `grep "worldData.ids" backend` = 0; `python -m compileall backend/app`; `python -m unittest tests.test_deterministic_ids tests.test_library_packs_b3` (+ test_canonical_library).
- **Done:** пакет `app/ids` импортируется; старого пути нет.

### Шаг 2 — `context/` → `application/cascade/` — выполнен 2026-10-09

- **Цель:** cascade-движок в собственный application-домен.
- **ТЗ:** `docs/tz_cascade_context.md` §2, §4.
- **Файлы:** `worldData/context/*.py` → `application/cascade/`; rewrite `worldData.context` → `application.cascade` (~28 файлов: generators, settlementOutdoor, api/routes/debug, core/loggingConfig, core/generationLogging, tests). Внутри `locationScope` импорты `worldData.locationPayloadAccess` / `settlementSkeletonAccess` / `ids` → новые пути (`app.ids`; worldData-пути после шагов 8–9).
- **Контракт:** путь; `extend()`, `scope_sequence()`, `debug_building_context` без изменений.
- **Проверка:** grep = 0; compileall; `python -m unittest tests.test_context_extend tests.test_cascade_context_baseline tests.test_cascade_migration_m2`.
- **Done:** `application/cascade` импортируется; `worldData/context/` удалён.

### Шаг 3 — templateLibrary домен — выполнен 2026-10-17 (b7e36b53, 947f7332)

- **Цель:** библиотека шаблонов — отдельный application-домен.
- **ТЗ:** `docs/tz_template_library_packs.md` §3–§6; `docs/tz_building_generator.md` §5–6; `docs/tz_terrain_relief.md` R29/R34/R35.
- **Файлы:** `worldData/libraryPacks/` (64 модуля + `domainAdapters/`) → `application/templateLibrary/packs/` с внутренней нарезкой на подпакеты (решение мастера 2026-10-16): core-модель плоско в `packs/` (22 модуля), `packs/write/` (23), `packs/legacy/` (12), `packs/reinstantiate/` (5), `packs/archive/` (2), `packs/domainAdapters/` без изменений. Слои: core + domainAdapters ← catalog ← write ← {legacy, reinstantiate, archive, packService}.
- Плоские файлы → `application/templateLibrary/`: `buildingTemplateLibraryService`, `plotTemplateLibraryService`, `structureTemplate{LibraryService,FsImport,Errors}`, `relief{TemplateLibraryService,TemplateFsImport,WorldImportService,Errors,GeomWarn,TerrainSync,WorldRefValidation}`, `loadReliefTemplatesForWorld`, `templateContracts`, `templateSnapshotLoader` (15 файлов; последние 5 добавлены против исходного списка — потребители только в домене). `worldData/errors.py` (`WorldDataError`) **остаётся** — общая ошибка worldData.
- Rewrite `worldData.libraryPacks` + плоские пути (~65 потребителей: api/{errorMapping,libraryWrite}, routes {libraryArchives,libraryPacks,reliefTemplates,structureTemplates}, bundle/*, worldBundleService, core/{app,container,templateRepositories}, dataModel/worldBuildingLayoutDefaults, scripts, ~30 tests).
- **Контракт:** пути; сервисные классы и FS-layout доменов (`structures_templates/`, `relief_templates/`) не меняются.
- **Проверка:** `grep "worldData.libraryPacks\|worldData\.<flat>" backend` = 0; compileall; `python -m unittest tests.test_library_packs_schema tests.test_canonical_library tests.test_library_packs_b3` (+ write/legacy/reinstantiate профили по grep).
- **Done:** `application/templateLibrary` собран; worldData корень очищен от template-library файлов.

### Шаг 4 — `application/worldBundle/` — выполнен 2026-10-17 (b7e36b53, 947f7332)

- **Цель:** bundle/exchange в отдельный домен, sibling `dataModel/worldBundle`.
- **ТЗ:** `docs/tz_world_bundle.md` WB-1/WB-9/WB-11/WB-13/WB-14.
- **Файлы:** `worldData/bundle/*` → `application/worldBundle/` (плоско: `handler/registry/order/errors/copyTokens/legacyTemplateBodies/worldCopyImport/worldLibraries` + подпакеты `archive/entity/library`); + `worldBundleService`, `bundleRemapService`, `deriveWorldUid`, `connectionGraphService`; rewrite (~30 файлов: routes `libraryArchives/perks/races/worlds`, `templateLibrary/packs/archive/archiveService` + `reliefWorldImportService`, `worldData/{raceService,worldPerkService}`, container, scripts, ~11 tests). Также правится `_EXEMPT` в `test_deterministic_ids.py` — slash-path `application/worldData/deriveWorldUid.py` → `application/worldBundle/deriveWorldUid.py`.
- **Контракт:** пути; `build_bundle_handlers`, `WorldBundleService`, `derive_world_uid` без изменений.
- **Проверка:** grep = 0; compileall; `python -m unittest tests.test_bundle_remap`.
- **Done:** `application/worldBundle` импортируется.

### Шаг 5 — `application/session/` — выполнен 2026-10-17 (b7e36b53, 947f7332)

- **Цель:** player/session сервисы из worldData.
- **ТЗ:** нет доменного ТЗ — граница по потребителям (`routes/characters.py`, `routes/sessions.py`).
- **Файлы:** `playerService.py`, `gameSessionService.py` → `application/session/`; rewrite (container, 2 routes, tests при наличии).
- **Проверка:** grep = 0; compileall; smoke импорта `from app.application.session import …`.
- **Done:** worldData корень без session-домена.

### Шаг 6 — `worldData/materialize/` — выполнен 2026-10-17 (2c46b927, 3c35e095)

- **Цель:** оркестрация материализации поверхности в одну папку.
- **ТЗ:** `docs/tz_terrain_generation.md` § TR-PAR; `docs/tz_climate.md` § CL-PAR.
- **Файлы:** `materializationContext`, `parallelPolicy`, `chunkComputePool`, `serialPersistQueue`, `terrainParallelLog`, `loadingProgress`, `persistResult`, `terrainBatchOrchestrator`, `climateBatchOrchestrator`, `worldSurfaceMaterializationOrchestrator`; rewrite (pack/*, routes/map, scripts/bake_world_pack, tests).
- **Проверка:** compileall; `python -m unittest tests.test_materialization_parallel tests.test_pack_climate_parallel`.
- **Done:** корень без materialize-файлов.

### Шаг 7 — `worldData/mapCells/` — выполнен 2026-10-17 (5273e35f)

- **Цель:** map_cells read/patch/persist facade в одну папку.
- **ТЗ:** `docs/tz_terrain_generation.md` § Persist cycle, WP-20.
- **Файлы:** `mapCellService`, `mapCellReadService`, `mapCellQueryFacade`, `patchStoreService`, `bootstrapMapCellWriter`; rewrite (container, pack/*, serialPersistQueue→materialize уже переехал).
- **Проверка:** compileall; профильные map-cell тесты (подобрать по `grep "mapCellService\|mapCellQueryFacade" tests/`).
- **Done:** корень без map-cell файлов.

### Шаг 8 — `worldData/persist/` — выполнен 2026-10-17 (0948a005, 1c5e79ba)

- **Цель:** settlement/connection/relief persist в одну папку.
- **ТЗ:** `docs/tz_city_generation.md` §11.5; `docs/tz_terrain_relief.md` §8c/R43.
- **Файлы:** `settlementPersistService`, `settlementPersistScope`, `connectionPersistService`, `connectionUids`, `persistReliefGrades`; rewrite (container, settlementOutdoor, pack/*).
- **Проверка:** compileall; `python -m unittest tests.test_settlement_topology` (+ найти persist-тесты).
- **Done:** корень без persist-файлов.

### Шаг 9 — `worldData/locations/` + `worldData/registries/` — выполнен 2026-10-17 (b440cc8f, 15767e4e)

- **Цель:** location-доступ и world-реестры развести по папкам.
- **ТЗ:** `docs/tz_locations.md` § Payload per type; `docs/tz_world_bundle.md` WB-13/WB-14 (reестры).
- **Файлы:** locations — `namedLocationService`, `locationPayloadAccess`, `settlementSkeletonAccess`, `settlementMapOccupancy`; registries — `worldService`, `raceService`, `worldPerkService`, `stateService`, `seedService`, `repairWorldDefaults`, **`worldColumnWrite`, `worldLookup`** (+2 к плану: W2 column-write seam и world lookup — потребители только worldService-семейство + templateLibrary, явный registries-домен); rewrite (container, routes, cascade/locationScope, scripts/debug_settlement).
- **Проверка:** compileall; `python -m unittest tests.test_location_payload_schema` (+ registry-тесты по grep).
- **Done:** корень без locations/registries файлов.

### Шаг 10 — `worldData/relief/` + хвост — выполнен 2026-10-17 (b440cc8f, 15767e4e)

- **Цель:** relief-каталог/алгебра в папку; закрыть остаток корня.
- **ТЗ:** `docs/tz_terrain_relief.md` § T-3c, R43, RELIEF-T-20.
- **Файлы:** `gradeCatalog`, `gradeInstanceMerge`, `gradeVertexSystem`, `parseObjectReliefPickPolicy` → `relief/`; `facingArrows.py`, `debugStructureRotations.py`, **`errors.py`** — остаются в корне (errors.py — общие ошибки worldData-домена, потребители api/session/worldData; вариант `application/errors.py` сломал бы «корень без strays» шага 17).
- **Проверка:** compileall; relief-тесты по grep `gradeCatalog|gradeVertex`.
- **Done:** корень worldData = только доменные папки + 3 задокументированных leaf-файла.

### Шаг 11 — разрез `core/container.py` на wiring-mixin'ы — в работе 2026-10-17

- **Цель:** убрать монолит-контейнер (~925 строк); проводка доменов живёт
  рядом с границами целевого дерева.
- **ТЗ:** правило `class-size-limit` (>300 строк тела класса); границы —
  по целевым доменам этого плана.
- **Файлы:** `app/core/container.py` → `app/core/container/{__init__,
  repositories,llm,engine,templateLibrary,packs,worldData,worldBundle,
  session}.py`; импорты доменов — уже финальные пути шагов 1–10.
  Уточнение списка 2026-10-17: один `worldData.py` собрал бы ~44 метода
  (~600 строк) — прямое нарушение `class-size-limit`, поэтому wiring
  дробится по доменам целевого дерева: `templateLibrary` (packs/services/
  snapshot/refResolver/import/legacy), `packs` (pack io + read facades +
  parent-light cache), `worldData` (domain services + orchestrators +
  transitions + persist), `worldBundle` (bundle + connection_graph).
  `errors.py` остаётся leaf'ом (см. шаг 10).
- **Контракт:** `container.<service>()` / `container.<repo>()` сигнатуры и
  lazy-семантика не меняются; `Container` = facade-класс от mixin'ов.
  Per-world фабрики (`pack_read_services`, `*_for(world)` и т.п.) уходят
  в `worldData.py` wiring без изменения API.
- **Проверка:** compileall; smoke `python -c "from app.core.container import Container"`; профильные тесты wiring по grep (`container` в tests/).
- **Done:** `container.py` монолита нет; ни один wiring-модуль > 300 строк.

### Шаг 12 — `pack/refine/` зонирование

- **Цель:** 36 плоских файлов → подпакеты по стадиям refine pipeline.
- **ТЗ:** `docs/tz_terrain_relief.md` (detailed/fine grade pipeline);
  `class-size-limit` (зоны в одном файле-пакете).
- **Файлы:** `refine/detailed/` — `detailedGrade*` (12) + `detailedJobUid`;
  `refine/fine/` — `fineChunk*` (4), `fineGradeCatalog`, `fineRefineResult`,
  `fineTerrainRefineOrchestrator`, `fineTileContext`, `fineTilePrep`;
  `refine/entry/` — `entryAnchorTracker`, `entryRefineOrchestrator`,
  `entryRingGeom`; `refine/chunks/` — `chunkRefine{Queue,Worker}`,
  `chunkSchedule`. Остаток (`gradeCellSlots`, `gradeRimRays`,
  `gridNeighborHalo`, `fineGradeSurface`, `pathCorridorSelect`,
  `pathHeading`, `columnBounds`) — плоско в `refine/` как shared;
  точная раскладка сверяется по импорт-связности на исполнении.
- **Контракт:** пути; поведение и сигнатуры не меняются.
- **Проверка:** compileall; refine-тесты по grep `refine|detailedGrade|fineChunk`.
- **Done:** `refine/` = 4 подпакета + ≤8 shared-файлов.

### Шаг 13 — сплит `pack/bake/packBakeLog.py` — выполнен 2026-10-17 — выполнен 2026-10-16

- **Цель:** 1440-строчный лог-дамп → подпакет по фазам bake.
- **ТЗ:** `class-size-limit` (смешение зон); `docs/tz_world_pack_storage.md`.
- **Файлы:** `packBakeLog.py` → `pack/bake/log/{__init__,compute,persist,
  worldMap,fineTerrain,wilderness,misc}.py`; `__init__` реэкспортирует
  все `log_pack_*` — точки импорта callers не меняются.
- **Контракт:** только перенос функций; тексты сообщений и extra-поля —
  байт-в-байт.
- **Проверка:** compileall; `grep "packBakeLog import"` — работает через
  пакетный `__init__` без правки callers.
- **Done:** ни один log-модуль > ~300 строк; импорты callers неизменны.

### Шаг 14 — `dataModel/worldPack/` группировка

- **Цель:** 36 плоских POJO → подпапки по поддоменам pack-модели.
- **ТЗ:** `docs/tz_world_pack_storage.md`; `docs/project_data_storage_tz.md`.
- **Файлы:** `worldPack/wire/` — cell/terrain/hydro/climate/locations
  wire-модели (`*Wire`, `mapCell*`, `mergeMapCells`, `paintedRoadEdge`,
  `territoryVolume*`, `worldBounds`, `worldSeamCopy`, `light*Tile`,
  `settlementStructure*`); `worldPack/bake/` — job/policy/plan
  (`packBake*`, `packJobUid`, `packReadPolicy`, `packTilePlan`,
  `packCompleteness`, `detailedBakeScope`, `gradePipelineStages`,
  `lightFineTilePolicy`, `parentLightRefinePolicy`, `pathHeadingPolicy`,
  `wildernessRefineStatus`, `layerPriority`); `worldPack/meta/` —
  `worldPackManifest`, `worldPackMetadata`, `worldMapResolutionSettings`,
  `worldGridSettings`. Rewrite импортов (~по grep `dataModel.worldPack`).
- **Контракт:** пути; поля/defaults POJO не трогаем (`dataModel-no-hardcode`
  — никаких поведенческих правок «заодно»).
- **Проверка:** compileall; `python -m unittest` профили pack/wire.
- **Done:** корень `worldPack/` = только `__init__.py` + 3 подпапки.

### Шаг 15 — `worldData/render/` внутренняя нарезка

- **Цель:** 24 flat-рендерера → подпапки по назначению.
- **ТЗ:** нет доменного ТЗ — граница по назначению (debug-визуализация).
- **Файлы:** `render/light/` — `light*` (4); `render/worldMap/` —
  `world*`, `worldMap*` (5); `render/pack/` — `*PackRenderer`,
  `location*`, `packMapGridRender` (5); корень — dump/ascii/symbols/misc
  (9). Точная раскладка по импорт-связности на исполнении.
- **Проверка:** compileall; smoke debug-render вызовов по grep.
- **Done:** `render/` = 3 подпапки + ≤9 shared-файлов.

### Шаг 16 — `generators/structure/` внутренняя нарезка — выполнен 2026-10-17 (624a46e1, b9369809) — выполнен 2026-10-17

- **Цель:** 17 flat-файлов корня структурного генератора → подпакеты.
- **ТЗ:** `docs/tz_building_generator.md`; `layer-boundaries` (генератор
  только materialize).
- **Файлы:** `structure/layout/` — `layout*` (3); `structure/shape/` —
  `shape*` (3); `structure/walls/` — `wall*` (2); корень — service,
  cell*, errors, orientation, postProcess, heightChecker,
  physicalTransition, gridRenderer (9). `StructureGeneratorService`
  (тело ~575 строк) — **не** разрезать здесь: поведенческий долг в
  Follow-up, этот шаг только перенос.
- **Проверка:** compileall; structure-тесты по grep.
- **Done:** корень `structure/` = 3 подпакета + ≤9 файлов.
- **Результат:** 8 модулей перенесены через `git mv` в `layout/`, `shape/`, `walls/`; импорты и строковые пути тестов обновлены. `StructureGeneratorService` не разрезан (только импорты). Старых dotted-path ссылок нет; compileall и `git diff --check` пройдены. 37 тестовых модулей / 359 тестов: 353 passed, 1 expected failure, 5 прежних ошибок SQL-фикстур (`building_templates.structure_type`); результат совпадает с чистым HEAD. Ветка `codex/worlddata-step-16-structure`, отдельный worktree; без коммита, ожидается «ок».

### Шаг 17 — stray-файлы `application/` корня — выполнен 2026-10-17

- **Цель:** `importResult.py` + `import_helpers.py` (shared
  import-контракты, ~10 потребителей) — из корня application в пакет.
- **ТЗ:** нет доменного ТЗ — граница по потребителям (bundle, mapCell,
  race/namedLocation services, api/schemas).
- **Файлы:** → `application/imports/{__init__,result,helpers}.py`
  (имя пакета — по вкусу мастера); rewrite ~10 импортёров.
- **Проверка:** compileall; smoke `from app.application.imports import …`.
- **Done:** корень `application/` без `.py`-файлов кроме `__init__`.

### Шаг 17a — application-потребители `api.schemas.imports` → `application.imports` — выполнен 2026-10-17

- **Цель:** убрать обратную зависимость `application → api`: 10 файлов
  читают `ImportResult`/`ImportError` через реэкспорт
  `app.api.schemas.imports` вместо SoT `app.application.imports.result`.
  Доводка шага 17: его rewrite шёл по старым путям
  `application.importResult`/`import_helpers` и api-пути не захватил.
- **ТЗ:** `layer-boundaries` (application не импортирует api); docstring
  `application/imports/result.py` — «services must not import from
  api.schemas».
- **Файлы (10):** `worldData/registries/{worldService,stateService,
  seedService}.py`, `worldData/mapCells/mapCellService.py`,
  `worldData/materialize/{climateBatchOrchestrator,
  terrainBatchOrchestrator,serialPersistQueue}.py`,
  `worldData/persist/{settlementPersistService,
  connectionPersistService}.py`,
  `worldBundle/connectionGraphService.py` — замена
  `from app.api.schemas.imports import …` →
  `from app.application.imports.result import …`.
- **Контракт:** `api/schemas/imports.py` остаётся реэкспортом
  (`PathImportRequest` + `ImportError`/`ImportResult`) — направление
  api → application корректно, не трогаем.
- **Проверка:** `grep "app\.api" backend/app/application` = 0;
  compileall; unittest профили импортёров (seed/world/mapCell по grep).
- **Done:** в `application/` нет импортов из `app.api.*`.

### Шаг 18 — `tests/` доменная нарезка

- **Цель:** 230 плоских тест-файлов → подпапки по доменам.
- **ТЗ:** нет — граница по тестируемому домену; зеркалить целевое дерево
  `application/`.
- **Файлы:** `tests/{libraryPacks,pack,terrain,structure,settlement,
  bundle,engine,cascade,…}/`; shared helpers (`canonicalCatalog.py`,
  `structureWire.py`, `template_domain_transport_fixture.py`) →
  `tests/helpers/` или корень. Каждая подпапка получает `__init__.py`
  (unittest discover требует packages).
- **Контракт:** имена тестов и содержимое не меняются; `import` внутри
  тестов — на финальные пути приложения.
- **Проверка:** `python -m unittest discover tests` — полный прогон,
  count тестов до/после совпадает.
- **Done:** корень `tests/` = `__init__.py`, helpers и доменные папки.

### Шаг 19 — синк документов и правил

- **Цель:** ссылки на новые пути в правилах, ТЗ, активных планах.
- **Файлы/места:** `.cursor/rules/template-pack-layout.mdc` («`worldData/ids`» → `app/ids`); docstrings `dataModel/libraryPacks/{packManifest,libraryPinEntry}.py`; `docs/project_data_storage_tz.md` §DET-1, `docs/tz_cascade_context.md`, `docs/tz_world_bundle.md`, `docs/tz_template_library_packs.md` — grep `worldData.` и правка упоминаний путей; активные планы `.cursor/plans/*.md` (не `-done`) с ссылками на старые пути; `.cursor/rules/project-context.mdc` — описание слоёв при необходимости.
- **Проверка:** `grep "worldData\.(ids|context|libraryPacks|bundle)" .cursor docs backend` = 0 (кроме исторических `-done` планов).
- **Done:** живая документация указывает на новые пути.

## Follow-up (не этот план)

- `dataModel` может импортировать `app.ids.uidKind.LibraryKind` напрямую —
  снять строковую валидацию `library_kind` в `LibraryPinEntry`/`PackManifest`
  (поведенческая правка, отдельный шаг/план).
- Binding-таблица cascade-движка (`_MATERIALIZE`/`_FOLDS` →
  `worldData.generators.utils`) — ужесточение направления зависимости
  (регистрация извне или перенос callables).
- `api/routes` достаёт до `worldData.generators.*`/`pack.*` напрямую
  (map.py, debug.py, locations.py) — отдельный долг тонких routes.
  `map.py` — 713 строк / 17 endpoints: аудит на встроенную логику
  (`layer-boundaries`: route = validate → service → DTO).
- `StructureGeneratorService` — тело ~575 строк (нарушение
  `class-size-limit`): layout + footprint + transitions. Поведенческий
  разрез по ответственности, отдельный план — не rename-механика.
- `WorldSlice` (`jsonValidation/worldSlices.py`, ~450 строк) — проверить
  долю оркестрации против POJO-исключения `class-size-limit`.
- `settlementOutdoor/` (14 файлов, uniform prefix `settlementOutdoor*`)
  — осознанно остаётся плоским: префикс-конвенция читаема, один домен.
- `Container`: per-world фабрики (`transition_service(world, …)`,
  `pack_read_services(world_uid)`, `*_for(world)`) и lazy-синглтоны —
  две семантики жизненного цикла в одном классе; после разреза на
  wiring-mixin'ы стоит развести их явно (отдельный слой/scope).
- Rename `packs/`↔`libraryPacks/` и имена подпапок — по вкусу мастера,
  стоимость одинакова при rewrite.

## Порядок и зависимости

**Условие входа — снято 2026-10-16.** Трек
[`plan-dependency-graph.md`](plan-dependency-graph.md) (pack-модель
библиотек: A/B/C-1..5/4a–4d/5a/5b/6/7) закрыт: шаги 6 и 7
`library-packs-model-done.md` выполнены 2026-10-16, их smoke-дефекты
зафиксированы и закрыты в `library-packs-67-smoke-debt-done.md`;
W2-0..4, G-1 и PBF-1..3 также закрыты. Основание блока (трек активно
правит те же файлы) отпало — шаги 3 и выше доступны.

Остатки трека, не гейтящие шаг 3:

- **C-6** (`pack/` subtree архива, уровень full) — вне критического пути;
  трогает `worldData/bundle/`, а не `libraryPacks/` и template services.
  Потенциально пересекается с шагом 4 (worldBundle) — решение о
  порядке за мастером.
- **5c** (world/pack override) — отложен в отдельное ТЗ contextual
  fallback, явно не блокирует.

Протухшие артефакты: скиллы
`.agents/skills/source-command-impl-libpack-6`, `-impl-5b-b7`,
`-impl-4d-l5` описывают уже сданные шаги и ссылаются на старые пути —
удалить/поправить при ближайшей уборке, до реструктуры не трогать.

Линейно 1→19 (+ доводка 17a). **Статус на 2026-10-17 (сверено с
кодом):** шаги 1–10, 13, 16, 17, 17a выполнены и смержены в `dev_structure`;
корень `worldData/` = 3 задокументированных leaf-файла (`errors.py`,
`facingArrows.py`, `debugStructureRotations.py`); stale-пути по всем
переездам = 0 (compileall + профильные тесты зелёные). Шаг 11
(container) — в работе (`container.py → container/` в дереве).
Открыты: 12 (refine), 14 (worldPack), 15 (render), 18 (tests), 19
(синк документов).

## Мультиагентный режим (несколько агентов параллельно)

Различать два вида независимости: **логическую** (разные домены/целевые
папки — свободный порядок) и **текстовую** (не пересекаются ли файлы при
repo-wide rewrite). Каждый шаг переписывает импорты во всех потребителях —
шаги с общими файлами-потребителями в параллельных ветках дадут
merge-конфликты, даже если домены разные.

**Безопасно параллельно (разные ветки, файлы не пересекаются):**

| Шаг | Почему безопасен |
|---|---|
| 5 (session) | Полностью разобщён: свои файлы, свои consumers |
| 13 (packBakeLog) | Re-export через `__init__` — **нулевой** внешний rewrite, чужие файлы не трогает |
| 16 (structure/) | Внутренняя нарезка `generators/`; потребители сами не переезжают |

**Логически независимы, но текстово связаны — только последовательно:**

- **3 ↔ 4**: `bundle/*` импортирует `libraryPacks` (`worldCopyImport`,
  `worldLibraries`, `libraryTemplateSection`, `copyTokens`,
  `legacyTemplateBodies`) — параллельно = конфликты на этих файлах.
  Порядок свободный (3→4 или 4→3), но не одновременно.
- **14 (worldPack)** vs почти всё: потребители размазаны по `pack/*`,
  корню worldData, tests — конфликтует с любым параллельным rewrite.
- **6–10 между собой**: свободный порядок, но общие потребители
  (`container` до шага 11, `pack/*`, routes) — последовательно чище.
- **12, 15** (refine, render): сами по себе независимы, но их файлы
  импортируют worldData-корень — если идут до 6–10, импорты
  перепишутся дважды. Не конфликт, но двойная работа; дешевле после
  6–10 или в паузах между ними.
- **17** (application-strays): крошечный rewrite (~10 файлов);
  потребители пересекаются с 3/4/6–10 — ставить в свободное окно, не
  параллельно с ними.
- **17a** (api.schemas доводка): 10 однострочных замен в тех же
  потребителях, что у 17 — то же правило окон.

**Рекомендуемая схема ускорения:**

```text
lane 1 (основная):  3 → 4 → 6 → 7 → 8 → 9 → 10 → 11
lane 2 (параллель): 5 ∥ 13 ∥ 16          — разные ветки, merge в любой момент
добивка после 11:   12, 14, 15, 17       — последовательно или в паузах
финал:              18 → 19              — один агент, после merge всех lanes
```

Два агента в одной ветке не работают: каждый rewrite трогает общий
пул файлов. Параллель = отдельная ветка/worktree на шаг, merge после
«ок» мастера.

Каждый шаг: `git mv` → repo-wide замена dotted-path → `grep` старого пути = 0 →
`compileall` → профильные unittest → короткий отчёт → ждать «ок».
