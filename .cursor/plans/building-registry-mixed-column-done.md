# Building registry — гетерогенная колонка (pointer + embedded layout) — DONE

Источник: D9 из [`library-packs-b3-review-debt-done.md`](library-packs-b3-review-debt-done.md).
ТЗ: [`docs/tz_building_generator.md`](../../docs/tz_building_generator.md) §5.2/§6.2,
[`docs/tz_json_validation.md`](../../docs/tz_json_validation.md) § GV-3 (facade slices),
`docs/tz_city_generation_technical_debt.md` CITY-T-5o/2b (interim overlay).

## Проблема

`worlds.building_template_registry` фактически хранит **два вида строк**:

| Вид | Признак | Потребитель |
|---|---|---|
| uid-pointer | `system_template_uid` | `BuildingTemplateRegistryEntry` → `layouts_for_world`, `_ensure_registry` |
| embedded layout | `system_name` + `display_name` (+ `main_building`/`secondary_buildings`) | `PlotLayoutTemplate` → `world_building_layout_overrides` → packing |

ПОJO `WorldBuildingTemplateRegistry` объявляет только pointer-вид
(`system_template_uid: StrictOnWire`). Следствия:

1. `normalize_world` → `_merge_registry_list` → `resolve_root_list`
   отклоняет мир с layout-строками → **`worlds.update` любого поля такого
   мира падает 422**, `import_from_json` — ImportValidationError, bundle
   `normalize_world` (`worldBundleService.py:109`) — то же.
2. `_ensure_registry` (`buildingTemplateLibraryService.py:217`) читает
   реестр через entry-POJO — на смешанной колонке падает; а его patch —
   полная замена колонки — потерял бы layout-строки, если бы дошёл.
3. Remap-адаптеры уже ходят repo-write именно из-за этого (комментарий в
   `_RegistryPointerMixin`) — обход долга, а не его снятие.

## Целевое состояние

Колонка — объявленно гетерогенная: **дискриминатор = наличие
`system_template_uid`** (тот же, что в `world_building_layout_overrides`
и remap-коде). Один union-POJO — единственный контракт:

```python
BuildingRegistryRow = Annotated[
    Union[
        Annotated[BuildingTemplateRegistryEntry, Tag("pointer")],
        Annotated[PlotLayoutTemplate, Tag("layout")],
    ],
    Discriminator(_row_tag),   # "system_template_uid" in row → pointer
]
```

`WorldBuildingTemplateRegistry.root: list[BuildingRegistryRow]` +
`pointers` / `layouts` фильтры — читатели не дискриминируют вручную.

Замечания по дизайну:

- Callable `Discriminator`+`Tag` (pydantic 2.13) — детерминированный
  выбор по ключу, не «smart union по совпадению»: строка с обоими
  ключами — pointer (то же правило, что в `worldRow`/remap).
- Mусорная строка (ни pointer, ни layout) — ошибки layout-члена union
  в отчёте с `path=(registry, index)` — fail loud, как сейчас.
- Normalize пишет `model_dump` обеих форм — layout-строки при update
  материализуют defaults (та же семантика, что у членов-боди и всех
  facade-слайсов).
- `relief_template_registry` не трогаем — там только pointer-вид.

## Шаг 1 — правка ТЗ §5.2

**Цель.** Зафиксировать в контракте колонки второй вид строк до кода
(gate: «нет раздела — сначала правка ТЗ»).

**ТЗ.** `tz_building_generator.md` §5.2 — дополнить: колонка хранит
pointer-строки и world-override layout-строки (interim, CITY-T-2b/5o),
дискриминатор `system_template_uid`, потребители идут через union-POJO.

**Файлы.** `docs/tz_building_generator.md`.

**Проверка.** Глазами — формулировка покрывает оба вида и дискриминатор.

**Done.** §5.2 описывает гетерогенность; ссылка из кода валидна.

## Шаг 2 — failing tests смешанной колонки

**Цель.** Воспроизвести D9 на всех публичных путях записи до фикса.

**ТЗ.** `tz_building_generator.md` §5.2 (после шага 1), §6.2.

**Файлы.** Новый `backend/tests/test_building_registry_mixed.py`
(стиль фикстур — `test_world_row_t28.py` / `test_library_packs_4b.py`).

**Покрытие (red):**

- `world_service.update` мира с layout-строкой + pointer-строкой —
  успех, обе строки сохранены (сейчас 422).
- `world_service.import_from_json` с тем же миксом — принимается.
- `_ensure_registry`/добавление pointer-строки — layout-строки мира не
  теряются (сейчас падение на resolve).
- `world_building_layout_overrides` возвращает layout-строки, pointer
  не протекает; pointer-only мир → `[]`.
- Строка-«гибрид» (оба ключа) → pointer-семантика; мусорная строка →
  ошибка валидации с индексом.

**Проверка.** `python -m unittest tests.test_building_registry_mixed` —
ожидаемые падения, подтверждающие баг.

**Done.** Красные тесты закоммичены вместе с реализацией шага 3
(один PR), падения задокументированы в отчёте шага.

## Шаг 3 — union-POJO + typed-потребители

**Цель.** Колонка валидна для обеих форм; читатели/писатели typed.

**ТЗ.** `tz_building_generator.md` §5.2; `tz_json_validation.md` GV-3.

**Файлы.**

- `app/dataModel/locations/structure/building/worldBuildingTemplateRegistry.py`
  — `BuildingRegistryRow` union, `root`, `pointers`, `layouts`.
- `app/application/worldData/buildingTemplateLibraryService.py` —
  `_registry_entries` → `reg.pointers`; `layouts_for_world` /
  `export_bodies_for_world` — по указателям как раньше;
  `_ensure_registry` — append pointer к полному `model_dump` `reg.root`
  (layout-строки сохраняются при replace-семантике patch).
- `app/application/jsonValidation/worldRow.py` —
  `world_building_layout_overrides` → `building_template_registry(world)
  .layouts` + `plot_type_defaulted` warning-цикл; ручная дискриминация и
  per-row `resolve_model` уходят (POJO владеет строкой).
- `domainAdapters.py` — без правок: `_remap_structure_refs` уже typed
  (шаг 2 debt-плана), pointer-early-exit совпадает с дискриминатором.

**Контракт.** `WorldBuildingTemplateRegistry.root` —
`list[BuildingRegistryRow]`; `_registry_entries` возвращает только
`BuildingTemplateRegistryEntry` (signature не меняется); write-path
всех слоёв (`update`/`import`/bundle/pack remap) принимает микс.

**Проверка.** Шаг-2 тесты зелёные + регрессия:
`python -m unittest tests.test_building_registry_mixed
tests.test_library_packs_4a tests.test_library_packs_4b
tests.test_library_packs_b3 tests.test_library_packs_schema
tests.test_world_row_t28 tests.test_bundle_remap
tests.test_import_validation_policy` + `python -m compileall app`.

**Done.** Микс проходит все пути записи; потребители typed; ни один
`worlds.update` не падает на мире с layout-строками.

## Не шаги

- `StructurePackAdapter.remap_world_refs` — после debt-шага 2 уже typed;
  перевод на `reg.root`-итерацию — опционально, не нужно для фикса.
- Миграция layout-строк из колонки в отдельный механизм (pack-era) —
  CITY-T-2b закрытие, не этот план.
