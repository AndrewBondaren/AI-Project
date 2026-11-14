# Source review: pinned-origin редакция 1

2026-11-14. Проверен snapshot-pinned-origin-contract-r1.md против принятого source-pack-s1-s2-contract.md r2 §2–5 и source-proof-v2-contract-spec.md §12.1/13. Scope — адресная Source проверка first call и explicit retained-input repeat после confirmed rollback. Это не общая приёмка storage/codec, public маршрута или всего C-PIN-1.

**Verdict: PASS по совместимости с Source S1/S2 в указанной границе.** Новых блокирующих замечаний к Source semantics/order в этой редакции не найдено. Совместный ACCEPTED этим отчётом не объявляется: нужен итог Pack и owning приёмка оставшихся частей. Runtime не проверялся.

## Проверенная цепочка

1. Authenticated existing pin → exact verified manifest/all proofs → S1 через SourceProofCoverageCheckInput. Запись `check_coverage(request, available)` в trace читается только как создание принятого named input, как прямо указано в документе, не новая двухаргументная signature.
2. S2 preflight выполняет один bind/collect/reset; его результат остаётся данными. Issuer получает Source-owned exact closure через private evidence после настоящих успешных checks, не через caller-provided refs/flags. Manifest/pin authority принадлежит Snapshot/Pack, не Source.
3. Fresh pinned grant выдаётся после preflight внутри уже принятой register/resolve стадии. Scope/task/DB/connection/target/request/pin/manifest привязаны к registry. Нет дополнительного commit, acquire, public Source call или повторного collector внутри provider.
4. Register/resolve дают exact ordered VerifiedArtifactRef pairs. Adopt сохраняет signature и заново collect/full-set/hold/target checks перед acquire. Grant/private evidence не заменяют ни одну из этих проверок.
5. Late refusal откатывает provisional registrations и holds предыдущих proofs. Cleanup отзывает grant/evidence на всех выходах; бизнес-отказ возвращается только после подтверждённого rollback. Unknown outcome не считается confirmed rollback и не разрешает автоматический reissue.

## Ошибки и границы

SourceFailure, CHECK_COVERAGE/ADOPT_CLOSURE и typed diagnostic root не меняются. Proposed authority COVERAGE_MISMATCH относится к holder/binding set против preflight closure, а не к Source logical coverage. Pin/manifest refusal сохраняет existing ManifestReadRefusal и PackPreparationReadAbort. Authority ошибки не становятся SnapshotApplyResult/SourceFailure. Empty proof имеет empty sources/entries, но не освобождает issuer от pin/manifest admission.

Повторный вызов не использует ExecutionPins.acquire/latest при пропавшем pin. Grant не восстанавливается из UID/checkpoint. Pin DTO является повторно проверяемым input; lawful origin подтверждают owning authenticated adapter/persisted binding/holds. Это соответствует согласованной Pack границе, не добавляет Source authority token.

## Что остаётся открытым

- Полный input после crash должен поступать от подтверждённого caller/recovery producer. Он пока не предъявлен. Поэтому explicit repeat с сохранёнными values нельзя назвать автоматическим end-to-end restart и нельзя закрыть весь C-PIN-1.
- SQL layout/canonical IDs durable authority records остаются owning gates. Этот Source PASS не принимает их и не объявляет store реализованным.
- Pack подтверждает scoped pin refusal mapping, all-provenance boundary и fixtures отдельно. Source fixtures требуют G2, не legacy conversion или fabricated finalized rows.
- Operation-origin G4, Source finalizer hookup, public DAG/новые ноды не входят в review.

Сверены также текущий PinnedManifestGuard mapping и фактический путь shared aggregation helper: backend/app/dataModel/validation/diagnostics/validatorAggregationHelper.py. Историческая ссылка app.core.validatorAggregationHelper не соответствует текущему файлу; при будущем implement-plan брать актуальный owning import, не создавать compatibility module. Pinned proposal конкретного устаревшего import не задаёт.

Код/accepted Source specification/implementation gates не изменены. Тесты не запускались; изменение — только этот review report.
