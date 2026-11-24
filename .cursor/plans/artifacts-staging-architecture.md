# Artifacts: архитектура staging, 2026-11-21

## Приоритетное ограничение пользователя — 2026-11-24

По уточнению основного координатора: пользователь сказал «Пока маршрут не закрыт, я не даю добро», затем поручил закрыть маршрут, оставив генератор/gameplay и верхнее получение inputs вне scope. Текущая работа — контрактный маршрут; прежнее разрешение реализации не является code-go зависимой реализации/активации. Исторические заявления ниже о сохранённом разрешении читать с этим ограничением.

Concrete binding рассматривается от готовых typed inputs; synthetic caller допустим. Реализация генератора/gameplay, новые APIs/ноды для них и верхняя orchestration не добавляются в план и не становятся gates. Клетка producer в binding matrix означает owning преобразование готового входа (например Pack), а не обязательную реализацию внешнего источника. Authority и lease issuance внутри согласуемой owning boundary требуют реального контракта, не synthetic lease или доверия caller payload. Закрываются Pack/Artifacts/issuer IO/Error, format binding, внутренний транспорт и POJO inventory; без implicit BLOB выбора.

Snapshot scoped handoff — отдельный bounded контракт из `artifacts-scoped-held-refs-contract.md`, не standalone stage и не ожидание полного completion. Предложение scoped lookup передано координатору (2), реализация до сведения с Publication не выполняется. Ни внешние generator/gameplay, ни full Source/Pack production для этого стыка не требуются.

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
| Existing ArtifactFormatContract[C], ArtifactBackend[C] | Контракт concrete format и storage write/verify/delete; TARGET read-only write_admission раскрывает только используемый claim port для composition check | Producer semantics не попадает в generic Artifacts; иной скрытый claim adapter, mutable C или unbounded SQL binding без доказательств — отказ регистрации |
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

**Composition closure (TARGET, обязательна до выдачи writer):** одних независимых constructor arguments недостаточно. Минимальные дополнения existing внутренних портов:

- `ArtifactBackend[C].write_admission` — read-only property `-> IArtifactWriteAdmission`, возвращает именно объект, которым backend реально получает claims; ContentAddressedBlobBackend возвращает свой `_leases`, а не новый proxy. Конструктор BLOB backend в TARGET принимает этот узкий port. Каждый concrete SQL_ROWS binding предъявляет такую же связь до регистрации; неподтверждённый backend не допускается.
- `IArtifactCatalog.assert_write_admission(self, admission: IArtifactWriteAdmission) -> None` — sync pure composition check, без SQL и без выдачи scope. SqliteArtifactCatalog реализует проверку SQLite object graph ниже; неизвестная реализация admission отвергается, а не считается совместимой по наличию методов. Это внутренний порт, не DAG input и не публичная storage capability.
- Writer constructor после `backend = registry.resolve(contract)` проверяет `backend.write_admission is admission`, затем вызывает `catalog.assert_write_admission(admission)`. До успешных checks instance не выдаётся и stage не вызывается. Failure — PublicationInfrastructureError конфигурации, не lease refusal. На runtime write дополнительно проверяется неизменность `backend.write_admission is admission`; wiring связей immutable после construction, hot-rebind запрещён.

Точный проверяющий SQLite graph — **SqliteArtifactCatalog.assert_write_admission**, а не generic writer и не новый factory. При `admission: SqliteArtifactLeases` он проверяет identity: `admission._scopes is self._scopes`, `admission._operations is self._operations`, `admission._access is self._access`, `self._access is self._scopes.access`, `self._operations._commits is self._scopes.commits`, `self._operations._access is self._access`, `self._operations._artifacts is self._artifacts`, `self._artifacts._access is self._access`, `self._access.registry is self._scopes.commits.registry`. Также проверяется внутренний catalog admission: `admission._catalog._scopes is self._scopes`, `_operations is self._operations`, `_artifacts is self._artifacts`, `_access is self._access`. Проверки private implementation links остаются внутри SQLite adapter layer; generic application writer видит только два описанных выше typed public члена внутренних портов. Scope/coordinator/access/registry наружу не экспортируются. Existing checks constructors operations/evidence/scopes сохраняются; H2 target checks добавляются owning composition отдельно.

Concrete composition trace: existing `core/container/packs.py::PacksWiring.initialize_pack_storage` сейчас создаёт один registry/access/commits/operations/leases и регистрирует BLOB backends, но **не создаёт новый stage writer и не доказывает его binding**. TARGET registration использует один именованный `artifact_scopes = SqliteArtifactScope(commits, access)` для `leases = SqliteArtifactLeases(artifact_scopes, operations, artifacts)` и `catalog = SqliteArtifactCatalog(artifact_scopes, operations, artifacts)`; backend создаётся с этими `leases`, регистрируется в format registry; writer получает тот же registry/contract/catalog/admission=leases и выполняет checks выше. Это конкретный assembly recipe для согласованной specialization, не разрешение менять PacksWiring или создать универсальную фабрику. Уже зарегистрированный backend с другим lease adapter не переиспользуется молча.

Так standalone guard admission проверяет тот же ContextVar scopes, который catalog мог бы borrow, и тот же coordinator/access/registry, который обслуживает backend claims и внутренний lease catalog. Приёмка: отдельно подменить backend leases, catalog scopes (даже с теми же commits/access), coordinator, access, registry, operation store, artifact reader и внутренний lease catalog; каждый mismatch отвергается до SQL/IO. Positive case — один graph. Guard coverage не доказывается одинаковым database path или равенством DTO.

В описании write/seal ниже `leases.assert_writable/writer` означает вызовы **admission.assert_writable/writer** через этот узкий port. Семантика остаётся existing: assert_writable — текущая fenced admission проверка, не долговечное разрешение; writer — acquire/release существующего fenced claim, cancellation требует drain. Ошибки и unknown outcome не преобразуются самим structural port; TARGET site mapping задан ниже, изменения owning boundaries требуют реализации и сверки. Новый протокол не ослабляет атомарные checks catalog.reserve/seal.

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
| catalog._lease: operations._load вернул None | Lease(OPERATION_MISSING), если нет orphan admission rows; иначе Invariant | По единому порядку ниже: сначала проверка отсутствующего владельца и admission rows, не ранний return |
| catalog._lease: world/kind/preparation_fingerprint отличается | Lease(BINDING_MISMATCH) | Только после полной проверки persisted operation/admission facts; до fence/phase checks |
| catalog._lease: record.fence отличается | Lease(FENCE_MISMATCH) | Только после persisted checks и binding comparison |
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
| Backend.write: самостоятельный повторный contract.encode(content) выбросил Exception | ArtifactCodecError с исходным cause | В ContentAddressedBlobBackend.write непосредственно вокруг вызова callback, до acquisition writer claim/physical IO; уже созданные reservation/hold не снимаются. Existing typed ArtifactCodecError пробрасывается, CancelledError/BaseException не ловить; исключение callback не классифицируется по тексту/типу ValueError |
| Backend._contained: escape/symlink/junction; _verify: size/hash отличается; missing final body | Existing Infra (existing CorruptBlobError, если конкретный backend уже его возвращает, сохраняется) | Physical storage boundary. BLOB _verify сейчас возвращает Infra, не заявлять CorruptBlobError реализованным там |
| Backend temp/place/fsync/open/unlink: OSError, включая cleanup | Existing Infra с cause | Owning physical IO boundary; existing target path при placement не ошибка сам по себе, затем verification обязательна |
| Writer проверяет возвращённые reservation/ref против запрошенных | Invariant | Writer непосредственно после catalog результата |
| Coordinator commit/rollback unconfirmed; quarantined connection | Existing UnknownCommitOutcome | Проброс без переклассификации/retry/cleanup; confirmed rollback нужен для выдачи ожидаемого отказа |
| Cancellation в backend worker / claim acquire/release | Existing CancelledError после existing drain; неизвестный cleanup outcome остаётся UnknownCommitOutcome | Backend _io и leases cleanup владеют ожиданием, pipeline не подменяет это освобождением holds |
| После seal: ArtifactLogRecord construction, emit type/validation/cause/level/serialization до sink | Invariant с cause | Writer в узкой boundary формирования и emit seal event нормализует validation/configuration ошибки; не охватывает storage/codec. Seal уже committed: это fault доставки результата, не rollback/refusal и не UnknownCommitOutcome |
| После seal: UnknownLogConsumerError из emit | Existing UnknownLogConsumerError без изменения | Fail-fast сохраняется; writer не подавляет и не превращает в lease/input refusal. ArtifactRef не возвращён, но confirmed seal не отменён; ни компенсационного release, ни автоматического retry |
| После seal: обычное Exception внутри sink _LOGGER.log | Existing emit подавляет ошибку; stage возвращает ArtifactRef | Только существующая sink boundary. Не распространять suppression на validation до sink или UnknownLogConsumerError |

**Единый TARGET порядок catalog._lease (в одном переданном scope):** (1) operations._load полностью проверяет persisted operation/event/terminal/evidence; load failure — Infra. (2) Загрузить raw admission boolean check и все admission events для operation_id. Если record отсутствует: наличие любых admission rows — orphan state, Invariant; отсутствие и record, и admission rows — Lease(OPERATION_MISSING). Никакой fence/binding comparison для отсутствующей operation нет. Это проверка локальных operation/admission facts, не обещание глобального аудита всех таблиц. (3) При существующем record проверить все admission rows: raw bool, shape/UID, sequence/predecessor/root, owner, monotonic fence и запрет reopening относительно **persisted record.fence**, а не requested fence. Повреждение — Invariant независимо от неверного входного lease. (4) Только затем классифицировать requested binding mismatch, затем requested fence mismatch. (5) Для writable проверить latest absent → LEASE_ABSENT, phase != PREPARING → PHASE_NOT_WRITABLE, closed → ADMISSION_CLOSED, latest fence mismatch → FENCE_MISMATCH. Для closed режима применяется его existing контракт после тех же persisted checks; stage этот режим не вызывает.

Таким образом, TARGET требует **перестановки existing ранних comparisons после admission chain validation**, а не только замены raise. Нормативная последовательность выше имеет приоритет над порядком строк таблицы. Приёмочные случаи: corrupt admission + wrong binding; corrupt admission + wrong fence; corrupt operation + missing admission; orphan admission без operation; clean missing operation; valid persisted facts с несколькими входными несовпадениями. Первые четыре — infrastructure, последний классифицируется binding перед fence. Проверять и read assert_writable, и transaction reserve/writer/seal, поскольку все используют _lease.

Для остальных checks, которые сейчас непосредственно делают `raise ValueError`, TARGET меняет raise на typed carrier в owning месте; parsing текста exception запрещён. Если причина поймана как exception, использовать `raise ... from error`; при прямом predicate raise первичного exception нет, искусственный ValueError-cause не создаётся. При secondary cleanup failure сохранять исходное исключение в цепочке context/cause; UnknownCommitOutcome не понижается до подтверждённого refusal. Неожиданный programming error не выдаётся за бизнес-отказ: fault boundary сохраняет traceback; catch-all mapping в pipeline запрещён.

Post-seal fault не означает, что запись отсутствует: confirmed seal/hold сохраняется до самостоятельного lifecycle действия; DAG останавливает зависимый completion, не запускает автоматическое повторное staging или освобождение по logging exception. Ошибка логирования не даёт гарантии live hold в момент её доставки. Тесты отдельно инъецируют callback exception повторного encoding, log validation до sink, UnknownLogConsumerError и обычный sink exception; проверяют category/cause, число encode, отсутствие seal для codec fault и сохранённый sealed catalog/hold без compensation для post-seal faults.

`finish_preparation`, `cancel`, holder public acquire/release/handoff, GC/delete и read_verified не вызываются stage и в эту таблицу не включены. Новый SQL_ROWS backend добавляет свои sites до допуска specialization; mapping BLOB/SQLite не объявляется автоматически полным для неизвестного SQL adapter. Приёмочные cases: каждый predicate отдельно, corrupt persisted state вместе со stale lease (corruption не маскируется), missing hold при writable lease, нормальный concurrent cancel, rollback failure поверх typed refusal, cause chain и отсутствие raw ValueError на перечисленных runtime paths.

### Транзитивный inventory SQLite write path

Это дополнение к верхней таблице, включая вызываемые private методы. Existing storage classes сохраняются; новых engines/holders/POJO не требуется. Все SQL эффекты — через один согласованный coordinator/access/registry, конкретные identity проверки constructors обязательны.

| Existing owner / методы в closure | Ответственность, dependencies/effects | Критерий отказа |
|---|---|---|
| SqliteArtifactCatalog: reserve, seal, _lease, _find, _by_id, _descriptor, _storage, _writers; TARGET assert_write_admission | Catalog rows/storage facts и atomic lease/hold/claim admission; scopes, operations, operationArtifacts, holder static append/chain; pure composition identity check | IO backend, own completion, незамкнутая транзакция проверки/записи, неверная classification corruption как refusal, принятие чужого scope graph |
| SqliteArtifactLeases: assert_writable, writer, _transaction, _cleanup, _release; TARGET require_standalone | Fenced claims и drain; catalog/scopes/access, existing coordinator transactions | Borrow ambient stage, release до worker drain, скрытый retry unknown, новый terminal R в writer API |
| SqliteArtifactHolders: _key, _chain, _append, _operation_hold | Проверка chain, idempotent append operation hold в переданном scope, без своего commit | Вызов public acquire/handoff или history traversal вместо scoped append; смешение source/target owners. Конструктор holder/history не нужен для этих static методов |
| SqliteOperationArtifacts.read | Read active operation refs через ScopedSqliteAccess и ArtifactCatalogRow | Запись/hold acquisition, доверие malformed persisted descriptor |
| SqliteOperationStore._load/_event | Полное persisted OperationRecord: access, operationArtifacts, codec, evidence; только чтение в переданном scope | Выполнение claim/terminal write из staging, пропуск terminal evidence ради быстрого writable check |
| StoredTerminalCodec.decode, canonical codec, checked blob, row validation | Pure stored terminal verification; schema manifest и owning result models | Fallback legacy/unknown root, IO, признание corruption отсутствием operation |
| SqlitePublicationEvidence.check | Historical consistency terminal; access, world/player publication stores; read-only | Новая публикация/Source call/repair/retry вместо проверки evidence |
| SqliteWorldPublicationStore._by_id → _publication_by_id/_ref → _check_timeline/_read_head; worldPublicationValidation.decode_publication/validate_bootstrap/validate_transition | Historical world publication, predecessor, operation, timeline и snapshot head checks; только shared access reads и pure validation | Missing/mismatched predecessor/operation/timeline/head — Infra, не stale lease; initialize/compare_append в stage недостижимы |
| SqlitePlayerPublicationStore._for_operation → _ref | Чтение participants, predecessor sequence, snapshot ownership/lineage; shared access, existing PlayerSnapshotRef | Missing/invalid parent/root/head/lineage — Infra; compare_append и repair запрещены |
| ScopedSqliteAccess.one/all/one_row/all_rows/insert; mapper to_row/from_row | Capability-checked SQL, typed hydration; scope registry и existing connection | Собственный commit, передача connection worker, raw row errors как user input |
| SqliteArtifactScope._require_unbound/transaction/read_scope/bind | Task-local scope lifetime, existing coordinator; stage требует unbound, internal transactions могут локально bind | Stage borrowing caller scope; scope reset раньше окончания SQL |
| SqliteScopeRegistry.issue/check/read_only/revoke/assert_available/quarantine; SqliteCommitScopeBinding | Task/connection/lifetime/write capability; existing Database/GuardedConnection | Foreign/expired scope accepted, разрешение worker по copy_context |
| SqlitePublicationCommitStore.transaction/read_scope/_transaction/_quarantine | Own transaction begin/commit/rollback acknowledgement; registry, transaction driver, Database/GuardedConnection | Nested ambient stage, acknowledgement предположен, ошибка rollback выдана как confirmed refusal |
| SqliteTransactionDriver._require_owner/begin/_acknowledge/commit/rollback/close | BEGIN и acknowledged COMMIT/ROLLBACK на existing worker; shield/drain сообщает cancellation coordinator | pending.result failure не доказательство rollback; новый worker/connection, early release — отказ |
| GuardedConnection._acquire/_release/_has_transaction/owns_unit_of_work/owns_transaction/_worker_result/_execute/unit_of_work; Database.main_conn | Task-owned gate, existing connection identity, SQL worker drain; implicit rollback вне explicit UOW | Владение другой task не даёт текущей права использовать scope; gate не освобождается до settling work. Обход owning coordinator ради nested stage запрещён |
| ContentAddressedBlobBackend.write/_ref/_path/_contained/_io/_temp/_place/_verify/_sync_directory/verify | Bytes binding, repeated encoding, contained immutable storage, fsync, fenced claims/drain | Mutable input, overwrite existing body, IO после claim release. Existing _io использует copy_context: это НЕ выдаёт worker capability; worker callbacks не могут пользоваться scope/connection |

Прямая trace: DAG → StageOpenPipeline → admission/descriptor → writer.require_standalone → lease._lease → operations._load (event/refs/terminal/evidence) → catalog.reserve (lease/find/holder append) → backend.write (claim transaction/IO/drain/release) → seal claim → backend.verify → catalog.seal (find/lease/writers/holder chain/storage fact) → release → log → ArtifactRef. Проверки terminal/evidence могут исполниться уже при первом assert_writable для старой операции; их нельзя исключить по happy-path PREPARING.

Дополнительно прочитаны nested world/player readers, transaction driver и GuardedConnection: они не добавляют доменных записей в этот trace. Их persisted/driver failure sites относятся к строкам Infra/Unknown выше, а не новым lease refusal. Узкий protocol не устраняет ни эти зависимости, ни обязанность согласовать дельты их error boundaries с владельцами; implementation evidence и независимая повторная приёмка ещё требуются.

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

6. Standalone entry: stage внутри scopes.bind(write/read), внутри same-task unbound coordinator UOW и implicit transaction — отказ ДО catalog insert/holder append/claim/physical IO; проверить неизменность внешней transaction и отсутствие её commit/rollback со стороны stage. Другая task на той же connection ждёт gate; independent connection проходит свои fence checks. Quarantine сохраняет UnknownCommitOutcome. Pure prepare не получает ограничение на ambient scope, поскольку не имеет storage effects.

### Статус замечаний независимой приёмки

P1 errors: приведён site mapping и владельцы conversion, требуется повторная приёмка TARGET и реализация, не объявлять существующие ValueError уже устранёнными. P1 ambient: выбран standalone с explicit pre-effect check; это дельта proposed lease port, предъявляется координатору. P1 inventory: транзитивный SQLite/BLOB trace раскрыт, неизвестный SQL_ROWS adapter не покрывается этой проверкой. P2 H2: runtime и design разделены.

P1 Pack integration остаётся OPEN. [Карта перехода](pack-staging-completion-cutover.md) — источник owning cutover, но пока не exact принятый контракт: producer output/evidence, completion IO/Error и возвращаемый candidate должны быть зафиксированы Pack/Publication. Критерий удаления old path: согласованные Output→Input mappings, проверенные concrete DAG registrations, confirmed completion→candidate/replay tests и полный production/test caller inventory. После переноса caller прямые manifest_stager.stage/staging.finish_preparation в нём запрещены; старый helper не остаётся fallback. До выполнения критериев он обозначен только existing, не целевой маршрут. Artifacts не исправляет Pack helper/plan самостоятельно и не принимает перенесённого caller. Локальный неизменяющий его срез не блокируется всем completion автоматически.

Тесты сейчас не запускались: документ не содержит реализованных TARGET классов. Написание этих тестов относится к отдельно разрешённой реализации; их PASS требуется для регистрации и приёмки реализации, не выдаётся заранее.

## Приёмка по правилу агента

### Уточнение inventory и координации — 2026-11-24

**Результат адресной сверки агента (2), получен 2026-11-24:** п3 PASS TARGET — standalone guard до IO, backend.write_admission identity и catalog.assert_write_admission graph; Publication явно подтвердил private operations links внутри SQLite composition check (не generic writer/Pack/DAG), без расширения Publication API. PASS TARGET — persisted operation/terminal/evidence → admission chain по persisted fence → requested binding/fence → writable; missing+orphan infrastructure, clean missing OPERATION_MISSING. Existing catalogStore ещё не соответствует этому порядку: это implementation delta, не повторно открытый архитектурный finding. При изменении _lease проверить всех callers и сохранить closed contract writable=False. Callback/post-seal/log mapping поддержан с no false rollback/unknown/compensation; runtime tests остаются обязательными.

Уточнение actual H2 по сверке: leases generic, store/ledger identity checks уже есть; ArtifactStagingService ещё nongeneric, новый stage graph отсутствует. Исторические формулировки «всё только TARGET» не применяются к уже реализованным owning компонентам. Полная ARCH-STAGE приёмка по этому сообщению не выдана.

**П1 — точная кандидатная строка Pack, пока PROPOSED:** `app.application.worldData.pack.preparation.packManifestPreparationOpenPipeline.PackManifestPreparationOpenPipeline.prepare_material(PackPreparationInput) -> PackManifestMaterial`; `app.dataModel.worldPack.preparation.manifestMaterial.PackManifestMaterial.content:bytes` → ArtifactPrepareStageInput[bytes] → PreparedArtifact[bytes] → ArtifactStageInput[bytes](lease,prepared) → ArtifactRef → `PackStagedManifestInput.artifact` → `admit_staged -> PackStagedManifest`. Owning источник endpoints/DTO — `pack-staging-owning-contract-delta.md`; это не actual или accepted маршрут.

Existing format-кандидат: `app.application.worldData.pack.encoding.manifestFormat.manifest_format`, key `world_pack.manifest.json`, BLOB/bytes/row_count=None, actual storage version 1 (не назначение final schema). Existing encode вызывает semantic decode_manifest; перенос semantics в Pack producer/consumer требует owning consumer inventory и согласованного cutover, не скрытой замены format factory в Artifacts.

Точные оставшиеся binding gaps: (а) принятие proposed producer/consumer IO/Error и semantic placement; (б) exact issuer error/live admission contract — existing ArtifactStagingService.open_operation является только кандидатом, повтор может вернуть CLOSED lease, не гарантирует writable; (в) concrete in-memory DAG binding и identity gate. Fake lease/synthetic authority и новые nodes не вводятся. Эти уточнения заменяют формулировку «кандидат вообще неизвестен», но не заполняют accepted value в binding matrix. Full completion не prerequisite этого среза. POJO/error inventory данной кандидатной цепочки продолжает Artifacts после сверки owning DTO, без объявления proposal принятым.

По прямому поручению пользователя concrete binding и приёмка изменённых storage/error границ переданы агенту «Between domain operations (2)», `01a1f529-898c-7342-82f4-1e68983b3a9c`. POJO/error inventory остаётся работой Artifacts; не делегируется пользователю или координатору. Передача запроса не означает закрытие gate.

Сверка actual shared diagnostics уточняет общий inventory:

- `dataModel/validation/diagnostics/fieldPathError.py::FieldPathError[CodeT]`: code:concrete Enum, path:ValidatedFieldPath, message:StrictStr. Strict/frozen/extra-forbid/revalidate always; допустим только именованный concrete subclass. TARGET ArtifactInputIssue наследует его, не копирует поля и не создаёт generic FieldPathError экземпляры.
- `validation/importIssues/jsonFieldError.py::JsonFieldError`: унаследованные code/path/message плюс location:WireLocation, wire_path:tuple[WirePart,...] (непустой), schema_id:StrictStr|None, pydantic_type:ErrorType|None. pydantic_type присутствует ровно для SCHEMA_VIOLATION. path — canonical declared field, wire_path — фактический alias; Artifacts не подменяет одно другим.
- `validation/importIssues/wireShapeIssue.py::WireShapeIssue`: code:JsonValidationCode, location:WireLocation, message:StrictStr, pydantic_type:ErrorType|None с тем же условием SCHEMA_VIOLATION. Не FieldPathError: применяется, когда declared POJO field отсутствует. Фиктивный path не создаётся.
- TARGET `ArtifactInputError.issues` — непустой tuple этих двух existing concrete classes либо ArtifactInputIssue; aggregation через existing ValidatorAggregationHelper, независимые issues в стабильном порядке. Lease failure остаётся logic POJO, corruption/codec/unknown не добавляются в issues.
- Все TARGET runtime wrappers и carriers остаются без назначенных wire IDs. Generic node wrappers из owning DAG-плана не получают копии content/descriptor/lease полей; concrete schema/field-selector inventory дополняет Artifacts после получения owning C, а не запрашивает его проектирование у пользователя.

**Изменение runtime с предыдущей сверки:** `dataModel/artifacts/lifecycle/operation/record.py` теперь содержит `OperationRecord[R: SnapshotApplyResult]`: operation_id, world_uid, kind, preparation_fingerprint, publication_fingerprint?, phase, fence>=1, leased_artifacts и terminal:R|PackActivationResult|GameplayStarted|OperationCancelled|None. Проверяются terminal↔phase, fingerprint при APPLYING, уникальность refs, operation/world/kind/result correlation. Это existing generic POJO, не новое зеркало stage. Поэтому историческое утверждение о bare OperationRecord нельзя распространять на весь текущий runtime. При этом наличие generic record само по себе не доказывает завершённые H2 factory checks всех adapters; они сверяются отдельно по актуальному коду. Данные terminal не включаются в public stage result.

### Повторная независимая проверка — 2026-11-22

Чат «Artifacts — независимая приёмка архитектуры», `01a1ffc7-1b31-71f2-935a-b1b2e710ae68`, закрыл три последних findings **на уровне архитектуры**: persisted-first _lease, standalone composition closure, repeated codec/post-seal error mapping. Runtime PASS не выдан. ARCH-STAGE остаётся OPEN: concrete specialization и полный POJO inventory её closure. Разрешение реализации получено 2026-11-22 через координатора; повторно оно не запрашивается, но не подменяет приёмку exact binding. Координатору направлен запрос на принятые producer/content/format/version/lease issuer/consumer/caller route. Full Source/Pack completion не является автоматическим prerequisite независимого stage.

Общий POJO inventory до получения concrete binding (пути относительно backend/app; это не утверждение полного concrete closure):

| Тип / модуль / статус | Поля, validation, владелец и отсутствие зеркала |
|---|---|
| Existing `dataModel/artifacts/references.py::ArtifactRef` | Artifacts: kind, format_key, format_version, content_hash, nbytes>=0, row_count>=0 либо None; BLOB запрещает row_count, SQL_ROWS требует его. Strict/frozen/extra-forbid/revalidate always. Используется напрямую, не копируется в descriptor DTO |
| Existing `references.py::ArtifactFormatMetadata`, ArtifactFormatRegistry | Artifacts: key/supported_versions nonempty; entries tuple с unique keys. RegistryKey/FormatVersion/RevisionHex переиспользуются; не authority и не budgets |
| Existing `dataModel/artifacts/lifecycle/lease.py::OperationLeaseRef` | Artifacts lifecycle: operation_id/world_uid/kind/preparation_fingerprint/fence>=1, strict/frozen/extra-forbid/revalidate always. Structural validity не подтверждает live lease/authority; issuer остаётся concrete binding prerequisite |
| Existing `lease.py::StagingReservation` | Artifacts storage: artifact_id/lease/ref, те же strict/frozen настройки; только internal, отсутствует в DAG Input/Output |
| TARGET `dataModel/artifacts/staging/preparedArtifact.py::ArtifactPrepareStageInput[C]` | content:C, strict/frozen/extra-forbid; concrete schema + deep immutability; admitted content instance сохраняется |
| TARGET тот же модуль `PreparedArtifact[C]` | content:C/descriptor:ArtifactRef; runtime envelope без wire ID, authority и storage lifetime. Instance-preserving validation не отключает schema checks |
| TARGET `dataModel/artifacts/staging/stageInput.py::ArtifactStageInput[C]` | lease:OperationLeaseRef/prepared:PreparedArtifact[C]; strict/frozen/extra-forbid; сохраняются content и prepared identity. Не вводит вторые поля descriptor/lease |
| TARGET `dataModel/artifacts/staging/inputErrors.py::ArtifactInputIssue`, ArtifactInputError | Owning FieldPathError subclass с code/path/message; codes CONTENT_NOT_IMMUTABLE/CONTENT_TYPE_MISMATCH/FORMAT_BINDING_MISMATCH/DESCRIPTOR_MISMATCH. Error: непустой tuple existing JsonFieldError, WireShapeIssue или owning issue; не новый framework field errors |
| Existing `dataModel/validation/diagnostics/fieldPathError.py`, `validation/importIssues/jsonFieldError.py`, `wireShapeIssue.py` | Общие owning diagnostics переиспользуются без переопределения их полей. Concrete accepted field paths и schema refs надо сверить при freeze specialization, не угадывать |
| TARGET `dataModel/artifacts/lifecycle/leaseFailure.py::ArtifactLeaseFailure` | lease/requirement(WRITABLE,CLOSED)/code из owning enum; logic refusal, не field error. Коды и порядок predicates указаны в failure table; не generic stage failure |
| Existing `dataModel/artifacts/events.py::ArtifactLogRecord` | activity/operation_id/world_uid?/preparation_fingerprint?/request_fingerprint?/artifact_hash?/gc_failure?; GC_FAILED требует matching ref hash, остальные запрещают gc_failure. TARGET LEASE_REFUSED/lease_failure — дельта этого типа по owning-плану, не второй event DTO; seal использует existing fields |
| TARGET ArtifactInputRejected, ArtifactLeaseRefused; ArtifactCodecError/ArtifactDescriptorConflictError/ArtifactStorageInvariantError | Application carriers, не POJO/wire models; error/failure и cause, без алгоритмов, logging или новых schema IDs. Existing infrastructure/unknown/busy/cancellation категории не зеркалируются |

Concrete C, owning nested fields/validators/codec schemas, typed field selectors и concrete DAG wrappers/error binding пока не названы принятым маршрутом. Именно этот остаток не позволяет отметить полный POJO closure PASS; наличие таблицы общих типов не заменяет его. Existing persistence row/terminal models из transitive inventory остаются у своих владельцев, в новые transport wrappers не копируются.

### Binding matrix: точные owning gaps — 2026-11-22

Координатор `01a1ef35-3287-7a12-89e2-76273eaa043d` сверил источники: accepted concrete binding не найден; статус зафиксирован в §2 плана нод. Pack material binding — PROPOSED. Пустое поле ниже означает отсутствие accepted значения, не default.

| Binding cell | Accepted value | Владелец необходимого решения / exact gap |
|---|---|---|
| Producer public method и Output field | — | Owning producer (Pack для предложенного material route): exact public Output, поле content/evidence; не existing прямой finish_pack_preparation |
| Concrete C и nested POJO/schema | — | Producer объявляет тип готового content; Artifacts сверяет immutable/identity admission и field/error closure. bytes не назначается автоматически |
| ArtifactFormatContract[C], key, kind, version | — | Owning format + Artifacts composition: exact существующий contract instance/import, supported version; не новый wire/storage ID по догадке |
| Lease issuer public method/Output→OperationLeaseRef | — | Lifecycle/Publication owning issuer: exact world/kind/fingerprint/fence и право stage. Новый issuer не создаётся внутри Artifacts |
| prepare/stage public IO | Общий TARGET V1.1 | Artifacts: signatures определены, но их specialization C/contract/version и принятый foreign mapping ещё отсутствуют |
| DAG caller/transport route | — | DAG/координатор: concrete registration и in-memory route; без нового NodeId/порядка от Artifacts. P1 contract test требуется при регистрации |
| ArtifactRef consumer public Input field | — | Owning consumer + DAG: exact поля, correlation с producer/evidence и граница stage success; proposed completion не accepted consumer |
| Error transport specialization | — | Artifacts предоставляет field/lease/fault категории; DAG фиксирует concrete wrapper mapping, без переопределения owning meaning |

Общий алгоритм stage имеет проработанные архитектурные исправления, но это не означает принятую specialization или готовый runtime. Регистрация требует freeze всех клеток и identity evidence. По текущему owning gate ARCH-STAGE scope включает concrete binding, поэтому полная приёмка остаётся OPEN; нет самостоятельного решения автора заменить её default BLOB или объявить разрешённым общий код в обход gate. Time/Lifecycle, X-READ и полный Pack production не добавляются в prerequisites этого локального решения.

| Критерий | Статус и основание |
|---|---|
| Три запрета DAG | TARGET локально соблюдены описанным trace; интеграция OPEN: existing Pack bypass и concrete registrations |
| Ответственность классов | Предложена конкретная декомпозиция write path; полный ARCH-0 OPEN: read/protection/completion lifecycle и H2 cutover не закрыты этой таблицей |
| Public/internal boundary | Локальный TARGET, standalone guard и site mapping предложены после ревью; независимая повторная приёмка и concrete bindings OPEN |
| Неизменность порядка | prepare → stage сохранён; foreign consumer cutover/нормативная синхронизация через координатора OPEN |
| CRUD данных: create/read/update/delete | create: этот stage proposal; read: bounded verified read OPEN; update: content immutable, замена owning refs у consumer, публичный контракт OPEN; delete: guarded GC existing, публичный caller contract OPEN |
| CRUD настроек: create/read/update/delete | Fixed composition не доказывает отсутствие потребности в настройках. По всем четырём операциям applicable scope/публичный контракт не зафиксирован: OPEN, искусственные методы не добавляются |
| Foreign CRUD | Producer→DAG→Artifacts зафиксирован; authority/lifecycle/public completion требуют owning contracts, OPEN |
| POJO/error closure | Reuse ArtifactRef/lease/reservation и failure site mapping зафиксированы; TARGET wrappers требуют concrete C identity validation и полного field inventory, OPEN |
| Совместная приёмка | Требуется координатор и решение пользователя; отправка proposal не означает PASS |

**Вердикт: архитектурное предложение существенно конкретизировано; ARCH-STAGE и ARCH-0 ещё не приняты.** Следующая проверка — точная совместимость декомпозиции с H2 и устранение bypass Pack, не разрешение писать весь Artifacts. Ни одна ранее предоставленная гарантия не ослаблена ради локального среза.
