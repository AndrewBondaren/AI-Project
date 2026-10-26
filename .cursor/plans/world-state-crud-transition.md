# Общий World State CRUD — архитектура и переход по классам

Статус: DESIGN ДЛЯ ПРИЁМКИ (2026-10-25). Запрос мастера — разделить
общий механизм и потребителей и явно описать переход. Это план архитектуры,
не разрешение реализации. Snapshot runtime вне scope. Ни один шаг не DONE.

Следующий пункт проработки **WS-0A — capabilities, фасады и UOW** вынесен в
[отдельный план](world-state-crud-capabilities-uow.md). Он уточняет таблицы
ниже: полный CRUD не обязателен каждому backend, query/mutation фасады
разделяются, атомарность охватывает целую доменную команду. Контрольный
сценарий — одна fine_cell жидкости с selective patch без потери других полей.
До приёмки WS-0A не реализовывать прежние широкие adapter interfaces и не
считать existing upsert доказательством атомарной domain mutation.

## Сквозной архитектурный gate каждого шага (решение мастера, 2026-10-26)

Разделение ответственности — критическое условие приёмки **каждого** шага
WS-0, WS-0A, WS-1, WS-2a/b/c, WS-3, WS-4 и WS-5, а не только финального
ревью. Норматив и проверяемые границы — docs/tz_world_snapshot.md, раздел
«Обязательное разделение ответственности — gate каждого шага WS».
Snapshot lifecycle остаётся вне scope этого CRUD-перехода; gate проверяет
соблюдение границ, не требует реализовать snapshot runtime в текущем треке.

Для каждого шага в evidence приёмки фиксировать class/method responsibility
map, разделение typed contracts и concrete implementations, направление
зависимостей, владельцев координации/UOW/error handling и проверку отсутствия
смешения ответственности по затронутым путям. Доменные правила остаются у
доменов, общий service делегирует их через ports; pure compute не получает
IO, read не вызывает materialization. Проверять фактические calls/imports
для кода и contracts для design. При нарушении шаг не DONE; весь WS не
может быть завершён до устранения нарушения. Исправление нельзя откладывать
до интеграции; для неприменимых границ явно указать причину.

## 1. Владелец и границы

Общий интерфейс и общая реализация принадлежат платформенному домену
**worldState**, вне generators и вне отдельного terrain/climate/regions.
WorldSnapshot — отдельный lifecycle истории. Его будущая интеграция не
создаёт второй World State CRUD. Решение заменяет прежнюю трактовку «весь
общий CRUD принадлежит worldSnapshot»; snapshot CRUD управляет только snapshots.

WorldStateService — application service текущего состояния: typed запрос,
проверка поддерживаемой операции/адресата, делегирование storage/domain port,
typed результат. Не мировой генератор и не новый state store. Существующие
SQL, pack и patches остаются единственными хранилищами соответствующих данных.

Домены внутри generators — потребители общего read-контракта/готовых inputs.
Они не реализуют world CRUD, не сохраняют snapshot и не управляют pack IO.
Pure compute получает подготовленные DTO до worker pool: async read не
встраивается в cell loop, kernel, scorer или provider.build.

Read metadata/materialized data не запускает generate/refine. Отдельные
application operation owners явно вызывают materialization по запросу.
Текущие WP-20 merge/fallback, region-state overlay, patch precedence, WP-13
refine и skip complete сохраняются. Snapshot freshness/provenance,
incremental chunk skip и auto-resume этим переходом не реализуются.

ТЗ: docs/tz_world_pack_storage.md §WP-20/§Read path/§WP-13;
docs/tz_terrain_generation.md §Surface planning/cache;
docs/tz_patch_system.md §Границы слоёв;
docs/tz_world_snapshot.md §Общий World State CRUD и snapshot lifecycle.

## 2. Классы, слои и точные target пути

Все пути относительно backend/app/. Новых файлов в generators нет.

| Класс/контракт | Домен, слой | Target файл | Единственная обязанность |
|---|---|---|---|
| IWorldStateRead | worldState, application port | application/worldState/contracts/worldStateCrud.py | Async typed read; без generate и записи |
| IWorldStateCreate / IWorldStateUpdate / IWorldStateDelete / IWorldStateCrud | worldState, application port | тот же файл | Независимые write capabilities; IWorldStateCrud — композиция четырёх только для full implementation, не обязательство каждого backend |
| WorldStateService | worldState, application | application/worldState/service/worldStateService.py | Единая реализация public interface; typed dispatch/делегирование |
| IWorldMetadataPort / IWorldCellPort / IWorldRegionPort | worldState, application storage/domain ports | application/worldState/contracts/domainPorts.py | Минимальные typed операции backend; никаких kernels |
| WorldMetadataAdapter | worldState integration, application | application/worldState/adapters/metadata/worldMetadataAdapter.py | Делегировать existing WorldService/NamedLocationService reads/writes |
| WorldCellAdapter | worldState integration, application | application/worldState/adapters/cells/worldCellAdapter.py | Делегировать existing merged cell read, cell/patch CRUD и pack chunk read |
| WorldRegionAdapter | worldState integration, application | application/worldState/adapters/regions/worldRegionAdapter.py | Делегировать region store reads и existing region mutation owner; не вычислять transition |
| WorldStateQuery / typed query variants / result variants | worldState, dataModel | dataModel/worldState/query.py | Данные запроса/ответа; без SQL, WorldService, генераторов |
| WorldStateCreate / WorldStateUpdate / WorldStateDelete / mutation results | worldState, dataModel | dataModel/worldState/mutation.py | Typed команды с явной domain семантикой |
| WorldStateAddress | worldState, dataModel | dataModel/worldState/address.py | world_uid + адресат; scope и LOD отдельно |
| ObjectScope / ChunkScope / AreaScope / FineCellScope | spatial, dataModel | dataModel/spatial/query/worldScope.py | Общая адресация с explicit coordinate space; FineCellScope использует FineGridCoord |

Публичные контракты не импортируют реализации/adapters/db repositories.
WorldStateService импортирует только свои ports/DTO; concrete adapters
подставляет composition root. Adapters импортируют публичные existing API,
но не их private buffers/algorithms. Generator consumers зависят только от
IWorldStateRead/DTO либо получают уже подготовленные DTO.

IWorldStateRead — ограниченная capability того же service instance, не вторая
реализация CRUD. Полный IWorldStateCrud не внедряется в pure генераторы.

## 3. Методы и контракты

Все четыре публичных метода async. Typed query overloads связывают конкретный
query и result без Any/raw dict, string action dispatch или cast.

| Метод | Вход → выход | Граница |
|---|---|---|
| WorldStateService.read | WorldStateQuery → соответствующий typed WorldStateReadResult | Делегировать metadata/cell/chunk/object/region read; не materialize |
| WorldStateService.create | WorldStateCreate → WorldStateMutationResult | Делегировать создание явно указанного вида данных; не создание snapshot |
| WorldStateService.update | WorldStateUpdate → WorldStateMutationResult | Делегировать доменную mutation/patch, сохранять existing validation/UOW |
| WorldStateService.delete | WorldStateDelete → WorldStateMutationResult | Явная операция домена: удаление источника, tombstone или reset override; не универсальный DELETE по координатам |
| WorldMetadataAdapter.read/create/update/delete | Typed metadata commands/results | WorldService и NamedLocationService, без planning/capture |
| WorldCellAdapter.read | Cell/area/chunk query → typed merged cells либо persisted chunk result по виду query | MapCellQueryFacade.get_cell/get_scene_volume/get_cells; WorldPackReader.read_wilderness_chunk для явно raw chunk query |
| WorldCellAdapter.create/update/delete | Typed cell patch commands → mutation result | MapCellService/PatchStoreService existing API; не перезапись immutable pack |
| WorldRegionAdapter.read | Region query → typed current region-state result | IRegionStateRepository; mapping через existing state_from_row |
| WorldRegionAdapter.create/update/delete | Typed declaration/state commands → existing domain result | WorldService.edit_region/DeclaredRegionEditor.reconcile/StateChangeConsumer; без повторной реализации их алгоритмов |

Scope не определяет read representation. Merged gameplay cell и raw chunk
различаются типом query; raw read никогда не подменяет merged WP-20 read.
Metadata query не требует decode/materialization. Data query возвращает
фактически доступные данные с existing fallback. Отсутствие L2 может означать
валидный L0 результат, а не ошибку или приказ refine. Patch deletion означает
снятие override, не удаление исходной materialized клетки. Reset override,
удаление declaration и region tombstone — разные typed commands.

ObjectScope несёт domain + stable object UID; geometry/footprint разрешается
владельцем объекта через его public API, не WorldStateService. ChunkScope
несёт system coordinates и chunk identity; размер берётся из metadata.
FineCellScope — x/y/z через FineGridCoord. AreaScope явно задаёт координатную
систему и bounds. Unsupported query/operation возвращает явный typed результат,
не пустой successful payload. Ошибка storage/validation не превращается в missing.

WorldStateService делегирует mutation facade, которая владеет root UOW одной
typed команды либо явно join'ит её существующий WorldMutationSession.
Domain handlers/services присоединяются к той же SQL transaction, без
самостоятельного commit. Это не arbitrary cross-domain batch: новая batch
семантика требует отдельного контракта. Pre-BEGIN ambient отказ, rollback-only,
selective multiwriter policy и live writer gate зафиксированы WS-0A §9–10.1.

Нормативное уточнение §2–3: архитектура capabilities/query-mutation/UOW и
поклассовые методы зафиксированы в world-state-crud-capabilities-uow.md §7–13.
Названия IWorldMetadataPort/IWorldCellPort/IWorldRegionPort в ранней карте
заменяются на отдельные Read/Write ports из WS-0A. Полный CRUD не обязателен
ни одному read-only backend; таблица семейства adapter методов выше не
разрешает добавить always-fail writer. WorldStateService делегирует отдельным
query/mutation фасадам, mutation facade владеет root/join UOW protocol.

**Freeze gate WS-0:** до кода выписать полный набор DTO полей/дискриминаторов,
query→result overloads, supported-operation matrix, create-vs-upsert/delete
семантику каждой команды, exact existing backend method и error mapping.
Таблица выше задаёт ownership/направление, но не разрешает придумать payload
или недостающий repository delete во время реализации. Snapshot selector
сейчас не вводится; временное current чтение не именуется snapshot isolation.

## 4. Переход существующих классов

| Existing класс/метод | Роль после перехода | Что меняется / что сохраняется |
|---|---|---|
| WorldService.get_by_id/update/edit_region | Domain backend metadata mutation | Сохраняет normalize/ref-integrity и domain write scope; не вызывает WorldStateService обратно |
| NamedLocationService | Domain backend objects | Сохраняет свои правила; WorldMetadataAdapter делегирует public методы |
| MapCellService.save_pass/clear | Backend cell/patch mutation | Не превращается в общий CRUD мира; scoped delete не подменяется clear(world) |
| MapCellService.get_scene_volume/get_z_slice_for_read | Временный compatibility entry | Внешние consumers переводятся на WorldStateService.read; конечный backend read — MapCellQueryFacade, без цикла через compatibility routing |
| PatchStoreService.upsert_patch/get_patch_at/get_patches_in_bbox | Patch storage backend | Сохраняет роль; merged read не заменяется raw patch read |
| MapCellQueryFacade.get_cell/get_scene_volume/get_cells | Canonical merged-read backend | WP-20 и overlay остаются здесь; не дублируются в общем service/adapter |
| MapCellReadService / PackReadServices | Existing pack wiring/compatibility | Backend composition; новые consumers не обходят общий port через эти factories |
| PackReadContext / WorldPackReader | Physical pack read/cache | Остаются storage механизмом; не выбирают snapshot или domain policy |
| StateChangeConsumer.evaluate | Единственный region-state writer | Доменный transition остаётся здесь; common CRUD не пишет region_states напрямую |
| SurfacePlanningCapture.capture | Потребитель подготовленных source metadata | Async load через общий read port на application boundary; сам capture остаётся sync/pure projection |
| SurfacePlanningEntry.capture_view/prepare_captured (PC-11 target) | Surface application consumer | Получает typed metadata до capture; не реализует CRUD и не создаёт snapshot |
| ClimateWorkingFields / TerrainWorkingFields / HydrologyWorkingFields (PC-11 target) | Domain consumers frozen plans | Их indexes/алгоритмы не переносятся в WorldStateService; не делают IO из cell workers |
| LandcoverMaterializer.collect/materialize | Consumer domain context/inputs | Не читает repositories/common service в inner loop; prepared metadata приходит снаружи |
| WorldSurfaceMaterializationOrchestrator / EntryRefineOrchestrator | Explicit operation consumers | Read metadata/готовых данных через общий port, materialize отдельным вызовом; не backend общего CRUD |
| WorldDataWiring | Composition root | Создаёт один WorldStateService и concrete adapters; algorithms сюда не переносятся |

Direction: consumer → common port → WorldStateService → backend adapter →
existing backend. Если external MapCellService wrapper делегирует common port,
adapter НЕ вызывает этот wrapper, а использует canonical backend напрямую.
Симметрично WorldService backend не маршрутизирует обратно в common CRUD.
Полный caller/import ledger фиксируется WS-0: routes/scripts/debug/region
read/edit и не-generator consumers тоже учитываются; переименования классов
сами по себе переходом не считаются.

## 5. Последовательность реализации — по одному шагу

Каждый шаг: отчёт/проверки → приёмка мастера → следующий. Snapshot вне всех шагов.

| Шаг | Цель / файлы | Контракт, проверка и Done |
|---|---|---|
| WS-0, design only | Freeze DTO/методов/operation matrix/caller ledger в настоящем плане и связанных ТЗ | Ownership review против layer-boundaries.mdc; точные поля/error semantics/методы всех adapters; разрешены только документы; DONE после приёмки |
| WS-0A, следующий design пункт | world-state-crud-capabilities-uow.md | Capability matrix, query/mutation facade method map, atomic command/UOW contract и selective patch scenario; код не писать, закрыть архитектурные вопросы до WS-1/WS-2 |
| WS-1 | dataModel/worldState, spatial/query, application/worldState/contracts | Только общий контракт, без fake implementations; type-positive/negative, no generator/db imports; интерфейс пригоден всем named consumers |
| WS-2 | application/worldState/service + adapters + existing DI | Одна shared implementation поверх существующих CRUD/read backends; WP-20/patch/region single-writer baseline; public interface не содержит materialize/snapshot operations |
| WS-2a, детализация для приёмки | Query facade + read adapters + WorldStateService.read | Existing read parity; read-only capabilities не требуют writer; no read-generate |
| WS-2b, детализация для приёмки | UOW/session + CellPatchMutationHandler + selective repository methods | Один root commit, rollback-only join, selective patch/reset без INSERT OR REPLACE; выполнить до остальных writer bindings |
| WS-2c, детализация для приёмки | WorldMutationHandler / LocationMutationHandler / RegionStateMutationHandler + DI | Existing domain validators/writers присоединяются к тому же UOW; нет циклов и независимых commit |
| WS-3 | application surface entry + capture callers + landcover/climate input owners | Atomic read-port wiring на границе async loading; factories/kernel получают готовые данные; счётчики показывают отсутствие per-cell IO и второго source path |
| WS-4 | external read/mutation callers + compatibility wrappers по WS-0 ledger | Consumers переведены, нет callback cycles или параллельного mutation path; исполняются old/new parity cases до удаления wrapper |
| WS-5 | Удаление ненужных compatibility paths + итоговая приёмка | Все named entry cases исполнены: object/chunk/area/fine_cell, raw vs merged, missing/fallback/patch reset, no read-generate; no second store и snapshot TODO подтверждены |

ТЗ каждого шага — документы §1 плюс зафиксированные WS-0 нормативные additions.
Точные команды существующих suites/новые минимальные tests и typing targets
вносятся в WS-0 после caller ledger; пока команды не закреплены, WS-1…5 не
готовы к исполнению. SQL/DAG/backend-start/коммиты не входят в этот запрос.

## 6. Композиция папок

Новые leaf paths: application/worldState root — init (1); contracts —
init/worldStateCrud/domainPorts/unitOfWork/mutationHandler (5); service —
init/worldStateService/worldStateQueryFacade/worldStateMutationFacade/
worldReadContextProvider (5);
unitOfWork — init/worldStateUnitOfWork (2);
adapters root — init (1); metadata/regions — init + adapter (по 2);
cells — init/worldCellAdapter/cellPatchStorageAdapter (3), чтобы storage
adapter не создавал DI-цикл с CellPatchMutationHandler.
dataModel/worldState — init/address/query/mutation (4), spatial/query —
init/worldScope (2). Полный DTO freeze WS-0 не должен молча разрастить эти файлы
или добавить шестой без WARN; при необходимости карта уточняется до кода.

Existing direct counts: mapCells 6→6, pack/read 22→22, regions 8→8,
core/container 9→9. Новые root modules там не добавлять. Нужная композиция
переполненных каталогов не делается попутно. WARN сообщён мастеру при проектировании.
Domain handlers и selective patch DTO — отдельные leaf paths/counts по
WS-0A §7/§11; их не добавлять root-файлами в mapCells/registries/regions.
Freeze review 2026-10-26 — WS-0A §13. Handler protocols и world read-context
provider обязательны в WS-0 ledger. NOT NULL insert, полный empty-row predicate,
structural-OR/read visibility, pre-BEGIN ambient refusal и multiwriter rollout
gate — фиксированные входы WS-2b, не решения «по месту» при coding.

## 7. Связь с PC-11 и будущими snapshots

**Read/write шов PC-11 (уточнение 2026-10-26).** PC-11.1-D/E фиксирует
отдельные method/caller contracts: gameplay merged read по WP-20; debug
WildernessRegionReadService.outline с membership early return; explicit
materialize_pack_*/refine_from_entry с existing scope/parent-light/publication
gates. Отсутствие данных в read не запускает bake/refine. Для outline absent
возвращает None без capture/prepare/state reads; present готовит inputs и
вычисляет read-контур без записи L0/L2, stale geometry даёт existing ошибку.
Read TODO не назначается write-owner EntryRefineOrchestrator.refine_from_entry.

В PC-11.6b TODO ставится в WildernessRegionReadService.outline до membership
early return и ссылается на настоящий WS-план, §7:
`TODO(snapshot): integrate snapshot existence lookup via the shared CRUD;
see .cursor/plans/world-state-crud-transition.md, section 7 (PC-11 and future snapshots).`
WS-3/WS-4 при caller cutover назначают общий application read-owner и
переносят этот TODO по ledger; low-level merged-read backend не получает
самостоятельный snapshot service или planning на каждую клетку. Это вход
для будущего snapshot design: точный порядок existence lookup, missing
semantics и pinned selector пока не заморожены. Их реализация не становится
дополнительным Done-критерием PC-11 или WS-1…WS-5 текущего CRUD.

PC-11 method map остаётся domain cutover-планом, не реализацией shared CRUD.
**Порядок согласован мастером 2026-10-26:** сначала WS-0/WS-0A замораживают
surface/region/climate read DTO/capabilities, error mapping и caller ledger;
затем PC-11 выполняется с согласованными inputs. Pure domain factories/views
не зависят от snapshot runtime. WS-1 и read implementation WS-2a должны быть
готовы до подключения общего port. WS-3 выполняет один согласованный cutover
того же entry/input ledger PC-11.3/11.5/11.6b; повторная независимая миграция
entry API после PC-11 не планируется. Это интеграционная последовательность,
не объединение всех шагов в один кодовый заход: приёмка остаётся пошаговой,
каждый переключённый consumer использует один source path, с parity/typing.
Остальные WS writer/external-caller шаги сохраняют свои dependencies/scope
и не объявляются частью PC-11.

Region-state read для materialization имеет lifetime операции по PC-11.1-D:
operation owner получает один readonly mapping и передаёт его всем tiles,
scene/path/internal drains; FineChunkRunner не делает собственный reload.
Новый самостоятельный drain-запрос получает новый read. WS-3 подключает
общий region read port на этой boundary, не в workers и не per tile;
смена backend не создаёт второго чтения или второго region-state writer.
Для этого caller используется полный world-scoped read existing
RegionQuery/RegionResult family: WorldRegionAdapter делегирует существующему
IRegionStateRepository.get_by_world(world_uid), включая tombstones, и
state_from_row. get/get_many сохраняются для object/selected-UID reads;
их частичный результат не заменяет полный read materialization. Domain
payload переиспользует existing RegionState, materialization projection —
existing StateSnapshotEntry; поля не копируются в новый WS-specific state
POJO. Проекция принадлежит existing regions/regionStateSnapshot.py, точный
mapping/mandatory parameter ledger закреплён в PC-11.1-D. Found с пустой
коллекцией — пустой store; Missing/UnsupportedOperation/storage error не
превращаются в пустой успешный snapshot. Это binding существующего read
контракта и bulk backend, не новый API или повторный freeze POJO.

Snapshot-трек позже подключает чтение выбранного snapshot и immutable mutation
через тот же worldState interface. WorldSnapshotService владеет только
snapshot create/read/update/delete/restore/branch lifecycle, не состоянием
terrain и не materialization. Его storage adapter не называется второй
WorldStateService. При PC-11 cutover в коде оставляется только TODO со ссылкой
на настоящий WS-план, §7 (точный текст выше); placeholder snapshot backend/selector/always-exists
и фиктивная реализация интерфейса запрещены.
