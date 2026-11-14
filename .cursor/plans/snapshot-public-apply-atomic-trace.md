# Snapshot public apply — S3 atomic trace и contract gates

Актуальные concrete предложения R1–R3: [snapshot-retention-cancel-diagnostics-contract.md](snapshot-retention-cancel-diagnostics-contract.md). R1 заменяет preliminary artifact→destinations запись на state/history-bound retention, поскольку иначе наследование остаётся неоднозначным. Подробные proposals ниже читаются с этим уточнением; accepted DTO/code ещё не изменены.

2026-11-14. Документальный этап плана snapshot-public-contracts-dag-integration.md. Публичные три метода описаны в snapshot-public-methods-contract.md. Этот документ проверяет именно apply; код/DDL/DAG, Source authored writer, Pack authority и Time T5 не меняются.

## 1. Existing owner/transaction trace

1. WorldSnapshotService revalidates PatchSet и registry/model/version/dependencies, вычисляет canonical request fingerprint через existing PatchSetCodec. DAG собирает PatchSet; Snapshot не строит чужие patches.
2. IOperationStore.claim_publication(SNAPSHOT_APPLY, operation_id, world_uid, preparation_fingerprint, request_fingerprint) — отдельная короткая transaction. Existing реализация либо возвращает PublicationOwner, либо PublicationTerminal, либо PublicationBusy; immutable identity mismatch сейчас ValueError. На terminal не запускаются handlers и повторные target checks.
3. PublicationOwner разрешает service продолжить одну попытку согласно existing claim; source-mutation grant/recovery proposal не переносится сюда автоматически. Artifact refs должны оставаться held от проверки до commit.
4. Владелец publication transaction — SqlitePublicationCommitStore.transaction(operation_id). Service читает expected world/player heads, gameplay/base/timeline/turn и validates все sections в принятом порядке. Конфликт до apply не вызывает handlers.apply.
5. Existing _apply_to_target выдаёт assigned context и последовательно вызывает handlers.apply. Внутри его yield service пишет metadata/handoff. После выхода yield выполняются world CAS, затем player CAS в expected order. Любой отказ/ошибка выходит за outer transaction и откатывает domain writes, metadata, handoff и все CAS вместе.
6. Только после успешного выхода _apply_to_target, но ещё внутри outer transaction, service формирует SnapshotCommitRefs и вызывает record_terminal(scope, COMMITTED). Затем coordinator подтверждает COMMIT; только после этого возвращается COMMITTED и эмитируется success.
7. Existing record_refusal(claim, outcome) открывает **отдельную** короткую transaction после подтверждённого rollback основного apply. Это accepted Snapshot port, не Source proposal с savepoint. При unknown rollback/commit refusal не записывается.

Public refusal возвращается лишь после confirmed record_refusal commit. Если отказ уже вычислен, но запись refusal не удалась, caller получает infrastructure/unknown, а не ложный durable REJECTED. Между rollback и refusal commit crash оставляет unresolved APPLYING; existing claim/recover не является автоматическим takeover. Это explicit runtime recovery limitation, не повод повторить handler из service.

## 2. Caller outcomes и holds — что уже следует из кода

| Состояние | Caller / durable результат |
|---|---|
| Exact stored SnapshotApplyResult | Возврат сохранённого исхода до target refs/handlers; immutable binding сначала |
| PublicationBusy | Public BUSY transport; никакого hidden retry/domain work |
| Body/CAS refusal + confirmed rollback + confirmed refusal commit | Existing CONFLICT/REJECTED, committed=None, исходные diagnostics |
| Refusal commit lost acknowledgement | OUTCOME_UNKNOWN; свежий coordinator читает ledger, не перезапускает body |
| Body commit lost acknowledgement | OUTCOME_UNKNOWN, не CONFLICT и не record_refusal |
| Cancelled invocation | CancelledError после owning cleanup; нельзя объявлять operation cancelled или не committed без acknowledgement |
| Success | Metadata/heads/handoff/terminal видимы вместе на втором connection |

Existing record_refusal **не освобождает operation holds**. Поэтому нельзя обещать cleanup по одному REJECTED/CONFLICT или считать terminal эквивалентом cancel. Если нужен release refused-operation holds, требуется отдельное принятое lifecycle решение; этот trace его не изобретает. Untransferred holds в успешном partial handoff остаются operation-owned по принятому 4D2 evidence.

## 3. Gate R1: отсутствует ownership artifact destinations

**Контрпример:** один SectionApplyReceipt содержит world и player state refs и retained_artifacts=(a,). Возможны три корректных намерения: a принадлежит world, player либо обоим. Existing receipt одинаков во всех случаях. Поэтому flat refs не определяют вход retained: Mapping[SnapshotRef, tuple[ArtifactRef,...]] для metadata builder. Публичный PatchSet также этого не определяет, а DAG не должен знать assigned snapshot IDs. Нельзя автоматически отдать ref всем, выбрать world или вывести назначение по format.

**Предложенное минимальное изменение до зависимого кода:** оставить публичный apply signature, уточнить internal receipt contract владельца Patch/Snapshot. Добавить explicit typed retention assignments на выходе handler, использующие assigned SnapshotRef из SnapshotApplyContext. Предлагаемый record `SnapshotArtifactAssignment` в dataModel/patch/results/artifactAssignment.py: `artifact: ArtifactRef`, `destinations: tuple[SnapshotRef,...]`, nonempty/unique; strict/frozen/extra-forbid/revalidate-always. В SectionApplyReceipt заменить flat retained_artifacts на `artifact_assignments: tuple[SnapshotArtifactAssignment,...]`; unique artifact entries, full union используется для transfer selection. Это **breaking proposal**, не принятый DTO и не разрешение мигрировать код.

Каждая destination должна входить в assigned context и принадлежать section owner согласно contract; foreign world/player отклоняется до metadata append. Много получателей разрешено явно. Inherited state требует полного retention closure текущей секции/назначения, включая no-op; новый receipt contract должен определить, как handler сообщает inherited artifacts без чтения чужих sections. Existing metadata содержит flat per-snapshot retained set, поэтому полное наследование нельзя восстановить автоматически при замене одной из нескольких секций. Этот связанный storage/read вопрос входит в R1 review; простая замена поля сама по себе его не закрывает.

Вариант «передать map из DAG» отвергается: раскрывает assigned internal refs и заставляет caller управлять storage ownership. Variant «оставить плоский receipt, resolver угадает» отвергается контрпримером. До принятия R1 existing проверенные helper/tests остаются как есть; production public apply readiness не заявляется.

## 4. Gate R2: terminal cancellation не имеет public apply representation

**Контрпример:** operation SNAPSHOT_APPLY отменена в PREPARING/READY; claim_publication того же preparation возвращает PublicationTerminal(OperationCancelled). SnapshotApplyResult допускает только COMMITTED/CONFLICT/REJECTED и требует непустые business diagnostics для последних. Преобразовать cancel в REJECTED означает выдумать business reason; CancelledError означает отмену invocation и также неверен.

**Предложение:** не менять SnapshotApplyResult/OperationCancelled enums. В application/worldSnapshot/errors.py добавить `SnapshotOperationCancelledError`, переносящий **existing OperationCancelled** как `outcome`, без нового cancel DTO. Это отдельный declared public control carrier, не SnapshotPublicFault.Kind и не asyncio.CancelledError. DAG mapping различает три факта: business refusal, durable cancelled operation, cancelled invocation.

Replay cancellation проверяет доступное immutable binding: world/kind/preparation и existing publication fingerprint, если он уже установлен. Если отмена раньше claim и publication fingerprint отсутствует, caller получает cancellation **preparation operation**, а не утверждение, что конкретный request fingerprint применялся. Никакой request fingerprint не дописывается в cancelled ledger для replay. Другой preparation binding отклоняется. Это уточнение public error contract требует принятия до реализации; operation terminal roster не расширяется.

## 5. Gate R3: типизация immutable mismatch и core refusal diagnostics

Existing operation store сообщает immutable mismatch через ValueError. Public method не должен классифицировать его по тексту или ловить все ValueError как mismatch: тот же тип может означать повреждённый invariant. До реализации нужно выделить owning typed mismatch carrier со checked operation/request facts либо checked result branch и отдельно определить concrete core FieldPathError codes для accepted REJECTED outcome. Existing generic FieldPathError не инстанцируется; raw строка не typed reason.

Конкретные diagnostics для registry/version, gameplay/timeline/turn, world/player CAS также должны быть сверены с already accepted error contracts before additions. Этот S3 trace не объявляет голые NamedTuple CAS traces готовыми public diagnostics. Scoped D1 metadata остаётся без изменений. При missing persisted parent corruption остаётся infrastructure, не бизнес missing-base refusal.

## 6. Read methods и пределы первого среза

Read_snapshot/read_publication из public-methods-contract.md не зависят от R1–R3: их proposal Input/Output/Error и existing read_scope mechanism можно принимать/реализовывать отдельным разрешённым срезом. Public apply signature accepted freeze сохраняется, но законченный implementation plan обязан закрыть R1–R3 и recovery limitations прежде чем обещать end-to-end readiness.

Внешние Source/Pack/Cache public операции не запускаются из apply. Генераторы/другие домены v1 не перепроектируются и не адаптируются. Не надо менять их producers для документальной проверки этих общих gates. Новые internal receipt/error changes сначала предъявляются пользователю, затем freeze/implementation.

## 7. Evidence и следующий шаг

Прочитаны IOperationStore и SqliteOperationStore claim/record_terminal/record_refusal, OperationRecord/OperationClaim, WorldSnapshotService и builder, owning 4D2 evidence. Выявленные gaps — статический анализ, не новые воспроизведённые runtime баги. Тесты не запускались, код не менялся. git diff --check — документационная проверка.

S3 trace подготовлен; приёмка public apply implementation **не закрыта**. Следующий контрактный результат Snapshot: R1 explicit destination+inherited retention contract и R2 control carrier на пользовательскую приёмку; R3 scoped diagnostics freeze. Не обходить эти изменения с помощью legacy adapters и не переносить их в DAG payload assembly.
