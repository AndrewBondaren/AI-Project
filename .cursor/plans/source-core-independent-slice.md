# Source core — первый независимый срез после R2

2026-11-16. Конкретный architectural candidate, **не разрешение реализации**. Выбран вариант R2(a): invariant components без owning admission. После ревью плана предложен prerequisite A0 — общие локальные правила dataModel вместо дублирования в POJO/checkers; точные функции, файлы и границы — source-core-invariants-implementation.md §3.A0. Пять application-компонентов уже написаны, но не приняты; A0 не реализован. Следующий gate — принятие исправленного среза, не продолжение кода. Source architecture review 2026-11-15 и прежние собственные тесты — историческое evidence.

## Состав

Пути относительно `backend/app/application/worldData/sourceVersioning/`:

| Файл / класс / метод | Algorithm prerequisites | Кто обеспечивает | Гарантия результата |
|---|---|---|---|
| proof/validation/sourceWorldChecker.py / SourceWorldChecker.check | Strict EntityUid и исходный diagnostic context | Typed caller/leaf validation | Только сравнение world; не проверка регистрации |
| proof/validation/sourceUsageConflictChecker.py / SourceUsageConflictChecker.check | Пригодные capture/ref facts и согласованные original positions | Request traversal; exact фактовый API checker §3 | Только конфликты revisions внутри exact SourceCaptureRef; не capture_uid и не completeness всего повреждённого request |
| proof/validation/sourceProofCanonicalChecker.py / SourceProofCanonicalChecker.check | Структурно пригодный SourceDurableProof и CheckedPath к нему | Typed caller/structural boundary | Canonical order/duplicates/empty-use policy, без owning key validation |
| proof/atomIndex.py / SourceProofAtomIndex.enumerate | Структурно пригодный canonical proof | Canonical checker до вызова | Стабильная enumeration exact atoms, не admission |
| proof/validation/sourceSelectionChecker.py / SourceSelectionChecker.check | Пригодный canonical proof; selection доступны проверяемые поля; original path/index | Structural boundary и canonical checker; повреждённые поля сохраняют отдельный structural refusal | Fingerprint/bounds и пригодные structural selection checks; не subset extraction |

Единственная constructor dependency внутри среза: SelectionChecker → AtomIndex. Остальные constructors без owning adapters. Shared dependencies — существующие Source values/errors, CheckedPath/FieldRef и фиксированный SOURCE_PROOF_SCHEMA_V1/CanonicalCodec. Никаких Terrain/Snapshot/Pack/body readers/IO/holder imports.

Дополнительная предлагаемая module dependency после ревью: POJO wrappers и canonical/selection checkers → Source-owned `_proofValueRules.py` (A0). Новые carriers и application imports из dataModel запрещены. AtomIndex работает только при canonical prerequisite от caller, не обещает самостоятельного отказа на noncanonical input. Production guard после ошибки canonical checker принимается вместе с будущим request traversal.

Ограничение malformed input: этот срез не заявляет готовую request-wide aggregation. Conflict checker принимает пригодные leaf facts из частично повреждённого usage, а не сам повреждённый record. Полный traversal, выдающий одновременно shape+logic issues, остаётся отдельным компонентом архитектуры; его контракт R1 исправлен, реализация ещё не поставлена. Tests facts API проверяют сохранение original indices и запрещённые несогласованные facts; не имитируют production admission stub.

Для selection, если payload непригоден для typed checker, request traversal отдельно выполняет доступные structural проверки и не фабрикует исправленную selection. Обещать сохранение всех independent checks на malformed selection можно только после реализации этой boundary, не по одним tests данного среза.

## Что исключено

Normalizer/union/extraction/matching сохраняют текущие требования к входу и не включаются в первую поставку. Identity/membership/request-wide admission, closure, публичные OpenPipeline, mutation/recovery, capture finalize, prune, configuration CRUD и все интеграции исключены. Нет allow_partial/skip_keys/TEST режима. Не создаются fake production registrations или durable refs.

## Приёмка

Negative typing path/value; world mismatch включая пустой proof на уровне caller facts; conflicting exact revisions той же capture при допустимых historical revisions разных captures; facts из use с повреждённым соседом; canonical ordering/duplicates; atom order; selection fingerprint/bounds; отсутствие IO/owning imports; stateless repeated calls. Дополнительно A0: единственная реализация общих правил, сохранение POJO strict/frozen validation и canonical vectors. Все negative facts cases используют явные existing values, не legacy fixtures/conversion.

CAPTURE_ID_CONFLICT исключён из приёмки этого среза: SourceCaptureRef не содержит capture_uid. Ответственность decoded witness/finalization остаётся за Source в отдельном срезе; нельзя добавлять UID в ref, выводить его из artifact hash или объявлять эту проверку выполненной facts checker.

Эти проверки подтверждают только перечисленные методы. Complete request diagnostics проверяются позднее на настоящем request traversal; public admission и durable guarantees этим срезом не принимаются. До кода — отдельное принятие архитектуры и implement-plan; independent review не подменяется собственной повторной проверкой документа.
