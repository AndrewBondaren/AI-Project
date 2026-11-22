# Source core — exact checker API

2026-11-15. DRAFT шага 1 остатка архитектуры: signatures, constructors и diagnostics. Основание — согласованный CheckedPath подход в source-core-internal-api.md §3; коды и порядок — source-proof-v2-contract-spec.md §11.3. Это не реализация и не изменение public DTO/shared diagnostics.

## 1. Общая граница

**Консолидированный proposal 2026-11-16:** Identity/Selection signatures ниже синхронизированы с source-core-traversal-contract.md §4; прежние варианты с whole ref/selection больше не являются инструкцией будущей реализации. Решение принимается в целой архитектуре АР-1…АР-6. Код A0→D получил независимый PASS; прежние записи ниже «не приняты» относятся к истории до этого результата и не распространяют PASS на новую дельту.

Корень модулей — `app.application.worldData.sourceVersioning.proof.validation`, один именованный checker на модуль с тем же lowerCamelCase именем. Все методы sync, pure, без IO, mutation, holds или public calls. Отрицательный результат — existing issues; пустой tuple означает отсутствие найденных нарушений этой проверки, не полную admission. SourceFailure собирается request-specific стадией, не каждым checker. Operation в checker не передаётся.

В signatures ниже используются существующие Source POJO и shared BaseModel/EntityUid/CheckedPath. `SourceFieldIssue | SourceLogicIssue` — union существующих типов, не новый carrier. Aggregator стабильно разделяет issues на два tuple и применяет порядок §11.3; порядок вызова helpers не заменяет нормативный порядок diagnostics.

Уточнение после ревью плана 2026-11-16: signatures остаются кандидатами; написанные пять application-компонентов не приняты. Повторяющиеся локальные правила proof/selection предлагается вынести в Source dataModel `_proofValueRules.py` и переиспользовать из POJO и checkers; exact перечень и порядок A0 — source-core-invariants-implementation.md §3.A0. Checkers владеют request diagnostics, canonical byte ordering и proof-relative checks, не второй реализацией POJO-правил. Эта дельта требует принятия до продолжения кода.

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
    def check[RootT: BaseModel, IdentityT: (
        RegistryMemberId, LibraryMemberId, EntityObjectId,
        SourceSettingsId, SourceCollectionId,
    )](
        self, identity: IdentityT, *, path: CheckedPath[RootT, IdentityT],
        group_index: int | None, use_index: int | None,
        source: SourceVersionRef | SourceCollectionVersionRef | None,
    ) -> tuple[SourceFieldIssue | SourceLogicIssue, ...]: ...
```

World checker — отдельный инвариант, общий для request/proof/capture/identity. Нужен в том числе для пустого foreign-world proof: отсутствие atoms не отменяет проверку world. Единственный код WRONG_WORLD. Request стадия вызывает его для фактов с собственной world identity; GLOBAL library identity не получает выдуманный world.

Identity checker владеет только descriptor/category/scope/key_kind и exact key admissibility. Traversal уже продолжил ref path через object_id/variant либо collection_id; checker получает путь непосредственно к identity после structural/local value допуска. Повреждённая revision не отменяет эту проверку: source=None, исходные group/use сохраняются. Unknown descriptor → UNKNOWN_DESCRIPTOR; несовместимая definition → DESCRIPTOR_MISMATCH; invalid key → INVALID_IDENTITY по точному owning key field. При unknown/mismatched definition зависимая owning key проверка пропускается. Значение identity/path/source поступают из одного обхода request.

**Уточнение SourceIdentityKeyAdapter:** ранее предложенный internal abstract `validate_exact(identity: SourceObjectId) -> SourceFieldCode | None` сохраняется как key-only port, отрицательный результат только INVALID_IDENTITY. Он выбирает подтверждённую owning validation по immutable registration, не проверяет world/category/membership. Collection/key_kind NONE не вызывает adapter. Missing required registration — composition error, не permissive успех и не business отсутствие. Concrete adapters — INT-TERRAIN, не новая реализация чужих validators. Exact constructor immutable key registry конкретного adapter относится к интеграции, не маскируется пустым implementation.

## 3. Конфликты usage

```python
# sourceUsageConflictChecker.py
class SourceUsageConflictChecker:
    def __init__(self) -> None: ...
    def check(
        self,
        *,
        captures: tuple[tuple[int | None, int, SourceCaptureRef], ...],
        dependencies: tuple[tuple[
            int | None, int, int, SourceCaptureRef,
            SourceVersionRef | SourceCollectionVersionRef,
        ], ...],
    ) -> tuple[SourceLogicIssue, ...]: ...
```

Уточнение R1 (2026-11-16): checker получает пригодные факты, а не целые usages. `captures` содержит `(original_group_index, original_use_index, capture_ref)` даже при повреждённых dependencies. `dependencies` содержит `(original_group_index, original_use_index, original_dependency_index, capture_ref, exact_source_ref)` для каждого пригодного ref. Object/collection категория определяется конкретным existing ref type; dependency_index относится к исходному objects либо collections, не к уплотнённому списку. Это internal tuple существующих values, не новый persisted/public DTO или error carrier.

Для single request group=None; для groups/available — исходная позиция. Facts всей стороны request передаются одним batch в исходном порядке; expected и presented стороны не смешиваются. Каждый dependency fact обязан ссылаться на тот же exact capture ref и исходную позицию из captures. Неуникальные capture positions, неверные indices или несогласованные факты — programming error обхода, не business failure. Checker не строит исправленный SourceCaptureUsage и не нормализует вход.

Обход валидирует leaves независимо: непригодный ref получает structural diagnostic и не попадает в dependencies; пригодные соседние refs остаются. При отсутствии пригодного capture ref нельзя проверять capture-relative конфликт этого use, но world/descriptor/shape проверки доступных полей продолжаются. По captures проверяется согласованность исходных позиций даже у use без пригодных dependencies, а не capture_uid identity. Для nested `objects=(None, A@r1)` и соседнего use той же capture с A@r2 итог содержит INVALID_SHAPE по исходному objects[0] и REVISION_CONFLICT по исходному второму use. Capture/world/ref values не достраиваются из defaults.

Корректировка пользователя 2026-11-16: внутри одного exact SourceCaptureRef разные revisions dependency → REVISION_CONFLICT с exact source и исходными group/use indices offending occurrence. CAPTURE_ID_CONFLICT здесь не проверяется: capture_uid отсутствует в SourceCaptureRef и доступен только в decoded SourceCaptureWitness; эта проверка принадлежит witness/finalization. Dependency index сохраняется в facts для исходного порядка и traversal checks, но не добавляется в SourceLogicIssue новым полем. Exact повтор declared refs допустим; разные revisions в разных captures допустимы. World/descriptor checks выполняются своими owners, не повторяются здесь. Повреждённый usage не передаётся как валидный; его пригодные leaf facts продолжают участвовать в проверке.

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
        self, *, fingerprint: RevisionHex | None,
        indices: tuple[tuple[int, int, CheckedPath[RootT, int]], ...],
        proof: SourceDurableProof | None,
        selection_index: int | None,
    ) -> tuple[SourceFieldIssue | SourceLogicIssue, ...]: ...
```

Оба используют fixed existing SOURCE_PROOF_SCHEMA_V1/CanonicalCodec; caller не подаёт schema. Canonical checker проверяет persisted order/unique form, пустые uses и nested dependency collections; NON_CANONICAL_PROOF указывает на точную typed nested collection. Не нормализует и не проверяет наличие body. Semantic conflicts остаются checker §3; сообщения не дублируются как конфликт и order error без самостоятельного нарушения.

Selection checker получает готовые facts: original position, пригодное значение индекса, original path. Structural bool/negative ошибки диагностирует только inspect_selection; semantic duplicate/unsorted — только checker через shared rule. proof при наличии уже canonical; None пропускает только fingerprint/bounds, не проверку порядка indices. fingerprint=None означает уже диагностированную непригодность поля. Fingerprint mismatch → SELECTION_PROOF_MISMATCH; bounds → SELECTION_OUT_OF_RANGE. selection_index=None для одиночного SELECT, исходный индекс для groups; он записывается в existing logic group_index, use_index=None согласно §11.3. Checker не обходит selection повторно, не строит subset и не проверяет соответствие ожидаемой группе: это SourceProofGroupMatcher.

Число selections проверяет request-specific VERIFY_GROUPS стадия: единственный GROUP_COUNT_MISMATCH на result.selections. Это relation двух полей конкретного request, не отдельный универсальный service. Не создавать SourceSelectionCountChecker без иной самостоятельной ответственности.

Уточнение кратности bounds: один SELECTION_OUT_OF_RANGE на selection при наличии хотя бы одного пригодного int вне bounds. Два индекса (4, 5) при трёх atoms не создают два одинаковых logic issues. Точная позиция dependency_indices[j] этим logic carrier не передаётся; добавление такой локализации потребовало бы отдельной контрактной дельты. INVALID_SELECTION остаётся field diagnostic с точным путём. Проверки fingerprint и bounds независимы; расширение SourceLogicIssue не требуется.

## 5. Membership предъявленного capture

```python
# sourceCaptureMembershipChecker.py
class SourceCaptureMembershipChecker:
    def __init__(self, descriptors: SourceDescriptorLookup) -> None: ...
    def check(
        self, usage: SourceCaptureUsage, *,
        witness: SourceCaptureWitness, capture: SourceCapture,
        collections: tuple[tuple[SourceCollectionVersion, SourceCollectionBody], ...],
    ) -> tuple[SourceLogicIssue, ...]: ...
```

Здесь только relation checks уже структурно пригодных values: usage соответствует witness/capture mappings и membership. Structural errors decoded content не адресуются ложным путём внутри request: owning read boundary отвечает за decoding/corrupt payload. World и descriptor admission выполняются соответствующими checks до зависимых membership проверок.

**Адресная дельта АР-1, 2026-11-22:** membership checker больше не принимает group_index/use_index. Все его issues возвращаются с group_index=None/use_index=None. Он проверяет canonical usage один раз, не назначая canonical ordinal как original index. Единственная граница назначения original coordinates — locate_logic по projected occurrences. Collector сохраняет capture/atom context вызова и передаёт его вместе с issue; source/artifact сами не заменяют этот context. Общие capture relation issues локализуются на capture occurrences, dependency issues — на соответствующие exact atom occurrences. Публичный SourceLogicIssue не меняется; world/identity request checkers и selection checker сохраняют собственные уже определённые координаты и через locate_logic повторно не проходят.

Проверка: canonical capture C, заявленный в groups[0].uses[1] и groups[2].uses[0], проверяется один раз; его capture-level issue без indices превращается в два original issues (0,1) и (2,0). Для atom-level issue берутся только uses, где заявлен соответствующий atom. Передача уже локализованной issue в locate_logic — programming failure. Полнота materialized input проверяется до membership, её отсутствие не диагностируется semantic issue.

Пары collection mapping/body передаются явно, не связываются по неоговорённому порядку двух списков. Read binding обязан доказать ArtifactRef→decoded bytes/value связь; pure checker её не выдумывает. Противоречивые mappings, отсутствующая requested revision, неполный collection membership классифицируются BODY_MAPPING_CONFLICT, DEPENDENCY_NOT_CAPTURED, INCOMPLETE_COLLECTION по §11.3; CAPTURE_ID_CONFLICT — при несовпадении предъявленного witness с usage capture identity. Exact conditions не расширяют meaning кодов. Missing/unsealed/corrupt artifact и committed finalization — ответственность IO, не этого checker.

## 6. Request traversal и ошибки формы

Request-specific стадия держит original typed root и обходит его поля через FieldRef/CheckedPath. Для пригодного source ref передаются ref+path и original indices; для nested malformed поля сохраняется существующий INVALID_SHAPE на известном содержащем поле. Текст ValueError не используется для выбора кода. Если ошибка неизвестного root/extra не представима existing field path, применяется предусмотренный structural отказ, без fake path.

Невалидные внутренние indices, path/value type mismatch и отсутствующий обязательный constructor binding — programming/composition failures, не Source business failures. Эти случаи нельзя ловить широким ValueError и переводить в INVALID_IDENTITY. CheckedPath не удостоверяет происхождение значения: tests request traversal обязаны проверять, что diagnostic path относится к реальному исходному элементу.

Не вводится общий mutable context. Checkers не хранят request/path между вызовами. Return tuples и issues immutable. Request-specific aggregator единственный назначает operation и исходный порядок ошибок; FieldIssue и LogicIssue остаются раздельными existing carriers.

## 7. Проверки и статус

Минимальная проверка design/implementation: negative typing path↔value; SourceVersionRef/SourceCollectionVersionRef paths; original root в ADMIT/READ/GROUPS/VERIFY/SELECT/COVERAGE; cross-group conflict; historical revisions; foreign empty proof; wrong fingerprint вместе с пригодными независимыми ошибками; отсутствие IO и повторной нормализации; отсутствие duplicate diagnostics; independent aggregation при повреждённой соседней ветви.

Это exact proposal шага 1, не выполненные tests и не independent PASS. Шесть checker-классов (world выделен из смешанной identity проверки), constructor dependencies и return types предъявлены. У SourceIdentityKeyAdapter пока нет production integration; это не мешает принять pure signatures, но не позволяет объявить полную admission готовой. Public operation constructors с IO/closure не входят в этот шаг. Изменения кода и shared типов отсутствуют.
