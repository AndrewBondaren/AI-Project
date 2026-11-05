---
name: review-error-track-types
description: Code review ERROR-CONTRACTS-1 — воспроизведение багов, тестирование и статическая проверка Pyright.
---

Проведи read-only code review по [правилам проекта](../rules/review-split.mdc). По умолчанию проверь текущую реализацию трека JSON/import (J3a/b/c, EC-11, J4), включая незакоммиченные исправления R-J3c-6 и R-J3b-6, если они ещё не вошли в HEAD. Аргумент после команды может сузить срез или задать ревизии. Зафиксируй фактические HEAD, базу сравнения и релевантный diff; рабочие файлы, статусы плана и git index не менять.

### Поведение

Выполни проверки и **оба набора unittest** из [review-error-track](review-error-track.md). По [плану](../plans/error-contracts-1.md) проследи сценарии от входа до наблюдаемого результата. Для PATCH сопоставь с полной моделью при конфликте alias и Python-имени, AliasChoices, пропущенном поле и extra-ключе. Для union проверь служебную метку ветки, реальный одноимённый ключ и вложенный контейнер. Сверь число причин, wire loc и код в preview/422. В общей цепочке проверь блокирующий и неблокирующий каналы, границу записи и rollback. Ищи ошибки также за пределами уже известных воспроизведений.

### Типизация

Из корня репозитория запусти установленный проектный Pyright с настройками Python 3.14. Проверяй production-файлы напрямую: typing fixtures покрывают контракт ядра и не заменяют проверку его callers. Для другого явно заданного среза скорректируй список путей.

```powershell
$reviewPaths = @(
    'backend/app/application/jsonValidation'
    'backend/app/application/worldBundle/worldBundleService.py'
    'backend/app/application/worldBundle/worldCopyImport.py'
    'backend/app/application/worldData/masks/regionIdentity.py'
    'backend/app/application/worldData/registries/worldService.py'
    'backend/app/dataModel/validation'
    'backend/tests/errorContracts'
)
& ./node_modules/.bin/pyright.cmd --project backend/tests/typing/errorContracts/pyrightconfig.valid.json @reviewPaths
$reviewPyrightExit = $LASTEXITCODE
```

Сверь результаты позитивных и негативных typing fixtures через `test_typing.py` в уже запущенном `tests/errorContracts`. Ожидаемые ошибки negative fixture сверяются с размеченными строками. Проверяй конкретные diagnostics Pyright (путь, строка, правило), особенно optional/union, generic, тип исключения и возврат нормализованной модели. Для отличия регрессии от прежней ошибки используй ту же версию инструмента, конфиг и пути на проверяемой базе либо явно пометь происхождение как неустановленное. Не исправляй ошибки, не добавляй type ignores и не ослабляй конфиг во время ревью.

### Отчёт

Сначала баги по серьёзности: файл:строка, воспроизведение, ожидание, фактический исход и влияние. Затем отдельный вердикт по типизации: версия Pyright, область прогона, exit code, новые и прежние diagnostics, статус typing fixtures. Заверши фактическими результатами unittest и непроверенными границами. Выполняй независимые проверки даже при падении одного этапа.
