# Контракт recovery отдельного stage — пакет согласования

2026-11-26. PROPOSED, не разрешение реализации. Пользователь поручил согласовать контракт без обходных путей. Координатор назначен пользователем: 01a218a4-bfc5-7012-b18b-8ed986cc786d. Связанный [identity-план](dag-artifacts-identity-transport.md), §7.3.

## Источники и доказанный разрыв

Owning ответы Artifacts 01a1ea09-2ab4-7f71-9d96-7a29d70269d7 и Publication 01a1ea8d-2bdb-7152-bb40-925c86c041d8 от 2026-11-26. Existing OperationLedger.recover возвращает observation операции, не разрешение повторить stage. lease/ref не различают отдельные вызовы. RUNNING → READY без owning основания не принят. Успех stage подтверждает исторический seal/hold; не гарантирует текущий hold после cancel.

## Рекомендуемая граница A

Publication предложил сосредоточить всю authority отдельного stage в Artifacts. Artifacts владеет binding, generation, выдачей/потреблением permit, полным execution claim, completion evidence и публичными begin/recover. Publication сохраняет operation identity/fence/phase/cancellation/terminal и transaction infrastructure. Stage recovery не переоткрывает и не завершает operation.

Ранее предложенный прямой Engine recovery → Publication service отозван. Доменные операции вызываются только через явно согласованный DAG CALL. Внутри Artifacts нет вызова public Publication recovery/issuance; внутри Publication нет вызова public stage. Storage adapter не скрывает такие вызовы.

Альтернатива B — передать Publication всю stage-attempt authority. Она требует более широкой смены границ; владельцем не рекомендована, в этом пакете не детализируется. Решение A/B относится к ответственности доменов и предъявляется пользователю.

## Конкретная форма публичного контракта A

Предлагаемые, не существующие модули: application/artifacts/staging/stageAttemptService.py и dataModel/artifacts/staging/stageAttempt.py. Классы/POJO из исходного Publication предложения переходят к единственному владельцу Artifacts; дубли в dataModel/publication не создаются.

`StageAttemptService.begin(request: StageBeginInput) -> StageAttemptResult` и `StageAttemptService.recover(request: StageRecoveryInput) -> StageAttemptResult` — async public методы. Один вызов обрабатывает один запрос и не запускает stage. Leaf/NodeId/регистрации ещё не назначены.

Все record POJO strict/frozen/extra-forbid; payload неизменяемый. Предлагаемый состав:

| Тип | Поля |
|---|---|
| StageBinding | stage_id: EntityUid; lease: OperationLeaseRef; artifact: ArtifactRef |
| StageBeginInput | binding: StageBinding |
| StageRecoveryInput | binding: StageBinding; generation: strict positive int — наблюдаемая потерянная generation, не запрошенная новая |
| StageAttemptPermit | binding: StageBinding; generation: strict positive int |
| StageAttemptAllowed | kind=ALLOWED; permit: StageAttemptPermit |
| StageConfirmed | kind=CONFIRMED; binding: StageBinding; completed_generation: strict positive int |
| StageRecoveryRefused | kind=REFUSED; binding: StageBinding; code: StageRecoveryRefusalCode; cancelled: OperationCancelled или None |
| StageRecoveryUnresolved | kind=UNRESOLVED; binding: StageBinding; code: StageRecoveryUnresolvedCode |
| ArtifactAuthorizedStageInput[C] | permit: StageAttemptPermit; prepared: PreparedArtifact[C] |

StageAttemptResult — discriminated union Allowed/Confirmed/Refused/Unresolved. Proposed refusal codes: operation_cancelled/admission_closed/stale_operation_fence/stale_stage_attempt. Unresolved codes: stage_untracked/attempt_not_quiescent/insufficient_evidence. cancelled — существующий typed OperationCancelled, не bool; непустой iff operation_cancelled. Окончательные owning enum/mapping требуют сверки Artifacts.

stage_id обозначает один логический stage, стабилен после restart; generation — исполнение stage, не operation fence и не Engine attempt. Namespace/issuer stage_id и правила сохранения до первого эффекта должны быть закреплены до реализации. Без дополнительного случайного permit token: authority проверяется по зарегистрированным binding/generation, а не по структурной валидности POJO.

begin идемпотентно предъявляет binding: новый binding регистрирует первую generation; exact повтор не создаёт новую попытку без основания. Уже потреблённый permit не запускает второго writer. recover возвращает новую generation только после доказанного безопасного retry. Первый stage и retry проходят один admission; старый stage input не оставляется fallback для этого маршрута. Изменение публичного входа требует явного согласованного перехода consumers.

stage(request: ArtifactAuthorizedStageInput[C]) -> ArtifactRef сохраняет public owning операцию Artifacts. lease берётся из permit.binding; prepared.descriptor сверяется с binding.artifact. PreparedArtifact передаётся тем же экземпляром по identity-плану. Дублирующий lease в новом input не добавляется.

Error: reuse ArtifactInputError и ArtifactLeaseFailure для существующих отказов; proposed ArtifactStageAdmissionFailure только для неизвестного разрешения/занятой generation и новых admission различий. Stage binding mismatch требует typed requested/stored bindings без копии ArtifactRef/lease полей; окончательная owning форма и enum ещё OPEN. Infrastructure/unknown commit/cancellation сохраняют категории, не превращаются в Unresolved. Unresolved — подтверждённая недостаточность evidence.

## Enforcement и атомарность

Proposed Artifacts IStageAttemptStore в application/artifacts/storage/stageAttemptStore.py:

- claim_stage(permit: StageAttemptPermit) -> AbstractAsyncContextManager[StageWriteClaim].
- async seal_stage(claim: StageWriteClaim, reservation: StagingReservation) -> ArtifactRef.

StageWriteClaim — внутренний runtime handle adapter, не публичный POJO и не второй permission token. Охватывает reserve → physical write → verify → seal; не означает SQL transaction на всё физическое IO. Новая generation недопустима, пока старая ещё может произвести эффект. Существующий worker drain сохраняется.

Publication предложил existing SqlitePublicationCommitStore.transaction(operation_id) -> CommitScope как инфраструктуру. В одном owning commit должны быть проверки актуального fence/admission/claim/generation, seal/hold и durable completion exact stage/generation/ref. Standalone seal с отдельным последующим evidence commit запрещён. ArtifactRef возвращается после confirmed commit; unknown остаётся UnknownCommitOutcome. Все adapters связаны одним coordinator/access/registry; scope/connection не раскрываются DAG.

Предлагаемый concrete adapter SqliteStageAttemptStore владеет этой атомарной операцией за Artifacts port. Exact constructor/dependencies и совместимость со scoped seal ещё должны быть предъявлены; SQL/новая таблица этим пакетом не назначаются. Разделение доменных public операций и общей transaction infrastructure проверяется по фактическим вложенным вызовам.

## Предлагаемая DAG-цепочка и outcomes

prepare → public begin → stage; prepare должен предшествовать begin, поскольку binding содержит готовый descriptor. Если begin вернул Confirmed, повтор stage не требуется. Восстановление незавершённого stage использует отдельный явный public recover CALL. Это предложение порядка, не утверждённый новый граф.

Confirmed → существующий ArtifactRef результата без повторной записи; Allowed → stage input с permit и исходным/восстановленным prepared; Refused/Unresolved → без stage. Engine runtime не вызывает доменный service напрямую и не читает catalog для выбора исхода. Точная передача сохранённого RUNNING в orchestration recovery CALL остаётся проектным контрактом DAG, не подменяется RUNNING→READY.

## Приёмка

### Реестр находок implement-plan review — 2026-11-26

Пользователь поручил зафиксировать ошибки и исправить либо делегировать владельцам. Исправления документации не разрешают код и не означают приёмку предложенного API.

| ID | Приоритет / дефект | Владелец / результат для закрытия | Статус |
|---|---|---|---|
| SR-01 | P1: identity mapping строил lease-only input в обход required permit | DAG: единый permit+prepared mapping, initial/retry и owning error cutover | Исправлено противоречие в identity-плане §§5.3–5.4; полный cutover зависит от SR-05 |
| SR-02 | P1: отсутствует переход сохранённого RUNNING в явный recovery CALL | Engine/DAG: состояния, parent event, join/CALL/outcome, сохранение checkpoint и отсутствие domain call внутри recovery owner | [Proposal перехода](dag-stage-recovery-transition-resolution.md) доработан; локальные замечания event/replay/retry устранены в проекте; общая приёмка OPEN по concrete parent и SR-03/04/05 |
| SR-03 | P1: неполный контракт enforcement безопасного retry | Artifacts + Publication: exact issuance/generation/claim/quiescence/atomic completion ports и cancel/READY совместимость | Scoped seal, lifecycle caller inventory и отдельный drain/constructor graph согласованы в проектах. OPEN: backend crash-proof capability, durable representation и общий consumer cutover |
| SR-04 | P1: issuer/namespace/persistence stage_id и повтор begin/recover не определены | Artifacts: точные правила correlation, таблица исходов, idempotency поколений, concurrent recovery | Authority precedence и retain/no-cleanup для текущего среза предъявлены; OPEN: concrete caller issuer/persistence. Future tombstone/retire не входит в текущую приёмку |
| SR-05 | P2: неполные Error/POJO/классы и migration diagnostic schema | Artifacts: поля/enum/carriers/paths, ответственность каждого класса, target vs existing и переход всех consumers | Единая error таблица предъявлена, [Fields/C0](artifacts-stage-recovery-fields-review.md) дал scoped PASS target paths; invariants/revalidation/aggregation-before-raise внесены в owning proposal. OPEN: manifest/consumer cutover и UnknownCommitOutcome transport |

Пакеты исправлений сохраняются отдельно владельцами; основной план меняет координатор после проверки. PASS не ставится по факту отправки поручения. Приёмка — повторная сверка всех обязательных критериев и общего маршрута, без повторного выбора уже принятого направления identity.

Координаторское ревью первого SR-02 proposal: REPORT_UNKNOWN/CallOutcomeUnknown и checkpoint CAS до scheduling соответствуют направлению; полный контракт не принят. Требуются: (a) at-least-once доставка event вместо недоказанного «один раз» и durable dedup logical CALL; (b) replay самого begin/recover при потерянном ACK без бесконечного recovery-of-recovery; (c) явная граница runtime FAILED/UnknownCommitOutcome, которые не доказывают отсутствие domain effects; (d) исключение обхода owning Allowed через existing retry_policy stage. Замечания переданы Engine в рамках пользовательского поручения исправлений. Доменные exceptions не разрешается классифицировать внутри generic Engine.

Повторная координаторская сверка SR-02 от 2026-11-26: (a) исправлено — at-least-once event, deterministic key/input/continuation и dedup одного logical dispatch; (b) исправлена формулировка — begin/recover RETRY только при доказанной SR-04 exact-request идемпотентности, без обещания одного physical call; (d) исправлено — REPORT_UNKNOWN stage требует retry_policy=None, следующая попытка только с owning Allowed. По (c) установлен безопасный предел: FAILED не означает отсутствие effects, auto stage retry запрещён; mapping UnknownCommitOutcome/category/cause до durable parent outcome остаётся внешним обязательным пунктом SR-05, пока не предъявлен точный error transport. Это scoped проверка проекта, не runtime PASS и не закрытие всего SR-02. Concrete parent continuation/CallTargets и общий маршрут должны быть сведены после owning пакетов.

Общая сверка owning + Publication resolution от 2026-11-26: контракты full claim, scoped seal/hold/completion и required operation drain согласуются по направлению. Не закрыто: Artifacts §8 ожидает proof quiescence от Publication, а Publication относит его к Artifacts; по границе A единственный владелец этого proof — Artifacts. Publication отвечает за включение данного predicate во все operation transitions, а не за самостоятельное определение остановки backend worker. Обоим владельцам возвращены конкретные исправления в их документах.

Дополнительные обязательные уточнения: precedence unconsumed Allowed относительно cancel/READY/stale fence в таблице Artifacts; lifetime stage correlation/completion относительно checkpoint replay и operation cleanup; полный fence/READY/terminal/release caller inventory. В SR-05 intermediate error carriers должны быть сведены в единую target таблицу. Fields/C0 передан новый schema-root/field+relation aggregate на отдельную проверку; старый P2 PASS не применяется автоматически. До закрытия этих пунктов owning документы остаются PROPOSED, не accepted API.

Повторная сверка обновлённых owning/Publication пакетов: перечисленные выше circular ownership, authority precedence и final error roster исправлены в проектах. Publication предъявил конкретные transition callers и retain/no deletion API; Artifacts подтвердил обязательное сохранение evidence для поддерживаемых checkpoints. Retired-key tombstone и новые retired enums у Artifacts относятся к ещё не принятой будущей очистке; они не должны расширять текущий retain-контракт.

Новое точное ограничение SR-03-BACKEND: existing ArtifactBackend.write/verify/delete и write_admission не дают restart-proof завершения ВСЕХ physical effects определённого execution. Local shield/join не доказывает quiescence после process loss. Для consumed non-completed generation без такого proof — Unresolved(ATTEMPT_NOT_QUIESCENT), без successor и без cancel hold release по timeout. Это честный предел предложенного контракта, не завершённое решение automatic crash retry.

Повторная сверка latest owning resolution: §8 синхронизирован с Publication — отдельный SqliteStageExecutionDrain(access), required в operations/leases/holders/stage store; stage-store-as-drain отозван. §7 оставляет retain/no deletion текущим контрактом; tombstones/retired enums и retire acknowledgement явно OUT и не блокируют текущую приёмку. §3 закрепляет relation invariants, revalidate_instances='always' для вложенных DTO и aggregation-before-raise независимых diagnostics. Эти три замечания исправлены на уровне проекта. Backend restart proof/durable representation, concrete caller issuer/persistence, manifest/consumer cutover и UnknownCommitOutcome transport остаются открытыми; runtime PASS и полная приёмка не заявляются.

Проверки: потеря ответа после seal, cancel до/после admission/seal, READY/closed и stale fence, второй consumer того же permit, полный drain, crash между write и seal, rollback/unknown, exact begin/recover replay и несовпадающий stage binding. Seal/evidence atomicity и отсутствие второго writer должны проверяться fault injection и конкурентными вызовами.

Publication рекомендует A; Artifacts дал scoped PASS именно границе владения A (ответ 2026-11-26). Координатор подтверждает согласованность этой предлагаемой границы с запретом прямых междоменных service calls. Это не PASS полного API. Artifacts отдельно потребовал совместимость cancel/READY/drain с полным stage claim: общего coordinator недостаточно.

Полная приёмка OPEN: пользовательское решение границы A; точные ошибки/namespace/issuer и initial issuance/recovery port; класс-by-класс inventory и соответствие текущему порядку; DAG recovery CALL и consumer cutover; доказательство атомарного scoped seal. Тесты будущей реализации не заменяют эти критерии. Код не изменялся.
