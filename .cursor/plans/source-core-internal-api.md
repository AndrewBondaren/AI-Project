# Source core — внутренние методы и зависимости

2026-11-15. DRAFT. Продолжение согласованной декомпозиции, без изменения кода/публичных POJO. Ниже точные кандидаты pure algorithm API и карта зависимостей; полный validation API ещё требует typed diagnostic location-контракта (§3). Не объявлять архитектуру или implementation-план принятыми при этом пробеле.

## 1. Алгоритмы: одна реализация каждой функции

Корень модулей: `app.application.worldData.sourceVersioning`. Все компоненты stateless, кроме immutable constructor dependencies. CanonicalCodec создаётся по existing SOURCE_PROOF_SCHEMA_V1 в owning composition, не передаётся в публичный request. Новых движков canonical/hash нет.

```python
# contracts/descriptorLookup.py
class SourceDescriptorLookup:
    def __init__(self, definitions: SourceDescriptorRegistry) -> None: ...
    def definition(self, key: SourceDescriptorKey) -> SourceDescriptorDefinition | None: ...

# proof/normalizer.py
class SourceProofNormalizer:
    def __init__(self) -> None: ...
    def normalize(self, world_uid: EntityUid,
                  uses: tuple[SourceCaptureUsage, ...]) -> SourceDurableProof: ...

# proof/atomIndex.py
class SourceProofAtomIndex:
    def __init__(self) -> None: ...
    def enumerate(self, proof: SourceDurableProof) -> tuple[SourceCaptureUsage, ...]: ...

# proof/groupUnionBuilder.py
class SourceProofGroupUnionBuilder:
    def __init__(self, normalizer: SourceProofNormalizer,
                 atoms: SourceProofAtomIndex) -> None: ...
    def build(self, request: SourceProofGroupsInput) -> SourceProofGroupProjection: ...

# proof/selectionExtractor.py
class SourceProofSelectionExtractor:
    def __init__(self, atoms: SourceProofAtomIndex,
                 normalizer: SourceProofNormalizer) -> None: ...
    def extract(self, request: SourceProofSelectInput) -> SourceDurableProof: ...

# proof/groupMatcher.py
class SourceProofGroupMatcher:
    def __init__(self, union: SourceProofGroupUnionBuilder) -> None: ...
    def match(self, request: SourceProofGroupsVerifyInput) -> None | SourceFailure: ...
```

**Изменение прежнего draft normalizer:** request validation отделяется от преобразования. Методы normalize/build/extract вызываются только после успешных структурных и соответствующих semantic checks исходного request. Невыполнение prerequisites во внутреннем вызове — programming error, не успешная «починка» входа. Public operation не может пропустить checks; tests проверяют отсутствие вызова преобразования после отказа. Domain failure не теряется: его создаёт validation стадия с исходным root до преобразования. Это proposal API, не молчаливое изменение прежнего sheet.

**Atom representation без зеркального DTO:** элемент результата enumerate — existing SourceCaptureUsage с тем же full capture ref и ровно одной dependency (один object ref либо один collection ref; второй tuple пуст). Порядок — принятый canonical atom order спецификации; capture identity не теряется. Пустой proof даёт пустой tuple. Такой результат internal, не новый persisted/public proof; его нельзя выдавать за полный captured read set. Это выбор внутреннего представления на согласование; отдельный SourceAtom carrier не вводится.

SourceProofGroupProjection остаётся единственным ранее предложенным internal frozen value: `proof: SourceDurableProof`, `selections: tuple[SourceProofSelection, ...]`; без refs/admission. Group matcher сравнивает normalized expected union и соответствие selections, но не durable refs: exact closure сравнивает владелец verify_groups после IO. Ошибки matcher используют VERIFY_GROUPS и original expected group indices, не synthetic request.

## 2. Preconditions и зависимости проверки

| Algorithm | Обязательные проверки до вызова | Что не делает |
|---|---|---|
| normalize | Structural validation; world/descriptor/key; full capture identity conflicts и конфликт revisions внутри capture по всем uses | Не исправляет READ, не вызывает key adapter/projector и не доказывает existence |
| enumerate | Canonical persisted proof | Не нормализует вход и не читает body |
| build | Все исходные groups, включая cross-group capture/revision conflicts | Не обрывает aggregation на первом group, не выдаёт durable result |
| extract | Canonical proof, selection fingerprint/order/unique/bounds | Не проверяет bytes/holds и не выбирает latest |
| match | Корректные expected groups и предъявленные proof/selections, сохранён original root | Не заменяет closure validation |

| Checker-кандидат | Constructor dependencies | Единственная обязанность |
|---|---|---|
| SourceIdentityChecker | SourceDescriptorLookup + key-validation port | Identity соответствует owning descriptor/key constraints |
| SourceUsageConflictChecker | Нет IO/dependencies | Не допускает несовместимость в пределах одного capture, сохраняя historical refs разных captures |
| SourceProofCanonicalChecker | Fixed canonical schema | Проверяет persisted canonical ordering/unique form без исправления |
| SourceSelectionChecker | SourceProofAtomIndex + fixed canonical schema | Fingerprint и bounds selection |
| SourceCaptureMembershipChecker | SourceDescriptorLookup | Exact usage↔предъявленные capture/witness/collection mappings |

Key-validation port — внешняя нужда ядра; его exact accepted Terrain validator не превращает всю registry composition в готовую. Не использовать fake permissive port для production admission. Core-проверки, не требующие owning key validation, должны быть выделены в независимый срез, а не называться полной admission.

## 3. Незавершённый typed diagnostic API — собственная задача ядра

Checkers должны возвращать existing SourceFieldIssue/SourceLogicIssue, агрегируемые в SourceFailure. Однако поля paths привязаны к типу исходного request, а shared checker получает вложенное значение. Поэтому сигнатура `check(value) -> SourceFailure` недостаточна: она теряет root/location либо вынуждает дублировать алгоритм для пяти операций.

До кода выбрать и предъявить точный typed location-контракт на existing FieldRef/CheckedPath с сохранением original root/group/use index. Не вводить string paths, Any/dict context, зеркальный error DTO или mutable общий context. Не выдавать универсальный `SourceOperation` за dispatch-флаг. SourceOperation допустим только как diagnostic context для одного и того же check.

Это не внешний интеграционный долг. Пока нет точной формы root/location и отрицательных tests, полные signatures checkers и public constructors не объявляются готовыми. Request-specific aggregation принадлежит отдельной стадии проверки конкретного request, а сами инварианты имеют одного владельца из §2.

## 4. Dependency graph без циклов

```text
immutable descriptor definitions → descriptor lookup → identity/membership checks
fixed canonical schema → canonical checker / atom index / normalizer
atom index + normalizer → group union builder / selection extractor
group union builder → group matcher
request-specific checks → operation owner → pure algorithm → closure integration
```

Checker не вызывает operation owner; normalizer не вызывает validator или union builder; union builder не вызывает group matcher; ни один internal component не вызывает public pipeline. Closure integration не входит в pure algorithm API и не заменяется фиктивными refs. Импорты Source dataModel → application запрещены.

## 5. Revision/mutation/recovery/prune: reuse inventory

Проверен existing `source-pregame-revision-staging-design.md`; это источник кандидатов, не evidence реализации. Дублировать его типы под новыми именами запрещено.

| Потребность ядра | Уже описанный кандидат | Следующая собственная задача, не интеграция |
|---|---|---|
| Вход registry mutation | SourceRegistryMutationInput; SourceRegistryCreate/Update/Delete; SourceCollectionMutation (§P1.1, P2.10 execution_version) | Свести единственный актуальный roster и local invariants; не расширять на все source categories |
| Committed outcome | SourceMutationApplied (§P1), SourceMutationRefused proposal | Разделить provisional internal result и committed public outcome без второго receipt; проверить точные ошибки |
| Revision transition | Existing SourceRevision/SourceVersionRef; P1.2/P1.3 описывают seq и label-only policy | Exact pure input/result classifier/builder; не подменять semantic hash content_hash артефакта |
| Recovery | P3.3–P3.5: terminal replay, unknown, preflight rejection и rollback carrier | Единая public error map с различением отказа до terminal, committed refusal и unknown; не создавать второй lifecycle |
| Prune policy | Основной план: explicit prune/history/root/holders | Exact facts/decision POJO для Source policy; не писать GC и не объявлять отсутствие hold доказанным без authoritative binding |

В частности, `SourceMutationApplied` по смыслу означает committed результат: future transition builder не должен возвращать этот тип до commit. Ошибки MUTATION_ID_CONFLICT/MEMBERSHIP_MISMATCH/REVISION_PRUNED/REVISION_NOT_FOUND из staging proposal не входят автоматически в принятый sourceErrors roster. Новые codes требуют собственной дельты, не применения сходных proof codes вместо них.

Integration debts INT-WRITER/INT-ARTIFACTS остаются в основном плане; из этого inventory не следует разрешение запускать их согласование до завершения ядра. Наличие неизвестной интеграции не снимает обязанность Source определить свои типы и различить смыслы outcomes.

## 6. Результат этапа

Предъявлены exact кандидаты шести pure API, constructor graph, preconditions и переиспользование имеющихся mutation-предложений. Не закрыты typed checker context и собственные mutation/recovery/prune value contracts. Следующий конкретный шаг ядра — typed diagnostic root/location: он нужен всем checks и не зависит от будущего Terrain/Pack/DAG. Затем консолидировать Source revision/mutation outcomes. Полная архитектура, независимая приёмка и код не заявляются.
