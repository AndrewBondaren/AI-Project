# G-1 — анализ переноса размера клетки в POJO ✅ DONE

- Дата: 2026-10-16.
- Статус: выполнен 2026-10-16 по согласованному объёму.
- Родитель: `world-scoped-column-write-done.md`, отдельный шаг G-1 после закрытого W2.

## Реализация и приёмка

- Добавлен `WorldGridSettings` с единственным strict int полем, прежними
  min/multiple ограничениями и существующим источником default. Facade slice,
  `grid_settings(world)`, публичный export и startup guard подключены.
- Прямой `prepare_import` проверяет общий grid-слайс на копии исходного
  mapping до конструктора World; explicit null не теряется. Ручной блок
  размера удалён из `_validate`, остальные technical-проверки сохранены.
- Новые 11 тестов `test_world_grid_settings` закрывают valid/invalid матрицу,
  missing/null/legacy alias, structured errors, scoped isolation/invalidation,
  direct import, bundle preview/apply и HTTP force. Старые W2-гарды обновлены.
- Регрессия: `test_world*.py` 105; `test_import_validation_policy` 11;
  `test_library_packs_5b_import` 11; `test_pack_bake_modes` 20;
  `test_policy*.py` 17; `test_library_world_column_write` 6;
  `test_runtime_world_edit_policy` 13. Все 183 теста прошли. Ранее описанные
  pre-existing ошибки import validation в этом запуске не воспроизвелись.
- ТЗ обновлено: schema/ошибки/coverage, доступность scoped size write,
  `map_subsurface_depth ≥0` по профильному ТЗ. Padding, pack metadata,
  terrain strictness и атомарная очистка в G-1 не изменялись.

## Согласованный объём

Перенести только `worlds.fine_cells_per_map_cell` в небольшой
`dataModel/worldPack/worldGridSettings.py::WorldGridSettings` и facade
`WorldSlice`. Это перенос существующего контракта без изменения допустимых
значений. Состав из одного поля намеренный: общего инварианта размера клетки
с другими текущими technical-полями не найдено.

`grid_bbox_padding` — независимый параметр extent вокруг anchors, а не масштаб
клетки. Его нынешняя проверка лишь `v < 0`: `True` и положительные float
проходят, `None` / строка дают TypeError. Включение его в strict int POJO
изменило бы контракт. Перенос padding и DR-8 (default `2` в generator/model/SQL)
нужно согласовать отдельно; G-1 не меняет его проверки и fallback.

`terrain_chunk_columns` и `map_subsurface_depth` уже принадлежат
`WorldTerrainScalars`; не переносить их и не копировать ограничения.
`world_map_cells_per_tile`, пути/hash/version pack относятся к отдельной
задаче pack metadata. L0 side не зависит от размера macro-cell (WP-10 v2).

## Контракт поля

- Имя wire/SQL: `fine_cells_per_map_cell`, без переименований и SQL migration.
- POJO: frozen, `extra="ignore"`, `SCHEMA_ID="SCH-WORLD-GRID-SETTINGS"`.
- Аннотация `DefaultWhenMissing[int]`, `constrained_field` с `strict=True`,
  `greater_equals=1000`, `multiple_of=1000`.
- Default брать из существующего `dataModel/worldPack/mapCellSize.py`
  (`FINE_CELLS_PER_MAP_CELL_DEFAULT=1000`); нового источника default не создавать.
- Допустимы 1000, 2000, 3000 и т.д.; отклоняются bool, float (включая 1000.0),
  строки (включая "1000"), null, значения <1000 и не кратные 1000.
- Missing полного документа → POJO default. Missing PATCH/scoped-операции →
  колонку не менять. Explicit null отклоняется, не означает reset.
- Legacy `map_cell_size_m` остаётся адаптером facade: новое имя имеет
  приоритет при наличии обоих. Не переносить alias в SQL/dataclass и не
  добавлять legacy alias в scoped resolver.

## Подключение

1. Использовать `worldScalarWire.pojo_wire_keys`, `scalar_wire_from_mapping`,
   `validate_world_row_pojo_columns` через тонкие wrappers нового POJO.
   Добавить `canonical_defaults()` по образцу существующих scalar slices.
2. Зарегистрировать facade multi-column slice с единственным полем.
   Generic facade/scoped resolver уже умеет эту форму; новых веток в
   `worldColumnResolve` / `worldColumnWrite` не требуется.
3. Добавить startup guard в `core/app.py`; runtime accessor `grid_settings`
   в `jsonValidation/worldRow.py` и публичный export по принятому шаблону.
   Массовая миграция generator consumers в G-1 не входит.
4. Подключить контракт к прямому `WorldService.prepare_import` до конструктора
   World, затем удалить ручной блок проверок размера клетки из `_validate`.
   Важный факт: `prepare_import` сам сейчас не вызывает normalize_world,
   хотя вызывается напрямую bundle/preflight/copy-import путями.
   Рекомендуемый способ — общий `merge_world_slice` только для grid-слайса
   на копии исходного mapping, с import ResolveContext, переводом
   `UnresolvedModelError` в `ImportValidationError` с исходными issues.
   Это сохраняет текущую границу остальных слайсов и не добавляет полный
   normalize всего документа в этот метод. Уже нормализованный вход может
   повторно пройти тот же одно-полевой POJO; второго набора правил нет.
5. Не строить grid-wire для этого write-check из уже созданного World:
   `scalar_wire_from_mapping(object)` пропускает None как SQL absence,
   тогда как исходный mapping сохраняет authored null. Explicit null нельзя
   потерять и заменить default перед проверкой.

Create/import/master-PATCH/bundle проходят существующий facade, который
подхватит slice автоматически. Прямой prepare_import получает указанную
явную grid-проверку. Generic scoped write становится разрешён для размера
клетки за счёт регистрации slice.

## Инвалидация и транзакции

`COLUMN_INVALIDATES` уже содержит `fine_cells_per_map_cell → map_cells`.
Не менять реестр: равное значение даёт пустой набор, изменённое — `map_cells`.
Scoped apply не сохраняет и не очищает таблицы: это обязанность caller.
Мастерские `requires_force`, `map_cells_invalidated` и `force` сохраняются.
Route по-прежнему очищает map_cells после сохранения мира. Изменение этой
неатомарности, очистка pack-файлов и новые последствия инвалидации требуют
отдельной задачи; POJO migration их не решает.

## Дубли и расхождения документации

- Удаляется только ad-hoc блок `fine_cells_per_map_cell` из `_validate`.
- Terrain-проверки нельзя просто удалить как эквивалентные дубли:
  `WorldTerrainScalars(terrain_chunk_columns=True)` сейчас даёт `1`, а
  сервис отвергает bool; аналогично нужно отдельно проверить strictness
  остальных int-полей. G-1 не меняет их допустимость.
- В `tz_json_validation.md` technical-раздел пишет `map_subsurface_depth ≥10`,
  но код/POJO допускают 0, а `tz_terrain_generation.md` описывает
  `N_base = world.map_subsurface_depth ?? 0` и surface-only режим.
  При актуализации документации исправить устаревшее ≥10 на ≥0 без изменения
  числовых ограничений кода.
- Уточнить technical-раздел, строку таблицы ошибок и scoped-описание:
  размер клетки переходит в POJO, ошибки становятся структурированными
  ImportValidationError/HTTP 422 вместо service-only текстовой ошибки.
  Формулировки о запрете scoped size write должны стать историческими.

## Проверки при реализации

- Один набор valid/invalid значений на POJO, facade full/PATCH,
  create/import/master-PATCH, прямом prepare_import и scoped resolve/apply.
- Missing/default, explicit null, legacy alias и приоритет нового имени.
- Structured issues: field path, schema ID, code; invalid scoped input
  не мутирует World, invalid service input не сохраняется.
- Scoped size write проходит при невалидной посторонней facade-колонке,
  меняет только размер, сообщает map_cells только при фактическом изменении.
- Master update сохраняет существующие force/no-force/equal-size сценарии;
  хотя бы одна HTTP-проверка подтверждает 422 и structured detail.
- Bundle validate_only/import отклоняют невалидный размер до сохранения,
  включая direct prepare_import path, без добавления новых side effects.
- Startup guard и World default совпадают с POJO/default source.
- Обновить W2-тесты, которые сейчас требуют отсутствия размера в
  WORLD_SLICE_BY_KEY и отклонения scoped-записи; сохранить отдельный guard
  COLUMN_INVALIDATES ⊆ поля World (он по-прежнему независим от facade).
- Regression: world column/write, world-row slices, import validation,
  bundle/copy import и pack bake; учесть ранее описанные pre-existing
  bundle-тесты и проверять их актуальное состояние при запуске.

## Done

Допустимость размера имеет единственного владельца — WorldGridSettings.
Все перечисленные write-входы используют его через общий resolver;
ручных int/min/mod проверок размера в WorldService нет. Scoped write
разрешён, возвращает корректные последствия и не делает I/O. Padding,
terrain strictness, pack metadata и атомарная очистка остаются за границей
этого шага. План/ТЗ и тесты отражают новое покрытие.
