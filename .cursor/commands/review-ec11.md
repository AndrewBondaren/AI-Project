---
name: review-ec11
description: Ревью реализации EC-11 для JSON/import и World Bundle, включая R-J4-1. Режимы code и architecture.
---

# Ревью EC-11

Команда выполняет ревью без правок и коммитов. Аргумент `code` или `architecture` задаёт вид ревью по [review-split.mdc](../rules/review-split.mdc). Если режим не указан, уточни его. Для запроса обоих режимов выдай два отдельных результата, сначала code.

Основание — [план ERROR-CONTRACTS-1](../plans/error-contracts-1.md), разделы «Политика поля POJO и реакция операции», «План реализации EC-11 для JSON/import и World Bundle» и R-J4-1. Реализация вошла в смешанный коммит `70f1d8d5`. Начни с `git show --stat 70f1d8d5`, изучи его diff по файлам EC-11 и проверь актуальное дерево на последующие изменения в этих файлах. Если пользователь указал диапазон, используй его. Исключи соседние изменения spatial distribution и чужие незакоммиченные файлы.

## Code

- Проследи путь от `declared_region_identity` через `ResolveReport` до `normalize_world`, preflight и допуска к записи. В одном контексте после разрешённой деградации ссылка `water` проходит, `absent` даёт именно `REF_W_UNKNOWN`. Проверь полный wire loc и оба канала отчёта.
- Сравни preview, обычный импорт, прямой runtime и тихий сбор. Проверь исход, UID, число предупреждений и состояние SQLite. Убедись, что missing, null, invalid и частичный PATCH сохраняют существующую семантику POJO.
- Проследи R-J4-1 от preflight до записи региона после remap. Один дефект исходной строки должен дать одно предупреждение на операцию; разные строки и независимые запросы не должны теряться. Проверь канонический префикс `world` для bundle, самостоятельный world-ввод, повторную валидацию целевого мира и сохранение UID/timestamp при continuation.
- Проверь, что блокирующая ошибка, отмена и сбой хранилища корректно проходят границу транзакции. Различай результаты до записи и после rollback.

## Architecture

- Установи, где POJO определяет валидность, где домен разрешает продолжение, где отчёт отвечает за доставку и где операция решает допуск к записи. Проверь, что `collect_only` меняет только доставку.
- Проверь границы F01–F09: JSON/import не назначает DAG retry/gate/status, не преобразует F05/F06 в полевую диагностику и не переопределяет disposition Planning/placement. Проверь совместимость существующих читателей `ctx.errors`.

## Проверки и результат

Из корня репозитория в PowerShell:

```powershell
Push-Location backend
try {
    $env:PYTHONPATH = 'tests'
    ../.venv/Scripts/python.exe -m unittest discover -s tests/errorContracts
    if ($LASTEXITCODE -ne 0) { throw 'errorContracts failed' }
    ../.venv/Scripts/python.exe -m unittest test_region_identity test_declared_region_edit test_import_validation_policy test_runtime_world_edit_policy test_library_packs_4d
    if ($LASTEXITCODE -ne 0) { throw 'EC-11 integration tests failed' }
} finally { Pop-Location }
```

Сначала перечисли находки по серьёзности, с файлом и строкой, сценарием, ожидаемым и фактическим результатом. Отдельно укажи проверенную ревизию, фактически запущенные тесты и непроверенные границы. Утверждение DONE в плане проверяй по коду и воспроизведению.
