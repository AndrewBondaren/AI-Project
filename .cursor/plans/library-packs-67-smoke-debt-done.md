# Техдолг приёмки library-packs шаги 6–7 (HTTP-smoke 2026-10-16) — DONE

Источник: `library-packs-model-done.md` § «HTTP-smoke приёмка шагов 6–7» →
«Результаты прогона 2026-10-16». Оба дефекта найдены приёмкой, но лежат
**вне зоны шагов 6–7** (locations registry / bundle export). Здесь только
фиксация; исполнение — отдельными атомарными шагами после согласования
(code-gates).

## D1 — `payload_kind: null` гасит settlement target filter

**Блокер.** Любой мир, чья `location_type_registry` прошла persist
round-trip без явного `payload_kind` у settlement-записи, получает 422 на
`generate-settlement`.

| | |
|---|---|
| Симптом | `POST /api/worlds/{w}/locations/{loc}/generate-settlement` → `422 «Location … is not a settlement outdoor target»` — воспроизведено на `world_test_002` (Айронхолд, `system_location_type=settlement`, subtype `city`) |
| Корень | Persist/normalize мира материализует `payload_kind: null` и `is_outdoor: null` в каждую запись `worlds.location_type_registry`. При чтении `payload_kind ∈ model_fields_set` → `_overlay_location_type` берёт world-значение (`None`) вместо engine `PayloadKind.SETTLEMENT` → `merged payload_kind=None` → `named_location_is_settlement_map_site` = False |
| Где | `dataModel/locations/locationType/locationTypeEntry.py` — `serialize_overrides` pop'ит только `is_inhabited`; `locationType/worldLocationTypeRegistry.py` `_overlay_location_type` — merge по `model_fields_set`; persist world row (dump без strip unset) |
| Проверено | `LocationTypeEntry.model_validate({'payload_kind': None})` → поле в `model_fields_set`; на реальной строке `db/game.db` merged `payload_kind=None`, при этом `is_inhabited` унаследован корректно (`IgnoreOnWire` + pop → ключа нет в stored JSON) |
| Асимметрия | `is_inhabited` защищён и не материализуется; `payload_kind`/`is_outdoor` — `DefaultWhenMissing`, пишутся `null`. `is_outdoor` безопасен лишь потому, что его merge — `is not None`, не `fields_set` |
| Затронуто | все pre-payload_kind миры и фикстуры после normalize; блокирует приёмку §2/§6 (generate-settlement smoke `world_test_002`) и любой settlement generate |

**Варианты fix (выбрать при имплементации):**

- (a) `serialize_overrides` в `LocationTypeEntry`: pop `payload_kind`
  (и `is_outdoor`) когда поле не в `model_fields_set` — симметрия с
  `is_inhabited`; authored `null` при этом сохраняется корректно
  (первичная валидация authored JSON его засчитывает);
- (b) merge `payload_kind`/`is_inhabited` по `is not None` вместо
  `model_fields_set` — теряет различение «явный null» у будущих
  authored-override;
- (c) strip unset/null полей на persist world row — шире, затрагивает все
  `DefaultWhenMissing` во всех реестрах; рассматривать как отдельную
  политику, не точечный fix.

## D2 — пустой world-owned пак ломает skeleton export мира

| | |
|---|---|
| Симптом | `GET /api/worlds/{w}/export?level=skeleton` → `422 «UID archive cannot export an empty pack»`; весь export мира отменяется |
| Корень | `export_pack` (`libraryPacks/archiveSources.py`) бросает при `members == []`; вызывается для каждого пака мира. Пустой world-owned пак возникает легально: `instantiate` пака с `missing_dependencies` создаёт instance с 0 members (`created: true`) |
| Воспроизведение | engine-пак с несуществующей dependency → `POST /worlds/{w}/library-packs/instantiate` → instance создан пустым → `export?level=skeleton` → 422; `DELETE` пустого пака восстанавливает export |
| Где | `libraryPacks/archiveSources.py` `export_pack`; instantiate-политика создания пустых instance — `packService`/`remapOps` |

**Варианты fix:**

- (a) world export пропускает пустые world-owned паки (диагностика в
  ответе) — минимальный;
- (b) `instantiate` не создаёт instance, когда все deps missing и членов
  нет — убирает источник пустых паков, но меняет семантику ответа
  (`created`);
- (c) `export_pack` отдаёт валидный архив с `members: []` — тогда
  симметрично должен принимать import-контракт; расширение формата.

Связано: сам факт, что instantiate с полностью missing deps создаёт
`created:true` пак без членов, стоит пересмотреть вместе с (b).

## Шаги имплементации (варианты согласованы 2026-10-16: D1 → (a), D2 → (a))

### Шаг 1 — D1 (a): unset-поля не материализуются в persisted JSON

| | |
|---|---|
| Цель | `payload_kind`/`is_outdoor` не пишутся `null` в stored JSON при отсутствии authored-значения — merge по `model_fields_set` перестаёт видеть фантомный override |
| ТЗ | `docs/tz_locations.md` § `worlds.location_type_registry` (N+1) + § Payload per type |
| Файлы | `backend/app/dataModel/locations/locationType/locationTypeEntry.py` |
| Контракт | `serialize_overrides`: pop `payload_kind`/`is_outdoor`, когда поле не в `model_fields_set` (симметрия с `is_inhabited`); authored `null` сохраняет семантику явного override (`test_world_overlay_preserves_missing_and_respects_explicit_kind`) |
| Проверка | `python tests/test_location_payload.py` (в т.ч. `test_recipe_overlay_survives_world_json_roundtrip`) + round-trip repro: omitted → stored без ключа → merged `payload_kind=SETTLEMENT`; `compileall` |
| Done | round-trip записи без authored `payload_kind` даёт merged `PayloadKind.SETTLEMENT`; suite зелёный |

### Шаг 2 — D2 (a): skeleton export пропускает пустые world-owned паки

| | |
|---|---|
| Цель | один пустой world-owned пак не отменяет `export?level=skeleton` |
| ТЗ | `docs/tz_template_library_packs.md` §4 (UID archive export) |
| Файлы | `backend/app/application/worldData/libraryPacks/archiveService.py` |
| Контракт | `export_world` фильтрует паки без members; guard «cannot export an empty pack» в `export_pack` сохраняется для одиночного экспорта; пропуск виден в диагностике ответа |
| Проверка | repro из D2 (instantiate с missing deps → export) + unittest по libraryPacks/archive; `compileall` |
| Done | пустой пак + `export?level=skeleton` → 200 с диагностикой пропуска |
