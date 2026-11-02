# Генераторные домены — исследование CRUD и уровней чтения

**Статус:** AS-IS STATIC RESEARCH, 2026-11-02. Поручение: исследовать CRUD в
генераторах после принятия архитектуры domain readers. Не новый owning план,
не API freeze, не разрешение изменения кода/production CRUD. Owning архитектура
readers — [GEN-BAKE-READ §15](./generator-public-bake-reads.md#15-принятая-архитектура-domain-readers-2026-11-02).

## 1. Вывод и границы исследования

Генераторы не образуют единый CRUD слой. Исследованные terrain/climate/hydrology/
settlement/structure services в основном вычисляют результаты в памяти.
Создание, изменение и удаление сохранённого состояния находятся у world/location/
transition application services, persist/job orchestration, SQL repositories и
Pack IO. Вызов generate не равен durable create, dict.update не равен storage update.

Прослежены HTTP входы worlds/locations/map, domain services, bake dispatch,
основные persist sinks и read candidates. Это не exhaustive dynamic call closure
всего backend: template libraries, gameplay modules и все repository implementations
не ревьюились целиком. Отсутствие операции ниже означает «не найдена в данном
исследованном public surface», а не доказательство отсутствия во всём проекте.

[Действующий Patch/Snapshot owning](./world-domain-patches-snapshots.md) сохраняет
владение CRUD за доменом; Patch не вызывает legacy writer для прямой мутации БД/
опубликованного состояния. Архивный [world-state-crud-transition](./world-state-crud-transition.md)
явно SUPERSEDED; его central CRUD и class map не восстанавливаются. Existing CRUD
описан как AS-IS, не одобрен как target runtime mutation route.

## 2. Generator services: что действительно происходит

Пути в ссылках — существующие production файлы; символы указаны явно.

| Домен / существующий service | Вход → результат | CRUD classification / caller evidence |
|---|---|---|
| [TerrainGeneratorService](../../backend/app/application/worldData/generators/terrain/terrainGeneratorService.py): generate_surface, generate_surface_chunk, generate_minimal | World/locations/heightmap/rect → list[MapCell] | Compute; не persisted read/create. generate_minimal вычисляет климат/terrain и использует defaults координат, не source read. generate_surface_chunk вызывается [TerrainBatchOrchestrator](../../backend/app/application/worldData/materialize/terrain/terrainBatchOrchestrator.py) |
| [ClimateGeneratorService](../../backend/app/application/worldData/generators/climate/climateGeneratorService.py): build_coarse_field, resolve_climate, sample_at_pole_field | Inputs/field → ClimateAnchorField, climate key, SurfaceClimateSample | Build/resolve/sample в памяти. Sample от caller-provided field — reuse алгоритма минимального чтения, но не public pinned persisted reader |
| [HydrologyGeneratorService.apply](../../backend/app/application/worldData/generators/hydrology/hydrologyGeneratorService.py) | World/heightmap/BasinSpecs/topology → HydrologyResult: bodies/unions/areas/floors/river facts | Bootstrap/preview solve; не water read и не storage CRUD. Нельзя вызывать для получения недостающих water facts в physics reader |
| [SettlementGeneratorService](../../backend/app/application/worldData/generators/assemblers/settlementAssembler/settlementGeneratorService.py): plan_occupancy_only, plan_slots_and_city_graph, generate_layout | World/NL/catalog → occupancy/topology/layout | Compute. Topology caller — [settlementOutdoorTopologyJob](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorTopologyJob.py). Комментарий service про persist в engine node — legacy текст, не accepted permission storage в ноде |
| [StructureGeneratorService.generate_from_template](../../backend/app/application/worldData/generators/structure/structureGeneratorService.py) | World/building/StructureTemplate → StructureLayout с levels/rooms/cells/transitions | Pure utility без repos/async. Caller [buildingAssembler](../../backend/app/application/worldData/generators/assemblers/buildingAssembler/buildingAssembler.py), также debugStructureRotations. Create layout не create persisted building |

## 3. Existing CRUD: публичные входы, владельцы, sinks

| Объект | C / R / U / D в AS-IS | Caller → owner → sink / ограничение |
|---|---|---|
| World/source settings | create; get_all/get_by_id/find_by_id; update/import_from_json(upsert); delete | [routes/worlds](../../backend/app/api/routes/worlds.py) → [WorldService](../../backend/app/application/worldData/registries/worldService.py) → [SqliteWorldRepository](../../backend/app/db/repositories/sqlite/worldRepository.py). Возвращается World либо WorldUpdateResult, не immutable published world contract |
| NamedLocation hierarchy | create; get_all/list_insert_order/get_by_id/get_children; update/import_from_json; delete | [routes/locations](../../backend/app/api/routes/locations.py) → [NamedLocationService](../../backend/app/application/worldData/locations/namedLocationService.py) → [SqliteNamedLocationRepository](../../backend/app/db/repositories/sqlite/namedLocationRepository.py). Проверка world, source validation/occupancy; CRUD ряда не доказывает update terrain/structure closure |
| Declared landcover region | AddRegion; чтение World declarations/manifest snapshot; UpdateRegion; RemoveRegion | routes/worlds.edit_declared_region → WorldService.edit_region → [apply_region_operation/DeclaredRegionEditor](../../backend/app/application/worldData/regions/declaredRegionEdit.py) → World repo + [StateChangeConsumer](../../backend/app/application/worldData/regions/stateChange/consumer.py). Remove declaration → state tombstone, не удаление baked artifact |
| Region runtime state | add_declared; region state repository reads; evaluate; tombstone/remove_declared | StateChangeConsumer owns state writes. remove без row сначала создаёт state, затем tombstone. Не generic delete и не read-side repair |
| Map patches | import/upsert_patch/save_generated; get_all/get_z_slice; save_pass/save_settlement_surface; clear | [MapCellService](../../backend/app/application/worldData/mapCells/mapCellService.py), [PatchStoreService](../../backend/app/application/worldData/mapCells/patchStoreService.py) → [SqliteMapCellRepository](../../backend/app/db/repositories/sqlite/mapCellRepository.py). clear удаляет map_cell_patches world; не Pack directory. save_generated insert-ignore; save_pass layer-specific upserts; terrain insert_only отвергается для wilderness |
| Terrain/climate/index Pack artifacts | writer write_* создаёт/заменяет; WorldPackReader read_*; overwrite/commit/save_manifest; object-specific public delete не найден | [routes/map.bake_world_pack](../../backend/app/api/routes/map.py) → [WorldSurfaceMaterializationOrchestrator](../../backend/app/application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py) → L0/detailed orchestrators → [WorldPackWriter](../../backend/app/application/worldData/pack/io/worldPackWriter.py). Atomic blob replacement не равно atomic world publication |
| Settlement C23/C24/C11 | plan_topology/materialize; legacy topology helpers/structure reads; skip/update jobs; public aggregate delete не найден | routes/locations generate-settlement(s), bake dispatch → [SettlementOutdoorOrchestrator](../../backend/app/application/worldData/settlementOutdoor/settlementOutdoorOrchestrator.py) → topology/packing jobs. write C23 SQL и settlement Pack — отдельные sinks |
| Legacy settlement persist | persist(scope)/persist_outdoor; reads для skip; upserts; delete не предоставлен | [SettlementPersistService](../../backend/app/application/worldData/persist/settlementPersistService.py) → MapCellService, locations repo, ConnectionPersistService. BUILDINGS пропускает существующие UID; не universal update aggregate |
| Connection graph | import_nodes/import_edges; get_nodes/get_edges/export; upsert; public delete в service не найден | [ConnectionGraphService](../../backend/app/application/worldBundle/connectionGraphService.py), [ConnectionPersistService.persist_graph](../../backend/app/application/worldData/persist/connectionPersistService.py) → node/edge/edge-cell repos. Bulk upsert не удаляет stale members сам по себе |
| Transition | create/read/update/delete; entries_of/for_level/for_node | [TransitionService](../../backend/app/application/worldData/transitions/transitionService.py) → ITransitionRepository. [TransitionReadService](../../backend/app/application/worldData/transitions/transitionReadService.py) combines SQL+explicit building Pack bindings, SQL выигрывает UID collisions; не pinned baked-only result |
| Pack ZIP import | import_zip; проверка manifest presence после extraction; замена файлов возможна; delete API нет | [routes/worlds.import_world_pack](../../backend/app/api/routes/worlds.py) → [PackImportService.import_zip](../../backend/app/application/worldData/pack/import_/packImportService.py). mkdir/extractall выполняются до manifest validation; это mutation entry, не read/preflight |

## 4. Сквозные mutation traces и последствия для contracts

1. **World update:** route→WorldService.update→normalize/merge/validate→invalidated
   tables. При grid change без force возвращает requires_force без save; с force
   сохраняет World, затем route отдельно вызывает MapCellService.clear. Это не
   доказанная atomic операция World+patches+Pack. Нельзя скрывать под reader.
2. **Region edit:** edit_region(validate_only) проверяет patch и возвращает без
   _update; обычный путь входит в editor transaction, пишет World и reconcile
   state. RemoveRegion меняет declaration и tombstone маскирует baked membership.
   Это существующий domain-specific reuse, не повод создавать общий CRUD router.
3. **Light/full:** route→bake_pack→materialize_pack_light/full→L0 orchestrator:
   planning capture/prepare, coarse climate, locations index, tiles и finalize.
   L0 loop переписывает planned tiles, а не только missing. Full application wrapper
   затем вызывает outdoor.plan_topology, если outdoor dependency подключена.
   Поэтому полная AS-IS full операция включает этот conditional C23 вызов;
   утверждение «сам L0 producer не строит C23» относится только к внутреннему L0
   component. Public read readiness не выводится из successful L0 report.
4. **Detailed:** wrapper capture/prepare→detailed.bake L2→freshness check и
   save_manifest→_maybe_materialize_c11 для settlement-like location. C11 exception
   упаковывается в MaterializeResult(status=error). Wilderness C11 не запускает.
   Следовательно уже сохранённый L2/manifest не доказывает завершение C11.
5. **Pack write:** write_location_terrain/write_wilderness_chunk обновляют blobs
   и manifest entries; settlement использует encode_settlement_structure_tmp затем
   publish_settlement_structure; grade sidecars имеют отдельные merge sinks.
   Publish в имени метода не доказывает accepted Snapshot publication protocol.
6. **Delete world:** route содержит явный TODO WP-DELETE-1: not FK-safe/not atomic;
   WorldService.delete делегирует delete world row. Не найдено общей cleanup
   транзакции SQL descendants+Pack+refs. Не выполнять destructive experiment.
7. **Clear map:** удаляет patches, baked terrain остаётся. Нельзя обещать «очистить
   сгенерированный мир» по этому методу. Delete NL также не доказывает очистку
   связанных Pack terrain/settlement artifacts или retained refs.

## 5. Read reuse: целая сущность → часть → минимум

Это evidence кандидатов, не назначение новых classes/NodeIds. Entity/part/unit
нужно определить в конкретном домене до exact API freeze.

| Домен / смысл | Whole / part / minimum в существующем коде | Что ещё не готово для принятой архитектуры |
|---|---|---|
| World/locations | WorldService.get_by_id; NL get_by_id/get_children/get_all | Это current SQL rows. Published immutable aggregate, revision binding и whole→part closure не обеспечены самим CRUD |
| Terrain | WorldPackReader location terrain/tile/chunk; MapCellQueryFacade scene/window/get_cell | Pack reader возвращает wires; gameplay facade merges layers/patches. Baked/raw и current merged contracts нельзя молча смешать |
| Climate | read_climate_coarse/read_climate_tile; sample_at_pole_field/anchor_field | Нельзя build field для компенсации missing в read. PackReadContext climate_tile_field ловит FileNotFound/ValueError→None: требуется раздельный error mapping |
| Water/hydrology | HydrologyResult содержит whole bodies и spatial facts после compute; принятый SP-1/EF-1 window contract | apply — solve, не reader. Whole water body и minimum-query executable ports этим не доказаны; не обещать готовый object-by-UID read |
| Settlement/structure | read_settlement_structure, read_building_interior_transitions; wire levels/rooms/columns | Storage whole/slice decode есть; immutable public aggregate и independent minimal structure queries требуют contract review. C23 SQL reload восстанавливает planner objects |
| Landcover region | WildernessRegionReadService.get_snapshot — manifest entry; outline — derived geometry | get_snapshot не целая authoritative region. outline вызывает entry.require_plan_inputs и prepare_landcover_inputs; исключить как готовый read-only public port |
| Connections/transitions | graph lists; TransitionService.read(uid), for_node/for_level/entries_of; SQL+Pack merged reader | Есть семантические unit/group запросы, пригодные для reuse. Нужны explicit current/published semantics и согласованность whole→part revision |

Domain reader может вернуть целую сущность metadata+verified refs, затем читать её
части в той же версии. Это не означает автоматически весь World как root DTO или
универсальный recursive reader. Minimal data может быть интервалом, relation,
column или другим фактом — не обязательной XYZ клеткой.

## 6. Disposition и вопросы для следующей приёмки

- **Reuse existing:** domain CRUD owners, validation, existing entity IDs, level/room
  contracts, coordinate/wire conventions, domain-specific query semantics.
- **Retain legacy отдельно:** debug/progress/outline/preparation и persist helpers;
  не переименовывать их в accepted readers и не удалять по результатам inventory.
- **Не создавать сейчас:** общий WorldState CRUD, central reader registry, generic
  Entity DTO, одинаковый C/U/D набор для всех generators, новые bake kinds.
- **Следующий архитектурный выбор:** какие existing entity aggregates принадлежат
  каждому домену, его минимальная read unit и raw/published/current view. Затем
  exact whole/part/minimum read contracts и reuse/class map. Не выбирать имена
  новых классов раньше этого решения.
- **Mutation OPEN:** domain C/U/D commands vs existing direct CRUD routing,
  invalidation dependent artifacts, staged apply/publication/rollback и retention
  при delete. Владельцы — соответствующие domains + Patch/Snapshot owning;
  эта инвентаризация не заменяет их решения и не разрешает bypass Snapshot.
- **Межплановые предложения отдельно:** синхронизировать TODO snapshot/shared CRUD
  в WildernessRegionReadService с active owning; доказать world/NL delete cleanup;
  определить adapter/error dispositions current SQL и baked Pack reads; предъявить
  существующие full/detailed nested operations для explicit DAG composition.
  Другие owning-планы и граф этим исследованием не менялись.

## 7. Проверка результата исследования

Статически прочитаны перечисленные implementations и route/caller paths; side
 effects traced до конкретных service/repository/Pack methods. Runtime reads,
CRUD requests, bake jobs, deletes и тестовые writes не выполнялись. Production
поведение не изменено. Полный динамический caller closure, concurrency/rollback
и публикационный protocol требуют отдельного evidence, не объявлены готовыми.

## 8. Повторная проверка read candidates — явный exclusion ledger (2026-11-02)

Основание: пользователь потребовал перепроверить утверждение о preparation и
скрытых ошибках. Повторно прочитаны bodies и вложенная цепочка planning.
Метки ниже относятся к возможности использовать метод **без адаптации** как
новый публичный read contract; это не утверждение, что legacy/debug поведение
само по себе дефектно. Production code не менялся.

### 8.1. CONFIRMED PREPARATION — не read-only public reader

**[WildernessRegionReadService.outline](../../backend/app/application/worldData/pack/read/wildernessRegionReadService.py), строки 32–52.**
При наличии manifest snapshot вызывается цепочка:

```text
outline
 → SurfacePlanningEntry.require_plan_inputs
 → capture_view + prepare_captured
 → prepare_captured_bundle
 → SurfacePlanningAssembler.prepare
 → _build
 → PlanningService.get_or_build
 → cache miss: executor.submit(_build, ...)
```

Проверенные definitions:
[SurfacePlanningEntry](../../backend/app/application/worldData/planning/composition/surfacePlanningEntry.py):
require_plan_inputs 82, prepare_captured 61;
[SurfacePlanningAssembler](../../backend/app/application/worldData/planning/composition/surfacePlanningAssembler.py):
_build 41, prepare_captured_bundle 145;
[PlanningService](../../backend/app/application/planning/service/planningService.py): get_or_build 181,
executor.submit 200. Cache hit может переиспользовать план; это не устраняет
возможность preparation на miss. После preparation outline загружает state,
формирует inputs и вычисляет outline. Pack writes/repair из этой цепочки здесь
не доказаны и не приписываются ей. Ранний return при отсутствии snapshot не
подготавливает планы.

**Disposition:** retain debug/derived operation; исключить как готовый public
persisted read. Требует отдельной границы explicit prepared inputs либо чтения
опубликованной geometry; выбор не принят. `get_snapshot` этого же класса не
вызывает preparation — не переносить exclusion всего класса на каждый метод.

### 8.2. CONFIRMED ERROR CONFLATION — ошибки превращаются в absence

| Метод и existing source | Точное поведение | Метка / disposition |
|---|---|---|
| [load_parent_light](../../backend/app/application/worldData/pack/read/parentLightLoad.py):26 | FileNotFoundError→None; OSError/ValueError из read_world_map_tile логируются и тоже→None. Ошибки ParentLightTile.from_cells вне try не подавляются | **ERROR→NONE**. Нет preparation; error mapping не reuse для public reader |
| require_parent_light, тот же файл:70 | Вызывает load_parent_light; любой None превращает в MissingParentLightError, включая read/decode failure, уже сведённые к None | **ERROR→MISSING EXCEPTION** транзитивно; retain legacy preparation helper |
| [PackReadContext.climate_tile_field](../../backend/app/application/worldData/pack/read/packReadContext.py):65 | Нет файла→cached None; FileNotFoundError/ValueError при decode→cached None. Прочие OSError не ловит | **DECODE ERROR→NONE**. Не называть подавлением всех ошибок; нужна раздельная absence/error политика |

### 8.3. CONFIRMED ABSENCE CONFLATION — потеря declared blob не отделяется от пустоты

Здесь методы обычно не ловят arbitrary corruption/OS error. Проблема точнее:
публичному контракту невозможно отличить допустимое отсутствие от потери уже
объявленного artifact по одному полученному None/[]/False. Некоторые debug outputs
сохраняют flags, но не поднимают требуемый public Error.

| Метод / source | Проверенное поведение | Disposition |
|---|---|---|
| [PackReadContext.climate_field](../../backend/app/application/worldData/pack/read/packReadContext.py):56 | FileNotFoundError→cached None; ValueError/прочие OSError распространяются | **MISSING FILE→NONE**, не blanket error swallow. Нужна проверка publication declaration |
| [WorldMapPackReader.sample_world_map](../../backend/app/application/worldData/pack/read/worldMapPackReader.py):35 | FileNotFoundError→None; отсутствующий sample также None | **FILE ABSENCE/SAMPLE ABSENCE CONFLATED** |
| WorldMapPackReader.world_map_contribution:43 | FileNotFoundError→None; отсутствие sample/вклада также None | **FILE ABSENCE/NO CONTRIBUTION CONFLATED**; это existing gameplay fallback, не baked completeness |
| WorldMapPackReader.surface_cells_for_tile:94 | FileNotFoundError→[]; side<=0 также [] | **FILE ABSENCE/EMPTY CONFLATED**; decode errors в общем случае не ловит |
| [PackRenderReadFacade.read_locations_index](../../backend/app/application/worldData/pack/read/packRenderReadFacade.py):83 | Нет index файла→LocationsIndexWire() | **MISSING INDEX→EMPTY INDEX**; valid empty index и missing index не различаются по результату |
| PackRenderReadFacade.try_world_map_source:92 | Для manifest entry с world_map_path FileNotFoundError логирует, increments missing_blobs, пропускает tile и продолжает render source | **DECLARED BLOB SKIPPED**; неполный render не public found |
| PackRenderReadFacade.has_location_terrain:153 / try_location_terrain:163 | has проверяет entry/path+is_file; try при false→None до decode | **DECLARED BLOB ABSENCE→NONE**; это не catch decode error |
| PackRenderReadFacade.has_settlement_structure:201 / try_settlement_structure:211 | has entry/path+is_file; false→None; race FileNotFoundError после has логируется и→None | **DECLARED BLOB ABSENCE→NONE**; прочие errors не blanket swallow |
| [SettlementStructureRaster.contribution](../../backend/app/application/worldData/pack/read/settlementStructureRaster.py):25 | Для подходящего manifest structure entry FileNotFoundError из _index_for→continue; в итоге возможно None | **DECLARED BLOB SKIPPED**. Raster/cache — допустимая read-side projection; проблема в loss semantics |
| [PackDebugReadFacade.column_has_merged_data](../../backend/app/application/worldData/pack/read/packDebugReadFacade.py):119 | FileNotFoundError первого tile read→side из manifest; sample_world_map затем→None→False | **TRANSITIVE ABSENCE→FALSE**; не evidence отсутствия данных во всей column |
| [PackFineTerrainReadFacade.read_wilderness_chunk](../../backend/app/application/worldData/pack/read/packFineTerrainReadFacade.py):57 | Нет blob→ok=True, blob_on_disk=False, column_count=0, даже при manifest ref | **DEBUG FLAGS, NO PUBLIC ERROR**; отсутствие не полностью скрыто, но public contract не соблюдён |
| PackFineTerrainReadFacade.read_location_terrain:116 | Есть entry, нет blob→ok=True, blob_on_disk=False, column_count=0 | **DEBUG FLAGS, NO PUBLIC ERROR**; нельзя брать только count/ok как public verdict |

Все эти методы retain в existing gameplay/render/debug use. Не удалять fallback
и не менять общий API по этой инвентаризации; для нового reader разделить
unpublished scope absence и declared artifact loss до применения fallback.

### 8.4. CORRECTION — capture/probe не preparation

**[PackLoadingProgressFacade.get_loading_progress](../../backend/app/application/worldData/pack/read/packLoadingProgressFacade.py):84**
при locations!=None и nonempty manifest вызывает SurfacePlanningEntry.probe_extent.
**probe_extent:52** выполняет capture_view + report_surface_diagnostics + extent_status;
его body не вызывает prepare_captured/prepare/get_or_build и не проектирует working
maps. Затем classifier вычисляет expected tile sets через PackTilePlanner.plan.

Метка: **CAPTURE/PROBE + CLASSIFICATION, НЕ CONFIRMED PREPARATION**. Предыдущее
сокращение «planning probe» нельзя читать как «подготавливает планы».
Он всё равно не ready public baked reader: возвращает counters/classification,
не полный verified data/ref результат. Ошибки decode manifest/index здесь не
преобразуются общим catch в missing. Наличие Capture само по себе не доказывает
persist/write/repair; такие эффекты этому методу данным audit не приписываются.

**prepare_landcover_inputs** отдельно также не preparation планов:
[landcoverInputs](../../backend/app/application/worldData/regions/inputs/landcoverInputs.py):
это binding state snapshot к working.landcover.inputs. Preparation в outline
доказана по require_plan_inputs, а не по слову prepare в названии binding helper.

### 8.5. Контрольные примеры: что не попало в exclusion

- WorldPackReader.read_world_map_tile/read_location_terrain/read_wilderness_chunk/
  read_climate_*: storage decode; kind mismatch и IO/decode exceptions выходят
  наружу. Нет подтверждённых hidden bake/repair calls в проверенных bodies.
  Отдельные limitations publication pinning/mutable wires сохраняются.
- PackReadContext.reader_for: создание storage reader и process cache; не bake.
- WildernessRegionReadService.get_snapshot: manifest lookup без require_plan_inputs.
- locationsIndexRead.load_locations_index: missing file→None, но JSON/validation
  errors не swallowed. Для public completeness всё равно нужен declaration context.
- mapCellToFineTerrainWire._column_surface_attrs catches invalid facing→None,
  но это write-side conversion helper, не самостоятельный read API; не включать
  в список публичных read error bugs только из-за папки pack/read.

Итог: confirmed preparation — outline (через plan build path); confirmed
read/decode failure conflation — load/require_parent_light и climate_tile_field;
остальные явно размечены как file-absence/debug/fallback semantics. Проверка
статическая; сценарии runtime fault injection не запускались, код не менялся.
