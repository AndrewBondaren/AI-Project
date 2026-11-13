# Pack / Source: concrete leaf contracts первого маршрута

Дата: 2026-11-14. Статус: CONTRACT PROPOSAL. Caller detailed_initialization и [последовательность 1–7](pack-source-first-route-review.md) согласованы. Здесь предъявляются имена/классы/POJO/registration для их проверки; код, новые runtime NodeId и canonical numeric IDs не создаются.

## 1. Имена и единственные owning вызовы

Все строки — отдельные PythonNode с explicit invocation input, без своего CALL/continuation/выбора следующей стадии. Caller leaf — соответствующая верхняя read_pack/write_pack/read_source нода через engine. Пять Pack leaf получают PackPreparationService; две Source leaf — SourceProofPipelineOpenPipeline через composition. Ни одна не получает другой домен.

| Шаг | Предлагаемый NodeId / concrete класс | Модуль под application/engine/nodes | Один owning вызов |
|---|---|---|---|
| 1 | describe_pack_metadata_usage_requests / DescribePackMetadataUsageRequestsNode | pack/describePackMetadataUsageRequestsNode.py | service.describe_metadata_usage_requests(input.request) |
| 2 | select_source_proof / SelectSourceProofNode | source/selectSourceProofNode.py | await pipeline.select(input.request) |
| 3 | import_pack_metadata_usage / ImportPackMetadataUsageNode | pack/importPackMetadataUsageNode.py | service.import_metadata_usage(input.request) |
| 4 | write_pack_settlement_structure / WritePackSettlementStructureNode | pack/writePackSettlementStructureNode.py | service.write_settlement_structure(input.request) |
| 5 | describe_pack_metadata / DescribePackMetadataNode | pack/describePackMetadataNode.py | service.describe_metadata(input.request) |
| 6 | admit_source_proof_groups / AdmitSourceProofGroupsNode | source/admitSourceProofGroupsNode.py | await pipeline.admit_groups(input.request) |
| 7 | bind_pack_metadata_provenance / BindPackMetadataProvenanceNode | pack/bindPackMetadataProvenanceNode.py | service.bind_metadata_provenance(input.request) |

Pack methods sync в проекте; async execute leaf не делает их IO. Source methods async/read-only: чтение owning artifacts, без capture creation/holds/publication. Повторный вызов другого публичного метода внутри leaf запрещён. Lifecycle Source refs не выводится из успеха leaf.

## 2. Exact DAG POJO

Модули `dataModel/engine/nodes/pack/contracts.py` и `dataModel/engine/nodes/source/contracts.py` из существующего DAG-проекта. Каждый Input имеет **ровно** `kind: Literal[NodeId строки]`, `request: owning тип ниже`; Output — **ровно** `kind: тот же Literal`, `value: owning тип ниже`. Обязательные поля без defaults; strict/frozen/extra-forbid/revalidate-always. Это расширение уже проектных node command wrappers, не второй domain DTO. Concrete классы, не public generic aliases.

| Input / Output классы | request | value |
|---|---|---|
| DescribePackMetadataUsageRequestsInput / DescribePackMetadataUsageRequestsOutput | PackMetadataUsageRequestsInput | tuple[PackMetadataUsageRequest, ...] |
| SelectSourceProofInput / SelectSourceProofOutput | SourceProofSelectInput | SourceProofResult |
| ImportPackMetadataUsageInput / ImportPackMetadataUsageOutput | PackMetadataUsageImportInput | PackPreparationState |
| WritePackSettlementStructureInput / WritePackSettlementStructureOutput | PackSettlementStructureInput | PackPreparationState |
| DescribePackMetadataInput / DescribePackMetadataOutput | PackMetadataSubjectsInput | tuple[PackMetadataDescription, ...] |
| AdmitSourceProofGroupsInput / AdmitSourceProofGroupsOutput | SourceProofGroupsInput | SourceProofGroupsResult |
| BindPackMetadataProvenanceInput / BindPackMetadataProvenanceOutput | PackMetadataProvenanceInput | PackPreparationState |

Owning Pack declarations и exact fields — [exchange](pack-source-exchange-contract.md), [metadata POJO](pack-metadata-dependency-pojo.md), [write-plan](pack-v2-public-write-operations.md); Source imports — app.dataModel.sourceVersioning.sourceProofSelection/sourceProofGroups/sourceProofResult. SourceFailure — app.dataModel.sourceVersioning.sourceErrors. Wrapper output не копирует input state, proof, world или дополнительный operation ID для проверки корреляции: эту связь держит engine.

Существующие проектные PackReadCommand/PackReadItemOutput дополняются DescribePackMetadataUsageRequestsInput/Output; DescribePackMetadataOutput меняет value на descriptions. PackWriteCommand/PackWriteItemOutput дополняются ImportPackMetadataUsageInput/Output; три остальные write пары переиспользуются. Это изменение closed unions, а не разрешение unknown kinds. SourceReadCommand/SourceReadItemOutput для данного среза содержат две пары Select/AdmitGroups; прочие Source операции не регистрируются автоматически. Общий будущий union расширяется отдельно при подключении READ/VERIFY_GROUPS/ADMIT.

Верхние ReadOnePackInput/ReadOneSourceInput и WritePackInput остаются existing проектными wrappers; точное соответствие command → output проверяется. All-read для этого маршрута не нужен и не становится обязательным. Верхние ноды вызывают leaf через declared CallTarget, не вызывают domain service напрямую.

## 3. Ошибки и mapping

- PackPreparationFailure(exc.error: PackPreparationError) → existing проектный PackPreparationNodeError(NodeError, error: PackPreparationError) → PythonNodeError. Имя и единственное поле сверены с DAG-планом §6.5 (Pack read/write); второй carrier не создаётся.
- SourceFailure как результат Source pipeline → SourceNodeError(NodeError, error: SourceFailure) → PythonNodeError. Успешный SourceProofResult не содержит failure. SourceProofFailure не вводится.
- Infrastructure/cancellation/unknown outcome не перехватываются общим except с превращением в domain отказ. Engine сохраняет свои outcomes. Leaf не выбирает retry и не делает fallback.
- Структурные ошибки node input обслуживает engine; domain validation сохраняет owning diagnostics. Произвольный ValueError не переводится в SOURCE_PROOF_MISMATCH. Pack semantic codes из metadata-проекта остаются на owning приёмке, не создаются заново в DAG.

## 4. Registration и runtime effects

Образец существующей реализации: [Cache registration](../../backend/app/application/engine/nodes/cache/registration.py), [ReadCacheEntryNode](../../backend/app/application/engine/nodes/cache/readCacheEntryNode.py). Каждая leaf: `async prepare_input(view)` отклоняет отсутствие explicit input; `async execute(input)` делает один owning вызов; frozen node с dependency, переданной фабрикой; skip_on_replan=False как отсутствие обещания повторного использования результатов. Импорт модуля ничего не регистрирует.

Предлагаемые ContractId:

| NodeId | ContractId |
|---|---|
| describe_pack_metadata_usage_requests | engine.pack.metadata.describe_usage_requests |
| select_source_proof | engine.source.proof.select |
| import_pack_metadata_usage | engine.pack.metadata.import_usage |
| write_pack_settlement_structure | engine.pack.settlement.write_structure |
| describe_pack_metadata | engine.pack.metadata.describe |
| admit_source_proof_groups | engine.source.proof.admit_groups |
| bind_pack_metadata_provenance | engine.pack.metadata.bind_provenance |

Engine ContractVersion первоначально "1" как required transport identity, не версия доменного алгоритма и не V1/V2 название реализации. IDs — кандидаты; перед регистрацией повторить collision check по актуальному registry. Поиск новых select/admit_groups/usage identifiers в runtime при подготовке документа совпадений не выявил.

NodeContract для каждой строки: input_type/output_type из §2; error_types=(соответствующий concrete NodeError,); reads=() — нет чтений других DAG outputs, все domain inputs явно переданы; calls=(); continuation=None; input_wait=None; retry_policy=None; error_policy=None. Reads=() не означает отсутствия Source IO. Source storage/retention принадлежат owning pipeline и его принятому binding.

Registration candidates: `register_pack_source_exchange_nodes(registry)` в pack/registration.py регистрирует пять Pack leaf; `register_source_proof_exchange_nodes(registry)` в source/registration.py — две Source leaf через registry.register_python(NodeClass, PythonNodeExecutor, contract). Это два bootstrap registration вызова, не service locator и не новый runtime orchestrator. Production bootstrap/factories принимаются отдельно; после согласования не регистрировать дубль уже поставленного узла.

У верхних нод calls содержит CallTarget разрешённых leaf. У detailed_initialization calls содержит верхние read_pack/read_source/write_pack, а не чужие domain services. Последовательность и continuation — [execution binding](pack-source-dag-execution-binding.md). NodeId родство не создаётся автоматически из CALL. Restore lifecycle нельзя объявить закрытым по model_validate: нужно проверить transport registration вложенных owning типов и связь восстановленного результата с execution lineage; Artifact holds не восстанавливаются одним codec.

## 5. Роли и критерии приёмки

Результат фактической документальной проверки 2026-11-14: [приёмка семи leaf contracts](pack-source-leaf-acceptance.md) — полный маршрут не принят, замечания A1–A4. Основные пробелы: sequential continuation, upper bindings, единый bind/error freeze, transport/restore. Ни caller, ни порядок повторно не открываются.

Для каждой из семи Node classes: ответственность — одна owning операция и error adapter; допустимая зависимость — только свой service/pipeline. DoD — exact request/result, один вызов, отказ на чужой kind; нарушение — hidden orchestration, повтор public calls, Source algorithm в Pack/DAG, side-store.

Для каждой Input/Output пары: только поля §2, строгие вложения, соответствие kind/owning типу, canonical round-trip. Для error carriers: один owning error без копий code/message. Для registration/factories: единственная binding identity, отсутствие import-time side effects, согласованные dependencies. Для верхних нод: только engine dispatch/aggregation, без owning algorithms. Для coordinator: сохранённый snapshot и correlation, без публикации child-нодой. Для NodeContract/CallTarget/InvocationCoordinator/CallResults/PythonNodeExecutor: existing typed checks и exact execution linkage; их ответственность не расширяется этой карточкой.

Обязательные проверки с engine registry/executor: happy path 1–7; Source failure без последующего import/write; old attribution refusal; None preserve/explicit empty; mixed A/B dependencies; source response от другого CALL; state подмена; одинаковый status с другим basis/usage; duplicate groups; cancellation; canonical restore; conflicting replay key/input/continuation. Последующие prepare/holds/activation не объявляются проверенными этим набором.

Статус: concrete leaf предложения предъявлены, единый Pack error adapter сверён. Полная приёмка требует согласования NodeIds/classes/contracts и верхних calls, canonical registration/restore, owning Pack POJO freeze. Не менять caller/порядок повторно, не блокировать независимые срезы. Реализация только отдельным implement-plan scope после прохождения обязательных критериев.
