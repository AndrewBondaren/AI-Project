# Artifacts: ответственность DAG-нод и контракты оркестрации

Сверка 2026-11-28: [архитектурный пакет](artifacts-architecture-acceptance.md), §§2–3 конкретизируют output dependency и заменяют прежнее требование отдельного producer-reference checkpoint projection для batch. Prepared identity не меняется. Остаток приёмки перечислен явно в §6 пакета.

2026-11-27. PLAN-ONLY. По поручению пользователя сведены все рассматриваемые входы и три уровня оркестрации. Это дополнение к artifacts-stage-recovery-complete-chain.md, не реализация и не назначение production NodeId. Proposed имена двух новых parents ниже конкретизируют обсуждённую иерархию; общий architecture/code-go не объявляется. Physical host, SQL и публичные Artifacts contracts определяются основным планом и owning resolution. Новые producer/gameplay workflows OUT.

## 1. Архитектура семейства

Нейминг и вложенная структура согласованы пользователем 2026-11-27: `WorkflowNode` означает только оркестрацию CALL, остальные `Node` — ровно один public domain method/pipeline. Класс совпадает с именем файла в PascalCase. Суффиксы PublicNode/ParentNode не вводятся. Смена proposed имён не меняет контракты, порядок, NodeId/ContractId или статус реализации.

```text
application/engine/nodes/artifacts/
├── prepareAndStageArtifactWorkflowNode.py
├── prepareArtifactNode.py
├── stage/
│   ├── stageRecoveryWorkflowNode.py
│   ├── beginArtifactStageNode.py
│   ├── stageArtifactNode.py
│   └── recoverArtifactStageNode.py
└── finalization/
    ├── finalizeOperationStagesWorkflowNode.py
    ├── pendingFinalizationsNode.py
    └── finalizeExecutionNode.py
```

Показаны только ноды. POJO/bindings/registration остаются отдельными модулями и не становятся дополнительными нодами. Групповые registrations собирает root registration семейства без регистрации при импорте. Прежние proposed названия с Parent заменены в текущих двух планах; compatibility aliases/classes не создаются.

Все девять классов нод принадлежат `application/engine/nodes/artifacts/`; каждая нода — один класс в отдельном .py. POJO — `dataModel/engine/dag/artifacts/`, кроме уже определённых stageRoute.py и existing prepare/stage wrappers: второй копии этих моделей не создавать. Зависимости parents — только статически зарегистрированные typed CALL targets и pure input/terminal bindings. Зависимость leaf — один публичный Artifacts интерфейс. В таблицах имена операций — CALL-роли, не назначенные NodeId.

| Класс / файл | Единственная ответственность | Дети / допустимые зависимости | Отказ приёмки |
|---|---|---|---|
| PrepareAndStageArtifactWorkflowNode / prepareAndStageArtifactWorkflowNode.py | Подготовить один artifact и передать управление его записи | prepare_artifact, StageRecoveryWorkflowNode | Повторяет begin/recover policy; делает storage IO или повторяет prepare после unknown stage |
| StageRecoveryWorkflowNode / stage/stageRecoveryWorkflowNode.py | Управлять одним logical stage, включая owning recovery и explicit resume | begin, stage_artifact, recover; полный контракт основного плана §§12–15 | Сам выдаёт permit/generation, проверяет физическую безопасность либо создаёт новый stage_id при resume |
| FinalizeOperationStagesWorkflowNode / finalization/finalizeOperationStagesWorkflowNode.py | Получить inventory и последовательно завершить перечисленные executions | pending_finalizations, finalize_execution | Вызывает Publication, объявляет operation drained/terminal, самостоятельно ищет stage в storage |
| PrepareArtifactNode / prepareArtifactNode.py | Один вызов prepare_stage | IArtifactPrepareStageOpenPipeline[C] | Сам encode/hash/descriptor, выбирает format по content, пишет storage |
| BeginArtifactStageNode / stage/beginArtifactStageNode.py | Один вызов begin | StageAttemptService.begin | Создаёт stage_id, сам запускает stage или повторяет begin по отказу |
| StageArtifactNode / stage/stageArtifactNode.py | Один вызов authorized stage | IArtifactStageOpenPipeline[C] | Сам reserve/write/seal, повторяет эффект по error, восстанавливает prepared из ref |
| RecoverArtifactStageNode / stage/recoverArtifactStageNode.py | Один вызов recover | StageAttemptService.recover | После Allowed сам вызывает stage или вычисляет successor |
| PendingFinalizationsNode / finalization/pendingFinalizationsNode.py | Один coherent inventory call | StageAttemptService.pending_finalizations | Читает tables, фильтрует batch по current fence/completion либо самостоятельно вызывает finalize |
| FinalizeExecutionNode / finalization/finalizeExecutionNode.py | Один вызов finalize_execution | StageAttemptService.finalize_execution | Выдаёт successor, удаляет final artifact, освобождает operation holds |

Родительские CALL-связи не меняют семейство вызываемой ноды. Prepare допускается самостоятельно; уже готовый producer source идёт прямо в StageRecoveryWorkflowNode. Direct recover/finalize допустимы как явно объявленные CALL другого согласованного parent, без автоматического запуска остальной цепочки. Низкие ноды не вызывают друг друга. Publication close/cancel остаются во внешнем cancellation parent; никаких нод reserve/WRITE/SEAL/gate/cleanup не вводится.

### Ответственности нод и домены

Таблицы сохранены по поручению пользователя 2026-11-27. Все девять нод относятся к DAG-семейству `artifacts`; публичные методы и их предметная логика принадлежат домену Artifacts. Таблица не означает приёмки ещё открытых registration/binding контрактов.

| Нода | Тип | Ответственность внутри DAG | Публичный метод | Домен-владелец метода |
|---|---|---|---|---|
| PrepareAndStageArtifactWorkflowNode | Оркестрация | Вызвать prepare, передать prepared source и lease в stage workflow, вернуть ссылку на его результат | Напрямую не вызывает | — |
| StageRecoveryWorkflowNode | Оркестрация | Управлять одним logical stage: begin → stage; при неизвестном исходе recover; повтор только после Allowed | Напрямую не вызывает | — |
| FinalizeOperationStagesWorkflowNode | Оркестрация | Получить inventory, последовательно вызвать finalize для каждого элемента, остановиться при неподтверждённом завершении | Напрямую не вызывает | — |
| PrepareArtifactNode | Публичная операция | Передать input в метод подготовки и обернуть результат/ошибку | ArtifactPrepareStageOpenPipeline.prepare_stage | Artifacts |
| BeginArtifactStageNode | Публичная операция | Передать binding и вернуть owning-решение о начале stage | StageAttemptService.begin | Artifacts |
| StageArtifactNode | Публичная операция | Передать permit и prepared; вернуть ArtifactRef или owning-ошибку | ArtifactStageOpenPipeline.stage | Artifacts |
| RecoverArtifactStageNode | Публичная операция | Передать binding/generation и вернуть решение восстановления | StageAttemptService.recover | Artifacts |
| PendingFinalizationsNode | Публичная операция | Передать operation coordinates и вернуть полный owning inventory | StageAttemptService.pending_finalizations | Artifacts |
| FinalizeExecutionNode | Публичная операция | Передать точную execution и вернуть результат завершения её lifetime | StageAttemptService.finalize_execution | Artifacts |

| Домен / слой | Ответственность |
|---|---|
| Engine | Исполнение CALL, checkpoint, identity, доставка outcomes/errors, generic dependency и retention checks |
| DAG-семейство Artifacts | Порядок публичных вызовов и Output → Input mapping |
| Artifacts | Validation, binding/permit/generation, stage admission, запись, recovery-решение, доказательство прекращения эффектов и finalization |
| Publication, часть Snapshot | Закрытие operation admission, окончательная отмена, освобождение operation holds и terminal |
| Инфраструктура Snapshot | Транзакции, scopes, commit/rollback acknowledgement и обработка unknown commit |

Граница: ноды не решают, безопасен ли retry или завершены ли физические эффекты. Они используют решение публичного метода владельца. Листовая нода вызывает ровно один публичный метод/pipeline; WorkflowNode вызывает только дочерние ноды через Engine.

## 2. Контракты листовых нод

Все зарегистрированные I/O — concrete strict/frozen/extra-forbid BaseModel. C полностью специализирован при registration; union допускается внутри именованной модели, не вместо target.input_type/output_type. Формат/версия задаются composition, не wire selector. Полная validation принадлежит owning public method; нода не пересобирает owning request ради проверки.

| Leaf | Registered Input → public method → registered Output |
|---|---|
| prepare_artifact | PrepareArtifactInput[C](request: ArtifactPrepareStageInput[C]) → prepare_stage(input.request) → PrepareArtifactOutput[C](value: PreparedArtifact[C]) |
| begin | StageBeginInput(binding) → await begin(input) → StageAttemptNodeOutput(result: StageAttemptResult) |
| stage_artifact | StageInput[C](request: ArtifactAuthorizedStageInput[C]) → await stage(input.request) → StageArtifactOutput(value: ArtifactRef) |
| recover | StageRecoveryInput(binding,generation) → await recover(input) → StageAttemptNodeOutput(result: StageAttemptResult) |
| pending_finalizations | OperationCloseInput(operation_id,fence) → await pending_finalizations(input) → StageInventoryNodeOutput(result: OperationStageFinalizationResult) |
| finalize_execution | StageFinalizeInput(binding,generation) → await finalize_execution(input) → StageFinalizeNodeOutput(result: StageFinalizeResult) |

PrepareArtifactInput/Output и StageArtifactOutput переиспользуются из gen-dag-artifacts-node-contracts; StageInput — target authorized wrapper identity-плана, не второй lease-only input. StageAttemptNodeOutput/StageInventoryNodeOutput/StageFinalizeNodeOutput — уже предложенные оболочки §12.3 основного плана. Domain Input/Result types импортируются из owning модулей, не определяются заново в DAG.

### Ошибки и политики leaf

PrepareArtifactError несёт unchanged ArtifactInputError. Target StageArtifactError расширяется до owning union ArtifactStageInputFailure / StageBindingConflict / ArtifactStageAdmissionFailure / ArtifactLeaseFailure из SR-05; одно поле error, без зеркальных enum/issue. Begin/recover используют именованный StageAttemptNodeError(error: StageBindingConflict). Это wrappers NodeError для PythonNodeError, не повторная domain validation. Для inventory/finalize business Refused/Unresolved остаются owning result, не превращаются в invented NodeError. Новые expected exception carriers сверх owning контракта не назначаются.

Infrastructure, codec, corrupt storage, UnknownCommitOutcome идут через зарегистрированный neutral FailureEnvelope; cancellation — отдельный Engine outcome после owning cleanup. Leaf не преобразует их в Refused/Confirmed. HOST_BOOT_V1 не выдаёт Unresolved по основному плану: неожиданное получение этого варианта от такой регистрации — contract failure, не разрешение продолжить. Legacy result union этим не изменяется.

Declared-error retry отсутствует у всех перечисленных leaves. Interruption policy: stage REPORT_UNKNOWN; prepare RETRY как pure computation; begin/recover RETRY только с exact-request semantics основного плана; inventory RETRY как coherent read; finalize RETRY как owning идемпотентная finalization с host dedup/ReconcileFinalize, не WRITE retry. При прерывании finalize допустим replay exact input: owning service обязан корректно различать Running/Completed/Failed и применять §10.1. Нода этого не реализует. Наличие политики не разрешает автоматический retry вернувшегося runtime failure.

## 3. PrepareAndStageArtifactWorkflowNode

Concrete specialization input `PrepareAndStageInput[C](request: ArtifactPrepareStageInput[C], lease: OperationLeaseRef)`. Prepared content приходит от внешнего producer; source генератора здесь не выбирается. Output `PrepareAndStageOutput(route_source: ExecutionIdentity)` адресует exact child terminal StageRouteResult. Не копирует его envelope, prepared или RouteSuspended и не выдаёт grandchild failure за собственный child failure.

Continuation `PrepareAndStageState(phase: WaitPrepared | WaitStageRoute)`, union с discriminator в поле. WaitPrepared: lease, expected: ExpectedCall. WaitStageRoute: prepared_source: ExecutionIdentity, expected: ExpectedCall. Сам content остаётся в initial input/prepare child input, не дублируется в continuation. concrete classes и ExpectedCall используют модель §12.4 основного плана; Python targets не сохраняются.

Переходы:

1. start: Call key=prepare, Input=PrepareArtifactInput(request=input.request), state=WaitPrepared(input.lease,...). До следующего child никакого stage_id/begin.
2. WaitPrepared + CallSuccess: source=event.identity, artifact=event.output.value.descriptor; CALL key=stage-route в StageRecoveryWorkflowNode с StageRouteInput(request=StageFreshInput(lease,artifact,prepared_source=source)). Engine сохраняет declared prepared edge по разрешённому returned prepare CALL. PreparedArtifact не копируется в parent input/state.
3. WaitStageRoute + CallSuccess: Complete PrepareAndStageOutput(route_source=event.identity), независимо от варианта StageRouteResult. Результат ребёнка остаётся единственным primary terminal; внешний caller получает его через зарегистрированный declared output dependency, не незащищённый lookup по identity. Prepare parent не возобновляет ребёнка автоматически.
4. Expected declared child error → тот же NodeError в parent.error_types и PythonNodeError. CallCancelled → Engine cancelled. CallRuntimeFailure → parent runtime failure с generic reference к child, без нового begin/stage/prepare. Родитель не создаёт собственную StageRecovery suspension.

**Конкретная обязанность output dependency:** registration declares slot `route` типа StageRouteResult от CALL stage-route. Terminal binding PrepareAndStageTerminalBinding возвращает reference на exact returned child; generic Engine проверяет key/step/target и атомарно закрепляет edge+terminal. Это уточнение generic reference admission §15.1: разрешены existing declared edges либо exact returned CALL, для которого заранее объявлен output slot; произвольная identity не даёт права создавать edge. Metadata не назначает domain ветви. Output caller наследует route dependency через registered mapping, затем явно решает Confirmed/Refused/Suspended. Retention closure включает child route, его prepared и failure sources. Нельзя переиспользовать StageRouteTerminalBinding напрямую на PrepareAndStageOutput.

Один prepare → один child StageRecoveryWorkflowNode. Begin/recover цикл целиком принадлежит ребёнку. Если caller хочет только подготовку, он вызывает leaf, а не этот parent. Если уже имеет prepared source — сразу StageRecoveryWorkflowNode. Новый batch-of-artifacts parent не добавляется.

## 4. StageRecoveryWorkflowNode

Переиспользует без второго определения StageRouteInput/StageRouteResult/StageRouteState и полную таблицу основного плана §§12–15. Fresh request содержит lease/artifact/prepared_source; resume request содержит bound RouteSuspended с exact source identity. Parent — единственный issuer stage_id по begin CALL origin, сохранённому до begin effects.

| Исход / состояние | Следующий CALL или terminal |
|---|---|
| Fresh | begin(binding) |
| begin Allowed | stage с permit и BoundInput на original prepared source |
| stage success | RouteConfirmed, historical seal; не гарантия operation hold на момент доставки |
| stage CallOutcomeUnknown / предусмотренный UNKNOWN_COMMIT | recover(binding,observed_generation) |
| recover Allowed | новый stage CALL с полученным permit; не повтор старого CALL по таймеру |
| begin/recover Confirmed | RouteConfirmed без stage |
| begin/recover Refused | RouteRefused с unchanged owning refusal |
| Runtime failure вне автоматической recovery ветви | RouteSuspended со ссылкой на exact failed child |
| Declared error / cancellation | Unchanged error / Engine cancelled, не business refusal |
| Explicit resume | Сохранённый binding; begin если generation ещё неизвестна, иначе recover; prepare не запускается |

Число generation, writable admission, quiescence, permit consumption проверяет Artifacts. Parent проверяет только CALL/POJO correlation и выбирает следующий публичный вызов. Сам не вызывает finalize leaf: owning recover уже содержит внутреннюю finalization своей atomic операции. Отдельная finalization-оркестрация ниже обслуживает operation-wide cancellation, не подменяет stage recovery.

## 5. FinalizeOperationStagesWorkflowNode

Input: existing concrete OperationCloseInput. Внешний cancellation parent передаёт строго close_result.request после OperationClosePending(FULL_STAGE или BOTH). Этот факт задаёт порядок caller; координаты input сами не являются portable authority. Leaf inventory повторно проверяет owning состояние. Busy, LOCAL_WRITERS, Ready/Terminal не создают этот CALL. Никакого собственного вызова close внутри Artifacts-parent.

Output: concrete `FinalizeOperationStagesOutput(result: OperationStagesCompleted | OperationStagesRefused | OperationStagesIncomplete)`, discriminator kind. DAG-owned формы:
- OperationStagesCompleted(kind=completed, request: OperationCloseInput, inventory_source: ExecutionIdentity): все элементы указанного inventory получили correlated StageExecutionFinalized. Не утверждает full/local drain всей operation и не заменяет Publication cancel.
- OperationStagesRefused(kind=refused, refusal: OperationStageFinalizationRefused): unchanged owning inventory refusal.
- OperationStagesIncomplete(kind=incomplete, request: OperationCloseInput, item: StageFinalizeInput, outcome: StageFinalizeUnresolved): контекст остановки на owning incomplete result. Для HOST_BOOT_V1 недопустим по договору registration, это contract failure; форма нужна только при отдельно принятом compatible legacy registration, не fallback между protocols.

Continuation `FinalizeOperationStagesState(phase: WaitInventory | WaitExecution)`, concrete wrapper с discriminated field. WaitInventory(request, expected). WaitExecution(request, batch: OperationStageFinalizationBatch, inventory_source: ExecutionIdentity, next_index: nonnegative int, expected). Batch — неизменный snapshot operands owning inventory, не самостоятельный storage registry. Generic binding/projection переиспользует primary inventory output при checkpoint restore, не меняет его поля; индекс — только прогресс DAG. Accumulated error/envelope list и второй authoritative список completed stages не создаются: child records хранят их исходы.

Строгая последовательность:
1. start → CALL inventory с exact request, key=inventory.
2. Inventory Refused → terminal OperationStagesRefused. Batch.request должен совпасть с input; mismatch — contract failure, не repair.
3. Пустой Batch → OperationStagesCompleted(inventory_source), без finalize. Это пустота конкретного full-stage observation, не доказательство отсутствия legacy local writers.
4. Непустой Batch → finalize(batch.pending[0]) с key=finalize/0. Порядок tuple сохраняется; сортировка/фильтр/parallel CallGroup не вводятся.
5. Correlated StageExecutionFinalized → checkpoint следующего индекса и один CALL finalize/i. После последнего — OperationStagesCompleted. Binding/generation результата должны соответствовать item; при mismatch остановка до следующего CALL.
6. Unresolved в допускающем его контракте → OperationStagesIncomplete, последующие items не запускаются. Для HOST_BOOT_V1 — contract failure.
7. Declared error → unchanged; runtime failure → Engine failed с generic child failure reference; cancellation → Engine cancelled. Нельзя возвращать Completed при частичном успехе. При shutdown текущее owning finalize самостоятельно обеспечивает lifetime, parent не принимает resource handles.

Crash/повтор доставки использует existing child CALL identities/checkpoint: завершённые items не вызываются заново в том же continuation. Interrupted finalize replay — только exact owning idempotent request. После terminal failure новый ЯВНЫЙ запуск parent начинает с нового inventory; уже released executions исчезают из owning inventory или дают идемпотентный result при гонке. Нет автоматического бесконечного inventory/finalize loop. Completed передаётся внешнему cancellation parent, который вызывает Publication.cancel; именно его UOW проверяет всю operation и снимает holds.

Registration declares returned inventory dependency slot и terminal retention для inventory_source; используется generic returned-CALL mapping из §3. Общая visibility не расширяется по наличию identity. Для batch continuation выбирается producer-reference projection того же generic checkpoint binding механизма; standalone второй JSON source не становится новым authority. До implementation проверить cold restore exact item sequence и next_index.

## 6. Общие gates контрактов и реализации

Новые parent POJO хранят только orchestration state/ссылки и импортированные owning operands. Не дублируют StageBinding, permits, OperationCancelled, failure envelopes или диагностические issue enums. Все public field/relation ошибки создаёт Artifacts; wrappers не правят root/path/order. Каждая concrete registration имеет полный finite tuple error_types; parent включает union своих declared child errors. Empty tuple у leaf без declared exceptions не превращает infrastructure в business result.

Ноды используют существующий NodeRunner/NodeStep/Call/Complete и proposed generic bindings из основного плана. У resumable parents start(input,origin), resume(state,event,origin); нижние ноды — PythonNode с одним публичным вызовом. NodeId/contract version/конкретный C задаются отдельной registration, не выводятся из имени файла. Ни одна нода не импортирует SQL repositories, storage host, gate или backend. Один family folder, каждый node class отдельный файл; test implementations/registrations — tests/support, app не импортирует tests.

Проверяемая приёмка: реальные NodeContract/CallTarget/ContinuationContract принимают concrete wrappers; каждый leaf делает один exact public call; upper write parent не вызывает begin/recover; StageRecoveryWorkflowNode не вызывает prepare/finalize; finalize parent не вызывает Publication. Fresh prepared identity и cold restore; exact resume без нового stage_id; отказ foreign dependency/error reference; последовательный batch/empty/refused/error на середине; никакого next item после failure; lost ACK до/после каждого accept; final cancel только через внешний parent и final UOW. Generic Engine не содержит веток по этим конкретным POJO.

**Статус:** responsibilities, proposed I/O и порядок здесь конкретизированы. Это плановая дельта двух родителей и их generic returned-output dependency mapping, а не утверждение уже существующего Engine API. До полной приёмки сверить эту дельту с §15.1 и checkpoint binding для batch continuation; production activation требует отдельной caller/cutover карты. Код/SQL/регистрация не менялись; тесты новых моделей ещё не выполнены. Обсуждённый порядок — prepare→stage-route и inventory→последовательные finalize с остановкой — не расширяется скрытыми повторными циклами.
