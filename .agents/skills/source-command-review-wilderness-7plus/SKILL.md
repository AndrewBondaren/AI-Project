---
name: "source-command-review-wilderness-7plus"
description: "Ревью реализации шагов 7 и выше плана wilderness-regions-mechanic (7, 7b, 8, 9a–c, 10a–c) против контрактов плана и ТЗ. Продолжение ревью 0–7 (wilderness-regions-review-debt.md). Аналитика + находки, код не пишет. Новый чат: /review-wilderness-7plus."
---

# source-command-review-wilderness-7plus

Use this skill when the user asks to run the migrated source command `review-wilderness-7plus`.

## Command Template

# Ревью кода: wilderness шаги 7+

Это **аналитическая задача — код не писать и не править**. Только чтение,
сверка, отчёт. Правило no-code-until-asked действует полностью.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT,
потом код, потом выводы.

## Прочитать до первого вывода

1. [`.cursor/plans/wilderness-regions-mechanic.md`](../plans/wilderness-regions-mechanic.md) —
   **SoT**: §4 строки 7, 7b, 8, 9a, 9b, 9c, 10a, 10b, 10c (цель/ТЗ/файлы/
   проверка каждого); §5 #5 (L0/L2), #6 (hydro-индекс), #7 (precedence,
   worldEdit), #8 (store/overlay/tombstone/revision-check), #11 (consumer,
   прогресс, частичный переход, морфинг); уточнения после таблицы (7b,
   шаг 8 приёмка, UID-инвариант, WR-TD-1, shape_kind).
2. [`.cursor/plans/wilderness-regions-review-debt.md`](../plans/wilderness-regions-review-debt.md) —
   прецедент ревью 0–7: формат находок → шагов; не дублировать уже
   зафиксированные находки.
3. [`docs/tz_map_light_bake.md`](../../docs/tz_map_light_bake.md) — § Регионы
   покрытия целиком (› L0/L2, › Declaration и suitability, › Состояние и
   переходы, › Identity, › Пересечения и приоритет, › Реестр и CoverageResolver),
   § Домены terrain_masks, § Plugin map, § Корни JSON.
4. [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) —
   § `WildernessRegionEntry`, § Region state store, § Region state overlay,
   § L2 open-land hills, § Fine terrain column.
5. [`docs/tz_runtime_world_edit_policy.md`](../../docs/tz_runtime_world_edit_policy.md) —
   worldEdit-контракт для 10c; [`docs/tz_json_validation.md`](../../docs/tz_json_validation.md) —
   `validate_only`/REF-W/`RegistryKey` для 9b/WR-TD-1.
6. Правила (нарушение кодом = находка):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/code-gates.mdc`](../rules/code-gates.mdc)
   - [`.cursor/rules/class-size-limit.mdc`](../rules/class-size-limit.mdc)
   - [`.cursor/rules/bulk-sql.mdc`](../rules/bulk-sql.mdc)
   - [`.cursor/rules/contract-creation.mdc`](../rules/contract-creation.mdc),
     [`.cursor/rules/type-kind-str-fields.mdc`](../rules/type-kind-str-fields.mdc)
     — ключи `TerrainKey`, не `str`; `cause`-enums.

## Что ревьюить (карта кода по шагам)

- **7** — `materialize/terrainBatchOrchestrator.py` (точка врезки между
  upsample и `place_hills`), `landcover/finePaint.py`,
  `dm/worldPack/wire/fineTerrainChunkWire.py` (`region_uid`).
- **7b** — `generators/terrain/hills/hillPlacement.py`,
  `relief/sample/openLandTerrains.py`, оркестратор; `TerrainRegistryEntry.hills`,
  `supports_open_land_grade`, `open_land_profile`; canonical defaults.
- **8** — `dm/worldPack/meta/wildernessRegionEntry.py`, `worldPackManifest.py`,
  `pack/bake/wildernessRegionIndex.py`, `pack/io/worldPackWriter.py`,
  `pack/read/wildernessRegionReadService.py`, `render/regions/regionOutline.py`,
  `api/routes/map.py` (thin endpoints); UID-инвариант (`region_seed_xy` vs
  `seed_xy`, уникальность всех uid, коллизия → отказ).
- **9a** — `0001_initial.sql` `region_states`, `db/models/regionState.py`,
  `db/repositories/iRegionStateRepository.py` (bulkSql? single-writer?).
- **9b** — `dm/regions/regionState.py` (typed `TerrainKey`? `history`
  append-only? `cause`-enum?) + revision-check в `landcover/collect.py`.
- **9c** — `pack/read/regionStateOverlay.py` + точка вызова (один фасад?
  ниже patch? `terrain_delta` сверху? только `system_terrain`?
  `overlap_rerank_deferred` лог?).
- **10a** — `regions/stateChange/{consumer,progress,history,morphEffects}.py`
  + `contracts.py`: single-writer? scorer без таблицы A→B? гистерезис?
  child-регион? `elapsed_ticks` комментарий-заглушка? эффекты на
  materialize, не read?
- **10b** — `maskDomainId.py` (FORESTS/PLAINS удалены?), `MASK_DOMAIN_CONTRIBUTOR`
  → LANDCOVER, `terrainZ.py` ×2 перепайка, `LandcoverRegionsCategoryPolicy`,
  `default_*` — wire-алиасы (не дубли значений).
- **10c** — worldEdit операции `declared_regions[]`, `validate_only` ветка,
  tombstone через consumer (не repo напрямую), одинаковое решение в обоих
  режимах.

## Что проверить (checklist)

### A. Код ↔ ТЗ контракт

- Каждый шаг реализует контракт своей строки ТЗ — не «почти»: поля,
  семантика, границы (overlay только `system_terrain`; entries — индекс,
  не SoT; single-writer; tombstone-политика).
- Имена/типы: `region_uid`, `entry_type`/`current_type` = `TerrainKey`
  (WR-TD-1), `state_fingerprint`, статусы entries, `region_seed_xy`/`seed_xy`
  разделение UID-источников (UID-инвариант шага 8).
- Строгая типизация: `*_type`/`*_kind`/`cause` — `TerrainKey`/StrEnum,
  не голый `str` (`type-kind-str-fields`); `str` только с пометкой в ТЗ.

### B. Инварианты архитектуры

- Одна формула членства L0/L2 (не две геометрии); одна точка правки в
  `build_tile_surface_state`; upsample = fallback-роль.
- Победитель клетки — только `regionPrecedence` (нет своих сравнений в
  L2/orchestrator).
- Каналы DET-1 (`seed`/`claim`/`edge`/`density`/`region_seed_xy`) —
  `seed_root`, без `bake_seed`/`random()`.
- Детерминизм: partial == full bake; sorted/min tie-breaks; нет
  `next(iter(set))`-паттернов; нет scope-зависимых uid.
- Single-writer `region_states`: записи только из `StateChangeConsumer`
  (grep write-путей repo).
- Hydro: preserve-роли не трогаются paint'ом; hydro-индекс — read-only
  (не выдуманные entries — уточнение шага 8).
- Классы ≤ 300 строк; bulk-записи — только `bulkSql`.

### C. Ошибки и границы

- Early-returns с утечкой stale `region_uid` (паттерн находки 2 ревью 0–7 —
  проверить на новых путях L0/L2/read).
- Немые fallback'и: `next(iter())`, `.get() or default`, `str`-сравнения
  uid, сортировки без канонического ключа.
- Пустые `None`-ветки там, где контракт требует WarningError.
- Overlay: не подменяет `system_material`/роли/z; не пишет в пак;
  `terrain_delta` выше.
- State machine: `pending_target` смена → reset; порог → history+лог;
  отсутствующий домен → `None` переживается.
- worldEdit: rename → новый uid + orphan-tombstone (не переиспользование);
  remove → tombstone через consumer.

### D. Регрессии и обещания плана

- Пометки «выполнен» в плане vs факт: что заявлено сделанным, но по коду
  не доделано (или наоборот — код есть, статуса нет).
- «Вне scope» пункты плана/ревью не протащены в реализацию (file-per-region,
  NamedLocation как declare-path, морфинг в реку/море).
- Заглушки с обязательным комментарием (`elapsed_ticks`, `flora.*`,
  `ForestComposition` — иначе находка).

## Формат отчёта

```markdown
# Ревью wilderness шагов 7+ — {дата}

## Вердикт
{соответствует контракту / есть дефекты / блокеры}

## Находки
| # | Шаг | Severity (blocker/major/minor) | Что | Файл:строка | Контракт |
|---|---|---|---|---|---|

## Подтверждённые факты
{что проверено и сошлось}

## Вопросы разработчику
{что нельзя решить без уточнения}
```

Результат — отчёт в чат **и** предложение сформировать
`.cursor/plans/wilderness-regions-review-debt-7plus.md` по образцу
ревью 0–7 (таблица находок → шаги), если мастер согласует.

## Границы

- Код не править, ТЗ не править, план не править — **только отчёт**.
- Находку-предположение верифицировать по коду (file:line), не по
  памяти плана.
- Не коммитить, не запускать backend.
- Если находка требует правки ТЗ/плана — зафиксировать вопросом,
  решение принимает разработчик.
