# SR-03 — Publication boundary for full stage claims

2026-11-26. Документальный owning PROPOSAL, вариант A. Код/SQL не менялись. Основной пакет: [artifacts-stage-recovery-contract.md](artifacts-stage-recovery-contract.md), SR-03. Artifacts owns stage-attempt authority; Publication остаётся инфраструктурой Snapshot и owns operation lifecycle/transaction acknowledgement. Publication StageAttemptService не вводится.

## Вердикт

### Уточнение этапа 1: pending full claim — 2026-11-28

Нормативная дельта предложения по P1 LIVE-01: после confirmed close admission existing cancel проверяет full drain вне write UOW. False немедленно даёт OperationBusyError с сохранением holds и без нового terminal, независимо от того, ещё работает owning execution или уже закончилась с drain error. Ошибки/Unknown predicate сохраняют категорию. Новый marker завершившегося owner, recovery service, timeout и автоматический retry не вводятся. Только local-only blockers сохраняют existing blocking wait; перед каждой итерацией проверяется full predicate. Финальный UOW по-прежнему повторяет local/full guards до первого release.

Это явное изменение waiting behavior для full claims в предложении этапа 1. Нижние исторические требования «ждать оба множества», «сохранить blocking promise» и сохранения full+local wait отменены в этой части; local-only поведение сохраняется. Busy не является доказательством close или разрешением finalization. Artifacts владеет predicate, Publication/SQLite lifecycle — его consumer и atomic release/terminal. Проверки и состояния handle: [LIVE-01](artifacts-stage-recovery-owning-resolution.md). Общая приёмка и реализация не объявляются.

### Q6 — окончательный operation release/terminal после finalization, 2026-11-27

Owning Publication proposal для общей приёмки; код не изменён, не code-go. Используется существующий public `OperationLedger[R].cancel(operation_id: EntityUid, fence: int) -> OperationRecord[R]` (async), делегирующий `IArtifactLeases[R].cancel` / `SqliteArtifactLeases[R].cancel` с той же сигнатурой. Положительный strict fence и operation_id валидируются existing boundary. Новый finalize-operation DTO/API не вводится. Вход берётся из проверенного `OperationCloseInput`: `cancel(close_result.request.operation_id, close_result.request.fence)`; stage result, inventory и их количество не являются аргументами/authority cancel. Выбор CALL принадлежит согласуемому DAG, этот раздел не назначает новые ноды или порядок.

Cancel этапа 1 сохраняет close → проверку вне write transaction → final transaction. Full blocker даёт OperationBusyError без ожидания; local-only blocker сохраняет existing ожидание с повторной full проверкой. Q6 не добавляет второй owner loop или polling service. Ни timeout, ни отмена ожидания не разрешают release.

**Единственная финальная write transaction.** Прежние наблюдения close/inventory/finalization/read-loop не заменяют следующие чтения в том же existing scope:

1. Загрузить и проверить authoritative operation record/lifecycle integrity; exact operation_id и current fence. Existing stale cancellation fence остаётся ValueError, не переносится новый Q5 error mapping на старый cancel. Missing/corrupt facts обрабатываются existing lifecycle/infrastructure policy, без успешного результата.
2. Если уже имеется valid terminal — вернуть existing record после успешного завершения scope, без новых hold releases/terminal insert и без интерпретации как нынешнего drain. Эта ветвь идёт после fence/integrity; terminal не позволяет обойти stale fence.
3. Для нового cancellation подтвердить закрытое admission и допустимость cancellation по existing evidence/lifecycle policy в текущем scope. Direct operation допускается лишь при authoritative policy, исключающей admission/новые acquisitions; отсутствие обязательной admission — fault. Ни смена phase, ни старый successful close не заменяют эту проверку.
4. Проверить ВСЕ active local writer claims operation через existing `SqliteArtifactCatalog._writers(scope, operation_id)`, без фильтра только по stage, текущему fence или наличию StageLocalClaimLink. Включаются legacy local-only writer и local claims всех executions. Любой acquired без authoritative release блокирует cancellation; corrupt chains не считаются пустыми.
5. В том же scope вызвать proposed internal `IStageExecutionDrain.assert_drained(scope, operation_id) -> None`. Predicate охватывает ВСЕ acquired stage executions operation: все stages/generations/historical fences, в том числе completed executions с residual cleanup, acquisition без reservation/local link и prohibited execution без confirmed release. Требуются authoritative matching releases и отсутствие сохраняющейся способности effects по owning Artifacts contract. Completion, prohibition, отсутствие local claim или записи в batch не заменяют full release. Unknown/integrity error не превращается в drained. Unconsumed permit не active execution, но closed admission обязана исключать его дальнейшее consumption.
6. До первой записи release проверить existing exact held-artifact/hold-chain/fence и cancellation evidence predicates. Освободить только existing operation holds по действующей retention policy; не удалять stage history, чужие holds, final artifacts или catalog reservation ради drain. Записать `OperationCancelled(operation_id=operation_id, reason=OperationCancellationReason.REQUESTED)` через existing `SqliteOperationStore.record_terminal(scope, outcome)` в этой же transaction. `_save` сохраняет existing typed terminal/evidence checks. Нельзя отделить hold release от terminal самостоятельным commit.
7. Выдать resulting OperationRecord[R] только после confirmed commit acknowledgement. Сбой любой проверки/записи откатывает всю final transaction при confirmed rollback; возможный commit при unknown не объявляется rollback.

Это operation-wide recheck. Publication знает scoped full-drain predicate, но не получает stage inventory и не реализует алгоритм физической quiescence. Pending executions/releases и их physical evidence остаются Artifacts-owned. Predicate adapter читает existing authoritative state через общий access/scope, не вызывает public Artifacts service и не ждёт OS gate под SQL transaction.

| Outcome cancel | Допустимое основание / эффекты |
|---|---|
| Новый OperationRecord с terminal OperationCancelled(REQUESTED) | Все перечисленные final predicates и hold releases/terminal подтверждены одним commit |
| Existing terminal OperationRecord[R] | Exact validated historical replay, возможно другой existing terminal alternative. Ноль новых release/terminal writes; не proof нынешнего full/local drain |
| Ожидание без результата | Только local blocker при подтверждённом full drain; full blocker завершает вызов через OperationBusyError |
| OperationBusyError | Final scoped drain recheck обнаружил blocker либо existing evidence policy дала Busy; никаких новых release/terminal в успешно завершённой final transaction. Busy не close proof и не автоматический trigger finalization |
| Existing validation/lifecycle error, включая ValueError stale fence | Отказ existing cancel boundary; Q5 error taxonomy его не меняет |
| PublicationInfrastructureError | Broken authoritative chains/scope/binding/held artifact либо infrastructure fault по existing policy; cause сохраняется, drained/result не фабрикуются |
| UnknownCommitOutcome | Неизвестен close/final commit/rollback outcome, existing quarantine/reconciliation. Нет success/refusal/compensation; final release и terminal могли commit вместе |
| CancelledError | Отменён вызов/ожидание; cleanup UOW следует existing cancellation policy, release по timeout/отмене запрещён. При потере ACK отсутствие commit не предполагается |

**Гонки и неполное завершение.** Unresolved одной execution оставляет её full claim blocker; успешные finalizations других stages этого не меняют. Пустой `pending_finalizations` batch не доказывает local drain и не является input proof; даже полный batch — observation, не блокировка operation. Legacy local-only writer учитывается независимо от batch/link. Несколько generations одного stage проверяются так же, как несколько stages.

Close и consumption сериализованы existing write UOW: consumption до close виден final predicate, после close запрещён. Concurrent finalization/release либо commit до final cancel scope и учитывается, либо ещё не commit и claim блокирует cancel; проверка и operation release не разделены TOCTOU-окном. Concurrent cancel после первого terminal возвращает exact historical record без повторных releases. Concurrent close не reopened admission, eventual terminal становится terminal replay. Concurrent fence change даёт stale отказ, а не замену fence caller-ом. Если finalization остаётся Unresolved, DAG обрабатывает её owning результат; вызов blocking cancel не может обойти её и вправе ждать. Новый автоматический цикл recovery/finalization в Publication не появляется.

Historical terminal может сосуществовать с residual stage execution по owning historical policy. Replay не переписывает history, не подтверждает очистку и не запускает Artifacts; отдельная residual finalization не получает permission release из terminal. Для НОВОГО terminal полный drain обязателен. После unknown final commit повтор exact cancel/reconciliation на здоровом authoritative scope определяет persisted outcome: matching terminal → replay, nonterminal → весь existing cancel/recheck путь заново; stale → отказ. Нельзя выдавать record_refusal после unknown rollback или повторять release по памяти об успешном stage.

**Конкретные consumers и минимальная дельта (пути относительно backend/).** Это уточнение уже proposed full-drain guards ниже, не заявление об их наличии в runtime:

| Existing метод / consumer | Необходимая граница |
|---|---|
| application/publication/service/operationLedger.py::OperationLedger.cancel | Сохранить signature/validation/delegation; никаких Artifacts public calls или owner loop |
| db/repositories/sqlite/artifacts/leaseStore.py::SqliteArtifactLeases.cancel | После close, до каждого local wait, full read predicate False → OperationBusyError; unknown/fault → propagate. Final UOW повторяет current closed/evidence, ALL local + full predicates до любого release и terminal |
| Тот же класс ::finish_preparation | Before READY — local + full guard в том же UOW, затем existing close/holds/sealed checks; READY не portable drain proof для cancel |
| db/repositories/sqlite/artifacts/holderStore.py::SqliteArtifactHolders.release (OperationHolder only) | Current binding/fence/closed + operation-wide local/full guard до append release. Existing current-fence-only local filter недостаточен для operation-wide guarantee; остальные holder branches не получают фиктивный operation_id |
| Тот же класс ::handoff | В borrowed write scope до первого append — existing APPLYING/lease/retention predicates + operation-wide local/full guard; собственного commit нет |
| db/repositories/sqlite/snapshotCore/operations/operationStore.py::SqliteOperationStore.claim_publication | Before NEW READY→APPLYING — scoped local/full guard; старое READY observation недостаточно |
| Тот же класс ::_save через record_terminal / record_refusal | Before NEW terminal/event — current lifecycle/evidence + scoped operation-wide local/full guard. Exact existing terminal replay без нового drain/release; record_refusal только после confirmed rollback |
| leaseStore.py::_release/_cleanup/writer; stage full/local release owner | НЕ требуют full operation drain для release собственного writer claim: иначе self-deadlock. Они подтверждают лишь свою exact execution/local release и не выпускают operation holds/terminal |

Required stateless `SqliteStageExecutionDrain(access)` / `IStageExecutionDrain` и общий scope graph уже предъявлены ниже; dependency на public StageAttemptService, backend/gate/job или второй coordinator не вводится. Local predicate остаётся existing catalog writer-chain predicate; для stores без него нужен scoped reuse того же existing authoritative query, без нового public API/второго алгоритма. Exact same-graph wiring local/full guards во всех consumers подлежит общей приёмке; отсутствие сведений о нём не считается PASS. OperationCloseInput не дублируется; нового cancellation outcome, owner класса или stage DTO нет. Ответственность и признаки нарушения existing классов дополнительно перечислены в таблицах ниже.

**Критерии проверки Q6.** Две connections и fault injection: два stages (один finalized, второй unresolved); несколько generations/старых fences; completed без release; no-link acquisition; пустой inventory + legacy writer; BOTH после release только full или только local. Во всех случаях ноль NEW operation release/terminal до полного drain. Проверить оба порядка close/consumption и finalization/cancel, два concurrent cancel (один новый terminal), fence race, historical terminal с residual claim (ноль новых writes), replay после lost ACK и confirmed rollback/unknown на close и final transaction. Ошибка после первого hold append должна откатить ВСЕ releases вместе с terminal; unknown не даёт ложного rollback/новой identity. Timeout/CancelledError не освобождают holds. Проверить каждый consumer таблицы, closed check, all-fence local query, same-scope full guard и отсутствие public foreign calls/нового loop. Blocking cancel этапа 1 сохраняет ожидание, return/error semantics и own-claim release без self-deadlock.

Статус Q6: предъявлен для общей приёмки координатором и пользователем; полная цепочка OPEN до сверки owning full predicate/physical evidence и exact consumer wiring. Эта правка документа не принимает этап 2 и не меняет штатный код этапа 1.

### Q5 — окончательная Publication-форма для общей приёмки, 2026-11-27

**Итог в рамках ответственности Publication.** Контрактная часть Q5 сведена и предъявлена; дополнительных вариантов Publication API не предлагается. Нормативная форма — этот раздел; P1.3/RC02 ниже сохраняют обоснование и не расширяют её. Полная междоменная приёмка остаётся OPEN, реализация не заявляется.

**Владельцы итогового пакета Q5 (фиксация 2026-11-27).** Таблица фиксирует ответственность и необходимые подтверждения, а не полученные согласования.

| Владелец | Предмет ответственности / предъявляемый результат | Статус и источник |
|---|---|---|
| Publication | OperationLedger.close_for_cancellation; OperationCloseInput/Result/Error; confirmed close/ack, exact request correlation, direct/terminal/stale/unknown/Busy semantics. Передаёт OperationClosePending.request без stage inventory | Итоговое owning предложение предъявлено в Q5 этого документа; общая приёмка OPEN |
| Artifacts | StageAttemptService.pending_finalizations(OperationCloseInput); OperationStageFinalizationResult/Batch/Refused; полный coherent inventory, historical binding, StageFinalizeInput и finalize_execution; physical evidence и full-drain predicate | Owning контракт: [Artifacts resolution, RC-02](artifacts-stage-recovery-owning-resolution.md); внешние ограничения и OPEN: [отложенный этап 2](artifacts-stage-finalization-deferred.md). Publication не принимает эту часть за владельца |
| DAG / назначенный координатор Between domain operations, thread ID 01a218a4-bfc5-7012-b18b-8ed986cc786d | Сверка всей цепочки close output → pending_finalizations input → batch.pending item → finalize_execution; только FULL_STAGE/BOTH дают inventory trigger. Проверка всех обязательных DAG-критериев, current-state rechecks, границы с Q6 и неизменности утверждённого порядка; явный вердикт PASS/OPEN/FAIL | Общая сверка OPEN. Назначение и порядок: [правило координации](../rules/interdomain-contract-coordination.mdc). Наличие mapping не означает согласования новых NodeId/маршрута |
| Publication — смежный Q6 | Existing cancel: окончательный operation-wide local/full recheck, release holds и новый terminal в одной transaction; historical replay и unknown commit | Отдельное owning предложение Q6 выше; Q5 не заменяет его приёмку и не выдаёт operation release permission |
| Пользователь | Окончательное решение по междоменной границе и объёму приёмки после вердикта координатора; отдельное разрешение на реализацию | Решение о полной приёмке Q5 этим документом не предполагается; code-go отсутствует |

Следующий адресат пакета — назначенный DAG-координатор для общей сверки, затем пользователь для решения. Фиксация владельцев не означает отправку сообщений, получение их согласия или закрытие внешних OPEN.

| Предмет итогового решения | Publication disposition |
|---|---|
| Producer | Existing OperationLedger[R], новый proposed async close_for_cancellation(OperationCloseInput) -> OperationCloseResult[R]; lifecycle transaction выполняет existing leases adapter |
| Proof | Только confirmed transaction acknowledgement и проверенная корреляция request/record. Ready/Pending подтверждают close и scoped drain observation; Terminal подтверждает historical record, не close/drain |
| Единственный междоменный operand | OperationClosePending.request: OperationCloseInput целиком, без дополнительных lease/stage полей. Только FULL_STAGE/BOTH обосновывают pending_finalizations(request) |
| Consumer mapping | Artifacts возвращает OperationStageFinalizationBatch.pending: tuple[StageFinalizeInput, ...]; DAG передаёт каждый item целиком в finalize_execution. Inventory, historical binding и execution evidence принадлежат Artifacts |
| Остальные ветви | LOCAL_WRITERS — local drain; Ready — existing cancellation handling; Terminal — operation-level replay. Direct без admission — Ready только при исключающей staging policy и отсутствии local/full facts. Stale/missing/corrupt — infrastructure error нового close метода |
| Неуспешный вызов | Busy, UnknownCommitOutcome, CancelledError и прочие exceptions не создают close output и не запускают finalization. Lost ACK требует exact retry/owning observation |
| Граница с Q6 | Close и stage finalization не снимают operation holds и не пишут cancellation terminal. Operation-wide final local/full recheck, release и terminal определены отдельно в Q6; успех одного stage/пустой batch их не заменяют |
| Scope неизменен | Без stage inventory в Publication, synthetic lease, public Artifacts calls из service, нового owner loop, NodeId или изменения штатного blocking cancel |

Остаток общей приёмки: координатор сверяет exact producer→consumer mapping с owning Artifacts контрактом, повторную current-state проверку и сохранение утверждённого порядка; пользователь принимает границу. Physical quiescence, полнота stage inventory и finalization outcomes принимаются у Artifacts, final operation release — по Q6. Publication не объявляет эти внешние обязательства выполненными. Критерии отказа и полный Input/Result/Error приведены далее; наличие типов и этой сводки не является runtime evidence или PASS всей цепочки.

Приоритетное уточнение P1.3/RC02 ниже. Полные Input/Result/enum declarations из P1.3 сохранены без дополнительных полей: OperationCloseInput(operation_id: EntityUid, fence: strict int >= 1); OperationCloseTerminal[R](kind=TERMINAL, record: OperationRecord[R]); OperationCloseReady(kind=CLOSED_DRAINED, request: OperationCloseInput); OperationClosePending(kind=CLOSED_PENDING, request: OperationCloseInput, pending: OperationDrainPending). Все поля обязательны; discriminated union по kind, strict/frozen/extra-forbid/revalidate always. Public async OperationLedger[R].close_for_cancellation(request: OperationCloseInput) -> OperationCloseResult[R]; owning module app.dataModel.publication.operationClose.

Каждый результат выдаётся только после confirmed commit acknowledgement одной короткой operation UOW. Внутри: integrity/binding → exact operation_id/current fence → terminal check → для nonterminal existing cancellation evidence policy → close/already-closed admission → local/full predicates → provisional result. Ошибка acknowledgement исключает выдачу provisional результата, включая Terminal. Ledger проверяет output.request == input либо record.operation_id/fence == input coordinates; mismatch — PublicationInfrastructureError.

| Result | Условия в подтверждённой UOW |
|---|---|
| Terminal(record) | Existing terminal phase и non-null terminal после integrity/current-fence checks. Подтверждает observation record, не новый close и не drain; stale fence не обходится |
| Ready(request) | Nonterminal, отмена допустима, admission закрыта; local_pending=false, full_pending=false |
| Pending(request, FULL_STAGE) | Nonterminal, отмена допустима, согласованная staging admission закрыта; full_pending=true, local_pending=false |
| Pending(request, BOTH) | Те же prerequisites; full_pending=true, local_pending=true |
| Pending(request, LOCAL_WRITERS) | Те же prerequisites; full_pending=false, local_pending=true |

Direct nonterminal operation без admission получает Ready только если authoritative policy исключает staging admission и все local/full facts отсутствуют. Lease/admission не синтезируются; подтверждается policy, запрещающая acquisitions. Missing обязательная admission или противоречащие direct policy local/full facts — infrastructure fault. Direct terminal проходит общие integrity/fence/terminal проверки. Full pending учитывает execution без confirmed release даже при completion/неизвестной physical quiescence; это не unknown commit. Ни один result не пишет OperationCancelled и не снимает holds.

Полный Error boundary — исключения, без альтернативных result DTO:

| Error | Условие |
|---|---|
| ValidationError | Malformed input до IO |
| PublicationInfrastructureError | Missing operation, stale fence, invalid/corrupt lifecycle binding, missing обязательная admission, contradictory facts, output correlation mismatch; unexpected infrastructure сохраняет cause |
| UnknownCommitOutcome | Нельзя подтвердить transaction outcome либо quarantine по existing UOW policy; result отсутствует, возможный commit не отрицается |
| CancelledError | Invocation cancellation; provisional result не выдаётся, rollback не предполагается |
| OperationBusyError | Existing evidence/dependency отказал; распространяется без преобразования в close proof |

Confirmed rollback сохраняет исходную typed ошибку и не превращается в Unknown автоматически. Unknown означает неизвестный исход. Любой Busy, в том числе посторонний, независимо от класса/текста/args НЕ proof close и НЕ запускает inventory или finalization. После lost ACK повтор exact request заново проверяет authority; допустимы Pending/Ready/Terminal либо stale/error, без reopen и bump fence.

Exact передача для Pending(FULL_STAGE/BOTH): `inventory_request: OperationCloseInput = close_result.request`; явный DAG CALL `StageAttemptService.pending_finalizations(inventory_request) -> OperationStageFinalizationResult`. Только batch предоставляет `pending: tuple[StageFinalizeInput, ...]`; `batch.request == close_result.request`. Каждый готовый item целиком передаётся отдельным public CALL `StageAttemptService.finalize_execution(item)`. Refused/exception не предоставляет partial batch. Artifacts заново проверяет current closed/fence и полный inventory в coherent scope; historical binding/generation восстанавливает сам, без подмены historical fence текущим request.fence.

LOCAL_WRITERS не запускает stage finalization. BOTH дополнительно требует local drain. Ready ведёт к existing cancellation handling с финальным recheck всей operation. Terminal не даёт автоматического inventory; если terminal наступил после Pending, Artifacts применяет свой terminal/residual inventory контракт. Fence change даёт owning refusal, DAG не ищет новый fence. Empty batch или отдельный finalized result не разрешают release/terminal всей operation.

Границы ответственности: Input — identity запроса, variants/enums — подтверждённые observations, existing OperationRecord — terminal без mirror DTO; Ledger — validation/correlation/delegation; IArtifactLeases/SqliteArtifactLeases — lifecycle UOW/ack; drain adapter — authoritative predicate; Artifacts service/store — inventory и отдельная finalization; DAG — выбор CALL и перенос owning POJO. Критерии отказа: CLOSED до commit, stage inventory в Publication, synthetic lease, DAG storage reads, foreign public service calls, hidden callback/worker orchestration, Busy→finalization или смена утверждённого порядка. Новые NodeId/маршрут не назначаются, штатный blocking cancel неизменен.

Статус: Publication Q5 предъявлен для общей приёмки; не PASS всей цепочки и не code-go. Локальная синхронизация имён не закрывает Q1–Q4/Q6 и physical proof. Общая проверка через назначенного координатора Between domain operations и решение пользователя остаются обязательными; пакет предоставляется пользователю для этой приёмки.

### RC02 — один exact close → inventory mapping

2026-11-26. После пользовательского «1. Ок» принят выбор формы для синхронизации документов: `OperationLedger[R].close_for_cancellation(OperationCloseInput) -> OperationCloseResult[R]` возвращает **OperationClosePending(request: OperationCloseInput, pending: OperationDrainPending)**. Existing proposed discriminator kind сохраняется. Input и Output POJO находятся в proposed `app.dataModel.publication.operationClose`; StageBinding/список stages в Publication не вводятся. Это не приёмка полного workflow и не code-go.

Matching public consumer из Artifacts owning resolution RC-02: `app.application.artifacts.staging.stageAttemptService.StageAttemptService.pending_finalizations(request: OperationCloseInput) -> OperationStageFinalizationResult` (async). Artifacts импортирует Publication Input напрямую. Единственный mapping: `pending_finalizations(close_output.request)`. Вызов — явный согласуемый DAG public CALL, не вложенный вызов Ledger/leases.cancel. Прежний OperationStageFinalizationInput(lease) отозван; дополнительный operand из continuation/storage не требуется.

Источник request — валидированный вход close с operation_id/fence, сверенными с persisted operation в той же close transaction. Output не создаётся при stale fence, missing/corrupt operation/admission или unknown close outcome. World/kind/preparation_fingerprint и historical fence для каждого StageFinalizeInput восстанавливает Artifacts из validated immutable StageBindingRow в своём coherent inventory scope; current request.fence не подменяет historical binding. Request не выдаёт writable permission и не обещает нынешний hold.

| Ветка / входной случай | Exact disposition |
|---|---|
| Pending FULL_STAGE/BOTH + подтверждённая существующая staging admission | output.request напрямую в pending_finalizations; consumer проверяет current closed/fence и полный inventory, включая старые generations/fences и completed executions без confirmed release |
| Pending LOCAL_WRITERS + существующая staging admission | Не является trigger stage inventory/settle; legacy local writer не превращается в fake stage. Local drain остаётся отдельным обязательным predicate Publication |
| Nonterminal direct operation без staging admission, local/full facts отсутствуют | OperationCloseReady(request); lease не синтезируется; путь — existing cancel финализации, НЕ pending_finalizations |
| Нет admission, но обнаружены local/full stage facts | PublicationInfrastructureError, без Ready/Pending и без synthetic lease |
| Ready для существующей staging operation | OperationCloseReady(request); inventory для продолжения этой cancellation не требуется, current drain повторно проверяет cancel; Ready не превращается в Pending и не требует достраивать lease |
| Existing terminal | OperationCloseTerminal[R](record), operation-level handling. В этой ветке close не утверждает закрытие admission/drain и не запускает inventory. Terminal не отменяет отдельную residual-cleanup обязанность Artifacts; автоматическое terminal→inventory данным ребром НЕ заявляется |
| Stale fence / missing operation / invalid binding | PublicationInfrastructureError нового close метода, не Busy и не typed stage refusal; существующий cancel не изменяется |
| Unknown/cancellation/иной Busy | Existing exception без CLOSED output; не основание inventory/settle |

Replay/races: повтор close после lost ACK заново читает authoritative state и может вернуть Pending, Ready либо Terminal; не выдаёт новый lease fence. Artifacts не доверяет прошлому Pending при intervening cancel/fence change: его own current-state admission остаётся обязательным. Inventory output относится ко всей operation; пустой список не доказывает отсутствие неучтённых local effects. Publication final cancel проверяет full/local drain в final UOW, не принимает portable inventory как permission release.

Ответственности: lifecycle adapter подтверждает request в своей close transaction и возвращает только после confirmed commit; Ledger проверяет id/fence корреляцию и typed result; DAG передаёт request целиком, затем каждый готовый batch.pending item в finalize_execution; Artifacts проверяет текущее состояние и полноту execution inventory и формирует полные StageFinalizeInput. Критерии отказа RC02: два публичных формата Pending, synthetic поля, DAG storage reads, implicit continuation, выбор ветки по тексту Busy, прямой foreign public call, terminal/Ready притворяются cancellation settlement proof. **RC02 формы Output→Input синхронизированы с Artifacts RC-02; общая приёмка маршрута остаётся у координатора и пользователя, runtime не реализован.** Blocking cancel этапа 1 не меняется.

RC04: Publication не владеет OS locks. Existing scope reuse не доказывает совместимость OS→SQL и SQL→OS lock order; до owning Artifacts сверки такой порядок не объявляется безопасным. Второй coordinator/ambient transaction workaround не добавляется; дополнительных изменений scope contract здесь нет.

Остаток этапа 2 имеет две конкретные owning границы. (1) Constructor SqliteStageAttemptStore(scopes, operations, catalog, stage_drain=...) ниже покрывает stage-1 SQL authority, но не предъявляет получение backend/effect gate для settle. Artifacts должен замкнуть exact dependencies и nested cleanup calls с учётом обратной зависимости backend.attempts, без dependency cycle и foreign public service. Этот constructor не является PASS всей stage-2 composition. (2) Existing ArtifactStagingService.verify → catalog.guard → registry.verify удерживает SQL guard при physical verify; Artifacts должен предъявить совместимый trace этого consumer и authorized OS→SQL пути, сохранив holder/GC predicates. Publication не разрешает ожидание OS gate под SQL UOW. Эти OPEN не меняют штатный blocking cancel этапа 1 и не устраняются одной синхронизацией POJO.

### P1.3 — explicit close result для workflow этапа 2

2026-11-26. **Прежняя shorthand Busy → settle НЕПОЛНА и не является принятым mapping.** OperationBusyError разных sites не доказывает confirmed close или потребность settle. Ни текст, ни args, ни сам класс Busy не выбирают этот маршрут. Ниже новая узкая owning PROPOSAL только этапа 2; blocking cancel этапа 1 и его return/error semantics НЕ меняются. Новых нод/NodeId/CALL этим документом не назначается.

Предлагаемый публичный метод existing `app.application.publication.service.operationLedger.OperationLedger[R]`:

```python
async def close_for_cancellation(
    self, request: OperationCloseInput,
) -> OperationCloseResult[R]: ...
```

Новый owning модуль данных `app.dataModel.publication.operationClose`. Все POJO strict/frozen/extra-forbid/revalidate always; required поля без defaults. Existing OperationRecord[R], EntityUid и strict positive fence переиспользуются, StageBinding/StageWriteClaim сюда не копируются.

| Тип | Все обязательные поля |
|---|---|
| OperationCloseInput | operation_id: EntityUid; fence: Annotated[StrictInt, Field(ge=1)] |
| OperationCloseTerminal[R] | kind: Literal[OperationCloseKind.TERMINAL]; record: OperationRecord[R] |
| OperationCloseReady | kind: Literal[OperationCloseKind.CLOSED_DRAINED]; request: OperationCloseInput |
| OperationClosePending | kind: Literal[OperationCloseKind.CLOSED_PENDING]; request: OperationCloseInput; pending: OperationDrainPending |

OperationCloseResult[R] — discriminated union этих трёх классов по kind. Owning StrEnum OperationCloseKind: TERMINAL="terminal", CLOSED_DRAINED="closed_drained", CLOSED_PENDING="closed_pending". Owning StrEnum OperationDrainPending: LOCAL_WRITERS="local_writers", FULL_STAGE="full_stage", BOTH="both". Exact enum/Python/JSON правила применять как к другим owning enums; wire IDs не назначаются. Terminal branch валидирует existing TERMINAL phase и non-null terminal; record сохраняет exact R/OperationCancelled/другие existing terminal alternatives, не второй terminal DTO.

Meaning: CLOSED_* означает confirmed commit закрытия admission для указанной operation/fence и scoped observation после проверки authoritative operation/local/full-stage state. Это историческое подтверждение результата вызова, не transferable authority; любой mutation consumer перепроверяет current binding/fence/phase. CLOSED_DRAINED позволяет предъявить existing cancel для финального operation результата, но сам не является OperationCancelled и не снимает holds. CLOSED_PENDING показывает классы незавершённых effects, не stage inventory и не обещание возможности безопасно завершить их. FULL_STAGE может включать неизвестную quiescence старой execution; это не unknown COMMIT и не доказательство process death.

Exact internal port в `app.application.artifacts.storage.artifactLeases.IArtifactLeases[R]` и concrete `SqliteArtifactLeases[R]` получает тот же async close_for_cancellation(request) -> OperationCloseResult[R]. Это operation lifecycle ownership Publication в existing storage placement, не публичный Artifacts stage call. Ledger validates request, делегирует и проверяет соответствие результата requested id/fence; новый service/owner loop не создаётся.

Owning contract порядка: validate request → в одной короткой operation write transaction проверить persisted integrity/binding/fence/terminal; existing terminal возвращается как Terminal без ложного утверждения close; для nonterminal подтвердить допустимость отмены existing evidence policy, закрыть admission (или проверить ранее закрытую) → проверить local/full-stage predicate в том же scope → сформировать provisional Ready/Pending → вернуть только после confirmed transaction acknowledgement. Не ждёт worker drain, не пишет OperationCancelled, не выпускает permit/generation, не снимает holds и не запускает settle. Отсутствие staging admission у direct operation не создаёт фиктивную lease row: Ready допустим лишь если authoritative operation policy исключает stage admission и writers отсутствуют; противоречивые facts — infrastructure.

Error boundary: malformed input → ValidationError; missing operation/stale fence/invalid lifecycle binding → PublicationInfrastructureError (для НОВОГО метода; existing cancel errors не переопределяются); unknown commit/rollback/quarantine → UnknownCommitOutcome без CLOSED output; invocation cancellation → CancelledError; другой OperationBusyError, если поднят existing evidence/dependency, распространяется без выбора settle; unexpected infrastructure сохраняет cause. Unknown не упаковывается в Pending. Exception output не является producer POJO. Возможный commit при потере ответа требует повторного exact запроса/owning observation, не предположения об отсутствии close.

Workflow mapping для согласования координатором:

| Выход public close operation | Допустимое значение для следующей границы, не назначение маршрута |
|---|---|
| Terminal | Existing record/outcome для operation-level обработки; не доказательство full-stage drain и не автоматический settle |
| ClosedReady | Тот же request.operation_id/fence для existing cancel finalization; current facts перепроверяются |
| ClosedPending(LOCAL_WRITERS) | Нет основания вызвать exact stage settle: stage из local writer не угадывать |
| ClosedPending(FULL_STAGE/BOTH) | Основание запросить у Artifacts ПОЛНЫЙ актуальный operation-level inventory незавершённых stage executions; НЕ основание сразу выбрать один stage или считать settle безопасным |
| Busy / Unknown / иной exception | Отдельная error handling ветвь; никаких derived close/settle claims |

**Актуальная P1 Output→Input поправка 2026-11-26:** Pending и Ready сохраняют OperationCloseInput request. В close UOW обязательны record.operation_id==request.operation_id и record.fence==request.fence; Pending допускается только при согласованной staging admission. Отсутствие admission при stage effects — infrastructure inconsistency. Provisional output выдаётся после confirmed commit; Ledger проверяет output.request == input. Прежнее предложение lease-поля отозвано. Direct operation не получает synthetic lease.

Единственный exact mapping: `OperationClosePending.request → StageAttemptService.pending_finalizations(request)`; результат `OperationStageFinalizationBatch.pending` содержит готовые `StageFinalizeInput`, каждый передаётся в `StageAttemptService.finalize_execution(item)` целиком. Refused не выдаёт частичного списка. Artifacts заново проверяет current authority/closed/fence и полный inventory; historical lease каждого item берётся из persisted stage binding. ClosePending(FULL_STAGE/BOTH) обосновывает inventory, LOCAL_WRITERS — нет. Unknown close не выдаёт Pending. Новые ноды/порядок этим mapping не назначаются.

Publication не добавляет stage IDs в result; DAG не читает SQL, operation record leased_artifacts или continuation для достраивания lease/поиска stage. Batch перечисляет stage executions, а не legacy local-only writers. Для BOTH Publication final guard учитывает local effects отдельно; даже полный stage batch не доказывает operation drain. После exact stage settlement Publication повторно проверяет ВСЮ operation перед release/terminal через existing cancel.

Acceptance этой дельты: output.request точно сохраняет checked input; stale fence/unknown commit не получают Pending; direct передача output.request не требует иных operands. Artifacts batch сохраняет world/kind/preparation/historical fence каждого binding, включает все unreleased acquired generations и не фильтрует по completion. Concurrent fence change даёт owning refusal; terminal не считается empty inventory. Python/JSON round-trip и общий coordinator mapping остаются проверками будущей реализации/приёмки, не runtime PASS.

Повтор close_for_cancellation после lost ACK идемпотентен относительно close; Ready/Pending могут меняться с текущим drain, eventual terminal возвращается Terminal. Closed не переоткрывается. Concurrent cancel может завершить operation после observation; next owning call должен корректно обработать terminal, не продолжать по старому portable результату. Exact terminal replay не изменяет stage history; residual cleanup после historical terminal — отдельный Artifacts inventory/settlement контракт, а не автоматическая интерпретация Terminal как Pending.

Responsibilities/приёмка: OperationCloseInput идентифицирует operation запрос, не authority; variants различают confirmed operation outcome без новых stage mirrors; Ledger — thin validated delegation; lifecycle adapter — одна close transaction с acknowledgement; drain adapter — read-only predicate; Artifacts — full inventory/settle. Отказ при raw Busy→settle, выдаче CLOSED до commit, terminal/refusal fabrication, private storage reads в DAG, новом owner loop или public foreign call внутри close/cancel.

**P1.3: формы Publication Output и Artifacts Input синхронизированы; общий workflow OPEN** до coordinator сверки и пользовательской приёмки всей цепочки. Artifacts inventory contract уже предъявлен в его RC-02, повторно объявлять его отсутствующим нельзя. Historical bounded-cancel proposal ниже не заменяет этот пакет и не даёт права менять этап 1. Тесты будущего этапа 2: Busy до close, unknown close commit, exact repeat, terminal before/after close, local-only/full/both, current fence change, неполный inventory не даёт release, terminal не маскирует residual cleanup. Сейчас только документ, runtime/schema tests не заявлены.

### Принятое пользователем разделение поставки — вариант 2, 2026-11-26

Пользователь выбрал «Ок, давай 2»: **поэтапное расширение существующих механизмов**. Это приоритетный scope над прежним предложением глобально заменить waiting cancel на busy-return. Выбор этапности не объявляет незакрытые контракты принятыми и не является code-go всех proposed классов.

**Этап 1 — штатная authorized запись.** Artifacts добавляет stage identity/authority, полный execution lifetime и exact durable completion; переиспользует existing backend worker drain, local writer protection, catalog predicates и transaction coordinator. Seal/hold/completion — один commit. Publication сохраняет waiting semantics cancel, расширяя его ожидание и финальную проверку на full-stage drain наряду с local writers. READY/release/terminal guards проверяют те же authoritative факты. Нового scheduler/worker-drain engine, второго seal алгоритма и глобального busy-return cutover нет.

Для этапа 1 existing цепочка ArtifactStagingService.cancel → OperationLedger.cancel → SqliteArtifactLeases.cancel и подтверждённое LEASE_RELEASED logging сохраняют waiting promise. Existing waiting tests сохраняются и расширяются full-stage gap cases; перечисленный ниже перевод этих tests на busy-return НЕ выполняется на этом этапе. Existing BusyError в иных guards/final recheck сохраняется, но не заменяет цикл ожидания штатной отмены.

**Этап 2 — automatic crash recovery.** Отдельно согласуются owning завершение старой execution, exact quiescence evidence, explicit DAG CALL/outcomes и способ выхода waiting cancel для этого маршрута. Предложение bounded cancel/busy-return ниже остаётся одним кандидатом этапа 2, не выбранной семантикой и не prerequisite этапа 1. До его принятия нельзя обещать автоматическое завершение cancel после crash или RUNNING→READY.

При process loss без proof состояние unresolved: retry/successor и release защищённых holds запрещены. Отсутствие restart proof не блокирует штатную запись, но live-worker drain/atomicity/negative fencing проверки этапа 1 обязательны. Историческое exact completion может подтвердить seal без обещания нынешнего hold; это не quiescence evidence.

Распределение владельцев неизменно: Artifacts — stage authority/backend/claim/completion; Publication — operation lifecycle/transaction acknowledgement; DAG — явные public вызовы и выбор продолжения. Дублирование verify/seal между ArtifactStageWriter и старым ArtifactStagingService устраняется reuse/cutover одного owning storage пути, не третьей копией predicates и не самовольным удалением старого public consumer. Inventory/retention/P2 ограничения ниже сохраняются.

### COMP04 / COMP05 — кандидат cutover этапа 2 и условия atomicity этапа 1

Источник распределения ответственности: [backend-fencing §8](artifacts-stage-recovery-backend-fencing.md). Publication owns operation lifecycle, несмотря на размещение SqliteArtifactLeases в artifacts storage. Artifacts owns full claim/backend/resource cleanup и seal/completion; координатор owns explicit DAG route. Ниже plan-only; одинаковая Python signature НЕ означает поведенческую совместимость.

#### COMP04: непринятый кандидат breaking delta для этапа 2

Предлагается единая bounded cancellation attempt для existing `cancel(operation_id: EntityUid, fence: int) -> OperationRecord[R]`: validate → первая owning transaction проверяет binding/fence/terminal и подтверждает close admission → без цикла ожидания одна финальная owning transaction rechecks current terminal/fence/closed/full+local drain → либо release+cancel terminal с confirmed commit, либо `OperationBusyError` без release/нового terminal. Две transactions сохраняют existing close-before-release boundary; отмена invocation/unknown между ними не откатывает уже подтверждённый close. Никаких sleep/timeout release, автоматического retry либо вызова public Artifacts completion из cancel.

Если этот кандидат будет выбран для этапа 2, его изменение затронет все consumers данного cancel API одним согласованным cutover, а не optional flag. Тогда ранее ожидавший caller должен будет уметь получить busy с оставшимися holds, и ожидание coroutine не будет обещать будущий OperationCancelled. Сейчас пользователь выбрал сохранение existing waiting semantics в этапе 1. Отдельный legacy waiting wrapper/скрытый retry не вводится; таблица ниже описывает только возможный будущий breaking cutover.

Return existing terminal сохраняется, включая терминал, отличный от OperationCancelled. Existing malformed/fence mismatch ошибки не нормализуются молча; raw unknown/cancel/infra сохраняются. Busy — не terminal и не proof close: класс также существует у иных sites, payload не добавляется. Caller не сериализует args и не считает busy cancellation success. Неподтверждённый исход commit/rollback не превращается в busy. Final transaction может ждать existing database gate; bounded attempt означает отсутствие lifecycle polling, а не таймаут SQL.

| Existing caller / контракт | AS-IS и exact cutover |
|---|---|
| `app/application/artifacts/storage/artifactLeases.py::IArtifactLeases[R].cancel` → `app/db/repositories/sqlite/artifacts/leaseStore.py::SqliteArtifactLeases[R].cancel` | Обновить documented waiting/error promise вместе с concrete реализацией; убрать only cancellation polling loop, сохранить close/final UOW, terminal/fence checks и confirmed acknowledgement |
| `app/application/publication/service/operationLedger.py::OperationLedger[R].cancel` | Сейчас validates id/fence и await leases.cancel. Сохранить delegation; объявить busy как достижимый исход незавершённой отмены. Не catch/retry/convert, не читать latest record вместо ответа |
| `app/application/artifacts/contracts/stagingPort.py::IArtifactStaging.cancel` → `app/application/artifacts/staging/artifactStaging.py::ArtifactStagingService.cancel` | Сейчас await ledger, model_validate record, при matching OperationCancelled emit LEASE_RELEASED. Busy выходит ДО record validation/log; LEASE_RELEASED нельзя emit на close/busy/unknown. Повтор после доказанного drain может вернуть terminal и emit по existing правилам; exactly-once logging не добавляется |
| `app/application/artifacts/logging/artifactLog.py::ArtifactLifecycleLog.emit` / ArtifactLogRecord | Не меняется sink policy. Post-terminal log fault не означает rollback; cancellation terminal/holds уже durable. Existing identity check до LEASE_RELEASED сохраняется |

По search `backend/app` concrete цепочка operation cancel — ArtifactStagingService → OperationLedger → SqliteArtifactLeases. Другие `.cancel()` в engine/worker/chat относятся к asyncio/checkpoint/request cancellation, не включаются в этот cutover. Новые consumers не подключаются по совпадению имени cancel.

**Existing tests, которые несовместимы с busy-return:**

- `tests/snapshotCore/storage/artifacts/test_leases.py::test_two_connections_cancel_while_owner_writes`: создаёт pending cancel и затем отменяет эту task; retry также запускается до выхода writer. Target: первый/ранний повтор получает busy, holds сохранены, admission закрыта; после выхода writer отдельный повтор получает matching terminal. Проверку invocation cancellation перенести на конкретную заблокированную DB acknowledgement boundary, не имитировать её удалённым sleep loop.
- `tests/snapshotCore/storage/artifacts/test_staging.py::test_cancel_drains_claim_and_gc_retains_until_release`: assert cancelling.done()==False и единственный await до terminal больше неверны. Target: busy без LEASE_RELEASED; GC retains; после release явный повтор cancel и existing log payload checks.
- В том же файле `test_cancel_drains_repeatedly_cancelled_placement_before_gc`: предположение pending cancel до release неверно. Target: busy operation cancel, но repeatedly cancelled stage task по-прежнему обязана дождаться physical worker/drain; GC не удаляет artifact; после drain явный cancel завершает operation. Не удалять эту physical-safety проверку ради зелёного теста.
- В том же файле `test_release_logging_requires_confirmed_matching_cancellation`, `test_release_logging_sink_failure_preserves_cancelled_result` и ledger cancellation validation cases: добавить busy no-log и сохранить mismatch/unknown/no false release assertions.
- `tests/snapshotCore/storage/artifacts/test_leases.py::test_cancel_reason_survives_reopen_and_repeat`, `test_cancelled_terminal_requires_released_holds_on_write_and_both_cancel_reads`; `tests/snapshotCore/storage/publication/test_claim_mapping.py::test_cancel_replay_preserves_absent_or_existing_request_binding`: terminal/exact-repeat сценарии не меняются; должны оставаться regression gates.

Тестовые fake stores в test_staging должны отражать новую семантику; fake waiting реализация не является evidence real storage. Required full-stage checks/composition из inventory ниже сохраняются. Migration охватывает contracts, adapters, facade docs и перечисленные tests одним срезом; нельзя выдать прежние passing waiting tests за совместимость. Фактических новых тестов здесь не запускали и код не меняли.

**COMP04 verdict: existing waiting semantics сохранены для принятого этапа 1; exact busy-return contract/caller delta предъявлена только как непринятый кандидат этапа 2.** Его выбор пользователем и общий DAG outcome mapping ещё нужны; explicit route не задаётся этой запиской. Штатная запись не зависит от принятия automatic crash completion; при сохранении waiting cancel нельзя заявлять готовность последовательного BF-01.

#### COMP05: только transaction/lifecycle compatibility

Existing `SqliteArtifactScope.transaction` может присоединиться к binding; safe reuse требует одного `scopes.bind(scope)` на owning seal transaction и отсутствия nested/reentrant bind. Proposed `seal_in_scope` принимает scope явно, проверяет его и не делает commit. `seal_stage` Artifacts владеет outer `SqlitePublicationCommitStore.transaction(operation_id)` и публикует ref после выхода с confirmed commit. Scoped ref до выхода provisional. Backend physical IO не объявляется частью этого SQL commit.

Publication conditions для Artifacts одного commit:

1. issued write scope task/connection/operation соответствует permit.binding.lease; exact claim/generation принадлежит Artifacts authority; operation binding/fence/PREPARING/open повторно проверены в этом UOW;
2. existing live LOCAL reservation writer и hold должны присутствовать при seal; full claim не заменяет их и не требует собственного drained состояния. Local release до seal запрещён. Release local claim не доказывает full drain;
3. sealed storage fact, требуемый operation hold и exact stage completion становятся visible вместе; completion не записывается как OperationRecord terminal, не меняет operation phase/fence и не расширяет R/PublicationResultBinding;
4. concurrent close vs seal определяется существующим transaction serialization: close первым — seal refuses, completion не создаётся; seal первым — historical completion сохраняется, cancel позже ждёт/проверяет full+local drain перед hold release;
5. fault до commit → rollback всех изменений этого UOW; reservation/physical effects предыдущих стадий могут существовать. Unknown acknowledgement → UnknownCommitOutcome, не success/absence/retry; confirmed completion не отменяется post-commit cleanup/log fault.

Common coordinator необходим, но недостаточен: обязательны same access/registry/scopes graph, exact scope operation, scoped admission rechecks и атомарное участие evidence persistence. Artifacts предъявляет exact storage implementation/claim/resource order; Publication не назначает stage SQL, таблицу или backend cleanup. Existing standalone seal плюс последующий evidence call не соответствует COMP05 даже при одном coordinator.

**COMP05 verdict: PASS TARGET transaction/lifecycle compatibility при этих условиях; actual integration/evidence OPEN за Artifacts и совместной приёмкой.** Никаких новых public междоменных вызовов или owner loops. Общий SR-03 этим локальным verdict не закрывается.

### BF-01: closed operation и отдельный DAG вызов завершения

2026-11-26. Сверен [backend-fencing §8/BF-01](artifacts-stage-recovery-backend-fencing.md). **PASS совместимости границ; конкретный automatic crash-completion маршрут остаётся OPEN.** Publication закрывает operation admission и завершает operation; Artifacts завершает старую stage execution и сохраняет authoritative drain evidence. Historical Confirmed/Refused из begin/recover не заменяют этот результат. Read-only StageExecutionDrain не получает mutation/worker-control.

Обязательный частичный порядок: confirmed close admission → явный DAG public CALL owning Artifacts завершения → Publication повторно проверяет current persisted full/local drain → release holds/OperationCancelled в одном final UOW. Закрытая admission препятствует новому stage/successor, но не owning cleanup уже принятых effects. Completion evidence не удаляется и operation terminal не меняется Artifacts-методом. Ноду/NodeId и точную Artifacts сигнатуру здесь не назначаем: их предъявляют владельцы. Это не разрешение прямого public Artifacts вызова из cancel.

**Доказанный AS-IS разрыв последовательного вызова:** SqliteArtifactLeases.cancel после close выполняет ожидание writers и не возвращает управление до drain/terminal. С расширенным full-stage predicate crash-orphan может оставить это ожидание незавершённым. Если DAG должен выполнить Artifacts завершение только ПОСЛЕ возврата этого CALL, порядок неработоспособен. Нельзя считать такое ожидание неявным запуском cleanup или добавлять параллельный owner loop.

**Минимальная Publication дельта на согласование для будущего crash-completion этапа:** сохранить сигнатуру `async OperationLedger[R].cancel(operation_id: EntityUid, fence: int) -> OperationRecord[R]` и storage delegation, но разрешить после confirmed close и одного authoritative full/local drain observation вернуть управление через existing `OperationBusyError`, если drain ещё не подтверждён. Тогда действие DAG по busy — отдельный разрешённый Artifacts завершительный CALL, затем повтор того же cancel(operation_id,fence). Ни автоматического вызова Artifacts, ни скрытого retry, ни нового cancel DTO. Это ЯВНАЯ proposed смена waiting behavior для этого контракта; пока не принята, existing cancel не объявляется готовым для последовательного BF-01 маршрута. Вариант не ограничивать ожидание, а запустить второй параллельный cleanup loop здесь не предлагается.

OperationBusyError сам по себе НЕ доказывает confirmed close: этот класс уже используется другими sites. Если нужно доказательство close для Artifacts входа, owning метод должен проверить актуальное persisted closed admission самостоятельно через свой storage boundary. DAG не извлекает authority из exception args и не получает scope/connection. Для unconfirmed close распространяется UnknownCommitOutcome; разрешённое дальнейшее действие не выводится из предположения «close наверняка состоялся».

После Artifacts результата Publication не доверяет portable bool/ref или прошлому read: final cancel UOW повторяет exact operation/fence/terminal и closed/full/local drain guards. Busy — release/новый terminal не выполняются; unknown — никакой компенсации, hold release или утверждения absent effects. Повтор cancel при existing terminal возвращает historical terminal по прежнему контракту; это НЕ подтверждение отсутствия остаточного cleanup. Если residual execution возможна после historical stage Confirmed/operation terminal, отдельный Artifacts завершительный вызов остаётся допустимым по owning контракту, без переписывания terminal.

Нужные проверки будущей реализации: cancel close подтверждён, process loss оставил consumed claim; cancel отдаёт busy без hold release; DAG вызывает реальный owning completion без successor/reopen; повтор cancel получает актуальный drained state и завершает operation; unknown close/drain/release не понижается; historical Confirmed с незавершённым cleanup не считается drained. Automatic crash recovery остаётся отдельным этапом и не блокирует независимую штатную запись с full live claim/drain/atomic seal.

Изменения этой записки не переоткрывают принятую P2 поправку: stateless drain wrappers могут различаться object identity при общем exact access/registry/coordinator и predicate. StageAttemptStore получает required stage_drain и сам drain adapter не реализует.

### Review P2: identity drain adapter и отдельный crash-recovery этап

2026-11-26. Проверено требование одного object instance SqliteStageExecutionDrain. Этот adapter пока PROPOSED; runtime реализации для проверки statefulness нет. В предъявленном constructor единственная зависимость — ScopedSqliteAccess; собственные cache/locks/claims/epoch/policy не объявлены. Existing ScopedSqliteAccess проверяет scope через свой registry перед/после IO; authority хранится в registry/transaction и authoritative Artifacts state, не в identity read-only drain wrapper.

**Результат:** для двух stateless экземпляров exact одного owning adapter с одним и тем же access и единым predicate нарушения invariant не выявлено. Они могут наблюдать разные состояния при разных scopes/времени, но один экземпляр наблюдал бы их точно так же. Atomicity обеспечивается scoped повторной проверкой в transition transaction, а не singleton adapter. Исходное требование одного экземпляра было избыточным усилением composition.

**Принятая P2 поправка плана, 2026-11-26 («Правим»):** требование `drain_a is drain_b` снято. Сохранены required dependency без default; exact owning implementation; `drain.access is consumer.access`; общий registry/coordinator graph; отсутствие mutable per-instance state и hot-rebind; единый authoritative predicate и переданный scope. Разные adapter objects с этими свойствами допустимы. Если Artifacts добавит stateful claim authority, cache или policy, потребуется заново предъявить её ownership/identity гарантию; такое состояние не считается частью нынешнего read-only wrapper по умолчанию. Это принятие поправки документа, не runtime/code-go.

Будущий тест принятой поправки: два независимо созданных stateless drain adapters на одном access дают одинаковое решение для одного stable scope/state; чужой access/registry отклоняется; scoped transition recheck ловит изменение authority независимо от числа adapters. Не ослабляются identity требования к самим scopes/access/coordinator, backend write admission и runtime StageWriteClaim. Constructor/composition требования ниже синхронизированы; singleton restriction больше не действует.

**Приоритетная граница пользователя:** automatic crash recovery выделен в отдельный этап. Отсутствие доказанного restart quiescence не блокирует независимую штатную authorized запись с настоящими acquisition/full-claim/worker-drain/atomic seal/evidence checks. В штатной поставке process loss либо непроверенная остановка оставляют stage Unresolved; safe retry, выпуск successor и release защищённых holds без proof запрещены. Lost ACK с уже доказанным completion может дать historical Confirmed, но отсутствие completion не доказывает отсутствие effects. Требования ниже к crash-proof относятся к acceptance automatic recovery, не к blanket gate штатного stage. Live cancel/READY/drain guards остаются обязательными для штатной записи.

Приоритет уточнения inventory/retention ниже: конкретные existing callers/factories перечислены; circular ownership quiescence снят в пользу Artifacts; cleanup не разрешает deletion stage evidence. После этого остаток SR-03 — согласование Artifacts реализации единого predicate/representation и предложенных required constructor/scoped seal дельт. Упоминания «inventory ещё требуется» в первоначальном тексте ниже означают необходимость проверки будущего cutover, а не отсутствие текущего списка.

**SR-03: OPEN общей приёмки; конкретная Publication TARGET-граница предъявлена ниже.** AS-IS несовместим с обещанием полного stage drain. Закрытие требует сверки этих портов с параллельным Artifacts resolution и consumer inventory переходов, не просто общего coordinator. Runtime PASS не заявляется. Реализация generator/gameplay, новый DAG route и полный Source/Pack completion OUT.

## Источники / AS-IS

- `backend/app/application/artifacts/staging/artifactStageWriter.py`: write последовательно reserve → backend.write → локальный writer → verify/seal; full-stage claim отсутствует.
- `backend/app/db/repositories/sqlite/artifacts/leaseStore.py`: SqliteArtifactLeases.finish_preparation проверяет catalog._writers, exact holds/sealed, закрывает admission и пишет READY. cancel закрывает admission, ждёт _writers вне write transaction, затем повторно проверяет fence/terminal/writers и снимает holds/пишет terminal. Этого недостаточно для промежутка между backend write и seal.
- `backend/app/db/repositories/sqlite/artifacts/catalogStore.py`: reserve и seal используют SqliteArtifactScope.transaction; seal требует локальный reservation writer и operation hold. Новая generation/completion ими не проверяются.
- `backend/app/db/repositories/sqlite/artifacts/access/artifactScope.py`: bind позволяет scoped storage access; не является разрешением публиковать промежуточный результат.
- `backend/app/db/repositories/sqlite/snapshotCore/commitScope.py`: SqlitePublicationCommitStore.transaction(operation_id: EntityUid) -> AbstractAsyncContextManager[CommitScope], confirmed commit/rollback, quarantine/UnknownCommitOutcome, scope revoke.
- `backend/app/db/repositories/sqlite/shared/capabilities/scopeRegistry.py`: check/operation_id проверяют issued scope, task, connection, lifetime/write authority.
- `backend/app/application/publication/service/operationLedger.py`: operation observation/recover/cancel, не stage-retry decision.
- [Обязательные критерии](../rules/dag-generator-interface.mdc), [правило координации](../rules/interdomain-contract-coordination.mdc), AGENTS.md; [Snapshot ТЗ](../../docs/tz_world_snapshot.md) — transaction/terminal/unknown semantics. Ни факт чтения этих источников, ни эта записка не являются приёмкой всего домена.

## Конкретные TARGET порты

Все нижеследующие additions PROPOSED. Existing OperationLeaseRef, StagingReservation, ArtifactRef, CommitScope/CommitReadScope переиспользуются; public permit/generation/error roster принадлежит Artifacts и здесь не дублируется.

`application/artifacts/storage/stageAttemptStore.py::IStageAttemptStore`: сигнатуры разделены по этапам согласно Artifacts owning resolution, разделам «Этап 1» и COMP-02/05. Документальная синхронизация по поручению пользователя 2026-11-26; зависимая реализация этапа 2 этим не разрешается.

```python
# Общий full-stage context обоих этапов.
def claim_stage(self, permit: StageAttemptPermit) -> AbstractAsyncContextManager[StageWriteClaim]: ...

# Этап 1: existing local writer удерживается вызывающим writer при verify/seal.
async def seal_stage(self, claim: StageWriteClaim, reservation: StagingReservation) -> ArtifactRef: ...

# Этап 2: замена сигнатуры после отдельного согласованного cutover.
async def seal_stage(self, claim: StageWriteClaim, local: StageLocalWriter,
                     reservation: StagingReservation) -> ArtifactRef: ...
```

Это последовательные версии одного internal port, не overload и не optional local/fallback. В этапе 2 ArtifactStageWriter получает `local` из `IStageAttemptStore.local_writer(claim, reservation) -> AbstractAsyncContextManager[StageLocalWriter]` после reserve и удерживает один context через write_authorized → verify_authorized → seal_stage. Backend повторно local claim не приобретает. Этап 1 сохраняет два existing local участка и двухаргументный seal.

`StageLocalWriter` — Artifacts-owned issued runtime handle в том же internal модуле stageAttemptStore, связанный с exact existing ArtifactWriterClaimRow, reservation и full claim. Его не создают caller/DAG и не добавляют в public Input/Output/Error. В этапе 2 seal_stage внутри общего UOW проверяет exact linked live local row, generation/full claim и reservation; foreign/released/mismatched handle отвергается как ArtifactStorageInvariantError по owning Artifacts контракту. Local/full release выполняется после соответствующего drain; closed settlement не вызывает seal и не создаёт completion. Отсутствие этой связи или освобождение local до seal означает отказ в приёмке.

`StageWriteClaim` — issued runtime capability Artifacts; не DTO/node payload, не второй durable token. Exact representation определяет Artifacts. Его lifetime покрывает reserve/write/verify/seal и drain workers до release. Не разрешает bypass operation fence/closed admission.

Дополнительный узкий внутренний lifecycle порт в том же модуле:

```python
class IStageExecutionDrain(Protocol):
    async def is_drained(self, scope: CommitReadScope, operation_id: EntityUid) -> bool: ...
    async def assert_drained(self, scope: CommitScope, operation_id: EntityUid) -> None: ...
```

Owner — Artifacts. Concrete `db/repositories/sqlite/artifacts/stageExecutionDrain.py::SqliteStageExecutionDrain(access: ScopedSqliteAccess)` реализует IStageExecutionDrain; SqliteStageAttemptStore реализует authority port и получает required drain dependency, но не является drain adapter. is_drained возвращает True только после подтверждения отсутствия способности всех stage generations операции продолжать effects; проверяет authoritative full-stage state, не только старые локальные claims. Unknown/corruption не возвращают False/True, а распространяются. assert_drained проверяет тот же predicate в указанном write scope: при подтверждённом busy — existing OperationBusyError; invalid scope/corruption — PublicationInfrastructureError; unknown/cancel без изменения категории. Новый refusal POJO для внутреннего drain не нужен.

TARGET storage primitive `SqliteArtifactCatalog.seal_in_scope(scope: CommitScope, reservation: StagingReservation) -> ArtifactRef` (async) сохраняет existing seal predicates и effects, но НЕ открывает/закрывает transaction и НЕ выдаёт confirmed outcome: возвращённый ref provisional. Existing seal может делегировать ему из собственной transaction; authorized stage вызывает его только из seal_stage. Это не новый public pipeline и не перенос holder SQL в Publication.

Durable completion write остаётся внутри SqliteStageAttemptStore за его seal_stage, в том же scope. Отдельный public completion writer или сериализуемое evidence из Artifacts в Publication не вводится. Method/class владельца evidence назван; внутренний SQL/таблица и отдельный repository не назначаются.

## Constructor graph и authority

Предлагаемый exact concrete constructor:

```python
SqliteStageAttemptStore[R](
    scopes: SqliteArtifactScope,
    operations: SqliteOperationStore[R],
    catalog: SqliteArtifactCatalog,
    *, stage_drain: IStageExecutionDrain,
)
```

Объект использует scopes.commits/access и catalog operationArtifacts; не принимает второй coordinator, callback или independently committing evidence service. При необходимости отдельного persistence collaborator Artifacts обязан предъявить его exact constructor и same-scope binding до принятия, а не добавить молча.

TARGET SqliteArtifactLeases[R] constructor сохраняет scopes/operations/artifacts и получает required keyword `stage_drain: IStageExecutionDrain`; target SQLite composition допускает exact stateless SqliteStageExecutionDrain с тем же access/registry/coordinator. Identity между самими drain wrappers не требуется. Optional/no-op default запрещён. Не создавать dependency cycle: drain зависит только от access, stage store не зависит от leases/public lifecycle service; owning stage admission использует internal scoped catalog/operation checks.

Fail-fast identities внутри SQLite adapter layer:

- stage_store.scopes is leases.scopes is catalog.scopes;
- общий operations, общий access; operations._commits is scopes.commits; operations._access is scopes.access;
- catalog._operations is operations; catalog._access is scopes.access; catalog._artifacts is operations._artifacts; artifact reader._access is scopes.access;
- access.registry is commits.registry; internal leases catalog имеет тот же scopes/operations/access/artifact reader;
- leases.record_model is operations.record_model is operations.result_binding.record_model; existing codec/store/ledger identity checks сохраняются;
- stage writer, backend admission и lease adapter имеют существующую проверенную identity graph; full-stage store связывается с этой же graph, не с отдельным lease adapter.

Имена private links выше — проверка concrete adapter composition, не public properties нового protocol. Generic writer/Engine/Source их не читает. Same database path/equal DTO недостаточны. Проверять подмену каждого элемента до IO. Scoped methods дополнительно используют registry.check(scope, True) и registry.operation_id(scope); authority не следует из constructor identity одной лишь.

## Порядок и совместимость lifecycle

1. claim_stage consumption: в короткой owning transaction проверить operation/admission integrity, binding/fence/PREPARING/open и актуальный permit, затем зарегистрировать полный execution claim до первого reserve/physical effect. Выдать handle только после confirmed acquisition. Lost ACK acquisition не означает отсутствие claim.
2. Writer выполняет reserve/write/verify/seal в lifetime этого claim. Этап 1 сохраняет existing локальные backend/seal участки; этап 2 по COMP-02/05 Artifacts заменяет их одним local_writer context с explicit StageLocalWriter, передаваемым в seal_stage. Это отдельный cutover, не изменение этапа 1. Full-stage и локальные claims различаются по роли. Не считать собственный full-stage claim конкурентом при seal; не ослаблять existing reservation-writer predicate.
3. finish_preparation: внутри одной transaction перед READY проверяет И existing локальные writers, И stage_drain.assert_drained(scope, oid), затем exact holds/sealed, close admission/READY. Блокирующего ожидания drain внутри transaction нет. Если stage ещё active — OperationBusyError, не READY. Issued, но ещё не consumed permit сам по себе не active writer: READY может закрыть admission, после чего consumption обязан отказать.
4. cancel: подтвердить close admission в existing первой transaction; ждать оба множества claims вне write transaction. stage_drain.is_drained использует текущий read scope. В финальной transaction повторить terminal/fence, closed admission, локальный drain и full-stage assert_drained ДО release holds/cancel terminal. Новая generation после close не выдаётся/не потребляется. Не добавлять второй background owner: это расширение existing cancel drain loop.
5. Любое разрешённое изменение operation fence и любой путь в READY/terminal, освобождающий stage-protected holds, обязаны использовать тот же scoped drain predicate до перехода. Stale fence сам по себе не доказывает остановку physical worker. Конкретный inventory всех transition callers должен быть сверен перед cutover; существующему recover не добавляется takeover по отсутствию локальных claims.
6. Закрытие admission во время stage запрещает дальнейший seal, но не прерывает cleanup/drain. Full claim выпускается только когда workers остановлены и нет отложенного эффекта. Unknown release сохраняет uncertainty; ни cancel, ни recovery не объявляют quiescence по timeout/отсутствию старых writers.

## Один commit seal / hold / exact completion

seal_stage открывает existing scopes.commits.transaction(binding.lease.operation_id). Внутри: issued claim и exact generation/binding; current operation/admission/fence; reservation/ref; existing live local writer/hold predicates; scoped seal; обеспечение требуемого operation hold; durable exact completion evidence stage/generation/ref в ЭТОМ scope. Completion evidence не является operation terminal и не расширяет PublicationResultBinding[R].

Physical write/verify уже завершены под full claim; SQL transaction не держится на всём IO. После выхода с confirmed commit возвращается ref; затем full-stage context выполняет cleanup. При ошибке до commit rollback отменяет seal/evidence изменения вместе (предшествующая reservation/hold могла существовать и не объявляется отсутствующей). При unknown никакой success/absence/компенсационный release не выводится. Lost ACK после commit восстанавливается по exact Artifacts completion evidence, даже если последующий cancel снял current hold. Post-seal logging fault не отменяет completion.

Запрещено: standalone catalog.seal с последующей записью evidence; две transactions; прямой вызов Publication public recover/stage service из adapter; выдача provisional ref как confirmed; восстановление completion по одному sealed descriptor.

## Inventory затронутых ролей и критерии отказа

| Класс/семейство | Ответственность / допустимая дельта | Отказ при приёмке |
|---|---|---|
| StageAttemptService, StageAttemptPermit и outcomes (Artifacts proposal) | begin/recover decisions, typed binding/generation; roster у Artifacts | Publication-копия POJO/service или evidence boolean без authority |
| IStageAttemptStore / SqliteStageAttemptStore[R] | Full execution authority и atomic seal/evidence, shared transaction infrastructure | Независимый commit evidence, claim gap, callback в другой public pipeline |
| IStageExecutionDrain | Scoped full-stage quiescence | True по отсутствию только локальных claims; скрытый wait/commit |
| StageWriteClaim | Issued runtime lifetime, не durable wire | Forgeable DTO принят как authority; release до worker drain |
| StageLocalWriter (только этап 2, Artifacts storage.stageAttemptStore) | Issued handle exact local acquisition/reservation/full claim; передаётся writer → seal_stage в одном local lifetime | Public/wire carrier, foreign/released handle, повторный backend acquire или local release до seal |
| ArtifactStageOpenPipeline / ArtifactStageWriter | Existing linear admission/descriptor/write; full claim вокруг всего stage | Orchestration recovery loop, optional permit bypass |
| ArtifactInputAdmission / ArtifactDescriptorBuilder | Existing pure checks | Новые storage/recovery обязанности |
| ArtifactFormatRegistryBinding / ArtifactFormatContract / ArtifactBackend | Binding/physical IO, existing worker claims/drain | Hot rebind, другой admission graph, скрытая запись completion |
| SqliteArtifactLeases[R] / IArtifactLeases[R] | Operation lifecycle, расширение drain consumer; public signatures finish/cancel не меняются | READY/cancel release при active full-stage claim |
| SqliteArtifactCatalog | Scoped reserve/seal predicates/storage facts | Новый lifecycle decision или собственный commit в seal_in_scope |
| SqliteArtifactHolders / SqliteOperationArtifacts | Existing hold chain/active refs primitives | Fork holder representation либо current refs как completion proof |
| SqliteOperationStore[R] / SqlitePublicationEvidence[R] / StoredTerminalCodec[R] / PublicationResultBinding[R] | Existing operation binding/terminal integrity | Stage evidence как новый terminal R, ослабление existing checks |
| OperationLedger[R] / ArtifactStagingService | Existing operation observation/delegation | Operation recover выдан как stage retry permission |
| SqliteArtifactScope / ScopedSqliteAccess | Same-scope access, scoped binding | Nested owning transaction/foreign scope accepted |
| SqlitePublicationCommitStore / SqliteScopeRegistry / SqliteTransactionDriver / GuardedConnection | Existing transaction/ack/lifetime/quarantine | Второй transaction engine, false confirmation, wait drain под write lock |
| Composition factories и lifecycle callers | Передать единственный graph и required drain | Неучтённый caller/default обход; конкретный caller inventory ещё требуется |

Не все эти классы требуют изменения кода: таблица включает reachable неизменные зависимости и зоны проверки. Конкретные backend specializations и factory consumers перечисляет Artifacts owning resolution; эта записка не выдаёт generic PASS любой регистрации.

## Обязательная приёмка / остаток

### Уточнение owner inventory и retention — 2026-11-26

Сверен [Artifacts owning resolution](artifacts-stage-recovery-owning-resolution.md), §§4–8. **Quiescence после process loss принадлежит Artifacts**: Publication не выдаёт proof по времени, operation phase или отсутствию local claims. Publication предъявляет обязательных consumers этого predicate ниже. Формулировка §8 Artifacts о получении quiescence от Publication не соответствует варианту A; её изменение выполняет владелец того документа.

Все пути ниже относительно `backend/`. Runtime поиск выполнен по `backend/app`, отдельно проверены composition fixtures; строки SQL, допускающие переход, не считаются реализованным caller.

| Concrete caller | Required TARGET full-stage check и последствия |
|---|---|
| `app/db/repositories/sqlite/artifacts/leaseStore.py::SqliteArtifactLeases.finish_preparation` | assert_drained(scope, lease.operation_id) вместе с local writers ДО close/READY в одной transaction. Busy → OperationBusyError, READY не пишется; unknown → propagate, не утверждать отсутствие transition |
| Тот же файл, `cancel` | После confirmed close ждать is_drained и local writers вне write UOW; в финальном UOW assert_drained до hold release и terminal. Busy при recheck → OperationBusyError, без release; unknown → propagate, не compensation |
| Тот же файл, `open_operation` | Новая операция fence=1; existing branch не увеличивает fence и не reopened admission. Не превращать его в stage resume; full claim не снимается. Existing closed replay не означает writable grant |
| Тот же файл, `recover` | Observation; APPLYING/RECOVERY_REQUIRED → existing busy. Не выдаёт новую generation/fence и не освобождает stage claim. Quiescence не выводится из возвращённого record |
| Тот же файл, `_release` / `_cleanup` / `writer` | Это release ЛОКАЛЬНОГО writer claim, не operation hold/full-stage claim. Нельзя требовать full drain перед этим release: возник бы self-deadlock. После local drain full-stage owner продолжает/завершает свой lifetime; unknown local cleanup запрещает объявить full quiescence |
| `app/db/repositories/sqlite/artifacts/holderStore.py::SqliteArtifactHolders.release` — только OperationHolder branch | В borrowed/owning write scope assert_drained(operation_id) после closed/fence check и до append release; сохранить local writer check. Busy → отказ без release; unknown → propagate. ArtifactRetentionHolder release не становится operation cancellation; non-operation ветви не получают фиктивный operation ID |
| Тот же файл, `handoff` | После APPLYING/closed/lease validation и до первого destination append проверить full drain наряду с local writers. Busy → без handoff effects; unknown → propagate outer owner. Existing subset/retention semantics не расширяются |
| Тот же файл, `_release_pin` | Не operation hold; вызов из owning GC/pin cleanup сохраняет собственную authority. Не применяет operation drain по guessed ID; stage evidence не удаляет |
| `app/db/repositories/sqlite/snapshotCore/operations/operationStore.py::SqliteOperationStore.claim_publication` | Перед переходом READY→APPLYING scoped assert_drained. Нельзя полагаться лишь на старую проверку READY producer. Existing terminal/busy replay не меняет claims; для этих ветвей новый drain не prerequisite исторического replay. Busy перед переходом → OperationBusyError; unknown сохраняется |
| Тот же файл, `_save` через `record_terminal` и `record_refusal` | Для НОВОГО terminal assert_drained в том же write scope до terminal/event insert; exact existing terminal replay не требует нынешнего drain. Busy → новый terminal не пишется; unknown → propagate. Это не разрешает record_refusal при unknown rollback |
| `app/application/publication/service/operationLedger.py::claim_publication/record_terminal/record_refusal/cancel/recover` | Delegation к указанным owning stores; второй drain/latest read здесь не добавляется |
| `app/application/artifacts/staging/artifactStaging.py::finish_preparation/recover` | Existing delegation сохраняется; operation observation не заменяет stage recover. Вызов через legacy фасад не обходит новые guards storage layer |
| `app/db/repositories/sqlite/artifacts/catalogStore.py::seal` и proposed `seal_in_scope` | НЕ assert full drained: seal исполняется под собственным active full claim. Authorized путь вместо этого проверяет exact live claim/generation; generic standalone seal не должен стать обходом authorized evidence commit |
| Тот же файл, `mark_deleted` | Existing holds/local writers guards сохраняются; physical artifact GC не удаляет stage binding/predecessor/completion. Full-stage authority должна защищать effects до их reserve/hold; механизм конкретного Artifacts claim остаётся owning contract |

**Fence inventory:** actual `_event` в operationStore.py и trigger `publication_operation_events` в `app/db/migrations/0001_initial.sql` допускают recovery READY с fence+1, но runtime producer такого перехода в проверенном `backend/app` не найден. Нельзя назвать `_event` writer: это validator. Если producer добавляется, обязательны closed admission + full/local drain в том же transaction до bump; busy/unknown запрещают выдачу нового fence. Existing finish_preparation READY сохраняет fence, claim_publication APPLYING также его не меняет.

### Construction без dependency cycle

Для новых guards operationStore/holders требуется отделить read-only drain adapter от stage store, который уже зависит от operationStore. Предыдущее предложение передавать сам stage store всем consumers заменяется этим exact TARGET:

```python
# proposed module db/repositories/sqlite/artifacts/stageExecutionDrain.py
SqliteStageExecutionDrain(access: ScopedSqliteAccess)
# implements IStageExecutionDrain; no operations/leases/service dependency
```

Он проверяет authoritative full-stage state Artifacts через тот же access/scope. Отдельного registry/state machine или второго quiescence policy не вводит: predicate единственный, reused stage store и lifecycle consumers. Artifacts подтверждает его совместимость со своей durable representation; Publication не определяет query/SQL.

Required keyword `stage_drain: IStageExecutionDrain` получают concrete SqliteOperationStore[R], SqliteArtifactLeases[R], SqliteArtifactHolders и SqliteStageAttemptStore[R]; optional/no-op default запрещён. Concrete SQLite checks требуют exact stateless SqliteStageExecutionDrain с тем же access/registry/coordinator graph и единым authoritative predicate; отдельные экземпляры допустимы, mutable state и hot-rebind запрещены. Это явная constructor дельта, не public method signature change. Порядок assembly: scopes/access → drain adapters → operations/catalog → stage store → leases/holders → backend/writer. Так operations не зависит от stage store и цикл не образуется. Поля/методы самого IStageExecutionDrain выше неизменны.

Concrete composition sites:

- `app/core/container/packs.py::PacksWiring.initialize_pack_storage`: existing единственная найденная production сборка operations/leases; создать named scopes и stateless drain adapter(s) на общем access до stores, передать required dependency. Сейчас также содержит старый `StoredTerminalCodec()` без binding — existing отдельная проблема, не разрешение подставить mock production binding. Эта фабрика не доказывает регистрацию authorized stage.
- `tests/snapshotCore/support/fixtures.py::live_database`: общий operations graph — создать drain рядом с access и передать store; fixtures не должны получать fake True drain.
- `tests/snapshotCore/support/artifactFixtures.py::adapters`: holders/catalog используют общий access из test composition; отдельный stateless drain instance допустим при exact implementation и том же predicate/authority graph.
- `tests/typing/snapshotCore/valid.py::sqlite_composition` и constructor expressions SqliteArtifactCatalog/SqliteArtifactHolders/SqliteArtifactLeases в этом файле: отразить required typed dependency, без Any/cast/default.
- Direct test constructors SqliteArtifactLeases в storage/lifecycle tests должны получать тот же реальный drain из test graph. Это миграция тестовых consumers, не ещё одна production factory; обнаружение всех call sites повторить после параллельных изменений перед кодом.

Критерий отказа каждого перечисленного factory: иной access/registry/coordinator, не exact owning drain implementation, mutable drain state/hot-rebind, другой predicate, default bypass или цикл constructors. Различие drain object identity само по себе не является отказом. Backend registration/format factories, не создающие operation stores, лишь reuse готовые leases и не становятся владельцами drain.

### Q6 — окончательный release/terminal после finalization: контракт и владельцы

2026-11-27. Зафиксировано по запросу пользователя. Статус PROPOSED / общая приёмка OPEN; фиксация не является code-go или принятием всего workflow. Этот раздел сохраняет blocking cancel этапа 1 и не принимает исторический bounded/busy-return кандидат этапа 2.

| Область | Владелец / ответственность |
|---|---|
| Q6, operation lifecycle | Publication: окончательный release operation holds, terminal, cancellation authority и lifecycle guards; размещение SqliteArtifactLeases в artifacts storage не меняет владельца |
| Execution lifetime | Artifacts: full/local claims, physical drain evidence, finalization exact execution и authoritative scoped stage-drain predicate |
| Transaction infrastructure | Snapshot / transaction infrastructure: общий scope/coordinator, atomic commit, acknowledgement и UnknownCommitOutcome; не принимает решение о physical drain |
| Междоменная цепочка | DAG-координатор Between domain operations, thread 01a218a4-bfc5-7012-b18b-8ed986cc786d: сверка порядка явных вызовов, Output → Input и сквозных гарантий; не переносит доменные алгоритмы в DAG |
| Принятие | Пользователь: окончательное решение о контракте, границах поставки и разрешении реализации |

**Одна финальная transaction.** В existing SqliteArtifactLeases.cancel(operation_id, fence) до нового release/terminal повторно проверяются следующие facts в том же scope, где будут записаны mutations:

| Facts | Обязательное условие |
|---|---|
| Operation | Существует, immutable binding и persisted chain корректны, requested fence совпадает с current fence; stale fence не доказывает остановку effects |
| Terminal / authority | Authoritative terminal перечитан; для нового cancellation terminal повторены applicable existing cancellation evidence/phase guards; staging admission подтверждённо закрыта. Direct publication без staging lease сохраняет existing disposition |
| Все full claims | stage_drain.assert_drained(scope, operation_id) проверяет все stages/generations и historical acquisitions операции, не только последний batch/current generation |
| Все local claims | _catalog._writers(scope, operation_id) пуст, включая legacy local-only acquisitions без stage link |
| Full/local integrity | Releases соответствуют exact acquisitions; linked local/full release chains согласованы. Partial/mismatched chain — infrastructure/invariant fault, не drained |
| Holds | Перечитан полный current набор operation holds; catalog identities и holder chains корректны, active holds имеют допустимый fence. Список refs из finalization не подменяет этот набор |

После успешных checks: append release всех active operation holds → existing SqliteOperationStore.record_terminal(scope, OperationCancelled(reason=REQUESTED)) → один commit. Existing terminal invariants, включая отсутствие operation holds для OperationCancelled, сохраняются. Результат выдаётся только после confirmed commit. Отдельный precheck перед transaction недостаточен: close/acquisition/release/terminal сериализуются общим transaction graph. SQL не ждёт physical drain и не производит его evidence; Artifacts release обязан уже означать lawful завершение lifetime.

| Состояние / исход | Disposition Publication |
|---|---|
| Полный drain и confirmed commit | OperationRecord с OperationCancelled; operation holds released |
| Валидный historical terminal при допустимом fence | Existing terminal replay без перезаписи, в том числе не cancellation. Replay не доказывает residual cleanup и не запускает его; нарушение existing terminal invariants — fault |
| Full/local blocker | Никаких release/нового terminal. Штатный cancel ждёт оба множества вне write transaction; blocker в final recheck даёт existing OperationBusyError без final mutations |
| Unresolved finalization | Exact execution остаётся blocker до authoritative release; holds могут сохраняться бессрочно. Unresolved не преобразуется в operation success |
| Несколько stages / пустой inventory | Успех одного или последнего известного stage и пустой inventory не являются operation barrier; весь full/local набор перечитывается в final transaction |
| Legacy local-only writer | Самостоятельный blocker даже при пустом full inventory; завершается existing owning writer lifetime, без synthetic stage/link или forced release |
| Stale / malformed / corrupt | Existing validation/conflict либо infrastructure/invariant error, без новой mutation; не маскируется Pending/Unresolved |
| Unknown commit | UnknownCommitOutcome сохраняется; authoritative reconciliation exact release chain либо operation terminal/holds перед выводом об исходе. Ни rollback, ни success, ни компенсационный release не предполагаются |
| Invocation cancellation | Исходная категория сохраняется; confirmed close автоматически не откатывается. Повтор existing cancel не создаёт новую operation |

Concurrent close/finalization/cancel: close запрещает новый admission/consumption, но не owning завершение старой execution. Finalization commit первым позволяет final cancel увидеть drain; наблюдение blocker первым не позволяет release. Два cancel сериализуются, второй возвращает existing terminal. Historical completion без full release не разрешает новый terminal. OperationCloseReady/CLOSED_DRAINED — предыдущее observation, а не portable release authority; OperationClosePending/Ready не добавляются в result union existing cancel.

| Existing метод / consumer | Минимальная необходимая дельта |
|---|---|
| SqliteArtifactLeases.cancel, app/db/repositories/sqlite/artifacts/leaseStore.py | Сохранить close → blocking wait → final UOW; расширить wait/recheck full + local predicate, повторить closed/admission и applicable cancellation guards |
| SqliteArtifactLeases.finish_preparation | В existing READY UOW добавить full-stage guard к local writers/exact holds/sealed checks |
| Proposed IStageExecutionDrain / SqliteStageExecutionDrain | Один scoped authoritative full-stage predicate; required dependency общего graph, без no-op default, IO/commit/cleanup/wait |
| OperationLedger.cancel, app/application/publication/service/operationLedger.py | Existing validation/delegation; без public Artifacts calls или нового loop |
| IArtifactStaging.cancel / ArtifactStagingService.cancel | Сохранить blocking promise и LEASE_RELEASED только после confirmed matching cancellation; close/unresolved/unknown не считаются release |
| SqliteOperationStore.record_terminal / _save / record_refusal | Проверить отсутствие обхода общего guard при новом terminal; сохранить terminal identity и replay checks |
| Все release protected holds / fence transitions, SQLite composition | Тот же scoped guard до mutation; сверить полный caller inventory и общий access/registry/coordinator. SqliteOperationArtifacts.read остаётся чтением holds, не drain evidence |

**Проверки:** active full claim до local acquire и между local участками; два stages с одним unresolved; empty inventory + legacy writer; completion без full release; гонки на независимых connections close/consume/seal/finalization/cancel и два cancel; rollback всех final mutations при fault между hold release и terminal insert; lost ACK release/terminal и exact replay; historical terminal без изменения history/автоматического cleanup; foreign graph/scope. Existing blocking/repeated cancellation/GC retention tests сохраняются, не заменяются busy-return tests.

**Границы и OPEN:** никаких timeout release, прямого public Artifacts вызова из Publication, нового owner loop, новых DAG-нод или перестановки утверждённых действий. Artifacts завершает execution, Publication завершает operation, DAG выбирает явное продолжение. До общей приёмки нужны owning proof full release, полный inventory release/fence/terminal callers и координаторская сверка всей цепочки с решением пользователя. Пакет предъявлен через пользователя; межчатовая отправка этой фиксацией не разрешается. Код и runtime tests этим разделом не заявляются выполненными.

### Cleanup и retention: конкретный запрет удаления в этом срезе

В проверенном `backend/app` public operation purge/prune метода не найдено. `0001_initial.sql` содержит no-delete triggers для publication_operations/publication_operation_events. `SqliteArtifactLeases.cancel` снимает holds/добавляет terminal, НЕ удаляет operation history. `_cleanup` завершает execution claim, НЕ удаляет recovery evidence. Physical artifact GC — отдельная lifetime, не основание удалить stage history.

**TARGET обязательство Artifacts:** immutable StageBinding, generation predecessor links и exact completion evidence сохраняются после claim release, cancel, READY, operation terminal и physical artifact GC. Для всех поддерживаемых checkpoint replay этого достаточно для historical Confirmed; нынешний body/hold не обещается. Unknown и absence не смешиваются; отсутствие обязательных сохранённых facts — infrastructure/integrity fault либо owning untracked policy только для действительно никогда не зарегистрированного stage, не «безопасный новый begin» после очистки.

**Кто разрешает deletion сейчас: никто. Контракта deletion authority в этом срезе нет, удаление этих facts запрещено.** Это конкретная disposition, не TTL и не скрытый новый storage. Operation cancellation/terminal/cleanup не являются разрешением. Существующий append-only lifecycle не требует invent purge ради closure SR-03.

Если позднее потребуется удаление, это отдельная принятая cross-owner boundary: checkpoint/replay owner должен необратимо исключить все поддерживаемые ссылки и future resume к stage; Artifacts проверяет отсутствие активной authority/неразрешённого outcome и владеет удалением своих facts; Publication отдельно разрешает удаление operation history только по собственному будущему контракту. Ни одному owner нельзя самостоятельно вывести чужую replay retirement из terminal/возраста. Exact future deletion API здесь намеренно не назначается и не является prerequisite сохранения evidence в текущем срезе.

Следовательно retention compatibility этого среза закрывается правилом **retain, no deletion API**, а не ссылкой на неопределённый operation cleanup. Срок не ограничен новым TTL; изменение этой политики требует отдельного принятого контракта.

Три запрета DAG: новые ноды/порядок не назначаются; решения begin/recover передаются только явным будущим DAG public CALL, Engine не читает storage; внутренние scoped storage методы не выбирают следующую публичную операцию. Public stage input остаётся Artifacts-owned, scope/claim не входят в node POJO. Нет foreign public service calls через adapter.

CRUD: дельта не создаёт настройки/доменное хранилище общего назначения; scoped authority и seal используют owning storage. Новые public begin/recover и ошибки принимаются в Artifacts resolution, не заменяются этим документом. POJO reuse перечислен выше, новый mirror holder/ref/lease/terminal не вводится. Общая доменная CRUD приёмка здесь не заявляется.

Порядок existing stage/cancel/READY сохраняется с обязательным full-stage guard и единой seal/evidence boundary; изменение shared lifecycle consumer semantics требует сверки non-stage consumers. Неустранимые из Publication-части вопросы: (а) Artifacts exact full-stage quiescence proof/claim invalidation при crash и отмене acquisition; (б) совместимость proposed required drain/scoped seal с его конкретным constructor/store design; (в) полный перечень fence/READY/terminal/release callers и отсутствие обхода; (г) persistence representation completion, обеспечивающая тот же scope. Не назначать SQL/новый журнал вместо ответа владельца.

Acceptance evidence будущей реализации: race cancel/READY vs consumption; cancel во время physical IO; active full claim в промежутке без local claims; unknown acquisition/release; lost ACK seal; fault между scoped seal и completion; concurrent recover; foreign graph/scope/claim; old generation worker после fencing; unchanged non-stage lifecycle; ни одного committed seal без exact completion для authorized stage. Это тестовые требования, не замена архитектурной приёмки. До сведения Artifacts resolution и подтверждения всех callers SR-03 целиком OPEN.
