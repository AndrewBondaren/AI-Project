# Stage persistence — полная цепочка этапа 2

2026-11-27. Конкретная спецификация координатора по поручению пользователя, без делегирования. PLAN-ONLY: новая SQL-схема и код не создаются. Документ уточняет persistence в unified contract, не принимает physical proof, witness owner, Q4 lifetime или production activation. Источники: current `0001_initial.sql`, catalogStore/leaseStore/holderStore/operationStore, owning resolution, deferred Q2/Q3, unified contract. Ниже нет второго transaction coordinator, generic event log или mutable status engine.

## 1. Архитектура и ответственность

Все Python paths ниже относительно backend/app. Stage-классы предложены в owning plan; выделение SqliteArtifactWriterClaims ниже — конкретизация U5 в этом документе, ещё не реализованная.

| Владелец | Методы / ответственность | Критерий отказа |
|---|---|---|
| SqliteStageAttemptStore, db/repositories/sqlite/artifacts/stageAttemptStore.py | begin, claim_stage, reserve_stage, local_writer, seal_stage, prohibit_effects, release_live/release_finalized, inspect/finish_recovery, pending_finalizations. Единственный writer stage facts; existing UOW/scopes/access | Physical IO, самостоятельный cleanup, второй issuer; commit внутри scoped primitive |
| SqliteArtifactCatalog | reserve_in_scope(scope,lease,descriptor), seal_in_scope(scope,reservation). Existing catalog/hold/seal predicates, provisional result | Дублирование predicates; изменение hold вне owning adapter; отдельный commit authorized seal |
| SqliteArtifactLeases | Existing local writer acquire/release chain; stage-2 scoped acquisition/release вызываются store в общем UOW | Проверка full-drained перед собственной local записью; это self-deadlock. Release до proof/join |
| SqliteStageExecutionDrain | is_drained(read_scope,oid), assert_drained(write_scope,oid): full acquired без released по ВСЕМ fences | IO-control, fake proof, фильтр только current fence |
| SqliteArtifactWriterClaims, db/repositories/sqlite/artifacts/writerClaims.py | Единственное чтение и validation existing local claim chains; active(scope, operation_id=None, artifact_id=None) и assert_local_drained_in_scope(scope,operation_id). Constructor(access: ScopedSqliteAccess) | Вторая копия query/validation; запись claims, wait/commit, зависимость от catalog/operations; фильтр current fence в operation drain |
| Publication lifecycle adapters: leases, holders, operations | Operation-wide recheck перед release/READY/APPLYING/NEW terminal; predicates в той же transaction | Снятие holds по stage result, empty inventory или старому read |
| Finalizer/writer/recovery jobs | Предъявляют issued capability и внешние preconditions, вызывают ровно нужный SQL transition | SQL completion/prohibition выдаются за physical evidence; повторный transition из context exit |
| Existing commit store/driver/registry | BEGIN IMMEDIATE, task/scope ownership, commit/rollback ACK, quarantine | Второй coordinator, implicit nested transaction, unknown как rollback |

Stage facts принадлежат Artifacts; operation lifecycle — Publication, включая методы в leaseStore. U5 решается одним internal SQLite reader SqliteArtifactWriterClaims, без дополнительного protocol/adapter/helper. Exact async signatures: active(scope: CommitReadScope | CommitScope, operation_id: EntityUid | None = None, artifact_id: EntityUid | None = None) -> tuple[ArtifactWriterClaimRow, ...]; assert_local_drained_in_scope(scope: CommitScope, operation_id: EntityUid) -> None. Первый метод переносит существующий catalog._writers целиком вместе с chain validation; второй вызывает первый без fence filter и при непустом результате бросает existing OperationBusyError. Corruption сохраняет PublicationInfrastructureError, не превращается в Busy. Ни один метод не открывает scope и не выполняет commit.

Catalog и operationStore получают required keyword dependency writer_claims: SqliteArtifactWriterClaims; catalog._writers временно только делегирует active для существующих внутренних callers, затем удаляется после их миграции без изменения алгоритма. Leases и holders получают тот же тип зависимости для operation-wide assertions; scoped local acquire/release сохраняют свои owning predicates. SqliteOperationArtifacts.read остаётся reader holds и не получает чужую ответственность. Assembly: ScopedSqliteAccess → SqliteArtifactWriterClaims / SqliteStageExecutionDrain → operations → catalog/attempts/leases/holders. Нет обратной зависимости reader→operations/catalog; нет singleton требования, требуется один authoritative storage и действительный scope того же access graph. Проверка миграции: всех callers _writers учесть, один источник chain validation, прежний catalog reserve/seal/GC не теряет artifact-scoped checks; operation consumers используют assertion без fence. Это внутренний storage контракт, не новый public service или DAG CALL. Exact stage owner остаётся attempts.

## 2. Identity и точные связи

Обозначения S=(operation_id,stage_id); G=(S,generation); K=(G,claim_id). Положительные integers strict; claim_id — unique canonical runtime_uid UUID. Все stage records insert-only, no update/delete/cascade. Текстовые идентификаторы сравниваются точно; отсутствие ряда не подменяется default. FK enforcement обязательно на каждом connection до workload. Row decoding сохраняет strict owning POJO validation.

| Fact / Row | PK и обязательные UNIQUE | FK и дополнительные ограничения |
|---|---|---|
| B StageBindingRow | PK S | operation_id → publication_operations. Полный immutable lease/ref как owning proposal. Trigger проверяет world/kind/preparation против operation, текущую writable authority при first begin. Повтор S с иным binding — typed conflict; old valid fence не переписывается |
| G StageGenerationRow | PK G; UNIQUE(S,predecessor_generation) | S→B; (S,predecessor_generation)→G. CHECK: g=1 и predecessor NULL ЛИБО g>1 и predecessor=g-1. Для g>1 trigger требует predecessor A+X, отсутствие C для S, current writable binding и отсутствие иной current successor. UNIQUE с NULL допускает root, PK/check оставляют ровно g=1 |
| A StageAcquisitionRow | PK G; UNIQUE(claim_id); UNIQUE(K) | G→generation. Trigger: текущая leaf generation, нет C для S, нет predecessor без X, operation writable, immutable binding совпадает. Один consumption; повтор не выдаёт новый handle автоматически |
| L StageLocalClaimLinkRow | PK G; UNIQUE(local_acquisition_event_id) | K→A(K); local_acquisition_event_id→artifact_writer_claims(event_id); artifact_id→catalog. Trigger: event_kind=acquire, exact operation/fence/artifact binding, текущий live local leaf, отсутствие P/X; catalog descriptor совпадает с B. Связь нескольких независимо существующих IDs недостаточна — проверяется полное отношение |
| P StageEffectProhibitionRow | PK G | K→A(K). Matching duplicate идемпотентен в adapter после compare; mismatch fault. P не требует L и не означает drain. Если X уже есть — no-op без вставки |
| C StageCompletionRow | PK S; UNIQUE(K) | K→A(K); artifact_id→catalog. Trigger: L для K, тот же artifact_id, live linked local leaf, нет P/X, current writable operation, sealed storage + exact operation hold. Полный descriptor catalog совпадает с B. Один completion на logical stage |
| X StageReleaseRow | PK G | K→A(K). Trigger: если L есть, exact linked local acquisition уже имеет непосредственный matching release successor; если L нет, требуется P и отсутствие C. X не создаёт C. Physical completion не проверяется SQL и остаётся precondition issued method |

K в каждой ссылке — четыре колонки, поэтому referenced A имеет явный UNIQUE(K), даже при отдельном unique claim_id. Нельзя заменить это двумя independent FK. Local acquire/release event identity и chain защищены existing PK/UNIQUE/predecessor triggers. Проверка artifact descriptor учитывает nullable row_count null-safe, не через SQL `=` с NULL.

Для stage-2 release_linked сначала append local release, затем X В ОДНОМ UOW. Поэтому X trigger видит release. Inverse требование «у каждого local release есть X» нельзя навесить на все existing events: legacy writers законно не имеют stage. Atomic pair обеспечивается закрытым scoped owning методом, rollback и transaction-boundary fault tests. Link+local acquire аналогично создаются одним методом/UOW; между inserts не вызывается consumer/worker. Непарный committed stage link/event при authoritative чтении — invariant fault, а не разрешение продолжить.

Legacy seal и authorized seal различаются caller contract, а не новым kind artifact. Нельзя требовать C для любого existing sealed event: один artifact может быть shared и ранее sealed legacy caller. Authorized method всегда записывает/проверяет C в seal UOW; отдельный raw SQL sealed event не считается stage success. Это явная граница DB enforcement против trusted adapter transaction, не обещание защиты от произвольного SQL с правами обхода owning methods.

## 3. Полная цепочка commit

Каждая строка — один short BEGIN IMMEDIATE UOW с confirmed ACK до dependent dispatch. Runtime handles не serialized. Existing standalone calls не вкладываются в UOW; используются scoped primitives.

| Transition | Чтения/preconditions | Записи и результат после commit |
|---|---|---|
| begin | Integrity, exact S/binding, current operation; historical C/replay по owning priority | Новый B+g1 атомарно либо owning outcome. Никакого acquisition/physical effect |
| consume | Exact current G, no C/consumption, writable | A с заранее выделенным claim_id. Только confirmed ACK позволяет выдать WRITE handle; unknown не dispatch |
| reserve_stage | Issued K; A, нет P/X; writable | Existing catalog identity + operation hold через reserve_in_scope. R не принадлежит исключительно K; возвращается exact reservation, без новой reservation table |
| local_writer | K/A, reservation/ref/hold/current authority; нет P/X; no active conflicting local writer | Existing acquired local event + L атомарно. Handle/dispatch только после ACK |
| physical batch | Gate/issued handle + committed A/L, нет P/X; owning authority recheck | Не SQL transaction: внешний IO. Persistence не объявляет его атомарным/завершённым |
| seal_stage | Issued full/local handles; A/L live, no P/X, current writable, verified exact ref | Existing scoped sealed event (либо reuse sealed artifact) + C в одной transaction. Отдельный completion commit запрещён; existing C сверяется целиком |
| prohibit | Exact A, integrity; L может отсутствовать; current writable не требуется | Insert P либо exact replay. После ACK новые reserve/local/authorized dispatch/seal запрещены, уже submitted IO ещё не считается drained |
| release_live linked | Exact live owner; stop/join/cleanup доказаны, no P/X; linked local leaf | Local release + X одним commit. C может отсутствовать после failed stage; completion не prerequisite release. Exit contexts не пишут повторно |
| release_finalized linked | A+P+L; внешний proof old effects/cleanup выполнен; exact release chain | Local release + X одним commit либо exact already released no-op. Нельзя fabricate physical proof из P |
| release_finalized NO_LOCAL | A+P, authoritative no L/X/C; доказан closed dispatch protocol | Только X. Catalog/holds/R сохраняются. Reserve/local/P serialization исключает последующее создание L/R этой execution |
| finish_recovery | Exact original G/binding; C прежде всех retry решений; writable; G leaf; X+partial-safety; no conflicting successor | Insert g+1 с predecessor=g. Запись successor сама является durable retirement predecessor: отдельный retired flag/table НЕ вводится |
| inventory | Один coherent scope: current request authority/closed, integrity всех B/G/A/X | Read-only A minus X по operation, включая все historical fences. C/L/temp не фильтры. Partial/corrupt read — fault, не batch |
| final cancel | Existing closed/fence/terminal checks + ALL local/full drain | Existing hold releases + outcome + terminal event в одном existing UOW. Stage results не передаются как bearer proof |

Идемпотентность successor: (S,g+1) и UNIQUE(S,predecessor) не дают fork. Two writers сериализуются BEGIN IMMEDIATE, второй читает уже существующий successor. Exact recover(g) после lost ACK возвращает его permit лишь если ещё unconsumed; consumed/complete/closed обрабатываются owning priority table, не выдаётся g+2. Новый explicit recover(g+1) — отдельный запрос. Отсутствие C не достаточно для issuance. Partial-safety остаётся backend precondition, не новый generic persisted bool.

## 4. Existing SQL guards и callers: обязательная дельта

Определить два разных predicate: `active_full(oid)=exists A without exact X`, `active_local(oid)=existing local acquired leaf without release`. Оба operation-wide, БЕЗ current-fence filter. Полный stage seal/reserve/acquire не требует отрицания active_full: его собственный A обязан быть активен.

| Existing DB guard / caller | Изменение этапа 2 |
|---|---|
| publication_operation_events_insert_guard: READY | Сохранить sealed holds/closed/local checks, добавить NOT active_full по operation |
| Тот же guard: APPLYING, увеличение fence, NEW TERMINAL | Требовать отсутствие active_local/full всех fences; сохранить existing transition/request/outcome checks. Увеличение fence не создаёт новый runtime producer |
| publication_outcomes_insert_guard | Перед NEW outcome добавить operation-wide full/local drain; сохранить existing publication evidence/refusal rules. Outcome и terminal event по-прежнему один UOW |
| artifact_holder_events_insert_guard: release holder_kind=operation | Заменить local current-fence фильтр на operation-wide; добавить full drain. Existing closed/fence/holder constraints сохраняются. Другие holder kinds не получают выдуманный operation_id |
| artifact_writer_claims_insert_guard | Сохранить local authority/hold/chain guards. НЕ добавлять global full-drained. Stage-specific exact K/no P/X проверяются L и owning transition; legacy acquisition остаётся legacy |
| artifact_storage_events_insert_guard: sealed | Existing live local+lease checks сохраняются. Stage-specific no P/X и exact full/local pair проверяет C/authorized seal method. NOT active_full здесь запрещён |
| Тот же guard: gc_deleted | Existing any-holder/any-local guard сохраняется. Добавить защиту artifact от active full binding с тем же descriptor; сопоставление через immutable B и catalog, т.к. no-link A может не иметь artifact_id. Не назначать GC новые cleanup обязанности |
| artifact_lease_events_insert_guard | Existing no-reopen/current fence сохраняются. Close admission допускается при active stage, иначе cancel не сможет начать drain |

Scope-level callers обязаны проверять те же predicate ДО insert, чтобы давать existing OperationBusyError, а не raw SQLite constraint error: leases.finish_preparation/cancel; holders.release(OperationHolder)/handoff; operationStore.claim_publication/_save(record_terminal/record_refusal). Final write scope — единственное основание release, предшествующий read только observation. Historical terminal replay не делает NEW inserts и не утверждает drain. Publication close_for_cancellation закрывает admission при active executions и возвращает Pending, не требует полного drain как предусловие close.

Own local release/_cleanup и stage-2 linked release НЕ требуют full-drained: сначала локальное завершение, затем X в общем commit. Operation-level hold release выполняется позже. GC no-link защита conservative: R может ещё отсутствовать либо быть shared; наличие active full binding не разрешает удалять чужие данные. Atomic SQL guards не подтверждают physical proof X — owning writer остаётся доверенной границей этого факта.

## 5. Replay, unknown и integrity

Для каждого K read выполняется через новый допустимый scope/connection после quarantine, без автоповтора side effect. Таблица допустимых durable состояний:

- B+G без A: выданный permit, не active execution; operation может закрыться, consumption тогда отказ.
- A без R/L: active no-dispatch кандидат; только P+NO_LOCAL позволяет X, отсутствие local row отдельно не proof.
- A+R без L: тот же путь, R/holds не удалять. P-first блокирует последующий reserve/local, local-first переводит в linked path.
- A+L без C/X: physical outcome неизвестен; P не заменяет drain.
- A+L+C без X: successful historical seal, residual lifetime ещё pending.
- A+X без C: завершённая неуспешная/неписавшая execution; retry только после authority и partial-safety checks.
- A+L+C+X: historical complete и завершённый lifetime; hold может позже быть снят cancellation.
- X без A, C без A/L, existing L с неверной identity, branch/gap поколений: fault до business outcome.

Lost ACK begin → повтор exact B; acquisition → lookup того же K, не новый claim_id и не второй dispatch; reserve → existing exact catalog/hold проверка; local/link → coherent reread пары; seal → C, не только storage.sealed; P → exact reread; release → X+local chain, не отсутствие temp; successor → predecessor relation. Unknown IO/SQL не превращается в empty inventory, rollback или release. Неполная пара local/X после committed owning operation — corruption; незакоммиченная пара не видна другому scope.

Stage facts и existing histories сохраняются без TTL/deletion. Explicit schema-version migration/cutover требуется до запуска consumers с новыми expectations; старые executions не получают synthetic A/L/C/X. Новые predicates проверяют только реально зарегистрированные stage facts плюс прежние local histories. Legacy callbacks не становятся authorized от совпадения format key. Production migration отдельно от текущего документа.

## 6. Проверки и граница завершённости

### Сквозная связь с публичным маршрутом

Caller сохраняет stable stage_id и exact StageBinding до begin CALL; это обязанность caller/Engine checkpoint, не stage store. begin сохраняет B/G до выдачи permit. Authorized stage принимает binding/permit, внутри Artifacts проходит A→R→L→physical→C→X; DAG не вызывает эти внутренние шаги. Durable C подтверждает исторический seal, а X — завершение execution lifetime, поэтому они не взаимозаменяемы. Подтверждённый CALL outcome переносится без повторного stage. Потерянный outcome ведёт к объявленному recovery CALL через REPORT_UNKNOWN; recovery читает facts, при необходимости выполняет owning finalization и лишь после допустимого finish выдаёт successor permit. Ошибка или Unresolved не разрешают повтор. Сохранение caller identity и exact Engine error transport остаются зависимостями U7/U6, не выполненными persistence-изменениями.

Cancellation route: Publication close_for_cancellation → typed ClosedPending.request → Artifacts pending_finalizations → каждый exact StageFinalizeInput → finalize_execution → existing Publication cancel с финальным operation-wide local/full recheck. Только DAG выбирает следующий публичный CALL. Busy сам по себе не запускает settlement; LOCAL_ONLY не превращается в stage; empty inventory не разрешает release. При ошибке/неопределённости одного элемента batch не считается полностью drained. Publication не вызывает Artifacts service; его storage adapters читают predicates в собственном UOW. Точные public POJO/Errors и mapping сохраняются из unified §§2–5, новые зеркала здесь не вводятся.

Таким образом, таблицы выше задают внутреннюю последовательность одной owning операции, а не дополнительные DAG-ноды. Порядок этапа 1 не меняется. Это спецификация persistence-участка полной цепочки; отсутствие witness/lifetime/Engine mapping не скрывается за локальным PASS.

Будущая schema проверка: compile FK/unique layout; foreign_keys enabled; запрет cross-stage/cross-generation claim references; cycle/gap/fork generation; duplicate consumption/completion; corruption nullable descriptor; P/no-L valid; C/no-L invalid. Две connections: concurrent begin/recover, reserve vs P, local vs P, seal vs P, release vs final cancel. Fault injection между каждой парой inserts B/G, local/L, seal/C, local-release/X, holds/outcome/terminal: видны либо все, либо ни одного. Replay каждого ACK boundary не добавляет generation/claim/effects.

Guard coverage: active full без local блокирует READY/APPLYING/outcome/operation hold release/GC нужного artifact; old-fence local также блокирует operation drain; own local acquisition/seal/release при active full НЕ блокируются. Legacy holder/reader paths сохраняют semantics. NO_LOCAL не снимает hold; BOTH/empty batch не обходят final cancel. Integrity faults не маскируются Busy/Unresolved.

Итог: в спецификации замкнуты B→G→A→R→L→C/P→X→successor и operation release, composite identities и распределение DB/adapter guards. Предложенная persistence-схема требует архитектурной приёмки и будущей проверки executable DDL; runtime/schema tests в этой работе не выполнялись. Открыты внешние physical proof/witness/Q4 lifetime, nominal handle U4 и generic error transport; SQL не выдаётся за их решение. U5 получает конкретный local predicate port/assembly здесь. Это не объявление полного stage-2 PASS.
