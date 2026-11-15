# Source core — implementation-план независимых инвариантов

2026-11-16. Предъявленный конкретный срез по указанию «Делай» после R1/R2. Код в ходе подготовки плана не менялся. Scope — пять компонентов из source-core-independent-slice.md. Это не разрешение реализации полного G1, request admission или других незавершённых областей. Реализация через implement-plan после проверки всех критериев этого среза; независимая приёмка отдельна.

## 1. Основание и preflight

Прочитать целиком перед кодом: этот план, source-core-independent-slice.md, source-core-checker-signatures.md, source-core-architecture-review-2026-11-15.md (ответ 2026-11-16); normative source-proof-v2-contract-spec.md §9.2/11.3/11.4; проектные правила dag-generator-interface.mdc и implement-plan. Сверить применимые docs/tz_json_validation.md и shared diagnostics правила. При расхождении с нормативной semantics не исправлять её молча.

Текущее evidence: Source values и encoding существуют, их не создавать повторно. Existing tests/sourceVersioning включает values/foundation/canonical/request canonical. Shared CanonicalCodec/content_digest, FieldRef/CheckedPath, SourceFieldIssue/SourceLogicIssue переиспользуются. Actual aggregation helper — `app.dataModel.validation.diagnostics.validatorAggregationHelper`, старый app.core путь из skill не создавать заново.

## 2. Точный scope файлов

Корень production — backend/app/application/worldData/sourceVersioning/:

1. proof/validation/sourceWorldChecker.py — SourceWorldChecker.check, только world equality.
2. proof/validation/sourceUsageConflictChecker.py — SourceUsageConflictChecker.check, только conflicts по пригодным facts R1.
3. proof/validation/sourceProofCanonicalChecker.py — SourceProofCanonicalChecker.check, только persisted canonical invariants.
4. proof/atomIndex.py — SourceProofAtomIndex.enumerate, только exact atom enumeration.
5. proof/validation/sourceSelectionChecker.py — SourceSelectionChecker.check, только fingerprint/index admissibility относительно canonical proof.

Добавить только необходимые package __init__.py без runtime registration/reexports side effects. Signatures/constructors — checker proposal §2–4 и internal API atomIndex. Ни key adapter, ни DescriptorLookup/registry production composition в этот срез не входят.

Tests: новые `backend/tests/sourceVersioning/test_core_invariants.py`, `test_core_atom_selection.py`; отдельные `backend/tests/typing/sourceVersioning/core_valid.py`, `core_invalid.py` и `pyrightconfig.core-valid.json`/`pyrightconfig.core-invalid.json`. Existing fixtures и negative typing expectations не переписывать ради новых tests.

Не менять dataModel, shared canonical/diagnostics, public proof methods, sourceErrors roster, request encoding, Terrain/Pack/Snapshot/Artifacts/SQL/DAG. Не реализовывать normalizer, union/extractor/matcher, request traversal, mutation/recovery/prune/settings. Не снимать общие TODO typed-errors одним созданием этих helpers.

## 3. Порядок реализации и завершение слоёв

### A. World и conflict

Реализовать exact methods без owning lookup/IO. Facts capture/dependency содержат original indices; check принимает оба tuples одним вызовом. Capture position уникальна; dependency fact ссылается на exact capture той же позиции; tuple order соответствует исходному обходу, object/collection категория определяется type ref. Несогласованность internal facts → programming ValueError/TypeError, не SourceFailure. Не перехватывать такие ошибки как business absence.

Отдельные faults внутри incoming usage не передаются сюда: tests непосредственно строят пригодные leaf facts с исходными индексами, демонстрируя отсутствие зависимости от целого usage. Полную INVALID_SHAPE+REVISION_CONFLICT aggregation исходного request этот слой не заявляет.

По согласованной корректировке 2026-11-16 проверяется только revision conflict внутри exact SourceCaptureRef, по offending dependency occurrence; порядок stable. Capture uid не доступен в этом POJO, CAPTURE_ID_CONFLICT остаётся witness/finalization. Разные revisions разных captures не conflict. Никакого автоматического dedup input для скрытия ошибок.

Слой закрывается адресными tests world/empty-world context, exact capture separation, object/collection revision conflict, допустимые повторения и history, несовместимые facts и stateless repeat calls.

### B. Canonical checker

Сравнивать full canonical bytes existing values, не repr/hash/python module names. Uses отсортированы по full capture ref; objects/collections по exact refs. Проверить duplicate captures, empty usage и duplicate dependency identities; не нормализовать input. Foreign world/revision conflicts относятся к собственным checker responsibilities и не переименовываются в NON_CANONICAL_PROOF без самостоятельного canonical нарушения.

Уточнение structural prerequisite: здесь «структурно пригодный proof» означает доступный правильный roster и пригодные strict leaf refs, а не успешный whole-model semantic validator. Existing SourceDurableProof constructor сам запрещает некоторые noncanonical случаи; для negative tests допустим model_construct с корректными leaves и нарушенным canonical инвариантом. Checker не вызывает whole-proof encode/model_validate до обнаружения этих нарушений, иначе ValueError заменит требуемые typed issues. Для sorting кодировать отдельные пригодные capture/source refs, а не заведомо invalid целый proof. Непригодный leaf вне prerequisites — structural/programming отказ; full malformed traversal остаётся вне среза.

Field paths — existing CheckedPath с typed FieldRef к конкретной nested collection. Aggregator request-local, concrete SourceFieldIssue, стабильный исходный порядок. Success — пустой tuple; никакого SourceProofResult.

Слой закрывается tests unsorted/duplicate uses/dependencies, empty usage, пустого допустимого proof, exact typed paths и неизменности входа.

### C. Atom index

Вход — canonical proof после checker B. Порядок: uses → objects → collections. Каждый atom представлен existing SourceCaptureUsage с исходным full capture и ровно одной dependency; второй tuple пуст. Capture identity входит в atom; одинаковая revision в разных captures даёт разные atoms. Пустой proof → пустой tuple.

Не допускается silent normalization при нарушенном prerequisite. Отказ на noncanonical внутреннем вызове — programming error, не другая версия enumeration. Если требуется defensive canonical check, переиспользовать SourceProofCanonicalChecker, а не дублировать правило sorting; constructor dependency/точная boundary должны быть явно отражены перед кодом, не добавляться скрыто. Базовый вариант среза: canonical prerequisite обеспечивает caller, tests отдельно выполняют B→C.

Слой закрывается literal expected atom order, capture-distinctness, empty proof и source tuple immutability tests.

### D. Selection checker

Единственная constructor dependency — AtomIndex. Proof canonical prerequisite обеспечен B. Fingerprint = existing content_digest(CanonicalCodec(SOURCE_PROOF_SCHEMA_V1).encode(proof)).hex(). Никакого caller codec/manifest. Fingerprint mismatch не скрывает независимый valid-int bounds failure.

При пригодном roster selection можно проверить forged values из model_construct: bool/negative/unsorted/duplicate → INVALID_SELECTION по исходному path; каждое пригодное неотрицательное int проверяется по bounds; остальные indices не останавливаются. Не восстанавливать новую исправленную selection. Malformed container/отсутствующее поле за пределами этого leaf-проверяющего среза; public request traversal должен сохранить structural refusal самостоятельно.

Logic selection_index → existing group_index, use_index=None; single SELECT index=None. Чужой fingerprint → SELECTION_PROOF_MISMATCH; out-of-range → SELECTION_OUT_OF_RANGE. Existing diagnostics roster не расширяется. Слой не извлекает subset и не проверяет matching группы.

Слой закрывается wrong fingerprint+out-of-range одним входом, duplicate/bool/negative/unsorted, empty selection/empty proof, точные original paths и повторные calls без state leakage.

## 4. Проверки всего среза

1. Из backend: `.venv/Scripts/python.exe -B -m unittest tests.sourceVersioning.test_core_invariants tests.sourceVersioning.test_core_atom_selection`.
2. Regression: `.venv/Scripts/python.exe -B -m unittest discover -s tests/sourceVersioning -p "test_*.py"`; shared canonical/UUID tests — существующие tests.planning.encoding.test_canonical_codec и test_uuid_codec.
3. Из root: `node node_modules/pyright/index.js -p backend/tests/typing/sourceVersioning/pyrightconfig.core-valid.json`; аналогично core-invalid. Positive — ноль errors; negative — заранее заданные ошибочные path/value и неверные argument types, каждый проверен, не произвольное число ошибок.
4. Проверить imports/effects: нет owning-domain/IO/storage/Pack imports и hidden registration. Нет public OpenPipeline, normalized repair, fake closure и второго implementation инварианта.
5. `git diff --check`, отдельный просмотр diff и новых файлов. Не запускать backend, не commit/push. Сохранить чужие параллельные правки.

Tests meaningful: проверяют отказ и invariants, а не повторяют implementation. Не использовать legacy fixture conversion. Own test report не independent review.

## 5. Обязательная приёмка среза

| Критерий | Проверяемая граница |
|---|---|
| Одна ответственность | Каждый из пяти классов соответствует единственному инварианту/перечислению §2; mixed world/admission/IO либо duplicated ordering — отказ |
| Три запрета DAG | Только internal pure methods, новых routes/нод/public nested calls нет; фактические imports проверяются при реализации |
| Public/internal | Existing POJO и issues переиспользуются; результаты не admission/holds evidence; полнота исходного malformed request не обещается |
| Порядок | A → B → C → D → общий regression/typing → отдельная независимая приёмка |
| POJO/errors | Новые DTO/errors не вводятся, SourceOperation не dispatch; wrong-root/path negative typing обязательно |
| CRUD/settings | В этом срезе public data/settings операции не создаются; full-domain CRUD acceptance не заявляется и не отменяется |
| Внешние зависимости | Shared values/codecs уже существуют; owning key/body/transaction integration отсутствует в graph, не заменяется stub |
| Полнота scope | Пять компонентов и tests реализованы либо незавершённый компонент явно не принимается; no full G1 claim |

## 6. Результат и следующий gate

После реализации — точный список imports/файлов, commands/results, пределы evidence и отдельный запрос независимой проверки в видимом чате по указанию пользователя. Полный request validation и остальные архитектурные вопросы Source не объявляются закрытыми. До реализации требуется завершить pre-code проверку применимых SoT и разрешить обнаруженные конкретные расхождения; сам этот документ не evidence выполненных tests.
