# Unknown wire keys — contour split в jsonValidation

> Карта межплановых зависимостей и критический путь:
> [`plan-dependency-graph.md`](plan-dependency-graph.md) — этот план
> независимый трек, пересечений с pack-моделью нет.

Целевое поведение для неизвестных wire-ключей (поле присутствует на
wire, отсутствует в модели) — общий двухконтурный контракт, уже
зафиксированный в `tz_template_library_packs.md` §0:

- **validation/импорт** — ошибка (`FieldPathError`, `UNKNOWN_FIELD`),
  собирается вместе со всеми остальными ошибками полей за один проход;
- **runtime** — `WarningError`-лог через sink `jsonValidation/resolve`,
  ключ отбрасывается, resolve продолжается.

Детект — обязанность слоя resolve (diff wire-ключей и полей модели),
единый для всех wire-моделей; `extra="forbid"`/`"ignore"` конфиг модели
поведение не определяет.

**Текущее состояние:** `resolve_model` → `Model.model_validate`;
`extra="ignore"` (дефолт большинства POJO) молча выкидывает ключ на обоих
контурах без WarningError; `extra="forbid"` (~25 моделей) фейлит оба
контура через `ValidationError` типа `extra_forbidden`. Diff wire vs
resolved уже вычисляется в `_log_resolve_transform` на INFO — детект
существует как побочный эффект логирования.

**Scope:** модели, которые resolve валидирует напрямую
(`resolve_model`, `resolve_root_list`, `resolve_root_dict`,
`resolve_patch`), плюс **один уровень** внутрь root-контейнеров —
строки `RootModel[list[Entry]]` и значения `RootModel[dict[str, Entry]]`
diff'ятся против их `Entry` (для dict — только значения; ключи верхнего
уровня — N+1 identity, не unknown). Более глубокие вложенные dict'ы
валидируются Pydantic внутри родительской модели — их unknown-ключи
покрываются там, где домен резолвит вложенность отдельным
`resolve_model` (пример: rooms/levels в `structureGeneratorService`).
Глубокий wire-vs-schema обход ниже уровня строки реестра — вне scope.

## Шаги

### Шаг 1 — ТЗ: секция контракта в tz_json_validation ✅ DONE

- **Цель:** контракт unknown-ключей живёт в доменном ТЗ слоя, а не только
  в packs-документе.
- **ТЗ:** `docs/tz_json_validation.md` — новый подраздел у «Field policy»
  / «Normalize vs reject» (unknown wire keys: два контура, агрегация,
  resolve-детект, `extra` модели не определяет поведение).
- **Файлы:** `docs/tz_json_validation.md`; ссылка из
  `tz_template_library_packs.md` §0 на новый раздел.
- **Проверка:** сверка с §0 packs-ТЗ — идентичная формулировка контуров.
- **Done:** раздел согласован.

### Шаг 2 — Детект unknown-ключей в resolve

- **Цель:** единый механизм детекта + контурная реакция в
  `resolve_model` (включая root-варианты и `resolve_patch`).
- **ТЗ:** `tz_json_validation.md` (раздел шага 1);
  `tz_template_library_packs.md` §0.
- **Файлы:** `backend/app/application/jsonValidation/resolve.py`;
  `backend/tests/test_json_validation_resolve.py` (новый).
- **Контракт:**
  - `split_unknown_keys(model, data) -> (recognized_data, unknown_keys)`
    — recognized по `model_fields` с учётом `alias`/`validation_alias`
    (переиспользует `_wire_lookup_keys`); no-op на non-dict `raw` и
    `RootModel` — diff только плоских объектов;
  - порядок в `resolve_model`: сначала детект extras → запись факта
    (import: `FieldPathError` per key, `UNKNOWN_FIELD`; runtime:
    один WarningError-лог с моделью и списком ключей) → strip extras →
    `model_validate` остального тела → его ошибки добавляются в тот же
    проход (полный список за одну валидацию);
  - `extra="forbid"` модели extras не видят (уже сняты) — поведение
    одинаково на любой конфигурации `extra`;
  - runtime-запись факта — отдельный warn-only путь (`logger.warning`,
    одна строка с моделью и списком ключей), **не** `reject_unresolved`:
    он `ctx.errors.extend` + raise `UnresolvedModelError`;
  - `validate_only` — тот же IMPORT-контур (`FieldPathError`, без
    записи); per-issue warning глушит существующий `reject_unresolved`,
    отдельной ветки не требуется;
  - `resolve_patch` — тот же split перед `_patch_validator`:
    unknown-ключи не попадают в `supplied`, контурная реакция по
    `ctx.mode` caller'а;
  - `resolve_root_list`/`resolve_root_dict` — дополнительно один
    уровень внутрь: entry-модель из `model_fields["root"].annotation`
    (`get_origin`/`get_args`), каждая строка-dict diff'ится против неё;
    для `dict[str, Entry]` diff идёт по значениям; path issue =
    `path_prefix + (index|key, field)`.
- **Проверка (cwd=backend):**
  `python -m unittest tests.test_json_validation_resolve` —
  runtime: warn + drop + resolve проходит; import: UNKNOWN_FIELD в
  отчёте вместе с остальными ошибками полей; alias-ключи не считаются
  unknown; forbid-модель в runtime не падает; unknown-ключ в patch и
  в строке реестра — та же контурная реакция; ключи dict-реестра
  не считаются unknown.
- **Done:** контурная реакция едина; `extra` модели не влияет на
  поведение.

### Шаг 3 — Аудит call sites: runtime warn не должен становиться fail

- **Цель:** проверить, что callers, эскалирующие `UnresolvedModelError` в
  `GenerationError`/reject, не ломают контракт: unknown-ключ в runtime
  — WarningError + продолжение, не отказ.
- **ТЗ:** `tz_json_validation.md` (раздел шага 1); `tz_logging.md`.
- **Файлы:** `structureGeneratorService.py`, `worldSliceMerge.py`,
  `loadReliefTemplatesForWorld.py`, прочие `reject_unresolved`/catch
  `UnresolvedModelError`.
- **Контракт:** unknown-ключи не доходят до `reject_unresolved` в
  runtime (снимаются до валидации) — callers не меняются; шаг только
  подтверждает это по коду и тестами.
- **Проверка:** тест/ручная трассировка: шаблон с лишним ключом →
  generation проходит с WarningError в логе; импорт того же тела →
  422/отчёт с `UNKNOWN_FIELD`.
- **Done:** ни один runtime caller не превращает unknown-ключ в отказ.

## Вне scope

- Рекурсивный детект unknown-ключей ниже уровня строки реестра /
  внутри полей вложенных моделей без отдельного `resolve_model`
  (см. Scope).
- Миграция моделей с `forbid` → `ignore` — не требуется: поведение
  нормализовано слоем resolve, конфиг остаётся как есть.
- Агрегация ошибок между независимыми секциями bundle — уже есть
  (`ctx.errors` в `_prepare_bundle`), не меняется.
