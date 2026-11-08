# TL-B · PROJECT

8 ноября 2026. В обеих World-подготовках наблюдение принадлежит общему вызову `projector.project(request)` в [candidate.py](../../backend/app/application/worldData/timeSettings/preparation/shared/candidate.py). При успехе Time молчит. Каждый из пяти типизированных отказов порождает один WARNING с кодом из матрицы. Затем World возвращает прежний бюджетный отказ, переносит issues из CalendarInvalid или возвращает исходную ошибку поля capture. CalendarTimeOverflow проверен подстановкой на границе контракта.

Fault и cancellation порождают по одной попытке записи с источником входной проекции. Bare raise сохраняет объект исключения. При сбое emitter, включая CancelledError, caller получает прежний результат либо исходное исключение проектора. Ошибка validator после проекции не создаёт Time fault.

## Сравнение по §6.3

Рабочее дерево уже содержало привязку и тесты. Для воспроизводимого сравнения в тестовом процессе использована версия candidate.py из HEAD `0d4260b3`. Семь тестов поведения прошли. При прогоне полного набора на HEAD три теста наблюдения обнаружили отсутствие ожидаемых событий или попыток emit. На рабочей версии все десять [тестов привязки](../../backend/tests/time/test_time_logging_bindings.py) прошли.

| Проверка из backend | Результат |
| --- | --- |
| time_core, time_logging_contracts, time_operation_log | 36 прошли, включая асинхронный pinned read при запуске вне песочницы |
| time_logging_bindings | 10 прошли |
| test_logging_routes, test_generation_logging с локальным TEMP/TMP | 28 прошли |
| Pyright по production-области §6.3 | 0 ошибок |
| Та же область с tests/time | 320 ошибок, как в исходной сверке §6.3. В новом файле диагностик нет |

Production read, apply и branch остаются за SN-TIME-READ, SN-TIME-APPLY и SN-TIME-BRANCH. Полная runtime-приёмка §47.3 остаётся отдельным этапом.
