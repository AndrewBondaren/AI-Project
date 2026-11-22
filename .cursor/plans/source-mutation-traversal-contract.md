# Source mutation — structural traversal

2026-11-22. Собственный проект АР-2, без runtime изменений и без нового публичного DTO. Основание — source-core-mutation-contract.md §1/6 и принятый принцип proof traversal: immutable facts, structural checks отдельно от semantic checks. Не разрешает локальный implementation-срез. Полная архитектурная приёмка сохраняется.

## 1. Размещение и единственная ответственность

Private функции: `backend/app/application/worldData/sourceVersioning/mutation/validation/traversal.py`. Каждая извлекает поля одного record или элементы одного контейнера; возвращает структурно пригодные facts и SourceFieldIssue. Не создаёт SourceFailure, не назначает SourceOperation, не вызывает semantic checker, builder, projector или storage.

Root boundary допускает только SourceRegistryMutationInput и не выполняет whole-tree model_validate, который прервал бы сбор независимых ошибок. Unknown root/extra без представимого пути — existing structural отказ без fake path. Вложенный wrong type адресуется исходным containing path. Forged/model_construct record не считается валидным лишь по isinstance.

Общие rules envelope/scalar/CheckedPath и existing inspect_registry_identity/inspect_collection_identity/inspect_object_ref/inspect_revision переиспользуются из Source traversal проекта. Не создавать их mutation-копии. Размещение shared leaf implementation пока сохраняется `proof/validation/requests/traversal.py`; внутренний импорт не даёт mutation права вызвать public proof operation. Возможный перенос shared файла не нужен для этого контракта.

## 2. Exact функции

RootT ограничен BaseModel. Запись `inspect_x(value: T) → R` в таблице разворачивается в `inspect_x[RootT: BaseModel](value: T, *, path: CheckedPath[RootT, T]) -> R`. Каждый последний элемент результата — `tuple[SourceFieldIssue, ...]`. Модельный slot означает только доступность envelope исходного экземпляра для дочернего обхода, не semantic validity. None в обычном slot означает missing/invalid и сопровождается issue.

| Функция / T | Exact R | Что извлекается |
|---|---|---|
| inspect_mutation / SourceRegistryMutationInput | `tuple[EntityUid | None, EntityUid | None, int | None, tuple[SourceRegistryChange, ...] | None, SourceCollectionMutation | None, tuple[SourceFieldIssue, ...]]` | operation_id, world_uid, execution_version, changes container, membership envelope; сохраняет доступные соседние поля |
| inspect_changes / tuple[SourceRegistryChange, ...] | `tuple[tuple[tuple[int, SourceRegistryChange, CheckedPath[RootT, SourceRegistryChange]], ...], tuple[SourceFieldIssue, ...]]` | Исходный индекс, объявленный concrete variant и его path; не допускает dict вместо модели |
| inspect_create / SourceRegistryCreate | `tuple[RegistryMemberId | None, ArtifactRef | None, tuple[SourceFieldIssue, ...]]` | identity/body независимо; kind проверяется по Literal annotation |
| inspect_update / SourceRegistryUpdate | `tuple[SourceVersionRef | None, ArtifactRef | None, tuple[SourceFieldIssue, ...]]` | expected/body независимо; kind проверяется по Literal annotation |
| inspect_delete / SourceRegistryDelete | `tuple[SourceVersionRef | None, tuple[SourceFieldIssue, ...]]` | expected; kind проверяется по Literal annotation |
| inspect_membership / SourceCollectionMutation | `tuple[SourceCollectionId | None, bool, SourceRevision | None, ArtifactRef | None, tuple[SourceFieldIssue, ...]]` | collection_id, пригодность nullable поля expected_revision, его значение/envelope, body |

Nullable expected_revision: `(True, None)` — допустимое явное отсутствие, `(False, None)` — отсутствующее обязательное поле либо неверная форма с issue, `(True, revision)` — доступный revision envelope для inspect_revision. Bool относится только к structural доступности nullable поля, не authority/existence/trust. Если дочерний revision непригоден, request checker не считает expected допустимым после одного envelope.

Конкретные варианты SourceRegistryChange допускаются через declared discriminated union; kind не восстанавливается по имени класса. Для типа record с повреждённым kind создаётся issue на kind и продолжается обход известных соседних полей. Неизвестный variant не преобразуется в CREATE. Paths variant/item строятся shared typed operations; строки путей не парсятся.

Scalar schema берётся из owning FieldInfo/annotations: strict execution_version, identity tokens, enums, nullable обязательность не задаются вторым набором literals. Пустой changes tuple проходит extraction как исходный tuple, а nonempty constraint проверяется один раз по owning field schema; наличие issue запрещает success. Повреждённый container возвращает None, а не пустой tuple. Original indices фактов не уплотняются.

ArtifactRef validation следует existing Source traversal boundary: owning TypeAdapter(ArtifactRef) strict проверяет исходное значение после envelope. Только ValidationError этой точной границы переводится в INVALID_SHAPE на body path. Нет анализа текста ValueError, format registration, existence или hash IO. SourceRevision и identities проходят общие leaf-функции; local predicates вызываются semantic стадией, не inspect-функцией.

## 3. Trace request checker

1. Root boundary → inspect_mutation. Operation id/world/version проверяются независимо; отсутствие пригодных changes не отменяет membership traversal.
2. inspect_changes сохраняет исходные позиции. По concrete variant вызывается ровно одна inspect_create/update/delete; nested identity/ref/revision проходят общие leaf functions. Это выбор структуры union внутри одного алгоритма проверки, не выбор публичной операции.
3. inspect_membership проверяет поля независимо; nullable distinction сохраняется до semantic стадии. Для каждого доступного ArtifactRef выполняется owning value validation.
4. SourceRegistryMutationRequestChecker использует накопленные facts: shared world/identity/key rules, variant constraints, duplicate/order predicates, membership descriptor compatibility. Сам checker не повторяет чтение полей request ради поиска paths.
5. Дубликаты/порядок проверяются по пригодным identities с исходными индексами. `_mutationValueRules` должны принимать извлечённые identity facts для application пути; запрещено реконструировать SourceRegistryChange из пригодных полей. Exact общий predicate contract уточнён ниже.
6. Request-local ValidatorAggregationHelper собирает issues; SourceFailure(operation=APPLY_MUTATION) возвращается только при непустом результате, иначе None. Любой отказ блокирует preparation. Expected-state/phase/retention проверки остаются отдельными от request validation.

## 4. Единые mutation predicates без repaired records

Уточнение к source-core-mutation-contract.md §3: `change_identity(change)` применяется только к полностью допустимому concrete change, в частности POJO validation. Для malformed application branches общий algorithm получает identities, а не восстановленные changes:

```python
# dataModel/sourceVersioning/_mutationValueRules.py
def duplicate_identity_positions(
    identities: tuple[RegistryMemberId, ...],
) -> tuple[int, ...]: ...

def invalid_identity_order_positions(
    identities: tuple[RegistryMemberId, ...],
) -> tuple[int, ...]: ...
```

Возвращаемые позиции относятся к переданному tuple пригодных identities; request checker отображает их через сохранённые original indices/paths. POJO batch_shape извлекает identities единственным change_identity и вызывает те же predicates. Ранее предложенные duplicate_change_positions/invalid_change_order_positions заменены этими двумя функциями, не реализуются параллельно. Оба algorithms pure: нет repair/sort/IO, canonical identity key берётся из единственного Source canonical правила.

## 5. Проверки ответственности

- UPDATE с повреждённой revision сохраняет пригодную identity для descriptor/duplicate проверки и проверяет независимый body.
- Из `(invalid, CREATE A, DELETE A)` получается shape issue позиции 0 и duplicate по исходной позиции 2; новый request не строится.
- Wrong discriminator не подменяется, но пригодный body получает свою независимую проверку.
- Missing expected_revision, явный None и valid revision различаются; nullable не получает default.
- Повреждённые changes не скрывают ошибку membership.world; invalid membership не отменяет соседние changes.
- Traversal не вызывает semantic checkers; checker не повторяет field traversal; invalid request не запускает preparation.
- Type/path mismatch во внутреннем вызове — programming failure, не INVALID_IDENTITY пользователя.
- Concurrent requests не разделяют facts/diagnostics; все возвращаемые коллекции immutable.

Это exact проект функций и trace, а не независимая приёмка/тестовый отчёт. Diagnostic mapping — mutation-contract §6; mutation public/error delta, state admission и foreign bindings остаются отдельными пунктами целой архитектуры.
