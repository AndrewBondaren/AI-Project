# DAG invocation runtime и bake admission

Дата: 2026-11-03. Delivery plan к [GEN §§4/18](gen-dag-node-dependency.md). Scope: проектирование; production code этим документом не изменён. Решения о поведении приняты пользователем; ниже фиксируется техническая декомпозиция. Первый срез R1–R4 имеет определённый контракт и может реализовываться на Python-нодах GEN-DAG-1 в тестовом binding. Подключение родителей GEN возможно только после R5–R7 и их domain-contract gates. Параллельные самостоятельные full/light bake одного мира отменены.

## 1. Проверенные ограничения исходного кода

| Файл от backend/app | AS-IS и необходимое изменение |
|---|---|
| `dataModel/engine/dag/identity.py` | ExecutionIdentity.result_key = execution/node/attempt; добавить invocation, сохранить node как provenance |
| `application/engine/runtime/dag/context/dagContext.py` | counters/open/current/errors индексируются NodeId, второй открытый attempt того же NodeId запрещён; перевод на invocation |
| `application/engine/runtime/dag/executionState.py` | statuses/attempt_passes по NodeId; переход на invocation, отдельная адресация plan instance |
| `application/engine/contracts/outputRef.py` | producer NodeId + typed Output; сохраняется как декларация, при binding разрешается в конкретный invocation |
| `application/engine/runtime/graphs/graphCompiler.py` | статический граф определений; добавить проверку calls, не превращая calls в deps |
| `application/engine/runtime/dag/dagExecutor.py` | исполнение Python уровнями; готовые invocation должны возвращаться в этот scheduler после CALL |
| `application/engine/runtime/execution/nodeRunner.py` | terminal outcome и глобальная gate/error policy; failure вызываемого child сначала доставляется caller |
| `application/cancellation/typed/sessionSnapshot.py` | snapshot запрещает RUNNING; schema индексирована NodeId; нужен versioned durable checkpoint |
| `application/cancellation/typed/snapshotStore.py` | обычный dict в памяти; restart durability отсутствует |
| `application/engine/runtime/dagEngine.py` | snapshot на cancellation, RESPONSE удаляет snapshot; WAIT_INPUT должен сохранять execution |
| `application/publication/service/operationLedger.py`, `contracts/operationStore.py` | publication claim/terminal в CommitScope, не compute admission |
| `dataModel/artifacts/lifecycle/operation/kinds.py`, `db/migrations/0001_initial.sql` | publication kinds только snapshot_apply/pack_activation/gameplay_start; нельзя объявить existing ledger готовым bake registry |

Нормативный predecessor: `docs/tz_engine_node_context.md`, `.cursor/plans/dag-typing-1.md`. Перед изменением production-контрактов R1 синхронизирует ТЗ. Не менять одноимённые legacy graphs/execution классы вместо target `runtime/`.

## 2. Identity, область данных и lifecycle

В `identity.py`: InvocationId, PlanInstanceId, CallKey, WaitId — строгие отдельные типы идентификаторов; ordinal/revision — целые неотрицательные типы, attempt > 0. ExecutionIdentity = execution_id, invocation_id, node_id, attempt, plan_revision. result_key = (execution_id, invocation_id, attempt).

InvocationRecord: execution_id, invocation_id, node_id, plan_instance_id, caller_invocation_id?, caller_step?, call_key?, contract_id/version, input, continuation?, step_index, status, attempt_counter, dependency_bindings, terminal?. Input/continuation/terminal сериализуются только через зарегистрированный versioned codec соответствующего POJO. Не pickle и не произвольный import path из persisted JSON. Payload boundary может быть bytes; в API ноды нет Any/dict с произвольным содержимым.

InvocationStatus: READY → RUNNING → SUCCEEDED | FAILED | CANCELLED | WAITING_CALLS | WAITING_INPUT | WAITING_OPERATION. WAITING_* не terminal Output и не NodeStatus.BLOCKED. WAITING_CALLS → READY после terminal всех children; WAITING_INPUT/OPERATION → READY после принятого события. Узел может проходить несколько continuation steps. Attempt — запуск одного step; retry увеличивает attempt, но не step_index или invocation_id. Переход на следующий step фиксируется вместе с потреблением события; replay восстанавливает тот же step.

Уникальность dispatch: (execution_id, caller_invocation_id, caller_step, call_key). Идентификатор child выделяется при первой фиксации dispatch; повторный такой dispatch возвращает существующий child. Иной Input/target под тем же ключом — runtime contract violation, не новый вызов.

PlanInstance — экземпляр статического closure зависимостей target. Root plan получает один instance; каждый CALL — новый. Внутри instance одному NodeId соответствует один invocation, общие deps diamond-графа исполняются один раз. RequiredOutput разрешается только через dependency_bindings этого instance. Cross-instance данные передаются явно через CALL Input/RETURN; implicit latest-by-NodeId запрещён. Для callee explicit Input заменяет prepare_input; для его статических prerequisite nodes сохраняется prepare_input(read_view). Порядковые deps и declared reads продолжают исполняться/проверяться в local instance. В R1–R4 cross-phase CALL и LLM callee запрещены compile validation; существующий root PRE/LLM/POST flow сохраняется.

Повторный pass root использует прежние invocation для прежнего логического root plan; это re-execution/reuse, не новый CALL. Изменение root plan membership регистрируется как новый plan instance с явными binding, а не переносом outputs по NodeId. Invalidation следует фактическим DependencyRead с identity, не всем совпадающим NodeId разных instances. Reuse между независимыми calls в первой версии отсутствует; bake dedup находится на другом уровне.

## 3. API ноды и компиляция

Новые immutable контракты в `contracts/invocation/`:

- `callTarget.py`: CallTarget[I,O,E](node_id, contract_id, version, input_type, output_type, error_types). NodeContract.calls — tuple targets, по умолчанию пустой.
- `nodeStep.py`: Complete[O](output), Call[I,O,E,S](key,target,input,state), CallGroup[S](requests,state), WaitInput[S,U](wait_spec,state), WaitOperation[S](operation_ref,state). Call — sugar для группы из одного элемента; join всегда ALL.
- `resumeEvent.py`: CallSuccess[O], CallFailure[E], CallCancelled, CallRuntimeFailure с typed diagnostic reference; CallResults предоставляет `get(key,target)` с проверкой target и возвращает типизированный union. InputReceived[U] и OperationCompleted — отдельные события. Не представлять undeclared exception как выдуманный domain E.
- `continuationContract.py`: ContinuationContract[S](contract_id,version,state_type) и InputWaitContract[U](contract_id,version,input_type). В NodeContract они optional; обязательны при соответствующих outcomes.

Новый `nodeTypes/resumablePythonNode.py`: ResumablePythonNode[I,O,E,S] наследует общий BaseNode; `start(input:I) -> NodeStep[O,S]`, `resume(state:S,event:ResumeEvent) -> NodeStep[O,S]`. Существующий PythonNode.execute(I)->O не ломается: runtime нормализует O в Complete. Результат generic event читается через typed target accessor; pyright positive/negative fixtures проверяют отсутствие смешения I/O/E разных targets. LLM node не получает этот API в первом срезе.

Compiler проверяет declaration/runtime target equality, регистрацию и contract versions, сериализуемый state, уникальные call keys группы, nonempty group, допустимую фазу. В первой версии rejects циклы графа calls и объединённого графа calls/deps: рекурсивные workflow не нужны этому flow. Runtime также проверяет фактически возвращённые targets и лимит числа invocation из execution options (обязательное положительное значение), чтобы статически acyclic graph не допускал бесконечную цепочку continuation calls.

Child declared failure после исчерпания принятой retry policy становится CallFailure; siblings продолжаются. После всех terminal children родитель получает результаты и решает, вернуть собственный E или продолжить. Child не вызывает глобальный REPLAN раньше caller. Root failure/error_policy сохраняет прежний binding. Runtime contract corruption останавливает execution с диагностикой; это не domain failure.

## 4. Scheduler и надёжная фиксация

`runtime/invocations/invocationCoordinator.py` — единственный writer invocation transitions. `dagExecutor.py` остаётся исполнителем; второй executor не создаётся. Worker выполняет один start/resume step и освобождает слот после outcome. WAIT не удерживает semaphore. READY queue включает независимые invocation и их prerequisite closures. Общий worker limit на execution, без отдельного неограниченного лимита children.

После CALL атомарный checkpoint содержит parent state + WAITING_CALLS + список children/keys. Только затем children допускаются к запуску. После завершения child checkpoint содержит terminal и готовность parent, если закрыт join. Перед resume фиксируется потребляемый event/step; completion нового step фиксирует его эффект над runtime state. Crash может повторить Python step: гарантируется однократное принятие RETURN, а не exactly-once произвольного внешнего эффекта. Доменным writes обязательно stable operation id.

Durable store: новый `contracts/invocation/executionStore.py`, async load/create/claim/checkpoint/release. Checkpoint CAS по revision и fencing token владельца execution. В первой версии один coordinator владеет execution; параллелизм workers внутри него. Ownership lease защищает от двух HTTP/resume workers; stale coordinator не может сохранить checkpoint. Смена владельца после expiry увеличивает fence. Lease timestamps определяет DB adapter, не часы клиента.

DB таблица `dag_executions`: execution_id PK, schema_version, revision, owner_id?, fence, lease_until?, status, checkpoint_blob, checksum. Checkpoint содержит весь immutable invocation graph, catalog, cursor, typed extension, pending/consumed events. CAS write одной строки обеспечивает согласованность parent/children. Terminal сохраняется для duplicate delivery, RESPONSE больше не удаляет durable запись немедленно; retention cleanup вне первого среза. Memory store остаётся test adapter той же семантики, не production гарантия.

Checkpoint сохраняется coordinator на каждой принятой границе step; работающие workers представлены persisted READY/in-flight metadata без сериализации coroutine. После crash незавершённый step повторяется с новым attempt; in-memory SessionSnapshot invariant «нет RUNNING» сохраняется для quiescent export, durable envelope явно различает recoverable in-flight и terminal. Нельзя просто разрешить RUNNING старому snapshot validator.

Schema v2: неподдерживаемые старые durable envelopes отклоняются до restore; существующие v1 memory snapshots не объявляются переживающими deploy. Existing static nodes проходят общий invocation path; parallel legacy runtime ради совместимости не создаётся. Registry/plan/continuation version mismatch — typed restore failure без автоматической генерации.

## 5. WAIT_INPUT и cancellation (после core)

WaitSpec: wait_id, input contract/version, trusted interaction binding reference, expected interaction revision, intermediate response POJO. Persisted binding хранит world/player/session identities и invocation/step; эти поля устанавливает application, не входящий UID. ResumeInput: wait_id, request_id, expected_revision, typed payload, authenticated context. Adapter проверяет session ownership и policy evidence; store атомарно потребляет одно событие и повышает revision. Duplicate request_id с тем же payload возвращает прежний receipt; с другим — conflict. Stale/out-of-order/чужой session request отклоняется без изменения execution.

DAGEngine result union: Completed[O], Waiting[IntermediateResponse], Failed[diagnostic]. Waiting сохраняет durable execution, закрывает HTTP без terminal domain Output. Другие READY задачи execution могут завершиться до quiescent Waiting; новый HTTP запрос resume загружает и claims execution. Cancel execution прекращает его непубликованные child invocations и отключает operation waiters; это не WAIT_INPUT. Node-level cancellation является CallCancelled в join. Explicit cancellation bake operation — отдельный domain API, не cancellation caller.

## 6. Bake admission и ownership

Владелец compute admission: новый `application/worldData/bakeOperations/`, POJO `dataModel/world/bakeOperation/`, SQL adapter `db/repositories/sqlite/bakeOperations/`. Это отдельная compute responsibility, не копия publication ledger: существующие publication transactions/holders остаются у `application/publication` и snapshotCore. Compute record хранит ссылку на publication operation, если она создаётся. Не расширять generic DAG model полями world/seed.

BakeRequest: world_uid, BakeKind(LIGHT,FULL,DETAILED), canonical scope, source_revision, preparation_contract_version, parameters_fingerprint. Canonical encoding — versioned typed JSON с сортировкой object keys, без сортировки семантически ordered arrays; digest SHA-256 от всех перечисленных полей. Domain request builder обязан включать seed и все влияющие настройки в fingerprint. Concrete builders проходят отдельную приёмку R7; универсальный hash произвольного HTTP body запрещён.

BakeAdmission = Started(operation_ref,owner_token) | Joined(operation_ref) | BakeConflict(active_operation_ref). Актуальный готовый результат читается доменным readiness read до compute admission; после захвата повторная проверка предотвращает redundant compute после гонки. Доступ к refs проверяет application authorization.

Таблицы: `bake_operations` (operation_id PK, world_uid FK, kind, fingerprint, request_blob/version, status, owner_id, fence, lease_until, result/error envelope, publication_operation_id nullable); `bake_world_claims` (world_uid PK, operation_id UNIQUE FK); `bake_waiters` (operation_id,execution_id,invocation_id,step_index,delivery_status; composite UNIQUE). SQLite admission — короткая BEGIN IMMEDIATE transaction: проверить world claim; equivalent → JOIN; другой fingerprint → BakeConflict; пусто → insert operation + claim. Работа внутри транзакции не исполняется. Автоматической очереди нет; lease expiry не делает мир свободным, а разрешает recover того же operation.

Operation states: PENDING/RUNNING/PUBLISHING/RECOVERY_REQUIRED/SUCCEEDED/FAILED/CANCELLED. Незавершённая операция сохраняет claim. Worker recovery claims operation с новым fence; heartbeat продлевает lease условно по owner/fence. Fencing проверяется в транзакции каждой видимой изменяющей записи/публикации. Подготовка пишет только operation-owned staging; если существующий bake пишет live данные раньше публикации, R7 обязан сначала дать guarded write boundary — запуск без неё запрещён.

Terminal result и освобождение world claim фиксируются атомарно с publication evidence либо после доказуемого rollback. Неизвестный исход commit → RECOVERY_REQUIRED, claim удерживается до чтения authoritative publication result. Existing publication ledger terminal используется как evidence, повторная публикация вслепую запрещена. Старый worker не имеет права ни публиковать, ни удалять новый claim.

Worker запускается application service lifecycle независимо от HTTP task. DB PENDING records — восстанавливаемая очередь уже принятых операций, не очередь конфликтующих bake. Waiters получают terminal через периодическое чтение durable record; notification — лишь ускорение, её потеря не теряет RETURN. Доставка имеет key(operation_id,invocation_id,step_index); caller checkpoint deduplicates её. Это избегает требования одной распределённой транзакции между DAG checkpoint и bake store. При потере ack повторяется subscribe/delivery с теми же ключами.

Отмена waiter удаляет/помечает только subscription. Даже без waiters worker завершает bake и публикацию. Полный cancellation execution не убивает этот worker. Full/light/detailed одного мира не выполняются как самостоятельные операции одновременно; внутренние tasks наследуют operation id/fence. Bake разных миров допускается параллельно.

## 7. File map и порядок поставки

Все пути ниже относительно backend/app, tests — backend/tests. В каждом шаге перед edit сверить actual usages и локальные инструкции; не добавлять все файлы заранее. Новые подпапки ограничивают ответственность, существующие большие каталоги не реструктурировать попутно.

| Шаг | Изменения | Exit criterion |
|---|---|---|
| R1 Identity/contracts | `dataModel/engine/dag/identity.py`, новые `invocations/{record,state,event}.py`; `contracts/invocation/{callTarget,nodeStep,resumeEvent,continuationContract,executionStore}.py`; nodeContract, новый resumablePythonNode; docs/tz_engine_node_context | exact typed contracts из §§2–3, static positive/negative typing; без production caller |
| R2 Compiler/catalog | runtime/graphs/graphCompiler, registration validation; runtime/dag/context/{dagContext,dagReadView,catalogSnapshot,resultInvalidation}; executionState, records, traces/diagnostics, snapshotMetadata; новый invocations/planInstance.py | два одинаковых NodeId изолированы, local deps diamond исполняется один раз; запрещены cross-instance implicit reads |
| R3 Scheduler | новый runtime/invocations/invocationCoordinator; runtime/execution/{nodeRunner,nodeOutcome,pythonNodeExecutor}, contracts/pythonExecutor; dagExecutor, executionPlan, dagEngine | два последовательных CALL и join ALL, error/cancel result routing, workers=1 без deadlock; static DAG regression |
| R4 Durable recovery | новый runtime/invocations/checkpointCodec; runtime/dag/lifecycle/executionSnapshotService, cancellation/typed/sessionSnapshot; новый db/repositories/sqlite/dagExecutions/executionStore; SQL schema и memory adapter | restart в каждом окне CALL/RETURN, CAS/lease и duplicate dispatch; первый core-срез завершён |
| R5 User wait | новые runtime/invocations/inputWaitCoordinator и contracts/invocation/inputWait; executionBindings/dagEngine; typed application interaction binding | HTTP wait/resume без cancellation; stale/duplicate/foreign-session checks на test adapter |
| R6 Bake service | новые bakeOperation/{request,record,admission}.py; bakeOperations/{service,store,worker}.py; sqlite/bakeOperations/{operationStore,waiterStore}.py; SQL | два независимых DB connections: один compute, equivalent join, full/light/detailed conflict, detached waiter, worker recovery/fence |
| R7 Concrete integration | domain request builders, public bake write/publication boundaries, DI registration, concrete GEN bindings после domain POJO freeze | реальный bake защищён на всех writes; два world_creation calls дают корректные accepted_base/detailed results; API interaction/load contracts приняты |

SQL: schema definitions в существующем `db/migrations/0001_initial.sql` синхронизируются с repository policy; если в целевом deployment уже применяется incremental migration, добавляется штатная upgrade migration без reset пользовательской БД. Это deployment check R4/R6, не разрешение удалить данные. DI wiring делается по реально используемому target composition, не legacy import redirect.

Первый срез R1–R4: Python-ноды GEN-DAG-1 в тестовом binding, вызовы в одной фазе; WAIT_INPUT, bake service и production parents не входят в его критерий готовности. Это ограничение scope, не скрытый stub поддерживаемого API. Декларации WAIT outcomes вводятся в R5, хотя их целевая модель определена здесь.

## 8. Проверки и завершение

Добавить `tests/dag_typing/invocations/` с contract/compiler, repeated calls, parallel join, error/cancel, dispatch/return replay, scoped reads и recovery tests. Extend existing `typing/valid.py`, `invalid.py` и configs; run existing `tests/dag_typing` целиком после R4, включая LLM group и pass/replan regression. Тесты storage используют отдельный temporary SQLite file и два соединения, а restart — новый coordinator/store instance с тем же файлом, не reuse dict.

Crash matrix: до/после CALL checkpoint; во время child step; после terminal child до parent resume; после resume эффекта до checkpoint; stale owner после lease takeover; после publication commit до delivery. Для внешнего эффекта проверяется operation idempotency, а не ложная гарантия единственного вызова Python функции.

R6 acceptance: full+equivalent full → один operation; full+light/full+ detailed/detailed+другой scope → BakeConflict; другой мир → параллельно; отказ от всех waiters не прекращает worker; unknown publication commit не освобождает claim. Group acceptance: child error не отменяет siblings, parent видит весь набор результатов.

План первого core-среза готов к реализации после чтения этого документа и текущих repository instructions, без нового продуктового выбора. Production acceptance всего GEN остаётся заблокирована R5–R7 и существующими доменными gates. Не объявлять completed по одним contract tests: нужны migration существующего catalog и restart evidence. Измерение ускорения full/light вне scope и отменено пользователем.

## 9. Независимое ревью R1–R4 от 2026-11-03

**CHANGES REQUIRED на `87bbfb08`.** Для повторного ревью открыты четыре находки. Первые две воспроизводятся через `DAGEngine.run` в одном живом процессе без отмены и без конкурирующего владельца.

### REV-1 · P1 · R2/R3 · Повторное исполнение PRE-зависимости POST-корня

Через GraphCompiler собрать план из двух Python-нод: `Pre` в PRE_LLM и invocation root `Post` в POST_LLM со статической зависимостью от `Pre`. Записать вызовы обеих нод в список. За один pass engine вернул успешный результат и последовательность `pre, pre, post`. После выполнения PRE-фазы workflow scheduler снова выделяет весь closure корня и исполняет `Pre` в POST. **Критерий закрытия:** через публичный engine получить `pre, post`; POST должен использовать результат уже выполненного PRE invocation в том же root instance. Сохранить изоляцию одноимённых нод в отдельных CALL instances. [dagExecutor.py:175–177](../../backend/app/application/engine/runtime/dag/dagExecutor.py#L175) · [invocationCoordinator.py:54–59](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L54)

### REV-2 · P1 · R4 · Потеря lease во время apply_effects

На временной SQLite БД задать `lease_seconds=2`. В `apply_effects` увеличить счётчик вызовов и выполнить `await asyncio.sleep(2.2)`. Первый `run` выполнил эффект и вернул `OwnershipConflict`. Второе соединение прочитало checkpoint с `response=None`. Затем `resume` повторил эффект (счётчик 2), снова вернул `OwnershipConflict`, response остался пустым. Scheduler продлевает lease при ожидании invocation workers, но в ожидании этого lifecycle hook продления нет. **Критерий закрытия:** живой owner сохраняет lease на протяжении hook, первый run записывает terminal response; повторный resume возвращает сохранённый ответ при счётчике 1. Сохранить отказ stale owner после действительного takeover. [dagEngine.py:219–223](../../backend/app/application/engine/runtime/dagEngine.py#L219) · [dagExecutor.py:111–114](../../backend/app/application/engine/runtime/dag/dagExecutor.py#L111)

### REV-3 · P1 · R4 · SQLiteExecutionStore подтверждает чужую транзакцию

На соединении A выполнить `INSERT INTO caller VALUES (7)` без commit. Соединение B видит пустую таблицу. Вызвать `SQLiteExecutionStore(A).create(...)`, затем выполнить caller rollback на A. После rollback соединение B прочитало `[(7,)]`: выход из `with self.db` внутри store закоммитил обе записи. Та же граница транзакции используется в claim, checkpoint, renew и release. **Критерий закрытия:** изолировать собственную транзакцию store либо отклонять вызов на соединении с открытой caller transaction до записи. Двухсоединительная регрессия должна показать, что после rollback caller его строка отсутствует, а при его собственном commit становится видимой на B. Проверить также путь отказа, чтобы store не откатывал чужой DML. [executionStore.py:14–18](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L14) · [executionStore.py:35–70](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L35)

### REV-4 · P2 · R3 · diagnostic_ref указывает на invocation без диагностики

В diamond fixture заставить `Merge.execute` выбросить исключение. Это prerequisite дочернего `world_creation`. Родителю доставлен `CallRuntimeFailure` со ссылкой на `call-2/world_creation`. В сохранённом checkpoint по этому адресу 0 диагностик, у `call-2/merge` — 1. При распространении FAILED scheduler помечает зависимый child, а RETURN ссылается на identity этого пропущенного child. **Критерий закрытия:** родитель получает ссылку на исходную диагностику prerequisite либо на записанную диагностику child с причиной отказа. Регрессия должна разрешить фактически возвращённый diagnostic_ref в сохранённом checkpoint. [invocationCoordinator.py:194–200](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L194) · [invocationCoordinator.py:225–230](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L225)

### Проверки и граница R4

На проверенном дереве полный прогон 19 модулей `dag_typing` дал **356 тестов OK за 17,016 с**, включая typing, LLM, pass/replan и invocation recovery. Обычный discover от `tests/dag_typing` нашёл 0 тестов. Команда для повторения из `backend` в PowerShell:

```powershell
$mods = rg --files tests/dag_typing -g 'test_*.py' | ForEach-Object { ($_ -replace '\.py$','') -replace '[\\/]','.' }
../.venv/Scripts/python.exe -B -m unittest $mods
```

Четыре контрпримера проверены отдельно от штатного набора. При повторном предъявлении приложить результат каждой новой регрессии и полного прогона.

**Отдельная проверка deployment.** На БД со схемой до R4 и уже применённой migration version 1 штатный `apply_migrations()` пропускает `0001_initial.sql`. Вызов `store.load` завершился `OperationalError: no such table: dag_executions`. По действующей политике локальная схема обновляется через recreate. Проверенный restart относится к БД, где таблица уже создана. Обновление существующей БД с сохранением данных остаётся отдельным deployment gate по §7. [database.py:66–86](../../backend/app/db/database.py#L66) · [0001_initial.sql:1966](../../backend/app/db/migrations/0001_initial.sql#L1966)

## 10. Повторное ревью R1–R4 на `c3427f36` от 2026-11-03

**CHANGES REQUIRED. Открыты два P1: REV-2 и новая REV-5.** REV-1 закрыта на исходном PRE→POST: журнал одного pass содержит `pre, post`, а POST читает опубликованный PRE output. REV-3 закрыта: все пять пишущих методов SQLite store отказали при активной транзакции caller, и второе соединение увидело запись только после caller commit. REV-4 закрыта: возвращённый родителю diagnostic_ref разрешился в сохранённую диагностику с указанием отказавшего prerequisite. [Регрессии §9](../../backend/tests/dag_typing/invocations/test_world_calls.py#L341)

### REV-2 · P1 · R4 · OPEN для lease в одну секунду

Регрессия с `lease_seconds=2` прошла. Для воспроизведения оставшегося случая взять тот же SQLite-сценарий с двумя соединениями, установить допустимое `lease_seconds=1` и задержку `apply_effects` 2,2 с. Без конкурирующего владельца первый `run` выполнил эффект и вернул `OwnershipConflict`; второе соединение прочитало `response=None`. Последующий `resume` увеличил счётчик эффектов до 2, снова вернул `OwnershipConflict` и не сохранил ответ. До смены целой секунды продление записывает прежний `unixepoch()+1`, а после смены секунды условие `lease_until > unixepoch()` уже ложно. [executionStore.py:43](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L43) · [executionStore.py:67–68](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L67) · [dagEngine.py:158–160](../../backend/app/application/engine/runtime/dagEngine.py#L158)

**Критерий закрытия.** При lease в 1 секунду и hook длительностью 2,2 с живой owner завершает run. Второе соединение видит terminal response и возвращает тот же ответ через resume при счётчике эффектов 1. Сохранить проверку fencing после действительного takeover.

### REV-5 · P1 · R2/R3 · OPEN · Подмена terminal root через prior_outputs

На fixture `Group` с MemoryExecutionStore первый `run_invocation` сохранил `detailed_ref="joined"`. Повторить вызов с тем же execution ID, передав в `prior_outputs` запись с адресом завершённого root, чужими `contract_id/version` и значением `detailed_ref="forged"`. Caller получил `"forged"`, хотя независимое чтение checkpoint из того же store вернуло `"joined"`. При восстановлении `bind_published` допускает root в набор результатов предыдущей фазы и перезаписывает его terminal в памяти до возврата. [dagExecutor.py:84–88](../../backend/app/application/engine/runtime/dag/dagExecutor.py#L84) · [invocationCoordinator.py:75–89](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L75)

**Критерий закрытия.** Принимать результаты только от допустимых узлов предыдущих фаз с соответствующим контрактом. Конфликтующая запись для root должна вызвать отказ. Следующий обычный повторный вызов должен вернуть сохранённое `"joined"`; проверить его совпадение с checkpoint. Сохранить прохождение PRE→POST из REV-1.

В этом ревью полный прогон по команде §9 дал **360 тестов OK за 21,970 с** (19 модулей). Scoped `git diff --check` по исправлению прошёл. Оба открытых контрпримера воспроизведены отдельно от штатного набора.

## 11. Повторное ревью R1–R4 на `7e4ea620` от 2026-11-03

**CHANGES REQUIRED. REV-2 и REV-5 закрыты по критериям §10. Единственная открытая находка — REV-6 (P1).**

- **REV-2 — CLOSED.** При lease в 1 секунду и `apply_effects` длительностью 2,2 секунды первый run завершился успешно. Второе SQLite-соединение прочитало статус COMPLETED, а resume вернул тот же ответ при счётчике эффектов 1. Дополнительная проба подтвердила семантику renew: после expiry прежний владелец может продлить тот же fence до takeover; после takeover его renew получает OwnershipConflict. [executionStore.py:62–71](../../backend/app/db/repositories/sqlite/dagExecutions/executionStore.py#L62)
- **REV-5 — CLOSED.** Попытки передать завершённый root в prior_outputs отклонены как с правильным, так и с чужим контрактом. Обычная повторная доставка вернула сохранённое `"joined"`; checkpoint совпал с исходным. [test_world_calls.py:423–445](../../backend/tests/dag_typing/invocations/test_world_calls.py#L423)

### REV-6 · P1 · R2/R4 · OPEN · Чужой DependencyRead в prior_outputs делает checkpoint невосстановимым

1. На MemoryExecutionStore собрать план `Pre → Post` с invocation root `Post`. У `Pre` нет зависимостей. Штатным конструктором создать для него OutputRecord с правильными identity, типом результата, contract_id и version. В reads передать один обязательный DependencyRead с результатом из того же execution, но с invocation_id `call-9/foreign`, который отсутствует в dependency_bindings узла `Pre`.
2. Передать запись в `run_invocation(..., prior_outputs=(output,))`. Первый вызов вернул SUCCEEDED и сохранил checkpoint ревизии 2. При привязке проверяются узел и контракт, затем `record.reads = output.reads` переносит чужую ссылку в граф. [invocationCoordinator.py:75–102](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L75)
3. Повторить вызов для того же execution ID без prior_outputs. Вместо сохранённого результата caller получил `RestoreFailure("invalid invocation checkpoint")` с причиной `foreign dependency read`: restore проверяет принадлежность результата к dependency_bindings. [checkpointCodec.py:81–85](../../backend/app/application/engine/runtime/invocations/checkpointCodec.py#L81)

**Критерий закрытия.** При привязке prior_outputs проверять принадлежность каждого непустого `reads[].result` к execution и dependency_bindings принимающего узла до сохранения результата. Регрессия должна получить отказ уже при первом вызове, затем успешно продолжить тот же execution с корректным prior output и прочитать сохранённый terminal при повторной доставке.

В независимом ревью полный прогон по команде §9 дал **362 теста OK за 34,934 с** (19 модулей). Scoped `git diff --check` прошёл. Контрпример REV-6 воспроизведён отдельно от штатного набора.

#### Запускаемый пример REV-6 на `cd6746a7`

Из `backend` в PowerShell выполнить блок целиком. В нём `Source` — PRE-узел без зависимостей, `Left` — POST-корень. Все три вызова используют один store и один execution ID; между первым и вторым вызовом меняется только поле `reads` переданного результата.

```powershell
@'
from tests.dag_typing.invocations import test_world_calls as f
from tests.snapshotCore.support.fixtures import run_async
from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
from app.application.engine.contracts.invocation.executionStore import RestoreFailure
from app.dataModel.engine.dag.executionPhase import ExecutionPhase
from app.dataModel.engine.dag.identity import ExecutionIdentity
from app.dataModel.engine.dag.records import DependencyRead, OutputRecord

async def probe():
    registry, bindings = f.NodeRegistry(), f.GraphBindings()
    for node, deps, phase in ((f.Source, (), ExecutionPhase.PRE_LLM),
                              (f.Left, (f.Source.id,), ExecutionPhase.POST_LLM)):
        contract = f.NodeContract(f.Payload, f.Payload, f.ContractId(node.id),
                                  f.ContractVersion("1"), (), error_types=())
        registry.register_python(node, f.FakeExecutor, contract)
        bindings.nodes[node.id] = node(deps=deps, phase=phase)
    compiler = f.GraphCompiler(registry, bindings, compile_rules=lambda _: (),
                               evaluate_rules=lambda *_: True)
    compiler.precompile()
    plan = compiler.compile(f.GraphRuleState(), invocation_root=f.Left.id)
    executor, _ = f.runtime()
    store = MemoryExecutionStore()
    execution = f.ExecutionId("probe")
    def identity(node, invocation):
        return ExecutionIdentity(execution_id=execution, node_id=node, invocation_id=invocation,
                                 attempt=1, plan_revision="1")
    foreign = DependencyRead(producer="foreign", contract_id="foreign", contract_version="1",
                             required=True, result=identity("foreign", "call-9/foreign"))
    def prior(reads):
        return OutputRecord[f.Payload](identity=identity(f.Source.id, "root/" + f.Source.id),
                                       contract_id=f.Source.id, contract_version="1",
                                       output=f.Payload(), reads=reads)
    for label, rows in (("foreign", (prior((foreign,)),)), ("correct", (prior(()),)), ("replay", ())):
        try:
            result = await executor.run_invocation(plan, execution, f.Left.id, f.PlanRevision("1"),
                                                   store, owner="a", workers=1, invocation_limit=2,
                                                   prior_outputs=rows)
            print(label, result.status)
        except RestoreFailure as exc:
            print(label, type(exc).__name__, exc.__cause__)
    print("revision", (await store.load(execution)).revision)

run_async(probe())
'@ | ../.venv/Scripts/python.exe -B -
```

Фактический вывод на `cd6746a7`:

```text
foreign SUCCEEDED
correct RestoreFailure foreign dependency read
replay RestoreFailure foreign dependency read
revision 2
```

После исправления ожидается отказ на `foreign` до записи чужого read, затем `correct SUCCEEDED` и `replay SUCCEEDED` с тем же terminal. На этом коммите полный прогон §9 дал 362 теста OK за 36,385 с.

## 12. Итог независимого ревью R1–R4 от 2026-11-03

**PASS. REV-6 закрыта. Все находки REV-1…6 закрыты.** Проверено рабочее дерево с исправлением поверх `cd6746a7`. При привязке prior output и при восстановлении checkpoint применяется одно условие: для каждого непустого `read.result` execution ID совпадает с execution ID узла, а invocation ID входит в его `dependency_bindings`. При привязке отказ происходит до изменения записи. [bind_published](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L89) · [accepts_reads](../../backend/app/dataModel/engine/dag/invocations/record.py#L49) · [restore](../../backend/app/application/engine/runtime/invocations/checkpointCodec.py#L82)

Пример §11 повторён на MemoryExecutionStore и на временной SQLite БД с новым соединением перед каждым вызовом. Результаты для одного execution ID:

| Вызов | Результат для caller | Сохранённый checkpoint |
|---|---|---|
| `foreign` с чужим DependencyRead | RestoreFailure | Ревизия 0, чужой read не записан |
| `correct` с исправленным prior output | SUCCEEDED | Terminal сохранён на ревизии 2 |
| `replay` без prior outputs | SUCCEEDED, тот же terminal | Checkpoint совпадает с сохранённым после `correct`, ревизия 2 |

Полный прогон по команде §9: **363 теста OK за 38,133 с** (19 модулей `dag_typing`), включая [регрессию REV-6](../../backend/tests/dag_typing/invocations/test_world_calls.py#L396). Scoped `git diff --check` прошёл. Вердикт относится к R1–R4; граница deployment для существующей БД описана в §9.

## 13. Независимое ревью R5 WAIT_INPUT от 2026-11-03

**CHANGES REQUIRED. Открыты REV-7 (P1) и REV-8 (P2).** Проверен 21 файл R5 на `bbefa875` по §5 и приёмке R5, включая четыре добавленных файла: `contracts/invocation/inputWait.py`, `runtime/invocations/inputWaitCoordinator.py`, `dataModel/engine/dag/invocations/inputWait.py`, `tests/dag_typing/invocations/test_input_wait.py`. На момент начала ревью эти файлы уже tracked в коммите, рабочее дерево было чистым. Остальные изменения вне scope. Код при ревью не менялся.

### REV-7 · P1 · R5 · Отмена execution недоступна при активном владельце lease

**Минимальное воспроизведение.** Через публичный `DAGEngine.run` запустить fixture `Ask`, задержав `start` на `asyncio.Event`. После входа в `start` через новый engine и второе соединение того же SQLite-файла вызвать `cancel_execution`. Затем освободить `start` и отправить ответ через `accept_input`.

**Ожидалось:** запрос отмены достигает активного владельца, execution прекращается, поздний input отклоняется. **Фактически:** `cancel_execution` выбрасывает `OwnershipConflict` при попытке захватить lease; намерение отмены не сохраняется. Первый engine возвращает `Waiting`, а последующий `accept_input` принимает ответ и возвращает receipt ревизии 4. При постоянно продлеваемом lease отмена этим API недоступна. Отдельная проба с предварительно захваченным lease также показала `OwnershipConflict` и неизменный checkpoint. [dagEngine.py:141](../../backend/app/application/engine/runtime/dagEngine.py#L141) · [cancel_execution:186](../../backend/app/application/engine/runtime/dagEngine.py#L186)

**Критерий закрытия:** отмена активного execution принимается и наблюдается владельцем без нарушения fencing. После её применения непубликованные invocation прекращаются, поздний input отклоняется. Добавить двухсоединительную регрессию с живым owner; сохранить отказ stale owner после takeover.

### REV-8 · P2 · R5 · Accepted-input checkpoint допускает отсутствие continuation

**Минимальное воспроизведение.** Выполнить `run → Waiting → accept_input`. До запуска continuation удалить у ожидавшей invocation `continuation` и `state_contract`, сохранив accepted input и receipt. Записать повреждённый checkpoint через store с корректной checksum. Через новый engine вызвать публичный `resume`.

**Ожидалось:** `RestoreFailure` до запуска пользовательского кода. **Фактически:** `CheckpointCodec.decode` принимает checkpoint. Executor повторно вызывает `start` вместо `resume(state, InputReceived)`; fixture завершается `InputConflict("undeclared input contract or reused wait id")`. Для произвольной ноды это также допускает повторение эффектов `start`. Проверка наличия continuation выполнена только для pending wait, но отсутствует для accepted input, чей следующий step ещё должен исполняться. [inputWaitCoordinator.py:105](../../backend/app/application/engine/runtime/invocations/inputWaitCoordinator.py#L105) · [dagExecutor.py:151](../../backend/app/application/engine/runtime/dag/dagExecutor.py#L151)

**Критерий закрытия:** восстановление отвергает accepted-input checkpoint без необходимого continuation/state contract до исполнения ноды. Регрессия должна сохранить штатный restart после receipt и до continuation, а также повторное чтение завершённого execution.

### Проверки и границы ревью R5

- При одном worker ожидающий child освобождает слот, готовая соседняя ветка завершается, caller остаётся на join ALL. `Waiting` возвращается без terminal output.
- HTTP fixture возвращает промежуточный ответ, затем новый engine и новое SQLite-соединение доставляют payload в типизированный `InputReceived` нужного continuation. Unknown wait, stale revision, чужая session и запрещённый payload отклоняются без изменения checkpoint; отдельные пробы чужих world/player также дали `PermissionError` без изменения checkpoint. Точный повтор возвращает прежний receipt, другой payload конфликтует.
- Restart после WAIT_INPUT и отдельно после receipt проходит при пересоздании engine/соединения. Конкурентная доставка через два соединения сохранила один receipt; оба вызова получили одинаковый receipt.
- Отмена quiescent execution и отказ позднему ответу проходят. Существующая проверка дочерней отмены сохраняет `CallCancelled` в join; WAIT_INPUT остаётся отдельным состоянием.
- Форма checkpoint R4 без новых полей восстанавливается. Регрессия REV-6 для чужого `DependencyRead` в prior_outputs проходит.

Полный набор по команде §9: **367 тестов OK за 51,761 с** (20 модулей), включая положительные и точные отрицательные проверки Pyright. Первый прогон: 367 тестов за 49,305 с, один `OwnershipConflict` в `test_slow_effect_retains_lease`. Отдельный повтор обоих lease-тестов прошёл (2 теста за 8,860 с), затем прошёл повторный полный набор. Причина единичного сбоя не установлена. В sandbox создание Windows asyncio loop зависало в `socketpair` до исполнения тестов; завершённые прогоны и asyncio-пробы выполнены вне sandbox. Scoped `git diff --check` прошёл.

**Правило apply_patch.** [.agents/skills/implement-plan/SKILL.md:51](../../.agents/skills/implement-plan/SKILL.md#L51) требует каждую ручную правку, включая создание и удаление файлов, выполнять инструментом `apply_patch`; запись через Python/PowerShell/другой shell запрещена, просмотр diff обязателен отдельно. Соблюдение в прошлой реализации **не установлено**: журнал её инструментальных вызовов в предоставленном контексте отсутствовал. Сам diff способ редактирования не доказывает.

**Непроверенные сценарии:** настоящий kill/restart процесса вместо пересоздания engine/соединения; исторические checkpoint-файлы R1–R4 вместо совместимой формы; отмена уже ожидающего child при сохранении работающего caller; production authentication/policy adapter за пределами тестового binding. Вердикт относится к R5, не к R6–R7.
