# C2-R4: общий источник provenance predicates

**Исправление повторного ревью 2026-11-21:** [R3/R4/R5 exact facts/diagnostics](snapshot-receipt-facts-diagnostics.md) заменяет fully-valid-only signature ниже: `collect_owned_receipt_provenance(facts:ReceiptFacts, assigned:SnapshotRef, base:SnapshotEnvelope|None)`. section_index принадлежит facts. Общие predicates operation/history/state объявлены там отдельно; partial refs не требуют unchecked receipt. Order aggregation задан по фазе/original index, не owner iteration. Старые формулировки «общая граница ещё не задана» ниже — история исходного предложения. Статус уточнения PROPOSED, требуется сверка, не code-go.

2026-11-21, PROPOSED. Source review: application/worldSnapshot/validation/receiptProvenance.py и service/snapshotMetadataBuilder.py. Код не меняется; R3/R5 остаются отдельными вопросами. Текущий helper с apply context нельзя напрямую вызвать из history append: последний располагает одним metadata/base, не полной картой transaction.

## Карта extraction

| Правило | Общая pure boundary | Остаётся у caller |
|---|---|---|
| Changed ref принадлежит operation | Один pure predicate полного operation_id | Early full input membership остаётся у SnapshotReceiptValidator; совместимость FOREIGN_OPERATION/membership reports — R5 |
| History использует assigned snapshot своего owner | Owner-local helper ниже | Early проверяет также наличие owner во всём assigned set; final single-envelope проверка не может доказать глобальное покрытие других owners |
| Новый state при empty changed запрещён | Owner-local helper | Нет Time/Lifecycle-specific cardinality |
| Inherited state полностью равен entry из exact pinned base | Owner-local helper | Parent/base identity admission отдельно до helper |
| Receipt одновременно заменяет и наследует state одного owner/key | Owner-local helper | Итоговая envelope membership всё равно проверяется отдельно |
| Foreign owner, missing player, extra/missing bases, self-parent | Не правило одного receipt/owner | Early context/base checks и builder; не назначать final append отсутствующие context данные |
| Metadata history = receipts history для assigned ref | Final validate_receipt_provenance | Early нет собранной metadata, это самостоятельный postcondition |
| Metadata states = inherited base states + replacements; все receipt states присутствуют | Final validate_receipt_provenance | Не переносить весь builder в ранний validator |
| Receipt section/input association и exact changed membership | SnapshotReceiptValidator | Final storage не получает исходную section и не должен угадывать её |

## Предлагаемые signatures без нового DTO

В existing `application/worldSnapshot/validation/receiptProvenance.py`:

`collect_owned_receipt_provenance(receipt: SectionApplyReceipt, assigned: SnapshotRef, base: SnapshotEnvelope | None, *, section_index: int) -> tuple[SnapshotMetadataRelationIssue, ...]`.

Предусловия: fully validated receipt, assigned и base; caller уже доказал точный parent/base binding; section_index strict int>=0 без bool. Helper проверяет только entries того же world/player owner, что assigned; unrelated owner entries не подтверждает и не отклоняет. Приёмка owner identity переиспользует один pure _same_owner/_owner источник, без второго алгоритма. Не открывает IO, не принимает scope и не читает current heads.

Early collect_receipt_provenance(receipt,context,bases,section_index) сохраняется как coordinator чистых checks: проверяет global owner coverage; для каждого assigned owner выбирает его exact base и вызывает owner-local helper. SnapshotMetadataBuilder использует тот же adapter для per-receipt predicates, а не повторяет циклы условий. Проверки duplicate receipts, context/base/pack/turn и сборка envelopes остаются у builder.

Existing validate_receipt_provenance(metadata,receipts,base,operation_id) сохраняет signature, strict admission и final postconditions. После собственной проверки metadata.operation/parent и duplicate receipt keys он вызывает owner-local helper для каждого receipt с assigned=metadata.ref. Нет реконструированного fake SnapshotApplyContext/next_publication и нет зависимости final append от service. Это сохраняет прежнюю область проверки одного envelope; global assignment evidence обеспечивает ранняя стадия. Новый standalone history caller не получает расширенных гарантий по другим owners автоматически.

Прямой storage append имеет receipt tuple и его собственные indices; main последовательный apply сохраняет соответствие sections[i]/receipts[i]. Если caller передаёт filtered tuple и требует исходные PatchSet indices, он должен предоставить explicit mapping отдельным контрактом, не выдавать локальный индекс за исходный. Наружный ValueError final checker и SnapshotMetadataFailure builder не меняются молча: mapping одинаковых predicate failures в существующие carriers/порядок фиксируется R5.

## Исправление Lifecycle no-op и граница R3

Actual code: builder FOREIGN_HISTORY для любого history snapshot вне assigned set; final checker запрещает history своего owner не на metadata.ref. **Inherited history receipt недопустим.** State inheritance допустим только полным retained entry из pinned base. Lifecycle no-op после exact duplicate change_uid должен вернуть history=(), changed=(), states=() или exact inherited state; новая history operation не создаётся. Это исправление прежнего Lifecycle proposal, не расширение C2. Для общего Snapshot не вводится новое правило history count == changed count.

Malformed receipt path existing builder сохраняет независимые valid refs даже при malformed artifact closure. Предложенный fully-valid helper сам по себе этот путь не покрывает. **R3 остаётся OPEN:** прежде реализации выделить общий набор predicates над отдельно admitted facts либо иной exact typed boundary, который сохранит существующее aggregation; не duplicate алгоритм в fallback и не считать весь R4 реализуемым без R3. Для malformed output BoundSectionHandler H2 останавливает путь раньше C2; это не разрешение ломать independent diagnostic behavior standalone metadata builder.

## Приёмка предложения

Доказать одинаковое решение owner predicates на early/final inputs: assigned new state, valid inherited closure, altered artifacts closure, foreign history, no-op new state, simultaneous replacement/inheritance, world/player owner separation. Final-specific missing/extra metadata state/history остаются отдельными tests. No-op Lifecycle не даёт inherited history и не меняет global history cardinality. Тесты ещё не выполнены; numeric IDs/публичные DTO/порядок apply не меняются.

R4 получил точную общую input boundary и карту predicates; статус **PROPOSED**, не ACCEPTED. Следующий необходимый разбор — R3 admitted facts/aggregation, затем R5 diagnostic compatibility. Полная приёмка extraction до их закрытия не заявляется.
