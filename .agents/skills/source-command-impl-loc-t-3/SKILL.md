---
name: "source-command-impl-loc-t-3"
description: "Имплементирует LOC-T-3: AABB-разведение поселений с запасом, ERROR лог (uid/size/z), occupancy больше footprint иначе раньше в locations[]. Новый чат: /impl-loc-t-3."
---

# source-command-impl-loc-t-3

Use this skill when the user asks to run the migrated source command `impl-loc-t-3`.

## Command Template

# Имплементация: LOC-T-3 разведение поселений

Это **явная просьба писать код** (слои плана LOC-T-3). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/loc-t-3-settlement-volume-separation.md`](../plans/loc-t-3-settlement-volume-separation.md) — **архитектура и порядок**; не отклоняться.
2. [`docs/tz_locations.md`](../../docs/tz_locations.md) § **Разведение поселений (LOC-T-3)** — продукт (предикат, приоритет, **таблица лога**).
3. [`docs/tz_world_pack_storage.md`](../../docs/tz_world_pack_storage.md) WP-21 (occupancy, не 422).
4. [`docs/tz_logging.md`](../../docs/tz_logging.md) sink `jsonValidation` / `resolve`.
5. Правила (нарушение = стоп):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/json-validation-architecture.mdc`](../rules/json-validation-architecture.mdc)
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — DAG / backend / commit / schema = только `0001`
   - [`.cursor/rules/dag-generator-interface.mdc`](../rules/dag-generator-interface.mdc)

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

Два settlement map-site: AABB `territory_volume` + запас XY/Z. Конфликт **не** валит import. Мир 200, обе NL в SQL. Карту занимает победитель. ERROR лог полный: uid, размер, z.

## Жёсткие запреты

- **Не HTTP 422** на этот конфликт. Не `SETTLEMENT_VOLUME_SEPARATION` как reject import.
- Не удалять проигравшего из `named_locations`. Не чистить его `map_x/y/z`.
- Не `deck` района, не climate z-band, не `LocationLevel`.
- Не LOC-T-1 / LOC-T-2 reopen. Не CITY-T-5. Не C23 FK. Не L0 `radius_light(None)`.
- Не DAG `application/engine/nodes/`. Не стартовать backend. Не коммитить, пока мастер не скажет.
- Не `0002_*.sql`. Не колонка ordinal «заодно» (план: v1 без неё).
- Литералы `50` / `1` только `Field(default=…)` на `TerritoryVolumePolicy`. Gate/generate читают POJO.
- Tie-break **не** `location_uid` и не `created_at`. Победитель: больше `footprint_side_fine`, иначе меньший индекс `locations[]`.
- Occupancy **не** в generator packing (C22). Фильтр на callers: index / territory volumes / C11+C23 оркестратор — тонкий список occupant’ов.
- Лог: не `print`, не только `packBakeLog`. Sink `jsonValidation` / `resolve`. Голый `getLogger` в route запрещён.

```python
# ❌ BAD
if abs(a.map_z - b.map_z) < 50: raise HTTPException(422, ...)
winner = min(a.location_uid, b.location_uid)

# ✅ GOOD
if volumes_conflict(vol_a, vol_b, TerritoryVolumePolicy.canonical_defaults()):
    log_settlement_volume_separation(...)  # ERROR, uid/size/z
occupants = pick_occupants(...)  # footprint then declaration_index
```

## Лог (обязательные поля)

SoT — таблица в TZ LOC-T-3. Событие без **uid / размера / z обоих** — не сдано.

| Обязано | Поля |
|---|---|
| uid | `winner_uid`, `loser_uid` |
| размер | subtype, rank (`winner_size` / `loser_size`), `side_fine` |
| z | `map_z` пина + `z0`/`z1` volume |
| ещё | `reason` = `footprint` \| `declaration_order`; `empty_*`; `min_xy`/`min_z` |

`msg` и `extra` несут те же числа. Префикс `json_validation | settlement_volume_separation`. Уровень **ERROR**.

## Порядок (слои целиком)

Контракты — только план §2 и таблица лога в TZ.

| Слой | Что | Готово когда |
|---|---|---|
| **A** POJO + pure | `min_settlement_separation_xy/z` на `TerritoryVolumePolicy`; `empty_inclusive`; `volumes_conflict`; `pick_occupants` | Unit: overlap; встык XY; empty_z=50 ok; large бьёт medium; равные medium — первый индекс; **нет** 422 |
| **B** лог | helper в `jsonValidation`; extra = таблица TZ | Unit ловит ERROR с uid/size/z |
| **C** persist gate | `NamedLocationService.import_from_json` / create / update: persist **все**, лог пар, не reject | Import overlapping → 200 + ERROR |
| **D** occupancy callers | `locations_index` / settlement contributor / `territory_volumes_by_location` (+ C11/C23 caller, не DAG) фильтруют occupants | Проигравший в SQL, не на L0 |
| **E** тесты | равные medium — первый occupant; large вторым — large occupant; разведённые XY — без ERROR | grep литералов 50/1 в gate = 0 |

Фикстура `world_test_gen.json`: пины (2,2)/(2,6) **не обязаны** разъезжаться. Оба medium → Айронхолд на карте, Амберпорт SQL + ERROR. Развести пины только если мастер явно просит оба generate.

## Стиль

Минимум файлов. Не рефакторить planner «заодно». Узкие unit в `backend/tests/`, не `debug_settlement.py`. После слоя: что сделано / grep хардкода / что осталось. Не recreate DB (нет schema).

## Старт

Прочитай план §1–4 и текущие `TerritoryVolumePolicy`, `locationTerritoryVolumes.py`, `locationFootprintPolicy.py` (`is_settlement_map_site`), `NamedLocationService`, `locationsIndexBake.py`, `jsonValidation/settlementSizeResolve.py` (образец лога). Затем слой A.
