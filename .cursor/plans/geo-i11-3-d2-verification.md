# GEO-I11.3 · отчёт проверки D2 №1–3 и регрессий №4/5

Основание — [принятый scoped D1](geo-i11-3-review-defects.md). Проверка проведена на checkout с HEAD `60f41b2f` и текущими рабочими изменениями.

| Дефект | Результат запуска |
|---|---|
| №1 — ранний отказ | PASS. Для noise, plate и plate-noise штатный capture и адаптер дают принятый вход. Затем одновременно меняются metadata.source_kind на LAKE и z_min на metadata.level. Один PlanBuildFailure содержит ровно две WaterDesignTypeError с корнем NativeCoastlineStrategyInput и кодом WATER_DESIGN_INVALID_PREPARATION_INPUT: continental_field.metadata.source_kind, затем continental_field.metadata.level. Ни layout, ни вычисления plate/noise не вызваны. |
| №2 — admission коллекторов | PASS. При валидном native-вызове наблюдались два экземпляра ValidatorAggregationHelper. У обоих admitted в точности (WaterDesignTypeError,). В каждый переданы WaterDesignTypeError и чужая PolicyTypeError: первая сохраняется, вторая вызывает IssueAdmissionError, snapshot содержит только первую. Наблюдатель конструктора возвращает настоящий коллектор, вход и решения policy проходят штатный путь. Отдельно прошли READY без behavior и проверка независимых причин с одинаковой проекцией пути. |
| №3 — FAILED support | PASS. На всём пути support → resolver → water decision сохраняются внешний WaterDesignTypeError и его содержимое. Без fallback оба режима дают UNRESOLVED. С правилом по FAILED_SUPPORT в validate результат UNRESOLVED, в runtime — DISABLED с ERROR_FALLBACK и provenance по FAILED_SUPPORT. Конкретный тип причины и исходные байты восстанавливаются при decode и decode_bounded. Дополнительно runtime-решение передано через stdin новому Python-процессу: он импортирует SURFACE_MANIFEST, декодирует WaterDesignDecision, проверяет точный класс причины и возвращает побайтно тот же encode. |
| №4 — ограничение геометрии | PASS. Для открытой линии на W 32×32 при max_area_fraction=0.04 получена непустая геометрия размером не более 40 клеток. CoastlineCapNotice с UID line доходит до FineWaterDesignConstraints. Строгий round-trip обоих владельцев сохраняет результат, тип notice и полный W.ref. |
| №5 — ограничение числа плит | PASS. Штатный capture → prepare_native → design_native_coastline при plate_count=1025 строит 1024 центра. Восстановленный FineProceduralWaterDesignDraft сохраняет точный PlateCountAdjustedNotice(requested=1025, effective=1024) и W.ref. При запросе 1024 корректировка отсутствует. |

## Воспроизведение

PowerShell, рабочий каталог `backend`:

```powershell
$env:PYTHONPATH='.;tests'
$cases = @(
  'tests.geo1.coastline_source.test_native_field'
  'tests.geo1.contracts.test_policy_resolver'
  'tests.geo1.coastline_source.test_adapter.CoastlineSourceAdapterTests.test_native_ready_admission_without_behavior_reports_field_before_geometry'
  'tests.geo1.coastline_source.test_adapter.CoastlineSourceAdapterTests.test_native_context_validates_nested_fields_and_join_before_geometry'
  'tests.geo1.coastline_source.test_adapter.CoastlineSourceAdapterTests.test_native_procedural_strategies_bind_exact_window_and_constraints'
  'tests.geo1.authored.test_native_geometry.NativeAuthoredGeometryTests.test_coastline_interior_and_open_cap'
)
.\.venv\Scripts\python -m unittest @cases -q
.\.venv\Scripts\python -m unittest discover -s tests/geo1 -t . -q
```

Адресный запуск: 41 тест, OK.

Полный `geo1`: 892 теста за 73,386 с, `FAILED (failures=1, errors=245)`, exit code 1. Единственный assertion failure — `contracts.cascade.test_legacy.LegacyGenerationTests.test_shared_wire_engine_uses_the_owning_before_validator`. Среди errors — проверка подменённых лимитов seas в authored geometry и сценарий вырожденного озёрного контура. Эти результаты относятся к полному набору; все пять сценариев из таблицы прошли. Статус независимого ревью и пользовательской приёмки фиксируется отдельно.

## Повторная адресная сверка текущего checkout — 2026-11-24

Из `backend` с `PYTHONPATH=.` повторена приведённая выше команда с теми же шестью unittest targets: **42 tests, OK**. Исторический результат D2 (41 tests, OK) и исторический полный geo1 (1 failure, 245 errors) относятся к прежнему checkout; сегодняшний полный geo1 не запускался. В текущем checkout просмотрены `design_native_coastline`, `ContinentalFieldComposer.build_native` и модель `FineProceduralWaterDesignDraft`: entry строит одно поле, сохраняет metadata и z_min; модель восстанавливает floor profile из сохранённых полей. Адресная проверка покрывает все пять ранее указанных сценариев. Отдельной записи пользовательской приёмки I11.3 в доступном owning-плане и связанных отчётах нет. Следующий зависимый срез fine placement preparation остаётся до этого решения закрыт.

## Решение пользователя и следующий контракт — 2026-11-24

Пользователь принял GEO-I11.3 ответом «Ок, принимаю, далее» после отчёта о 42 адресных тестах. Предшествующая запись об отсутствии приёмки фиксирует состояние *до* этого ответа. Fine placement preparation — следующий срез, но его публичная граница P3 в `geo-1-dag-public-contracts.md` помечена DRAFT/OPEN. Owning-план EF-1.2 описывает target-алгоритм и общий fine P2 cutover, но не утверждает отдельные Input/Output/Error, класс, сигнатуру и caller для изолированного следующего среза. По обязательным критериям DAG зависимую реализацию остановили до решения.

**Предложение GEO для координатора `Between domain operations` (thread `01a1ef35-3287-7a12-89e2-76273eaa043d`), OPEN, не согласовано:** публичная операция `DesignedWaterPlacementPreparer.prepare_native(input: NativeCoastlineStrategyInput, draft: FineProceduralWaterDesignDraft, *, selection_policy: WaterFieldSelectionPolicy) -> WaterDesignPreparation` в `application/worldData/generators/terrain/designedWater/preparation/placementPreparation.py`. Input содержит принятое W, constraints, metadata, field recipe, z_min и budget; draft содержит то же W.ref и metadata. Output предлагается как fine-marked `WaterDesignPreparation` из `dataModel/terrain/designedWater/preparation/result.py`: один `PlacementCandidate`, original_area = число уникальных fine-клеток, floor profile и notices. Error — `PlanBuildFailure` с конкретными `WaterDesignTypeError` для адресуемых неверных связей и принятыми доменными причинами для constraint conflict, empty target, shortfall; точный union, пути и disposition требуют согласования ERROR-CONTRACTS. Операция только готовит данные; admission/binding и общий P2 остаются отдельными стадиями. Потребитель — будущий fine P2 caller через DAG; конкретная нода и передача результата OPEN.

**Алгоритм для согласования:** строго ревалидировать input/draft/policy и полные W.ref, metadata, recipe, z_min; проверить required ⊆ allowed и принадлежность клеток W; отобрать fine samples в allowed, включить required; каждая fine-клетка весит 1 fine². Для остальных применить существующий `_wet_score`, порядок `(-score, y, x)` и один prefix с минимальной ошибкой к `allocated_fine2`, при равенстве выбрать меньший prefix. Сохранить notices, floor profile и точный W.ref; отсутствие клеток и дефицит площади обрабатывать по принятой политике, без изменения runtime fallback. Критерии: три стратегии, одинаковое W и чужой W, required/allowed, ties, budget меньше required, пустой результат и shortfall; сопоставить payload/fingerprint на допустимом пути и отсутствие вызова P2 до успеха preparation. Файлы после согласования: указанный preparer, fine result POJO и адресные `backend/tests/geo1/coastline_source/` тесты. Coarse `prepare` и `bind_admission`, семь envelopes, canonical source, Pack, G10-A и DAG bindings этим предложением не переключаются.
