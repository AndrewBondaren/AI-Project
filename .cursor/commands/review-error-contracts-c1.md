---
name: review-error-contracts-c1
description: >-
  Ревью реализации C1 (общее ядро ошибок) плана error-contracts-1: dataModel/fields
  (FieldRef, bind_field, CheckedPath, ValidatedFieldPath), generic FieldPathError[CodeT],
  ValidatorAggregationHelper[IssueT], пин Pydantic, typing gate. Code review или
  architecture review — раздельно. Код не пишет. Новый чат: /review-error-contracts-c1.
---

# Ревью: ERROR-CONTRACTS-1 C1 — общее ядро

Это **явная просьба о ревью** (`review-split.mdc`). Код не писать, не коммитить, не стартовать backend.

## Вид ревью

Текст после команды: `code` или `architecture`. Если не указан — **спросить одним вопросом** (code / architecture / оба последовательно: сначала code). Один запрос — один вид, формат ответа и оси — строго по [`.cursor/rules/review-split.mdc`](../rules/review-split.mdc).

## Прочитать до ревью

1. [`.cursor/plans/error-contracts-1.md`](../plans/error-contracts-1.md):
   - §0.1.1 — целевая карта ядра (A0 ACCEPTED), §0.1.2 — направление импортов;
   - §0.1.3–0.1.4 — impact ledger и полный A0 register, находки A0-F1…F7;
   - §3.9 — C0-1…C0-8 (ACCEPTED): представление ошибки, поля ядра, `ValidatedFieldPath`, `CheckedPath`, collector, Pydantic, typing gate, маппинг `errors()`;
   - §6 — порядок C1 → D2 и запрет промежуточного сломанного master.
2. Правила: [`folder-composition.mdc`](../rules/folder-composition.mdc), [`class-size-limit.mdc`](../rules/class-size-limit.mdc), [`layer-boundaries.mdc`](../rules/layer-boundaries.mdc), [`contract-creation.mdc`](../rules/contract-creation.mdc), [`cascade-pojo.mdc`](../rules/cascade-pojo.mdc), [`legacy-folder.mdc`](../rules/legacy-folder.mdc).

Контракт — план §3.9, а не догадки ревьюера. Расхождение план ↔ код: указать источник (раздел) и сценарий; без источника — гипотеза.

## Объект ревью (срез C1)

| Файл | Что |
|---|---|
| `backend/app/dataModel/fields/fieldRef.py` | `FieldRef` — перенос тем же объектом из `cascadeSpec.py` (A0-F4) |
| `backend/app/dataModel/fields/fieldBinding.py` | `BoundField`, `_FieldProbe`, `bind_field` — перенос из `cascadeGraph.py` |
| `backend/app/dataModel/fields/validatedFieldPath.py` | `ModelIdentity`, сегменты field/index/key/variant, `ValidatedFieldPath.projection` (C0-3) |
| `backend/app/dataModel/fields/checkedPath.py` | `CheckedPath[RootT, CurrentT]`, overloads `item`/`key`, `present`, `variant`, `freeze`, `from_pydantic_loc` (C0-4) |
| `backend/app/dataModel/validation/diagnostics/fieldPathError.py` | `FieldPathError(BaseModel, Generic[CodeT])`, запрет голого/параметризованного generic (C0-1/C0-2) |
| `backend/app/dataModel/validation/diagnostics/validatorAggregationHelper.py` | `ValidatorAggregationHelper[IssueT]`, `IssueAdmissionError` (C0-5); старый `app/core/validatorAggregationHelper.py` удалён |
| `backend/app/dataModel/cascade/cascadeSpec.py`, `cascadeGraph.py` | определения удалены, импорт из `dataModel.fields` без re-export |
| ~47 файлов `backend/app`, `backend/tests` | механическая замена импортов `FieldRef`/`bind_field`/`BoundField` |
| `backend/requirements.txt` | `pydantic==2.14.2` (C0-6) |
| `pyrightconfig.cascade.json` | include `dataModel/fields` (A0-F7) |
| `backend/tests/errorContracts/test_core.py`, `test_typing.py` | runtime-контракты и typing gate |
| `backend/tests/typing/errorContracts/` | `models.py`, `valid.py`, `invalid.py` (`# EXPECT:`), `pyrightconfig.{valid,invalid}.json` |

Получить diff: `git diff HEAD` / `git status` (если C1 не закоммичен) либо коммит, который назовёт мастер.

## Известное — не дефект среза C1

- Старые конструкторы `FieldPathError(path=..., message=..., code="...")` в ~130 файлах доменов падают (`TypeError` позиционных аргументов / `ValidationError`): это **запланированная** миграция доменов D0/D1/D2 по списку A0 (Planning → jsonValidation/worldBundle → Snapshot builder → Water Input/hydrology → `ReferenceIssueContext`). Не перечислять их поштучно; допустимо одной строкой оценить, достаточно ли A0 register покрывает фактические падения.
- `ReferenceIssueReason`/`ReferenceIssueContext` пока лежат в `fieldPathError.py` — их перенос в доменный subclass решается в D1 домена.
- Persisted-записи (manifests 105–109, 20016/20137–20139, `_SHAPE_LOCK`) не обновлены: A0-F1 — пересоздание данных, правка в срезе домена. Legacy-декодер v1 **не нужен** (решение мастера).
- Отклонение от C0-3: `VariantSegment` хранит только `branch: ModelIdentity`; владелец задаётся предыдущим `FieldSegment`. Оценить, а не считать автоматически ошибкой.
- `tests/typing/errorContracts/` — 6 файлов (WARN по folder-composition уже выдан).

## Что проверить обязательно

**Code review:**
- `bind_field`/`FieldRef`/`BoundField` — один объект: `CascadeNode` наследует извлечённый `BoundField`, `isinstance` в `policyReferences.py`/`policyIdentity.py`/`cascadeGraph.py` работает; ни одного дубликата/alias (`rg "class FieldRef|class BoundField|def bind_field" backend`).
- `CheckedPath`: инвариантность `CurrentT`, nullable (`present`), fixed-tuple vs `tuple[E, ...]`, `Annotated`/wire-обёртки (`unwrap_wire_type`), `variant` по runtime-членству, `from_pydantic_loc` на union/nullable/неизвестном `loc` → `None`.
- `FieldPathError`: strict/frozen/forbid/revalidate; чужой enum и строка в `code` отклоняются; `model_copy(update=…)` ловится strict-carrier'ом.
- Collector: допуск по точному `type`, `validate_immutable`, неизменяемый snapshot, пустой admitted → ошибка.
- Line endings: в diff нет переписанных целиком CRLF-файлов (`git diff --numstat | sort -rn | head`).
- Тесты реально проверяют контракт (негативные случаи, `# EXPECT:` строки совпадают с правилами pyright).

**Architecture review:**
- `dataModel/fields` нейтрален: не импортирует Cascade, application, доменные коды (C0, §0.1.2).
- Ядро без доменных полей (`schema_id`, `reference`, `runtime_context`) и без центральной таблицы кодов (C0-2, C0-8, §0.1.1).
- Нет второго API ошибок, `app/core/errorContracts`, `app/dataModel/errors`, bridge/re-export (§0.1.1, §6).
- Размещение `ValidatorAggregationHelper` в `validation/diagnostics`, удаление старого `core/` без legacy-хвоста (`legacy-folder.mdc`).
- Typing gate переиспользует существующий toolchain (`scripts/check-cascade-types.cjs`, схема `tests/typing/snapshotCore`), без копии раннера (C0-7).
- Folder composition и class size новых модулей.

## Команды проверки

```bash
cd backend && PYTHONPATH=. python -m unittest tests.errorContracts.test_core
cd backend && PYTHONPATH=. python -m unittest tests.errorContracts.test_typing   # нужен node + node_modules/pyright
npx pyright -p backend/tests/typing/errorContracts/pyrightconfig.valid.json     # 0 ошибок
npx pyright -p backend/tests/typing/errorContracts/pyrightconfig.invalid.json   # ровно строки # EXPECT:
npm run typecheck:cascade                                                       # регрессия против baseline
```

Python — 3.14 (как в ТЗ проекта). Полный `unittest discover` сравнивать с baseline по списку `ERROR:`/`FAIL:`, а не по числу: доменные падения ожидаемы (см. выше).

## Результат

Ответ в формате `review-split.mdc` для выбранного вида. Найденный техдолг — только в существующие реестры (`docs/tz_*.md` / план), отдельный документ ревью не создавать.
