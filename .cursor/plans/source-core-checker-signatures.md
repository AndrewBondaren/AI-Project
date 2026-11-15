# Source core — exact checker API

2026-11-15. DRAFT шага 1 остатка архитектуры: signatures, constructors и diagnostics. Основание — согласованный CheckedPath подход в source-core-internal-api.md §3; коды и порядок — source-proof-v2-contract-spec.md §11.3. Это не реализация и не изменение public DTO/shared diagnostics.

## 1. Общая граница

Корень модулей — `app.application.worldData.sourceVersioning.proof.validation`, один именованный checker на модуль с тем же lowerCamelCase именем. Все методы sync, pure, без IO, mutation, holds или public calls. Отрицательный результат — existing issues; пустой tuple означает отсутствие найденных нарушений этой проверки, не полную admission. SourceFailure собирается request-specific стадией, не каждым checker. Operation в checker не передаётся.

В signatures ниже используются существующие Source POJO и shared BaseModel/EntityUid/CheckedPath. `SourceFieldIssue | SourceLogicIssue` — union существующих типов, не новый carrier. Aggregator стабильно разделяет issues на два tuple и применяет порядок §11.3; порядок вызова helpers не заменяет нормативный порядок diagnostics.

## 2. World и descriptor/key

```python
# sourceWorldChecker.py
class SourceWorldChecker:
    def __init__(self) -> None: ...
    def check(self, actual: EntityUid, *, expected: EntityUid,
              group_index: int | None, use_index: int | None,
              source: SourceVersionRef | SourceCollectionVersionRef | None,
    ) -> tuple[SourceLogicIssue, ...]: ...

# sourceIdentityChecker.py
class SourceIdentityChecker:
    def __init__(self, descriptors: SourceDescriptorLookup,
                 keys: SourceIdentityKeyAdapter) -> None: ...
    def check[RootT: BaseModel, RefT: (SourceVersionRef, SourceCollectionVersionRef)](
        self, source: RefT, *, path: CheckedPath[RootT, RefT],
        group_index: int | None, use_index: int | None,
    ) -> tuple[SourceFieldIssue | SourceLogicIssue, ...]: ...
```

World checker — отдельный инвариант, общий для request/proof/capture/identity. Нужен в том числе для пустого foreign-world proof: отсутствие atoms не отменяет проверку world. Единственный код WRONG_WORLD. Request стадия вызывает его для фактов с собственной world identity; GLOBAL library identity не получает выдуманный world.

Identity checker владеет только descriptor/category/scope/key_kind и exact key admissibility. SourceVersionRef path продолжается через object_id и typed variant; collection path — через collection_id. Unknown descriptor → UNKNOWN_DESCRIPTOR; несовместимая definition → DESCRIPTOR_MISMATCH; invalid key → INVALID_IDENTITY по точному owning key field. При unknown/mismatched definition зависимая owning key проверка пропускается. Значение path и source поступают из одного обхода request.

**Уточнение SourceIdentityKeyAdapter:** ранее предложенный internal abstract `validate_exact(identity: SourceObjectId) -> SourceFieldCode | None` сохраняется как key-only port, отрицательный результат только INVALID_IDENTITY. Он выбирает подтверждённую owning validation по immutable registration, не проверяет world/category/membership. Collection/key_kind NONE не вызывает adapter. Missing required registration — composition error, не permissive успех и не business отсутствие. Concrete adapters — INT-TERRAIN, не новая реализация чужих validators. Exact constructor immutable key registry конкретного adapter относится к интеграции, не маскируется пустым implementation.

## 3. Конфликты usage

```python
# sourceUsageConflictChecker.py
class SourceUsageConflictChecker:
    def __init__(self) -> None: ...
    def check(
        self,
        uses: tuple[tuple[int | None, int, SourceCaptureUsage], ...],
    ) -> tuple[SourceLogicIssue, ...]: ...
```

Каждый элемент — `(original_group_index, original_use_index, usage)`. Это internal tuple явно типизированных существующих значений, не persisted/public DTO и не зеркало ошибки. Для single request group=None; для groups/available — исходная позиция. Весь request передаётся одним batch, иначе теряются cross-use/cross-group conflicts. Checker не нормализует и не удаляет повторения.

Capture uid с несовместимым full ref → CAPTURE_ID_CONFLICT; внутри одной full capture identity разные revisions dependency → REVISION_CONFLICT с exact source и исходными индексами offending occurrence. Exact повтор declared refs допустим; разные revisions в разных captures допустимы. World/descriptor checks выполняются своими owners, не повторяются здесь. Повреждённые structural branches не передаются как валидные usages; независимые доступные usages продолжают проверяться.

## 4. Canonical proof и selection

```python
# sourceProofCanonicalChecker.py
class SourceProofCanonicalChecker:
    def __init__(self) -> None: ...
    def check[RootT: BaseModel](
        self, proof: SourceDurableProof, *,
        path: CheckedPath[RootT, SourceDurableProof],
    ) -> tuple[SourceFieldIssue, ...]: ...

# sourceSelectionChecker.py
class SourceSelectionChecker:
    def __init__(self, atoms: SourceProofAtomIndex) -> None: ...
    def check[RootT: BaseModel](
        self, selection: SourceProofSelection, *, proof: SourceDurableProof,
        path: CheckedPath[RootT, SourceProofSelection],
        selection_index: int | None,
    ) -> tuple[SourceFieldIssue | SourceLogicIssue, ...]: ...
```

Оба используют fixed existing SOURCE_PROOF_SCHEMA_V1/CanonicalCodec; caller не подаёт schema. Canonical checker проверяет persisted order/unique form, пустые uses и nested dependency collections; NON_CANONICAL_PROOF указывает на точную typed nested collection. Не нормализует и не проверяет наличие body. Semantic conflicts остаются checker §3; сообщения не дублируются как конфликт и order error без самостоятельного нарушения.

Selection checker получает canonical proof; его own validation не повторяет canonical checker. Invalid bool/negative/duplicate/unsorted indices → INVALID_SELECTION по typed path; bounds проверяются только для пригодных indices. Fingerprint mismatch → SELECTION_PROOF_MISMATCH; bounds → SELECTION_OUT_OF_RANGE. selection_index=None для одиночного SELECT, исходный индекс для groups; он записывается в existing logic group_index, use_index=None согласно §11.3. Checker не строит subset и не проверяет соответствие ожидаемой группе: это SourceProofGroupMatcher.

Число selections проверяет request-specific VERIFY_GROUPS стадия: единственный GROUP_COUNT_MISMATCH на result.selections. Это relation двух полей конкретного request, не отдельный универсальный service. Не создавать SourceSelectionCountChecker без иной самостоятельной ответственности.

## 5. Membership предъявленного capture

```python
# sourceCaptureMembershipChecker.py
class SourceCaptureMembershipChecker:
    def __init__(self, descriptors: SourceDescriptorLookup) -> None: ...
    def check(
        self, usage: SourceCaptureUsage, *,
        witness: SourceCaptureWitness, capture: SourceCapture,
        collections: tuple[tuple[SourceCollectionVersion, SourceCollectionBody], ...],
        group_index: int | None, use_index: int,
    ) -> tuple[SourceLogicIssue, ...]: ...
```

Здесь только relation checks уже структурно пригодных values: usage соответствует witness/capture mappings и membership. Structural errors decoded content не адресуются ложным путём внутри request: owning read boundary отвечает за decoding/corrupt payload. World и descriptor admission выполняются соответствующими checks до зависимых membership проверок.

Пары collection mapping/body передаются явно, не связываются по неоговорённому порядку двух списков. Read binding обязан доказать ArtifactRef→decoded bytes/value связь; pure checker её не выдумывает. Противоречивые mappings, отсутствующая requested revision, неполный collection membership классифицируются BODY_MAPPING_CONFLICT, DEPENDENCY_NOT_CAPTURED, INCOMPLETE_COLLECTION по §11.3; CAPTURE_ID_CONFLICT — при несовпадении предъявленного witness с usage capture identity. Exact conditions не расширяют meaning кодов. Missing/unsealed/corrupt artifact и committed finalization — ответственность IO, не этого checker.

## 6. Request traversal и ошибки формы

Request-specific стадия держит original typed root и обходит его поля через FieldRef/CheckedPath. Для пригодного source ref передаются ref+path и original indices; для nested malformed поля сохраняется существующий INVALID_SHAPE на известном содержащем поле. Текст ValueError не используется для выбора кода. Если ошибка неизвестного root/extra не представима existing field path, применяется предусмотренный structural отказ, без fake path.

Невалидные внутренние indices, path/value type mismatch и отсутствующий обязательный constructor binding — programming/composition failures, не Source business failures. Эти случаи нельзя ловить широким ValueError и переводить в INVALID_IDENTITY. CheckedPath не удостоверяет происхождение значения: tests request traversal обязаны проверять, что diagnostic path относится к реальному исходному элементу.

Не вводится общий mutable context. Checkers не хранят request/path между вызовами. Return tuples и issues immutable. Request-specific aggregator единственный назначает operation и исходный порядок ошибок; FieldIssue и LogicIssue остаются раздельными existing carriers.

## 7. Проверки и статус

Минимальная проверка design/implementation: negative typing path↔value; SourceVersionRef/SourceCollectionVersionRef paths; original root в ADMIT/READ/GROUPS/VERIFY/SELECT/COVERAGE; cross-group conflict; historical revisions; foreign empty proof; wrong fingerprint вместе с пригодными независимыми ошибками; отсутствие IO и повторной нормализации; отсутствие duplicate diagnostics; independent aggregation при повреждённой соседней ветви.

Это exact proposal шага 1, не выполненные tests и не independent PASS. Шесть checker-классов (world выделен из смешанной identity проверки), constructor dependencies и return types предъявлены. У SourceIdentityKeyAdapter пока нет production integration; это не мешает принять pure signatures, но не позволяет объявить полную admission готовой. Public operation constructors с IO/closure не входят в этот шаг. Изменения кода и shared типов отсутствуют.
