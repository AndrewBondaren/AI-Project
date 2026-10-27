# Архив отменённой схемы общего World State CRUD

Статус: SUPERSEDED, 2026-10-27. **Не план реализации и не действующие
архитектурные требования.** Актуальное решение —
[новый план](world-domain-patches-snapshots.md): DAG вызывает domain.read/patch
напрямую; контракты принадлежат доменам; WS не маршрутизирует чтение и
не обращается к БД. Snapshot сохраняет patch-операции всех доменов.

Прежние WorldStateService/IWorldStateRead, WS adapters, DB-bound context и
WorldStateUnitOfWork отменены. Наблюдения о существующих SQL/типах ниже —
только инвентаризация; отдельные доменные требования требуют сверки с ТЗ.
Никакие прежние DTO/paths/WS-1…WS-5 отсюда не исполняются автоматически.

<details>
<summary>Архив прежнего проекта и его ревью</summary>

# World State CRUD — WS-0: контрактный ledger для приёмки

Статус: REVIEW REQUIRED, 2026-10-27. Подготовка WS-0 по просьбе мастера.
Это документальный шаг: runtime, SQL, DAG, fixtures и tests не изменялись.
WS-0/WS-0A не объявлены DONE; WS-1 не разрешён этим документом автоматически.

Уточнение мастера 2026-10-27: **сначала архитектура, только затем конкретные
реализации**. Таблицы existing backends/SQL и варианты D1/D2 ниже — материал
инвентаризации, не принятый выбор реализации. Сначала согласуются назначение
WS, domain/layer boundaries, публичные входы/выходы, data flow и совместимость
с GEN DAG, владельцы coordination/UOW/errors. Затем уточняются concrete
bindings и implementation ledger; код начинается после приёмки архитектуры.
Переиспользование DB rows не считается архитектурным решением по умолчанию.

Пересмотр 2026-10-27: [transition §8](world-state-crud-transition.md#8-пересмотр-архитектуры-и-последовательности-2026-10-27)
фиксирует исправленные R1/R2 и открытые architecture gaps R3–R8. Этот файл —
инвентаризация и набор предложений, **не принятый DTO freeze**: даже подробно
выписанное поле/overload/SQL binding не считается утверждённым архитектурой.

Основной порядок: [transition](world-state-crud-transition.md) §5.
Архитектура, capability/UOW и patch semantics:
[WS-0A](world-state-crud-capabilities-uow.md) §7–13.
Предыдущий [анализ](world-state-crud-analysis.md) — исторические findings;
его девять вопросов уже получили design-ответы в WS-0A §13.
Ниже отделены проверенные existing contracts, предлагаемый точный freeze
и оставшиеся решения. Имена target не означают существования реализации.

## 1. Норматив и граница приёмки

- `docs/tz_world_snapshot.md` — «Обязательное разделение ответственности —
  gate каждого шага WS», «Общий World State CRUD и snapshot lifecycle».
- `docs/tz_patch_system.md` — «Владельцы сбора патчей — только DAG и debug API»,
  «World State CRUD: capabilities и atomic command».
- `docs/tz_world_pack_storage.md` — WP-20, Read path, WP-13, Patch Store.
- `docs/tz_terrain_generation.md` — Surface planning/cache, TR-PAR-6,
  TR-PERF-DEBT-4 / Insert path matrix.
- `docs/tz_terrain_hydrology.md` — C2: surface hydrology, не runtime fluid volume.
- `docs/tz_locations.md` — named_locations; existing BundleNamedLocation.
- `docs/tz_world_generation_dag.md` — «Generator library + DAG callers»,
  «Три входа», «Gate: DAG»; `.cursor/rules/dag-generator-interface.mdc`.
- Правила: layer-boundaries, contract-creation, code-gates, folder-composition.

Новые доменные defaults/жидкостные правила не проектируются. Snapshot selector,
snapshot isolation, materialization и arbitrary cross-domain batch вне CRUD.
Чтение текущего состояния не обещает consistent snapshot SQL + pack.

Полный freeze нельзя принять, пока остаются решения D1–D4 (§9).
Подготовленный ledger — конкретный вход их приёмки, не разрешение выбирать
публичные payload-типы или трактовать bypass во время WS-1/WS-4.

### 1.1 Совместимость WS с GEN DAG — обязательное условие (мастер, 2026-10-27)

WS не меняет архитектуру вызова генераторов ради своего storage-контракта.
DAG, bake и debug HTTP остаются consumers одного стабильного application
интерфейса; assembler/planner/worker internals и storage API им не раскрываются.
Debug handler тонко вызывает тот же интерфейс, который использует DAG.

Production master/player flow проходит через DAG. Debug HTTP — инструмент
разработчика, не UI мастера; переобъявлять обычный CRUD/import route как debug
для обхода этого требования запрещено. In-process tests pure logic не являются
альтернативным production persist entry. Разрешение debug entry не даёт WS
права подключить к нему product flow.

Pure generator получает подготовленные значения/доменные inputs; не получает
WorldStateService, SQL repository, session или ExecutionState и не делает IO.
Existing `(World, ...)` signature сама по себе не нарушает pure contract:
существенно отсутствие IO и persistence в compute. Это не разрешение связать
стабильный generator API с новым WS-specific metadata wrapper. Получение и
преобразование metadata остаются вне compute, в owning application boundary.

WS read не выбирает момент generate, не делает materialization. Materialization
сохраняет целый вызов existing orchestrator и его publication protocol; SQL UOW
WS не заменяет C19/file publication или атомарность хода. PatchSet собирают
DAG/debug API, не WS facade, generator или storage adapter. DAG wiring и ноды
остаются за Gate G1–G5; WS не снимает gate и не проектирует их internals.

Статус общего DAG-документа — draft, но явные утверждённые инварианты/правила
выше обязательны. Старые node tables и interim SQL paths не становятся
эталоном только из-за существования в checkout. Расхождение с WS фиксируется
как незакрытый контракт, а не устраняется ослаблением GEN DAG.

## 2. Инвентаризация существующих типов

Пути далее относительно `backend/app/`.

| Смысл | Existing тип / файл | Решение для WS |
|---|---|---|
| UID сущности | `EntityUid`, dataModel/identity/uid.py | Переиспользовать для новых world/location/region UID; не новый UID alias |
| Fine-координата | `FineGridCoord`, `FineX/FineY/FineZ`, dataModel/spatial/grid/coordinateTypes.py | FineCellScope содержит одну координату; int conversion на backend boundary |
| Surface-координата/прямоугольник | `SurfaceGridCoord`, `SurfaceGridRect`, тот же файл | Не смешивать gx/gy с fine x/y |
| Coordinate space | `CoordinateSpace`, dataModel/spatial/grid/coordinateSpace.py | Existing enum; LOCATION_FINE_GRID требует отдельного binding (§3) |
| Merge payload/source | `MergedCellView`, `CellContribution`, `MapLayerKind`, dataModel/worldPack/{wire/mergeMapCells,bake/layerPriority}.py | Возвращать existing merged view, не копировать поля в WS Cell DTO |
| Raw L2 | `FineTerrainChunkWire`, dataModel/worldPack/wire/fineTerrainChunkWire.py | Existing payload, без merge/overlay |
| Raw L0 | `WorldMapCellWire`, dataModel/worldPack/wire/worldMapCellWire.py | Existing payload, отдельный query от L2 |
| Pack metadata | `WorldPackMetadata`, `WorldPackManifest`, dataModel/worldPack/meta/ | Metadata не должна decode terrain blob |
| Region state | `RegionState`, dataModel/regions/regionState.py | Возвращать existing POJO, включая tombstones; не новый WS state |
| Region materialization projection | `StateSnapshotEntry`, application/worldData/generators/terrain/landcover/types.py | Только existing operation-local projection после общего read; не public WS DTO |
| Region edit | `AddRegion/UpdateRegion/RemoveRegion`, `DeclaredRegionEdit`, dataModel/terrainMasks/regions/edit.py | Переиспользовать op/name/region и existing name normalization |
| Patch provenance | `MapCellPatchLayerKind`, `MapCellPatchLayerPolicy`, dataModel/worldPack/wire/mapCellPatchLayerKind.py | Strict enum для нового входа; default из policy, не permissive unknown→STRUCTURE |
| Mutable registry refs | `TerrainKey`, `MaterialKey` | Existing aliases; не новые bare str |
| Building element | `StructureElement`, dataModel/locations/structure/enums/buildingElement.py | Existing enum для нового delta |
| Hydrology | `MapCellHydrology`, dataModel/hydrology/mapCellHydrology.py | Existing surface semantics; dict только у DB mapper |
| Source location | `BundleNamedLocation`, dataModel/locations/namedLocation/bundleNamedLocation.py | Existing authored wire model; не объявлять тождественным полной DB row |
| Full world/location rows | `World`, `NamedLocation`, db/models/ | Возвращаются existing services; нет готового полного чистого WS source DTO, D1 |
| Region evaluation | `RegionEvaluation`, `SpatialEvaluation`, application/worldData/regions/stateChange/contracts.py | Existing application context с WorkingFields; нельзя импортировать в dataModel, D2 |
| Evaluation result | `EvaluationResult`, application/worldData/regions/stateChange/consumer.py | state + children + materialize_signals; не терять сигналы при wrapping, D2 |
| Validation diagnostics | `FieldPathError`, dataModel/validation/diagnostics/fieldPathError.py | Existing typed diagnostic; не dict/message parsing |

`BundleNamedLocation` — authored wire с defaults/validators/IgnoreOnWire,
`NamedLocation` — persisted/runtime row. Подмена одного другим требует
проверки round-trip всех полей, в том числе system/display description и
location_payload. `World` содержит также несхематизированные legacy JSON
колонки: списка planning POJO недостаточно для full-world CRUD/export.

## 3. Address/scope: точный предлагаемый контракт

`dataModel/worldState/address.py`:

- `WorldStateAddress(world_uid: EntityUid, scope: WorldScope)`.
- World-level queries несут `world_uid` напрямую: не выдумывать object UID
  для world-wide read. Address используется только у scoped queries/commands.

`dataModel/spatial/query/worldScope.py`:

| Variant / discriminator `kind` | Поля | Допустимость |
|---|---|---|
| ObjectScope / `object` | `domain: Literal["location", "region"]`, `object_uid: EntityUid` | Точная object metadata/state identity; domain dispatch без произвольной строки |
| ChunkScope / `chunk` | `tile: SurfaceGridCoord`, `cx: int`, `cy: int` | cx/cy >= 0 и внутри tile согласно metadata; размер не передаётся caller |
| AreaScope / `area` | `space: CoordinateSpace`, `bounds: GridBBox`, `z_min: FineZ`, `z_max: FineZ` | Первый merged area read поддерживает WORLD_FINE_GRID; все bounds inclusive |
| FineCellScope / `fine_cell` | `position: FineGridCoord` | WORLD_FINE_GRID задан типом scope; не location-local |

`GridBBox` остаётся existing inclusive value, coordinate space задаёт AreaScope.
Не создавать второй bbox. Reverse bounds/negative chunk index — InvalidInput
на boundary; не молчаливое переставление min/max. WORLD_SURFACE_GRID area и
LOCATION_FINE_GRID area в первом binding → UnsupportedOperation: generic CRUD
не конвертирует z/локальный origin и не определяет footprint. Raw L0 tile query
имеет SurfaceGridCoord и не masquerades как fine area. Object→footprint read
не заявлен до exact owner/public method; object metadata доступна отдельно.

Запрошенный LOD не поле WorldScope. Representation задаётся query variant:
merged fine query допускает existing L0 fallback, raw L2 никогда им не заменяется.

## 4. Read query → result → exact backend

### 4.1 Общая форма результатов

Предлагаемые tagged values в `dataModel/worldState/query.py`:

- `Found[T](kind: Literal["found"], payload: T)`.
- `Missing(kind: Literal["missing"], reason: MissingReason)`;
  MissingReason: WORLD_NOT_FOUND / OBJECT_NOT_FOUND / CELL_NOT_FOUND /
  PACK_NOT_FOUND / CHUNK_NOT_FOUND / REGION_NOT_FOUND.
- `UnsupportedOperation(kind: Literal["unsupported_operation"])`.
- `ReadOutcome[T] = Found[T] | Missing | UnsupportedOperation`.

Result aliases семейства сохраняют payload type и overload, не один
`Found[World | RegionState | MergedCellView | ...]`. Discriminators — Literal
или enum, не string dispatch/Any. Found(empty tuple) — успешный пустой набор;
не заменяет Missing world или неподключённый backend. Отсутствующая capability
на read-only consumer проверяется typing, а отсутствие binding на общем
facade даёт UnsupportedOperation.

| Query discriminator / точные поля | Payload Found | Existing backend / mapping |
|---|---|---|
| CellQuery `merged_cell`, address с FineCellScope | MergedCellView | resolve world один раз; MapCellQueryFacade.get_cell(world,x,y,z); empty.has_any_data()==False → CELL_NOT_FOUND |
| AreaQuery `merged_area`, address с AreaScope | tuple[MergedCellView,...] | PatchStoreService.get_patches_map_in_bbox(world_uid,x0,x1,y0,y1,z0,z1); построить coord→patch/None; MapCellQueryFacade.get_cells(world,patches); фильтр existing has_any_data |
| SceneQuery `merged_scene`, world_uid, center: FineGridCoord, xy_radius: int, z_below: int\|None, z_above: int | tuple[MergedCellView,...] | MapCellQueryFacade.get_scene_volume(world,x,y,z,xy_radius=...,z_below=...,z_above=...); default из SceneVolumePolicy, z_below=None сохраняет n_base(world) |
| ChunkQuery `raw_fine_chunk`, address с ChunkScope | FineTerrainChunkWire | PackReadContext.has_pack_for(world), reader_for(world), WorldPackReader.chunk_exists(gx,gy,cx,cy), read_wilderness_chunk(gx,gy,cx,cy) |
| WorldMapTileQuery `raw_world_map_tile`, world_uid, tile: SurfaceGridCoord | tuple[int, list[WorldMapCellWire]] | WorldPackReader.read_world_map_tile(gx,gy); int — existing side; payload не новая cell schema |
| PackManifestQuery `pack_manifest`, world_uid | WorldPackManifest | PackReadContext.has_pack_for(world); reader_for(world).manifest; без decode chunks |
| RegionQuery `region_state`, address с ObjectScope(domain=region) | RegionState | IRegionStateRepository.get(world_uid,region_uid), None → REGION_NOT_FOUND; state_from_row |
| RegionsQuery `region_states`, world_uid, region_uids: tuple[EntityUid,...] | tuple[RegionState,...] | get_many(world_uid,region_uids), state_from_row; отсутствующие UID не fabricated; включая tombstones |
| WorldRegionsQuery `world_region_states`, world_uid | tuple[RegionState,...] | get_by_world(world_uid), state_from_row; включая tombstones; именно этот полный query у materialization |
| MetadataQuery `world_metadata`, world_uid | D1 | WorldService.get_by_id; context.world reuse; full-row payload пока не frozen |
| ObjectQuery `location`, address с ObjectScope(domain=location) | D1 | NamedLocationService.get_by_id(world_uid,location_uid) |
| LocationsQuery `locations`, world_uid | tuple[D1,...] | NamedLocationService.get_all(world_uid); не менять порядок existing API молча |
| LocationChildrenQuery `location_children`, world_uid, parent_uid: EntityUid | tuple[D1,...] | NamedLocationService.get_children(world_uid,parent_uid); missing parent не Found(empty) |

Каждая строка — отдельный overload `read(query: ExactQuery) -> ReadOutcome[ExactPayload]`
на IWorldStateRead, service, query facade и соответствующем backend read port.
World resolve отсутствующего world → WORLD_NOT_FOUND до port read;
metadata adapter использует уже загруженный context.world. Ports получают
`ResolvedWorldReadContext`, без собственного повторного world lookup.

`SceneQuery`, raw L0 и manifest — явная детализация семейства queries:
они нужны существующим scene/raw/metadata callers и не являются materialize.
Raw patch row **не включена** в public read: CellContribution фильтруется по
read visibility, полной persistence row владеет ICellPatchStorage в UOW.
Existing raw administrative exports остаются отмечены в caller ledger до D1/D3.

### 4.2 Missing, corruption и existing fallback

- Только WorldDataNotFoundError на world resolve → WORLD_NOT_FOUND;
  та же ошибка location lookup → OBJECT_NOT_FOUND. Не ловить общий ValueError.
- `chunk_exists=False` → CHUNK_NOT_FOUND. Отсутствующий pack → PACK_NOT_FOUND.
  FileNotFoundError именно запрошенного blob после successful existence check
  допустимо отобразить в CHUNK_NOT_FOUND (TOCTOU); decode/codec/validation/
  permission error пробрасывается. Missing manifest при concurrent replacement
  не маскировать как missing chunk.
- Raw L0: missing exact tile path → CHUNK_NOT_FOUND; malformed payload — exception.
- Canonical merged backend сохраняет его existing missing fine/location blob
  fallback и WP-20 precedence. Adapter не добавляет fallback и не выдаёт
  source_layer за точный LOD всех полей: использовать field_sources.
- Invalid query construction — typed boundary diagnostic; не Missing.
- WorldRegionsQuery Found(()) означает пустой SQL store. Unsupported/Missing/
  storage error не превращаются в пустой StateSnapshotEntry mapping.
- Async interface допускает sync disk/decode делегирование в owning task;
  нет implicit executor, read-generate или planning внутри read adapters.

### 4.3 PC-11 binding текущего checkout

SurfacePlanningEntry/WorkingFields **уже существуют**, в отличие от состояния
старого world-state-crud-analysis.md. Это не evidence WS cutover:
worldState каталогов/общего port сейчас нет.

`load_region_state_snapshot` сейчас принимает repo|None и делает
get_by_world; функция сама строит readonly MappingProxyType StateSnapshotEntry.
Target после WS-3: `load_region_state_snapshot(read: IWorldStateRead,
world_uid: EntityUid) -> Mapping[str, StateSnapshotEntry]`, один полный
WorldRegionsQuery; existing projection остаётся в regions/regionStateSnapshot.py.
None backend→empty fallback в новом binding не сохраняется.

Operation-local mapping обязателен на вызове fine runner; read один до tiles,
scene/path/internal drain; самостоятельная operation читает заново. WS-3
не меняет fingerprints/projection и не делает SQL на каждую клетку.

## 5. Mutation freeze: данные, результаты, handlers

### 5.1 Delta и patch commands

Existing target `dataModel/mapCells/patch/cellPatchDelta.py`, без DB imports:

| Поле CellPatchDelta | FieldChange[value type] |
|---|---|
| system_terrain | TerrainKey |
| system_material | MaterialKey |
| system_building_element | StructureElement |
| temperature_base | int |
| rainfall | int |
| location_uid | EntityUid |
| hydrology | MapCellHydrology |
| travel_modifier_override | float |
| is_structural | Literal[True] |

FieldChange[T] = Keep(kind=`keep`) | SetValue[T](kind=`set`,value:T) |
ResetOverride(kind=`reset`). Каждое поле delta по умолчанию Keep; None
не значение SetValue. Raw unknown fields/unknown enum values отвергаются
boundary validation, не теряются через extra=ignore. Температура/осадки —
existing int, без новых диапазонов; nonfinite travel modifier отвергается.

Target commands в `dataModel/worldState/mutation.py`:

| Метод / command.kind | Поля | Семантика / handler |
|---|---|---|
| create / CreateCellPatch `create_cell_patch` | address: FineCell address, delta: CellPatchDelta, layer_kind: MapCellPatchLayerKind\|None=None | CREATE_ONLY SQL row; существующая patch → AlreadyExists |
| update / UpdateCellPatch `update_cell_patch` | те же | UPDATE_ONLY; отсутствующая patch → NotFound |
| update / UpsertCellPatch `upsert_cell_patch` | те же | Explicit UPSERT; не alternate default create |
| delete / ResetCellPatchFields `reset_cell_patch_fields` | address, fields: frozenset[CellPatchField] | Перечисленные mutable fields → ResetOverride, остальные Keep; отсутствующая patch — Applied(changed=False) |
| delete / ResetCellPatch `reset_cell_patch` | address | Удаление всей SQL patch row, включая preservation-only payload; pack не удаляется; absent → Applied(changed=False) |

`CellPatchField` — закрытый enum ровно девяти полей таблицы; существует
только у selective intent, не общий список SQL-колонок. Пустой fields set /
delta целиком Keep без explicit stamp — InvalidInput, без записи. Reset
всей строки — отдельное явное намерение, не способ очистки по read has_data.
SetFalse для structural — InvalidInput; Reset пишет model default False;
base structural-OR сохраняется. Model defaults/NOT NULL/empty row predicate
ровно по WS-0A §10, не новые значения из этого документа.

Все patch commands → WorldCellAdapter → CellPatchMutationHandler.apply →
ICellPatchStorage → CellPatchStorageAdapter → repository. Root SQL UOW
охватывает existence/mode check/read/write/readback/cleanup, не только UPDATE.
При all-reset пустой row удаляется по полному MapCell.has_patch_payload.
Applied не обещает materialized fine cell; SQL patch и base presence независимы.

### 5.2 Остальные команды: exact existing binding и открытые payload

| Метод / target command | Existing backend | Что нельзя потерять / состояние freeze |
|---|---|---|
| create / CreateWorld | WorldService.create(data) | prepare_import/normalize/_save/reconcile; typed source payload D1 |
| update / UpdateWorld | WorldService.update(world_uid,data) | requires_force, warning, map_cells_invalidated; полный atomic owner D4 |
| delete / DeleteWorld(world_uid) | WorldService.delete(world_uid) | existing FK failure не success; не обещать world cascade/purge |
| create / CreateLocation | NamedLocationService.create(world_uid,data) | existing _from_wire validation + occupancy; payload D1 |
| update / UpdateLocation | NamedLocationService.update(world_uid,location_uid,data) | immutable UID/created_at; omitted vs null vs default D1 |
| delete / DeleteLocation(world_uid,location_uid) | NamedLocationService.delete(world_uid,location_uid) | existing world ownership check; FK/storage error выходит наружу |
| create/update/delete / AddDeclaredRegion/UpdateDeclaredRegion/RemoveDeclaredRegion | WorldService.edit_region(world_uid, operation, validate_only=False) | Existing AddRegion/UpdateRegion/RemoveRegion payload; no separate state writer; op обязан соответствовать create/update/delete |
| update / EvaluateRegion | StateChangeConsumer.evaluate(world_uid,request) | Existing RegionEvaluation + полный EvaluationResult; public placement D2 |
| delete / TombstoneRegion(world_uid,region_uid,updated_at) | StateChangeConsumer.tombstone(...,updated_at=...) | affected row count; absent — successful no-op, не resurrect; updated_at caller-owned audit string |

validate_only region edit — existing validation operation, не mutation с
Applied(COMMITTED). Не вводить implicit validation write command. Declared
region create не означает public RegionState create; add_declared/remove_declared
остаются внутренними методами reconciliation existing owner.

### 5.3 Outcomes и session protocol

В mutation.py предлагаются:

- `Applied[T](kind="applied", payload:T, affected:WorldStateAddress,
  changed:bool, completion:MutationCompletion)`; completion enum COMMITTED/PENDING.
  World-wide operations требуют отдельного world target в D1, без fake scope.
- `Refused(kind="refused", reason:MutationRefusalReason,
  diagnostics:tuple[FieldPathError,...]=())`.
- `MutationOutcome[T] = Applied[T] | Refused`.
- Patch payload: `CellPatchReceipt(address, row_present:bool)`; возвращает
  persistence outcome, не fabricated merged state. Tombstone payload:
  `RegionTombstoneReceipt(region_uid:EntityUid, affected_rows:int)`.
- Reasons из WS-0A §8.3: UnsupportedOperation, ForbiddenOperation,
  InvalidInput, AlreadyExists, NotFound, NeedsMaterialization,
  AmbientTransactionRequiresSession, InvalidMutationSession. Domain validation
  diagnostics сохраняются; storage/codec/sqlite errors не Refused.

`IMutationHandler[CommandT,ResultT].apply(command, *, session)` требует
явную WorldMutationSession. Public create/update/delete допускают
`session: WorldMutationSession|None=None`. UOW contract в contracts/unitOfWork.py:
`transaction(*, session=None) -> AsyncContextManager[WorldMutationSession]`.
Session имеет публичные read-only `active:bool`, `rollback_only:bool` и
`mark_rollback_only(reason:BaseException)->None`; DB/root/task identity
инкапсулирована реализацией UOW, не new state dataModel. DB handles не
передаются caller/kernel. Abort исключение и его ответственность — D4.

Root: capability check → pre-BEGIN ambient check → BEGIN IMMEDIATE → handler
→ check rollback-only → commit → Applied(COMMITTED). Join: validate same
DB/root/task/connection → no BEGIN/COMMIT → Applied(PENDING). Любое исключение,
включая cancellation, делает joined root rollback-only; root не коммитится,
даже если nested error поймали. Refused root возвращается после abort/rollback;
joined refusal — typed abort наружу, без successful normal return в UOW.
SQL+pack-file publication в этот протокол не добавляется.

## 6. SQL writer ledger: проверенные masks и callers

Все строки относятся к `map_cell_patches`. `_upsert_partial` вставляет **все**
MapCell columns через mapper, но при конфликте обновляет только SET mask.
Поэтому сохранение existing чужих полей доказуемо только на conflict branch;
для insert caller всё ещё отвечает за корректные полные исходные значения.
`layer_kind` на конфликте этих legacy методов не обновляется.

| Repository method | SET на conflict | WHERE на conflict | Existing caller |
|---|---|---|---|
| upsert_terrain_skeleton | system_terrain | system_building_element IS NULL | MapCellService.save_pass(terrain), BootstrapMapCellWriter.write_terrain(insert_only=False) |
| upsert_climate_fields | temperature_base,rainfall,location_uid,system_terrain | system_building_element IS NULL | save_pass(climate), BootstrapMapCellWriter.write_climate; DAG generateClimateNode/recalculateClimateNode |
| upsert_ore_markers | system_material | system_building_element IS NULL | save_pass(ore) |
| upsert_cave_carve | system_terrain | system_building_element IS NULL AND system_material IS NULL | save_pass(cave) |
| upsert_settlement_surface | location_uid,system_terrain | system_building_element IS NULL | MapCellService.save_settlement_surface → SettlementPersistService |
| insert_bulk_ignore | нет: INSERT OR IGNORE | duplicate игнорируется | MapCellService.save_generated → SettlementPersistService; DAG lazyTerrainNode/lazySettlementNode |
| insert_terrain_bulk | нет: plain INSERT | duplicate — SQL error | BootstrapMapCellWriter.write_terrain(insert_only=True) |
| upsert → BaseRepository.upsert | INSERT OR REPLACE всей строки | нет field mask | MapCellService.import_from_json → import_list; PatchStoreService.upsert_patch |
| delete_by_world | DELETE всех rows world | world_uid | MapCellService.clear; map.py clear_map; worlds.py invalidation после update |

BootstrapMapCellWriter.write_terrain_chunk_batch открывает transaction_on
bootstrap connection на все chunks; write_climate сам transaction не открывает,
caller connection scope требуется явно. Main session не join bootstrap.
SerialPersistQueue.persist_stream/ClimateBatchOrchestrator/SettlementPersistService —
делегированные persist owners, не самостоятельное разрешение write entry.
Каждый live путь должен прослеживаться до DAG/debug API, см. §7.

Policy существования нескольких selective writers — WS-0A §10.1:
disjoint fields сохраняются, same field last successfully committed wins;
WHERE skip не Applied, SQLITE_BUSY/storage error без silent retry.
Whole-row paths требуют explicit administrative contract или caller-owned
selective intent. Автоматически получать Keep из старого MapCell запрещено.

### 6.1 Test callers, scripts и известные пределы аудита

Прямой поиск определений/вызовов перечисленных методов выполнен по
`backend/app`, `backend/tests`, `scripts` (Python). У проверенных scripts
вызовов patch family не найдено. Это статический audit, не runtime call trace
и не доказательство отсутствия dynamic getattr/внешних callers.

Из existing tests writer family вызывают test_bootstrap_map_cell_writer.py,
test_database_bootstrap_conn.py, test_map_cell_persist_perf.py.
Region write/read fixtures — test_declared_region_edit.py,
test_region_state_change.py, test_region_state_repository.py,
test_region_state_contract.py, test_region_state_overlay.py,
test_wilderness_region_index.py. Прямые repo writes тестовых fixtures —
изолированная setup-подготовка, не разрешённый production application entry.
Runtime parity WS-4 должна отдельно проверить production entry chain;
тест repo/handler сам по себе её не подтверждает.

## 7. Caller/import ledger и cutover ownership

### 7.1 Read consumers

| Existing caller / путь под backend/app | Existing read | Target шаг / ограничение |
|---|---|---|
| api/routes/map.py: scene_volume_route | MapCellService.get_scene_volume | WS-4 SceneQuery, map-cell HTTP serialization снаружи common service |
| map.py: has_column_cells_route | MapCellService.has_column_cells | WS-4: exact existence query ещё нужен, D4; не заменять чтением всей сцены |
| map.py: pack_fine_terrain_read | PackFineTerrainReadFacade.read_tile/read_wilderness_chunk/read_merged_cell/read_location_terrain | WS-4: raw/merged distinct; tile/location-debug envelope не покрыт одним ChunkQuery, D4 |
| map.py: list_map_cells/export_map; render/legacyMapGridRender.py | get_all_for_read/export_for_debug, pack debug export | WS-4: world-map-surface+patch export не полный merged world; D4 |
| api/routes/locations.py: list/get/get_children | NamedLocationService.get_all/get_by_id/get_children | WS-4 Locations/Object/LocationChildren, payload D1 |
| api/routes/worlds.py: list/get/export | WorldService.get_all/get_by_id; WorldBundleService.export | WS-4: world catalog query не world-scoped metadata; D1/D4 |
| application/worldBundle/entity/sections.py: WorldSectionHandler/LocationsSectionHandler.export_section | WorldService.get_by_id, NamedLocationService.get_all | WS-4; full source parity D1; bundle format остаётся у bundle owner |
| application/worldData/materialize/surface/worldSurfaceMaterializationOrchestrator.py | load_region_state_snapshot + source inputs | WS-3 operation-wide WorldRegionsQuery; D1 для world/location source |
| application/worldData/pack/bake/l0/packMaterializationOrchestrator.py | load_region_state_snapshot | WS-3 полный world store до bake, не selected UID |
| api/routes/map.py: refine_from_entry_route/refine_chunk_route/schedule_chunk_refine_route | load_region_state_snapshot | WS-3 один read на operation; передать mapping во все drains |
| pack/read/wildernessRegionReadService.py: outline | membership → entry.require_plan_inputs → load_region_state_snapshot | WS-3: absent early return до prepare/state read; existing RegionOutlineStaleError сохраняется |
| pack/read/regionStateOverlay.py | region store для canonical gameplay merge | Backend WS-2a, не маршрутизировать обратно через общий facade; не цикл |
| planning/composition/surfacePlanningEntry.py / surfacePlanningCapture.py | ready world/location + mountain templates → sync capture/prepare | WS-3 async acquisition снаружи; в capture нет общего read-port/DB IO |
| pack/refine/fine/prep/fineTilePrep.py; pack/refine/gridNeighborHalo.py | raw fine chunks для materialization parent/halo | Storage backend чтения explicit materialization, не gameplay wrapper; не вводить per-cell port |
| pack/read/packRenderReadFacade.py; packFineTerrainReadFacade.py; packDebugReadFacade.py | raw pack / gameplay facade | WS-4 external access через общий entry; внутренние storage calls не recursive facade |
| api/routes/debug.py | WorldService.get_by_id | WS-4 MetadataQuery после D1 |

Internal cell merge/overlay, pack decoding и parent-halo storage — backend
общей read реализации либо explicit materialization, не вторые external CRUD
entry. Их нельзя механически перекинуть на facade, создав цикл.
TODO(snapshot) остаётся на outline application read boundary, до membership
early return; не переносится в low-level get_cell/worker/write owner.

### 7.2 Mutation entries и critical bypass gate

| Existing entry → owner → writer | Фактический статус относительно правила DAG/debug API | Действие до приёмки |
|---|---|---|
| api/routes/map.py debug bake/refine → orchestrators → pack writer / delegated SQL persist | Разрешённый тип entry; проверен исходный debug маршрут; runtime trace не выполнялся | Сохранить explicit materialize, не CRUD command и не генераторный write |
| DAG terrain/climate nodes → map_cell_repo selective insert/update | DAG entry присутствует | Ноды не менять; WS-4 wiring только отдельно с мастером по DAG gate |
| api/routes/map.py import_map → MapCellService.import_from_json → repo.upsert | Debug entry, но unsafe whole-row replacement | Block live facade rollout до administrative intent/concurrency contract; не pretend selective |
| api/routes/map.py clear_map → MapCellService.clear → delete_by_world | Debug destructive administrative entry | Не fine_cell delete; отдельный explicit administrative scope |
| api/routes/worlds.py create/update/delete/edit_declared_region → WorldService → repo/reconcile | Обычный authoring CRUD router; явной DAG/debug boundary в цепочке нет | D3: не объявлять route debug по имени функции/намерению автора |
| api/routes/locations.py create/update/delete/import → NamedLocationService → repo | Обычный CRUD/import router, та же отсутствующая boundary | D3 |
| api/routes/worlds.py import endpoints → WorldBundleService/WorldCopyImport → entity sections → WorldService/NamedLocationService | Import application entry не доказан как DAG/debug; own root UOW | D3; future session join, не ambient autoadopt |
| DeclaredRegionEditor.reconcile → StateChangeConsumer.{add_declared,evaluate,remove_declared} → repo | Корректный single writer; допустимость entry наследуется от вызывающего WorldService | D3; reconciliation не самостоятельный facade и не новый writer |
| PatchStoreService.upsert_patch | Backend callable, прямых production callers поиском не обнаружено | WS-5 удалять только после проверки внешних bindings/tests; unsafe метод не live fallback |

По нормативу bypass уже блокирует приёмку затронутого шага, а не только WS-5.
Документирование обходов не закрывает их. D3 нужен **до** объявления WS-0 DONE;
его нельзя спрятать за обещанием «исправим в WS-4».

DI: `core/container/worldData.py` владеет service/adapters, repository instances
из existing wiring. `core/container/packs.py` сейчас также создаёт отдельный
SqliteRegionStateRepository на той же DB; repository object identity не равна
DB/transaction identity. Один DB/connection UOW обязателен, второй store нет.

## 8. Приёмочные проверки: exact target команды и evidence

Это **планируемые** проверки, сейчас tests/typing не создавались и не запускались.
Команды из корня, Python из `.venv/Scripts/python.exe`, `PYTHONPATH=backend`.

Existing suites (проверены имена файлов):

```powershell
$env:PYTHONPATH = 'backend'
.venv/Scripts/python.exe -m unittest tests.test_map_cell_query_facade tests.test_merge_map_cells tests.test_merge_fieldwise tests.test_merge9_debug_read
.venv/Scripts/python.exe -m unittest tests.test_bootstrap_map_cell_writer tests.test_database_bootstrap_conn tests.test_map_cell_persist_perf
.venv/Scripts/python.exe -m unittest tests.test_region_state_repository tests.test_region_state_overlay tests.test_region_state_contract tests.test_region_state_change tests.test_declared_region_edit tests.test_wilderness_region_index
```

Target WS tests leaf из WS-0A §12 сохраняется:
`backend/tests/worldState/{__init__,test_capabilities,test_uow,test_cell_patch,test_facade_wiring}.py`.

| Шаг | Cases / измеримое evidence |
|---|---|
| WS-1 | Overload каждого query → конкретный payload; read-only object без write methods; отказ передачи raw dict/str вместо delta/enum/coordinate; InvalidInput SetNone/SetFalse; импорт dataModel без application/db; concrete metadata/evaluation bindings только после D1/D2 |
| WS-2a | Каждый §4 variant делегирует exact backend; world resolve=1 на request; empty world store Found(()); missing vs storage errors; raw missing не L0 fallback; merged field_sources parity; no generate; outline absent не требует state read |
| WS-2b | CREATE/UPDATE/UPSERT, defaults parity schema/model/policy; полный empty-row predicate; travel=0/structural/preservation-only; reset lower layer; composite-key isolation; rollback после второй записи, cancellation, caught nested refusal; ambient OWNED/INHERITED отказ до BEGIN, independent task NONE; wrong DB/root/task session; bootstrap/main disjoint/same-field/rollback serialization |
| WS-2c | Existing domain diagnostics; same DB/UOW у world/location/reconcile/StateChangeConsumer; FK/storage error не Applied; update requires_force/invalidation D4; evaluation child/signals parity D2 |
| WS-3 | Один operation-wide region read, mapping identity до всех tiles/drains, новый standalone drain — новый read; factories/kernel без IO; один source path; exact outline early-return/TODO/stale error |
| WS-4 | Каждый external row §7 old/new parity; ни live replace fallback, ни bypass D3; unsupported debug export shapes не silently narrowed; DAG только после отдельной приёмки |
| WS-5 | Wrappers удаляются после executed parity; no second store/read-generate; все D1–D4 закрыты и caller rows покрыты |

Target команды:

```powershell
.venv/Scripts/python.exe -m unittest discover -s backend/tests/worldState -p 'test_*.py'
node_modules/.bin/pyright.cmd -p backend/tests/worldState/typing/pyright.valid.json
node_modules/.bin/pyright.cmd -p backend/tests/worldState/typing/pyright.invalid.json
```

valid: 0 errors. invalid: exact code/location diagnostics, не только count.
Negative fixture сейчас не freeze по строкам: файлы появятся в WS-1, ledger
диагностик фиксируется рядом с fixture при его создании; это не свобода
менять query→payload связь. WS-3 дополнительно запускает существующие
`unittest discover -s backend/tests/planning/consumers -p 'test_*.py'`.
Existing изменённые planning test/config файлы в worktree не редактировать
ради этого документа и не считать своей выполненной проверкой.

Responsibility evidence: typed DTO — данные, ports — contracts, facade —
dispatch/capability/UOW, adapters — существующие public API, handlers —
domain rules, DB mapper/repo — wire/SQL, operation owner — acquisition и
materialization, DAG/debug API — сбор PatchSet. Никакой новый класс WS не
собирает PatchSet. Snapshot service в этих checks отсутствует обоснованно.

## 9. Решения, без которых полный freeze остаётся открытым

### D1 — полный World/NamedLocation payload и source mutation intent

Факт: full-world чистого DTO нет. WorldService.create/update и
NamedLocationService.create/update принимают raw dict; update location
делает shallow generic.update, world update — merge_world_patch с omitted/null
семантикой. WorldScope не содержит world-level target для Applied.
Нельзя назвать `WorldCreate(data:dict)` typed command и объявить freeze закрытым.

Ранее предложенный implementation-вариант, **не выбранный до приёмки
архитектуры**: сохранить existing row payload на application boundary.
В таком варианте DataModel query/result envelopes generic, без DB imports;
конкретные aliases MetadataResult[World]/ObjectResult[NamedLocation] и
world/location команды с existing source types принадлежат application
contracts соответствующих доменов. Для source write всё равно нужен точный
typed intent: это не освобождение от fields/omitted/null freeze.
Следствие: нужно отдельно уточнить WS-1 запрет db imports (разрешить только
DB row types в application contracts) и class/file map до кода.
Это пока кандидат, не принятое исключение. Дополнительно действует §1.1:
ради WS нельзя менять stable generator signatures, передавать ему WS read
capability или заставлять DAG/debug callers знать SQL/storage shape.

Альтернатива: сперва выделить полный pure source DTO из DB rows и typed patch
intent в домены world/location, с schema/default/serialize parity. Это более
широкий подготовительный шаг; не создавать копию World внутри worldState.

До решения: Metadata/Object/full-source commands и world catalog не frozen.
Cell/region/pack payload таблицы от D1 не зависят, но это не разрешение
начать WS-1 урезанным контрактом.

### D2 — RegionEvaluation остаётся application command

Факт: request.context содержит FactConsumerContext с Climate/Terrain/Hydrology
WorkingFields; result содержит ChildRegion и MaterializeSignal. DataModel
не должен импортировать эти application/generator структуры.

Вариант для обсуждения после определения архитектурной границы evaluation:
**application-owned evaluation capability** с existing
RegionEvaluation/EvaluationResult; не переносить engine context в dataModel.
WorldStateService делегирует ему через специализированный generic application
port. Нужны уточнённые точные aliases/paths и импортные gates WS-1; public
read/patch DTO продолжают жить в dataModel. Альтернатива — отдельный domain
facts DTO + refactor StateChangeConsumer API, что меняет domain contract и
требует самостоятельного согласованного шага. Не копировать поля request.

До решения: EvaluateRegion и its result binding не frozen. Tombstone,
declared edit и region state reads уже имеют existing чистые payload.

### D3 — обычный authoring/import API против exclusive entry gate

Норматив разрешает только DAG/debug API. Existing worlds/locations CRUD и
bundle import явно не проходят такую boundary (§7.2). Их сохранение под
общим сервисом само по себе обход не устраняет.

Прежнее предложение объявить master authoring/import endpoints частью debug
API **снято 2026-10-27**: оно противоречит GEN DAG § «Три входа» — debug HTTP
не UI мастера. Перенос обычного production вызова в debug coordinator также
не устраняет противоречие. Требуется разделить по фактическому trigger:
production master/player → DAG → stable application operation; developer
smoke → debug HTTP → тот же operation. Current standalone authoring/import
mutations остаются несовпадением с exclusive-entry gate, а не исключением.
Exact target class/method/file map и compatibility protocol ещё не определены;
WS не реализует их и не меняет DAG wiring до совместного gate с мастером.

До решения: WS-0/WS-0A не DONE. Нельзя отложить gate до live rollout.
Здесь остаётся sequencing conflict R7 (transition §8): запрет DONE при runtime
bypass против design-only scope и отложенного DAG wiring. Критерий приёмки
должен быть согласован явно; документ не делает исключение из нормативного gate.

### D4 — непокрытые existing semantics, которые нельзя выдать за Applied/parity

1. `WorldUpdateResult.requires_force` возвращается **без записи**;
   map_cells_invalidated обслуживается отдельным route clear **после**
   WorldService.update. В reason enum пока нет ForceRequired, warning и
   invalidated scopes не определены. Предложение: добавить typed
   ForceRequired с warning; успешная invalidation cleanup — часть того же
   command root UOW до Applied, через explicit handler storage port.
   Это требует exact method/class/path map и дополнения command contract.
   Нельзя объявить RequiresForce Applied(changed=False) и потерять negotiation.
2. Новый typed abort для joined refusals: в target class map его класса/файла
   нет. Предложение: WorldMutationAborted(outcome:Refused) рядом с UOW
   contracts; root UOW вызывает тот же abort при rollback-only, сохраняя cause.
   Это contract exception, не DB error/HTTPException и не domain validator.
3. `has_column_cells`, all-world debug export, raw location terrain/tile debug
   envelope и world catalog не покрыты §4 overloads. Предложение: выписать
   отдельные точные query/result variants по public facade methods, сохраняя
   текущие read modes; UI raw dict envelope сериализуется за common port.
   Не заменять их одним AreaQuery/MetadataQuery и не удалять callers из scope.
4. После выбора D1/D2 нужна точная композиция новых application contracts:
   текущая contracts leaf уже содержит 5 target files. Дополнительный файл
   потребует WARN с count и принятой class/file map; добавление aliases
   нельзя оставить на усмотрение implementation. POJO/Pydantic с большим
   числом полей исключены из class-size-limit: сам размер DTO не блокер.

Эти четыре пункта — часть worklist архитектуры/полного freeze, не TODO
разработчику реализации. Вопросы responsibilities, command→patcher и
source→planning effects R3–R8 решаются до приёмки архитектуры; concrete aliases,
DTO fields и backend binding — после неё, до implementation. Полный набор
полей и binding всех consumers пока не объявляется замороженным.

## 10. Что подготовлено и что будет следующим

Подготовлены exact existing method/payload bindings, предлагаемые scoped
query/delta contracts, SQL conflict masks, operation lifetime и critical
caller findings. Девять прежних WS-0A решений не переоткрывались.
Сверка выявила дополнительные реальные gaps D1–D4; скрытых архитектурных
решений в коде не принято. Полный WS-0 freeze пока **не завершён**.

Следующий заход остаётся архитектурным: закрыть responsibilities/data flow
и решения R3–R8 с учётом GEN DAG → приёмка архитектуры → конкретные
DTO/class/method/file/error/backend bindings и проверки → полный freeze
WS-0/WS-0A → WS-1. Runtime tests сейчас не нужны: код не изменён.

</details>
