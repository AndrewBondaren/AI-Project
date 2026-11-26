# Передача Artifacts prepare → stage без потери object identity

Статус: направление решения выбрано пользователем; детализация OPEN, 2026-11-26. Пользователь выбрал вариант 2: восстановить результат prepare один раз и сформировать зависимый вход stage из него, «главное без обходных путей». Выбор не требует повторного согласования. Полная приёмка плана и поручение реализации этим статусом не заявляются.

## 1. Задача и основания

Сохранить исходный content и PreparedArtifact на непрерывном зарегистрированном маршруте prepare → stage при полноценной validation. Передача через JSON создаёт новые экземпляры и нарушает принятый is-контракт.

Источники:
- [Решение об откате Engine](../../docs/artifacts-dag-identity-bug-2026-11-25.md), верхний раздел от 2026-11-26: owning исправления Artifacts сохранены; identity_required/live transport и второй lifecycle откачены.
- [Контракт нод Artifacts](gen-dag-artifacts-node-contracts.md), §§2–4, 6 и P1: public methods, POJO, неизменный Error, exact registered route; restart/durable replay не обещает Python identity.
- [Координация](../rules/interdomain-contract-coordination.mdc) и [обязательная приёмка](../rules/dag-generator-interface.mdc#обязательная-приёмка-плана-любого-домена).

Фактические точки: InvocationCoordinator.encode/view/event и DAGExecutor._invocation_step используют JSON для активной передачи; InvocationRecord.input/terminal — строки. DAGContext уже хранит типизированные OutputRecord. Наличие этого каталога не доказывает его пригодность для всех вложенных invocation: это проверяется первым шагом.

## 2. Предлагаемая граница решения

В активном выполнении должен быть один основной набор типизированных данных invocation. CALL, возврат результата и dependency read используют принятые объекты из него. Checkpoint — сериализованное представление для сохранения и восстановления; создание checkpoint не заменяет активные объекты результатом decode.

Требование распространяется на весь путь content → prepare input → public prepare → output → CALL outcome/read → stage input → public stage после admission. Output.value передаётся непосредственно в owning поле prepared; нода не извлекает и не пересобирает доменные поля. Owning Error переносится целиком. Порядок операций и ошибки остаются заданными owning контрактом.

Не вводить параллельный live-cache, object registry, токены, identity_required, отдельный executor или второй worker/claim/renew/drain/release loop. Не обходить validation, не менять is на equality и не выбирать BLOB вместо model payload для прохождения теста. Изменение представления данных не разрешает переставлять checkpoint/CAS и побочные эффекты.

## 3. Последовательность работ

### A. Закрыть точный контракт и границы классов — до кода

Проследить public DAGEngine.run → admission → existing recovery owner → execution → CALL → parent outcome → следующий CALL. Отдельно сверить root input, prior-phase binding, dependency reads, retries, replan и повторные invocation одного NodeId. Зафиксировать ключ результата с invocation/attempt identity и срок его доступности.

Проектное решение: InvocationGraph/InvocationRecord становятся основным runtime-представлением активных invocation с типизированными payload. Отдельные wire-модели checkpoint создаются codec. DAGContext остаётся каталогом опубликованных результатов и получает ссылки на те же payload; для invocation он не становится вторым writer. Дельта §5 предложена к согласованию; это не существующая возможность Engine.

| Класс / группа | Ответственность и критерий приёмки | Основание отказа |
|---|---|---|
| InvocationRecord / InvocationGraph | Данные invocation и принятые переходы состояния; определить runtime/wire границу | Два независимо изменяемых payload одного результата; IO или orchestration в POJO |
| DAGContext / OutputRecord / CatalogSnapshot / PublishedDAGReadView | Каталог, provenance и разрешённое чтение; проверить адресацию вложенных invocation | Коллизия по NodeId, выдача устаревшей attempt, дублирование каталога |
| InvocationCoordinator | CALL bindings и outcomes из основного runtime-состояния | JSON reconstruction при живой передаче; управление claim/worker |
| DAGExecutor | Запуск нод в существующем порядке через зарегистрированный контракт | Альтернативный executor, обход admission или durable start CAS |
| ContractValidator / NodeRunner | Полная проверка зарегистрированных POJO и запуск | model_construct, ослабление rejection или клонирование protected payload |
| CheckpointCodec / SessionFrame | Encode/decode persistence-представления | Decode для обычной активной передачи либо мутация живого результата при encode |
| OwnedExecution | Существующие checkpoint/CAS и взаимодействие с владением | Новый источник payload или изменение fencing ради identity |
| ExecutionAdmission / ExecutionRecovery / PassExecution | Существующие admission, recovery ownership и pass lifecycle | Второй ownership loop; неоговорённые запреты resume/replan |
| Prepare/Stage wrappers и ноды | Один public owning call, mapping результата/ошибки | Доменные проверки, внутренние storage операции или скрытый вызов соседней ноды |

Для каждого реально затронутого класса раскрыть точный модуль, зависимости, вложенные calls и тестовый критерий; перечисленные группы развернуть в окончательной дельте. Неизменяемые классы отметить как проверенные зависимости.

### B. Детализировать выбранное восстановление — вариант 2

Принятое направление: после восстановления результат успешного prepare декодируется и полностью валидируется один раз для соответствующей invocation/attempt. Он становится основным объектом результата в восстановленном выполнении. CALL outcome, dependency read и поле prepared зависимого stage используют этот экземпляр через явный Output → Input mapping.

Identity относительно завершившегося процесса не обещается. В восстановленном выполнении контрольный экземпляр — восстановленный результат prepare; stage.prepared is restored_prepare.value и stage.prepared.content is restored_prepare.value.content обязательны после всех admission. Это явная граница lifetime, а не замена is проверкой equality внутри выполнения. В непрерывном fresh run остаётся полная цепочка original content из P1.

Зависимое поле prepared не восстанавливается независимо из копии сохранённого stage input. В A определить точное описание и сохранение существующей связи producer invocation/attempt → output.value → consumer input.prepared. Это связь DAG, не токен Python-объекта и не object registry. Нельзя находить объект сравнением значений, дедупликацией по hash, interning или особым условием для класса PreparedArtifact. Сопоставление выполняется штатным механизмом DAG; прочие поля stage input, включая lease, сохраняют своих производителей и validation.

Успешный prepare ради identity повторно не запускается. Восстановление mapping не исполняет произвольный parent заново и не повторяет его эффекты. Для уже начатого stage продолжение/повтор определяется существующим owning replay-контрактом и durable статусом; восстановление ссылки само по себе не разрешает новую запись. До кода предъявить таблицу actual состояний: prepare завершён/stage не запущен; stage запущен с неизвестным исходом; stage завершён; cancellation/owner loss. Terminal replay не вызывает ноды повторно.

Детализировать retry/replan и недоступный, устаревший или несовместимый producer result: проверка invocation/attempt/contract до consumer CALL, typed outcome через существующую границу ошибок. Обычные маршруты сохраняют принятые гарантии. Формат mapping, точные API и исходы остаются частью A/B; общий запрет resume, второй lifecycle или скрытый fallback не допускаются.

### C. Реализовать согласованную минимальную дельту

После A/B и пользовательской приёмки выполнить отдельное поручение реализации через implement-plan. Изменить runtime/checkpoint mapping только в принятом перечне файлов; сохранить единственный lifecycle и существующий порядок CAS/checkpoint/CALL. Owning Artifacts identity/P2 исправления повторно не переделывать.

### D. Проверить реальный маршрут

- Через public DAGEngine.run и registered prepare/stage проверить is original для runtime-created bytes и frozen model с revalidate_instances=always на всех звеньях P1, включая аргумент stage после admission.
- Использовать явно названные test-only binding/fixtures в tests/support; никакого app → tests. Storage stub допустим только на storage boundary. Test route не объявлять production activation.
- Проверить rejection wrong/mutable/forged payload и unchanged typed Error с правильными P2 paths.
- Восстановить checkpoint после prepare до stage через публичный маршрут: prepare не вызван повторно, stage получает ровно восстановленный producer object после admission; повторные reads/outcomes возвращают тот же payload. Тест должен обнаруживать независимое decode stage.prepared и подмену equality вместо is.
- Проверить сохранённый mapping для нескольких invocation одного NodeId и разных attempts; несовместимая или отсутствующая связь не допускает consumer CALL. Объекты разных invocation не объединяются по равным значениям.
- Проверить согласованные в B restore/replay, cancellation, owner loss, retry/replan; отсутствие следующего CALL/effects после остановки и устаревших payload после новой attempt.
- Прогнать existing test_world_calls и Artifacts test_content_identity + contracts.test_registry. Добавлять другие проверки только по затронутым гарантиям. PASS тестов не заменяет проверку ответственности.

## 4. Приёмка и оставшиеся решения

Три запрета DAG обязательны: ветвление и запуск остаются в DAG, public domain operation вызывается непосредственно нодой, домены не вызывают друг друга. Leaf выполняет один public call; parent оркестрирует. Production concrete C/binding, manifest IDs и порядок нового маршрута этим планом не назначаются.

Порядок исполнения сверяется с согласованным Artifacts контрактом и существующими start CAS / checkpoint / ownership переходами; до предъявления полной трассы A — OPEN. CRUD доменных данных/настроек не расширяется; существующий ExecutionStore контракт проверяется как зависимость. Если потребуется его изменение, нужен отдельный точный пакет CRUD-контракта до кода. Анализ всех затронутых POJO, field/logic errors и отсутствия дублирования завершается в A.

Текущие OPEN уточняются последующими §§5–7: полная сверка runtime/mapping/recovery и inventory, приёмка конкретной дельты пользователем. Выбор варианта 2 закрыт. Пользователь 2026-11-26 назначил координатором этот продолжающий чат 01a218a4-bfc5-7012-b18b-8ed986cc786d; AGENTS.md и правило синхронизированы. Без закрытия контрактных OPEN план не принят к реализации.

Вне объёма: generator/gameplay, domain storage/authority/transaction design, новая архитектура всего Engine, объединение prepare/stage, изменения других семейств нод и production activation.

## 5. Конкретная проектная дельта после ревью

Этот раздел уточняет A/B и имеет приоритет над формулировками «выбрать»/«штатный mapping» выше. Mapping ниже — предлагаемое расширение контракта CALL. Existing CallRequest содержит готовый input, а InvocationCoordinator.accept сохраняет JSON: persisted field mapping сейчас отсутствует.

### 5.1. Исходное состояние

Пользователь пояснил 2026-11-26: текущее состояние получено его откатом, поскольку предыдущие изменения также были проблемными. Наличие identity_required, _live, live_coordinator и отдельного worker/claim loop объяснено; это не неизвестная чужая дельта. Исходная точка работы — фактический workspace, а не восстановление исторического commit. Исторический dfe665088b56f30986c84e795b1938a721b15db0 допустим только для сравнения. По поручению пользователя составлена карта адресной замены §6; откат файлов целиком не требуется и не разрешается этим планом.

### 5.2. Единое runtime-представление и wire

В runtime InvocationRecord поля input, continuation, terminal содержат принятые BaseModel-экземпляры с exact concrete типом, заданным registry; не JSON. Registry — единственный источник concrete типов. Изменение общего типа поля не разрешает arbitrary BaseModel на публичной границе ноды. Structural/deep immutable admission обязателен. InvocationGraph.records — единственный writer состояния invocation. Никаких строковых shadow payload в runtime record.

В dataModel/engine/dag/invocations/checkpoint.py предложить InvocationCheckpoint и InvocationCheckpointRecord: wire-проекции existing graph/record metadata, включая адреса, статусы, caller/step, reads, diagnostics, waits и terminal/error_index. Payload кодируются строками JSON только в этой проекции. Это wire-представление тех же данных, не новый доменный результат и не самостоятельно изменяемый runtime-каталог. Имена runtime graph/record сохраняются; все прямые model_validate_json/model_dump_json графа переводятся на checkpoint codec, включая Checkpoint.with_cancelled_child, read_header и interaction readers.

CheckpointCodec.encode(graph: InvocationGraph) -> bytes создаёт wire-проекцию. decode(blob: bytes, plan: ExecutionPlan) -> InvocationGraph валидирует registry/адреса/контракты, декодирует terminal каждого producer один раз, затем строит зависимые inputs. restore(blob, plan) -> InvocationGraph дополнительно вызывает existing OutputLifecycle.validate_restored на том же экземпляре. Повторное decode для lifecycle запрещено.

SessionFrame содержит ссылки ExecutionIdentity на результаты, уже сохранённые в invocation checkpoint; самостоятельные результаты других фаз остаются собственными wire payload. CatalogSnapshot после восстановления получает те же runtime-экземпляры. Дубликат одной identity в двух owning wire slots — RestoreFailure, не выбор победителя по равенству. ExecutionSnapshotService.decode получает восстановленный graph как источник referenced outputs; encode не запускает decode.

### 5.3. Явный типизированный mapping CALL

Предлагаемые runtime-контракты Engine в application/engine/contracts/invocation/inputBinding.py:

| Тип / метод | Состав и ответственность |
|---|---|
| InputBinding[O,Q,I] | contract_id, version, source: CallTarget[...,O,...], parameters_type: type[Q], input_type: type[I]; абстрактный build(output: O, parameters: Q) -> I |
| BoundInput[O,Q,I] | binding: InputBinding[O,Q,I], source: ExecutionIdentity, parameters: Q; описание входа, без копии output |
| CallSuccess[O] (existing) | добавить identity: ExecutionIdentity к output; адрес результата выдаёт Engine, parent не вычисляет attempt |
| NodeContract (existing) | добавить input_bindings: tuple[InputBinding[..., ...], ...]; статическая регистрация допустимых mappings caller |
| Dispatch/CallRequest/Call (existing) | input допускает existing готовый I либо BoundInput[...,I]; target.input_type должен совпасть с binding.input_type |

InputBinding — транспортная композиция POJO, без IO, codec, domain admission, ветвления workflow или запуска нод. Проверяемый критерий: только constructors входных оболочек и прямое помещение source payload в owning поле. Произвольный callback из checkpoint не исполняется; реализация binding выбирается из статической регистрации по contract_id/version. В checkpoint Python-классы/функции не записываются.

Wire BoundInputCheckpoint в dataModel/engine/dag/invocations/inputBinding.py: binding_id: ContractId, binding_version: ContractVersion, source: ExecutionIdentity, parameters_json: str. CheckpointRecord.input содержит tagged literal input JSON либо BoundInputCheckpoint; для bound input готовый input JSON не сохраняется. Q — отдельный именованный concrete POJO параметров, не dict/Any. Runtime record хранит построенный input и его binding description; description не содержит вторую копию producer output.

InvocationCoordinator.accept проверяет declared binding, source success, точную execution/invocation/attempt/revision и допустимость источника: ранее возвращённый CALL данного parent либо declared dependency read. Чужой результат недоступен даже при правильном типе. build вызывается один раз при создании input и один раз при восстановлении input в новом процессе, затем работает штатная validation. Missing/stale/foreign source или неверный contract дают existing RestoreFailure на restore; при live CALL — existing engine contract/runtime failure с correlation, без выдуманного Artifacts refusal. Restore должен обнаруживать циклы bindings до запуска любой ноды.

Целевой mapping согласуется с artifacts-stage-recovery-contract.md: StageBindingParameters(permit: StageAttemptPermit); build(output: ConcretePrepareOutput, parameters: StageBindingParameters) -> ConcreteStageInput создаёт ArtifactAuthorizedStageInput(permit=parameters.permit, prepared=output.value) и внешнюю оболочку request. Полные пути: prepare.output.value → stage.input.request.prepared; Allowed.permit результата begin/recover → stage.input.request.permit. Ни initial stage, ни retry не используют старый lease-only input. Конкретный permit сохраняется в named parameters; источник и correlation результата begin/recover проверяются parent по контракту CALL. Сериализация permit не переносит prepared и не заменяет owning admission authority. Поле lease повторно не добавляется. Binding не проверяет domain admission и не пересчитывает descriptor. Concrete test binding/parameters живут tests/support; production binding не назначается. Это проект целевого перехода; existing public input изменяется только в принятом cutover.

### 5.4. Публичная граница Artifacts

Prepare сохраняет контракт gen-dag-artifacts-node-contracts §§2–4: PrepareArtifactInput.request → public prepare_stage(request) → PreparedArtifact → PrepareArtifactOutput.value. Для recovery-capable stage целевой owning input — ArtifactAuthorizedStageInput[C](permit, prepared) из artifacts-stage-recovery-contract.md; node wrapper.request передаётся в await public stage(request), ArtifactRef → StageArtifactOutput.value. PrepareArtifactError переносит ArtifactInputError; полный target StageArtifactError обязан включить owning admission error после закрытия SR-05. Existing ArtifactInputError/ArtifactLeaseFailure и infrastructure/unknown/cancellation сохраняют категории. Leaf делает один public call, parent принимает CALL outcomes и объявляет BoundInput; binding не управляет порядком вызовов. Историческая lease-only сигнатура — AS-IS, не разрешённый fallback целевого маршрута.

PreparedArtifact(content, descriptor), ArtifactRef, OperationLeaseRef и existing owning field/logic errors переиспользуются. ArtifactStageInput(lease, prepared) остаётся описанием AS-IS; целевой ArtifactAuthorizedStageInput, StageAttemptPermit и новые admission errors принадлежат Artifacts, не Engine. Cutover затрагивает wrappers, signatures и diagnostic roots; их окончательная owning карта — SR-05. BoundInputCheckpoint описывает происхождение входа, existing DependencyRead — факт чтения результата: семантики не заменяют друг друга. При чтении source формируется existing provenance; отдельный параллельный аудит reads не создаётся.

### 5.5. Порядок и состояния восстановления

Единственный owner — ExecutionRecovery. Fresh admission создаёт checkpoint и идёт через existing owner; сохранение original root input до этого первого decode отдельно проверяется на actual public entry. Если public entry принимает готовый payload, тот передаётся в тот же recovery execution path как основной graph, с проверкой checkpoint revision под claim; второй worker не создаётся. Нельзя обещать fresh identity, если entry уже сделал decode первоначального payload.

Под claim: compile/registry check → decode producers → resolve bindings и validation → validate_restored → восстановление catalog по ссылкам → existing scheduler. До CALL сохраняется existing start CAS; порядок effects и durable completion сохраняется. Decode/build не выполняют доменные операции.

| Сохранённое состояние | Действие | Запрещённое действие |
|---|---|---|
| prepare SUCCEEDED, stage ещё не создан | Parent получает CallSuccess с восстановленным output/identity и объявляет обычный bound CALL | Повтор prepare для восстановления identity |
| stage создан, READY | Input строится из сохранённого binding и producer; затем existing start CAS/CALL | Независимое decode prepared из stage input |
| stage RUNNING, durable исход отсутствует | Требуется доказательство existing owning replay-контракта до допуска этой регистрации к restart | Автоматически переводить такой stage в READY только ради транспорта |
| stage SUCCEEDED | Восстановить результат и вернуть outcome; stage не вызывать | Повтор записи |
| FAILED/CANCELLED или stop intent | Existing failure/cancellation/stop flow, без зависимого CALL | Успешный fallback |
| owner loss | Existing cancel/drain/release; новый owner заново восстанавливает graph | Использование объектов предыдущего owner через side channel |
| retry/replan | Existing policy; bindings ссылаются на exact attempt, invalidation охватывает потребителей; immutable результат удерживается, пока есть действующая ссылка | Подмена ссылки результатом новой attempt по NodeId |

Неизвестный исход stage остаётся owning OPEN; этот план не придумывает idempotency или новый отказ Artifacts. Это блокирует соответствующий restart scenario, а не проектирование транспортного mapping или тест READY restore.

### 5.6. Ответственность и объём файлов

Все пути относительно backend/app. Каждая строка ниже задаёт допустимую дельту; storage/authority алгоритмы не меняются.

| Класс и модуль | Дельта / зависимости / эффект / критерий отказа |
|---|---|
| InvocationRecord, InvocationGraph — dataModel/engine/dag/invocations/record.py | Runtime данные/переходы; registry admission снаружи; без IO; отказ при shadow JSON |
| InvocationCheckpoint, InvocationCheckpointRecord — dataModel/engine/dag/invocations/checkpoint.py | Только wire schema; без runtime ownership; отказ при отдельном writer состояния |
| BoundInputCheckpoint — dataModel/engine/dag/invocations/inputBinding.py | Только адрес источника и binding parameters; отказ при Python object token |
| InputBinding, BoundInput — application/engine/contracts/invocation/inputBinding.py | Typed композиция и описание input; без IO/оркестрации; отказ при domain алгоритме |
| NodeContract — application/engine/contracts/nodeContract.py | Регистрация binding; без выполнения; отказ при незарегистрированном mapping |
| Dispatch, CallRequest, Call — application/engine/contracts/invocation/nodeStep.py | Typed call request; без выполнения; отказ при несовместимом target input |
| CallSuccess, ReturnedCall, CallResults — application/engine/contracts/invocation/resumeEvent.py | Outcome и source identity; без decode; отказ при потере корреляции |
| InvocationCoordinator — application/engine/runtime/invocations/invocationCoordinator.py | Единственные переходы graph, bind/event/view; без claim/IO; отказ при _live или JSON transport |
| CheckpointCodec — application/engine/runtime/invocations/checkpointCodec.py | Единственная runtime/wire граница; dependencies registry/bindings/lifecycle; отказ при повторном producer decode |
| DAGExecutor — application/engine/runtime/dag/dagExecutor.py | Existing scheduler/start CAS, typed input; отказ при новом executor или прямом domain вызове |
| OwnedExecution — application/engine/runtime/invocations/ownedExecution.py | Existing renew/checkpoint/CAS; codec dependency; отказ при live_coordinator и новом lifecycle |
| SessionFrame — application/engine/runtime/invocations/sessionFrame.py | Wire snapshot с output references; отказ при повторном owning payload |
| ExecutionSnapshotService — application/engine/runtime/dag/lifecycle/executionSnapshotService.py | Связывание snapshot с primary graph; отказ при независимом decode referenced output |
| ActiveCheckpoint — application/engine/runtime/invocations/recovery/activeCheckpoint.py | Existing restore под claim; передача одного graph в snapshots/passes; отказ при втором load/decode payload |
| ExecutionAdmission — application/engine/runtime/dag/lifecycle/executionAdmission.py | Existing admission/create/delegation owner; отказ при собственном ownership worker |
| ExecutionRecovery — application/engine/runtime/invocations/recovery/executionRecovery.py | Единственный claim/renew/drain/release; отказ при альтернативном owner |
| PassExecution — application/engine/runtime/dag/lifecycle/passExecution.py | Existing pass order/invalidation; отказ при identity-specific запрете replan |
| Checkpoint — application/engine/contracts/invocation/executionStore.py | with_cancelled_child работает с wire schema и сохраняет bindings; storage signatures прежние; отказ при decode/clone domain payload |

Проверяемые зависимости без нового назначения ответственности: DAGContext — publication/provenance; OutputRecord — результат с identity; CatalogSnapshot — неизменяемый read snapshot; PublishedDAGReadView — разрешённое чтение; ContractValidator — полная structural validation; NodeRunner — existing node execution. Ни один из них не хранит дополнительную owner-копию payload. Подробный caller inventory read_header/ExecutionInteraction/InputWaitCoordinator и всех прямых graph serializers обязателен до фиксации окончательного diff; неизвестные callers не разрешается чинить автоматически вне плана.

### 5.7. CRUD и критерии завершения проектирования

ExecutionStore API сохраняется: create(execution_id, blob), load(execution_id), checkpoint(claim, revision, status, blob), cancel/cancel_child, claim/renew/release, record_stop_intent/finalize. Public create/read/update checkpoint затронуты форматом blob, не новым CRUD; delete и CRUD настроек не добавляются этим срезом. Полная приёмка домена Engine/Artifacts не заявляется. Формат checkpoint должен иметь явную версию; старый checkpoint без binding не позволяет восстановить identity-связь по значениям. Его допустимость для конкретного маршрута проверяется по версии контракта, с RestoreFailure при несовместимости; скрытая эвристическая миграция запрещена.

Перед реализацией: сверка назначенным координатором дельты CALL/NodeContract и lifetime PreparedArtifact; проверка покрытия serializers по §6; доказательство restore semantics начатого stage либо явное ограничение принимаемого restart coverage. Исходное состояние workspace объяснено пользователем и принято как точка адресной замены. Выбор варианта 2 не переоткрывается. Проверки D дополняются cold restore, запрещающим повтор decode producer, отсутствием двойного payload в checkpoint и тестом claim/CAS conflict перед первым side effect.

Статус ревью после детализации: конкретное направление runtime/wire и binding теперь предъявлено; полная приёмка остаётся OPEN по перечисленным внешним/implementation-boundary пунктам. Не считать таблицу будущих изменений доказательством уже выполненной реализации.

## 6. Адресная замена текущего кода — сверка 2026-11-26

Пути ниже относительно backend/app. Это план изменений, не отчёт о выполненном удалении. Сохранить несвязанные изменения пользователя; не восстанавливать файлы из исторического commit целиком. Удаление старого механизма и подключение замены выполняются одним согласованным переходом: fallback на старый live transport не оставлять.

### 6.1. Удалить обходные механизмы и заменить их потребителей

| Текущий элемент / файл | Действие и замена | Что обязательно сохранить |
|---|---|---|
| contracts/invocation/executionOptions.py: InvocationOptions.identity_required и его проверка | Удалить переключатель; единое runtime-представление применяется штатно | Остальные settings, workers, limits, lease и store binding |
| dataModel/engine/dag/invocations/record.py: InvocationGraph.identity_required | Удалить runtime/wire policy-флаг; совместимость задаётся версией checkpoint и зарегистрированных контрактов | Адреса invocation/attempt, статусы, caller bindings, reads, cancellation/stop |
| runtime/invocations/invocationCoordinator.py: _live, _remember, _refresh, clear_live | Удалить целиком и все вызовы из create/bind_published/next_pass/start/accept/ready; хранить принятые объекты в основном record | Проверки чужой attempt/revision, provenance и invalidation; перенести их на основные записи, а не удалить вместе с кешем |
| Тот же файл: payload(record, slot, wire, expected) | Удалить выбор cache/JSON; typed чтение соответствующего поля record с registry-проверкой | Contract mismatch rejection |
| Тот же файл: encode и сравнения JSON при replay CALL/RETURN | Перенести сериализацию в codec; сопоставление replay по принятому контракту и binding identity, с проверкой полного literal payload | Отказ conflicting/stale RETURN и повторного CALL key; не заменять все проверки сравнением is |
| runtime/invocations/ownedExecution.py: live_coordinator | Удалить; OwnedExecution владеет одним graph и существующей записью checkpoint | Lock, revision CAS, renew, stop intent и child cancellation conflict handling |
| runtime/dag/lifecycle/executionAdmission.py: identity ветви, worker_started, claim/worker/renew/shield/drain/release и clear_live | Удалить отдельный цикл; fresh graph передаётся в общий execution path существующего owner | _enter/_active, validate_run/resume, проверку существующего execution, state.release на всех ранних отказах |
| runtime/invocations/recovery/executionRecovery.py: policy mismatch, identity unfinished refusal и special terminal branch | Удалить специальные identity ветви; восстановление через единый codec, terminal через existing replay | Claim fencing, renew/drain/release, cancellation, stop/finalize, terminal response validation |
| runtime/dag/lifecycle/passExecution.py: identity_required replan refusal | Удалить условный запрет; replan работает с основными typed records и invalidation bindings | Утверждённый порядок pass и все прежние ограничения, не связанные с identity |
| runtime/dag/dagExecutor.py: identity_required, _coordinator_out, handed_off, live list, durable.live_coordinator, clear_live | Удалить флаг, вывод coordinator/claim через mutable list и ветки transport; возвращать обычный typed результат по штатному пути | Start CAS, scheduling, cancellation/drain и гарантированное освобождение claim по существующему пути |

В DAGExecutor.run_invocation уже существует собственный direct-entry claim/release путь. Не смешивать его молча с публичным recovery lifecycle и не удалять direct API как побочный эффект. Для public DAGEngine.run единственный owner — ExecutionRecovery; nested scheduling не захватывает второй claim. Direct run_invocation сохраняет одну область владения своего вызова и не передаёт claim наружу через _coordinator_out. Оба входа используют одинаковые runtime records и codec; тест direct-entry не заменяет public-entry тест.

Fresh handoff означает передачу основного graph существующему owner, не передачу кеша/coordinator. Под claim проверяются execution, revision и соответствие созданному checkpoint; при изменении checkpoint нельзя молча переключиться на копию и обещать original identity. Exact сигнатуру общего owner-entry зафиксировать при сверке ExecutionRecovery/ActiveCheckpoint; отдельный ownership loop недопустим.

### 6.2. Найденные потребители checkpoint и точные обязанности

| Файл / класс или функция | Требуемая адаптация | Проверка |
|---|---|---|
| runtime/invocations/checkpointCodec.py / CheckpointCodec | Runtime ↔ wire, registry validation, один decode producer, resolve bound inputs | Cold restore identity и corrupted binding rejection |
| contracts/invocation/executionStore.py / Checkpoint.with_cancelled_child | Работать с wire metadata, сохранять payload/bindings без пересоздания domain objects | cancel_child меняет только разрешённый wait/status и revision |
| runtime/invocations/ownedExecution.py / _checkpoint | Conflict reread использует wire header/waits; не заменяет основной graph decoded-копией | Concurrent child cancellation сохраняет активные object identities |
| runtime/invocations/recovery/checkpointHeader.py / read_header | Читать wire header/session metadata | Registry/version/cursor mismatch отклоняется до CALL |
| runtime/invocations/recovery/executionRecovery.py / resume | Предварительное чтение только header/terminal metadata; active payload восстанавливает ActiveCheckpoint | Нет первого полного decode до active restore |
| runtime/invocations/recovery/activeCheckpoint.py / resume | Единственный full restore graph, затем восстановление snapshot из того же graph | Lifecycle validation и catalog используют те же объекты |
| runtime/dag/lifecycle/sessionRecovery.py / restore | Проверка cancellation через wire header | Нет domain payload decode ради статуса |
| runtime/invocations/interaction/executionInteraction.py / чтение, accept/cancel | Явно отделить header/wire update от active full restore; encode через новую wire границу | Input acceptance/cancellation CAS не теряет bindings и terminal data |
| runtime/invocations/inputWaitCoordinator.py / open/accept/event/validate | Сверить доступы к graph/record; existing WAIT_INPUT payload wire-контракт сохранить | WAIT_INPUT receipts, replay и intermediate validation не меняются |
| runtime/dag/dagExecutor.py / run_invocation и publication | Удалить post-run reload/decode ради публикации: публиковать payload из завершённого основного graph | Catalog/read/return сохраняют один экземпляр |
| runtime/invocations/sessionFrame.py / capture/restore | Различать referenced invocation outputs и собственные outputs других фаз | Нет второй owning сериализации той же execution identity |
| runtime/dag/lifecycle/executionSnapshotService.py / encode/decode | Передать graph для referenced outputs, сохранить самостоятельные snapshot paths | Durable и nondurable snapshot regressions |

Проверены поиском прямые InvocationGraph.model_validate_json, graph.model_dump_json, CheckpointCodec.encode/decode/restore в backend/app. При реализации повторить поиск с aliases/imports и проверить каждый caller, а не считать текстовый поиск доказательством отсутствия косвенных вызовов. Wire header parse допускается без повторного decode вложенных доменных JSON. Запрет повторного producer decode относится к одному active restore, а не к независимому процессу, который читает wire для cancellation.

### 6.3. Порядок перехода и проверка удаления

1. Принять точные runtime/wire и CALL binding контракты, включая owner-entry и версию checkpoint. Подготовить тесты fresh/public, cold READY restore и conflicts до замены.
2. В одном согласованном срезе заменить payload representation и codec, адаптировать найденные readers/writers, подключить typed mapping и удалить элементы §6.1. Не оставлять opt-in old/new transport или временный fallback.
3. Сверить diff по каждому файлу: сохранены исходные проверки, порядок CAS и ответственность; появились только согласованные контракты. Отдельно проверить входы public/direct и освобождение ресурсов на ранних ошибках.
4. Проверить отсутствие identity_required, live_coordinator, _coordinator_out, clear_live и invocation _live-cache в production Engine. Поиск _refresh/_remember ограничить затронутым coordinator, не удалять одноимённые механизмы других доменов.
5. Прогнать проверки D, public restore/cancellation/owner-loss, direct invocation, input waits и checkpoint cancellation в объёме затронутых readers. Старый тест, ожидающий blanket refusal unfinished resume, не переносить как требование нового варианта. Тесты должны проверять новый контракт и прежние гарантии ownership/replay.

Текущий поиск backend/tests не обнаружил тестов, использующих identity_required/live_coordinator/_coordinator_out/clear_live. Это состояние каталога тестов на момент сверки, не доказательство покрытия или разрешение удалить произвольные файлы.

Пункт «неизвестное происхождение текущего кода» закрыт пояснением пользователя. Открыты конкретная owner-entry сигнатура, полный непротиворечивый контракт удержания результатов разных attempts при replan, owning recovery начатого stage и междоменная приёмка. Эти вопросы нельзя закрыть одной сменой статуса плана.

## 7. Уточнение owner-entry, replan и начатой записи

Раздел заменяет открытый выбор owner-entry и правил удержания в §§5–6 конкретным предложением. Owning неизвестный исход записи остаётся отдельным подтверждённым разрывом, описанным ниже.

### 7.1. Один owner-entry для fresh и restore

В application/engine/runtime/invocations/recovery/freshExecution.py предложить runtime dataclass FreshExecution: graph: InvocationGraph, state: ExecutionState, plan: ExecutionPlan, checkpoint: Checkpoint. ExecutionState и ExecutionPlan в actual коде nongeneric. Пакет содержит основной graph/state и подтверждение create, без coordinator, claim, кеша или фоновой задачи. Это внутренний аргумент lifecycle; публичные Node Input/Output его не видят.

Сигнатуры дельты к существующим методам:

- ExecutionRecovery.resume(execution_id: ExecutionId, settings: InvocationOptions, max_passes: int, options: LLMExecutionOptions, confirmed: Mapping[str, DomainRevision] | None, cancellation: CancellationRequest | None, requested_task: TaskType | None = None, *, fresh: FreshExecution | None = None) -> ExecutionResult[O].
- ExecutionRecovery._resume_claimed — существующие аргументы плюс keyword-only fresh того же типа; не создавать второй метод с самостоятельным claim/renew loop.
- ActiveCheckpoint.resume — существующие аргументы, header теперь InvocationCheckpoint, плюс keyword-only fresh: FreshExecution | None = None. Для fresh использовать предоставленный graph/state/plan после проверки; для cold restore использовать codec и snapshot restore. После выбора — один путь OwnedExecution → PassExecution.run.

ExecutionAdmission до передачи пакета владеет state и освобождает его при ошибке create. Вызов resume(fresh=...) передаёт владение state recovery на время await. Recovery освобождает state при load/claim/header/fresh mismatch до запуска PassExecution; после передачи PassExecution существующий finally последнего освобождает state. Выход через terminal replay до PassExecution также освобождает неиспользованный fresh state. Для каждого пути тест считает release ровно один раз.

После claim повторно загрузить checkpoint и проверить execution/plan/registry, revision/status, отсутствие чужого stop intent и соответствие подтверждённому create checkpoint. Несовпадение — existing RestoreFailure/OwnershipConflict до CALL с освобождением ресурсов. Не подменять fresh graph восстановленным и не терять original identity. Checkpoint в FreshExecution — immutable wire receipt, не второй изменяемый graph. Работа с store.create API не меняется; receipt строится из созданного blob и проверяется фактическим load под claim.

Существующий run_with_lease остаётся единственным циклом renew/drain/release для public пути. Ни FreshExecution, ни ActiveCheckpoint не захватывают claim. В direct run_invocation свежий graph аналогично сохраняется как основной после проверки созданного checkpoint; его уже существующая область claim/release остаётся локальной, без handoff наружу.

Критерий ответственности FreshExecution: только перенос ссылок и receipt; отказ при методах load/claim/run/release, дополнительном payload registry или публичной сериализации state/plan. Остальные классы и критерии — §6.1.

### 7.2. Replan: current results и каскадная invalidation

Источник: docs/tz_engine_node_context.md, текущий DAGContext/ResultInvalidation; current results снимаются вместе с фактическими потребителями, старые read views могут жить, но их evidence не разрешает новую публикацию. Не вводить архив payload разных attempts или самостоятельный writer поверх каталога.

Binding source содержит полную ExecutionIdentity. Пока producer reusable и не инвалидирован, все действующие bindings указывают на его существующий runtime-объект; replan не копирует payload и не переписывает source revision на новую.

Если producer снимается, до очистки terminal вычислить транзитивное множество потребителей по existing reads И bound-input source. Проверить все invocation instances, а не только record.plan_instance_id текущего root: сейчас next_pass ограничивает обход instance и поэтому недостаточен для bound CALL между siblings. Снять current outputs и зависимые inputs/continuations, которые используются следующим исполнением, согласованно с DAGContext invalidation. Затем очистить снимаемые record slots. Исторические diagnostics/caller metadata не дают права читать прежний payload.

Новая attempt создаёт новую ExecutionIdentity; parent формирует новый bound CALL из её CallSuccess. Старую source identity нельзя автоматически перепривязать. Stale literal/checkpoint binding отклоняется existing contract/restore failure до consumer CALL. Снятый current result не становится доступным через старый каталог или wire snapshot; lifecycle snapshot фиксируется после согласованной invalidation.

Старый read view может удерживать Python-ссылку до конца своей работы, как допускает ТЗ; это не архив Engine и не разрешение publish. После удаления всех обычных ссылок объект освобождается штатно; отдельный reference-count registry/GC не нужен.

Replan выполняется на существующей границе после завершения активных workers. Если обнаружен активный bound consumer, transition не очищает его source частично и не стартует новый pass до existing drain. Invalidation определяет пригодность данных, а разрешение повторять эффектную ноду остаётся существующей execution/retry/owning политикой. Новый binding не делает stage идемпотентным.

Тесты: reuse сохраняет is; смена producer attempt инвалидирует bound consumers другого invocation instance; старый view не публикуется; новый CALL получает новую identity; current checkpoint не содержит dangling binding; отсутствие архива `_live`/history payload. При invalidation consumer поле bound description очищается вместе с input, а не остаётся ссылкой на снятый producer.

### 7.3. Начатый stage: доказанный внешний контрактный разрыв

Обновление согласования 2026-11-26: Publication и Artifacts поддержали предложенную единую stage-attempt authority у Artifacts при сохранении operation lifecycle/transaction infrastructure Publication. Точный пакет и остающиеся gates — [контракт stage recovery](artifacts-stage-recovery-contract.md). Ниже сохранены основание запроса и existing статус; full API/production recovery ещё не приняты.

Actual публичные классы находятся в application/artifacts/staging/artifactOpenPipeline.py (не в отдельных целевых файлах старого плана): ArtifactPrepareStageOpenPipeline.prepare_stage(request: ArtifactPrepareStageInput[C]) -> PreparedArtifact[C]; async ArtifactStageOpenPipeline.stage(request: ArtifactStageInput[C]) -> ArtifactRef. Stage выполняет admission.stage → descriptors.check → await ArtifactStageWriter.write(lease, prepared).

Writer в artifactStageWriter.py выполняет require_standalone → validate descriptor → assert_writable → reserve → backend.write → writer claim → assert_writable/verify/assert_writable → seal → event. Проверка этого тела не доказывает безопасный повтор при потере ответа. В gen-dag-artifacts-node-contracts.md §4 явно указано: закрытый/READY lease не разрешает повторный stage, exact replay принадлежит lifecycle-владельцу, unknown не означает отсутствие effects.

В InvocationCoordinator.__init__ существует безусловное RUNNING → READY. Для данного stage это не может быть основанием recovery: процесс мог потерять ответ после seal. Не использовать descriptor как доказательство seal/hold и не вызывать storage/catalog из ноды или Engine для выяснения исхода.

Ответ Artifacts, переданный пользователем 2026-11-26: публичного контракта восстановления исхода отдельного stage нет. Publication владеет operation recovery/terminal; Artifacts владеет staging evidence и admission. Прежняя формулировка «владелец recovery — Artifacts» уточнена этим ответом.

Existing ArtifactStagingService.recover(operation_id: EntityUid) -> OperationRecord в application/artifacts/staging/artifactStaging.py делегирует Publication OperationLedger.recover(operation_id: EntityUid) -> OperationRecord[R] в application/publication/service/operationLedger.py. Это observation всей операции: phase/fence/leased artifacts/terminal, не решение о replay отдельного stage. По ответу владельца SQLite recovery для APPLYING/RECOVERY_REQUIRED бросает OperationBusyError. Ответ владельца — источник этих сведений; независимый runtime PASS не заявляется.

OperationLeaseRef и PreparedArtifact идентифицируют запрос/binding, но не доказывают seal конкретного вызова. Наличие descriptor, sealed storage, leased_artifacts или writable admission по отдельности не разрешает replay. Отсутствие hold после cancel не доказывает отсутствие прежнего seal. Успех stage подтверждает seal/hold на seal commit, не после concurrent cancel.

| Состояние / evidence | Подтверждённая владельцем граница |
|---|---|
| Engine сохранил terminal stage-result | Перенести результат без повторного stage |
| RUNNING и потерянный ответ | Автоматический повтор не разрешён существующим контрактом |
| Lease writable | Допуск записи не доказывает безопасность recovery-повтора |
| READY/closed lease | Повтор stage запрещён; возможен owning refusal |
| Подтверждённая отмена/stale fence | Старый stage не повторять; прошлые эффекты не исключены |
| UnknownCommitOutcome | Не преобразовывать в успех, отсутствие effects или разрешение retry |

Совместный пакет уже спроектирован в [owning resolution](artifacts-stage-recovery-owning-resolution.md) и [Publication resolution](artifacts-stage-recovery-publication-resolution.md): StageBinding, StageAttemptPermit, StageRecoveryInput, ArtifactAuthorizedStageInput, public begin/recover и различимые Confirmed/Allowed/Refused/Unresolved. [Engine resolution](dag-stage-recovery-transition-resolution.md) предъявляет REPORT_UNKNOWN и переход к явному recovery CALL. Это предложенные, ещё не полностью принятые контракты; повторное проектирование пакета не требуется. Историческое описание existing API выше не описывает статус этих proposals.

Автоматическое восстановление после потери процесса выделяется в отдельный этап: без backend proof quiescence consumed non-completed stage остаётся Unresolved, без successor и без освобождения hold по timeout. Это ограничение не блокирует независимую реализацию штатной записи после приёмки её локального контракта. Свежий маршрут и cold restore после prepare при stage READY остаются отдельным проверяемым транспортным объёмом; их PASS не закрывает полный restart. Подключение конкретного workflow требует producer/persistence stage_id и общей проверки DAG mapping.

Актуальный статус: owner-entry, current-result invalidation и stage-recovery delta спроектированы, полная приёмка остаётся OPEN по реестру [SR-01–SR-05](artifacts-stage-recovery-contract.md). Штатная запись, подключение workflow и automatic crash recovery имеют отдельные границы приёмки; отсутствие последнего не означает отсутствие проекта первых двух. Этот статус заменяет историческое утверждение «контрактная дельта ещё не спроектирована».
