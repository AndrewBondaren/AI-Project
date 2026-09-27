---
name: "source-command-impl-loc-t-2"
description: "Имплементирует LOC-T-2: ранг размера поселения (small/medium/large), rename system_city_size, footprint = subtype × rank. Новый чат: /impl-loc-t-2."
---

# source-command-impl-loc-t-2

Use this skill when the user asks to run the migrated source command `impl-loc-t-2`.

## Command Template

# Имплементация: LOC-T-2 ранг размера поселения

Это **явная просьба писать код** (слои плана LOC-T-2). Правило no-code-until-asked на этот чат не действует, пока задача не сдана.

Ты новый агент: **не** опирайся на чужую память сессии. Сначала SoT, потом код, потом пиши.

## Прочитать до первой правки

1. [`.cursor/plans/loc-t-2-settlement-size.md`](../plans/loc-t-2-settlement-size.md) — **архитектура и порядок**; не отклоняться.
2. [`docs/tz_locations.md`](../../docs/tz_locations.md) § **Размер поселения (LOC-T-2)** — продукт.
3. [`docs/tz_city_generation.md`](../../docs/tz_city_generation.md) §1.1, §6.1, §9.3.
4. Правила (нарушение = стоп, не «потом починим»):
   - [`.cursor/rules/dataModel-no-hardcode.mdc`](../rules/dataModel-no-hardcode.mdc)
   - [`.cursor/rules/pojo-world-row-wire.mdc`](../rules/pojo-world-row-wire.mdc)
   - [`.cursor/rules/layer-boundaries.mdc`](../rules/layer-boundaries.mdc)
   - [`.cursor/rules/json-validation-architecture.mdc`](../rules/json-validation-architecture.mdc)
   - [`.cursor/rules/project-context.mdc`](../rules/project-context.mdc) — DAG / backend / commit / schema = только `0001`

План важнее догадок. Противоречие план↔ТЗ — остановиться и спросить мастера.

## Цель

Морфология и размер — **два словаря**. `village` + `small` валидно. `village` + `village` → 422. Метры footprint = `footprint_by_size[subtype][size]`. Инвариант: малый город > большая деревня.

## Жёсткие запреты — хардкод и кривой dataModel

Это не «стиль». Параллельный литерал или мёртвый POJO = **критический баг**, задача не сдана.

### Хардкод (запрещено)

- `_DEFAULT_*`, `{"hamlet": 0.25, ...}`, `or "hamlet"`, `or "town"`, `or "medium"`, `return 1.0` в `footprint.py` / assembler / outdoor / overlay / tests helpers, если то же есть на POJO (`canonical_defaults`, field default, `footprint_by_size`).
- `dict.get("footprint_multiplier")` / `row.get("system_city_size")` вместо typed полей.
- Второй список рангов или множителей в generator, jsonValidation, db seed, fixture Python, debug script.
- `uses_settlement_fine_footprint`: ранг `small`/`medium`/`large` **не** признак поселения (иначе geographic станет settlement).
- Копипаст таблицы множителей в ТЗ «для удобства» — SoT уже в locations; в коде таблица **один раз** на engine subtype POJO.

```python
# ❌ BAD
mult = {"small": 0.25, "medium": 0.5}.get(size, 1.0)
size = skeleton.system_city_size or "hamlet"

# ✅ GOOD
mult = resolve_settlement_footprint_multiplier(subtype, size, location_types(world), settlement_sizes(world))
```

### Некорректный dataModel (запрещено плодить)

- Оставить `WorldCitySizeRegistry` **и** добавить `WorldSettlementSizeRegistry` (два SoT).
- `SettlementSizeEntry` с `footprint_multiplier` «на всякий случай» + `footprint_by_size` на subtype (два места метров).
- Alias-модель `CitySizeEntry = SettlementSizeEntry` с old+new полями.
- Параллельные `LocationSize` / `SettlementScale` / `FootprintBand` без плана.
- POJO без `SCHEMA_ID` / без `WireFieldPolicy` на wire-полях / без `canonical_defaults()`, который никто не зовёт.
- Резолв в `jsonValidation` словарём, пока POJO пустой декоратор.
- Дубль `typical_district_types` рецепта ради footprint.
- N+1 ключи морфологии (`village`, `city`) в size registry «чтобы старые фикстуры жил».

Целевой контракт POJO — **только** план §2:

| Модель | Держит | Не держит |
|---|---|---|
| `SettlementSizeEntry` | `system_size`, `display_size` | множитель, map_cells, морфологию |
| `WorldSettlementSizeRegistry` | упорядоченные ранги `small/medium/large` | таблицу метров |
| `LocationTypeSubtypeEntry.footprint_by_size` | метры ранга для **этого** subtype | список рангов мира |

Helper `resolve_settlement_footprint_multiplier` живёт **рядом с registry POJO** (dataModel), consumers тонкие. Не копия helper в assembler «чуть другими дефолтами».

После слоя A: grep `hamlet`, `system_city_size`, `footprint_multiplier_defaults`, `city_sizes(` — в затронутых модулях нулей, кроме комментария «legacy» если мастер явно оставил один shim на один релиз. **Shim не плодить по умолчанию** (план: breaking, recreate).

## Прочие запреты

- Не LOC-T-1 (infer type) в этом чате, если не влезет в тот же `prepare` **без** расползания. Не блокировать LOC-T-2 ожиданием LOC-T-1.
- Не CITY-T-5, не packing C22, не DAG `engine/nodes/`.
- Не стартовать backend. Не коммитить, пока мастер не скажет.
- Не `0002_*.sql`. Rename колонок — `0001_initial.sql` + `db/models`.
- Генераторы **pure sync**. Мир для реестра — через `worldRow`, не SQL в planner.
- Не принимать wire `min_city_size` / `system_city_size` после rename (breaking).

## Порядок (слои целиком)

Контракты — только план §2. Канон множителей — таблица в плане (TZ), в коде на `canonical_engine()` subtypes.

| Слой | Что | Готово когда |
|---|---|---|
| **A** dataModel | Rename/replace size POJO; `footprint_by_size` на subtype; helper + инвариант village≺city; default omit → medium **из POJO** | Unit: city+small > village+large; village+village helper error; **нет** multiplier на size entry |
| **B** slice + SQL | `0001` + `World.settlement_size_registry` + `worldSlices` + `settlement_sizes()`; убрать `city_sizes` | validate_schema; один world_key |
| **C** NL wire | `system_settlement_size` на Bundle/SQL/skeleton; duplicate-value 422; size на geographic → 422 | Import unit |
| **D** consumers | `footprint.py` и все call sites: `(subtype, size)`; policy footprint без ранга как site; placement `min_settlement_size`; overlay | grep старых имён в backend/app = 0 |
| **E** fixtures + тесты | `world_test_gen.json` registry + `size: small` на city; канон шаблонов порта `medium`; узкие unit | Чеклист recreate DB мастеру |

## Стиль

Минимум файлов. Не рефакторить planner «заодно». Узкие unit, не раздувать `debug_settlement.py`. После слоя: что сделано / grep хардкода / что осталось / recreate DB после B.

## Старт

Прочитай план §1–4 и текущие `CitySizeEntry`, `WorldCitySizeRegistry`, `LocationTypeSubtypeEntry`, `footprint.py`, `worldSlices.py` (`city_size_registry`), `BundleNamedLocation`, `PlacementConditionType`, `locationFootprintPolicy.py`. Затем слой A. Если тянет оставить старую модель «совместимости» — **не делать**, спросить мастера.
