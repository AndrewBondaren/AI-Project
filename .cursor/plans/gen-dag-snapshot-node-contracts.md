# Snapshot: POJO четырёх согласованных DAG-нод

2026-11-14. Состав согласован пользователем: read_snapshot над read_snapshot_metadata/read_snapshot_publication; apply_snapshot самостоятельно, без write_snapshot. Текущий документ предъявляет POJO и mapping для совместной приёмки. Код и регистрация не выполняются. Другие callers, generators, detailed_initialization и legacy-ноды не подключаются.

Основания: snapshot-public-methods-contract.md (публичные signatures/read/fault proposals); snapshot-retention-cancel-diagnostics-contract.md (актуальная принятая R1–R3, исторические OPEN ниже её заголовка не переоткрываются); текущие PatchSet, DomainSection, SnapshotApplyResult и SnapshotOperationCancelledError. Публичных apply/read_snapshot/read_publication в просмотренном WorldSnapshotService ещё нет: внутренние методы не используются вместо них. Runtime поиск новых node names/classes коллизий в engine не выявил.

## 1. Собственные контракты operation нод

Проектный модуль backend/app/dataModel/engine/nodes/snapshot/contracts.py. Все модели strict=True, frozen=True, extra="forbid", revalidate_instances="always"; все поля обязательны, без defaults. Owning records используются вложенно. Никаких Any, dict, services, scope, callbacks в POJO.

| POJO | Полный состав полей |
|---|---|
| ReadSnapshotMetadataInput | kind: Literal["read_snapshot_metadata"]; snapshot: SnapshotRef |
| ReadSnapshotMetadataOutput | kind: Literal["read_snapshot_metadata"]; value: SnapshotReadResult |
| ReadSnapshotPublicationInput | kind: Literal["read_snapshot_publication"]; request: SnapshotPublicationReadInput |
| ReadSnapshotPublicationOutput | kind: Literal["read_snapshot_publication"]; value: SnapshotPublicationReadResult |
| ApplySnapshotInput[S: DomainSection] | patch_set: PatchSet[S] |
| ApplySnapshotOutput | value: SnapshotApplyResult |
| SnapshotNodeError(NodeError) | error: SnapshotPublicFault |

kind у двух read пар нужен для закрытого command/result union верхней ноды. Это предложение конкретных полей поверх согласованного состава, не изменение owning read API. Apply отдельный, поэтому лишний discriminator операции ему не нужен.

| Нода | I → O; declared error | Единственный public call / mapping |
|---|---|---|
| read_snapshot_metadata | ReadSnapshotMetadataInput → ReadSnapshotMetadataOutput; SnapshotNodeError | await WorldSnapshotService.read_snapshot(input.snapshot); result → output.value, kind сохраняется |
| read_snapshot_publication | ReadSnapshotPublicationInput → ReadSnapshotPublicationOutput; SnapshotNodeError | await WorldSnapshotService.read_publication(input.request); result → output.value, kind сохраняется |
| apply_snapshot | конкретный named ApplySnapshotInput → ApplySnapshotOutput; SnapshotNodeError и отдельная граница отмены ниже | await WorldSnapshotService.apply(input.patch_set); result → output.value |

Read result metadata/publication=None — успешное отсутствие exact записи. Ошибка не преобразуется в None. read_publication — exact world_uid/publication_id, не latest. SnapshotApplyResult COMMITTED/CONFLICT/REJECTED сохраняется целиком; SUCCESS исполнения ноды не означает COMMITTED операции. Следующий caller обязан различать owning category. Нода не вычисляет fingerprints, не собирает section payload и не вмешивается в transaction/retention/CAS.

### Конкретизация apply

Generic ApplySnapshotInput[S] — декларация формы, **не готовый input_type для регистрации**. Нужен отдельно принятый закрытый union конкретных DomainSection с их owning patch DTO и один named nongeneric input class поверх этой специализации. Не подставлять DomainSection/BaseModel как универсальную секцию, не регистрировать один NodeId многократно с несовместимыми типами. Набор секций и имя concrete binding здесь не выдуманы; это оставшееся решение с пользователем/владельцем Snapshot. Поля PatchSet и их порядок сохраняются, existing проверки expected_world/players/section keys не дублируются в node wrapper.

## 2. read_snapshot: typed команды и результаты

В том же модуле:

| POJO / alias | Поля / состав |
|---|---|
| SnapshotReadCommand | ReadSnapshotMetadataInput \| ReadSnapshotPublicationInput; discriminator kind |
| SnapshotReadItemOutput | ReadSnapshotMetadataOutput \| ReadSnapshotPublicationOutput; discriminator kind |
| ReadOneSnapshotInput | kind: Literal["one"]; request: SnapshotReadCommand |
| ReadAllSnapshotInput | kind: Literal["all"]; requests: tuple[SnapshotReadCommand, ...] |
| ReadSnapshotInput | command: ReadOneSnapshotInput \| ReadAllSnapshotInput; discriminator command.kind |
| ReadOneSnapshotOutput | kind: Literal["one"]; value: SnapshotReadItemOutput |
| ReadAllSnapshotOutput | kind: Literal["all"]; values: tuple[SnapshotReadItemOutput, ...] |
| ReadSnapshotOutput | result: ReadOneSnapshotOutput \| ReadAllSnapshotOutput; discriminator result.kind |

Вертикальные черты в ячейках обозначают union типов. ReadSnapshotInput → ReadSnapshotOutput, declared error SnapshotNodeError. Верхняя нода не получает WorldSnapshotService: только engine CALL к двум согласованным read нодам. Один запрос вызывает одну соответствующую leaf. Для all предлагается последовательное чтение явного непустого списка, без сканирования хранилища и поиска дополнительных зависимостей. Непустота — ограничение новой aggregate команды, не изменение owning read методов. Политика all предъявляется для приёмки, параллельный запуск не предполагается.

All output сохраняет длину, порядок, variant и owning request/result identity каждого элемента. Повтор одинакового запроса допускается как отдельное чтение; дедупликация не выполняется. Это набор результатов отдельных операций, **не общий атомарный snapshot двух reads**: каждый public read открывает свой scope. Никакого scope/capability в DAG. При required failure/отмене полный успешный AllOutput не возвращается; normal not-found остаётся элементом результата и не прерывает список.

Проектный модуль dataModel/engine/nodes/snapshot/readContinuation.py:

- SnapshotReadOneWait(command: SnapshotReadCommand, key: CallKey).
- SnapshotReadAllWait(requests: tuple[SnapshotReadCommand, ...], next_index: StrictInt, completed: tuple[SnapshotReadItemOutput, ...], key: CallKey).
- SnapshotReadContinuation(wait: SnapshotReadOneWait | SnapshotReadAllWait) — для exact transport добавить обязательные kind="one"/"all" в соответствующие wait и discriminator wait.kind.

В all wait 0 <= next_index < len(requests), len(completed)=next_index; completed[j] соответствует requests[j]. На resume принимается только текущий key/фиксированный target, append один раз, затем следующий singleton CALL либо итоговый output. event не используется для поиска результатов прежних шагов. Данные accumulator — engine continuation, не owning Snapshot DTO. Имена contract IDs/version и окончательная registration отдельно принимаются после POJO; сейчас новые identities не назначаются.

## 3. Ошибки и отмена

SnapshotPublicError(fault) → PythonNodeError(SnapshotNodeError(error=fault)); SnapshotPublicFault остаётся owning proposal, его поля/enum не копируются. Structural ошибки внешнего POJO обрабатывает existing engine validation; собственных FieldPathError/code дублей нет. Snapshot бизнес-отказ остаётся в SnapshotApplyResult. Не перехватывать любые исключения с превращением в domain success/refusal.

Обычный asyncio.CancelledError — runtime cancellation. Existing SnapshotOperationCancelledError содержит сохранённый owning OperationCancelled, а не SnapshotPublicFault. Его нельзя потерять через вымышленный SnapshotPublicFailureKind или выдать за SnapshotApplyResult. **Открытый точный binding:** как сохранить OperationCancelled и его operation identity в engine cancellation/result transport apply_snapshot. Предложений нового NodeError с копиями cancellation fields здесь нет. До совместного решения apply error/cancellation contract не считается завершённым. R2 Snapshot при этом не переоткрывается.

BUSY не запускает скрытый retry, OUTCOME_UNKNOWN не означает rollback и не превращается в REJECTED. Повтор apply использует исходный PatchSet и owning immutable operation binding; нода не генерирует новый operation_id. Replay engine исторического output не является новым применением; новый вызов регулируется Snapshot terminal replay. Read output — наблюдение metadata, не pin/hold и не обещание доступа к blobs.

## 4. Роли классов, эффекты и критерии отказа

| Класс/группа | Ответственность / допустимые зависимости | Проверка и отказ |
|---|---|---|
| ReadSnapshotMetadataNode, ReadSnapshotPublicationNode (проект) | Один public read; DI WorldSnapshotService | Exact input/result/error; отказ при latest fallback/SQL/repair/другом public call |
| ApplySnapshotNode (проект) | Один public apply; DI WorldSnapshotService | PatchSet без изменений; отказ при сборке чужих patches, commit/CAS внутри ноды |
| ReadSnapshotNode (проект) | Только dispatch двух read targets и ordered aggregation | Отказ при direct service call, новом target или объявлении aggregate общей transaction |
| Все Input/Output/Wait выше | Только immutable данные и correlation | Все и только перечисленные поля; отказ при IO/dispatch/storage handles/зеркале owning fields |
| SnapshotNodeError | Один owning fault в existing NodeError | Отказ при перекодировании owning причин или дублировании field errors |
| NodeContract/CallTarget/NodeRegistry, NodeRunner/InvocationCoordinator | Existing typed registration/execution/step correlation | Проверить concrete types, JSON round-trip и replay; нет второго executor |
| WorldSnapshotService и public input validator | Owning validation и атомарная операция по Snapshot public plan | DAG не вызывает private helpers; отказ при hidden междоменной orchestration |
| Snapshot history/exact publication stores и SqlitePublicationCommitStore | Existing scoped read/transaction реализация за public service | Scope не выходит в DAG; отказ при независимом node commit |
| SectionRegistry/handlers, metadata builder, artifact holders | Existing Snapshot apply internals по owning плану | Порядок validation/apply/metadata/handoff/CAS/terminal сохраняется; не превращаются в DAG-ноды |

Нет import-time registration. Production caller/родство вне четырёх нод не назначаются. До реализации требуется полный актуальный roster применяемых concrete section handlers и внутреннего apply trace от Snapshot owner; не вводится связь с генераторами.

## 5. Обязательная проверка проекта и остаток

| Критерий | Вывод |
|---|---|
| Три запрета DAG | Dispatch только в read_snapshot через engine, leaf один public call, прямых междоменных вызовов нет. Runtime ещё не реализован |
| Ответственность каждого класса | Роли выше; concrete section roster пока неизвестен — полная implementation-приёмка не пройдена |
| Public / implementation | Exact три signatures из Snapshot proposal, private helper bypass исключён. Public read/fault реализация не предъявлена как готовая |
| Порядок | Согласованные четыре роли сохранены; owning apply порядок не меняется. Sequential all — отдельное предложение для принятия |
| CRUD данных C/U | Только apply по existing PatchSet, не произвольная запись immutable row |
| CRUD данных R | Exact snapshot metadata / exact historical publication |
| CRUD данных D | Не входит: публичного delete этому срезу не назначено |
| CRUD настроек C/R/U/D | Ни одна из четырёх операций настроек этим node scope не вводится; полный domain CRUD не объявлен принятым |
| Междоменный протокол | Вход — owning Snapshot POJO, public owner Snapshot, результат — node wrapper; foreign producer contracts/новые маршруты не добавлены |
| POJO/field/logic errors без дублей | Owning DTO reuse; node wrappers имеют engine command/result ответственность. Cancellation mapping пока OPEN, ложная универсальная ошибка не вводится |

Состав нод согласован; POJO данного документа предъявлены пользователю, **не полная приёмка реализации**. Для read осталось принять поля/one-all семантику и owning public fault/read contracts, затем конкретный engine binding. Для apply — concrete section specialization и OperationCancelled transport, готовность публичного apply. Эти вопросы не требуют проектировать detailed_initialization или использовать legacy-ноды. Код и тесты не менялись.

## 6. Read binding — конкретизация по поручению «Делай»

Scope: только три согласованные read-ноды. Проектные модули application/engine/nodes/snapshot/readSnapshotMetadataNode.py, readSnapshotPublicationNode.py, readSnapshotNode.py, registration.py. Первые две — PythonNode с DI WorldSnapshotService; верхняя — ResumablePythonNode без service/store. Все frozen, phase=PRE_LLM, deps=(), skip_on_replan=False, reads=(), input_wait/retry_policy/error_policy=None. prepare_input отклоняет отсутствие explicit invocation input как configuration failure до IO. OutputLifecycle=None: сохранённый результат — историческое наблюдение, не право читать blobs и не current head.

| NodeId / класс | NodeContract ID, version="1" | I / O / E | calls / continuation |
|---|---|---|---|
| read_snapshot_metadata / ReadSnapshotMetadataNode | engine.snapshot.read_metadata | ReadSnapshotMetadataInput / ReadSnapshotMetadataOutput / SnapshotNodeError | (); None |
| read_snapshot_publication / ReadSnapshotPublicationNode | engine.snapshot.read_publication | ReadSnapshotPublicationInput / ReadSnapshotPublicationOutput / SnapshotNodeError | (); None |
| read_snapshot / ReadSnapshotNode | engine.snapshot.read | ReadSnapshotInput / ReadSnapshotOutput / SnapshotNodeError | два exact leaf CallTarget из строк выше; SnapshotReadContinuation |

ContinuationContract: contract_id="engine.snapshot.read.continuation", version="1", state_type=SnapshotReadContinuation. Это предложенные строковые engine identities, не numeric canonical IDs. Публичные node I/O — named BaseModel; SnapshotRef вложен в ReadSnapshotMetadataInput, union не передаётся как input_type NodeContract.

Factories: make_read_snapshot_metadata_node(service: WorldSnapshotService) -> ReadSnapshotMetadataNode; make_read_snapshot_publication_node(service: WorldSnapshotService) -> ReadSnapshotPublicationNode; make_read_snapshot_node() -> ReadSnapshotNode. register_snapshot_read_nodes(registry: NodeRegistry) регистрирует обе leaf через register_python, верхнюю через register_resumable; executor class existing PythonNodeExecutor. GraphBindings предоставляет три экземпляра до GraphCompiler.precompile. Импорт ничего не регистрирует; новый production caller не назначается.

На start one сохраняет SnapshotReadOneWait(kind="one",command,key=CallKey("one")) и возвращает existing Call(key,target,input,state). Для all новая команда требует хотя бы один request; первый wait next_index=0/completed=(), key="item/0". После каждого успешного event.get(wait.key, fixed_target) верхняя нода проверяет соответствующий output variant и owning request identity, дополняет prefix и возвращает следующий Call с key="item/{index}" либо Complete(ReadSnapshotOutput(...)). Никаких прямых execute, callback и CallGroup. Target определяется конкретным command variant, не внешней строкой service method.

CallFailure(SnapshotNodeError) передаётся через PythonNodeError без изменения fault; CallCancelled — runtime cancellation; CallRuntimeFailure — runtime failure без преобразования в Snapshot fault и без дальнейшего CALL. Проверка correlation не заменяет owning проверку metadata/ref. Пустой all отклоняется структурно до первого CALL. Malformed независимые поля проверяются existing validation с агрегацией; новый validator framework не нужен.

### Проверка фактической готовности 2026-11-14

В WorldSnapshotService имеются private apply helpers, но публичных read_snapshot/read_publication пока нет. Не найдены runtime SnapshotReadResult, SnapshotPublicationReadInput/Result, SnapshotPublicFault/SnapshotPublicError. Нужные storage ports уже существуют: ISnapshotHistoryStore.read и IExactWorldPublicationReader.read_exact; они не подменяют public service. ТЗ tz_world_snapshot.md содержит более общий проект SnapshotQuery/read (§интеграции), тогда как snapshot-public-methods-contract.md предъявляет два exact метода; перед кодом owning Snapshot должен согласовать нормативную публичную границу, не оставлять два конкурирующих read API по умолчанию.

**Конкретная зависимость до реализации нод:** поставка двух public reads и их named I/O/error POJO по snapshot-public-methods-contract.md, с owning read-scope/identity/error mapping. Изменять Snapshot internals вместо вызова отсутствующего public метода или создавать локальный fake service ради зелёных тестов не разрешается. Отсутствие public reads не связано с apply/R1–R3/генераторами/Planning.

Обязательная приёмка read-среза: роли и exact engine binding предъявлены; порядок one/all явный; C/U/D данных и C/R/U/D настроек этим срезом не исполняются. Полная приёмка реализации не пройдена по критерию public contract/implementation: отсутствует вызываемая публичная граница и её runtime модели. Подготовка DAG binding не объявляет owning Snapshot proposal принятым. Это точечная зависимость, не новое требование пересмотреть состав нод.

После поставки owning reads проверить через реальный service и engine: world/player metadata found/missing, exact publication found/missing, corrupt identity не None, обе one команды, mixed ordered all и повторяющиеся запросы, empty/malformed input до IO, failure/cancel без следующих reads, binary/error/continuation JSON round-trip, два одинаковых NodeId в разных invocations, checkpoint replay без повторных уже завершённых reads. Новые invocation читают актуальную доступность; replay возвращает historical outputs. Read scopes открывает только сервис; no writes/holds/repair. Эти проверки запланированы, не выполнены.
