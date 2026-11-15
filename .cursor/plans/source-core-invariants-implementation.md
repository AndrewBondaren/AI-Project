# Source core — implementation-план независимых инвариантов

2026-11-16. Исправленная редакция после ревью плана: **PROPOSED / NOT EXECUTION-READY до принятия изменённого среза**. Пять application-компонентов из source-core-independent-slice.md уже написаны, но не приняты. Историческое «Делай» было истолковано исполнителем как разрешение исправления и реализации одновременно; отдельная приёмка архитектуры исправленного среза не зафиксирована и задним числом не заявляется. Текущее «Правь» разрешает исправление документов, не продолжение кода. Предлагаемый scope дополнен A0 — устранением дублирования локальных правил в двух существующих POJO. Полный G1, request admission и интеграции не входят. Реализация только через implement-plan после принятия этой дельты; независимая приёмка отдельна.

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

Предлагаемая ограниченная дельта dataModel: новый private module `backend/app/dataModel/sourceVersioning/_proofValueRules.py` и делегирование повторяющихся правил из `sourceDurableProof.py` / `sourceProofSelection.py` согласно A0. Public поля, strict/frozen-настройки, canonical manifest и принимаемое множество значений сохраняются. Это изменение scope требует принятия до кода; старый запрет любых правок dataModel для этой редакции заменён только указанным перечнем.

Не менять shared canonical/diagnostics, public proof methods, sourceErrors roster, request encoding, другие POJO, Terrain/Pack/Snapshot/Artifacts/SQL/DAG. Не реализовывать normalizer, union/extractor/matcher, request traversal, mutation/recovery/prune/settings. Не снимать общие TODO typed-errors одним созданием этих helpers.

## 3. Порядок реализации и завершение слоёв

### A0. Один владелец повторяющихся правил — предлагаемая дельта до A

Владелец локальных правил значения — Source dataModel; application добавляет request paths и существующие typed issues. `_proofValueRules.py` содержит только pure функции, без BaseModel, application/encoding imports, IO или новых carriers. Типы входов — existing SourceCaptureUsage, SourceDependencySet, SourceVersionRef, SourceCollectionVersionRef; возвращаемые bool/tuple[int, ...] — внутренние результаты проверки, не публичный error-контракт.

| Функция / единственная ответственность | Потребители / критерий отказа в приёмке |
|---|---|
| `duplicate_capture_positions(uses: tuple[SourceCaptureUsage, ...]) -> tuple[int, ...]` — позиции повторов full capture после первого | SourceDurableProof.persisted_shape и CanonicalChecker; собственный второй set/цикл поиска повторов у потребителя — отказ |
| `has_dependencies(dependencies: SourceDependencySet) -> bool` — непустой usage | Те же потребители; второе правило непустоты — отказ |
| `has_unique_object_identities(refs: tuple[SourceVersionRef, ...]) -> bool` — одна revision на object identity | Те же потребители; сравниваются identities, не только равенство полных refs; вторая реализация — отказ |
| `has_unique_collection_identities(refs: tuple[SourceCollectionVersionRef, ...]) -> bool` — одна revision на collection identity | Те же потребители; object/collection типы не смешиваются; вторая реализация — отказ |
| `invalid_selection_order_positions(indices: tuple[int, ...]) -> tuple[int, ...]` — исходные позиции duplicate/non-increasing пригодных индексов | SourceProofSelection.increasing_indices и SelectionChecker; один issue на offending occurrence, повторный алгоритм порядка — отказ |

Последняя функция принимает strict non-negative int; форма проверяется existing POJO schema. SelectionChecker при forged input проверяет пригодность элемента по существующей аннотации поля (через Pydantic TypeAdapter, без новой Source-копии StrictInt/ge schema), сохраняет исходные позиции, передаёт пригодную последовательность функции порядка и отображает её позиции обратно. Это локальные facts для диагностики, не repaired selection; bounds остаются независимыми. Primitive structural validation и присоединение request path не переносятся в функцию порядка.

SourceDurableProof сохраняет свою world relation validation; SourceProofSelection сохраняет strict shape. Их wrappers используют общие правила для существующего Pydantic отказа. Checkers переводят отрицательные результаты этих же функций в SourceFieldIssue. Публичные carriers/errors не добавляются, dataModel не зависит от application. Canonical byte ordering и proof-relative fingerprint/bounds остаются application-инвариантами: POJO сейчас их не реализуют. Элементарное сравнение world у разных relations не заменяется новым универсальным service.

Приёмка A0: существующие values/encoding vectors неизменны; один набор контрпримеров проверяет оба потребителя правил; duplicate identities с разными revisions не проходят; selection сохраняет strict отказ на bool/negative и исходные positions при forged inputs. Статический просмотр подтверждает отсутствие второго алгоритма перечисленных правил. Тесты добавить в существующие тестовые файлы среза из §2. A0 ещё не реализован. Порядок **предлагается** изменить на A0 → A → B → C → D; это не утверждение, что прежний код прошёл новый порядок.

### A. World и conflict

Реализовать exact methods без owning lookup/IO. Facts capture/dependency содержат original indices; check принимает оба tuples одним вызовом. Capture position уникальна; dependency fact ссылается на exact capture той же позиции; tuple order соответствует исходному обходу, object/collection категория определяется type ref. Несогласованность internal facts → programming ValueError/TypeError, не SourceFailure. Не перехватывать такие ошибки как business absence.

Отдельные faults внутри incoming usage не передаются сюда: tests непосредственно строят пригодные leaf facts с исходными индексами, демонстрируя отсутствие зависимости от целого usage. Полную INVALID_SHAPE+REVISION_CONFLICT aggregation исходного request этот слой не заявляет.

По согласованной корректировке 2026-11-16 проверяется только revision conflict внутри exact SourceCaptureRef, по offending dependency occurrence; порядок stable. Capture uid не доступен в этом POJO, CAPTURE_ID_CONFLICT остаётся witness/finalization. Разные revisions разных captures не conflict. Никакого автоматического dedup input для скрытия ошибок.

Слой закрывается адресными tests world/empty-world context, exact capture separation, object/collection revision conflict, допустимые повторения и history, несовместимые facts и stateless repeat calls.

### B. Canonical checker

Сравнивать full canonical bytes existing values, не repr/hash/python module names. Uses отсортированы по full capture ref; objects/collections по exact refs. Duplicate captures, empty usage и duplicate dependency identities проверять только функциями A0; не нормализовать input. Application отвечает за byte ordering и связывание результата правила с путём, не содержит второй алгоритм POJO-инварианта. Если на одной коллекции одновременно нарушены порядок и уникальность, формируется один NON_CANONICAL_PROOF на эту коллекцию. Foreign world/revision conflicts относятся к собственным checker responsibilities и не переименовываются в NON_CANONICAL_PROOF без самостоятельного canonical нарушения.

Уточнение structural prerequisite: здесь «структурно пригодный proof» означает доступный правильный roster и пригодные strict leaf refs, а не успешный whole-model semantic validator. Existing SourceDurableProof constructor сам запрещает некоторые noncanonical случаи; для negative tests допустим model_construct с корректными leaves и нарушенным canonical инвариантом. Checker не вызывает whole-proof encode/model_validate до обнаружения этих нарушений, иначе ValueError заменит требуемые typed issues. Для sorting кодировать отдельные пригодные capture/source refs, а не заведомо invalid целый proof. Непригодный leaf вне prerequisites — structural/programming отказ; full malformed traversal остаётся вне среза.

Field paths — existing CheckedPath с typed FieldRef к конкретной nested collection. Aggregator request-local, concrete SourceFieldIssue, стабильный исходный порядок. Success — пустой tuple; никакого SourceProofResult.

Слой закрывается tests unsorted/duplicate uses/dependencies, empty usage, пустого допустимого proof, exact typed paths и неизменности входа.

### C. Atom index

Вход — canonical proof после checker B. Порядок: uses → objects → collections. Каждый atom представлен existing SourceCaptureUsage с исходным full capture и ровно одной dependency; второй tuple пуст. Capture identity входит в atom; одинаковая revision в разных captures даёт разные atoms. Пустой proof → пустой tuple.

Canonical prerequisite обеспечивает caller. `enumerate` не проверяет его повторно, не нормализует вход и **не гарантирует runtime exception** при прямом вызове с noncanonical proof; такой вызов нарушает внутренний контракт, его результат нельзя использовать. Constructor dependencies не добавляются. В этом срезе tests выполняют B→C только при пустом результате B; это проверка договорённого использования, не evidence production guard. Обязательный отказ от вызова AtomIndex/SelectionChecker после ошибки B проверяется на настоящем request caller при отдельной поставке traversal; эта проверка остаётся открытой, а не подменяется тестовым orchestrator.

Слой закрывается literal expected atom order, capture-distinctness, empty proof и source tuple immutability tests.

### D. Selection checker

Единственная constructor dependency — AtomIndex. Proof canonical prerequisite обеспечен B. Fingerprint = existing content_digest(CanonicalCodec(SOURCE_PROOF_SCHEMA_V1).encode(proof)).hex(). Никакого caller codec/manifest. Fingerprint mismatch не скрывает независимый valid-int bounds failure.

При пригодном roster selection можно проверить forged values из model_construct: bool/negative/unsorted/duplicate → INVALID_SELECTION по исходному path; structural пригодность и общий порядок реализуются по A0, а не вторым циклом правил selection. Каждое пригодное неотрицательное int проверяется по bounds; остальные indices не останавливаются. Не восстанавливать новую исправленную selection. Malformed container/отсутствующее поле за пределами этого leaf-проверяющего среза; public request traversal должен сохранить structural refusal самостоятельно.

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
| Порядок | Принятие исправленной архитектуры и дельты A0 → implementation-plan → A0 → A → B → C → D → общий regression/typing → отдельная независимая приёмка; до принятия дельты код не продолжать |
| POJO/errors | Новые DTO/errors не вводятся, SourceOperation не dispatch; wrong-root/path negative typing обязательно |
| CRUD/settings | В этом срезе public data/settings операции не создаются; full-domain CRUD acceptance не заявляется и не отменяется |
| Внешние зависимости | Shared values/codecs уже существуют; owning key/body/transaction integration отсутствует в graph, не заменяется stub |
| Полнота scope | A0, пять компонентов и tests реализованы либо незавершённый компонент явно не принимается; no full G1 claim |

## 6. Результат и следующий gate

После реализации — точный список imports/файлов, commands/results, пределы evidence и отдельный запрос независимой проверки в видимом чате по указанию пользователя. Полный request validation и остальные архитектурные вопросы Source не объявляются закрытыми. До реализации требуется завершить pre-code проверку применимых SoT и разрешить обнаруженные конкретные расхождения; сам этот документ не evidence выполненных tests.

### Историческое evidence реализации 2026-11-16 (до исправления плана)

Пять application-компонентов §2 написаны до этого ревью. Прежнее утверждение о соблюдении утверждённого порядка снято: допуск исправленной архитектуры не зафиксирован, A0 не реализован, код содержит повторяющиеся правила. SourceCaptureRef не содержит capture_uid, поэтому здесь только revision conflicts exact capture; witness/finalization не реализованы. AtomIndex требует canonical prerequisite от caller. Selection checker возвращает field issues до logic issues и сохраняет независимую проверку bounds при чужом fingerprint.

Собственные проверки §4: адресные tests — 13 PASS; regression Source — 53 PASS (включая эти 13); shared canonical/UUID — 13 PASS. Core-positive pyright — 0 errors; core-negative — ровно 4 ожидаемые ошибки: неверный тип path, неверный proof value, неверный world argument и несовместимый root path. Исходные typing fixtures не изменялись. Производственные imports ограничены Source values/encoding и shared validation/fields; IO, owning adapters и public operations не добавлены.

Эти результаты относятся к прежнему коду и не доказывают соответствие исправленной редакции. Статус: **CHANGES REQUIRED; independent PASS отсутствует**. Следующий gate — повторное ревью и принятие исправленного плана с дельтой A0. Только после этого — корректировка реализации через implement-plan, повторные проверки и отдельная независимая приёмка кода. Полный G1, request traversal/aggregation, POJO TODO typed-errors и интеграционный техдолг остаются открытыми.
