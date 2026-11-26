# Artifacts stage recovery — owning resolution SR-03/04/05

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
