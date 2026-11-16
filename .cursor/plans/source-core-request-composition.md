# Source core — request checks, aggregation и pure computation

2026-11-15. DRAFT конкретной внутренней композиции. Основание — source-core-checker-signatures.md и source-core-internal-api.md; семантика proof/errors — accepted spec §9/11.3. Ни public runtime, ни независимая приёмка не заявлены. Код не разрешён.

## 1. Ответственность request check stage

Одна стадия отвечает за проверку одного вида исходного request. Она обходит поля, строит typed paths, вызывает единственные реализации инвариантов и агрегирует issues. Она не нормализует, не извлекает subset, не читает storage и не возвращает durable result. Локальный обход вложенных records — алгоритм одной проверки, не межоперационная оркестрация.

Корень модулей: `app.application.worldData.sourceVersioning.proof.validation.requests`. Каждый класс — отдельный lowerCamelCase модуль. Точные кандидаты:

```python
class SourceAdmissionRequestChecker:
    def __init__(self, worlds: SourceWorldChecker,
                 identities: SourceIdentityChecker,
                 conflicts: SourceUsageConflictChecker) -> None: ...
    def check(self, request: SourceProofInput) -> SourceFailure | None: ...

class SourceReadRequestChecker:
    def __init__(self, worlds: SourceWorldChecker,
                 identities: SourceIdentityChecker,
                 conflicts: SourceUsageConflictChecker,
                 canonical: SourceProofCanonicalChecker) -> None: ...
    def check(self, request: SourceProofReadInput) -> SourceFailure | None: ...

class SourceGroupAdmissionRequestChecker:
    def __init__(self, worlds: SourceWorldChecker,
                 identities: SourceIdentityChecker,
                 conflicts: SourceUsageConflictChecker) -> None: ...
    def check(self, request: SourceProofGroupsInput) -> SourceFailure | None: ...

class SourceGroupVerificationRequestChecker:
    def __init__(self, worlds: SourceWorldChecker,
                 identities: SourceIdentityChecker,
                 conflicts: SourceUsageConflictChecker,
                 canonical: SourceProofCanonicalChecker,
                 selections: SourceSelectionChecker) -> None: ...
    def check(self, request: SourceProofGroupsVerifyInput) -> SourceFailure | None: ...

class SourceSelectionRequestChecker:
    def __init__(self, worlds: SourceWorldChecker,
                 identities: SourceIdentityChecker,
                 conflicts: SourceUsageConflictChecker,
                 canonical: SourceProofCanonicalChecker,
                 selections: SourceSelectionChecker) -> None: ...
    def check(self, request: SourceProofSelectInput) -> SourceFailure | None: ...
```

Operation фиксирована классом: ADMIT, READ, ADMIT_GROUPS, VERIFY_GROUPS, SELECT соответственно. Нет mode/operation переключателя в public check, нет универсального класса на пять операций. None означает только завершение request-level проверки, не capture authority или доступность bytes. Pure processing исходного SourceProofReadInput при ADOPT/COVERAGE не должно вызывать этот READ-specific класс и затем переименовывать operation: такие owners используют общие инварианты с собственным root по своим принятым контрактам.

Общая приватная механика обхода полей переиспользуется через typed функции, сохраняющие RootT/path. Она не содержит вторую реализацию инвариантов и не превращается в mode-dispatch service. Отдельный universal traversal/context DTO не нужен. Точные функции, их входы/результаты/ошибки и вложенные вызовы определяются в архитектуре АР-1 **до реализации**, а не в implementation-срезе. Negative typing проверяет принятое решение, не заменяет его.

### Решение пользователя: вариант 2 — typed traversal по ветвям

2026-11-16, ответ «Ок» на сравнение трёх вариантов. Выбран обход известной структуры каждого request с сохранением пригодных leaves повреждённых ветвей. Полная предварительная semantic revalidation request и универсальный рекурсивный обходчик всех моделей не выбраны. Решение касается архитектуры, не разрешает код или новый локальный срез.

| Участник | Единственная обязанность | Результат и предел гарантии |
|---|---|---|
| Root boundary | Допустить известный concrete request root | Неизвестный root/непредставимая root error остаётся structural отказом; fake path не создаётся |
| Typed traversal функции | Извлечь известные поля/элементы и установить их structural пригодность с исходным RootT/path | Пригодные facts и existing diagnostics; original indices не уплотняются, repaired request не создаётся |
| Semantic checker | Проверить один Source-инвариант пригодных facts | Existing SourceFieldIssue/SourceLogicIssue; не обход другого request и не storage |
| Request checker | Свести независимые проверки своего вида request | SourceFailure с фиксированной operation либо None; не transformation |
| Public operation owner | После успешной проверки выполнить собственную принятую внутреннюю цепочку | Не запускать зависимый алгоритм после refusal; не вызывать public операции друг друга |

Правила продолжения: повреждён `objects[0]` — выдать diagnostic его исходного поля, проверить `objects[1]`; отсутствующий/непригодный capture исключает только capture-dependent проверки, не проверки доступных соседних world/identity полей. Непригодный контейнер не заменяется пустым tuple. При неизвестной форме элемента используется существующий путь к содержащему полю; неизвестные child names не становятся выдуманными FieldRef. Вложенные forged/model_construct instances не считаются пригодными только по isinstance. Полная model_validate исходного request не должна обрывать независимые проверки semantic after-validator; точная structural leaf boundary должна быть определена в API функций.

Общие функции не принимают operation/mode switch, не нормализуют, не получают holders и не читают storage. Возвращаются конкретные facts и существующие issues; новый общий TraversalContext/Any-carrier запрещён. Сохранение происхождения после normalization/union для closure — отдельный контракт АР-1, не дополнительная ответственность traversal.

Остаток SRC-AR-04: предъявить точные signatures/functions для proof/usages/dependencies/selections и structural leaf boundary, с nullable/повреждёнными ветвями и original positions в результатах; сверить их вызовы во всех пяти request checkers. Принятие варианта 2 закрывает выбор подхода, **не закрывает этот остаток и не означает приёмку АР-1**.

## 2. Последовательность и prerequisites

### Принятое представление результатов traversal

2026-11-16: пользователь выбрал **вариант 1 — immutable facts и diagnostics**, затем подтвердил оба ограничения ответственности. Это второй выбор (форма результата), не отмена ранее выбранного подхода «typed traversal по ветвям».

1. Функции обхода только извлекают известные поля/элементы и проверяют structural пригодность. Они **не вызывают semantic checkers**, не назначают SourceOperation и не формируют итоговый SourceFailure.
2. Request checker использует общие функции обхода, **не реализует этот обход повторно**. Его ответственность — порядок semantic checks, сбор независимых diagnostics и итоговый SourceFailure с фиксированной operation либо None.

Результат функции — конкретные immutable tuples пригодных facts и существующих diagnostics. Каждый fact сохраняет исходные indices и typed path; повреждённая ветвь не заменяется исправленным POJO или пустым контейнером. Например, при повреждённом objects[0] пригодный objects[1] возвращается с индексом 1, а issue — по пути элемента 0. Не вводятся universal context, mutable accumulator во внешнем интерфейсе, callbacks, ленивый поток событий либо новый публичный DTO. Вызов возвращает все доступные structural diagnostics своей ветви, не требует дочитывания iterator.

Приватные имена inspect_proof/inspect_usages/inspect_dependencies/inspect_selection остаются кандидатами до предъявления exact signatures. Конкретный состав tuples, RootT/path binding и structural leaf validation без преждевременных semantic after-validators — оставшаяся работа АР-1/SRC-AR-04. Выбор формы результата не считается завершением архитектуры или разрешением кода.

### АР-1: exact proposal приватных traversal функций

Следующие сигнатуры — проект внутри целой архитектуры, не код и не принятый runtime API. RootT — existing BaseModel; все paths — existing CheckedPath. Функции располагаются в `proof/validation/requests/traversal.py`; это private pure модуль без service-класса. Извлечение идёт через FieldRef, продолжение пути — field/item/variant; строковые имена полей не становятся второй схемой.

```python
def inspect_proof[RootT: BaseModel](
    proof: SourceDurableProof, *, path: CheckedPath[RootT, SourceDurableProof],
) -> tuple[
    EntityUid | None,
    tuple[SourceCaptureUsage, ...] | None,
    tuple[SourceFieldIssue, ...],
]: ...

def inspect_usages[RootT: BaseModel](
    uses: tuple[SourceCaptureUsage, ...], *,
    path: CheckedPath[RootT, tuple[SourceCaptureUsage, ...]],
) -> tuple[
    tuple[tuple[int, SourceCaptureUsage, CheckedPath[RootT, SourceCaptureUsage]], ...],
    tuple[SourceFieldIssue, ...],
]: ...

def inspect_usage[RootT: BaseModel](
    usage: SourceCaptureUsage, *, path: CheckedPath[RootT, SourceCaptureUsage],
) -> tuple[
    SourceCaptureRef | None, SourceDependencySet | None,
    tuple[SourceFieldIssue, ...],
]: ...

def inspect_dependencies[RootT: BaseModel](
    dependencies: SourceDependencySet, *, path: CheckedPath[RootT, SourceDependencySet],
) -> tuple[
    tuple[tuple[int, SourceVersionRef, CheckedPath[RootT, SourceVersionRef]], ...],
    tuple[tuple[int, SourceCollectionVersionRef, CheckedPath[RootT, SourceCollectionVersionRef]], ...],
    tuple[SourceFieldIssue, ...],
]: ...

def inspect_selection[RootT: BaseModel](
    selection: SourceProofSelection, *, path: CheckedPath[RootT, SourceProofSelection],
) -> tuple[
    RevisionHex | None,
    tuple[tuple[int, int, CheckedPath[RootT, int]], ...],
    tuple[SourceFieldIssue, ...],
]: ...
```

Первая int в каждом fact — исходная позиция, а не номер в возвращённом tuple. Последняя функция возвращает только structurally пригодные non-negative int с исходными paths; порядок/duplicates и bounds не проверяет. Primitive schema берётся из existing POJO annotation. Вторая int — предъявленное значение индекса. None означает недоступность поля из-за зафиксированного structural refusal, не допустимое значение в исходном обязательном поле. Каждый такой None сопровождается issue. Пустой facts tuple при повреждённом контейнере сопровождается issue и не означает пустой валидный вход. Semantic стадия не восстанавливает новый selection или usage из этих tuples.

**Существенный предел типизации:** returned model instances — исходные экземпляры известного типа, пригодные для дальнейшего обхода, а не сертификат полного semantic допуска. `inspect_usages` не выкидывает целый use из-за повреждения его dependencies: проверяет record envelope, а поля разбираются inspect_usage и inspect_dependencies. Wrong runtime type элемента даёт structural issue по его original path и пропускает только этот элемент. `inspect_usage` рассматривает capture и dependencies независимо. При доступном record с неизвестными extra полями выдаётся issue по содержащему полю и продолжается обработка известных полей; исходный объект не исправляется. Любые diagnostics запрещают завершение operation успехом, даже если часть facts пригодна.

`inspect_proof` независимо проверяет schema_version по existing field schema, world_uid и форму uses; не проверяет canonical order, duplicate captures либо world relations. Missing/invalid version создаёт issue, а доступные world/uses сохраняются для независимых проверок. Путь uses для inspect_usages продолжается исходным FieldRef, не реконструируется по результату функции. Public root неизвестного типа не передаётся этим функциям. Ошибка CheckedPath/несовместимые аргументы — programming error; её нельзя превращать в business INVALID_SHAPE.

**Вложенные вызовы:** request-specific root traversal → inspect_proof (где есть persisted proof) → inspect_usages → inspect_usage → inspect_dependencies. Selection-ветка отдельно вызывает inspect_selection. Каждый вызов возвращает полностью вычисленный immutable tuple, callbacks/yield отсутствуют. Group wrappers сохраняют исходный group index вне дочерней функции; при формировании существующего conflict batch добавляют group/use indices только к допущенным leaf refs. Expected и presented стороны не смешиваются. Проверки world/identity/revisions/canonical/selection выполняются request checker после обхода, не указанными функциями.

**Оставшийся обязательный контракт перед приёмкой этих signatures:** leaf inspection capture/ref/identity/revision и обход root/group wrappers. Простое isinstance или whole-model model_validate не заменяют leaf boundary. Текущий код содержит semantic validators `LibraryMemberId.canonical_uuid`, `_SourceIdentity.nonempty_descriptor`, `SourceCaptureRef.witness_shape`, а также relation validators usage/proof. Поэтому returned structural ref ещё нельзя передавать conflict checker/codec, требующим валидный ref. Нужны exact scalar facts и однократный semantic admission leaf до этого вызова. Нельзя обходить validators через model_construct, анализировать текст ValueError или объявлять любой semantic отказ INVALID_SHAPE. Эти функции и распределение existing validators должны быть предъявлены в АР-1, без копии схемы/зеркальных POJO. SRC-AR-04 остаётся OPEN до завершения этой части и сверки всех пяти callers.

### Порядок проверки после structural traversal

1. Проверить structural пригодность request и вложенных ветвей. Root failure без представимого пути сохраняет предусмотренный Pydantic отказ. Для представимых nested failures — INVALID_SHAPE с known containing path; оригинальные индексы не сдвигать.
2. Обойти все доступные world/descriptor/key facts. Проверить world у пустого proof/group, даже когда нет dependencies. Unknown descriptor отменяет только зависящую key проверку; остальные группы продолжаются.
3. Собрать пригодные capture refs и dependency refs с исходными group/use/dependency indices по exact facts API checker §3. Проверить conflicts целым batch, не отдельно на каждой группе. Не восстанавливать повреждённый SourceCaptureUsage ради вызова checker: пригодные leaves внутри него сохраняются независимо от повреждённых соседей. Expected и presented proof — разные стороны сравнения, их facts проверяются раздельно.
4. Для persisted стороны проверить canonical форму без изменения. Для declared стороны repetitions/empty usages не объявлять persisted ошибкой.
5. Проверить доступные selections; bounds требуют пригодного canonical proof/atom index. Проверка fingerprint не допускает чтения latest. При group-count mismatch дополнительно проверить доступные selections, не запускать matching отсутствующих пар.
6. Собрать SourceFailure после всех независимых проверок. При наличии failures normalizer/union/extractor/matcher не вызываются. При None — выполнить конкретное pure преобразование §4.

Повторная model_validate всего request не должна обрывать проверку всех доступных nested branches первым semantic after-validator. Будущий implementation должен различить structural damage и checks, перенесённые в typed boundary; existing TODO в POJO не снимаются этим документом. Нельзя считать ValueError text машинным кодом ошибки.

## 3. Aggregation и пути

Field paths создаются от actual request class через existing FieldRef/CheckedPath. Проверяемое значение и path извлекаются одним обходом; checker не доказывает их instance identity. Examples root сохраняется:

- ADMIT: uses[i].dependencies…
- ADMIT_GROUPS: groups[g].uses[i].dependencies…
- VERIFY_GROUPS: expected.groups[g].uses[i]… и result.admission.proof… / result.selections[s]…
- READ/SELECT: proof…; SELECT selection…

Existing ValidatorAggregationHelper создаётся заново на каждый check и принимает только concrete SourceFieldIssue/SourceLogicIssue. Никакой instance-level mutable issues list между requests. Aggregation использует фазовые локальные коллекции и stable обход, а не разбор строк path/message для сортировки.

Field issues — порядок полей и исходных индексов. Logic issues — world → descriptor → capture → dependency → selection → closure; внутри фазы исходный порядок. Proof-level отсутствующие indices остаются None. В этой стадии closure issues ещё не вычисляются. Поздняя IO стадия добавляет свои diagnostics согласно той же семантике, не меняя исходную operation. SourceFailure создаётся только для непустого результата, success — None.

## 4. Pure sequence после проверки

| Request | Request checker | Единственный следующий pure алгоритм | Результат этого участка |
|---|---|---|---|
| SourceProofInput | AdmissionRequestChecker | normalizer.normalize(world_uid, uses) | SourceDurableProof как значение, без admission/closure |
| SourceProofReadInput | ReadRequestChecker | Нет преобразования | Исходный proof без изменения |
| SourceProofGroupsInput | GroupAdmissionRequestChecker | union.build(request) | Internal SourceProofGroupProjection |
| SourceProofGroupsVerifyInput | GroupVerificationRequestChecker | matcher.match(request) | None либо SourceFailure; refs ещё не сверены с вычисленным closure |
| SourceProofSelectInput | SelectionRequestChecker | extractor.extract(request) | Самостоятельный SourceDurableProof как значение |

Public result формируется **только позднее**, после exact finalized capture checks и полного computed closure. Не создавать SourceProofResult с пустыми refs для имитации завершения pure участка. Пустой proof имеет допустимую семантику, но не используется для скрытия отсутствующего collector. Internal stages не вызывают публичные Source методы друг друга.

## 5. Constructor graph и внешние prerequisites

```text
SourceDescriptorRegistry → SourceDescriptorLookup ┐
подтверждённый key-validation adapter ────────────┴→ SourceIdentityChecker
SourceWorldChecker / SourceUsageConflictChecker / SourceProofCanonicalChecker
fixed schema → SourceProofAtomIndex → SourceSelectionChecker
          ↓ shared invariant instances
пять отдельных request checkers
          ↓ успешно проверенные исходные значения
normalizer / union builder / extractor / matcher
          ↓
pure result → будущая exact-read/closure интеграция → public result
```

Полные request checkers используют owning key validation. Поэтому **они не являются полностью независимым production admission-срезом**, пока INT-TERRAIN/другие нужные descriptor bindings не подтверждены. Не вводить `skip_keys`, `allow_partial`, None-adapter или TEST mode в production для снятия зависимости.

**Историческое решение после R2:** world/conflict/canonical/selection инварианты и atom enumeration поставлены в A0→D и получили независимый PASS. Перечень — source-core-independent-slice.md. Это не разрешает следующие локальные срезы: действующий порядок пользователя требует сначала завершить и принять архитектуру целого ядра. Normalizer, union builder, extractor, matcher, identity/membership и request-wide checkers остаются в этой архитектуре со своими prerequisites; тестовые значения не заменяют owning admission.

## 6. Матрица проверки request composition

| Сценарий | Обязательный результат |
|---|---|
| Ошибки в groups[0] и groups[2] при повреждённой ветви [1] | Доступные независимые ошибки обеих групп сохранены, indices не сдвинуты |
| В одном use objects=(None, A@r1), в другом той же capture A@r2 | INVALID_SHAPE и REVISION_CONFLICT; facts сохраняют исходные позиции, никакого repaired usage |
| Capture ref непригоден, соседние dependency leaves пригодны | Отменён только capture-relative conflict; независимые shape/world/descriptor проверки продолжаются |
| Конфликт revision между uses разных groups одной full capture | REVISION_CONFLICT до union |
| Historical revisions разных captures | Не ложный conflict |
| Foreign empty proof | WRONG_WORLD, не потерян из-за отсутствия atoms |
| Noncanonical READ | Отказ без normalize и без изменения proof |
| Неверные count/fingerprint/индексы | Все независимые применимые issues, без dependent extract/match |
| VERIFY_GROUPS failure | Пути от verify root, не synthetic ADMIT/READ |
| Повтор check на том же checker | Нет накопленных issues от предыдущего вызова |
| Любой request-level failure | Ноль вызовов преобразования и IO |
| Pure успешный результат | Нет claims о finalization/holds и нет fake durable_refs |

Матрица пока design; tests не выполнялись. Конкретные test doubles допустимы для проверки call ordering, но не являются доказательством production owning bindings.

## 7. Итог и остаток

Точная request-check → aggregation → pure transformation последовательность предъявлена. Новых error/context DTO, stateful универсального validator и public pure API для Pack нет. Полная admission не приписана независимому pure-срезу.

До implementation: завершение АР-1…АР-6 и приёмка архитектуры целого ядра по обязательным критериям проекта. Затем — последовательная реализация архитектурных шагов основного плана через implement-plan. Выбирать новый independent subset запрещено. Source mutation/capture/prune/configuration вопросы из единой карты не объявляются завершёнными. Интеграции остаются в source-technical-debt.md.
