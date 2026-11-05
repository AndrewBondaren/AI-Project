# GEO-I11.3 — проверка доставки notices №4 и №5

Проверка от 2026-11-05, checkout `master`, HEAD `24d059b5`. Область проверки — принятый D1 по №4 и №5.

## №4 — PASS до FineWaterDesignConstraints

Открытая линия `(4,4)–(12,4)` с UID `line` на окне 32×32 и `max_area_fraction=0.04` дала footprint размером не более 40 клеток. По флагу `capped` растеризатор создал один `CoastlineCapNotice(code=WaterPreparationCode.CAP_REACHED, source_uid="line")` в `AuthoredWaterGeometry.notices`. Метод `CoastlineConstraintPreparer.prepare_native` передал эту коллекцию в `FineWaterDesignConstraints.notices`. Строгий dump/restore каждого владельца подтвердил точный класс, код, UID, исходный `pre_hydrology_ref` и равенство модели. Клетки constraints совпали с footprint. [Producer](../../backend/app/application/worldData/placement/adapters/waterGeometry/nativeGeometry.py#L30) · [Передача в constraints](../../backend/app/application/worldData/generators/terrain/designedWater/preparation/coastlineConstraintPreparer.py#L56)

## №5 — PASS до FineProceduralWaterDesignDraft.field.notices

На окне 32×32 запрос `plate_count=1025` дал 1024 центра и один `PlateCountAdjustedNotice(code=WaterDesignIssueCode.PLATE_COUNT_ADJUSTED, requested=1025, effective=1024)` в `PlateLayout.notices`. На явно собранном `NativeCoastlineStrategyInput` вызов `design_native_coastline` перенёс notice через `FineContinentalField.notices` в `draft.field.notices`. Строгий dump/restore всего draft подтвердил равенство модели, конкретный класс, значения notice и ссылку поля на то же окно. При запросе ровно 1024 плит коллекция layout была пуста. [Producer](../../backend/app/application/worldData/generators/terrain/designedWater/fields/plateFieldGenerator.py#L55) · [Передача в поле](../../backend/app/application/worldData/generators/terrain/designedWater/fields/continentalFieldComposer.py#L43) · [Сборка draft](../../backend/app/application/worldData/generators/terrain/designedWater/strategies/procedural/nativeCoastlineDesign.py#L8)

## Штатный вход — границы воспроизведения

- **№3.** При `capture(strategy=PLATE)` вызов дошёл до стадии `PRIORITY`. Метод `read` на строке 67 вызвал `issue(...)` для отсутствующего факта. Строка 18 попыталась создать `FieldPathError` и получила `TypeError: FieldPathError requires a named concrete domain subclass`. Адаптер ещё не вызывался. [Caller](../../backend/app/application/policy/policyRead.py#L67)
- **№2.** При отдельно собранном типизированном `READY` admission, полном fine-окне и совпадающем `expected_window` вызов `CoastlineWaterSourceAdapter.prepare_native` остановился на первом `ValidatorAggregationHelper()`. Исключение — `TypeError: ValidatorAggregationHelper.__init__() missing 1 required positional argument: 'admitted'`. Это граница до сравнения ref, подготовки геометрии и возврата принятого входа. [Caller](../../backend/app/application/worldData/generators/terrain/designedWater/preparation/coastlineWaterSourceAdapter.py#L119)

Таким образом, сквозной путь через admission остаётся заблокирован для обеих цепочек. №1 на успешном входе №5 не проявился.

## Повтор адресных тестов

Из каталога `backend` выполнено:

```powershell
$env:PYTHONPATH='.;tests'
.\.venv\Scripts\python -m unittest -v tests.geo1.authored.test_native_geometry.NativeAuthoredGeometryTests.test_coastline_interior_and_open_cap tests.geo1.coastline_source.test_native_field.NativeFieldTests.test_plate_adjustment_survives_native_draft_restore
```

Результат — `Ran 2 tests in 2.019s`, `OK`. [Тест №4](../../backend/tests/geo1/authored/test_native_geometry.py#L69) · [Тест №5](../../backend/tests/geo1/coastline_source/test_native_field.py#L73)
