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

## 14. Расширенная повторная проверка R5 от 2026-11-03

**CHANGES REQUIRED. REV-7 и REV-8 закрыты; выявлен контрактный пробел REV-9 (P2).** Проверены исправления рабочего дерева поверх `f330d087`. Production-код при ревью не менялся. Предыдущий PASS относился к исправлениям REV-7/8, не к перечисленным в §13 непроверенным сценариям.

- **REV-7 — CLOSED.** Новая регрессия отменяет execution через второе SQLite-соединение при живом owner, останавливает его task и отвергает поздний input. Проверка stale claim подтверждает отзыв fence. Независимая проба также отменила уже выполняющийся `InputReceived` continuation на SQLite и memory store: результат `Failed`, task остановлен, durable статус `CANCELLED`, повтор receipt после отмены получает `InputConflict`.
- **REV-8 — CLOSED.** Повреждённый accepted-input checkpoint без continuation теперь получает `RestoreFailure` до вызова `start`. Штатные restart после receipt и replay terminal проходят.
- **Настоящий kill/restart — PASS.** Два отдельных дочерних Python-процесса принудительно завершены родителем через `Popen.kill()` сразу после durable checkpoint: отдельно после WAIT_INPUT и отдельно после receipt до continuation. Marker выдавался после успешной записи, процесс блокировался до kill, без graceful cleanup. После expiry lease в 1 секунду новый engine на новом соединении восстановил execution; ответ `count=7`, точный повтор `resume_input` вернул тот же delivery. Для окна WAIT_INPUT дополнительно проверен промежуточный `resume → Waiting`.
- **Исторические checkpoints — PASS.** Код `backend/app` и `backend/tests` из настоящих коммитов `cd6746a7` и `9654051f` извлечён во временные каталоги и запущен отдельными Python-процессами. Для каждой версии создана своя SQLite БД с terminal checkpoint и отдельно с незавершённым CALL checkpoint. Текущий runtime восстановил все четыре случая и вернул тот же JSON результата. При восстановлении использованы исходные fixture node ID, POJO и контракты: их переименование не является совместимой заменой catalog. Это проверка двух версий durable R4, не обещание совместимости при изменённых domain contracts; отдельного durable формата R1–R3 план не вводит.
- **Production auth/policy wiring — отсутствует, граница R7.** Поиск по `backend/app` не обнаружил реализации `InteractionPort`, создания `InvocationOptions` или HTTP callers `accept_input`/`resume_input` за пределами generic runtime/contracts. Поэтому реальный production adapter проверить запуском backend невозможно; R5 проверен на test adapter, как требует его приёмка. Test HTTP использует ASGI transport без сетевого сервера. Это не подтверждение production authorization и не новая находка против R5.

### REV-9 · P2 · R5 · Нет отдельной отмены child в WAITING_INPUT; её checkpoint отвергается

**Контракт §5:** node-level cancellation доставляется caller как `CallCancelled` в join и отличается от cancellation всего execution. Для уже ожидающего input child этот путь не предоставлен: публичный `DAGEngine` имеет только `cancel_execution`; `InvocationCoordinator.finish` принимает новый terminal outcome только из RUNNING, не из WAITING_INPUT. [dagEngine.py:178](../../backend/app/application/engine/runtime/dagEngine.py#L178) · [invocationCoordinator.py:151–154](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py#L151)

**Минимальный контрактный контрпример.** Через публичный engine запустить `AskAndFormat` до `Waiting`: Ask в WAITING_INPUT, Format SUCCEEDED, caller WAITING_CALLS. В копии полученного graph представить отмену только Ask (`status=CANCELLED`), сохранив SavedWait, живой caller и `graph.cancellation=None`; вызвать `CheckpointCodec.decode`. **Ожидалось:** представимое durable состояние отдельной отмены child, которое позволяет закрыть join с `CallCancelled` и отвергать поздний ответ. **Фактически:** `RestoreFailure`, cause `input wait differs from invocation state`. Условие на строке 116 исключает отменённый wait из pending только при отмене всего execution. [inputWaitCoordinator.py:116–120](../../backend/app/application/engine/runtime/invocations/inputWaitCoordinator.py#L116)

Контрпример намеренно синтезирует terminal child в копии checkpoint: штатного публичного API такого перехода сейчас нет. Он не доказывает, что обычный `run` самостоятельно сохраняет повреждённый checkpoint. Отдельная проба **после принятия input** заставила `Ask.resume` выбросить `CancelledError`: caller получил `CallCancelled`, соседний результат — `CallSuccess`, execution завершился `COMPLETED`. Значит существующий RUNNING → CANCELLED путь работает, пробел относится именно к ожидающему child.

**Критерий закрытия:** предоставить согласованный writer-путь отмены WAITING_INPUT invocation с сохранением caller/siblings, отключением этого wait и durable checkpoint; restart закрывает join с `CallCancelled`, поздний ответ отклоняется без изменения checkpoint. Сохранить работающую отмену execution и дочернюю отмену из RUNNING. Нужна регрессия через предоставленный API, а не только ручная подмена статуса.

Полный прогон §9: **370 тестов OK за 54,863 с**, включая положительные и точные отрицательные проверки Pyright, restart/CAS/fencing и REV-6. Scoped `git diff --check` прошёл. Тестовые процессы и временные БД использовались вне sandbox из-за Windows asyncio socketpair; backend не запускался. Инструментальный журнал реализации другого агента по-прежнему не предоставлен: соблюдение `apply_patch` в его работе не установлено. Оставшаяся граница: production auth/policy — R7; отдельная отмена ожидающего child — открытая REV-9. Весь crash matrix R6/publication не входит в R5.

## 15. Ревью исправления REV-9 на `edc082b7` от 2026-11-03

**CHANGES REQUIRED. Исходный сценарий REV-9 закрыт; открыта REV-10 (P2): отмена ожидающего child при активном owner.** Проверены только изменения R5; посторонние изменения коммита исключены. Production-код при ревью не менялся.

**REV-9 — CLOSED для исходного quiescent-сценария.** Публичный `cancel_waiting_child` отменяет child, сохраняет caller/siblings и checkpoint; новый engine с новым SQLite-соединением восстанавливает join и возвращает `cancelled/count=4`. Повтор отмены идемпотентен, поздний input отклоняется без изменения checkpoint. Проверки чужой сессии, stale revision и запрета отмены уже принятого wait проходят. Отмена из RUNNING и REV-7/8 продолжают проходить. Независимая проба с двумя WAITING_INPUT children подтвердила оба варианта: отменить первый, после restart получить Waiting только для второго и ответить ему; отменить оба и завершить caller с двумя CallCancelled. Повтор отмены после terminal response не меняет checkpoint.

### REV-10 · P2 · R5 · cancel_waiting_child требует свободного execution lease

**Файл:** [dagEngine.py:182](../../backend/app/application/engine/runtime/dagEngine.py#L182).

**Минимальное воспроизведение.** На fixture `AskAndFormat` с workers=1 задержать `FormatCaller.start` на `asyncio.Event`. Через публичный `run` дождаться входа Format в start; второе SQLite-соединение читает `pipeline=WAITING_CALLS`, `count=WAITING_INPUT`, `format=RUNNING`. Через новый engine вызвать `cancel_waiting_child(execution_id, "pick", expected_revision=3)` с правильной сессией.

**Ожидалось:** отмена ожидающего child принимается/передаётся владельцу execution, сохраняя работающего sibling; caller после join получает `CallCancelled`. **Фактически:** попытка `store.claim` получает `OwnershipConflict`, checkpoint не меняется, намерение отмены не сохраняется. После освобождения Format первый run возвращает `Waiting`; только после release execution lease та же отмена проходит, а resume возвращает `cancelled/count=4`. Следовательно новый API работает лишь после quiescence всего execution, хотя целевой child уже находится в WAITING_INPUT. Длительная соседняя ветка блокирует его отмену аналогично прежней REV-7 для execution.

**Критерий закрытия:** доставлять запрос отдельной отмены WAITING_INPUT child при активном owner без отмены sibling и без обхода fencing/CAS. Добавить двухсоединительную регрессию с заблокированным активным sibling; owner наблюдает отмену child, sibling завершается штатно, join содержит CallCancelled, поздний input отклоняется. Сохранить quiescent/restart/idempotent сценарии REV-9.

Полный набор по §9: **372 теста OK за 65,040 с**, включая положительные и точные отрицательные проверки Pyright. Scoped `git diff HEAD^ HEAD --check` прошёл. Проверки выполнены вне sandbox из-за Windows asyncio socketpair, backend не запускался. В этом раунде проверены новые engine/соединения после отмены; настоящий kill процесса и исторические checkpoints из §14 повторно не запускались. Production auth/policy остаётся интеграцией R7. Журнал инструментальных вызовов автора исправления отсутствует; способ внесения правок по diff не устанавливался.

### Ревью типизации checkpoint_status (`f98afe50`)

**PASS.** Pyright принимает оба разрешённых enum и отклоняет строки, чужие enum и присваивание `COMPLETED` полю статуса invocation. Приоритеты `checkpoint_status()` сохранены. Корневая invocation остаётся `SUCCEEDED`, а checkpoint получает `COMPLETED` при сохранении ответа. MemoryExecutionStore сохраняет переданный объект без runtime-валидации. После повторного открытия SQLite все восемь строковых статусов, записанных прежним store, восстановились как точные элементы enum (проверено через `is`). Неизвестное значение вызвало `ValidationError`. Полный прогон §9, включая положительные и точные отрицательные проверки Pyright, прошёл с первого раза — **374 теста OK за 60,768 с**.

## Независимое ревью R6 по §§6–8 от 2026-11-04

**CHANGES REQUIRED.** Проверен диапазон от родителя R6 `bd4c78cf` до рабочего дерева на `362c54fe`. Реализация вошла в `a2acb7df`, последняя правка PublicationOperationId — в `f83c34a7`. Между ним и конечным HEAD изменился только посторонний план. Проверены модели, контракты, service, worker, оба SQLite-адаптера, SQL и тесты.

| Приоритет и место | Воспроизведение и фактический результат | Критерий закрытия |
|---|---|---|
| P1 · [operationStore.py:59–61](../../backend/app/db/repositories/sqlite/bakeOperations/operationStore.py#L59) | В PUBLISHING и RECOVERY_REQUIRED записать SQL NULL в publication_operation_id. read возвращает None. После takeover тестовый reconcile возвращает BakeResult, store сохраняет SUCCEEDED и снимает claim при publish=0. При пустой строке read выдаёт ValidationError, статус и claim сохраняются. | Обе повреждённые формы отклоняются до reconcile с сохранением claim, включая ранее записанные строки. До публикации None допустим. |
| P2 · [worker.py:52](../../backend/app/application/worldData/bakeOperations/worker.py#L52) | Выйти из транзакции публикации настоящим commit, затем выбросить OperationalError потери ответа. Durable SUCCEEDED, claim снят, одна строка эффекта и один publish. Попытка uncertain сообщает BakeFenceLost без смены владельца. | Распознать подтверждённый terminal без ложной ошибки worker. При недоказанном исходе удерживать claim, исключить повторный publish. |
| P2 · [service.py:24–29](../../backend/app/application/worldData/bakeOperations/service.py#L24) | При разрешающем authorize вызовы submit(None, waiter) и submit(request, None) возвращают cached BakeResult, если ready его нашёл. При ready → None оба дают поздний AttributeError. Операций и claims нет, publish=0. | Обе формы отклоняются до readiness и admission независимо от наличия готового результата. |
| P2 · [DB-модель:14–24](../../backend/app/db/models/bakeOperation.py#L14) | После publishing(token, PublicationOperationId("pub-1")) прочитать строку через from_row(BakeOperation, row). Типы publication_operation_id, kind и status — str. Специализированный store.read восстанавливает заявленные типы. Состояние PUBLISHING, claim удерживается, publish=0. | Поддерживаемая гидратация возвращает объявленные типы либо модель явно описывает сырую строку БД и её преобразование. |
| P2 · [worker.py:60](../../backend/app/application/worldData/bakeOperations/worker.py#L60), [operationStore.py:24,109](../../backend/app/db/repositories/sqlite/bakeOperations/operationStore.py#L24) | Строгий Pyright по девяти новым модулям даёт два reportUnnecessaryIsInstance на runtime-границах и один reportDeprecated для Iterator у contextmanager. В basic ошибок нет. | Ноль строгих диагностик при сохранении независимых проверок worker и store. |

**Статическая проверка.** Pyright принимает PublicationOperationId для результата async stage, аргумента publishing и поля BakeRecord. Для str, ExecutionId и None у stage получены три reportIncompatibleMethodOverride, у publishing — три reportArgumentType. У BakeRecord str и ExecutionId дают ещё два reportArgumentType, None принят. Итого восемь ожидаемых диагностик.

**Поведение во время исполнения.** Через публичный service типизированный ID дал SUCCEEDED, снятый claim и publish=1. Каждое из шести других значений (обычная строка "pub-1", пустая строка, пробелы, None, bytes, чужой StrEnum) дало перехваченный worker TypeError, durable FAILED, снятый claim и publish=0. Прямой publishing на каждом из шести дал TypeError, RUNNING и удержанный claim при publish=0. Конструктор ID принимает валидную строку и строковый enum, отклоняет пустую строку, пробелы, None и bytes с ValidationError. После штатного SQLite round-trip проверка type(record.publication_operation_id) is PublicationOperationId истинна.

Пропуск обязательного аргумента у submit, publishing или конструктора ID даёт TypeError до исполнения. При обычном создании BakeRequest и Waiter пропуск обязательного поля, None и пустые идентификаторы дают ValidationError до admission, без операции, claim и publish. Строковый kind, scope в виде списка и пустая строка внутри scope отклонены. При чтении повреждённого request_blob='{}' получен ValidationError, неизвестного delivery_status — ValueError.

**Приёмка SQLite.** Два соединения дали один Started и один Joined с общим ref, один stage и одну публикацию для эквивалентной пары. Несовместимые kind, ordered scope, revision и parameters_fingerprint дали BakeConflict. Для разных миров оба stage одновременно дошли до барьера, после detach всех waiters оба завершились публикацией. Второй readiness read позволил завершиться при stage=0 и publish=0. Takeover сохранил operation и увеличил fence. Старые heartbeat, publication и prepared_terminal получили BakeFenceLost, claim сохранился. При потере ответа с rollback остался RECOVERY_REQUIRED с claim и нулём строк эффекта. Конфликт блокировался до authoritative evidence. После закрытия обоих соединений и создания нового service/store два poll вернули прежний результат, эффект в БД один, после acknowledge повторный poll вернул None.

**Первые прогоны.** R6 — 8/8 OK за 41,046 с. Полный DAG по команде §9 — 382/382 OK за 197,117 с, 21 модуль. Оба набора прошли без повторов. Вспомогательная проба границ сначала остановилась до проверок из-за отказа sandbox открыть временную SQLite БД, повтор вне sandbox прошёл. У отдельной runtime-пробы были предупреждения Windows об очистке временных файлов, сценарии завершились с кодом 0.

**Вопросы автору.** Как трактовать scope=() по видам LIGHT/FULL/DETAILED и где проверять обязательные цели? Конструктор принимает пустой tuple для всех трёх, §§6–8 не задают минимальную длину. Допустимы ли явное создание ID из чужого StrEnum и приведение version=True к 1? Требуется ли upgrade существующей БД с уже применённой миграцией 1? Проверен restart на БД с таблицами R6. Исторический upgrade и настоящий kill процесса остаются непроверенными. Production bindings входят в R7.

## Итог повторного ревью R6 от 2026-11-04

**PASS по §§6–8.** База предыдущего ревью — `362c54fe`. Проверено рабочее дерево на HEAD `8de6092f6db35f75240fcc0e7d36fcaae26b738a`, включая незакоммиченные `worker.py`, `operationStore.py` и `test_bake_operations.py`. Вердикт относится к этому дереву.

| Прежняя находка | Вердикт и проверенный результат |
|---|---|
| P1 · Повреждённый checkpoint | **CLOSED.** На двух соединениях все четыре сочетания PUBLISHING / RECOVERY_REQUIRED и SQL NULL / пустой строки остановили worker до reconcile. Статус и claim сохранились. В PENDING и RUNNING чтение NULL вернуло None. |
| P2 · Потеря ответа после publish | **CLOSED.** Настоящий commit с последующим OperationalError дал SUCCEEDED, один эффект, один publish и снятый claim. Worker завершился штатно. После rollback claim удерживался до подтверждения исхода. |
| P2 · Некорректный submit | **CLOSED.** При пустом и заполненном кеше отсутствие request или waiter давало TypeError до authorize, ready и admit. Все три таблицы bake остались пустыми. |
| P2 · Общий DB mapper | **CLOSED.** Оба пути чтения и запись через to_row проверены для заполненного ID и допустимого NULL. SQL round-trip прошёл также для BakeWaiter, World и DagExecution. |
| P2 · Строгая типизация | **CLOSED.** Все девять модулей R6 входят в include и strict штатного конфига. Статические и runtime-пробы приведены ниже. |
| P2 из повторного ревью · Потеря ответа после reconcile | **CLOSED.** После commit с BakeResult или RolledBack worker подтвердил соответствующий SUCCEEDED или FAILED без повторной публикации. При неизвестном исходе сохранился исходный claim. Если мир уже заняла следующая операция, её claim сохранился. Старый fence и чужой ID при подтверждении терминала отклонены. |

### Pyright strict — PASS

Штатный конфиг прошёл без диагностик. Во временной strict-пробе приняты async stage с результатом PublicationOperationId, publishing(token, publication_id), send_text(publication_id.value) при параметре str и require("pub-1") при параметре object. Получены ровно шесть ожидаемых ошибок.

| Выражение во временном probe.py | Диагностика |
|---|---|
| Строки 11 и 14 · stage возвращает str или None | Две reportIncompatibleMethodOverride |
| Строки 23 и 25 · publishing получает "pub-1" или ExecutionId | Две reportArgumentType |
| Строка 24 · send_text получает сам PublicationOperationId | reportArgumentType |
| Строка 26 · присваивание publication_id.value | reportAttributeAccessIssue, поле доступно только для чтения |

### Нетипизированный Python — PASS

Валидный PublicationOperationId("pub-1") через async stage дал SUCCEEDED, снятый claim и publish=1. Прямой publishing перевёл операцию в PUBLISHING. По отдельности проверены "pub-1", пустая строка, пробелы, None, bytes, чужой StrEnum и посторонний объект с полем value. Все семь значений через stage дали FAILED с ошибкой «expected a PublicationOperationId», снятым claim и publish=0. Прямой publishing во всех семи случаях выбросил TypeError, сохранив RUNNING и claim.

require вернул исходный экземпляр для готового ID и выбросил TypeError для строки. Конструктор отклонил ForeignEnum.X с TypeError. Для `id = PublicationOperationId("pub-1")` выражение `type(id.value) is str` дало True. Выражения `isinstance(id, str)` и `id == "pub-1"` дали False. Присваивание value вызвало FrozenInstanceError. Аннотация str у обычной функции send_text сама по себе вызов в Python не блокирует.

При чтении BakeRequest из JSON пропущенная version и целое 1 дали int со значением 1. Для true, 1.0, "1" и null получен ValidationError с «version must be an integer», для 0 и 2 — «Input should be 1».

### SQLite — PASS

Одну строку записал текущий worker, другую — исторический SQLiteBakeOperations.publishing из `362c54fe` с тогдашним PublicationOperationId(str). После закрытия и повторного открытия БД у обеих строк typeof(publication_operation_id) = 'text'. И SQLiteBakeOperations.read, и from_row(BakeOperation, row) вернули точный тип PublicationOperationId с value == "pub-1". Для обеих строк колонки и параметры из to_row переданы напрямую в INSERT под новым PK. Копии прошли те же проверки.

**Прогоны.** До правки reconcile первые попытки внутри sandbox прерваны на Windows asyncio socketpair. Вне sandbox R6 прошёл 14/14, полный §9 дал 387/388 с OwnershipConflict в test_slow_effect_retains_one_second_lease. Изолированный повтор прошёл 1/1, полный повтор — 388/388. После правки reconcile профильный набор прошёл 15/15 за 55,557 с, полный — 389/389 за 118,805 с. В отдельном повторном ревью полный набор прошёл с первого запуска, 389/389 за 104,777 с.

Проверка конкретной цели scope остаётся в builder R7. Для тестовых БД принят reset, upgrade не требуется. Принудительный kill процесса и физический обрыв соединения не воспроизводились.

## Ревью R6 на 42e7f6e0 от 2026-11-04

**CHANGES REQUIRED.** Проверен HEAD `42e7f6e029656bbd5a274435ff23b59628a93542`. Три открытые находки воспроизведены через нетипизированный Python и SQLite.

| Находка | Воспроизведение и наблюдаемый эффект | Критерий закрытия |
|---|---|---|
| **P1 · OPEN** · [operationStore.py, строки 157–158](../../backend/app/db/repositories/sqlite/bakeOperations/operationStore.py#L157) | После takeover callback восстановления вернул `SimpleNamespace(reason="unverified")`. Второе соединение увидело FAILED с причиной PUBLICATION_ROLLED_BACK и снятый world claim. Следующий admit того же мира вернул Started. | Только явный RolledBack подтверждает откат. При неизвестном типе результата операция сохраняет claim. |
| **P2 · OPEN** · [bakeOperation.py, строка 24](../../backend/app/db/models/bakeOperation.py#L24) | В SUCCEEDED-строке заменили result на `BakeError(kind=BakeErrorKind.LEGACY, message="oops")`. INSERT значений из to_row сохранил JSON ошибки в result_blob. После commit оба пути чтения, SQLiteBakeOperations.read и from_row, дали ValidationError. | Сериализатор принимает ненулевой результат только типа BakeResult и отклоняет чужую модель до записи. |
| **P2 · OPEN** · [bakeOperation.py, строка 30](../../backend/app/db/models/bakeOperation.py#L30) | Для `publication_operation_id = SimpleNamespace(value="foreign")` mapper извлёк строку и INSERT прошёл. Оба пути чтения вернули `PublicationOperationId("foreign")`. Прямой publishing отклоняет такой объект. | Общий mapper проверяет тип ненулевого ID перед извлечением value. Допустимый SQL NULL сохраняется. |

Контрольная строка с корректными BakeResult и PublicationOperationId прошла INSERT и оба пути чтения. Штатный Pyright завершился без диагностик. Первый полный DAG-прогон по §9 дал **389/390 за 144,376 с** с одним `OwnershipConflict('lease')` при checkpoint. Контрольный прогон 16 тестов R6 и двух lease-тестов дал **18/18 за 64,741 с**. Связь сбоя аренды с находками R6 не установлена. В пробе takeover Windows выдала предупреждение при очистке временной БД после проверки результата.

## Повторное ревью R6 на 5ec113b1 от 2026-11-04

**CHANGES REQUIRED.** Проверен HEAD `5ec113b1903a8e8ffce21cc613960d1846122629`. Все три находки от `42e7f6e0` закрыты. Открыта одна новая P2.

| Прежняя находка | Вердикт | Результат повтора |
|---|---|---|
| P1 · Ложное подтверждение rollback | **CLOSED** | После takeover объект `SimpleNamespace(reason="unverified")` вызвал TypeError. При прямом вызове store сохранились PUBLISHING и claim, через worker — RECOVERY_REQUIRED и claim. |
| P2 · Чужая модель в result_blob | **CLOSED** | При BakeError в поле result вызов to_row выбросил TypeError до INSERT. Строка не появилась. |
| P2 · Посторонний объект вместо ID | **CLOSED** | При `SimpleNamespace(value="foreign")` в поле publication_operation_id вызов to_row выбросил TypeError до INSERT. Корректный ID и допустимый SQL NULL прошли запись и чтение. |

**P2 · OPEN · Подклассы BakeResult и BakeError.** Если callback публикации возвращает подкласс BakeResult с дополнительным полем `detail`, кодировщик сохраняет это поле в JSON. После commit в БД видны SUCCEEDED и снятый claim, но и `SQLiteBakeOperations.read`, и `from_row(BakeOperation, row)` выбрасывают `ValidationError(extra_forbidden)` для `detail`. Та же проба с подклассом BakeError через `prepared_terminal` дала FAILED и снятый claim, а прочитать причину ошибки обоими путями не удалось. [BakeResult.encode](../../backend/app/dataModel/world/bakeOperation/record.py#L87) · [BakeError.encode](../../backend/app/dataModel/world/bakeOperation/record.py#L69)

**Критерий закрытия.** Для обоих подклассов после фиксации терминала второе SQLite-соединение должно прочитать результат или причину ошибки обоими штатными путями.

**Прогоны.** Профильный R6 — **17/17 за 33,170 с**, полный DAG по §9 — **391/391 за 102,094 с**. Оба прошли с первого запуска. Штатный Pyright и `git diff --check` прошли без замечаний. Контрпример с подклассами воспроизведён отдельной пробой на двух SQLite-соединениях.

## Итог ревью R6 на 7b6104d7 от 2026-11-05

**PASS. P2 по подклассам BakeResult и BakeError — CLOSED.** Проверены изменения от `5ec113b1` до `7b6104d71763d314ecf4f3b1e5e11e330a91e98b`. Новых находок в исправлении нет.

Повторена SQLite-проба с дополнительным полем `detail` у обоих подклассов. После commit второе соединение прочитало обе операции через `SQLiteBakeOperations.read` и `from_row(BakeOperation, row)`. Для SUCCEEDED восстановился точный тип BakeResult, для FAILED — BakeError с исходными kind и message. Оба claim сняты. Сохранённый JSON содержал только поля базовых моделей. Отдельный INSERT значений из `to_row` для обоих подклассов дал тот же результат. [Кодировщики](../../backend/app/dataModel/world/bakeOperation/record.py#L69) · [Регрессионный тест](../../backend/tests/dag_typing/invocations/test_bake_operations.py#L284)

Полный DAG-набор по §9, включая профильные тесты R6, прошёл с первого запуска — **392/392 за 143,966 с**. Штатный Pyright и `git diff --check` прошли без замечаний.
