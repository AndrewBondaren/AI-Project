# GEO · WATER_KIND_MISMATCH · отчёт D2

6 ноября 2026 года, рабочее дерево с HEAD `d01cf073`. До правки сверены локальные изменения и воспроизведён адресный тест из [принятого D1](geo-water-kind-mismatch-d1.md). Исходный caller — `materialize_water`, строка 75. При создании базового `FieldPathError` исполнение прерывалось до callback.

## Домен и публикация

[Producer](../../backend/app/application/worldData/generators/hydrology/water/waterMaterialize.py) передаёт в общий маршрут доставки [WaterKindMismatchIssue](../../backend/app/dataModel/hydrology/waterKindMismatchIssue.py). В каждой причине есть исходный UID, обе классификации BasinKind и проверенный путь к WaterBody.kind. При восстановлении модель проверяет точный путь и различие kinds. Декларация определяет kind тела, а producer назначает FALLBACK.

Сверка с [реестром владельца surface codec](../../backend/app/application/worldData/planning/encoding/surfaceManifest.py) дала последний занятый ID 322. Зарегистрированы запись 323 и enum 324. Переиспользованы BasinKind (41), WaterBody (153), ValidatedFieldPath, ModelIdentity и FieldSegment (303–305). Граница проверки — fine-water envelope. Решение о совместимости open-water source V1 остаётся у владельца storage.

[Две регрессии](../../backend/tests/geo1/fine_water/test_kind_mismatch.py) прошли. Реальный fill двух отдельных равновеликих озёр публикует две причины LAKE/OCEAN, два тела LAKE и mapping по UID. Перестановка specs даёт тот же envelope. Сравнение полного результата assembler с emit и без него прошло в validate_only, collect_only и runtime. Проверены аргументы доставки, отсутствие повторной записи в контекст и по одному вызову лога на факт в runtime. При совпадающих kinds диагностики отсутствуют.

Строгий decode и decode_bounded восстанавливают конкретный тип, значения, сообщение, путь и disposition. В новом процессе штатный manifest декодирует весь envelope и повторно кодирует его в исходные байты. Проверены обе dependency refs и admit_result на том же ref. Удаление диагностик нарушает output proof. Decode отвергает равные kinds, чужое поле или корень, неизвестный код и wire ID.

## Следующие причинные вызовы

* Исходный touching-sources тест повторён без изменения fixture. До следующего исключения наблюдались ровно две доставки, для a и b, обе LAKE/OCEAN с FALLBACK и путём kind. Следующий caller — [materialize_water, ветвь WATER_LEVEL_SPILL](../../backend/app/application/worldData/generators/hydrology/water/waterMaterialize.py#L126). Поэтому этот конкретный запуск до публикации union и проверки mapping не доходит.
* SourceAssemblyTests, SourceBedTests и SourceMembershipTests запущены вместе. Все три setUpClass прошли прежний барьер и остановились при подготовке coarse river. Первый причинный caller — [prepare_river_from_inputs, строка 145](../../backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py#L145), передающий ERROR в [_emit_diagnostic, строка 233](../../backend/app/application/worldData/generators/hydrology/rivers/riverPrepare.py#L233). Там создаётся базовый FieldPathError. Результат запуска — 0 выполненных методов, 3 setup errors.

## Полный geo1 discover

Из backend с `PYTHONPATH=.;tests` выполнен `.venv\Scripts\python -m unittest discover -s tests/geo1 -t . -q`. Итог — 894 теста за 82,010 с, 229 errors и 2 failures. Относительно базы 892 / 245 / 1 добавились два теста D2, число записей ERROR уменьшилось на 16, FAIL увеличилось на одну. Записи setup и subtests входят в эти счётчики.

В traceback больше нет вызова старого конструктора для mismatch (прежде 58 записей). В выводе 6 вызовов WATER_LEVEL_SPILL, 3 WATER_CANNOT_HOLD, 2 WATER_TERRAIN_UNRESOLVED и 29 traceback со строкой 233 riverPrepare. Прежний failure остаётся в legacy cascade wire. Дополнительный failure — [проверка исторического digest результата river route](../../backend/tests/geo1/procedural_refinement/test_proposals.py#L160): при первых settings получен `d632ae06…`, ожидается `1ccb025f…`. Эталон сохранён для разбора владельцем. Остановка после D2 mismatch.
