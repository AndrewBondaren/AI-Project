# Artifacts: архитектура staging, 2026-11-21

Статус: **PROPOSED, ARCH-STAGE OPEN**. Детализация первого архитектурного пункта [owning-плана](artifacts-public-staging-dag.md), не разрешение реализации. При конфликте с принятым междоменным контрактом действует принятый контракт до согласования указанной здесь дельты. BLOB — существующий storage kind; Blob/God Object и BLOB-first обход архитектуры запрещены.

## Граница решения

Публичные операции остаются `prepare_stage → stage`, прямой caller — согласованная DAG-нода. Prepare не имеет IO, stage возвращает ArtifactRef. Ни одна операция не запускает completion, чтение Source, публикацию, recover, cancel или GC. Engine владеет маршрутом; producer владеет содержимым; Artifacts — descriptor admission и физическим размещением; Publication — candidate/evidence, UOW, READY и публикацией. Source владеет полным semantic closure.

Согласованные гарантии сохраняются: передача исходного immutable объекта в одном процессе; reserve/write/seal с writer fencing; hold подтверждается в момент seal commit, не на момент доставки ответа; stage не означает READY. Durable транспорт большого payload, registry объектов и изменения Engine не входят в решение.

## Проверенный existing inventory и судьба фасада

Пути ниже относительно `backend/app/`. Поиск callers выполнен по `backend/app` и `backend/tests`, а не только по папке Artifacts.

`application/artifacts/staging/artifactStaging.py::ArtifactStagingService` сейчас содержит восемь разных операций. **Сохранять его в таком виде как новый public pipeline нельзя.** Но удалять методы без cutover зависимых callers также нельзя.

| Existing метод | Ответственность и целевая судьба | Что обязано сохраниться |
|---|---|---|
| `open_operation(operation_id, world_uid, kind, preparation_fingerprint)` | Выдача lease у existing IArtifactLeases; убрать из нового staging API. Внешний lifecycle entry требует owning согласования | Binding/fence выдаёт lifecycle, stage не создаёт lease автоматически |
| `reserve(lease, descriptor)` | Внутренняя staging admission/storage операция; перенести в ArtifactStageWriter | Проверка descriptor, lease и атомарное создание reservation + operation hold в catalog |
| `seal(reservation)` | Та же связная ответственность write/seal; перенести в ArtifactStageWriter как внутреннюю стадию | Writer claim, физическая verification, повторная fence проверка, catalog seal, единственный seal event |
| `finish_preparation(lease, refs)` | Completion lifecycle; не часть stage. Existing standalone остаётся до согласованного completion cutover | Exact held/sealed set, закрытие admission; не обещает acquisition inherited refs |
| `verify(ref, holder)` | Existing guarded integrity/membership check; не публичный verified read и не authority | Catalog/body guard удерживается до окончания verification. Не выдавать этот результат за долговечный read permit |
| `recover(operation_id)` | Existing Publication OperationLedger, убрать зависимость ledger из нового stage | Terminal codec/result binding H2; не вызывать recover автоматически при stage error |
| `cancel(operation_id, fence)` | Lifecycle cancellation; отдельная owning операция, не stage fallback | Close admission → drain writers → release, проверка terminal/fence, LEASE_RELEASED только для подтверждённого cancel |
| `collect(operation_id, candidates)` | Existing ArtifactGarbageCollector; убрать delegate из нового stage | Guard + проверка holders + physical delete + catalog fact; GC не выбирает lifecycle |

Disposition: **split по ответственности, без класса на каждый delegate**. Новый stage зависит только от write/seal реализации. Старый фасад пока existing, не часть целевого публичного контракта. Его полное удаление — отдельный consumer cutover; до него нельзя объявлять весь домен очищенным от обходных путей.

Найден реальный foreign caller: `application/worldData/pack/encoding/preparedManifest.py::finish_pack_preparation` напрямую вызывает TypedArtifactStager.stage, затем IArtifactStaging.finish_preparation и формирует PreparedPackCandidate. Этот existing путь **не соответствует целевому DAG-маршруту**. Его удаление/замена принадлежит Pack + DAG + Publication, а не скрытой правке Artifacts. Тестовые callers есть в `tests/snapshotCore/storage/artifacts/test_staging.py`, `tests/spatial_pack/` и `tests/typing/snapshotCore/`. Их нельзя считать доказательством новой регистрации.

H2 design предусматривает `ArtifactStagingService[R]/IArtifactStaging[R]` и exact `record_model/result_binding`. Это сохраняемое целевое требование, **не факт runtime**: проверенные ArtifactStagingService и SqliteArtifactLeases негeneric, используют bare OperationRecord; properties и single-R factory checks здесь ещё не реализованы. Новый stage не переносит R в своём публичном контракте, но existing catalog._lease → operations._load транзитивно читает terminal codec/evidence. Поэтому отсутствие R в constructor writer не означает независимости всей реализации от H2. H2 implementation gap остаётся у owning lifecycle/persistence; legacy compatibility не вводится, фасад до cutover не удаляется.

## Классы нового среза: ответственность и критерии отказа

Все TARGET ниже — проектирование; этих новых классов пока нет в runtime. Existing компоненты переиспользуются без зеркальных портов.

| Класс / путь под application/artifacts | Единственная ответственность; зависимости и эффекты | Критерий приёмки / признак отказа |
|---|---|---|
| TARGET `staging/artifactPrepareStageOpenPipeline.py::ArtifactPrepareStageOpenPipeline[C]` | Линейный порядок prepare; admission → descriptor → prepared result, без IO | Замена codec не меняет pipeline; hash/row-count/schema algorithms внутри pipeline — отказ |
| TARGET `staging/artifactStageOpenPipeline.py::ArtifactStageOpenPipeline[C]` | Линейный порядок одной stage операции; admission → descriptor match → writer; boundary logging | Нет выбора следующей DAG операции. Recover/cancel/finish/GC или SQL здесь — отказ |
| TARGET `staging/artifactAdmission.py::ArtifactInputAdmission[C]` | Structural/type/deep-immutability admission входа и binding; existing validation diagnostics, без IO | Возвращает те же instances; сериализация/копирование, semantic decoding Pack/Source — отказ |
| TARGET `staging/artifactDescriptor.py::ArtifactDescriptorBuilder[C]` | Canonical descriptor и проверка его соответствия content; fixed ArtifactFormatContract[C], FormatVersion, registry encode, canonical digest | Весь codec/digest/row_count алгоритм здесь; lease/IO/domain strategy — отказ |
| TARGET `staging/artifactStageWriter.py::ArtifactStageWriter[C]` | Реализация физического reserve/write/verify/seal протокола; fixed backend, registry, catalog, leases, lifecycle log | Не знает candidate/terminal R/Source; не меняется при смене DAG-порядка. Ledger/holders/GC dependencies — отказ |
| Existing `registry/artifactRegistry.py::ArtifactFormatRegistryBinding` | Связь format key/contract с codec и backend; existing encode/decode/verify/delete | Не выбирает DAG route и не создаёт lease. Новая регистрация обязана доказать identity validation |
| Existing ArtifactFormatContract[C], ArtifactBackend[C] | Контракт concrete format и storage write/verify/delete | Producer semantics не попадает в generic Artifacts; mutable C или unbounded SQL binding без доказательств — отказ регистрации |
| Existing IArtifactCatalog / SqliteArtifactCatalog | Identity/reservation/seal и общий storage guard | Reserve атомарно проверяет fence и приобретает hold; раздельные check/acquire transactions — отказ |
| Existing IArtifactLeases / SqliteArtifactLeases | Persistent fenced admission/writer lifecycle | Не передаёт task-bound connection workers, cancel ждёт writers; скрытый commit в borrowed scope — отказ |
| Existing SqliteArtifactScope | Присоединение к допустимому scope либо собственная transaction по существующему контракту | Standalone допускается; заимствованный scope не коммитится и не передаётся другой task |
| Existing ContentAddressedBlobBackend | Physical bytes storage, verification, drain IO | Полные bytes проверяются против descriptor; worker не продолжает IO после освобождения claim |
| Existing ArtifactLifecycleLog | Доставка typed lifecycle events по existing политике | Sink не превращает committed stage в business refusal; дублирующий rethrow log — отказ |

`TypedArtifactStager` не остаётся вторым public entry: его descriptor алгоритм переходит в ArtifactDescriptorBuilder, write protocol — в ArtifactStageWriter. Переименование старого метода целиком не удовлетворяет архитектуре. Ни один новый компонент не объединяет lifecycle/read/GC с записью.

## Exact методы TARGET и вложенный trace

### Writer constructor и узкий lease port — PROPOSED

Сверка координатора (2): направление совместимо с H2, но dependency на полный IArtifactLeases[R] не доказывала независимость writer от terminal R. Проверены existing `application/artifacts/storage/artifactLeases.py` и `application/artifacts/contracts/`: подходящего отдельного порта admission/claims там нет. Поэтому предлагается минимальный structural protocol, а не новый runtime adapter или lease subsystem.

TARGET `application/artifacts/storage/artifactWriteAdmission.py::IArtifactWriteAdmission(Protocol)`:

```python
async def assert_writable(self, lease: OperationLeaseRef) -> None: ...
def require_standalone(self) -> None: ...
def writer(self, reservation: StagingReservation) -> AbstractAsyncContextManager[None]: ...
```

Exact imports: `typing.Protocol`, `contextlib.AbstractAsyncContextManager`, `app.dataModel.artifacts.lifecycle.lease.OperationLeaseRef` и `StagingReservation`. Protocol не generic по R, без состояния, POJO, open/finish/recover/cancel, record_model и result_binding. Existing SqliteArtifactLeases уже имеет assert_writable/writer; require_standalone — необходимая TARGET дельта existing adapter после замечания о partial ambient borrowing. Новый forwarding wrapper не нужен. Это внутренний storage port, не новый public DAG API. Runtime код пока не изменяется.

TARGET exact constructor:

```python
ArtifactStageWriter[C].__init__(
    self, *,
    contract: ArtifactFormatContract[C],
    registry: ArtifactFormatRegistryBinding,
    catalog: IArtifactCatalog,
    admission: IArtifactWriteAdmission,
    log: ArtifactLifecycleLog,
) -> None
```

Existing imports соответственно: `app.application.artifacts.contracts.formatBackend.ArtifactFormatContract`, `app.application.artifacts.registry.artifactRegistry.ArtifactFormatRegistryBinding`, `app.application.artifacts.storage.artifactCatalog.IArtifactCatalog`, `app.application.artifacts.logging.artifactLog.ArtifactLifecycleLog`; новый port импортируется из указанного TARGET модуля. Constructor выполняет `registry.resolve(contract)` и сохраняет полученный `ArtifactBackend[C]`; отдельный backend argument не нужен, поскольку создал бы второй источник binding. Версию и descriptor строит fixed descriptor builder; writer проверяет descriptor через registry и принятую input admission, не выбирает format/version самостоятельно. Ledger, terminal codec, R, holders и GC constructor не принимает.

В описании write/seal ниже `leases.assert_writable/writer` означает вызовы **admission.assert_writable/writer** через этот узкий port. Семантика остаётся existing: assert_writable — текущая fenced admission проверка, не долговечное разрешение; writer — acquire/release существующего fenced claim, cancellation требует drain. Ошибки и unknown outcome не преобразуются самим structural port; mapping storage sites остаётся отдельным OPEN. Новый протокол не ослабляет атомарные checks catalog.reserve/seal.

В целевой H2 composition передаётся тот же concrete lifecycle adapter с owning single-R configuration. Требуемые identity `record_model/result_binding` checks принадлежат owning factory/lifecycle consumers; writer их не повторяет. Сейчас это implementation gap, не существующая гарантия кода. Приёмочный typing case после H2 реализации должен показать передачу одного SqliteArtifactLeases[R] в lifecycle consumer и IArtifactWriteAdmission без Any/cast/нового экземпляра; runtime test проверяет целевые identity checks. До H2 нельзя объявлять их выполненными. Нового транзакционного движка, store или lease POJO нет.

Старый ArtifactStagingService/IArtifactStaging остаётся до [consumer cutover](pack-staging-completion-cutover.md); extraction writer не удаляет его lifecycle API. Уточнение предъявлено как owning proposal, окончательная междоменная приёмка не выдана.

Generic `C` ограничен `bytes | BaseModel`, concrete type фиксирует composition. Конструкторы выполняют binding validation один раз: fixed contract, supported version, backend registry identity. Ошибки composition — fail-fast, не пользовательский refusal и не ветка DAG.

Публичные сигнатуры и модели сохраняют V1.1 owning-плана:

- `ArtifactPrepareStageOpenPipeline[C].prepare_stage(self, request: ArtifactPrepareStageInput[C]) -> PreparedArtifact[C]` — sync, pure.
- `ArtifactStageOpenPipeline[C].stage(self, request: ArtifactStageInput[C]) -> ArtifactRef` — async, IO.
- Модели: `dataModel/artifacts/staging/preparedArtifact.py::{ArtifactPrepareStageInput, PreparedArtifact}` и `staging/stageInput.py::ArtifactStageInput`; поля соответственно `content`, `content/descriptor`, `lease/prepared`. Новых зеркал ArtifactRef/OperationLeaseRef нет.

Предлагаемые внутренние методы (не API DAG):

| Метод | Pre/post, calls, эффекты и ошибки |
|---|---|
| `ArtifactInputAdmission[C].prepare(self, request: ArtifactPrepareStageInput[C]) -> ArtifactPrepareStageInput[C]` | Проверяет schema/type/deep immutability/binding, возвращает исходный request; ArtifactInputRejected для ожидаемых field issues; без codec и IO |
| `ArtifactInputAdmission[C].stage(self, request: ArtifactStageInput[C]) -> ArtifactStageInput[C]` | Аналогично для lease/prepared/descriptor structure; без проверки live writable в памяти; тот же объект |
| `ArtifactDescriptorBuilder[C].build(self, content: C) -> ArtifactRef` | Accepted immutable C; registry.encode → canonical digest + nbytes + owning row_count → ArtifactRef. Codec fault → ArtifactCodecError с cause; не IO |
| `ArtifactDescriptorBuilder[C].prepare(self, content: C) -> PreparedArtifact[C]` | build → validated PreparedArtifact; `result.content is content`; создание результата является частью descriptor preparation, не pipeline algorithm |
| `ArtifactDescriptorBuilder[C].check(self, prepared: PreparedArtifact[C]) -> None` | build(prepared.content) и exact descriptor comparison; mismatch → ArtifactInputRejected с DESCRIPTOR_MISMATCH; codec fault не маскируется |
| `ArtifactStageWriter[C].write(self, lease: OperationLeaseRef, prepared: PreparedArtifact[C]) -> ArtifactRef` (async) | Только admitted request после check; registry.validate descriptor → leases.assert_writable → catalog.reserve → exact reservation validation → bound backend.write → fenced verify/seal. Нарушение storage binding → ArtifactStorageInvariantError; коллизия descriptor → ArtifactDescriptorConflictError |

Prepare pipeline вызывает admission.prepare → descriptor.prepare. Stage pipeline вызывает admission.stage → descriptor.check → writer.write и передаёт typed result/error. Ни циклов выбора format, ни hash calculation, ни lease business validation в pipeline нет. Writer — внутренняя реализация одного atomic-in-intent storage протокола, **не обещает общей SQL transaction для физической записи**.

Внутри writer порядок существующего seal сохраняется: `leases.writer(reservation)` → assert_writable → registry.verify(ref) → assert_writable → catalog.seal → equality check → release claim → seal event. Catalog seal повторно защищает изменяемые условия транзакционно; предварительная проверка не заменяет её. Backend write владеет своим claim/drain. Между backend write и seal cancel может победить: seal откажет, не создавая ложный success.

Error roster public stage: owning proposed ArtifactInputRejected/ArtifactLeaseRefused; ArtifactCodecError/ArtifactDescriptorConflictError/ArtifactStorageInvariantError как PublicationInfrastructureError; existing CorruptBlobError, OperationBusyError, UnknownCommitOutcome, CancelledError сохраняют категории. Mapping достижимых existing sites указан ниже. Это TARGET замена неоднозначных raises в owning местах, не runtime guarantee и не blanket catch ValueError в pipeline.

### Классификация ошибок достижимого stage path

В этой таблице `Lease(code)` — TARGET `ArtifactLeaseRefused(ArtifactLeaseFailure(lease=requested_lease, requirement=WRITABLE, code=code))`, модули `application/artifacts/lifecycle/leaseErrors.py` и `dataModel/artifacts/lifecycle/leaseFailure.py`. Поля/enum переиспользуются из owning-плана. `Input(code)` — существующий в design ArtifactInputRejected/ArtifactInputError с typed field path к request.prepared либо content. `Invariant` — TARGET ArtifactStorageInvariantError; `Infra` — existing PublicationInfrastructureError. Для infrastructure faults новый business POJO не вводится: они не являются ожидаемым отказом входа DAG.

| Site / проверенное условие | TARGET category / POJO | Точное место классификации |
|---|---|---|
| Public admission: shape, concrete C, deep immutability, format binding | Input с owning CONTENT_TYPE_MISMATCH/CONTENT_NOT_IMMUTABLE/FORMAT_BINDING_MISMATCH и existing field issues | ArtifactInputAdmission до любых effects; Pydantic ValidationError переводится здесь с cause |
| DescriptorBuilder.check: content descriptor отличается от предъявленного | Input(DESCRIPTOR_MISMATCH) | Сам check до reserve; точный field path prepared.descriptor |
| Registry.resolve/register: неизвестный contract, duplicate key, несовпадающий backend instance; constructor root/type/version | Composition error, не lease/input refusal | При composition до регистрации; existing ValueError/TypeError допустимы только здесь. Их неожиданное появление после successful composition — Invariant на конкретном registry binding check |
| registry.encode: callback выбросил исключение или вернул не bytes; row_count callback/invalid result | ArtifactCodecError | DescriptorBuilder вокруг именно codec/row_count invocation, с cause; CancelledError/BaseException не ловить. Неверный internal C после admission — Invariant, не повторный field refusal |
| catalog._lease: operations._load вернул None | Lease(OPERATION_MISSING) | В _lease до попытки собрать/сравнить lease |
| catalog._lease: world/kind/preparation_fingerprint отличается | Lease(BINDING_MISMATCH) | В _lease сравнение структурных полей, до fence/phase checks |
| catalog._lease: record.fence отличается | Lease(FENCE_MISMATCH) | В _lease после binding comparison |
| catalog._lease: latest admission отсутствует / phase не PREPARING / admission closed / latest fence отличается | Соответственно Lease(LEASE_ABSENT), Lease(PHASE_NOT_WRITABLE), Lease(ADMISSION_CLOSED), Lease(FENCE_MISMATCH) | В _lease раздельные predicate checks в указанном порядке после полной проверки persisted chains; corrupt chain имеет приоритет над business classification |
| catalog._find: существующая identity имеет другой полный descriptor | ArtifactDescriptorConflictError | В _find вместо ValueError; не трактовать как lease stale либо user descriptor mismatch |
| catalog.seal или leases.writer: reservation identity mismatch; catalog._by_id missing/mismatched identity | Invariant | В соответствующем adapter site: reservation создан самим catalog; не внешний capability для исправления пользователем |
| leases.writer: reservation not held после successful writable check; catalog.seal: нет live writer или reservation hold | Invariant | В writer/seal после повторной mutable lease проверки в той же transaction. При нормальном concurrent cancel первым должен сработать Lease refusal; валидный writable lease без обязательного hold/claim — повреждение инварианта, не «ожидаемый cancel» |
| leases.writer: уже есть active writer этой reservation | Existing OperationBusyError | В writer, без retry/преобразования в input refusal |
| leases._release: потерян acquired claim | Invariant | В _release, cleanup fault не превращается в success и не освобождает holds |
| catalog._descriptor/_storage/_writers/_lease malformed raw bool/chain; holder._chain malformed row/chain | Invariant либо уже существующий Infra | На owning row/chain validation site, не в DAG. _values/_wire/DTO ошибки persisted данных оборачиваются локально с cause; не Lease failure |
| operations._load/_event: malformed identity/event/record, terminal/phase/evidence mismatch; operationArtifacts.read malformed descriptor | Existing Infra (либо Invariant для Artifacts-owned rows) | На persisted hydration boundary; нельзя catch ValueError от всей stage и объявить stale lease |
| StoredTerminalCodec.decode: checksum/version/discriminator/root/body mismatch; evidence.check и historical publication readers | Existing Infra | Owning persistence decode/evidence boundary; неизвестный terminal root не missing/retry/refusal. Не вводить legacy reader |
| require_standalone / scope registry: ambient, foreign/expired/task-mismatched capability, wrong connection | Existing Infra | До первого эффекта и повторно existing registry/coordinator checks; не business refusal |
| ScopedSqliteAccess: SQL driver failure; invalid hydrated row; insert serialization failure | Existing Infra; сохранять уже typed faults | DB IO boundary: sqlite driver/row exceptions с cause. Не преобразовывать UnknownCommitOutcome либо cancellation. Нарушение write capability уже классифицирует registry |
| Backend._ref/type content не соответствует принятому binding; bytes повторного encoding отличаются от reservation | Invariant для binding/type; ArtifactCodecError для nondeterministic/invalid повторного encoding | На конкретных backend checks. После immutable admission и descriptor check это не новый пользовательский input mismatch |
| Backend._contained: escape/symlink/junction; _verify: size/hash отличается; missing final body | Existing Infra (existing CorruptBlobError, если конкретный backend уже его возвращает, сохраняется) | Physical storage boundary. BLOB _verify сейчас возвращает Infra, не заявлять CorruptBlobError реализованным там |
| Backend temp/place/fsync/open/unlink: OSError, включая cleanup | Existing Infra с cause | Owning physical IO boundary; existing target path при placement не ошибка сам по себе, затем verification обязательна |
| Writer проверяет возвращённые reservation/ref против запрошенных | Invariant | Writer непосредственно после catalog результата |
| Coordinator commit/rollback unconfirmed; quarantined connection | Existing UnknownCommitOutcome | Проброс без переклассификации/retry/cleanup; confirmed rollback нужен для выдачи ожидаемого отказа |
| Cancellation в backend worker / claim acquire/release | Existing CancelledError после existing drain; неизвестный cleanup outcome остаётся UnknownCommitOutcome | Backend _io и leases cleanup владеют ожиданием, pipeline не подменяет это освобождением holds |

Для checks, которые сейчас непосредственно делают `raise ValueError`, TARGET меняет raise на typed carrier в том же owning месте, с теми же проверяемыми данными; parsing текста exception запрещён. Если причина поймана как exception, использовать `raise ... from error`; при прямом predicate raise первичного exception нет, искусственный ValueError-cause не создаётся. При secondary cleanup failure сохранять исходное исключение в цепочке context/cause; UnknownCommitOutcome не понижается до подтверждённого refusal. Неожиданный programming error не выдаётся за бизнес-отказ: fault boundary сохраняет traceback; catch-all mapping в pipeline запрещён.

`finish_preparation`, `cancel`, holder public acquire/release/handoff, GC/delete и read_verified не вызываются stage и в эту таблицу не включены. Новый SQL_ROWS backend добавляет свои sites до допуска specialization; mapping BLOB/SQLite не объявляется автоматически полным для неизвестного SQL adapter. Приёмочные cases: каждый predicate отдельно, corrupt persisted state вместе со stale lease (corruption не маскируется), missing hold при writable lease, нормальный concurrent cancel, rollback failure поверх typed refusal, cause chain и отсутствие raw ValueError на перечисленных runtime paths.

### Транзитивный inventory SQLite write path

Это дополнение к верхней таблице, включая вызываемые private методы. Existing storage classes сохраняются; новых engines/holders/POJO не требуется. Все SQL эффекты — через один согласованный coordinator/access/registry, конкретные identity проверки constructors обязательны.

| Existing owner / методы в closure | Ответственность, dependencies/effects | Критерий отказа |
|---|---|---|
| SqliteArtifactCatalog: reserve, seal, _lease, _find, _by_id, _descriptor, _storage, _writers | Catalog rows/storage facts и atomic lease/hold/claim admission; scopes, operations, operationArtifacts, holder static append/chain | IO backend, own completion, незамкнутая транзакция проверки/записи, неверная classification corruption как refusal |
| SqliteArtifactLeases: assert_writable, writer, _transaction, _cleanup, _release; TARGET require_standalone | Fenced claims и drain; catalog/scopes/access, existing coordinator transactions | Borrow ambient stage, release до worker drain, скрытый retry unknown, новый terminal R в writer API |
| SqliteArtifactHolders: _key, _chain, _append, _operation_hold | Проверка chain, idempotent append operation hold в переданном scope, без своего commit | Вызов public acquire/handoff или history traversal вместо scoped append; смешение source/target owners. Конструктор holder/history не нужен для этих static методов |
| SqliteOperationArtifacts.read | Read active operation refs через ScopedSqliteAccess и ArtifactCatalogRow | Запись/hold acquisition, доверие malformed persisted descriptor |
| SqliteOperationStore._load/_event | Полное persisted OperationRecord: access, operationArtifacts, codec, evidence; только чтение в переданном scope | Выполнение claim/terminal write из staging, пропуск terminal evidence ради быстрого writable check |
| StoredTerminalCodec.decode, canonical codec, checked blob, row validation | Pure stored terminal verification; schema manifest и owning result models | Fallback legacy/unknown root, IO, признание corruption отсутствием operation |
| SqlitePublicationEvidence.check | Historical consistency terminal; access, world/player publication stores; read-only | Новая публикация/Source call/repair/retry вместо проверки evidence |
| SqliteWorldPublicationStore._by_id / SqlitePlayerPublicationStore._for_operation и их nested persisted readers | Existing owning historical read closure, достигается при terminal operation; shared scope/access | Вынос этих проверок в Artifacts либо объявление их недостижимыми для stale/terminal lease. Их полная nested class audit остаётся OPEN, не скрыта общей строкой catalog |
| ScopedSqliteAccess.one/all/one_row/all_rows/insert; mapper to_row/from_row | Capability-checked SQL, typed hydration; scope registry и existing connection | Собственный commit, передача connection worker, raw row errors как user input |
| SqliteArtifactScope._require_unbound/transaction/read_scope/bind | Task-local scope lifetime, existing coordinator; stage требует unbound, internal transactions могут локально bind | Stage borrowing caller scope; scope reset раньше окончания SQL |
| SqliteScopeRegistry.issue/check/read_only/revoke/assert_available/quarantine; SqliteCommitScopeBinding | Task/connection/lifetime/write capability; existing Database/GuardedConnection | Foreign/expired scope accepted, разрешение worker по copy_context |
| SqlitePublicationCommitStore.transaction/read_scope/_transaction/_quarantine | Own transaction begin/commit/rollback acknowledgement; registry, transaction driver, Database/GuardedConnection | Nested ambient stage, acknowledgement предположен, ошибка rollback выдана как confirmed refusal |
| SqliteTransactionDriver; GuardedConnection.unit_of_work; Database.main_conn | Existing serialized connection execution, transaction completion/drain | Новый механизм lock/UOW, потеря driver failure/unknown, перенос live connection между tasks. Детальный method-level audit этих нижних компонентов остаётся OPEN |
| ContentAddressedBlobBackend.write/_ref/_path/_contained/_io/_temp/_place/_verify/_sync_directory/verify | Bytes binding, repeated encoding, contained immutable storage, fsync, fenced claims/drain | Mutable input, overwrite existing body, IO после claim release. Existing _io использует copy_context: это НЕ выдаёт worker capability; worker callbacks не могут пользоваться scope/connection |

Прямая trace: DAG → StageOpenPipeline → admission/descriptor → writer.require_standalone → lease._lease → operations._load (event/refs/terminal/evidence) → catalog.reserve (lease/find/holder append) → backend.write (claim transaction/IO/drain/release) → seal claim → backend.verify → catalog.seal (find/lease/writers/holder chain/storage fact) → release → log → ArtifactRef. Проверки terminal/evidence могут исполниться уже при первом assert_writable для старой операции; их нельзя исключить по happy-path PREPARING.

Такой inventory делает H2-связность видимой, но не выдаёт за завершённую проверку lower-level closure: отмеченные nested history/driver audit нужно завершить до локальной приёмки. Узкий protocol не является основанием обходить эту проверку.

## Transactions, отказ и конкуренция

Stage — **только standalone**: не принимает CommitScope и не присоединяется к ambient transaction. Первое действие writer.write, до assert_writable/read/reserve/physical IO: admission.require_standalone(). TARGET SqliteArtifactLeases.require_standalone вызывает existing scopes._require_unbound(), registry.assert_available() и проверяет отсутствие принадлежащих текущей task owns_unit_of_work/owns_transaction на existing GuardedConnection. Неверная binding/task/connection или ambient UOW — PublicationInfrastructureError до первого эффекта; quarantine — existing UnknownCommitOutcome. Проверка не присваивает connection/scope и не открывает UOW. Далее каждая storage transaction сохраняет собственные повторные проверки coordinator, в том числе после ожидания gate. Параллельная task не отклоняется только потому, что другая task владеет UOW: она ждёт existing coordinator. Общий SqliteArtifactScope.transaction продолжает поддерживать borrowing для других контрактов, но stage его не использует. Borrowed completion — отдельный scoped контракт; existing standalone finish нельзя оборачивать bind.

| Сценарий | Обязательный результат |
|---|---|
| Descriptor mismatch | Отказ до reserve и physical write |
| Ошибка write/verify | Нет seal success; reservation/hold не снимается самовольно. Cleanup выполняет owning cancel/GC после drain |
| Cancel во время worker IO | Claim остаётся до окончания IO; cancellation не означает остановку thread. Только потом возможен release |
| Unknown reserve/seal commit | Проброс UnknownCommitOutcome; ни retry, ни cleanup, ни success по предположению. Existing reconciliation у владельца lifecycle |
| Повтор stage | Content address и exact descriptor проверяются заново; writable/fence проверяются заново; никакого cached authority |
| Две DAG invocations | Независимые leases/tasks/connections; сериализация mutable checks обеспечена storage coordinator, не Python instance lock |
| Thread workers | Передаются только immutable данные и IO arguments; scope/connection/context authority не переносятся автоматически |

Full-route completion остаётся отдельным PROPOSED из owning-плана: Publication UOW содержит acquisition target holds, exact set, candidate и READY; scoped Artifacts port не коммитит, не вызывает Source, не отпускает source protection. Rollback откатывает новые effects вместе, unknown удерживает protection до reconciliation. Этот документ не замораживает ещё неизвестный public Publication IO/Error.

## Проверки до регистрации и приёмки

1. P1 для КАЖДОГО concrete C/registration: original → ArtifactPrepareStageInput → PrepareArtifactInput → prepare admission → PreparedArtifact → PrepareArtifactOutput → Engine validation/catalog/read → ArtifactStageInput → StageArtifactInput → stage admission → writer. Проверять content identity на всех уровнях и prepared identity после всех вложенных Pydantic wrappers. Реально исполнять зарегистрированный маршрут; workflow JSON round-trip не проходит. `model_construct`, object registry и изменения Engine запрещены.
2. P2 complete-path benchmark: codec/row_count/digest counters отдельно prepare/check/backend verification, peak RSS и Python allocations раздельно, wall time, concrete sizes/repeats/environment. Контрольный descriptor остаётся обязательным; оптимизация только по измерениям.
3. SQL_ROWS: concrete adapter/C обязателен для заявления о готовности этого binding; coherent row-set, canonical descriptor, bounded fetch и budget отказ ДО полной материализации. Bytes binding не служит evidence SQL_ROWS. Отдельно memory bounds для encoding stage и для read.
4. Independent connections: cancel между write/seal, GC против reserve/write/verify/seal, restart с pending reservation, stale fence, identical replay, descriptor conflict; assertions по holds/claims/catalog/physical body и отсутствию premature cleanup.
5. Completion tests принадлежат совместному срезу: injected rollback после acquisition/candidate/READY, unknown commit/rollback, concurrent cancel и exact replay с fresh connection, включая уже освобождённые holds. Standalone finish tests этого не доказывают.

Тесты сейчас не запускались: документ не содержит реализованных TARGET классов. Написание этих тестов относится к отдельно разрешённой реализации; их PASS требуется для регистрации и приёмки реализации, не выдаётся заранее.

## Приёмка по правилу агента

| Критерий | Статус и основание |
|---|---|
| Три запрета DAG | TARGET локально соблюдены описанным trace; интеграция OPEN: existing Pack bypass и concrete registrations |
| Ответственность классов | Предложена конкретная декомпозиция write path; полный ARCH-0 OPEN: read/protection/completion lifecycle и H2 cutover не закрыты этой таблицей |
| Public/internal boundary | Локальный TARGET определён; точный mapping storage errors и concrete bindings OPEN |
| Неизменность порядка | prepare → stage сохранён; foreign consumer cutover/нормативная синхронизация через координатора OPEN |
| CRUD данных: create/read/update/delete | create: этот stage proposal; read: bounded verified read OPEN; update: content immutable, замена owning refs у consumer, публичный контракт OPEN; delete: guarded GC existing, публичный caller contract OPEN |
| CRUD настроек: create/read/update/delete | Fixed composition не доказывает отсутствие потребности в настройках. По всем четырём операциям applicable scope/публичный контракт не зафиксирован: OPEN, искусственные методы не добавляются |
| Foreign CRUD | Producer→DAG→Artifacts зафиксирован; authority/lifecycle/public completion требуют owning contracts, OPEN |
| POJO/error closure | Reuse ArtifactRef/lease/reservation зафиксирован; TARGET wrappers требуют concrete C identity validation, storage refusal mapping и полного field inventory, OPEN |
| Совместная приёмка | Требуется координатор и решение пользователя; отправка proposal не означает PASS |

**Вердикт: архитектурное предложение существенно конкретизировано; ARCH-STAGE и ARCH-0 ещё не приняты.** Следующая проверка — точная совместимость декомпозиции с H2 и устранение bypass Pack, не разрешение писать весь Artifacts. Ни одна ранее предоставленная гарантия не ослаблена ради локального среза.
