# Pack / Source: binding результата через engine CALL

Дата: 2026-11-13. Статус: PROPOSED для приёмки. Конкретизирует [Pack exchange inputs](pack-source-exchange-contract.md) и [DAG §6.7](gen-dag-cache-pack-source-families.md). Код, NodeId и новый порядок не вводятся; Source API не меняется.

## 1. Проверенная основа engine

- [CallTarget.request](../../backend/app/application/engine/contracts/invocation/callTarget.py) формирует typed CallRequest(key,target,input).
- [InvocationCoordinator](../../backend/app/application/engine/runtime/invocations/invocationCoordinator.py) разрешает только contract.calls, сохраняет serialized input и caller_invocation_id/caller_step/call_key. Replay key с другим node/input либо иной continuation отклоняется.
- Coordinator формирует CallSuccess из terminal output child конкретного parent step. [CallResults.get](../../backend/app/application/engine/contracts/invocation/resumeEvent.py) проверяет key/target и output/error type.
- [ContinuationContract](../../backend/app/application/engine/contracts/invocation/continuationContract.py) задаёт тип сохраняемого state; invocation record содержит continuation и её contract identity.

Это статическая трассировка, не runtime acceptance. CallSuccess можно сконструировать в Python: доверие обеспечивается контролируемым registry/executor/store и кодом принимаемых нод, не фактом наличия dataclass. Production Source/Pack registrations и защищённость checkpoint restore этим не доказаны.

## 2. Кандидаты DAG continuation POJO

Модуль-кандидат `dataModel/engine/nodes/pack/sourceExchangeContinuation.py`. Strict/frozen/extra-forbid, обязательные поля, owning Pack/Source типы переиспользуются. Имя класса не назначает coordinating node или parent relation.

| POJO | Все поля |
|---|---|
| PackSourceSelectionCall | key: CallKey; requested: PackMetadataUsageRequest |
| PackSourceSelectionWait | state: PackPreparationState; calls: tuple[PackSourceSelectionCall, ...] |
| PackSourceGroupsWait | state: PackPreparationState; description: PackMetadataDescription; key: CallKey; source_request: SourceProofGroupsInput |
| PackSourceClosureCall | key: CallKey; request: SourceProofReadInput |
| PackSourceClosureWait | body: PackPreparationBody; calls: tuple[PackSourceClosureCall, ...] |

Target не приходит от внешнего caller: он фиксируется accepted CallTarget в contract.calls. ClosureWait.body содержит source_closures=() до получения ответов и не передаётся final prepare в неполном виде. Body не содержит continuation. Для verify_groups предъявленный result находится в exact typed child input, сохранённом engine; successful output не заменяется исходным недоверенным carrier.

Continuation удерживает именно snapshot Pack state, из которого сформированы запросы. После возврата Source importer/bind получает этот snapshot, не latest state по world_uid и не иной state с равным status. При выборе другого state прежние результаты не переносятся автоматически. Это локальная последовательность одного exchange, не глобальная блокировка других workflows.

## 3. Mapping к Pack inputs

| Этап | Что сохраняет DAG | Что берёт из успешного CALL | Принимающий Pack input |
|---|---|---|---|
| Historical select | state и PackMetadataUsageRequest каждого key | SourceProofResult от соответствующего SELECT | PackMetadataUsageImportInput(state, entries), где entry.requested из continuation, result из CALL |
| Grouped admission/verification | state, description, source_request | SourceProofGroupsResult | PackMetadataProofBinding(subject, provenance, source_request, source_result, groups); enclosing PackMetadataProvenanceInput.state из continuation |
| Closure read | body с конечным state/capture/scope и запросы по всем proofs | SourceProofResult каждого READ | Новый body с теми же state/capture/scope и source_closures: tuple[PackSourceClosureResolution, ...] |

В bind subject/group keys/basis берутся из сохранённого description; selections — из output по исходной позиции; общий proof — result.admission.proof. Planning — по отдельному owning binding, не из Source. Pack проверяет exact локальные subject/basis и equality перенесённых данных, но не исполняет Source subset/union алгоритм.

Import принимает полный набор групп каждой запрошенной строки согласно exchange, не частичный Description. Для closure требуется полный набор proofs конечного state; при отсутствии Source dependencies допускается явно пустой набор. Failure одного required вызова не даёт partial success. SourceFailure/Cancelled/RuntimeFailure не превращаются в successful resolution и не запускают скрытый retry.

На обоих уровнях read_source → operation leaf сохраняются exact request и owning output; получение результата другого экземпляра по одному NodeId запрещено. Используется engine CALL, не прямой execute другой ноды. Concrete coordinating caller, upper/leaf contracts, keys и deps ещё должны быть приняты. Список calls не означает разрешение параллельного CallGroup.

## 4. Доверенная граница и resume

Внешний запрос инициирует работу, но не подставляет engine ReturnedCall, terminal или continuation с готовыми Source results. Production Pack exchange допускает только контролируемый engine result path. Прямой вызов importer/bind с произвольным JSON success не считается supported Source admission. Это требование регистрации/entrypoint, не проверяемый секретный флаг в Pack input.

После resume результат child используется только с его engine lineage и exact восстановленной continuation. Пока integrity/ownership источника checkpoints и exact restore binding не приняты, arbitrary persisted success не доказывает исполнение. Для недоверенного select result остаётся исполнение SELECT над сверенным запросом через DAG; READ subset и VERIFY_GROUPS его не заменяют. Автоматический повтор/новая нода этим документом не назначаются.

Source read success не удерживает refs. Перед READY остаётся внешний publication entry/target lifetime над принятым internal Source adoption. Ни CALL identity, ни неизменность state не заменяют atomic hold checks.

## 5. Приёмка и остаток

Проверки через реальные engine registrations/test nodes: чужие key/target/type; replay с другим input/continuation; два одновременных экземпляра одинаковой ноды; перестановка ответов разных groups; equal-value/different-usage; state A против B; required failure/cancellation; resume сохранённого exact request; недоверенный checkpoint; release после READ до adoption. Только Python-конструирование CallSuccess в тесте этих гарантий не доказывает.

SourceNodeError оборачивает единый SourceFailure из sourceErrors; исторический SourceProofFailure не создавать. PackPreparationFailure/diagnostic union сохраняются. Новый error domain, token или receipt store не вводится.

Конкретный механизм предложен на существующем CALL. До реализации требуется приёмка coordinating caller/leaf bindings и порядка, continuation canonical registration/restore, error adapters и новых Pack публичных signatures из exchange. Source дополнительных методов для этой передачи не требует. Это не объявление полной готовности Pack или запрет независимых срезов.
