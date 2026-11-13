# DAG Pack / Source: дополнение A1, A2, A4

Дата: 2026-11-14. Только проект, **не приёмка и не разрешение реализации**. Дополнение к dag-pack-source-binding-response-2026-11-14.md. Учтены исправленные next_index и single settlement description в execution-binding. Общие Pack документы, NodeId, родство и порядок 1–7 не меняются. A3 конкретизирует Pack owner.

## A1. Полный фазовый carrier семи шагов

**Основание отсрочки PACK-METADATA-PLANNING (пользователь, 2026-11-14):** отсутствуют согласованные публичные контракты результатов и зависимостей гидрологии, климата, settlement и других производителей. Mapping metadata → Planning уточняется по мере принятия соответствующих доменных контрактов, а не выводится из legacy trace. До этого он остаётся отложенным интеграционным вопросом без фиктивных значений и без блокировки текущего Pack scope; см. owning раздел в pack-v2-public-write-operations.md.

Предлагаемый модуль: dataModel/engine/nodes/pack/sourceExchangeContinuation.py. Все следующие POJO strict/frozen/extra-forbid/revalidate-always, поля обязательны. Это state DAG, не новые поля PackPreparationState. Target не хранится как caller-controlled объект: для каждой фазы фиксирован upper CallTarget.

Общий PackSourceRouteContext:

| Поле | Тип / назначение |
|---|---|
| prepared_write | PackSettlementStructureInput; полный готовый вход шага 4 с исходным state, part/provenance/territory/status/preserve полями. Переиспользуется owning POJO, отдельного зеркала prepared payload нет |
| usage_request | PackMetadataUsageRequestsInput; полный исходный state/fields шага 1 |
| describe_request | PackMetadataSubjectsInput; полный шаблон шага 5, ровно одна settlement строка; актуальный state подставляется после write |
| metadata_planning | tuple[PlanDependency, ...]; готовое Planning основание **metadata строки**, отдельное от provenance payload в prepared_write.part |

Контекст сохраняется целиком до bind. На входе все три state должны относиться к одному исходному snapshot; fields и describe subject относятся к settlement prepared_write. Никакого объединения Planning dependencies в DAG. **Отложенная интеграция PACK-METADATA-PLANNING:** действует прямое решение пользователя из [write-plan](pack-v2-public-write-operations.md#отложенный-вопрос-pack-metadata-planning--разрешённая-заглушка-проекта): незавершённый mapping не блокирует разработку или приёмку текущего Pack scope. Поле metadata_planning выше — кандидат места хранения для будущего полного binding, не новая обязательная предпосылка независимого Pack. Producer и необходимость прямой Planning зависимости уточняются отдельно по фактическим входам; автоматически брать payload planning, подставлять () или фиктивный PlanRef нельзя. Новую Planning стадию/тип этот документ не вводит и повторного согласования отсрочки не требует.

Подстановка state означает создание валидируемого нового owning input с прежними остальными полями, не mutation и не доверенный model_copy без валидации. prepared_write не исполняется до шага 4.

Предлагаемые варианты поля phase у PackSourceRouteContinuation:

| Concrete POJO / discriminator | Все поля помимо phase | Ожидаемый верхний CALL / следующий переход |
|---|---|---|
| PackSourceRequestsPhase / "usage_requests" | context: PackSourceRouteContext; key: CallKey | read_pack(DescribePackMetadataUsageRequestsInput(request=context.usage_request)); результат формирует calls и SELECT wait |
| PackSourceSelectionsPhase / "select" | context: PackSourceRouteContext; wait: PackSourceSelectionWait | read_source(SelectSourceProofInput(request=wait.calls[wait.next_index].requested.request)); prefix дополняется, затем очередной SELECT либо import |
| PackSourceImportPhase / "import" | context: PackSourceRouteContext; key: CallKey; request: PackMetadataUsageImportInput | write_pack(ImportPackMetadataUsageInput(request=request)); result state подставляется в context.prepared_write |
| PackSourceWritePhase / "settlement_write" | context: PackSourceRouteContext; key: CallKey; request: PackSettlementStructureInput | write_pack(WritePackSettlementStructureInput(request=request)); result state подставляется в context.describe_request |
| PackSourceDescribePhase / "describe" | context: PackSourceRouteContext; key: CallKey; request: PackMetadataSubjectsInput | read_pack(DescribePackMetadataInput(request=request)); ровно одна matching description; создаётся groups request |
| PackSourceAdmissionPhase / "admit_groups" | context: PackSourceRouteContext; wait: PackSourceGroupsWait | read_source(AdmitSourceProofGroupsInput(request=wait.source_request)); формируется bind input |
| PackSourceBindPhase / "bind" | context: PackSourceRouteContext; key: CallKey; request: PackMetadataProvenanceInput | write_pack(BindPackMetadataProvenanceInput(request=request)); bound state передаётся существующему продолжению detailed_initialization, не READY |

PackSourceRouteContinuation имеет ровно поле phase: discriminated union этих семи named POJO по их строковому phase. Этот envelope — кандидат **exchange-ветки** continuation detailed_initialization, не замена состояний получения detailed_bake_initialization и последующей publication. Полный внешний continuation этого caller ещё не объявлен; его точное имя/union/registration нельзя выдумать из таблицы exchange.

При первом SELECT wait.state = context.usage_request.state; completed=(); next_index=0; calls — неизменяемый ordered результат шага 1 с ключами select/{index}. Ключи остальных фаз — usage_requests, import_usage, settlement_write, describe_metadata, admit_groups, bind_metadata. Это локальные CallKey одного parent, не новые NodeId. Для каждого save в SELECT wait: 0 <= next_index < len(calls), len(completed)=next_index и точное соответствие prefix исходным requests. Завершённый prefix переносится в request.entries следующего ImportPhase; прежние events не запрашиваются. Пустой результат не создаёт wait: только допустимый owning empty import либо owning отказ, как в execution-binding.

Admission wait.state = DescribePhase.request.state; description — единственный проверенный output; source_request.groups механически копируются из ordered dependencies[].source_usage. Bind request.state = wait.state; entry.subject и groups[].group/basis берутся из wait.description, selections из успешного Source output по позиции, source_request/result сохраняются целиком. Общий Source proof берётся из result.admission.proof; Planning — context.metadata_planning через **owning принятую форму PackPartProvenance**, не конструируется из Source. Exact constructor ветви PackPartProvenance и metadata_planning producer остаются owning boundary, а не разрешением придумать DTO.

На каждой фазе результат извлекается только по её key и фиксированному upper target; upper kind/value должны соответствовать ожидаемой операции. SourceFailure остаётся в SourceNodeError; PackPreparationError — в PackPreparationNodeError. Required failure завершает маршрут без следующего CALL; CallCancelled передаётся runtime cancellation, CallRuntimeFailure — runtime failure, без domain remapping/retry. Неожиданный variant/event — runtime contract failure. После завершённого bind exchange не повторяет write/describe и не запускает prepare самостоятельно.

**Граница полноты A1:** фазовый carrier и сохранение prepared/state предъявлены. Реальный gate полного маршрута — включение exchange-ветки в полный caller continuation и exact mapping принятых Pack/Source inputs/results. PACK-METADATA-PLANNING отдельно остаётся отложенной интеграцией: отсутствие metadata_planning producer не является условием продолжения или приёмки независимого Pack и не должно возвращаться как такой gate. Его отсрочка не объявляет весь production маршрут принятым. Порядок не меняется.

## A2. Широкие unions сохраняются; capability ограничивает dispatch

Предыдущее предложение сужать верхние schemas для первого scope здесь заменено вариантом без сужения. ReadPackInput/Output, WritePackInput/Output, ReadSourceInput/Output сохраняют формы one/all и все объявленные общими проектами варианты. Актуальные дополнения describe_usage_requests/import/select/admit_groups включаются ровно по leaf-contracts. Source общий exact union пока не полностью freeze; перечисленные там OPEN нельзя считать готовыми runtime типами. Это явный оставшийся compile-time gate, а не runtime unknown command.

Поддержанные команды первого binding: read_pack — DescribePackMetadataUsageRequestsInput и DescribePackMetadataInput; write_pack — ImportPackMetadataUsageInput, WritePackSettlementStructureInput, BindPackMetadataProvenanceInput; read_source — SelectSourceProofInput, AdmitSourceProofGroupsInput. На read поддерживается только one. All остаётся структурно корректным входом общего контракта, но не поддерживается этим binding.

**Отказ без заглушки и без новой ошибки:** start сначала проверяет concrete вариант команды по статической таблице capability. Для неподключённого варианта/all поднимает NotImplementedError с фиксированным сообщением "command is not supported by this node binding", до любого CallTarget.request. NodeRunner.run_resumable переводит это в FAILED с runtime diagnostic (тип исключения), без успешного output, без owning domain error и без retry_policy. Неизвестный kind, не входящий в общий union, отклоняется structural validation ещё раньше. Это предлагаемая явная эксплуатационная политика binding; её необходимо согласовать, поскольку широкий schema union сам по себе не обещает реализацию каждой операции. Если требуется typed unsupported response, минимальное **изменение контракта** — новый engine-owned declared error и расширение error_types всех затронутых callers; здесь оно не вводится.

### Точные кандидаты верхних bindings

Все три — ResumablePythonNode, frozen, deps=(), phase=PRE_LLM, skip_on_replan=False; explicit input required. reads=(), input_wait=None, retry_policy=None, error_policy=None; lifecycle=None только как historical materialized result, не holds guarantee. Executor — existing PythonNodeExecutor; register_resumable, а не register_python. Leaf contracts остаются из leaf-contracts.

| Класс / существующая проектная роль | I / O / declared E | NodeContract ID / ContinuationContract ID; version обоих "1" |
|---|---|---|
| ReadPackNode / read_pack | ReadPackInput / ReadPackOutput / PackPreparationNodeError | engine.pack.read / engine.pack.read.continuation |
| WritePackNode / write_pack | WritePackInput / WritePackOutput / PackPreparationNodeError | engine.pack.write / engine.pack.write.continuation |
| ReadSourceNode / read_source | ReadSourceInput / ReadSourceOutput / SourceNodeError | engine.source.read / engine.source.read.continuation |

Строковые IDs — предложения, не numeric IDs и не изменение NodeId. Перед реализацией collision check; расширение capabilities/схем с несовместимым restore требует версионирования.

ReadPackWait: command: DescribePackMetadataUsageRequestsInput | DescribePackMetadataInput; key: CallKey. WritePackWait: command: ImportPackMetadataUsageInput | WritePackSettlementStructureInput | BindPackMetadataProvenanceInput; key: CallKey. ReadSourceWait: command: SelectSourceProofInput | AdmitSourceProofGroupsInput; key: CallKey. Discriminator command.kind; состояние поддерживает только исполнимые команды, общий input/output union остаётся широким. Эти три named BaseModel — точные state_type соответствующих ContinuationContract. Модуль проекта dataModel/engine/nodes/pack/upperContinuation.py и source/upperContinuation.py. В каждом upper start key=CallKey("operation"), единственный CALL; resume возвращает только output этого CALL в existing one/result envelope. Никакого batch/fallback.

calls ReadPackNode — targets describe_pack_metadata_usage_requests и describe_pack_metadata; WritePackNode — import_pack_metadata_usage, write_pack_settlement_structure, bind_pack_metadata_provenance; ReadSourceNode — select_source_proof, admit_source_proof_groups. Каждый target полностью равен регистрации leaf из leaf-contracts: NodeId, ContractId, version, input/output/error types. Неподключённые команды не имеют фиктивных targets. Три upper contract instances — READ_PACK_CONTRACT, WRITE_PACK_CONTRACT, READ_SOURCE_CONTRACT; static targets берутся из этих экземпляров для coordinator, не из пользовательского ввода.

Фабрики-кандидаты make_read_pack_node() -> ReadPackNode, make_write_pack_node() -> WritePackNode, make_read_source_node() -> ReadSourceNode не принимают services/store/container и не запускают домены. Статические accepted targets принадлежат модулю регистрации. Leaf factories получают только PackPreparationService либо SourceProofPipelineOpenPipeline по своему домену.

register_pack_exchange_upper_nodes(registry: NodeRegistry) -> None регистрирует две Pack upper; register_source_exchange_upper_nodes(registry: NodeRegistry) -> None — одну Source upper. Explicit bootstrap: зарегистрировать семь leaf, затем три upper, предоставить их фабрики GraphBindings, затем precompile; отсутствие leaf/continuation/несовместимость target — bootstrap failure. Import-time registration запрещена. Exact production composition caller пока отсутствует (A4); общий detailed_initialization контракт не заменяется только тремя calls: существующий prepared-child binding сохраняется.

**Остаток A2:** принять политику runtime unsupported и proposed identities; freeze полного Source union и существующих широких Pack owning вариантов для компиляции; предъявить concrete detailed_initialization external I/O/continuation/registration. Отсутствующие типы не заменять Any, и не объявлять этот документ готовым к компиляции.

## A4. Фактический entry/store/restore и отсутствующая граница

Проверенные существующие классы (пути относительно backend/app):

| Boundary | Реальный код / проверяемая гарантия |
|---|---|
| Прямой внутренний entry | application/engine/runtime/dag/dagExecutor.py::DAGExecutor.run_invocation принимает plan/execution_id/root/revision/store/input; create при отсутствии, claim, load, CheckpointCodec.restore; сверяет execution/revision/root и exact initial input; finally release |
| Session admission | application/engine/runtime/dag/lifecycle/executionAdmission.py::ExecutionAdmission.run использует settings.store и LifecycleBinding.compile; не является сам по себе auth endpoint |
| Session recovery | application/engine/runtime/invocations/recovery/executionRecovery.py::ExecutionRecovery.resume загружает checkpoint, claim/heartbeat; ActiveCheckpoint.resume компилирует через LifecycleBinding, вызывает CheckpointCodec.restore и сверяет revision/root |
| Memory store | application/engine/runtime/invocations/memoryExecutionStore.py::MemoryExecutionStore — in-process snapshots, lease/fence/revision; не durable production recovery |
| SQLite store | db/repositories/sqlite/dagExecutions/executionStore.py::SQLiteExecutionStore — sqlite connection, persisted checkpoints, version/checksum, ownership fence/lease/CAS; SHA256 checksum обнаруживает повреждение, но не аутентифицирует автора blob |
| Codec | application/engine/runtime/invocations/checkpointCodec.py::CheckpointCodec — JSON schema/registry/parent linkage; optional lifecycle.validate_restored только для SUCCEEDED outputs |
| Checkpoint writer | application/engine/runtime/invocations/ownedExecution.py::OwnedExecution — сохранение через ExecutionStore с claim/revision; это execution ownership, не user/tenant authorization |

По поиску в backend/app не найдено создание SQLiteExecutionStore/MemoryExecutionStore в production composition данного маршрута; определения классов есть. InvocationOptions используется infrastructure, но concrete Pack/Source runtime registration и production initiating/resume endpoint для detailed_initialization в этом scope не предъявлены. Поэтому нельзя назвать существующий production trust binding готовым.

**Точно отсутствующее звено:** application composition, выбирающая server-owned connection/store и полный registry/GraphBindings для accepted route, плюс entry/resume caller, связывающий внешнего пользователя/мир с допустимым ExecutionId и pinned/prepared inputs. owner_id lease — идентификатор worker, не доказательство права пользователя на execution. Внешний caller не должен выбирать store/blob/terminal/continuation/prior_outputs; prior_outputs допускаются только из контролируемого engine context. Нужен источник/срок удержания pinned base и prepared artifacts на всём exchange/resume; Source success сам holds не создаёт.

Минимальное решение без изменения engine contracts: конкретная server-side composition существующего SQLiteExecutionStore + существующий engine entry/recovery; initiating API принимает только разрешённый domain request, resume — разрешённый ExecutionId; server выбирает root/revision/store/registry/owner. Auth/ownership может принадлежать существующему application layer, но точный класс должен быть указан владельцем composition. Никакого нового checkpoint token/store/Source метода не требуется. Недоверенный imported checkpoint не поддерживается. Это предложение инфраструктурного binding вне текущей реализации, не новый NodeId и не стадия 1–7.

JSON transport сохраняет complete prepared/state/continuation; numeric CanonicalSchema registration не подменяет Pydantic validation. Для реализуемых Pack/Source контрактов нужен конкретный nested roster и round-trip/lifetime binding. Это не требование разрешить отложенный PACK-METADATA-PLANNING до независимого Pack scope. lifecycle=None не восстанавливает holds на input/continuation. Test-only композиция с MemoryExecutionStore докажет CALL/replay механику, но не production auth/durability.

## Итог review дополнения

Три запрета DAG сохраняются: dispatch принадлежит coordinator/upper через engine, каждый leaf делает один owning public call, Pack↔Source прямых вызовов нет. POJO удерживают данные и correlation, не алгоритмы/IO. Общие unions и порядок сохранены. Предъявлены полный семифазовый carrier, exact upper binding candidates и реальная инфраструктурная трасса с точным отсутствующим production звеном. **Полная production-приёмка не объявлена:** остаются полный внешний caller contract, широкий Source union, unsupported policy и production trust/lifetime; A3 остаётся у Pack owner. **Отдельно:** PACK-METADATA-PLANNING отложен пользователем и не блокирует разработку/приёмку текущего независимого Pack scope; фиктивные значения не вводятся. Код и runtime тесты не менялись.
