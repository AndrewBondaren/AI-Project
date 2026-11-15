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

Общая приватная механика обхода полей может переиспользоваться через typed функции, сохраняющие RootT/path. Она не содержит вторую реализацию инвариантов и не превращается в mode-dispatch service. Отдельный universal traversal/context DTO не нужен. Точные приватные функции определяются в implementation-срезе под negative typing checks, не публичным API потребителя.

## 2. Последовательность и prerequisites

1. Проверить structural пригодность request и вложенных ветвей. Root failure без представимого пути сохраняет предусмотренный Pydantic отказ. Для представимых nested failures — INVALID_SHAPE с known containing path; оригинальные индексы не сдвигать.
2. Обойти все доступные world/descriptor/key facts. Проверить world у пустого proof/group, даже когда нет dependencies. Unknown descriptor отменяет только зависящую key проверку; остальные группы продолжаются.
3. Собрать все доступные `(original_group_index, original_use_index, usage)` и проверить conflicts целым batch; не отдельно на каждой группе. Expected и presented proof — разные стороны сравнения: не объединять их в одну конфликтную историю вместо проверки соответствия.
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

## 5. Constructor graph и граница независимого среза

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

Независимо можно принять и реализовать world/conflict/canonical/selection инварианты и pure algorithms с документированными preconditions и existing values. Тесты этих алгоритмов используют явные значения, а не stub, объявленный owning validation. Coverage таких tests не распространяется на request-wide admission, IO, финализацию или runtime Source.

## 6. Матрица проверки среза

| Сценарий | Обязательный результат |
|---|---|
| Ошибки в groups[0] и groups[2] при повреждённой ветви [1] | Доступные независимые ошибки обеих групп сохранены, indices не сдвинуты |
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

До implementation: архитектурный review/checker signature review, принятие выбранного independent subset и отдельный implement-plan с файлами/проверками. Source mutation/capture/prune/configuration вопросы из единой карты не объявляются завершёнными. Интеграции остаются в source-technical-debt.md.
