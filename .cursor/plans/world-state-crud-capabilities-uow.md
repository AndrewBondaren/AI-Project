# World State CRUD — capabilities, фасады и атомарность

Статус: OPEN / архитектура WS-0A детализирована для приёмки (2026-10-25).
Freeze review 2026-10-26: адресные решения девяти замечаний — §13;
соответствующие class/method/field contracts §7–12 обновлены. Это design
для приёмки, не evidence реализации и не автоматическое закрытие WS-0.
Продолжение world-state-crud-transition.md, не новый параллельный CRUD.
Мастер попросил вынести вопросы capabilities и атомарности отдельно.
Это фиксация требований и целевой схемы для приёмки; код не разрешён,
порядок implementation steps WS-1…WS-5 автоматически не меняется.
Нормативная детализация — §7–13 ниже: она заменяет предварительные
формулировки §2–6 при расхождении. Архитектурные решения записаны, но
приёмка мастером и реализация ещё не выполнены.

## Обязательный gate приёмки каждого шага

Решение мастера 2026-10-26: разделение ответственности проверяется на каждом
design/implementation/integration шаге WS; при нарушении шаг и весь WS не
могут считаться завершёнными. Применяется сквозной gate из
world-state-crud-transition.md и норматив docs/tz_world_snapshot.md, раздел
«Обязательное разделение ответственности — gate каждого шага WS».
В evidence каждого шага обязательны class/method responsibility map,
границы contracts/implementations, зависимости и владельцы coordination,
UOW и ошибок. Общие facade/service/adapter не поглощают доменные алгоритмы;
проверка по contracts и фактическим calls/imports выполняется до DONE,
а не переносится на будущую интеграцию. Snapshot runtime этим gate не
добавляется в scope текущего плана.

Критический gate каждого шага также включает запрет любого доменного
пути записи в scope WS в обход DAG или debug API как application-входа.
Проверять writer/caller ledger и фактическую цепочку entry → coordination
→ handler → storage, включая internal/debug/import/batch callers.
Typed capability сама по себе не разрешает самостоятельный обходной
write-entry. Делегированная запись внутри разрешённого сценария допустима.
При обходе затронутый шаг не DONE; весь WS не завершён, пока остаётся
хотя бы один обход в scope. Evidence требуется на каждом шаге, не только
при финальной интеграции; норматив — docs/tz_world_snapshot.md,
«Обязательное разделение ответственности — gate каждого шага WS».

## 1. Scope и нормативные входы

Разобрать интерфейсы поддерживаемых операций, query/mutation фасады,
владельца UOW и одну fine_cell жидкости как контрольный сценарий.
Общий домен worldState — вне generators; домены generators — consumers.
Snapshot runtime, snapshot freshness/provenance, физика распространения
жидкости и новая реализация жидкостей вне scope. Задел snapshot — TODO
со ссылкой на docs/tz_world_snapshot.md, без фиктивного backend.

Входы: docs/tz_world_pack_storage.md §WP-20/§WP-13/§Gameplay modifications;
docs/tz_patch_system.md §Границы слоёв; docs/tz_terrain_hydrology.md §C2
(surface metadata не равно произвольному runtime fluid volume);
world-state-crud-transition.md §2–5; layer-boundaries.mdc и code-gates.mdc.

## 2. Интерфейсы: capabilities вместо обязательного полного CRUD

IWorldStateRead.read, IWorldStateCreate.create, IWorldStateUpdate.update,
IWorldStateDelete.delete — независимые application ports общего worldState.
IWorldStateCrud — композиция четырёх capabilities только для реализации,
которая действительно их предоставляет. Read-only backend не обязан
реализовывать write методы с NotImplementedError, no-op или always-fail.
Внутренний consumer получает минимально необходимый capability interface.
Генераторам не внедряется full CRUD ради одного read.

Различать три результата:
- операция отсутствует у backend — capability не предоставлена;
- универсальный внешний вход получил неподдерживаемую command/target
  комбинацию — typed UnsupportedOperation до записи;
- операция поддерживается, но запрещена для текущего состояния/прав доступа
  — typed domain/authorization refusal, без записи и без подмены Missing.

Разделение статических capabilities не заменяет runtime authorization.
Типизированная supported-operation matrix и binding ports фиксируются до кода.
Таблицы read/create/update/delete у adapters в исходном transition плане
описывают семейство возможных операций, не обязательный интерфейс каждого
adapter. Этот документ уточняет соответствующую прежнюю формулировку.

## 3. Target классы и методы

Пути относительно backend/app/, target для приёмки, не существующий runtime.

| Класс/метод | Домен / слой / target путь | Единственная ответственность |
|---|---|---|
| IWorldStateRead.read / IWorldStateCreate.create / IWorldStateUpdate.update / IWorldStateDelete.delete | worldState, application/worldState/contracts/worldStateCrud.py | Typed capabilities, без SQL/генерации |
| WorldStateService.read/create/update/delete | worldState, application/worldState/service/worldStateService.py | Единственная внешняя shared implementation; делегирование query/mutation фасаду, не второй алгоритм |
| WorldStateQueryFacade.read | worldState, application/worldState/service/worldStateQueryFacade.py | Typed dispatch к read ports; metadata/готовые данные, no generate |
| WorldStateMutationFacade.create/update/delete | worldState, application/worldState/service/worldStateMutationFacade.py | Проверка binding/capability, domain handler и единый UOW операции |
| WorldStateUnitOfWork.transaction | worldState, application/worldState/unitOfWork/worldStateUnitOfWork.py | Async transaction context поверх existing Database transaction, без domain logic |
| Доменные handler.apply | Домен соответствующего изменения, application | Validate/apply только своей доменной команды; точный class/path каждого handler — freeze перед его реализацией |
| Backend adapters | Пути metadata/cells/regions исходного transition плана | Только поддерживаемые read/write capabilities; делегирование public existing API |

Новых root modules в generators/mapCells/pack/read нет.
Service leaf: init + WorldStateService +
query facade + mutation facade = 4 файла; unitOfWork leaf = init + UOW = 2.
Это уточнение композиции, не разрешение создать названные файлы сейчас.

Read цепочка: WorldStateService.read → WorldStateQueryFacade.read →
read port/adapter → существующий MapCellQueryFacade или metadata reader.
Mutation цепочка: WorldStateService.update → WorldStateMutationFacade.update
→ UOW → typed domain handler → write port/adapter → repository.
Common facade не импортирует domain kernels/scorers/buffers. Handler не
реализует pack IO и не создаёт вложенный независимый commit.

## 4. Атомарность — вся доменная команда, не отдельный SQL-вызов

Одна команда задаёт логическую атомарную операцию. Проверки состояния,
зависящие от неё записи и фиксация должны иметь одну UOW/один commit.
WorldStateMutationFacade вызывает WorldStateUnitOfWork.transaction;
existing atomic domain owner присоединяется к той же транзакции через
Database.transaction_if_needed, repository не коммитит посередине.
Внутри внешнего UOW владение остаётся у него; вложенный вызов не объявляет
операцию durable раньше outer commit. Ошибка выходит наружу с rollback
outer UOW; проглоченный отказ после частичной записи недопустим.
Если требуется независимый recoverable nested scope, savepoint protocol
нужно согласовать отдельно — считать его уже существующим нельзя.

SQL-only patch change не переписывает immutable pack. Обычный SQL UOW
не обеспечивает атомарность SQL + файлов + внешних side effects. Такие
сценарии требуют отдельного publication protocol; не прятать их внутрь CRUD.
State-dependent checks выполняются под соответствующей concurrency защитой;
простой preflight read до transaction не предотвращает lost update.
Existing Database.transaction_on использует BEGIN IMMEDIATE, но согласованное
чтение mutable SQL + concurrently published pack отдельно проверяется при
freeze: не объявлять весь read view атомарным только по факту SQL BEGIN.

## 5. Контрольный сценарий: добавить одну fine_cell жидкости

AddLiquidCell — typed domain command, не generic upsert(MapCell).
Предлагаемое имя LiquidCellMutationHandler.apply обозначает runtime domain
handler, не существующий класс. До реализации определить его владельца,
точный application path и нормативный жидкостный контракт. Не помещать
handler по умолчанию в pure surface hydrology generator.

Минимальный сценарий:
1. Передать world/адрес FineCellScope и material key через typed command;
   точные поля, ожидания occupancy и retry semantics заморозить до кода.
2. Открыть одну UOW и прочитать доступное состояние, на котором основана
   допустимость изменения; проверки материала/занятости/детализации — у домена.
3. При недостаточном материальном представлении вернуть явный отказ/сигнал
   NeedsMaterialization без записи; не запускать generate из CRUD read.
4. Подготовить selective patch всех обязательных связанных полей жидкости.
   Terrain/material/hydrology меняются согласованно по доменному контракту;
   не требовать всех полей всегда и не изобретать liquid volume schema.
5. Записать дельту и другие обязательные записи одной команды, затем commit.
   Ошибка любого шага — rollback всей операции. Если требуется изменение
   water-object state, оно входит в ту же логическую операцию с явным owner.
6. Read по WP-20 возвращает новое состояние поверх неизменённого pack.

Одна адресованная клетка не означает одну SQL-колонку или одну SQL-команду.
Create клетки также не тождественен добавлению жидкости: base cell может
уже существовать, а команда добавляет/изменяет её содержимое через patch.
Распространение на соседей/смешение жидкостей не запускается неявно generic CRUD.

Обязательное сохранение чужих patch полей: temperature/rainfall/другие
override остаются прежними, если команда не меняет их явно. Различать
«поле не передано», «установить значение» и «снять override»; nullable
whole-row upsert не заменяет этот контракт. Повтор команды/retry и конфликт
двух изменений — отдельные обязательные semantics до implementation,
не объявлять idempotency существующей по наличию operation_uid в предложении.

Existing gaps, не считать готовой реализацией сценария:
- SqliteMapCellRepository.upsert_terrain_skeleton при conflict обновляет
  только system_terrain; согласованная liquid mutation этим не покрыта.
- PatchStoreService.upsert_patch делегирует generic repository.upsert;
  сохранение всех незатронутых полей этой цепочкой не доказано.
- MapCellHydrology — surface-top metadata, не доказанный контракт runtime
  жидкости в произвольном x/y/z. Пример задаёт требования к CRUD/UOW,
  а не разрешает расширить hydrology POJO/SQL или реализовать fluid simulation.

## 6. Следующий пункт проработки и приёмка

Следующий design пункт WS-0A в исходном transition плане:
- freeze capability matrix: какой backend/consumer поддерживает какой port;
- freeze typed commands/results/refusals и право владения UOW;
- поклассово указать методы join UOW, selective update и error propagation;
- определить domain owner/path жидкостной команды только если её реализация
  будет включена отдельной явной задачей;
- закрепить tests: read-only backend без write methods, отказ до записи,
  rollback после первой из нескольких записей, сохранение других patch полей,
  concurrent changes/retry и отсутствие read-generate.

Эти проверки — target acceptance, tests сейчас не пишутся. Конкретные commands,
транзакционные fixtures и typing targets фиксируются после contract freeze.
Пример с жидкостью можно проверить модельным тестом selective patch/UOW,
не реализуя runtime fluids ради теста. Snapshot не нужен и не имитируется.
После приёмки WS-0A обновить исходные WS-1/WS-2 class/method/file ledger;
не выполнять сразу весь переход и не помечать WS-0 DONE этой записью.

## 7. WS-0A — окончательная карта архитектурных обязанностей для приёмки

Архитектурная единица — одна typed операция над состоянием, а не generic
table CRUD и не новый snapshot. Одна shared реализация состоит из query и
mutation фасадов; backend capability не обязана совпадать с public API целиком.
Предлагаемый ранее LiquidCellMutationHandler не вводится в WS-0A: fluid rules
ещё не определены, поэтому рабочий контрольный механизм — selective cell patch
с подготовленным доменным изменением, а не придуманная модель жидкости.

Полные target пути относительно backend/app/. Существующие методы помечены
existing, остальные target. Перечень классов этого шага замкнут: helper с чужой
responsibility в facade/adapter запрещён независимо от числа строк.

| Класс | Домен/слой и точный файл | Ответственность / допустимые зависимости |
|---|---|---|
| IWorldStateRead / IWorldStateCreate / IWorldStateUpdate / IWorldStateDelete / IWorldStateCrud | worldState application ports, application/worldState/contracts/worldStateCrud.py | Protocol capabilities; только worldState/domain DTO, без concrete db/services |
| IWorldMetadataRead / IWorldMetadataWrite / IWorldCellRead / IWorldCellPatchWrite / IWorldRegionRead / IWorldRegionWrite | worldState application backend ports, application/worldState/contracts/domainPorts.py | Typed backend capabilities; read-only pack не реализует IWorldCellPatchWrite |
| IWorldStateUnitOfWork | worldState application port, application/worldState/contracts/unitOfWork.py | transaction(existing session или None) → AsyncContextManager[WorldMutationSession]; без domain policy |
| WorldMutationSession | worldState application contract, тот же contracts/unitOfWork.py | Явный request token владельца UOW: связь с одной DB/транзакцией, root/join и rollback-only; не state/snapshot store |
| WorldStateService | worldState application, application/worldState/service/worldStateService.py | Публичная реализация capabilities; делегирует фасадам, не собственные loops/validation/SQL |
| WorldStateQueryFacade | worldState application, application/worldState/service/worldStateQueryFacade.py | Проверяет query variant и маршрутизирует в один read port; merged/raw metadata семантику не переопределяет |
| WorldStateMutationFacade | worldState application, application/worldState/service/worldStateMutationFacade.py | Проверяет capability, открывает/присоединяет UOW, вызывает один mutation adapter; adapter делает typed handler dispatch; не доменные алгоритмы |
| WorldStateUnitOfWork | worldState application infra adapter, application/worldState/unitOfWork/worldStateUnitOfWork.py | Реализует UOW port через Database.transaction; root commit/rollback и session validation |
| WorldMetadataAdapter | worldState integration, application/worldState/adapters/metadata/worldMetadataAdapter.py | Read и поддержанные metadata commands → existing WorldService/NamedLocationService |
| WorldCellAdapter | worldState integration, application/worldState/adapters/cells/worldCellAdapter.py | Merged/raw read и dispatch patch commands к handler; no fluid/topology/merge kernel |
| ICellPatchStorage | worldState application storage port, application/worldState/contracts/domainPorts.py | Только get/write/delete patch row под переданным UOW, без domain dispatch |
| CellPatchStorageAdapter | worldState storage integration, application/worldState/adapters/cells/cellPatchStorageAdapter.py | Маппинг typed selective delta к SqliteMapCellRepository; не вызывает domain handler |
| WorldRegionAdapter | worldState integration, application/worldState/adapters/regions/worldRegionAdapter.py | Region read → existing repo/mapping, mutation → existing domain owner; no coverage/growth kernel |
| CellPatchMutationHandler | cell patch application domain, application/worldData/mapCells/mutations/cellPatchMutationHandler.py | Применить typed selective patch/field reset в UOW; не materialize/resolve жидкость |
| WorldMutationHandler | world metadata application domain, application/worldData/registries/mutations/worldMutationHandler.py | Typed world command → WorldService.create/update/delete/edit_region, с существующим validation |
| LocationMutationHandler | location application domain, application/worldData/locations/mutations/locationMutationHandler.py | Typed location command → NamedLocationService.create/update/delete, включая existing occupancy validation |
| RegionStateMutationHandler | regions application domain, application/worldData/regions/stateChange/mutations/regionStateMutationHandler.py | Typed evaluation/tombstone → StateChangeConsumer; не второй region_states writer |
| FieldChange[T] / Keep / SetValue[T] / ResetOverride / CellPatchDelta | map cell dataModel, dataModel/mapCells/patch/cellPatchDelta.py | Typed намерение изменения полей клетки; никакого SQL/merge over pack |
| WorldState read queries/results | worldState dataModel, dataModel/worldState/query.py | Typed read variants и результаты |
| WorldState mutation commands/results | worldState dataModel, dataModel/worldState/mutation.py | Tagged команды и исходы; domain DTO импортируются, не дублируются |
| WorldStateAddress | worldState dataModel, dataModel/worldState/address.py | world_uid и explicit domain target; не обобщённый raw dict |
| IMutationHandler[CommandT,ResultT] | worldState application port, application/worldState/contracts/mutationHandler.py | async apply(command: CommandT, *, session: WorldMutationSession) → соответствующий typed MutationOutcome[ResultT]; не Any/cast dispatch |
| IWorldReadContextProvider / ResolvedWorldReadContext | worldState application contracts, application/worldState/contracts/domainPorts.py | async resolve(world_uid) → context с existing World либо typed WorldNotFound; context request-local, не snapshot |
| WorldReadContextProvider | worldState application integration, application/worldState/service/worldReadContextProvider.py | resolve делегирует WorldService.get_by_id один раз на read request; не normalize/repair/planning |
| MapCell.has_patch_payload (existing класс, target метод) | DB row/persistence model, db/models/mapCell.py | Полный предикат живого payload §10; не gameplay merge и не generator policy |
| Database.transaction_context (existing класс, target метод) / DatabaseTransactionContext (target enum) | DB infra, db/database.py | NONE / OWNED / INHERITED для вызывающей task; публичный pre-BEGIN запрос, без открытия/присоединения транзакции |
| GuardedConnection.owns_transaction (existing класс, target property) | DB infra, db/guardedConnection.py | Только ownership текущей task, включая explicit/implicit transaction; не глобальный флаг чужой connection transaction |

Domain mutation handler — application owner. Конкретные домены generators
не реализуют эти storage handlers и потребляют IWorldStateRead/готовые inputs.
worldState не импортирует concrete handlers: typed backend ports передаются
конструктором, adapters делегируют handlers. Handler пишет через узкий port
или публичный existing domain service; прямое повторное WorldStateService
из handler/adapter запрещено. Это исключает consumer→facade→adapter→facade цикл.

## 8. Методы, capabilities и исходы

### 8.1 Public и backend методы

| Метод | Вход → выход / фиксированная семантика |
|---|---|
| WorldStateService.read | read query → соответствующий typed read result; делегирует WorldStateQueryFacade.read |
| WorldStateService.create/update/delete | typed command + session=None → mutation result; делегирует соответствующему WorldStateMutationFacade методу |
| WorldStateQueryFacade.read | MetadataQuery / ObjectQuery / CellQuery / AreaQuery / ChunkQuery / RegionQuery → variant-specific result; один resolve world context и одна ветка backend read |
| WorldStateMutationFacade.create/update/delete | command + session → capability check до UOW, dispatch внутри UOW, result после успешного выхода; arbitrary batch не поддерживается |
| WorldMetadataAdapter.read | metadata/object query + ResolvedWorldReadContext → context.world либо NamedLocationService.get_by_id/get_all; без повторного world resolve/capture/generate |
| WorldMetadataAdapter.create/update/delete | world/location/declaration command → WorldMutationHandler.apply или LocationMutationHandler.apply |
| WorldCellAdapter.read | query + context: ResolvedWorldReadContext → merged cell/area через MapCellQueryFacade.get_cell/get_cells/get_scene_volume(context.world,...); explicit raw chunk → WorldPackReader.chunk_exists/read_wilderness_chunk; нового World lookup нет |
| WorldCellAdapter.create_patch/update_patch/reset_patch | соответствующая patch command + session → CellPatchMutationHandler.apply; не generic full-row upsert |
| CellPatchStorageAdapter.get_patch_at/write_patch_fields/delete_patch_at | Полный адрес + typed delta/mode для write + session → patch snapshot/storage outcome; storage-only, делегирует repository |
| WorldRegionAdapter.read | Existing RegionQuery/RegionResult: object/selected UID → IRegionStateRepository.get/get_many; полный world-scoped materialization read → get_by_world(world_uid), включая tombstones; mapping через existing state_from_row в RegionState |
| WorldRegionAdapter.evaluate/tombstone | existing RegionEvaluation/uid+audit marker + session → RegionStateMutationHandler.apply → existing StateChangeConsumer.evaluate/tombstone |
| CellPatchMutationHandler.apply | cell patch command + session → checked patch outcome; read/modify/write одной patch row под UOW |
| WorldMutationHandler.apply | world/declaration command + session → WorldService.create/update/delete/edit_region |
| LocationMutationHandler.apply | location command + session → NamedLocationService.create/update/delete |
| RegionStateMutationHandler.apply | evaluate/tombstone command + session → StateChangeConsumer.evaluate/tombstone; произвольный set current_type запрещён |

CellPatchMutationHandler принимает ICellPatchStorage, реализованный отдельным
CellPatchStorageAdapter. WorldCellAdapter принимает готовый handler, а не
является его storage dependency. DI-граф ацикличен:
repository → storage adapter → handler → WorldCellAdapter → mutation facade
→ WorldStateService (порядок создания). Runtime вызовы идут в обратную сторону.
Нет setter binding, lazy service locator или ссылки handler→WorldCellAdapter.

WorldReadContextProvider.resolve(world_uid) вызывает WorldService.get_by_id;
только existing WorldDataNotFoundError отображается в typed WorldNotFound,
storage/validation errors пробрасываются. ResolvedWorldReadContext содержит
world: World и проверенный world_uid; это application DTO, допустим existing
DB model import, без repository dependency в public dataModel query DTO.
WorldStateQueryFacade.read резолвит context один раз и передаёт его всем
subreads этой query; внутри batch get_cells world повторно не загружается.
WorldMetadataAdapter для world query использует context.world, а не читает
WorldService второй раз. Context не process cache, не snapshot и не гарантия
атомарного SQL+pack read. Для уже загруженных application inputs reuse context
допускается только в рамках того же request, не скрытым optional World аргументом.

WorldMutationHandler, LocationMutationHandler, RegionStateMutationHandler и
CellPatchMutationHandler реализуют IMutationHandler с собственным command
union/result binding. Adapter получает соответствующий специализированный
Protocol, а не concrete handler или callable[...,Any]. Конкретные командные
DTO/overloads и mapping каждого existing public method — обязательная часть
WS-0; интерфейс apply и его UOW obligation уже зафиксированы, это не опция.

**Async read contract:** async port гарантирует awaitable interface, но не
объявляется nonblocking I/O/CPU interface. WorldPackReader sync disk/decode,
SurfacePlanningCapture.capture и sync render kernel outline можно вызывать
напрямую в owning application task с existing поведением. Async outline entry
await'ит свои SQL reads, после них делегирует sync render. Не вводить неявный
to_thread/run_in_executor и не передавать туда session/SQL connection. Перенос
тяжёлого sync compute в workers — отдельное performance-изменение с явным
ownership/immutable inputs и проверкой; async синтаксис сам blocking не убирает.

### 8.2 Supported-operation matrix

| Backend/target | Read | Create | Update | Delete/reset |
|---|---|---|---|---|
| Immutable persisted pack L0/L2/raw chunk | Да | Нет в CRUD | Нет в CRUD | Нет в CRUD; pack lifecycle отдельно |
| Cell patch | merged/raw patch query по виду запроса | CREATE_ONLY patch row | UPDATE_ONLY либо явно UPSERT command | Reset перечисленных override полей/всей patch row; base cell не удаляет |
| World source metadata | Да | WorldService.create | WorldService.update | WorldService.delete по его existing policy |
| Named location | Да | NamedLocationService.create | NamedLocationService.update | NamedLocationService.delete по existing policy |
| Declared region | Да как source metadata | WorldService.edit_region(AddRegion) | WorldService.edit_region(UpdateRegion) | WorldService.edit_region(RemoveRegion), existing reconcile |
| Runtime RegionState | Да | Не самостоятельный public CRUD create | Typed evaluate через single writer | Typed tombstone через single writer |
| Snapshot | Нет backend в этом треке | Нет | Нет | Нет |

Нет методов pack.update/delete, возвращающих NotImplementedError. Read-only
consumers получают только IWorldStateRead. Public WorldStateService вправе
предоставить full composition capabilities для поддерживаемого command union,
это не обещание поддержки каждой операции для каждого target.

### 8.3 Typed результаты и ошибки

WorldStateReadResult сохраняет связь query→payload: MetadataResult,
ObjectResult, CellResult, AreaResult, ChunkResult, RegionResult. Общие исходы
Found/Missing/UnsupportedOperation не маскируют storage/validation ошибки.
CellResult сообщает фактический source layer/LOD через existing merged view;
L0 fallback не выдаётся за готовую fine materialization.

Mutation result: Applied с affected scope и completion=COMMITTED либо PENDING
внешнего UOW; Refused с typed reason. Reasons: UnsupportedOperation,
ForbiddenOperation, InvalidInput, AlreadyExists, NotFound, NeedsMaterialization,
AmbientTransactionRequiresSession, InvalidMutationSession.
Это target discriminators DTO, не разбор строк exception.message. Domain
validation producer сохраняет свои existing typed diagnostics.

UnsupportedOperation и caller restrictions проверяются до записи. Expected
domain refusal тоже проходит через abort UOW, а не successful normal exit
после частичного apply. Наружу Refused преобразуется только после rollback
собственного root. При joined session refusal выходит typed исключением и
помечает session rollback-only: внешний owner не получает успешный commit.
Storage errors не превращаются в Refused/Missing; исключение выходит наружу.
Широкий except→return False/None запрещён.

## 9. Явный UOW protocol по методам

WorldStateUnitOfWork.transaction(session=None) создаёт root session и вызывает
existing Database.transaction: один main connection, BEGIN IMMEDIATE,
один commit при успехе, rollback на exception/BaseException/cancellation.
session с другой DB/закрытым root отвергается до записи. Join допускается
только через явно переданный WorldMutationSession того же root; ambient
transaction без такого token не подхватывается молча. На таких legacy entry
caller ledger должен явно добавить session binding до перевода write path.
**Проверка до BEGIN:** WorldStateUnitOfWork.transaction сначала вызывает
Database.transaction_context. При OWNED (explicit/implicit ambient текущей
task, включая bootstrap scope) или INHERITED (ContextVar унаследован от другой
task) и session=None — typed AmbientTransactionRequiresSession, без BEGIN,
commit, rollback или изменения существующей ambient транзакции. Facade root
отображает этот preflight отказ в Refused. Не дожидаться sqlite nested BEGIN
error. Session не той DB/root/task либо закрытая → InvalidMutationSession.
При валидном session DB context и main connection ownership должны совпасть;
несовпадение отвергается до SQL. Session bootstrap connection к main UOW не
присоединяется. Собственный UOW другой независимой task не считается ambient
этой task: NONE → обычное ожидание connection gate/SQL lock, не false refusal.

Database.transaction_context — DB-owned adapter над existing _in_transaction
и guarded connection ownership; worldState не импортирует private ContextVar.
Внутри DB различается inherited owner и owner текущей task, а implicit main
transaction проверяется через GuardedConnection.owns_transaction. Нельзя
использовать только connection.in_transaction: он видит и чужую task.
Эти два existing-file изменения входят в WS-2b явно; базовое поведение
Database.transaction_if_needed для остальных callers не меняется попутно.

WorldStateUnitOfWork.transaction(session=existing) не делает BEGIN/COMMIT.
При любом исключении помечает root rollback-only и пробрасывает исходную
ошибку. WorldMutationSession.mark_rollback_only(reason) не хранит domain
state, только cause неуспешного UOW. Root после yield проверяет rollback-only;
если caller поймал вложенную ошибку, root всё равно возбуждает abort до
выхода из Database.transaction и получает rollback. Savepoint/recoverable
subtransaction не реализуются в этом треке.

WorldStateMutationFacade не перехватывает domain refusal внутри transaction
для normal return. Для root преобразование abort→Refused делается снаружи
context; для join exception остаётся внешнему owner. Applied(PENDING) не
объявляется durable result и не вызывает внешние side effects. Новая
callback/outbox/event система не вводится попутно.

WorldService._write_scope/DeclaredRegionEditor.transaction existing вызывают
Database.transaction_if_needed и присоединяются к root SQL transaction.
NamedLocationService/StateChangeConsumer/repos используют тот же connection;
не вводить второй Database instance. Existing BaseRepository commit guard
проверяется tests, не считается достаточным по названию метода.

Согласованность mutable SQL + pack files НЕ обеспечивается одним SQL lock.
В WS-0A generic selective patch handler основывает read/modify/write на SQL
patch row; whole-pack consistent liquid preconditions не имитируются.
Операция, которой для admissibility нужен стабильный pack view, не включается
в supported commands до отдельного publication/read-consistency контракта.
Это сохраняет snapshot/publication scope отдельно, а не вводит псевдоатомарность.
Session task-bound: не передавать её в compute workers, другие concurrent
tasks или другой connection. Отмена задачи инвалидирует session после rollback;
повторный запуск создаёт новую root, а не переиспользует закрытый token.

## 10. Selective cell patch — точная граница storage

CellPatchDelta содержит explicit FieldChange. Первый mutable whitelist:
system_terrain, system_material, system_building_element, temperature_base,
rainfall, location_uid, hydrology, travel_modifier_override, **is_structural**.
Cell patch domain владеет контрактом; Hydrology — typed MapCellHydrology с
existing surface семантикой, не новая runtime-liquid модель.

**Preservation-only, НЕ mutation/read expansion первого контракта:**
system_danger_level_override, gap_width_override, railing_sides, system_facing,
display_facing, glass_material, system_grade_uid. Selective writer обязан
сохранить эти колонки, storage emptiness обязан их учитывать. Новый CRUD
не даёт им Set/Reset и не обещает их gameplay-проекцию через CellContribution;
запрос их изменения → typed UnsupportedOperation, без SQL. Их существующие
доменные writers/readers не удаляются. world_uid/x/y/z — immutable identity,
layer_kind — audit stamp по правилам ниже, не mutable FieldChange.

Для каждого поля: Keep — SQL колонку не менять; SetValue(value) — установить
валидное непустое значение; ResetOverride — снять override и открыть нижний
слой WP-20 (SQL NULL там, где existing storage это допускает). SetValue(None)
не является четвёртым состоянием; явное значение NULL/void, если понадобится
домену, требует отдельного контракта. Layer-kind stamp не определяет field
presence и не фильтрует read, существующий field-wise merge сохраняется.

**is_structural без смены WP-20:** Keep сохраняет колонку;
SetValue(True) устанавливает structural contribution; ResetOverride пишет
existing MapCell default False (SQL NOT NULL), снимая ТОЛЬКО этот patch flag.
SetValue(False) отвергается как InvalidInput: existing merge structural-OR не
позволяет false скрыть structural=True нижнего слоя. Reset не обещает снести
base structure. False-as-explicit-negative override требует отдельного
wire/merge контракта вне WS-0A, без молчаливой замены текущей семантики.

**INSERT/NOT NULL и stamp:** command несёт optional typed
layer_kind: MapCellPatchLayerKind, это provenance stamp, не источник priority.
Новая CREATE_ONLY/UPSERT row: layer_kind = явно переданный kind, иначе
MapCellPatchLayerPolicy.canonical_defaults().default_kind (сейчас STRUCTURE);
is_structural = SetValue(True) либо existing default из MapCell (сейчас False).
Identity берётся из адреса; nullable columns вне SetValue получают existing
model defaults. На UPDATE stamp сохраняется, если не передан явно; явный stamp
меняет только audit column. Model/SQL defaults должны совпасть в contract test.
В application SQL-building не копировать literals 'structure'/0: defaults
читаются из existing policy/model. Для существующей строки Keep не пишет default.

PatchWriteMode: CREATE_ONLY → AlreadyExists если patch row уже есть;
UPDATE_ONLY → NotFound если patch row отсутствует; UPSERT только у explicit
UpsertCellPatch command. Эти проверки выполняются в той же SQL UOW, не
перед BEGIN. Наличие base cell в pack не равно наличию patch row.

CellPatchMutationHandler.apply вызывает ICellPatchStorage через отдельный
CellPatchStorageAdapter, который делегирует новые точные методы repository:
- IMapCellRepository.get_patch_at / SqliteMapCellRepository.get_patch_at:
  полный composite key (world_uid,x,y,z) → MapCell или None;
- IMapCellRepository.write_patch_fields /
  SqliteMapCellRepository.write_patch_fields: адрес + typed delta + mode →
  storage outcome; whitelist SQL columns, no INSERT OR REPLACE;
- IMapCellRepository.delete_patch_at / SqliteMapCellRepository.delete_patch_at:
  тот же полный key, удалить только SQL patch row, не pack/весь мир.

Repository implementation остаётся в existing sqlite/mapCellRepository.py,
port — existing iMapCellRepository.py; serializers/DB mapper — единственная
граница typed hydrology → wire dict. SQL для отсутствующей строки заполняет
обязательные поля из existing MapCell/POJO defaults, не новых literals.
Пустая после reset patch row удаляется только по MapCell.has_patch_payload:
`bool(is_structural) OR any(value IS NOT NULL)` для полного набора nullable
payload columns: system_terrain, system_building_element, system_material,
travel_modifier_override, system_danger_level_override, gap_width_override,
temperature_base, rainfall, location_uid, railing_sides, system_facing,
display_facing, glass_material, hydrology, system_grade_uid. Identity и
layer_kind не payload. 0/0.0/пустая строка/[]/{} считаются present (не NULL);
их нормализация/валидация принадлежит producer, а не empty-row cleanup.
Строка с одним travel_modifier_override=0.0 или одним preservation-only полем
не удаляется. Has_payload принадлежит DB row model и используется handler
после чтения полной patch row в той же UOW, не raw SQL predicate по whitelist.
Тест сверяет полный список nullable payload полей с schema/model: новая
колонка требует явного freeze, иначе test fail; молчаливый auto-ignore запрещён.

CellContribution.has_data и MergedCellView.has_any_data — ДРУГИЕ predicates,
только видимости read. В WS-2b явно включена узкая правка existing
dataModel/worldPack/wire/mergeMapCells.py: добавить travel_modifier_override
и true is_structural в has_data; добавить travel_modifier_override в
has_any_data (structural там уже есть). Иначе PatchStoreService filters/scene
read потеряют structural-only/travel-only вклад. Никакое из этих has_data
не используется для storage deletion. Preservation-only read fields этим
не расширяются. Незатронутые existing колонки сохраняются.

PatchStoreService.upsert_patch/MapCellService.save_pass — legacy/backends
по caller ledger, не canonical selective command implementation. Их перевод
не подменяется вызовом generic BaseRepository.upsert: existing
INSERT OR REPLACE опасен для незатронутых полей. Создание нового scoped delete
не делегирует MapCellService.clear(world_uid).

Повтор SetValue той же величиной идемпотентен по состоянию; CREATE_ONLY retry
даёт AlreadyExists, а не фиктивный exactly-once success. Durable operation
dedup/event log и relative AddVolume не вводятся. Concurrent disjoint-field
updates сохраняют оба изменения при serialized SQL UOW; для одного поля
порядок commit определяет последнюю запись. Domain-specific optimistic
preconditions требуют typed command, не скрытой смены этой политики.

### 10.1 Два семейства SQL-writer: явная coexistence policy

Single-writer для map_cell_patches НЕ заявляется. Existing generation/bulk
SQL paths и новый selective handler могут сосуществовать, но только с
явно записанными write masks и transaction semantics. Pack bake пишет
WorldPackWriter, не обязан писать map_cell_patches; legacy climate/bootstrap/
save_pass SQL paths действительно пишут ту же patch table и учитываются.

Для разрешённых selective writers frozen policy: disjoint поля сохраняются,
одно и то же поле получает значение последней успешно committed SQL записи.
Это осознанный last-committed-write-wins, а не приоритет gameplay над bake и
не claim snapshot freshness. Partial legacy SQL с WHERE может не принять
запись; тогда его existing rejected/skip outcome не объявляется Applied.
Main/bootstrap connections к одной SQLite DB сериализуются SQLite write lock;
bootstrap UOW не join main session. BUSY/ошибка abort'ит свою операцию,
без внутреннего silent retry/replay команды. SQL serialization не заменяет
семантическую field mask и не разрешает whole-row replacement.

Обязательный live writer ledger WS-0 (все callers, включая debug/import/tests):
- MapCellService.save_pass → upsert_terrain_skeleton/upsert_climate_fields/
  upsert_ore_markers/upsert_cave_carve: exact SET/WHERE masks из existing SQL;
- BootstrapMapCellWriter.write_terrain/write_terrain_chunk_batch/write_climate:
  те же masks/insert semantics на bootstrap_conn;
- MapCellService.save_settlement_surface → upsert_settlement_surface;
- MapCellService.save_generated → insert_bulk_ignore (existing row не меняет),
  insert_terrain_bulk — insert, duplicate не превращается в replace;
- PatchStoreService.upsert_patch, MapCellService.import_from_json и любой
  прямой IMapCellRepository.upsert → unsafe whole-row path до caller cutover;
- MapCellService.clear/delete_by_world — destructive administrative scope,
  не fine_cell delete и не background bake.

До включения нового write facade для live callers unsafe whole-row пути
должны быть переведены на explicit typed selective intent либо оставлены
только в явно отдельной administrative replace/reset операции без конкурирующих
live writes. Нельзя автоматически вывести Keep/Reset из MapCell defaults:
старый DTO не кодирует намерение. Каждый caller обязан явно выбрать новое
намерение; если это ещё не определено, rollout writer блокируется, а не
вводится runtime compatibility fallback к INSERT OR REPLACE.
Это release gate WS-0/WS-4, не объявление single-writer и не новая snapshot/
row-version система. WS-2b тестирует backend до live exposure; включение
caller маршрута в WS-4 происходит вместе с закрытием unsafe paths.

Конфликтные tests: climate bootstrap и gameplay delta одной клетки при
разных полях сохраняют оба значения; при одном поле финал соответствует
порядку успешных commits; rollback проигравшей/ошибочной transaction не
затирает committed peer. Whole-row replace в live writer ledger — fail.
Если понадобится «gameplay всегда сильнее bake», требуется отдельный
field provenance/priority контракт; текущая схема layer_kind его не выражает.

Жидкостный пример §5 проверяет атомарность и сохранение полей модельным
CellPatchDelta, не обещает поддержку AddLiquidCell сейчас. Нет runtime
fluid handler, симуляции соседей или volume schema в supported matrix.

## 11. Переход классов и композиция

1. WS-1: capabilities/DTO/UOW ports. Все contracts frozen до writer coding.
2. WS-2a: query facade/adapters + WorldStateService.read над existing backends;
   read не зависит от незавершённого writer или snapshot.
3. WS-2b: UOW/session + selective cell patch repository/handler/adapter.
   Включает явные target изменения Database.transaction_context,
   GuardedConnection.owns_transaction, MapCell.has_patch_payload,
   CellContribution.has_data/MergedCellView.has_any_data. Проверить
   rollback/selective merge/read visibility до metadata/region writer bindings;
   live exposure только после gate unsafe writers §10.1.
4. WS-2c: world/location/region handlers, capability binding и atomic write
   joins. Каждый public path имеет один owner; StateChangeConsumer сохраняет
   single-writer, DeclaredRegionEditor reconciliation не дублируется.
5. WS-3/WS-4: перевод callers с явным capability/session по основному ledger;
   затем WS-5 удаление legacy wrappers после исполняемой parity-проверки.

WS-2a/b/c — предлагаемая детализация исходного WS-2, подлежит приёмке вместе
с этой картой. Не выполнять три подшага за один заход. Root method map
основного transition плана приведён к этой карте; другие dependencies PC-11
не меняются молча.

Новые leaf direct counts: contracts 5 (init/worldStateCrud/domainPorts/
unitOfWork/mutationHandler); service 5 (init/worldStateService/
worldStateQueryFacade/worldStateMutationFacade/worldReadContextProvider);
unitOfWork 2; adapters/metadata и adapters/regions
по 2, adapters/cells 3 (init/worldCellAdapter/cellPatchStorageAdapter);
mapCells/mutations 2; registries/mutations 2; locations/mutations 2;
regions/stateChange/mutations 2; dataModel/mapCells root 1(init), patch 2.
Existing mapCells6→6, pack/read22→22, regions8→8, core/container9→9,
db/repositories28→28 — новых root files там нет. Domain owner folders
mutations — выделенные leaf, не additions в переполненные roots.
Дальнейшее разбиение DTO/SQL требует обновить карту до кода, не misc/helpers.

## 12. Архитектурная приёмка WS-0A

Проверить отдельно от numerical baseline:
- read-only adapter не реализует writer, generator consumer не получает writer;
- public facade/adapter не импортирует domain kernels или private buffers;
- unsupported/refused не дают частичной записи, raw и merged read различаются;
- root commit единственный; join другого DB/root отвергается;
- rollback-only срабатывает даже если внешний caller поймал nested exception;
- ошибка второй SQL-записи откатывает первую; cancellation тоже откатывает;
- selective delta сохраняет unrelated patch поля; reset открывает base layer;
- structural-only/travel-only patch видна через get_patch_at/bbox/scene read;
- preservation-only поля живы для persistence, но не writable в первом DTO;
- has_patch_payload не удаляет travel=0.0, structural=True, {} и legacy-only поле;
- CREATE_ONLY/UPSERT вставляют оба NOT NULL поля из model/policy defaults;
- structural=False как Set отвергается, Reset не отменяет base structural=True;
- ambient без session → typed отказ до BEGIN; чужая independent task не ambient;
- world_uid→World resolve один раз на read/batch, ошибки missing/storage различимы;
- handler Protocol apply binding проверяется typing; dispatch остаётся adapter-owned;
- selective multiwriter conflict policy и отсутствие unsafe live whole-row writer;
- async read parity допускает existing sync delegation, без неявного offload UOW;
- composite-key delete затрагивает одну patch row, не соседнюю клетку;
- update-only/create-only/explicit upsert различаются; retry semantics честные;
- ни read, ни CRUD write не генерируют fine cells и не делают snapshot lookup.

До реализации закрепить конкретные test cases/commands в implementation
ledger WS-1/WS-2a/b/c. Это проверка реализации, не дополнительный выбор
архитектуры. Полный query DTO freeze WS-0 и integration order с PC-11 остаются
отдельными design gates исходного плана. Snapshot/fluid simulation не являются
скрытыми prerequisites закрытия WS-0A. Статус WS-0A остаётся OPEN до приёмки.

Target проверок реализации: новый tests leaf backend/tests/worldState/
(init + test_capabilities.py + test_uow.py + test_cell_patch.py +
test_facade_wiring.py = 5 direct files); typing leaf под ним
(positive.py, negative.py, pyright.valid.json, pyright.invalid.json = 4).
Не добавлять tests root module в существующую плоскую tests папку.
Команда target runtime suites из корня при PYTHONPATH=backend:
`python -m unittest discover -s backend/tests/worldState -p "test_*.py"`.
Typing targets: `pyright -p backend/tests/worldState/typing/pyright.valid.json`
(0 errors) и `pyright -p backend/tests/worldState/typing/pyright.invalid.json`
(exact expected code/location diagnostics, не только общее число).
Пока это планируемые файлы/команды: их сейчас не создавать и не сообщать
как запущенные. Existing WP-20/region/patch regression suite names добавляются
в WS-0 caller ledger до старта implementation.

## 13. Freeze review 2026-10-26 — решения по девяти замечаниям

| № | Решение / где зафиксировано | Обязательное evidence реализации |
|---|---|---|
| 1 | §10: is_structural включён с existing structural-OR семантикой; семь других колонок preservation-only | Keep/SetTrue/Reset, запрет SetFalse, сохранение legacy-only полей |
| 2 | §10: new row stamp из explicit kind или MapCellPatchLayerPolicy; bool из SetTrue либо MapCell default; UPDATE Keep не пишет default | CREATE_ONLY/UPSERT NOT NULL и model/SQL default parity |
| 3 | §7/10: отдельный MapCell.has_patch_payload по всем nullable payload columns + true structural; read predicates исправляются узко | travel=0.0/structural-only/legacy-only/non-NULL empty collections не теряются |
| 4 | §7/8: facade capability+UOW, adapter dispatch; IMutationHandler.apply Protocol в class map, не future optional helper | Typed handler binding, ацикличный DI и ownership test |
| 5 | §7/8: WorldReadContextProvider.resolve → WorldService.get_by_id один раз; WorldCellAdapter получает ResolvedWorldReadContext | WorldNotFound vs storage error, one lookup на batch |
| 6 | §9: Database-owned transaction_context и GuardedConnection ownership; ambient без token отклоняется до BEGIN | OWNED/INHERITED отказ без nested BEGIN, NONE другой task корректно ждёт |
| 7 | Transition §3 синхронизирован: одна команда имеет root UOW, arbitrary cross-domain batch не возникает | Root/join/rollback-only parity в facade writer tests |
| 8 | §10.1: сознательное selective multiwriter coexistence, field last-committed-wins; unsafe replacement блокирует live rollout | Exact writer masks/callers, main↔bootstrap conflict/rollback tests, отсутствие unsafe live replace |
| 9 | §8: async port — awaitable protocol с existing sync disk/decode/render delegation; не обещание nonblocking | Read/output parity; session не уходит в executor/worker |

Все девять решений — зафиксированный design proposal для приёмки мастером. Они не
объявляют соответствующие runtime fixes существующими и не снимают WS-0
gate полного command/query/error/caller ledger. Конкретные DTO variants
и тестовые команды связываются с этими решениями до implementation.
