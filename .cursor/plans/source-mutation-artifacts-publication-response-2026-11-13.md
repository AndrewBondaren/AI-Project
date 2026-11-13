# Ответ Artifacts/publication по Source mutation

2026-11-13. Контрактное предложение, DESIGN OPEN. Подготовлено по P2.3–P2.5 source-pregame-revision-staging-design.md. Приёмка SourceDurableProof и R1/R2 является исходной зависимостью. Документ фиксирует обсуждение refusal/recovery и root acquisition; реализация требует отдельной приёмки.

## Refusal после подтверждённого rollback

Рекомендуется terminal отказа. Один operation_id связывается с окончательным результатом. Exact replay возвращает исходный отказ. Исправленный запрос или новые expected revisions используют новую operation identity.

Source-owned SourceMutationRefused в backend/app/dataModel/sourceVersioning/sourceMutationOutcome.py содержит operation_id, world_uid, request_fingerprint и failure: SourceFailure. Record frozen/strict/extra-forbid/revalidate-always. Failure.operation равен APPLY_MUTATION; исходные issues и порядок сохраняются. Envelope связывает отказ с запросом в общем ledger.

Предлагается discriminator source_mutation_refused, category=None. OperationRecord проверяет SOURCE_MUTATION, world, operation identity и request fingerprint. Terminal union, StoredTerminalCodec, manifest и storage checks требуют совместной регистрации. Canonical IDs остаются OPEN.

SourceMutationRollback в backend/app/application/worldData/sourceVersioning/sourceMutationErrors.py переносит SourceFailure через внешнюю transaction boundary. ConfirmedRollback в backend/app/application/publication/contracts/rollbackEvidence.py — непрозрачная runtime capability coordinator. Она связана с database/coordinator, transaction attempt, operation identity и lease/fence. Выдаётся только после подтверждённого rollback. Точный rollback-carrier API остаётся OPEN.

Предлагаемые internal signatures:

```python
def transaction_for_claim(
    claim: PublicationOwner,
) -> AbstractAsyncContextManager[CommitScope]: ...

async def record_source_refusal(
    claim: PublicationOwner,
    rollback: ConfirmedRollback,
    outcome: SourceMutationRefused,
) -> SourceMutationRefused: ...
```

Первый метод принадлежит общему commit owner. Второй — IOperationStore, OperationLedger и SqliteOperationStore. Source apply owner вызывает их внутри одной атомарной доменной операции.

Порядок: Source поднимает rollback-carrier с failure; coordinator подтверждает rollback, отзывает scope и выдаёт capability; наружная граница формирует envelope; record_source_refusal открывает короткую bookkeeping transaction, повторно проверяет binding/claim/fence/admission/drain/evidence, освобождает только operation holds этой операции и сохраняет terminal. После подтверждённого commit caller получает исходный SourceFailure. Release и terminal атомарны; все затрагиваемые holder chains проверяются до первого release.

transaction_for_claim должен обеспечивать одну активную apply attempt на claim, после rollback переводя runtime ownership в finalizing. Отсутствие artifact writer claims само по себе не доказывает отсутствие конкурирующей domain apply attempt. Межпроцессный takeover остаётся OPEN.

Предложение RefusalFinalizationError в backend/app/application/publication/errors.py содержит operation_id и enum-код STALE_CLAIM, BINDING_MISMATCH, INVALID_ROLLBACK_EVIDENCE либо TERMINAL_MISMATCH. Live writer/недоказанная quiescence дают OperationBusyError; повреждение persisted chains — PublicationInfrastructureError; неподтверждённый commit/rollback — UnknownCommitOutcome.

Exact terminal replay возвращает сохранённый отказ до повторного cleanup. Unknown domain commit запрещает запись refusal до recovery. Recovery читает общий terminal: Applied возвращает прежний успех, Refused — прежний failure. При отсутствии terminal операция остаётся unresolved.

Аварийное окно между rollback и записью refusal остаётся OPEN: runtime evidence и failure могут быть утрачены. Требуется принятие durable recovery protocol либо fenced takeover с явно определённой семантикой повторной попытки. Повторная проверка изменившегося latest не восстанавливает исходный отказ.

## Historical roots и acquire

Уточнение прежнего предложения по P2.4: root каждой body-bearing revision сохраняется до explicit prune. A→B приобретает root B и сохраняет root A. DELETE сохраняет roots исторических live revisions. Label-only использует прежний exact ref/root.

Предложение SourceRootHolder в backend/app/dataModel/artifacts/lifecycle/sourceRootHolder.py содержит kind=SOURCE_ROOT и source: SourceVersionRef | SourceCollectionVersionRef. Полный source ref задаёт holder identity. Artifacts владеет representation/codec, Source — eligibility и lifetime.

Предлагаемая signature в backend/app/application/artifacts/contracts/sourceRootPort.py:

```python
async def acquire(
    self,
    scope: CommitScope,
    claim: PublicationOwner,
    holder: SourceRootHolder,
) -> None | SourceFailure: ...
```

Реализация — предлагаемый backend/app/db/repositories/sqlite/artifacts/sourceRootStore.py. Scope проверяется по task/database/lifetime/write authority. Registry operation_id должен совпасть с claim. Persisted record должен иметь SOURCE_MUTATION, APPLYING и тот же полный lease/fence. Admission закрыт, writer claims drained, world holder совпадает с operation world.

Предлагаемый SourceRootReadBinding.retained_refs(scope, source, operation=...) вычисляет exact canonical storage closure без writes/latest. Для полномочия fresh uncommitted mapping дополнительно нужна Source-owned проверка:

```python
async def validate_acquisition(
    self,
    scope: CommitScope,
    source: SourceVersionRef | SourceCollectionVersionRef,
    *,
    operation_id: EntityUid,
    operation: SourceOperation,
) -> None | SourceFailure: ...
```

Предлагаемое размещение — backend/app/application/worldData/sourceVersioning/retention/rootEligibilityBinding.py. Проверяются persisted operation→exact revision linkage, world/descriptor/status mapping и участие revision в текущей mutation. Для no-op требуется связь текущей операции с прежней revision; одного created_by_operation недостаточно. Конкретное хранение linkage остаётся OPEN. Использовать Source index linkage P1, без второй копии terminal outcome.

Порядок acquire: scope/claim validation → Source eligibility → retained_refs → проверка всего closure → holder appends. До первого append проверяются catalog identity, sealed состояние, holder chains и защита bytes. Fresh bodies имеют operation hold claim. Для переиспользуемых dependencies нужно согласовать набор допустимых исходных durable holders. Общий writer scope сериализован с GC. SourceFailure до записи возвращается caller; storage failure после начала appends пересекает transaction boundary и вызывает rollback.

Source failures используют existing codes для world/descriptor/status/mapping/body. Для отсутствующего operation→revision linkage предложен MUTATION_BINDING_MISMATCH, решение OPEN. Scope/lease/fence/phase ошибки требуют owning typed infrastructure contract, его enum OPEN. Busy, infrastructure corruption и unknown outcome сохраняют общие исключения.

Mutation binding не содержит release. Explicit-prune binding отдельно повторяет latest/external usage checks, затем атомарно отмечает mapping pruned и снимает root выбранного exact ref. Собственный archival root исключается только из причин запрета prune. До release он защищает bytes от physical GC. Roots других revisions и capture/publication holders сохраняются.

Collection root удерживает storage closure collection body. Member bodies удерживаются по принятому capture-контракту. Refusal cleanup после rollback освобождает operation holds; новые Source mappings/roots уже откатились вместе, исторические roots продолжают действовать.

## Открытые решения до приёмки

- Canonical регистрация refusal envelope и точный rollback-carrier API.
- Единственная apply attempt на claim и recovery аварийного окна до записи refusal.
- Scoped operation→revision linkage, включая no-op.
- Source eligibility и согласование MUTATION_BINDING_MISMATCH.
- Допустимые исходные holders переиспользуемых closure artifacts.
- Typed infrastructure errors root acquire.
- Отдельный explicit-prune/usage контракт release.

Предложения не назначают новый DAG порядок или публичные междоменные pipelines. Порядок поставки остаётся inventory → projector/body codec → mutation/error contract → lifecycle/terminal/refusal → Source index/eligibility → root binding → atomic apply/recovery tests. P2/P3 остаются OPEN до совместной приёмки перечисленных решений.
