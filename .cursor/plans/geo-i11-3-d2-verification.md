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
