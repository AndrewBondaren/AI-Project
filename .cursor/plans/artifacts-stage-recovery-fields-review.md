# SR-05 — Fields/C0 review authorized-stage diagnostics

2026-11-26. Итог: **OPEN**, не приёмка SR-05 и не code-go. Scoped **PASS TARGET** для новой base-root цепочки и разделения field/relation diagnostics. Старый P2 verdict автоматически не переносится. Владелец исправления Artifacts; общая сверка — координатор `01a218a4-bfc5-7012-b18b-8ed986cc786d`, окончательное решение — пользователь.

Исследованы `artifacts-stage-recovery-owning-resolution.md` §3 и реестр `artifacts-stage-recovery-contract.md`; actual `backend/app/dataModel/fields/{checkedPath,fieldRef,fieldBinding,validatedFieldPath}.py`, `validation/diagnostics/{fieldPathError,validatorAggregationHelper}.py`, `artifacts/staging/{inputErrors,preparedArtifact,stageInput}.py`, `artifacts/{references,lifecycle/lease}.py`, `backend/app/encoding/canonicalCodec.py`. Основание C0: `error-contracts-1.md` §3.9 C0-1…5, C0-8/9. Это исследование кода; runtime/typing проверки не запускались.

## 1. Exact paths — PASS TARGET

Обозначения: A = `app.dataModel.artifacts.staging.stageInput.ArtifactAuthorizedStageInputBase`; P = `app.dataModel.artifacts.staging.preparedArtifact.PreparedArtifactBase`; R = `app.dataModel.artifacts.staging.preparedArtifact.ArtifactPrepareStageInputBase`.

| Причина | root | ordered owner.name | projection |
|---|---|---|---|
| Prepare content | R | R.content | `(content,)` |
| Stage content | A | A.prepared, P.content | `(prepared, content)` |
| Stage format | A | A.prepared | `(prepared,)` |
| Descriptor vs encoded content | A | A.prepared, P.descriptor | `(prepared, descriptor)` |

Каждый root/owner — `ModelIdentity.of` соответствующего named nongeneric nonabstract BaseModel. `CheckedPath.root(A)` → direct `FieldRef[A, P]` для prepared → direct `FieldRef[P, bytes | BaseModel]` для content либо `FieldRef[P, ArtifactRef]` для descriptor → freeze. Не использовать generic specialization как owner; не строить segments вручную. `CheckedPath.field` берёт owner из bound ref и аннотацию следующего шага из текущей модели. Первый owner равен root согласно `ValidatedFieldPath._starts_at_root_field`.

A — новый sibling diagnostic root, не наследник lease-содержащего ArtifactStageInputBase: иначе останется лишний обязательный lease. Generic authorized envelope наследует A и сужает prepared с existing instance-preserving validation. Root обозначает объявленную схему операции, не runtime specialization и не экземпляр запроса. Error связывается с вызовом контекстом переноса, без переписывания path wrapper-ом. `from_pydantic_loc(A, ...)` покрывает указанные терминальные пути, не произвольные внутренние поля C через bytes | BaseModel.

## 2. Reuse, ответственность и агрегация — PASS TARGET / OPEN деталей

- `ArtifactInputIssue` остаётся concrete `FieldPathError[ArtifactInputIssueCode]`; `ArtifactInputError` сохраняет existing nonempty tuple JsonFieldError/WireShapeIssue/ArtifactInputIssue. Новые field POJO/коды для прежних причин не нужны.
- `ArtifactStageBindingIssue(permit: StageAttemptPermit, descriptor: ArtifactRef)` обозначает только неравенство `permit.binding.artifact != descriptor`. Нет копирования полей lease/ref. Это logic relation двух operands одного запроса, не FieldPathError. `StageBindingConflict(requested, registered)` относится к durable registration, поэтому не дублирует эту причину. Зафиксировать predicate неравенства как инвариант issue; равные operands не образуют такую ошибку.
- `ArtifactStageInputFailure(fields: ArtifactInputError | None, binding: ArtifactStageBindingIssue | None)` — только aggregate. Обязателен validator «хотя бы одно не None»; пустой fields запрещён existing ArtifactInputError. Relation не повторяется дополнительным field issue за то же сравнение. Новые logic records/aggregate должны быть strict/frozen/extra-forbid/revalidate_instances=always, включая вложенные permit/binding records: одного frozen недостаточно для C0 admission и защиты от model_copy.
- `ValidatorAggregationHelper` собирает field issues в stable order content → format. После snapshot, а не преждевременного raise_if_any, добавляется отдельный relation result и выбрасывается один ArtifactStageInputRejected. Invalid content не отменяет format и relation, если их typed operands доступны. Если malformed descriptor/permit не даёт operands, зависимая relation пропускается; нельзя создавать вымышленные operands. Форматная ошибка и relation могут сосуществовать: они сравнивают разные отношения.
- Кодирование/descriptor recomputation зависит от content admission и выполняется только после успешного pure admission. Его mismatch отдаётся тем же aggregate, fields-only. Invalid content не запускает codec. Codec/infra exception не становится field mismatch. DTO не выполняют IO/authority checks, helper не выбирает DAG route, carrier только переносит error.

OPEN: owning §3 сначала перечисляет старый ArtifactInputRejected и затем промежуточный StageInputBindingRejected, хотя финальный абзац их заменяет. Нужна одна нормативная target таблица: prepare → ArtifactInputRejected; authorized stage input/descriptor failures → ArtifactStageInputRejected(ArtifactStageInputFailure); StageBindingRejected только requested-vs-registered; lease/admission/fault carriers отдельно. Промежуточный StageInputBindingRejected не вводить. Failure и relation issue имеют proposed module stageAttempt.py, carrier — application/artifacts/staging/stageAttemptErrors.py; это нужно закрепить явно вместе с конфигурацией и invariants.

## 3. Python / JSON / canonical — требования закрытия

**Python:** strict model_validate по конкретному ArtifactStageInputFailure и вложенным concrete types, в том числе existing instance revalidation. Проверить fields-only/binding-only/both; reject both None, empty issues, неверный enum/operand, подделанный model_copy, mutable values. Для field collector разрешены exact classes; конфигурация и validate_immutable проверяются `ValidatorAggregationHelper`. Новые request/permit схемы требуют отдельной проверки identity prepared/content; error equality не доказывает request identity.

**JSON:** full error `model_dump_json` → конкретный `ArtifactStageInputFailure.model_validate_json`, без Python strict-validation результата json.loads (tuple/list и enum имеют разные правила). Проверить точные concrete issue классы, enum, root/owners/segments, порядок и оба aggregate поля. Exception carrier сам не JSON POJO. Не заменять concrete issues аннотацией голого FieldPathError: его Python carrier mechanism не равен native JSON schema named concrete subclass. Обычный JSON decode ModelIdentity проверяет структуру, но НЕ manifest allowlist и НЕ полную семантику цепочки; не объявлять его cold identity resolver.

**Canonical:** `canonicalCodec.validate_decoded_identity` разрешает identity только при exact module/qualname named concrete owner в фактически используемом CanonicalSchemaManifest. Нужны A и P (R для prepare), независимо от наличия generic input registrations; регистрацию прежнего stage root нельзя считать регистрацией A. Общие Fields BINDINGS покрывают path records, но не referenced schema owners. В manifest error surface должны входить ArtifactStageInputFailure, ArtifactStageBindingIssue, StageAttemptPermit, StageBinding, existing ArtifactInputError, все реально поддерживаемые concrete issues/enums и полная транзитивная closure records/enums их operands (ArtifactRef, OperationLeaseRef и их зависимости), плюс path segment/identity records. Existing entries переиспользовать, IDs здесь не назначать. Python exception class не регистрируется как error POJO.

Проверить cold full-error round-trip в fresh manifest/composition без dynamic imports; отрицательные случаи missing A/P и неизвестного owner. Codec проверяет identity allowlist, но не доказывает весь owner chain: exact chain проверяется construction-time CheckedPath и regression assertions. Manifest schema bases используются для identity lookup, не для транспортной сериализации generic payload через bytes | BaseModel. Это не redesign Engine JSON identity.

## 4. Необходимая дельта и предел verdict

До scoped acceptance SR-05 нужны: единая error таблица вместо промежуточных carriers; explicit modules/config/invariants aggregate и relation; точное правило snapshot/aggregate-before-raise; actual manifest/composition closure и перечисленные positive/negative tests; inventory stage consumers с переносом полного нового Error без изменения paths и сохранением prepare API. Existing StageInputBase не fallback нового authorized route. Смена публичного input требует отдельного явного consumer cutover, который этот отзыв не принимает.

Новые diagnostic DTO не вводят pipeline, междоменные service calls или ветвление маршрута: локально три запрета DAG не нарушены. Порядок pure checks соответствует owning §3 и не меняет prepare/begin/stage/recover. Полный DAG, authority, storage, lifetime, UnknownCommitOutcome transport, весь class inventory SR-03/04/05 и общий порядок остаются в компетенции координатора; нехватка их доказательств исключает PASS полного плана. Реализаций и коммитов нет, owning/основные планы этим отзывом не изменены.
