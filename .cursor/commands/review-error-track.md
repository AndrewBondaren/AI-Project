---
name: review-error-track
description: Сквозное code review текущего трека ошибок ERROR-CONTRACTS-1 — J3a/b/c, EC-11 и граница J4.
---

Проведи независимое code review и тестирование трека ошибок по [плану](../plans/error-contracts-1.md) и [правилам ревью](../rules/review-split.mdc). Зафиксируй HEAD, целевую ревизию/диапазон, если переданы, и релевантные рабочие изменения. Учитывай реализацию, уже вошедшую в master. Код, план и статусы не менять. Проверка выбора tier от города до здания выполняется отдельно командой `/review-cascade-source`.

## Что проверить

1. Проследи реальные пути J3a/b/c через публичные входы и текущие модули `jsonValidation/resolution/`. Проверь, что после разделения `resolve.py` callers используют тот же контракт. Проверь missing/null/invalid, PATCH, неизвестную REF-W, чужую колонку multi_column, alias, ключ словаря, похожий на служебную метку Pydantic. Сверяй тип причины, машинный код и полный wire loc в исключении, preview и HTTP 422.
2. Для EC-11 проверь на одном контексте разрешённую деградацию региона и затем валидную либо ошибочную ссылку. Сверь отдельно `ctx.errors`, `report.diagnostics`, количество warning и итог операции. Убедись, что переключение только `collect_only` сохраняет значение и допуск к записи.
3. Для J4 пройди ранний отказ preflight, агрегацию большого числа невалидных строк, remap и повторную проверку целевого мира. Проверь отсутствие записи в preview (включая самостоятельный импорт), фактическое состояние SQLite после rollback, один warning на дефект исходной строки и продолжение импорта с подписанным token.
4. Сверь границы семейств: полевой/доменный отказ, техническая ошибка и отмена проходят по предназначенным путям; инфраструктурный сбой не превращается в 422. Retry/gate/status DAG остаются за пределами JSON-отчёта. Отличай регрессию этого среза от ранее зарегистрированного дефекта другого домена.

## Тесты

Из корня репозитория в PowerShell:

```powershell
Push-Location backend
try {
    $env:PYTHONPATH = 'tests'
    ../.venv/Scripts/python.exe -m unittest discover -s tests/errorContracts
    $contractsExit = $LASTEXITCODE
    ../.venv/Scripts/python.exe -m unittest test_runtime_world_edit_policy test_policy_field_migration test_region_identity test_declared_region_edit test_import_validation_policy test_world_column_write test_library_packs_4d
    if ($contractsExit -ne 0 -or $LASTEXITCODE -ne 0) { throw 'Error track tests failed' }
} finally { Pop-Location }
```

## Результат

Сначала находки по серьёзности: файл и строка, минимальный вход, ожидаемый и фактический исход, последствия для клиента или записи. Затем дай вердикт отдельно по J3a, J3b, J3c, EC-11 и J4. Приведи фактическое число запущенных тестов, сбои и непроверенные границы. Для замечания, которое тестовый набор не обнаруживает, приложи отдельное воспроизведение.
