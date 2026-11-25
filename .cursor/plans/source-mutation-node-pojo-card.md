# Source pregame registry mutation — node POJO card

Node-level Input/Output/Error и проверенный engine transport зафиксированы отдельно: [DAG Source mutation contract](dag-source-mutation-node-contract.md). Эта карта остаётся источником owning public POJO; engine wrappers/carriers её не заменяют. Внутренние методы доменов не входят в приёмку ноды.

2026-11-25. OWNER PROPOSAL для координатора. **Node contract unchanged** относительно mutation contract §8.1: последние after-graph/execution-version изменения не меняют поля request/result. NodeId, CALL, producer/consumer nodes и маршруты этим документом не назначаются. Recovery/prune OUT.

## Роль и public метод

Логическая роль: применить один pregame registry mutation request. Предложенный модуль `app.application.worldData.sourceVersioning.operations.registryMutationPipelineOpenPipeline`, класс `SourceRegistryMutationPipelineOpenPipeline`, метод `async apply(request: SourceRegistryMutationInput) -> SourceMutationApplied | SourceMutationRefused | SourceFailure | OperationCancelled`.

Метод и mutation POJO спроектированы в source-core-mutation-contract.md, не заявлены реализованными/принятыми. Existing SourceFailure, refs, identities, OperationCancelled и publication exceptions существуют. Thin node только передаёт request и возвращает value; не выполняет доменную validation/recovery и не превращает result в Snapshot PatchSet.

## Owning input

Предложенный import `app.dataModel.sourceVersioning.sourceRegistryMutation`:

| POJO | Все обязательные поля |
|---|---|
| SourceRegistryMutationInput | operation_id: EntityUid; world_uid: EntityUid; execution_version: Annotated[StrictInt, Field(ge=1)]; changes: tuple[SourceRegistryChange, ...]; membership: SourceCollectionMutation |
| SourceRegistryCreate | kind: Literal[SourceRegistryMutationKind.CREATE]; identity: RegistryMemberId; body: ArtifactRef |
| SourceRegistryUpdate | kind: Literal[SourceRegistryMutationKind.UPDATE]; expected: SourceVersionRef; body: ArtifactRef |
| SourceRegistryDelete | kind: Literal[SourceRegistryMutationKind.DELETE]; expected: SourceVersionRef |
| SourceCollectionMutation | collection_id: SourceCollectionId; expected_revision: SourceRevision \| None; body: ArtifactRef |

SourceRegistryChange = discriminated union Create/Update/Delete, discriminator kind; enum wire create/update/delete. Все поля required, nullable не optional. Strict/frozen/deep immutable/extra-forbid; changes непустые, unique/canonical, один world/member descriptor; §1 owning contract содержит инварианты. Existing refs/identity types переиспользуются, не разворачиваются в зеркальные node DTO.

## Owning output и исключения

Предложенный import `app.dataModel.sourceVersioning.sourceMutationOutcome`:

| Вариант value | Все обязательные поля / смысл |
|---|---|
| SourceMutationApplied | operation_id: EntityUid; world_uid: EntityUid; request_fingerprint: RevisionHex; object_revisions: tuple[SourceVersionRef, ...]; collection_revisions: tuple[SourceCollectionVersionRef, ...]. Confirmed success |
| SourceMutationRefused | operation_id: EntityUid; world_uid: EntityUid; request_fingerprint: RevisionHex; failure: SourceFailure. Confirmed terminal refusal |
| SourceFailure | operation: SourceOperation; field_issues: tuple[SourceFieldIssue, ...]; logic_issues: tuple[SourceLogicIssue, ...]. Existing app.dataModel.sourceVersioning.sourceErrors; здесь только preflight refusal |
| OperationCancelled | operation_id: EntityUid; reason: OperationCancellationReason (REQUESTED="requested"). Existing app.dataModel.artifacts.lifecycle.operation.record; authoritative terminal cancellation, не business refusal |

SourceLogicIssue: code: SourceLogicCode; group_index/use_index: nonnegative strict int | None; source: SourceVersionRef | SourceCollectionVersionRef | None; artifact: ArtifactRef | None. Предложенные MEMBERSHIP_MISMATCH, MUTATION_REFERENCE_CONFLICT, REVISION_NOT_FOUND, REVISION_PRUNED передаются в existing carrier unchanged. Node не перекодирует их; mapping потребителя не назначен. Наличие кода в proposal не означает runtime enum registration.

Окончательный **proposed** declared exception roster для apply (не runtime/пользовательская приёмка):

| Exception | Public payload / propagation |
|---|---|
| app.application.publication.errors.PregameMutationRefusedError (proposal) | `.refusal: app.dataModel.publication.pregameMutationRefusal.PregameMutationRefusal`, unchanged |
| app.application.publication.errors.OperationBindingMismatchError (existing) | `.mismatch: app.dataModel.publication.operationBindingMismatch.OperationBindingMismatch`, unchanged |
| app.application.publication.errors.OperationBusyError (existing) | Typed payload отсутствует |
| app.application.publication.errors.UnknownCommitOutcome (existing) | Typed payload отсутствует; отдельная категория до базового PublicationInfrastructureError |
| app.application.publication.errors.PublicationInfrastructureError (existing) | Typed payload отсутствует |

Return union окончательного предложения остаётся SourceMutationApplied | SourceMutationRefused | SourceFailure | OperationCancelled, поля приведены выше. Иные runtime/programming exceptions (включая Pydantic ValidationError при нарушении internal typed preconditions) и asyncio.CancelledError распространяются без превращения в business value. Этот список declared ошибок не обещает подавления неожиданных исключений и не разрешает сериализовать их args/traceback.

PregameMutationRefusal required payload: code: Literal[PregameMutationRefusalCode.GAMEPLAY_STARTED]; operation_id: EntityUid; world_uid: EntityUid; request_fingerprint: RevisionHex. Owning enum из того же модуля имеет wire `publication.pregame_mutation.gameplay_started`. Strict/frozen/extra-forbid/revalidate-always, без defaults. Python принимает exact owning enum member, не plain string/foreign enum; JSON string декодируется в owning member. Эти гарантии — proposal Publication, не проверенная runtime поставка. Source apply распространяет exception и `.refusal` неизменными, не создаёт SourceFailure/SourceMutationRefused и не добавляет вариант return. Payload не является свидетельством terminal/rollback; owning UnknownCommitOutcome не понижается до фазового отказа.

OperationBindingMismatch required payload: operation_id: EntityUid; requested_kind/stored_kind: OperationKind; requested_world_uid/stored_world_uid: EntityUid; requested_preparation_fingerprint/stored_preparation_fingerprint/requested_request_fingerprint: RevisionHex; stored_request_fingerprint: RevisionHex | None. Это existing owning модель, не Source error mirror. Фазовый transport теперь конкретизирован owning proposal publication-pregame-mutation-phase-contract.md; отсутствие типа в runtime не означает отсутствия проекта.

## Thin node и поля рёбер

### Результат узкой сверки координатора и error boundary

2026-11-25: координатор подтвердил PASS только mapping request → apply → value. Операция остаётся неподключённой pregame mutation; отсутствие consumer не блокирует самостоятельный owning метод и не разрешает подключение к assemble_patch_set/apply_snapshot.

Для Error mapping явно различаются: OperationBindingMismatchError — единственный из перечисленных existing publication exceptions с declared typed payload `.mismatch`; OperationBusyError — без typed payload; UnknownCommitOutcome — без typed payload, обрабатывается отдельно до его базового PublicationInfrastructureError; PublicationInfrastructureError — без typed payload. Exception args, traceback и произвольные attributes не являются контрактом сериализации. Остальные runtime/programming exceptions — unhandled infrastructure failure, не расширяемый business union; engine handling принадлежит DAG. asyncio.CancelledError распространяется как cancellation, не как возвращённый OperationCancelled. Source не создаёт общий exception serializer.

**Фазовое error edge спроектировано:** Publication предъявил PregameMutationRefusedError, Source подтверждает unchanged propagation в apply. Предложенный roster выше завершён для данной узкой сверки. Окончательное пользовательское принятие и runtime реализация не заявлены. DAG владеет node Error mapping; CommitScope не входит в Input/Output/Error, новые CALL не назначаются.

Рекомендованная форма, без назначения новых class names/imports DAG: Input имеет единственное required `request: SourceRegistryMutationInput`; Output — единственное required `value: SourceMutationApplied | SourceMutationRefused | SourceFailure | OperationCancelled`. Оба immutable; domain DTO передаются целиком.

| Producer Output.field | Node Input.field → argument | Public result → Node Output.field | Следующий consumer Input.field |
|---|---|---|---|
| Внешний typed input: SourceRegistryMutationInput; producer node не назначен и вне scope | request → apply(request=request) | весь return union → value | Не назначен: требуется consumer field принимающий этот union либо согласованная orchestration-развязка его вариантов |
| Не применимо: exception не producer POJO | тот же вызов | declared exception/cancellation распространяется; Output не создаётся | Engine exception handling, конкретный POJO mapping не заявлен |

Готовая форма внешнего input не означает наличие runtime класса. Generator/gameplay producer здесь не проектируется. SourceMutationApplied — outcome завершённой pregame операции, не section для нового commit. Незамкнутое ребро ровно `Output.value → consumer.Input.<не назначено>`; Source не выбирает consumer или ветвление. Existing/proposed различия и конкретизированный phase error transport предъявлены координатору отдельно от внутренних implementation gates.
