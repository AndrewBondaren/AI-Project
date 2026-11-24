# Source: полнота finalization/prune

2026-11-25. Собственная архитектурная проверка по запросу пользователя, не независимая приёмка и не runtime test. Источники: source-core-capture-prune-configuration.md §§1–2, source-x-read-internal-boundary.md, source-proof-v2-contract-spec.md §§10.4, 11.2, 12.2 и source-core-error-contract.md.

## Итог: CHANGES REQUIRED по собственной полноте

Исправления после отчёта: source-x-read-internal-boundary.md §3 задаёт collect_candidate без finalized proof, generic provenance context и общий graph algorithm; source-core-capture-prune-configuration.md §2 задаёт prune admission и confirmed outcome semantics. F1/F3 имеют адресные проекты исправления, но повторная независимая приёмка не выполнена. Старый текст findings ниже сохраняет основания проверки, не утверждает отсутствие этих новых проектов. Public prune/error tag и foreign bindings не объявлены принятыми.

Внешние writer/retention/authority bindings не считаются дефектом независимого ядра. Ниже перечислены собственные обязанности, которые уже можно проверить или нужно определить без ожидания интеграций.

| Контракт | Вход | Результат/ошибка | Вложенные вызовы | Вывод |
|---|---|---|---|---|
| SourceCaptureCandidateChecker.check | witness, capture, exact collection pairs; completeness prerequisite | tuple SourceLogicIssue, без original indices; не finalization evidence | Единственная check_capture_relations; descriptor lookup | Форма определена; relation code mismatch исправлен по spec §10.4 |
| Materialized completeness перед candidate | Exact required Source refs и материализованные значения | Internal gaps; proposed MATERIALIZED_INPUT_INCOMPLETE через FINALIZE_CAPTURE | Общий completeness algorithm; no IO | Семантика определена; error delta ещё на согласовании |
| SourceCaptureFinalizer.finalize | Исторический witness+lease; нет exact materialized candidate входа нового пути | SourceCaptureRef только после confirmed commit; SourceFailure после безопасного отказа, unknown отдельно | Старый spec вызывает scoped read/collector/catalog/holders | Новый собственный call graph ещё не сведён; нельзя исполнять старую цепочку как новую materialized architecture |
| FinalizationStore find/read/append | Exact uid/witness/ref; capability отдельно | Identity сохраняется после GC; immutable conflict; read отсутствие content отдельно | Только persistence; без commit/holder/retry | Собственные storage semantics заданы в spec §11.2; foreign binding deferred |
| SourceRevisionPrunePolicy.evaluate | requested exact object refs и authoritative latest | tuple candidates; internal misuse отдельно | Pure, без holders/GC | Узкий candidate контракт определён, не полный preview/confirm |
| Prune admission/confirm | Нет полного Source request/state/result контракта | Missing/pruned/latest rejection и durable prune outcome не сведены | Требуются Source state admission и history marker, external release/GC отдельно | Собственный остаток, нельзя скрыть ожиданием Artifacts |

## F1: candidate closure не имеет собственного законченного пути

Новый SourceProofClosureCollector.collect принимает canonical SourceDurableProof, finalized witness associations и CaptureOrigins. Finalizer получает ещё не finalized SourceCaptureWitness. Старый collect_capture_body(scope, capture, capture_body) не соответствует materialized пути, но его обязанность вычислить полный closure **без witness**, затем добавить exact candidate witness ref остаётся.

Нельзя создавать fake finalized SourceCaptureRef/proof либо origins для вызова proof collector. Нужно определить собственный candidate-data метод и общий алгоритм body roots/graph, переиспользуемый proof и finalize; callback/mode flag вместо этого не допускаются. Сейчас capture_roots и CaptureRefs graph context тоже привязаны к SourceCaptureRef — это конкретная внутренняя зависимость, а не отсутствие foreign transport. До её устранения candidate checker не даёт готовый finalization pipeline.

## F2: конфликт error mapping устранён адресно

Spec §10.4 требует INCOMPLETE_CLOSURE для member, неразрешимого в capture mappings. Candidate документ ошибочно приводил этот случай как INCOMPLETE_COLLECTION. Он исправлен. Отсутствующий переданный collection body по-прежнему является completeness gap до relations; физический MISSING_BODY из этого не следует. Для остальных INCOMPLETE_COLLECTION условий нужна точная relation matrix, не общий catch-all.

## F3: prune policy не закрывает собственный preview/confirm контракт

evaluate намеренно исключает latest и не знает missing/pruned/live/tombstone state. Это корректная граница, но до вызова отсутствует завершённый Source admission owner/input/error mapping для requested history. Требуется отделить: never-found, already-pruned, допустимый historical revision, current latest. Не переносить pruning в SourceMutationStateChecker: он отвечает за CREATE/UPDATE/DELETE.

После selection нужно определить Source history outcome: какие exact revisions подтверждённо pruned, что происходит с immutable identity/mapping history, как replay отличается от новой попытки. Foreign holders/release/GC предоставляют полномочия и физические эффекты, но не определяют Source результат за Source. Код REVISION_PRUNED в проекте ошибок ещё не задаёт этот workflow. Collection prune не включается автоматически в object-only policy.

## Обязательные проверки собственной цепочки

- Candidate без committed witness не требует fake proof; полный candidate body closure включает все mappings.
- Same uid/same canonical content replay не проверяет latest заново; same uid/different content конфликтует и после GC identity retention.
- Full content с неразрешимым member → INCOMPLETE_CLOSURE; missing materialized collection → completeness refusal, relation helper не вызван.
- Domain refusal после append не становится preflight до confirmed rollback; unknown/cleanup failure не выдаёт success.
- Prune preview никогда не authority; latest изменился/новый hold возник до confirm — требуется owning повторная атомарная проверка.
- Tombstone не равно pruned; исключённый latest не возвращается как удалённый; same candidate refs не доказательство replay.

Собственные следующие действия: candidate closure reuse без finalized proof; exact prune admission/result semantics; сверка единого finalize trace с этим входом. Внешний integration transport остаётся EXTERNAL / DEFERRED. После изменений требуется повторная архитектурная проверка; этот отчёт ничего не объявляет реализованным.
