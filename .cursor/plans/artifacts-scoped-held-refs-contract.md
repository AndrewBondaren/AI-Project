# Artifacts: scoped operation-held lookup для Snapshot — 2026-11-24

Статус: **PROPOSED**, ответ на consumer заявку `snapshot-public-apply-atomic-trace.md`. Не часть standalone stage; его require_standalone сюда не переносится. Код не изменён, новый engine/holder/DTO не вводится.

## Existing и минимальная дельта

Existing `app.application.artifacts.contracts.holderPort.IArtifactHolders.handoff(scope:CommitScope, lease:OperationLeaseRef, snapshots:tuple[SnapshotRef,...], retained_refs:tuple[ArtifactRef,...])->None` — async. Concrete `app.db.repositories.sqlite.artifacts.holderStore.SqliteArtifactHolders` заимствует scope, приобретает каждому snapshot holds его metadata closure и снимает только перечисленные operation holds. Собственного commit нет.

Existing holders/is_held не перечисляют полный operation set и не принимают scope. `SqliteOperationArtifacts.read(scope:CommitReadScope, operation_id:EntityUid)->tuple[ArtifactRef,...]` — внутреннее чтение, не authority port. Его JOIN/DISTINCT не доказывает отсутствие orphan/повреждённых holder chains и не проверяет fence. `IOperationStore.read` не принимает scope. Достаточного existing public application метода для заявки не обнаружено.

Минимальная предложенная дельта **existing IArtifactHolders**, реализация в existing SqliteArtifactHolders:

```python
async def read_operation_held(
    self, scope: CommitScope, lease: OperationLeaseRef,
) -> tuple[ArtifactRef, ...]: ...
```

Imports уже имеются в holderPort.py: CommitScope из `app.application.worldSnapshot.contracts.commitScope`, OperationLeaseRef из `app.dataModel.artifacts.lifecycle.lease`, ArtifactRef из `app.dataModel.artifacts.references`. Это внутренний scoped storage contract для atomic apply, не DAG POJO/public pipeline; scope не транспортируется через DAG. Snapshot передаёт lease исходного PublicationOwner, а не lease из пользовательского payload. PublicationOwner сейчас содержит только lease: новой authority семантики wrapping не добавляет.

## Проверки и lifetime

1. Strict lease validation; registry проверяет issued writable scope, текущие task/connection/lifetime и operation_id(scope)==lease.operation_id. Через existing bind(scope), без вложенной transaction и без reentrant bind. Composition holders/operations/history/access/coordinator — existing общий graph.
2. В том же scope загрузить и проверить persisted operation/event/terminal/evidence и admission chain до сравнения входного binding/fence. Проверить exact lease binding, closed admission, phase APPLYING, отсутствие writers. Не использовать writable stage admission. Отсутствующая операция, stale/foreign attempt, открытая admission или writers запрещают выдачу результата. Publication request-fingerprint admission остаётся у owning claim/attempt builder; lease lookup не заменяет её.
3. Полноту читать из existing holder event таблицы: получить все distinct artifact_id, на которые ссылаются operation holder events этого operation_id, **без inner JOIN, способного скрыть orphan**. Для каждого ID existing catalog._by_id проверяет наличие/descriptor, holder._chain проверяет полный chain. Из validated latest событий выбрать active operation holds; каждый активный hold этого operation_id обязан иметь текущий lease.fence. Исторические released holds другого fence не включаются; active другого fence — infrastructure invariant failure.
4. Для каждого активного ref проверить sealed storage chain. Вернуть unique tuple в порядке kind/format_key/format_version/content_hash. Empty tuple законен после полной проверки attempt и всех найденных chains. До возврата проверить весь набор; частичный результат не выдавать. Это дополнительные scoped проверки поверх existing SQL/chain primitives, не использование SqliteOperationArtifacts.read как готового доказательства. Новая таблица/index/holder policy не требуется.

Метод не приобретает/снимает holds, не меняет admission и не коммитит. Tuple — проверенное наблюдение внутри текущего outer write UOW, не token для другой task/transaction. Нельзя вынести read до claim либо заменить его independent latest read. После возврата consumer в том же scope вычисляет intersection с union retention_closure новых metadata и вызывает existing handoff. Handoff повторно проверяет свои preconditions перед append; наличие tuple не отключает эти проверки.

## Errors и atomicity

Malformed lease — existing ValidationError; invalid scope/corrupt persisted state/orphan/active wrong-fence/unsealed held content — PublicationInfrastructureError с cause, где ошибка поймана. Stale/binding/phase/admission/writer guard failure в этой proposed минимальной дельте также PublicationInfrastructureError: это отказ внутреннего claimed attempt contract, **не** новый business refusal, не расширение ArtifactLeaseFailure WRITABLE/CLOSED semantics. Не добавляется error carrier или код. Existing UnknownCommitOutcome и CancelledError сохраняются; произвольный ValueError/SQLite fault не превращается Snapshot в business result. При реализации normalization ограничивается owning hydration/DB boundaries с сохранением cause.

Lookup не изменяет effects; последующий handoff provisional. Любой fault прерывает apply до следующих CAS; rollback внешнего owner отменяет domain writes/metadata/holds/CAS вместе. Unknown rollback/commit остаётся unknown, без record_refusal/компенсационного release/автоматического retry. После окончания scope tuple не является доказательством актуального удержания.

## Actual handoff semantics и предел подтверждения

- Shared ref получает отдельный SnapshotHolder для каждого metadata closure, который его содержит.
- Inherited ref из metadata получает destination hold, даже если отсутствует в transferred.
- Partial transferred снимает только указанные operation holds; leftovers и прежние holders сохраняются.
- Empty transferred не отменяет приобретение destination holds.
- Existing previous-release+destination check поддерживает повтор handoff. Новый lookup возвращает current active set, не реконструирует прошлый transferred; exact terminal replay — owning Publication, не повтор apply.
- Existing handoff сам не требует равенства retained_refs полному intersection; допускает destination через ArtifactRetentionHolder вне snapshot planned set. Для полного Snapshot apply exact intersection формирует и проверяет Snapshot. Не усиливать существующий general port этим consumer-specific требованием молча.

## Приёмка дельты

Нужна координаторская/owning сверка signature и taxonomy до реализации. Проверки: correct same-scope attempt; foreign task/connection/operation/fence; closed vs open; active writers; corrupt chain при stale lease; orphan без catalog; active old-fence; partial/shared/inherited/empty; отсутствие mutations на любом lookup failure; rollback после handoff и после CAS; unknown acknowledgement без compensation; independent connection не меняет protected facts внутри outer writer UOW. Standalone ARCH-STAGE не ждёт этой отдельной дельты.
