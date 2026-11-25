# Source mutation: внешний контракт ноды

2026-11-25. По поручению пользователя проверен существующий engine transport и зафиксирована node-level дельта. Это проект конкретного binding, не реализация/регистрация и не подключение к write_changes. Owning источник: source-mutation-node-pojo-card.md. Внутренние assert_allowed, composition, replay, storage и CommitScope OUT.

## Класс и размещение

Target класс SourceRegistryMutationNode: backend/app/application/engine/nodes/source/sourceRegistryMutationNode.py. Семейство Source, один корень nodes/source/, одна нода — один файл — один класс. Target node POJO: backend/app/dataModel/engine/nodes/source/mutationContracts.py. Регистрация отдельно nodes/source/registration.py; NodeId/ContractId не назначены этой фиксацией. Parent/CALL consumer не назначен.

## Input / Output / Error

Все wrappers strict/frozen/extra-forbid/revalidate-always, поля required. Owning DTO используются вложенно, без зеркальных полей.

| Node POJO | Поля |
|---|---|
| SourceRegistryMutationInput | request: owning app.dataModel.sourceVersioning.sourceRegistryMutation.SourceRegistryMutationInput |
| SourceRegistryMutationOutput | value: SourceMutationApplied \| SourceMutationRefused \| SourceFailure \| OperationCancelled |
| SourceMutationPhaseNodeError(NodeError) | refusal: app.dataModel.publication.pregameMutationRefusal.PregameMutationRefusal |
| SourceMutationBindingNodeError(NodeError) | mismatch: app.dataModel.publication.operationBindingMismatch.OperationBindingMismatch |

Node и owning Input имеют разные модули; при импорте использовать явный alias owning типа, не вторую domain модель. Proposed mutation result типы принадлежат sourceMutationOutcome, SourceFailure — sourceErrors, OperationCancelled — existing artifacts.lifecycle.operation.record; полные owning поля задаёт owning карточка.

Один public вызов: await SourceRegistryMutationPipelineOpenPipeline.apply(input.request). Public module: app.application.worldData.sourceVersioning.operations.registryMutationPipelineOpenPipeline. reads=(), calls=(); public method не child node CALL. E = SourceMutationPhaseNodeError | SourceMutationBindingNodeError; error_types — эти два exact concrete класса.

| Public outcome | Node mapping |
|---|---|
| Любой вариант return union | SourceRegistryMutationOutput(value=result) без преобразования |
| PregameMutationRefusedError | raise PythonNodeError(SourceMutationPhaseNodeError(refusal=exc.refusal)) from exc |
| OperationBindingMismatchError | raise PythonNodeError(SourceMutationBindingNodeError(mismatch=exc.mismatch)) from exc |
| OperationBusyError / UnknownCommitOutcome / PublicationInfrastructureError / другие exceptions | Не перехватывать в leaf; existing engine exception path |
| asyncio.CancelledError | Existing engine cancellation control path |

OperationCancelled внутри value — authoritative returned outcome, не asyncio cancellation. Phase error не превращается в SourceFailure/durable refusal. Типы, enum identity, refs и порядок issues сохраняются; Python object identity после штатной revalidation не гарантируется. args/traceback не сериализуются.

## Почему нужны два carrier

Проверен actual NodeRunner.run: только PythonNodeError проходит validate_error против NodeContract.error_types и сохраняется как typed outcome.error. Обычный Exception превращается в FAILED с именем exception в detail, без typed payload. PythonNodeExecutor лишь вызывает execute. Existing универсальный carrier для этих двух owning payload в проверенных engine POJO не найден; существующий Snapshot carrier имеет другой payload и не расширяется.

Два carrier сохраняют публичные POJO, не создают новый error framework. Для остальных исключений новый carrier без owning typed payload не придумывается. Existing engine FAILED не является доказательством absence of effects/rollback или safe retry; категория unknown/busy не становится структурированным POJO автоматически. Потребитель, которому нужна машинная развязка этих категорий, требует отдельной публичной error-дельты до такого подключения. Автоматический retry/recovery здесь не вводится.

## Рёбра и статус

Внешний готовый typed request → input.request → public apply; public result → output.value. Generator/gameplay producer OUT. Следующий consumer не назначен. SourceMutationApplied не является native section/PatchSet и не направляется в assemble_patch_set/apply_snapshot. Отсутствие consumer не блокирует независимый owning метод, но сквозного маршрута пока нет.

Owning mutation DTO/method и phase error — proposal, не existing runtime. Error roster подтверждён Source проектно. Эта карта фиксирует необходимый engine mapping, не заявляет полный runtime PASS. Для реализации нужны actual owning imports и node identity/registration; внутренние domain implementation вопросы не становятся полями ноды или новыми DAG gates.

Проверки при реализации: один public call; все return variants; exact payload двух ошибок в outcome.error; отсутствие output при ошибке; cancellation отдельно; malformed/undeclared NodeError rejected; no retry; JSON/Python roundtrip owning payload; регистрация без дублей. Spy evidence не подтверждает исполнение Source mutation.
