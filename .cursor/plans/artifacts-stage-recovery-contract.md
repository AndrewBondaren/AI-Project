# Контракт recovery отдельного stage — пакет согласования

2026-11-26. PROPOSED, не разрешение реализации. Пользователь поручил согласовать контракт без обходных путей. Координатор назначен пользователем: 01a218a4-bfc5-7012-b18b-8ed986cc786d. Связанный [identity-план](dag-artifacts-identity-transport.md), §7.3.

## Источники и доказанный разрыв

Архитектура варианта 2 подробно зафиксирована по поручению пользователя в [backend fencing](artifacts-stage-recovery-backend-fencing.md): ответственность классов/доменов, атомарность authority и effects, recovery/cancel порядок, partial effects, ограничения внешнего IO и критерии приёмки. Это целевое направление; конкретный backend mechanism и public API ещё требуют проверки и приёмки. Документ не разрешает реализацию и не объявляет SR-03-BACKEND закрытым.

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

### Открытые вопросы для решения — 2026-11-26

#### Проверка actual механизмов перед выбором решения

По поручению пользователя «Проверь, затем только потом решим» проведено чтение actual кода, без изменения runtime и без выбора proposal. Это статическая проверка гарантий, не crash-test PASS.

- `backend/app/storage/artifacts/blobBackend.py::ContentAddressedBlobBackend._io/write`: executor future shielded и дожидается завершения при CancelledError. Temp creation/fsync, placement/verification и cleanup находятся под local writer claim. Между assert_writable и `_place` есть отдельный await/physical IO; generation/fence не проверяется атомарно с filesystem effect. No-overwrite/content-addressing защищает содержание файла, но не доказывает прекращение старой execution. Публичного restart-proof/worker identity API здесь нет. Подтверждённая смерть процесса и потеря его доступности — разные факты; recovery не получает подтверждение первого.
- `backend/app/db/repositories/sqlite/artifacts/leaseStore.py::writer/_cleanup/cancel/recover`: durable acquire/release; cleanup освобождает claim при штатном выходе; cancel закрывает admission и ждёт исчезновения writers в цикле без deadline; recover возвращает operation observation. После crash с сохранённым acquire и без release автоматического доказательства quiescence/освобождения в этих методах нет. `ArtifactWriterClaimRow` содержит artifact/operation/fence/event chain, но не durable идентичность процесса/worker и свидетельство его остановки.
- `backend/app/application/artifacts/staging/artifactStageWriter.py::write`: backend.write имеет собственный claim, затем writer отдельно берёт claim для verify/seal. Полного stage-attempt claim/evidence из proposal в actual пути ещё нет. `ArtifactBackend` предоставляет write/verify/delete и write_admission, не recovery конкретного execution. По поиску concrete наследников в backend/app найден ContentAddressedBlobBackend; production SQL_ROWS backend для рассматриваемого маршрута не предъявлен. Test rows fixtures не доказывают production capability; BLOB этим аудитом не выбран.
- `backend/app/application/engine/runtime/invocations/invocationCoordinator.py::accept` сохраняет parent continuation и child input/address и дедуплицирует parent step/key; `dagExecutor.py::_start_selected` выполняет owned.save до `_invocation_step`. Основа checkpoint-before-effect существует. `ResumablePythonNode.start(input)/resume(state,event)` не получают parent address/step; NodeRunner имеет ExecutionIdentity внутри, но не передаёт его public parent. CallOrigin остаётся расширением API, а не уже доступным механизмом.
- Actual `InvocationCoordinator.__init__` переводит RUNNING в READY. В `resumeEvent.py` нет CallOutcomeUnknown; CallRuntimeFailure содержит только diagnostic_ref. `NodeRunner.run/run_resumable` при необъявленном exception сохраняет имя типа в diagnostic message, но не typed category/cause payload. Поэтому UnknownCommitOutcome не имеет предложенного durable typed transport к parent; наличие текстового имени не закрывает SR-05. REPORT_UNKNOWN/OUTCOME_UNKNOWN и конкретный recovery CALL остаются проектом.

Вывод проверки: existing CALL/checkpoint и local cancellation drain можно переиспользовать. Готового crash-recovery proof, public stage-id producer и полного unknown/error route нет. Выбор нового механизма остаётся за последующим решением; утверждение «достаточно существующего fencing» actual кодом не подтверждено. Новые тесты и runtime правки в этой проверке не выполнялись.

Этот список фиксирует оставшуюся работу по запросу пользователя «Зафиксируй вопросы, затем нужно решить, предложения?». Предложения ниже не являются принятым API и не разрешают код. Перенос crash recovery в отдельный этап не закрывает его.

| Вопрос | Владелец | Предложение и критерий закрытия |
|---|---|---|
| Q1 / SR-03-BACKEND: как после потери процесса доказать прекращение ВСЕХ эффектов прежней execution и завершить drain? | Artifacts: concrete backend и claim authority; Publication: использование доказанного drain в lifecycle | Сначала предъявить карту effects фактически нужного backend: write/verify/seal, workers, внешние запросы и cleanup. Предпочтительный вариант при поддержке backend — проверка действующей execution authority атомарно с каждым изменением защищённого ресурса, с доказанным завершением уже принятых работ. Альтернатива — подтверждённое прекращение и drain конкретного execution средствами владельца workers/backend. Проверка fence перед IO, истечение lease, отсутствие локального task или timeout сами по себе недостаточны. Закрытие: старый worker после takeover не может изменить защищённый ресурс; все уже принятые effects/cleanup завершены или доказанно отменены; exact completion отличим от отсутствующего/unknown. Затем owning recover может разрешить successor, а Publication — закончить drain. |
| Q2 / SR-04-CALLER: кто выдаёт и сохраняет stage_id до begin? | DAG/Engine: public CALL origin и checkpoint; Artifacts: формат и binding | Переиспользовать адрес исходного begin CALL через предложенный CallOrigin, без второго allocator/registry. Parent один раз строит StageBinding и сохраняет его в input/continuation до begin effects. Stage/recover/successor используют сохранённый id. Закрытие: согласованы namespace/длина и public signature migration; replay до/после accept/CAS не меняет id; новый логический stage отличается от повторной попытки прежнего. |
| Q3 / SR-02 + SR-05: как провести unknown/error до конкретного owning recovery CALL? | Engine: generic event/error transport; Artifacts: owning errors/results; DAG: конкретный parent и mapping | Свести одну таблицу: child terminal/status → public event/error → parent continuation → declared CALL/input → owning outcome. REPORT_UNKNOWN не заменяет runtime/declared errors. Для UnknownCommitOutcome явно указать сохраняемые category/cause и wire representation; generic Engine не классифицирует Artifacts exceptions. Закрытие: конкретные parent/leaf POJO и CallTargets, один public call на leaf, checkpoint/replay сохраняют категории, ни один путь не повторяет stage без Allowed; Confirmed не создаёт фальшивый success старого child. |

Рекомендуемый порядок: Q1 — сначала выяснить реальные capabilities нужного backend и выбрать доказуемый механизм; Q2 — согласовать уже предъявленную узкую public дельту; Q3 — свести конкретную цепочку с результатами Q1/Q2. Проверку Q2 и инвентарь Q3 можно вести независимо от Q1. Не выбирать production binding из удобства, не заменять полный physical drain запретом одной лишь публикации и не вводить второй Engine lifecycle. Если backend не умеет ни надёжно fence все effects, ни подтверждать их прекращение, automatic recovery для него остаётся неподдержанным до отдельного изменения backend; это явный результат проверки, не «решение через Unresolved».

### Реестр находок implement-plan review — 2026-11-26

Уточнение объёма по ревью пользователя: automatic recovery после потери процесса выделяется в отдельный этап SR-03-BACKEND. До его реализации возможна бессрочная блокировка consumed non-completed stage: Unresolved, запрет successor и запрет hold release без proof остаются обязательными. Это известное ограничение, не блокер независимой реализации штатной записи после локальной приёмки и не утверждение готовности crash recovery. SR-04-CALLER блокирует подключение конкретного workflow, а не внутреннюю реализацию Artifacts. Приёмка плана сама по себе не разрешает код.

Проверка existing CALL identity завершена в [Engine resolution, SR-04-CALLER](dag-stage-recovery-transition-resolution.md): InvocationCoordinator.accept сопоставляет child по parent invocation/step/call_key, сохраняет эти поля и continuation в graph, проверяет exact replay input. Child invocation_id создаётся после формирования request.input, а public start/resume не получают parent invocation/step. Следовательно existing identity можно переиспользовать, но доступного публичного producer до begin сейчас нет. Предложены CallOrigin и mapping адреса begin CALL в stage_id, сохранение StageBinding в input/continuation с checkpoint CAS до effects и перенос прежнего id через stage/recover/successor. Это новая непринимаемая автоматически public API-дельта; namespace/длина проверяются Artifacts. Новый allocator/registry не требуется. SR-04-CALLER остаётся точным integration gap, а не поводом перепроектировать внутренний Artifacts API.

SR-03-DI исправлен в проекте после проверки Publication и поручения пользователя «Правим»: отдельный read-only drain устраняет constructor cycle; object identity между stateless adapters не защищает дополнительный invariant и не требуется. Сохраняются exact owning implementation, drain.access is consumer.access, общий registry/coordinator, единый authoritative predicate, отсутствие mutable per-instance state/hot-rebind и scoped recheck в transaction. Default/no-op запрещены. Разные wrappers допустимы; identity scopes/access и StageWriteClaim не ослабляется. Приёмочные проверки: два adapters на одном stable scope/state; отказ при чужом access/registry; изменение authority ловится transition recheck.

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
