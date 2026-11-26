# Artifacts stage recovery — owning resolution SR-03/04/05

## Этап 1: синхронизация со штатным actual path — приоритетная редакция

2026-11-26. По поручению пользователя после сверки actual механизмов. PLAN-ONLY: этот раздел замыкает target caller trace для локальной приёмки, не объявляет реализацию или весь контракт принятым. Он имеет приоритет над нижними COMP/BF предложениями в отношении ЭТАПА 1. Выбранное пользователем направление — поэтапное расширение, а не одновременная замена backend/registry/local claims/cancel.

### Один штатный trace

1. Public authorized stage: existing pure admission/descriptor check, затем writer. Required permit+prepared остаётся публичной target дельтой; scope/claim не появляются в DAG Input.
2. Writer проверяет standalone/same composition и атомарно потребляет permit через IStageAttemptStore.claim_stage. Полный StageWriteClaim приобретён ДО reserve; выдаётся только после confirmed acquisition. При unknown нет backend dispatch и нет второго claim.
3. Existing catalog.reserve проверяет operation authority и приобретает hold. Full claim не заменяет этих predicates. Reservation сверяется с exact permit binding/ref.
4. Existing backend.write(reservation, content) выполняет свой existing LOCAL writer acquisition, worker IO, cancellation drain и temp cleanup, затем release LOCAL claim. Writer НЕ приобретает внешний local claim вокруг этого вызова: иначе existing no-active-writer check откажет. Content/descriptor/codec semantics сохраняются.
5. Full claim остаётся active в промежутке после backend.write. Writer приобретает existing второй LOCAL writer через admission.writer(reservation) для verify/seal. Нельзя считать отсутствие local claims в промежутке полным drain.
6. Под вторым local claim выполняется общий internal verification job и затем IStageAttemptStore.seal_stage(full_claim,reservation). Последний открывает один existing Publication UOW; проверяет exact stage authority/current operation, live local reservation writer/hold, вызывает единый catalog.seal_in_scope и записывает exact completion в ЭТОМ scope. Ref до confirmed commit provisional.
7. После confirmed commit выходит второй local context; full claim освобождается только после завершения всех вызванных workers/local cleanup. ARTIFACT_SEALED logging сохраняет existing policy и не отменяет completion. Post-commit cleanup/log fault не превращается в rollback/absence.

Это сохраняет два существующих local участка и добавляет непрерывный full lifetime. Полный lifetime не держит долгую SQL transaction на physical IO. Cleanup temp остаётся внутри backend.write ДО verify/seal. Статус success не усиливается до гарантии hold при доставке ответа.

### Конкретные классы и минимальные signatures этапа 1

| Класс/модуль | Target дельта и ответственность | Критерий отказа |
|---|---|---|
| ArtifactStageWriter, application.artifacts.staging.artifactStageWriter | Existing contract/registry/catalog/admission/log dependencies + required attempts: IStageAttemptStore; write(permit: StageAttemptPermit, prepared: PreparedArtifact[C]) -> ArtifactRef (async). Registry.resolve возвращает existing ArtifactBackend; existing write_admission graph checks сохраняются | Optional permit/fake authority; второй local acquire вокруг backend.write; выдача successor/recovery loop |
| IStageAttemptStore, application.artifacts.storage.stageAttemptStore | claim_stage(permit) -> AbstractAsyncContextManager[StageWriteClaim]; async seal_stage(claim, reservation) -> ArtifactRef. Durable initial authority/full claim/completion; собственный generation не заменяет operation fence | Unknown acquisition как отсутствие, release до backend drain, отдельный completion commit |
| ArtifactReservationVerifier, proposed application.artifacts.staging.artifactReservationVerifier | Constructor(registry: ArtifactFormatRegistryBinding, admission: IArtifactWriteAdmission); async verify(reservation: StagingReservation) -> None. Единственная existing последовательность assert_writable → registry.verify(ref) → assert_writable; local claim удерживается caller | Никаких acquisition/commit/публикации/recovery; не второй codec/descriptor algorithm |
| SqliteArtifactCatalog, db.repositories.sqlite.artifacts.catalogStore | async seal_in_scope(scope: CommitScope, reservation: StagingReservation) -> ArtifactRef; existing seal predicates/effects перенесены сюда ОДИН раз. Existing seal открывает existing transaction и делегирует; authorized seal_stage вызывает scoped primitive в своём UOW | Две копии predicates; nested bind/commit; provisional ref выдан как confirmed |
| ArtifactStagingService.seal, application.artifacts.staging.artifactStaging | Existing public signature/legacy consumer сохранены; свой local context → общий ArtifactReservationVerifier → existing catalog.seal. Existing ref/log проверки сохраняются | Вызов public authorized stage, synthetic permit или третья verify/seal реализация |
| ArtifactFormatRegistryBinding / ArtifactBackend / ContentAddressedBlobBackend | На этапе 1 register/resolve/verify/write contracts остаются existing. Обязателен real worker drain при cancellation до возврата/raise; full caller держит lifetime | Legacy method объявлен restart-safe или worker продолжает effects после завершения await |
| SqliteStageExecutionDrain + Publication lifecycle consumers | Existing согласованный scoped predicate: проверять full claims вместе с local; stateless adapter same access/registry; waiting cancel сохранён | True только по отсутствию local claims; global busy-return cutover |

ArtifactReservationVerifier — внутренний job, не pipeline/новая нода. Вложенные calls остаются внутри Artifacts; public фасады не вызывают друг друга. Последовательность verify+seal единая по primitives, transaction owner различается явно: legacy standalone против authorized seal+completion. Existing catalog predicate/ref validation не копируются в verifier.

Registry compatibility этапа 1 не требует AuthorizedFormatBinding/register_authorized/resolve_authorized: существующий backend остаётся явной зависимостью штатного writer. Это ограниченная live-execution гарантия, а НЕ opaque fallback в crash-safe path. Caller full claim покрывает весь awaited write/verify и existing backend drain; backend не интерпретирует stage generation и не обещает atomic physical fencing. Требование COMP-01/02 explicit claim на каждой physical границе остаётся у этапа 2 и не считается выполненным этим trace.

### Что отложено, а что обязательно

### Исправления локального review этапа 1 — durable authority / release / composition

Этот подраздел конкретизирует три замечания review; все storage additions остаются PROPOSED до общей приёмки. Не разрешает SQL/код и не добавляет второй coordinator/operation lifecycle. Прежнее «representation не предъявлено» заменяется следующей предлагаемой моделью этапа 1; физическое crash fencing остаётся OUT.

**1. Persistent facts — минимальная необходимая дельта.** Existing ArtifactLeaseEventRow содержит только operation/fence/admission; ArtifactWriterClaimRow — artifact/operation/fence; ArtifactStorageEventRow — storage seal без stage identity. Ни одна запись не позволяет отличить два logical stage одного ref. Добавлять stage completion в OperationRecord terminal неверно. Поэтому предлагаются отдельные нормализованные facts Artifacts, не generic event journal и не новая система holders. Reuse existing ScopedSqliteAccess/row mapper/transaction driver; операции выполняет один SqliteStageAttemptStore, drain читает те же facts.

Proposed frozen storage rows в `app.db.models.artifacts.stageAttemptRows` (не публичные DTO; перечисленные поля отражают storage shape, публичные lease/ref не зеркалируются новым API):

| Row / proposed table | Поля / constraints |
|---|---|
| StageBindingRow / artifact_stage_bindings | operation_id, stage_id (composite PK); world_uid, operation_kind, preparation_fingerprint, operation_fence; artifact_kind, format_key, format_version, content_hash, nbytes, row_count. Полный immutable binding, FK operation_id к existing operation |
| StageGenerationRow / artifact_stage_generations | operation_id, stage_id, generation (composite PK), predecessor_generation nullable; FK к binding; generation positive. В этапе 1 только generation=1, predecessor=NULL; successor issuance OUT |
| StageAcquisitionRow / artifact_stage_acquisitions | operation_id, stage_id, generation (PK/FK generation), claim_id (unique opaque existing runtime_uid value). Не больше одного consumption на generation |
| StageCompletionRow / artifact_stage_completions | operation_id, stage_id (PK/FK binding), generation, claim_id, artifact_id; FK exact acquired generation/claim и existing catalog. Не больше одного completion на logical stage |
| StageReleaseRow / artifact_stage_releases | operation_id, stage_id, generation (PK/FK acquisition), claim_id exact. Confirmed release значит live execution перестала иметь возможность dispatch и все запущенные работы drained |

Все facts insert-only, no deletion/update в этом срезе. Индексы/FK связывают composite identities, а не только отдельно существующие IDs; uniqueness completion не позволяет второй generation записать второй исход. Состав claim_id не public permit и не право, выводимое из строки. StageWriteClaim проверяется как issued handle текущего store/task/lifetime, correlated с persisted acquisition. Row decoding восстанавливает existing OperationLeaseRef/ArtifactRef через strict validation: malformed enum/hash/count/fence, orphan или несовпадающий operation/catalog binding → ArtifactStorageInvariantError/PublicationInfrastructureError до business refusal. Отсутствие acquisition при completion/release — corruption. Completion без release допустим; release без completion допустим после неуспешной попытки. Issued без acquired не active execution.

begin в одном UOW сверяет operation authority и immutable binding, вставляет binding+generation 1 либо возвращает exact current result. claim_stage в одном UOW проверяет binding/generation/open authority и вставляет acquisition; duplicate consumption → declared stage admission refusal, не второй writer. seal_stage в одном UOW сверяет live issued full handle, acquisition без release, current lease/local writer/hold, scoped seal и completion artifact_id; catalog descriptor должен совпадать с binding. Release не меняет completion. Ни один method не пишет отдельный evidence commit после seal. Drain predicate: acquired без matching release = active; malformed chains = fault; отсутствие acquisition у issued permit не препятствует READY. После process loss active остаётся active, не infer drain.

Partial creation: binding+initial generation atomic; acquisition отдельно подтверждён до dispatch; reservation/physical effects могут существовать независимо от completion. Unknown commit не хранится как ложный status absence: registry quarantine/error сохраняются, authoritative reread выполняется лишь после законного восстановления connection. Stage-1 public recover не выдаёт successors: exact completion → historical Confirmed; incomplete consumed → Unresolved согласно таблице без crash takeover. Generation/predecessor schema оставляет future relation явной, но этап 1 не реализует её переходы.

Эти пять facts — конкретное предложение persistence, не существующие tables. При реализации потребовалась бы отдельная явно разрешённая правка `0001_initial.sql` и sync row models; сейчас их нет и они не создаются. Разделение фактов обосновано insert-only policy и уникальностью отдельных commits; нельзя заменить их неограниченным JSON log, mutable generic status engine или таблицей holders. Критерии: corrupt/orphan/duplicate negatives, atomic begin/consumption/seal, two-connection uniqueness, same-scope rollback и unknown injection.

**2. Cancellation-safe полный context.** `claim_stage(permit)` остаётся async context manager. Concrete private methods SqliteStageAttemptStore: `_acquire(permit: StageAttemptPermit, claim_id: EntityUid) -> StageWriteClaim` (async), `_release_live(claim: StageWriteClaim) -> None` (async), `_drain_release(claim: StageWriteClaim) -> None` (async). Claim_id выделяется один раз до acquisition, exact replay не выделяет новый; callbacks/выдача handle не происходят до confirmed acquisition. Это owning methods, не public nodes/DTO.

State/lifetime внутри context: acquiring → issued → closing → released. Closing запрещает дальнейший dispatch через этот execution owner. Обычный stage последовательно awaits backend/local contexts; backend контракт гарантирует worker drain ДО возврата/raise. Поэтому normal exit и исключение обрабатываются после завершения этих await. Full release производится только после закрытия обоих возможных local contexts; ошибка local release/worker cleanup оставляет full acquisition unreleased, не теряется за generic finally. Seal completion при этом не отменяется.

Acquisition cancellation: commit store может подтвердить COMMIT и затем поднять CancelledError. Context, ещё не выдавший handle, сохраняет original claim_id и через scoped lookup проверяет exact acquisition. Confirmed absent (rollback) → ничего release; confirmed matching acquisition без выдачи handle → `_drain_release` (worker dispatch структурно ещё невозможен); mismatch → fault. Unknown/невозможность lookup → preserve uncertainty, не pretend release и не новая acquisition. Это отличается от process loss: в живом контексте контроль выдачи handle доказан порядком исполнения.

`_drain_release` запускает один защищённый cleanup task и ждёт его завершения через shield-loop по existing SqliteArtifactLeases._cleanup pattern; повторная CancelledError фиксируется, не прерывает ожидание release ACK и не создаёт второй cleanup task. После confirmed release повторно распространяется cancellation. Release проверяет exact acquisition/claim и отсутствие completion ambiguity влияющей на authority; insert matching release в коротком existing UOW. Already present matching release идемпотентен, foreign release corruption. Ошибка/unknown release не поглощается и не превращается в cancellation success: категория infrastructure/UnknownCommitOutcome сохраняется, исходное исключение сохраняется cause/context; store не объявляет drained. Ошибка stage без проблем cleanup распространяется неизменной. Проверка unknown completion не должна запрещать безопасное прекращение live работ, но не разрешает infer rollback/compensation.

Физический backend обязан завершать accepted worker effects до raise; если это не доказано для concrete binding, context НЕ вправе использовать один факт возврата coroutine как evidence. Для existing BLOB local `_io`/finally поведение проверяется tests; для generic backend такое свойство — обязательный binding admission criterion, не blanket PASS. Full context не создаёт scheduler и не занимается чужим worker loop.

**3. Точное подключение общего verifier.** Proposed ArtifactReservationVerifier(registry: ArtifactFormatRegistryBinding, admission: IArtifactWriteAdmission) хранит read-only registry/admission identity; `verify(reservation) -> None` async выполняет только existing assert/verify/assert. Catalog seal predicates остаются только catalog, codec вызывается только registry; verifier не логирует.

Target constructors (required keyword, no default/самосборки второго job):

    ArtifactStageWriter(contract, registry, catalog, admission, log, *, attempts: IStageAttemptStore, verifier: ArtifactReservationVerifier)
    ArtifactStagingService(registry, catalog, leases, holders, gc, ledger, log, *, verifier: ArtifactReservationVerifier)

Оба constructor проверяют verifier.registry is registry и verifier.admission is соответствующий admission/leases до IO. Один verifier instance допускается, но не обязателен: он stateless, важны dependency identities. Writer после второго local acquire вызывает verifier.verify ровно один раз, затем attempts.seal_stage; legacy service.seal внутри своего local acquire — verifier.verify ровно один раз, затем catalog.seal. Проверка возвращённого ref и existing logging остаются на своих границах, без второго emit внутри verifier. Public service methods не вызывают друг друга.

Actual constructor call inventory по `rg` backend: `tests/snapshotCore/storage/artifacts/test_staging.py` — fake lifecycle setup, restarted setup и SqliteBlobLifecycleTests setup; `tests/typing/snapshotCore/valid.py::sqlite_composition`. Все получают verifier из своих registry/admission, включая restarted graph; fake job, скрывающий verify, не заменяет integration tests. Production ArtifactStageWriter/ArtifactStagingService constructor calls в проверенном backend/app не найдены; не назначать PacksWiring их factory по догадке. Новые stage-1 test composition обязаны собрать real attempts + verifier и общий access/scopes/drain graph. Перед implementation повторить call inventory из-за параллельных изменений.

Delivery порядок внутри этапа 1: принять эту storage/transition дельту → row/strict facts + transaction store/drain → cancellation-safe full context → единый scoped catalog seal → общий verifier и явные constructor callers → public authorized writer/pipeline → meaningful integration/typing tests. Каждый следующий слой после контракта и проверки предыдущего. Это внутренний порядок реализации, не изменение DAG процесса. Runtime acceptance по этим описаниям не выдана.

Нижние proposed AuthorizedArtifactBackend, StageLocalWriter, перенос local acquisition из backend, seal_stage(full,local,reservation), SETTLE mode, durable temp identity, cross-process physical fencing и busy-return cancel относятся к этапу 2 и НЕ являются условиями реализации этапа 1. Их ранние формулировки «заменяет» не заменяют приведённый здесь stage-1 контракт. Нельзя активировать второй этап простым использованием первого без новой приёмки.

Обязательны в этапе 1: durable facts и same-scope binding по review-коррекции выше; single-R/composition checks; correct typed Error; unchanged generic identity; full/local lifecycle guards; concrete live worker-drain evidence. Persistence representation теперь предъявлена как proposal и требует приёмки до code-go storage среза; callback/in-memory registry её не заменяет. Выбор production crash-recovery binding НЕ blanket blocker этих внутренних контрактов.

Publication cancel сохраняет close → wait local+full вне write UOW → final recheck → release/terminal. READY проверяет local+full в своей transaction без ожидания под lock. Close до seal → refusal без completion; seal до close → historical completion, затем cancel ждёт release. После process loss могут остаться бессрочные unresolved claims/holds; никакого auto retry/release/fence takeover. Принятый этап 1 не обещает успешное завершение отмены после crash.

### Проверки локальной приёмки

- Задержать исполнение между backend-local release и second-local acquire: cancel/READY не проходят full guard, GC сохраняет protection.
- Cancel во время worker, repeated task cancellation: backend завершает worker/cleanup до возврата, full release позже; existing waiting tests сохраняются.
- Confirmed acquisition и потеря ACK/cancellation: не второй dispatch; unknown release не считается drained.
- Fault между scoped seal и completion: один rollback; reservation/physical effects не объявляются отсутствующими. Lost ACK commit: UnknownCommitOutcome, без компенсации.
- Foreign scope/operation/admission/registry rejected; standalone entry не заимствует ambient transaction, внутренний seal UOW допускается только owning store.
- Legacy ArtifactStagingService и authorized writer используют один verification job/одни catalog predicates; при migration нет удвоения codec/verify вызовов, событий или commits.
- Full Error/identity regressions сохраняются; никакого изменения Engine/nodes/foreign public contracts из этого среза.

Итог синхронизации: stage-1 caller trace предъявлен для review; proposed persistent authority и реализация ещё не приняты. COMP/BF crash-recovery OPEN не перенесены на штатную запись. Код и foreign планы этим разделом не меняются.

## COMP-01/02/03/05 — concrete composition correction (PROPOSED)

2026-11-26. Приоритет над несовместимыми ранними sibling-port/cleanup формулировками ниже. Только документация; missing production binding НЕ мешает предъявить generic composition delta. Physical file fencing по-прежнему не доказан. COMP-04 принадлежит Publication, новый cancel waiting contract не принят этим пакетом.

### COMP-01 — registry и authorized path

Existing evidence: application/artifacts/registry/artifactRegistry.py::register требует isinstance(backend, ArtifactBackend), backend.contract is contract, уникальный key; resolve возвращает ArtifactBackend[C]; verify(ref) вызывает backend.verify(ref). ArtifactStageWriter.__init__ проверяет backend.write_admission is admission. Sibling ABC из BF-02 этому не соответствует.

Коррекция: proposed `AuthorizedArtifactBackend[C](ArtifactBackend[C])` в contracts/authorizedBackend.py — capability subclass с НОВЫМИ различимыми методами, не несовместимым override:

    @property stage_authority -> IStageAttemptStore
    async write_authorized(claim: StageWriteClaim, reservation: StagingReservation, content: C) -> None
    async verify_authorized(claim: StageWriteClaim, reservation: StagingReservation) -> None
    async cleanup_authorized(claim: StageWriteClaim, reservation: StagingReservation) -> None

Старые write/verify/delete/contract/write_admission остаются отдельным existing API; никакого optional claim, вызова legacy write из authorized метода или inferred authority по ref. Concrete subclass обязан явно реализовать обе поверхности либо не объявлять поддержку legacy writer; consumer cutover должен устранить такой вызов до активации. Существующий unclaimed verify для read/legacy не используется authorized stage.

Proposed immutable internal `AuthorizedFormatBinding[C]` в registry/artifactRegistry.py: contract: ArtifactFormatContract[C]; backend: AuthorizedArtifactBackend[C]. Это runtime DI pair, не domain DTO/новый format key и не durable authority. Новые методы ТОГО ЖЕ registry:

    register_authorized(contract: ArtifactFormatContract[C], backend: AuthorizedArtifactBackend[C]) -> AuthorizedFormatBinding[C]
    resolve_authorized(binding: AuthorizedFormatBinding[C]) -> AuthorizedArtifactBackend[C]

register_authorized выполняет одну existing register (тот же key, одна запись) и возвращает typed binding. resolve_authorized проверяет identity обеих ссылок с единственной existing _bindings записью и возвращает binding.backend, без cast или type-erased value в caller. Самодельный binding не обход: обе identity сверяются с registered objects, unregistered/mismatch → fail-fast TypeError/ValueError до IO, как existing composition. Existing внутренний cast legacy resolve этим предложением не расширяется; новых casts не нужно.

Target ArtifactStageWriter constructor `(binding: AuthorizedFormatBinding[C], registry: ArtifactFormatRegistryBinding, catalog: IArtifactCatalog, attempts: IStageAttemptStore, admission: IArtifactWriteAdmission, log: ArtifactLifecycleLog)`. Он использует resolve_authorized(binding), проверяет backend.stage_authority is attempts (runtime authority owner) и existing backend.write_admission is admission/catalog graph. Это не требование singleton для stateless drain. DescriptorBuilder/codec reuse existing contract+registry encode; stage verify идёт непосредственно в resolved backend.verify_authorized(claim,reservation), НЕ registry.verify(ref). Registry.validate(ref) сохраняется.

Migration: factories выбранного format переходят на register_authorized ВМЕСТО register, не рядом; authorized writer получает returned binding. Legacy TypedArtifactStager и ArtifactStagingService verify используют existing API до отдельного cutover; новый route не вызывает их. Read/GC consumers прежних verify/delete не получают фиктивный claim. Concrete factories сейчас PacksWiring register_manifest/climate/grade — кандидаты migration только если их binding выбран. Проверки: duplicate key rejected; forged/mismatched DI pair rejected; вызовы authorized stage никогда не попадают в legacy verify/write; same content/descriptor/authority identity. OPEN: concrete capability subclass и его physical guard, не generic registry wiring.

### COMP-02 — existing local claim и closed settlement

Existing leaseStore.py::writer требует writable lease, exact reservation+hold и отсутствие active writer; выдаёт None, держит ArtifactWriterClaimRow локально и _cleanup освобождает его. _release не требует writable, но принимает только известный acquired row, не получает stage generation. Следовательно новый обычный writer acquire при closed/stale settle недопустим.

Минимальная target boundary в storage.stageAttemptStore, реализуется concrete SqliteStageAttemptStore:

    local_writer(claim: StageWriteClaim, reservation: StagingReservation) -> AbstractAsyncContextManager[StageLocalWriter]
    async release_local_in_scope(scope: CommitScope, claim: StageWriteClaim, local: StageLocalWriter) -> None

StageLocalWriter — internal issued runtime handle exact existing ArtifactWriterClaimRow, read-only reservation/full-claim correlation; не wire DTO/новая generation. local_writer разрешён только WRITE full claim и open authority. Acquisition existing local row и durable association exact stage/generation→row выполняются в ОДНОМ UOW; handle выдаётся после confirmed commit. Повторный local acquire backend-ом запрещён. Existing row shape/release chain reuse; representation association — минимально необходимая owning persistence дельта, exact schema OPEN, новый журнал этим не назначается.

Settlement восстанавливает association из authoritative facts и завершает ТУ ЖЕ local claim через scoped release после доказанного physical drain, без writer(reservation), нового acquire или reopen. SETTLE capability проверяет original binding/generation, ownership row и settlement exclusion; current operation fence может отличаться, но нельзя release чужую/новую row. Already released exact row идемпотентно подтверждается по цепочке; missing association при active row → invariant fault/неподтверждённый drain, не wildcard release. Normal exit и settle используют одну scoped release проверку; конкуренция завершается одной release записью, без allow_rollback как общего разрешения. Unknown association/release → unknown, повтор не создаёт второй local claim.

Проверки: closed/stale settle не вызывает ordinary writer; unrelated active claim остаётся; duplicate settle/normal exit не дают double release; unknown acquire/release не объявляют drained. OPEN: storage representation exact association и backend proof; не невозможность reuse local release.

### COMP-03 — file resource identity и cleanup порядок

Existing blobBackend.py::write хранит temps только в local list, _temp использует random mkstemp prefix hash(operation_id,fence), _place размещает final, finally unlink происходит ДО возврата write и до later verify/seal writer. После crash этот список теряется; prefix не различает stage/generation, и поиск/удаление всех matching temp запрещены. Новый after-seal cleanup не может молча заменить этот actual порядок.

Target для file capability, если выбран: сохранить порядок write_authorized(temp/create/place → cleanup exact temp → return) → verify_authorized → scoped seal. cleanup_authorized используется как общий идемпотентный primitive из write-finally и settle; post-seal вызов нужен только для реально оставшихся ресурсов, не переносит temp deletion после seal. Исключение cleanup до seal не подтверждает успех; after-seal failure сохраняет durable completion и pending drain.

Минимальная необходимая resource дельта: exact execution-owned temp identity должна быть определена и durable связана со stage/generation ДО возможного создания файла. Random mkstemp с регистрацией после создания оставляет leak window. Предлагаемый file-specific internal `StageTempResource` (storage/artifacts/stageTempResource.py): reservation identity + generation + ordinal + opaque relative_name, выдаётся только owning resource preparation; не public artifact/ref/holder. Relative name/ordinal сохраняются до create, create-exclusive и containment обязательны; final content-addressed path shared, НЕ execution-owned cleanup resource. Конкретный naming encoding/representation не назначается до выбранного binding; автоматический backend registration отсутствует.

Даже durable temp identity НЕ решает cleanup fencing: old WRITE cleanup, old SETTLE cleanup и новый settle должны атомарно исключаться в МЕСТЕ unlink/rename, а не только проверять SQL до вызова. Exact resource identity решает «что», effect guard решает «кто ещё может менять». Existing backend такого OS guard не имеет. Поэтому нельзя честно объявить COMP-03 закрытым без physical mechanism; новый Python mutex/SQL flag недостаточен. Проверки: crash до create/после create до записи/после placement; одновременный old finally и settle; shared final никогда не удаляется; отсутствие temp не заменяет drain принятого worker. No broad scans, no new purge.

### COMP-05 — full/local/seal/completion порядок

Existing catalogStore.py::seal проверяет live local writer для reservation, writable lease и hold; собственная SqliteArtifactScope.transaction даёт standalone commit. Если backend освобождает свой local guard и следующий verify/seal не приобретает новый — seal откажет; второй standalone commit evidence запрещён.

Authorized target последовательность: full WRITE claim → reserve → один local_writer(full,reservation) → backend.write_authorized (включая temp cleanup) → backend.verify_authorized → seal_stage(full,local,reservation) → local release → full release после remaining workers. Backend больше не приобретает local writer самостоятельно; full/local owner — writer/attempt store, backend лишь пользуется выданной authority. Внутренний proposed signature уточняется до `async IStageAttemptStore.seal_stage(claim: StageWriteClaim, local: StageLocalWriter, reservation: StagingReservation) -> ArtifactRef`, заменяет ранний двухаргументный proposal для authorized path.

seal_stage открывает один existing commits.transaction(operation_id), проверяет exact full generation/claim + exact linked live local row + reservation/hold + current operation authority, вызывает `SqliteArtifactCatalog.seal_in_scope(scope,reservation)` (provisional), записывает exact completion в этом же scope. Возврат ref только после confirmed commit. Local/full claims остаются live во время commit; release после commit не является вторым commit completion и не отменяет completion. Exception/unknown ведёт к drain/cleanup под теми же claims без ложного rollback; unknown release остаётся pending. Никакого await standalone seal внутри UOW.

При closed settle seal не вызывается, completion не создаётся; после historical Confirmed завершаются только residual effects и linked local/full releases. Publication проверяет совместимость exact guard порядка и cancel; её public services не вызываются writer-ом. Тесты: остановка между write и verify — обе claims удерживаются; fault между scoped seal и completion — общий rollback; lost ACK commit — exact evidence; cancel не освобождает holds до обеих release; foreign local handle отвергается. OPEN: actual scoped implementation/persistence и Publication сверка; statement о необходимости live local guard теперь замкнут в proposed caller trace.

Итог COMP: 01 generic binding/resolve path уточнён; 02 scoped exact local release предложен; 03 resource identity delta и physical exclusion gap разделены; 05 signature/order уточнены. Это не общий PASS и не production выбор. Earlier sibling write/verify names и backend-owned local acquire на authorized path WITHDRAWN в пользу этого раздела. Остальные existing legacy paths неизменны до явного consumer cutover.

## Actual backend audit для совместной приёмки — 2026-11-26

PLAN-ONLY. Проверены runtime declarations/callers в backend/app, а не только fixtures. Ни один найденный binding не объявляется выбранным для authorized recovery. pack-staging-completion-cutover.md прямо оставляет manifest specialization candidate; backend-fencing.md также не назначает production binding. Ниже existing и необходимая дельта разделены. Все пути в таблицах относительно backend/.

### Реальные кандидаты и единственный недостающий выбор

| Кандидат C / key / storage version | Actual backend, ресурсы и callers | Статус выбора |
|---|---|---|
| bytes / world_pack.manifest.json / 1 | app/storage/artifacts/manifestBlobBackend.py::ManifestBlobBackend(root, leases, max_bytes); inherits ContentAddressedBlobBackend. PacksWiring.initialize_pack_storage → register_manifest_format; root = database parent/artifacts. app/application/worldData/pack/encoding/preparedManifest.py::finish_pack_preparation вызывает TypedArtifactStager.stage, затем finish_preparation | Реальный production wiring/legacy caller, но новый route candidate, не accepted specialization |
| bytes / world_pack.climate_field.zstd / 1 | app/application/worldData/pack/encoding/climateFieldFormat.py::CLIMATE_FIELD_FORMAT; PacksWiring.initialize_pack_storage → register_climate_field_format → ContentAddressedBlobBackend(root, contract, leases); тот же disk root/worker механизм | Реальная registration; не доказательство выбора recovery route |
| bytes / world_pack.grade_slots.json / 1 | gradeSlotsFormat.py::grade_slots_format(limits); PacksWiring.register_grade_slots_format → ContentAddressedBlobBackend. В проверенном app вызов этой factory не найден | Реальная factory, activation не подтверждена |
| bytes / hydrology.open_water.root.tlv и hydrology.open_water.shard.tlv / 1 | generators/hydrology/encoding/packFormats.py::ROOT_FORMAT/SHARD_FORMAT; keys в dataModel/hydrology/pack/profile.py; Pack OpenWaterBlobReader — reader caller | Форматы/reader реальны, concrete production writer registration в проверенном app не найдена |
| SQL_ROWS | В проверенном backend/app нет concrete ArtifactBackend subclass для SQL_ROWS; test.rows — fixture, не production binding | Нет основания назначать вариант SQL ради удобства |

Нужен ровно один выбор для продолжения concrete BF-03: **какой реально необходимый production format/backend binding из маршрута является первым предметом crash-recovery приёмки**. Если это иной SQL_ROWS/backend — требуется ссылка на его concrete writer/composition, а не имя теста. Найденные BLOB candidates не выбираются автоматически и не отменяют прежний запрет BLOB-first. Поля C/key/version/class/resources для двух зарегистрированных кандидатов уже предъявлены; повторно спрашивать их вместо выбора не требуется.

### Карта всех effects найденного файлового backend

Строки F1–F8 совместно покрывают полный write/verify/cleanup путь ОБОИХ зарегистрированных candidates и grade-slots factory. Manifest override меняет только read budget; физическая реализация общая app/storage/artifacts/blobBackend.py. Кодеки manifest/climate/grade выполняют pure semantic decode/validation; их перенос — отдельный consumer contract, не physical fencing.

| Backend/effect / actual method | Existing защита | Минимальная недостающая дельта | Применимый вариант |
|---|---|---|---|
| F1 namespace mkdir; _temp: final.parent.mkdir(parents=True) | Path containment, symlink/junction rejection через _contained; предварительный lease check | Effect-time fencing и учёт namespace creation; SQL check до mkdir не атомарен | 2, не реализован |
| F2 _temp: mkstemp, write/flush/fsync, _verify temp | Random temp; prefix hash(operation_id,fence); local reservation writer; hash/size verification | Exact execution/generation ownership temp, fencing создания/записи, durable disposition после crash; prefix не различает stage/generation | 2, не реализован |
| F3 _sync_directory(root.parent/root), _verify directory fsync (POSIX) | Durability sync; на Windows _sync_directory no-op | Включить sync в завершение accepted effects; отсутствие async task не подтверждает окончания IO | 2 |
| F4 _place: Windows MoveFileExW WRITE_THROUGH/no replace либо POSIX os.link | No overwrite; повторный writable check до dispatch; final hash/size verify | Нужна общая с authority atomic physical fencing граница; повторный SQL check и content addressing этого не обеспечивают | 2 |
| F5 _verify final/temp; public verify → _io | Чтение chunks; Windows r+b; file fsync и directory sync, containment | Explicit claim и worker completion; verify не pure/read-only по effects, не выпадать из drain | 2 |
| F6 _temp exception и write finally: unlink(missing_ok=True) | Cleanup известного local Path; normal finally после awaited _io | Cleanup exact execution-owned path после restart; исключение старого/второго cleanup worker; нельзя удалять по broad prefix | 2 |
| F7 _io: run_in_executor(copy_context().run,...), shield/join при cancellation | Local cancellation ждёт завершения executor future; exceptions извлекаются | Не даёт cross-process exclusion/restart proof; copied context не передаёт валидный live SQL scope/task authority | 2 |
| F8 backend.delete: unlink final + directory fsync | Caller GC/holder/writer guard обязан быть удержан | OUT settlement: нельзя использовать как cleanup опубликованных shared blobs. Сохранить existing GC discipline, не расширять purge | Не часть нового settle |
| SQL reserve/hold/local claims: catalogStore.py::reserve, leaseStore.py::writer/_cleanup | Existing transaction/lease/fence и reservation guard | Связать с full generation, не выводить authority из ref; local guard subordinate | 1 для SQL facts, не всего BLOB |
| SQL seal: catalogStore.py::seal | Existing local writer/hold predicates, own transaction | scoped seal + exact completion в одном UOW; independent standalone commit forbidden | 1 для SQL facts, не F1–F7 |

Actual ContentAddressedBlobBackend constructor `(root: Path, contract: ArtifactFormatContract[bytes], leases: IArtifactLeases)` не принимает StageWriteClaim/effect guard; ManifestBlobBackend `(root, leases, *, max_bytes)` также не принимает. Рабочие методы write/verify и cleanup therefore НЕ соответствуют proposed authorized port. Это конкретный API gap, не готовый constructor, который можно включить без physical design.

### Что именно можно reuse из SQLite

app/db/repositories/sqlite/shared/transactions/transactionDriver.py::SqliteTransactionDriver.begin использует BEGIN IMMEDIATE для write, BEGIN для read. _acknowledge сохраняет UOW owner и ждёт aiosqlite worker ACK при cancellation; commit/rollback failure не доказывает rollback. snapshotCore/commitScope.py::SqlitePublicationCommitStore._transaction запрещает ambient/nested transaction, берёт GuardedConnection.unit_of_work, выдаёт registry scope и отзывает его в finally; uncertain commit/rollback → quarantine + UnknownCommitOutcome. shared/access/scopedAccess.py::ScopedSqliteAccess проверяет scope через registry до row IO. Reuse этих механизмов предпочтителен, второй coordinator не нужен.

Условная SQL-only реализация (не найденный production binding): каждая backend mutation и проверка generation должны выполняться в одном BEGIN IMMEDIATE UOW над тем же authoritative database. Fencing transition конкурирует с этими transactions; confirmed COMMIT запрета — linearization, ранее захвативший write lock effect уже commit/rollback, следующий writer читает запрет и отказывает. Только если ВСЕ effects, включая cleanup, удовлетворяют этому условию, применим вариант 1. Statements/таблицы generation пока не существуют в принятом binding — их нельзя написать фиктивно вместо evidence. Для F1–F7 BEGIN IMMEDIATE удерживает SQLite writer lock, но не предотвращает OS эффект другого worker и не откатывает file effects.

### Уточнение BF-01/02: normal exit, settlement и cleanup конкуренция

Существующий ниже proposal public StageAttemptService.settle(StageSettleInput) → StageSettleResult и internal IStageAttemptStore.settle сохраняется без повторного проектирования. Publication busy-cancel proposal НЕ принят: automatic close → settle → drain/release требует отдельного согласования, settle не вызывается из Publication service/adapter. Historical Confirmed/closed/stale fence не разрешают новые data writes, но settlement exact старой execution не должен early-return до residual cleanup/drain.

Обязательная concrete дельта для выбранного backend: normal-exit cleanup и concurrent settle должны конкурировать на ОДНОЙ authority завершения exact generation. Issued SETTLE handle не даёт общего права unlink: каждое cleanup действие проверяет exclusivity/ownership в той же effect boundary; старый WRITE/SETTLE worker после fencing не должен продолжать cleanup. Если старый cleanup уже принят, новый settlement ждёт его завершения/подтверждённой отмены; SQL флаг сам по себе не разрешает второй physical cleanup. При unknown cleanup/release повтор читает durable evidence и проверяет physical disposition, не объявляет drained из missing temp. Concrete реализация этой границы для file candidates пока отсутствует; добавление mutex только в Python-процессе не закрывает crash fencing.

BF-02 proposed write/verify/cleanup(claim,...) остаются explicit typed port. Full claim выдаёт/освобождает только owning StageAttemptStore/StageWriteClaim context. Backend получает и освобождает existing local reservation writer как subordinate guard вокруг своего участка; он не выдаёт generation и не вызывает recover. Full claim не снимается между write и verify/seal/cleanup; local guard не заменяет его. В target file adapter worker не вызывает непрозрачный legacy write: каждый F1–F7 должен быть подключён к concrete effect guard. Constructor такого guard нельзя назначить до решения о выбранном backend и physical mechanism.

### BF-03: проверяемая transaction карта и предел доказательства

Сохраняются точки нижеследующего BF-03 proposal: acquire → effects → fencing → settlement/drain → successor. Для SQL facts reuse UOW/ACK/quarantine доказан чтением actual кода. Для file effects durable prohibition старого WRITE И старого SETTLE worker не предъявлен, поэтому никакая транзакционная таблица этой записки не закрывает физический слой.

Необходимые crash probes после выбора binding: acquisition commit до ACK (не выдавать второй claim); partial file/SQL commits до seal (не объявлять отсутствие эффекта); fence commit до drain (resume exact settlement без re-open); cleanup commit до release ACK (не второй unguarded cleanup); drain commit до issuance (recheck operation, не bump дважды); issuance commit до ACK (exact predecessor replay); seal commit до cleanup (Confirmed отдельно от drained). Unknown на каждом шаге не компенсируется re-open/unconsume/release. Concurrent normal exit/settle/recover должны сходиться к одному durable completion/drain и максимум одному successor. Пока concrete physical marker/lock и restart-путь отсутствуют, отсутствие зависания не обещается: Unresolved/hold могут сохраняться бессрочно.

### Рекомендация и результат для решения

Вариант 1 рекомендуется ТОЛЬКО для реально необходимого SQL-only binding, которого в проверенном production app не найдено. Для manifest/climate/grade на existing file backend требуется вариант 2 — адресная physical дельта; её нельзя назвать минимально реализуемой, пока не выбран binding и не предъявлен effect-time fencing mechanism. Не менять storage формат ради удобства fencing. Следующий конкретный вход — выбор production binding из первой таблицы либо ссылка на иной actual writer. Без него остаются BF-02 concrete constructor/guard и BF-03 physical serialization; generic API proposal не выдаётся за решение.

Ownership/nested calls: DAG → public begin/stage/recover/settle; внутри Artifacts → owning store/backend primitives; scoped Publication infrastructure только transaction/operation authority, без foreign public service. Read-only drain не запускает cleanup. Writer не выбирает recovery branch; settle не выдаёт successor; маршрутом управляет DAG. Новые ноды/порядок не назначены. Изменён только этот документ; production registration, код, SQL, общий framework/GC OUT. Итог для совместной приёмки: actual audit предъявлен, полный PASS цепочки НЕ выдан.

## Дополнение BF-01/02/03 — предложение crash-recovery этапа

Прочитан artifacts-stage-recovery-backend-fencing.md §8. Нижеследующие additions — PROPOSED, не code-go и не доказательство concrete backend. Они не блокируют отдельно принимаемый штатный stage. Production format/backend binding по-прежнему не назначен; BF-03 не закрывается абстрактной схемой транзакций.

### BF-01. Завершение execution отдельно от replay/выдачи successor

Предложение public `StageAttemptService.settle(request: StageSettleInput) -> StageSettleResult` (async, тот же application.artifacts.staging.stageAttemptService). Это отдельная owning операция, не вызов recover из cancel и не изменение ранних Refused/Confirmed в recover. Caller — только явный согласуемый DAG CALL; точный workflow close → settle → drain/release требует Publication/DAG приёмки. Нынешний blocking cancel сам такой CALL не запускает: интеграция отмены остаётся OPEN, новый вызов внутри adapter запрещён.

Типы в dataModel.artifacts.staging.stageAttempt, strict/frozen/extra-forbid/revalidate_instances=always:
- StageSettleInput(binding: StageBinding, generation: positive strict int).
- StageSettled(kind='settled', binding: StageBinding, generation: positive strict int): authoritative drain подтверждён для exact execution; НЕ утверждает успешный stage, сохранность hold или возможность retry.
- StageSettleUnresolved(kind='unresolved', binding: StageBinding, generation: positive strict int, code: StageSettleUnresolvedCode).
- StageSettleUnresolvedCode: STAGE_UNTRACKED, GENERATION_UNTRACKED, EFFECTS_NOT_QUIESCENT, INSUFFICIENT_EVIDENCE.
- StageSettleResult: discriminated union StageSettled | StageSettleUnresolved.

StageBindingRejected применяется к durable mismatch; malformed construction → ValidationError; corruption/unknown/cancellation распространяются без преобразования в Unresolved. Unresolved — подтверждённая недостаточность evidence, а не ошибка запроса к storage. Новый outcome не дублирует Confirmed: он утверждает прекращение effects, а не seal. Новых field paths не нужно: operands логические, existing binding reuse.

Internal `IStageAttemptStore.settle(request: StageSettleInput) -> StageSettleResult` (async), реализуется SqliteStageAttemptStore. Последовательность: проверить persisted integrity/exact binding/generation → закрыть допуск ТОЛЬКО этой execution к новым effects → установить границу завершения уже принятых effects → завершить допустимый backend cleanup → durable зафиксировать drain/release. Historical completion проверяется, но НЕ даёт early return без settlement. Cancel/READY/stale operation fence запрещают data write/successor, но не блокируют завершение ранее начатой execution. Для stale fence нельзя выдавать новое write право; cleanup разрешается только для точно принадлежащих execution ресурсов, без изменения published data/чужих holds. Operation terminal/fence не меняются. Повтор settle exact request идемпотентен; два settle сериализуются по одной execution authority; absent registration не создаёт stage.

Settle не выдаёт permit, не переоткрывает lease, не принимает решение о successor и не возвращает ArtifactRef. Recovery incomplete generation использует ТУ ЖЕ внутреннюю реализацию settlement, не вызывает public settle; лишь после успешного settlement оценивает partial effects и разрешение successor. Read-only SqliteStageExecutionDrain только читает сохранённый authoritative predicate, никогда не выполняет settle. Нормальный claim exit и crash settlement обязаны сохранять одинаковый predicate, второго stage owner нет.

### BF-02. Явный runtime claim в backend

Предлагаемый internal sibling port `app.application.artifacts.contracts.authorizedBackend.AuthorizedArtifactBackend[C]`, не замена legacy ArtifactBackend по умолчанию:

    async write(claim: StageWriteClaim, reservation: StagingReservation, content: C) -> None
    async verify(claim: StageWriteClaim, reservation: StagingReservation) -> None
    async cleanup(claim: StageWriteClaim, reservation: StagingReservation) -> None

Все три метода проверяют exact claim issuance/lifetime, binding/generation и reservation. Нельзя восстановить claim по ref, прочитать global context либо самостоятельно acquire полный stage claim. Claim — тот же internal StageWriteClaim, не копия permit и не public DTO. Writer передаёт один handle явно write → verify → seal_stage → cleanup/drain. Cleanup не удаляет опубликованный artifact; только execution-owned временные/частичные ресурсы по concrete backend contract. Completion сохраняется даже при последующем cleanup failure.

StageWriteClaim имеет internal read-only mode: WRITE либо SETTLE. WRITE выдаётся только confirmed consumption; SETTLE — owning settlement для той же generation после fencing, без нового permit/generation. SETTLE не даёт write/verify/seal полномочий, допускает только ограниченный cleanup и завершение работ. Это режим одного runtime capability, не второй lifecycle/token. Worker получает explicit immutable execution coordinates и доступ к backend-owned effect guard, но не live SQL scope/connection родительского task. Concrete guard должен атомарно валидировать координаты с effect; одних скопированных координат недостаточно.

Legacy backend-local writer допускается только как подчинённый reservation/storage guard внутри full claim, без собственной stage generation/issuance/recovery. Он сохраняет existing hold/GC predicates; его release не доказывает full drain. Authorized method не вызывает legacy write как непрозрачный fallback: сначала конкретный adapter должен предъявить явное подключение claim к КАЖДОМУ effect. Existing legacy consumers остаются на прежнем port до своего cutover, но не входят в restart-safe route. Binding/registry для authorized backend должен требовать этот port и same authority graph; structural наличие методов без concrete fencing evidence недостаточно.

Конкретный constructor physical adapter сейчас нельзя указать: нет выбранного production backend. Требуемые входы constructor — existing concrete content contract/storage dependencies плюс проверенный execution authority/effect guard из того же composition; точные классы и signatures предъявляются владельцем выбранного binding до его приёмки. Generic Protocol не считается готовым physical adapter. Этот пункт BF-02 остаётся OPEN в части concrete wiring/call-site cutover, хотя proposed typed передача claim определена.

### BF-03. Транзакционные точки и недостающий concrete input

Условная схема для backend, ВСЕ эффекты которого доказанно находятся в одной serialization области с authority. Это критерий будущего concrete binding, НЕ заявление о существующем SQLite/BLOB/SQL_ROWS:

1. Каждая effect transaction читает и проверяет exact live generation/claim/write admission под конфликтующим authority lock/CAS и меняет ресурс в той же transaction. Commit effect — его linearization. Проверка в предыдущем read scope недостаточна.
2. Fencing transaction конфликтует с каждой такой effect transaction: durable запрещает новые effects old execution. Её confirmed commit — linearization запрета. Принятые раньше transactions должны уже commit/rollback; последующие обязаны отказать. Если хотя бы worker/cleanup effect вне этой области, такого вывода нет и требуется отдельное доказательство.
3. После fencing owning settlement классифицирует committed partial effects, выполняет только разрешённую exact cleanup, затем фиксирует drain. Fencing и drained — разные факты. Для нескольких cleanup commits нужен конкретный идемпотентный resume marker/инвариант existing backend, не произвольный второй журнал. Crash после fence продолжает settlement exact generation, не выдаёт successor и не пытается вернуть old write admission.
4. После confirmed drain recovery повторно проверяет completion и current operation authority. Если completion есть — Confirmed; если closed — Refused без successor; иначе только при доказанной safe partial disposition один atomic transition retire old/register successor. Два recovery одной generation не создают два successor. Settle останавливается после drain независимо от результата этого решения.
5. Rollback fence оставляет old execution potentially active; rollback cleanup не отменяет прежние partial commits; rollback drain не доказывает release; rollback issuance не разрешает новую generation. Unknown на любой границе сохраняет неопределённость: reread exact durable transition плюс physical evidence перед продолжением. Нельзя компенсировать unknown re-open/unconsume/release или выдать новый номер «на всякий случай». Crash после issuance до ACK использует existing predecessor replay, не вторую issuance.

Конкретный вход, которого НЕ ХВАТАЕТ для BF-03: утверждённая строка production binding `(C, format_key/version, concrete backend class/module, storage resources, writer/worker implementation)` и карта effects с authority storage/lock/isolation, включая reserve/temp/placement/fsync/verify/cleanup. Для неё требуется назвать authoritative representation execution prohibition, конфликтующие transaction statements/locking и committed partial disposition. Existing общая SQLite operation transaction не доказывает fencing чужих physical effects. BLOB и test.rows не назначаются вместо этого входа. Без него нельзя честно указать concrete linearization primitive, constructor или restart progress guarantee; BF-03 остаётся OPEN, durable proof/новый журнал не изобретаются.

Дополнения inventory: StageAttemptService.settle — одна public owning операция без successor; StageSettleInput/results — только correlation/outcomes без IO; IStageAttemptStore.settle — durable settlement, без operation lifecycle; AuthorizedArtifactBackend — эффекты под explicit claim, не allocator; StageWriteClaim mode — проверяемое runtime право, не node DTO. Для каждого нарушение указанных ограничений означает отказ в приёмке. Ошибки backend сохраняют existing infrastructure/UnknownCommitOutcome/CancelledError; конкретный expected cleanup refusal нельзя изобрести до выбранного backend. Settle не ослабляет retain/no deletion policy.

Статусы: BF-01 public/internal предложение предъявлено, Publication cancel workflow и physical settlement остаются на общей сверке; BF-02 typed port предложен, concrete adapter/wiring OPEN; BF-03 concrete binding input отсутствует, automatic recovery не принят. Штатная запись и integration gates остаются раздельными. Основные планы/код этим дополнением не меняются.

2026-11-26. PROPOSED для общей приёмки; не code-go. Единственный изменяемый файл этого поручения. Основание: artifacts-stage-recovery-contract.md, реестр SR-03…05; AGENTS.md и обязательные критерии dag-generator-interface.mdc. Координатор 01a218a4-bfc5-7012-b18b-8ed986cc786d. Код после пользовательского отката не меняется. Этот документ не принимает API, регистрацию или полный домен.

## Приоритетное уточнение границ приёмки — решение пользователя

Три объёма принимаются отдельно; эта запись уточняет общие формулировки OPEN ниже, не меняет контракты и не разрешает код сама по себе.

| Этап | Условия и предел приёмки |
|---|---|
| Внутренняя штатная запись Artifacts | После локальной приёмки IO/Error, authority, полного live claim/drain, atomic seal/evidence и composition допускается независимая реализация. SR-03-BACKEND crash recovery и SR-04-CALLER не являются её blanket blockers. Runtime PASS заранее не выдан |
| Workflow integration | SR-04-CALLER остаётся gate: Engine проверяет existing CALL identity и durable binding до effects. Не блокирует внутреннюю реализацию Artifacts; не разрешает fake authority или потерю correlation внутри Artifacts |
| Automatic recovery после process loss | Отдельный этап SR-03-BACKEND. Нужен доказанный backend quiescence/fencing/drain контракт. До этого consumed incomplete attempt может оставаться Unresolved бессрочно, а holds/claims — удерживаться без ограниченного срока; cancel может не завершить drain. Ни timeout, ни process loss не разрешают retry/release |

Локальная приёмка штатной записи не означает готовность production restart или полного workflow. Известное ограничение отсутствия гарантии завершения восстановления сохраняется явно. По проверке Publication и решению координатора в рамках поручения пользователя «Правим» singleton drain не требуется: разные stateless экземпляры exact owning adapter допустимы при одном access/registry/coordinator и едином scoped predicate; остальные composition требования сохраняются.

## 1. Existing / target и граница

Existing ArtifactStageOpenPipeline.stage принимает ArtifactStageInput[C](lease, prepared); ArtifactStageWriter выполняет reserve/write/verify/seal. IArtifactCatalog.reserve/seal не предоставляют stage generation correlation. Existing OperationLedger.recover возвращает operation observation. Ни один из них не является stage recovery API. Named diagnostic bases уже присутствуют в текущем дереве, но это не evidence production регистрации.

Target A: Artifacts владеет stage binding/generation/admission/completion. Publication владеет operation binding/fence/phase/cancel/terminal. Использование общей transaction infrastructure не разрешает вызовы чужого public service. Новая durable корреляция нужна: existing lease/ref не различают отдельные stage и seal-before-lost-ACK. Физическая схема/новый журнал здесь НЕ назначены; storage-дизайн обязан сначала предъявить reuse existing persistence, либо отдельно обосновать минимальную добавку. Без durable correlation реализация отклоняется, in-memory substitute запрещён.

Прямые callers begin/recover/stage — только согласованный DAG. Каждый public метод исполняет одну owning операцию; begin/recover никогда не запускают stage. Выбор следующего CALL остаётся у DAG. Текущий согласуемый порядок prepare → begin → stage не меняется; восстановление — отдельный recover. Топология, NodeIds и Engine recovery механизм OUT.

## 2. SR-04: identity и persistence

Предложение: ключ stage — (lease.operation_id, stage_id), namespace stage_id локален одной operation, но НЕ одному fence. StageBinding неизменяем целиком, включая fence, world, kind, preparation_fingerprint и полный ArtifactRef. Повтор ключа с другим binding — BINDING_CONFLICT, без перезаписи. Одинаковый ref у разных stage допустим и не объединяет их evidence.

Issuer stage_id — caller логического stage, не stage/recover и не случайный uid при каждом retry. Он обязан выдать EntityUid один раз и durable сохранить вместе с binding ДО первого begin CALL. begin durable регистрирует binding/generation ДО возврата Allowed; эффекты stage до этого невозможны. Artifacts не создаёт новый stage_id при retry. Потерянный ответ begin восстанавливается exact повтором того же binding. Если caller потерял сам stage_id, искать «последний stage по ref» запрещено.

Это точная caller обязанность, но конкретный owning producer и его persistence API пока НЕ предъявлены: внешний gap SR-04-CALLER. Координатор должен сопоставить existing durable call identity с этим требованием либо вернуть отсутствие binding; Artifacts не проектирует Engine и не объявляет issuer реализованным. Генератор/gameplay не назначаются issuer по умолчанию.

### Owning сверка предложения CALL identity — 2026-11-26

Прочитан dag-stage-recovery-transition-resolution.md, секция SR-04-CALLER. Прежняя формулировка «producer не предъявлен» уточняется: Engine предъявил proposal public CallOrigin и parent issuer, но API/проводка ещё не приняты и не реализованы этим документом. Scoped PASS совместимости направления с Artifacts namespace/correlation при следующих точных условиях:

- `dag-stage-call:v1|` + пять length-prefixed компонентов (execution_id, parent_invocation_id, canonical decimal nonnegative parent_step, begin_call_key, begin_target.node_id) является однозначной tuple encoding при фиксированном порядке, длине в Unicode code points и decimal length без leading zeros. Компоненты сохраняются буквально, без Unicode normalization, trim или повторного escaping. Target — именно begin CALL, не stage/recover successor.
- Actual `app.dataModel.identity.uid.EntityUid` — StrictStr с min_length=1 и pattern `^\S(?:.*\S)?$`; max_length не задан. Artifacts не требует UUID, UidKind.STAGE или собственной фиксированной ширины. Полный результат обязан пройти existing EntityUid validation: prefix не делает произвольный component допустимым (в частности, перенос строки внутри может нарушить regex). Невалидный result отвергается до begin, не исправляется hash/alias/обрезанием. Concrete Engine component restrictions и такие negative cases проверяет caller.
- Числовой max length в этой сверке не вводится. Размер равен длине prefix плюс сумме `digits(len(component)) + 1 + len(component)`; storage обязан сохранять exact строку без truncation/case-folding. Stage persistence пока proposal, поэтому compatibility с конкретной будущей колонкой/индексом не объявляется runtime PASS. Если выбранный storage имеет меньший bound, он должен быть предъявлен и согласован до registration, а не скрыт новым allocator.
- Корреляционный ключ Artifacts остаётся `(lease.operation_id, stage_id)`. Operation/world/artifact не обязаны кодироваться в stage_id: authority и связь обеспечиваются immutable полным StageBinding, проверенным existing operation lease и durable exact comparison. Тот же ключ с иными world/kind/fingerprint/fence/ref отвергается как binding conflict; наличие CALL-looking строки не даёт authority. Один stage_id в другой operation попадает в другой namespace; это не replay исходного stage.
- Первый binding сохраняется в begin child/parent continuation до effects, как предлагает Engine; после begin он переносится буквально через stage/recover/successor. Новый CALL address не используется для пересчёта existing stage_id. Replan с новым begin address — новый logical stage, а не продолжение прежнего permit; общее решение о разрешении такого маршрута остаётся у DAG, не у Artifacts.

Итог: namespace и отсутствие собственного max-length совместимы на уровне EntityUid/public proposal; новый allocator не нужен. SR-04-CALLER остаётся integration OPEN до принятия CallOrigin/signatures и доказательства checkpoint-before-effects/exact replay. Этот gap не блокирует внутреннюю штатную запись после её локальной приёмки. Новых Engine API этим owning заключением не принимается.

generation: strict int >=1, относится только к stage. Начальная 1; successor ровно previous+1. Operation fence и Engine attempt не заменяют generation. Для каждой retired generation сохраняется однозначная ссылка на выданного successor; exact recover потерянного ответа не выдаёт ещё одну generation.

## 3. SR-05: POJO, ошибки и публичные signatures

Все новые типы ниже PROPOSED, владелец Artifacts. Модуль `app.dataModel.artifacts.staging.stageAttempt`: strict/frozen/extra-forbid records, positive strict generation, explicit discriminators. Не создаются копии в Publication.

| Тип | Поля / invariant |
|---|---|
| StageBinding | stage_id: EntityUid; lease: OperationLeaseRef; artifact: ArtifactRef |
| StageBeginInput | binding: StageBinding |
| StageRecoveryInput | binding: StageBinding; generation: positive int — восстанавливаемая попытка |
| StageAttemptPermit | binding: StageBinding; generation: positive int; структурный POJO НЕ authority |
| StageAttemptAllowed | kind: Literal['allowed']; permit: StageAttemptPermit |
| StageConfirmed | kind: Literal['confirmed']; binding: StageBinding; completed_generation: positive int |
| StageRecoveryRefused | kind: Literal['refused']; binding: StageBinding; code: StageRecoveryRefusalCode; cancelled: OperationCancelled | None |
| StageRecoveryUnresolved | kind: Literal['unresolved']; binding: StageBinding; code: StageRecoveryUnresolvedCode |
| StageBindingConflict | requested: StageBinding; registered: StageBinding; одинаковый ключ, разные bindings |
| ArtifactStageAdmissionFailure | permit: StageAttemptPermit; code: StageAdmissionCode |

StageAttemptResult = discriminated union Allowed/Confirmed/Refused/Unresolved. Confirmed — исторический seal данной generation, не current hold. cancelled непустой iff code=OPERATION_CANCELLED; operation_id совпадает с binding. StageBindingConflict — отдельная logic issue, не фиктивная ошибка поля.

Enums в том же модуле:
- StageRecoveryRefusalCode: OPERATION_CANCELLED, ADMISSION_CLOSED, STALE_OPERATION_FENCE, STALE_STAGE_ATTEMPT.
- StageRecoveryUnresolvedCode: STAGE_UNTRACKED, ATTEMPT_NOT_QUIESCENT, INSUFFICIENT_EVIDENCE.
- StageAdmissionCode: PERMIT_UNREGISTERED, GENERATION_STALE, GENERATION_ACTIVE, GENERATION_COMPLETED.

Existing ArtifactLeaseFailure используется для stage lease refusal; новые enums не заменяют его и не копируют persisted corruption в business refusal. Recovery refusal — результат решения об операции восстановления, stage admission failure — отказ потребления permit; разделение методов и carriers не позволяет смешать эти значения.

В `app.application.artifacts.staging.stageAttemptService` concrete public StageAttemptService:

    async begin(request: StageBeginInput) -> StageAttemptResult
    async recover(request: StageRecoveryInput) -> StageAttemptResult

Declared expected exception carrier в `app.application.artifacts.staging.stageAttemptErrors`: StageBindingRejected(error: StageBindingConflict). Malformed typed inputs отклоняются Pydantic construction validation; не изобретается JSON endpoint. Infrastructure, UnknownCommitOutcome и CancelledError распространяются, НЕ становятся Unresolved. Unresolved означает успешно установленную недостаточность доказательства.

В `app.dataModel.artifacts.staging.stageInput` предложены ArtifactAuthorizedStageInputBase(permit: StageAttemptPermit, prepared: PreparedArtifactBase) и ArtifactAuthorizedStageInput[C], наследующий base и сужающий prepared до PreparedArtifact[C] с existing instance-preserving validation. Existing generic inputs не изменяются молча.

Target public `ArtifactStageOpenPipeline.stage(request: ArtifactAuthorizedStageInput[C]) -> ArtifactRef`. Единственный окончательный target error roster — таблица ниже. Stage не возвращает Confirmed вместо ArtifactRef.

### Typed diagnostics

Reuse ArtifactInputIssue/ArtifactInputError, FieldPathError, CheckedPath, FieldRef и ValidatorAggregationHelper. Никаких ручных ModelIdentity/segments и mirror lease/ref POJO.

| Нарушение | Root / owners / path |
|---|---|
| Prepare content | existing ArtifactPrepareStageInputBase / content; без изменений |
| Stage content | ArtifactAuthorizedStageInputBase.prepared → PreparedArtifactBase.content |
| Stage format | ArtifactAuthorizedStageInputBase.prepared |
| Descriptor vs encoded content | ArtifactAuthorizedStageInputBase.prepared → PreparedArtifactBase.descriptor |
| permit.binding.artifact vs prepared.descriptor | proposed ArtifactStageBindingIssue: permit + descriptor: ArtifactRef; relation issue, не подмена field path |

ArtifactStageBindingIssue в stageAttempt.py сравнивает два operand одного запроса, а не request против durable registration (StageBindingConflict). Порядок независимой pure проверки: content, format, request binding relation; field issues собираются existing helper. Proposed ArtifactStageInputFailure(fields: ArtifactInputError | None, binding: ArtifactStageBindingIssue | None) требует хотя бы одно непустое поле. Codec descriptor check выполняется только после admission, использует тот же aggregate с fields. Зависимые вычисления после content failure не запускаются. StageInputBindingRejected WITHDRAWN; прямой ArtifactInputRejected на authorized stage WITHDRAWN. Prepare и не мигрированные legacy consumers сохраняют existing carrier.

| Публичная операция | Expected exception carrier / payload (окончательный target) |
|---|---|
| prepare_stage | existing ArtifactInputRejected / ArtifactInputError |
| begin, recover | StageBindingRejected / StageBindingConflict; остальные ожидаемые решения в StageAttemptResult |
| authorized stage: pure input/descriptor | ArtifactStageInputRejected / ArtifactStageInputFailure |
| authorized stage: durable binding | StageBindingRejected / StageBindingConflict |
| authorized stage: permit consumption | ArtifactStageAdmissionRejected / ArtifactStageAdmissionFailure |
| authorized stage: operation lease | existing ArtifactLeaseRefused / ArtifactLeaseFailure |

Новые carriers — stageAttemptErrors; payload — stageAttempt.py, кроме existing ArtifactInputError/ArtifactLeaseFailure. Для всех методов infrastructure/codec/storage corruption, UnknownCommitOutcome и CancelledError сохраняют категории/cause; это не expected result enum. Malformed construction input остаётся Pydantic ValidationError. Эта таблица отменяет промежуточные комбинации carriers, а не existing API вне миграции.

Schema bases и все referenced owners включаются в конкретный cold allowlist; IDs не назначаются этим документом. Python/JSON/canonical full Error round-trip должен сохранить root/owners/order. Новый root требует отдельного Fields/C0 согласования, старый scoped verdict не переносится автоматически.

Уточнение по artifacts-stage-recovery-fields-review.md: получен scoped PASS TARGET цепочкам roots и разделению field/relation, не full SR-05. Authorized base — sibling, НЕ наследник lease-содержащего ArtifactStageInputBase. Все новые logic DTO/aggregate и вложенные StageAttemptPermit/StageBinding: ConfigDict(strict=True, frozen=True, extra='forbid', revalidate_instances='always'). ArtifactStageBindingIssue допускается только при permit.binding.artifact != descriptor; равные operands отклоняются validator. StageBindingConflict требует одинакового ключа и неравных полных bindings. Aggregate требует хотя бы один непустой компонент; relation не дублируется field issue.

Admission сначала собирает content → format через ValidatorAggregationHelper с exact allowed issue classes, затем берёт snapshot(), проверяет доступную relation и только после этого поднимает один ArtifactStageInputRejected. Преждевременный raise_if_any запрещён. Invalid content не отменяет независимые format/relation, если descriptor/permit доступны и типизированы. Если malformed operand отсутствует/невалиден, зависимая проверка пропускается без выдуманных operands; доступные structural/field diagnostics сохраняются. Codec запускается только после успешного pure admission; его exception не превращается в mismatch. Требования Fields к forged model_copy negatives, full Python/JSON/canonical closure и identity остаются gates реализации, не runtime PASS.

## 4. SR-03: exact internal port proposal

`app.application.artifacts.storage.stageAttemptStore.IStageAttemptStore`:

    async begin(request: StageBeginInput) -> StageAttemptResult
    async recover(request: StageRecoveryInput) -> StageAttemptResult
    claim_stage(permit: StageAttemptPermit) -> AbstractAsyncContextManager[StageWriteClaim]
    async seal_stage(claim: StageWriteClaim, reservation: StagingReservation) -> ArtifactRef

begin/recover имеют тот же error contract что service; claim_stage — StageBindingRejected, ArtifactStageAdmissionRejected, ArtifactLeaseRefused плюс infrastructure/unknown/cancellation; seal_stage — те же категории, reservation/claim inconsistency является ArtifactStorageInvariantError. Storage port не public DAG API, service не вызывает другие public методы.

StageWriteClaim в том же internal модуле: read-only permit: StageAttemptPermit; context lifetime; concrete adapter владеет закрытым runtime ownership handle. Пользовательские scope/connection/claim не передаются через DAG и не создаются caller. Quiescence не представляется переносимым bool/proof DTO. recover обязан доказать её и атомарно исключить старые эффекты в рамках одной owning операции; публичный check_quiescence с последующим TOCTOU запрещён.

Full execution claim приобретается до reserve и охватывает write/verify/seal и drain workers. Физическое IO вне длинной SQL transaction. Выход по ошибке освобождает runtime claim только после drain, но НЕ восстанавливает consumed permit автоматически. Process loss не считается drain. Повторное использование consumed permit всегда отказ; решение о successor принимает recover.

seal_stage обязан атомарно проверить operation fence/admission, exact claim/generation/reservation, закрепить seal/hold и completion evidence. Commit confirmed → ref; rollback → нет completion этого commit, предшествующие physical effects возможны; unknown → UnknownCommitOutcome без компенсации/новой generation. Durable completion читается раньше текущего закрытия lease для exact replay Confirmed, но после проверки integrity и exact binding. Concurrent cancel после completion не меняет исторический результат.

## 5. Таблица begin/recover и гонок

Таблица применяется СТРОГО после следующих приоритетных проверок в coherent observation/transaction, а не сверху вниз независимо:
1. Persisted integrity всей доступной operation/stage/chain/evidence; corruption/orphans → fault. Затем exact immutable binding; конфликт → StageBindingRejected.
2. Historical completion: begin возвращает Confirmed; recover возвращает Confirmed только для completed generation или её доказанной predecessor chain. Произвольная future g не получает Confirmed. Cancel/READY/current fence не отменяют этот исторический исход. Retired/tombstone ветви в текущем контракте отсутствуют: deletion запрещён.
3. Если исторический исход запрос не разрешил: current operation authority. При stale operation fence → STALE_OPERATION_FENCE; при matching fence и cancel terminal → OPERATION_CANCELLED; затем READY/closed/другой terminal → ADMISSION_CLOSED. Отсутствующая operation при сохранённом stage — integrity fault, не разрешение повторного begin.
4. Только при current writable authority проверить generation membership/current/successor/consumption и применять строки Allowed/Unresolved ниже. Поэтому unconsumed permit НЕ получает Allowed после cancel/READY. Для отсутствующего stage recover → STAGE_UNTRACKED только после успешной authority проверки; отсутствие operation при отсутствии stage отображается в STAGE_UNTRACKED без регистрации, не в Allowed.
5. Выдача initial/successor и consumption linearize с operation close в общей write transaction; после возврата Allowed consumption повторяет authority проверку. Recovery старой g, successor которой consumed, возвращает ATTEMPT_NOT_QUIESCENT (либо INSUFFICIENT_EVIDENCE при доказанном drain), но НЕ новую generation. Для восстановления successor нужен explicit recover(successor.g).

| Состояние | begin(binding) | recover(binding, g) |
|---|---|---|
| Нет stage registration, operation writable | Durable register g=1 → Allowed | Unresolved(STAGE_UNTRACKED), не создаёт stage |
| Permit текущей g выдан, не consumed | Тот же Allowed | Для g тот же Allowed; не bump |
| g consumed, live writer или quiescence не доказана | Unresolved(ATTEMPT_NOT_QUIESCENT) | То же, без successor |
| g consumed, quiescent, partial effects безопасны, operation writable | Unresolved(INSUFFICIENT_EVIDENCE): begin не делает recovery | Atomic retire g/register g+1 → Allowed |
| g consumed, safety partial effects не доказана | Unresolved(INSUFFICIENT_EVIDENCE) | То же, без retry |
| Completion существует | Confirmed exact completed_generation | Confirmed, если g относится к завершённой попытке либо её записанной predecessor chain |
| Уже выдан successor g+1 после recover(g) | Allowed только если current permit ещё unconsumed; иначе unresolved/confirmed | Exact повтор recover(g) возвращает того же successor, если unconsumed; consumed → unresolved; completed → Confirmed; не выдаёт g+2 |
| g неизвестна, future либо не относится к durable chain | begin рассматривает current registration | Refused(STALE_STAGE_ATTEMPT), без effects |
| Operation cancel terminal, completion отсутствует | Refused(OPERATION_CANCELLED), reuse terminal | То же |
| READY/closed, completion отсутствует | Refused(ADMISSION_CLOSED) | То же |
| Lease fence устарел, completion отсутствует | Refused(STALE_OPERATION_FENCE) | То же |

Два одновременных begin linearize в один g=1. Два recover(g) linearize в один successor. Lost ACK begin/recover повторяет тот же request, не bump. Unknown commit сначала разрешается чтением authoritative durable state внутри owning операции; наличие Unresolved не скрывает exception незавершённого read/commit. Lost ACK seal разрешается только completion evidence. Если successor уже consumed, повтор старого recover не является новым recovery successor: нужен запрос с generation successor. Это обеспечивает bounded idempotency без implicit retry.

Условный Allowed может устареть из-за cancel/READY: claim_stage повторно атомарно проверяет authority до effects. Если cancel опередил claim — refusal; если claim опередил cancel — drain охватывает ВСЕ effects. Точки ordering принимаются для сверки из Publication resolution, раздел «Порядок и совместимость lifecycle»: close admission до ожидания; оба drain predicates до release/terminal; READY проверяет full drain внутри commit без ожидания под SQL lock. Это согласование proposal, не runtime PASS.

## 6. Классы, зависимости, эффекты, критерии отказа

| Класс / модуль | Роль и зависимости; effects | Проверка / отказ |
|---|---|---|
| Все новые records/enums §3, dataModel.artifacts.staging.stageAttempt | Только operands/results/invariants; existing lease/ref/cancel | Никакого IO или lifecycle transition; reject inconsistent discriminator/binding/generation |
| Authorized input/base, dataModel.artifacts.staging.stageInput | Typed immutable input; PreparedArtifact/permit | Полная validation и same-instance; reject silent coercion или mandatory wrapper для старого API |
| Existing PreparedArtifact/Base, preparedArtifact.py | Content/descriptor; unchanged | Нельзя клонировать transport payload или переносить authority в descriptor |
| Existing ArtifactInputIssue/Error, inputErrors.py; Fields CheckedPath/FieldRef | Field diagnostics/path building | Reject ручные owners, новые mirrors, path внутри произвольного C |
| New logic issues/aggregate §3 | Relation operands плюс reuse field diagnostics | Reject потеря независимых issues или ложный field owner |
| Carriers stageAttemptErrors; existing stageErrors/lease refusal | Перенос owning errors, без logging/retry | Reject изменение исхода, duplicate logging |
| StageAttemptService, application.artifacts.staging.stageAttemptService | Один begin/recover → IStageAttemptStore, exact returned POJO | Нет stage вызова/маршрутизации/чужого public service |
| ArtifactInputAdmission, staging.artifactInputAdmission | Pure content/format/request-relation admission | Reject IO; collect stable independent errors до effects |
| ArtifactDescriptorBuilder, staging.artifactDescriptor | Existing encode/descriptor check; registry | Новый authorized schema-root передаётся через owning diagnostic binding, не DAG; reject hardcoded old root |
| ArtifactStageOpenPipeline, staging.artifactOpenPipeline | Admission → descriptor check → writer | Не выбирает recovery branch и не вызывает begin |
| ArtifactStageWriter, staging.artifactStageWriter | IStageAttemptStore, catalog, registry/backend, existing log; full claim IO | Reject standalone seal followed by evidence; post-seal fault не означает rollback |
| IStageAttemptStore / StageWriteClaim, storage.stageAttemptStore | Узкая durable authority boundary §4 | Не expose в public DTO; no fake authority/обход consumed generation |
| SqliteStageAttemptStore, db.repositories.sqlite.artifacts.stageAttemptStore | Concrete owner; scopes/operations/catalog и required stage_drain | Constructor graph §8; несогласованный graph отклоняется до IO; store не является общим drain adapter |
| SqliteStageExecutionDrain, db.repositories.sqlite.artifacts.stageExecutionDrain | Read-only authoritative predicate через ScopedSqliteAccess; implements IStageExecutionDrain | Нет зависимости от operations/leases/stage store и нет второй policy; unknown не превращается в drained |
| Existing IArtifactCatalog/SqliteArtifactCatalog | Reserve и scoped seal implementation reuse | Без второго seal commit; existing standalone API не притворяется scoped |
| Existing IArtifactWriteAdmission/SqliteArtifactLeases | Operation lease admission + drain | Не дублирует stage generation; cancel/READY обязаны видеть full claims |
| Existing ArtifactFormatRegistryBinding / ArtifactBackend | Codec, physical write/verify | Не выдаёт permit; worker drain до release, live scope не переносится workers |
| Existing ArtifactLifecycleLog | Post-outcome event | Не превращает successful seal в false rollback/unknown |
| Existing Publication operation/transaction adapters | Единственный operation lifecycle/transaction owner | Не вызывают Artifacts public service, не вводят параллельный terminal |

Роль каждого existing concrete backend должна быть проверена для выбранного binding; binding не выбирается BLOB-first. Таблица не выдаёт full architecture PASS при OPEN exact composition.

## 7. Consumer migration и приёмка

Сначала принять IO/Error/authority и schema roots; затем реализации/тесты; затем согласованный consumer cutover. Новый route использует только required permit+prepared, без overload lease-only fallback. Existing ArtifactStageInput и legacy стейджеры не удаляются до inventory callers; они не допускаются к новому recovery маршруту. DAG wrappers должны переносить новые owning failures целиком. Pack manifest callers и legacy TypedArtifactStager — отдельный cutover, не скрытый вызов begin внутри них. DescriptorBuilder.check needs authorized-root binding для нового caller; существующие callers сохраняют старую diagnostic семантику до своего явного перехода. Concrete перечень callers и node mapping предъявляет координатор; отсутствие перечня блокирует full migration, не закрывается этим документом.

Тесты: duplicate/concurrent begin/recover; lost ACK каждого commit; future/stale/conflicting bindings; второй consumer permit; old generation после successor; workers+cancel/READY; crash до/после reserve/write/seal; unknown без компенсации; completion after cancellation возвращает historical Confirmed; independent field+relation errors; каждый root/segment owner; Python/JSON/cold allowlist; bytes и concrete SQL_ROWS identity. Fake authority fixtures недопустимы для positive storage tests.

CRUD disposition текущего среза: begin создаёт immutable binding/authority; recover читает и условно обновляет generation; stage записывает artifact. Retention = retain, no deletion API. Artifacts сохраняет binding, predecessor chain, acquisition/release uncertainty и completion после claim release, cancel, READY, terminal и physical artifact GC. Удалять эти facts сейчас не вправе никто; TTL не вводится. Missing обязательные persisted facts — integrity fault, а не основание заново создать g=1. STAGE_UNTRACKED применим только к действительно не зарегистрированному stage. Publication сохраняет operation history по своей append-only границе. Это завершённая target disposition retention, не ожидание будущего retire API. Настройки новые не вводятся; полная CRUD-приёмка домена не заявляется.

Deferred future proposal, OUT текущего API: возможные tombstones, STAGE_RETIRED/PERMIT_RETIRED и retire acknowledgement обсуждаются только если пользователь отдельно потребует удаление. Эти enums НЕ добавляются в §3, ветви НЕ входят в §5, future acknowledgement не блокирует retain-контракт. Будущее удаление потребует cross-owner решения об исключении всех поддерживаемых replay, authority/unknown и operation history; конкретный механизм здесь не назначается.

## 8. SR-03: owning quiescence и сверка предъявленного Publication package

Сверена latest секция «Construction без dependency cycle» в artifacts-stage-recovery-publication-resolution.md. Совместимый TARGET: `SqliteStageExecutionDrain(access: ScopedSqliteAccess)` в db/repositories/sqlite/artifacts/stageExecutionDrain.py — единственный concrete IStageExecutionDrain. Required keyword `stage_drain: IStageExecutionDrain` получают SqliteOperationStore[R], SqliteArtifactLeases[R], SqliteArtifactHolders и `SqliteStageAttemptStore[R](scopes: SqliteArtifactScope, operations: SqliteOperationStore[R], catalog: SqliteArtifactCatalog, *, stage_drain: IStageExecutionDrain)`. Store-as-drain WITHDRAWN. Каждый exact SqliteStageExecutionDrain использует тот же access, что consumer; no-op/default запрещены. Один экземпляр допустим, но object identity между drain adapters не требуется: wrapper stateless, без cache/locks/claims/epoch/hot-rebind и собственной policy. Assembly: scopes/access → drain → operations/catalog → stage store → leases/holders → backend/writer. Сохраняются все Publication same-graph checks до IO и scoped recheck внутри transition transaction. Drain не зависит от stage store/operations/leases и не имеет отдельной state machine; authoritative predicate принадлежит Artifacts, durable representation пока OPEN.

`async SqliteArtifactCatalog.seal_in_scope(scope: CommitScope, reservation: StagingReservation) -> ArtifactRef` остаётся provisional, без собственного commit. seal_stage фиксирует completion в том же scopes.commits.transaction(operation_id), без отдельного evidence service. Concrete composition migration sites принимаются из Publication: PacksWiring.initialize_pack_storage, live_database, artifactFixtures.adapters, typing sqlite_composition и direct test constructors; fake drain True недопустим. Наличие такого перечня не означает runtime соответствия или регистрацию authorized stage.

Protocol `IStageExecutionDrain` объявляется в storage.stageAttemptStore, concrete реализация — отдельный SqliteStageExecutionDrain: `async is_drained(scope: CommitReadScope, operation_id: EntityUid) -> bool`, `async assert_drained(scope: CommitScope, operation_id: EntityUid) -> None`. Scoped authority/task/operation проверяются; no wait/commit внутри. True разрешён только когда каждая acquisition определённо не создала claim либо каждый созданный claim подтверждённо закончил все workers/effects и release. Подтверждённый live execution → False / OperationBusyError. Неразрешённый acquisition/release outcome либо corruption → соответствующий infrastructure/unknown fault, НЕ False/True. Generation fence запрещает будущий SQL admission, но не останавливает уже исполняющийся physical worker.

Proof owner — Artifacts, не Publication. Для штатного выполнения proof составляют: registered exact claim; запрет новых work submissions после начала drain; завершение всех уже submitted workers (включая executor future, rename/fsync и backend cleanup); отсутствие отложенного effect; confirmed release в authority store. Release нельзя подтвердить до worker join. Проверки generation выполняются перед каждым новым эффектом, но не заменяют join уже начатых эффектов.

Cancellation acquisition: до подтверждённого commit handle не выдаётся и workers не запускаются. Подтверждённый rollback означает отсутствие acquisition; потерянный ACK/unknown разрешается exact authoritative claim lookup. До разрешения новый claim/successor не выдаётся. Если acquisition committed, но callback не получил handle, отсутствие worker допускается доказать лишь если протокол handoff однозначно исключает выдачу handle и будущий запуск; одной пустой локальной таблицы tasks недостаточно. Cancellation после выдачи handle запускает owning drain, а не автоматический unconsume. Неизвестный release запрещает вывод quiescence; после authoritative reread требуется также сохранённое доказательство завершения workers, а не только отсутствие claim row.

Точная missing backend capability: existing `ArtifactBackend.write(reservation, content)`/verify/delete и write_admission не имеют контракта установления после restart, что ВСЕ effects конкретной execution identity завершены/не могут продолжиться. Existing BLOB shield/join обеспечивает local cancellation drain, не durable restart proof; concrete SQL_ROWS binding должен отдельно предъявить такую возможность. Нельзя обещать generic fencing physical IO только из operation/generation fence. Пока concrete backend не предъявил mechanism, consumed non-completed generation после потери process → Unresolved(ATTEMPT_NOT_QUIESCENT); successor не создаётся. Cancel также не завершает hold release по timeout. Подтверждённый completion может дать historical Confirmed, но lifecycle drain всё ещё должен доказать завершение оставшегося worker/cleanup.

Минимальная необходимая дельта перед automatic retry после crash — backend-specific контракт durable execution identity и способ исключить/дождаться всех старых physical effects, связанный с StageWriteClaim, включая cancellation acquisition/unknown release. Exact метод/representation нельзя честно назначить generic port без выбранного backend и его capabilities. Это локальный SR-03-BACKEND gap Artifacts, не запрос Publication доказать physical quiescence. Ни новый журнал, ни SQL, ни BLOB binding автоматически не назначены. До закрытия gap safe crash retry не принимается; штатный live drain отдельно проверяем.

Publication предъявил drain/scoped-seal constructor graph, transition inventory и retain/no deletion policy; они сверены как совместимое proposal. Остаётся общая приёмка их полного consumer cutover, а не повторный запрос отсутствующего пакета. Physical quiescence и stage persistence остаются Artifacts; foreign public service calls запрещены.

SR-03: latest Publication drain/constructor ports сверены; Artifacts crash-proof backend capability/persistence и общий cutover OPEN, safe crash retry не принят. SR-04: retain/no deletion target определён; concrete caller issuer/persistence OPEN, future retire acknowledgement OUT и не gate. SR-05: Fields/C0 scoped PASS TARGET roots учтён, invariants/aggregation уточнены; runtime/typing/cold closure и общий consumer cutover OPEN. Ни один SR не CLOSED по факту документа. Недостающие сведения исключают общую приёмку до сверки координатора и решения пользователя.
